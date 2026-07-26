#!/usr/bin/env python3
"""
enrich_usgs.py — add USGS hydrology to every NC fishing access point.

For each of the 911 access points, tags on:
  * elevation_m               — USGS 3DEP point elevation (EPQS)
  * stream_order / slope      — NHDPlus HR flowline (river gradient & size)
  * drainage_area_sqkm        — cumulative drainage (proxy for river size)
  * mean_annual_flow_cfs      — NHDPlus EROM estimate
  * nhd_name                  — the matched NHD flowline name
  * nearest_gage              — closest active USGS streamgage {id,name,km,url}

This is what turns "catfish are reported downstream" into quantified reach
attributes (lower slope + higher order + bigger drainage = the warm, deep,
slow water catfish/musky favor; steep low-order reaches = trout).

Output -> nc-fishing-guide-data/fishing-areas/enrichment.json  (keyed by locationID)
       -> merged all-locations-enriched.json

    python3 enrich_usgs.py           # all sites
    python3 enrich_usgs.py --limit 25 --waterbody "FRENCH BROAD"   # test subset
"""

import argparse
import json
import math
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.expanduser("~/onedrive/fishing/nc-fishing-guide-data")
SRC = os.path.join(BASE, "fishing-areas", "all-locations.json")
EPQS = "https://epqs.nationalmap.gov/v1/json"
NHD = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/3/query"
NWIS = "https://waterservices.usgs.gov/nwis/site/"
UA = "nc-fishing-enrich/1.0"


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.2 * (i + 1))


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load_gages():
    """All active NC streamgages with real-time data -> [(id,name,lat,lon)]."""
    q = urllib.parse.urlencode({"format": "rdb", "stateCd": "nc", "siteType": "ST",
                                "siteStatus": "active", "hasDataTypeCd": "iv"})
    gages = []
    for line in get(f"{NWIS}?{q}").splitlines():
        if line.startswith("USGS\t"):
            f = line.split("\t")
            try:
                gages.append((f[1], f[2], float(f[4]), float(f[5])))
            except (ValueError, IndexError):
                pass
    return gages


def elevation(lat, lon):
    try:
        d = json.loads(get(f"{EPQS}?" + urllib.parse.urlencode(
            {"x": lon, "y": lat, "units": "Meters", "wkid": 4326})))
        v = float(d["value"])
        return round(v, 1) if v > -1000 else None
    except Exception:
        return None


def nhd_reach(lat, lon, waterbody):
    """Nearest NHDPlus flowline; prefer a name match, else largest drainage."""
    q = urllib.parse.urlencode({
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "distance": 350, "units": "esriSRUnit_Meter",
        "outFields": "gnis_name,streamorde,slope,totdasqkm,lengthkm,qama",
        "returnGeometry": "false", "f": "json"})
    try:
        feats = json.loads(get(f"{NHD}?{q}")).get("features", [])
    except Exception:
        return {}
    if not feats:
        return {}
    wb = (waterbody or "").upper().replace(" RIVER", "").replace(" CREEK", "").strip()
    named = [f for f in feats if wb and f["attributes"].get("gnis_name")
             and wb in f["attributes"]["gnis_name"].upper()]
    pool = named or feats
    best = max(pool, key=lambda f: f["attributes"].get("totdasqkm") or 0)
    a = best["attributes"]
    slope = a.get("slope")
    return {
        "nhd_name": a.get("gnis_name"),
        "stream_order": a.get("streamorde"),
        "slope": round(slope, 5) if slope not in (None, -9998, -9999) else None,
        "drainage_area_sqkm": round(a["totdasqkm"], 1) if a.get("totdasqkm") else None,
        "mean_annual_flow_cfs": round(a["qama"], 1) if a.get("qama") and a["qama"] > 0 else None,
        "name_matched": bool(named),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--waterbody", help="only sites whose waterbody contains this")
    a = ap.parse_args()

    sites = json.load(open(SRC))
    if a.waterbody:
        sites = [s for s in sites
                 if a.waterbody.upper() in (s.get("waterbodyName") or "").upper()]
    if a.limit:
        sites = sites[:a.limit]

    print(f"Loading NC active streamgages ...", flush=True)
    gages = load_gages()
    print(f"  {len(gages)} gages. Enriching {len(sites)} sites ...", flush=True)

    def enrich(s):
        lat, lon = s["latitude"], s["longitude"]
        rec = {"locationID": s["locationID"], "locationName": s["locationName"],
               "waterbodyName": s.get("waterbodyName"),
               "elevation_m": elevation(lat, lon)}
        rec.update(nhd_reach(lat, lon, s.get("waterbodyName")))
        if gages:
            gid, gname, glat, glon = min(
                gages, key=lambda g: haversine(lat, lon, g[2], g[3]))
            rec["nearest_gage"] = {
                "id": gid, "name": gname,
                "km": round(haversine(lat, lon, glat, glon), 1),
                "url": f"https://waterdata.usgs.gov/monitoring-location/{gid}/"}
        return rec

    out = {}
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(enrich, s): s for s in sites}
        for fut in as_completed(futs):
            r = fut.result()
            out[r["locationID"]] = r
            done += 1
            if done % 100 == 0 or done == len(sites):
                print(f"  {done}/{len(sites)}", flush=True)

    enr_path = os.path.join(BASE, "fishing-areas", "enrichment.json")
    # merge with any prior enrichment when running subsets
    if os.path.exists(enr_path) and (a.limit or a.waterbody):
        prior = json.load(open(enr_path))
        prior.update({str(k): v for k, v in out.items()})
        out_save = prior
    else:
        out_save = {str(k): v for k, v in out.items()}
    with open(enr_path, "w") as f:
        json.dump(out_save, f, indent=2)

    # merged enriched locations (only when full run)
    if not (a.limit or a.waterbody):
        merged = []
        for s in json.load(open(SRC)):
            m = dict(s)
            m["usgs"] = out.get(s["locationID"], {})
            merged.append(m)
        with open(os.path.join(BASE, "fishing-areas",
                               "all-locations-enriched.json"), "w") as f:
            json.dump(merged, f, indent=2)

    ok = sum(1 for r in out.values() if r.get("stream_order"))
    print(f"Done. {ok}/{len(out)} got NHD reach attrs. -> {enr_path}", flush=True)


if __name__ == "__main__":
    main()
