#!/usr/bin/env python3
"""
SC Department of Natural Resources (SCDNR) public water access extractor.

Source: SCDNR "South Carolina Public Water Access PUBLIC VIEW" ArcGIS
FeatureServer — the layer behind the SC Public Fishing Access and SC Public
Boat Ramps web apps (data-scdnr.opendata.arcgis.com). One public endpoint, no
auth, ~1,030 points in a single request.

Each SCDNR point becomes a record in the same shape the NC pipeline writes to
`fishing-areas/all-locations.json` (locationID, locationName, waterbodyName,
county, region, latitude/longitude, speciesInfo, the amenity flags), so the
USGS enrichment and every downstream consumer read both states alike. Fields
SCDNR publishes that NCWRC does not (parking, launch lanes, courtesy dock,
owner, directions) ride along in a `facilities` block, as NC's PFA/BAA join does.

Freshwater only: SCDNR's saltwater points (piers, tidal landings on the
ocean side of the salt/fresh dividing line) are kept in the raw archive but
not in all-locations.json, because no consumer models saltwater species yet.

    python3 sc/extract_sc_fishing.py --out /path/to/sc-fishing-guide-data
"""

import argparse
import json
import os
import urllib.parse
import urllib.request

import _common
from _common import AGENCY_FACTUAL, ARCHIVE, QUERY

LAYER = ("https://services.arcgis.com/acgZYxoN5Oj8pDLa/arcgis/rest/services/"
         "South_Carolina_Public_Water_Access_PUBLIC_VIEW/FeatureServer/0")
UA = "openangler-extractors/1.0"
STATE = "US-SC"

# ---- SC county -> physiographic region ----------------------------------------
#
# The same three labels NC uses, so a region filter means the same thing in both
# states. County-level, so coarse: "Mountains" is the three Blue Ridge counties
# SCDNR itself names for mountain trout (Oconee, Pickens, Greenville), although
# Lake Hartwell and the city of Greenville sit on Piedmont ground inside them.
# The Sandhills counties on the fall line are Coastal Plain, which is the
# province they belong to.
MOUNTAINS = {"Oconee", "Pickens", "Greenville"}
PIEDMONT = {
    "Abbeville", "Anderson", "Cherokee", "Chester", "Edgefield", "Fairfield",
    "Greenwood", "Lancaster", "Laurens", "McCormick", "Newberry", "Saluda",
    "Spartanburg", "Union", "York",
}
COASTAL = {
    "Aiken", "Allendale", "Bamberg", "Barnwell", "Beaufort", "Berkeley", "Calhoun",
    "Charleston", "Chesterfield", "Clarendon", "Colleton", "Darlington", "Dillon",
    "Dorchester", "Florence", "Georgetown", "Hampton", "Horry", "Jasper", "Kershaw",
    "Lee", "Lexington", "Marion", "Marlboro", "Orangeburg", "Richland", "Sumter",
    "Williamsburg",
}


def clean_county(raw):
    """'Berkeley ' / 'Charleston County' -> 'Berkeley' / 'Charleston'."""
    county = (raw or "").strip()
    if county.lower().endswith(" county"):
        county = county[:-len(" county")].strip()
    return county or None


def region_for(county):
    if county in MOUNTAINS:
        return "Mountains"
    if county in PIEDMONT:
        return "Piedmont"
    if county in COASTAL:
        return "Coastal Plain"
    return "Unknown"


def species_name(raw):
    """One SCDNR species label, cleaned.

    The hybrid is published as "Striped Bass X white Bass hybrid*" — the asterisk
    is a footnote marker with no footnote in the layer, and the casing is
    inconsistent. Everything else is already a clean common name.
    """
    name = raw.strip().rstrip("*").strip()
    if name.lower() == "striped bass x white bass hybrid":
        return "Hybrid Striped Bass"
    return name


def species_info(species_list):
    """'Bluegill, Largemouth Bass' -> NC-shaped [{commonName, stocked, wild}].

    SCDNR says which species are present, not whether they are stocked or wild,
    so both flags are null rather than a guess.
    """
    seen, out = set(), []
    for part in (species_list or "").split(","):
        name = species_name(part)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"commonName": name, "stocked": None, "wild": None})
    return out


def yes(value):
    """SCDNR's 'Yes'/'No'/null flags -> True/False/None."""
    if value is None:
        return None
    return str(value).strip().lower() == "yes"


# SCDNR attributes NC has no equivalent for, carried under `facilities`.
FACILITY_FIELDS = (
    "WaterAccessSubType", "WaterAccessMaterial", "WaterAccessDescription",
    "WaterbodyType", "Parking", "ParkingSurface", "LaunchLanes", "CourtesyDock",
    "FishingPier", "PicnicArea", "Camping", "Accessible", "AccessibleDescription",
    "Restrooms", "Owner", "Maintenance", "Address", "PublicAccess", "Comments",
)


