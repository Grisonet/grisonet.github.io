#!/usr/bin/env python3
"""Hora de chegada de cada seção no TSE (DT_BU_RECEBIDO) e eleitores aptos no 2º turno de 2022, para o replay.

Saída: base/2022_t2_ordem.json -> {"UF|MUN|ZONA|SECAO": "2022-10-30T17:34:43"}
       base/2022_t2_aptos.json -> {"UF|MUN|ZONA|SECAO": 312}
"""
import csv, glob, io, json, os, zipfile
from datetime import datetime

here = os.path.dirname(os.path.abspath(__file__))
ordem, aptos = {}, {}
for zp in sorted(glob.glob(os.path.join(here, "raw", "bweb22", "bweb_2t_*.zip"))):
    z = zipfile.ZipFile(zp)
    name = [n for n in z.namelist() if n.endswith(".csv")][0]
    rd = csv.reader(io.TextIOWrapper(z.open(name), encoding="latin-1"), delimiter=";")
    h = {c: i for i, c in enumerate(next(rd))}
    iUF, iMU, iZ, iS, iC, iD = (h[c] for c in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO_PERGUNTA", "DT_BU_RECEBIDO"))
    iA = h["QT_APTOS"]
    for r in rd:
        if r[iC] != "1":
            continue
        k = f"{r[iUF]}|{int(r[iMU])}|{int(r[iZ])}|{int(r[iS])}"
        if k not in ordem:
            ordem[k] = datetime.strptime(r[iD], "%d/%m/%Y %H:%M:%S").isoformat()
            aptos[k] = int(r[iA])
    print(os.path.basename(zp), len(ordem))
json.dump(ordem, open(os.path.join(here, "base", "2022_t2_ordem.json"), "w"), separators=(",", ":"))
json.dump(aptos, open(os.path.join(here, "base", "2022_t2_aptos.json"), "w"), separators=(",", ":"))
