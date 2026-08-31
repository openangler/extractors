#!/usr/bin/env python3
"""
build_pmtw_layer.py — turn the 1,809 Public Mountain Trout Water reaches into a
queryable trout "where" layer.

For each PMTW stream reach: stream name, reach description, WRC classification +
a plain-language REGULATION summary + a structured bait_rule, Mountain Heritage
flag, length, a representative midpoint coordinate, the county (point-in-polygon
against our county boundaries), and midpoint elevation (USGS 3DEP).

bait_rule answers "is natural bait legal here?" without parsing the prose:
allowed / prohibited / seasonal / unknown, plus whether bait may even be
possessed, the season rules for Delayed Harvest water, who the water is open to
(the Delayed Harvest opening morning is a youth-only session), and an explicit
unknown where the class says to read the signage.
bait_rule_on(rule, date[, time]) flattens it for one day, or one moment.

Output -> trout-waters/pmtw-reaches.json     (the reach index)
       -> trout-waters/pmtw-summary.json      (counts by class & county)

    python3 build_pmtw_layer.py                # with elevation (1,809 EPQS calls)
    python3 build_pmtw_layer.py --no-elevation # fast, skip elevation
    python3 build_pmtw_layer.py --out /data/nc-fishing-guide-data
"""

import argparse
import copy
import datetime
import glob
import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import _common
from _common import AGENCY_FACTUAL, CURATED, FEDERAL, QUERY

EPQS = "https://epqs.nationalmap.gov/v1/json"

# plain-language regulation summary per WRC classification (verify current regs
# at the NCWRC link on each reach — these are standard NC trout-water rules).
REGS = {
    "Wild Trout Waters":
        "Single-hook artificial lures only (no natural bait — you may not even "
        "possess it while fishing). 7\" min size, 4-trout creel. Open all year.",
    "Hatchery Supported Trout Waters":
        "Any bait or lure incl. natural bait. No size limit, 7-trout creel. Open all "
        "year EXCEPT closed Mar 1 – 7 a.m. first Sat in April (stocking).",
    "Delayed Harvest Trout Waters":
        "Oct 1 – ½ hour after sunset on the FRIDAY before the first Sat in June: "
        "CATCH & RELEASE, single-hook artificial lures only, no harvest, no "
        "natural bait even in possession. Then closed to all fishing overnight; "
        "6 a.m.–noon that Saturday is a YOUTH-ONLY session (under 16, no bait or "
        "lure restriction). Noon that Saturday – Sep 30: hatchery-supported rules "
        "(harvest & any bait). Heavily stocked — top numbers water.",
    "Catch and Release/Artificial Flies and Lures Only Trout Waters":
        "Catch & release only, single-hook artificial FLIES AND LURES only. No "
        "harvest, year-round.",
    "Special Regulation Trout Waters":
        "Special site-specific regulations — check the posted/NCWRC rules for this "
        "water before fishing.",
}

# ---- bait legality, structured -------------------------------------------------
#
# REGS above is prose. It has to be: it carries size and creel limits that no
# enum can hold. But an app that answers "is the bait in my hand legal where I
# am standing?" should not have to parse English to do it, in exactly the
# situation where being wrong means a citation. bait_rule below is that one
# question, structured, alongside the prose rather than instead of it.
#
# It is deliberately NOT a boolean:
#   * Delayed Harvest water is artificial-only from Oct 1 until one-half hour
#     after sunset on the Friday before the first Saturday in June, and
#     bait-legal for the rest of the year, so the honest answer is "seasonal,
#     here are the periods", not true or false.
#   * That handover is not even a clean day boundary. The water shuts overnight
#     and reopens the next morning as a youth-only session, so one calendar day
#     holds three different answers — hence sub-day parts on a period, and an
#     open_to field that says who may fish, not just what they may fish with.
#   * Special Regulation water genuinely means "read the sign". "unknown" is
#     the correct answer there, and a consumer must be able to tell it apart
#     from "allowed" — which a boolean cannot do.
#
# Sourced from 15A NCAC 10C .0205(b) (the classifications) and .0316 (seasons,
# creel limits, the Delayed Harvest closure); docs/nc-bait-regulations.md
# carries the verbatim text and the citations.

BAIT_ALLOWED = "allowed"
BAIT_PROHIBITED = "prohibited"
BAIT_SEASONAL = "seasonal"        # date-dependent; see rule["periods"]
BAIT_UNKNOWN = "unknown"          # not known here — read the posted rules
BAIT_STATES = (BAIT_ALLOWED, BAIT_PROHIBITED, BAIT_SEASONAL, BAIT_UNKNOWN)

# Using bait and *carrying* it are different offences. 10C .0205(b)(6): "No
# person shall possess natural bait while fishing these waters" (Wild Trout),
# and .0205(b)(3) says the same of Delayed Harvest water in season — bait in
# the vest is the violation, no cast required. Waters whose rule only governs
# what may be *used* (Catch and Release, .0205(b)(2)) are recorded as unknown
# rather than as permission we were never given.
POSSESSION_PROHIBITED = "prohibited"
POSSESSION_NOT_RESTRICTED = "not_restricted"
POSSESSION_UNKNOWN = "unknown"
POSSESSION_STATES = (POSSESSION_PROHIBITED, POSSESSION_NOT_RESTRICTED,
                     POSSESSION_UNKNOWN)

