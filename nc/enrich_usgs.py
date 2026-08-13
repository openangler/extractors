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

Output -> <out>/fishing-areas/enrichment.json  (keyed by locationID)
       -> merged all-locations-enriched.json

    python3 enrich_usgs.py           # all sites
    python3 enrich_usgs.py --limit 25 --waterbody "FRENCH BROAD"   # test subset
    python3 enrich_usgs.py --out /data/nc-fishing-guide-data
"""

import argparse
import json
import math
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, ARCHIVE, FEDERAL, QUERY

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


# NHDPlus HR value-added attributes carry no-data sentinels rather than nulls:
# -9 on streamorde, -9998/-9999 on slope / totdasqkm / qama. They look like data
# (a -9 stream order sorts below a headwater stream), so normalise them here —
# at extraction, once — instead of leaving every consumer to recognise them.
NHD_NODATA = (-9.0, -9998.0, -9999.0)


def nhd_number(raw, allow_negative=False):
    """NHDPlus VAA value -> float, or None if it is a no-data sentinel.

    Stream order, slope, drainage area and mean-annual flow are all
    non-negative quantities, so any negative is treated as no-data too — that
    catches sentinel codes NHDPlus adds later without a code change.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v in NHD_NODATA or (not allow_negative and v < 0):
        return None
    return v


def epqs_url(lat, lon):
    return f"{EPQS}?" + urllib.parse.urlencode(
        {"x": lon, "y": lat, "units": "Meters", "wkid": 4326})


def parse_elevation(payload):
    """EPQS response -> metres. Its own no-data value is -1000000."""
    try:
        v = float(json.loads(payload)["value"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return round(v, 1) if v > -1000 else None


def elevation(lat, lon):
    try:
        return parse_elevation(get(epqs_url(lat, lon)))
    except Exception:
        return None


def nhd_url(lat, lon):
    q = urllib.parse.urlencode({
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "distance": 350, "units": "esriSRUnit_Meter",
        "outFields": "gnis_name,streamorde,slope,totdasqkm,lengthkm,qama",
        "returnGeometry": "false", "f": "json"})
    return f"{NHD}?{q}"


def nhd_pick(feats, waterbody):
    """Pick the reach for this site and normalise its attributes.

    Prefers a flowline whose GNIS name matches the waterbody, else the one with
    the largest drainage area.
    """
    if not feats:
        return {}
    wb = (waterbody or "").upper().replace(" RIVER", "").replace(" CREEK", "").strip()
    named = [f for f in feats if wb and f["attributes"].get("gnis_name")
             and wb in f["attributes"]["gnis_name"].upper()]
    pool = named or feats
    best = max(pool, key=lambda f: nhd_number(f["attributes"].get("totdasqkm")) or 0)
    a = best["attributes"]
    order = nhd_number(a.get("streamorde"))
    slope = nhd_number(a.get("slope"))
    da = nhd_number(a.get("totdasqkm"))
    qama = nhd_number(a.get("qama"))
    return {
        "nhd_name": a.get("gnis_name"),
        "stream_order": int(order) if order is not None else None,
        "slope": round(slope, 5) if slope is not None else None,
        "drainage_area_sqkm": round(da, 1) if da is not None else None,
        "mean_annual_flow_cfs": round(qama, 1) if qama is not None else None,
        "name_matched": bool(named),
    }


def nhd_reach(lat, lon, waterbody):
    """Nearest NHDPlus flowline; prefer a name match, else largest drainage."""
    try:
        feats = json.loads(get(nhd_url(lat, lon))).get("features", [])
    except Exception:
        return {}
    return nhd_pick(feats, waterbody)


# The three fields copied straight off the NCWRC site record so the enrichment
# is readable on its own. Everything else in a record is measured by USGS.
IDENTITY = ("locationID", "locationName", "waterbodyName")
MEASURED = ("elevation_m", "stream_order", "slope", "drainage_area_sqkm",
            "mean_annual_flow_cfs", "nhd_name", "name_matched", "nearest_gage")


def artifact_tiers(full_run, sample=None, merged_sample=None):
    """Provenance tier and role for every artifact this script writes."""
    rules = {f: FEDERAL for f in MEASURED}
    rules.update({f: AGENCY_FACTUAL for f in IDENTITY})
    arts = {
        "fishing-areas/enrichment.json": {
            "tiers": [FEDERAL, AGENCY_FACTUAL], "role": QUERY,
            # Deliberately no default: an untagged new field must not silently
            # inherit "federal", which is the permissive direction.
            "fields": {"records": "map", "rules": rules, "sample": sample},
            "note": "USGS 3DEP / NHDPlus HR / NWIS attributes, keyed by NCWRC "
                    "locationID. The three identity fields are copied from "
                    "NCWRC; every measured attribute is federal."},
    }
    if full_run:
        merged_rules = {"usgs": FEDERAL}
        # Longest match wins, so the identity fields carried into the usgs block
        # stay NCWRC's even though the block as a whole is federal.
        merged_rules.update({f"usgs.{f}": AGENCY_FACTUAL for f in IDENTITY})
        arts["fishing-areas/all-locations-enriched.json"] = {
            "tiers": [AGENCY_FACTUAL, FEDERAL], "role": ARCHIVE,
            "derived_from": ["fishing-areas/all-locations.json",
                             "fishing-areas/enrichment.json"],
            "fields": {"records": "list", "rules": merged_rules,
                       # Safe direction: an unrecognised field is NCWRC's, not
                       # federal.
                       "default": AGENCY_FACTUAL, "sample": merged_sample},
            "note": "Join of the NCWRC site record with the USGS enrichment "
                    "block. Mixed by construction: everything under `usgs` is "
                    "federal, everything else is NCWRC. Holds no content that "
                    "is not in the two artifacts it is derived from."}
    return arts


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--waterbody", help="only sites whose waterbody contains this")
    a = ap.parse_args()

    BASE = _common.resolve_out(a.out)
    SRC = os.path.join(BASE, "fishing-areas", "all-locations.json")
    print(f"Dataset -> {BASE}", flush=True)

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
    merged = []
    if not (a.limit or a.waterbody):
        for s in json.load(open(SRC)):
            m = dict(s)
            m["usgs"] = out.get(s["locationID"], {})
            merged.append(m)
        with open(os.path.join(BASE, "fishing-areas",
                               "all-locations-enriched.json"), "w") as f:
            json.dump(merged, f, indent=2)

    ok = sum(1 for r in out.values() if r.get("stream_order"))
    # Hand the real records to the manifest so it can check that every field
    # written this run actually resolves to a tier.
    _common.record_artifacts(
        BASE, "enrich_usgs.py",
        artifact_tiers(not (a.limit or a.waterbody),
                       sample=list(out.values()), merged_sample=merged or None),
        run={"sites_enriched": len(out), "with_nhd_reach": ok,
             "subset": bool(a.limit or a.waterbody),
             "sources": ["USGS 3DEP EPQS", "USGS NHDPlus HR", "USGS NWIS"]})
    print(f"Done. {ok}/{len(out)} got NHD reach attrs. -> {enr_path}", flush=True)


if __name__ == "__main__":
    main()
