"""enrich_usgs.py — NHDPlus no-data handling and reach selection.

Parsing only: nhd_pick / parse_elevation take a captured response, so no USGS
endpoint is contacted.
"""

import unittest
import urllib.parse

import context
import enrich_usgs as eu

FLOWLINES = context.fixture("nhd_flowlines.json")


class TestNhdNumber(unittest.TestCase):
    def test_sentinels_become_none(self):
        for sentinel in (-9, -9998, -9999, -9.0, "-9999"):
            self.assertIsNone(eu.nhd_number(sentinel), sentinel)

    def test_real_values_survive(self):
        self.assertEqual(eu.nhd_number(8), 8.0)
        self.assertEqual(eu.nhd_number(0.001274), 0.001274)
        self.assertEqual(eu.nhd_number(2073.68), 2073.68)

    def test_zero_is_a_value_not_a_sentinel(self):
        self.assertEqual(eu.nhd_number(0), 0.0)

    def test_unknown_negative_codes_are_also_rejected(self):
        # stream order / slope / drainage / flow are non-negative quantities
        self.assertIsNone(eu.nhd_number(-1))
        self.assertIsNone(eu.nhd_number(-9997))

    def test_missing_or_junk_is_none(self):
        self.assertIsNone(eu.nhd_number(None))
        self.assertIsNone(eu.nhd_number(""))
        self.assertIsNone(eu.nhd_number("n/a"))
        self.assertIsNone(eu.nhd_number(True))


class TestNhdPick(unittest.TestCase):
    def test_coastal_sentinel_reach_yields_nulls_not_minus_nine(self):
        """Issue #6: -9 stream order sorted 29 coastal reaches below headwaters."""
        r = eu.nhd_pick(FLOWLINES["coastal_sentinel"]["features"], "KITTY HAWK BAY")
        self.assertIsNone(r["stream_order"])
        self.assertIsNone(r["drainage_area_sqkm"])
        self.assertIsNone(r["slope"])
        self.assertEqual(r["mean_annual_flow_cfs"], 0.4)     # genuine, kept
        self.assertIsNone(r["nhd_name"])
        self.assertFalse(r["name_matched"])

    def test_sentinels_are_per_field(self):
        r = eu.nhd_pick(FLOWLINES["partial_sentinel"]["features"], "NEUSE RIVER")
        self.assertIsNone(r["slope"])
        self.assertEqual(r["stream_order"], 7)
        self.assertEqual(r["drainage_area_sqkm"], 2274.9)
        self.assertEqual(r["mean_annual_flow_cfs"], 974.7)

    def test_name_match_beats_a_larger_neighbour(self):
        r = eu.nhd_pick(FLOWLINES["named_match"]["features"], "FRENCH BROAD RIVER")
        self.assertEqual(r["nhd_name"], "French Broad River")
        self.assertTrue(r["name_matched"])
        self.assertEqual(r["stream_order"], 8)
        self.assertEqual(r["slope"], 0.00127)
        self.assertEqual(r["drainage_area_sqkm"], 2073.7)

    def test_unnamed_falls_back_to_largest_drainage(self):
        r = eu.nhd_pick(FLOWLINES["unnamed_largest"]["features"], "FROG POND")
        self.assertEqual(r["nhd_name"], "Ezra Fork")
        self.assertFalse(r["name_matched"])
        self.assertEqual(r["stream_order"], 2)

    def test_no_flowline_in_range(self):
        self.assertEqual(eu.nhd_pick(FLOWLINES["empty"]["features"], "X"), {})
        self.assertEqual(eu.nhd_pick([], None), {})

    def test_stream_order_is_an_int(self):
        r = eu.nhd_pick(FLOWLINES["named_match"]["features"], "FRENCH BROAD RIVER")
        self.assertIsInstance(r["stream_order"], int)

    def test_sentinel_drainage_never_wins_the_max(self):
        feats = (FLOWLINES["coastal_sentinel"]["features"]
                 + FLOWLINES["unnamed_largest"]["features"])
        self.assertEqual(eu.nhd_pick(feats, None)["nhd_name"], "Ezra Fork")


class TestElevation(unittest.TestCase):
    def test_parses_metres(self):
        self.assertEqual(eu.parse_elevation('{"value": "651.23"}'), 651.2)

    def test_epqs_no_data_becomes_none(self):
        self.assertIsNone(eu.parse_elevation('{"value": -1000000}'))

    def test_junk_response_becomes_none(self):
        self.assertIsNone(eu.parse_elevation("<html>service unavailable</html>"))
        self.assertIsNone(eu.parse_elevation('{"error": "bad request"}'))


class TestRequestBuilding(unittest.TestCase):
    def test_epqs_url_carries_lat_lon_the_right_way_round(self):
        q = urllib.parse.parse_qs(
            urllib.parse.urlparse(eu.epqs_url(35.59, -82.58)).query)
        self.assertEqual(q["x"], ["-82.58"])
        self.assertEqual(q["y"], ["35.59"])

    def test_nhd_url_requests_the_vaa_fields_we_normalise(self):
        q = urllib.parse.parse_qs(
            urllib.parse.urlparse(eu.nhd_url(35.59, -82.58)).query)
        self.assertEqual(q["geometry"], ["-82.58,35.59"])
        for field in ("streamorde", "slope", "totdasqkm", "qama"):
            self.assertIn(field, q["outFields"][0])


class TestHaversine(unittest.TestCase):
    def test_known_distance(self):
        # Asheville -> Raleigh, ~330 km
        km = eu.haversine(35.5951, -82.5515, 35.7796, -78.6382)
        self.assertAlmostEqual(km, 353.0, delta=5.0)

    def test_zero_distance(self):
        self.assertEqual(eu.haversine(35.0, -80.0, 35.0, -80.0), 0.0)


class TestArtifactTiers(unittest.TestCase):
    def test_enrichment_is_declared_mixed_and_validates(self):
        import _common
        entries = _common.build_entries("enrich_usgs.py", eu.artifact_tiers(True))
        enr = entries["fishing-areas/enrichment.json"]
        self.assertTrue(enr["mixed"])
        self.assertEqual(enr["tier_detail"]["stream_order"], _common.FEDERAL)
        self.assertEqual(enr["tier_detail"]["locationName"], _common.AGENCY_FACTUAL)
        merged = entries["fishing-areas/all-locations-enriched.json"]
        self.assertEqual(merged["tier_detail"]["usgs"], _common.FEDERAL)

    def test_subset_run_does_not_claim_the_merged_file(self):
        self.assertNotIn("fishing-areas/all-locations-enriched.json",
                         eu.artifact_tiers(False))


if __name__ == "__main__":
    unittest.main()
