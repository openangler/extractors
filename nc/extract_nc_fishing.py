#!/usr/bin/env python3
"""
NC Wildlife Resources Commission (NCWRC) Fishing Areas + Trout Waters extractor.

Source: https://www.ncpaws.org/ncwrcmaps/fishingareas  (public NCWRC map app)

Pulls every fishing-area marker with full detail (amenities, species, management,
photo), downloads site photos, and downloads the ArcGIS map layers behind the app
(trout waters, game lands, county boundaries, etc.). Everything is organized by NC
region (Mountains / Piedmont / Coastal Plain) for a local NC-fishing AI agent.

All endpoints are public. No auth required.
"""

import argparse
import csv
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, AGENCY_MEDIA, ARCHIVE, GEOMETRY, MEDIA, QUERY

BASE = "https://www.ncpaws.org/NCWRCMaps/FishingAreas/Home"
AGOL = "https://services1.arcgis.com/YfqBAUM5nWR3yhGP/arcgis/rest/services"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) fishing-data-extract/1.0"

# ---- NC county -> region (all 100 counties) -----------------------------------
MOUNTAINS = {
    "Alleghany","Ashe","Avery","Buncombe","Burke","Caldwell","Cherokee","Clay",
    "Graham","Haywood","Henderson","Jackson","Macon","Madison","McDowell",
    "Mitchell","Polk","Rutherford","Swain","Transylvania","Watauga","Wilkes","Yancey",
}
PIEDMONT = {
    "Alamance","Alexander","Anson","Cabarrus","Caswell","Catawba","Chatham","Cleveland",
    "Davidson","Davie","Durham","Forsyth","Franklin","Gaston","Granville","Guilford",
    "Iredell","Lincoln","Mecklenburg","Montgomery","Moore","Orange","Person","Randolph",
    "Rockingham","Rowan","Stanly","Stokes","Surry","Union","Vance","Wake","Warren","Yadkin",
}
COASTAL = {
    "Beaufort","Bertie","Bladen","Brunswick","Camden","Carteret","Chowan","Columbus",
    "Craven","Cumberland","Currituck","Dare","Duplin","Edgecombe","Gates","Greene",
    "Halifax","Harnett","Hertford","Hoke","Hyde","Johnston","Jones","Lee","Lenoir",
    "Martin","Nash","New Hanover","Northampton","Onslow","Pamlico","Pasquotank","Pender",
    "Perquimans","Pitt","Richmond","Robeson","Sampson","Scotland","Tyrrell","Wayne",
    "Wilson","Washington",
}
REGION_DIR = {"Mountains": "mountains", "Piedmont": "piedmont",
              "Coastal Plain": "coastal-plain", "Unknown": "unknown-region"}
LOCATION_TYPES = {1: "Boating Access Area (BAA)", 3: "Public Fishing Area (PFA)",
                  7: "Non-WRC / Partner site"}


def region_for(county):
    if not county:
        return "Unknown"
    c = county.strip().title().replace("Mcdowell", "McDowell")
    if c in MOUNTAINS: return "Mountains"
    if c in PIEDMONT: return "Piedmont"
    if c in COASTAL: return "Coastal Plain"
    return "Unknown"


def get(url, tries=4, binary=False):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else data.decode("utf-8")
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "site"


