"""plan_bundle.py — the consumer side of the manifest contract.

The test that matters for issue #3: a subset is assembled from `manifest.json`
alone. Nothing below tells the tool which field came from where, that photos
are media, or that `all-species-knowledge.json` is a map of species — it reads
that out of the manifest the extractors wrote.
"""

import json
import os
import tempfile
import unittest

import context                                    # noqa: F401  (sys.path setup)
import _common
import plan_bundle


# A miniature dataset with the same shapes as the real one: a plain query file,
# a big geometry layer, a media directory, a redundant view, and two mixed
# artifacts (a list-of-records and a directory of single-record files).
KB_RECORD = {"slug": "brook-trout", "name": "Brook Trout",
             "baits_ranked": ["worm"], "ncwrc_fishing_tips": "fish it slow",
             "habitat_envelope": {"ranges": {"stream_order": {"p10": 1}},
                                  "derived_from": "USGS reach attributes"}}
REACH = {"stream_name": "Cranberry Creek", "wrc_class": "Hatchery Supported",
         "regulation_summary": "Any bait or lure.", "elevation_m": 812.0}


def dataset(base):
    """Write the files, then record them exactly as the extractors would."""
    def write(rel, body):
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(body if isinstance(body, str) else json.dumps(body))

    write("fishing-areas/all-locations.json", [{"locationID": 1}])
    write("fishing-areas/mountains/locations.json", [{"locationID": 1}])
    write("fishing-areas/mountains/photos/1.jpg", "J" * 4000)
    write("reference-layers/county-boundaries.geojson", "G" * 9000)
    write("trout-waters/pmtw-reaches.json", [REACH, dict(REACH, county="Avery")])
    write("species-knowledge/kb/brook-trout.json", KB_RECORD)
    write("README.md", "not an artifact")

    _common.record_artifacts(base, "extract_nc_fishing.py", {
        "fishing-areas/all-locations.json": {
            "tiers": [_common.AGENCY_FACTUAL], "role": _common.QUERY},
        "fishing-areas/mountains/locations.json": {
            "tiers": [_common.AGENCY_FACTUAL], "role": _common.ARCHIVE,
            "derived_from": ["fishing-areas/all-locations.json"]},
        "fishing-areas/mountains/photos/": {
            "tiers": [_common.AGENCY_MEDIA], "role": _common.MEDIA},
        "reference-layers/county-boundaries.geojson": {
            "tiers": [_common.AGENCY_FACTUAL], "role": _common.GEOMETRY},
    })
    _common.record_artifacts(base, "build_pmtw_layer.py", {
        "trout-waters/pmtw-reaches.json": {
            "tiers": [_common.AGENCY_FACTUAL, _common.CURATED, _common.FEDERAL],
            "role": _common.QUERY,
            "fields": {"records": "list", "sample": [REACH], "rules": {
                "stream_name": _common.AGENCY_FACTUAL,
                "wrc_class": _common.AGENCY_FACTUAL,
                "county": _common.AGENCY_FACTUAL,
                "regulation_summary": _common.CURATED,
                "elevation_m": _common.FEDERAL}}},
    })
    _common.record_artifacts(base, "build_species_kb.py", {
        "species-knowledge/kb/": {
            "tiers": [_common.CURATED, _common.AGENCY_FACTUAL, _common.FEDERAL],
            "role": _common.QUERY,
            "fields": {"records": "object", "sample": KB_RECORD, "rules": {
                "slug": _common.AGENCY_FACTUAL,
                "name": _common.AGENCY_FACTUAL,
                "ncwrc_fishing_tips": _common.AGENCY_FACTUAL,
                "baits_ranked": _common.CURATED,
                "habitat_envelope": _common.FEDERAL,
                "habitat_envelope.derived_from": _common.CURATED}}},
    })


class BundleTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        dataset(self.base)
        _, self.manifest = plan_bundle.load_manifest(self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def select(self, tiers, roles):
        return {p for p, e in self.manifest["artifacts"].items()
                if plan_bundle.classify(e, set(tiers), set(roles))[0]}

    def weigh(self, paths):
        return sum(self.manifest["artifacts"][p]["bytes"] for p in paths)


class TestSelection(BundleTestCase):
    ALL_TIERS = set(_common.TIERS)
    ALL_ROLES = set(_common.ROLES)

    def test_dropping_the_media_tier_keeps_everything_else(self):
        kept = self.select(self.ALL_TIERS - {_common.AGENCY_MEDIA}, self.ALL_ROLES)
        self.assertNotIn("fishing-areas/mountains/photos/", kept)
        self.assertIn("reference-layers/county-boundaries.geojson", kept)
        self.assertEqual(len(kept), len(self.manifest["artifacts"]) - 1)

    def test_tier_alone_leaves_the_bulk_geometry_in_the_bundle(self):
        """Issue #3's point: the two axes are independent."""
        by_tier = self.select(self.ALL_TIERS - {_common.AGENCY_MEDIA},
                              self.ALL_ROLES)
        by_both = self.select(self.ALL_TIERS - {_common.AGENCY_MEDIA},
                              {_common.QUERY})
        self.assertGreater(self.weigh(by_tier), 9000)
        self.assertLess(self.weigh(by_both), 1000)
        self.assertIn("reference-layers/county-boundaries.geojson", by_tier)
        self.assertNotIn("reference-layers/county-boundaries.geojson", by_both)

    def test_a_mixed_artifact_is_kept_and_filtered_never_dropped(self):
        kept = self.select(self.ALL_TIERS - {_common.CURATED}, self.ALL_ROLES)
        self.assertIn("trout-waters/pmtw-reaches.json", kept)
        self.assertIn("species-knowledge/kb/", kept)

    def test_the_reason_an_artifact_was_dropped_is_reported(self):
        photos = self.manifest["artifacts"]["fishing-areas/mountains/photos/"]
        self.assertEqual(
            plan_bundle.classify(photos, self.ALL_TIERS, {_common.QUERY}),
            (False, "role"))
        self.assertEqual(
            plan_bundle.classify(photos, self.ALL_TIERS - {_common.AGENCY_MEDIA},
                                 self.ALL_ROLES),
            (False, "tier"))

    def test_an_older_manifest_is_refused_rather_than_misread(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "manifest.json"), "w") as f:
                json.dump({"manifest_version": 2, "artifacts": {}}, f)
            with self.assertRaises(SystemExit):
                plan_bundle.load_manifest(d)


class TestFieldStripping(BundleTestCase):
    ALLOWED = set(_common.TIERS) - {_common.CURATED, _common.AGENCY_MEDIA}

    def test_the_plan_names_the_selectors_that_go(self):
        entry = self.manifest["artifacts"]["trout-waters/pmtw-reaches.json"]
        plan = plan_bundle.strip_plan(entry, self.ALLOWED)
        self.assertEqual(plan["drop"], ["regulation_summary"])
        self.assertEqual(plan["records"], "list")

    def test_nothing_is_stripped_when_every_tier_is_allowed(self):
        entry = self.manifest["artifacts"]["trout-waters/pmtw-reaches.json"]
        self.assertIsNone(plan_bundle.strip_plan(entry, set(_common.TIERS)))

    def test_a_list_document_keeps_its_shape_minus_the_dropped_field(self):
        entry = self.manifest["artifacts"]["trout-waters/pmtw-reaches.json"]
        with open(os.path.join(self.base, "trout-waters/pmtw-reaches.json")) as f:
            doc = json.load(f)
        out = plan_bundle.filter_document(doc, entry["fields"], self.ALLOWED)
        self.assertEqual(len(out), 2)
        self.assertNotIn("regulation_summary", out[0])
        self.assertEqual(out[0]["stream_name"], "Cranberry Creek")
        self.assertEqual(out[0]["elevation_m"], 812.0)

    def test_a_nested_override_survives_its_parent_being_dropped(self):
        """habitat_envelope is federal; the sentence inside it is not."""
        entry = self.manifest["artifacts"]["species-knowledge/kb/"]
        out = plan_bundle.filter_document(KB_RECORD, entry["fields"], self.ALLOWED)
        self.assertIn("ranges", out["habitat_envelope"])
        self.assertNotIn("derived_from", out["habitat_envelope"])
        self.assertNotIn("baits_ranked", out)
        self.assertEqual(out["name"], "Brook Trout")

    def test_the_reverse_case_a_kept_field_under_a_dropped_parent(self):
        federal_only = {_common.FEDERAL}
        entry = self.manifest["artifacts"]["species-knowledge/kb/"]
        out = plan_bundle.filter_document(KB_RECORD, entry["fields"], federal_only)
        self.assertEqual(list(out), ["habitat_envelope"])
        self.assertEqual(out["habitat_envelope"], {"ranges": {"stream_order":
                                                             {"p10": 1}}})


