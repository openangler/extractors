# Spike: depth data availability (issues #7 and #8)

Research spike. **No extractor was written and none should be written yet.** The
deliverable is an answer to "does the data exist, and what would it take to use it".

- **#7** — public bathymetry surveys for NC reservoirs, with High Rock Lake as the
  concrete test case.
- **#8** — whether a useful river depth proxy can be derived from layers already in
  the dataset.

Date of investigation: 2026-08. Every claim below is either cited to a URL or marked
as "could not determine".

---

## Headline answers

| Question | Answer |
| --- | --- |
| Is there a public bathymetry source good enough to replace the Navionics chart on **High Rock Lake**? | **No.** Not at any resolution useful for anchoring. |
| Same for **Tuckertown** and **Badin**? | **No**, and worse — less material exists than for High Rock. |
| Is there a repeatable per-state reservoir bathymetry path at all? | **Partially.** It works for a minority of NC reservoirs (federal/USACE-built, or impounded after ~1950). It does not work for the Yadkin chain. |
| Is a **river depth proxy** worth building? | **Not as a depth layer.** A reach-character layer is worth building and is cheap; a river *depth* number is not, and must never be rendered as a contour. |

---

# Spike #7 — Reservoir bathymetry

## What I looked at

| Source | Checked how | Result for NC reservoirs |
| --- | --- | --- |
| USACE **eHydro** | Queried the national feature service over an NC bounding box | **Nothing.** 100% federal navigation channels |
| USACE Wilmington District lake surveys | Web search of district pages | Surveys exist internally; **no public download found** |
| **USGS Inland Bathymetric & Topobathymetric Survey Inventory** | Queried the ArcGIS feature service directly | **1** inland NC survey nationally-catalogued, and it is a river, not a lake |
| **USGS RESSED** reservoir sedimentation database | Fetched the NC index | 43 NC reservoirs incl. High Rock — but **capacity data, not contours**, scanned PDFs |
| **NOAA** hydrographic / NCEI | Scope review | Coastal & Great Lakes navigable waters only — **inland NC out of scope** |
| **NC OneMap / NCCGIA** | ArcGIS search for NC bathymetry layers | **No inland bathymetry layer found** |
| **NCDEQ** (TMDL / nutrient modelling) | Read the two High Rock reports in full | DEQ's own contractor states no unified bathymetry exists — see below |
| **NCWRC** | Enumerated their ArcGIS services | Fish attractors and access points only; **no depth layer** |
| **TVA** (far-western NC lakes) | Web search | Still *collecting* bathymetry as of Apr 2025; **not published** |
| **Cube Hydro Carolinas** (owns the Yadkin chain) | Fetched their public pages | Lake **levels** only, `Copyright … All Rights Reserved` |
| Pre-impoundment **USGS historical topo** | Queried TNM Access API per lake | Works for post-1950 reservoirs; **fails for High Rock** |
| **GLOBathy** (global modelled lake bathymetry) | Reviewed method | Modelled from surface geometry — **not a survey**, see "do not use" |
| Aggregators (fishermap, gpsnauticalcharts, fishn-buddy) | Search only | Navionics/iBoating derivatives — **excluded by the issue, correctly** |

## The concrete test case: High Rock Lake

**Setting.** High Rock (~15,180 ac, Davidson/Rowan Co.) is the head reservoir of the
Yadkin Project, **FERC No. 2197** — a *private* hydro project, built 1927 by Tallassee
Power Co., later Alcoa Power Generating Inc. (APGI), sold to Cube Hydro Carolinas in
2017. It is not a USACE lake, not a TVA lake, and not a NOAA navigable water. That
single fact eliminates every federal path in one stroke.

### What actually exists

