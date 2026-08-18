#!/usr/bin/env python3
"""
extract_bait_shops.py — bait & tackle shops from OpenStreetMap (Overpass API).

No agency publishes a bait-shop directory, so this layer is community-mapped
data rather than agency data: `shop=fishing` / `shop=bait`, a couple of narrow
secondary signals, and bait vending machines (the only thing reliably open at
4 a.m.). See SELECTORS for exactly what is asked for and REJECTED for what is
deliberately not.

Two things this layer is honest about, because a wrong answer sends someone to
a closed gas station before dawn:

  * **Coverage, not a directory.** The file records the bbox it queried.
    Nothing inside that box means OSM has none mapped there; anything outside
    it is not covered at all. Rural NC is thin either way.
  * **Hours are unknown, never closed.** OSM's `opening_hours` is the field
    that matters most and the one it carries least often. Every shop gets a
    `hours.known` flag; a missing value is never rendered as "closed".

Licence: OpenStreetMap is **ODbL 1.0 — share-alike, not non-commercial**.
Displaying these shops is a Produced Work needing attribution only;
redistributing this file or a database derived from it is a Derivative Database
and carries the share-alike obligation. The output carries the attribution and
the licence terms so a consumer never has to guess (see LICENSE_BLOCK).

Output -> bait-shops/shops.json     (attribution + coverage + the shops)
       -> bait-shops/summary.json   (counts, incl. how many have usable hours)

    python3 extract_bait_shops.py --dry-run          # print the query, no network
    python3 extract_bait_shops.py                    # whole of NC
    python3 extract_bait_shops.py --bbox 35.45,-80.65,36.0,-79.95   # High Rock
    python3 extract_bait_shops.py --out /data/nc-fishing-guide-data
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import _common
from _common import CURATED, QUERY

# ---- a tier for community-contributed open data --------------------------------
#
# ADR-0007 names five tiers and OSM is none of them: not `federal-public-domain`
# (not a federal work), not `agency-factual` (OSM is not an agency — its content
# is contributed by volunteers and licensed, not published by a government), not
# `curated-original` (we did not author it). Nor is the difference cosmetic: this
# is the first tier that carries an *obligation* rather than a risk. Attribution
# is mandatory on display, and redistributing a derived database triggers
# share-alike. A consumer filtering on tier has to be able to see that.
#
# The constant belongs in _common.py beside FEDERAL/AGENCY_FACTUAL/CURATED once
# ADR-0007 is amended; it is registered from here so this script can land first.
# setdefault, so the day it moves into _common.py this line becomes a no-op.
COMMUNITY = "community-share-alike"
_common.TIERS.setdefault(COMMUNITY, (
    "Community-contributed open data under a share-alike licence "
    "(OpenStreetMap, ODbL 1.0). Not an agency source and not public domain. "
    "Usable commercially: displaying it is a Produced Work and needs "
    "attribution only. Redistributing it, or a database derived from it, is a "
    "Derivative Database and must itself be offered under ODbL."))

# ---- source --------------------------------------------------------------------

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "openangler-extractors/1.0 (bait-shop layer; +https://github.com/openangler/extractors)"

# North Carolina, south,west,north,east — Overpass bbox order.
NC_BBOX = (33.75, -84.40, 36.62, -75.40)

# What we ask Overpass for. Each selector is a claim a mapper made about the
# place itself; nothing here is inferred from a neighbouring feature.
#
#   primary   — the POI's own main tag says it is a fishing/bait shop.
#   secondary — a different kind of POI carrying an explicit, unambiguous
#               "sells bait" / "sells fishing gear" attribute. Kept, but flagged,
#               because these are the ones most likely to be a counter with three
#               tubs of nightcrawlers rather than a shop.
SELECTORS = (
    'nwr["shop"="fishing"]',                     # documented value: tackle + bait
    'nwr["shop"="bait"]',                        # undocumented but unambiguous
    'nwr["shop"="fishing_tackle"]',              # in-use variant of shop=fishing
    'nwr["amenity"="vending_machine"]["vending"~"bait"]',
    'nwr["bait"="yes"]',                         # secondary, on any POI
    'nwr["shop"="sports"]["sport"~"fishing"]',   # secondary, a tackle specialist
)

# Deliberately NOT queried. Recorded here because the omissions are the whole
# design: every one of these would generate the 4 a.m. false positive.
REJECTED = {
    "fishing=yes": "on a marina, pier or lake this means fishing is *permitted*, "
                   "not that bait is sold — the single largest false-positive "
                   "source in OSM for this layer",
    "shop=convenience": "a gas station near a lake is not evidence it sells bait; "
                        "it needs bait=yes on the POI itself, which is queried",
    "leisure=marina": "a marina is not a bait shop unless tagged as selling bait",
    "shop=outdoor / shop=hunting": "outfitters and gun shops are not bait shops "
                                   "without an explicit fishing attribute",
    "disused:/abandoned:/was: lifecycle prefixes":
        "a dead shop is retagged onto a prefixed key, which is a different key, "
        "so it never matches any selector above — nothing to exclude. What does "
        "have to be excluded is a live tag alongside disused=yes; DEAD does that",
}

# A shop that matched a selector but is flagged shut. Note this is *not* a check
# on lifecycle-prefixed keys: `shop=fishing` + `disused:amenity=fuel` is a bait
# shop in a former gas station, and dropping it would be the false negative.
DEAD = {"disused", "abandoned", "demolished", "removed", "closed", "razed"}

CLASSES = {
    "fishing": ("fishing_tackle_shop", "primary"),
    "bait": ("bait_shop", "primary"),
    "fishing_tackle": ("fishing_tackle_shop", "primary"),
}

# A bait=yes has to sit on something that is actually a place of business.
POI_KEYS = ("shop", "amenity", "leisure", "craft", "tourism")

ATTRIBUTION = ("© OpenStreetMap contributors — https://www.openstreetmap.org/copyright"
               " — data available under the Open Database License (ODbL) 1.0")

LICENSE_BLOCK = {
    "source": "OpenStreetMap, via the Overpass API",
    "source_url": "https://www.openstreetmap.org/copyright",
    "license": "ODbL-1.0",
    "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
    "attribution": ATTRIBUTION,
    "attribution_required": True,
    "share_alike": True,
    "non_commercial": False,
    "note": "Share-alike, NOT non-commercial — materially different from a "
            "CC-BY-NC source. Showing these shops to a user is a Produced Work: "
            "display the attribution string and you are done, commercial or not. "
            "Redistributing this file, or any database built from it, is a "
            "Derivative Database and must itself be offered under ODbL. "
            "Engineering documentation, not legal advice.",
}

HOURS_NOTE = (
    "opening_hours is the field that decides whether a shop is any use at 4 a.m., "
    "and it is the field OSM carries least often. hours.known=false means OSM has "
    "no hours for that shop — it does NOT mean closed, and must never be rendered "
    "as closed. Call ahead, or prefer a shop with hours.open_24_7=true."
)

COVERAGE_NOTE = (
    "This file covers exactly the bbox in coverage.bbox and nothing else. Inside "
    "it, no shop means none is mapped in OpenStreetMap — not that none exists; "
    "OSM coverage of rural North Carolina is thin, and this layer is a seed, not "
    "a directory. Outside it, this file says nothing at all: absence there is "
    "absence of data, not absence of shops. Expect to layer local corrections on "
    "top."
)


# ---- Overpass ------------------------------------------------------------------


def overpass_query(bbox, timeout=180):
    """The QL for one bbox. One request, all selectors — Overpass is donated."""
    box = ",".join(f"{v:g}" for v in bbox)
    clauses = "\n".join(f"  {sel}({box});" for sel in SELECTORS)
    return f"[out:json][timeout:{timeout}];\n(\n{clauses}\n);\nout center meta;"


def fetch(query, endpoint=OVERPASS, tries=3):
    """POST one query. Backs off on the rate-limit/overload codes Overpass uses.

    A free, donated, shared service: 429 (slot exhausted) and 504 (gateway
    timeout under load) are answers, not errors, so wait rather than hammer.
    """
    data = urllib.parse.urlencode({"data": query}).encode()
    for i in range(tries):
        req = urllib.request.Request(endpoint, data=data,
                                     headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 504) or i == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 30 * (i + 1)
            print(f"  Overpass {e.code}; backing off {wait}s "
                  f"(attempt {i + 1}/{tries})", flush=True)
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            wait = 30 * (i + 1)
            print(f"  Overpass unreachable; retrying in {wait}s", flush=True)
        time.sleep(wait)


# ---- element -> record ---------------------------------------------------------


def _multi(value):
    """OSM packs multiple values into one tag with ';'."""
    return [p.strip() for p in (value or "").split(";") if p.strip()]


def classify(tags):
    """(class, confidence, matched tags) for an element, or None to drop it.

    Only the element's own tags are consulted. Anything that does not assert
    "this place sells bait or fishing gear" is dropped, however close it sits to
    water.
    """
    shop = tags.get("shop")
    if shop in CLASSES:
        cls, conf = CLASSES[shop]
        return cls, conf, {"shop": shop}
    if tags.get("amenity") == "vending_machine":
        vending = [v for v in _multi(tags.get("vending")) if "bait" in v]
        if vending:
            # Unstaffed, so it is the one class whose hours are usually real.
            return "bait_vending_machine", "primary", {
                "amenity": "vending_machine", "vending": ";".join(vending)}
    if tags.get("bait") == "yes" and any(k in tags for k in POI_KEYS):
        return "sells_bait", "secondary", {"bait": "yes", **{
            k: tags[k] for k in POI_KEYS if k in tags}}
    if shop == "sports" and "fishing" in _multi(tags.get("sport")):
        return "tackle_at_sports_shop", "secondary", {"shop": "sports",
                                                      "sport": tags["sport"]}
    return None


def _address(tags):
    house = " ".join(t for t in (tags.get("addr:housenumber"),
                                 tags.get("addr:street")) if t)
    tail = " ".join(t for t in (tags.get("addr:state"),
                                tags.get("addr:postcode")) if t)
    parts = [p for p in (house, tags.get("addr:city"), tail) if p]
    return ", ".join(parts) or None


def _hours(tags):
    """Hours, with 'we do not know' stated rather than implied.

    `seasonal` rides along because it is the other way a shop is shut when you
    get there: the first real record this extractor pulled was a lake-park bait
    shop tagged seasonal=summer.
    """
    raw = (tags.get("opening_hours") or "").strip()
    hours = {"opening_hours": raw or None,
             "known": bool(raw) and raw.lower() not in ("unknown", "?"),
             "open_24_7": raw == "24/7",
             "seasonal": tags.get("seasonal")}
    if not hours["known"]:
        hours["opening_hours"] = None
    return hours


def shop_record(element):
    """One Overpass element -> one shop record, or None if it is not one.

    Records the *tags that matched* so a consumer can second-guess the call, and
    the last-edit date so it can weigh a 2013 node against a 2025 one.
    """
    tags = element.get("tags") or {}
    if (tags.get("disused") == "yes" or tags.get("abandoned") == "yes"
            or tags.get("shop") == "vacant"
            or (tags.get("operational_status") or "").lower() in DEAD):
        return None
    hit = classify(tags)
    if not hit:
        return None
    cls, confidence, matched = hit
    center = element.get("center") or element
    lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None                      # geometry-less element: not placeable
    otype, oid = element.get("type"), element.get("id")
    return {
        "osm_id": f"{otype}/{oid}",
        "osm_url": f"https://www.openstreetmap.org/{otype}/{oid}",
        "name": tags.get("name") or tags.get("operator") or tags.get("brand"),
        "class": cls,
        "confidence": confidence,
        "matched_tags": matched,
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "address": _address(tags),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "website": tags.get("website") or tags.get("contact:website"),
        "hours": _hours(tags),
        # Staleness, not provenance: OSM records who last touched an element,
        # but a mapper's username is personal data and no use here, so only the
        # date is kept.
        "last_edited": (element.get("timestamp") or "")[:10] or None,
        "last_checked": tags.get("check_date") or tags.get("survey:date"),
    }


def records_from(payload):
    """Every shop in an Overpass response, deduped by OSM id, name-sorted."""
    seen = {}
    for element in payload.get("elements") or []:
        rec = shop_record(element)
        if rec and rec["osm_id"] not in seen:
            seen[rec["osm_id"]] = rec
    return sorted(seen.values(), key=lambda r: ((r["name"] or "~").lower(),
                                                r["osm_id"]))


def osm_base_timestamp(payload):
    """When OSM's data was last applied to the Overpass instance we asked."""
    return (payload.get("osm3s") or {}).get("timestamp_osm_base")


