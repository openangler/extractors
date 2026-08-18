# North Carolina live bait & baitfish regulations — sourced summary

**Status:** research spike for openangler/extractors#13. **No extractor was written.**
**Retrieved:** 2026-08-17 (all URLs below fetched on this date).
**Jurisdiction:** North Carolina *inland fishing waters* only. Coastal and joint fishing
waters are partly under the NC Marine Fisheries Commission and are **not** covered here.

> **Read this before quoting anything below.**
> NC fishing rules are readopted or amended most years (several rules cited here carry
> amendments effective 2023, 2024, 2025 and 2026). A summary without a retrieval date is
> unusable. Any consuming app must (a) show the retrieval date, (b) link the source, and
> (c) tell the angler to check the current digest and any posted signage at the water.
> Where this document says **GAP** or **AMBIGUOUS**, the app must stay silent or defer to
> NCWRC rather than answer.

---

## Sources and how to cite them

| Key | Source | URL | Notes |
|---|---|---|---|
| `NCAC-10C` | 15A NCAC Subchapter 10C — Inland Fishing Regulations (full text, NC Office of Administrative Hearings) | `http://reports.oah.state.nc.us/ncac/title%2015a%20-%20environmental%20quality/chapter%2010%20-%20wildlife%20resources%20and%20water%20safety/subchapter%20c/subchapter%20c%20rules.html` | **Primary/authoritative.** HTTP only — no TLS. Individual rules also available as PDFs (pattern below). |
| `NCAC-10D` | 15A NCAC Subchapter 10D — Game Lands | `http://reports.oah.state.nc.us/ncac/title%2015a%20-%20environmental%20quality/chapter%2010%20-%20wildlife%20resources%20and%20water%20safety/subchapter%20d/subchapter%20d%20rules.html` | Primary. HTTP only. |
| `LII` | Cornell Legal Information Institute mirror | `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0402` (pattern) | HTTPS, link-friendly, but a **mirror** and may lag the OAH text. Verified to resolve for every rule cited here. Use OAH as the authority. |
| `NCWRC-REGS` | NCWRC "Fishing, Hunting & Trapping Regulations" landing page | `https://www.ncwildlife.gov/hunting/fishing-hunting-trapping-regulations` | NCWRC's own page; links to the digest. |
| `DIGEST-2627` | 2026-27 NC Inland Fishing, Hunting & Trapping Regulations Digest (flipbook) | `https://online.flippingbook.com/view/424369678/` | The official digest, as linked from `NCWRC-REGS`. |
| `DIGEST-WEB` | Same digest, web edition (eRegulations) | `https://www.eregulations.com/northcarolina` | Linked from `NCWRC-REGS` as the official web edition. Plain-language; the rule text governs. |
| `NCWRC-ANS` | NCWRC Aquatic Nuisance Species | `https://www.ncwildlife.gov/wildlife-habitat/aquatic-nuisance-species` | NCWRC guidance (not law). |
| `NCWRC-STOCK` | NCWRC Fish Stocking and Grass Carp Possession Permits | `https://www.ncwildlife.gov/fishing/hatcheries-and-stocking/fish-stocking-and-grass-carp-possession-permits` | Permit process. |
| `NCWRC-NONGAME` | NCWRC Nongame Possession and Collection | `https://www.ncwildlife.gov/hunting/regulations/nongame-and-other-regulations/nongame-possession-and-collection` | |
| `NCWRC-TROUT` | NCWRC Trout Fishing in North Carolina | `https://www.ncwildlife.gov/fishing/trout-fishing-north-carolina` | |
| `NCWRC-PR-2025` | NCWRC press release, "Mountain Trout Jeopardized by Unauthorized Stocking", 2025-06-23 | `https://www.ncwildlife.gov/news/press-releases/2025/06/23/mountain-trout-jeopardized-unauthorized-stocking` | Agency framing of the ecological risk. |

Per-rule PDF pattern (OAH, HTTP only), e.g. for 15A NCAC 10C .0402:

```
http://reports.oah.state.nc.us/ncac/title%2015a%20-%20environmental%20quality/chapter%2010%20-%20wildlife%20resources%20and%20water%20safety/subchapter%20c/15a%20ncac%2010c%20.0402.pdf
```

Verified 200 OK on 2026-08-17 for 10C .0205, .0206, .0209, .0211, .0212, .0301, .0302,
.0316, .0401, .0402, .0423 and 10D .0104, .0105.

Statutes cited (NC General Assembly, HTTPS):

- G.S. 113-292, WRC authority over inland fishing and introduction of exotic species —
  `https://www.ncleg.gov/EnactedLegislation/Statutes/PDF/BySection/Chapter_113/GS_113-292.pdf`
- G.S. 113-272.3, special provisions respecting fishing licences; **taking bait fish** —
  `https://www.ncleg.gov/EnactedLegislation/Statutes/PDF/BySection/Chapter_113/GS_113-272.3.pdf`
- G.S. 113-135, general penalties —
  `https://www.ncleg.gov/EnactedLegislation/Statutes/PDF/BySection/Chapter_113/GS_113-135.pdf`

---

## 1. Which species may be used as live bait

### NC-BAIT-001 — Inland game fish MAY be used as bait, if legally taken

**Rule (digest, plain language):**

> "Inland game fish may be used as bait if they are legally taken and meet the size and
> creel limits of the waters being fished and other regulations."

