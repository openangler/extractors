#!/usr/bin/env python3
"""
build_species_kb.py — generic knowledge-base builder for ALL species.

Reads every curated file in species-knowledge/curated/*.json (authored per
SCHEMA.md), computes each species' empirical HABITAT ENVELOPE from our data +
USGS enrichment, merges with the NCWRC profile, and writes:

    species-knowledge/all-species-knowledge.json   # combined, keyed by slug
    species-knowledge/kb/<slug>.json               # one per species

This supersedes the catfish-only build_catfish_kb.py: catfish now lives in
curated/catfish.json like every other species. Re-run after any agent adds a
curated file.
"""

import glob
import json
import os
import statistics as st

BASE = os.path.expanduser("~/onedrive/fishing/nc-fishing-guide-data")
CUR = os.path.join(BASE, "species-knowledge", "curated")
OUT = os.path.join(BASE, "species-knowledge")


def envelope(sites, enr, match):
    rows = []
    for s in sites:
        sp = [x["commonName"].lower() for x in (s.get("speciesInfo") or [])]
        if any(match in c for c in sp):
            r = enr.get(str(s["locationID"]), {})
            if r.get("stream_order"):
                rows.append(r)

    def rng(key, nd=1):
        v = sorted(r[key] for r in rows if r.get(key) is not None)
        if not v:
            return None
        return {"n": len(v), "p10": round(v[len(v) // 10], nd),
                "median": round(st.median(v), nd), "p90": round(v[len(v) * 9 // 10], nd)}
    return len(rows), {
        "stream_order": rng("stream_order"),
        "drainage_area_sqkm": rng("drainage_area_sqkm"),
        "mean_annual_flow_cfs": rng("mean_annual_flow_cfs"),
        "elevation_m": rng("elevation_m"),
        "slope": rng("slope", 5),
    }


def main():
    os.makedirs(os.path.join(OUT, "kb"), exist_ok=True)
    sites = json.load(open(os.path.join(BASE, "fishing-areas", "all-locations.json")))
    enr = json.load(open(os.path.join(BASE, "fishing-areas", "enrichment.json")))
    profiles = {p["slug"]: p for p in
                json.load(open(os.path.join(BASE, "species", "all-species.json")))}
    report_index = json.load(open(os.path.join(
        BASE, "species", "reports", "index.json")))

    curated = {}
    for path in sorted(glob.glob(os.path.join(CUR, "*.json"))):
        try:
            data = json.load(open(path))
        except json.JSONDecodeError as e:
            print(f"  SKIP {os.path.basename(path)}: invalid JSON ({e})")
            continue
        for slug, entry in data.items():
            if "match" not in entry:
                print(f"  SKIP {slug}: no 'match' field")
                continue
            curated[slug] = (entry, os.path.basename(path))

    kb = {}
    for slug, (cur, srcfile) in sorted(curated.items()):
        prof = profiles.get(slug, {})
        n, env = envelope(sites, enr, cur["match"])
        kb[slug] = {
            "slug": slug,
            "name": prof.get("name", slug.replace("-", " ").title()),
            "match": cur["match"],
            "curated_source_file": srcfile,
            "ncwrc_url": prof.get("url"),
            "ncwrc_fishing_tips": prof.get("fishing_tips"),
            "ncwrc_places_to_fish": prof.get("places_to_fish"),
            "ncwrc_regulations": prof.get("regulations"),
            "target_size": cur.get("target_size"),
            "baits_ranked": cur.get("baits_ranked", []),
            "bait_note": cur.get("bait_note"),
            "habitat_scoring": cur.get("habitat_scoring", {}),
            "rigs": cur.get("rigs", []),
            "seasonal": cur.get("seasonal", {}),
            "habitat_envelope": {
                "reported_access_points": n,
                "derived_from": "USGS reach attributes at every NC access point reporting this species",
                "ranges": env,
            },
            "linked_reports": [
                {"media_id": m, "filename": report_index.get(m, {}).get("filename")}
                for m in prof.get("media_ids", [])
            ],
        }
        with open(os.path.join(OUT, "kb", f"{slug}.json"), "w") as f:
            json.dump(kb[slug], f, indent=2)

    with open(os.path.join(OUT, "all-species-knowledge.json"), "w") as f:
        json.dump(kb, f, indent=2)

    print(f"Built KB for {len(kb)} species -> all-species-knowledge.json")
    for slug, v in kb.items():
        e = v["habitat_envelope"]
        so = e["ranges"].get("stream_order") or {}
        modes = {k: m.get("mode") for k, m in v["habitat_scoring"].items()}
        print(f"  {v['name']:20s} n={e['reported_access_points']:3d} "
              f"rigs={len(v['rigs'])} baits={len(v['baits_ranked'])} "
              f"modes={modes}")


if __name__ == "__main__":
    main()
