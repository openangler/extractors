"""build_pmtw_layer.py — the structured bait rule.

regulation_summary is prose; bait_rule is the yes/no an app needs to tell an
angler whether the bait in their hand is legal. These tests exist because the
cost of being wrong is a citation, so they lean on the two failure modes that
matter: answering "allowed" when we do not know, and answering a date-dependent
question with a fixed date.

No network: the season maths is pure, and the real-dataset check reads a file.
"""

import datetime
import os
import unittest

import context
import _common
import build_pmtw_layer as pmtw

FEATURES = context.fixture("pmtw_features.json")["features"]

# The whole reach index, if a produced dataset is on this machine ($OPENANGLER_OUT).
REACHES_PATH = os.path.join(_common.resolve_out(), "trout-waters",
                            "pmtw-reaches.json")


def days_of(year):
    day = datetime.date(year, 1, 1)
    while day.year == year:
        yield day
        day += datetime.timedelta(days=1)


class TestResolveAnchor(unittest.TestCase):
    def test_fixed_day(self):
        self.assertEqual(pmtw.resolve_anchor(pmtw.OCT_1, 2026),
                         datetime.date(2026, 10, 1))

    def test_first_saturday_in_june_is_computed_not_stored(self):
        """The date moves every year; storing 2026's answer would rot in 2027."""
        for year, expected in ((2024, (6, 1)), (2025, (6, 7)), (2026, (6, 6)),
                               (2027, (6, 5)), (2028, (6, 3))):
            self.assertEqual(pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, year),
                             datetime.date(year, *expected))

    def test_first_saturday_is_always_a_saturday_in_the_right_month(self):
        for year in range(2020, 2041):
            for anchor, month in ((pmtw.FIRST_SAT_IN_JUNE, 6),
                                  (pmtw.FIRST_SAT_IN_APRIL, 4)):
                day = pmtw.resolve_anchor(anchor, year)
                self.assertEqual(day.weekday(), 5, day)
                self.assertEqual(day.month, month, day)
                self.assertLessEqual(day.day, 7, day)

    def test_nth_weekday(self):
        self.assertEqual(
            pmtw.resolve_anchor({"month": 6, "weekday": "saturday", "nth": 3},
                                2026),
            datetime.date(2026, 6, 20))

    def test_malformed_anchors_raise(self):
        for bad in ({"month": 13, "day": 1}, {"month": 6},
                    {"month": 6, "weekday": "caturday"},
                    {"month": 6, "weekday": "saturday", "nth": 0},
                    {"month": 2, "weekday": "saturday", "nth": 5},
                    {"before": pmtw.FIRST_SAT_IN_JUNE},
                    {"weekday": "friday", "before": {"month": 13, "day": 1}},
                    {"weekday": "caturday", "after": pmtw.FIRST_SAT_IN_JUNE}):
            with self.assertRaises(ValueError, msg=bad):
                pmtw.resolve_anchor(bad, 2026)

    def test_an_anchor_can_be_relative_to_another_anchor(self):
        """"The Friday before the first Saturday in June" is the regulation's

        own wording, and it moves: Jun 5 in 2026, Jun 4 in 2027. Only the
        relationship is stable, so only the relationship is stored.
        """
        for year, friday, saturday in ((2026, (6, 5), (6, 6)),
                                       (2027, (6, 4), (6, 5)),
                                       (2028, (6, 2), (6, 3))):
            got = pmtw.resolve_anchor(pmtw.FRI_BEFORE_FIRST_SAT_IN_JUNE, year)
            self.assertEqual(got, datetime.date(year, *friday))
            self.assertEqual(got.weekday(), 4, got)               # a Friday
            self.assertEqual(
                got + datetime.timedelta(days=1),
                pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, year))
            self.assertEqual(
                pmtw.resolve_anchor(pmtw.SUN_AFTER_FIRST_SAT_IN_JUNE, year),
                datetime.date(year, *saturday) + datetime.timedelta(days=1))

    def test_relative_anchors_hold_for_twenty_years(self):
        for year in range(2020, 2041):
            saturday = pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, year)
            friday = pmtw.resolve_anchor(pmtw.FRI_BEFORE_FIRST_SAT_IN_JUNE, year)
            sunday = pmtw.resolve_anchor(pmtw.SUN_AFTER_FIRST_SAT_IN_JUNE, year)
            self.assertEqual((saturday - friday).days, 1, year)
            self.assertEqual((sunday - saturday).days, 1, year)
            self.assertEqual((friday.weekday(), sunday.weekday()), (4, 6), year)

    def test_before_and_after_mean_strictly_before_and_after(self):
        """Same weekday as the anchor: step a whole week, never zero days."""
        june = pmtw.FIRST_SAT_IN_JUNE
        self.assertEqual(
            pmtw.resolve_anchor({"weekday": "saturday", "before": june}, 2026),
            datetime.date(2026, 5, 30))
        self.assertEqual(
            pmtw.resolve_anchor({"weekday": "saturday", "after": june}, 2026),
            datetime.date(2026, 6, 13))

    def test_the_digest_dates_for_2026_27_fall_out_of_the_rule(self):
        """The 2026-27 digest prints Jun 4 2027 / Jun 5 2027. Same answer."""
        self.assertEqual(
            pmtw.resolve_anchor(pmtw.FRI_BEFORE_FIRST_SAT_IN_JUNE, 2027),
            datetime.date(2027, 6, 4))                # last restricted day
        self.assertEqual(pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, 2027),
                         datetime.date(2027, 6, 5))   # youth session