def summarize(records, bbox, elements):
    """Counts, led by the three fields that decide whether this layer is useful."""
    with_hours = sum(1 for r in records if r["hours"]["known"])
    return {
        "source": "OpenStreetMap via Overpass API",
        "license": "ODbL-1.0",
        "attribution": ATTRIBUTION,
        "bbox": list(bbox),
        "elements_returned": elements,
        "shops": len(records),
        "by_class": dict(Counter(r["class"] for r in records)),
        "by_confidence": dict(Counter(r["confidence"] for r in records)),
        "with_opening_hours": with_hours,
        "hours_unknown": len(records) - with_hours,
        "open_24_7": sum(1 for r in records if r["hours"]["open_24_7"]),
        "with_phone": sum(1 for r in records if r["phone"]),
        "with_website": sum(1 for r in records if r["website"]),
        "with_address": sum(1 for r in records if r["address"]),
        "seasonal": sum(1 for r in records if r["hours"]["seasonal"]),
        "edited_before_2021": sum(1 for r in records
                                  if (r["last_edited"] or "9999") < "2021"),
    }


def document(records, bbox, elements, stamp, osm_base=None):
    """shops.json: the attribution and the coverage caveat travel with the data.

    A bare list would let both get lost the first time a consumer copies the
    file, and ODbL attribution is not optional.
    """
    return {
        "attribution": ATTRIBUTION,
        "license": dict(LICENSE_BLOCK),
        "coverage": {
            "bbox": {"south": bbox[0], "west": bbox[1],
                     "north": bbox[2], "east": bbox[3]},
            "queried": stamp,
            "osm_data_timestamp": osm_base,
            "elements_returned": elements,
            "shops": len(records),
            "selectors": list(SELECTORS),
            "not_queried": dict(REJECTED),
            "note": COVERAGE_NOTE,
        },
        "hours_note": HOURS_NOTE,
        "shops": records,
    }


