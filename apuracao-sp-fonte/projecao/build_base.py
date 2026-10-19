#!/usr/bin/env python3
"""Base do 1º turno por seção (Presidente) a partir do votacao_secao_{ano}_BR.zip do TSE.

Saída: base/{ano}_t{turno}.json  ->  {"UF|MUN|ZONA|SECAO": [v22, v13, outros, brancos, nulos]}
mais base/municipios_{ano}.json  ->  {"UF|MUN": nome}
Uso: python3 build_base.py 2026 1   |   python3 build_base.py 2022 1   |   python3 build_base.py 2022 2
"""
import csv, io, json, os, sys, zipfile

ano, turno = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
z = zipfile.ZipFile(os.path.join(here, "raw", f"votacao_secao_{ano}_BR.zip"))
name = [n for n in z.namelist() if n.endswith(".csv")][0]
rd = csv.reader(io.TextIOWrapper(z.open(name), encoding="latin-1"), delimiter=";")
h = {c: i for i, c in enumerate(next(rd))}
iT, iUF, iMU, iNM, iZ, iS, iC, iV, iQ = (h[c] for c in (
    "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS"))

secoes, muns = {}, {}
for r in rd:
    if r[iT] != turno or r[iC] != "1":
        continue
    k = f"{r[iUF]}|{int(r[iMU])}|{int(r[iZ])}|{int(r[iS])}"
    v = secoes.get(k)
    if v is None:
        v = secoes[k] = [0, 0, 0, 0, 0]
        muns[f"{r[iUF]}|{int(r[iMU])}"] = r[iNM]
    n, q = r[iV], int(r[iQ])
    v[0 if n == "22" else 1 if n == "13" else 3 if n == "95" else 4 if n == "96" else 2] += q

os.makedirs(os.path.join(here, "base"), exist_ok=True)
json.dump(secoes, open(os.path.join(here, "base", f"{ano}_t{turno}.json"), "w"), separators=(",", ":"))
json.dump(muns, open(os.path.join(here, "base", f"municipios_{ano}.json"), "w"), ensure_ascii=False)
tot = [sum(v[i] for v in secoes.values()) for i in range(5)]
print(ano, turno, len(secoes), "seções", "22/13/outros/br/nu =", tot)
