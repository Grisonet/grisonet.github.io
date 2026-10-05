#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cruza resultados (votos/eleito) x prestacao de contas (gasto, impulsionamento, origem do recurso)
para dep. federal e estadual de SP. Gera financeiro-sp.json."""
import csv, json, urllib.request, ssl
csv.field_size_limit(10_000_000)
ctx = ssl.create_default_context()
HERE = "/private/tmp/claude-501/-Users-griso/dc703419-d903-40b9-9f31-294a56bf5a68/scratchpad"

def getj(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"x"}), timeout=30, context=ctx).read())
def toi(s):
    try: return int(str(s).replace('.','')) if s not in (None,'') else 0
    except: return 0
def vf(s):
    try: return float(str(s).replace('.','').replace(',','.'))
    except: return 0.0

# ---- 1) resultados: votos, eleito, tipo de vaga, por sqcand ----
def load_result(cargo_cd, cargo_key):
    d = getj(f"https://resultados.tse.jus.br/oficial/ele2026/6259/dados/sp/sp-c{cargo_cd}-e006259-u.json")
    carg = d["carg"][0]; qe = toi(carg.get("qe")); thr = qe*0.1
    out = {}
    for a in carg.get("agr", []):
        vag = toi(a.get("vag"))
        partyTot = sum(toi(p.get("tvtn"))+toi(p.get("tvtl")) for p in a.get("par", []))
        qp = qe and partyTot//qe or 0
        cc = []
        for p in a.get("par", []):
            for c in p.get("cand", []):
                out[c["sqcand"]] = {"nm": c.get("nmu") or c.get("nm"), "nr": c["n"], "sg": p.get("sg",""),
                                    "cargo": cargo_key, "votos": toi(c.get("vap")), "pvap": c.get("pvap","0"),
                                    "eleito": False, "tipo": None, "agr": a.get("com","")}
                cc.append((c["sqcand"], toi(c.get("vap"))))
        elig = sorted([x for x in cc if x[1] >= thr], key=lambda x:-x[1])[:vag] if vag else []
        for i,(sq,v) in enumerate(elig):
            out[sq]["eleito"] = True
            out[sq]["tipo"] = "direta" if v>=qe else ("qp" if i<qp else "media")
    return out

cands = {}
cands.update(load_result("0006","DF"))
cands.update(load_result("0007","DE"))
print("candidatos (resultados):", len(cands))

# ---- 2) despesas: total, impulsionamento, impuls meta ----
def is_meta(nm):
    nm = nm.upper()
    return any(k in nm for k in ("FACEBOOK","DLOCAL","EBANX","META "))
for sq in cands: cands[sq].update(desp=0.0, imp=0.0, imp_meta=0.0)
with open(f"{HERE}/despesas_contratadas_candidatos_2026_SP.csv", encoding="latin-1") as f:
    for row in csv.DictReader(f, delimiter=';'):
        sq = row["SQ_CANDIDATO"]
        if sq not in cands: continue
        val = vf(row["VR_DESPESA_CONTRATADA"]); cands[sq]["desp"] += val
        if "IMPULS" in row["DS_ORIGEM_DESPESA"].upper():
            cands[sq]["imp"] += val
            if is_meta(row.get("NM_FORNECEDOR_RFB") or row.get("NM_FORNECEDOR") or ""):
                cands[sq]["imp_meta"] += val

# ---- 3) receitas: total e por origem ----
for sq in cands: cands[sq].update(rec=0.0, fefc=0.0, fpart=0.0, prop=0.0, pf=0.0, col=0.0, outr=0.0)
with open(f"{HERE}/receitas_candidatos_2026_SP.csv", encoding="latin-1") as f:
    for row in csv.DictReader(f, delimiter=';'):
        sq = row["SQ_CANDIDATO"]
        if sq not in cands: continue
        val = vf(row["VR_RECEITA"]); c = cands[sq]; c["rec"] += val
        fonte = row["DS_FONTE_RECEITA"].upper(); orig = row["DS_ORIGEM_RECEITA"].upper()
        if "FUNDO ESPECIAL" in fonte: c["fefc"] += val
        elif "FUNDO PARTID" in fonte: c["fpart"] += val
        elif "PRÓPRIOS" in orig or "PROPRIOS" in orig: c["prop"] += val
        elif "PESSOAS FÍSICAS" in orig or "PESSOAS FISICAS" in orig: c["pf"] += val
        elif "FINANCIAMENTO COLETIVO" in orig: c["col"] += val
        else: c["outr"] += val

# ---- 4) monta registros + resumo ----
rows = []
for sq, c in cands.items():
    publico = round(c["fefc"]+c["fpart"], 2)
    rows.append({
        "sq": sq, "nm": c["nm"], "nr": c["nr"], "sg": c["sg"], "cargo": c["cargo"],
        "votos": c["votos"], "pvap": c["pvap"], "eleito": c["eleito"], "tipo": c["tipo"],
        "desp": round(c["desp"],2), "imp": round(c["imp"],2), "imp_meta": round(c["imp_meta"],2),
        "rec": round(c["rec"],2), "fefc": round(c["fefc"],2), "fpart": round(c["fpart"],2),
        "publico": publico, "prop": round(c["prop"],2), "pf": round(c["pf"],2),
        "col": round(c["col"],2), "outr": round(c["outr"],2),
        "cpv": round(c["desp"]/c["votos"],2) if c["votos"] else None,   # custo por voto
    })
rows.sort(key=lambda r: -r["votos"])

def agg(filt):
    sel = [r for r in rows if filt(r)]
    return {"n": len(sel),
            "desp": round(sum(r["desp"] for r in sel),2),
            "imp": round(sum(r["imp"] for r in sel),2),
            "imp_meta": round(sum(r["imp_meta"] for r in sel),2),
            "fefc": round(sum(r["fefc"] for r in sel),2),
            "fpart": round(sum(r["fpart"] for r in sel),2)}
data = {
    "gerado": "prestacao de contas TSE 2026 (parcial, 04/10) x resultados oficiais",
    "resumo": {"todos": agg(lambda r:True),
               "eleitos": agg(lambda r:r["eleito"]),
               "DF": agg(lambda r:r["cargo"]=="DF"),
               "DE": agg(lambda r:r["cargo"]=="DE")},
    "cand": rows,
}
open(f"{HERE}/financeiro-sp.json","w",encoding="utf-8").write(json.dumps(data,ensure_ascii=False,separators=(",",":")))
print("gravado financeiro-sp.json |", len(rows), "candidatos")
print("Impuls Meta total: R$ %.2f" % data["resumo"]["todos"]["imp_meta"])
print("Top 5 impuls Meta:")
for r in sorted(rows,key=lambda r:-r["imp_meta"])[:5]:
    print(f"  {r['nm'][:28]:28s} {r['sg']:6s} {r['cargo']} votos={r['votos']:>8} impMeta=R${r['imp_meta']:>12,.0f} eleito={r['eleito']}".replace(',','.'))