def clean_dms(s):
    if not s:
        return s
    repl = {"&deg;": "°", "&nbsp;": " ", "&rsquo;": "'", "&rdquo;": '"',
            "&lsquo;": "'", "&ldquo;": '"', "&#39;": "'"}
    for k, v in repl.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def artifact_tiers(counts, layers, dl_photos):
    """Provenance tier and role for every artifact this script writes."""
    facts = "NCWRC fishing-area facts (coordinates, amenities, species, management)."
    all_locations = "fishing-areas/all-locations.json"
    arts = {
        "raw/all-fishing-areas.json": {
            "tiers": [AGENCY_FACTUAL], "role": ARCHIVE,
            "note": "Untouched NCWRC master marker list, kept so a run can be "
                    "audited against its source. Everything in it is also in "
                    + all_locations + "."},
        all_locations: {
            "tiers": [AGENCY_FACTUAL], "role": QUERY,
            "note": facts + " locationPhotoID references an agency-media photo "
                    "but the file contains no media. Sites matched to a PFA/BAA "
                    "feature service also carry a `facilities` block (amenities, "
                    "pier counts, Access_Notes) joined from that service by name "
                    "and proximity — see `_source` and `_match_km` inside it."},
    }
    for region in sorted(counts):
        d = REGION_DIR[region]
        # Regional splits and the CSV are convenience views of all-locations.json:
        # no content of their own, so a minimal bundle can leave them out.
        arts[f"fishing-areas/{d}/locations.json"] = {
            "tiers": [AGENCY_FACTUAL], "role": ARCHIVE,
            "derived_from": [all_locations],
            "note": facts + f" The {region} partition of " + all_locations + "."}
        arts[f"fishing-areas/{d}/locations.csv"] = {
            "tiers": [AGENCY_FACTUAL], "role": ARCHIVE,
            "derived_from": [all_locations],
            "note": facts + " Flat one-row-per-site view."}
        if dl_photos:
            arts[f"fishing-areas/{d}/photos/"] = {
                "tiers": [AGENCY_MEDIA], "role": MEDIA,
                "note": "NCWRC site photographs — creative works, not facts. "
                        "Drop this tier for a redistributable or offline subset."}
    for relpath in layers:
        arts[relpath] = {
            "tiers": [AGENCY_FACTUAL], "role": GEOMETRY,
            "note": "NCWRC ArcGIS map layer: public geometry and attributes. "
                    "Factual, and still the bulk of a media-free dataset — "
                    "needed to draw a map, not to answer a query."}
    return arts


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    ap.add_argument("--no-photos", action="store_true",
                    help="skip downloading site photos (the agency-media tier)")
    args = ap.parse_args()
    OUT = _common.resolve_out(args.out)
    DL_PHOTOS = not args.no_photos
    print(f"Output -> {OUT}", flush=True)

    os.makedirs(OUT, exist_ok=True)
    raw_dir = os.path.join(OUT, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # 1) master list of all fishing areas ---------------------------------------
    print("[1/6] Fetching master fishing-area list ...", flush=True)
    master = json.loads(get(f"{BASE}/GetFilteredFishingAreas"))
    with open(os.path.join(raw_dir, "all-fishing-areas.json"), "w") as f:
        json.dump(master, f, indent=2)
    print(f"      {len(master)} fishing areas.", flush=True)

    # 2) detail for each location (threaded) ------------------------------------
    print("[2/6] Fetching per-location detail ...", flush=True)

    def fetch_detail(item):
        lid = item["locationID"]
        try:
            d = json.loads(get(f"{BASE}/GetFishingAreaInfo?locationID={lid}"))
        except Exception as e:
            return lid, {"_error": str(e)}
        d["locationID"] = lid              # API returns 0 here; restore canonical id
        d["locationTypeName"] = LOCATION_TYPES.get(d.get("locationTypeID"), "Other")
        d["latitudeDMSString"] = clean_dms(d.get("latitudeDMSString"))
        d["longitudeDMSString"] = clean_dms(d.get("longitudeDMSString"))
        d["region"] = region_for(d.get("county"))
        for k in ("locationName", "latitude", "longitude"):
            d[k] = item.get(k, d.get(k))
        d["waterbodyName"] = item.get("waterbodyName") or d.get("waterbodyName")
        d["operatedBy"] = item.get("operatedBy")
        return lid, d

    details = {}
    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fetch_detail, it): it for it in master}
        for fut in as_completed(futs):
            lid, d = fut.result()
            details[lid] = d
            done += 1
            if done % 100 == 0 or done == len(master):
                print(f"      {done}/{len(master)}", flush=True)

    errors = [l for l, d in details.items() if "_error" in d]
    if errors:
        print(f"      WARNING: {len(errors)} detail errors: {errors[:10]}", flush=True)

    # 3) group by region, write JSON + CSV --------------------------------------
    print("[3/6] Writing per-region JSON + CSV ...", flush=True)
    by_region = {}
    for it in master:
        d = details.get(it["locationID"], {})
        by_region.setdefault(d.get("region", "Unknown"), []).append(d)

    csv_cols = ["locationID", "locationName", "region", "county", "waterbodyName",
                "locationTypeName", "latitude", "longitude", "wrcSite",
                "shorelineAccess", "boatRamp", "canoeAccess", "fishingPierAccess",
                "wheelchairAccessible", "troutStocked", "warmWaterFishStocked",
                "management", "ownerName", "operatedBy", "locationPhotoID"]

    counts = {}
    for region, recs in by_region.items():
        recs.sort(key=lambda r: (r.get("county") or "", r.get("locationName") or ""))
        rdir = os.path.join(OUT, "fishing-areas", REGION_DIR[region])
        os.makedirs(rdir, exist_ok=True)
        with open(os.path.join(rdir, "locations.json"), "w") as f:
            json.dump(recs, f, indent=2)
        with open(os.path.join(rdir, "locations.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
            w.writeheader()
            for r in recs:
                w.writerow(r)
        counts[region] = len(recs)
        print(f"      {region}: {len(recs)} sites", flush=True)

    # combined file (everything) for easy RAG ingestion
    all_recs = [details[it["locationID"]] for it in master]
    with open(os.path.join(OUT, "fishing-areas", "all-locations.json"), "w") as f:
        json.dump(all_recs, f, indent=2)

    # 4) photos ------------------------------------------------------------------
    if DL_PHOTOS:
        print("[4/6] Downloading site photos ...", flush=True)
        photo_jobs = []
        for it in master:
            d = details.get(it["locationID"], {})
            pid = d.get("locationPhotoID")
            if pid and "_error" not in d:
                region = d.get("region", "Unknown")
                pdir = os.path.join(OUT, "fishing-areas", REGION_DIR[region], "photos")
                fname = f'{it["locationID"]}_{slug(d.get("locationName"))}.jpg'
                photo_jobs.append((pid, os.path.join(pdir, fname)))

        for _, path in photo_jobs:
            os.makedirs(os.path.dirname(path), exist_ok=True)

        def fetch_photo(job):
            pid, path = job
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return True
            try:
                data = get(f"{BASE}/GetLocationPhoto?locationPhotoID={pid}", binary=True)
                with open(path, "wb") as f:
                    f.write(data)
                return True
            except Exception:
                return False

        ok = 0
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(fetch_photo, j) for j in photo_jobs]
            for i, fut in enumerate(as_completed(futs), 1):
                ok += 1 if fut.result() else 0
                if i % 100 == 0 or i == len(photo_jobs):
                    print(f"      {i}/{len(photo_jobs)} photos", flush=True)
        print(f"      {ok} photos saved.", flush=True)
    else:
        print("[4/6] Skipping photos (--no-photos).", flush=True)

    # 5) ArcGIS map layers -------------------------------------------------------
    print("[5/6] Downloading ArcGIS map layers (GeoJSON) ...", flush=True)
    # NCWRC publishes 158 services on this org. Most are wildlife-division plumbing
    # (Survey123 backends, bird-atlas blocks, deer/CWD grids, prescribed burns); ~27 are
    # plausibly relevant here. These are the ones worth carrying — see
    # openangler/extractors#15 for the ones deliberately skipped and why.
    layers = {
        # Trout waters. 2026 supersedes the 2025/2024 vintages this extractor shipped
        # for its first year; the older names still resolve, so a stale run looks fine
        # and is simply a year behind.
        "trout-waters/pmtw-streams-2026.geojson":
            f"{AGOL}/PMTW_Streams_2026/FeatureServer/0",
        "trout-waters/pmtw-impoundments-2026.geojson":
            f"{AGOL}/PMTW_Impoundments_2026/FeatureServer/0",
        "trout-waters/mountain-heritage-trout-waters-cities.geojson":
            f"{AGOL}/MHTW_Cities/FeatureServer/0",

        # THE ACCESS SERVICES. The map-app JSON scraped in step 2 carries ~27 fields per
        # site; these carry ~50, including amenities that decide whether a site is worth
        # fishing at night (Lighting), whether fish are concentrated (Fish_Feeder, true
        # at only 54 of 261 sites), pier counts and types, and free-text Access_Notes /
        # Caution_Notes. Step 6 joins them onto the per-location records.
        "fishing-areas/pfa-facilities.geojson":
            f"{AGOL}/NCWRC_Public_Fishing_Areas_view/FeatureServer/0",
        "fishing-areas/baa-facilities.geojson":
            f"{AGOL}/NCWRC_Boating_Access_Areas_view/FeatureServer/0",

        "reference-layers/county-boundaries.geojson":
            f"{AGOL}/countyboundaries/FeatureServer/0",
        "reference-layers/game-lands-general.geojson":
            f"{AGOL}/gamelands_general/FeatureServer/21",
        "reference-layers/game-lands-detail.geojson":
            f"{AGOL}/gamelands_detail/FeatureServer/0",
        "reference-layers/fish-attractors.geojson":
            f"{AGOL}/Fish_Attractors_public_view/FeatureServer/0",
        "reference-layers/coastal-joint-waters.geojson":
            f"{AGOL}/CoastJointWatersNC/FeatureServer/0",

        # Dams and barriers, for tailwater generation alerts: a barrier upstream of a
        # reach is what makes its flow schedule-driven rather than weather-driven.
        "reference-layers/aquatic-barriers.geojson":
            f"{AGOL}/AquaticBarriers_wFlow/FeatureServer/0",
        # Hatcheries — where stocked fish physically come from.
        "reference-layers/hatcheries-depots.geojson":
            f"{AGOL}/WRC_Depots_EduCenters_Hatcheries/FeatureServer/0",
        # Navigation hazards worth knowing about before running a boat at night.
        "reference-layers/buoys.geojson":
            f"{AGOL}/BUOYS_view/FeatureServer/0",
        # Game Land Access is multi-sublayer; parking is the one that matters for
        # reaching water on foot.
        "reference-layers/game-land-parking.geojson":
            f"{AGOL}/Game_Land_Access/FeatureServer/1",
    }
    for relpath, svc in layers.items():
        path = os.path.join(OUT, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        feats, offset, page = [], 0, 2000
        while True:
            q = urllib.parse.urlencode({
                "where": "1=1", "outFields": "*", "f": "geojson",
                "resultOffset": offset, "resultRecordCount": page,
                "outSR": "4326",
            })
            try:
                gj = json.loads(get(f"{svc}/query?{q}"))
            except Exception as e:
                print(f"      ERROR {relpath}: {e}", flush=True)
                break
            batch = gj.get("features", [])
            feats.extend(batch)
            if len(batch) < page or not gj.get("exceededTransferLimit"):
                break
            offset += page
        out = {"type": "FeatureCollection", "features": feats}
        with open(path, "w") as f:
            json.dump(out, f)
        print(f"      {relpath}: {len(feats)} features", flush=True)

    # 6) Join facility attributes onto each location -----------------------------
    #
    # The map app (step 2) and the PFA/BAA feature services describe the SAME sites
    # through different doors, and the services carry roughly twice the fields. Without
    # this join the richer half is downloaded and never reaches a consumer, which is how
    # `Fish_Feeder` and `Lighting` stayed invisible for a year.
    #
    # Matched on name + proximity, not on id: the two systems share no key. Names are
    # normalised loosely (the app says "LAKE JULIAN", the service agrees, but casing and
    # punctuation drift elsewhere) and a match must also be within MATCH_KM, so two
    # like-named sites on different waters cannot collide. Anything ambiguous is left
    # unjoined and counted — a missing amenity block is recoverable, a wrong one is not.
    print("[6/6] Joining PFA/BAA facility attributes to locations ...", flush=True)
    MATCH_KM = 1.5
    # The map app appends closure text to a name ("ENO RIVER - CLOSED UNTIL FURTHER
    # NOTICE DUE TO LOW WATER LEVEL CONDITIONS"); the feature services do not. Nine
    # sites, and every one of them fails to match without this.
    STATUS_SUFFIX = re.compile(r"\s+-\s+(closed|temporarily|under|no )\b.*$", re.I)

    def norm(name):
        return re.sub(r"[^a-z0-9]+", " ",
                      STATUS_SUFFIX.sub("", name or "").lower()).strip()

    def km(lat1, lon1, lat2, lon2):
        dlat = (lat2 - lat1) * 111.32
        dlon = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
        return math.hypot(dlat, dlon)

    facilities = []
    for relpath, kind in (("fishing-areas/pfa-facilities.geojson", "PFA"),
                          ("fishing-areas/baa-facilities.geojson", "BAA")):
        path = os.path.join(OUT, relpath)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for feat in json.load(f).get("features", []):
                a = feat.get("properties") or {}
                g = (feat.get("geometry") or {}).get("coordinates") or [None, None]
                name = a.get("PFA_Name") or a.get("BAA_Name") or a.get("Name")
                lat = a.get("Latitude") if a.get("Latitude") is not None else g[1]
                lon = a.get("Longitude") if a.get("Longitude") is not None else g[0]
                if name and lat is not None and lon is not None:
                    facilities.append((kind, norm(name), float(lat), float(lon), a))

    def clean(attrs):
        return {k: v for k, v in attrs.items()
                if v not in (None, "", " ") and k != "OBJECTID"}

    joined = ambiguous = dual = 0
    for rec in master:
        rlat, rlon = rec.get("latitude"), rec.get("longitude")
        if rlat is None or rlon is None:
            continue
        target = norm(rec.get("locationName"))
        hits = [(k, a, km(rlat, rlon, flat, flon))
                for k, fname, flat, flon, a in facilities
                if fname == target and km(rlat, rlon, flat, flon) <= MATCH_KM]
        if not hits:
            continue

        # A site is very often BOTH a public fishing area and a boating access area —
        # 92 of them are. Two hits of DIFFERENT kinds is not ambiguity, it is the same
        # place described by two services, and both halves are wanted. Only two hits of
        # the SAME kind are genuinely undecidable; those are left unjoined and counted,
        # because a missing amenity block is recoverable and a wrong one is not.
        by_kind = {}
        for kind, attrs, dist in hits:
            by_kind.setdefault(kind, []).append((dist, attrs))
        if any(len(v) > 1 for v in by_kind.values()):
            ambiguous += 1
            continue

        block = {}
        for kind in sorted(by_kind):
            dist, attrs = by_kind[kind][0]
            block.update(clean(attrs))
            block[f"_{kind.lower()}_match_km"] = round(dist, 3)
        block["_source"] = "+".join(sorted(by_kind))
        rec["facilities"] = block
        joined += 1
        if len(by_kind) > 1:
            dual += 1

    print(f"      joined {joined}/{len(master)} locations "
          f"({dual} matched both a PFA and a BAA, "
          f"{ambiguous} ambiguous and left unjoined)", flush=True)

    with open(os.path.join(OUT, "fishing-areas", "all-locations.json"), "w") as f:
        json.dump(master, f)

    # summary + provenance manifest
    run = {
        "source": "https://www.ncpaws.org/ncwrcmaps/fishingareas",
        "total_fishing_areas": len(master),
        "detail_errors": len(errors),
        "by_region": counts,
        "photos_downloaded": DL_PHOTOS,
        "map_layers": list(layers.keys()),
        "facility_joins": joined,
        "facility_joins_ambiguous": ambiguous,
        "facility_joins_pfa_and_baa": dual,
    }
    _common.record_artifacts(OUT, "extract_nc_fishing.py",
                             artifact_tiers(counts, layers, DL_PHOTOS), run=run)
    print("\nDONE. Summary:", json.dumps(run, indent=2), flush=True)


if __name__ == "__main__":
    main()
