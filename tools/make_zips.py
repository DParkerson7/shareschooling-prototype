"""
Rebuilds data/zips.json: zip code -> county and zip centre point, for the
pilot states. Uses free US Census files (public domain), no paid API.

Steps:
  1. Download both files:
     https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt
     https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_zcta_national.zip  (unzip it)
  2. Run:  python3 tools/make_zips.py tab20_zcta520_county20_natl.txt 2020_Gaz_zcta_national.txt data/zips.json

A zip that crosses a county line is assigned to the county holding most of its land.
"""
import csv, json, sys

STATES = {"47", "28"}  # Tennessee, Mississippi
rel_path, gaz_path, out = sys.argv[1:4]

best = {}  # zip -> (land area in county, county FIPS)
with open(rel_path, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f, delimiter="|"):
        z, county = row["GEOID_ZCTA5_20"], row["GEOID_COUNTY_20"]
        if not z:
            continue
        area = int(row["AREALAND_PART"] or 0)
        if z not in best or area > best[z][0]:
            best[z] = (area, county)

centres = {}
with open(gaz_path, encoding="utf-8") as f:
    reader = csv.reader(f, delimiter="\t")
    next(reader)
    for row in reader:
        centres[row[0].strip()] = (round(float(row[5]), 4), round(float(row[6]), 4))

zips = {z: [c, *centres[z]] for z, (_, c) in sorted(best.items()) if c[:2] in STATES and z in centres}
json.dump({"source": "US Census Bureau 2020 ZCTA files", "zips": zips}, open(out, "w"), separators=(",", ":"))
print(len(zips), "zip codes")