**Source:** `DIGEST-WEB` — `https://www.eregulations.com/northcarolina/fishing/inland-fishing-regulations` (retrieved 2026-08-17)

**Caveat for the app:** this is the *digest's* statement. I did **not** find an equivalent
sentence in the administrative code itself. The code constrains it indirectly (see
NC-BAIT-002 / NC-BAIT-003). Quote the digest, link the digest, and do not upgrade this to
"the law says".

### NC-BAIT-002 — Game fish may only be taken by hook and line, so you cannot net them for bait

**Rule (verbatim, 15A NCAC 10C .0302):**

> "(a) Inland game fishes may only be taken with hook and line unless otherwise provided.
> (b) Landing nets may be used to land fishes caught on hook and line."

**Rule (verbatim, 15A NCAC 10C .0402(d)):**

> "Game fishes taken shall be returned unharmed to the water, except for the following:
> (1) American and hickory shad may be taken when captured with dip nets and bow nets from
> March 1 through April 30 subject to the size and creel limits specified in 15A NAC 10C
> .0313. (2) white perch may be taken when captured in a cast net being used to collect
> nongame fishes for bait or personal consumption in all impounded waters west of I-95 and
> in the Tar River Reservoir (Nash County) subject to the size and creel limits specified
> in 15A NCAC 10C .0319."

**Digest phrasing of the same rule:**

> "Game fish incidentally taken with nets or traps, while capturing bait, must not be
> harmed and must be released immediately."

**Sources:** `NCAC-10C` 10C .0302 and 10C .0402(d);
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0302`,
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0402`;
`DIGEST-WEB` — `https://www.eregulations.com/northcarolina/fishing/nongame-fish-regulations`
(retrieved 2026-08-17)

**Net effect:** a bluegill you caught on a hook and line, within creel and size limits for
the water you are fishing, may be used as bait. A bluegill in your cast net or minnow trap
must go back in the water unharmed.

### NC-BAIT-003 — "Bream" / sunfish ARE game fish in North Carolina

This is the item the issue flagged, and the answer is the opposite of the common
assumption: sunfish are **not** a nongame exception. They are classified game fish.

**Rule (verbatim, 15A NCAC 10C .0301(a)):**

> "The following fishes are classified and designated as inland game fishes in inland,
> joint, and coastal fishing waters: … (7) sunfish, including bluegill (bream), flier,
> pumpkinseed, redbreast (robin), redear (shellcracker), Roanoke bass, rock bass (redeye),
> warmouth, and all other species of the sunfish family (Centrarchidae) not specifically
> listed in this Rule."

(The rule also lists black/white crappie, the black basses, pickerel/muskellunge, kokanee
salmon, mountain trout, sauger and walleye as game fish statewide; and shad, bullheads,
white catfish, flounder, red drum, spotted seatrout, striped/white bass and Morone hybrids,
white perch, and yellow perch as game fish **when found in inland fishing waters**.)

**Source:** `NCAC-10C` 10C .0301 (History Note: "Amended Eff. February 1, 2026") —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0301`
(retrieved 2026-08-17)

**Where sunfish *are* treated differently from other game fish:** the creel limits are
mostly unrestricted, which is why bream are practically usable as bait.

- 15A NCAC 10C .0315: "There is no daily creel limit for Sunfish, except for waters
  identified in Paragraph (e) of this Rule. … There is no minimum size limit. … There is no
  closed season." Paragraph (e) sets a 30-fish aggregate limit (max 12 redbreast) in the
  listed coastal-plain rivers "and all other public fishing waters east of Interstate 95,
  except Tar River Reservoir in Nash County."
  `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0315`
- 15A NCAC 10C .0311 carves Roanoke bass and rock bass out of the sunfish rule: no creel or
  size limit statewide **except** "In all public fishing waters east of Interstate 77, the
  daily creel limit for Roanoke and Rock Bass is two fish in the aggregate and the minimum
  size for these fish is eight inches."
  `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0311`

**App guidance:** do not tell an angler "bream aren't game fish". Tell them bream are game
fish, so hook-and-line only, and the east-of-I-95 / east-of-I-77 creel limits apply to bait
fish the same as to fish you keep.

### NC-BAIT-004 — Nongame fish taken for bait count against that species' limits

**Rule (verbatim, 15A NCAC 10C .0402(e)–(f)):**

> "(e) No person shall take or possess during one day more than 200 nongame fish, in
> aggregate, for bait or personal consumption, accounting for species specific size and
> creel limits identified in Section .0400 of this Subchapter.
> (f) Any fishes taken for bait purposes are included within the daily possession limit for
> that species."

**Digest phrasing:** "The daily creel limit is 200 nongame fish, crayfish, and mollusks, in
combination, subject to species-specific size and creel limits."

**Sources:** `NCAC-10C` 10C .0402;
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0402`;
`DIGEST-WEB` — `https://www.eregulations.com/northcarolina/fishing/nongame-fish-regulations`
(retrieved 2026-08-17)

### NC-BAIT-005 — Species that may NOT be possessed alive at all (statewide)

**Rule (verbatim, 15A NCAC 10C .0211(a)):**

> "It shall be unlawful to transport, purchase, possess, sell, or stock in the public or
> private waters of North Carolina any live individuals of: …"

