#!/usr/bin/env python3
"""Coletor do painel "Projeção do 2º turno" (GR Data).

A cada ciclo:
  1. lê a lista de seções de cada UF no TSE (arquivo-urna/<pleito>/config) e vê
     quais já chegaram;
  2. baixa e decodifica o boletim de urna de cada seção nova (.bu.dat);
  3. passa a seção para o modelo (seção do 2º turno × mesma seção no 1º);
  4. grava out/live/snapshot.json + dados.csv e serve por HTTP com CORS.

Só stdlib. Seções já lidas ficam em cache (secoes.jsonl), então reiniciar não
baixa tudo de novo.

  python3 coletor.py                    # 2º turno de verdade (pleito 3221 / eleição 6258)
  ENSAIO=1 UFS=ac,rr python3 coletor.py # ensaio com o 1º turno (3220/6257), poucas UFs
"""
import concurrent.futures, csv, io, json, os, sys, threading, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from bu import presidente
from modelo import ModeloTransferencia

here = os.path.dirname(os.path.abspath(__file__))
ENSAIO = os.environ.get("ENSAIO") == "1"
PLEITO = int(os.environ.get("PLEITO") or (3220 if ENSAIO else 3221))
ELEICAO = int(os.environ.get("ELEICAO") or (6257 if ENSAIO else 6258))
BASE = os.environ.get("BASE") or os.path.join(here, "base", "2026_t1.json")
SAIDA = os.environ.get("SAIDA") or os.path.join(here, "out", "ensaio" if ENSAIO else "live")
PORTA = int(os.environ.get("PORT") or os.environ.get("PORTA") or 8787)
INTERVALO = int(os.environ.get("INTERVALO") or 30)
THREADS = int(os.environ.get("THREADS") or 48)
LOTE = int(os.environ.get("LOTE") or 5000)
# Plano B (IP de datacenter barrado pelo TSE): coleta no Mac e envia ao Railway, que só serve.
RELAY = os.environ.get("RELAY") == "1"              # só serve o que receber por PUT
ENVIA_PARA = (os.environ.get("ENVIA_PARA") or "").rstrip("/")   # coletor envia cada publicação para cá
TOKEN = os.environ.get("RELAY_TOKEN") or ""
INICIO = os.environ.get("INICIO") or "2026-10-25T17:00:00-03:00"
UFS = (os.environ.get("UFS") or "ac,al,am,ap,ba,ce,df,es,go,ma,mg,ms,mt,pa,pb,pe,pi,pr,rj,rn,ro,rr,rs,sc,se,sp,to,zz").split(",")
T = "https://resultados.tse.jus.br/oficial/ele2026"
BRT = timezone(timedelta(hours=-3))
UA = {"User-Agent": "GRData-Projecao/1.0 (+https://grisonet.github.io/apuracao-sp/)"}


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
            elif i == tentativas - 1:
                raise
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
    tmp = os.path.join(SAIDA, nome + ".tmp")
    open(tmp, "w", encoding="utf-8").write(texto)
    os.replace(tmp, os.path.join(SAIDA, nome))


