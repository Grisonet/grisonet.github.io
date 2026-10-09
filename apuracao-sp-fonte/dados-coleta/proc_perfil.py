#!/usr/bin/env python3
"""Acrescenta o PERFIL de cada candidato (dep. fed/est SP) ao financeiro-sp.json.

Fontes (TSE):
  - consulta_cand_2026_SP.csv               (sexo, cor/raça, instrução, estado civil, ocupação, UF nasc., federação)
  - consulta_cand_complementar_2026_SP.csv  (idade na posse, nacionalidade, quilombola, situação da candidatura)
  - bem_candidato_2026_SP.csv               (patrimônio declarado = soma dos bens)
    zips em https://cdn.tse.jus.br/estatistica/sead/odsele/{consulta_cand,consulta_cand_complementar,bem_candidato}/..._2026.zip
  - DivulgaCand, 1 JSON por candidato em <api_dir>/<sq>.json:
    https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura/buscar/2026/SP/20322002026/candidato/<sq>
    (identidade de gênero e orientação sexual — só vêm quando o candidato autorizou divulgar — e eleições anteriores).
    A API exige cabeçalhos de navegador (User-Agent, Referer, sec-ch-ua, sec-fetch-*), senão dá "Access Denied".
    ⚠️ Esses JSONs trazem CPF/título: NÃO versionar; aqui só se extraem os campos abaixo.

Uso: python3 proc_perfil.py <dir_csv> <api_dir> <financeiro-sp.json>
Não mexe nos campos financeiros nem em `seg`.
"""
import csv, json, os, sys
from collections import defaultdict

CSV_DIR, API_DIR, OUT = sys.argv[1:4]


def rd(nome):
    for raiz, _, arqs in os.walk(CSV_DIR):
        if nome in arqs:
            with open(os.path.join(raiz, nome), encoding="latin-1", newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
    raise SystemExit("faltou " + nome)


def lim(v):
    v = (v or "").strip()
    return None if v in ("", "#NULO", "#NULO#", "#NE", "#NE#", "-1", "-3") else v


def cap(v):
    v = lim(v)
    return v[:1].upper() + v[1:].lower() if v else None


cand = {r["SQ_CANDIDATO"]: r for r in rd("consulta_cand_2026_SP.csv")}
comp = {r["SQ_CANDIDATO"]: r for r in rd("consulta_cand_complementar_2026_SP.csv")}
bens = defaultdict(float)
for r in rd("bem_candidato_2026_SP.csv"):
    bens[r["SQ_CANDIDATO"]] += float(r["VR_BEM_CANDIDATO"].replace(",", "."))

d = json.load(open(OUT, encoding="utf-8"))
sem_api = 0
for c in d["cand"]:
    sq = c["sq"]
    a, b = cand[sq], comp[sq]
    c["gen"] = cap(a["DS_GENERO"])
    c["idade"] = int(b["NR_IDADE_DATA_POSSE"]) if lim(b["NR_IDADE_DATA_POSSE"]) else None
    c["cor"] = cap(a["DS_COR_RACA"])
    c["inst"] = cap(a["DS_GRAU_INSTRUCAO"])
    c["ec"] = cap(a["DS_ESTADO_CIVIL"])
    c["ocup"] = cap(a["DS_OCUPACAO"])
    c["ufn"] = lim(a["SG_UF_NASCIMENTO"])
    c["nac"] = cap(b["DS_NACIONALIDADE"])
    c["quil"] = b["ST_QUILOMBOLA"] == "S"
    c["fed"] = lim(a["NM_FEDERACAO"])
    c["sitc"] = cap(b["DS_SITUACAO_CANDIDATO_TOT"])
    c["bens"] = round(bens[sq], 2) if b["ST_DECLARAR_BENS"] == "S" else None
    # DivulgaCand
    for k in ("idg", "ors", "nant", "jaeleito", "reel22"):
        c.pop(k, None)
    p = os.path.join(API_DIR, sq + ".json")
    if not os.path.exists(p):
        sem_api += 1
        continue
    j = json.load(open(p, encoding="utf-8"))
    ic = j.get("infoComplementar") or {}
    c["idg"] = ic.get("identidadeGenero") if ic.get("generoPublicavel") else None
    c["ors"] = ic.get("orientacaoSexual") if ic.get("orientacaoSexualPublicavel") else None
    ant = [e for e in (j.get("eleicoesAnteriores") or []) if (e.get("nrAno") or 0) < 2026]
    eleito = lambda e: (e.get("situacaoTotalizacao") or "").startswith("Eleito")
    cargo = "Deputado Federal" if c["cargo"] == "DF" else "Deputado Estadual"
    c["nant"] = len(ant)
    c["jaeleito"] = any(eleito(e) for e in ant)
    c["reel22"] = any(e.get("nrAno") == 2022 and e.get("cargo") == cargo and eleito(e) for e in ant)

d["perfil"] = "consulta_cand + complementar + bens (TSE, 08/10/2026) e DivulgaCand"
json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(d["cand"]), "candidatos; sem ficha DivulgaCand:", sem_api)