The list (38 entries as retrieved) includes several that turn up in or near the bait trade:
**red shiner** (*Cyprinella lutrensis*), **rudd**, **Oriental weatherfish**, **round goby**,
**tubenose goby**, **ruffe**, **European minnow**, **European perch**, **Crucian carp**,
**Prussian carp**, **yellow bass**, bighead/silver/black carp, snakehead, and the crayfishes
**rusty crayfish** (*Faxonius rusticus*), **virile crayfish**, **bigclaw crayfish**,
**Creole painted crayfish**, **marbled crayfish/Marmorkrebs**, and **Australian red claw**;
plus zebra and quagga mussels, applesnails and mysterysnails. Grass carp are prohibited
alive except certified triploid individuals under permit (10C .0211(b)).

**Source:** `NCAC-10C` 10C .0211 —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0211`
(retrieved 2026-08-17). **Quote the current rule; this list is amended over time.**

**Consuming apps should render the full list from the rule, not from this summary.**

### NC-BAIT-006 — Water-specific live-bait species bans

| Where | Rule (verbatim) | Citation |
|---|---|---|
| Little Tennessee River, in and upstream of Lake Santeetlah and Cedar Cliff Lake, incl. all tributaries and impoundments, and adjacent shorelines, docks, access ramps and bridge crossings | "It shall be unlawful to transport, possess, or release live river herring, also known as alewife or blueback herring, in the waters of the Little Tennessee River in and upstream of Lake Santeetlah and Cedar Cliff Lake, including all the tributaries and impoundments thereof, and on adjacent shorelines, docks, access ramps, and bridge crossings." | 10C .0211(c); identical text at 10C .0423(e) — `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0423` |
| **In and west of** Haywood, Buncombe and Rutherford counties | "it is unlawful to transport, possess, or release live white perch." | 10C .0319(d) — `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0319` |
| Lake Rim (Cumberland County, state fish hatchery water) | "On Lake Rim it shall be unlawful to: … (3) use, or have in one's possession, any minnows, or other species of fish except golden shiners for use as bait." | 10C .0212(b)(3) — `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0212` |
| Statewide, on trotlines / jug hooks / set hooks | "Trotlines, jug hooks, and set hooks may be set in the inland waters of North Carolina, **provided no live bait is used** …" | 10C .0206(b) — `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0206` |

All retrieved 2026-08-17.

Also relevant: alewife/blueback herring over six inches may not be taken or possessed
"regardless of origin" in a long list of eastern waters and "all other inland fishing waters
east of I-95" (10C .0423(d)) — a direct constraint on live herring as bait in the east.

---

## 2. Transporting live bait between waters

This is the section to be most careful with. The plain reading of the rule is broader than
what anglers actually do, and I could not find NCWRC guidance reconciling the two.

### NC-BAIT-010 — A permit is required to transport live freshwater nongame fish

**Rule (verbatim, 15A NCAC 10C .0209(a)):**

> "Fish Transport: It shall be unlawful for any person, firm, or corporation to transport
> live freshwater nongame fishes, or live game fishes in excess of the possession limit, or
> fish eggs without having in possession a permit obtained from the North Carolina Wildlife
> Resources Commission."

**NCWRC's own restatement:**

> "It is unlawful for any person, firm, or corporation to transport live freshwater nongame
> fishes, or live game fishes in excess of the possession limit, or fish eggs without having
> in possession a permit … (15a ncac 10c .0209)"

**Sources:** `NCAC-10C` 10C .0209 —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0209`;
`NCWRC-NONGAME` (retrieved 2026-08-17)

> **AMBIGUOUS — the app must not resolve this.** Read literally, 10C .0209(a) covers an
> angler carrying a bucket of live minnows, because baitfish are freshwater nongame fish.
> Yet 10C .0402 expressly authorises collecting nongame fish *for bait*, and bait is sold
> commercially in NC, which implies routine lawful transport. **I found no NCWRC page,
> digest passage, FAQ, or rule text that states an exemption for anglers' live bait, and I
> found no NCWRC page saying anglers need a transport permit for bait either.** The NCWRC
> permit pages I found (`NCWRC-STOCK`) describe the **stocking** permit and the grass carp
> permit, not an angler bait-transport permit.
>
> **Correct app behaviour:** state the rule, link it, and say the transport question for
> live bait should be confirmed with NCWRC (833-950-0575, the number NCWRC publishes on
> `NCWRC-NONGAME`). Do not tell anglers it is fine, and do not tell them they need a permit.

### NC-BAIT-011 — Absolute regional transport bans (these are unambiguous)

Both are quoted verbatim in **NC-BAIT-006**:

- **Live alewife / blueback herring:** may not be transported, possessed or released in the
  Little Tennessee River in and upstream of Lake Santeetlah and Cedar Cliff Lake, including
  tributaries and impoundments, and on adjacent shorelines, docks, access ramps and bridge
  crossings. (10C .0211(c), 10C .0423(e))
- **Live white perch:** may not be transported, possessed or released in and west of
  Haywood, Buncombe and Rutherford counties. (10C .0319(d))

These are the two clearest "do not carry this bait into this region" rules in the code.

### NC-BAIT-012 — NCWRC's non-binding guidance is unambiguous even where the law is not

**Verbatim from `NCWRC-ANS`:**

> "Do not transport live fish from one water body to another."

> "Clean: Equipment of all aquatic plants, animals and mud."
> "Drain: Water from boats, live wells, bait buckets and all equipment."
> "Dry: All equipment thoroughly"
> "Never Move: Fish, plants or other organisms from one body of water to another."

