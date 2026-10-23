"""Distrito da capital (ponto no polígono)."""
import json
# ---------- distritos da capital ----------
dist = json.load(open("sp-distritos.geojson"))["features"]
def _inring(x, y, ring):
    ins = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins
DB = []
for f in dist:
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
    DB.append((f["properties"]["ds_codigo"], polys, (min(xs), min(ys), max(xs), max(ys))))
def distrito(lon, lat):
    for cod, polys, (x0, y0, x1, y1) in DB:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in polys:
            if _inring(lon, lat, poly[0]) and not any(_inring(lon, lat, h) for h in poly[1:]):
                return cod
    return ""

