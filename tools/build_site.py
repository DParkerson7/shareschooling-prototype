"""
Builds every page of the site from the data files. Run it after any change
to data/ or templates/:

    python3 tools/build_site.py

Reads:   data/listings.json, data/map.json, data/site.json, templates/pages/*.html
Writes:  index.html, the other top-level pages, one folder per state
         (tn/, ms/, al/ ...), listing/, data/county-routes.json,
         data/places.json, sitemap.xml

Uses only the Python standard library. GitHub Pages serves the output as-is,
so commit the generated files along with your data changes.
"""
import html
import json
import math
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATE_CODES = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
NAV = [
    ("index.html", "Find local help"),
    ("online.html", "Online options"),
    ("about.html", "About"),
    ("book.html", "The Book"),
    ("list-your-resource.html", "List your co-op or tutor"),
    ("contact.html", "Contact"),
]
CONFIRM_NOTE = "We're still confirming this listing's details."
FAITH_NOTE = "Some listings haven't told us yet. Those appear under All."
NEEDS_NOTE = {"Needs verification", "Flagged: older source"}

esc = lambda s: html.escape(str(s), quote=True)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def fmt_date(iso):
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def present(value):
    """Null, empty strings and empty lists all count as 'not known'."""
    return value not in (None, "", [], {})


# ---------------------------------------------------------------- data

data = json.loads((ROOT / "data/listings.json").read_text())
geo = json.loads((ROOT / "data/map.json").read_text())
site = json.loads((ROOT / "data/site.json").read_text())
COMMUNITY_MODULES = (
    "reviews", "claims", "groupPortal", "lawGuides", "lookingFor", "events", "badges", "favorites",
)


def module_flags():
    raw = site.get("modules") or {}
    return {key: bool(raw.get(key)) for key in COMMUNITY_MODULES}


def demo_mode():
    """No API yet: show every module with sample data so the test site can be reviewed."""
    return not str(site.get("communityApi") or "").strip()


def community_on(name):
    if demo_mode():
        return True
    return module_flags().get(name, False)


def show_community():
    return demo_mode() or any(module_flags().values())


def community_config(kind, **extra):
    payload = {
        "api": str(site.get("communityApi") or "").strip(),
        "demo": demo_mode(),
        "built": {key: community_on(key) for key in COMMUNITY_MODULES},
        "flagDefaults": module_flags(),
        "page": {"kind": kind, **extra},
    }
    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")


PAGE_COMMUNITY = {"kind": "page"}
BASE = site["baseUrl"].rstrip("/") + "/"

CATS = data["categories"]
CAT_NAME = {c["id"]: c["name"] for c in CATS}
PILOT = {s["code"]: s for s in data["states"] if s.get("pilot")}

STATES = {}  # code -> {code, name, fips, d}
for fips, s in geo["states"].items():
    code = STATE_CODES.get(fips)
    if code:
        STATES[code] = {"code": code, "name": s["name"], "fips": fips, "d": s["d"], "slug": code.lower()}

COUNTIES = {}  # "TN:Shelby" -> county info
for fips, c in geo["counties"].items():
    st = c["state"]
    key = f"{st}:{c['name']}"
    COUNTIES[key] = {
        "key": key, "fips": fips, "name": c["name"], "state": st, "d": c["d"],
        "label": f"{c['name']} County", "slug": slug(c["name"]) + "-county",
        "pilot": c["name"] in PILOT.get(st, {}).get("pilotCounties", []),
        "neighbor_fips": c["neighbors"],
    }
BY_FIPS = {c["fips"]: c for c in COUNTIES.values()}
for c in COUNTIES.values():
    c["neighbors"] = [BY_FIPS[f]["key"] for f in c["neighbor_fips"] if f in BY_FIPS]
# The brief links DeSoto County, MS with both Shelby and Fayette counties, TN.
for a, b in [("MS:DeSoto", "TN:Shelby"), ("MS:DeSoto", "TN:Fayette")]:
    for x, y in [(a, b), (b, a)]:
        if y not in COUNTIES[x]["neighbors"]:
            COUNTIES[x]["neighbors"].append(y)


def resolve_county(name, home_state):
    """serviceArea holds bare county names. Use the pilot state that has that county."""
    for code, st in PILOT.items():
        if name in st["pilotCounties"]:
            return f"{code}:{name}"
    key = f"{home_state}:{name}"
    return key if key in COUNTIES else None


def visible(listing):
    return listing.get("status") == "Published" or (site.get("showDrafts") and listing.get("status") == "Draft")


LISTINGS = [l for l in data["listings"] if visible(l)]
for l in LISTINGS:
    loc = l.get("location") or {}
    l["_state"] = loc.get("state") or ""
    l["_home"] = f"{l['_state']}:{loc['county']}" if present(loc.get("county")) else None
    l["_city"] = loc.get("city") or ""
    l["_serves"] = [k for k in (resolve_county(n, l["_state"]) for n in (l.get("serviceArea") or {}).get("counties", [])) if k]
    l["_needs_note"] = l.get("verificationStatus") in NEEDS_NOTE
    l["_url"] = f"listing/{l['id']}/"


def sort_listings(items):
    # Featured is a hand-set label. Portal status, claims, and ratings are not sort keys.
    return sorted(items, key=lambda l: (not l.get("featured"), l["_needs_note"], l["name"].lower()))


def county_listings(key):
    return sort_listings([l for l in LISTINGS if key in l["_serves"]])


def statewide(code):
    return sort_listings([l for l in LISTINGS if l.get("reach") == "Statewide" and l["_state"] == code])


def state_url(code):
    return f"{code.lower()}/"


def county_url(c):
    return f"{c['state'].lower()}/{c['slug']}/"


# Cities with pages: home cities of listings in pilot counties.
CITIES = {}  # (county key, city) -> info
for l in LISTINGS:
    if l["_home"] and l["_city"] and l["_home"] in COUNTIES and COUNTIES[l["_home"]]["pilot"]:
        k = (l["_home"], l["_city"])
        CITIES.setdefault(k, {"county": COUNTIES[l["_home"]], "name": l["_city"], "slug": slug(l["_city"]), "listings": []})
        CITIES[k]["listings"].append(l)


def city_url(city):
    return county_url(city["county"]) + city["slug"] + "/"


# ---------------------------------------------------------------- map drawing

def project(lon, lat):
    """d3.geoAlbersUsa().scale(1300).translate([487.5, 305]) for the lower 48, matching data/map.json."""
    rad = math.pi / 180
    phi0, phi1 = 29.5 * rad, 45.5 * rad
    sy0 = math.sin(phi0)
    n = (sy0 + math.sin(phi1)) / 2
    c = 1 + sy0 * (2 * n - sy0)
    r0 = math.sqrt(c) / n

    def raw(lam, phi):
        r = math.sqrt(c - 2 * n * math.sin(phi)) / n
        return r * math.sin(lam * n), r0 - r * math.cos(lam * n)

    cx, cy = raw(-0.6 * rad, 38.7 * rad)
    x, y = raw((lon + 96) * rad, lat * rad)
    return 487.5 + (x - cx) * 1300, 305 - (y - cy) * 1300


def bbox(*paths):
    nums = [float(n) for d in paths for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _load_interstates():
    path = ROOT / "data" / "interstates.json"
    if not path.exists():
        return []
    lines = json.loads(path.read_text()).get("lines", [])
    for line in lines:
        xs = [p[0] for p in line["pts"]]
        ys = [p[1] for p in line["pts"]]
        line["_box"] = (min(xs), min(ys), max(xs), max(ys))
    return lines


ROADS = _load_interstates()
_RING_CACHE = {}


def parse_rings(d):
    rings, cur = [], []
    for tok in re.findall(r"[MLZ]|-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", d):
        if tok == "M":
            if len(cur) >= 3:
                rings.append(cur)
            cur = []
        elif tok == "Z":
            if len(cur) >= 3:
                rings.append(cur)
            cur = []
        elif tok != "L":
            x, y = tok.split(",")
            cur.append((float(x), float(y)))
    if len(cur) >= 3:
        rings.append(cur)
    return rings


def _ring_area(ring):
    area = 0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        area += x1 * y2 - x2 * y1
    return area / 2


def _pip(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def polygon_of(d):
    cached = _RING_CACHE.get(d)
    if cached is not None:
        return cached
    classified = [(ring, _ring_area(ring) < 0) for ring in parse_rings(d)]
    _RING_CACHE[d] = classified
    return classified


def _inside(x, y, classified):
    in_ext = in_hole = False
    for ring, is_hole in classified:
        if _pip(x, y, ring):
            if is_hole:
                in_hole = True
            else:
                in_ext = True
    return in_ext and not in_hole


def _seg_hits(a, b, ring):
    ax, ay = a
    bx, by = b
    rx, ry = bx - ax, by - ay
    hits = []
    prev = ring[-1]
    for cur in ring:
        sx, sy = cur[0] - prev[0], cur[1] - prev[1]
        den = rx * sy - ry * sx
        if abs(den) > 1e-9:
            qpx, qpy = prev[0] - ax, prev[1] - ay
            t = (qpx * sy - qpy * sx) / den
            u = (qpx * ry - qpy * rx) / den
            if 0 < t < 1 and 0 <= u <= 1:
                hits.append(t)
        prev = cur
    return hits


def clip_line(pts, classified):
    pieces, cur = [], []

    def flush():
        nonlocal cur
        if len(cur) >= 2:
            pieces.append(cur)
        cur = []

    for a, b in zip(pts, pts[1:]):
        ts = [0.0, 1.0]
        for ring, _hole in classified:
            ts.extend(_seg_hits(a, b, ring))
        ts = sorted(set(round(t, 5) for t in ts))
        ax, ay = a
        bx, by = b
        for t0, t1 in zip(ts, ts[1:]):
            if t1 - t0 < 1e-5:
                continue
            mid = ((t0 + t1) / 2)
            mx, my = ax + (bx - ax) * mid, ay + (by - ay) * mid
            if _inside(mx, my, classified):
                p0 = (ax + (bx - ax) * t0, ay + (by - ay) * t0)
                p1 = (ax + (bx - ax) * t1, ay + (by - ay) * t1)
                if cur and math.hypot(cur[-1][0] - p0[0], cur[-1][1] - p0[1]) < 0.05:
                    cur.append(p1)
                else:
                    flush()
                    cur = [p0, p1]
            else:
                flush()
    flush()
    return pieces


def _boxes_overlap(a, b, pad=0.4):
    return not (a[2] < b[0] - pad or b[2] < a[0] - pad or a[3] < b[1] - pad or b[3] < a[1] - pad)


def _path_d(pts):
    if len(pts) < 2:
        return ""
    head = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    return head + "".join(f"L{x:.2f},{y:.2f}" for x, y in pts[1:])


def _line_length(pts):
    return sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:]))


