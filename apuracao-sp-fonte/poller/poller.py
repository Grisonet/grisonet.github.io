#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor de apuração TSE 2026 -> WhatsApp (Evolution API).
Monitora Presidente (BR), Governador/Senador SP e deputados escolhidos,
e manda um snapshot consolidado no WhatsApp a cada avanço relevante.
Sem dependências externas: só a stdlib do Python 3.
"""
import json
import os
import ssl
import sys
import time
import shutil
import subprocess
import threading
import concurrent.futures
import urllib.request
import urllib.error
from datetime import datetime

# ----------------------------------------------------------------------------
# Config via ambiente (.env ao lado deste arquivo)
# ----------------------------------------------------------------------------
def load_dotenv(path):
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Aceita tanto os nomes próprios quanto os mesmos do GRChat (copiar e colar).
EVOLUTION_URL      = (os.environ.get("EVOLUTION_URL") or os.environ.get("EVOLUTION_API_URL") or "").rstrip("/")
EVOLUTION_APIKEY   = os.environ.get("EVOLUTION_APIKEY") or os.environ.get("EVOLUTION_API_KEY") or ""
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE") or "griso"
WHATSAPP_TO        = os.environ.get("WHATSAPP_TO", "")  # ex: 5512999998888
POLL_INTERVAL      = int(os.environ.get("POLL_INTERVAL", "30"))   # segundos entre leituras
MIN_MSG_GAP        = int(os.environ.get("MIN_MSG_GAP", "180"))    # intervalo mínimo entre mensagens
PROGRESS_STEP      = float(os.environ.get("PROGRESS_STEP", "2"))  # % de avanço que dispara msg
DRY_RUN            = os.environ.get("DRY_RUN", "0") == "1"        # 1 = só imprime, não envia

BASE = "https://resultados.tse.jus.br/oficial/ele2026"

# ----------------------------------------------------------------------------
# Corridas monitoradas
# ----------------------------------------------------------------------------
RACES = [
    {"key": "PRES",   "title": "🇧🇷 PRESIDENTE",            "pleito": "6257", "uf": "br", "cargo": "0001", "mode": "top",   "topn": 6},
    {"key": "GOVSP",  "title": "🏛️ GOVERNADOR — SP",        "pleito": "6259", "uf": "sp", "cargo": "0003", "mode": "top",   "topn": 6},
    {"key": "SENSP",  "title": "🗳️ SENADOR — SP (3 vagas)", "pleito": "6259", "uf": "sp", "cargo": "0005", "mode": "top",   "topn": 6, "vagas": 3},
    {"key": "DEPFED", "title": "🟦 DEP. FEDERAL SP (seus)",  "pleito": "6259", "uf": "sp", "cargo": "0006", "mode": "track",
        "track": {"2033": "Danilo do Posto", "5522": "Guti", "2222": "Renato Bolsonaro",
                  "5533": "Paulo A. Barbosa", "1800": "Marco Martins",
                  "5588": "Vinicius Marchese", "1502": "Sidney Cruz"}},
    {"key": "DEPEST", "title": "🟩 DEP. ESTADUAL SP (seus)", "pleito": "6259", "uf": "sp", "cargo": "0007", "mode": "track",
        "track": {"55900": "Aline Torres", "55033": "Cabo Samuel",
                  "18000": "Prof. Fernando Oliveira", "10002": "Dani Dias da Rádio",
                  "15115": "Regina Nunes"}},
]

_ctx = ssl.create_default_context()

def url_for(r):
    return f"{BASE}/{r['pleito']}/dados/{r['uf']}/{r['uf']}-c{r['cargo']}-e00{r['pleito']}-u.json"

def fetch_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "apurador-eleicao/1.0"})
            with urllib.request.urlopen(req, timeout=20, context=_ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print(f"  ! erro ao buscar {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2)
    return None

def to_float(s):
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except Exception:
        return 0.0

def to_int(s):
    try:
        return int(str(s).replace(".", ""))
    except Exception:
        return 0

def fmt_int(n):
    return f"{n:,}".replace(",", ".")

def all_cands(doc):
    out = []
    for carg in doc.get("carg", []):
        for agr in carg.get("agr", []):
            for par in agr.get("par", []):
                for c in par.get("cand", []):
                    out.append(c)
    return out

def status_tag(c):
    if c.get("e") == "s":
        return " ✅"
    st = (c.get("st") or "").strip()
    if st and st.lower() not in ("válido", "valido"):
        return f" ({st})"
    return ""

# ----------------------------------------------------------------------------
# Montagem da mensagem + assinatura (pra detectar mudança)
# ----------------------------------------------------------------------------
def build_race(r, doc):
    cands = all_cands(doc)
    for c in cands:
        c["_vap"] = to_int(c.get("vap"))
        c["_pvap"] = to_float(c.get("pvap"))
    cands.sort(key=lambda c: c["_vap"], reverse=True)
    pst = to_float(doc.get("s", {}).get("pst"))  # % seções apuradas

    lines = [f"*{r['title']}*  _({pst:.2f}% apurado)_"]
    sig = [r["key"], f"{pst:.2f}"]  # 2 casas = sensível a qualquer avanço (tempo real)

    if r["mode"] == "top":
        vagas = r.get("vagas", 1)
        top = cands[: r.get("topn", 5)]
        for i, c in enumerate(top):
            mark = "🏆 " if i < vagas else "   "
            lines.append(f"{mark}{c.get('nmu')} ({c.get('n')}) — {c['_pvap']:.2f}%  · {fmt_int(c['_vap'])}{status_tag(c)}")
        # assinatura: líderes (vagas) + faixa de % do líder
        for c in top[:max(vagas, 1)]:
            sig.append(f"{c.get('sqcand')}:{status_tag(c).strip()}")
        if top:
            sig.append(f"L{top[0]['_pvap']:.2f}")
    else:  # track
        track = r["track"]
        rank = {c.get("sqcand"): i + 1 for i, c in enumerate(cands)}
        picked = [c for c in cands if c.get("n") in track]
        picked.sort(key=lambda c: c["_vap"], reverse=True)
        if not picked:
            lines.append("  (candidatos não encontrados no arquivo)")
        for c in picked:
            pos = rank.get(c.get("sqcand"), "?")
            label = track.get(c.get("n"), c.get("nmu"))
            lines.append(f"   {label} ({c.get('n')}) — {c['_pvap']:.2f}%  · {fmt_int(c['_vap'])}  · {pos}º no estado{status_tag(c)}")
            sig.append(f"{c.get('sqcand')}:{c['_pvap']:.2f}:{status_tag(c).strip()}")

    return "\n".join(lines), "|".join(sig), pst

def snapshot():
    blocks, sigs, psts = [], [], []
    for r in RACES:
        doc = fetch_json(url_for(r))
        if not doc:
            blocks.append(f"*{r['title']}*  _(indisponível)_")
            continue
        txt, sig, pst = build_race(r, doc)
        blocks.append(txt)
        sigs.append(sig)
        psts.append(pst)
    now = datetime.now().strftime("%d/%m %H:%M:%S")
    header = f"📊 *APURAÇÃO TSE 2026*  —  {now}"
    body = header + "\n\n" + "\n\n".join(blocks) + "\n\n_🏆 = em vaga · ✅ = eleito_"
    return body, "||".join(sigs), (max(psts) if psts else 0.0)

# ----------------------------------------------------------------------------
# Envio Evolution API (v2: POST /message/sendText/{instance})
# ----------------------------------------------------------------------------
def send_whatsapp(text, to=None):
    to = to or WHATSAPP_TO
    if DRY_RUN or not (EVOLUTION_URL and EVOLUTION_APIKEY and EVOLUTION_INSTANCE and to):
        print(f"---- (DRY-RUN / sem credenciais) mensagem p/ {to} ----")
        print(text)
        print("----------------------------------------------------------------")
        return True
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    payload = json.dumps({"number": to, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "apikey": EVOLUTION_APIKEY,
    })
    try:
        with urllib.request.urlopen(req, timeout=25, context=_ctx) as resp:
            resp.read()
        return True
    except urllib.error.HTTPError as e:
        print(f"  ! Evolution HTTP {e.code}: {e.read().decode('utf-8','ignore')[:300]}", file=sys.stderr)
    except Exception as e:
        print(f"  ! Evolution erro: {e}", file=sys.stderr)
    return False

# ----------------------------------------------------------------------------
# Comparativo municipal: Dani Dias da Rádio x Cabo Samuel (dep. estadual)
# ----------------------------------------------------------------------------
CMP_A = {"n": "10002", "nm": "Dani Dias da Rádio", "e": "🎙️"}
CMP_B = {"n": "55033", "nm": "Cabo Samuel",        "e": "🪖"}

def muni_url(cd, cargo="0007"):
    return f"https://resultados.tse.jus.br/oficial/ele2026/6259/dados/sp/sp{cd}-c{cargo}-e006259-u.json"

# Vale Histórico do Paraíba — 17 cidades (Guaratinguetá incluída). cd TSE : nome
VALE = {
    "64696":"Guaratinguetá","61646":"Arapeí","61697":"Areias","61972":"Bananal",
    "62731":"Cachoeira Paulista","62103":"Canas","63690":"Cruzeiro","63738":"Cunha",
    "66338":"Lavrinhas","66451":"Lorena","68713":"Piquete","61565":"Potim",
    "69396":"Queluz","69876":"Roseira","70939":"São José do Barreiro","71412":"Silveiras",
    "66273":"Lagoinha",
}
CMP_SCOPES = [
    {"key":"CMP_GUARA", "label":"Guaratinguetá",                          "cds":{"64696":"Guaratinguetá"}},
    {"key":"CMP_VALE",  "label":"Vale Histórico do Paraíba (17 cidades)",  "cds":VALE},
]

# Destinatários: os cargos vão só p/ WHATSAPP_TO; o comparativo vai p/ WHATSAPP_TO + extras.
CMP_EXTRA = [x.strip() for x in os.environ.get("WHATSAPP_CMP_TO", "").split(",") if x.strip()]
CMP_RECIPIENTS = list(dict.fromkeys([n for n in ([WHATSAPP_TO] + CMP_EXTRA) if n]))

# ----------------------------------------------------------------------------
# estado.json — Samuel x Dani nas 645 cidades de SP (p/ o mapa). Atualiza a cada 3 min.
# ----------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR        = "/Volumes/Griso 480/Projetos/GR Data"
_REPO_AP        = os.path.join(REPO_DIR, "apuracao-sp")
ESTADO_LOCAL    = os.path.join(_HERE, "estado.json")
REPO_ESTADO     = os.path.join(_REPO_AP, "estado.json")
GOV_LOCAL       = os.path.join(_HERE, "gov-sp.json")
PRES_LOCAL      = os.path.join(_HERE, "presidente.json")
# arquivos a publicar (local -> nome no repo)
PUSH_FILES = {ESTADO_LOCAL: "estado.json", GOV_LOCAL: "gov-sp.json", PRES_LOCAL: "presidente.json"}
ESTADO_INTERVAL = int(os.environ.get("ESTADO_INTERVAL", "180"))     # 3 min
ESTADO_PUSH     = os.environ.get("ESTADO_PUSH", "1") == "1"
UFS = ["ac","al","am","ap","ba","ce","df","es","go","ma","mg","ms","mt","pa","pb",
       "pe","pi","pr","rj","rn","ro","rr","rs","sc","se","sp","to"]
_SP_MUNS = None       # cache da lista de municípios
_MUN_FINAL = {}       # cdi -> row dep (c0007) de cidades já 100%
_GOV_FINAL = {}       # cdi -> row gov (c0003) de cidades já 100%

def _load_sp_muns():
    global _SP_MUNS
    if _SP_MUNS is None:
        cfg = fetch_json("https://resultados.tse.jus.br/oficial/ele2026/6259/config/mun-e006259-cm.json")
        sp = next(a for a in cfg["abr"] if a["cd"] == "sp")
        _SP_MUNS = [{"cd": m["cd"], "cdi": m["cdi"], "nm": m["nm"]} for m in sp["mu"]]
    return _SP_MUNS

def _one_mun(m):
    if m["cdi"] in _MUN_FINAL:
        return _MUN_FINAL[m["cdi"]]
    doc = fetch_json(muni_url(m["cd"]))
    if not doc:
        return None
    row = {"ibge": m["cdi"], "nm": m["nm"],
           "s": _cand_vap(doc, CMP_B["n"]),   # Cabo Samuel 55033
           "d": _cand_vap(doc, CMP_A["n"]),   # Dani Dias 10002
           "p": round(to_float(doc.get("s", {}).get("pst")), 2)}
    if row["p"] >= 100.0:
        _MUN_FINAL[m["cdi"]] = row
    return row

def build_estado():
    muns = _load_sp_muns()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for r in ex.map(_one_mun, muns):
            if r:
                rows.append(r)
    # TOTAL do estado = arquivo oficial da UF (os municipais propagam mais devagar e subcontam).
    uf = fetch_json("https://resultados.tse.jus.br/oficial/ele2026/6259/dados/sp/sp-c0007-e006259-u.json")
    if uf:
        ts = _cand_vap(uf, CMP_B["n"]); td = _cand_vap(uf, CMP_A["n"])
        uf_pst = round(to_float(uf.get("s", {}).get("pst")), 2)
    else:  # fallback: soma dos municípios
        ts = sum(x["s"] for x in rows); td = sum(x["d"] for x in rows); uf_pst = 0.0
    return {
        "updated": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "pst": uf_pst,
        "cand": {"s": {"nm": "Cabo Samuel", "sq": "250002540588", "n": "55033"},
                 "d": {"nm": "Dani Dias da Rádio", "sq": "250002541892", "n": "10002"}},
        "tot": {"s": ts, "d": td},
        "cidades": rows,
    }

def _cands_of(doc):
    """{numero: {'vap':int,'nm':str,'sq':str}} de um arquivo de cargo."""
    out = {}
    for c in doc.get("carg", []):
        for a in c.get("agr", []):
            for p in a.get("par", []):
                for cd in p.get("cand", []):
                    out[cd["n"]] = {"vap": to_int(cd.get("vap")), "nm": cd.get("nmu") or cd.get("nm"), "sq": cd.get("sqcand")}
    return out

def _gov_mun(m):
    if m["cdi"] in _GOV_FINAL:
        return _GOV_FINAL[m["cdi"]]
    doc = fetch_json(muni_url(m["cd"], "0003"))
    if not doc:
        return None
    cands = _cands_of(doc)
    p = round(to_float(doc.get("s", {}).get("pst")), 2)
    v = {n: cands[n]["vap"] for n in cands}
    lead = max(v, key=lambda n: v[n]) if (v and max(v.values()) > 0 and p > 0) else None
    row = {"ibge": m["cdi"], "nm": m["nm"], "lead": lead, "p": p, "v": v}
    if p >= 100.0:
        _GOV_FINAL[m["cdi"]] = row
    return row

def build_govsp():
    muns = _load_sp_muns()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for r in ex.map(_gov_mun, muns):
            if r:
                rows.append(r)
    uf = fetch_json("https://resultados.tse.jus.br/oficial/ele2026/6259/dados/sp/sp-c0003-e006259-u.json")
    cand, tot, uf_pst = {}, {}, 0.0
    if uf:
        cs = _cands_of(uf)
        cand = {n: {"nm": cs[n]["nm"], "sq": cs[n]["sq"]} for n in cs}
        tot = {n: cs[n]["vap"] for n in cs}
        uf_pst = round(to_float(uf.get("s", {}).get("pst")), 2)
    return {"updated": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "pst": uf_pst,
            "cand": cand, "tot": tot, "cidades": rows}

def _pres_uf(uf):
    doc = fetch_json(f"https://resultados.tse.jus.br/oficial/ele2026/6257/dados/{uf}/{uf}-c0001-e006257-u.json")
    if not doc:
        return None
    cs = _cands_of(doc)
    p = round(to_float(doc.get("s", {}).get("pst")), 2)
    ranked = sorted(([n, cs[n]["vap"]] for n in cs), key=lambda x: -x[1])
    lead = ranked[0][0] if (ranked and ranked[0][1] > 0 and p > 0) else None
    return {"uf": uf, "lead": lead, "p": p, "top": ranked[:3]}

def build_presidente():
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_pres_uf, UFS):
            if r:
                rows.append(r)
    br = fetch_json("https://resultados.tse.jus.br/oficial/ele2026/6257/dados/br/br-c0001-e006257-u.json")
    cand, tot, br_pst = {}, {}, 0.0
    if br:
        cs = _cands_of(br)
        cand = {n: {"nm": cs[n]["nm"], "sq": cs[n]["sq"]} for n in cs}
        tot = {n: cs[n]["vap"] for n in cs}
        br_pst = round(to_float(br.get("s", {}).get("pst")), 2)
    return {"updated": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "pst": br_pst,
            "cand": cand, "tot": tot, "ufs": rows}

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

def _git_push_all():
    try:
        rel = []
        for local, name in PUSH_FILES.items():
            if os.path.exists(local):
                shutil.copyfile(local, os.path.join(_REPO_AP, name))
                rel.append("apuracao-sp/" + name)
        if not rel:
            return
        subprocess.run(["git", "-C", REPO_DIR, "add"] + rel, capture_output=True, timeout=60)
        subprocess.run(["git", "-C", REPO_DIR, "commit", "-m", "apuracao-sp: atualiza dados dos mapas (estado/gov/presidente)"], capture_output=True, timeout=60)
        subprocess.run(["git", "-C", REPO_DIR, "push", "origin", "main"], capture_output=True, timeout=90)
    except Exception as e:
        print(f"  ! git push: {e}", file=sys.stderr)

def estado_loop():
    while True:
        t0 = time.time()
        try:
            est = build_estado();  _write_json(ESTADO_LOCAL, est)
            gov = build_govsp();   _write_json(GOV_LOCAL, gov)
            pres = build_presidente(); _write_json(PRES_LOCAL, pres)
            done = sum(1 for c in est["cidades"] if c["p"] > 0)
            ls = sum(1 for c in est["cidades"] if c["s"] > c["d"] and c["p"] > 0)
            ld = sum(1 for c in est["cidades"] if c["d"] > c["s"] and c["p"] > 0)
            gv_t = sum(1 for c in gov["cidades"] if c["lead"] == "10")
            gv_h = sum(1 for c in gov["cidades"] if c["lead"] == "13")
            pr_u = sum(1 for u in pres["ufs"] if u["lead"])
            print(f"[{datetime.now():%H:%M:%S}] MAPAS — dep:{done}cid (Samuel {ls}x{ld} Dani) | gov:(Tarcísio {gv_t}x{gv_h} Haddad) | pres:{pr_u}/27 UFs | {time.time()-t0:.0f}s")
            if ESTADO_PUSH:
                _git_push_all()
        except Exception as e:
            print(f"  ! estado_loop: {e}", file=sys.stderr)
        time.sleep(max(30, ESTADO_INTERVAL - (time.time() - t0)))

def _cand_vap(doc, n):
    for c in doc.get("carg", []):
        for a in c.get("agr", []):
            for p in a.get("par", []):
                for cd in p.get("cand", []):
                    if cd.get("n") == n:
                        return to_int(cd.get("vap"))
    return 0

def pt(n):  # 1234567 -> "1.234.567"
    return f"{n:,}".replace(",", ".")

def build_scope(scope):
    """Comparativo Dani x Samuel somando os municípios do escopo. Retorna (texto, sig, pst)."""
    va = vb = st = ts = rep = 0
    for cd in scope["cds"]:
        doc = fetch_json(muni_url(cd))
        if not doc:
            continue
        va += _cand_vap(doc, CMP_A["n"]); vb += _cand_vap(doc, CMP_B["n"])
        s = doc.get("s", {}); st += to_int(s.get("st")); ts += to_int(s.get("ts"))
        if to_float(s.get("pst")) > 0:
            rep += 1
    pst = (st / ts * 100) if ts else 0.0
    diff = va - vb
    total = va + vb
    sa = (va / total * 100) if total else 0.0
    sb = (vb / total * 100) if total else 0.0
    if diff > 0:   lead = f"🟢 *{CMP_A['nm']}* à frente"
    elif diff < 0: lead = f"🟢 *{CMP_B['nm']}* à frente"
    else:          lead = "⚖️ *empate*"
    nc = len(scope["cds"])
    extra = f" · {rep}/{nc} cidades apurando" if nc > 1 else ""
    lines = [
        f"⚔️ *DANI DIAS × CABO SAMUEL* · {datetime.now():%d/%m %H:%M}",
        f"📍 {scope['label']}  _({pst:.2f}% apurado{extra})_",
        "",
        f"{CMP_A['e']} {CMP_A['nm']}: *{pt(va)}* votos · {sa:.0f}%",
        f"{CMP_B['e']} {CMP_B['nm']}: *{pt(vb)}* votos · {sb:.0f}%",
        f"{lead} por *{pt(abs(diff))}* voto(s)",
    ]
    return "\n".join(lines), f"{scope['key']}|{pst:.2f}|{va}|{vb}", pst

# ----------------------------------------------------------------------------
# Loop principal
# ----------------------------------------------------------------------------
def one_race(r):
    """Busca e monta o bloco de um único cargo. Retorna (texto, sig, pst) ou None."""
    doc = fetch_json(url_for(r))
    if not doc:
        return None
    return build_race(r, doc)

def _decide(key, full_txt, sig, pst, state, now, recipients=None):
    """Decide se envia (mesma lógica dos cargos) e envia a cada destinatário. Retorna pst."""
    recipients = [r for r in (recipients or [WHATSAPP_TO]) if r]
    s = state[key]
    first   = s["sig"] is None
    changed = sig != s["sig"]
    advanced = (pst - s["pst"]) >= PROGRESS_STEP
    gap_ok  = (now - s["sent"]) >= MIN_MSG_GAP
    final   = pst >= 100.0 and s["pst"] < 100.0
    fire = (first and pst > 0) or final or (changed and (advanced or "✅" in full_txt or "eleito" in full_txt.lower()) and gap_ok)
    if fire:
        ok = False
        for to in recipients:
            if send_whatsapp(full_txt, to):
                ok = True
            time.sleep(0.6)  # respira entre destinatários
        if ok:
            s["sig"], s["pst"], s["sent"] = sig, pst, now
            print(f"[{datetime.now():%H:%M:%S}] {key:10s} ENVIADO — {pst:.2f}% → {len(recipients)} nº" + ("  [FINAL]" if final else ""))
    else:
        print(f"[{datetime.now():%H:%M:%S}] {key:10s} ok {pst:.2f}% (mudou={changed} avançou={advanced} gap={gap_ok})")
    return pst

def race_message(r):
    res = one_race(r)
    if not res:
        return None
    txt, sig, pst = res
    hdr = f"📊 *APURAÇÃO TSE 2026* · {datetime.now():%d/%m %H:%M}\n\n"
    foot = "\n\n_🏆 = em vaga · ✅ = eleito_"
    return hdr + txt + foot, sig, pst

def main():
    print("== Apurador TSE 2026 -> WhatsApp (cargos + comparativo Dani×Samuel) ==")
    print(f"   destino cargos={WHATSAPP_TO or '(não setado)'}  comparativo={CMP_RECIPIENTS}  intervalo={POLL_INTERVAL}s  gap_min={MIN_MSG_GAP}s  passo={PROGRESS_STEP}%  dry_run={DRY_RUN}")
    keys = [r["key"] for r in RACES] + [sc["key"] for sc in CMP_SCOPES]
    state = {k: {"sig": None, "pst": -1.0, "sent": 0.0} for k in keys}
    # mapa estadual Samuel x Dani em thread separada (a cada ESTADO_INTERVAL s)
    threading.Thread(target=estado_loop, daemon=True).start()
    print(f"   mapa estadual: estado.json a cada {ESTADO_INTERVAL}s (push={ESTADO_PUSH})")
    while True:
        try:
            now = time.time()
            done = True
            for r in RACES:
                m = race_message(r)
                if not m:
                    done = False; continue
                full, sig, pst = m
                _decide(r["key"], full, sig, pst, state, now)
                if pst < 100.0: done = False
            for sc in CMP_SCOPES:
                full, sig, pst = build_scope(sc)
                _decide(sc["key"], full, sig, pst, state, now, CMP_RECIPIENTS)
                if pst < 100.0: done = False
            if done:
                print("Tudo em 100%. Encerrando.")
                break
        except KeyboardInterrupt:
            print("\nencerrado pelo usuário.")
            break
        except Exception as e:
            print(f"  ! erro no loop: {e}", file=sys.stderr)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
