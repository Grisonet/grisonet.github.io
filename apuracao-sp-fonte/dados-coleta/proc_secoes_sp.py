#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa votação por seção (TSE 2026 SP) p/ São Paulo capital (CD_MUNICIPIO 71072),
candidatos Aline Torres (dep est 55900) e Cássio Navarro (dep fed 5550).
Junta lat/long dos locais de votação (geocode 2024) e agrega por local e por zona.
Lê o CSV grande via stdin (unzip -p ...), pra não extrair 4,95 GB em disco.
Saída: aline-cassio-sp-secoes.json
"""
import sys, csv, json, subprocess, io, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
MUNI = "71072"                 # São Paulo capital (código TSE)
A_N, C_N = "55900", "5550"     # Aline (estadual) / Cássio (federal)
SECZIP = os.path.join(HERE, "votacao_secao_2026_SP.zip")
GEOZIP = os.path.join(HERE, "locais_2024.zip")

def rows_from_zip(zippath, member):
    """Gera listas de campos (csv ;, latin-1) por streaming de unzip -p."""
    p = subprocess.Popen(["unzip", "-p", zippath, member], stdout=subprocess.PIPE)
    txt = io.TextIOWrapper(p.stdout, encoding="latin-1", newline="")
    r = csv.reader(txt, delimiter=";")
    for row in r:
        yield row
    p.stdout.close(); p.wait()

# ---------- 1) geocode: (zona,secao) -> local info/lat/long p/ muni 71072 ----------
print("lendo geocode...", file=sys.stderr)
geo = {}            # (zona,secao) -> dict
loc_pt = {}         # local_code -> (lat,lon) representativo
hdr = None
for row in rows_from_zip(GEOZIP, "eleitorado_local_votacao_2024.csv"):
    if hdr is None:
        hdr = {name.strip('"'): i for i, name in enumerate(row)}
        continue
    if row[hdr["CD_MUNICIPIO"]] != MUNI:
        continue
    z = row[hdr["NR_ZONA"]]; s = row[hdr["NR_SECAO"]]
    lc = row[hdr["NR_LOCAL_VOTACAO"]]
    try:
        lat = float(row[hdr["NR_LATITUDE"]]); lon = float(row[hdr["NR_LONGITUDE"]])
    except Exception:
        lat = lon = None
    info = {"lc": lc, "nm": row[hdr["NM_LOCAL_VOTACAO"]], "bairro": row[hdr["NM_BAIRRO"]],
            "end": row[hdr["DS_ENDERECO"]], "lat": lat, "lon": lon}
    geo[(z, s)] = info
    if lat and lon and -90 < lat < 90 and lc not in loc_pt:
        loc_pt[lc] = (lat, lon)
print(f"  geocode: {len(geo)} (zona,seção) · {len(loc_pt)} locais com coord", file=sys.stderr)

# ---------- 2) votos por seção (streaming do CSV grande) ----------
print("filtrando votação por seção (streaming 4,95 GB)...", file=sys.stderr)
# por local: votos Aline/Cássio + set de seções ; por zona idem
loc = defaultdict(lambda: {"a": 0, "c": 0, "sec": set()})
hdr = None; nread = 0; nhit = 0
for row in rows_from_zip(SECZIP, "votacao_secao_2026_SP.csv"):
    if hdr is None:
        hdr = {name.strip('"'): i for i, name in enumerate(row)}
        iM, iV, iZ, iS, iL, iQ = (hdr["CD_MUNICIPIO"], hdr["NR_VOTAVEL"], hdr["NR_ZONA"],
                                   hdr["NR_SECAO"], hdr["NR_LOCAL_VOTACAO"], hdr["QT_VOTOS"])
        continue
    nread += 1
    if row[iM] != MUNI:
        continue
    v = row[iV]
    if v != A_N and v != C_N:
        continue
    nhit += 1
    z, s, lc = row[iZ], row[iS], row[iL]
    try: q = int(row[iQ])
    except Exception: q = 0
    key = (z, lc)
    d = loc[key]
    d["sec"].add(s)
    if v == A_N: d["a"] += q
    else:        d["c"] += q
    # guarda geo do local a partir da 1ª seção que casar
    if "geo" not in d:
        g = geo.get((z, s))
        if g: d["geo"] = g
print(f"  linhas lidas ~{nread:,} · hits {nhit:,} · locais {len(loc)}", file=sys.stderr)

# ---------- 3) montar locais + zonas ----------
locais = []
zonas = defaultdict(lambda: {"a": 0, "c": 0, "nl": 0, "slat": 0.0, "slon": 0.0, "nco": 0})
tot_a = tot_c = 0
for (z, lc), d in loc.items():
    g = d.get("geo") or {}
    lat = g.get("lat"); lon = g.get("lon")
    if (lat is None or lon is None) and lc in loc_pt:
        lat, lon = loc_pt[lc]
    rec = {"z": int(z), "lc": lc, "nm": g.get("nm", ""), "bairro": g.get("bairro", ""),
           "a": d["a"], "c": d["c"], "sec": len(d["sec"]),
           "lat": round(lat, 6) if lat else None, "lon": round(lon, 6) if lon else None}
    locais.append(rec)
    tot_a += d["a"]; tot_c += d["c"]
    zz = zonas[z]; zz["a"] += d["a"]; zz["c"] += d["c"]; zz["nl"] += 1
    if lat and lon:
        zz["slat"] += lat; zz["slon"] += lon; zz["nco"] += 1

zlist = []
for z, zz in zonas.items():
    zlist.append({"z": int(z), "a": zz["a"], "c": zz["c"], "nl": zz["nl"],
                  "lat": round(zz["slat"]/zz["nco"], 6) if zz["nco"] else None,
                  "lon": round(zz["slon"]/zz["nco"], 6) if zz["nco"] else None})
zlist.sort(key=lambda x: -(x["a"] + x["c"]))
locais.sort(key=lambda x: -(x["a"] + x["c"]))

out = {
    "municipio": "São Paulo",
    "cand": {"a": {"nm": "Aline Torres", "n": A_N, "cargo": "Dep. Estadual"},
             "c": {"nm": "Cássio Navarro", "n": C_N, "cargo": "Dep. Federal"}},
    "tot": {"a": tot_a, "c": tot_c},
    "nlocais": len(locais), "nzonas": len(zlist),
    "sem_coord": sum(1 for x in locais if x["lat"] is None),
    "zonas": zlist,
    "locais": locais,
}
p = os.path.join(HERE, "aline-cassio-sp-secoes.json")
json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"OK -> {p}")
print(f"   SP capital: Aline(est) {tot_a:,} · Cássio(fed) {tot_c:,} | {len(locais)} locais · {len(zlist)} zonas · {out['sem_coord']} locais sem coord")
