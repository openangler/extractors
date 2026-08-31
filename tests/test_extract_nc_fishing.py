"""extract_nc_fishing.py — county/region mapping and the artifact tiers.

Pure helpers only; the NCWRC endpoints are never contacted.
"""

import unittest

import context
import extract_nc_fishing as ex


class TestRegionFor(unittest.TestCase):
    def test_the_three_ncwrc_regions(self):
        self.assertEqual(ex.region_for("Buncombe"), "Mountains")
        self.assertEqual(ex.region_for("Wake"), "Piedmont")
        self.assertEqual(ex.region_for("Dare"), "Coastal Plain")

    def test_case_and_whitespace_are_normalised(self):
        self.assertEqual(ex.region_for("  wake "), "Piedmont")
        self.assertEqual(ex.region_for("NEW HANOVER"), "Coastal Plain")

    def test_mcdowell_keeps_its_capital_d(self):
        self.assertEqual(ex.region_for("mcdowell"), "Mountains")

    def test_missing_or_unknown_county(self):
        self.assertEqual(ex.region_for(None), "Unknown")
        self.assertEqual(ex.region_for(""), "Unknown")
        self.assertEqual(ex.region_for("Fairfax"), "Unknown")

    def test_all_100_nc_counties_are_covered_exactly_once(self):
        counties = ex.MOUNTAINS | ex.PIEDMONT | ex.COASTAL
        self.assertEqual(len(counties), 100)
        self.assertEqual(len(ex.MOUNTAINS) + len(ex.PIEDMONT) + len(ex.COASTAL), 100)

    def test_every_region_has_an_output_directory(self):
        for region in ("Mountains", "Piedmont", "Coastal Plain", "Unknown"):
            self.assertIn(region, ex.REGION_DIR)


class TestSlug(unittest.TestCase):
    def test_filename_safe(self):
        self.assertEqual(ex.slug("Gordon's Myers at Cedar Point"),
                         "gordon-s-myers-at-cedar-point")

    def test_empty_falls_back(self):
        self.assertEqual(ex.slug(""), "site")
        self.assertEqual(ex.slug(None), "site")
        self.assertEqual(ex.slug("!!!"), "site")

    def test_length_is_capped(self):
        self.assertLessEqual(len(ex.slug("x" * 200)), 60)


class TestCleanDms(unittest.TestCase):
    def test_html_entities_become_characters(self):
        self.assertEqual(ex.clean_dms("35&deg; 35&rsquo; 42&rdquo; N"),
                         "35° 35' 42\" N")

    def test_whitespace_is_collapsed(self):
        self.assertEqual(ex.clean_dms("  35&deg;\n  35  "), "35° 35")

    def test_none_passes_through(self):
        self.assertIsNone(ex.clean_dms(None))


class TestArtifactTiers(unittest.TestCase):
    def test_photos_are_the_only_media(self):
        import _common
        counts = {"Mountains": 239, "Piedmont": 355, "Coastal Plain": 317}
        layers = {"trout-waters/pmtw-streams-2026.geojson": "..."}
        entries = _common.build_entries(
            "extract_nc_fishing.py", ex.artifact_tiers(counts, layers, True))
        media = sorted(p for p, e in entries.items()
                       if _common.AGENCY_MEDIA in e["tiers"])
        self.assertEqual(media, ["fishing-areas/coastal-plain/photos/",
                                 "fishing-areas/mountains/photos/",
                                 "fishing-areas/piedmont/photos/"])
        self.assertEqual(entries["fishing-areas/all-locations.json"]["tiers"],
                         [_common.AGENCY_FACTUAL])
        self.assertIn("trout-waters/pmtw-streams-2026.geojson", entries)

    def test_no_photo_run_claims_no_media(self):
        import _common
        entries = _common.build_entries(
            "extract_nc_fishing.py",
            ex.artifact_tiers({"Mountains": 239}, {}, False))
        self.assertFalse(any(_common.AGENCY_MEDIA in e["tiers"]
                             for e in entries.values()))

    def test_geometry_is_the_same_tier_as_the_data_but_a_different_role(self):
        """Issue #3: tier alone cannot separate 100 MB of GeoJSON from 1 MB of JSON."""
        import _common
        counts = {"Mountains": 239}
        layers = {"reference-layers/county-boundaries.geojson": "..."}
        entries = _common.build_entries(
            "extract_nc_fishing.py", ex.artifact_tiers(counts, layers, True))
        geo = entries["reference-layers/county-boundaries.geojson"]
        data = entries["fishing-areas/all-locations.json"]
        self.assertEqual(geo["tiers"], data["tiers"])
        self.assertEqual(geo["role"], _common.GEOMETRY)
        self.assertEqual(data["role"], _common.QUERY)
        self.assertEqual(entries["fishing-areas/mountains/photos/"]["role"],
                         _common.MEDIA)

    def test_redundant_views_say_what_they_duplicate(self):
        import _common
        entries = _common.build_entries(
            "extract_nc_fishing.py", ex.artifact_tiers({"Mountains": 239}, {}, False))
        for relpath in ("fishing-areas/mountains/locations.json",
                        "fishing-areas/mountains/locations.csv"):
            self.assertEqual(entries[relpath]["role"], _common.ARCHIVE)
            self.assertEqual(entries[relpath]["derived_from"],
                             ["fishing-areas/all-locations.json"])


