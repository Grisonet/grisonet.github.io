#!/usr/bin/env python3
"""Ordem de chegada simulada para os replays de 2014 e 2018.

O TSE não publicou a hora de chegada das urnas nesses anos (2018 só traz o horário
de encerramento em hora local; 2014, nenhum horário). Para refazer a noite, cada seção
recebe o horário de chegada de uma seção do mesmo município em 2022, no mesmo quantil:
assim se preserva a geografia da chegada, que é o que distorce o placar.

Também extrai os eleitores aptos de cada seção do boletim de urna (bweb) do 2º turno.

Saída: base/{ano}_t2_ordem.json e base/{ano}_t2_aptos.json
Uso:   python3 build_ordem_simulada.py 2018
"""
import csv, glob, io, itertools, json, os, random, sys, zipfile

ano = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
t2 = json.load(open(os.path.join(here, "base", f"{ano}_t2.json")))
ordem22 = json.load(open(os.path.join(here, "base", "2022_t2_ordem.json")))

por_mun, por_uf = {}, {}
for k, t in ordem22.items():
    uf, mun = k.split("|")[:2]
    por_mun.setdefault(f"{uf}|{mun}", []).append(t)
    por_uf.setdefault(uf, []).append(t)
for d in (por_mun, por_uf):
    for v in d.values():
        v.sort()

rng = random.Random(int(ano))
grupos = {}
for k in t2:
    uf, mun = k.split("|")[:2]
    grupos.setdefault(f"{uf}|{mun}", []).append(k)
ordem = {}
for um, chaves in grupos.items():
    ref = por_mun.get(um) or por_uf.get(um.split("|")[0]) or sorted(ordem22.values())
    rng.shuffle(chaves)
    n = len(chaves)
    for i, k in enumerate(chaves):
        ordem[k] = ref[min(int((i + 0.5) / n * len(ref)), len(ref) - 1)]
json.dump(ordem, open(os.path.join(here, "base", f"{ano}_t2_ordem.json"), "w"), separators=(",", ":"))

# eleitores aptos por seção (bweb do 2º turno)
aptos = {}
for zp in sorted(glob.glob(os.path.join(here, "raw", f"bweb{ano[2:]}", "*.zip"))):
    z = zipfile.ZipFile(zp)
    name = [n for n in z.namelist() if n.lower().endswith((".csv", ".txt"))][0]
    rd = csv.reader(io.TextIOWrapper(z.open(name), encoding="latin-1"), delimiter=";")
    primeira = next(rd)
    if "QT_APTOS" in primeira:
        h = {c.replace(" ", ""): i for i, c in enumerate(primeira)}
        iUF, iMU, iZ, iS, iC, iA = (h[c] for c in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO_PERGUNTA", "QT_APTOS"))
        linhas = rd
    else:   # 2014: sem cabeçalho (leiame do TSE): UF=4, cargo=5, zona=7, seção=8, município=12, aptos=15
        iUF, iC, iZ, iS, iMU, iA = 4, 5, 7, 8, 12, 15
        linhas = itertools.chain([primeira], rd)
    for r in linhas:
        if r[iC] != "1":
            continue
        k = f"{r[iUF]}|{int(r[iMU])}|{int(r[iZ])}|{int(r[iS])}"
        aptos.setdefault(k, int(r[iA]))
json.dump(aptos, open(os.path.join(here, "base", f"{ano}_t2_aptos.json"), "w"), separators=(",", ":"))
print(ano, "ordem", len(ordem), "aptos", len(aptos), "casam com a base", len(aptos.keys() & t2.keys()))
