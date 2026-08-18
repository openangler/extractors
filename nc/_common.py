#!/usr/bin/env python3
"""
_common.py — the things every NC extractor needs to do identically.

  * Where to write.  add_out_arg() / resolve_out() give all five scripts the
    same `--out DIR` flag and the same `$OPENANGLER_OUT` fallback, so the
    dataset location is picked once and every step agrees on it.

  * What it produced.  record_artifacts() merges the calling script's outputs
    into the dataset-level manifest.json. Scripts read-modify-write, so every
    step adds its own artifacts without clobbering the ones written before it.

Each artifact carries three independent things:

  * **tiers** — where the content came from, and therefore how freely it can be
    redistributed. Several artifacts fuse sources in one file, so a file-level
    tier on them would be a lie by rounding. Those carry a `fields` block that
    tags provenance *per field*, in a selector syntax a consumer can apply
    mechanically (see FIELD_NOTE). The files themselves keep their shape —
    applications read these artifacts directly, so splitting them per tier is
    not an option.
  * **role** — what kind of thing it is: runtime query data, bulk map geometry,
    binary media, or an archive/input kept for reproducibility. Size and
    purpose are a different axis from provenance: the ~103 MB of GeoJSON is
    the same `agency-factual` tier as 3 MB of app-critical JSON. A phone
    bundle needs both axes.
  * **bytes / files** — measured at record time, so a consumer can weigh a
    filtered subset from the manifest alone without walking the dataset.

Standard library only, like the rest of this directory. This is a helper, not
a framework: the scripts stay readable single-purpose tools.
"""

import json
import os
import sys
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
# The only tier that carries an *obligation* rather than a risk: every other tier is
# either freely redistributable or flagged for removal. ODbL is usable — including
# commercially — but conditionally, so a consumer filtering by tier has to be able to
# see it. Folding OpenStreetMap into agency-factual would make the condition invisible.
COMMUNITY = "community-share-alike"

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
    COMMUNITY: "Community-contributed open data under a share-alike licence "
               "(OpenStreetMap, ODbL 1.0). Not an agency source and not public "
               "domain. Usable commercially: displaying it is a Produced Work and "
               "needs attribution only. Redistributing it, or a database derived "
               "from it, is a Derivative Database and must itself be offered under "
               "ODbL.",
}

# ---- roles --------------------------------------------------------------------
#
# What the artifact is *for*, independent of where it came from. Only facts the
# producer actually knows: nothing here guesses at a particular consumer's app.

QUERY = "query"
GEOMETRY = "geometry"
MEDIA = "media"
ARCHIVE = "archive"

ROLES = {
    QUERY: "Structured data a query or recommendation engine reads at runtime. "
           "Small, and the reason the dataset exists.",
    GEOMETRY: "Bulk map geometry (GeoJSON feature collections). Needed to draw "
              "a map, not to answer a query. Large.",
    MEDIA: "Binary creative works — photographs, PDF documents.",
    ARCHIVE: "Kept for reproducibility, or a hand-authored pipeline input, or a "
             "redundant view of another artifact (see derived_from). Not read "
             "at runtime.",
}

MANIFEST_VERSION = 3
MANIFEST_NAME = "manifest.json"

TIER_NOTE = (
    "Each artifact carries the provenance tier(s) of its content and a role. "
    "An artifact whose fields come from more than one tier is marked mixed=true "
    "and carries a `fields` block; treating its tier list as a single file-level "
    "tier is a lie by rounding. These artifacts are read directly by "
    "applications, so they are tagged per field rather than split per tier — "
    "the field selectors are machine-applicable, so a tier-filtered subset can "
    "be produced from this manifest alone."
)