def _point_at(pts, frac):
    target = _line_length(pts) * frac
    walked = 0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        step = math.hypot(bx - ax, by - ay)
        if walked + step >= target and step:
            t = (target - walked) / step
            return ax + (bx - ax) * t, ay + (by - ay) * t
        walked += step
    return pts[len(pts) // 2]


def _midpoint(pts):
    return _point_at(pts, 0.5)


def _clip_rect(pts, box):
    x0, y0, x1, y1 = box
    ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return clip_line(pts, [(ring, False)])


def roads_for(d, label_view=None):
    """Interstate pieces clipped to a projected polygon, plus a few label anchors."""
    if not ROADS:
        return [], []
    classified = polygon_of(d)
    if not classified:
        return [], []
    box = bbox(d)
    pieces = []
    for line in ROADS:
        if not _boxes_overlap(line["_box"], box):
            continue
        for part in clip_line(line["pts"], classified):
            if _line_length(part) < 0.4:
                continue
            pieces.append((line["ref"], part))
    label_src = pieces
    span_box = box
    if label_view:
        span_box = label_view
        label_src = []
        for ref, part in pieces:
            for bit in _clip_rect(part, label_view):
                if _line_length(bit) >= 0.8:
                    label_src.append((ref, bit))
    best = {}
    for ref, part in label_src:
        length = _line_length(part)
        if ref not in best or length > best[ref][0]:
            best[ref] = (length, part)
    labels = []
    placed = []
    span = max(span_box[2] - span_box[0], span_box[3] - span_box[1])
    sep = max(span * 0.045, 2.2)
    for ref, (length, part) in sorted(best.items(), key=lambda kv: (len(kv[0]) > 2, -kv[1][0])):
        if length < max(1.1, span * 0.03):
            continue
        spot = None
        for frac in (0.5, 0.32, 0.68, 0.18, 0.82):
            x, y = _point_at(part, frac)
            if any(math.hypot(x - px, y - py) < sep for _oref, px, py in placed):
                continue
            spot = (x, y)
            break
        if not spot:
            continue
        placed.append((ref, spot[0], spot[1]))
        labels.append({"ref": ref, "x": round(spot[0], 2), "y": round(spot[1], 2)})
    return pieces, labels


def interstate_paths(pieces):
    body = "".join(f'<path class="interstate" d="{_path_d(part)}"/>' for _ref, part in pieces)
    if not body:
        return ""
    return f'<g class="interstates" aria-hidden="true">{body}</g>'


def interstate_static_labels(labels, font):
    return "".join(
        f'<text class="road-label" x="{lab["x"]:.2f}" y="{lab["y"]:.2f}" text-anchor="middle" '
        f'font-size="{font:.2f}" stroke-width="{font / 3:.2f}">I-{esc(lab["ref"])}</text>'
        for lab in labels)


def view_box(box, pad=0.06, extra_bottom=0.0):
    x0, y0, x1, y1 = box
    p = max(x1 - x0, y1 - y0) * pad
    return f"{x0 - p:.2f} {y0 - p:.2f} {x1 - x0 + 2 * p:.2f} {y1 - y0 + 2 * p + extra_bottom:.2f}"


def plural(n, word="listing"):
    return f"{n} {word}" + ("" if n == 1 else "s")


def shade(count):
    return "pilot-1" if count <= 2 else "pilot-2" if count <= 5 else "pilot-3" if count <= 10 else "pilot-4"


# Marker colors live in css/theme.css. Co-ops use the original pin rust.
PIN_KNOWN = {
    "co-ops", "microschools", "hybrid", "tutors", "classes", "support-groups",
    "field-trips", "sports", "testing", "special-needs", "curriculum",
    "associations", "umbrella-schools",
}
CAT_SHORT = {
    "co-ops": "Co-ops",
    "microschools": "Microschools",
    "hybrid": "Hybrid / university-model",
    "tutors": "Tutors",
    "classes": "Classes and enrichment",
    "support-groups": "Support groups",
    "field-trips": "Field trips",
    "sports": "Sports",
    "testing": "Testing",
    "special-needs": "Special needs support",
    "curriculum": "Curriculum and online",
    "associations": "State associations",
    "umbrella-schools": "Umbrella schools",
}
MAGNIFIER = ('<svg class="icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">'
             '<circle cx="7" cy="7" r="5.2" fill="none" stroke="currentColor" stroke-width="2"/>'
             '<path d="M11 11 L15 15" fill="none" stroke="currentColor" stroke-width="2"/></svg>')
FIT_ICON = ('<svg class="icon" width="20" height="20" viewBox="0 0 16 16" aria-hidden="true">'
            '<path d="M2.2 6.2V2.2h4M9.8 2.2h4v4M13.8 9.8v4h-4M6.2 13.8h-4v-4" fill="none" '
            'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def pin_token(cat_id):
    if cat_id in PIN_KNOWN:
        return cat_id
    return f"extra-{sum(ord(ch) for ch in str(cat_id)) % 6 + 1}"


def cat_short(cat_id):
    return CAT_SHORT.get(cat_id, CAT_NAME.get(cat_id, cat_id))


def json_embed(obj):
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def unique_listings(listings):
    seen, out = set(), []
    for l in listings:
        if l["id"] not in seen:
            seen.add(l["id"])
            out.append(l)
    return out


def listing_pin(l, emphasize=None):
    if l.get("latitude") is None or l.get("longitude") is None:
        return None
    x, y = project(l["longitude"], l["latitude"])
    faith = l.get("religiousAffiliation") if l.get("religiousAffiliation") in ("Faith-based", "Secular") else ""
    return {
        "id": l["id"],
        "name": l["name"],
        "cat": l["category"],
        "catLabel": cat_short(l["category"]),
        "token": pin_token(l["category"]),
        "exact": l.get("geocodePrecision") != "city",
        "x": round(x, 3),
        "y": round(y, 3),
        "city": l["_city"],
        "state": l["_state"],
        "url": l["_url"],
        "ages": l.get("agesGrades") or "",
        "faith": faith,
        "delivery": l.get("delivery") or "",
        "dim": bool(emphasize and l["_city"] != emphasize),
    }


def tight_bounds(county, listings):
    """County shape, plus pins that sit just across the line. Far outliers stay reachable by Fit."""
    box = bbox(county["d"])
    reach = max(box[2] - box[0], box[3] - box[1]) * 0.22
    grown = box
    for l in listings:
        if l.get("latitude") is None:
            continue
        x, y = project(l["longitude"], l["latitude"])
        if box[0] - reach <= x <= box[2] + reach and box[1] - reach <= y <= box[3] + reach:
            grown = (min(grown[0], x), min(grown[1], y), max(grown[2], x), max(grown[3], y))
    x0, y0, x1, y1 = grown
    w, h = max(x1 - x0, 1), max(y1 - y0, 1)
    px, py = max(w * 0.1, max(w, h) * 0.05), max(h * 0.1, max(w, h) * 0.05)
    return (x0 - px, y0 - py, x1 + px, y1 + py)


def place_search_form(suffix, overlay=False):
    kind = "overlay" if overlay else "bar-search"
    return f'''<form class="place-search {kind}" data-place-form role="search" data-status="place-status">
      <label class="visually-hidden" for="place-{suffix}">ZIP code or city</label>
      <span class="place-field">{MAGNIFIER}<input id="place-{suffix}" name="place" maxlength="48" autocomplete="off" placeholder="ZIP code or city" enterkeyhint="search"></span>
      <button class="btn" type="submit">Go</button>
    </form>'''


def legend_html():
    items = []
    for c in CATS:
        token = pin_token(c["id"])
        items.append(
            f'<li data-legend-cat="{esc(c["id"])}"><span class="mk solid pin-{token}" aria-hidden="true"></span>{esc(cat_short(c["id"]))}</li>')
    return f'''<div class="map-key" id="map-key">
      <h2>Resource type (marker color)</h2>
      <ul>{"".join(items)}</ul>
      <div class="key-sub">
        <span><span class="mk solid" style="--c:#5c544a" aria-hidden="true"></span>Solid = exact location</span>
        <span><span class="mk hollow" style="--c:#5c544a" aria-hidden="true"></span>Hollow = approximate (city only)</span>
        <span><span class="mk cluster-sample" aria-hidden="true">99+</span>Number = group. Click to zoom in. Over 99 shows as 99+.</span>
        <span><span class="road-sample" aria-hidden="true"></span>Interstate</span>
      </div>
      <p class="hint map-scroll-hint">Scrolling moves the page. Pinch, or hold Ctrl and scroll, to zoom the map.</p>
      <p class="hint unpinned-note" data-unpinned-note></p>
    </div>'''


def map_controls_html():
    dots = "".join(
        f'<span class="mk solid pin-{pin_token(c["id"])}" aria-hidden="true"></span>'
        for c in CATS[:3])
    return f'''<div class="map-controls">
      <div class="zoom-stack">
        <button type="button" data-zoom-in aria-label="Zoom in">+</button>
        <button type="button" data-zoom-out aria-label="Zoom out">−</button>
      </div>
      <button type="button" class="fit-btn" data-fit aria-label="Fit to results">{FIT_ICON}<span class="fit-label">Fit to results</span></button>
    </div>
    <button type="button" class="key-btn" data-key aria-controls="map-key">{dots} Key</button>'''


def interactive_map(county, listings, title, emphasize=None, small=False, preview=True):
    """County shape plus a JSON pin list. js/site.js clusters, zooms, and opens the preview."""
    bounds = tight_bounds(county, listings)
    x0, y0, x1, y1 = bounds
    home = f"{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}"
    neighbors = []
    labels = []
    font = max(x1 - x0, y1 - y0) / 42
    for key in county["neighbors"]:
        n = COUNTIES[key]
        neighbors.append(f'<path class="area neighbor" d="{n["d"]}"/>')
        nx0, ny0, nx1, ny1 = bbox(n["d"])
        cx, cy = (nx0 + nx1) / 2, (ny0 + ny1) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            label = n["name"].upper() + (" CO." if n["state"] == county["state"] else f" CO., {n['state']}")
            labels.append(
                f'<text class="neighbor-label" x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" font-size="{font:.2f}">{esc(label)}</text>')
    pins = [p for p in (listing_pin(l, emphasize) for l in listings) if p]
    road_pieces, road_labels = roads_for(county["d"])
    roads = interstate_paths(road_pieces)
    road_json = json_embed(road_labels)
    size = " small" if small else ""
    preview_html = ""
    if preview:
        preview_html = '''<div class="map-preview" data-preview hidden role="dialog" aria-modal="false" aria-labelledby="map-preview-title" tabindex="-1">
      <div class="preview-handle" aria-hidden="true"></div>
      <button type="button" class="map-preview-close" data-preview-close aria-label="Close">×</button>
      <p class="pc-cat" data-preview-cat></p>
      <h3 id="map-preview-title" data-preview-name></h3>
      <p class="pc-meta" data-preview-meta></p>
      <p class="pc-loc" data-preview-loc></p>
      <p class="pc-reviews" data-preview-reviews hidden></p>
      <p class="pc-save" data-preview-save hidden></p>
      <div class="pc-foot">
        <a class="preview-details" data-preview-link href="#">View details</a>
        <div class="pager" data-preview-pager hidden>
          <button type="button" data-preview-prev aria-label="Previous listing in this group">‹</button>
          <span data-preview-count></span>
          <button type="button" data-preview-next aria-label="Next listing in this group">›</button>
        </div>
      </div>
    </div>'''
    overlay = place_search_form("map", overlay=True) if not small else ""
    legend = "" if small else legend_html()
    return f'''<div class="map-column">
  <div class="map-stage{size}" id="map-area" data-map tabindex="0" role="region" data-home="{home}" data-emphasize="{esc(emphasize or "")}" data-allow-preview="{1 if preview else 0}" aria-label="{esc(title)}. Plus zooms in, minus zooms out. Drag sideways or pinch to move the map. Scrolling still moves the page.">
    {overlay}
    <svg class="map-svg interactive" viewBox="{home}" preserveAspectRatio="xMidYMid meet" role="group" aria-label="{esc(title)}">
      {"".join(neighbors)}
      <path class="area focus" d="{county["d"]}"/>
      {roads}
      {"".join(labels)}
      <g data-road-labels></g>
      <g data-marker-layer></g>
    </svg>
    {map_controls_html()}
    {preview_html}
    <script type="application/json" data-map-pins>{json_embed(pins)}</script>
    <script type="application/json" data-road-label-data>{road_json}</script>
  </div>
  {legend}
</div>'''


def results_rail(listings):
    rows = []
    ordered = sorted(unique_listings(listings), key=lambda l: l["name"].lower())
    for l in ordered:
        token = pin_token(l["category"])
        exact = l.get("latitude") is not None and l.get("geocodePrecision") != "city"
        hollow = "hollow" if l.get("latitude") is not None and not exact else "solid"
        if l.get("latitude") is None:
            loc = "No map pin"
            mark = f'<span class="mk hollow" style="--c:#5c544a" aria-hidden="true"></span>'
        else:
            loc = "Exact location" if exact else "Approximate (city only)"
            mark = f'<span class="mk {hollow} pin-{token}" aria-hidden="true"></span>'
        place = ", ".join(x for x in [l["_city"], l["_state"]] if x)
        meta = f'<span class="ct">{esc(cat_short(l["category"]))}</span>' + (f" · {esc(place)}" if place else "")
        body = f'{mark}<span><span class="nm">{esc(l["name"])}</span><span class="mt">{meta}</span><span class="loc">{loc}</span></span>'
        if l.get("latitude") is None:
            rows.append(
                f'<li data-result data-id="{esc(l["id"])}" data-name="{esc(l["name"].lower())}">'
                f'<a class="result-link" href="{{root}}{l["_url"]}">{body}</a></li>')
        else:
            rows.append(
                f'<li data-result data-id="{esc(l["id"])}" data-name="{esc(l["name"].lower())}">'
                f'<button type="button" class="result-btn">{body}</button></li>')
    return f'''<aside class="results-rail" data-results-rail aria-labelledby="results-heading">
  <h2 id="results-heading">Results <small data-rail-scope>A–Z · tap a result to find it on the map</small></h2>
  <p class="rail-scope-actions"><button type="button" class="link-button" data-rail-all hidden>Show every result</button></p>
  <ul>{"".join(rows)}</ul>
  <p class="hint rail-note" data-unpinned-note></p>
  <p class="empty-note" data-rail-empty hidden>No listings match these filters.</p>
</aside>'''


def explorer_block(county, listings, title, emphasize=None):
    return f'''<div class="explorer view-map" data-explorer>
  <div class="explorer-grid">
    {results_rail(listings)}
    {interactive_map(county, listings, title, emphasize=emphasize)}
  </div>
</div>'''


def outline_svg(d, title):
    pieces, labels = roads_for(d)
    font = max(bbox(d)[2] - bbox(d)[0], bbox(d)[3] - bbox(d)[1]) / 28
    return (f'<svg class="map-svg" viewBox="{view_box(bbox(d), 0.08)}" role="img" aria-label="{esc(title)}" style="max-height:260px">'
            f'<path class="area focus" d="{d}"/>{interstate_paths(pieces)}{interstate_static_labels(labels, font)}</svg>')


def state_map_svg(code):
    """County map of a pilot state. Pilot counties are shaded by listing count."""
    st = STATES[code]
    counties = sorted((c for c in COUNTIES.values() if c["state"] == code), key=lambda c: c["name"])
    extra_paths = []
    cross = []
    if code == "TN":
        cross = [COUNTIES["MS:DeSoto"]]
    elif code == "MS":
        cross = [COUNTIES["TN:Shelby"]]
    # Zoom to the pilot area (plus the cross-state county) so small counties stay readable.
    # Counties outside it are clipped at the edge of the map; the page lists them all.
    focus = [c["d"] for c in counties if c["pilot"]] + [c["d"] for c in cross]
    box = bbox(*focus) if code == "TN" else bbox(st["d"], *[c["d"] for c in cross])
    size = max(box[2] - box[0], box[3] - box[1])
    font = size / 50
    parts = [f'<svg class="map-svg" viewBox="{view_box(box, 0.05, font * 2.5)}" role="group" aria-labelledby="state-map-title">',
             f'<title id="state-map-title">Map of {esc(st["name"])} counties. Shaded counties are in the pilot.</title>']
    labels = []
    for c in counties:
        if c["pilot"]:
            n = len(county_listings(c["key"]))
            cls, label = shade(n), f"{c['label']}: {plural(n)}"
            x0, y0, x1, y1 = bbox(c["d"])
            labels.append(f'<text class="count-label{" on-light" if cls in ("pilot-1", "pilot-2") else ""}" x="{(x0 + x1) / 2:.2f}" y="{(y0 + y1) / 2 + font / 3:.2f}" text-anchor="middle" font-size="{font:.2f}">{n}</text>')
        else:
            cls, label = "", f"{c['label']}: coming soon"
        parts.append(f'<a href="{{root}}{county_url(c)}" aria-label="{esc(label)}"><path class="area {cls}" d="{c["d"]}"><title>{esc(label)}</title></path></a>')
    road_pieces, road_labels = roads_for(st["d"], label_view=box)
    parts.append(interstate_paths(road_pieces))
    parts.append(f'<path class="state-line" d="{st["d"]}"/>')
    parts.append(interstate_static_labels(road_labels, font * 0.72))
    for c in cross:
        n = len(county_listings(c["key"]))
        name = f"{c['label']}, {c['state']}"
        x0, y0, x1, y1 = bbox(c["d"])  # used by both labels below
        parts.append(f'<a href="{{root}}{county_url(c)}" aria-label="{esc(name)}: {plural(n)}"><path class="area cross-state {shade(n)}" d="{c["d"]}"><title>{esc(name)}</title></path></a>')
        labels.append(f'<text class="count-label{" on-light" if shade(n) in ("pilot-1", "pilot-2") else ""}" x="{(x0 + x1) / 2:.2f}" y="{(y0 + y1) / 2 + font / 3:.2f}" text-anchor="middle" font-size="{font:.2f}">{n}</text>')
        # Label starts at the county's left edge, below it in TN view and above it in MS view.
        ly = y1 + font * 1.3 if code == "TN" else y0 - font * 0.5
        labels.append(f'<text class="map-label" x="{x0:.2f}" y="{ly:.2f}" font-size="{font:.2f}" stroke-width="{font / 4:.2f}">{esc(name)}</text>')
    parts += labels
    parts.append("</svg>")
    return "".join(parts)


def us_map_svg():
    parts = [f'<svg class="map-svg" viewBox="{geo["viewBox"]}" role="group" aria-labelledby="us-map-title">',
             '<title id="us-map-title">Map of the United States. Choose a state.</title>']
    for code, st in sorted(STATES.items(), key=lambda kv: kv[1]["name"]):
        if code in PILOT:
            cls = "pilot-state" if code == "TN" else "pilot-partial"
            label = f"{st['name']}: {PILOT[code]['pilotLabel']}"
        else:
            cls, label = "", f"{st['name']}: coming soon"
        parts.append(f'<a href="{{root}}{state_url(code)}" aria-label="{esc(label)}"><path class="area {cls}" d="{st["d"]}"><title>{esc(label)}</title></path></a>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- shared HTML parts

def breadcrumbs(items):
    lis = []
    for i, (label, href) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li><span aria-current="page">{esc(label)}</span></li>')
        else:
            lis.append(f'<li><a href="{{root}}{href}">{esc(label)}</a></li>')
    return f'<nav class="breadcrumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'


def crumbs_for(state=None, county=None, city=None, last=None):
    items = [("US", "index.html")]
    if state:
        items.append((STATES[state]["name"], state_url(state)))
    if county:
        items.append((county["label"], county_url(county)))
    if city:
        items.append((city["name"], city_url(city)))
    if last:
        items.append((last, ""))
    return breadcrumbs(items)


def faith_value(l):
    return {"Faith-based": "faith-based", "Secular": "secular"}.get(l.get("religiousAffiliation"), "unknown")


def card(l, view_state=None):
    loc = l.get("location") or {}
    place = ", ".join(x for x in [l["_city"]] if x)
    state_tag = ""
    if view_state and l["_state"] and l["_state"] != view_state:
        state_tag = f' <span class="tag tag-state" title="Based in {esc(STATES[l["_state"]]["name"])}">{esc(l["_state"])}</span>'
    tags = [f'<li><span class="tag">{esc(l["reach"])}</span></li>', f'<li><span class="tag">{esc(l["delivery"])}</span></li>']
    if l.get("religiousAffiliation") in ("Faith-based", "Secular"):
        tags.append(f'<li><span class="tag">{esc(l["religiousAffiliation"])}</span></li>')
    top = []
    if l.get("featured"):
        top.append('<li><span class="tag tag-featured">Featured</span></li>')
    if l.get("status") == "Draft":
        top.append('<li><span class="tag tag-draft">Draft</span></li>')
    lat, lon = l.get("latitude"), l.get("longitude")
    coords = f' data-lat="{lat}" data-lon="{lon}"' if lat is not None and lon is not None else ""
    return (
        f'<li data-listing data-id="{esc(l["id"])}" data-cat="{esc(l["category"])}" data-reach="{esc(l["reach"])}"'
        f' data-delivery="{esc(l["delivery"])}" data-faith="{faith_value(l)}" data-featured="{1 if l.get("featured") else 0}"'
        f' data-confirm="{1 if l["_needs_note"] else 0}" data-name="{esc(l["name"].lower())}"'
        f'{coords}>'
        f'<article class="card{" featured" if l.get("featured") else ""}">'
        + (f'<ul class="tags">{"".join(top)}</ul>' if top else "")
        + f'<h3><a href="{{root}}{l["_url"]}">{esc(l["name"])}</a></h3>'
        f'<p class="meta"><span class="cat">{esc(CAT_NAME.get(l["category"], l["category"]))}</span>'
        + (f' · {esc(place)}' if place else "") + state_tag + '</p>'
        f'<p class="desc">{esc(l["description"])}</p>'
        f'<ul class="tags">{"".join(tags)}</ul>'
        + (f'<p class="confirm-note">{CONFIRM_NOTE}</p>' if l["_needs_note"] else "")
        + ('<p class="review-line" data-review-summary hidden></p>' if community_on("reviews") else "")
        + ('<p class="updated-line" data-updated hidden></p>' if community_on("claims") else "")
        + ('<p class="save-row"><button type="button" class="link-button save-btn" data-save hidden>Save</button></p>' if community_on("favorites") else "")
        + f'<p class="foot"><span>Last verified: {esc(fmt_date(l.get("lastChecked")))}</span><span data-distance></span></p>'
        '</article></li>')


def card_list(listings, view_state, empty_text):
    return (f'<ul class="card-grid" data-list>{"".join(card(l, view_state) for l in listings)}</ul>'
            f'<p class="empty-note" data-empty{"" if not listings else " hidden"}>{empty_text}</p>')


def category_sections(listings, view_state, suggest_href):
    out = []
    for c in CATS:
        items = [l for l in listings if l["category"] == c["id"]]
        if items:
            out.append(f'<section class="cat-section" data-section aria-labelledby="sec-{c["id"]}">'
                       f'<h2 id="sec-{c["id"]}">{esc(c["name"])}</h2>{card_list(items, view_state, "None match these filters.")}</section>')
    out.append(f'<p class="empty-note" data-all-empty hidden>No listings match these filters yet. '
               f'<a href="{{root}}{suggest_href}">Suggest a resource</a></p>')
    return "".join(out)


def missing_categories_note(listings, state_code, suggest_href):
    have = {l["category"] for l in listings + statewide(state_code)}
    notes = PILOT.get(state_code, {}).get("categoryNotes", {})
    missing = [c["name"] for c in CATS if c["id"] not in have and c["id"] not in notes]
    if not missing:
        return ""
    return (f'<p class="gap-note">No listings here yet for: {esc(", ".join(missing))}. '
            f'Know one? <a href="{{root}}{suggest_href}">Suggest a resource</a>.</p>')


def filter_bar(state_code=None, with_map=False, list_total=0):
    notes = PILOT.get(state_code, {}).get("categoryNotes", {}) if state_code else {}
    chips, chip_notes = [], []
    for c in CATS:
        if c["id"] in notes:
            chips.append(f'<li><button type="button" class="chip" data-chip="{c["id"]}" aria-pressed="false" disabled aria-describedby="note-{c["id"]}">{esc(c["name"])}</button></li>')
            chip_notes.append(f'<p class="note-line" id="note-{c["id"]}">{esc(notes[c["id"]])}</p>')
        else:
            chips.append(f'<li><button type="button" class="chip" data-chip="{c["id"]}" aria-pressed="false">{esc(c["name"])}</button></li>')
    opts = lambda values: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values)
    if with_map:
        search = place_search_form("bar")
        view_toggle = f'''<div class="view-toggle map-toggle" role="group" aria-label="Map or list">
      <button type="button" data-view="map" aria-pressed="true">Map</button>
      <button type="button" data-view="list" aria-pressed="false">List (<span data-list-count>{list_total}</span>)</button>
    </div>'''
        tools = ""
        count = f'<p class="results-count" data-results-count aria-live="polite">Showing {list_total} of {list_total} listings</p>'
    else:
        search = ""
        view_toggle = ""
        tools = '''<form class="zip-mini" data-zip-form role="search">
      <label class="visually-hidden" for="bar-zip">ZIP code or city</label>
      <input id="bar-zip" name="place" maxlength="48" autocomplete="off" placeholder="ZIP code or city">
      <button class="btn" type="submit">Go</button>
    </form>'''
        count = '<p class="results-count" data-results-count aria-live="polite"></p>'
    return f'''
<div class="filterbar" data-filterbar>
  {search}
  <div class="bar-row">
    <button type="button" class="btn btn-secondary filters-toggle" data-filters-toggle aria-expanded="false" aria-controls="filter-panel">Filters<span class="count-badge" data-filter-count hidden></span></button>
    {count if with_map else ""}
    {tools}
  </div>
  <p class="zip-status" id="place-status" data-zip-status aria-live="polite"></p>
  {view_toggle}
  <div id="filter-panel" class="filter-panel" hidden>
    <div class="label" id="cat-label">Category</div>
    <ul class="chips" aria-labelledby="cat-label">{"".join(chips)}</ul>
    {"".join(chip_notes)}
    <div class="groups">
      <div><label for="f-reach">Who it serves</label><select id="f-reach" data-filter="reach"><option value="">All</option>{opts(["Local", "Regional", "Statewide"])}</select></div>
      <div><label for="f-delivery">Delivery</label><select id="f-delivery" data-filter="delivery"><option value="">All</option>{opts(["In person", "Online", "Both"])}</select></div>
      <fieldset>
        <legend>Faith</legend>
        <div class="segmented">
          <label><input type="radio" name="faith" value="" checked><span>All</span></label>
          <label><input type="radio" name="faith" value="faith-based"><span>Faith-based</span></label>
          <label><input type="radio" name="faith" value="secular"><span>Secular</span></label>
        </div>
        <p class="note-line">{FAITH_NOTE}</p>
      </fieldset>
    </div>
    <button type="button" class="link-button" data-clear-filters>Clear filters</button>
  </div>
  {"" if with_map else count}
</div>'''


def state_options(selected=None, include_other=False):
    out = ['<option value="">Choose…</option>']
    for code, st in sorted(STATES.items(), key=lambda kv: kv[1]["name"]):
        out.append(f'<option value="{code}"{" selected" if code == selected else ""}>{esc(st["name"])}</option>')
    return "".join(out)


_form_ids = [0]


def signup_form(heading, state_code=None, county_name=""):
    _form_ids[0] += 1
    p = f"su{_form_ids[0]}"
    return f'''
<form class="signup-form" data-signup novalidate aria-labelledby="{p}-h">
  <h2 id="{p}-h">{esc(heading)}</h2>
  <div class="row">
    <div class="form-row"><label for="{p}-email">Email</label><input id="{p}-email" name="email" type="email" autocomplete="email" required></div>
    <div class="form-row"><label for="{p}-state">State</label><select id="{p}-state" name="state">{state_options(state_code)}</select></div>
    <div class="form-row"><label for="{p}-county">County (optional)</label><input id="{p}-county" name="county" value="{esc(county_name)}"></div>
  </div>
  <fieldset>
    <legend>Email me about</legend>
    <label class="check"><input type="checkbox" name="interests" value="new-listings-near-me" checked> New listings near me</label>
    <label class="check"><input type="checkbox" name="interests" value="launch-news" checked> Launch news</label>
  </fieldset>
  <div class="honeypot" aria-hidden="true"><label for="{p}-hp">Leave this empty</label><input id="{p}-hp" name="company" tabindex="-1" autocomplete="off"></div>
  <button class="btn" type="submit">Sign up</button>
  <p class="form-message" role="status"></p>
</form>'''


def suggest_href(state_code=None, county_name=None):
    q = []
    if state_code:
        q.append(f"state={state_code}")
    if county_name:
        q.append(f"county={county_name.replace(' ', '+')}")
    return "list-your-resource.html" + ("?" + "&".join(q) if q else "") + "#form-heading"


def json_ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def item_list(name, listings):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name,
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": BASE + l["_url"], "name": l["name"]}
                                for i, l in enumerate(listings)]}


# ---------------------------------------------------------------- page wrapper

PAGES = []  # (path, html)


def page(path, title, desc, body, state_code=None, county_name="", extra_head="", community=None):
    depth = path.count("/")
    root = "../" * depth
    url_path = path[:-len("index.html")] if path.endswith("index.html") else path
    canonical = BASE + url_path
    CURRENT_ATTR = ' aria-current="page"'
    current = path if depth == 0 else ("index.html" if depth else path)
    links = list(NAV)
    if show_community():
        extras = []
        if community_on("lookingFor"):
            extras.append(("looking-for/index.html", "Looking for"))
        if community_on("favorites"):
            extras.append(("saved/index.html", "Saved"))
        links = links[:-1] + extras + links[-1:]
    nav = "".join(f'<li><a href="{root}{href}"{CURRENT_ATTR if href == current else ""}>{label}</a></li>' for href, label in links)
    context = community or PAGE_COMMUNITY
    community_head = ""
    community_json = ""
    demo_banner = ""
    if show_community():
        community_head = f'\n  <link rel="stylesheet" href="{root}css/community.css">'
        community_json = f'\n  <script type="application/json" id="community-config">{community_config(context.get("kind", "page"), **{k: v for k, v in context.items() if k != "kind"})}</script>'
    if demo_mode():
        demo_banner = (
            '<div class="demo-banner" role="note">Community preview: sample families and groups in this browser, '
            "not a live database. Reviews are the friends-test default. The other modules are on in this preview "
            "so you can check the look. Nothing here is charged, and the map is the same pilot map.</div>"
        )
    robots = "" if site.get("allowSearchEngines") else '\n  <meta name="robots" content="noindex, nofollow">'
    footer_heading = "Get ShareSchooling updates"
    doc = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">{robots}
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="{root}img/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&amp;display=swap">
  <link rel="stylesheet" href="{root}css/theme.css">
  <link rel="stylesheet" href="{root}css/styles.css">{community_head}{extra_head}
