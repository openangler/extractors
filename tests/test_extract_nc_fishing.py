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
        layers = {"trout-waters/pmtw-streams-2025.geojson": "..."}
        entries = _common.build_entries(
            "extract_nc_fishing.py", ex.artifact_tiers(counts, layers, True))
        media = sorted(p for p, e in entries.items()
                       if _common.AGENCY_MEDIA in e["tiers"])
        self.assertEqual(media, ["fishing-areas/coastal-plain/photos/",
                                 "fishing-areas/mountains/photos/",
                                 "fishing-areas/piedmont/photos/"])
        self.assertEqual(entries["fishing-areas/all-locations.json"]["tiers"],
                         [_common.AGENCY_FACTUAL])
        self.assertIn("trout-waters/pmtw-streams-2025.geojson", entries)

    def test_no_photo_run_claims_no_media(self):
        import _common
        entries = _common.build_entries(
            "extract_nc_fishing.py",
            ex.artifact_tiers({"Mountains": 239}, {}, False))
        self.assertFalse(any(_common.AGENCY_MEDIA in e["tiers"]
                             for e in entries.values()))


if __name__ == "__main__":
    unittest.main()
