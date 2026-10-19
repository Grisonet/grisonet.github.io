#!/usr/bin/env python3
"""Coletor do painel "Projeção do 2º turno" (GR Data).

A cada ciclo:
  1. lê a lista de seções de cada UF no TSE (arquivo-urna/<pleito>/config) e vê quais já chegaram;
  2. baixa, de cada seção nova, o aux.json, o arquivo de assinaturas (.vsc) e o boletim (.bu.dat);
  3. confere a cadeia de integridade (integridade.py) num pool de processos — boletim que não
     confere fica de fora e é listado no snapshot;
  4. passa a seção para o modelo de cada disputa (Presidente + governadores com 2º turno);
  5. grava <saida>/snapshot.json + dados.csv de cada disputa e serve por HTTP com CORS.

Só stdlib. Seções já lidas ficam em cache (secoes.jsonl), então reiniciar não baixa tudo de novo.

  python3 coletor.py                    # 2º turno de verdade (pleito 3221)
  ENSAIO=1 UFS=ac,rr python3 coletor.py # ensaio com o 1º turno (pleito 3220), poucas UFs
  RELAY=1 python3 coletor.py            # só serve o que receber por PUT (Railway)
"""
import concurrent.futures, csv, hashlib, hmac, io, json, os, re, threading, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

here = os.path.dirname(os.path.abspath(__file__))
ENSAIO = os.environ.get("ENSAIO") == "1"
PLEITO = int(os.environ.get("PLEITO") or (3220 if ENSAIO else 3221))
SAIDA = os.environ.get("SAIDA") or os.path.join(here, "out", "ensaio" if ENSAIO else "live")
PORTA = int(os.environ.get("PORT") or os.environ.get("PORTA") or 8787)
INTERVALO = int(os.environ.get("INTERVALO") or 30)
THREADS = int(os.environ.get("THREADS") or 48)
LOTE = int(os.environ.get("LOTE") or 5000)
VERIFICAR = os.environ.get("VERIFICAR", "1") != "0"     # conferir assinatura de cada boletim
PROCESSOS = int(os.environ.get("PROCESSOS") or max(2, (os.cpu_count() or 4) - 2))
# Plano B (IP de datacenter barrado pelo TSE): coleta no Mac e envia ao Railway, que só serve.
RELAY = os.environ.get("RELAY") == "1"              # só serve o que receber por PUT
ENVIA_PARA = (os.environ.get("ENVIA_PARA") or "").rstrip("/")   # coletor envia cada publicação para cá
TOKEN = os.environ.get("RELAY_TOKEN") or ""
# no relay basta o hash do token (o token em si fica só na máquina que coleta)
TOKEN_SHA256 = os.environ.get("RELAY_TOKEN_SHA256") or (hashlib.sha256(TOKEN.encode()).hexdigest() if TOKEN else "")
INICIO = os.environ.get("INICIO") or "2026-10-25T17:00:00-03:00"
UFS = (os.environ.get("UFS") or "ac,al,am,ap,ba,ce,df,es,go,ma,mg,ms,mt,pa,pb,pe,pi,pr,rj,rn,ro,rr,rs,sc,se,sp,to,zz").split(",")
T = "https://resultados.tse.jus.br/oficial/ele2026"
BRT = timezone(timedelta(hours=-3))
UA = {"User-Agent": "GRData-Projecao/1.0 (+https://grisonet.github.io/apuracao-sp/)"}
PUBLICAVEIS = re.compile(r"^(governador/[a-z]{2}/)?(snapshot\.json|dados\.csv)$")


def log(*a):
    print(datetime.now(BRT).strftime("%H:%M:%S"), *a, flush=True)


class Limitador:
    """Limita as requisições por segundo ao TSE (todas as threads) e recua junto quando vem 429."""

    def __init__(self, por_seg):
        self.intervalo = 1.0 / por_seg
        self.prox = time.monotonic()
        self.pausa_ate = 0.0
        self.lock = threading.Lock()
        self.n429 = 0

    def espera(self):
        with self.lock:
            agora = time.monotonic()
            t = max(self.prox, agora, self.pausa_ate)
            self.prox = t + self.intervalo
        if t > agora:
            time.sleep(t - agora)

    def recua(self, segundos):
        with self.lock:
            self.n429 += 1
            self.pausa_ate = max(self.pausa_ate, time.monotonic() + segundos)


