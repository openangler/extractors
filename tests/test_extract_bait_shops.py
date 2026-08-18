"""extract_bait_shops.py — classification, the hours contract, and the ODbL tier.

Parsing only: every test runs `shop_record` / `records_from` over a captured
Overpass response, so no Overpass instance is contacted. Overpass is a free,
donated, rate-limited service; a test suite has no business calling it.
"""

import unittest

import context
import extract_bait_shops as bs

RESPONSES = context.fixture("overpass_bait_shops.json")
HIGH_ROCK = RESPONSES["high_rock"]
EDGE = RESPONSES["edge_cases"]

BBOX = (35.45, -80.65, 36.0, -79.95)


def by_name(records):
    return {r["name"]: r for r in records}


class TestRealHighRockResponse(unittest.TestCase):
    """What Overpass actually returned for Davidson/Rowan around High Rock Lake."""

    RECORDS = bs.records_from(HIGH_ROCK)

    def test_both_mapped_shops_survive(self):
        self.assertEqual([r["name"] for r in self.RECORDS],
                         ["Lake Thom-A-Lex Park Bait Shop", "Mimi's Bait & Tackle"])
        for r in self.RECORDS:
            self.assertEqual(r["class"], "fishing_tackle_shop")
            self.assertEqual(r["confidence"], "primary")
            self.assertEqual(r["matched_tags"], {"shop": "fishing"})

    def test_neither_has_hours_and_neither_is_called_closed(self):
        """The honest measure of this layer: 0 of 2 answer 'open at 4 a.m.?'."""
        for r in self.RECORDS:
            self.assertFalse(r["hours"]["known"])
            self.assertIsNone(r["hours"]["opening_hours"])
            self.assertFalse(r["hours"]["open_24_7"])

    def test_address_is_assembled_from_the_addr_tags(self):
        mimi = by_name(self.RECORDS)["Mimi's Bait & Tackle"]
        self.assertEqual(mimi["address"], "7169 NC-8, Lexington, NC 27292")
        self.assertEqual(mimi["phone"], "+1-336-798-3588")

    def test_a_shop_with_no_addr_tags_gets_null_not_an_empty_string(self):
        thomalex = by_name(self.RECORDS)["Lake Thom-A-Lex Park Bait Shop"]
        self.assertIsNone(thomalex["address"])
        self.assertIsNone(thomalex["phone"])
        self.assertIsNone(thomalex["website"])

    def test_seasonal_is_carried_because_it_also_means_shut(self):
        thomalex = by_name(self.RECORDS)["Lake Thom-A-Lex Park Bait Shop"]
        self.assertEqual(thomalex["hours"]["seasonal"], "summer")
        self.assertIsNone(by_name(self.RECORDS)["Mimi's Bait & Tackle"]
                          ["hours"]["seasonal"])

    def test_staleness_is_kept_and_the_contributor_is_not(self):
        thomalex = by_name(self.RECORDS)["Lake Thom-A-Lex Park Bait Shop"]
        self.assertEqual(thomalex["last_edited"], "2021-08-12")
        self.assertNotIn("user", thomalex)
        self.assertNotIn("uid", thomalex)

    def test_ids_are_typed_and_link_back_to_osm(self):
        mimi = by_name(self.RECORDS)["Mimi's Bait & Tackle"]
        self.assertEqual(mimi["osm_id"], "node/10588666767")
        self.assertEqual(mimi["osm_url"],
                         "https://www.openstreetmap.org/node/10588666767")

    def test_the_osm_data_timestamp_is_recoverable(self):
        self.assertEqual(bs.osm_base_timestamp(HIGH_ROCK),
                         "2026-08-18T00:22:11Z")
        self.assertIsNone(bs.osm_base_timestamp({}))


