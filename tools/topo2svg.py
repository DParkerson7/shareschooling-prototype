"""
Rebuilds data/map.json (state shapes, plus county shapes for the example states).

Only needed if you add a new state. Steps:
  1. Download https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/counties-albers-10m.json
  2. Add the new state's 2-digit FIPS code to keep_states below.
  3. Run:  python3 tools/topo2svg.py counties-albers-10m.json data/map.json
"""
import json, sys
src, out = sys.argv[1], sys.argv[2]
keep_states = {"47", "08"}  # Tennessee, Colorado
t = json.load(open(src))
sc, tr = t["transform"]["scale"], t["transform"]["translate"]
arcs = []
for a in t["arcs"]:
    x = y = 0; pts = []
    for dx, dy in a:
        x += dx; y += dy
        pts.append((round(x*sc[0]+tr[0], 1), round(y*sc[1]+tr[1], 1)))
    arcs.append(pts)
def ring(r):
    pts = []
    for i in r:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return "M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z"
def path(g):
    polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
    return "".join(ring(r) for p in polys for r in p)
res = {"viewBox": "0 0 975 610", "source": "us-atlas 3.0.1 (ISC license, US Census Bureau cartographic boundaries)", "states": {}, "counties": {}}
for g in t["objects"]["states"]["geometries"]:
    res["states"][g["id"]] = {"name": g["properties"]["name"], "d": path(g)}
for g in t["objects"]["counties"]["geometries"]:
    if g["id"][:2] in keep_states:
        res["counties"][g["id"]] = {"name": g["properties"]["name"], "d": path(g)}
json.dump(res, open(out, "w"), separators=(",", ":"))
print(len(res["states"]), len(res["counties"]))
