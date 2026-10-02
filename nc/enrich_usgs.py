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
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, ARCHIVE, FEDERAL, QUERY

# The USGS lookups are state-independent and live in shared/usgs.py; they are
# re-exported here because this script and its tests have always reached them
# as enrich_usgs.<name>.
from usgs import (NHD_NODATA, elevation, enrich_site,  # noqa: F401
                  epqs_url, get, haversine, load_gages, nearest_gage,
                  nhd_number, nhd_pick, nhd_reach, nhd_url, parse_elevation)

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
    gages = load_gages("nc")
    print(f"  {len(gages)} gages. Enriching {len(sites)} sites ...", flush=True)

    out = {}
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(enrich_site, s, gages): s for s in sites}
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
