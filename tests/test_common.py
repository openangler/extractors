"""Output-path resolution and the provenance manifest (_common.py)."""

import contextlib
import io
import json
import os
import tempfile
import unittest

import context                                    # noqa: F401  (sys.path setup)
import _common


def spec(tiers, role=_common.QUERY, **extra):
    """A minimal valid artifact spec, so tests say only what they mean."""
    return dict({"tiers": list(tiers), "role": role}, **extra)


class TestResolveOut(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop(_common.OUT_ENV, None)

    def tearDown(self):
        os.environ.pop(_common.OUT_ENV, None)
        if self._saved is not None:
            os.environ[_common.OUT_ENV] = self._saved

    def test_default_is_the_historical_path(self):
        self.assertEqual(_common.resolve_out(None),
                         os.path.expanduser(_common.DEFAULT_OUT))

    def test_env_var_overrides_default(self):
        os.environ[_common.OUT_ENV] = "/data/nc-fishing-guide-data"
        self.assertEqual(_common.resolve_out(None), "/data/nc-fishing-guide-data")

    def test_cli_overrides_env(self):
        os.environ[_common.OUT_ENV] = "/data/from-env"
        self.assertEqual(_common.resolve_out("/data/from-cli"), "/data/from-cli")

    def test_empty_env_falls_through_to_default(self):
        os.environ[_common.OUT_ENV] = ""
        self.assertEqual(_common.resolve_out(None),
                         os.path.expanduser(_common.DEFAULT_OUT))

    def test_tilde_and_relative_paths_are_expanded(self):
        self.assertEqual(_common.resolve_out("~/x"),
                         os.path.join(os.path.expanduser("~"), "x"))
        self.assertTrue(os.path.isabs(_common.resolve_out("rel/path")))

    def test_all_five_scripts_expose_the_same_flag(self):
        import argparse
        ap = argparse.ArgumentParser()
        _common.add_out_arg(ap)
        self.assertEqual(ap.parse_args(["--out", "/tmp/x"]).out, "/tmp/x")
        self.assertIsNone(ap.parse_args([]).out)


class TestFieldPaths(unittest.TestCase):
    """Enumerating a record's fields — the input to the coverage check."""

    def test_nested_objects_become_dotted_paths(self):
        self.assertEqual(
            sorted(_common.field_paths({"a": {"b": {"c": 1}}})),
            ["a", "a.b", "a.b.c"])

    def test_list_indices_are_elided_so_one_rule_covers_an_array(self):
        paths = _common.field_paths({"rigs": [{"name": "x"}, {"why": "y"}]})
        self.assertEqual(sorted(set(paths)), ["rigs", "rigs.name", "rigs.why"])

    def test_scalars_and_nulls_are_still_fields(self):
        self.assertEqual(sorted(_common.field_paths({"a": None, "b": 1})),
                         ["a", "b"])

    def test_empty_containers_still_report_themselves(self):
        self.assertEqual(_common.field_paths({"a": [], "b": {}}), ["a", "b"])


class TestFieldTier(unittest.TestCase):
    """The entire consumer-side filter: resolve one field path to a tier."""

    FIELDS = {"rules": {"usgs": _common.FEDERAL,
                        "usgs.locationID": _common.AGENCY_FACTUAL}}

    def test_a_rule_covers_everything_beneath_it(self):
        self.assertEqual(_common.field_tier(self.FIELDS, "usgs.stream_order"),
                         _common.FEDERAL)
        self.assertEqual(_common.field_tier(self.FIELDS, "usgs.nearest_gage.id"),
                         _common.FEDERAL)

    def test_the_longest_matching_rule_wins(self):
        self.assertEqual(_common.field_tier(self.FIELDS, "usgs.locationID"),
                         _common.AGENCY_FACTUAL)

    def test_a_rule_is_not_a_string_prefix_match(self):
        """`usgs` must not claim `usgs_extra`; only `usgs` and `usgs.*`."""
        self.assertIsNone(_common.field_tier(self.FIELDS, "usgs_extra"))

    def test_unmatched_falls_to_default_then_to_none(self):
        self.assertIsNone(_common.field_tier(self.FIELDS, "county"))
        with_default = dict(self.FIELDS, default=_common.AGENCY_FACTUAL)
        self.assertEqual(_common.field_tier(with_default, "county"),
                         _common.AGENCY_FACTUAL)


class TestBuildEntries(unittest.TestCase):
    def test_single_tier_is_not_mixed(self):
        e = _common.build_entries("x.py", {
            "a.json": spec([_common.AGENCY_FACTUAL])})["a.json"]
        self.assertEqual(e["tiers"], [_common.AGENCY_FACTUAL])
        self.assertFalse(e["mixed"])
        self.assertNotIn("fields", e)
        self.assertEqual(e["produced_by"], "x.py")
        self.assertEqual(e["role"], _common.QUERY)

    def test_multiple_tiers_are_flagged_mixed(self):
        e = _common.build_entries("x.py", {"a.json": spec(
            [_common.FEDERAL, _common.AGENCY_FACTUAL],
            fields={"records": "list",
                    "rules": {"usgs": _common.FEDERAL,
                              "name": _common.AGENCY_FACTUAL}})})["a.json"]
        self.assertTrue(e["mixed"])
        self.assertEqual(e["fields"]["rules"]["usgs"], _common.FEDERAL)
        self.assertEqual(e["fields"]["records"], "list")

    def test_mixed_without_a_fields_block_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec(
                [_common.FEDERAL, _common.CURATED])})

    def test_unknown_tier_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec(["public-ish"])})
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec(
                [_common.FEDERAL, _common.CURATED],
                fields={"records": "list", "rules": {"f": "made-up"}})})

    def test_no_tier_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec([])})

    def test_role_is_required_and_checked(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {
                "a.json": {"tiers": [_common.CURATED]}})
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {
                "a.json": spec([_common.CURATED], role="important")})

    def test_a_declared_tier_no_field_carries_is_rejected(self):
        """Drift guard: a tier list that over-claims is as wrong as one that under-claims."""
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec(
                [_common.FEDERAL, _common.CURATED, _common.AGENCY_MEDIA],
                fields={"records": "list",
                        "rules": {"a": _common.FEDERAL, "b": _common.CURATED}})})

    def test_a_field_tier_outside_the_tier_list_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec(
                [_common.FEDERAL, _common.CURATED],
                fields={"records": "list",
                        "rules": {"a": _common.FEDERAL, "b": _common.CURATED,
                                  "c": _common.AGENCY_MEDIA}})})

    def test_bad_selectors_and_shapes_are_rejected(self):
        for bad in ({"records": "array", "rules": {"a": _common.FEDERAL}},
                    {"records": "list", "rules": {}},
                    {"records": "list", "rules": {"a..b": _common.FEDERAL}},
                    {"records": "list", "rules": {"": _common.FEDERAL}}):
            with self.assertRaises(ValueError, msg=bad):
                _common.build_entries("x.py", {"a.json": spec(
                    [_common.FEDERAL], fields=bad)})

    def test_coverage_is_verified_against_a_real_record(self):
        e = _common.build_entries("x.py", {"a.json": spec(
            [_common.FEDERAL, _common.AGENCY_FACTUAL],
            fields={"records": "map",
                    "rules": {"usgs": _common.FEDERAL,
                              "name": _common.AGENCY_FACTUAL},
                    "sample": {"name": "x", "usgs": {"order": 3}}})})["a.json"]
        self.assertEqual(e["fields"]["coverage"], "complete")
        self.assertNotIn("untagged", e["fields"])
        self.assertNotIn("sample", e["fields"])       # never copied into the manifest

    def test_an_untagged_field_is_named_not_silently_swallowed(self):
        warning = io.StringIO()
        with contextlib.redirect_stderr(warning):
            e = _common.build_entries("x.py", {"a.json": spec(
                [_common.FEDERAL, _common.AGENCY_FACTUAL],
                fields={"records": "map",
                        "rules": {"usgs": _common.FEDERAL,
                                  "name": _common.AGENCY_FACTUAL},
                        "sample": {"name": "x", "usgs": {},
                                   "surprise": 1}})})["a.json"]
        self.assertEqual(e["fields"]["coverage"], "partial")
        self.assertEqual(e["fields"]["untagged"], ["surprise"])
        # a run that silently drops a field is exactly the failure mode this
        # replaces, so it has to be loud as well as recorded
        self.assertIn("surprise", warning.getvalue())

    def test_no_sample_means_unverified_not_complete(self):
        e = _common.build_entries("x.py", {"a.json": spec(
            [_common.FEDERAL, _common.AGENCY_FACTUAL],
            fields={"records": "map",
                    "rules": {"usgs": _common.FEDERAL,
                              "name": _common.AGENCY_FACTUAL}})})["a.json"]
        self.assertEqual(e["fields"]["coverage"], "unverified")

    def test_derived_from_is_recorded_as_a_list(self):
        e = _common.build_entries("x.py", {"a.json": spec(
            [_common.AGENCY_FACTUAL], derived_from=["b.json"])})["a.json"]
        self.assertEqual(e["derived_from"], ["b.json"])
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": spec(
                [_common.AGENCY_FACTUAL], derived_from="b.json")})


