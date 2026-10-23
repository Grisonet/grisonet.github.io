"""Completa lat/long de locais sem coordenada usando o mesmo local em outros anos
(mesma cidade+zona+número, depois mesma cidade+nome)."""
import json, re, unicodedata
from cand_cfg import CANDS
def nk(s): return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFD",s or "").encode("ascii","ignore").decode().lower())
Y=[2026,2024,2022,2020,2018,2016,2014,2012,2008]
D={y:json.load(open(f"secoes_{y}.json")) for y in Y}
byn={};byname={}
for y in Y:
    for l in D[y]["locais"]:
        if l[5] is None: continue
        byn.setdefault((l[0],l[1],l[2]),(l[5],l[6],l[7])); byname.setdefault((l[0],nk(l[3])),(l[5],l[6],l[7]))
for y in Y:
    a=b=0
    for l in D[y]["locais"]:
        if l[5] is not None: continue
        g=byname.get((l[0],nk(l[3]))) or (byn.get((l[0],l[1],l[2])) if y>=2012 else None)  # antes de 2012 o número do local não é comparável
        if g: l[5],l[6]=g[0],g[1]; l[7]=l[7] or g[2]; a+=1
        else: b+=1
    print(y,"preenchidos",a,"ainda sem",b)
    json.dump(D[y],open(f"secoes_{y}.json","w"),ensure_ascii=False,separators=(",",":"))