class TestClassify(unittest.TestCase):
    """What counts as a bait shop. A false positive is a 4 a.m. wasted drive."""

    def test_primary_shop_values(self):
        for value in ("fishing", "bait", "fishing_tackle"):
            cls, conf, matched = bs.classify({"shop": value})
            self.assertEqual(conf, "primary", value)
            self.assertEqual(matched, {"shop": value})
        self.assertEqual(bs.classify({"shop": "bait"})[0], "bait_shop")
        self.assertEqual(bs.classify({"shop": "fishing_tackle"})[0],
                         "fishing_tackle_shop")

    def test_bait_vending_machine_is_primary(self):
        cls, conf, matched = bs.classify({"amenity": "vending_machine",
                                          "vending": "fishing_bait;drinks"})
        self.assertEqual((cls, conf), ("bait_vending_machine", "primary"))
        self.assertEqual(matched["vending"], "fishing_bait")

    def test_a_vending_machine_selling_something_else_is_not_a_bait_shop(self):
        self.assertIsNone(bs.classify({"amenity": "vending_machine",
                                       "vending": "drinks;sweets"}))

    def test_bait_yes_on_a_convenience_store_is_secondary_not_dropped(self):
        cls, conf, matched = bs.classify({"shop": "convenience", "bait": "yes"})
        self.assertEqual((cls, conf), ("sells_bait", "secondary"))
        self.assertEqual(matched, {"bait": "yes", "shop": "convenience"})

    def test_a_plain_convenience_store_near_water_is_not_a_bait_shop(self):
        self.assertIsNone(bs.classify({"shop": "convenience",
                                       "name": "Lakeside Gas"}))

    def test_sports_shop_needs_sport_fishing(self):
        self.assertEqual(bs.classify({"shop": "sports",
                                      "sport": "fishing;hunting"})[1],
                         "secondary")
        self.assertIsNone(bs.classify({"shop": "sports", "sport": "soccer"}))
        self.assertIsNone(bs.classify({"shop": "sports"}))

    def test_fishing_yes_means_fishing_is_allowed_not_that_bait_is_sold(self):
        """The single biggest false-positive source, and it is not queried."""
        self.assertIsNone(bs.classify({"leisure": "marina", "fishing": "yes"}))
        self.assertIsNone(bs.classify({"natural": "water", "fishing": "yes"}))
        for selector in bs.SELECTORS:
            self.assertNotIn('"fishing"="yes"', selector)

    def test_bait_yes_on_something_that_is_not_a_place_of_business(self):
        self.assertIsNone(bs.classify({"natural": "water", "bait": "yes"}))
        self.assertEqual(bs.classify({"leisure": "marina", "bait": "yes"})[0],
                         "sells_bait")

    def test_untagged_element(self):
        self.assertIsNone(bs.classify({}))


class TestEdgeCaseRecords(unittest.TestCase):

    RECORDS = bs.records_from(EDGE)

    def test_a_dead_shop_is_dropped(self):
        self.assertNotIn("Old Abandoned Bait Stand", by_name(self.RECORDS))
        self.assertIsNone(bs.shop_record(
            {"type": "node", "id": 1, "lat": 1, "lon": 1,
             "tags": {"shop": "fishing", "disused": "yes"}}))
        self.assertIsNone(bs.shop_record(
            {"type": "node", "id": 1, "lat": 1, "lon": 1,
             "tags": {"shop": "vacant", "bait": "yes"}}))

    def test_a_live_shop_in_a_dead_gas_station_survives(self):
        """disused:amenity=fuel is the site's history, not this shop's status."""
        self.assertIn("Pump House Bait", by_name(self.RECORDS))

    def test_an_element_with_no_geometry_is_dropped(self):
        self.assertNotIn("Geometryless Tackle", by_name(self.RECORDS))

    def test_a_way_is_placed_at_its_center(self):
        barn = by_name(self.RECORDS)["Tackle Barn"]
        self.assertEqual((barn["lat"], barn["lon"]), (35.61, -80.21))
        self.assertEqual(barn["osm_id"], "way/200")

    def test_a_vending_machine_falls_back_to_operator_for_a_name(self):
        self.assertIn("Dockside Marina", by_name(self.RECORDS))

    def test_contact_prefixed_tags_are_read_too(self):
        night = by_name(self.RECORDS)["Open All Night Bait"]
        self.assertEqual(night["phone"], "+1-704-555-0100")
        self.assertEqual(night["website"], "https://example.invalid/bait")

    def test_check_date_is_kept_separate_from_last_edited(self):
        barn = by_name(self.RECORDS)["Tackle Barn"]
        self.assertEqual(barn["last_edited"], "2019-06-14")
        self.assertEqual(barn["last_checked"], "2023-04-01")

    def test_duplicate_ids_are_collapsed(self):
        ids = [r["osm_id"] for r in self.RECORDS]
        self.assertEqual(len(ids), len(set(ids)))


