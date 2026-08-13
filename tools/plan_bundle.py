#!/usr/bin/env python3
"""
plan_bundle.py — build a tier- and role-filtered subset of a dataset from its
manifest.json, without knowing anything about the dataset.

This is the consumer side of the provenance contract, and the proof that the
contract is machine-applicable: everything below reads `manifest.json` and
nothing else. It never needs to know that `usgs.*` is federal, that photos live
under `fishing-areas/*/photos/`, or that `all-species-knowledge.json` is a map
of species. The manifest says all of it.

    # what a phone needs: runtime data, no state-agency creative works
    python3 tools/plan_bundle.py /data/nc-fishing-guide-data \
        --drop-tiers agency-media --roles query

    # same, plus offline map geometry
    python3 tools/plan_bundle.py /data/nc-fishing-guide-data \
        --drop-tiers agency-media --roles query,geometry

    # licence-clean full dataset: drop the media tier, keep every role
    python3 tools/plan_bundle.py /data/nc-fishing-guide-data \
        --drop-tiers agency-media

Add `--build DIR` to materialise the subset. Artifacts that fuse tiers in one
file are not dropped and not split — their disallowed fields are stripped, per
the manifest's field rules, so the file keeps the shape its consumers expect.

Standard library only. Read-only on the source dataset.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nc"))

# The manifest contract lives in nc/_common.py, which is also what writes it —
# one implementation of the field-selector rules, not two. When a second state
# lands, _common.py graduates to a shared module and this import gets shorter.
import _common                                        # noqa: E402


def load_manifest(target):
    """Accept a dataset directory or a manifest.json path; return (dir, manifest)."""
    if os.path.isdir(target):
        base, path = target, os.path.join(target, _common.MANIFEST_NAME)
    else:
        base, path = os.path.dirname(target) or ".", target
    with open(path) as f:
        manifest = json.load(f)
    version = manifest.get("manifest_version", 0)
    if version < 3:
        sys.exit(f"{path}: manifest_version {version} has no per-field "
                 "provenance or roles; re-run the extractors to regenerate it")
    return base, manifest


# ---- filtering ----------------------------------------------------------------


def classify(entry, tiers, roles):
    """(included, reason) for one artifact under an allow-list."""
    if entry.get("role") not in roles:
        return False, "role"
    if not set(entry.get("tiers", [])) & tiers:
        return False, "tier"
    return True, None


def strip_plan(entry, tiers):
    """Which field selectors an included artifact loses, or None if it keeps all."""
    fields = entry.get("fields")
    if not fields:
        return None
    drop = sorted(sel for sel, tier in fields["rules"].items() if tier not in tiers)
    default = fields.get("default")
    drops_default = bool(default) and default not in tiers
    untagged = fields.get("untagged") or []
    if not drop and not drops_default and not untagged:
        return None
    return {"records": fields["records"], "drop": drop,
            "drops_unmatched": drops_default or not default,
            "untagged": untagged}


def filter_value(value, path, fields, tiers):
    """Drop every field whose tier is not allowed. Returns (value, keep)."""
    if isinstance(value, dict):
        out = {}
        for key, sub in value.items():
            child = f"{path}.{key}" if path else str(key)
            kept, keep = filter_value(sub, child, fields, tiers)
            if keep:
                out[key] = kept
        return out, bool(out) or _allowed(fields, path, tiers)
    if isinstance(value, list):
        out, any_kept = [], False
        for item in value:
            kept, keep = filter_value(item, path, fields, tiers)
            if keep:
                out.append(kept)
                any_kept = True
        return out, any_kept or _allowed(fields, path, tiers)
    return value, _allowed(fields, path, tiers)


def _allowed(fields, path, tiers):
    """A record's root is always allowed; a field is allowed if its tier is."""
    return True if not path else _common.field_tier(fields, path) in tiers


def filter_document(doc, fields, tiers):
    """Apply the field rules to a whole document, per its `records` shape."""
    shape = fields["records"]
    if shape == "list":
        return [filter_value(r, "", fields, tiers)[0] for r in doc]
    if shape == "map":
        return {k: filter_value(r, "", fields, tiers)[0] for k, r in doc.items()}
    return filter_value(doc, "", fields, tiers)[0]


# ---- building -----------------------------------------------------------------


def owner_index(artifacts):
    """Longest-declared-path-wins index, the same rule the manifest measures by."""
    return sorted(((p.rstrip("/"), p) for p in artifacts), key=lambda t: -len(t[0]))


def owner_of(rel, owners):
    for base, relpath in owners:
        if rel == base or rel.startswith(base + "/"):
            return relpath
    return None


def build(base, manifest, included, tiers, dest):
    """Materialise the subset into `dest`. Reads `base`, writes only `dest`."""
    if os.path.exists(dest) and os.listdir(dest):
        sys.exit(f"{dest}: refusing to build into a non-empty directory")
    owners = owner_index(manifest["artifacts"])
    copied = stripped = 0
    for dirpath, _dirs, names in os.walk(base):
        for name in names:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, base).replace(os.sep, "/")
            if rel == _common.MANIFEST_NAME:
                continue
            relpath = owner_of(rel, owners)
            if relpath is None or relpath not in included:
                continue
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            fields = manifest["artifacts"][relpath].get("fields")
            if fields and strip_plan(manifest["artifacts"][relpath], tiers):
                with open(src) as f:
                    doc = json.load(f)
                with open(out, "w") as f:
                    json.dump(filter_document(doc, fields, tiers), f, indent=2)
                stripped += 1
            else:
                shutil.copy2(src, out)
            copied += 1

    sub = dict(manifest)
    sub["artifacts"] = {p: e for p, e in manifest["artifacts"].items()
                        if p in included}
    sub["mixed_tier_artifacts"] = sorted(
        p for p, e in sub["artifacts"].items() if e.get("mixed"))
    sub["bundle"] = {"source_manifest_version": manifest["manifest_version"],
                     "tiers": sorted(tiers),
                     "roles": sorted({e["role"] for e in sub["artifacts"].values()})}
    with open(os.path.join(dest, _common.MANIFEST_NAME), "w") as f:
        json.dump(sub, f, indent=2)
    return copied, stripped


