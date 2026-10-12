#!/usr/bin/env python3
"""Atualiza SÓ os campos financeiros do financeiro-sp.json com uma prestação de contas mais nova,
preservando votos, eleito/tipo, `seg` (seguidores) e os campos de perfil.

Uso: python3 atualiza_financeiro.py <dir_csv_prestacao> <financeiro-sp.json> ["DD/MM/AAAA"]
  Sem a data, usa a DT_GERACAO que vem no próprio CSV do TSE. Se nada mudou, não regrava o arquivo.
  Roda sozinho todo dia pelo workflow .github/workflows/atualiza-prestacao.yml.
  dir_csv_prestacao = pasta com despesas_contratadas_candidatos_2026_SP.csv e receitas_candidatos_2026_SP.csv
  (zip em cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip)
Mesmas regras do proc_financeiro.py. Imprime o que mudou."""
import csv, json, sys
csv.field_size_limit(10**9)
DIR, OUT = sys.argv[1:3]
ROT = sys.argv[3] if len(sys.argv) > 3 else None

def vf(s):
    try: return float(str(s).replace(".", "").replace(",", "."))
    except ValueError: return 0.0

def is_meta(nm):
    nm = nm.upper()
    return any(k in nm for k in ("FACEBOOK", "DLOCAL", "EBANX", "META "))

d = json.load(open(OUT, encoding="utf-8"))
C = {c["sq"]: c for c in d["cand"]}
antes = {sq: (c["desp"], c["rec"], c["imp_meta"], c["publico"]) for sq, c in C.items()}
N = {sq: dict(desp=0.0, imp=0.0, imp_meta=0.0, rec=0.0, fefc=0.0, fpart=0.0, prop=0.0, pf=0.0, col=0.0, outr=0.0) for sq in C}

with open(f"{DIR}/despesas_contratadas_candidatos_2026_SP.csv", encoding="latin-1") as f:
    for r in csv.DictReader(f, delimiter=";"):
        ROT = ROT or r["DT_GERACAO"]
        n = N.get(r["SQ_CANDIDATO"])
        if n is None: continue
        v = vf(r["VR_DESPESA_CONTRATADA"]); n["desp"] += v
        if "IMPULS" in r["DS_ORIGEM_DESPESA"].upper():
            n["imp"] += v
            if is_meta(r.get("NM_FORNECEDOR_RFB") or r.get("NM_FORNECEDOR") or ""): n["imp_meta"] += v
with open(f"{DIR}/receitas_candidatos_2026_SP.csv", encoding="latin-1") as f:
    for r in csv.DictReader(f, delimiter=";"):
        n = N.get(r["SQ_CANDIDATO"])
        if n is None: continue
        v = vf(r["VR_RECEITA"]); n["rec"] += v
        fonte = r["DS_FONTE_RECEITA"].upper(); orig = r["DS_ORIGEM_RECEITA"].upper()
        if "FUNDO ESPECIAL" in fonte: n["fefc"] += v
        elif "FUNDO PARTID" in fonte: n["fpart"] += v
        elif "PRÓPRIOS" in orig or "PROPRIOS" in orig: n["prop"] += v
        elif "PESSOAS FÍSICAS" in orig or "PESSOAS FISICAS" in orig: n["pf"] += v
        elif "FINANCIAMENTO COLETIVO" in orig: n["col"] += v
        else: n["outr"] += v

for sq, c in C.items():
    n = N[sq]
    for k, v in n.items(): c[k] = round(v, 2)
    c["publico"] = round(n["fefc"] + n["fpart"], 2)
    c["cpv"] = round(n["desp"] / c["votos"], 2) if c["votos"] else None

def agg(f):
    s = [c for c in d["cand"] if f(c)]
    return {"n": len(s), **{k: round(sum(c[k] for c in s), 2) for k in ("desp", "imp", "imp_meta", "fefc", "fpart")}}
seg = d["resumo"].get("seg_cobertura")
d["resumo"] = {"todos": agg(lambda c: True), "eleitos": agg(lambda c: c["eleito"]), "DF": agg(lambda c: c["cargo"] == "DF"), "DE": agg(lambda c: c["cargo"] == "DE")}
if seg: d["resumo"]["seg_cobertura"] = seg
mudou = sum(1 for sq, c in C.items() if (c["desp"], c["rec"], c["imp_meta"], c["publico"]) != antes[sq])
if not mudou and d.get("data_prestacao"):
    print("nada mudou desde", d["data_prestacao"]); sys.exit(0)
d["gerado"] = f"prestacao de contas TSE 2026 (parcial, dados de {ROT}) x resultados oficiais"
d["data_prestacao"] = ROT
json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

f = lambda v: f"{v:,.0f}".replace(",", ".")
tot = lambda i: sum(a[i] for a in antes.values())
print("candidatos:", len(C), "| gasto mudou em", sum(1 for sq, c in C.items() if abs(c["desp"] - antes[sq][0]) > 1), "| receita mudou em", sum(1 for sq, c in C.items() if abs(c["rec"] - antes[sq][1]) > 1))
for nome, i, k in (("gasto", 0, "desp"), ("receita", 1, "rec"), ("anúncios Meta", 2, "imp_meta"), ("dinheiro público", 3, "publico")):
    a = tot(i); b = sum(c[k] for c in C.values())
    print(f"  {nome}: R$ {f(a)} -> R$ {f(b)} ({100*(b-a)/a:+.1f}%)")
print("maiores aumentos de gasto:")
for sq, c in sorted(C.items(), key=lambda kv: -(kv[1]["desp"] - antes[kv[0]][0]))[:12]:
    print(f"  {c['nm'][:28]:<28}{c['sg']:<8}{c['cargo']} {f(antes[sq][0]):>11} -> {f(c['desp']):>11}  eleito={c['eleito']}")