class TestWindow(unittest.TestCase):
    def test_window_inside_one_year_is_half_open(self):
        june = pmtw.FIRST_SAT_IN_JUNE
        self.assertIsNotNone(pmtw.window_around(june, pmtw.OCT_1,
                                                datetime.date(2026, 6, 6)))
        self.assertIsNone(pmtw.window_around(june, pmtw.OCT_1,
                                             datetime.date(2026, 6, 5)))
        self.assertIsNone(pmtw.window_around(june, pmtw.OCT_1,
                                             datetime.date(2026, 10, 1)))

    def test_window_that_wraps_new_year_resolves_both_years(self):
        w = pmtw.window_around(pmtw.OCT_1, pmtw.FIRST_SAT_IN_JUNE,
                               datetime.date(2026, 11, 15))
        self.assertEqual(w, (datetime.date(2026, 10, 1),
                             datetime.date(2027, 6, 5)))
        w = pmtw.window_around(pmtw.OCT_1, pmtw.FIRST_SAT_IN_JUNE,
                               datetime.date(2027, 1, 15))
        self.assertEqual(w, (datetime.date(2026, 10, 1),
                             datetime.date(2027, 6, 5)))


class TestRuleTable(unittest.TestCase):
    def test_every_class_in_the_prose_table_has_a_bait_rule(self):
        self.assertEqual(set(pmtw.REGS), set(pmtw.BAIT_RULES))

    def test_every_rule_is_well_formed(self):
        for cls, rule in pmtw.BAIT_RULES.items():
            self.assertIn(rule["natural_bait"], pmtw.BAIT_STATES, cls)
            self.assertIn(rule["natural_bait_possession"],
                          pmtw.POSSESSION_STATES, cls)
            self.assertIn(rule["open_to"], pmtw.ANGLER_STATES, cls)
            self.assertTrue(rule["reason"], cls)
            self.assertIn(rule["basis"],
                          (pmtw.BASIS_CLASS, pmtw.BASIS_POSTED), cls)
            if rule["natural_bait"] == pmtw.BAIT_SEASONAL:
                self.assertTrue(rule.get("periods"), cls)
            else:
                self.assertNotIn("periods", rule, cls)

    def test_every_period_and_day_part_is_well_formed(self):
        for cls, rule in pmtw.BAIT_RULES.items():
            entries = list(rule.get("periods") or []) \
                + list(rule.get("closures") or [])
            for entry in entries:
                for anchor in (entry["start"], entry["end"]):
                    self.assertIsInstance(
                        pmtw.resolve_anchor(anchor, 2026), datetime.date)
                for part in entry.get("day_parts") or []:
                    self.assertTrue(part["label"], (cls, entry))
                    self.assertIn(part["open_to"], pmtw.ANGLER_STATES, cls)
                    self.assertTrue(part["reason"], (cls, part["label"]))
                    for bound in (part.get("from"), part.get("to")):
                        self.assertTrue(
                            bound is None or "clock" in bound
                            or "solar" in bound, (cls, bound))

    def test_day_parts_from_a_period_and_a_closure_never_land_on_one_day(self):
        """The evaluator refuses to merge two sub-day timelines, and closes the

        water instead. That is the safe answer, but it is only ever the right
        one if the table never actually does it — so the table is held to it.
        """
        for cls, rule in pmtw.BAIT_RULES.items():
            for year in (2026, 2027, 2028):
                for day in days_of(year):
                    parted = [
                        entry for group in ("periods", "closures")
                        for entry in (rule.get(group) or [])
                        if entry.get("day_parts")
                        and pmtw.window_around(entry["start"], entry["end"], day)]
                    self.assertLessEqual(len(parted), 1, (cls, day))

    def test_lookup_survives_cosmetic_whitespace_and_case_drift(self):
        self.assertEqual(
            pmtw.bait_rule_for("  wild   trout  waters ")["natural_bait"],
            pmtw.BAIT_PROHIBITED)

    def test_source_url_rides_along_with_the_rule(self):
        rule = pmtw.bait_rule_for("Wild Trout Waters", source="https://x/y")
        self.assertEqual(rule["source"], "https://x/y")
        # and callers cannot mutate the shared table through what they got back
        rule["natural_bait"] = "allowed"
        self.assertEqual(pmtw.BAIT_RULES["Wild Trout Waters"]["natural_bait"],
                         pmtw.BAIT_PROHIBITED)