LIMITE = Limitador(float(os.environ.get("REQ_POR_SEG") or 60))


def get(url, timeout=20, tentativas=4):
    for i in range(tentativas):
        LIMITE.espera()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                try:
                    ra = float(e.headers.get("Retry-After") or 0)
                except ValueError:
                    ra = 0
                LIMITE.recua(max(ra, 3 * (i + 1)))
            if i == tentativas - 1:
                raise
        except Exception:
            if i == tentativas - 1:
                raise
        time.sleep(0.5 + i)


def agora_iso():
    return datetime.now(BRT).isoformat(timespec="seconds")


def iso_tse(dg, hg):
    d, m, a = dg.split("/")
    return f"{a}-{m}-{d}T{hg}-03:00"


def grava(nome, texto):
    destino = os.path.join(SAIDA, nome)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    tmp = destino + ".tmp"
    open(tmp, "w", encoding="utf-8").write(texto)
    os.replace(tmp, destino)


def processa(hash_aux, vsc, bu, nome_bu, verificar):
    """Roda num processo separado: confere a integridade e decodifica o boletim."""
    from bu import resultados
    from integridade import confere
    if verificar:
        ok, info = confere(hash_aux, vsc, bu, nome_bu)
        if not ok:
            return False, info, None
    else:
        info = "não verificado"
    return True, info, resultados(bu)


# ----------------------------------------------------------------------------
class Disputa:
    def __init__(self, cfg):
        from modelo import ModeloTransferencia
        self.cfg = cfg
        self.eleicao = cfg["eleicao_1t"] if ENSAIO else cfg["eleicao"]
        self.ufs = set(cfg["ufs"]) if cfg["ufs"] else None
        detalhe = None if self.ufs is None else "zona" if self.ufs == {"DF"} else "municipio"
        nomes = json.load(open(os.path.join(here, "base", "municipios_2026.json"))) if detalhe else None
        self.modelo = ModeloTransferencia(json.load(open(os.path.join(here, "base", cfg["base"]))),
                                          detalhe=detalhe, nomes=nomes)
        self.oficial = None
        self.ultimo_lote = None
        self.lote = [0, 0, 0]

    def aceita(self, chave):
        return self.ufs is None or chave[:2] in self.ufs

    def adiciona(self, chave, res, do_cache=False):
        from bu import confronto
        r = res.get(f"{self.eleicao}:{self.cfg['cargo']}") if do_cache else res.get((self.eleicao, self.cfg["cargo"]))
        if r is None:
            return
        ca, cb = self.cfg["candidatos"]["a"]["numero"], self.cfg["candidatos"]["b"]["numero"]
        if do_cache:
            r = {"votos": {int(k): v for k, v in r["votos"].items()}, **{k: r[k] for k in ("brancos", "nulos", "comparecimento", "aptos")}}
        va, vb, _, br, nu, comp, aptos = confronto(r, ca, cb)
        if self.modelo.adiciona(chave, va, vb, br + nu, comp, aptos):
            self.lote[0] += 1; self.lote[1] += va; self.lote[2] += vb
        return va, vb

    def fecha_lote(self):
        n, va, vb = self.lote
        if n:
            self.ultimo_lote = {"secoes": n, "validos": va + vb, "pcta": round(100 * va / (va + vb), 2) if va + vb else None}
        self.lote = [0, 0, 0]

    def le_oficial(self):
        uf = "br" if self.ufs is None else next(iter(self.ufs)).lower()
        cargo = self.cfg["cargo"]
        try:
            doc = json.loads(get(f"{T}/{self.eleicao}/dados/{uf}/{uf}-c{cargo:04d}-e{self.eleicao:06d}-u.json"))
        except Exception:
            return
        cand = {}
        for c in doc.get("carg", []):
            for a in c.get("agr", []):
                for p in a.get("par", []):
                    for cd in p.get("cand", []):
                        cand[int(cd["n"])] = int(str(cd.get("vap") or 0).replace(".", "") or 0)
        pst = float(str(doc.get("s", {}).get("pst") or "0").replace(",", "."))
        va = cand.get(self.cfg["candidatos"]["a"]["numero"], 0)
        vb = cand.get(self.cfg["candidatos"]["b"]["numero"], 0)
        self.oficial = {"pst": pst, "va": va, "vb": vb, "pcta": round(100 * va / (va + vb), 2) if va + vb else None,
                        "atualizado": iso_tse(doc["dg"], doc["hg"]) if doc.get("dg") else None}

    def snapshot(self, gerado_tse, integridade):
        br = self.modelo.areas["BR"]
        modo = "aguardando" if br.ap == 0 else "final" if br.ap >= br.total else "ensaio" if ENSAIO else "ao_vivo"
        meta = {"modo": modo, "ano": 2026, "disputa": self.cfg["id"], "titulo": self.cfg["titulo"],
                "abrangencia": self.cfg["abrangencia"], "candidatos": self.cfg["candidatos"], "inicio": INICIO,
                "gerado_tse": gerado_tse, "gerado_painel": agora_iso(), "oficial": self.oficial,
                "integridade": integridade}
        return self.modelo.snapshot(meta, self.ultimo_lote) if br.ap else dict(meta, historico=[])


