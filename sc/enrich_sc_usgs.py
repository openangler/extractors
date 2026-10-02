#!/usr/bin/env python3
"""
enrich_sc_usgs.py — add USGS hydrology to every SC fishing access point.

The SC counterpart of nc/enrich_usgs.py, over the same shared lookups
(shared/usgs.py): 3DEP elevation, the NHDPlus HR reach (stream order, slope,
drainage, mean-annual flow) and the nearest active streamgage. Gages are drawn
from SC and its two neighbours, because the Savannah and Chattooga are the
Georgia line and the Catawba, Broad and Pee Dee all arrive from NC — the
nearest gage to a border landing is often across it.

Output -> <out>/fishing-areas/enrichment.json  (keyed by locationID)

    python3 sc/enrich_sc_usgs.py --out /path/to/sc-fishing-guide-data
    python3 sc/enrich_sc_usgs.py --out ... --limit 20      # smoke test, not saved
"""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, FEDERAL, QUERY
from usgs import enrich_site, load_gages

GAGE_STATES = ("sc", "ga", "nc")
IDENTITY = ("locationID", "locationName", "waterbodyName")
MEASURED = ("elevation_m", "stream_order", "slope", "drainage_area_sqkm",
            "mean_annual_flow_cfs", "nhd_name", "name_matched", "nearest_gage")


def artifact_tiers(sample=None):
    rules = {f: FEDERAL for f in MEASURED}
    rules.update({f: AGENCY_FACTUAL for f in IDENTITY})
    return {
        "fishing-areas/enrichment.json": {
            "tiers": [FEDERAL, AGENCY_FACTUAL], "role": QUERY,
            # No default: an untagged new field must not inherit "federal".
            "fields": {"records": "map", "rules": rules, "sample": sample},
            "note": "USGS 3DEP / NHDPlus HR / NWIS attributes, keyed by SCDNR "
                    "WaterAccessID. The three identity fields are copied from "
                    "SCDNR; every measured attribute is federal."},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    ap.add_argument("--limit", type=int,
                    help="enrich only the first N sites and print them; writes nothing")
    a = ap.parse_args()
    out_dir = _common.resolve_out(a.out)
    with open(os.path.join(out_dir, "fishing-areas", "all-locations.json")) as f:
        sites = json.load(f)
    if a.limit:
        sites = sites[:a.limit]

    gages = []
    for st in GAGE_STATES:
        gages += load_gages(st)
    print(f"{len(gages)} gages ({'/'.join(GAGE_STATES)}). "
          f"Enriching {len(sites)} sites ...", flush=True)

    out = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(enrich_site, s, gages) for s in sites]
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            out[str(r["locationID"])] = r
            if n % 100 == 0 or n == len(sites):
                print(f"  {n}/{len(sites)}", flush=True)

    if a.limit:
        print(json.dumps(out, indent=2))
        return
    path = os.path.join(out_dir, "fishing-areas", "enrichment.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    ok = sum(1 for r in out.values() if r.get("stream_order"))
    _common.record_artifacts(
        out_dir, "enrich_sc_usgs.py", artifact_tiers(sample=list(out.values())),
        run={"sites_enriched": len(out), "with_nhd_reach": ok,
             "gage_states": list(GAGE_STATES),
             "sources": ["USGS 3DEP EPQS", "USGS NHDPlus HR", "USGS NWIS"]})
    print(f"Done. {ok}/{len(out)} got NHD reach attrs. -> {path}", flush=True)


if __name__ == "__main__":
    main()
