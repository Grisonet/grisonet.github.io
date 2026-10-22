#!/usr/bin/env python3
"""Prestação de contas das 10 candidaturas da família Leite (TSE, dados abertos).
Extrai cada receita e cada despesa contratada (lançamento a lançamento) num formato único
para 2014-2026 e classifica a origem do dinheiro.
Saída: financeiro.json  {id: {"rec": [...], "desp": [...]}}"""
import csv, io, json, re, subprocess
from collections import Counter

from cand_cfg import CANDS

SQ = {c["sq"]: c for c in CANDS}

def rows(zp, member):
    p = subprocess.Popen(["unzip", "-p", zp, member], stdout=subprocess.PIPE)
    yield from csv.DictReader(io.TextIOWrapper(p.stdout, encoding="latin-1", newline=""), delimiter=";")
    p.wait()

def num(s):
    s = (s or "0").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0

def nul(s):
    s = (s or "").strip()
    return "" if s in ("#NULO", "#NULO#", "#NE", "-1", "-4") else s

def doc_pub(d):
    """Só CNPJ (empresa/partido/comitê); CPF de pessoa física não vai para a página."""
    d = re.sub(r"\D", "", d or "")
    return d if len(d) == 14 else ""

def cat_receita(fonte, origem):
    f, o = fonte.upper(), origem.lower()
    if "ESPECIAL" in f:
        return "Fundo Eleitoral (FEFC)"
    if "PARTID" in f:
        return "Fundo Partidário"
    if "jur" in o:
        return "Doações de empresas"
    if "próprio" in o or "proprio" in o:
        return "Recursos próprios"
    if "físicas" in o or "fisicas" in o or "internet" in o or "coletivo" in o:
        return "Doações de pessoas físicas"
    if "partido" in o or "candidato" in o or "comit" in o:
        return "Repasses de partido e candidatos"
    return "Outras receitas"

def impuls(tipo, forn):
    return "impulsionamento" in tipo.lower()

out = {c["id"]: {"rec": [], "desp": []} for c in CANDS}

def add_rec(sq, data, valor, fonte, origem, especie, doador, doc, orig_nome="", orig_tipo=""):
    out[SQ[sq]["id"]]["rec"].append({
        "data": data[:10], "valor": valor, "cat": cat_receita(fonte, origem),
        "fonte": fonte, "origem": origem, "especie": especie,
        "doador": doador, "cnpj": doc_pub(doc), "orig": orig_nome, "orig_tipo": orig_tipo})

def add_desp(sq, data, valor, tipo, forn, doc, desc):
    out[SQ[sq]["id"]]["desp"].append({
        "data": data[:10], "valor": valor, "tipo": tipo, "fornecedor": forn,
        "cnpj": doc_pub(doc), "desc": desc, "imp": impuls(tipo, forn)})

# ---------- 2014 e 2016 (layout antigo) ----------
OLD = {2014: ("raw/prestacao_final_2014.zip", "receitas_candidatos_2014_SP.txt", "despesas_candidatos_2014_SP.txt"),
       2016: ("raw/prestacao_contas_final_2016.zip", "receitas_candidatos_prestacao_contas_final_2016_SP.txt",
              "despesas_candidatos_prestacao_contas_final_2016_SP.txt")}
for ano, (zp, rm, dm) in OLD.items():
    for r in rows(zp, rm):
        sq = r["Sequencial Candidato"]
        if sq not in SQ:
            continue
        add_rec(sq, r["Data da receita"], num(r["Valor receita"]), nul(r["Fonte recurso"]), nul(r["Tipo receita"]),
                nul(r["Especie recurso"]), nul(r["Nome do doador (Receita Federal)"]) or nul(r["Nome do doador"]),
                r["CPF/CNPJ do doador"], nul(r.get("Nome do doador originário (Receita Federal)")) or nul(r.get("Nome do doador originário")),
                nul(r.get("Tipo doador originário")))
    for r in rows(zp, dm):
        sq = r["Sequencial Candidato"]
        if sq not in SQ:
            continue
        add_desp(sq, r["Data da despesa"], num(r["Valor despesa"]), nul(r["Tipo despesa"]),
                 nul(r["Nome do fornecedor (Receita Federal)"]) or nul(r["Nome do fornecedor"]),
                 r["CPF/CNPJ do fornecedor"], nul(r["Descriçao da despesa"]))

# ---------- 2018 em diante ----------
for ano in (2018, 2020, 2022, 2026):
    zp = f"raw/prestacao_de_contas_eleitorais_candidatos_{ano}.zip"
    for r in rows(zp, f"receitas_candidatos_{ano}_SP.csv"):
        sq = r["SQ_CANDIDATO"]
        if sq not in SQ:
            continue
        add_rec(sq, r["DT_RECEITA"], num(r["VR_RECEITA"]), nul(r["DS_FONTE_RECEITA"]), nul(r["DS_ORIGEM_RECEITA"]),
                nul(r["DS_ESPECIE_RECEITA"]) + (" · " + nul(r["DS_NATUREZA_RECEITA"]) if nul(r["DS_NATUREZA_RECEITA"]) else ""),
                nul(r["NM_DOADOR_RFB"]) or nul(r["NM_DOADOR"]), r["NR_CPF_CNPJ_DOADOR"])
    for r in rows(zp, f"despesas_contratadas_candidatos_{ano}_SP.csv"):
        sq = r["SQ_CANDIDATO"]
        if sq not in SQ:
            continue
        add_desp(sq, r["DT_DESPESA"], num(r["VR_DESPESA_CONTRATADA"]), nul(r["DS_ORIGEM_DESPESA"]),
                 nul(r["NM_FORNECEDOR_RFB"]) or nul(r["NM_FORNECEDOR"]), r["NR_CPF_CNPJ_FORNECEDOR"], nul(r["DS_DESPESA"]))

for c in CANDS:
    d = out[c["id"]]
    tr = sum(x["valor"] for x in d["rec"]); td = sum(x["valor"] for x in d["desp"])
    ti = sum(x["valor"] for x in d["desp"] if x["imp"])
    cats = Counter()
    for x in d["rec"]:
        cats[x["cat"]] += x["valor"]
    print(f'{c["id"]:9} rec {len(d["rec"]):5} R$ {tr:>14,.2f} | desp {len(d["desp"]):5} R$ {td:>14,.2f} | imp R$ {ti:>12,.2f}')
    print("          ", {k: round(v) for k, v in cats.most_common()})
json.dump(out, open("financeiro.json", "w"), ensure_ascii=False, separators=(",", ":"))
