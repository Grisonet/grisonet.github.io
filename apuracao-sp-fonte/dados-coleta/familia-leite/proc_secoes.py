#!/usr/bin/env python3
"""Votação seção a seção das candidaturas da família Leite num ano.
uso: proc_secoes.py ANO
- deputados (2014/2018/2022/2026): todas as seções do estado de SP
- vereador (2016/2020): seções da capital
Junta o local de votação (nome, bairro, lat/long) do cadastro de locais do mesmo ano
e, na capital, o distrito (ponto no polígono, distritos da Prefeitura).
Votos válidos da seção = todos os votos do cargo menos brancos (95) e nulos (96/97/98).
Saída: secoes_ANO.json"""
import csv, io, json, subprocess, sys
from collections import defaultdict

from cand_cfg import CANDS

ANO = int(sys.argv[1])
CAP = "71072"
T2I = json.load(open("tse2ibge.json"))
cs = [c for c in CANDS if c["ano"] == ANO]
MUNIC = ANO in (2016, 2020)
cargos = sorted({c["cd_cargo"] for c in cs}, key=int)
nums = {(c["cd_cargo"], c["n"]): c["id"] for c in cs}
INVAL = {"95", "96", "97", "98"}

def rows(zp, member):
    p = subprocess.Popen(["unzip", "-p", zp, member], stdout=subprocess.PIPE)
    r = csv.reader(io.TextIOWrapper(p.stdout, encoding="latin-1", newline=""), delimiter=";")
    hdr = next(r)
    yield {h: i for i, h in enumerate(hdr)}
    yield from r
    p.wait()

# ---------- distritos da capital ----------
dist = json.load(open("sp-distritos.geojson"))["features"]
def _inring(x, y, ring):
    ins = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins
DB = []
for f in dist:
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
    DB.append((f["properties"]["ds_codigo"], polys, (min(xs), min(ys), max(xs), max(ys))))
def distrito(lon, lat):
    for cod, polys, (x0, y0, x1, y1) in DB:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in polys:
            if _inring(lon, lat, poly[0]) and not any(_inring(lon, lat, h) for h in poly[1:]):
                return cod
    return ""

# ---------- cadastro de locais (lat/long) ----------
lzip = f"raw/eleitorado_local_votacao_{ANO}.zip"
lmem = f"eleitorado_local_votacao_{ANO}_SP.csv" if ANO == 2026 else f"eleitorado_local_votacao_{ANO}.csv"
it = rows(lzip, lmem); h = next(it)
geo = {}
for r in it:
    if r[h["SG_UF"]] != "SP" or ("NR_TURNO" in h and r[h["NR_TURNO"]] not in ("1", "")):
        continue
    if MUNIC and r[h["CD_MUNICIPIO"]] != CAP:
        continue
    try:
        lat = float(r[h["NR_LATITUDE"]].replace(",", ".")); lon = float(r[h["NR_LONGITUDE"]].replace(",", "."))
        if not (-26 < lat < -19 and -54 < lon < -44):
            lat = lon = None
    except ValueError:
        lat = lon = None
    k = (r[h["CD_MUNICIPIO"]], int(r[h["NR_ZONA"]]), int(r[h["NR_LOCAL_VOTACAO"]]))
    if k not in geo or (geo[k][2] is None and lat):
        geo[k] = (r[h["NM_LOCAL_VOTACAO"]].strip(), r[h["NM_BAIRRO"]].strip().title(), lat, lon,
                  r[h["DS_ENDERECO"]].strip().title())
print(ANO, "locais no cadastro:", len(geo), file=sys.stderr)

# ---------- votos por seção ----------
tot = defaultdict(lambda: defaultdict(int))     # (mun,zona,secao) -> cargo -> válidos
cv = defaultdict(lambda: defaultdict(int))      # (mun,zona,secao) -> cand id -> votos
loc_of = {}
nmloc = {}
it = rows(f"raw/votacao_secao_{ANO}_SP.zip", f"votacao_secao_{ANO}_SP.csv"); h = next(it)
iT, iC, iM, iZ, iS, iV, iQ, iL = (h["NR_TURNO"], h["CD_CARGO"], h["CD_MUNICIPIO"], h["NR_ZONA"], h["NR_SECAO"],
                                  h["NR_VOTAVEL"], h["QT_VOTOS"], h["NR_LOCAL_VOTACAO"])
iN = h.get("NM_LOCAL_VOTACAO")
n = 0
for r in it:
    n += 1
    if r[iT] != "1" or r[iC] not in cargos:
        continue
    if MUNIC and r[iM] != CAP:
        continue
    k = (r[iM], int(r[iZ]), int(r[iS]))
    v = int(r[iQ]); nv = r[iV]
    if nv not in INVAL:
        tot[k][r[iC]] += v
    cid = nums.get((r[iC], nv))
    if cid:
        cv[k][cid] += v
    if k not in loc_of:
        loc_of[k] = int(r[iL])
        if iN is not None:
            nmloc[(r[iM], int(r[iZ]), int(r[iL]))] = r[iN].strip()
print(ANO, "linhas lidas:", n, "seções:", len(tot), file=sys.stderr)

# ---------- monta saída ----------
cols = []
for cg in cargos:
    cols.append("t" + cg)
    cols += [c["id"] for c in cs if c["cd_cargo"] == cg]
locais, lidx, secs = [], {}, []
miss = 0
for k in sorted(tot, key=lambda k: (k[0], k[1], loc_of[k], k[2])):
    m, z, s = k
    lk = (m, z, loc_of[k])
    if lk not in lidx:
        g = geo.get(lk)
        nm, bairro, lat, lon, end = g if g else (nmloc.get(lk, f"Local {lk[2]}"), "", None, None, "")
        if lat is None:
            miss += 1
        d = distrito(lon, lat) if (m == CAP and lat) else ""
        lidx[lk] = len(locais)
        locais.append([T2I.get(m, m), z, lk[2], nm, bairro, round(lat, 5) if lat else None,
                       round(lon, 5) if lon else None, d, end])
    row = [lidx[lk], s]
    for c in cols:
        row.append(tot[k][c[1:]] if c.startswith("t") else cv[k].get(c, 0))
    secs.append(row)
out = {"ano": ANO, "cols": cols,
       "locais_campos": ["ibge", "zona", "local", "nome", "bairro", "lat", "lon", "distrito", "endereco"],
       "locais": locais, "secoes_campos": ["local_idx", "secao"] + cols, "secoes": secs}
json.dump(out, open(f"secoes_{ANO}.json", "w"), ensure_ascii=False, separators=(",", ":"))
for c in cs:
    j = 2 + cols.index(c["id"])
    print(ANO, c["id"], "votos somados nas seções:", sum(r[j] for r in secs), file=sys.stderr)
print(ANO, "locais:", len(locais), "sem coordenada:", miss, "seções:", len(secs), file=sys.stderr)
