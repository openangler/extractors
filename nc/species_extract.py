#!/usr/bin/env python3
"""
species_extract.py — download the NCWRC fish species database + linked research.

For every NC fish species profile on ncwildlife.gov (/species/<slug>) this pulls:
  * a structured profile: overview/biology, habitat, regulations,
    FISHING TIPS (bait), PLACES TO FISH (where), management
  * every linked NCWRC document (/media/N/download): one-page fact sheets and
    Inland Fisheries research reports (river surveys, population assessments)

Output -> <out>/species/
    profiles/<slug>.json      one structured profile each
    all-species.json          combined
    reports/<filename>.pdf     downloaded fact sheets & research reports
    reports/index.json         media-id -> filename/size/referencing species

    python3 species_extract.py --out /data/nc-fishing-guide-data
"""

import argparse
import html
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, AGENCY_MEDIA, ARCHIVE, MEDIA, QUERY

SITE = "https://www.ncwildlife.gov"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) nc-fishing-extract/1.0"

# section labels (found as <h2>/<h3>/<strong>, so nav <a> links never match)
LABEL_RE = re.compile(
    r'(?is)<(?:strong|h2|h3|h4)[^>]*>\s*'
    r'(Overview|Identifying[^<:]*|Range[^<:]*|Habitat|Biology|Food Habits|'
    r'Feeding[^<:]*|Regulations|Fishing Tips|Places to Fish|Management)'
    r'\s*:?\s*</(?:strong|h2|h3|h4)>')
FOOTER_RE = re.compile(r'(?is)<h2[^>]*>\s*(Related Topics|Work With Us)')


def _canon(label):
    l = label.lower()
    if l.startswith("fishing tips"):
        return "fishing_tips"
    if l.startswith("places to fish"):
        return "places_to_fish"
    if l.startswith("regulations"):
        return "regulations"
    if l.startswith("management"):
        return "management"
    return "overview"          # overview/identifying/range/habitat/biology/feeding


