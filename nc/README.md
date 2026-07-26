# NC — North Carolina extractors

The North Carolina state pipeline. Five standard-library Python scripts that
build the NC OpenAngler dataset from public NCWRC and USGS endpoints.

All output is written to a local directory (**not committed** — see the note on
the hardcoded output path at the bottom). Requires Python 3.10+, no third-party
dependencies.

## Run order

The scripts have data dependencies, so run them in this order:

1. **`extract_nc_fishing.py`** — produces `fishing-areas/all-locations.json`
2. **`species_extract.py`** — independent; produces the species profiles + reports
3. **`enrich_usgs.py`** — reads `all-locations.json` from step 1
4. **`build_pmtw_layer.py`** — reads the trout-waters layer downloaded in step 1
5. **`build_species_kb.py`** — reads step 3's enrichment + curated species files

Steps 1 and 2 are independent of each other. Steps 3–5 depend on step 1.

## Scripts

### 1. `extract_nc_fishing.py`
- **Source:** NCWRC public map app `https://www.ncpaws.org/NCWRCMaps/FishingAreas`
  and the ArcGIS FeatureServers behind it
  (`services1.arcgis.com/YfqBAUM5nWR3yhGP`). Public, no auth.
- **Does:** pulls every fishing-area marker with full detail (amenities, species,
  management, photo), downloads site photos, and downloads the ArcGIS map layers
  (trout waters, game lands, county boundaries, etc.), organized by NC region
  (Mountains / Piedmont / Coastal Plain). Pass `--no-photos` to skip photo
  downloads.
- **Output:** `fishing-areas/all-locations.json`, per-region files, downloaded
  photos, the ArcGIS map layers, and a top-level `manifest.json`.

### 2. `species_extract.py`
- **Source:** NCWRC species profiles `https://www.ncwildlife.gov/species/<slug>`
  and linked documents `/media/N/download`. Public, no auth.
- **Does:** for every NC fish species profile, scrapes a structured profile
  (overview/biology, habitat, regulations, fishing tips, places to fish,
  management) plus every linked NCWRC document (one-page fact sheets and Inland
  Fisheries research reports) into structured JSON.
- **Output:** `species/profiles/<slug>.json` (one per species),
  `species/all-species.json` (combined), `species/reports/*.pdf` (downloaded
  documents), and `species/reports/index.json` (media-id → filename/size/species).

### 3. `enrich_usgs.py`
- **Source:** USGS 3DEP EPQS (`epqs.nationalmap.gov`), NHDPlus HR
  (`hydro.nationalmap.gov`), and NWIS site service
  (`waterservices.usgs.gov`). Public, no auth.
- **Does:** for each of the 911 access points, tags on point elevation (3DEP),
  NHDPlus HR stream order / slope / drainage area / mean-annual-flow, the matched
  NHD flowline name, and the nearest active USGS streamgage. Reads
  `fishing-areas/all-locations.json` (from step 1). Supports `--limit N` and
  `--waterbody "NAME"` for testing a subset.
- **Output:** `fishing-areas/enrichment.json` (keyed by locationID) and a merged
  `all-locations-enriched.json`.

### 4. `build_pmtw_layer.py`
- **Source:** the Public Mountain Trout Water (PMTW) reaches and county
  boundaries downloaded in step 1, plus USGS 3DEP EPQS
  (`epqs.nationalmap.gov`) for midpoint elevation.
- **Does:** turns the 1,809 PMTW stream reaches into a classified/regulated reach
  layer — stream name, reach description, WRC classification with a plain-language
  regulation summary, Mountain Heritage flag, length, a representative midpoint
  coordinate, the county (point-in-polygon), and midpoint elevation. Pass
  `--no-elevation` to skip the 1,809 EPQS calls.
- **Output:** `trout-waters/pmtw-reaches.json` (the reach index) and
  `trout-waters/pmtw-summary.json` (counts by class and county).

### 5. `build_species_kb.py`
- **Source:** local files only — `species-knowledge/curated/*.json` (hand-authored
  per the knowledge-base schema) plus the enrichment produced in step 3.
- **Does:** builds the per-species knowledge base. For each curated species it
  computes an empirical habitat envelope (p10 / median / p90 of stream order,
  drainage, flow, elevation, slope) from occurrence data × USGS reach attributes,
  and merges it with the NCWRC profile and curated content.
- **Output:** `species-knowledge/all-species-knowledge.json` (combined, keyed by
  slug) and `species-knowledge/kb/<slug>.json` (one per species).

## Known TODO — output path

Every script writes to a hardcoded local path
(`~/onedrive/fishing/nc-fishing-guide-data/`) inherited from the original
project. Making this configurable (CLI flag / env var) is a planned improvement.
For now, edit the `OUT` / `BASE` constant near the top of each script to change
where data lands. **Output data is never committed to this repo.**
