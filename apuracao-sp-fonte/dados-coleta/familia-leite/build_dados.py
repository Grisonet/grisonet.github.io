#!/usr/bin/env python3
"""Junta candidaturas + votos + resumo financeiro em dados.json e grava os lançamentos
em financeiro.json (pasta de publicação: site/leite/)."""
import json, os, shutil
from collections import Counter, defaultdict

from cand_cfg import CANDS, P

OUT = "site/leite"
os.makedirs(OUT + "/fotos", exist_ok=True)
V = json.load(open("votos.json"))
F = json.load(open("financeiro.json"))

def refine(r, ano):
    """2014: o dinheiro de empresa chegava via partido; o TSE registra o doador originário."""
    if r["cat"] == "Repasses de partido e candidatos" and r.get("orig"):
        if r.get("orig_tipo") == "J" and not any(w in r["orig"].upper() for w in ("PARTIDO", "DEMOCRATAS", "COMITE", "ELEICAO", "DIRETORIO")):
            return "Doações de empresas (via partido)"
        if r.get("orig_tipo") == "F":
            return "Doações de pessoas físicas (via partido)"
    return r["cat"]

cands, fin_out = [], {}
for c in CANDS:
    cid = c["id"]; v = V[cid]; f = F[cid]
    foto = [x for x in os.listdir("fotos") if x.startswith(c["sq"])][0]
    shutil.copy("fotos/" + foto, f"{OUT}/fotos/{cid}.jpg")
    for r in f["rec"]:
        r["cat"] = refine(r, c["ano"])
    rec_cat = Counter(); desp_tipo = Counter(); forn = Counter(); doad = Counter(); imp_f = Counter()
    for r in f["rec"]:
        rec_cat[r["cat"]] += r["valor"]
        doad[(r.get("orig") or r["doador"]) if r["cat"].endswith("(via partido)") else r["doador"]] += r["valor"]
    estim = sum(r["valor"] for r in f["rec"] if "estim" in (r["especie"] or "").lower())
    for d in f["desp"]:
        desp_tipo[d["tipo"] or "Não informado"] += d["valor"]; forn[d["fornecedor"] or "Não informado"] += d["valor"]
        if d["imp"]:
            imp_f[d["fornecedor"]] += d["valor"]
    rt = round(sum(rec_cat.values()), 2); dt = round(sum(desp_tipo.values()), 2)
    outros = round(sum(x for k, x in desp_tipo.items() if k.lower().startswith("doações financeiras a outros")), 2)
    gasto = round(dt - outros, 2)
    fundo = rec_cat.get("Fundo Eleitoral (FEFC)", 0) + rec_cat.get("Fundo Partidário", 0)
    doac = sum(x for k, x in rec_cat.items() if k.startswith("Doações"))
    cands.append({
        **{k: c[k] for k in ("id", "ano", "p", "cargo", "cd_cargo", "n", "partido", "sq")},
        "nome": P[c["p"]]["nome"], "foto": f"leite/fotos/{cid}.jpg",
        "votos": v["votos"], "rank": v["rank"], "ncand": v["ncand"], "sit": v["sit"],
        "nominais_cargo": v["nominais_cargo"], "mun": v["mun"], "zonas": v["zonas"],
        "fin": {
            "receita": rt, "despesa": dt, "repasse_outros": outros, "gasto": gasto,
            "custo_voto": round(gasto / v["votos"], 2) if v["votos"] else None,
            "impulsionamento": round(sum(imp_f.values()), 2),
            "imp_fornecedores": {k: round(x, 2) for k, x in imp_f.most_common()},
            "fundo_publico": round(fundo, 2), "doacoes": round(doac, 2),
            "proprios": round(rec_cat.get("Recursos próprios", 0), 2),
            "estimavel": round(estim, 2),
            "rec_cat": {k: round(x, 2) for k, x in rec_cat.most_common()},
            "desp_tipo": {k: round(x, 2) for k, x in desp_tipo.most_common(12)},
            "fornecedores": [[k, round(x, 2)] for k, x in forn.most_common(10)],
            "doadores": [[k, round(x, 2)] for k, x in doad.most_common(10)],
            "n_rec": len(f["rec"]), "n_desp": len(f["desp"]),
        }})
    fin_out[cid] = f

dados = {"gerado": __import__("datetime").datetime.now().strftime("%d/%m/%Y"),
         "pessoas": P, "cands": cands}
json.dump(dados, open(f"{OUT}/dados.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(fin_out, open(f"{OUT}/financeiro.json", "w"), ensure_ascii=False, separators=(",", ":"))
for y in (2014, 2016, 2018, 2020, 2022, 2026):
    shutil.copy(f"secoes_{y}.json", f"{OUT}/secoes_{y}.json")
shutil.copy("sp-distritos.geojson", f"{OUT}/sp-distritos.geojson")
for c in cands:
    f = c["fin"]
    print(f'{c["id"]:9} votos {c["votos"]:>7,} | gasto R$ {f["gasto"]:>12,.0f} | R$/voto {f["custo_voto"]:>6} | fundo {f["fundo_publico"]:>12,.0f} | doações {f["doacoes"]:>12,.0f} | imp {f["impulsionamento"]:>9,.0f}')