# ----------------------------------------------------------------------------
class Coletor:
    def __init__(self):
        os.makedirs(SAIDA, exist_ok=True)
        log(f"carregando base {os.path.basename(BASE)} …")
        base = json.load(open(BASE))
        self.modelo = ModeloTransferencia(base)
        self.cache_path = os.path.join(SAIDA, "secoes.jsonl")
        self.pendentes = {}            # chave -> url do diretório da seção
        self.gerado_tse = None
        self.oficial = None
        self.ultimo_lote = None
        self._carrega_cache()

    def _carrega_cache(self):
        if not os.path.exists(self.cache_path):
            return
        n = 0
        for linha in open(self.cache_path):
            try:
                r = json.loads(linha)
            except ValueError:
                continue
            self.modelo.adiciona(r["k"], r["v22"], r["v13"], r["bn"], r["comp"], r["aptos"])
            n += 1
        log(f"cache: {n} seções já lidas")

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
                        for zo in mu.get("zon", []):
                            for se in zo.get("sec", []):
                                if "da" not in se:
                                    continue
                                k = f"{UF}|{int(mu['cd'])}|{int(zo['cd'])}|{int(se['ns'])}"
                                if k in self.modelo.feitas or k in self.pendentes:
                                    continue
                                self.pendentes[k] = (uf, mu["cd"], zo["cd"], se["ns"])
                                novas += 1
        self.gerado_tse = ultimo or self.gerado_tse
        return novas

    # -- 2. boletim de cada seção ---------------------------------------------
    def _le_secao(self, k):
        uf, mu, zo, se = self.pendentes[k]
        d = f"{T}/arquivo-urna/{PLEITO}/dados/{uf}/{mu}/{zo}/{se}"
        raw = get(f"{d}/p{PLEITO:06d}-{uf}-m{mu}-z{zo}-s{se}-aux.json")
        if not raw:
            return k, None
        aux = json.loads(raw)
        for h in reversed(aux.get("hashes", [])):
            nm = next((a["nm"] for a in h.get("arq", []) if a.get("tp") == "bu"), None)
            if nm:
                bu = get(f"{d}/{h['hash']}/{nm}")
                if bu:
                    return k, presidente(bu, ELEICAO)
        return k, None

    def le_pendentes(self, limite=None):
        chaves = list(self.pendentes)[:limite] if limite else list(self.pendentes)
        ok = falhas = 0
        lote = {"secoes": 0, "v22": 0, "v13": 0}
        with open(self.cache_path, "a") as cache, \
                concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
            futs = [ex.submit(self._le_secao, k) for k in chaves]
            for f in concurrent.futures.as_completed(futs):
                try:
                    k, r = f.result()
                except Exception as e:
                    falhas += 1
                    continue
                if r is None:
                    falhas += 1
                    continue
                self.pendentes.pop(k, None)
                bn = r["brancos"] + r["nulos"]
                if self.modelo.adiciona(k, r["v22"], r["v13"], bn, r["comparecimento"], r["aptos"]):
                    cache.write(json.dumps({"k": k, "v22": r["v22"], "v13": r["v13"], "bn": bn,
                                            "comp": r["comparecimento"], "aptos": r["aptos"]}) + "\n")
                    lote["secoes"] += 1; lote["v22"] += r["v22"]; lote["v13"] += r["v13"]
                    ok += 1
        if lote["secoes"]:
            v = lote["v22"] + lote["v13"]
            self.ultimo_lote = {"secoes": lote["secoes"], "validos": v,
                                "pct22": round(100 * lote["v22"] / v, 2) if v else None}
        return ok, falhas

    # -- placar oficial agregado (só para conferência na tela) -----------------
    def le_oficial(self):
        try:
            doc = json.loads(get(f"{T}/{ELEICAO}/dados/br/br-c0001-e{ELEICAO:06d}-u.json"))
        except Exception:
            return
        cand = {}
        for c in doc.get("carg", []):
            for a in c.get("agr", []):
                for p in a.get("par", []):
                    for cd in p.get("cand", []):
                        cand[cd["n"]] = int(str(cd.get("vap") or 0).replace(".", "") or 0)
        pst = float(str(doc.get("s", {}).get("pst") or "0").replace(",", "."))
        v22, v13 = cand.get("22", 0), cand.get("13", 0)
        self.oficial = {"pst": pst, "v22": v22, "v13": v13,
                        "pct22": round(100 * v22 / (v22 + v13), 2) if v22 + v13 else None,
                        "atualizado": iso_tse(doc["dg"], doc["hg"]) if doc.get("dg") else None}

    # -- 3. publica ------------------------------------------------------------
    def publica(self):
        br = self.modelo.areas["BR"]
        if br.ap == 0:
            modo = "aguardando"
        elif br.ap >= br.total:
            modo = "final"
        else:
            modo = "ensaio" if ENSAIO else "ao_vivo"
        meta = {"modo": modo, "ano": 2026, "inicio": INICIO, "gerado_tse": self.gerado_tse,
                "gerado_painel": agora_iso(), "oficial": self.oficial,
                "nomes": {"22": "Flávio", "13": "Lula"}}
        snap = self.modelo.snapshot(meta, self.ultimo_lote) if br.ap else dict(meta, historico=[])
        self._grava("snapshot.json", json.dumps(snap, ensure_ascii=False, separators=(",", ":")))
        # CSV com o histórico da noite, para qualquer pessoa conferir
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["horario_tse", "secoes_apuradas_pct", "placar_pct_22", "projecao_pct_22",
                    "faixa_min", "faixa_max", "diferenca_votos_22_menos_13"])
        for h in snap.get("historico", []):
            fx = h.get("faixa") or [None, None]
            w.writerow([h.get("t"), h.get("pct"), h.get("placar22"), h.get("proj"), fx[0], fx[1], h.get("dif")])
        self._grava("dados.csv", buf.getvalue())
        return snap

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
        self.le_oficial()
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
        log(f"novas {novas} lidas {ok} falhas {falhas} 429s {LIMITE.n429} pendentes {len(self.pendentes)} | apuradas {s.get('apuradas', 0)}/{s.get('total', 0)} "
            f"({s.get('pct', 0)}%) | proj 22 {pr.get('pct22')} {pr.get('faixa')} {pr.get('status')} | {time.time() - t0:.0f}s")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SAIDA, **kw)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/health"):
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(b"ok"); return
        if not self.path.split("?")[0].endswith((".json", ".csv")) or "secoes.jsonl" in self.path:
            self.send_error(404); return
        super().do_GET()

    def do_PUT(self):
        nome = self.path.split("?")[0].lstrip("/")
        if not (RELAY and TOKEN and self.headers.get("X-Token") == TOKEN and nome in ("snapshot.json", "dados.csv")):
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
    log(f"servindo {SAIDA} em :{PORTA}  pleito {PLEITO} eleição {ELEICAO}  UFs {len(UFS)}")
    while True:
        try:
            c.ciclo()
        except Exception as e:
            log("! ciclo falhou:", repr(e))
        # antes da apuração (até 10 min antes das 17h) não há o que buscar a cada 30 s
        cedo = datetime.now(BRT) < datetime.fromisoformat(INICIO) - timedelta(minutes=10)
        time.sleep(300 if cedo and not ENSAIO and c.modelo.areas["BR"].ap == 0 else INTERVALO)


if __name__ == "__main__":
    main()
