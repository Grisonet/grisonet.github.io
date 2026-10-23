"""2008: o arquivo traz o nome do local com siglas antigas (EEPG, EEPSG) e sem endereço.
Compara o nome, sem as siglas e títulos, com os locais da mesma zona em 2012-2026."""
import json, re, unicodedata, difflib
STOP = {"ee","eepg","eepsg","eeps","eepsg","emef","emei","emeif","eeb","ceu","escola","estadual","municipal","de","da","do","das","dos","e",
        "ensino","fundamental","medio","prof","profa","professor","professora","dr","dra","doutor","pres","presidente","cel","colegio","col",
        "eem","em","epg","psg","pg","sg","1o","2o","grau","graus","i","ii","unidade","predio","sesi","senai","etec","fac","faculdade","faculdades"}
def toks(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return [t for t in re.findall(r"[a-z0-9]+", s) if t not in STOP]
def key(s): return " ".join(toks(s))
ref = {}
for y in (2012, 2014, 2016, 2018, 2020, 2022, 2026):
    for l in json.load(open(f"secoes_{y}.json"))["locais"]:
        if l[5] is not None and l[0] == "3550308":
            ref.setdefault((l[1], key(l[3])), (l[5], l[6], l[7]))
byz = {}
for (z, k), g in ref.items():
    byz.setdefault(z, []).append((k, g))
j = json.load(open("secoes_2008.json")); a = b = 0
for l in j["locais"]:
    if l[5] is not None:
        continue
    k = key(l[3]); best = None; br = 0
    for kk, g in byz.get(l[1], []):
        r = difflib.SequenceMatcher(None, k, kk).ratio()
        if set(k.split()) and set(k.split()) <= set(kk.split()):
            r = max(r, .9)
        if r > br:
            br, best = r, g
    if best and br >= .82 and len(k) >= 5:
        l[5], l[6] = best[0], best[1]; l[7] = l[7] or best[2]
        while len(l) < 10: l.append("")
        l[9] = "nome"; a += 1
    else:
        b += 1
json.dump(j, open("secoes_2008.json", "w"), ensure_ascii=False, separators=(",", ":"))
print("2008 posicionados pelo nome (mesma zona):", a, "ainda sem:", b)