class TestUnrecognisedClass(unittest.TestCase):
    """The dangerous direction is defaulting to permissive. Never do that."""

    def test_bait_rule_for_raises_rather_than_guessing(self):
        for cls in ("Brand New Class", "", None, "Wild Trout"):
            with self.assertRaises(pmtw.UnknownTroutClass, msg=cls):
                pmtw.bait_rule_for(cls)

    def test_the_soft_form_is_unknown_and_says_which_class_it_choked_on(self):
        rule = pmtw.bait_rule_or_unknown("Brand New Class", "https://x/y")
        self.assertEqual(rule["natural_bait"], pmtw.BAIT_UNKNOWN)
        self.assertEqual(rule["basis"], pmtw.BASIS_UNRECOGNISED)
        self.assertIn("Brand New Class", rule["reason"])
        self.assertEqual(rule["source"], "https://x/y")

    def test_an_unknown_class_never_comes_back_bait_legal_on_any_date(self):
        rule = pmtw.bait_rule_or_unknown("Brand New Class")
        for day in (datetime.date(2026, 1, 1), datetime.date(2026, 7, 4),
                    datetime.date(2026, 12, 31)):
            self.assertEqual(pmtw.bait_rule_on(rule, day)["natural_bait"],
                             pmtw.BAIT_UNKNOWN)

    def test_a_reach_with_an_unknown_class_still_builds_but_stays_unknown(self):
        f = {"properties": {"WRC_Class": "Brand New Class"},
             "geometry": {"type": "LineString", "coordinates": [[-82.5, 35.5]]}}
        r = pmtw.reach_record(f, [])
        self.assertEqual(r["bait_rule"]["natural_bait"], pmtw.BAIT_UNKNOWN)
        self.assertEqual(r["bait_rule"]["basis"], pmtw.BASIS_UNRECOGNISED)


class TestWildTrout(unittest.TestCase):
    RULE = pmtw.BAIT_RULES["Wild Trout Waters"]

    def test_natural_bait_is_never_legal(self):
        for month in range(1, 13):
            on = pmtw.bait_rule_on(self.RULE, datetime.date(2026, month, 15))
            self.assertEqual(on["natural_bait"], pmtw.BAIT_PROHIBITED)
            self.assertEqual(on["gear_restriction"],
                             pmtw.GEAR_SINGLE_HOOK_ARTIFICIAL)
            self.assertTrue(on["fishing_open"])
            self.assertEqual(on["open_to"], pmtw.ANGLERS_ALL)

    def test_bait_may_not_even_be_possessed(self):
        """10C .0205(b)(6): "No person shall possess natural bait while fishing

        these waters." Bait in the vest is the violation — a stronger claim
        than "you may not fish it", and one the app can only make if the data
        carries it separately.
        """
        on = pmtw.bait_rule_on(self.RULE, datetime.date(2026, 7, 4))
        self.assertEqual(on["natural_bait_possession"],
                         pmtw.POSSESSION_PROHIBITED)
        self.assertNotEqual(on["natural_bait_possession"],
                            pmtw.POSSESSION_UNKNOWN)


class TestHatcherySupported(unittest.TestCase):
    RULE = pmtw.BAIT_RULES["Hatchery Supported Trout Waters"]

    def test_natural_bait_is_legal(self):
        on = pmtw.bait_rule_on(self.RULE, datetime.date(2026, 7, 4))
        self.assertEqual(on["natural_bait"], pmtw.BAIT_ALLOWED)
        self.assertEqual(on["gear_restriction"], pmtw.GEAR_ANY)
        self.assertTrue(on["fishing_open"])

    def test_the_stocking_closure_shuts_the_water_without_changing_the_bait(self):
        """Legal bait on a closed stream is still the wrong answer to give."""
        closed = pmtw.bait_rule_on(self.RULE, datetime.date(2026, 3, 15))
        self.assertEqual(closed["natural_bait"], pmtw.BAIT_ALLOWED)
        self.assertFalse(closed["fishing_open"])
        self.assertEqual(closed["closure"]["end"], "2026-04-04")

    def test_the_water_reopens_on_the_first_saturday_in_april(self):
        self.assertFalse(pmtw.bait_rule_on(
            self.RULE, datetime.date(2026, 4, 3))["fishing_open"])
        self.assertTrue(pmtw.bait_rule_on(
            self.RULE, datetime.date(2026, 4, 4))["fishing_open"])
        self.assertTrue(pmtw.bait_rule_on(
            self.RULE, datetime.date(2026, 2, 28))["fishing_open"])

    def test_opening_day_opens_at_seven_am_not_at_midnight(self):
        """Same half-day error as the June handover, so it gets the same shape."""
        for year, opening in ((2026, (4, 4)), (2027, (4, 3))):
            day = datetime.date(year, *opening)
            self.assertEqual(pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_APRIL, year),
                             day)
            self.assertEqual(pmtw.bait_rule_on(self.RULE, day)["open_to"],
                             pmtw.ANGLERS_VARIES)
            for hour, open_to in ((3, pmtw.ANGLERS_NONE), (6, pmtw.ANGLERS_NONE),
                                  (7, pmtw.ANGLERS_ALL), (18, pmtw.ANGLERS_ALL)):
                on = pmtw.bait_rule_on(self.RULE, day, datetime.time(hour))
                self.assertEqual(on["open_to"], open_to, (day, hour))
                self.assertEqual(on["fishing_open"],
                                 open_to != pmtw.ANGLERS_NONE, (day, hour))
                # bait was never the constraint here; the clock is
                self.assertEqual(on["natural_bait"], pmtw.BAIT_ALLOWED)

    def test_bait_possession_is_not_restricted_here(self):
        self.assertEqual(
            pmtw.bait_rule_on(self.RULE,
                              datetime.date(2026, 7, 4))["natural_bait_possession"],
            pmtw.POSSESSION_NOT_RESTRICTED)