# ---- reporting ----------------------------------------------------------------


def mb(n):
    return f"{n / 1_000_000:>9,.1f} MB"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.strip().split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", help="dataset directory, or a manifest.json")
    ap.add_argument("--tiers", help="comma-separated allow-list "
                                    "(default: every tier in the glossary)")
    ap.add_argument("--drop-tiers", help="comma-separated deny-list, applied to "
                                         "the glossary")
    ap.add_argument("--roles", help="comma-separated allow-list "
                                    "(default: every role in the glossary)")
    ap.add_argument("--build", metavar="DIR", help="materialise the subset")
    ap.add_argument("--json", action="store_true", help="emit the plan as JSON")
    a = ap.parse_args()

    base, manifest = load_manifest(a.dataset)
    artifacts = manifest["artifacts"]

    all_tiers = set(manifest.get("tier_glossary") or _common.TIERS)
    all_roles = set(manifest.get("role_glossary") or _common.ROLES)
    tiers = set(a.tiers.split(",")) if a.tiers else set(all_tiers)
    if a.drop_tiers:
        tiers -= set(a.drop_tiers.split(","))
    roles = set(a.roles.split(",")) if a.roles else set(all_roles)
    for name, chosen, known in (("tier", tiers, all_tiers),
                                ("role", roles, all_roles)):
        unknown = chosen - known
        if unknown:
            sys.exit(f"unknown {name}(s): {', '.join(sorted(unknown))} "
                     f"(known: {', '.join(sorted(known))})")

    included, excluded = {}, {}
    for relpath, entry in sorted(artifacts.items()):
        keep, why = classify(entry, tiers, roles)
        (included if keep else excluded)[relpath] = (entry, why)

    plan = {
        "dataset": base,
        "tiers": sorted(tiers), "roles": sorted(roles),
        "total_bytes": manifest.get("totals", {}).get("bytes"),
        "included": [
            {"path": p, "bytes": e.get("bytes", 0), "role": e["role"],
             "tiers": e["tiers"], "strip": strip_plan(e, tiers)}
            for p, (e, _) in included.items()],
        "excluded": [
            {"path": p, "bytes": e.get("bytes", 0), "role": e["role"],
             "tiers": e["tiers"], "reason": why}
            for p, (e, why) in excluded.items()],
    }
    plan["included_bytes"] = sum(x["bytes"] for x in plan["included"])
    plan["excluded_bytes"] = sum(x["bytes"] for x in plan["excluded"])

    if a.json:
        print(json.dumps(plan, indent=2))
    else:
        report(plan, manifest)

    if a.build:
        copied, edited = build(base, manifest, set(included), tiers, a.build)
        print(f"\nBuilt {a.build}: {copied} file(s), {edited} rewritten to drop "
              "disallowed fields.")


def report(plan, manifest):
    totals = manifest.get("totals", {})
    print(f"Dataset   {plan['dataset']}")
    print(f"Manifest  version {manifest['manifest_version']}, "
          f"{totals.get('artifacts', '?')} artifacts, "
          f"{mb(totals.get('bytes', 0)).strip()} "
          f"({mb(totals.get('unclaimed_bytes', 0)).strip()} claimed by no "
          "artifact)")
    print(f"Keeping   tiers: {', '.join(plan['tiers'])}")
    print(f"          roles: {', '.join(plan['roles'])}")

    print(f"\nINCLUDED  {len(plan['included'])} artifacts, "
          f"{mb(plan['included_bytes']).strip()}")
    for x in sorted(plan["included"], key=lambda x: -x["bytes"]):
        mark = " *" if x["strip"] else "  "
        print(f"  {mb(x['bytes'])} {x['role']:<9}{mark} {x['path']}")

    print(f"\nEXCLUDED  {len(plan['excluded'])} artifacts, "
          f"{mb(plan['excluded_bytes']).strip()}")
    for x in sorted(plan["excluded"], key=lambda x: -x["bytes"]):
        why = ("role " + x["role"] if x["reason"] == "role"
               else "tier " + ", ".join(x["tiers"]))
        print(f"  {mb(x['bytes'])} {x['role']:<9}  {x['path']}  [{why}]")

    strips = [x for x in plan["included"] if x["strip"]]
    if strips:
        print("\n* MIXED-TIER ARTIFACTS KEPT, FIELDS STRIPPED")
        print("  These fuse tiers in one file and are read directly by "
              "applications, so\n  they are filtered per field instead of "
              "split or dropped:")
        for x in strips:
            s = x["strip"]
            print(f"    {x['path']}  (records: {s['records']})")
            if s["drop"]:
                print(f"      drop: {', '.join(s['drop'])}")
            if s["drops_unmatched"]:
                print("      drop: any field matching no rule")
            if s["untagged"]:
                print(f"      NOTE untagged in this dataset: "
                      f"{', '.join(s['untagged'])}")

    unverified = [x["path"] for x in plan["included"]
                  if (manifest["artifacts"][x["path"]].get("fields") or {})
                  .get("coverage") not in (None, "complete")]
    if unverified:
        print("\n! field coverage not verified complete for: "
              + ", ".join(unverified))


if __name__ == "__main__":
    main()