> "Dispose of fish parts carefully when cleaning fish. Dry disposal is best; dispose of the
> carcass in the garbage, by deep burying, or by total burning. Please do not dispose of
> fish heads, skeletons or entrails in any body of water."

**Source:** `NCWRC-ANS` — `https://www.ncwildlife.gov/wildlife-habitat/aquatic-nuisance-species`
(retrieved 2026-08-17)

**Agency framing of the risk** (`NCWRC-PR-2025`, retrieved 2026-08-17):

> "Transporting live fish from one water body to another can have irreversible
> consequences." — Rachael Hoch, Inland Fisheries Assistant Chief, NCWRC

> "The newly stocked fish may carry parasites or other pathogens that can impact the fish
> species in those waters." — Rachael Hoch

This is guidance, not law. It is, however, NCWRC's own published position, and it is the
right thing for the app to surface prominently: **the safe answer and the agency's answer
are the same — do not move live fish between waters.**

---

## 3. Leftover bait

### NC-BAIT-020 — Releasing leftover live bait into public water is "stocking"

This is the single most important legal chain in this document, so it is quoted in full.

**Rule (verbatim, 15A NCAC 10C .0209(b), (d), (e)):**

> "(b) Fish Stocking: It shall be unlawful for any person, firm, or corporation to stock any
> life stage of any species of fish in the inland fishing waters of this State without
> having first procured a stocking permit from the North Carolina Wildlife Resources
> Commission."

> "(d) For purposes of this Rule, stocking is the introduction or attempted introduction of
> one or more individuals of a particular species of live fish into public waters for any
> purpose other than:
> (1) As bait affixed to a hook and line, or
> (2) A release incidental to 'catch and release' fishing in an area within the same body of
> water where the fish was caught, or within an adjacent body of water not separated from
> that body by any natural or manmade obstruction to the passage of that species."

> "(e) The release of more than the daily creel limit, or if there is no established creel
> limit for the species, more than five individuals of the species, shall constitute prima
> facie evidence of an intentional release."

**Source:** `NCAC-10C` 10C .0209 (History Note: "Readopted Eff. August 1, 2020") —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0209`
(retrieved 2026-08-17)

**What the app may safely say, tied to that text:**

- Emptying a bait bucket of live bait into public water is **not** covered by exception
  (d)(1) — the bait is not "affixed to a hook and line".
- It is **not** covered by exception (d)(2) unless the fish were caught in that same body of
  water (or an adjacent one with no barrier to passage). Bait bought at a shop, or netted in
  a different watershed, is not covered.
- Therefore it is "stocking", and 10C .0209(b) makes stocking without a permit unlawful.
  The definition bites at "**one or more individuals**" — there is no de minimis quantity.
- Paragraph (e) is an evidentiary rule, not a threshold: dumping more than five individuals
  of a species with no creel limit is *prima facie* evidence of intentional release.
- Penalty framing: violations of WRC rules are misdemeanours under G.S. 113-135 (Class 3 on
  first conviction, Class 2 for a second or subsequent conviction within three years), as
  limited by G.S. 113-135.1 —
  `https://www.ncleg.gov/EnactedLegislation/Statutes/PDF/BySection/Chapter_113/GS_113-135.pdf`

**Marked as inference, not quotation:** the reading that "bait you personally caught in this
same water may be released back into it" follows from exception (d)(2), but (d)(2) is worded
around "catch and release fishing", not around bait disposal. Present it as *likely* and
recommend the safe behaviour instead. Do not present it as settled.

### NC-BAIT-021 — What NCWRC actually tells you to do with the leftovers

