#!/usr/bin/env python3
"""Geolocaliza pelo endereço os locais de votação sem coordenada no cadastro do TSE.
Nominatim (OpenStreetMap), 1 consulta por segundo, com cache em geocache.json.
Só aceita o ponto se ele cair dentro do município (polígono do IBGE em sp-mun.geojson).
Marca o local com "osm" no campo 9 (posição pelo endereço)."""
import json, time, urllib.parse, urllib.request, os

MUN = json.load(open(os.path.expanduser("~/Documents/projetos/GR Data/apuracao-sp/sp-mun.geojson")))
POLY = {f["properties"]["id"]: (f["properties"]["name"], f["geometry"]) for f in MUN["features"]}
CACHE = json.load(open("geocache.json")) if os.path.exists("geocache.json") else {}

def inring(x, y, r):
    ins = False; j = len(r) - 1
    for i in range(len(r)):
        xi, yi = r[i]; xj, yj = r[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins
def inside(ibge, lon, lat):
    g = POLY[ibge][1]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return any(inring(lon, lat, p[0]) for p in polys)

def nominatim(params):
    key = json.dumps(params, sort_keys=True, ensure_ascii=False)
    if key in CACHE:
        return CACHE[key]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({**params, "format": "json", "limit": 3, "countrycodes": "br"})
    req = urllib.request.Request(url, headers={"User-Agent": "GRData-analise-votos/1.0 (contato: grisodata.com.br)"})
    for i in range(3):
        try:
            res = json.loads(urllib.request.urlopen(req, timeout=30).read())
            break
        except Exception:
            time.sleep(5)
    else:
        res = []
    time.sleep(1.1)
    CACHE[key] = res
    json.dump(CACHE, open("geocache.json", "w"), ensure_ascii=False)
    return res

def locate(ibge, nome, bairro, end):
    city = POLY[ibge][0]
    tries = []
    if end:
        tries.append({"street": end, "city": city, "state": "São Paulo"})
        tries.append({"q": f"{end}, {bairro}, {city}, SP"})
    tries.append({"q": f"{nome}, {city}, SP"})
    for t in tries:
        for r in nominatim(t):
            lat, lon = float(r["lat"]), float(r["lon"])
            # rejeita resultado no nível de cidade/estado (não é o endereço)
            if r.get("addresstype") in ("city", "town", "municipality", "state", "county", "region"):
                continue
            if inside(ibge, lon, lat):
                return round(lat, 5), round(lon, 5)
    return None

Y = [2008, 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026]
D = {y: json.load(open(f"secoes_{y}.json")) for y in Y}
todo = {}
for y in Y:
    for l in D[y]["locais"]:
        if l[5] is None:
            todo.setdefault((l[0], l[8] or "", l[3]), (l[4],))
print("endereços a geolocalizar:", len(todo), flush=True)
found = {}
for n, ((ibge, end, nome), (bairro,)) in enumerate(todo.items()):
    found[(ibge, end, nome)] = locate(ibge, nome, bairro, end)
    if (n + 1) % 25 == 0:
        print(f"  {n+1}/{len(todo)} · achados {sum(1 for v in found.values() if v)}", flush=True)
for y in Y:
    a = b = 0
    for l in D[y]["locais"]:
        if l[5] is not None:
            continue
        g = found.get((l[0], l[8] or "", l[3]))
        if g:
            l[5], l[6] = g
            while len(l) < 10:
                l.append("")
            l[9] = "osm"; a += 1
        else:
            b += 1
    json.dump(D[y], open(f"secoes_{y}.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(y, "geolocalizados", a, "sem posição", b, flush=True)