class Coletor:
    def __init__(self):
        from disputas import DISPUTAS
        os.makedirs(SAIDA, exist_ok=True)
        log("carregando as bases do 1º turno …")
        self.disputas = [Disputa(c) for c in DISPUTAS]
        self.cache_path = os.path.join(SAIDA, "secoes.jsonl")
        self.feitas = set()
        self.pendentes = {}
        self.gerado_tse = None
        self.integ = {"verificadas": 0, "rejeitadas": 0, "por_ac": {}, "lista": [], "ativa": VERIFICAR}
        self.pool = concurrent.futures.ProcessPoolExecutor(PROCESSOS)
        # mapa de Presidente por cidade de SP (página inicial): votos somados por município
        self.sp_ibge = json.load(open(os.path.join(here, "base", "sp_ibge.json")))
        self.mapa_sp = {}       # município TSE -> [votos a, votos b, seções apuradas]
        self.sp_total = {}      # município TSE -> seções no total
        self._carrega_cache()

    def _carrega_cache(self):
        if not os.path.exists(self.cache_path):
            return
        for linha in open(self.cache_path):
            try:
                r = json.loads(linha)
            except ValueError:
                continue
            self._registra(r["k"], r.get("info", ""), r["res"], do_cache=True, grava_cache=None)
        log(f"cache: {len(self.feitas)} seções já lidas")

    def _registra(self, k, info, res, do_cache=False, grava_cache=None):
        self.feitas.add(k)
        if info.startswith("AC "):
            self.integ["verificadas"] += 1
            self.integ["por_ac"][info] = self.integ["por_ac"].get(info, 0) + 1
        for d in self.disputas:
            if d.aceita(k):
                v = d.adiciona(k, res, do_cache)
                if v and d.cfg["id"] == "presidente" and k.startswith("SP|"):
                    m = self.mapa_sp.setdefault(int(k.split("|")[1]), [0, 0, 0])
                    m[0] += v[0]; m[1] += v[1]; m[2] += 1
        if grava_cache:
            grava_cache.write(json.dumps({"k": k, "info": info, "res": {f"{e}:{c}": v for (e, c), v in res.items()
                                                                       if (e, c) in self._interessa}}) + "\n")

    @property
    def _interessa(self):
        return {(d.eleicao, d.cfg["cargo"]) for d in self.disputas}

    # -- 1. quem chegou ------------------------------------------------------
    def _config_uf(self, uf):
        raw = get(f"{T}/arquivo-urna/{PLEITO}/config/{uf}/{uf}-p{PLEITO:06d}-cs.json", timeout=60)
        return uf, json.loads(raw) if raw else None

    def varre_configs(self):
        novas = 0
        ultimo = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            for uf, cfg in ex.map(self._config_uf, UFS):
                if not cfg:
                    continue
                dt = iso_tse(cfg["dg"], cfg["hg"])
                ultimo = max(ultimo or dt, dt)
                for ab in cfg.get("abr", []):
                    UF = ab["cd"].upper()
                    for mu in ab.get("mu", []):
                        if UF == "SP":
                            self.sp_total[int(mu["cd"])] = sum(len(zo.get("sec", [])) for zo in mu.get("zon", []))
                        for zo in mu.get("zon", []):
                            for se in zo.get("sec", []):
                                if "da" not in se:
                                    continue
                                k = f"{UF}|{int(mu['cd'])}|{int(zo['cd'])}|{int(se['ns'])}"
                                if k in self.feitas or k in self.pendentes:
                                    continue
                                self.pendentes[k] = (uf, mu["cd"], zo["cd"], se["ns"])
                                novas += 1
        self.gerado_tse = ultimo or self.gerado_tse
        return novas

    # -- 2. arquivos de cada seção --------------------------------------------
    def _baixa_secao(self, k):
        uf, mu, zo, se = self.pendentes[k]
        d = f"{T}/arquivo-urna/{PLEITO}/dados/{uf}/{mu}/{zo}/{se}"
        raw = get(f"{d}/p{PLEITO:06d}-{uf}-m{mu}-z{zo}-s{se}-aux.json")
        if not raw:
            return k, None
        aux = json.loads(raw)
        for h in reversed(aux.get("hashes", [])):
            arq = {a.get("tp"): a["nm"] for a in h.get("arq", [])}
            if "bu" not in arq:
                continue
            bu = get(f"{d}/{h['hash']}/{arq['bu']}")
            vsc = get(f"{d}/{h['hash']}/{arq['vota']}") if VERIFICAR and "vota" in arq else b""
            if bu:
                return k, (h["hash"], vsc, bu, arq["bu"])
        return k, None

    def le_pendentes(self, limite=None):
        chaves = list(self.pendentes)[:limite] if limite else list(self.pendentes)
        ok = falhas = 0
        conferencias = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
            for f in concurrent.futures.as_completed([ex.submit(self._baixa_secao, k) for k in chaves]):
                try:
                    k, arqs = f.result()
                except Exception:
                    falhas += 1
                    continue
                if arqs is None:
                    falhas += 1
                    continue
                conferencias.append((k, self.pool.submit(processa, *arqs, VERIFICAR)))
        with open(self.cache_path, "a") as cache:
            for k, fut in conferencias:
                try:
                    valido, info, res = fut.result()
                except Exception as e:
                    valido, info, res = False, f"boletim ilegível ({type(e).__name__})", None
                self.pendentes.pop(k, None)
                if not valido:
                    self.feitas.add(k)
                    self.integ["rejeitadas"] += 1
                    if len(self.integ["lista"]) < 100:
                        self.integ["lista"].append({"secao": k, "motivo": info})
                    log(f"! boletim rejeitado {k}: {info}")
                    cache.write(json.dumps({"k": k, "info": info, "res": {}}) + "\n")
                    continue
                self._registra(k, info, res, grava_cache=cache)
                ok += 1
        for d in self.disputas:
            d.fecha_lote()
        return ok, falhas

    # -- 3. publica ------------------------------------------------------------
    def publica(self):
        integ = {k: v for k, v in self.integ.items() if k != "lista"}
        integ["rejeitadas_lista"] = self.integ["lista"]
        snaps = []
        for d in self.disputas:
            snap = d.snapshot(self.gerado_tse, integ)
            if d.cfg["id"] == "presidente" and self.sp_total:
                # [IBGE, votos a, votos b, seções apuradas, seções no total] por cidade de SP
                snap["mapa_sp"] = [[self.sp_ibge.get(str(m), ""), *self.mapa_sp.get(m, [0, 0, 0]), t]
                                   for m, t in sorted(self.sp_total.items())]
            pre = d.cfg["saida"]
            self._grava(pre + "snapshot.json", json.dumps(snap, ensure_ascii=False, separators=(",", ":")))
            buf = io.StringIO()
            w = csv.writer(buf)
            na, nb = d.cfg["candidatos"]["a"]["numero"], d.cfg["candidatos"]["b"]["numero"]
            w.writerow(["horario_tse", "secoes_apuradas_pct", f"placar_pct_{na}", f"projecao_pct_{na}",
                        "faixa_min", "faixa_max", f"diferenca_votos_{na}_menos_{nb}"])
            for h in snap.get("historico", []):
                fx = h.get("faixa") or [None, None]
                w.writerow([h.get("t"), h.get("pct"), h.get("placara"), h.get("proj"), fx[0], fx[1], h.get("dif")])
            self._grava(pre + "dados.csv", buf.getvalue())
            snaps.append(snap)
        return snaps[0]

    def _grava(self, nome, texto):
        grava(nome, texto)
        if ENVIA_PARA:
            try:
                req = urllib.request.Request(f"{ENVIA_PARA}/{nome}", data=texto.encode("utf-8"), method="PUT",
                                             headers={"X-Token": TOKEN, "Content-Type": "application/octet-stream"})
                urllib.request.urlopen(req, timeout=20).read()
            except Exception as e:
                log(f"! envio {nome} para o relay falhou: {e!r}")

    # -- laço ------------------------------------------------------------------
    def ciclo(self):
        t0 = time.time()
        novas = self.varre_configs()
        for d in self.disputas:
            d.le_oficial()
        ok = falhas = 0
        # publica a cada lote, para a página não congelar quando há muitas seções acumuladas
        while True:
            o, f = self.le_pendentes(limite=LOTE) if self.pendentes else (0, 0)
            ok += o; falhas += f
            snap = self.publica()
            if not self.pendentes or o == 0:
                break
        pr = snap.get("projecao") or {}
        s = snap.get("secoes") or {}
        log(f"novas {novas} lidas {ok} falhas {falhas} 429s {LIMITE.n429} pendentes {len(self.pendentes)} "
            f"rejeitadas {self.integ['rejeitadas']} | Presidente {s.get('apuradas', 0)}/{s.get('total', 0)} "
            f"({s.get('pct', 0)}%) proj a {pr.get('pcta')} {pr.get('faixa')} {pr.get('status')} | {time.time() - t0:.0f}s")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SAIDA, **kw)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        super().end_headers()

    def do_GET(self):
        caminho = self.path.split("?")[0]
        if caminho in ("/", "/health"):
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"ok"); return
        if not PUBLICAVEIS.match(caminho.lstrip("/")):
            self.send_error(404); return
        super().do_GET()

    def do_PUT(self):
        nome = self.path.split("?")[0].lstrip("/")
        recebido = hashlib.sha256((self.headers.get("X-Token") or "").encode()).hexdigest()
        if not (RELAY and TOKEN_SHA256 and hmac.compare_digest(recebido, TOKEN_SHA256) and PUBLICAVEIS.match(nome)):
            self.send_error(403); return
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20_000_000:
            self.send_error(413); return
        grava(nome, self.rfile.read(n).decode("utf-8"))
        self.send_response(204); self.end_headers()

    def log_message(self, *a):
        pass