FIELD_NOTE = (
    "A `fields` block tags provenance per field. `records` says where records "
    "live in the document: 'list' (each array element is a record), 'map' (each "
    "object value is a record), 'object' (the document itself is one record — "
    "for a directory artifact, each file in it). A key in `rules` is a dotted "
    "field path relative to a record; list indices are elided, so the rule "
    "`rigs` covers rigs[*].name. A rule matches its own path and everything "
    "beneath it, and the longest matching rule wins, so `usgs` can be federal "
    "while `usgs.locationID` stays agency-factual. Anything unmatched takes "
    "`default`, and is untagged when there is no default. `coverage` says "
    "whether that was verified against a real record from this run: 'complete' "
    "(every field resolved), 'partial' (the fields in `untagged` did not — "
    "treat them as unknown provenance), 'unverified' (not checked). An artifact "
    "with no `fields` block is single-tier throughout."
)

ROLE_NOTE = (
    "Role is orthogonal to tier: size and purpose are a different axis from "
    "provenance. Filtering by tier alone drops the media but keeps every "
    "GeoJSON layer; a runtime/offline subset is role=query, and adding "
    "role=geometry buys offline maps at ~30x the size."
)

RECORD_SHAPES = ("list", "map", "object")


def _stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---- field selectors ----------------------------------------------------------
#
# The whole point of tagging instead of splitting: these two functions are the
# entire consumer-side filter. Keep them boring and total.


def field_tier(fields, path):
    """Provenance tier of one dotted field path in a record, or None.

    A rule matches its own path and everything beneath it; the longest matching
    rule wins. Unmatched paths fall through to `default`.
    """
    best, best_len = None, -1
    for selector, tier in (fields.get("rules") or {}).items():
        if (path == selector or path.startswith(selector + ".")) \
                and len(selector) > best_len:
            best, best_len = tier, len(selector)
    return best if best is not None else fields.get("default")


def field_paths(value, prefix=""):
    """Every dotted field path in a record. List indices are elided.

    A list contributes its elements' paths under the list's own name, so one
    rule covers a whole array of objects.
    """
    out = []
    if isinstance(value, dict):
        for key, sub in value.items():
            path = prefix + str(key)
            out.append(path)
            out.extend(field_paths(sub, path + "."))
    elif isinstance(value, list):
        for item in value:
            out.extend(field_paths(item, prefix))
    return out


def _valid_selector(selector):
    return (isinstance(selector, str) and bool(selector)
            and all(seg for seg in selector.split(".")))


def _check_fields(relpath, fields, tiers):
    """Validate a fields block, resolve coverage, and strip the sample record."""
    shape = fields.get("records")
    if shape not in RECORD_SHAPES:
        raise ValueError(f"{relpath}: fields.records must be one of "
                         f"{list(RECORD_SHAPES)}, got {shape!r}")
    rules = fields.get("rules") or {}
    if not rules:
        raise ValueError(f"{relpath}: fields block needs at least one rule")
    for selector, tier in rules.items():
        if not _valid_selector(selector):
            raise ValueError(f"{relpath}: bad field selector {selector!r} "
                             "(dotted path, no empty segments)")
        if tier not in TIERS:
            raise ValueError(f"{relpath}: unknown tier {tier!r} in fields.rules")
    default = fields.get("default")
    if default is not None and default not in TIERS:
        raise ValueError(f"{relpath}: unknown tier {default!r} in fields.default")

    used = set(rules.values()) | ({default} if default else set())
    if not used <= set(tiers):
        raise ValueError(f"{relpath}: fields use tier(s) "
                         f"{sorted(used - set(tiers))} not declared in tiers")
    if len(tiers) > 1 and used != set(tiers):
        raise ValueError(f"{relpath}: tier(s) {sorted(set(tiers) - used)} are "
                         "declared but no field carries them")

    out = {"records": shape, "rules": dict(rules)}
    if default:
        out["default"] = default

    sample = fields.get("sample")
    if sample is None:
        out["coverage"] = "unverified"
        return out
    untagged = sorted({p for p in field_paths(sample)
                       if field_tier(out, p) is None})
    out["coverage"] = "partial" if untagged else "complete"
    if untagged:
        out["untagged"] = untagged
        print(f"  WARNING {relpath}: {len(untagged)} field(s) have no "
              f"provenance rule: {', '.join(untagged)}", file=sys.stderr,
              flush=True)
    return out