</head>
<body data-root="{root}"{f' data-state="{esc(state_code)}"' if state_code else ""}{f' data-county="{esc(county_name)}"' if county_name else ""}>
  <a class="skip-link" href="#main">Skip to main content</a>
  <div class="test-banner" role="note">Test site: listings are drafts gathered from public pages and not yet confirmed by the organizations.</div>
  {demo_banner}
  <header class="site-header">
    <div class="inner">
      <a class="logo" href="{root}index.html">Share<span>Schooling</span></a>
      <div class="account-slot" data-account-slot></div>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
      <nav id="site-nav" class="site-nav" aria-label="Main"><ul>{nav}</ul></nav>
    </div>
  </header>
  <div class="page-layout">
    <main id="main" tabindex="-1">
{body}
    </main>
    <aside class="sponsor-left" aria-label="Sponsor space"><div class="sponsor-box">Sponsor placeholder</div></aside>
    <aside class="sponsor-right" aria-label="Sponsor space"><div class="sponsor-box">Sponsor placeholder</div></aside>
  </div>
  <footer class="site-footer">
    <div class="inner">
      {signup_form(footer_heading, state_code, county_name)}
      <div class="fine">
        <p>ShareSchooling is a book and a guide to homeschool help near you. This is a test site for the West Tennessee and DeSoto County, MS pilot.</p>
        <p>We publish only organizational contact info. We don't publish home addresses.</p>
        <p>Map shapes and zip codes: US Census Bureau, via the open-source us-atlas project.</p>
      </div>
    </div>
  </footer>
  {community_json}
  <script src="{root}js/site.js"></script>