GEAR_ANY = "any_bait_or_lure"
# Two different restrictions, and they must not be collapsed: Wild Trout Waters
# are artificial *lures* (.0205(b)(6)); Catch and Release waters are artificial
# *flies and lures* (.0205(b)(2)). Both require one single hook.
GEAR_SINGLE_HOOK_ARTIFICIAL = "single_hook_artificial_lures"
GEAR_SINGLE_HOOK_FLIES_AND_LURES = "single_hook_artificial_flies_and_lures"

HARVEST_ALLOWED = "allowed"
HARVEST_CATCH_AND_RELEASE = "catch_and_release"
HARVEST_UNKNOWN = "unknown"

# Who may fish, which is a different question from what they may fish with, and
# the reason the Delayed Harvest opening day is not simply "bait allowed": from
# 6 a.m. to noon only anglers under 16 may fish it. An adult reading "allowed"
# that morning is being handed a citation, so the youth session gets its own
# value here instead of hiding inside natural_bait.
ANGLERS_ALL = "all_anglers"
ANGLERS_YOUTH_ONLY = "youth_only"      # under 16 — 10C .0205(a)(5)
ANGLERS_NONE = "closed"
ANGLERS_VARIES = "varies_by_time"      # more than one answer today; see day_parts
ANGLERS_UNKNOWN = "unknown"
ANGLER_STATES = (ANGLERS_ALL, ANGLERS_YOUTH_ONLY, ANGLERS_NONE,
                 ANGLERS_VARIES, ANGLERS_UNKNOWN)

ANGLER_ADULT = "adult"                 # 16 or older
ANGLER_YOUTH = "youth"                 # under 16

# how the rule was arrived at, so "unknown" is never ambiguous: the class told
# us, the class told us to read the signage, or we did not recognise the class.
BASIS_CLASS = "wrc_class"
BASIS_POSTED = "posted_signage"
BASIS_UNRECOGNISED = "unrecognised_class"

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}

# Calendar anchors. "First Saturday in June" is a rule, not a date — storing the
# 2026 answer would quietly rot in 2027, so the rule is what gets stored. The
# regulation also states boundaries *relative* to such an anchor ("the Friday
# before the first Saturday in June"), so an anchor can be relative to another.
MAR_1 = {"month": 3, "day": 1}
OCT_1 = {"month": 10, "day": 1}
FIRST_SAT_IN_APRIL = {"month": 4, "weekday": "saturday", "nth": 1}
FIRST_SAT_IN_JUNE = {"month": 6, "weekday": "saturday", "nth": 1}
FRI_BEFORE_FIRST_SAT_IN_JUNE = {"weekday": "friday", "before": FIRST_SAT_IN_JUNE}
SUN_AFTER_FIRST_SAT_IN_JUNE = {"weekday": "sunday", "after": FIRST_SAT_IN_JUNE}
SUN_AFTER_FIRST_SAT_IN_APRIL = {"weekday": "sunday", "after": FIRST_SAT_IN_APRIL}

# Sub-day boundaries, for the days that hold more than one answer. A clock
# boundary is exact; a solar one ("one-half hour after sunset") is just as real
# in the regulation but needs an ephemeris this stdlib-only extractor has no
# business faking, so it is carried through symbolically for a consumer that
# has sunset times to resolve. Nothing here ever guesses a sunset: an
# unresolvable boundary makes the day answer "varies_by_time", never "open".
SUNSET_PLUS_30 = {"solar": "sunset", "offset_minutes": 30}
SIX_AM = {"clock": "06:00"}
SEVEN_AM = {"clock": "07:00"}
NOON = {"clock": "12:00"}


class UnknownTroutClass(ValueError):
    """A WRC classification with no bait rule. Never guess one."""


def _weekday_of(anchor):
    if "weekday" not in anchor:
        raise ValueError(f"anchor {anchor!r} needs a day or a weekday")
    weekday = WEEKDAYS.get(str(anchor["weekday"]).strip().lower())
    if weekday is None:
        raise ValueError(f"bad weekday in anchor {anchor!r}")
    return weekday


def _nth_of(anchor):
    nth = anchor.get("nth", 1)
    if not isinstance(nth, int) or nth < 1:
        raise ValueError(f"bad nth in anchor {anchor!r}")
    return nth


