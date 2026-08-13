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

    python3 build_species_kb.py --out /data/nc-fishing-guide-data
"""

import argparse
import glob
import json
import os
import statistics as st

import _common
from _common import AGENCY_FACTUAL, ARCHIVE, CURATED, FEDERAL, QUERY
from species_extract import canonical_slug    # one definition of the slug rule


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


def profile_index(profiles):
    """slug -> profile, resolvable by the canonical slug or any recorded alias.

    species_extract.py canonicalises NCWRC's URL de-dup suffix
    ('largemouth-bass-0' -> 'largemouth-bass') and records the old value in
    `aliases`. Indexing the real slug, its aliases and its canonical form means
    a curated file keyed on either spelling joins, in either direction, even
    against a dataset whose profiles predate the canonicalisation. A real slug
    always wins over an alias.
    """
    idx = {p["slug"]: p for p in profiles}
    for p in profiles:
        for alias in list(p.get("aliases", [])) + [canonical_slug(p["slug"])]:
            idx.setdefault(alias, p)
    return idx


def artifact_tiers(sample=None):
    """Provenance tier and role for every artifact this script writes."""
    rules = {
        # hand-authored in species-knowledge/curated/
        "match": CURATED, "target_size": CURATED, "baits_ranked": CURATED,
        "bait_note": CURATED, "habitat_scoring": CURATED, "rigs": CURATED,
        "seasonal": CURATED, "curated_source_file": CURATED,
        # computed here from USGS reach attributes
        "habitat_envelope": FEDERAL,
        # ... except the sentence describing the method, which is written here
        "habitat_envelope.derived_from": CURATED,
        # copied from the NCWRC species profile
        "ncwrc_fishing_tips": AGENCY_FACTUAL,
        "ncwrc_places_to_fish": AGENCY_FACTUAL,
        "ncwrc_regulations": AGENCY_FACTUAL,
        "ncwrc_url": AGENCY_FACTUAL,
        "name": AGENCY_FACTUAL,
        "slug": AGENCY_FACTUAL,
        "aliases": AGENCY_FACTUAL,
        "linked_reports": AGENCY_FACTUAL,
    }
    note = ("Merged per-species knowledge: curated content, NCWRC profile facts, "
            "and a habitat envelope computed from USGS reach attributes. Mixed "
            "at field level — see fields.rules; the envelope numbers are "
            "federal, the sentence describing how they were derived is not. "
            "linked_reports names agency-media PDFs but embeds none.")
    combined = "species-knowledge/all-species-knowledge.json"
    return {
        "species-knowledge/curated/": {
            "tiers": [CURATED], "role": ARCHIVE,
            "note": "Hand-authored input, not generated: bait rankings, rigs, "
                    "seasonal patterns, habitat scoring weights. Read at build "
                    "time; nothing downstream opens it."},
        combined: {
            "tiers": [CURATED, AGENCY_FACTUAL, FEDERAL], "role": QUERY,
            "fields": {"records": "map", "rules": rules, "sample": sample},
            "note": note},
        "species-knowledge/kb/": {
            "tiers": [CURATED, AGENCY_FACTUAL, FEDERAL], "role": QUERY,
            "derived_from": [combined],
            # one file per species, each file a single record
            "fields": {"records": "object", "rules": rules, "sample": sample},
            "note": note + " One file per species — the same records as "
                           "all-species-knowledge.json, split for direct "
                           "lookup, and read that way by consumers."},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    a = ap.parse_args()

    BASE = _common.resolve_out(a.out)
    CUR = os.path.join(BASE, "species-knowledge", "curated")
    OUT = os.path.join(BASE, "species-knowledge")
    print(f"Dataset -> {BASE}", flush=True)

    os.makedirs(os.path.join(OUT, "kb"), exist_ok=True)
    sites = json.load(open(os.path.join(BASE, "fishing-areas", "all-locations.json")))
    enr = json.load(open(os.path.join(BASE, "fishing-areas", "enrichment.json")))
    profiles = profile_index(
        json.load(open(os.path.join(BASE, "species", "all-species.json"))))
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
    renamed = {}
    for slug, (cur, srcfile) in sorted(curated.items()):
        prof = profiles.get(slug, {})
        # a curated key may still carry NCWRC's URL de-dup suffix; the KB is the
        # public face of a species, so publish the canonical slug and keep the
        # curated key as an alias.
        canon = canonical_slug(slug, (set(curated) - {slug}) | set(kb))
        if canon != slug:
            renamed[slug] = canon
        n, env = envelope(sites, enr, cur["match"])
        kb[canon] = {
            "slug": canon,
            "name": prof.get("name", canon.replace("-", " ").title()),
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
        aliases = sorted({s for s in (slug, prof.get("source_slug")) if s and s != canon})
        if aliases:
            kb[canon]["aliases"] = aliases
        with open(os.path.join(OUT, "kb", f"{canon}.json"), "w") as f:
            json.dump(kb[canon], f, indent=2)

    keep = {f"{s}.json" for s in kb}
    for f in os.listdir(os.path.join(OUT, "kb")):        # drop stale files
        if f.endswith(".json") and f not in keep:
            os.remove(os.path.join(OUT, "kb", f))

    with open(os.path.join(OUT, "all-species-knowledge.json"), "w") as f:
        json.dump(kb, f, indent=2)

    # the real records go to the manifest, which checks that every field
    # written this run resolves to a provenance tier
    _common.record_artifacts(BASE, "build_species_kb.py",
                             artifact_tiers(sample=list(kb.values())),
                             run={"species": len(kb),
                                  "canonicalised_slugs": renamed})

    if renamed:
        print(f"Canonicalised {len(renamed)} curated slug(s): {renamed} "
              f"(rename the curated key to make this a no-op)")
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