class TestHoursAreUnknownNeverClosed(unittest.TestCase):
    """The field that decides whether the layer is worth anything."""

    def test_absent_hours_are_flagged_unknown(self):
        h = bs._hours({"shop": "fishing"})
        self.assertFalse(h["known"])
        self.assertIsNone(h["opening_hours"])
        self.assertFalse(h["open_24_7"])

    def test_the_literal_string_unknown_is_also_unknown(self):
        for value in ("unknown", "?", "", "   "):
            h = bs._hours({"opening_hours": value})
            self.assertFalse(h["known"], value)
            self.assertIsNone(h["opening_hours"], value)

    def test_real_hours_are_passed_through_verbatim(self):
        h = bs._hours({"opening_hours": "Mo-Sa 06:00-19:00; Su 06:00-12:00"})
        self.assertTrue(h["known"])
        self.assertEqual(h["opening_hours"], "Mo-Sa 06:00-19:00; Su 06:00-12:00")
        self.assertFalse(h["open_24_7"])

    def test_24_7_is_called_out_because_it_is_the_actual_question(self):
        h = bs._hours({"opening_hours": "24/7"})
        self.assertTrue(h["known"] and h["open_24_7"])

    def test_no_record_ever_says_closed(self):
        for record in bs.records_from(EDGE) + bs.records_from(HIGH_ROCK):
            self.assertEqual(set(record["hours"]),
                             {"opening_hours", "known", "open_24_7", "seasonal"})
            if not record["hours"]["known"]:
                self.assertIsNone(record["hours"]["opening_hours"])


class TestQueryBuilding(unittest.TestCase):

    def test_bbox_goes_in_in_overpass_order(self):
        q = bs.overpass_query(BBOX)
        self.assertIn("(35.45,-80.65,36,-79.95)", q)
        self.assertIn("[out:json]", q)
        self.assertIn("out center meta;", q)

    def test_one_request_asks_for_every_selector(self):
        q = bs.overpass_query(BBOX)
        for selector in bs.SELECTORS:
            self.assertIn(selector, q)
        self.assertEqual(q.count("[out:json]"), 1)

    def test_parse_bbox_round_trips(self):
        self.assertEqual(bs.parse_bbox("35.45,-80.65,36.0,-79.95"), BBOX)

    def test_parse_bbox_rejects_a_flipped_box(self):
        import argparse
        for bad in ("36.0,-80.65,35.45,-79.95",   # south > north
                    "35.45,-79.95,36.0,-80.65",   # west > east
                    "35.45,-80.65,36.0",          # too few
                    "a,b,c,d"):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                bs.parse_bbox(bad)


class TestSummary(unittest.TestCase):

    def test_high_rock_counts(self):
        s = bs.summarize(bs.records_from(HIGH_ROCK), BBOX, 2)
        self.assertEqual(s["shops"], 2)
        self.assertEqual(s["with_opening_hours"], 0)
        self.assertEqual(s["hours_unknown"], 2)
        self.assertEqual(s["with_phone"], 1)
        self.assertEqual(s["with_address"], 1)
        self.assertEqual(s["seasonal"], 1)
        self.assertEqual(s["by_confidence"], {"primary": 2})

    def test_summary_carries_the_attribution(self):
        s = bs.summarize([], BBOX, 0)
        self.assertIn("OpenStreetMap contributors", s["attribution"])
        self.assertEqual(s["license"], "ODbL-1.0")

    def test_empty_area_is_reported_as_zero_not_as_a_failure(self):
        s = bs.summarize([], BBOX, 0)
        self.assertEqual((s["shops"], s["by_class"]), (0, {}))


class TestCoverageIsStatedNotImplied(unittest.TestCase):
    """'No shops here' and 'no data here' have to be distinguishable."""

    DOC = bs.document(bs.records_from(HIGH_ROCK), BBOX, 2,
                      "2026-08-18T00:22:36Z", "2026-08-18T00:22:11Z")

    def test_the_document_records_the_bbox_it_asked_about(self):
        self.assertEqual(self.DOC["coverage"]["bbox"],
                         {"south": 35.45, "west": -80.65,
                          "north": 36.0, "east": -79.95})

    def test_the_coverage_note_says_absence_outside_the_bbox_is_absence_of_data(self):
        note = self.DOC["coverage"]["note"].lower()
        self.assertIn("not that none exists", note)
        self.assertIn("seed, not", note)

    def test_the_hours_note_forbids_rendering_unknown_as_closed(self):
        self.assertIn("does NOT mean closed", self.DOC["hours_note"])

    def test_the_selectors_and_the_omissions_both_travel_with_the_data(self):
        cov = self.DOC["coverage"]
        self.assertEqual(cov["selectors"], list(bs.SELECTORS))
        self.assertIn("fishing=yes", cov["not_queried"])

    def test_the_overpass_data_timestamp_is_recorded(self):
        self.assertEqual(self.DOC["coverage"]["osm_data_timestamp"],
                         "2026-08-18T00:22:11Z")