def main():
    if RELAY:
        os.makedirs(SAIDA, exist_ok=True)
        if not os.path.exists(os.path.join(SAIDA, "snapshot.json")):
            grava("snapshot.json", json.dumps({"modo": "aguardando", "ano": 2026, "inicio": INICIO, "historico": []}))
        log(f"relay: servindo {SAIDA} em :{PORTA} (recebe PUT com X-Token)")
        ThreadingHTTPServer(("0.0.0.0", PORTA), Handler).serve_forever()
        return
    c = Coletor()
    c.publica()
    srv = ThreadingHTTPServer(("0.0.0.0", PORTA), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"servindo {SAIDA} em :{PORTA}  pleito {PLEITO}  disputas {len(c.disputas)}  UFs {len(UFS)}  "
        f"conferência de assinatura {'ligada' if VERIFICAR else 'DESLIGADA'} ({PROCESSOS} processos)")
    while True:
        try:
            c.ciclo()
        except Exception as e:
            log("! ciclo falhou:", repr(e))
        # antes da apuração (até 10 min antes das 17h) não há o que buscar a cada 30 s
        cedo = datetime.now(BRT) < datetime.fromisoformat(INICIO) - timedelta(minutes=10)
        time.sleep(300 if cedo and not ENSAIO and not c.feitas else INTERVALO)


if __name__ == "__main__":
    main()