class TestDelayedHarvest(unittest.TestCase):
    """The class the whole shape exists for: the answer depends on the date."""

    RULE = pmtw.BAIT_RULES["Delayed Harvest Trout Waters"]

    def test_the_static_answer_is_seasonal_not_true_or_false(self):
        self.assertEqual(self.RULE["natural_bait"], pmtw.BAIT_SEASONAL)

    def test_artificial_only_from_oct_1_to_the_first_saturday_in_june(self):
        for day in (datetime.date(2026, 10, 1), datetime.date(2026, 12, 25),
                    datetime.date(2027, 1, 1), datetime.date(2027, 6, 4)):
            on = pmtw.bait_rule_on(self.RULE, day)
            self.assertEqual(on["natural_bait"], pmtw.BAIT_PROHIBITED, day)
            self.assertEqual(on["natural_bait_possession"],
                             pmtw.POSSESSION_PROHIBITED, day)
            self.assertEqual(on["harvest"], pmtw.HARVEST_CATCH_AND_RELEASE, day)
            self.assertEqual(on["gear_restriction"],
                             pmtw.GEAR_SINGLE_HOOK_ARTIFICIAL, day)

    def test_bait_legal_from_the_day_after_the_handover_to_sep_30(self):
        for day in (datetime.date(2027, 6, 6), datetime.date(2027, 7, 4),
                    datetime.date(2027, 9, 30)):
            on = pmtw.bait_rule_on(self.RULE, day)
            self.assertEqual(on["natural_bait"], pmtw.BAIT_ALLOWED, day)
            self.assertEqual(on["harvest"], pmtw.HARVEST_ALLOWED, day)
            self.assertEqual(on["open_to"], pmtw.ANGLERS_ALL, day)
            self.assertTrue(pmtw.may_fish(on["open_to"], pmtw.ANGLER_ADULT), day)

    def test_the_switch_lands_on_the_computed_date_not_a_fixed_one(self):
        """The handover is Jun 6 in 2026 and Jun 5 in 2027 — computed, and the

        day before it is still catch & release in both years.
        """
        for year in (2026, 2027, 2028):
            saturday = pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, year)
            friday = saturday - datetime.timedelta(days=1)
            sunday = saturday + datetime.timedelta(days=1)
            self.assertEqual(
                pmtw.bait_rule_on(self.RULE, friday)["natural_bait"],
                pmtw.BAIT_PROHIBITED, friday)
            self.assertNotEqual(
                pmtw.bait_rule_on(self.RULE, saturday)["open_to"],
                pmtw.ANGLERS_ALL, saturday)
            self.assertEqual(
                pmtw.bait_rule_on(self.RULE, sunday)["open_to"],
                pmtw.ANGLERS_ALL, sunday)

    def test_the_season_carries_its_real_start_and_end_across_new_year(self):
        on = pmtw.bait_rule_on(self.RULE, datetime.date(2027, 2, 1))
        self.assertEqual(on["season"]["label"], "delayed-harvest season")
        self.assertEqual(on["season"]["start"], "2026-10-01")
        self.assertEqual(on["season"]["end"], "2027-06-05")

    def test_the_periods_tile_the_year_with_no_gap_and_no_overlap(self):
        for year in (2026, 2027, 2028):                 # 2028 is a leap year
            for day in days_of(year):
                matched = [p for p in self.RULE["periods"]
                           if pmtw.window_around(p["start"], p["end"], day)]
                self.assertEqual(len(matched), 1, day)
                on = pmtw.bait_rule_on(self.RULE, day)
                self.assertIn(on["natural_bait"],
                              (pmtw.BAIT_ALLOWED, pmtw.BAIT_PROHIBITED), day)
                self.assertIn(on["open_to"], pmtw.ANGLER_STATES, day)
                # and at every hour of it, still exactly one answer
                for hour in range(0, 24, 3):
                    at = pmtw.bait_rule_on(self.RULE, day, datetime.time(hour))
                    self.assertIn(at["natural_bait"],
                                  (pmtw.BAIT_ALLOWED, pmtw.BAIT_PROHIBITED),
                                  (day, hour))
                    self.assertIn(at["open_to"], pmtw.ANGLER_STATES, (day, hour))