def artifact_tiers(sample=None):
    """Provenance tier and role for every artifact this script writes."""
    return {
        "bait-shops/shops.json": {
            "tiers": [COMMUNITY, CURATED], "role": QUERY,
            "fields": {
                "records": "object",
                # Default is the OSM tier on purpose: a field added later and
                # left untagged keeps the attribution and share-alike
                # obligations attached. Losing them is the expensive mistake;
                # over-attributing our own sentence is not.
                "default": COMMUNITY,
                "rules": {
                    "shops": COMMUNITY,
                    "attribution": COMMUNITY,
                    "license": COMMUNITY,
                    # written here, not by OSM
                    "license.note": CURATED,
                    "hours_note": CURATED,
                    "coverage": CURATED,
                },
                "sample": sample},
            "note": "Bait & tackle shops from OpenStreetMap (ODbL 1.0). Shop "
                    "records are OSM's; the coverage caveat, the hours caveat "
                    "and the plain-language licence note are written by this "
                    "script. Attribution is required wherever these are shown."},
        "bait-shops/summary.json": {
            "tiers": [COMMUNITY], "role": QUERY,
            "derived_from": ["bait-shops/shops.json"],
            "note": "Counts over the OSM shop records, including how many carry "
                    "usable opening hours. Aggregates of an ODbL database are "
                    "still a derived database."},
    }


