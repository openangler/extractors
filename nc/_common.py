#!/usr/bin/env python3
"""
_common.py — the two things every NC extractor needs to do identically.

  * Where to write.  add_out_arg() / resolve_out() give all five scripts the
    same `--out DIR` flag and the same `$OPENANGLER_OUT` fallback, so the
    dataset location is picked once and every step agrees on it.

  * What it produced.  record_artifacts() merges the calling script's outputs
    into the dataset-level manifest.json, each tagged with a provenance and
    licence tier. Scripts read-modify-write, so every step adds its own
    artifacts without clobbering the ones written before it.

Standard library only, like the rest of this directory. This is a helper, not
a framework: the scripts stay readable single-purpose tools.
"""

import json
import os
import time

# ---- output path --------------------------------------------------------------

DEFAULT_OUT = "~/onedrive/fishing/nc-fishing-guide-data"
OUT_ENV = "OPENANGLER_OUT"


def add_out_arg(parser):
    """Add the shared --out flag. Same flag, same help, in all five scripts."""
    parser.add_argument(
        "--out", metavar="DIR", default=None,
        help=f"dataset output directory (default: ${OUT_ENV} if set, "
             f"else {DEFAULT_OUT})")
    return parser


def resolve_out(cli_value=None):
    """--out wins, then $OPENANGLER_OUT, then the historical default path."""
    value = cli_value or os.environ.get(OUT_ENV) or DEFAULT_OUT
    return os.path.abspath(os.path.expanduser(value))


# ---- provenance / licence tiers -----------------------------------------------
#
# Tier vocabulary per raibid-fish ADR-0007. "agency-" means a state
# wildlife/natural-resources agency, so the vocabulary survives OpenAngler's
# expansion to other states. Engineering documentation, not legal advice.

FEDERAL = "federal-public-domain"
AGENCY_FACTUAL = "agency-factual"
AGENCY_MEDIA = "agency-media"
CURATED = "curated-original"
PERSONAL = "personal"

TIERS = {
    FEDERAL: "Work of the US federal government, 17 U.S.C. §105 — "
             "USGS 3DEP / NHDPlus HR / NWIS.",
    AGENCY_FACTUAL: "Facts extracted from a state agency source "
                    "(coordinates, species-per-water, amenities, "
                    "regulation classes). Facts are not copyrightable in the US.",
    AGENCY_MEDIA: "Creative works published by a state agency — site photos, "
                  "PDFs. Highest-risk content to redistribute, and the bulk of "
                  "the dataset by size; drop this tier for an offline/phone subset.",
    CURATED: "Hand-authored by the dataset maintainer (curated species files, "
             "plain-language regulation summaries, scoring weights).",
    PERSONAL: "Private user data (catch logs, session telemetry). Never "
              "produced by these extractors.",
}

TIER_NOTE = (
    "Each artifact carries the provenance tier(s) of its content. An artifact "
    "whose fields come from more than one tier is marked mixed=true and carries "
    "tier_detail; treating a mixed artifact's tier list as a single file-level "
    "tier is a lie by rounding. Splitting mixed artifacts is tracked as "
    "openangler/extractors#3."
)

MANIFEST_VERSION = 2
MANIFEST_NAME = "manifest.json"


def _stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_entries(produced_by, artifacts, stamp=None):
    """Validate and normalise {relpath: spec} into manifest artifact entries.

    spec: {"tiers": [...], "note": str (optional),
           "tier_detail": {field-or-block: tier} (required when >1 tier)}
    """
    stamp = stamp or _stamp()
    entries = {}
    for relpath, spec in artifacts.items():
        tiers = list(spec["tiers"])
        if not tiers:
            raise ValueError(f"{relpath}: at least one tier is required")
        for t in tiers:
            if t not in TIERS:
                raise ValueError(f"{relpath}: unknown tier {t!r}")
        detail = spec.get("tier_detail") or {}
        if len(tiers) > 1 and not detail:
            raise ValueError(
                f"{relpath}: mixed-tier artifacts must declare tier_detail")
        for t in detail.values():
            if t not in TIERS:
                raise ValueError(f"{relpath}: unknown tier {t!r} in tier_detail")
        entry = {"produced_by": produced_by, "generated": stamp,
                 "tiers": tiers, "mixed": len(tiers) > 1}
        if detail:
            entry["tier_detail"] = dict(detail)
        if spec.get("note"):
            entry["note"] = spec["note"]
        entries[relpath] = entry
    return entries


def record_artifacts(out_dir, produced_by, artifacts, run=None):
    """Merge this script's artifacts + run summary into <out_dir>/manifest.json."""
    path = os.path.join(out_dir, MANIFEST_NAME)
    manifest = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            manifest = {}                     # unreadable manifest: start fresh
    if not isinstance(manifest, dict):
        manifest = {}

    stamp = _stamp()
    manifest["manifest_version"] = MANIFEST_VERSION
    manifest["tier_glossary"] = TIERS
    manifest["tier_note"] = TIER_NOTE
    manifest.setdefault("artifacts", {}).update(
        build_entries(produced_by, artifacts, stamp))
    manifest["mixed_tier_artifacts"] = sorted(
        p for p, e in manifest["artifacts"].items()
        if isinstance(e, dict) and e.get("mixed"))
    manifest.setdefault("runs", {})[produced_by] = dict(run or {}, generated=stamp)

    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest
