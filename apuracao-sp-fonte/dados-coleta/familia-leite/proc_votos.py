#!/usr/bin/env python3
"""Votos por município (deputados) e por zona da capital, das 10 candidaturas
de Milton Leite, Alexandre Leite e Milton Leite Filho (2014-2026).
Fonte: TSE, votacao_candidato_munzona_{ano}.zip (arquivo _SP.csv, latin-1, ;).
Também guarda o total de votos nominais de todos os candidatos do cargo em
cada município/zona (para a fatia) e a posição do candidato em cada município.
Saída: votos.json"""
import csv, io, json, subprocess
from collections import defaultdict

from cand_cfg import CANDS

T2I = json.load(open("tse2ibge.json"))
CAP = "71072"

def rows(zp, member):
    p = subprocess.Popen(["unzip", "-p", zp, member], stdout=subprocess.PIPE)
    yield from csv.DictReader(io.TextIOWrapper(p.stdout, encoding="latin-1", newline=""), delimiter=";")
    p.wait()

out = {}
for ano in sorted({c["ano"] for c in CANDS}):
    cs = [c for c in CANDS if c["ano"] == ano]
    cargos = {c["cd_cargo"] for c in cs}
    sqs = {c["sq"]: c for c in cs}
    # (cargo, mun) -> sq -> votos ; (cargo, zona capital) -> sq -> votos
    mun = defaultdict(lambda: defaultdict(int))
    zon = defaultdict(lambda: defaultdict(int))
    tot = defaultdict(lambda: defaultdict(int))   # cargo -> sq -> votos no estado/cidade
    sit = {}
    for r in rows(f"raw/votacao_candidato_munzona_{ano}.zip", f"votacao_candidato_munzona_{ano}_SP.csv"):
        if r["NR_TURNO"] != "1" or r["CD_CARGO"] not in cargos:
            continue
        v = int(r.get("QT_VOTOS_NOMINAIS_VALIDOS") or r["QT_VOTOS_NOMINAIS"] or 0)
        if not v:
            continue
        cg, sq, cm = r["CD_CARGO"], r["SQ_CANDIDATO"], r["CD_MUNICIPIO"]
        mun[(cg, cm)][sq] += v
        tot[cg][sq] += v
        if cm == CAP:
            zon[(cg, r["NR_ZONA"])][sq] += v
        if sq in sqs:
            sit[sq] = r["DS_SIT_TOT_TURNO"]
    for c in cs:
        cg, sq = c["cd_cargo"], c["sq"]
        allc = tot[cg]
        rank = 1 + sum(1 for s, v in allc.items() if v > allc.get(sq, 0))
        m = {}
        for (g, cm), d in mun.items():
            if g != cg or not d.get(sq):
                continue
            pos = 1 + sum(1 for v in d.values() if v > d[sq])
            m[T2I.get(cm, cm)] = [d[sq], sum(d.values()), pos]
        z = {}
        for (g, zn), d in zon.items():
            if g != cg:
                continue
            pos = 1 + sum(1 for v in d.values() if v > d.get(sq, 0))
            z[str(int(zn))] = [d.get(sq, 0), sum(d.values()), pos]
        out[c["id"]] = {"votos": allc.get(sq, 0), "nominais_cargo": sum(allc.values()),
                        "rank": rank, "ncand": len(allc), "sit": sit.get(sq, ""),
                        "mun": m, "zonas": z}
        print(c["id"], allc.get(sq, 0), "rank", rank, "/", len(allc), sit.get(sq), len(m), "mun", len(z), "zonas")

json.dump(out, open("votos.json", "w"), ensure_ascii=False, separators=(",", ":"))