class TestOdblAttribution(unittest.TestCase):
    """ODbL needs attribution on display, so it ships inside the artifact."""

    DOC = bs.document(bs.records_from(HIGH_ROCK), BBOX, 2, "2026-08-18T00:22:36Z")

    def test_attribution_is_at_the_top_of_the_document(self):
        self.assertIn("© OpenStreetMap contributors", self.DOC["attribution"])
        self.assertIn("opendatacommons.org", self.DOC["license"]["license_url"])
        self.assertIn("openstreetmap.org/copyright", self.DOC["attribution"])

    def test_the_licence_block_states_share_alike_and_not_non_commercial(self):
        lic = self.DOC["license"]
        self.assertEqual(lic["license"], "ODbL-1.0")
        self.assertTrue(lic["attribution_required"])
        self.assertTrue(lic["share_alike"])
        self.assertFalse(lic["non_commercial"])

    def test_the_note_distinguishes_produced_work_from_derivative_database(self):
        note = self.DOC["license"]["note"]
        self.assertIn("Produced Work", note)
        self.assertIn("Derivative Database", note)


class TestProvenanceTier(unittest.TestCase):
    """ADR-0007 has no slot for community-contributed open data; this adds one."""

    DOC = bs.document(bs.records_from(HIGH_ROCK), BBOX, 2, "2026-08-18T00:22:36Z")

    def _entries(self):
        import _common
        return _common.build_entries("extract_bait_shops.py",
                                     bs.artifact_tiers(sample=self.DOC))

    def test_the_tier_is_registered_with_a_glossary_entry(self):
        import _common
        self.assertIn(bs.COMMUNITY, _common.TIERS)
        gloss = _common.TIERS[bs.COMMUNITY]
        self.assertIn("ODbL", gloss)
        self.assertIn("share-alike", gloss)

    def test_osm_is_none_of_the_five_existing_tiers(self):
        import _common
        self.assertNotIn(bs.COMMUNITY, (_common.FEDERAL, _common.AGENCY_FACTUAL,
                                        _common.AGENCY_MEDIA, _common.CURATED,
                                        _common.PERSONAL))

    def test_shop_records_carry_the_osm_tier_and_our_prose_does_not(self):
        import _common
        fields = self._entries()["bait-shops/shops.json"]["fields"]
        for path in ("shops", "shops.name", "shops.hours.known", "attribution"):
            self.assertEqual(_common.field_tier(fields, path), bs.COMMUNITY, path)
        for path in ("coverage.note", "hours_note", "license.note"):
            self.assertEqual(_common.field_tier(fields, path), _common.CURATED,
                             path)

    def test_the_licence_block_itself_stays_with_the_source(self):
        import _common
        fields = self._entries()["bait-shops/shops.json"]["fields"]
        self.assertEqual(_common.field_tier(fields, "license.attribution"),
                         bs.COMMUNITY)

    def test_an_untagged_new_field_keeps_the_obligations_attached(self):
        import _common
        fields = self._entries()["bait-shops/shops.json"]["fields"]
        self.assertEqual(fields["default"], bs.COMMUNITY)
        self.assertEqual(_common.field_tier(fields, "something_added_later"),
                         bs.COMMUNITY)

    def test_every_field_of_a_real_document_resolves(self):
        self.assertEqual(self._entries()["bait-shops/shops.json"]
                         ["fields"]["coverage"], "complete")

    def test_the_artifacts_are_query_role_and_the_summary_is_derived(self):
        import _common
        entries = self._entries()
        self.assertEqual(entries["bait-shops/shops.json"]["role"], _common.QUERY)
        summary = entries["bait-shops/summary.json"]
        self.assertEqual(summary["role"], _common.QUERY)
        self.assertEqual(summary["derived_from"], ["bait-shops/shops.json"])
        self.assertEqual(summary["tiers"], [bs.COMMUNITY])
        self.assertFalse(summary["mixed"])

    def test_shops_json_is_declared_mixed(self):
        self.assertTrue(self._entries()["bait-shops/shops.json"]["mixed"])


if __name__ == "__main__":
    unittest.main()
