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
│   └── _common.py   shared: --out/$OPENANGLER_OUT resolution + tier manifest
├── tests/         stdlib unittest for the pure logic; never touches the network
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
export OPENANGLER_OUT=/path/to/nc-fishing-guide-data   # or pass --out DIR
python3 nc/extract_nc_fishing.py
python3 nc/species_extract.py
python3 nc/enrich_usgs.py
python3 nc/build_pmtw_layer.py
python3 nc/build_species_kb.py
```

Tests: `python3 -m unittest discover -s tests -v` — no dependencies, no network.

## Output — do NOT commit data

The scripts generate a large local dataset (~535 MB: photos, PDFs, JSON). **Only
code lives in this repo.** `output/`, `data/`, `*.pdf`, and the dataset
directory are `.gitignore`d. Never commit extracted data.

### Output path

All five scripts resolve the dataset directory identically, via
`nc/_common.py`: `--out DIR`, else `$OPENANGLER_OUT`, else the historical
default `~/onedrive/fishing/nc-fishing-guide-data`. Keep that precedence and
that default — the default is what stops existing runs breaking. Do not add
any other real local path, and do not add references to external, private, or
proprietary projects.

### Provenance tiers

Each script declares the provenance/licence tier of everything it writes
(`artifact_tiers()` in each script) and merges it into the dataset's
`manifest.json` via `_common.record_artifacts()`. Tiers: `federal-public-domain`,
`agency-factual`, `agency-media`, `curated-original`, `personal`. An artifact
that merges tiers must set `mixed` with a per-field `tier_detail` — the helper
refuses to record a multi-tier artifact without one, because a wrong tag is
worse than no tag. If you add an output, tag it. Engineering documentation, not
legal advice.

## Conventions

- Keep scripts runnable as plain `python3 nc/<script>.py` with no install step.
- Stay standard-library only unless there's a strong reason; if you add a
  dependency, update `requirements.txt` and the "no dependencies" claims in the
  READMEs.
- CI byte-compiles (`python -m py_compile nc/*.py`) and runs the unit tests. It
  never runs the extractors themselves, because they hit live public APIs.
- **Never re-run the scraping steps to test a change.** Four of the five scripts
  hammer public agency endpoints (and a full run downloads 357 photos and 158
  PDFs). Factor the pure logic out of the I/O and test it against a fixture in
  `tests/fixtures/`. Only `build_species_kb.py` is local-only and safe to run end
  to end — and even then, write to a scratch `--out` directory, never over a
  live dataset.

## License

MIT — see `LICENSE`. Copyright (c) 2026 OpenAngler contributors.
