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
  and the ArcGIS FeatureServers behind it. The map app carries ~27 fields per site;
  the dedicated `NCWRC_Public_Fishing_Areas_view` / `NCWRC_Boating_Access_Areas_view`
  services carry ~50, and step 6 joins them on (name, proximity) — 496 of 526 PFA/BAA
  sites match, 92 of them to both services at once. That join is where `Fish_Feeder`
  and `Lighting` come from.
  (`services1.arcgis.com/YfqBAUM5nWR3yhGP`). Public, no auth.
- **Does:** pulls every fishing-area marker with full detail (amenities, species,
  management, photo), downloads site photos, and downloads the ArcGIS map layers
  (trout waters, game lands, county boundaries, etc.), organized by NC region
  (Mountains / Piedmont / Coastal Plain). Pass `--no-photos` to skip photo
  downloads — that flag also drops the entire `agency-media` tier.
- **Output:** `fishing-areas/all-locations.json`, per-region files, downloaded
  photos, the ArcGIS map layers, and a top-level `manifest.json`.
- **Tiers:** `agency-factual`, except the site photos (`agency-media`).
- **Roles:** `all-locations.json` is `query`; the GeoJSON layers are `geometry`
  (same tier, ~103 MB); photos are `media`; the per-region JSON/CSV are
  `archive`, `derived_from` `all-locations.json`.

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
- **Roles:** `all-species.json` and `reports/index.json` are `query` (the index
  survives a media drop, so `linked_reports` still resolves); `profiles/` is
  `archive`, `derived_from` `all-species.json`; `reports/` is `media`.

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
- **Tiers:** both are **mixed**, tagged per field — every measured attribute is
  `federal-public-domain`, the three site identity fields it is keyed by are
  `agency-factual`. `enrichment.json` has no `default`, so a new untagged field
  is reported rather than silently called federal. In
  `all-locations-enriched.json` the rule `usgs` is federal and
  `usgs.locationID` / `usgs.locationName` / `usgs.waterbodyName` override it
  back to `agency-factual` — longest match wins.
- **Roles:** `enrichment.json` is `query`; `all-locations-enriched.json` is
  `archive`, `derived_from` the two artifacts it joins.

### 4. `build_pmtw_layer.py`
- **Source:** the Public Mountain Trout Water (PMTW) reaches and county
  boundaries downloaded in step 1, plus USGS 3DEP EPQS
  (`epqs.nationalmap.gov`) for midpoint elevation.
- **Does:** turns the 1,809 PMTW stream reaches into a classified/regulated reach
  layer — stream name, reach description, WRC classification with a plain-language
  regulation summary **and a structured `bait_rule`**, Mountain Heritage flag,
  length, a representative midpoint coordinate, the county (point-in-polygon),
  and midpoint elevation. Pass `--no-elevation` to skip the 1,809 EPQS calls.
- **Output:** `trout-waters/pmtw-reaches.json` (the reach index) and
  `trout-waters/pmtw-summary.json` (counts by class and county, plus counts by
  bait state and any WRC class with no bait rule).