def get(url, binary=False, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                info = r.headers.get("Content-Disposition", "")
                data = r.read()
            return (data, info) if binary else data.decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def clean(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def parse_profile(slug, raw):
    m = re.search(r'(?is)<h1[^>]*>(.*?)</h1>', raw)
    name = clean(m.group(1)) if m else slug

    # content region: after the species <h1> up to the site footer
    start = m.end() if m else 0
    fm = FOOTER_RE.search(raw, start)
    content = raw[start:fm.start()] if fm else raw[start:]

    # find every section label (heading/strong), slice text between them
    hits = [(mm.start(), _canon(mm.group(1)), mm.end())
            for mm in LABEL_RE.finditer(content)]
    sections = {}
    for k, (pos, key, hend) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(content)
        seg = clean(content[hend:end])
        if len(seg) < 3:
            continue
        sections[key] = (sections.get(key, "") + " " + seg).strip()[:4000]

    media = sorted(set(re.findall(r'/media/(\d+)/download', raw)))
    internal = sorted(set(re.findall(r'https?://192\.168[^"]+\.pdf[^"]*', raw)))
    return {"slug": slug, "name": name, "url": f"{SITE}/species/{slug}",
            **sections, "media_ids": media, "internal_doc_links": internal}


SUFFIX_RE = re.compile(r"-\d+$")


def canonical_slug(slug, taken=()):
    """Drop NCWRC's URL de-dup suffix: 'largemouth-bass-0' -> 'largemouth-bass'.

    The suffix is an artefact of how NCWRC numbers duplicate URL paths, not part
    of the species' identity. Keeps the raw slug when the canonical form is
    already claimed by a different species, so two profiles never collide.
    """
    base = SUFFIX_RE.sub("", slug)
    if not base or base == slug:
        return slug
    return slug if base in taken else base


def canonicalise(profiles):
    """Rewrite each profile's slug to its canonical form.

    The raw NCWRC URL stays in `url`; the raw slug is kept in `source_slug` and
    listed in `aliases` so old /species/<slug> links stay resolvable.
    """
    raw_slugs = {p["slug"] for p in profiles}
    assigned, out = set(), []
    for p in sorted(profiles, key=lambda p: p["slug"]):
        raw = p["slug"]
        canon = canonical_slug(raw, (raw_slugs - {raw}) | assigned)
        assigned.add(canon)
        p = dict(p)
        p["slug"] = canon
        if canon != raw:
            p["source_slug"] = raw
            p["aliases"] = [raw]
        out.append(p)
    return sorted(out, key=lambda p: p["slug"])


def artifact_tiers():
    """Provenance tier and role for every artifact this script writes."""
    facts = ("Species facts scraped from NCWRC profile pages (habitat, "
             "regulations, bait tips, places to fish).")
    return {
        "species/all-species.json": {
            "tiers": [AGENCY_FACTUAL], "role": QUERY, "note": facts},
        "species/profiles/": {
            "tiers": [AGENCY_FACTUAL], "role": ARCHIVE,
            "derived_from": ["species/all-species.json"],
            "note": facts + " One file per species; the same records as "
                    "all-species.json, split for direct lookup."},
        "species/reports/": {
            "tiers": [AGENCY_MEDIA], "role": MEDIA,
            "note": "NCWRC fact sheets and Inland Fisheries research reports "
                    "(PDFs) — creative works, not facts. Drop this tier for a "
                    "redistributable or offline subset. Facts extracted out of "
                    "these documents become agency-factual; the PDFs do not."},
        "species/reports/index.json": {
            "tiers": [AGENCY_FACTUAL], "role": QUERY,
            "note": "Listing only (media id -> filename/size/species). Describes "
                    "the agency-media PDFs; contains none of them, and stays "
                    "useful in a media-free bundle because the knowledge base "
                    "links to reports by media id."},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    ap.add_argument("--species-list", metavar="FILE", default="/tmp/species_all.txt",
                    help="file of NCWRC /species/<slug> URLs or slugs, one per "
                         "line (default: /tmp/species_all.txt)")
    args = ap.parse_args()
    BASE = _common.resolve_out(args.out)
    OUT = os.path.join(BASE, "species")
    print(f"Output -> {OUT}", flush=True)

    os.makedirs(os.path.join(OUT, "profiles"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "reports"), exist_ok=True)

    slugs = sorted({l.strip().split("/species/")[-1]
                    for l in open(args.species_list) if l.strip()})
    print(f"[1/3] Parsing {len(slugs)} species profiles ...", flush=True)

    def do(slug):
        try:
            raw = get(f"{SITE}/species/{slug}")
            return parse_profile(slug, raw)
        except Exception as e:
            return {"slug": slug, "_error": str(e)}

    profiles = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(do, s) for s in slugs]):
            profiles.append(fut.result())

    # dedupe by species name; keep the richest (tips + places + reports)
    def richness(p):
        return (len(p.get("fishing_tips", "")) + len(p.get("places_to_fish", ""))
                + 200 * len(p.get("media_ids", [])) + len(p.get("overview", "")))
    best = {}
    for p in profiles:
        key = (p.get("name") or p["slug"]).lower()
        if key not in best or richness(p) > richness(best[key]):
            best[key] = p
    profiles = canonicalise(best.values())
    keep = {p["slug"] for p in profiles}
    for f in os.listdir(os.path.join(OUT, "profiles")):          # drop stale files
        if f.endswith(".json") and f[:-5] not in keep:
            os.remove(os.path.join(OUT, "profiles", f))
    for p in profiles:
        with open(os.path.join(OUT, "profiles", f'{p["slug"]}.json'), "w") as f:
            json.dump(p, f, indent=2)
    with open(os.path.join(OUT, "all-species.json"), "w") as f:
        json.dump(profiles, f, indent=2)
    ok = [p for p in profiles if "_error" not in p]
    print(f"      parsed {len(ok)}/{len(profiles)} "
          f"({sum('fishing_tips' in p for p in ok)} with bait tips)", flush=True)

    # collect media ids -> which species reference them
    ref = {}
    for p in ok:
        for mid in p.get("media_ids", []):
            ref.setdefault(mid, []).append(p["slug"])
    print(f"[2/3] Downloading {len(ref)} linked documents (fact sheets + reports) ...",
          flush=True)

    index = {}

    idx_path = os.path.join(OUT, "reports", "index.json")
    prev = json.load(open(idx_path)) if os.path.exists(idx_path) else {}

    def fetch_media(mid):
        try:
            # skip re-download if a prior run already saved this media id's file
            pm = prev.get(mid)
            if pm and "filename" in pm:
                fp = os.path.join(OUT, "reports", pm["filename"])
                if os.path.exists(fp) and os.path.getsize(fp) > 0:
                    return mid, {"filename": pm["filename"],
                                 "bytes": os.path.getsize(fp),
                                 "species": ref[mid], "cached": True}
            data, disp = get(f"{SITE}/media/{mid}/download", binary=True)
            m = re.search(r'filename="?([^"]+\.pdf)"?', disp, re.I)
            fname = m.group(1) if m else f"media-{mid}.pdf"
            fname = re.sub(r'[^A-Za-z0-9._-]+', '-', fname)
            path = os.path.join(OUT, "reports", fname)
            with open(path, "wb") as f:
                f.write(data)
            return mid, {"filename": fname, "bytes": len(data),
                         "species": ref[mid]}
        except Exception as e:
            return mid, {"error": str(e), "species": ref[mid]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        for fut in as_completed([ex.submit(fetch_media, m) for m in ref]):
            mid, meta = fut.result()
            index[mid] = meta
    with open(os.path.join(OUT, "reports", "index.json"), "w") as f:
        json.dump(index, f, indent=2)
    good = [v for v in index.values() if "error" not in v]
    print(f"      downloaded {len(good)}/{len(index)} PDFs "
          f"({sum(v.get('bytes',0) for v in good)//1024} KB)", flush=True)

    renamed = {p["source_slug"]: p["slug"] for p in profiles if "source_slug" in p}
    if renamed:
        print(f"      canonicalised {len(renamed)} slug(s): {renamed}", flush=True)
    _common.record_artifacts(BASE, "species_extract.py", artifact_tiers(),
                             run={"species": len(profiles),
                                  "documents": len(index),
                                  "canonicalised_slugs": renamed})

    print("[3/3] Done.", flush=True)
    print("Sample — flathead-catfish bait tips:", flush=True)
    fh = next((p for p in ok if p["slug"] == "flathead-catfish"), None)
    if fh:
        print("  ", fh.get("fishing_tips", "")[:200], flush=True)


if __name__ == "__main__":
    main()