def parse_bbox(text):
    """--bbox S,W,N,E — Overpass order, so the query is the argument."""
    parts = text.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox needs 4 values: S,W,N,E")
    try:
        s, w, n, e = (float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("bbox values must be numbers")
    if not (s < n and w < e):
        raise argparse.ArgumentTypeError(
            f"bbox must be south,west,north,east — got south={s} north={n}, "
            f"west={w} east={e}")
    return (s, w, n, e)


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    ap.add_argument("--bbox", type=parse_bbox, default=NC_BBOX,
                    metavar="S,W,N,E",
                    help="area to query, Overpass order (default: all of NC, "
                         f"{','.join(str(v) for v in NC_BBOX)})")
    ap.add_argument("--endpoint", default=OVERPASS,
                    help=f"Overpass instance (default: {OVERPASS})")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the Overpass query and exit, without querying")
    a = ap.parse_args()

    query = overpass_query(a.bbox)
    if a.dry_run:
        print(query)
        return

    BASE = _common.resolve_out(a.out)
    OUT = os.path.join(BASE, "bait-shops")
    print(f"Dataset -> {BASE}", flush=True)
    print(f"Querying {a.endpoint} for bbox {a.bbox} ...", flush=True)

    payload = fetch(query, a.endpoint)
    elements = len(payload.get("elements") or [])
    records = records_from(payload)
    print(f"  {elements} elements -> {len(records)} shops "
          f"({elements - len(records)} dropped: no geometry, lifecycle-tagged, "
          f"or not a bait/tackle POI).", flush=True)

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc = document(records, a.bbox, elements, stamp, osm_base_timestamp(payload))
    summary = summarize(records, a.bbox, elements)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "shops.json"), "w") as f:
        json.dump(doc, f, indent=2)
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    _common.record_artifacts(BASE, "extract_bait_shops.py",
                             artifact_tiers(sample=doc), run=summary)

    print("Done ->", os.path.join(OUT, "shops.json"))
    print(json.dumps(summary, indent=2))
    print(f"\n{summary['with_opening_hours']}/{len(records)} shops have opening "
          f"hours; the other {summary['hours_unknown']} are UNKNOWN, not closed.",
          flush=True)
    print(ATTRIBUTION, flush=True)


if __name__ == "__main__":
    main()
