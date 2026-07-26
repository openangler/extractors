#!/usr/bin/env python3
"""
build_pmtw_layer.py — turn the 1,809 Public Mountain Trout Water reaches into a
queryable trout "where" layer.

For each PMTW stream reach: stream name, reach description, WRC classification +
a plain-language REGULATION summary, Mountain Heritage flag, length, a
representative midpoint coordinate, the county (point-in-polygon against our
county boundaries), and midpoint elevation (USGS 3DEP).

Output -> trout-waters/pmtw-reaches.json     (the reach index)
       -> trout-waters/pmtw-summary.json      (counts by class & county)

    python3 build_pmtw_layer.py                # with elevation (1,809 EPQS calls)
    python3 build_pmtw_layer.py --no-elevation # fast, skip elevation
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.expanduser("~/onedrive/fishing/nc-fishing-guide-data")
TW = os.path.join(BASE, "trout-waters")
EPQS = "https://epqs.nationalmap.gov/v1/json"

# plain-language regulation summary per WRC classification (verify current regs
# at the NCWRC link on each reach — these are standard NC trout-water rules).
REGS = {
    "Wild Trout Waters":
        "Single-hook artificial lures only (no natural bait). 7\" min size, 4-trout "
        "creel. Open all year.",
    "Hatchery Supported Trout Waters":
        "Any bait or lure incl. natural bait. No size limit, 7-trout creel. Open all "
        "year EXCEPT closed Mar 1 – 7 a.m. first Sat in April (stocking).",
    "Delayed Harvest Trout Waters":
        "Oct 1 – first Sat in June: CATCH & RELEASE, single-hook artificial lures "
        "only, no harvest. First Sat in June – Sep 30: hatchery-supported rules "
        "(harvest & any bait). Heavily stocked — top numbers water.",
    "Catch and Release/Artificial Flies and Lures Only Trout Waters":
        "Catch & release only, single-hook artificial FLIES AND LURES only. No "
        "harvest, year-round.",
    "Special Regulation Trout Waters":
        "Special site-specific regulations — check the posted/NCWRC rules for this "
        "water before fishing.",
}


def midpoint(geom):
    """Representative point: the middle vertex of the flattened (multi)line."""
    pts = []
    if geom["type"] == "MultiLineString":
        for line in geom["coordinates"]:
            pts.extend(line)
    elif geom["type"] == "LineString":
        pts = geom["coordinates"]
    if not pts:
        return None
    return pts[len(pts) // 2]        # [lon, lat]


def load_counties():
    g = json.load(open(os.path.join(BASE, "reference-layers", "county-boundaries.geojson")))
    props = g["features"][0]["properties"]
    namekey = next((k for k in props if "name" in k.lower() or "cnty" in k.lower()
                    or "county" in k.lower()), None)
    polys = []
    for f in g["features"]:
        name = f["properties"].get(namekey, "?")
        geom = f["geometry"]
        rings = (geom["coordinates"] if geom["type"] == "Polygon"
                 else [r for poly in geom["coordinates"] for r in poly])
        for ring in rings:
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            polys.append((name, ring, min(xs), min(ys), max(xs), max(ys)))
    return polys


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def county_for(lon, lat, polys):
    for name, ring, x0, y0, x1, y1 in polys:
        if x0 <= lon <= x1 and y0 <= lat <= y1 and point_in_ring(lon, lat, ring):
            return name
    return None


def elevation(lat, lon):
    try:
        d = json.loads(urllib.request.urlopen(
            urllib.request.Request(
                f"{EPQS}?" + urllib.parse.urlencode(
                    {"x": lon, "y": lat, "units": "Meters", "wkid": 4326}),
                headers={"User-Agent": "pmtw-layer/1.0"}), timeout=30).read())
        v = float(d["value"])
        return round(v, 1) if v > -1000 else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-elevation", action="store_true")
    a = ap.parse_args()

    streams = json.load(open(os.path.join(TW, "pmtw-streams-2025.geojson")))
    counties = load_counties()
    print(f"Building layer from {len(streams['features'])} PMTW reaches ...", flush=True)

    reaches = []
    for f in streams["features"]:
        p = f["properties"]
        mp = midpoint(f["geometry"])
        if not mp:
            continue
        lon, lat = mp[0], mp[1]
        cls = p.get("WRC_Class")
        mhtw = (p.get("FIRST_MHTW", "").strip() or p.get("MHTW_Reach", "").strip())
        reaches.append({
            "stream_name": p.get("Displ_Name"),
            "reach": p.get("FIRST_Reg1") or p.get("FIRST_Reg_"),
            "wrc_class": cls,
            "regulation_summary": REGS.get(cls, "See NCWRC rules."),
            "mountain_heritage": bool(mhtw and mhtw != " "),
            "mhtw_reach": mhtw if (mhtw and mhtw != " ") else None,
            "length_m": round(p.get("Shape__Length", 0)),
            "midpoint": {"lat": round(lat, 5), "lon": round(lon, 5)},
            "county": county_for(lon, lat, counties),
            "elevation_m": None,
            "ncwrc_link": p.get("WEB_Refere"),
        })
    print(f"  midpoints + counties done ({sum(1 for r in reaches if r['county'])} "
          f"with county).", flush=True)

    if not a.no_elevation:
        print("  fetching midpoint elevations (USGS 3DEP) ...", flush=True)

        def add_elev(i):
            reaches[i]["elevation_m"] = elevation(reaches[i]["midpoint"]["lat"],
                                                  reaches[i]["midpoint"]["lon"])
            return i
        done = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            for _ in as_completed([ex.submit(add_elev, i) for i in range(len(reaches))]):
                done += 1
                if done % 300 == 0 or done == len(reaches):
                    print(f"    {done}/{len(reaches)}", flush=True)

    reaches.sort(key=lambda r: (r["county"] or "zz", r["stream_name"] or ""))
    with open(os.path.join(TW, "pmtw-reaches.json"), "w") as f:
        json.dump(reaches, f, indent=2)

    # summary
    from collections import Counter
    by_class = Counter(r["wrc_class"] for r in reaches)
    by_county = Counter(r["county"] for r in reaches if r["county"])
    summary = {
        "total_reaches": len(reaches),
        "by_class": dict(by_class),
        "mountain_heritage_reaches": sum(1 for r in reaches if r["mountain_heritage"]),
        "top_counties": dict(by_county.most_common(12)),
        "elevation_included": not a.no_elevation,
    }
    with open(os.path.join(TW, "pmtw-summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("Done ->", os.path.join(TW, "pmtw-reaches.json"))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