</body>
</html>
'''
    PAGES.append((path, doc.replace("{root}", root)))


def law_guide(code):
    path = ROOT / "data" / "law" / f"{code.lower()}.json"
    if not path.exists():
        return None
    guide = json.loads(path.read_text())
    if guide.get("status") != "approved":
        return None
    return guide


def law_box(code, fallback):
    name = STATES[code]["name"]
    if not community_on("lawGuides"):
        if not fallback:
            return ""
        return (
            '<section class="placeholder-box" aria-labelledby="law-heading">'
            '<h2 id="law-heading" style="font-size:1.2rem">State homeschool law basics</h2>'
            f'<p style="margin:0">{esc(fallback)}</p></section>'
        )
    guide = law_guide(code)
    if not guide:
        sample = ""
        if demo_mode() and (ROOT / "data" / "law" / "layout-sample.json").exists():
            sample = '<p style="margin:0.75rem 0 0"><a href="{root}sample/homeschool-law/">Preview the page template (sample layout, not legal advice)</a></p>'
        return (
            '<section class="placeholder-box" aria-labelledby="law-heading">'
            '<h2 id="law-heading" style="font-size:1.2rem">State homeschool law basics</h2>'
            f'<p style="margin:0">A plain-language guide isn\'t ready for {esc(name)} yet.</p>{sample}</section>'
        )
    who = guide.get("who") or ""
    checked = guide.get("lastChecked") or ""
    return (
        '<section class="placeholder-box" aria-labelledby="law-heading">'
        '<h2 id="law-heading" style="font-size:1.2rem">State homeschool law basics</h2>'
        f'<p style="margin:0">{esc(who)}</p>'
        + (f'<p class="hint">Last checked {esc(fmt_date(checked))}.</p>' if checked else "")
        + f'<p style="margin:0.75rem 0 0"><a href="{{root}}{code.lower()}/homeschool-law/">Read the full guide</a></p></section>'
    )


def county_community(state_code, county_name):
    blocks = []
    if community_on("lookingFor"):
        blocks.append('<section class="community-block" data-module="lookingFor" data-looking-for hidden></section>')
    if community_on("events"):
        blocks.append('<section class="community-block" data-module="events" data-events hidden></section>')
    if not blocks:
        return ""
    return '<div class="community-stack">' + "".join(blocks) + "</div>"


def listing_community_blocks(listing):
    parts = ['<div data-overlay-mount></div>'] if community_on("claims") else []
    if community_on("reviews"):
        parts.append(
            f'<section class="community-block" id="family-reviews" data-module="reviews" data-listing-id="{esc(listing["id"])}" hidden>'
            '<h2>Family reviews</h2><div data-reviews-root></div></section>'
        )
    if community_on("claims"):
        parts.append(
            '<section class="community-block" data-module="claims" data-listing-editor hidden>'
            '<h2>Keep this listing current</h2><div data-claims-editor></div></section>'
        )
    return "".join(parts)


def build_account_page():
    page("account/index.html", "Sign in | ShareSchooling",
         "Sign in or create a ShareSchooling family account.",
         '''<h1>Your account</h1>
<p class="intro">Families sign in to leave a review. The display name is a family name or a first name and last initial. It is not an email, and it is not a child's name.</p>
<div class="community-block" data-account-page></div>''',
         community={"kind": "account"})


def build_admin_page():
    page("admin/index.html", "Admin | ShareSchooling",
         "Moderation queue and community settings.",
         '''<h1>Admin</h1>
<div class="community-block" data-admin-page></div>''',
         community={"kind": "admin"})


def build_looking_page():
    page("looking-for/index.html", "Looking for | ShareSchooling",
         "Families post what they are looking for. Posts are not map pins.",
         '''<h1>Looking for</h1>
<p class="intro">A family can post a need, such as a tutor or a class. Keep children's names and home addresses out of it.</p>
<div class="community-block" data-module="lookingFor" data-looking-page></div>''',
         community={"kind": "looking"})


def build_saved_page():
    page("saved/index.html", "Saved | ShareSchooling",
         "Listings you saved on ShareSchooling.",
         '''<h1>Saved</h1>
<div class="community-block" data-module="favorites" data-saved-page></div>''',
         community={"kind": "saved"})


def build_portal_page():
    page("portal/index.html", "Group portal (test) | ShareSchooling",
         "A private test area for one group. No real charges.",
         '''<h1>Group portal (test)</h1>
<div class="community-block" data-module="groupPortal" data-portal-page></div>''',
         community={"kind": "portal"})


def build_law_pages():
    folder = ROOT / "data" / "law"
    if not folder.exists():
        return
    for path in sorted(folder.glob("*.json")):
        guide = json.loads(path.read_text())
        if guide.get("status") != "approved":
            continue
        code = str(guide.get("state") or "").lower()
        if not code:
            continue
        title = guide.get("title") or "Homeschool guide"
        steps = "".join(
            f'<h2>{esc(step.get("heading") or "")}</h2><p>{esc(step.get("body") or "")}</p>'
            for step in guide.get("steps") or []
        )
        sources = guide.get("sources") or []
        if sources:
            source_html = "<ul>" + "".join(
                f'<li><a href="{esc(item.get("url") or "")}">{esc(item.get("name") or item.get("url") or "")}</a>'
                + (f' <span class="hint">accessed {esc(item.get("accessed") or "")}</span>' if item.get("accessed") else "")
                + "</li>"
                for item in sources
            ) + "</ul>"
        else:
            source_html = "<p>No sources are listed in this sample. Official pages belong here after they are checked.</p>"
        checked = guide.get("lastChecked")
        checked_html = f'<p><strong>Last checked {esc(fmt_date(checked))}.</strong></p>' if checked else ""
        body = f'''<article class="prose community-block">