class TestDelayedHarvestHandover(unittest.TestCase):
    """The Friday-night / Saturday-morning handover, which is where the old

    boundary was wrong: it flipped natural bait to "allowed" at midnight on the
    first Saturday in June. In fact the restricted season runs to one-half hour
    after sunset on the *Friday* before it, the water is then shut overnight,
    and 6 a.m. to noon on the Saturday is a youth-only session. An adult told
    "allowed" anywhere in there is being told to break the law.
    """

    RULE = pmtw.BAIT_RULES["Delayed Harvest Trout Waters"]

    def days(self, year):
        saturday = pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, year)
        return (saturday - datetime.timedelta(days=2),      # Thursday
                saturday - datetime.timedelta(days=1),      # Friday
                saturday,
                saturday + datetime.timedelta(days=1))      # Sunday

    def test_the_friday_is_still_the_restricted_season(self):
        for year in (2026, 2027):
            _, friday, _, _ = self.days(year)
            on = pmtw.bait_rule_on(self.RULE, friday)
            self.assertEqual(on["natural_bait"], pmtw.BAIT_PROHIBITED, friday)
            self.assertEqual(on["natural_bait_possession"],
                             pmtw.POSSESSION_PROHIBITED, friday)
            self.assertEqual(on["season"]["label"], "delayed-harvest season")

    def test_the_friday_evening_closure_is_carried_not_guessed(self):
        """Sunset needs an ephemeris. Carry the boundary; never invent a time."""
        for year in (2026, 2027):
            _, friday, saturday, _ = self.days(year)
            on = pmtw.bait_rule_on(self.RULE, friday)
            self.assertEqual(on["closure"]["start"], friday.isoformat())
            self.assertEqual(on["closure"]["end"], saturday.isoformat())
            closing, closed = on["day_parts"]
            self.assertEqual(closing["open_to"], pmtw.ANGLERS_ALL)
            self.assertEqual(closed["open_to"], pmtw.ANGLERS_NONE)
            self.assertEqual(closed["from"],
                             {"solar": "sunset", "offset_minutes": 30})
            # unresolvable here, so the day answers "it depends" at any hour —
            # never a confident "open" after dark
            for hour in (9, 21):
                at = pmtw.bait_rule_on(self.RULE, friday, datetime.time(hour))
                self.assertEqual(at["open_to"], pmtw.ANGLERS_VARIES, hour)
                self.assertIsNone(pmtw.may_fish(at["open_to"],
                                                pmtw.ANGLER_ADULT))

    def test_the_saturday_is_closed_then_youth_only_then_open(self):
        for year in (2026, 2027):
            _, _, saturday, _ = self.days(year)
            expected = ((0, 0, pmtw.ANGLERS_NONE), (5, 59, pmtw.ANGLERS_NONE),
                        (6, 0, pmtw.ANGLERS_YOUTH_ONLY),
                        (9, 0, pmtw.ANGLERS_YOUTH_ONLY),
                        (11, 59, pmtw.ANGLERS_YOUTH_ONLY),
                        (12, 0, pmtw.ANGLERS_ALL), (23, 59, pmtw.ANGLERS_ALL))
            for hour, minute, open_to in expected:
                on = pmtw.bait_rule_on(self.RULE, saturday,
                                       datetime.time(hour, minute))
                self.assertEqual(on["open_to"], open_to,
                                 (saturday, hour, minute))
                self.assertEqual(on["fishing_open"],
                                 open_to != pmtw.ANGLERS_NONE)

    def test_an_adult_is_never_told_they_may_fish_before_noon(self):
        """The bug, stated as the thing it costs: a citation before lunchtime."""
        for year in (2026, 2027, 2028):
            _, _, saturday, _ = self.days(year)
            for hour in range(0, 12):
                on = pmtw.bait_rule_on(self.RULE, saturday,
                                       datetime.time(hour, 30))
                self.assertIs(pmtw.may_fish(on["open_to"], pmtw.ANGLER_ADULT),
                              False, (saturday, hour))
                self.assertNotEqual(on["open_to"], pmtw.ANGLERS_ALL)
            for hour in range(12, 24):
                on = pmtw.bait_rule_on(self.RULE, saturday,
                                       datetime.time(hour, 30))
                self.assertIs(pmtw.may_fish(on["open_to"], pmtw.ANGLER_ADULT),
                              True, (saturday, hour))

    def test_a_youth_may_fish_the_morning_session_but_not_the_closure(self):
        for year in (2026, 2027):
            _, _, saturday, _ = self.days(year)
            morning = pmtw.bait_rule_on(self.RULE, saturday,
                                        datetime.time(9, 0))
            self.assertIs(pmtw.may_fish(morning["open_to"], pmtw.ANGLER_YOUTH),
                          True)
            self.assertEqual(morning["natural_bait"], pmtw.BAIT_ALLOWED)
            self.assertEqual(morning["gear_restriction"], pmtw.GEAR_ANY)
            night = pmtw.bait_rule_on(self.RULE, saturday, datetime.time(3, 0))
            self.assertIs(pmtw.may_fish(night["open_to"], pmtw.ANGLER_YOUTH),
                          False)

    def test_the_youth_session_is_its_own_state_not_a_flavour_of_allowed(self):
        for year in (2026, 2027):
            _, _, saturday, _ = self.days(year)
            labels = [p["label"]
                      for p in pmtw.bait_rule_on(self.RULE, saturday)["day_parts"]]
            self.assertEqual(labels, ["closed overnight", "youth-only session",
                                      "open to all anglers"])
            self.assertIn(pmtw.ANGLERS_YOUTH_ONLY, pmtw.ANGLER_STATES)
            self.assertNotEqual(pmtw.ANGLERS_YOUTH_ONLY, pmtw.BAIT_ALLOWED)

    def test_without_a_time_the_handover_day_says_it_varies(self):
        """No time in hand is not permission. It is "ask me again with one"."""
        for year in (2026, 2027):
            _, _, saturday, _ = self.days(year)
            on = pmtw.bait_rule_on(self.RULE, saturday)
            self.assertEqual(on["open_to"], pmtw.ANGLERS_VARIES)
            self.assertIsNone(pmtw.may_fish(on["open_to"], pmtw.ANGLER_ADULT))
            self.assertEqual(len(on["day_parts"]), 3)

    def test_the_2026_and_2027_handovers_fall_on_different_dates(self):
        self.assertEqual(self.days(2026)[2], datetime.date(2026, 6, 6))
        self.assertEqual(self.days(2027)[2], datetime.date(2027, 6, 5))
        # the old, wrong answer: bait "allowed" all day on the first Saturday
        for saturday in (datetime.date(2026, 6, 6), datetime.date(2027, 6, 5)):
            on = pmtw.bait_rule_on(self.RULE, saturday, datetime.time(9, 0))
            self.assertIsNot(pmtw.may_fish(on["open_to"], pmtw.ANGLER_ADULT),
                             True, saturday)