if __name__ == "__main__":
    unittest.main()


class TestJoinFacilities(unittest.TestCase):
    """The facility join, and the bug that made it destroy the dataset.

    The first version iterated the 8-field marker list from step 1 instead of the
    detailed records, and the caller then wrote that same list back over
    all-locations.json — so every record lost county, region, amenities and
    speciesInfo, leaving a file that was still the right length and still parsed.
    """

    JULIAN = {"PFA_Name": "LAKE JULIAN", "Latitude": 35.4799, "Longitude": -82.5373,
              "Fish_Feeder": 1, "Lighting": 1, "OBJECTID": 39, "Website": ""}

    def _detailed(self):
        return [{"locationID": 1619, "locationName": "LAKE JULIAN",
                 "latitude": 35.4799, "longitude": -82.5373,
                 "county": "Buncombe", "region": "Mountains",
                 "locationTypeName": "Public Fishing Area (PFA)",
                 "boatRamp": True, "speciesInfo": [{"commonName": "Channel Catfish"}]}]

    def _facilities(self, *entries):
        return [(kind, ex.norm_site_name(a["PFA_Name"] if "PFA_Name" in a else a["BAA_Name"]),
                 a["Latitude"], a["Longitude"], a) for kind, a in entries]

    def test_detail_fields_survive_the_join(self):
        recs = self._detailed()
        ex.join_facilities(recs, self._facilities(("PFA", self.JULIAN)))
        r = recs[0]
        for field in ("county", "region", "locationTypeName", "boatRamp", "speciesInfo"):
            self.assertIn(field, r, f"{field} was lost by the join")
        self.assertEqual(r["county"], "Buncombe")
        self.assertEqual(r["facilities"]["Fish_Feeder"], 1)

    def test_objectid_and_blanks_are_stripped(self):
        recs = self._detailed()
        ex.join_facilities(recs, self._facilities(("PFA", self.JULIAN)))
        self.assertNotIn("OBJECTID", recs[0]["facilities"])
        self.assertNotIn("Website", recs[0]["facilities"])

    def test_a_site_that_is_both_pfa_and_baa_merges_rather_than_going_ambiguous(self):
        baa = {"BAA_Name": "LAKE JULIAN", "Latitude": 35.4799, "Longitude": -82.5373,
               "Boat_Ramp": 1}
        recs = self._detailed()
        joined, dual, ambiguous = ex.join_facilities(
            recs, self._facilities(("PFA", self.JULIAN), ("BAA", baa)))
        self.assertEqual((joined, dual, ambiguous), (1, 1, 0))
        self.assertEqual(recs[0]["facilities"]["_source"], "BAA+PFA")
        self.assertEqual(recs[0]["facilities"]["Fish_Feeder"], 1)
        self.assertEqual(recs[0]["facilities"]["Boat_Ramp"], 1)

    def test_two_of_the_same_kind_are_left_unjoined(self):
        twin = dict(self.JULIAN, Latitude=35.4800, Fish_Feeder=0)
        recs = self._detailed()
        joined, _, ambiguous = ex.join_facilities(
            recs, self._facilities(("PFA", self.JULIAN), ("PFA", twin)))
        self.assertEqual((joined, ambiguous), (0, 1))
        self.assertNotIn("facilities", recs[0])

    def test_a_like_named_site_too_far_away_does_not_match(self):
        far = dict(self.JULIAN, Latitude=36.0, Longitude=-80.0)
        recs = self._detailed()
        joined, _, _ = ex.join_facilities(recs, self._facilities(("PFA", far)))
        self.assertEqual(joined, 0)

    def test_closure_text_in_the_app_name_still_matches(self):
        recs = self._detailed()
        recs[0]["locationName"] = "LAKE JULIAN - CLOSED UNTIL FURTHER NOTICE"
        joined, _, _ = ex.join_facilities(recs, self._facilities(("PFA", self.JULIAN)))
        self.assertEqual(joined, 1)
