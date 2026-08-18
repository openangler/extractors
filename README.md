# openangler-extractors

**Public-data pipelines that build [OpenAngler](https://github.com/openangler)
datasets from state and federal agency sources — state by state.**

Each extractor pulls from public agency endpoints (fishing-access inventories,
species profiles, hydrology, elevation, weather) and produces structured JSON
intended to conform to the [`openangler/schema`](https://github.com/openangler/schema).
The goal is an open, reproducible dataset for anglers built entirely from
public data.

> **Status: alpha.** Only **North Carolina** is implemented so far
> (see [`nc/`](nc/)). The repo is structured so other states get sibling
> directories (`nc/`, and later `sc/`, `va/`, `ga/`, …), each a self-contained
> state pipeline.

## Repository layout

```
extractors/
├── nc/            North Carolina state pipeline (5 scripts) — see nc/README.md
│   ├── extract_nc_fishing.py
│   ├── species_extract.py
│   ├── enrich_usgs.py
│   ├── build_pmtw_layer.py
│   ├── build_species_kb.py
│   └── _common.py          output-path resolution + the provenance manifest
├── tools/
│   └── plan_bundle.py      build a tier/role-filtered subset from a manifest
├── tests/         unit tests for the pure logic (stdlib unittest, no network)
├── requirements.txt
├── LICENSE
└── README.md
```

## Public data sources

All endpoints are public and require no authentication.

| Source | What it provides | Used by |
| --- | --- | --- |
| **NCWRC** — `ncpaws.org/NCWRCMaps/FishingAreas` app JSON + ArcGIS FeatureServers (`services1.arcgis.com/YfqBAUM5nWR3yhGP`) | 911 fishing-access points (amenities, species, management), site photos, and map layers (trout waters, game lands, county boundaries) | `extract_nc_fishing.py`, `build_pmtw_layer.py` |
| **NCWRC** — `ncwildlife.gov/species/*` profiles + `/media/N/download` PDFs | Structured fish species profiles and linked Inland Fisheries research reports / fact sheets | `species_extract.py` |
| **USGS** — 3DEP EPQS (`epqs.nationalmap.gov`), NHDPlus HR (`hydro.nationalmap.gov`), NWIS (`waterservices.usgs.gov`) | Point elevation, stream order / slope / drainage / mean-annual-flow, and nearest active streamgage | `enrich_usgs.py`, `build_pmtw_layer.py` |
| **Open-Meteo** (`open-meteo.com`) | Weather/forecast enrichment (used by downstream OpenAngler tooling; not yet exercised by the NC extractors in this repo) | — |

## Requirements

**Python 3.10+ — standard library only, no third-party dependencies.** See
[`requirements.txt`](requirements.txt). Nothing to `pip install`.

## How to run

Clone the repo and run any script directly with a system Python 3.10+:

```bash
git clone https://github.com/openangler/extractors
cd extractors

export OPENANGLER_OUT=/path/to/nc-fishing-guide-data   # where the dataset lands

# North Carolina pipeline (run in order — see nc/README.md)
python3 nc/extract_nc_fishing.py       # 911 access points + photos + ArcGIS layers
python3 nc/species_extract.py          # species profiles + research PDFs
python3 nc/enrich_usgs.py              # add USGS hydrology to each access point
python3 nc/build_pmtw_layer.py         # classify the 1,809 trout-water reaches
                                       #   (+ a structured bait_rule per reach:
                                       #    is natural bait legal here, and when?)
python3 nc/build_species_kb.py         # per-species habitat knowledge base
```

Every script takes `--out DIR` as well; the precedence is `--out`, then
`$OPENANGLER_OUT`, then the historical default
(`~/onedrive/fishing/nc-fishing-guide-data`). Each step must be pointed at the
same directory — steps 3–5 read what step 1 wrote.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Standard-library `unittest`, no dependencies, and **no network** — the tests
exercise the pure logic (response parsing, NHD no-data normalisation, slug
canonicalisation, region mapping, provenance tiers, field-selector resolution
and bundle filtering) against fixtures captured from a produced dataset.
`tests/context.py` blocks socket creation so a test can never quietly start
scraping a public agency endpoint. CI runs these plus a byte-compile on
Python 3.10 and 3.12.

## Output

**Output data is NOT committed to this repo.** The full NC dataset is roughly
**~535 MB** (photos, PDFs, JSON) and is generated locally when you run the
pipeline. `output/`, `data/`, `*.pdf`, and the dataset directory are all
`.gitignore`d. This repo ships **code only** — you produce the data yourself by
running the extractors.

### Provenance tiers, roles, and `manifest.json`

Every run writes a `manifest.json` at the root of the dataset. Each artifact
records **where its content came from** (tier), **what it is for** (role), and
**what it weighs** (measured, not declared).

| Tier | Means |
| --- | --- |
| `federal-public-domain` | Work of the US federal government, 17 U.S.C. §105 — USGS 3DEP / NHDPlus HR / NWIS |
| `agency-factual` | Facts extracted from a state agency source — coordinates, species-per-water, amenities, regulation classes |
| `agency-media` | Creative works published by a state agency — site photos, PDFs |
| `curated-original` | Hand-authored content (curated species files, plain-language regulation summaries) |
| `personal` | Private user data; never produced by these extractors |

| Role | Means |
| --- | --- |
| `query` | Structured data a query or recommendation engine reads at runtime |
| `geometry` | Bulk map geometry (GeoJSON) — needed to draw a map, not to answer a query |
| `media` | Binary creative works: photographs, PDFs |
| `archive` | Reproducibility copy, hand-authored input, or a redundant view of another artifact (`derived_from` says which) |

**Tier and role are independent axes, and you need both.** Dropping the
`agency-media` tier takes the NC dataset from ~537 MB to ~110 MB — but ~103 MB
of what is left is GeoJSON map geometry, tagged `agency-factual`, the same tier
as the JSON a recommendation actually reads. Filtering on tier *and* role gives
a **~3.2 MB** offline bundle; add `geometry` back for offline maps and it is
~106 MB. Measured on the NC dataset, from the manifest alone:

| Filter | Artifacts | Size |
| --- | --- | --- |
| everything | 29 | ~537 MB |
| `--drop-tiers agency-media` | 25 | ~110 MB |
| `--drop-tiers agency-media --roles query,geometry` | 15 | ~106 MB |
| `--drop-tiers agency-media --roles query` | 8 | **~3.2 MB** |

#### Mixed-tier artifacts are tagged per field, not split

Several artifacts fuse sources in one file — `enrichment.json` (USGS attributes
under NCWRC identity keys), `pmtw-reaches.json` (NCWRC reach facts, a curated
regulation summary and `bait_rule`, USGS elevation), `all-species-knowledge.json` and `kb/`
(curated content, NCWRC profile text, a USGS-derived envelope). A file-level
tier on those would be a lie by rounding.

They are **not** split, because applications read these exact files and paths.
Instead each carries a `fields` block whose selectors a consumer applies
mechanically:

```jsonc
"fishing-areas/all-locations-enriched.json": {
  "tiers": ["agency-factual", "federal-public-domain"], "mixed": true,
  "role": "archive", "bytes": 1807157, "files": 1,
  "derived_from": ["fishing-areas/all-locations.json",
                   "fishing-areas/enrichment.json"],
  "fields": {
    "records": "list",                     // each array element is a record
    "default": "agency-factual",           // anything unmatched is NCWRC's
    "rules": {
      "usgs": "federal-public-domain",     // ... and everything beneath it
      "usgs.locationID": "agency-factual"  // ... except this: longest match wins
    },
    "coverage": "complete"                 // verified against real records
  }
}
```

- `records` — where records live: `list` (array elements), `map` (object
  values), `object` (the document itself; for a directory artifact, each file).
- A rule key is a dotted path relative to a record. List indices are elided, so
  the rule `rigs` covers `rigs[*].name`. A rule covers its own path and
  everything beneath it, and **the longest matching rule wins**.
- Unmatched fields take `default`, or are untagged when there is no default.
  Defaults are only ever used in the conservative direction.
- `coverage` is checked at build time against the records actually written:
  `complete`, or `partial` with the offending paths in `untagged`. Add a field
  and forget to tag it and the run says so.

#### Filtering, mechanically

`tools/plan_bundle.py` is the consumer side. It reads `manifest.json` and
nothing else — no knowledge of which file holds what:

```bash
# what a phone needs for offline field use: ~3.2 MB
python3 tools/plan_bundle.py /path/to/dataset --drop-tiers agency-media --roles query

# same, plus offline map geometry
python3 tools/plan_bundle.py /path/to/dataset --drop-tiers agency-media --roles query,geometry

# and materialise it — mixed artifacts keep their shape, minus disallowed fields
python3 tools/plan_bundle.py /path/to/dataset --drop-tiers agency-media \
    --roles query --build /tmp/phone-bundle
```

*Engineering documentation, not legal advice.*

## License

MIT — see [LICENSE](LICENSE). Contributions welcome; see the
[org CONTRIBUTING guide](https://github.com/openangler/.github/blob/main/CONTRIBUTING.md).
