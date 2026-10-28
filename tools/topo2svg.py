"""
Rebuilds data/map.json: every state's outline, plus county outlines and
county neighbours for the pilot states.

Only needed if the pilot adds a state. Steps:
  1. Download https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/counties-albers-10m.json
  2. Add the new state's 2-digit FIPS code to KEEP_STATES below.
  3. Run:  python3 tools/topo2svg.py counties-albers-10m.json data/map.json
  4. Run:  python3 tools/build_site.py
"""
import json, sys
from collections import defaultdict

KEEP_STATES = {"47": "TN", "28": "MS"}  # Tennessee, Mississippi

src, out = sys.argv[1], sys.argv[2]
t = json.load(open(src))
sc, tr = t["transform"]["scale"], t["transform"]["translate"]
arcs = []
for a in t["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in a:
        x += dx
        y += dy
        pts.append((round(x * sc[0] + tr[0], 2), round(y * sc[1] + tr[1], 2)))
    arcs.append(pts)


def ring(r, nd=2):
    pts = []
    for i in r:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return "M" + "L".join(f"{round(x, nd):g},{round(y, nd):g}" for x, y in pts) + "Z"


def polys(g):
    return [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]


def path(g, nd=2):
    return "".join(ring(r, nd) for p in polys(g) for r in p)


def arc_ids(g):
    return {i if i >= 0 else ~i for p in polys(g) for r in p for i in r}


res = {
    "viewBox": "0 0 975 610",
    "source": "us-atlas 3.0.1 (ISC license), based on US Census Bureau cartographic boundaries",
    "states": {},
    "counties": {},
}
for g in t["objects"]["states"]["geometries"]:
    res["states"][g["id"]] = {"name": g["properties"]["name"], "d": path(g, 1)}  # 1 decimal keeps the US map small

# Counties that share a border arc are neighbours (works across state lines too).
by_arc = defaultdict(set)
kept = [g for g in t["objects"]["counties"]["geometries"] if g["id"][:2] in KEEP_STATES]
for g in kept:
    for a in arc_ids(g):
        by_arc[a].add(g["id"])
for g in kept:
    neighbours = set()
    for a in arc_ids(g):
        neighbours |= by_arc[a]
    neighbours.discard(g["id"])
    res["counties"][g["id"]] = {
        "name": g["properties"]["name"],
        "state": KEEP_STATES[g["id"][:2]],
        "d": path(g),
        "neighbors": sorted(neighbours),
    }
json.dump(res, open(out, "w"), separators=(",", ":"))
print(len(res["states"]), "states,", len(res["counties"]), "counties")