def build_entries(produced_by, artifacts, stamp=None):
    """Validate and normalise {relpath: spec} into manifest artifact entries.

    spec: {"tiers": [...], "role": one of ROLES, "note": str (optional),
           "derived_from": [relpath, ...] (optional),
           "fields": {"records": ..., "rules": {selector: tier},
                      "default": tier (optional),
                      "sample": a record from this run (optional but wanted)}}

    A `fields` block is required when the artifact spans more than one tier.
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
        role = spec.get("role")
        if role not in ROLES:
            raise ValueError(f"{relpath}: role must be one of "
                             f"{sorted(ROLES)}, got {role!r}")
        fields = spec.get("fields")
        if len(tiers) > 1 and not fields:
            raise ValueError(
                f"{relpath}: mixed-tier artifacts must declare a fields block")
        entry = {"produced_by": produced_by, "generated": stamp,
                 "tiers": tiers, "mixed": len(tiers) > 1, "role": role}
        if fields:
            entry["fields"] = _check_fields(relpath, fields, tiers)
        derived = spec.get("derived_from")
        if derived:
            if isinstance(derived, str) or not all(isinstance(p, str)
                                                   for p in derived):
                raise ValueError(f"{relpath}: derived_from must be a list of "
                                 "artifact paths")
            entry["derived_from"] = list(derived)
        if spec.get("note"):
            entry["note"] = spec["note"]
        entries[relpath] = entry
    return entries


# ---- size accounting ----------------------------------------------------------


def measure(out_dir, relpaths):
    """Bytes and file counts per artifact, plus whatever nothing claimed.

    Every file is charged to exactly one artifact — the longest declared path
    that contains it — so `species/reports/index.json` is not also counted
    inside `species/reports/`, and the totals add up to the dataset.
    """
    sizes = {p: 0 for p in relpaths}
    counts = {p: 0 for p in relpaths}
    bases = sorted(((p.rstrip("/"), p) for p in relpaths),
                   key=lambda t: -len(t[0]))
    unclaimed_bytes = unclaimed_files = 0
    for dirpath, _dirs, filenames in os.walk(out_dir):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, out_dir).replace(os.sep, "/")
            if rel == MANIFEST_NAME:
                continue
            try:
                nbytes = os.path.getsize(full)
            except OSError:
                continue
            for base, relpath in bases:
                if rel == base or rel.startswith(base + "/"):
                    sizes[relpath] += nbytes
                    counts[relpath] += 1
                    break
            else:
                unclaimed_bytes += nbytes
                unclaimed_files += 1
    return sizes, counts, unclaimed_bytes, unclaimed_files


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
    manifest["role_glossary"] = ROLES
    manifest["tier_note"] = TIER_NOTE
    manifest["role_note"] = ROLE_NOTE
    manifest["field_note"] = FIELD_NOTE
    manifest.setdefault("artifacts", {}).update(
        build_entries(produced_by, artifacts, stamp))
    manifest["mixed_tier_artifacts"] = sorted(
        p for p, e in manifest["artifacts"].items()
        if isinstance(e, dict) and e.get("mixed"))
    manifest.setdefault("runs", {})[produced_by] = dict(run or {}, generated=stamp)

    os.makedirs(out_dir, exist_ok=True)
    # Sizes are measured, never declared, and re-measured for every artifact on
    # every step — a later step can rewrite what an earlier one produced.
    sizes, counts, extra_bytes, extra_files = measure(
        out_dir, list(manifest["artifacts"]))
    for relpath, entry in manifest["artifacts"].items():
        if isinstance(entry, dict):
            entry["bytes"] = sizes.get(relpath, 0)
            entry["files"] = counts.get(relpath, 0)
    manifest["totals"] = {
        "artifacts": len(manifest["artifacts"]),
        "bytes": sum(sizes.values()) + extra_bytes,
        "files": sum(counts.values()) + extra_files,
        "unclaimed_bytes": extra_bytes,
        "unclaimed_files": extra_files,
    }

    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest
