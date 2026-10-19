#!/usr/bin/env python3
"""Base por seção a partir dos dados abertos do TSE (votacao_secao_{ano}_{BR|UF}.zip).

Saída: base/<nome>.json -> {"UF|MUN|ZONA|SECAO": [va, vb, outros, brancos, nulos]}
  va / vb = votos dos candidatos "a" e "b" do confronto (números passados em --numeros)
e base/municipios_<ano>.json -> {"UF|MUN": nome}

Exemplos:
  python3 build_base.py 2026 1                                   # Presidente, 22×13 -> base/2026_t1.json
  python3 build_base.py 2018 2 --numeros 17,13                   # -> base/2018_t2.json
  python3 build_base.py 2026 1 --cargo 3 --uf DF --numeros 11,13 --nome gov_df_2026_t1
"""
import argparse, csv, io, json, os, zipfile

ap = argparse.ArgumentParser()
ap.add_argument("ano"); ap.add_argument("turno")
ap.add_argument("--numeros", default="22,13")
ap.add_argument("--cargo", default="1")
ap.add_argument("--uf", default="BR")
ap.add_argument("--nome")
a = ap.parse_args()
na, nb = a.numeros.split(",")
here = os.path.dirname(os.path.abspath(__file__))
zp = os.path.join(here, "raw", f"votacao_secao_{a.ano}_{a.uf}.zip")
if not os.path.exists(zp):
    zp = os.path.join(here, "raw", "gov26", f"votacao_secao_{a.ano}_{a.uf}.zip")
z = zipfile.ZipFile(zp)
name = [n for n in z.namelist() if n.lower().endswith((".csv", ".txt"))][0]
rd = csv.reader(io.TextIOWrapper(z.open(name), encoding="latin-1"), delimiter=";")
h = {c: i for i, c in enumerate(next(rd))}
iT, iUF, iMU, iNM, iZ, iS, iC, iV, iQ = (h[c] for c in (
    "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS"))

secoes, muns = {}, {}
for r in rd:
    if r[iT] != a.turno or r[iC] != a.cargo:
        continue
    k = f"{r[iUF]}|{int(r[iMU])}|{int(r[iZ])}|{int(r[iS])}"
    v = secoes.get(k)
    if v is None:
        v = secoes[k] = [0, 0, 0, 0, 0]
        muns[f"{r[iUF]}|{int(r[iMU])}"] = r[iNM]
    n, q = r[iV], int(r[iQ])
    v[0 if n == na else 1 if n == nb else 3 if n == "95" else 4 if n == "96" else 2] += q

nome = a.nome or f"{a.ano}_t{a.turno}"
os.makedirs(os.path.join(here, "base"), exist_ok=True)
json.dump(secoes, open(os.path.join(here, "base", f"{nome}.json"), "w"), separators=(",", ":"))
mp = os.path.join(here, "base", f"municipios_{a.ano}.json")
todos = json.load(open(mp)) if os.path.exists(mp) else {}
todos.update(muns)
json.dump(todos, open(mp, "w"), ensure_ascii=False)
tot = [sum(v[i] for v in secoes.values()) for i in range(5)]
print(nome, len(secoes), "seções", f"{na}/{nb}/outros/br/nu =", tot)