class TestCatchAndRelease(unittest.TestCase):
    RULE = pmtw.BAIT_RULES[
        "Catch and Release/Artificial Flies and Lures Only Trout Waters"]

    def test_flies_and_lures_only_year_round(self):
        for month in range(1, 13):
            on = pmtw.bait_rule_on(self.RULE, datetime.date(2026, month, 15))
            self.assertEqual(on["natural_bait"], pmtw.BAIT_PROHIBITED)
            self.assertEqual(on["gear_restriction"],
                             pmtw.GEAR_SINGLE_HOOK_FLIES_AND_LURES)
            self.assertEqual(on["harvest"], pmtw.HARVEST_CATCH_AND_RELEASE)

    def test_flies_and_lures_is_not_the_same_gear_rule_as_lures(self):
        """.0205(b)(2) is flies AND lures; (b)(6) is lures. Don't collapse them."""
        self.assertNotEqual(pmtw.GEAR_SINGLE_HOOK_FLIES_AND_LURES,
                            pmtw.GEAR_SINGLE_HOOK_ARTIFICIAL)
        self.assertEqual(pmtw.BAIT_RULES["Wild Trout Waters"]["gear_restriction"],
                         pmtw.GEAR_SINGLE_HOOK_ARTIFICIAL)
        self.assertEqual(self.RULE["gear_restriction"],
                         pmtw.GEAR_SINGLE_HOOK_FLIES_AND_LURES)

    def test_possession_is_unknown_because_the_rule_is_silent_on_it(self):
        """Wild Trout Waters ban possessing bait; these waters govern only what

        may be used. Silence is not permission, so it is recorded as unknown
        rather than as "not restricted".
        """
        self.assertEqual(self.RULE["natural_bait_possession"],
                         pmtw.POSSESSION_UNKNOWN)
        self.assertNotEqual(self.RULE["natural_bait_possession"],
                            pmtw.POSSESSION_NOT_RESTRICTED)


class TestSpecialRegulation(unittest.TestCase):
    """"Go read the sign" is the honest answer, and must not read as "allowed"."""

    RULE = pmtw.BAIT_RULES["Special Regulation Trout Waters"]

    def test_it_is_unknown_and_distinguishable_from_allowed(self):
        self.assertEqual(self.RULE["natural_bait"], pmtw.BAIT_UNKNOWN)
        self.assertNotEqual(self.RULE["natural_bait"], pmtw.BAIT_ALLOWED)
        self.assertEqual(self.RULE["basis"], pmtw.BASIS_POSTED)
        self.assertIn("posted", self.RULE["reason"].lower())

    def test_no_date_makes_it_knowable(self):
        for day in (datetime.date(2026, 1, 1), datetime.date(2026, 6, 6),
                    datetime.date(2026, 11, 20)):
            self.assertEqual(pmtw.bait_rule_on(self.RULE, day)["natural_bait"],
                             pmtw.BAIT_UNKNOWN)

    def test_unknown_from_signage_differs_from_unknown_from_a_bad_class(self):
        other = pmtw.bait_rule_or_unknown("Brand New Class")
        self.assertEqual(other["natural_bait"], self.RULE["natural_bait"])
        self.assertNotEqual(other["basis"], self.RULE["basis"])


