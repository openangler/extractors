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
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, AGENCY_MEDIA

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
    """Provenance/licence tier for every artifact this script writes."""
    facts = "NCWRC fishing-area facts (coordinates, amenities, species, management)."
    arts = {
        "raw/all-fishing-areas.json": {
            "tiers": [AGENCY_FACTUAL],
            "note": "Untouched NCWRC master marker list."},
        "fishing-areas/all-locations.json": {
            "tiers": [AGENCY_FACTUAL],
            "note": facts + " locationPhotoID references an agency-media photo "
                    "but the file contains no media."},
    }
    for region in sorted(counts):
        d = REGION_DIR[region]
        arts[f"fishing-areas/{d}/locations.json"] = {
            "tiers": [AGENCY_FACTUAL], "note": facts}
        arts[f"fishing-areas/{d}/locations.csv"] = {
            "tiers": [AGENCY_FACTUAL], "note": facts + " Flat one-row-per-site view."}
        if dl_photos:
            arts[f"fishing-areas/{d}/photos/"] = {
                "tiers": [AGENCY_MEDIA],
                "note": "NCWRC site photographs — creative works, not facts. "
                        "Drop this tier for a redistributable or offline subset."}
    for relpath in layers:
        arts[relpath] = {
            "tiers": [AGENCY_FACTUAL],
            "note": "NCWRC ArcGIS map layer: public geometry and attributes."}
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
    print("[1/5] Fetching master fishing-area list ...", flush=True)
    master = json.loads(get(f"{BASE}/GetFilteredFishingAreas"))
    with open(os.path.join(raw_dir, "all-fishing-areas.json"), "w") as f:
        json.dump(master, f, indent=2)
    print(f"      {len(master)} fishing areas.", flush=True)

    # 2) detail for each location (threaded) ------------------------------------
    print("[2/5] Fetching per-location detail ...", flush=True)

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
    print("[3/5] Writing per-region JSON + CSV ...", flush=True)
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
        print("[4/5] Downloading site photos ...", flush=True)
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
        print("[4/5] Skipping photos (--no-photos).", flush=True)

    # 5) ArcGIS map layers -------------------------------------------------------
    print("[5/5] Downloading ArcGIS map layers (GeoJSON) ...", flush=True)
    layers = {
        "trout-waters/pmtw-streams-2025.geojson":
            f"{AGOL}/PMTW_streams_2025/FeatureServer/0",
        "trout-waters/pmtw-impoundments-2024.geojson":
            f"{AGOL}/PMTW_impoundments_2024/FeatureServer/0",
        "trout-waters/mountain-heritage-trout-waters-cities.geojson":
            f"{AGOL}/MHTW_Cities/FeatureServer/0",
        "reference-layers/county-boundaries.geojson":
            f"{AGOL}/countyboundaries/FeatureServer/0",
        "reference-layers/game-lands-general.geojson":
            f"{AGOL}/gamelands_general/FeatureServer/21",
        "reference-layers/fish-attractors.geojson":
            f"{AGOL}/Fish_Attractors_public_view/FeatureServer/0",
        "reference-layers/coastal-joint-waters.geojson":
            f"{AGOL}/CoastJointWatersNC/FeatureServer/0",
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

    # summary + provenance manifest
    run = {
        "source": "https://www.ncpaws.org/ncwrcmaps/fishingareas",
        "total_fishing_areas": len(master),
        "detail_errors": len(errors),
        "by_region": counts,
        "photos_downloaded": DL_PHOTOS,
        "map_layers": list(layers.keys()),
    }
    _common.record_artifacts(OUT, "extract_nc_fishing.py",
                             artifact_tiers(counts, layers, DL_PHOTOS), run=run)
    print("\nDONE. Summary:", json.dumps(run, indent=2), flush=True)


if __name__ == "__main__":
    main()
