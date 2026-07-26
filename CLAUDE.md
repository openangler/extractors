# CLAUDE.md — guide for AI assistants working in this repo

## What this repo is

`openangler/extractors` holds **public-data pipelines that build OpenAngler
datasets from state and federal agency sources, state by state.** Each extractor
pulls from public agency endpoints (fishing-access inventories, species
profiles, hydrology, elevation, weather) and produces structured JSON intended
to conform to the [`openangler/schema`](https://github.com/openangler/schema).

This repo is part of **[OpenAngler](https://github.com/openangler)** — an
open-source effort providing open tooling and open data for anglers, built
entirely from public data.

**Status: alpha.** Only North Carolina is implemented so far.

## Layout

The repo is organized as one directory per state. Each state directory is a
self-contained pipeline:

```
extractors/
├── nc/            North Carolina pipeline (5 scripts) — see nc/README.md
├── requirements.txt
├── LICENSE        MIT
├── README.md
└── CLAUDE.md      (this file)
```

Future states get sibling directories (`sc/`, `va/`, `ga/`, …). Keep each
state's code inside its own directory; do not cross-import between states.

## The NC pipeline (`nc/`)

Five standard-library Python scripts, run in this order (see `nc/README.md` for
full per-script detail):

1. `extract_nc_fishing.py` — 911 fishing-access points + photos + ArcGIS map layers
2. `species_extract.py` — species profiles + linked research PDFs (independent of #1)
3. `enrich_usgs.py` — adds USGS hydrology to each access point (needs #1's output)
4. `build_pmtw_layer.py` — classifies the 1,809 Public Mountain Trout Water reaches
5. `build_species_kb.py` — builds the per-species habitat knowledge base (needs #3)

## Public data sources (all public, no auth)

- **NCWRC** — `ncpaws.org/NCWRCMaps/FishingAreas` app JSON and ArcGIS
  FeatureServers (`services1.arcgis.com/YfqBAUM5nWR3yhGP`): access points,
  photos, and map layers.
- **NCWRC** — `ncwildlife.gov/species/*` profiles and `/media/N/download` PDFs.
- **USGS** — 3DEP EPQS (`epqs.nationalmap.gov`), NHDPlus HR
  (`hydro.nationalmap.gov`), NWIS (`waterservices.usgs.gov`).
- **Open-Meteo** (`open-meteo.com`) — weather enrichment for downstream
  OpenAngler tooling.

Be a good API citizen: these are free public services. Keep concurrency
modest and don't hammer endpoints.

## How to run

Python 3.10+, **standard library only — no third-party dependencies** (see
`requirements.txt`; nothing to `pip install`).

```bash
python3 nc/extract_nc_fishing.py
python3 nc/species_extract.py
python3 nc/enrich_usgs.py
python3 nc/build_pmtw_layer.py
python3 nc/build_species_kb.py
```

## Output — do NOT commit data

The scripts generate a large local dataset (~535 MB: photos, PDFs, JSON). **Only
code lives in this repo.** `output/`, `data/`, `*.pdf`, and the dataset
directory are `.gitignore`d. Never commit extracted data.

### Known TODO — output path

Every script currently writes to a hardcoded local path
(`~/onedrive/fishing/nc-fishing-guide-data/`) via an `OUT` / `BASE` constant near
the top of the file. Making this configurable (CLI flag / env var) is a planned
improvement. If you need a different location for now, edit that constant. Do not
commit any real local paths beyond this existing default, and do not add
references to external, private, or proprietary projects.

## Conventions

- Keep scripts runnable as plain `python3 nc/<script>.py` with no install step.
- Stay standard-library only unless there's a strong reason; if you add a
  dependency, update `requirements.txt` and the "no dependencies" claims in the
  READMEs.
- CI only byte-compiles (`python -m py_compile nc/*.py`) — it does not run the
  scripts, because they hit live public APIs.

## License

MIT — see `LICENSE`. Copyright (c) 2026 OpenAngler contributors.
