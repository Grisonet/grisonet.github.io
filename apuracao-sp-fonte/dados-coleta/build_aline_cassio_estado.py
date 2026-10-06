#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera aline-cassio-estado.json: votos de Aline Torres (dep est, c0007 nº 55900)
e Cássio Navarro (dep fed, c0006 nº 5550) nas 645 cidades de SP, p/ o mapa do estado."""
import json, ssl, sys, time, concurrent.futures, urllib.request
from datetime import datetime

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
_ctx = ssl.create_default_context()
A_N, C_N = "55900", "5550"   # Aline (estadual), Cássio (federal)

def fetch_json(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "apurador/1.0"})
            with urllib.request.urlopen(req, timeout=25, context=_ctx) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == tries-1: return None
            time.sleep(1.5)
    return None

def to_int(s):
    try: return int(str(s).replace(".", ""))
    except Exception: return 0
def to_float(s):
    try: return float(str(s).replace(".", "").replace(",", "."))
    except Exception: return 0.0

def cand_vap(doc, n):
    for c in doc.get("carg", []):
        for a in c.get("agr", []):
            for p in a.get("par", []):
                for cd in p.get("cand", []):
                    if cd.get("n") == n: return to_int(cd.get("vap"))
    return 0

def load_muns():
    cfg = fetch_json(f"{BASE}/6259/config/mun-e006259-cm.json")
    sp = next(a for a in cfg["abr"] if a["cd"] == "sp")
    return [{"cd": m["cd"], "cdi": m["cdi"], "nm": m["nm"]} for m in sp["mu"]]

def murl(cd, cargo):
    return f"{BASE}/6259/dados/sp/sp{cd}-c{cargo}-e006259-u.json"

def one(m):
    de = fetch_json(murl(m["cd"], "0007"))   # Aline
    df = fetch_json(murl(m["cd"], "0006"))   # Cássio
    if not de and not df: return None
    pa = round(to_float(de.get("s", {}).get("pst")), 2) if de else 0.0
    pc = round(to_float(df.get("s", {}).get("pst")), 2) if df else 0.0
    return {"ibge": m["cdi"], "nm": m["nm"],
            "a": cand_vap(de, A_N) if de else 0,
            "c": cand_vap(df, C_N) if df else 0,
            "p": round(max(pa, pc), 2)}

def main():
    muns = load_muns()
    print(f"municípios: {len(muns)}", file=sys.stderr)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for i, r in enumerate(ex.map(one, muns)):
            if r: rows.append(r)
            if (i+1) % 100 == 0: print(f"  {i+1}/{len(muns)}", file=sys.stderr)
    ufe = fetch_json(murl("", "0007").replace("sp-c", "sp-c"))  # fallback below
    ufe = fetch_json(f"{BASE}/6259/dados/sp/sp-c0007-e006259-u.json")
    uff = fetch_json(f"{BASE}/6259/dados/sp/sp-c0006-e006259-u.json")
    ta = cand_vap(ufe, A_N) if ufe else sum(x["a"] for x in rows)
    tc = cand_vap(uff, C_N) if uff else sum(x["c"] for x in rows)
    pa = round(to_float(ufe.get("s", {}).get("pst")), 2) if ufe else 0.0
    pc = round(to_float(uff.get("s", {}).get("pst")), 2) if uff else 0.0
    out = {
        "updated": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "pa": pa, "pc": pc,
        "cand": {"a": {"nm": "Aline Torres", "n": A_N, "cargo": "Dep. Estadual"},
                 "c": {"nm": "Cássio Navarro", "n": C_N, "cargo": "Dep. Federal"}},
        "tot": {"a": ta, "c": tc},
        "cidades": rows,
    }
    p = "aline-cassio-estado.json"
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"OK -> {p} | Aline(est) {ta:,} ({pa}%) · Cássio(fed) {tc:,} ({pc}%) | {len(rows)} cidades")

if __name__ == "__main__":
    main()
