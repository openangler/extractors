"""species_extract.py — profile parsing and slug canonicalisation.

parse_profile() runs against a captured page; nothing here hits ncwildlife.gov.
"""

import unittest

import context
import species_extract as se

REAL_SLUGS = context.fixture("species_slugs.json")     # the 47 slugs NCWRC serves


class TestCanonicalSlug(unittest.TestCase):
    def test_strips_the_ncwrc_dedup_suffix(self):
        """Issue #4: the -0 is NCWRC's URL de-dup counter, not the species."""
        self.assertEqual(se.canonical_slug("largemouth-bass-0"), "largemouth-bass")

    def test_leaves_ordinary_slugs_alone(self):
        for slug in ("brook-trout", "muskellunge", "bodie-bass-hybrid-striped-bass"):
            self.assertEqual(se.canonical_slug(slug), slug)

    def test_keeps_the_suffix_when_the_canonical_form_is_taken(self):
        self.assertEqual(
            se.canonical_slug("largemouth-bass-0", {"largemouth-bass"}),
            "largemouth-bass-0")

    def test_multi_digit_suffix(self):
        self.assertEqual(se.canonical_slug("channel-catfish-12"), "channel-catfish")

    def test_a_slug_that_is_only_digits_is_left_alone(self):
        self.assertEqual(se.canonical_slug("-3"), "-3")

    def test_exactly_one_real_slug_needs_canonicalising(self):
        changed = {s: se.canonical_slug(s, set(REAL_SLUGS) - {s})
                   for s in REAL_SLUGS}
        self.assertEqual({k: v for k, v in changed.items() if k != v},
                         {"largemouth-bass-0": "largemouth-bass"})


class TestCanonicalise(unittest.TestCase):
    def test_rewrites_slug_and_records_the_alias(self):
        out = se.canonicalise([
            {"slug": "largemouth-bass-0", "name": "Largemouth Bass",
             "url": "https://www.ncwildlife.gov/species/largemouth-bass-0"},
            {"slug": "brook-trout", "name": "Brook Trout",
             "url": "https://www.ncwildlife.gov/species/brook-trout"}])
        bass = {p["slug"]: p for p in out}["largemouth-bass"]
        self.assertEqual(bass["source_slug"], "largemouth-bass-0")
        self.assertEqual(bass["aliases"], ["largemouth-bass-0"])
        # nothing is lost: the raw NCWRC URL still points at the real page
        self.assertEqual(bass["url"],
                         "https://www.ncwildlife.gov/species/largemouth-bass-0")

    def test_untouched_profiles_gain_no_alias_noise(self):
        out = se.canonicalise([{"slug": "brook-trout"}])
        self.assertNotIn("aliases", out[0])
        self.assertNotIn("source_slug", out[0])

    def test_collision_with_a_distinct_species_keeps_both(self):
        out = se.canonicalise([{"slug": "largemouth-bass-0"},
                               {"slug": "largemouth-bass"}])
        self.assertEqual(sorted(p["slug"] for p in out),
                         ["largemouth-bass", "largemouth-bass-0"])

    def test_two_suffixed_variants_do_not_collide_with_each_other(self):
        out = se.canonicalise([{"slug": "spotted-bass-0"}, {"slug": "spotted-bass-1"}])
        slugs = sorted(p["slug"] for p in out)
        self.assertEqual(len(set(slugs)), 2)
        self.assertIn("spotted-bass", slugs)

    def test_output_is_sorted_and_complete(self):
        out = se.canonicalise([{"slug": s} for s in REAL_SLUGS])
        self.assertEqual(len(out), len(REAL_SLUGS))
        self.assertEqual([p["slug"] for p in out],
                         sorted(p["slug"] for p in out))
        self.assertNotIn("largemouth-bass-0", [p["slug"] for p in out])


class TestParseProfile(unittest.TestCase):
    def setUp(self):
        self.p = se.parse_profile("flathead-catfish",
                                  context.fixture("species_profile.html"))

    def test_name_and_url(self):
        self.assertEqual(self.p["name"], "Flathead Catfish")
        self.assertEqual(self.p["url"],
                         "https://www.ncwildlife.gov/species/flathead-catfish")

    def test_sections_are_split_by_label(self):
        self.assertTrue(self.p["fishing_tips"].startswith("Live fish"))
        self.assertIn("Cape Fear", self.p["places_to_fish"])
        self.assertIn("nongame fish", self.p["regulations"])
        self.assertIn("flat head", self.p["overview"])

    def test_habitat_and_overview_collapse_together(self):
        self.assertIn("Deep, slow pools", self.p["overview"])

    def test_entities_are_unescaped(self):
        self.assertNotIn("&nbsp;", self.p["overview"])

    def test_footer_is_not_swallowed_into_a_section(self):
        self.assertNotIn("Related Topics", self.p["management"])
        self.assertNotIn("Trout fishing in North Carolina", self.p["management"])

    def test_media_and_internal_links(self):
        self.assertEqual(self.p["media_ids"], ["2893", "2894"])
        self.assertEqual(len(self.p["internal_doc_links"]), 1)

    def test_nav_links_are_not_mistaken_for_sections(self):
        self.assertNotIn("blue-catfish", str(self.p))


class TestArtifactTiers(unittest.TestCase):
    def test_pdfs_are_media_and_the_index_is_not(self):
        import _common
        entries = _common.build_entries("species_extract.py", se.artifact_tiers())
        self.assertEqual(entries["species/reports/"]["tiers"],
                         [_common.AGENCY_MEDIA])
        self.assertEqual(entries["species/reports/index.json"]["tiers"],
                         [_common.AGENCY_FACTUAL])
        self.assertFalse(entries["species/all-species.json"]["mixed"])


if __name__ == "__main__":
    unittest.main()