def normalize(attrs):
    """One SCDNR feature's attributes -> an NC-shaped access-point record.

    `locationID` is SCDNR's WaterAccessID ("BR224": BR boat ramp, FA fishing
    access, PL paddle launch) — a string, unlike NCWRC's integer. The handful of
    points without one fall back to their GlobalID, which is stable across
    edits; OBJECTID is not.
    """
    kind = attrs.get("WaterAccessType")
    county = clean_county(attrs.get("County"))
    facilities = {k: attrs.get(k) for k in FACILITY_FIELDS if attrs.get(k) is not None}
    facilities["_source"] = "SCDNR Public Water Access"
    return {
        "state": STATE,
        "locationID": attrs.get("WaterAccessID") or (attrs.get("GlobalID") or "").strip("{}"),
        "locationName": (attrs.get("WaterAccessName") or "").strip(),
        "locationTypeName": kind,
        "waterbodyName": (attrs.get("Waterbody") or "").strip() or None,
        "county": county,
        "region": region_for(county),
        "latitude": attrs.get("Latitude"),
        "longitude": attrs.get("Longitude"),
        "boatRamp": kind == "Boat Ramp",
        "fishingPierAccess": kind == "Pier" or yes(attrs.get("FishingPier")) is True,
        "shorelineAccess": kind == "Bank",
        "canoeAccess": kind == "Paddle Launch",
        "wheelchairAccessible": yes(attrs.get("Accessible")),
        "troutWater": yes(attrs.get("TroutWater")),
        # SCDNR does not say what it stocks where; null, not False.
        "troutStocked": None,
        "warmWaterFishStocked": None,
        "speciesInfo": species_info(attrs.get("SpeciesList")),
        "management": attrs.get("Maintenance"),
        "ownerName": attrs.get("Owner"),
        "directions": attrs.get("Directions"),
        "description": attrs.get("WaterAccessDescription"),
        "facilities": facilities,
    }


def keep(attrs):
    """Open, active, freshwater points with coordinates."""
    return (attrs.get("WaterType") == "Freshwater"
            and attrs.get("Status") == "Active"
            and attrs.get("PublicAccess") != "Closed"
            and attrs.get("Latitude") is not None
            and attrs.get("Longitude") is not None)


def build(features):
    """Raw ArcGIS features -> (records, counts). Pure; tested on a fixture."""
    attrs = [f["attributes"] for f in features]
    records = [normalize(a) for a in attrs if keep(a)]
    records.sort(key=lambda r: (r["county"] or "", r["locationName"]))
    counts = {"features": len(attrs), "kept": len(records),
              "saltwater": sum(1 for a in attrs if a.get("WaterType") == "Saltwater"),
              "unknown_region": sum(1 for r in records if r["region"] == "Unknown")}
    return records, counts


def fetch():
    """Every feature, paging in case the layer outgrows one request."""
    features, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": "1=1", "outFields": "*", "returnGeometry": "false",
            "orderByFields": "OBJECTID", "resultOffset": offset,
            "resultRecordCount": 1000, "f": "json"})
        req = urllib.request.Request(f"{LAYER}/query?{q}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        if "error" in page:
            raise RuntimeError(f"SCDNR layer error: {page['error']}")
        features += page.get("features", [])
        if not page.get("exceededTransferLimit"):
            return features
        offset = len(features)


def artifact_tiers():
    """Provenance tier and role for every artifact this script writes."""
    all_locations = "fishing-areas/all-locations.json"
    return {
        "raw/scdnr-public-water-access.json": {
            "tiers": [AGENCY_FACTUAL], "role": ARCHIVE,
            "note": "Untouched SCDNR Public Water Access features, saltwater "
                    "included, kept so a run can be audited against its source."},
        all_locations: {
            "tiers": [AGENCY_FACTUAL], "role": QUERY,
            "note": "SCDNR public water access facts (coordinates, access type, "
                    "amenities, species present), freshwater only, in the NC "
                    "all-locations shape. SCDNR-only attributes are under "
                    "`facilities`."},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    a = ap.parse_args()
    out = _common.resolve_out(a.out)
    print(f"Dataset -> {out}", flush=True)

    features = fetch()
    records, counts = build(features)
    os.makedirs(os.path.join(out, "raw"), exist_ok=True)
    os.makedirs(os.path.join(out, "fishing-areas"), exist_ok=True)
    with open(os.path.join(out, "raw", "scdnr-public-water-access.json"), "w") as f:
        json.dump(features, f, indent=2)
    with open(os.path.join(out, "fishing-areas", "all-locations.json"), "w") as f:
        json.dump(records, f, indent=2)

    _common.record_artifacts(out, "extract_sc_fishing.py", artifact_tiers(),
                             run=dict(counts, sources=["SCDNR Public Water Access"]))
    print(f"Done. {counts['kept']} freshwater access points "
          f"({counts['saltwater']} saltwater skipped).", flush=True)


if __name__ == "__main__":
    main()