def resolve_anchor(anchor, year):
    """A calendar anchor -> the date it lands on in `year`.

        {"month": 10, "day": 1}                            -> Oct 1
        {"month": 6, "weekday": "saturday", "nth": 1}      -> first Sat in June
        {"weekday": "friday", "before": FIRST_SAT_IN_JUNE} -> the Friday before it
        {"weekday": "sunday", "after": FIRST_SAT_IN_JUNE}  -> the Sunday after it

    The relative forms are not a convenience: the regulation itself states the
    end of the Delayed Harvest season as "the Friday before the first Saturday
    of the following June" — a Friday that moves with the Saturday, one day in
    2026 and another in 2027. Written as an offset from the anchor it stays
    right; written as a date it is wrong within twelve months. `before` and
    `after` both mean strictly before/after, so an anchor that already falls on
    the named weekday steps a whole week.
    """
    for key, direction in (("before", -1), ("after", 1)):
        if key in anchor:
            base = resolve_anchor(anchor[key], year)
            weekday, nth = _weekday_of(anchor), _nth_of(anchor)
            steps = (direction * (weekday - base.weekday())) % 7 or 7
            return base + datetime.timedelta(
                days=direction * (steps + 7 * (nth - 1)))
    month = anchor.get("month")
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError(f"bad month in anchor {anchor!r}")
    if "day" in anchor:
        return datetime.date(year, month, anchor["day"])
    weekday, nth = _weekday_of(anchor), _nth_of(anchor)
    first = datetime.date(year, month, 1)
    day = first + datetime.timedelta(
        days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    if day.month != month:
        raise ValueError(f"anchor {anchor!r} does not occur in {year}")
    return day


def window_around(start, end, day):
    """[start, end) resolved around `day`, or None if `day` falls outside it.

    Half-open, so a set of periods can tile the year with no gap and no
    overlap: the first Saturday in June both ends the delayed-harvest season
    and opens the youth session, and belongs to exactly one of them. Windows
    that wrap New Year (Oct 1 -> first Sat in June) are resolved into the pair
    of years that actually contains `day`.

    Day-level on purpose. A boundary that falls part-way through a day — 6 a.m.,
    noon, one-half hour after sunset — is not expressed by moving this window;
    it is expressed by day_parts inside the period or closure that owns the day,
    so that the tiling stays exact.
    """
    year = day.year
    s, e = resolve_anchor(start, year), resolve_anchor(end, year)
    if s < e:                                    # inside one calendar year
        return (s, e) if s <= day < e else None
    if day >= s:                                 # wraps: day is before New Year
        return (s, resolve_anchor(end, year + 1))
    if day < e:                                  # wraps: day is after New Year
        return (resolve_anchor(start, year - 1), e)
    return None


BAIT_RULES = {
    "Wild Trout Waters": {
        "natural_bait": BAIT_PROHIBITED,
        "natural_bait_possession": POSSESSION_PROHIBITED,
        "gear_restriction": GEAR_SINGLE_HOOK_ARTIFICIAL,
        "harvest": HARVEST_ALLOWED,
        "open_to": ANGLERS_ALL,
        "basis": BASIS_CLASS,
        "reason": "Wild Trout Waters take artificial lures with one single hook "
                  "only, all year — natural bait is never legal, and 10C "
                  ".0205(b)(6) bans possessing it while fishing these waters at "
                  "all, not merely using it.",
    },
    "Hatchery Supported Trout Waters": {
        "natural_bait": BAIT_ALLOWED,
        "natural_bait_possession": POSSESSION_NOT_RESTRICTED,
        "gear_restriction": GEAR_ANY,
        "harvest": HARVEST_ALLOWED,
        "open_to": ANGLERS_ALL,
        "basis": BASIS_CLASS,
        "reason": "Hatchery Supported Trout Waters allow any bait or lure, "
                  "including natural bait.",
        # bait is unrestricted here, but the water itself shuts for stocking,
        # and "your bait is legal" on a closed stream is the wrong answer.
        # Opening day is its own entry because the water opens at 7 a.m., not
        # at midnight — the same half-day error as the June handover.
        "closures": [
            {"start": MAR_1, "end": FIRST_SAT_IN_APRIL,
             "reason": "Closed to all fishing from Mar 1 for stocking; the "
                       "season opens at 7 a.m. on the first Saturday in April."},
            {"start": FIRST_SAT_IN_APRIL, "end": SUN_AFTER_FIRST_SAT_IN_APRIL,
             "reason": "Opening day: still closed until 7 a.m., open from 7 "
                       "a.m. (10C .0316(a)).",
             "day_parts": [
                 {"label": "closed until opening",
                  "from": None, "to": SEVEN_AM,
                  "open_to": ANGLERS_NONE,
                  "reason": "Opening day, but the season does not open until 7 "
                            "a.m. — the water is still closed to all fishing."},
                 {"label": "open",
                  "from": SEVEN_AM, "to": None,
                  "open_to": ANGLERS_ALL,
                  "reason": "Open from 7 a.m. under hatchery-supported rules — "
                            "any bait or lure."},
             ]},
        ],
    },
    "Delayed Harvest Trout Waters": {
        "natural_bait": BAIT_SEASONAL,
        "natural_bait_possession": POSSESSION_UNKNOWN,
        "gear_restriction": None,
        "harvest": HARVEST_UNKNOWN,
        "open_to": ANGLERS_UNKNOWN,
        "basis": BASIS_CLASS,
        "reason": "Delayed Harvest water swaps rules once a year, and the "
                  "handover is not a clean day boundary — the answer depends on "
                  "the date, and on the two days either side of the handover on "
                  "the hour too; see periods.",
        # The handover, per 10C .0205(b)(3) and .0316(d), in order:
        #   ... -> ½ hour after sunset on the FRIDAY before the first Saturday
        #          in June: catch & release, no natural bait even in possession
        #   that moment -> 6 a.m. Saturday: closed to all fishing
        #   6 a.m. -> noon Saturday: youth anglers (under 16) only, no bait or
        #          lure restriction
        #   noon Saturday -> Sep 30: open to all, harvest and any bait
        # The old boundary — bait legal from midnight on the Saturday — was
        # wrong by a night and a morning, in the permissive direction.
        "periods": [
            {"label": "delayed-harvest season",
             "start": OCT_1, "end": FIRST_SAT_IN_JUNE,
             "natural_bait": BAIT_PROHIBITED,
             "natural_bait_possession": POSSESSION_PROHIBITED,
             "gear_restriction": GEAR_SINGLE_HOOK_ARTIFICIAL,
             "harvest": HARVEST_CATCH_AND_RELEASE,
             "open_to": ANGLERS_ALL,
             "reason": "From Oct 1 until one-half hour after sunset on the "
                       "Friday before the first Saturday in June, Delayed "
                       "Harvest water is catch & release with artificial lures "
                       "having one single hook — natural bait may not even be "
                       "possessed. On that last Friday the water shuts for the "
                       "night: see day_parts."},
            {"label": "opening day (youth session, then open)",
             "start": FIRST_SAT_IN_JUNE, "end": SUN_AFTER_FIRST_SAT_IN_JUNE,
             "natural_bait": BAIT_ALLOWED,
             "natural_bait_possession": POSSESSION_NOT_RESTRICTED,
             "gear_restriction": GEAR_ANY,
             "harvest": HARVEST_ALLOWED,
             "open_to": ANGLERS_VARIES,
             "reason": "The first Saturday in June is the handover day and it "
                       "holds three answers: closed to everyone until 6 a.m.; "
                       "youth anglers (under 16) only from 6 a.m. until noon; "
                       "open to all anglers from noon. Whoever may fish faces "
                       "no bait or lure restriction — but an adult fishing "
                       "before noon is fishing a session they are not eligible "
                       "for. Check open_to, not just natural_bait.",
             "day_parts": [
                 {"label": "closed overnight",
                  "from": None, "to": SIX_AM,
                  "open_to": ANGLERS_NONE,
                  "reason": "Still closed: Delayed Harvest water is shut to all "
                            "fishing from one-half hour after sunset on Friday "
                            "until 6 a.m. this morning."},
                 {"label": "youth-only session",
                  "from": SIX_AM, "to": NOON,
                  "open_to": ANGLERS_YOUTH_ONLY,
                  "reason": "Youth-only Delayed Harvest season, 6 a.m. to noon: "
                            "only anglers under 16 may fish, and they face no "
                            "bait or lure restriction. Adults may not fish."},
                 {"label": "open to all anglers",
                  "from": NOON, "to": None,
                  "open_to": ANGLERS_ALL,
                  "reason": "From noon the water is open to all anglers under "
                            "hatchery-supported rules — any bait or lure, "
                            "harvest allowed."},
             ]},
            {"label": "hatchery-supported season",
             "start": SUN_AFTER_FIRST_SAT_IN_JUNE, "end": OCT_1,
             "natural_bait": BAIT_ALLOWED,
             "natural_bait_possession": POSSESSION_NOT_RESTRICTED,
             "gear_restriction": GEAR_ANY,
             "harvest": HARVEST_ALLOWED,
             "open_to": ANGLERS_ALL,
             "reason": "From noon on the first Saturday in June through Sep 30, "
                       "Delayed Harvest water follows hatchery-supported rules "
                       "— any bait or lure, harvest allowed."},
        ],
        "closures": [{
            "start": FRI_BEFORE_FIRST_SAT_IN_JUNE, "end": FIRST_SAT_IN_JUNE,
            "reason": "Delayed Harvest water closes to all fishing one-half "
                      "hour after sunset on the Friday before the first "
                      "Saturday in June and stays closed until 6 a.m. the next "
                      "morning (10C .0316(d)). The other half of that overnight "
                      "closure is the first day_part of the following day.",
            "day_parts": [
                {"label": "open, delayed-harvest rules",
                 "from": None, "to": SUNSET_PLUS_30,
                 "open_to": ANGLERS_ALL,
                 "reason": "Last day of the delayed-harvest season: catch & "
                           "release, artificial lures with one single hook, no "
                           "natural bait in possession — until one-half hour "
                           "after sunset."},
                {"label": "closed overnight",
                 "from": SUNSET_PLUS_30, "to": None,
                 "open_to": ANGLERS_NONE,
                 "reason": "Closed to all fishing from one-half hour after "
                           "sunset until 6 a.m. on the first Saturday in June."},
            ],
        }],
    },
    "Catch and Release/Artificial Flies and Lures Only Trout Waters": {
        "natural_bait": BAIT_PROHIBITED,
        # .0205(b)(2) governs what may be *used* and, unlike Wild Trout Waters,
        # says nothing about carrying bait. Silence is not permission; it is
        # silence, and gets recorded as such.
        "natural_bait_possession": POSSESSION_UNKNOWN,
        "gear_restriction": GEAR_SINGLE_HOOK_FLIES_AND_LURES,
        "harvest": HARVEST_CATCH_AND_RELEASE,
        "open_to": ANGLERS_ALL,
        "basis": BASIS_CLASS,
        "reason": "Catch & Release / Artificial Flies and Lures Only waters take "
                  "artificial flies and lures with one single hook — no natural "
                  "bait and no harvest, all year. Flies AND lures here; Wild "
                  "Trout Waters are lures only.",
    },
    "Special Regulation Trout Waters": {
        # genuinely site-specific. Guessing a value here is how someone gets
        # written up, so the dataset says it does not know.
        "natural_bait": BAIT_UNKNOWN,
        "natural_bait_possession": POSSESSION_UNKNOWN,
        "gear_restriction": None,
        "harvest": HARVEST_UNKNOWN,
        "open_to": ANGLERS_UNKNOWN,
        "basis": BASIS_POSTED,
        "reason": "Special Regulation water is site-specific and this dataset "
                  "does not carry the rule. Read the regulations posted at the "
                  "water, or the NCWRC page, before fishing.",
    },
}


def _class_key(wrc_class):
    """Fold whitespace and case so the lookup survives cosmetic NCWRC drift."""
    return " ".join(str(wrc_class or "").split()).casefold()


_BAIT_RULES_BY_KEY = {_class_key(k): v for k, v in BAIT_RULES.items()}


def bait_rule_for(wrc_class, source=None):
    """Structured bait rule for a WRC classification. Strict on purpose.

    Derived from the classification itself — never from the prose in REGS,
    which is ours to reword. An unrecognised class raises: NCWRC can add or
    rename one, and a new class silently inheriting "bait allowed" is the
    failure that ends in a citation. Callers that must keep going record the
    unknown state (see bait_rule_or_unknown) rather than guess.
    """
    rule = _BAIT_RULES_BY_KEY.get(_class_key(wrc_class))
    if rule is None:
        raise UnknownTroutClass(
            f"no bait rule for WRC classification {wrc_class!r} — add it to "
            "BAIT_RULES; refusing to guess whether natural bait is legal here")
    rule = copy.deepcopy(rule)
    rule["source"] = source
    return rule


def unrecognised_class_rule(wrc_class, source=None):
    """The safe placeholder for a class we do not know: unknown, and says why."""
    return {
        "natural_bait": BAIT_UNKNOWN,
        "natural_bait_possession": POSSESSION_UNKNOWN,
        "gear_restriction": None,
        "harvest": HARVEST_UNKNOWN,
        "open_to": ANGLERS_UNKNOWN,
        "basis": BASIS_UNRECOGNISED,
        "reason": f"Unrecognised NCWRC classification {wrc_class!r} — this "
                  "dataset has no bait rule for it. Read the posted/NCWRC "
                  "regulations before fishing.",
        "source": source,
    }


def bait_rule_or_unknown(wrc_class, source=None):
    """bait_rule_for(), degrading to an explicit unknown instead of raising.

    Used when building the layer: one new classification should not abort
    1,809 reaches, but it must be visible in the data (basis =
    'unrecognised_class') and in the run summary, never absorbed as "allowed".
    """
    try:
        return bait_rule_for(wrc_class, source)
    except UnknownTroutClass:
        return unrecognised_class_rule(wrc_class, source)


def may_fish(open_to, angler):
    """Can this angler fish under `open_to`? None when the data cannot say.

    The point of open_to having its own vocabulary: a consumer asking on behalf
    of an adult at 9 a.m. on the first Saturday in June gets False, not a bait
    answer that happens to read "allowed".
    """
    if open_to == ANGLERS_NONE:
        return False
    if open_to == ANGLERS_ALL:
        return True
    if open_to == ANGLERS_YOUTH_ONLY:
        return angler == ANGLER_YOUTH if angler in (ANGLER_YOUTH,
                                                    ANGLER_ADULT) else None
    return None                      # varies_by_time, unknown, or a bad value


def _split_moment(day, at):
    """Accept a date, a date + time, or a datetime; normalise to (date, time)."""
    if isinstance(day, datetime.datetime):   # test first: a datetime IS a date
        return day.date(), at if at is not None else day.time()
    return day, at


def boundary_minutes(boundary, default):
    """A sub-day boundary as minutes past midnight, or None if unresolvable.

    None as the boundary means the edge of the day, and yields `default`. A
    clock boundary is exact. A solar one is honest about not being computable
    here (see SUNSET_PLUS_30) and comes back None, so the caller falls back to
    the whole-day answer rather than guessing a sunset and possibly calling a
    closed water open.
    """
    if boundary is None:
        return default
    if "clock" in boundary:
        hours, _, minutes = str(boundary["clock"]).partition(":")
        return int(hours) * 60 + int(minutes or 0)
    return None


# what a day_part may restate; anything it is silent about it inherits from the
# period (or, for a closure's parts, from the day the closure lands on).
PART_FIELDS = ("label", "natural_bait", "natural_bait_possession",
               "gear_restriction", "harvest", "open_to", "reason")


def _resolved_parts(entry, base):
    """`entry`'s sub-day parts, each filled out from `base` where it is silent."""
    parts = []
    for raw in entry.get("day_parts") or []:
        part = {field: raw[field] if field in raw else base.get(field)
                for field in PART_FIELDS}
        part["from"] = copy.deepcopy(raw.get("from"))
        part["to"] = copy.deepcopy(raw.get("to"))
        parts.append(part)
    return parts


def _part_at(parts, at):
    """The part holding clock time `at`, or None if the day cannot be resolved."""
    spans = []
    for part in parts:
        start = boundary_minutes(part["from"], 0)
        end = boundary_minutes(part["to"], 24 * 60)
        if start is None or end is None:
            return None              # a symbolic boundary: refuse to pick one
        spans.append((start, end, part))
    minutes = at.hour * 60 + at.minute
    for start, end, part in spans:
        if start <= minutes < end:
            return part
    return None


def _agreed(parts, field, mixed):
    """The value every part shares, or `mixed` when they disagree."""
    values = {part.get(field) for part in parts}
    return values.pop() if len(values) == 1 else mixed


def bait_rule_on(rule, day, at=None):
    """Flatten a bait rule to the one in force on `day`, and at `at` if given.

    `day` is a datetime.date, or a datetime.datetime whose time is used; `at` is
    an optional datetime.time.

    Total: it always answers. A seasonal rule resolves to the period holding
    `day`, with that season's real start/end (end exclusive) for the years in
    question; a date no period claims comes back `unknown`, never `allowed`.

    One day can hold several answers — the Delayed Harvest handover Saturday is
    closed, then youth-only, then open, inside 24 hours — so `day_parts` lists
    the sub-day windows and `open_to` reads `varies_by_time` until `at` pins it
    down. `open_to` is what keeps an adult from reading a youth-only morning as
    an invitation: it is never `all_anglers` while the water is closed or
    youth-only, and may_fish() turns it into a yes/no for a given angler.
    `fishing_open` is False only when the water is shut for the whole of the
    resolved moment — bait legality is moot on water that is shut.
    """
    day, at = _split_moment(day, at)
    out = {
        "natural_bait": rule.get("natural_bait", BAIT_UNKNOWN),
        "natural_bait_possession": rule.get("natural_bait_possession",
                                            POSSESSION_UNKNOWN),
        "gear_restriction": rule.get("gear_restriction"),
        "harvest": rule.get("harvest", HARVEST_UNKNOWN),
        "open_to": rule.get("open_to", ANGLERS_UNKNOWN),
        "reason": rule.get("reason", ""),
        "basis": rule.get("basis", BASIS_UNRECOGNISED),
        "fishing_open": True,
        "season": None,
        "closure": None,
        "day_parts": None,
        "at": at.isoformat(timespec="minutes") if at is not None else None,
    }
    parts = []
    if out["natural_bait"] == BAIT_SEASONAL:
        out.update({
            "natural_bait": BAIT_UNKNOWN,
            "natural_bait_possession": POSSESSION_UNKNOWN,
            "gear_restriction": None, "harvest": HARVEST_UNKNOWN,
            "open_to": ANGLERS_UNKNOWN,
            "reason": f"No season in this rule covers {day.isoformat()} — read "
                      "the posted/NCWRC regulations before fishing."})
        for period in rule.get("periods") or []:
            span = window_around(period["start"], period["end"], day)
            if span:
                out.update({
                    "natural_bait": period.get("natural_bait", BAIT_UNKNOWN),
                    "natural_bait_possession": period.get(
                        "natural_bait_possession", POSSESSION_UNKNOWN),
                    "gear_restriction": period.get("gear_restriction"),
                    "harvest": period.get("harvest", HARVEST_UNKNOWN),
                    "open_to": period.get("open_to", ANGLERS_UNKNOWN),
                    "reason": period.get("reason", ""),
                    "season": {"label": period.get("label"),
                               "start": span[0].isoformat(),
                               "end": span[1].isoformat()}})
                parts = _resolved_parts(period, out)
                break
    for closure in rule.get("closures") or []:
        span = window_around(closure["start"], closure["end"], day)
        if span:
            out["closure"] = {"start": span[0].isoformat(),
                              "end": span[1].isoformat(),
                              "reason": closure.get("reason", "")}
            if not closure.get("day_parts"):
                parts, out["open_to"] = [], ANGLERS_NONE     # shut all day
            elif parts:
                # two sets of sub-day parts landing on one date. Nothing in
                # BAIT_RULES does that (a test holds it that way), and merging
                # two timelines — one of them symbolic — is not something to
                # invent on a guess. Take the closed answer, the safe one.
                parts, out["open_to"] = [], ANGLERS_NONE
            else:
                parts = _resolved_parts(closure, out)
            break
    if parts:
        out["day_parts"] = [copy.deepcopy(part) for part in parts]
        chosen = _part_at(parts, at) if at is not None else None
        held = [chosen] if chosen else parts
        out.update({
            "natural_bait": _agreed(held, "natural_bait", BAIT_UNKNOWN),
            "natural_bait_possession": _agreed(held, "natural_bait_possession",
                                               POSSESSION_UNKNOWN),
            "gear_restriction": _agreed(held, "gear_restriction", None),
            "harvest": _agreed(held, "harvest", HARVEST_UNKNOWN),
            "open_to": _agreed(held, "open_to", ANGLERS_VARIES),
        })
        if chosen and chosen.get("reason"):
            out["reason"] = chosen["reason"]
    out["fishing_open"] = out["open_to"] != ANGLERS_NONE
    return out


def midpoint(geom):
    """Representative point: the middle vertex of the flattened (multi)line."""
    pts = []
    if geom["type"] == "MultiLineString":
        for line in geom["coordinates"]:
            pts.extend(line)
    elif geom["type"] == "LineString":
        pts = geom["coordinates"]
    if not pts:
        return None
    return pts[len(pts) // 2]        # [lon, lat]


def load_counties(base):
    g = json.load(open(os.path.join(base, "reference-layers", "county-boundaries.geojson")))
    props = g["features"][0]["properties"]
    namekey = next((k for k in props if "name" in k.lower() or "cnty" in k.lower()
                    or "county" in k.lower()), None)
    polys = []
    for f in g["features"]:
        name = f["properties"].get(namekey, "?")
        geom = f["geometry"]
        rings = (geom["coordinates"] if geom["type"] == "Polygon"
                 else [r for poly in geom["coordinates"] for r in poly])
        for ring in rings:
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            polys.append((name, ring, min(xs), min(ys), max(xs), max(ys)))
    return polys


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def county_for(lon, lat, polys):
    for name, ring, x0, y0, x1, y1 in polys:
        if x0 <= lon <= x1 and y0 <= lat <= y1 and point_in_ring(lon, lat, ring):
            return name
    return None


def elevation(lat, lon):
    try:
        d = json.loads(urllib.request.urlopen(
            urllib.request.Request(
                f"{EPQS}?" + urllib.parse.urlencode(
                    {"x": lon, "y": lat, "units": "Meters", "wkid": 4326}),
                headers={"User-Agent": "pmtw-layer/1.0"}), timeout=30).read())
        v = float(d["value"])
        return round(v, 1) if v > -1000 else None
    except Exception:
        return None


def reach_record(feature, counties):
    """One PMTW GeoJSON feature -> one reach record. Pure; no elevation yet."""
    p = feature["properties"]
    mp = midpoint(feature["geometry"])
    if not mp:
        return None
    lon, lat = mp[0], mp[1]
    cls = p.get("WRC_Class")
    link = p.get("WEB_Refere")
    mhtw = (p.get("FIRST_MHTW", "").strip() or p.get("MHTW_Reach", "").strip())
    return {
        "stream_name": p.get("Displ_Name"),
        "reach": p.get("FIRST_Reg1") or p.get("FIRST_Reg_"),
        "wrc_class": cls,
        "regulation_summary": REGS.get(cls, "See NCWRC rules."),
        # the same knowledge as regulation_summary, minus the English
        "bait_rule": bait_rule_or_unknown(cls, link),
        "mountain_heritage": bool(mhtw and mhtw != " "),
        "mhtw_reach": mhtw if (mhtw and mhtw != " ") else None,
        "length_m": round(p.get("Shape__Length", 0)),
        "midpoint": {"lat": round(lat, 5), "lon": round(lon, 5)},
        "county": county_for(lon, lat, counties),
        "elevation_m": None,
        "ncwrc_link": link,
    }


def artifact_tiers(with_elevation, sample=None, summary=None):
    """Provenance tier and role for every artifact this script writes."""
    rules = {
        "stream_name": AGENCY_FACTUAL, "reach": AGENCY_FACTUAL,
        "wrc_class": AGENCY_FACTUAL, "mountain_heritage": AGENCY_FACTUAL,
        "mhtw_reach": AGENCY_FACTUAL, "length_m": AGENCY_FACTUAL,
        "midpoint": AGENCY_FACTUAL, "county": AGENCY_FACTUAL,
        "ncwrc_link": AGENCY_FACTUAL,
        # written by this script, not by NCWRC
        "regulation_summary": CURATED,
        # bait_rule is the same authorship as regulation_summary: our reading of
        # the NCWRC classification, structured. The URL inside it is NCWRC's,
        # and the longer selector wins, so it keeps its own tier.
        "bait_rule": CURATED,
        "bait_rule.source": AGENCY_FACTUAL,
        # the elevation_m slot exists either way; --no-elevation leaves it null
        "elevation_m": FEDERAL,
    }
    return {
        "trout-waters/pmtw-reaches.json": {
            "tiers": [AGENCY_FACTUAL, CURATED, FEDERAL], "role": QUERY,
            "fields": {"records": "list", "rules": rules, "sample": sample},
            "note": "NCWRC PMTW reach facts, plus a hand-written plain-language "
                    "regulation_summary and a structured bait_rule per class "
                    "(both curated, neither is NCWRC text)"
                    + (", plus USGS 3DEP midpoint elevation." if with_elevation
                       else ". Elevation skipped on this run: elevation_m is "
                            "null in every record.")},
        "trout-waters/pmtw-summary.json": {
            "tiers": [AGENCY_FACTUAL, CURATED], "role": QUERY,
            "derived_from": ["trout-waters/pmtw-reaches.json"],
            "fields": {"records": "object", "default": AGENCY_FACTUAL,
                       "rules": {"by_natural_bait": CURATED,
                                 "unrecognised_wrc_classes": CURATED},
                       "sample": summary},
            "note": "Counts by class and county, derived from NCWRC facts — "
                    "except the bait-rule counts, which count our curated "
                    "reading of those classes."},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    _common.add_out_arg(ap)
    ap.add_argument("--no-elevation", action="store_true",
                    help="skip the USGS 3DEP midpoint elevation lookups")
    a = ap.parse_args()

    BASE = _common.resolve_out(a.out)
    TW = os.path.join(BASE, "trout-waters")
    print(f"Dataset -> {BASE}", flush=True)

    # Vintage-agnostic: the extractor names this file by NCWRC's layer year, so a
    # hardcoded year makes bumping the source layer break this step — which is exactly
    # what happened when PMTW moved 2025 -> 2026 (openangler/extractors#16). Take the
    # newest pmtw-streams-*.geojson present, and say so plainly if there is none.
    candidates = sorted(glob.glob(os.path.join(TW, "pmtw-streams-*.geojson")))
    if not candidates:
        raise SystemExit(
            f"no pmtw-streams-*.geojson in {TW} — run nc/extract_nc_fishing.py first")
    streams_path = candidates[-1]
    print(f"  streams layer: {os.path.basename(streams_path)}", flush=True)
    streams = json.load(open(streams_path))
    counties = load_counties(BASE)
    print(f"Building layer from {len(streams['features'])} PMTW reaches ...", flush=True)

    reaches = []
    for f in streams["features"]:
        r = reach_record(f, counties)
        if r:
            reaches.append(r)
    print(f"  midpoints + counties done ({sum(1 for r in reaches if r['county'])} "
          f"with county).", flush=True)

    if not a.no_elevation:
        print("  fetching midpoint elevations (USGS 3DEP) ...", flush=True)

        def add_elev(i):
            reaches[i]["elevation_m"] = elevation(reaches[i]["midpoint"]["lat"],
                                                  reaches[i]["midpoint"]["lon"])
            return i
        done = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            for _ in as_completed([ex.submit(add_elev, i) for i in range(len(reaches))]):
                done += 1
                if done % 300 == 0 or done == len(reaches):
                    print(f"    {done}/{len(reaches)}", flush=True)

    reaches.sort(key=lambda r: (r["county"] or "zz", r["stream_name"] or ""))
    with open(os.path.join(TW, "pmtw-reaches.json"), "w") as f:
        json.dump(reaches, f, indent=2)

    # summary
    from collections import Counter
    by_class = Counter(r["wrc_class"] for r in reaches)
    by_county = Counter(r["county"] for r in reaches if r["county"])
    by_bait = Counter(r["bait_rule"]["natural_bait"] for r in reaches)
    unrecognised = Counter(
        r["wrc_class"] for r in reaches
        if r["bait_rule"]["basis"] == BASIS_UNRECOGNISED)
    summary = {
        "total_reaches": len(reaches),
        "by_class": dict(by_class),
        "mountain_heritage_reaches": sum(1 for r in reaches if r["mountain_heritage"]),
        "top_counties": dict(by_county.most_common(12)),
        "elevation_included": not a.no_elevation,
        "by_natural_bait": {s: by_bait[s] for s in BAIT_STATES if by_bait[s]},
        "unrecognised_wrc_classes": dict(unrecognised),
    }
    if unrecognised:
        print(f"  WARNING: {sum(unrecognised.values())} reach(es) carry a WRC "
              f"classification with no bait rule: "
              f"{', '.join(sorted(map(repr, unrecognised)))}. Their bait_rule is "
              f"'{BAIT_UNKNOWN}' — add them to BAIT_RULES before an app relies "
              f"on this layer.", file=sys.stderr, flush=True)
    with open(os.path.join(TW, "pmtw-summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    _common.record_artifacts(BASE, "build_pmtw_layer.py",
                             artifact_tiers(not a.no_elevation, sample=reaches,
                                            summary=summary),
                             run=summary)
    print("Done ->", os.path.join(TW, "pmtw-reaches.json"))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
