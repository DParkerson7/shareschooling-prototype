"""
Build data/interstates.json from US Census TIGER/Line primary roads.

Keeps interstate highways only (RTTYP = I). Geometry is public domain
(U.S. government work). The lines are projected with the same lower-48
Albers formula as data/map.json and simplified for the small maps.

    python3 tools/build_roads.py [/path/to/tl_*_us_primaryroads.shp]

If you pass no path, the script reads /tmp/tiger/tl_2024_us_primaryroads.shp
after you unzip the Census download:

    https://www2.census.gov/geo/tiger/TIGER2024/PRIMARYROADS/tl_2024_us_primaryroads.zip

Uses only the Python standard library. build_site.py reads the JSON; it does
not download Census files.
"""
import json
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import project  # noqa: E402

DEFAULT_SHP = Path("/tmp/tiger/tl_2024_us_primaryroads.shp")
OUT = ROOT / "data" / "interstates.json"
# About a third of a mile in this projection. Fine for a statewide map.
SIMPLIFY = 0.28


def read_dbf(path):
    data = path.read_bytes()
    nrec, hlen, rlen = struct.unpack("<IHH", data[4:12])
    pos = 32
    fields = []
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\x00")[0].decode()
        typ = chr(data[pos + 11])
        length = data[pos + 16]
        fields.append((name, typ, length))
        pos += 32
    body = data[hlen:]
    rows = []
    for i in range(nrec):
        rec = body[i * rlen:(i + 1) * rlen]
        if rec[:1] == b"*":
            rows.append(None)
            continue
        o = 1
        vals = {}
        for name, typ, length in fields:
            vals[name] = rec[o:o + length].decode("latin1").strip()
            o += length
        rows.append(vals)
    return rows


def iter_polylines(shp_path):
    """Yield (record_index, list of parts) for PolyLine shapes. record_index matches the DBF."""
    data = shp_path.read_bytes()
    pos = 100
    index = 0
    while pos + 8 <= len(data):
        _num, words = struct.unpack(">II", data[pos:pos + 8])
        pos += 8
        end = pos + words * 2
        chunk = data[pos:end]
        pos = end
        if len(chunk) < 4:
            index += 1
            continue
        shape_type = struct.unpack("<i", chunk[:4])[0]
        if shape_type == 0:
            yield index, []
        elif shape_type in (3, 13):  # PolyLine, PolyLineZ
            num_parts, num_points = struct.unpack("<ii", chunk[36:44])
            parts = struct.unpack("<" + "i" * num_parts, chunk[44:44 + 4 * num_parts])
            start = 44 + 4 * num_parts
            # PolyLineZ has z and m after the xy points; xy still comes first.
            pts = []
            for i in range(num_points):
                x, y = struct.unpack("<dd", chunk[start + 16 * i:start + 16 * i + 16])
                pts.append((x, y))
            parts = list(parts) + [num_points]
            segs = [pts[parts[i]:parts[i + 1]] for i in range(num_parts) if parts[i + 1] - parts[i] >= 2]
            yield index, segs
        else:
            yield index, []
        index += 1


def route_ref(fullname):
    """'W I- 40' and 'I- 240' become '40' and '240'. Skip Hawaii H routes."""
    if re.search(r"\bH-?\s*\d", fullname):
        return None
    match = re.search(r"I-\s*(\d{1,3})\b", fullname)
    if not match:
        return None
    return match.group(1)


def dist_point_line(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    mag = dx * dx + dy * dy
    if mag == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / mag))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def rdp(points, eps):
    if len(points) < 3:
        return points
    end = len(points) - 1
    worst, idx = 0, 0
    for i in range(1, end):
        d = dist_point_line(points[i], points[0], points[end])
        if d > worst:
            worst, idx = d, i
    if worst <= eps:
        return [points[0], points[end]]
    return rdp(points[:idx + 1], eps)[:-1] + rdp(points[idx:], eps)


def in_lower_48(lon, lat):
    return -125 <= lon <= -66 and 24 <= lat <= 50


def main():
    shp = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SHP
    dbf = shp.with_suffix(".dbf")
    if not shp.exists() or not dbf.exists():
        sys.exit(f"Need the Census shapefile and DBF at {shp}. See the top of this script.")
    rows = read_dbf(dbf)
    lines = []
    kept = 0
    for index, parts in iter_polylines(shp):
        row = rows[index] if index < len(rows) else None
        if not row or row.get("RTTYP") != "I":
            continue
        ref = route_ref(row.get("FULLNAME", ""))
        if not ref:
            continue
        for part in parts:
            projected = []
            for lon, lat in part:
                if not in_lower_48(lon, lat):
                    if len(projected) >= 2:
                        lines.append({"ref": ref, "pts": rdp(projected, SIMPLIFY)})
                    projected = []
                    continue
                projected.append(project(lon, lat))
            if len(projected) >= 2:
                lines.append({"ref": ref, "pts": rdp(projected, SIMPLIFY)})
                kept += 1
    # Drop tiny spurs left by simplification.
    cleaned = []
    for line in lines:
        pts = line["pts"]
        length = sum(math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:]))
        if length < 0.35:
            continue
        cleaned.append({"ref": line["ref"], "pts": [[round(x, 2), round(y, 2)] for x, y in pts]})
    doc = {
        "_about": (
            "Interstate highways only, for the ShareSchooling maps. "
            "Source: U.S. Census Bureau TIGER/Line 2024 primary roads "
            "(tl_2024_us_primaryroads), filtered to RTTYP = 'I'. "
            "License: public domain (U.S. government work). "
            "Projected with the same lower-48 Albers formula as data/map.json "
            "(d3.geoAlbersUsa scale 1300, translate [487.5, 305]) and simplified for display. "
            "Alaska and Hawaii are omitted because those states are drawn as insets, "
            "not in this projection. Regenerate with tools/build_roads.py."
        ),
        "source": "https://www2.census.gov/geo/tiger/TIGER2024/PRIMARYROADS/tl_2024_us_primaryroads.zip",
        "license": "Public domain. U.S. Census Bureau TIGER/Line.",
        "year": 2024,
        "lines": cleaned,
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")))
    pts = sum(len(line["pts"]) for line in cleaned)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(cleaned)} lines, {pts} points, from {kept} parts).")


if __name__ == "__main__":
    main()