- **Tiers:** `pmtw-reaches.json` is **mixed**, tagged per field — NCWRC reach
  facts are `agency-factual`, the plain-language `regulation_summary` and the
  `bait_rule` are `curated-original` (both are written in this script, not by
  NCWRC; `bait_rule.source` is NCWRC's own URL and stays `agency-factual`), and
  `elevation_m` is `federal-public-domain`. `--no-elevation` leaves that field
  present and null, so it stays tagged.
- **Roles:** both `query`; `pmtw-summary.json` is `derived_from`
  `pmtw-reaches.json`.

#### `bait_rule` — "is the bait in my hand legal here?", structured

`regulation_summary` is prose and has to be: it carries size and creel limits no
enum holds. `bait_rule` is the one question an app must answer without parsing
English, because being wrong means a citation. Per reach:

| field | values |
|---|---|
| `natural_bait` | `allowed` / `prohibited` / `seasonal` (date-dependent, see `periods`) / `unknown` |
| `natural_bait_possession` | `prohibited` / `not_restricted` / `unknown` — Wild Trout Waters (15A NCAC 10C .0205(b)(6)) and Delayed Harvest water in season ban *possessing* bait while fishing, not merely using it. Where the rule governs only use and is silent on possession (Catch and Release), this is `unknown`: silence is not permission |
| `gear_restriction` | `any_bait_or_lure` / `single_hook_artificial_lures` (Wild Trout, Delayed Harvest in season) / `single_hook_artificial_flies_and_lures` (Catch and Release). Lures and flies-and-lures are different rules and are never collapsed |
| `harvest` | `allowed` / `catch_and_release` / `unknown` |
| `open_to` | `all_anglers` / `youth_only` / `closed` / `varies_by_time` / `unknown` — who may fish, which is a different question from what they may fish with |
| `basis` | `wrc_class` / `posted_signage` (Special Regulation water: read the sign) / `unrecognised_class` |
| `periods`, `closures` | for water whose answer moves with the calendar |
| `source` | the NCWRC URL for the reach |

Season boundaries are stored as **anchors**, not dates — `{"month": 6,
"weekday": "saturday", "nth": 1}` is the first Saturday in June, and
`{"weekday": "friday", "before": …}` is the Friday before it, which is how the
regulation itself states the end of the Delayed Harvest season. A hardcoded
date would be wrong within twelve months. Periods tile the year half-open, so
every date lands in exactly one of them.

A day that holds more than one answer carries `day_parts`, sub-day windows whose
boundaries are either a clock time (`{"clock": "06:00"}`) or a symbolic solar
one (`{"solar": "sunset", "offset_minutes": 30}`) left for a consumer with an
ephemeris to resolve — this script never guesses a sunset.

`bait_rule_on(rule, date[, time])` flattens all of that to the answer in force,
and `may_fish(open_to, angler)` turns `open_to` into a yes/no for an adult or a
youth angler. Both are importable; nothing in them touches the network.

The Delayed Harvest handover is the case the shape exists for. On the first
Saturday in June the water is **closed** until 6 a.m., **youth-only** (under 16)
from 6 a.m. to noon, and open to all from noon; the restricted season before it
ends one-half hour after sunset on the **Friday** before, not at midnight on the
Saturday. Ask with a time and you get `closed` / `youth_only` / `all_anglers`;
ask with only a date and you get `varies_by_time` and the `day_parts` — never a
bare "allowed" that would send an adult onto a youth-only stream.

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
  the habitat envelope numbers are `federal-public-domain`, the merged NCWRC
  profile text is `agency-factual`. The one sentence describing how the
  envelope was derived (`habitat_envelope.derived_from`) is written here, so it
  overrides the federal block back to `curated-original`.
- **Roles:** both outputs are `query` (`kb/` is `derived_from`
  `all-species-knowledge.json` but is read directly by consumers, so it is not
  an archive); `species-knowledge/curated/` is `archive` — a hand-authored
  input, read at build time only.

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

## Provenance tiers, roles, and `manifest.json`

Each script records what it produced in the dataset-level `manifest.json`,
merging into whatever earlier steps wrote. Each artifact entry carries
`produced_by`, `generated`, its provenance `tiers`, its `role`, its measured
`bytes` / `files`, an optional `derived_from`, and — when it merges more than
one tier — `mixed: true` plus a `fields` block giving the tier of every field.
Mixed artifacts are also listed under `mixed_tier_artifacts`.

**Mixed artifacts are tagged, not split.** `enrichment.json`,
`pmtw-reaches.json`, `all-species-knowledge.json` and `kb/<slug>.json` are read
directly, at those paths, by applications; splitting them per tier would break
every consumer. The `fields` selectors are precise enough that a consumer can
strip the disallowed fields and leave the file shape untouched.

Filtering on tier alone drops the media but keeps ~104 MB of GeoJSON, which is
the same `agency-factual` tier as the JSON a recommendation reads. That is why
each artifact also has a role:

| Filter | Artifacts | Size |
| --- | --- | --- |
| everything | 29 | ~537 MB |
| `--drop-tiers agency-media` | 25 | ~110 MB |
| `--drop-tiers agency-media --roles query,geometry` | 15 | ~106 MB |
| `--drop-tiers agency-media --roles query` | 8 | **~3.2 MB** |

```bash
python3 ../tools/plan_bundle.py "$OPENANGLER_OUT" \
    --drop-tiers agency-media --roles query --build /tmp/phone-bundle
```

`plan_bundle.py` reads `manifest.json` and nothing else — it is the check that
the tagging is complete enough to be useful.

Tier and role vocabulary, and the field-selector syntax: see the root
[README](../README.md#provenance-tiers-roles-and-manifestjson).

## Tests

```bash
cd .. && python3 -m unittest discover -s tests -v
```

The tests cover the pure logic only — parsing, NHD no-data normalisation, slug
canonicalisation, region mapping, tier and role declarations, field-selector
resolution, and the consumer-side bundle filter — against fixtures captured from
a produced dataset. They never touch the network, and neither should any test
added here: four of these five scripts scrape live public agency endpoints.
