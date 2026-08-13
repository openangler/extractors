# NC — North Carolina extractors

The North Carolina state pipeline. Five standard-library Python scripts that
build the NC OpenAngler dataset from public NCWRC and USGS endpoints.

All output is written to a local directory (**not committed** — see
[Output location](#output-location) below). Requires Python 3.10+, no
third-party dependencies.

## Run order

The scripts have data dependencies, so run them in this order — all pointed at
the same output directory:

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
  downloads — that flag also drops the entire `agency-media` tier.
- **Output:** `fishing-areas/all-locations.json`, per-region files, downloaded
  photos, the ArcGIS map layers, and a top-level `manifest.json`.
- **Tiers:** `agency-factual`, except the site photos (`agency-media`).

### 2. `species_extract.py`
- **Source:** NCWRC species profiles `https://www.ncwildlife.gov/species/<slug>`
  and linked documents `/media/N/download`. Public, no auth.
- **Does:** for every NC fish species profile, scrapes a structured profile
  (overview/biology, habitat, regulations, fishing tips, places to fish,
  management) plus every linked NCWRC document (one-page fact sheets and Inland
  Fisheries research reports) into structured JSON.
  The species key is canonicalised: NCWRC's URL de-dup suffix is stripped
  (`largemouth-bass-0` → `largemouth-bass`) unless that would collide with a
  different species. The raw URL stays in `url`, and the raw slug is kept in
  `source_slug` / `aliases` so old links still resolve. The list of species
  pages to scrape comes from `--species-list FILE`.
- **Output:** `species/profiles/<slug>.json` (one per species),
  `species/all-species.json` (combined), `species/reports/*.pdf` (downloaded
  documents), and `species/reports/index.json` (media-id → filename/size/species).
- **Tiers:** profiles and the report index are `agency-factual`; the PDFs
  themselves are `agency-media`.

### 3. `enrich_usgs.py`
- **Source:** USGS 3DEP EPQS (`epqs.nationalmap.gov`), NHDPlus HR
  (`hydro.nationalmap.gov`), and NWIS site service
  (`waterservices.usgs.gov`). Public, no auth.
- **Does:** for each of the 911 access points, tags on point elevation (3DEP),
  NHDPlus HR stream order / slope / drainage area / mean-annual-flow, the matched
  NHD flowline name, and the nearest active USGS streamgage. Reads
  `fishing-areas/all-locations.json` (from step 1). Supports `--limit N` and
  `--waterbody "NAME"` for testing a subset.
  NHDPlus no-data sentinels (`-9` on stream order, `-9998`/`-9999` on slope,
  drainage and flow) are normalised to `null` — they used to pass through as
  real values, and a `-9` stream order sorts *below* a headwater stream.
- **Output:** `fishing-areas/enrichment.json` (keyed by locationID) and a merged
  `all-locations-enriched.json`.
- **Tiers:** both are **mixed** — every measured attribute is
  `federal-public-domain`, the site identity fields it is keyed by are
  `agency-factual`.

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
- **Tiers:** `pmtw-reaches.json` is **mixed** — NCWRC reach facts are
  `agency-factual`, the plain-language `regulation_summary` is
  `curated-original` (it is written in this script, not by NCWRC), and the
  midpoint elevation is `federal-public-domain`.

### 5. `build_species_kb.py`
- **Source:** local files only — `species-knowledge/curated/*.json` (hand-authored
  per the knowledge-base schema) plus the enrichment produced in step 3.
- **Does:** builds the per-species knowledge base. For each curated species it
  computes an empirical habitat envelope (p10 / median / p90 of stream order,
  drainage, flow, elevation, slope) from occurrence data × USGS reach attributes,
  and merges it with the NCWRC profile and curated content.
  Curated keys are canonicalised with the same rule as step 2, and joined to the
  profiles by canonical slug or alias, so a curated file keyed
  `largemouth-bass-0` still finds the `largemouth-bass` profile and vice versa.
  Stale `kb/*.json` files from a previous build are removed.
- **Output:** `species-knowledge/all-species-knowledge.json` (combined, keyed by
  slug) and `species-knowledge/kb/<slug>.json` (one per species).
- **Tiers:** **mixed** at field level — curated content is `curated-original`,
  the habitat envelopes are `federal-public-domain`, the merged NCWRC profile
  text is `agency-factual`.

## Output location

All five scripts resolve the dataset directory the same way:

1. `--out DIR` on the command line, else
2. the `OPENANGLER_OUT` environment variable, else
3. `~/onedrive/fishing/nc-fishing-guide-data` (the historical default, kept so
   existing runs keep working).

```bash
export OPENANGLER_OUT=/data/nc-fishing-guide-data
python3 extract_nc_fishing.py
# or, per run:
python3 enrich_usgs.py --out /data/nc-fishing-guide-data
```

Every step must be pointed at the same directory — steps 3–5 read what steps 1
and 2 wrote. **Output data is never committed to this repo.**

## Provenance tiers and `manifest.json`

Each script records what it produced in the dataset-level `manifest.json`,
merging into whatever earlier steps wrote. Each artifact entry carries
`produced_by`, `generated`, its provenance `tiers`, and — when it merges more
than one tier — `mixed: true` plus a per-field `tier_detail`. Mixed artifacts
are also listed under `mixed_tier_artifacts`; a file-level tier on those would
be a rounding error, so filter them at field level or split them.

Selecting `agency-factual` + `federal-public-domain` + `curated-original` and
dropping `agency-media` yields the ~110 MB offline subset: every artifact a
recommendation actually reads, and none of the photos or PDFs.

Tier vocabulary and the size argument: see the root
[README](../README.md#provenance-and-licence-tiers).

## Tests

```bash
cd .. && python3 -m unittest discover -s tests -v
```

The tests cover the pure logic only — parsing, NHD no-data normalisation, slug
canonicalisation, region mapping, tier declarations — against fixtures captured
from a produced dataset. They never touch the network, and neither should any
test added here: four of these five scripts scrape live public agency
endpoints.
