"""SC pipeline — SCDNR record normalisation and the one-state-per-dataset guard."""

import json
import os
import tempfile
import unittest

import context
import enrich_sc_usgs
import extract_sc_fishing as sc
import manifest


class TestNormalize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.features = context.fixture("scdnr_water_access.json")
        cls.records, cls.counts = sc.build(cls.features)
        cls.by_id = {r["locationID"]: r for r in cls.records}

    def test_saltwater_and_closed_points_are_dropped(self):
        self.assertEqual(self.counts["features"], 9)
        self.assertEqual(self.counts["saltwater"], 3)
        self.assertEqual(self.counts["kept"], 6)
        self.assertNotIn("BR298", self.by_id)

    def test_record_has_the_nc_shape(self):
        r = self.by_id["BR224"]
        self.assertEqual(r["state"], "US-SC")
        self.assertEqual(r["locationName"], "Blue Hole")
        self.assertEqual(r["waterbodyName"], "Lake Russell")
        self.assertEqual((r["county"], r["region"]), ("Abbeville", "Piedmont"))
        self.assertTrue(r["boatRamp"])
        self.assertTrue(r["fishingPierAccess"])      # FishingPier: Yes on a ramp
        self.assertIsNone(r["troutStocked"])         # SCDNR does not say; not False
        self.assertEqual(r["facilities"]["Owner"], "USACE")
        self.assertEqual(r["facilities"]["_source"], "SCDNR Public Water Access")

    def test_hybrid_label_is_cleaned(self):
        names = [s["commonName"] for s in self.by_id["BR224"]["speciesInfo"]]
        self.assertIn("Hybrid Striped Bass", names)
        self.assertFalse(any("*" in n for n in names))
        self.assertTrue(all(s["stocked"] is None and s["wild"] is None
                            for s in self.by_id["BR224"]["speciesInfo"]))

    def test_trout_water_flag(self):
        r = self.by_id["BR594"]
        self.assertTrue(r["troutWater"])
        self.assertEqual(r["region"], "Mountains")

    def test_missing_id_falls_back_to_global_id(self):
        no_id = [r for r in self.records if r["county"] == "Aiken"]
        self.assertEqual(len(no_id), 1)
        self.assertRegex(no_id[0]["locationID"], r"^[0-9a-fA-F-]{36}$")

    def test_county_spelling_is_normalised(self):
        self.assertEqual(self.by_id["FA507"]["county"], "Berkeley")
        self.assertEqual(sc.clean_county("Charleston County"), "Charleston")
        self.assertIsNone(sc.clean_county("  "))

    def test_access_type_flags(self):
        self.assertTrue(self.by_id["PL001"]["canoeAccess"])
        self.assertFalse(self.by_id["PL001"]["boatRamp"])
        self.assertTrue(self.by_id["FA082"]["fishingPierAccess"])

    def test_every_sc_county_has_a_region(self):
        regions = sc.MOUNTAINS | sc.PIEDMONT | sc.COASTAL
        self.assertEqual(len(regions), 46)
        self.assertFalse(sc.MOUNTAINS & sc.PIEDMONT or sc.PIEDMONT & sc.COASTAL
                         or sc.MOUNTAINS & sc.COASTAL)

    def test_species_are_deduplicated(self):
        info = sc.species_info("Bluegill, bluegill , Largemouth Bass,")
        self.assertEqual([s["commonName"] for s in info], ["Bluegill", "Largemouth Bass"])


class TestTiers(unittest.TestCase):
    def test_extract_artifacts_are_valid(self):
        manifest.build_entries("extract_sc_fishing.py", sc.artifact_tiers())

    def test_enrichment_fields_are_fully_tagged(self):
        sample = [{"locationID": "BR224", "locationName": "Blue Hole",
                   "waterbodyName": "Lake Russell", "elevation_m": 100.0,
                   "stream_order": 7, "slope": 0.0, "drainage_area_sqkm": 1.0,
                   "mean_annual_flow_cfs": 1.0, "nhd_name": "x", "name_matched": True,
                   "nearest_gage": {"id": "1", "name": "g", "km": 1.0, "url": "u"}}]
        entries = manifest.build_entries("enrich_sc_usgs.py",
                                         enrich_sc_usgs.artifact_tiers(sample))
        self.assertEqual(entries["fishing-areas/enrichment.json"]["fields"]["coverage"], "complete")


class TestStateGuard(unittest.TestCase):
    def _manifest(self, d, body):
        with open(os.path.join(d, manifest.MANIFEST_NAME), "w") as f:
            json.dump(body, f)

    def test_legacy_manifest_with_artifacts_is_nc(self):
        self.assertEqual(manifest.dataset_state({"artifacts": {"a": {}}}), "US-NC")
        self.assertIsNone(manifest.dataset_state({}))
        self.assertEqual(manifest.dataset_state({"state": "US-SC"}), "US-SC")

    def test_sc_refuses_the_nc_dataset(self):
        sc_common = context.load_sc_common()
        with tempfile.TemporaryDirectory() as d:
            self._manifest(d, {"artifacts": {"fishing-areas/all-locations.json": {}}})
            with self.assertRaises(SystemExit):
                sc_common.resolve_out(d)

    def test_sc_accepts_a_new_or_sc_dataset(self):
        sc_common = context.load_sc_common()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sc_common.resolve_out(d), d)
            self._manifest(d, {"state": "US-SC", "artifacts": {"x": {}}})
            self.assertEqual(sc_common.resolve_out(d), d)

    def test_sc_has_no_default_output(self):
        sc_common = context.load_sc_common()
        saved = os.environ.pop(manifest.OUT_ENV, None)
        try:
            with self.assertRaises(SystemExit):
                sc_common.resolve_out(None)
        finally:
            if saved is not None:
                os.environ[manifest.OUT_ENV] = saved

    def test_record_artifacts_stamps_the_state(self):
        sc_common = context.load_sc_common()
        with tempfile.TemporaryDirectory() as d:
            m = sc_common.record_artifacts(d, "extract_sc_fishing.py", sc.artifact_tiers())
            self.assertEqual(m["state"], "US-SC")


if __name__ == "__main__":
    unittest.main()