<p class="confirm-note">{esc(guide.get("disclaimer") or "")}</p>
<h1>{esc(title)}</h1>
<h2>Who this is for</h2><p>{esc(guide.get("who") or "")}</p>
{steps}
<h2>Notice</h2><p>{esc(guide.get("notice") or "")}</p>
<h2>Testing</h2><p>{esc(guide.get("testing") or "")}</p>
<h2>Umbrella schools</h2><p>{esc(guide.get("umbrella") or "")}</p>
<h2>Sources</h2>{source_html}
{checked_html}
<p><a href="{{root}}contact.html">Something look wrong?</a></p>
</article>'''
        page(f"{code}/homeschool-law/index.html", f"{title} | ShareSchooling",
             (guide.get("disclaimer") or title)[:155], body,
             community={"kind": "law", "state": guide.get("state")})


# ---------------------------------------------------------------- pages

def build_home():
    tn, ms = STATES["TN"], STATES["MS"]
    shelby, madison, desoto = COUNTIES["TN:Shelby"], COUNTIES["TN:Madison"], COUNTIES["MS:DeSoto"]
    other_states = "".join(f'<option value="{{root}}{state_url(c)}">{esc(s["name"])}</option>'
                           for c, s in sorted(STATES.items(), key=lambda kv: kv[1]["name"]))
    body = f'''
<section class="hero">
  <h1>Join the Education Revolution!</h1>
  <p>You made the right decision. You don't have to know everything or teach every subject yourself. Help is closer than you think, and you can do this.</p>
</section>
<div class="map-layout">
  <section class="panel" aria-labelledby="map-heading">
    <h2 id="map-heading">Start with your state</h2>
    {us_map_svg()}
    <div class="map-legend">
      <span><span class="swatch" style="background:var(--color-map-pilot-4)"></span>Tennessee: live pilot (West TN)</span>
      <span><span class="swatch" style="background:var(--color-map-pilot-2)"></span>Mississippi: pilot in DeSoto County</span>
      <span><span class="swatch" style="background:var(--color-map-muted)"></span>Coming soon</span>
    </div>
  </section>
  <div>
    <section class="panel" aria-labelledby="zip-heading">
      <h2 id="zip-heading">Find help near you</h2>
      <form data-zip-form role="search">
        <label for="home-zip">ZIP code or city</label>
        <div class="btn-row"><input id="home-zip" name="place" maxlength="48" autocomplete="off" placeholder="ZIP code or city" style="flex:1 1 8rem"><button class="btn" type="submit">Go</button></div>
      </form>
      <p class="zip-status" data-zip-status aria-live="polite"></p>
      <p class="hint" style="margin:0.5rem 0 0">The pilot covers West Tennessee and DeSoto County, MS.</p>
    </section>
    <section class="panel" aria-labelledby="pilot-heading">
      <h2 id="pilot-heading">Pilot areas</h2>
      <ul class="link-list">
        <li><a href="{{root}}{state_url("TN")}"><span>West Tennessee</span><span class="count">21 counties</span></a></li>
        <li><a href="{{root}}{county_url(shelby)}"><span>Shelby County (Memphis)</span><span class="count">{plural(len(county_listings(shelby["key"])))}</span></a></li>
        <li><a href="{{root}}{county_url(madison)}"><span>Madison County (Jackson)</span><span class="count">{plural(len(county_listings(madison["key"])))}</span></a></li>
        <li><a href="{{root}}{county_url(desoto)}"><span>DeSoto County, MS</span><span class="count">{plural(len(county_listings(desoto["key"])))}</span></a></li>
      </ul>
      <label for="state-jump" style="margin-top:0.75rem">Or choose any state</label>
      <select id="state-jump" data-jump><option value="">Choose a state…</option>{other_states}</select>
    </section>
  </div>
</div>'''
    page("index.html", "ShareSchooling: homeschool co-ops, tutors & resources near you",
         "Find homeschool co-ops, tutors, classes, field trips and support near you. Now piloting in West Tennessee and DeSoto County, MS.",
         body)


def build_pilot_state(code):
    st, ps = STATES[code], PILOT[code]
    counties = sorted((c for c in COUNTIES.values() if c["state"] == code), key=lambda c: c["name"])
    pilot_c = [c for c in counties if c["pilot"]]
    other_c = [c for c in counties if not c["pilot"]]
    sw = statewide(code)
    cross = COUNTIES["MS:DeSoto"] if code == "TN" else COUNTIES["TN:Shelby"]
    region = "West Tennessee" if code == "TN" else "DeSoto County"
    pilot_list = "".join(f'<li><a href="{{root}}{county_url(c)}"><span>{esc(c["label"])}</span><span class="count">{plural(len(county_listings(c["key"])))}</span></a></li>' for c in pilot_c)
    other_list = "".join(f'<li><a href="{{root}}{county_url(c)}">{esc(c["label"])}</a></li>' for c in other_c)
    body = f'''
{crumbs_for(state=code)}
<h1>Homeschool resources in {esc(st["name"])}</h1>
<p class="intro">The {esc(st["name"])} pilot covers {esc(region)}{" (" + str(len(pilot_c)) + " counties)" if len(pilot_c) > 1 else ""}. Choose a county to see local co-ops, tutors, classes and more. Other counties are coming soon.</p>
<div class="map-layout">
  <section class="panel" aria-labelledby="county-map-heading">
    <h2 id="county-map-heading">Choose a county</h2>
    {state_map_svg(code)}
    <div class="map-legend">
      <span><span class="swatch" style="background:var(--color-map-pilot-1)"></span>1–2 listings</span>
      <span><span class="swatch" style="background:var(--color-map-pilot-2)"></span>3–5</span>
      <span><span class="swatch" style="background:var(--color-map-pilot-3)"></span>6–10</span>
      <span><span class="swatch" style="background:var(--color-map-pilot-4)"></span>11 or more</span>
      <span><span class="swatch" style="background:var(--color-map-muted)"></span>Coming soon</span>
      <span><span class="road-sample" aria-hidden="true"></span>Interstate</span>
    </div>
  </section>
  <div>
    <section class="panel" aria-labelledby="pilot-counties-heading">
      <h2 id="pilot-counties-heading">Pilot counties</h2>
      <ul class="link-list">{pilot_list}</ul>
      <p class="hint" style="margin:0.75rem 0 0">Across the state line: <a href="{{root}}{county_url(cross)}">{esc(cross["label"])}, {cross["state"]}</a></p>
    </section>
    <section class="panel" aria-labelledby="zip-heading">
      <h2 id="zip-heading">Search by ZIP code or city</h2>
      <form data-zip-form role="search"><label class="visually-hidden" for="state-zip">ZIP code or city</label>
        <div class="btn-row"><input id="state-zip" name="place" maxlength="48" autocomplete="off" placeholder="ZIP code or city" style="flex:1 1 8rem"><button class="btn" type="submit">Go</button></div></form>
      <p class="zip-status" data-zip-status aria-live="polite"></p>
    </section>
  </div>
</div>
{law_box(code, ps["lawBasics"])}
<section aria-labelledby="statewide-heading">
  <h2 id="statewide-heading">Statewide resources</h2>
  {card_list(sw, code, "No statewide listings yet.")}
</section>
<details class="panel" style="margin-top:1.5rem">
  <summary><strong>Other {esc(st["name"])} counties (coming soon)</strong></summary>
  <ul class="inline-links" style="margin-top:0.5rem">{other_list}</ul>
</details>'''
    jsonld = json_ld(item_list(f"Statewide homeschool resources in {st['name']}", sw))
    page(f"{code.lower()}/index.html", f"Homeschool co-ops, tutors & resources in {st['name']} | ShareSchooling",
         f"Homeschool help in {st['name']}: pilot listings for {region}, plus statewide associations and programs.",
         body, state_code=code, extra_head="\n  " + jsonld,
         community={"kind": "state", "state": code})


def build_other_state(code):
    st = STATES[code]
    body = f'''
{crumbs_for(state=code)}
<div class="map-layout">
  <section class="panel coming-soon">
    <div class="big" aria-hidden="true">🌱</div>
    <h1>{esc(st["name"])} is coming soon</h1>
    <p>We're starting with West Tennessee and DeSoto County, MS, and adding more places as we go. You're not alone in this.</p>
    <div class="btn-row"><a class="btn" href="{{root}}{suggest_href(code)}">Suggest a resource</a><a class="btn btn-secondary" href="{{root}}online.html">Browse online options</a></div>
    {signup_form(f"Tell me when {st['name']} launches", code)}
    {law_box(code, None)}
  </section>
  <div class="panel">{outline_svg(st["d"], "Outline of " + st["name"])}</div>
