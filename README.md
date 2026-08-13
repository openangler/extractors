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
canonicalisation, region mapping, provenance tiers) against fixtures captured
from a produced dataset. `tests/context.py` blocks socket creation so a test can
never quietly start scraping a public agency endpoint. CI runs these plus a
byte-compile on Python 3.10 and 3.12.

## Output

**Output data is NOT committed to this repo.** The full NC dataset is roughly
**~535 MB** (photos, PDFs, JSON) and is generated locally when you run the
pipeline. `output/`, `data/`, `*.pdf`, and the dataset directory are all
`.gitignore`d. This repo ships **code only** — you produce the data yourself by
running the extractors.

### Provenance and licence tiers

Every run writes a `manifest.json` at the root of the dataset recording, per
artifact, where its content came from:

| Tier | Means |
| --- | --- |
| `federal-public-domain` | Work of the US federal government, 17 U.S.C. §105 — USGS 3DEP / NHDPlus HR / NWIS |
| `agency-factual` | Facts extracted from a state agency source — coordinates, species-per-water, amenities, regulation classes |
| `agency-media` | Creative works published by a state agency — site photos, PDFs |
| `curated-original` | Hand-authored content (curated species files, plain-language regulation summaries) |
| `personal` | Private user data; never produced by these extractors |

The practical payoff is a one-line filter: dropping every artifact tagged
`agency-media` (the 357 site photos and 158 PDFs) takes the NC dataset from
~537 MB to ~110 MB, which is what makes it fit on a phone for offline use.

Some artifacts genuinely merge tiers — `all-locations-enriched.json` joins NCWRC
facts with USGS attributes, `all-species-knowledge.json` merges curated content,
NCWRC profile text and USGS-derived envelopes. Those are marked `mixed: true`,
carry a per-field `tier_detail`, and are listed under `mixed_tier_artifacts`.
**Do not treat a mixed artifact's tier list as a file-level licence.** Splitting
them is tracked separately.

*Engineering documentation, not legal advice.*

## License

MIT — see [LICENSE](LICENSE). Contributions welcome; see the
[org CONTRIBUTING guide](https://github.com/openangler/.github/blob/main/CONTRIBUTING.md).