**1. The 1917 pre-impoundment survey.** 79 Tallassee Power Co. maps, *"Topography and
Property Survey – High Rock Basin"*, covering the Yadkin valley from the
Yadkin/South Yadkin confluence down to the dam site. Described in the FERC
relicensing sediment report ([Sediment Fate and Transport, Normandeau/PB Power,
Dec 2004](https://www.savehighrocklake.org/Proj2197/IAG/WQ/FinalDraftSedimentReport120904.pdf)).
This is genuine pre-impoundment topography — i.e. real bathymetry once flooded.
**But:** it is a set of 1917 paper maps held by the licensee. I found no digital,
georeferenced, publicly downloadable copy. And it is 109 years stale.

**2. The 1997 aerial survey.** Continental Aerial Survey, Inc., commissioned by APGI,
2 ft contour interval. Critically, per the same report it covers only
*"from 12 feet below normal full pool outwards"* — it is a **shoreline-rim survey
during drawdown, not a bathymetric survey.** Everything deeper than 12 ft is
1917 data. Also licensee-held, not published.

**3. What was published.** Figures 4-1 … 4-6 of the 2004 FERC report: the 1917 and
1997 surfaces rendered as **two-class shading — deeper than 10 ft (red) vs shallower
than 10 ft (pink)** — from Abbotts Creek upstream to the confluence. That is the full
extent of publicly-released High Rock bathymetry. A binary 10 ft mask, as raster
figures in a PDF, at ~2004 vintage.

**4. NC DEQ's attempt.** The state built an EFDC/WASP model of High Rock for the
nutrient TMDL. Its
[final report](https://files.nc.gov/ncdeq/Water%20Quality/Planning/TMDL/Internal%20files/Final_HighRockLakeModel_Mar2015_revFeb2016_revAug2016_revOct2016.2.pdf)
(§2.2.2) says, verbatim:

> "The bathymetry, or bottom elevation, for the model grid was estimated from
> multiple sources. **A single unified source of lake bathymetry was not available**
> to prescribe the bottom elevation."

They stitched together DWR cross-section soundings taken on monitoring trips, APGI's
(private) contour coverage, an APGI upper-lake cross-section survey, dam/forebay
drawings, and a City of Salisbury HEC-6 study, then **hand-interpolated a thalweg
between two anchor elevations** and iterated until the stage-volume curve matched.
The resulting grid is **538 surface cells at ~100–300 m** over 15,180 acres — roughly
one depth value per 28 acres. That is a water-quality model grid. It is not a chart,
and it is not safe to navigate by.

The
[companion data-collection report](https://files.nc.gov/ncdeq/Water%20Quality/Planning/TMDL/Special%20Studies/High%20Rock%20Lake/FINAL_Report_EW08011_7_30_10.pdf)
confirms DWR/EPA measured bathymetry as **cross-sections at 10 monitoring stations
(twice at two of them)** and that *"NCDWQ and/or EPA collected the bathymetry data,
which was not included in the database."* Ten cross-sections, not released.

**5. RESSED.** High Rock is in the
[USGS/ACWI reservoir sedimentation database](https://water.usgs.gov/osw/ressed/interactive_map/map_nc.html)
as NID NC00388, datasheet `7-10`. I fetched it: a **64 KB scanned image PDF** with no
text layer. RESSED carries storage-capacity-by-stage, not contours. Useful for
"the lake has lost ~6% of capacity"; useless for "where is the 18 ft break".

**6. Historical topo.** I queried the TNM Access API over the High Rock bbox
(`-80.35,35.55,-80.15,35.72`): **29 historical quads, earliest 1949.** The dam closed
in 1927. There is **no pre-impoundment USGS quadrangle for High Rock Lake.** The
pre-impoundment-topo trick — which is the one genuinely repeatable licence-clean
method — does not work here.

### Tuckertown and Badin

- **Badin Lake** (Narrows Dam, 1917). Same licensee, same FERC project. Earliest
  1:24k quads over the pool are 1977–1994 — all post-impoundment. Nothing found.
- **Tuckertown Reservoir** (1962). The **1949 High Rock 7.5′ quad** predates it and
  covers part of the upper pool; the quads over the lower pool (Albemarle NE 1977,
  Handy 1980) do not. So *partial* pre-impoundment coverage exists, at whatever
  contour interval that 1949 sheet carries — **I did not verify the contour
  interval**; the GeoPDF is a raster scan with no text layer, so it needs a human to
  read the collar. NC Piedmont sheets of that era are typically 10 or 20 ft, which is
  far too coarse to fish by regardless.

### The direct answer

**No.** There is no public bathymetry source good enough to replace the Navionics
chart on High Rock Lake. The best public artifact is a two-class 10 ft mask in a
2004 PDF; the best public numeric grid is a 538-cell water-quality model that its own
authors describe as interpolated between two anchor points. The actual surveys —
1917 and 1997 — are privately held by the licensee and were never released as data.

The honest framing for the tournament: **if the owner is reading contours off
Navionics for the Abbotts Creek arm, there is nothing public to switch to.** One
mildly useful crumb from the sediment report: the Abbotts Creek → Crane Creek section
is the part of High Rock that changed *least* between 1917 and 1997 (the >10 ft area
is "similar in 1917 and 1997"), with the heavy infill concentrated from Swearing
Creek up to the I-85 bridge. So the older material is *less* wrong down there than
elsewhere — which is a statement about a PDF figure, not a substitute for a chart.

## Where the reservoir path *does* work (the repeatable part)

Two methods generalise, and both are licence-clean:

**A. Pre-impoundment USGS topo differencing.** For any reservoir impounded after the
7.5′ quad programme reached the area (~1950 in NC Piedmont), the pre-impoundment quad
gives real land contours; subtract from full-pool elevation and you have depth
contours. Verified as viable via TNM Access API:

| Reservoir | Impounded | Pre-impoundment 1:24k quads found |
| --- | --- | --- |
| Falls Lake | 1981 | Bayleaf 1967, Wake Forest 1967, NE Durham 1973, SE Durham 1973, Creedmoor 1974, Grissom 1978 |
| Jordan Lake | 1982 | Chapel Hill 1946, Farrington 1951, Merry Oaks 1969, New Hope Dam 1969, Moncure 1970, SW Durham 1973, Green Level 1973, Cokesbury 1974, New Hill 1974 |
| Randleman | 2010 | Randleman 1970, Climax 1970, Glenola 1970, Asheboro 1970, Grays Chapel 1974, Farmer 1974 |
| Tuckertown | 1962 | High Rock 1949 (partial pool only) |
| High Rock | 1927 | **none** |
| Badin | 1917 | **none** |

Caveats that must be stated on any layer built this way: it is **pre-sedimentation**
(High Rock lost 14,919 ac-ft — ~6% of capacity — in 80 years, and the loss is not
spatially uniform); contour interval is 10–20 ft, not the 1–2 ft anglers expect; and
the maps are raster GeoPDFs requiring contour vectorisation, which is error-prone
near the shoreline. Licence: USGS topo maps are **US federal works, public domain**,
downloadable from the TNM Access API (`datasets=Historical Topographic Maps`),
7–22 MB per GeoPDF.

**B. USGS published bathymetric surveys**, where they exist. Discovery is solved: the
[USGS Inland Bathymetric and Topobathymetric Survey Inventory](https://www.sciencebase.gov/catalog/item/5fce600bd34e30b912396ad0)
is queryable as an ArcGIS feature service
(`services.arcgis.com/v01gqwM5QqNysAAi/.../USGS_InlandBathymetry_SurveyInventory_v3/FeatureServer/1`)
with per-survey vintage, method, resolution and a DOI link. **251 surveys nationally.**
Over an NC bbox it returns **2 records**, one of which is a regional coastal-plain
topobathy DEM that merely clips NC. So: **0 NC reservoirs.** (I queried v3; a v4 exists
as a 62 MB file geodatabase on ScienceBase that I did not download — I could not
confirm whether v4 adds NC reservoirs, but nothing suggests it does.) Licence: USGS
data releases are public domain. This is the right per-state discovery mechanism even
though NC comes back nearly empty — it is cheap, it is one HTTP call, and it will
return real hits in states with active USGS lake-survey cooperation.

**What is not worth pursuing:**

- **USACE eHydro.** I queried the survey feature service over an NC bbox: it caps at
  2000 records and every one is a navigation project — Wilmington Harbor, Morehead
  City, AIWW, Oregon Inlet, Hatteras, Beaufort. **Zero inland reservoirs.** eHydro is
  a dredging archive, not a lake programme.
- **USACE district lake surveys.** Falls/Jordan/Kerr Scott are resurveyed for
  sedimentation, but I could not find a public download of any of it. **Could not
  determine** whether it is releasable; the realistic path is a records request to
  Wilmington District, not an extractor.
- **NOAA.** Hydrographic survey scope is navigable coastal waters and the Great Lakes.
  Inland NC reservoirs are outside it entirely.
- **GLOBathy** and similar global modelled lake bathymetry. CC0 and technically
  attractive, but the depths are **inferred from surface geometry and a maximum-depth
  regression**, validated at 1,503 waterbodies globally. It will happily produce a
  smooth 30 m "bathymetry" for High Rock that looks like data and is fiction. Same
  failure mode as the river proxy below, but more dangerous because it arrives as a
  raster and looks authoritative. **Do not ingest.**

## Licence notes (reservoirs)

- **USGS / USACE / NOAA / NAIP** — works of the US federal government, **public
  domain**. Clean for commercial use.
- **NC state agencies (NCWRC, NCDEQ)** — public records under NC G.S. Ch. 132. The
  NCWRC ArcGIS services carry **no `copyrightText`, no `licenseInfo`** (verified via
  the service JSON) — i.e. no stated restriction, but also no affirmative grant.
- **⚠ County and city GIS in NC is different.**
  [G.S. 132-10](https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_132/GS_132-10.html)
  lets a **county or city** condition an electronic copy on a written agreement that
  it *"will not be resold or otherwise used for trade or commercial purposes."* This
  does **not** apply to state agencies, but NC OneMap aggregates county-sourced
  layers. Any layer that traces back to a county/city source must be licence-checked
  individually before it enters a commercial path.
- **Cube Hydro Carolinas** (High Rock/Tuckertown/Badin/Falls levels and any survey
  data) — `Copyright Cube Hydro Carolinas. All Rights Reserved.`
  **Not usable.** Their lake-level pages are the only public real-time pool data for
  these three reservoirs (there is **no USGS reservoir-elevation gauge** on any of
  them — see below).
- Aggregators (fishermap.org, gpsnauticalcharts, fishn-buddy, thefishinguide) are
  Navionics/iBoating derivatives. The issue is right to exclude them, and my search
  for a High Rock depth map surfaced **only** these — which is itself confirmation
  that no primary public source exists.

## Recommendation — #7

**Do not build a general NC reservoir bathymetry extractor.** The coverage is not
there. Specifically:

- **Do not build anything for High Rock, Tuckertown, or Badin.** Answer to the owner:
  keep the Navionics chart; nothing public replaces it.
- **Do build** the one-call **USGS Inland Bathymetry Inventory probe** as a discovery
  step in the per-state pipeline (~30 lines, returns per-state survey records with
  DOIs). It costs almost nothing and it is the correct generic mechanism. It will
  return ~nothing for NC and real results for other states.
- **Consider, narrowly,** pre-impoundment topo differencing — but scoped to Falls,
  Jordan and Randleman only, clearly labelled *"pre-impoundment land contours,
  10–20 ft interval, does not account for sedimentation, not for navigation"*. This
  is a **later** piece of work; it needs raster contour vectorisation and it is not
  what the immediate use case wants.
- **Record the negative result** in the dataset itself — a `bathymetry: none_public`
  attribute per waterbody is more valuable than a bad layer, because it stops the
  next person re-running this spike.

---

# Spike #8 — River depth proxy

## Confirming the gap first

Before evaluating proxies: **is there really no public river bathymetry?** Nearly.
The USGS inventory query over NC returned exactly one real inland survey:

> [Single-beam bathymetric survey of the French Broad River near the I-26 bridge
> south of Asheville, June 2019 (pre-construction)](https://doi.org/10.5066/P9UP7SUO)
> — CEESCOPE single-beam echosounder on a canoe, RTK-positioned, NAD83(2011) /
> NAVD88, UTM 17N. Extent: **300 m upstream to 500 m downstream of the bridge.**
> One 4.1 MB `.xyz` file. Public domain (USGS data release).

That is **800 metres** of the French Broad, surveyed for NCDOT bridge-scour purposes.
It is the only one. So the premise of issue #8 holds: there is no contour source for
NC rivers, and this is not going to change.

## Evaluating the four candidate proxies

### 1. NHDPlus slope + stream order + mean annual flow — **useful, but not depth**

Already wired: `nc/enrich_usgs.py` pulls `streamorde`, `slope`, `totdasqkm`, `qama`
from NHDPlus HR (layer 3) and normalises the `-9 / -9998 / -9999` sentinels. These
are real, public-domain, per-reach, statewide. They describe **reach character** —
steep low-order = trout riffle water; low-slope high-order with big drainage = the
warm slow water catfish and musky sit in.

They contain **no depth information whatsoever.** Slope is a longitudinal gradient;
order and drainage are size proxies. Nothing in NHDPlus HR resolves a pool from a
riffle, let alone gives feet of water.

There is a closer-to-depth federal product worth naming:
[**Select Hydrologic Attributes: Bankfull Hydraulic Geometry Related to Physiographic
Divisions**](https://www.sciencebase.gov/catalog/item/5cf02bdae4b0b51330e22b85) —
bankfull width, depth and cross-sectional area for **every NHDPlusV2 flowline in
CONUS**, `BANKFULL_CONUS.zip`, **18.6 MB**, public domain. Derived from
[Bieger et al. 2015](https://swat.tamu.edu/media/114657/bieger_etal_2015.pdf)
regional regressions.

Read the fine print before anyone gets excited:

- It is a **regression on drainage area alone**. Every reach with the same drainage
  area in the same physiographic division gets the **same** depth. There is no
  within-reach variation, no pool, no hole, no channel.
- CONUS R² for **bankfull depth vs drainage area is 0.43**. In the Appalachian
  Highlands division (which covers the Piedmont and the Blue Ridge, i.e. all of the
  French Broad and Yadkin) it is better — **R² 0.77, SEE 0.12 log₁₀ units**, i.e. a
  one-standard-error band of roughly **×/÷ 1.3**.
- Most importantly: **bankfull depth is not water depth.** Bankfull is the
  channel-forming stage — roughly a 1–2 year flood. Today's water is somewhere below
  it, usually well below. This number describes the *channel*, not the *river*.

Verdict: **ingest it as a channel-character attribute, never as depth.**

### 2. USGS gauge stage — **the strongest real signal, and it is relative**

Verified against NWIS: **291 active NC sites with real-time gage height (00065)**,
including six on the French Broad —
Rosman `03439000`, Blantyre `03443000`, Fletcher `03447687`, Asheville `03451500`,
Marshall `03453500`, Hot Springs `03454500`. Public domain, already a dependency
(`waterservices.usgs.gov`).

This is genuinely actionable and the issue is right that on a tailwater it beats a
static contour: "the river is 1.8 ft above yesterday and rising" changes where fish
are and whether you can wade, in a way a contour never will. It also composes
directly with the dam-generation alerting work.

But note what it is **not**: gage height is stage above an arbitrary local datum, not
depth. Two gauges 20 miles apart are not on the same datum. Stage tells you *change*
at *one point*. It says nothing about depth anywhere, including at the gauge.

Reservoir caveat found while doing #7: querying NWIS for NC reservoir-elevation
parameters (`00062/62614/62615`, active, IV) returns **19 sites** — Falls, Jordan,
Kerr Scott, Hyco, Mattamuskeet and a cluster of small Wake County lakes. **High Rock,
Tuckertown and Badin are not among them.** For the Yadkin chain, real-time pool
elevation exists only on Cube's copyrighted pages. That matters: on a lake with a
significant drawdown, a contour without a current pool elevation is already wrong.

### 3. The 1,009 NCWRC fish attractors — **quantified, and they do not help rivers**

I measured this rather than assuming, in
`reference-layers/fish-attractors.geojson` (606 KB, 1,009 point features):

- **254 of 1,009 (25.2%)** carry a non-null `Full_Pool_Depth_Ft`.
- All 254 are clean integers — no sentinels, no text. Range **2–40 ft**,
  median **12 ft**, mean 11.3 ft. **43.3% are ≤10 ft.**
- Only **20 of 71 waterbodies** have any depth value at all.
- **Every one of the 71 waterbodies is a lake, reservoir or pond.** There are
  **zero river attractors.** This layer contributes **nothing** to a river proxy.
- And for the #7 test case: **High Rock (22 attractors), Tuckertown (18) and Badin
  (27) — all 67 have `Full_Pool_Depth_Ft = null`.** The one dataset that carries real
  point depths carries none for the three lakes that were asked about.

Where depths do exist they are concentrated in small Piedmont impoundments —
Harris Lake 75/182, Lake Cammack 31/42, Randleman 22/41, Lake Mackintosh 17/46,
Graham-Mebane 15/21, Lake Hickory 15/15.

These are real measured depths and they are worth surfacing **as what they are: a
depth annotation on a known structure point**. "This brush pile sits in 14 ft at full
pool" is a true and useful sentence. Interpolating a surface from ~20 points spread
over a 4,100-acre lake is not.

### 4. Depth from NAIP colour breaks — **no**

NAIP itself is fine: USDA/FSA, **public domain**, 0.6 m 4-band since 2018 (1–2 m
2002–2017), free via the National Map image service and the AWS open-data registry.
Licence-clean, as the issue says.

The physics is the problem. The USGS's own work on spectral depth retrieval
([Legleiter, *The optical river bathymetry toolkit*, 2021](https://onlinelibrary.wiley.com/doi/full/10.1002/rra.3773);
[Legleiter et al. 2011 on turbid sand-bed rivers](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2011WR010591))
is explicit: optical depth retrieval works only in **clear, shallow water — typically
under 2 m, and not in turbid or deeper rivers.** Turbidity is the dominant predictor
of failure.

Applied to the two waters actually in question:

- **French Broad** — a turbid Piedmont/Blue Ridge river with a stained water column.
  Below roughly 2 m the signal is gone. Above 2 m it is confounded by substrate
  colour: dark bedrock in 3 ft and light sand in 8 ft look the same.
- **High Rock** — the most sediment-loaded reservoir on the Yadkin, receiving the
  bedload of the entire upper basin. Optical retrieval is hopeless there.

Additional practical blockers even where the physics allowed it: NAIP is a single
uncalibrated leaf-on acquisition per cycle with no water-surface elevation metadata,
so there is no way to tie a derived depth to a stage; and mosaic seamlines cross
water bodies with visible radiometric jumps.

Verdict: **do not build.** This is the classic case where an attractive
licence-clean input produces a confident-looking wrong answer.

## The failure mode, stated plainly

The requirement in the issue is right and should be written into whatever ships:

> **A derived depth layer presented as a contour is worse than nothing.**

The concrete failure is a person anchoring a small boat at night, on inferred depth,
in a reservoir whose deep channel has migrated with sedimentation. Bankfull-regression
depth and colour-break depth are both *smooth* — they will never show the stump field,
the old roadbed, or the channel edge, which are exactly the things that matter. A
smooth wrong surface is more dangerous than a blank map, because a blank map makes the
angler look overboard.

So: whatever is built from #8 may say **"this reach is low-gradient, high-order, big
drainage — slow deep-character water"** and **"stage is up 1.4 ft since yesterday"**.
It may **never** emit a number in feet against a location, and it must never be
rendered as an isoline.

## Recommendation — #8

**Build a narrower version. Do not build a river depth layer.**

Build (cheap, honest, uses what is already wired):

1. **Reach-character classification** from NHDPlus HR slope / stream order /
   drainage area / mean annual flow — already fetched by `enrich_usgs.py`. Emit an
   ordinal character class, **not a depth**.
2. **Stage-change from NWIS `00065`** on the nearest gauge — 291 active NC sites,
   already a dependency. Relative, per-gauge, framed as change. Composes with
   dam-generation alerting.
3. Optionally ingest **`BANKFULL_CONUS.zip`** (18.6 MB, public domain) as a
   `bankfull_depth_ft` **channel-geometry** attribute, with the R² and the
   "not water depth" caveat carried in the schema field description, not just the
   docs.
4. **Surface the 254 attractor point depths as points**, attached to their structure,
   scoped to the 20 waterbodies that have them. Never interpolate between them.

Do not build:

- NAIP-derived depth. Physics says no for these waters.
- Any interpolated river or lake depth surface from any of the above.
- Anything that renders as a contour line.

---

## Sources

- USGS Inland Bathymetric and Topobathymetric Survey Inventory — https://www.sciencebase.gov/catalog/item/5fce600bd34e30b912396ad0
- USGS Inland Bathymetry programme — https://www.usgs.gov/3d-elevation-program/inland-bathymetry
- USGS single-beam survey, French Broad River at I-26 (2019) — https://doi.org/10.5066/P9UP7SUO
- USGS/ACWI RESSED, North Carolina index — https://water.usgs.gov/osw/ressed/interactive_map/map_nc.html
- USGS RESSED datasheet 7-10 (High Rock) — https://water.usgs.gov/osw/ressed/datasheets/7-10.pdf
- USACE eHydro / hydrosurvey archive — https://data.gov/maritime/hydrosurvey-data-archive-for-federal-navigation-projects/
- USACE Wilmington District hydrographic surveys — https://www.saw.usace.army.mil/Missions/Navigation/Hydrographic-Surveys/
- NOAA hydrographic survey data (scope) — https://nauticalcharts.noaa.gov/data/hydrographic-survey-data.html
- Yadkin Project (FERC 2197), *Sediment Fate and Transport*, Normandeau/PB Power, Dec 2004 — https://www.savehighrocklake.org/Proj2197/IAG/WQ/FinalDraftSedimentReport120904.pdf
- NC DEQ, *High Rock Lake hydrodynamic and nutrient response model*, final Oct 2016 — https://files.nc.gov/ncdeq/Water%20Quality/Planning/TMDL/Internal%20files/Final_HighRockLakeModel_Mar2015_revFeb2016_revAug2016_revOct2016.2.pdf
- NC DEQ, *Data Collection in Support of Upper Yadkin River Watershed–High Rock Lake* (EW08011, 2010) — https://files.nc.gov/ncdeq/Water%20Quality/Planning/TMDL/Special%20Studies/High%20Rock%20Lake/FINAL_Report_EW08011_7_30_10.pdf
- Cube Hydro Carolinas lake levels — https://cubecarolinas.com/lake-levels/
- TVA Chatuge dam safety page (states bathymetry collection still in progress, Apr 2025) — https://www.tva.com/newsroom/regional-mountain-dams-safety-initiative/chatuge-dam-safety-modifications
- USGS TNM Access API (historical topographic maps) — https://tnmaccess.nationalmap.gov/api/v1/products
- USGS Select Hydrologic Attributes: Bankfull Hydraulic Geometry — https://www.sciencebase.gov/catalog/item/5cf02bdae4b0b51330e22b85
- Bieger et al. 2015, *Bankfull Hydraulic Geometry Relationships for the Physiographic Regions of the US*, JAWRA 51(3):842–858 — https://swat.tamu.edu/media/114657/bieger_etal_2015.pdf
- Legleiter 2021, *The optical river bathymetry toolkit* — https://onlinelibrary.wiley.com/doi/full/10.1002/rra.3773
- Legleiter et al. 2011, remote bathymetric mapping of a turbid sand-bed river — https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2011WR010591
- NAIP on AWS Registry of Open Data (licence) — https://registry.opendata.aws/naip/
- USGS NAIP imagery service — https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer
- GLOBathy — https://www.nature.com/articles/s41597-022-01132-9
- NC G.S. 132-10, qualified exception for GIS — https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_132/GS_132-10.html
- NC OneMap — https://www.nconemap.gov/
- USGS NWIS water services (gauge inventory queries) — https://waterservices.usgs.gov/
