# SC — South Carolina extractors

The South Carolina state pipeline: SCDNR's public water access points, in the
same record shape the NC pipeline writes, plus the same USGS enrichment. Two
standard-library Python scripts; Python 3.10+, no dependencies.

SC writes **its own dataset**, never NC's. There is no default output
directory: pass `--out` or set `$OPENANGLER_OUT`, and the scripts refuse a
directory whose `manifest.json` belongs to another state.

```bash
python3 sc/extract_sc_fishing.py --out /path/to/sc-fishing-guide-data
python3 sc/enrich_sc_usgs.py     --out /path/to/sc-fishing-guide-data
```

## 1. `extract_sc_fishing.py`

- **Source:** SCDNR "South Carolina Public Water Access PUBLIC VIEW" ArcGIS
  FeatureServer — the layer behind the SC Public Fishing Access and SC Public
  Boat Ramps apps (data-scdnr.opendata.arcgis.com). One public request.
- **Output:** `fishing-areas/all-locations.json` (freshwater, open, active
  points; `query`) and `raw/scdnr-public-water-access.json` (every feature,
  saltwater included; `archive`). Both `agency-factual`.
- **Shape:** NC's — `locationID`, `locationName`, `waterbodyName`, `county`,
  `region`, `latitude`/`longitude`, `speciesInfo`, the amenity flags — plus
  `state: "US-SC"` and `troutWater`. What NCWRC has no field for (parking,
  launch lanes, courtesy dock, owner, …) is under `facilities`.
- **Normalisation, all in pure functions tested against a fixture:**
  - `locationID` is SCDNR's `WaterAccessID` string (`BR` boat ramp, `FA`
    fishing access, `PL` paddle launch); the few points without one use their
    `GlobalID`.
  - County spellings are cleaned (`"Berkeley "`, `"Charleston County"`).
  - `region` uses NC's three labels from a county map: Oconee/Pickens/
    Greenville are Mountains (SCDNR's own mountain-trout counties), the fall-line
    Sandhills counties are Coastal Plain. County-level, so coarse.
  - `"Striped Bass X white Bass hybrid*"` becomes `"Hybrid Striped Bass"`.
  - SCDNR says which species are present, not whether stocked or wild, so
    `stocked`/`wild` and `troutStocked` are `null`, never a guessed `false`.
  - Saltwater points (121) are left out of `all-locations.json`.

## 2. `enrich_sc_usgs.py`

The shared USGS lookups (`shared/usgs.py`) over every SC site: 3DEP elevation,
the NHDPlus HR reach, and the nearest active real-time gage from SC, GA or NC —
border landings on the Savannah, Chattooga, Catawba and Pee Dee are often
nearest a gage across the line. Output `fishing-areas/enrichment.json`
(keyed by `locationID`; `query`; USGS fields federal, identity fields SCDNR).
`--limit N` enriches N sites and prints them without writing anything.

First run (2026-10-01): 909 sites, 812 matched to an NHD reach.

## Not yet

No SC trout-stream layer (SC has no PMTW-style reach layer; its rules live in
the SCDNR Trout Book PDF), no species profiles, no saltwater.