class TestMeasure(unittest.TestCase):
    def _dataset(self, d, files):
        for rel, body in files.items():
            path = os.path.join(d, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(body)

    def test_a_file_is_charged_to_the_longest_declared_path(self):
        """`species/reports/index.json` must not also be counted in `species/reports/`."""
        with tempfile.TemporaryDirectory() as d:
            self._dataset(d, {"species/reports/a.pdf": "x" * 100,
                              "species/reports/index.json": "y" * 10})
            sizes, counts, extra_b, extra_f = _common.measure(
                d, ["species/reports/", "species/reports/index.json"])
            self.assertEqual(sizes["species/reports/"], 100)
            self.assertEqual(counts["species/reports/"], 1)
            self.assertEqual(sizes["species/reports/index.json"], 10)
            self.assertEqual((extra_b, extra_f), (0, 0))

    def test_files_no_artifact_claims_are_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as d:
            self._dataset(d, {"a.json": "x" * 5, "README.md": "y" * 7})
            _sizes, _counts, extra_b, extra_f = _common.measure(d, ["a.json"])
            self.assertEqual((extra_b, extra_f), (7, 1))

    def test_a_declared_path_that_was_not_written_weighs_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            sizes, counts, _b, _f = _common.measure(d, ["missing.json"])
            self.assertEqual((sizes["missing.json"], counts["missing.json"]), (0, 0))


class TestRecordArtifacts(unittest.TestCase):
    def _manifest(self, d):
        with open(os.path.join(d, _common.MANIFEST_NAME)) as f:
            return json.load(f)

    def test_later_steps_merge_instead_of_clobbering(self):
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "extract_nc_fishing.py", {
                "fishing-areas/all-locations.json": spec([_common.AGENCY_FACTUAL]),
                "fishing-areas/mountains/photos/": spec([_common.AGENCY_MEDIA],
                                                        role=_common.MEDIA),
            }, run={"total_fishing_areas": 911})
            _common.record_artifacts(d, "enrich_usgs.py", {
                "fishing-areas/enrichment.json": spec(
                    [_common.FEDERAL, _common.AGENCY_FACTUAL],
                    fields={"records": "map",
                            "rules": {"stream_order": _common.FEDERAL,
                                      "locationName": _common.AGENCY_FACTUAL}}),
            }, run={"sites_enriched": 911})

            man = self._manifest(d)
            self.assertEqual(sorted(man["artifacts"]), [
                "fishing-areas/all-locations.json",
                "fishing-areas/enrichment.json",
                "fishing-areas/mountains/photos/"])
            self.assertEqual(sorted(man["runs"]),
                             ["enrich_usgs.py", "extract_nc_fishing.py"])
            self.assertEqual(man["runs"]["extract_nc_fishing.py"]
                             ["total_fishing_areas"], 911)
            self.assertEqual(man["mixed_tier_artifacts"],
                             ["fishing-areas/enrichment.json"])
            self.assertEqual(man["manifest_version"], _common.MANIFEST_VERSION)

    def test_media_tier_is_discoverable_for_the_offline_subset(self):
        """The point of the tags: find every agency-media path and drop it."""
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "species_extract.py", {
                "species/all-species.json": spec([_common.AGENCY_FACTUAL]),
                "species/reports/": spec([_common.AGENCY_MEDIA],
                                         role=_common.MEDIA),
            })
            man = self._manifest(d)
            media = [p for p, e in man["artifacts"].items()
                     if _common.AGENCY_MEDIA in e["tiers"]]
            self.assertEqual(media, ["species/reports/"])

    def test_role_separates_bulk_geometry_from_the_data_a_query_reads(self):
        """Same tier, wildly different size and purpose — issue #3's second axis."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "layer.geojson"), "w") as f:
                f.write("x" * 5000)
            with open(os.path.join(d, "small.json"), "w") as f:
                f.write("y" * 50)
            man = _common.record_artifacts(d, "extract_nc_fishing.py", {
                "layer.geojson": spec([_common.AGENCY_FACTUAL],
                                      role=_common.GEOMETRY),
                "small.json": spec([_common.AGENCY_FACTUAL]),
            })
            self.assertEqual({e["tiers"][0] for e in man["artifacts"].values()},
                             {_common.AGENCY_FACTUAL})
            by_role = {e["role"]: e["bytes"] for e in man["artifacts"].values()}
            self.assertEqual(by_role, {_common.GEOMETRY: 5000, _common.QUERY: 50})

    def test_sizes_are_measured_and_totalled(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "photos"))
            for i in range(3):
                with open(os.path.join(d, "photos", f"{i}.jpg"), "w") as f:
                    f.write("x" * 100)
            with open(os.path.join(d, "README.md"), "w") as f:
                f.write("z" * 9)
            man = _common.record_artifacts(d, "x.py", {
                "photos/": spec([_common.AGENCY_MEDIA], role=_common.MEDIA)})
            self.assertEqual(man["artifacts"]["photos/"]["bytes"], 300)
            self.assertEqual(man["artifacts"]["photos/"]["files"], 3)
            self.assertEqual(man["totals"]["bytes"], 309)
            self.assertEqual(man["totals"]["unclaimed_bytes"], 9)

    def test_a_later_step_refreshes_an_earlier_steps_size(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.json"), "w") as f:
                f.write("x" * 10)
            _common.record_artifacts(d, "one.py", {
                "a.json": spec([_common.AGENCY_FACTUAL])})
            with open(os.path.join(d, "a.json"), "w") as f:
                f.write("x" * 40)
            man = _common.record_artifacts(d, "two.py", {
                "b.json": spec([_common.AGENCY_FACTUAL])})
            self.assertEqual(man["artifacts"]["a.json"]["bytes"], 40)

    def test_glossary_covers_every_tier_and_role_in_use(self):
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "x.py", {
                "a.json": spec([_common.CURATED], role=_common.ARCHIVE)})
            man = self._manifest(d)
            for entry in man["artifacts"].values():
                for tier in entry["tiers"]:
                    self.assertIn(tier, man["tier_glossary"])
                self.assertIn(entry["role"], man["role_glossary"])
            self.assertIn("mixed", man["tier_note"])
            self.assertIn("longest matching rule wins", man["field_note"])

    def test_rerun_replaces_that_scripts_entry(self):
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "x.py", {
                "a.json": spec([_common.AGENCY_MEDIA], role=_common.MEDIA)})
            _common.record_artifacts(d, "x.py", {
                "a.json": spec([_common.AGENCY_FACTUAL])})
            man = self._manifest(d)
            self.assertEqual(man["artifacts"]["a.json"]["tiers"],
                             [_common.AGENCY_FACTUAL])
            self.assertEqual(man["mixed_tier_artifacts"], [])

    def test_unreadable_manifest_does_not_abort_a_run(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, _common.MANIFEST_NAME), "w") as f:
                f.write("{ this is not json")
            man = _common.record_artifacts(d, "x.py", {
                "a.json": spec([_common.CURATED])})
            self.assertIn("a.json", man["artifacts"])


if __name__ == "__main__":
    unittest.main()
