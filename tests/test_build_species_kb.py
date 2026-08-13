"""build_species_kb.py — habitat envelopes and the curated<->profile join.

This step is local-only; these tests use real site and enrichment records
captured from a produced dataset.
"""

import unittest

import context
import build_species_kb as kb

SITES = context.fixture("sites_sample.json")
ENR = context.fixture("enrichment_sample.json")


class TestEnvelope(unittest.TestCase):
    def test_matches_species_by_substring_of_common_name(self):
        n, env = kb.envelope(SITES, ENR, "bass")
        self.assertGreater(n, 0)
        self.assertEqual(env["stream_order"]["n"], n)

    def test_unknown_species_yields_an_empty_envelope(self):
        n, env = kb.envelope(SITES, ENR, "arapaima")
        self.assertEqual(n, 0)
        self.assertTrue(all(v is None for v in env.values()))

    def test_normalised_sentinel_rows_drop_out_of_the_envelope(self):
        """Issue #6, consumer side.

        locationID 1757 (AVALON BEACH, a coastal site with stream_order -9)
        reports Largemouth Bass, so today it lands in the bass envelope carrying
        a -9 order and a -9999 drainage. Once enrich_usgs writes null instead,
        the existing `if r.get("stream_order")` guard excludes it.
        """
        fixed = {k: (dict(v, stream_order=None, drainage_area_sqkm=None)
                     if v.get("stream_order") == -9 else v)
                 for k, v in ENR.items()}
        before, env_before = kb.envelope(SITES, ENR, "largemouth bass")
        after, env_after = kb.envelope(SITES, fixed, "largemouth bass")
        self.assertEqual(before - after, 1)
        self.assertLess(env_before["drainage_area_sqkm"]["p10"], 0)
        self.assertGreaterEqual(env_after["drainage_area_sqkm"]["p10"], 0)
        self.assertGreaterEqual(env_after["stream_order"]["p10"], 1)

    def test_a_minus_nine_stream_order_would_poison_the_p10(self):
        """Guards issue #6 from the consumer side: -9 is not a stream order."""
        sites = [{"locationID": i, "speciesInfo": [{"commonName": "Channel Catfish"}]}
                 for i in (1, 2, 3)]
        clean = {"1": {"stream_order": 4}, "2": {"stream_order": 5},
                 "3": {"stream_order": 6}}
        n, env = kb.envelope(sites, clean, "catfish")
        self.assertEqual(n, 3)
        self.assertEqual(env["stream_order"]["p10"], 4)
        self.assertGreaterEqual(env["stream_order"]["median"], 4)

    def test_percentiles_and_rounding(self):
        sites = [{"locationID": i, "speciesInfo": [{"commonName": "Brook Trout"}]}
                 for i in range(10)]
        enr = {str(i): {"stream_order": i + 1, "slope": 0.0012345 * (i + 1)}
               for i in range(10)}
        n, env = kb.envelope(sites, enr, "trout")
        self.assertEqual(n, 10)
        self.assertEqual(env["stream_order"]["p10"], 2)
        self.assertEqual(env["stream_order"]["median"], 5.5)
        self.assertEqual(env["stream_order"]["p90"], 10)
        self.assertEqual(env["slope"]["p10"], round(0.0012345 * 2, 5))


class TestProfileIndex(unittest.TestCase):
    def test_alias_resolves_to_the_canonical_profile(self):
        idx = kb.profile_index([
            {"slug": "largemouth-bass", "aliases": ["largemouth-bass-0"],
             "name": "Largemouth Bass"}])
        self.assertIs(idx["largemouth-bass-0"], idx["largemouth-bass"])

    def test_a_real_slug_always_beats_an_alias(self):
        idx = kb.profile_index([
            {"slug": "largemouth-bass-0", "name": "Different Species"},
            {"slug": "largemouth-bass", "aliases": ["largemouth-bass-0"],
             "name": "Largemouth Bass"}])
        self.assertEqual(idx["largemouth-bass-0"]["name"], "Different Species")

    def test_profiles_without_aliases(self):
        idx = kb.profile_index([{"slug": "brook-trout"}])
        self.assertEqual(list(idx), ["brook-trout"])

    def test_join_works_in_both_directions(self):
        """A curated key may be renamed before the profiles are re-scraped."""
        stale = kb.profile_index([{"slug": "largemouth-bass-0", "name": "LMB"}])
        self.assertEqual(stale["largemouth-bass"]["name"], "LMB")
        fresh = kb.profile_index([{"slug": "largemouth-bass",
                                   "aliases": ["largemouth-bass-0"], "name": "LMB"}])
        self.assertEqual(fresh["largemouth-bass-0"]["name"], "LMB")

    def test_canonical_shortcut_never_shadows_a_real_species(self):
        idx = kb.profile_index([{"slug": "spotted-bass-0", "name": "Suffixed"},
                                {"slug": "spotted-bass", "name": "Real"}])
        self.assertEqual(idx["spotted-bass"]["name"], "Real")


class TestCuratedSlugCanonicalisation(unittest.TestCase):
    def test_curated_key_is_published_canonically(self):
        """curated/bass.json is keyed 'largemouth-bass-0'; the KB should not be."""
        curated = {"largemouth-bass-0", "smallmouth-bass", "spotted-bass"}
        canon = kb.canonical_slug("largemouth-bass-0", curated - {"largemouth-bass-0"})
        self.assertEqual(canon, "largemouth-bass")

    def test_renaming_the_curated_key_makes_it_a_no_op(self):
        curated = {"largemouth-bass", "smallmouth-bass"}
        self.assertEqual(
            kb.canonical_slug("largemouth-bass", curated - {"largemouth-bass"}),
            "largemouth-bass")


class TestArtifactTiers(unittest.TestCase):
    def test_kb_is_mixed_and_names_the_curated_fields(self):
        import _common
        entries = _common.build_entries("build_species_kb.py", kb.artifact_tiers())
        e = entries["species-knowledge/all-species-knowledge.json"]
        self.assertTrue(e["mixed"])
        self.assertEqual(e["tier_detail"]["baits_ranked"], _common.CURATED)
        self.assertEqual(e["tier_detail"]["habitat_envelope"], _common.FEDERAL)
        self.assertEqual(e["tier_detail"]["ncwrc_fishing_tips"],
                         _common.AGENCY_FACTUAL)
        self.assertEqual(entries["species-knowledge/curated/"]["tiers"],
                         [_common.CURATED])


if __name__ == "__main__":
    unittest.main()
