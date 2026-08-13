"""Output-path resolution and the provenance-tier manifest (_common.py)."""

import json
import os
import tempfile
import unittest

import context                                    # noqa: F401  (sys.path setup)
import _common


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


class TestBuildEntries(unittest.TestCase):
    def test_single_tier_is_not_mixed(self):
        e = _common.build_entries("x.py", {
            "a.json": {"tiers": [_common.AGENCY_FACTUAL]}})["a.json"]
        self.assertEqual(e["tiers"], [_common.AGENCY_FACTUAL])
        self.assertFalse(e["mixed"])
        self.assertNotIn("tier_detail", e)
        self.assertEqual(e["produced_by"], "x.py")

    def test_multiple_tiers_are_flagged_mixed(self):
        e = _common.build_entries("x.py", {"a.json": {
            "tiers": [_common.FEDERAL, _common.AGENCY_FACTUAL],
            "tier_detail": {"usgs": _common.FEDERAL,
                            "name": _common.AGENCY_FACTUAL}}})["a.json"]
        self.assertTrue(e["mixed"])
        self.assertEqual(e["tier_detail"]["usgs"], _common.FEDERAL)

    def test_mixed_without_detail_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": {
                "tiers": [_common.FEDERAL, _common.CURATED]}})

    def test_unknown_tier_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": {"tiers": ["public-ish"]}})
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": {
                "tiers": [_common.FEDERAL, _common.CURATED],
                "tier_detail": {"f": "made-up"}}})

    def test_no_tier_is_rejected(self):
        with self.assertRaises(ValueError):
            _common.build_entries("x.py", {"a.json": {"tiers": []}})


class TestRecordArtifacts(unittest.TestCase):
    def _manifest(self, d):
        with open(os.path.join(d, _common.MANIFEST_NAME)) as f:
            return json.load(f)

    def test_later_steps_merge_instead_of_clobbering(self):
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "extract_nc_fishing.py", {
                "fishing-areas/all-locations.json": {
                    "tiers": [_common.AGENCY_FACTUAL]},
                "fishing-areas/mountains/photos/": {
                    "tiers": [_common.AGENCY_MEDIA]},
            }, run={"total_fishing_areas": 911})
            _common.record_artifacts(d, "enrich_usgs.py", {
                "fishing-areas/enrichment.json": {
                    "tiers": [_common.FEDERAL, _common.AGENCY_FACTUAL],
                    "tier_detail": {"stream_order": _common.FEDERAL,
                                    "locationName": _common.AGENCY_FACTUAL}},
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
                "species/all-species.json": {"tiers": [_common.AGENCY_FACTUAL]},
                "species/reports/": {"tiers": [_common.AGENCY_MEDIA]},
            })
            man = self._manifest(d)
            media = [p for p, e in man["artifacts"].items()
                     if _common.AGENCY_MEDIA in e["tiers"]]
            self.assertEqual(media, ["species/reports/"])

    def test_glossary_covers_every_tier_in_use(self):
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "x.py", {
                "a.json": {"tiers": [_common.CURATED]}})
            man = self._manifest(d)
            for entry in man["artifacts"].values():
                for tier in entry["tiers"]:
                    self.assertIn(tier, man["tier_glossary"])
            self.assertIn("mixed", man["tier_note"])

    def test_rerun_replaces_that_scripts_entry(self):
        with tempfile.TemporaryDirectory() as d:
            _common.record_artifacts(d, "x.py", {
                "a.json": {"tiers": [_common.AGENCY_MEDIA]}})
            _common.record_artifacts(d, "x.py", {
                "a.json": {"tiers": [_common.AGENCY_FACTUAL]}})
            man = self._manifest(d)
            self.assertEqual(man["artifacts"]["a.json"]["tiers"],
                             [_common.AGENCY_FACTUAL])
            self.assertEqual(man["mixed_tier_artifacts"], [])

    def test_unreadable_manifest_does_not_abort_a_run(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, _common.MANIFEST_NAME), "w") as f:
                f.write("{ this is not json")
            man = _common.record_artifacts(d, "x.py", {
                "a.json": {"tiers": [_common.CURATED]}})
            self.assertIn("a.json", man["artifacts"])


if __name__ == "__main__":
    unittest.main()
