import csv,io,zipfile,re,json,sys
out=[]
for y in [2014,2016,2018,2020,2022,2024,2026]:
    z=zipfile.ZipFile(f"cand_{y}.zip")
    names=[n for n in z.namelist() if n.endswith(".csv")]
    sp=[n for n in names if n.endswith("_SP.csv")] or [n for n in names if "BRASIL" in n] or names
    for n in sp:
        for r in csv.DictReader(io.TextIOWrapper(z.open(n),encoding="latin-1"),delimiter=";"):
            nm=r["NM_CANDIDATO"]
            if r["SG_UF"]!="SP": continue
            if not re.search(r"MILTON LEITE|ALEXANDRE .*LEITE|^MILTON .*LEITE", nm) and not re.search(r"MILTON LEITE|ALEXANDRE LEITE",r["NM_URNA_CANDIDATO"]): continue
            if r.get("NR_TURNO","1")!="1": continue
            d={k:r.get(k) for k in ["ANO_ELEICAO","NM_UE","SG_UE","CD_CARGO","DS_CARGO","SQ_CANDIDATO","NR_CANDIDATO","NM_CANDIDATO","NM_URNA_CANDIDATO","SG_PARTIDO","DS_SITUACAO_CANDIDATURA","DS_SIT_TOT_TURNO","NR_CPF_CANDIDATO","DT_NASCIMENTO","CD_ELEICAO"]}
            out.append(d); print(y, d["NM_UE"], d["DS_CARGO"], d["NR_CANDIDATO"], d["NM_URNA_CANDIDATO"], "|", d["NM_CANDIDATO"], d["SG_PARTIDO"], d["DS_SIT_TOT_TURNO"], d["DS_SITUACAO_CANDIDATURA"], d["SQ_CANDIDATO"], d["NR_CPF_CANDIDATO"], d["CD_ELEICAO"])
json.dump(out,open("../cands.json","w"),ensure_ascii=False,indent=1)