</div>'''
    page(f"{code.lower()}/index.html", f"Homeschool resources in {st['name']}: coming soon | ShareSchooling",
         f"ShareSchooling is coming to {st['name']}. Suggest a homeschool co-op, tutor or resource, or sign up to hear when it launches.",
         body, state_code=code, community={"kind": "state", "state": code})


def neighbors_html(c):
    items = []
    for key in sorted(c["neighbors"], key=lambda k: (COUNTIES[k]["state"] != c["state"], COUNTIES[k]["name"])):
        n = COUNTIES[key]
        label = n["label"] + (f", {n['state']}" if n["state"] != c["state"] else "")
        status = plural(len(county_listings(key))) if n["pilot"] else "coming soon"
        items.append(f'<li><a href="{{root}}{county_url(n)}"><span>{esc(label)}</span><span class="count">{status}</span></a></li>')
    return f'<section class="panel" aria-labelledby="near-heading"><h2 id="near-heading">Nearby counties</h2><ul class="link-list">{"".join(items)}</ul></section>'


def also_column(code):
    sw = statewide(code)
    return (f'<aside class="also-col" aria-labelledby="also-heading"><h2 id="also-heading">Also available to you</h2>'
            f'<p class="hint">Statewide resources for {esc(STATES[code]["name"])} families.</p>'
            f'{card_list(sw, None, "None match these filters.")}</aside>')


def build_pilot_county(c):
    code, st = c["state"], STATES[c["state"]]
    listings = county_listings(c["key"])
    sw = statewide(code)
    pinned = listings + [l for l in sw if l["_home"] == c["key"]]
    cities = sorted((ci for ci in CITIES.values() if ci["county"]["key"] == c["key"]), key=lambda ci: ci["name"])
    place = f"{c['label']}, {code}"
    nlocal = len(listings)
    ncats = len({l["category"] for l in listings})
    city_links = "".join(f'<li><a href="{{root}}{city_url(ci)}"><span>{esc(ci["name"])}</span><span class="count">{len(ci["listings"])} based here</span></a></li>' for ci in cities)
    shown = unique_listings(pinned)
    body = f'''
{crumbs_for(state=code, county=c)}
<h1>Homeschool resources in {esc(c["label"])}, {esc(st["name"])}</h1>
<p class="intro map-intro">{plural(nlocal, "local and regional listing")} serve {esc(c["label"])} across {ncats} categories, plus statewide resources for {esc(st["name"])} families.</p>
{filter_bar(code, with_map=True, list_total=nlocal)}
{explorer_block(c, shown, "Map of " + place)}
{county_community(code, c["name"])}
<div class="list-extra">
  <div class="map-layout">
    <div>
      {f'<section class="panel" aria-labelledby="cities-h"><h2 id="cities-h">Cities</h2><ul class="link-list">{city_links}</ul></section>' if cities else ""}
    </div>
    {neighbors_html(c)}
  </div>
  <div class="results-layout" style="margin-top:1.5rem">
    <div>{category_sections(listings, code, suggest_href(code, c["name"]))}
    {missing_categories_note(listings, code, suggest_href(code, c["name"]))}</div>
    {also_column(code)}
  </div>
</div>'''
    jsonld = json_ld(item_list(f"Homeschool resources in {place}", listings))
    page(county_url(c) + "index.html", f"Homeschool co-ops, tutors & resources in {place} | ShareSchooling",
         f"Find homeschool co-ops, tutors, classes, field trips and support in {place}. {nlocal} local listings plus statewide resources.",
         body, state_code=code, county_name=c["name"], extra_head="\n  " + jsonld,
         community={"kind": "county", "state": code, "county": c["name"]})


def build_other_county(c):
    code, st = c["state"], STATES[c["state"]]
    place = f"{c['label']}, {code}"
    body = f'''
{crumbs_for(state=code, county=c)}
<div class="map-layout">
  <section class="panel coming-soon">
    <div class="big" aria-hidden="true">🌱</div>
    <h1>{esc(c["label"])}, {esc(st["name"])} is coming soon</h1>
    <p>Local listings for {esc(c["label"])} aren't in the pilot yet. Statewide resources below are open to you now.</p>
    <div class="btn-row"><a class="btn" href="{{root}}{suggest_href(code, c["name"])}">Suggest a resource</a></div>
    {signup_form(f"Tell me when {c['label']} launches", code, c["name"])}
  </section>
  <div>
    <div class="panel">{outline_svg(c["d"], "Outline of " + place)}</div>
    {neighbors_html(c)}
  </div>
</div>
<div style="margin-top:1.5rem">{also_column(code)}</div>'''
    page(county_url(c) + "index.html", f"Homeschool resources in {place}: coming soon | ShareSchooling",
         f"Local homeschool listings for {place} are coming soon. See statewide resources for {st['name']} families, or suggest a resource.",
         body, state_code=code, county_name=c["name"])


def build_city(ci):
    c = ci["county"]
    code, st = c["state"], STATES[c["state"]]
    here = sort_listings(ci["listings"])
    ids = {l["id"] for l in here}
    rest = [l for l in county_listings(c["key"]) if l["id"] not in ids]
    sw = statewide(code)
    place = f"{ci['name']}, {code}"
    mapped = unique_listings(here + rest + [l for l in sw if l["_home"] == c["key"]])
    body = f'''
{crumbs_for(state=code, county=c, city=ci)}
<h1>Homeschool resources in {esc(ci["name"])}, {esc(st["name"])}</h1>
<p class="intro map-intro">{len(here)} listings are based in {esc(ci["name"])}, and {len(rest)} more serve the rest of {esc(c["label"])}. Pins for {esc(ci["name"])} are solid color. Faded pins are elsewhere in {esc(c["label"])}.</p>
{filter_bar(code, with_map=True, list_total=len(here) + len(rest))}
{explorer_block(c, mapped, "Map of " + c["label"] + ", with " + ci["name"] + " highlighted", emphasize=ci["name"])}
{county_community(code, c["name"])}
<div class="list-extra">
  <div class="map-layout">{neighbors_html(c)}</div>
  <div class="results-layout" style="margin-top:1.5rem">
    <div>
      <section class="cat-section" data-section aria-labelledby="here-h"><h2 id="here-h">In {esc(ci["name"])}</h2>{card_list(here, code, "None match these filters.")}</section>
      <section class="cat-section" data-section aria-labelledby="rest-h"><h2 id="rest-h">Elsewhere in {esc(c["label"])}</h2>{card_list(rest, code, "None match these filters.")}</section>
      <p class="empty-note" data-all-empty hidden>No listings match these filters yet. <a href="{{root}}{suggest_href(code, c["name"])}">Suggest a resource</a></p>
    </div>
    {also_column(code)}
  </div>
</div>'''
    jsonld = json_ld(item_list(f"Homeschool resources in {place}", here + rest))
    page(city_url(ci) + "index.html", f"Homeschool co-ops, tutors & resources in {place} | ShareSchooling",
         f"Homeschool co-ops, tutors, classes and support in {place} and the rest of {c['label']}.",
         body, state_code=code, county_name=c["name"], extra_head="\n  " + jsonld,
         community={"kind": "county", "state": code, "county": c["name"]})


def build_listing(l):
    loc = l.get("location") or {}
    code = l["_state"]
    county = COUNTIES.get(l["_home"]) if l["_home"] else None
    city = CITIES.get((l["_home"], l["_city"])) if county else None
    cat = CAT_NAME.get(l["category"], l["category"])

    rows = []

    def row(label, value_html):
        if value_html:
            rows.append(f"<dt>{esc(label)}</dt><dd>{value_html}</dd>")

    serves = [COUNTIES[k] for k in l["_serves"]]
    serves_html = ", ".join(f'<a href="{{root}}{county_url(s)}">{esc(s["label"])}{", " + s["state"] if s["state"] != code else ""}</a>' for s in serves)
    if l["reach"] == "Statewide" and not serves:
        serves_html = f'All of <a href="{{root}}{state_url(code)}">{esc(STATES[code]["name"])}</a>'
    location_bits = [x for x in [loc.get("city"), (county["label"] if county else None), STATES[code]["name"] if code else None] if present(x)]
    row("Category", esc(cat))
    row("Who it serves", esc(l["reach"]))
    row("Serves", serves_html)
    row("Based in", esc(", ".join(location_bits)))
    if present(loc.get("address")):
        row("Address", esc(loc["address"]))
    elif present(loc.get("zip")):
        row("Zip code", esc(loc["zip"]))
    row("Delivery", esc(l["delivery"]))
    row("Ages / grades", esc(l["agesGrades"]) if present(l.get("agesGrades")) else "")
    row("Faith", esc(l["religiousAffiliation"]) if l.get("religiousAffiliation") in ("Faith-based", "Secular") else "")
    row("Cost", esc(l["costNotes"]) if present(l.get("costNotes")) else "")
    if present(l.get("website")):
        row("Website", f'<a href="{esc(l["website"])}" rel="noopener nofollow">{esc(l["website"])}</a>')
    if present(l.get("email")):
        row("Email", f'<a href="mailto:{esc(l["email"])}">{esc(l["email"])}</a>')
    if present(l.get("phone")):
        row("Phone", f'<a href="tel:{esc(re.sub(r"[^0-9+]", "", l["phone"]))}">{esc(l["phone"])}</a>')
    row("Source", f'<a href="{esc(l["sourceUrl"])}" rel="noopener nofollow">{esc(l["sourceUrl"])}</a>' if present(l.get("sourceUrl")) else "")
    row("Last verified", esc(fmt_date(l.get("lastChecked"))))
    row("Claim status", f'<span data-claim-status>{esc(l.get("claimStatus") or "")}</span>')
    if l.get("status") == "Draft":
        row("Listing status", "Draft (not yet published)")

    contact = []
    if present(l.get("phone")):
        contact.append(f'<a class="btn" href="tel:{esc(re.sub(r"[^0-9+]", "", l["phone"]))}">Call</a>')
    if present(l.get("email")):
        contact.append(f'<a class="btn btn-secondary" href="mailto:{esc(l["email"])}">Email</a>')
    if present(l.get("website")):
        contact.append(f'<a class="btn btn-secondary" href="{esc(l["website"])}" rel="noopener nofollow">Website</a>')

    featured = l.get("featured") and l.get("listingTier") == "Featured"
    photo = f'<img class="feature-photo" src="{{root}}{esc(l["photo"])}" alt="Photo for {esc(l["name"])}">' if featured and present(l.get("photo")) else ""
    long_desc = f'<p>{esc(l["longDescription"])}</p>' if featured and present(l.get("longDescription")) else ""

    if county and l.get("latitude") is not None:
        side_map = interactive_map(county, [l], f"Map of {county['label']} showing {l['name']}", small=True, preview=False)
        map_note = "Approximate location (city only)." if l.get("geocodePrecision") == "city" else "Exact location."
    elif county:
        side_map = outline_svg(county["d"], "Outline of " + county["label"])
        map_note = "No fixed spot on the map. Serves the area shown."
    else:
        side_map = outline_svg(STATES[code]["d"], "Outline of " + STATES[code]["name"])
        map_note = "Serves the whole state."

    tags = []
    if l.get("featured"):
        tags.append('<li><span class="tag tag-featured">Featured</span></li>')
    if l.get("status") == "Draft":
        tags.append('<li><span class="tag tag-draft">Draft</span></li>')
    tags.append(f'<li><span class="tag">{esc(l["reach"])}</span></li><li><span class="tag">{esc(l["delivery"])}</span></li>')
    if l.get("religiousAffiliation") in ("Faith-based", "Secular"):
        tags.append(f'<li><span class="tag">{esc(l["religiousAffiliation"])}</span></li>')

    body = f'''
{crumbs_for(state=code, county=county, city=city, last=l["name"])}
<div class="detail-layout">
  <article>
    <ul class="tags">{"".join(tags)}</ul>
    <h1 style="margin-top:0.5rem">{esc(l["name"])}</h1>
    <p class="cat" style="color:var(--color-primary-hover);font-weight:700">{esc(cat)}</p>
    {photo}
    <p data-public-description>{esc(l["description"])}</p>
    {long_desc}
    {f'<p class="confirm-note">{CONFIRM_NOTE}</p>' if l["_needs_note"] else ""}
    {f'<div class="contact-actions">{"".join(contact)}</div>' if contact else ""}
    <dl class="detail-fields">{"".join(rows)}</dl>
    <div class="detail-actions">
      <a href="{{root}}list-your-resource.html?claim={esc(l["id"])}#claim">Claim this listing</a>
      <button type="button" class="link-button" data-report>Report an issue</button>
    </div>
    <p class="form-message" data-report-message role="status"></p>
    {listing_community_blocks(l)}
  </article>
  <aside class="panel" aria-label="Location">
    {side_map}
    {f'<p class="hint" style="margin:0.5rem 0 0">{map_note}</p>' if map_note else ""}
  </aside>