class TestEvaluatorIsTotal(unittest.TestCase):
    def test_a_date_no_period_claims_is_unknown_not_allowed(self):
        holed = {"natural_bait": pmtw.BAIT_SEASONAL, "basis": pmtw.BASIS_CLASS,
                 "reason": "", "periods": [
                     {"start": {"month": 6, "day": 1},
                      "end": {"month": 7, "day": 1},
                      "natural_bait": pmtw.BAIT_ALLOWED}]}
        self.assertEqual(
            pmtw.bait_rule_on(holed, datetime.date(2026, 6, 15))["natural_bait"],
            pmtw.BAIT_ALLOWED)
        gap = pmtw.bait_rule_on(holed, datetime.date(2026, 9, 1))
        self.assertEqual(gap["natural_bait"], pmtw.BAIT_UNKNOWN)
        self.assertIn("2026-09-01", gap["reason"])

    def test_an_empty_rule_is_unknown(self):
        self.assertEqual(pmtw.bait_rule_on({}, datetime.date(2026, 5, 1)),
                         {"natural_bait": pmtw.BAIT_UNKNOWN,
                          "natural_bait_possession": pmtw.POSSESSION_UNKNOWN,
                          "gear_restriction": None,
                          "harvest": pmtw.HARVEST_UNKNOWN,
                          "open_to": pmtw.ANGLERS_UNKNOWN, "reason": "",
                          "basis": pmtw.BASIS_UNRECOGNISED,
                          "fishing_open": True, "season": None,
                          "closure": None, "day_parts": None, "at": None})

    def test_a_moment_can_be_given_as_a_datetime_or_as_a_date_and_time(self):
        rule = pmtw.BAIT_RULES["Delayed Harvest Trout Waters"]
        both = (pmtw.bait_rule_on(rule, datetime.datetime(2026, 6, 6, 9, 0)),
                pmtw.bait_rule_on(rule, datetime.date(2026, 6, 6),
                                  datetime.time(9, 0)))
        for on in both:
            self.assertEqual(on["at"], "09:00")
        self.assertEqual(*both)


class TestReachRecord(unittest.TestCase):
    def test_the_prose_is_kept_alongside_the_structure(self):
        r = pmtw.reach_record(FEATURES[0], [])
        self.assertIn("7-trout creel", r["regulation_summary"])
        self.assertEqual(r["bait_rule"]["natural_bait"], pmtw.BAIT_ALLOWED)

    def test_every_fixture_reach_lands_in_a_defined_state(self):
        for f in FEATURES:
            r = pmtw.reach_record(f, [])
            self.assertIn(r["bait_rule"]["natural_bait"], pmtw.BAIT_STATES)
            self.assertNotEqual(r["bait_rule"]["basis"],
                                pmtw.BASIS_UNRECOGNISED, r["wrc_class"])
            self.assertEqual(r["bait_rule"]["source"], r["ncwrc_link"])


class TestProvenance(unittest.TestCase):
    def test_bait_rule_is_curated_but_its_source_url_is_the_agency_s(self):
        fields = _common.build_entries(
            "build_pmtw_layer.py",
            pmtw.artifact_tiers(True))["trout-waters/pmtw-reaches.json"]["fields"]
        self.assertEqual(_common.field_tier(fields, "bait_rule"),
                         _common.CURATED)
        self.assertEqual(_common.field_tier(fields, "bait_rule.periods.reason"),
                         _common.CURATED)
        self.assertEqual(_common.field_tier(fields, "bait_rule.source"),
                         _common.AGENCY_FACTUAL)

    def test_every_field_of_a_reach_carrying_a_bait_rule_has_a_tier(self):
        reaches = [r for r in (pmtw.reach_record(f, []) for f in FEATURES) if r]
        self.assertTrue(any(r["bait_rule"].get("periods") for r in reaches),
                        "fixture should include a Delayed Harvest reach")
        entries = _common.build_entries(
            "build_pmtw_layer.py", pmtw.artifact_tiers(True, sample=reaches))
        fields = entries["trout-waters/pmtw-reaches.json"]["fields"]
        self.assertEqual(fields["coverage"], "complete")


@unittest.skipUnless(os.path.exists(REACHES_PATH),
                     f"no produced dataset at {REACHES_PATH} "
                     "(set $OPENANGLER_OUT to run this)")
