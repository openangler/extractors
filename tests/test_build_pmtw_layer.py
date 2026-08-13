"""build_pmtw_layer.py — geometry, point-in-polygon and reach records.

reach_record() is pure; the only network call in this script is the optional
3DEP elevation lookup, which these tests do not touch.
"""

import unittest

import context
import build_pmtw_layer as pmtw

FEATURES = context.fixture("pmtw_features.json")["features"]

# a 1-degree square "county", enough to exercise the ray-casting
SQUARE = [[-83.0, 35.0], [-82.0, 35.0], [-82.0, 36.0], [-83.0, 36.0], [-83.0, 35.0]]
COUNTIES = [("Jackson", SQUARE, -83.0, 35.0, -82.0, 36.0)]


class TestMidpoint(unittest.TestCase):
    def test_linestring(self):
        self.assertEqual(pmtw.midpoint({"type": "LineString",
                                        "coordinates": [[0, 0], [1, 1], [2, 2]]}),
                         [1, 1])

    def test_multilinestring_is_flattened_first(self):
        self.assertEqual(
            pmtw.midpoint({"type": "MultiLineString",
                           "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}),
            [2, 2])

    def test_empty_geometry(self):
        self.assertIsNone(pmtw.midpoint({"type": "LineString", "coordinates": []}))
        self.assertIsNone(pmtw.midpoint({"type": "Point", "coordinates": [1, 2]}))

    def test_real_reaches_all_have_a_midpoint_in_nc(self):
        for f in FEATURES:
            lon, lat = pmtw.midpoint(f["geometry"])
            self.assertTrue(-85 < lon < -75, lon)
            self.assertTrue(33 < lat < 37, lat)


class TestPointInPolygon(unittest.TestCase):
    def test_inside_and_outside(self):
        self.assertTrue(pmtw.point_in_ring(-82.5, 35.5, SQUARE))
        self.assertFalse(pmtw.point_in_ring(-81.5, 35.5, SQUARE))

    def test_county_for_uses_the_bounding_box_then_the_ring(self):
        self.assertEqual(pmtw.county_for(-82.5, 35.5, COUNTIES), "Jackson")
        self.assertIsNone(pmtw.county_for(-79.0, 35.5, COUNTIES))


class TestReachRecord(unittest.TestCase):
    def test_real_feature_becomes_a_reach(self):
        r = pmtw.reach_record(FEATURES[0], [])
        self.assertEqual(r["stream_name"], FEATURES[0]["properties"]["Displ_Name"])
        self.assertEqual(r["wrc_class"], "Hatchery Supported Trout Waters")
        self.assertIn("7-trout creel", r["regulation_summary"])
        self.assertIsNone(r["elevation_m"])          # filled in later, if at all
        self.assertIsNone(r["county"])               # no county polygons supplied
        self.assertEqual(set(r["midpoint"]), {"lat", "lon"})

    def test_every_real_class_has_a_regulation_summary(self):
        for f in FEATURES:
            r = pmtw.reach_record(f, [])
            self.assertNotEqual(r["regulation_summary"], "See NCWRC rules.",
                                r["wrc_class"])

    def test_unknown_class_falls_back(self):
        f = {"properties": {"WRC_Class": "Brand New Class"},
             "geometry": {"type": "LineString", "coordinates": [[-82.5, 35.5]]}}
        self.assertEqual(pmtw.reach_record(f, [])["regulation_summary"],
                         "See NCWRC rules.")

    def test_blank_mhtw_placeholder_is_not_a_flag(self):
        r = pmtw.reach_record(FEATURES[0], [])
        self.assertFalse(r["mountain_heritage"])
        self.assertIsNone(r["mhtw_reach"])

    def test_geometryless_feature_is_skipped(self):
        self.assertIsNone(pmtw.reach_record(
            {"properties": {}, "geometry": {"type": "LineString",
                                            "coordinates": []}}, []))


class TestArtifactTiers(unittest.TestCase):
    def test_regulation_summary_is_curated_not_agency_text(self):
        import _common
        entries = _common.build_entries("build_pmtw_layer.py",
                                        pmtw.artifact_tiers(True))
        reaches = entries["trout-waters/pmtw-reaches.json"]
        self.assertTrue(reaches["mixed"])
        self.assertEqual(reaches["tier_detail"]["regulation_summary"],
                         _common.CURATED)
        self.assertEqual(reaches["tier_detail"]["wrc_class"], _common.AGENCY_FACTUAL)
        self.assertEqual(reaches["tier_detail"]["elevation_m"], _common.FEDERAL)

    def test_no_federal_tier_claimed_when_elevation_is_skipped(self):
        tiers = pmtw.artifact_tiers(False)["trout-waters/pmtw-reaches.json"]
        import _common
        self.assertNotIn(_common.FEDERAL, tiers["tiers"])
        self.assertNotIn("elevation_m", tiers["tier_detail"])


if __name__ == "__main__":
    unittest.main()