</div>'''

    org = {"@context": "https://schema.org", "@type": "Organization", "name": l["name"], "description": l["description"]}
    if present(loc.get("address")) and "p.o. box" not in loc["address"].lower():
        org["@type"] = "LocalBusiness"
    if present(l.get("website")):
        org["url"] = l["website"]
    if present(l.get("email")):
        org["email"] = l["email"]
    if present(l.get("phone")):
        org["telephone"] = l["phone"]
    if present(loc.get("address")) or present(loc.get("city")):
        addr = {"@type": "PostalAddress", "addressRegion": code, "addressCountry": "US"}
        if present(loc.get("address")):
            addr["streetAddress"] = loc["address"]
        if present(loc.get("city")):
            addr["addressLocality"] = loc["city"]
        if present(loc.get("zip")):
            addr["postalCode"] = loc["zip"]
        org["address"] = addr
    org["areaServed"] = [f"{s['label']}, {s['state']}" for s in serves] or STATES[code]["name"]

    where = ", ".join(x for x in [l["_city"], code] if x)
    page(l["_url"] + "index.html", f"{l['name']}: {cat}{' in ' + where if where else ''} | ShareSchooling",
         l["description"][:155], body, state_code=code, county_name=county["name"] if county else "",
         extra_head="\n  " + json_ld(org),
         community={"kind": "listing", "listingId": l["id"], "name": l["name"]})


def build_online():
    online = sort_listings([l for l in LISTINGS if l["delivery"] in ("Online", "Both")])
    body = f'''
<h1>Online options</h1>
<p class="intro">Programs in the pilot that families can use online, in full or in part. Narrow them down by category, reach, delivery or faith.</p>
{filter_bar()}
{category_sections(online, None, suggest_href())}'''
    page("online.html", "Online homeschool programs and resources | ShareSchooling",
         "Homeschool programs and resources you can use online, from the ShareSchooling West Tennessee and DeSoto County pilot.", body)


def build_template_pages():
    county_opts = "".join(f'<option value="{esc(c["state"])}:{esc(c["name"])}">{esc(c["label"])}{", MS" if c["state"] == "MS" else ""}</option>'
                          for c in sorted((c for c in COUNTIES.values() if c["pilot"]), key=lambda c: (c["state"] != "TN", c["name"])))
    cat_opts = "".join(f'<option value="{esc(c["id"])}">{esc(c["name"])}</option>' for c in CATS)
    for f in sorted((ROOT / "templates/pages").glob("*.html")):
        text = f.read_text()
        title = re.search(r"<!--\s*title:\s*(.*?)\s*-->", text).group(1)
        desc = re.search(r"<!--\s*description:\s*(.*?)\s*-->", text).group(1)
        body = re.sub(r"<!--\s*(title|description):.*?-->\n?", "", text)
        body = body.replace("{{category_options}}", cat_opts).replace("{{county_options}}", county_opts)
        if community_on("reviews"):
            body = body.replace(
                "[Placeholder: the claim process isn't built yet.]",
                "Sign in, confirm that you represent the organization, and ask an admin to verify the claim. This test server does not send mail.",
            )
            body = body.replace(
                '<p class="form-note" data-claim-note hidden></p>',
                '<p class="form-note" data-claim-note hidden></p>\n  <div data-claim-flow></div>',
            )
        page(f.name, f"{title} | ShareSchooling", desc, body, community={"kind": "claim" if f.name == "list-your-resource.html" else "page"})


# ---------------------------------------------------------------- write everything

def clean_old_output():
    for code in STATES:
        shutil.rmtree(ROOT / code.lower(), ignore_errors=True)
    shutil.rmtree(ROOT / "listing", ignore_errors=True)
    for extra in ("account", "admin", "looking-for", "saved", "portal", "sample"):
        shutil.rmtree(ROOT / extra, ignore_errors=True)


def norm_place(text):
    text = re.sub(r"\bcounty\b", " ", str(text).lower().replace(".", " "))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def build_places():
    """City and pilot-county names the ZIP/city box can jump to. Not listing content."""
    cities = {}
    for ci in CITIES.values():
        pts = [(l["latitude"], l["longitude"]) for l in ci["listings"] if l.get("latitude") is not None]
        rec = {
            "name": ci["name"], "state": ci["county"]["state"], "county": ci["county"]["name"],
            "url": city_url(ci), "countyUrl": county_url(ci["county"]),
            "lat": round(sum(p[0] for p in pts) / len(pts), 5) if pts else None,
            "lon": round(sum(p[1] for p in pts) / len(pts), 5) if pts else None,
        }
        bucket = cities.setdefault(norm_place(ci["name"]), [])
        if not any(r["url"] == rec["url"] for r in bucket):
            bucket.append(rec)
    counties = {}
    for c in COUNTIES.values():
        if not c["pilot"]:
            continue
        rec = {"name": c["label"], "state": c["state"], "url": county_url(c), "countyUrl": county_url(c)}
        for key in (norm_place(c["name"]), norm_place(c["label"])):
            if not key:
                continue
            bucket = counties.setdefault(key, [])
            if not any(r["url"] == rec["url"] for r in bucket):
                bucket.append(rec)
    states = {code: st["name"] for code, st in STATES.items()}
    return {"cities": cities, "counties": counties, "states": states}


def main():
    clean_old_output()
    build_home()
    for code in STATES:
        (build_pilot_state if code in PILOT else build_other_state)(code)
    for c in COUNTIES.values():
        (build_pilot_county if c["pilot"] else build_other_county)(c)
    for ci in CITIES.values():
        build_city(ci)
    for l in LISTINGS:
        build_listing(l)
    build_online()
    build_template_pages()
    if community_on("reviews"):
        build_account_page()
        build_admin_page()
    if community_on("lookingFor"):
        build_looking_page()
    if community_on("favorites"):
        build_saved_page()
    if community_on("groupPortal"):
        build_portal_page()
    if community_on("lawGuides"):
        build_law_pages()
    catalog = []
    for listing in LISTINGS:
        loc = listing.get("location") or {}
        catalog.append({
            "id": listing["id"],
            "name": listing["name"],
            "email": listing.get("email") or "",
            "website": listing.get("website") or "",
            "state": listing["_state"],
            "county": loc.get("county") or "",
            "city": listing["_city"],
            "category": listing["category"],
        })
    (ROOT / "data" / "community-catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")))

    for path, doc in PAGES:
        out = ROOT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc)

    routes = {c["fips"]: [county_url(c), c["pilot"], f"{c['label']}, {c['state']}"] for c in COUNTIES.values()}
    (ROOT / "data/county-routes.json").write_text(json.dumps(routes, separators=(",", ":")))
    (ROOT / "data/places.json").write_text(json.dumps(build_places(), ensure_ascii=False, separators=(",", ":")))

    today = date.today().isoformat()
    urls = "".join(f"  <url><loc>{esc(BASE + (p[:-len('index.html')] if p.endswith('index.html') else p))}</loc><lastmod>{today}</lastmod></url>\n"
                   for p, _ in sorted(PAGES))
    (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    print(f"Built {len(PAGES)} pages ({len(LISTINGS)} listings, {sum(c['pilot'] for c in COUNTIES.values())} pilot counties, {len(CITIES)} cities).")


if __name__ == "__main__":
    main()