class TestRealDataset(unittest.TestCase):
    """Classify every reach in a produced dataset. Read-only; no network."""

    @classmethod
    def setUpClass(cls):
        import json
        with open(REACHES_PATH) as f:
            cls.reaches = json.load(f)
        cls.rules = [pmtw.bait_rule_or_unknown(r["wrc_class"], r["ncwrc_link"])
                     for r in cls.reaches]

    def test_every_reach_lands_in_a_defined_state(self):
        for reach, rule in zip(self.reaches, self.rules):
            self.assertIn(rule["natural_bait"], pmtw.BAIT_STATES,
                          reach["wrc_class"])

    def test_no_reach_falls_through_to_an_unrecognised_class(self):
        unrecognised = sorted({r["wrc_class"] for r, rule
                               in zip(self.reaches, self.rules)
                               if rule["basis"] == pmtw.BASIS_UNRECOGNISED})
        self.assertEqual(unrecognised, [])

    def test_the_distribution_matches_the_classes_in_the_data(self):
        from collections import Counter
        by_state = Counter(rule["natural_bait"] for rule in self.rules)
        by_class = Counter(r["wrc_class"] for r in self.reaches)
        self.assertEqual(by_state[pmtw.BAIT_PROHIBITED],
                         by_class["Wild Trout Waters"]
                         + by_class["Catch and Release/Artificial Flies and "
                                    "Lures Only Trout Waters"])
        self.assertEqual(by_state[pmtw.BAIT_ALLOWED],
                         by_class["Hatchery Supported Trout Waters"])
        self.assertEqual(by_state[pmtw.BAIT_SEASONAL],
                         by_class["Delayed Harvest Trout Waters"])
        self.assertEqual(by_state[pmtw.BAIT_UNKNOWN],
                         by_class["Special Regulation Trout Waters"])
        self.assertEqual(sum(by_state.values()), len(self.reaches))

    def test_every_reach_answers_on_every_kind_of_day(self):
        for day in (datetime.date(2026, 1, 15), datetime.date(2026, 3, 15),
                    datetime.date(2026, 6, 5), datetime.date(2026, 6, 6),
                    datetime.date(2026, 7, 4), datetime.date(2026, 10, 1)):
            for reach, rule in zip(self.reaches, self.rules):
                on = pmtw.bait_rule_on(rule, day)
                self.assertIn(on["natural_bait"],
                              (pmtw.BAIT_ALLOWED, pmtw.BAIT_PROHIBITED,
                               pmtw.BAIT_UNKNOWN), (reach["wrc_class"], day))
                # never seasonal once a date is applied — that is the point
                self.assertNotEqual(on["natural_bait"], pmtw.BAIT_SEASONAL)
                self.assertIn(on["open_to"], pmtw.ANGLER_STATES,
                              (reach["wrc_class"], day))
                self.assertIn(on["natural_bait_possession"],
                              pmtw.POSSESSION_STATES, (reach["wrc_class"], day))

    def test_every_reach_answers_at_a_moment_too(self):
        for at in (datetime.time(3, 0), datetime.time(9, 0),
                   datetime.time(13, 0), datetime.time(22, 0)):
            for day in (datetime.date(2026, 4, 4), datetime.date(2026, 6, 6)):
                for reach, rule in zip(self.reaches, self.rules):
                    on = pmtw.bait_rule_on(rule, day, at)
                    self.assertIn(on["open_to"], pmtw.ANGLER_STATES,
                                  (reach["wrc_class"], day, at))
                    self.assertEqual(on["fishing_open"],
                                     on["open_to"] != pmtw.ANGLERS_NONE)

    def test_no_reach_invites_an_adult_into_the_youth_session(self):
        """The bug, checked over the whole produced layer rather than one rule."""
        for year in (2026, 2027):
            saturday = pmtw.resolve_anchor(pmtw.FIRST_SAT_IN_JUNE, year)
            for reach, rule in zip(self.reaches, self.rules):
                if reach["wrc_class"] != "Delayed Harvest Trout Waters":
                    continue
                for hour in range(0, 12):
                    on = pmtw.bait_rule_on(rule, saturday,
                                           datetime.time(hour, 30))
                    self.assertIs(
                        pmtw.may_fish(on["open_to"], pmtw.ANGLER_ADULT), False,
                        (reach["stream_name"], saturday, hour))
                afternoon = pmtw.bait_rule_on(rule, saturday,
                                              datetime.time(13, 0))
                self.assertIs(
                    pmtw.may_fish(afternoon["open_to"], pmtw.ANGLER_ADULT),
                    True, (reach["stream_name"], saturday))

    def test_bait_possession_bans_land_where_the_regulation_puts_them(self):
        """Wild Trout all year, Delayed Harvest only in its restricted season."""
        from collections import Counter
        by_class = Counter(r["wrc_class"] for r in self.reaches)
        for day, expected in (
                (datetime.date(2026, 7, 4), by_class["Wild Trout Waters"]),
                (datetime.date(2026, 12, 1),
                 by_class["Wild Trout Waters"]
                 + by_class["Delayed Harvest Trout Waters"])):
            banned = sum(1 for rule in self.rules
                         if pmtw.bait_rule_on(rule, day)["natural_bait_possession"]
                         == pmtw.POSSESSION_PROHIBITED)
            self.assertEqual(banned, expected, day)

    def test_the_prose_and_the_structure_agree(self):
        """Cross-check: where the prose says no natural bait, so does the rule."""
        for reach, rule in zip(self.reaches, self.rules):
            prose = reach["regulation_summary"].lower()
            if "no natural bait" in prose:
                self.assertEqual(rule["natural_bait"], pmtw.BAIT_PROHIBITED,
                                 reach["wrc_class"])
            if "any bait or lure incl. natural bait" in prose:
                self.assertEqual(rule["natural_bait"], pmtw.BAIT_ALLOWED,
                                 reach["wrc_class"])


if __name__ == "__main__":
    unittest.main()