class TestBuild(BundleTestCase):
    def setUp(self):
        super().setUp()
        # a home for the bundle outside the dataset, so building it cannot
        # change what the dataset weighs
        self._out = tempfile.TemporaryDirectory()
        self.addCleanup(self._out.cleanup)

    def _build(self, tiers, roles):
        dest = os.path.join(self._out.name, "bundle")
        included = self.select(tiers, roles)
        plan_bundle.build(self.base, self.manifest, included, set(tiers), dest)
        return dest, included

    def test_a_phone_bundle_is_assembled_from_the_manifest_alone(self):
        dest, _ = self._build(set(_common.TIERS) - {_common.AGENCY_MEDIA},
                              {_common.QUERY})
        got = sorted(os.path.relpath(os.path.join(dp, n), dest)
                     for dp, _d, ns in os.walk(dest) for n in ns)
        self.assertEqual(got, ["fishing-areas/all-locations.json",
                               "manifest.json",
                               "species-knowledge/kb/brook-trout.json",
                               "trout-waters/pmtw-reaches.json"])

    def test_files_no_artifact_claims_are_left_behind(self):
        dest, _ = self._build(set(_common.TIERS), set(_common.ROLES))
        self.assertFalse(os.path.exists(os.path.join(dest, "README.md")))

    def test_the_bundle_carries_a_manifest_describing_itself(self):
        dest, included = self._build(set(_common.TIERS) - {_common.AGENCY_MEDIA},
                                     {_common.QUERY})
        with open(os.path.join(dest, "manifest.json")) as f:
            man = json.load(f)
        self.assertEqual(set(man["artifacts"]), included)
        self.assertEqual(man["bundle"]["roles"], [_common.QUERY])
        self.assertNotIn(_common.AGENCY_MEDIA, man["bundle"]["tiers"])

    def test_curated_content_is_stripped_from_the_files_that_are_kept(self):
        dest, _ = self._build(set(_common.TIERS) - {_common.CURATED},
                              set(_common.ROLES))
        with open(os.path.join(dest, "trout-waters/pmtw-reaches.json")) as f:
            reaches = json.load(f)
        self.assertNotIn("regulation_summary", reaches[0])
        with open(os.path.join(dest, "species-knowledge/kb/brook-trout.json")) as f:
            record = json.load(f)
        self.assertNotIn("baits_ranked", record)
        self.assertEqual(record["slug"], "brook-trout")

    def test_it_refuses_to_build_over_an_existing_bundle(self):
        dest, included = self._build(set(_common.TIERS), set(_common.ROLES))
        with self.assertRaises(SystemExit):
            plan_bundle.build(self.base, self.manifest, included,
                              set(_common.TIERS), dest)


if __name__ == "__main__":
    unittest.main()