> **GAP — this is the most important gap in this document.**
> I could not find any NCWRC page, digest section, or rule that tells an angler what to
> *do* with leftover live bait. There is no published NCWRC instruction to freeze it, bin
> it, keep it for next time, or take it home. Searches across ncwildlife.gov and the digest
> for leftover/unused bait and bait-bucket disposal returned nothing on point.
>
> The only NCWRC statements that touch it are the general ANS guidance quoted in
> **NC-BAIT-012** ("Never Move: Fish, plants or other organisms from one body of water to
> another"; "Drain: Water from boats, live wells, bait buckets and all equipment") and the
> **fish-cleaning** disposal advice ("Dry disposal is best; dispose of the carcass in the
> garbage, by deep burying, or by total burning"), which is written about fish carcasses,
> **not** about live leftover bait.
>
> **The app must not invent disposal instructions.** It may (a) state the prohibition in
> NC-BAIT-020, (b) quote NCWRC's "Never Move" guidance, and (c) say NCWRC does not publish
> specific leftover-bait disposal instructions and the angler should contact NCWRC. Anything
> more specific — "freeze it", "put it in the trash", "pour it on the bank" — would be the
> app's invention, and the on-the-bank version in particular could be unlawful *take* or
> waste depending on facts.

---

## 4. Where bait itself is prohibited

### NC-BAIT-030 — Definition of "natural bait" (this is the operative term)

**Rule (verbatim, 15A NCAC 10C .0205(a)):**

> "(1) 'Natural bait' means a living or dead plant or animal, or parts thereof, or prepared
> substances designed to attract fish by the sense of taste or smell.
> (2) 'Single hook' means a fish hook with only one point.
> (3) 'Artificial lure' means a fishing lure that neither contains nor has been treated by a
> substance that attracts fish by the sense of taste or smell.
> (4) 'Artificial fly' means one single hook dressed with feathers, hair, thread, tinsel,
> rubber, or a similar material to which no additional hook, spinner, spoon, or similar
> device is added.
> (5) 'Youth anglers' are individuals under 16 years of age."

**Source:** `NCAC-10C` 10C .0205(a) —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0205`
(retrieved 2026-08-17)

Note the breadth: scented soft plastics and dough baits are "natural bait" under (1)/(3),
not "artificial lures". This matters wherever natural bait is barred.

### NC-BAIT-031 — Trout water classifications, verbatim

**Rule (verbatim, 15A NCAC 10C .0205(b)):**

> "(1) 'Public Mountain Trout Waters' are the waters included in this Rule and those
> designated in 15A NCAC 10D .0104.
>
> (2) 'Catch and Release Artificial Flies and Lures Only Trout Waters' are Public Mountain
> Trout Waters where only artificial flies and lures having one single hook may be used. No
> trout may be possessed or harvested while fishing these streams. Waters with this
> designation include tributaries unless otherwise noted.
>
> (3) 'Delayed Harvest Trout Waters' are Public Mountain Trout Waters where between October
> 1 and one-half hour after sunset on the Friday before the first Saturday of the following
> June, it is unlawful to possess natural bait, use more than one single hook on an
> artificial lure, or harvest or possess trout while fishing. From 6:00 a.m. until noon on
> the first Saturday in June, only youth anglers may fish and these waters have no bait or
> lure restrictions. From noon on the first Saturday in June until October 1, anglers may
> fish these waters with no bait or lure restrictions. Waters with this designation do not
> include tributaries unless otherwise noted.
>
> (4) 'Hatchery Supported Trout Waters' are Public Mountain Trout Waters that have no bait
> or lure restrictions. Waters with this designation do not include tributaries unless
> otherwise noted.
>
> (5) 'Special Regulation Trout Waters' are Public Mountain Trout Waters where
> watercourse-specific regulations apply. Waters with this designation do not include
> tributaries unless otherwise noted.
>
> (6) 'Wild Trout Waters' are Public Mountain Trout Waters identified in this Rule or 15A
> NCAC 10D .0104. Only artificial lures having only one single hook may be used. No person
> shall possess natural bait while fishing these waters. Waters with this designation do not
> include tributaries unless otherwise noted.
>
> (7) 'Undesignated Waters' are the other waters in the State. These waters have no bait or
> lure restrictions."

**Source:** `NCAC-10C` 10C .0205(b) —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0205`
(retrieved 2026-08-17)

**Verification against this project's derived dataset:**

- The project's Wild Trout Waters reaches carry "single-hook artificial lures only (no
  natural bait)". **Confirmed** by 10C .0205(b)(6), and the wording is close to exact. Two
  refinements the dataset's phrasing loses:
  1. The rule bans **possession** of natural bait while fishing, not merely its use. An
     angler with bait in a vest is in violation.
  2. Wild Trout Waters are "artificial **lures**" — Catch and Release waters are "artificial
     **flies and lures**". Both require one single hook. Don't collapse the two labels.
- **Tributaries:** Wild Trout, Delayed Harvest, Hatchery Supported and Special Regulation
  designations **do not** include tributaries unless noted; Catch and Release **does**
  include tributaries unless noted. If the derived dataset propagated a classification onto
  tributary reaches, that is a defect. I did not audit the dataset's reach geometry.
- **I did not verify the count of 1,516 reaches.** That count is a property of this
  project's dataset, not of the rule.

**Why Wild Trout Waters are so numerous — verbatim, 15A NCAC 10D .0104(e):**

> "The designated public mountain trout waters identified in Paragraph (d) of this Rule are
> Wild Trout Waters unless classified otherwise in 15A NCAC 10C .0205(d)."

Paragraph (d) designates whole game lands (Nantahala and Pisgah National Forest Game Lands,
DuPont State Forest, Green River, South Mountains, Cold Mountain, Headwaters State Forest,
Pond Mountain, Little Fork State Forest, Three Top Mountain, Thurmond Chatham, Toxaway,
William H. Silvers, with named exceptions) as Public Mountain Trout Waters. Everything in
them defaults to Wild Trout Waters — i.e. **no natural bait** — unless 10C .0205(d) says
otherwise for a specific named watercourse.

**Source:** `NCAC-10D` 10D .0104 —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10D-0104`
(retrieved 2026-08-17)

### NC-BAIT-032 — Special Regulation Trout Waters: check the posted regulations

10C .0205(b)(5) defines these purely as "waters where watercourse-specific regulations
apply". 10C .0316(e) sets creel/size for the two currently listed (Apalachia Reservoir,
Cherokee County; Catawba River, Burke County, from Muddy Creek to the City of Morganton
water intake dam) but says nothing about bait for either.

> **GAP / correct answer is deferral.** I found no bait rule for Special Regulation Trout
> Waters in 10C .0205 or 10C .0316. The app must show "check the posted regulations at the
> water and the current digest" for any `Special Regulation` reach and must not infer a bait
> rule from the classification. `NCWRC-TROUT` and the digest's trout pages likewise give
> creel/size for these waters without a bait statement.

### NC-BAIT-033 — A Public Mountain Trout Water is closed to *all* fishing outside trout season

**Rule (verbatim, 15A NCAC 10C .0316(h)):**

> "In designated Public Mountain Trout Waters the season for taking all species of fish is
> the same as the trout fishing season."

So on Hatchery Supported waters during the March 1 → first-Saturday-in-April closure, you
cannot fish for anything, bait or otherwise — and see NC-BAIT-041, you cannot collect bait
there in any season.

**Source:** `NCAC-10C` 10C .0316 —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0316`
(retrieved 2026-08-17)

### NC-BAIT-034 — Non-trout bait restrictions elsewhere

- **Roanoke River upstream of the U.S. 258 bridge:** "only a single barbless circle hook may
  be used when fishing with live or natural bait from April 1 to June 30. With other tackle,
  only a single barbless hook may be used." (10C .0401(h); also at 10C .0302(e)) —
  `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0401`
- **Trotlines, jug hooks, set hooks:** no live bait, statewide. (10C .0206(b))
- **Lake Rim:** golden shiners only. (10C .0212(b)(3))

---

## 5. Seasonality

### NC-BAIT-040 — Delayed Harvest is the only seasonal bait rule I found

**Verification of this project's claim** ("artificial-only Oct 1 → first Saturday in June,
bait-legal outside that window"): **substantially correct, but the boundaries are wrong in a
way that matters at the margin.** Per 10C .0205(b)(3) and 10C .0316(d), verbatim above and
below, the actual cycle is:

| Period | Bait status | Trout harvest |
|---|---|---|
| Noon, first Saturday in June → September 30 | "no bait or lure restrictions" | 7/day, no size limit |
| October 1 → **one-half hour after sunset on the Friday before** the first Saturday in June | "unlawful to possess natural bait, use more than one single hook on an artificial lure" | none — no harvest or possession |
| ½ hour after sunset Friday → 6:00 a.m. first Saturday in June | **closed to fishing entirely** | — |
| 6:00 a.m. → noon, first Saturday in June | "no bait or lure restrictions" | youth anglers (under 16) only |

**Rule (verbatim, 15A NCAC 10C .0316(d)):**

> "The daily creel limit for trout in Delayed Harvest Trout Waters is seven fish. There is no
> minimum size limit for these fish. The Youth-only Delayed Harvest Trout Water Season is
> from 6:00 a.m. on the first Saturday in June until 12 p.m. that same day. During this
> season individuals under 16 years of age may fish. From 12:00 p.m. on the first Saturday
> in June until September 30, the Delayed Harvest Trout Waters Season is open for anglers.
> From October 1 to one-half hour after sunset on the Friday before the first Saturday in
> June, trout shall not be harvested or possessed while fishing these waters. Delayed
> Harvest Trout Waters are closed to fishing from one-half hour after sunset on the Friday
> before the first Saturday in June to 6 a.m. on the first Saturday in June."

**Concrete dates for the 2026-27 licence year, from the digest:** the digest gives Delayed
Harvest as harvest-open "Aug. 1, 2026 – Sept. 30, 2026", then "Oct. 1, 2026 – June 4, 2027"
restricted to "artificial lures with a single hook" with "No trout may be possessed" and
"Natural bait may not be possessed", with the youth session on June 5, 2027.

**Sources:** `NCAC-10C` 10C .0205(b)(3), 10C .0316(d); `DIGEST-WEB` —
`https://www.eregulations.com/northcarolina/fishing/general-mountain-trout-regulations`
(retrieved 2026-08-17)

**Fixes the dataset needs:** the restricted window ends at ½ hour after sunset on the
**Friday**, not on the Saturday; there is an overnight full closure; and the Saturday
morning is youth-only with no bait restriction. A "can I use bait today?" answer on the
first Saturday in June is wrong under the dataset's current phrasing.

### NC-BAIT-041 — Wild Trout and Catch & Release bait bans are year-round

10C .0205(b)(2) and (b)(6) contain no dates. `NCWRC-TROUT` and the digest both describe
these classifications as year-round with no closed season.

**Source:** `NCWRC-TROUT` — `https://www.ncwildlife.gov/fishing/trout-fishing-north-carolina`;
`DIGEST-WEB` general mountain trout regulations (retrieved 2026-08-17)

---

## 6. Collecting your own bait

### NC-BAIT-050 — Licence

**Rule (verbatim, 15A NCAC 10C .0402(a)):**

> "The use of equipment specified in this Rule requires a valid license that provides basic
> inland fishing privileges."

**Statutory basis (verbatim, G.S. 113-272.3(b)):**

> "In accordance with established fishing customs and the orderly conservation of wildlife
> resources, the Wildlife Resources Commission may by rule provide for use of nets or other
> special devices which it may authorize as an incident to hook-and-line fishing or for
> procuring bait fish without requiring a special device license. In this instance, however,
> the individual fishing must meet applicable hook-and-line license requirements."

**Sources:** `NCAC-10C` 10C .0402(a);
`https://www.ncleg.gov/EnactedLegislation/Statutes/PDF/BySection/Chapter_113/GS_113-272.3.pdf`
(retrieved 2026-08-17)

So: a basic inland fishing licence covers the 10C .0402 bait-collection gear. A **special
device licence** is a separate thing governed by 10C .0401(c), .0404, .0405 and .0407, and
its devices are only lawful in the counties/waters and seasons listed in 10C .0407.

### NC-BAIT-051 — Permitted bait-collection equipment (exhaustive list)

**Rule (verbatim, 15A NCAC 10C .0402(b)):**

> "It is unlawful to take nongame fish for bait or personal consumption in the inland waters
> of North Carolina using equipment other than:
> (1) a net of dip net design not greater than six feet across;
> (2) a seine of not greater than 12 feet in length (except in Lake Waccamaw in Columbus
> County where there is no length limitation) and with a bar mesh measure of not more than
> one-fourth inch;
> (3) a cast net;
> (4) a bow net for the seasons and waters in which the use of bow nets is authorized in 15A
> NCAC 10C .0407;
> (5) a dip net when used in conjunction with a licensed hand-crank electrofisher;
> (6) a gig (except in Public Mountain Trout Waters);
> (7) up to three traps for the seasons and waters in which the use of traps is authorized
> in 15A NCAC 10C .0407;
> (8) up to two eel pots;
> (9) a spear gun for the seasons and waters in which the use of a spear gun is authorized
> in 15A NCAC 10C .0407;
> (10) minnow traps not exceeding 12 inches in diameter and 24 inches in length, with funnel
> openings not exceeding one inch in diameter, from which all fish and animals are removed
> daily, and that are labeled with the user's Wildlife Resources Commission customer number
> or name and address;
> (11) a hand-held line with a single bait attached;
> (12) a single, multiple-bait line for taking crabs not to exceed 100 feet in length,
> marked on each end with a solid float no less than five inches in diameter, bearing legible
> and indelible identification of the user's name and address, and under the immediate
> control and attendance of the person using the device, with a limit of one line per person
> and no more than one line per vessel; or
> (13) a collapsible crab trap with the largest open dimension not greater than 18 inches
> and that by design is collapsed at all times when in the water, except when it is being
> retrieved or lowered to the bottom, with a limit of one trap per person."

**Source:** `NCAC-10C` 10C .0402(b) (History Note: "Readopted Eff. August 1, 2021; Temporary
Amended Eff. September 1, 2022; Amended Eff. March 15, 2023") —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0402`
(retrieved 2026-08-17)

Items (4), (7) and (9) are only lawful where 10C .0407 opens a season — that rule is a
county-by-county list running to roughly 19,000 characters. **Do not summarise it; render it
or link it.** `https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10C-0407`

### NC-BAIT-052 — Limits

10C .0402(e): 200 nongame fish per day in aggregate, subject to species-specific size and
creel limits. 10C .0402(f): bait counts toward the species' daily possession limit. See
NC-BAIT-004.

### NC-BAIT-053 — Waters closed to bait collection

**Rule (verbatim, 15A NCAC 10C .0402(g)):**

> "It is unlawful to take nongame fish for bait from the following waters:
> (1) Public Mountain Trout Waters (except in impounded waters of power reservoirs and
> municipally-owned water supply reservoirs);
> (2) Bear Creek in Chatham County;
> (3) Deep River in Chatham, Lee, and Moore counties and downstream of Coleridge Dam in
> Randolph County;
> (4) Fork Creek in Randolph County; and
> (5) Rocky River in Chatham County."

Additionally, on game lands, **15A NCAC 10D .0104(b)**, verbatim:

> "No trotline, set-hook, net, trap, gig, or other special fishing device mentioned in 15A
> NCAC 10C .0404(b),(c),(d), and (f) may be used in impounded waters located entirely on
> game lands."

**Sources:** `NCAC-10C` 10C .0402(g); `NCAC-10D` 10D .0104(b) (retrieved 2026-08-17)

### NC-BAIT-054 — You may not sell what you collect

**Rule (verbatim, 15A NCAC 10C .0402(c)):** "It is unlawful to sell nongame fishes or
aquatic animals taken under this Rule."

Note the contrast with 10C .0401(g), which allows sale of nongame fishes taken by hook and
line, grabbling, or special device with a special device licence "unless otherwise specified
in this Section". And 10C .0304(d): "Inland game fishes taken from Inland Fishing Waters
shall not be sold."

**Source:** `NCAC-10C` 10C .0402(c), .0401(g), .0304(d) (retrieved 2026-08-17)

### NC-BAIT-055 — Worms and other invertebrates on Commission land

**Rule (verbatim, 15A NCAC 10D .0105(b)(4)):**

> "Insects, worms, or other invertebrates collected as fish bait may be possessed on and
> removed from Commission lands without written permission for personal use only, except
> species on a State or federal protected list may not be collected and may not be removed
> from Commission lands. Sale of these resources is prohibited."

**Source:** `NCAC-10D` 10D .0105 —
`https://www.law.cornell.edu/regulations/north-carolina/15A-N-C-Admin-Code-10D-0105`
(retrieved 2026-08-17)

### NC-BAIT-056 — Salamanders ("spring lizards") and frogs as bait

**Digest, verbatim:**

> "A Wildlife Collection License is needed to take or collect 25 or more frogs (includes
> toads) or salamanders (includes 'spring lizards') in larval (tadpole) or adult form."

> "The daily bag limit (from 12:00 noon to 12:00 noon) for taking bullfrogs is 24, with no
> closed season or license requirement."

**NCWRC, verbatim:** collection without a licence is limited to "fewer than 5 reptiles or
fewer than 25 amphibians that are not endangered, threatened, or special concerned species"
(citing 15A NCAC 10B .0119).

**Sources:** `DIGEST-WEB` —
`https://www.eregulations.com/northcarolina/fishing/nongame-regulations`; `NCWRC-NONGAME`
(retrieved 2026-08-17)

**Caveat:** protected-species status is the binding constraint here and NC has many
range-restricted salamanders. The app should not encourage salamander collection without
pointing at the protected-species list.

### NC-BAIT-057 — Hours: catching bait outside fishing hours

This matters because a downstream tournament rule permits catching bait outside fishing
hours.

> **GAP.** I searched 15A NCAC Subchapters 10C and 10D in full for hour-of-day restrictions
> and found **no statewide restriction on the hours during which inland fishing or bait
> collection may occur.** The only time-of-day provisions I found are:
>
> - the Delayed Harvest overnight closure (10C .0316(d)) and the 6:00 a.m.–noon youth window;
> - Hatchery Supported Trout Waters open "from 7 a.m. on the first Saturday in April" (10C
>   .0316(a)) — an opening-morning time, not a daily one;
> - game lands posted as "Day Use Only Zones", where 15A NCAC 10D .0102 provides that "the
>   use by the public shall be prohibited from sunset to sunrise";
> - minnow traps, which must have "all fish and animals … removed daily" (10C .0402(b)(10)).
>
> **The absence of a statewide hours rule in the code is not the same as an affirmative
> NCWRC statement that night bait collection is allowed, and local laws, municipal
> ordinances, Mountain Heritage Trout City rules, and access-area gate hours are outside the
> scope of what I checked.** The app should not assert "you may catch bait at any hour". It
> should say no statewide hours restriction was found in 15A NCAC 10C/10D, link the rules,
> and defer to posted signage and local rules.

---

## Explicit list of things I could NOT find a citation for

The app must stay silent, or defer to NCWRC, on every one of these.

1. **Whether an angler transporting live bait needs a 10C .0209(a) transport permit.** The
   rule's text covers live freshwater nongame fish with no bait carve-out; no NCWRC page,
   digest passage, or FAQ addresses it either way. See NC-BAIT-010. This is the largest
   unresolved question in the whole file and it sits directly on the disease/invasive vector.
2. **What to lawfully do with leftover live bait.** No NCWRC disposal guidance exists that I
   could find. The carcass-disposal advice on `NCWRC-ANS` is about cleaned fish, not live
   bait, and should not be repurposed. See NC-BAIT-021.
3. **Whether releasing bait back into the same water it was caught from is lawful.**
   Exception 10C .0209(d)(2) is written around "catch and release fishing"; applying it to
   bait is my inference, not the rule's language. See NC-BAIT-020.
4. **Bait rules for `Special Regulation` Trout Waters.** Neither 10C .0205 nor 10C .0316
   states a bait rule for them. Defer to posted regulations. See NC-BAIT-032.
5. **Any statewide hours restriction on fishing or bait collection.** None found; absence of
   a rule is not permission. See NC-BAIT-057.
6. **Any NC health-certification or disease-testing requirement for commercially sold
   baitfish** (e.g. VHS/whirling-disease certification, of the kind several states impose).
   Nothing found in 15A NCAC 10C. If such a requirement exists it is likely under NCDA&CS
   rather than NCWRC, and I did not search NCDA&CS.
7. **Any bait-dealer licence or bait-shop regulation.** Nothing found in 15A NCAC 10C. 10C
   .0402(c) bars *selling* bait you collected yourself, which implies commercial bait comes
   from a differently-regulated channel, but I did not locate that channel.
8. **Rules on importing live bait from another state into NC.** Nothing found beyond the
   10C .0211 prohibited-species list, which applies regardless of origin.
9. **Whether crayfish collection for bait is subject to the same 10C .0402 gear list.** The
   digest says "nongame fishes, crustaceans (crayfish and blue crabs), and mollusks" are
   covered; the rule text of 10C .0402 says "nongame fish". The digest is broader than the
   rule. I did not resolve which controls.
10. **Verification of this project's 1,516 Wild Trout Waters reach count**, and whether the
    dataset correctly excludes tributaries for Wild Trout / Delayed Harvest / Hatchery
    Supported / Special Regulation classifications. The rule wording was confirmed; the
    dataset was not audited. See NC-BAIT-031.
11. **Whether "bream" gets any bait-specific treatment distinct from other game fish.** It
    does not, as far as the code goes — sunfish are game fish (10C .0301(a)(7)). The only
    difference I could source is the creel-limit structure. If a distinct bait rule for
    bream exists somewhere, I did not find it.
12. **Mountain Heritage Trout Waters** (G.S. 113-272.3(e)) — city-designated waters with
    their own management plans. I did not determine whether any impose bait restrictions
    beyond the underlying 10C .0205 classification.

---

## Suggested shape for a consuming app

Each `NC-BAIT-0xx` block above is intended to be a record with: `id`, `claim` (one
sentence), `quote` (verbatim rule text), `citation` (rule number + URL), `retrieved`
(2026-08-17), `confidence` (`rule` | `digest` | `guidance` | `inference` | `gap`), and
`waters_scope`.

Hard rules for the UI:

- Never show a bait claim without its source link and retrieval date.
- Any reach classified `Special Regulation` renders "check the posted regulations" and
  nothing else about bait.
- The leftover-bait screen shows NC-BAIT-020 (the prohibition, quoted) plus NCWRC's "Never
  Move" guidance, and explicitly says NCWRC publishes no disposal instructions — it does not
  invent one.
- The transport screen shows NC-BAIT-010 as unresolved and the two absolute regional bans
  (NC-BAIT-011) as resolved.
- Where the safe ecological answer and the legal answer diverge in certainty, lead with the
  ecological one: **do not move live fish between waters.**
