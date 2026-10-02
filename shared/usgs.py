"""usgs.py — USGS hydrology lookups for a single point, any state.

  * elevation()     — USGS 3DEP point elevation (EPQS)
  * nhd_reach()     — the NHDPlus HR flowline at a point: stream order, slope,
                      drainage area, mean-annual flow, GNIS name
  * load_gages() / nearest_gage() — active real-time NWIS streamgages

Moved out of nc/enrich_usgs.py when SC needed the same lookups. Every output is
federal public domain (17 U.S.C. §105). Standard library only.
"""

import json
import math
import time
import urllib.parse
import urllib.request

EPQS = "https://epqs.nationalmap.gov/v1/json"
NHD = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/3/query"
NWIS = "https://waterservices.usgs.gov/nwis/site/"
UA = "openangler-extractors/1.0"


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.2 * (i + 1))


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load_gages(state_cd):
    """Active streamgages with real-time data in one state -> [(id,name,lat,lon)].

    `state_cd` is the two-letter USPS code NWIS expects ("nc", "sc").
    """
    q = urllib.parse.urlencode({"format": "rdb", "stateCd": state_cd, "siteType": "ST",
                                "siteStatus": "active", "hasDataTypeCd": "iv"})
    gages = []
    for line in get(f"{NWIS}?{q}").splitlines():
        if line.startswith("USGS\t"):
            f = line.split("\t")
            try:
                gages.append((f[1], f[2], float(f[4]), float(f[5])))
            except (ValueError, IndexError):
                pass
    return gages


# NHDPlus HR value-added attributes carry no-data sentinels rather than nulls:
# -9 on streamorde, -9998/-9999 on slope / totdasqkm / qama. They look like data
# (a -9 stream order sorts below a headwater stream), so normalise them here —
# at extraction, once — instead of leaving every consumer to recognise them.
NHD_NODATA = (-9.0, -9998.0, -9999.0)


def nhd_number(raw, allow_negative=False):
    """NHDPlus VAA value -> float, or None if it is a no-data sentinel.

    Stream order, slope, drainage area and mean-annual flow are all
    non-negative quantities, so any negative is treated as no-data too — that
    catches sentinel codes NHDPlus adds later without a code change.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v in NHD_NODATA or (not allow_negative and v < 0):
        return None
    return v


def epqs_url(lat, lon):
    return f"{EPQS}?" + urllib.parse.urlencode(
        {"x": lon, "y": lat, "units": "Meters", "wkid": 4326})


def parse_elevation(payload):
    """EPQS response -> metres. Its own no-data value is -1000000."""
    try:
        v = float(json.loads(payload)["value"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return round(v, 1) if v > -1000 else None


def elevation(lat, lon):
    try:
        return parse_elevation(get(epqs_url(lat, lon)))
    except Exception:
        return None


def nhd_url(lat, lon):
    q = urllib.parse.urlencode({
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
        "distance": 350, "units": "esriSRUnit_Meter",
        "outFields": "gnis_name,streamorde,slope,totdasqkm,lengthkm,qama",
        "returnGeometry": "false", "f": "json"})
    return f"{NHD}?{q}"


def nhd_pick(feats, waterbody):
    """Pick the reach for this site and normalise its attributes.

    Prefers a flowline whose GNIS name matches the waterbody, else the one with
    the largest drainage area.
    """
    if not feats:
        return {}
    wb = (waterbody or "").upper().replace(" RIVER", "").replace(" CREEK", "").strip()
    named = [f for f in feats if wb and f["attributes"].get("gnis_name")
             and wb in f["attributes"]["gnis_name"].upper()]
    pool = named or feats
    best = max(pool, key=lambda f: nhd_number(f["attributes"].get("totdasqkm")) or 0)
    a = best["attributes"]
    order = nhd_number(a.get("streamorde"))
    slope = nhd_number(a.get("slope"))
    da = nhd_number(a.get("totdasqkm"))
    qama = nhd_number(a.get("qama"))
    return {
        "nhd_name": a.get("gnis_name"),
        "stream_order": int(order) if order is not None else None,
        "slope": round(slope, 5) if slope is not None else None,
        "drainage_area_sqkm": round(da, 1) if da is not None else None,
        "mean_annual_flow_cfs": round(qama, 1) if qama is not None else None,
        "name_matched": bool(named),
    }


def nhd_reach(lat, lon, waterbody):
    """Nearest NHDPlus flowline; prefer a name match, else largest drainage."""
    try:
        feats = json.loads(get(nhd_url(lat, lon))).get("features", [])
    except Exception:
        return {}
    return nhd_pick(feats, waterbody)


def nearest_gage(lat, lon, gages):
    """The closest gage to a point as {id,name,km,url}, or None with no gages."""
    if not gages:
        return None
    gid, gname, glat, glon = min(gages, key=lambda g: haversine(lat, lon, g[2], g[3]))
    return {"id": gid, "name": gname,
            "km": round(haversine(lat, lon, glat, glon), 1),
            "url": f"https://waterdata.usgs.gov/monitoring-location/{gid}/"}


def enrich_site(site, gages):
    """USGS attributes for one access-point record, keyed like the record.

    `site` needs locationID, locationName, waterbodyName, latitude, longitude —
    the fields every state's all-locations.json carries.
    """
    lat, lon = site["latitude"], site["longitude"]
    rec = {"locationID": site["locationID"], "locationName": site["locationName"],
           "waterbodyName": site.get("waterbodyName"),
           "elevation_m": elevation(lat, lon)}
    rec.update(nhd_reach(lat, lon, site.get("waterbodyName")))
    gage = nearest_gage(lat, lon, gages)
    if gage:
        rec["nearest_gage"] = gage
    return rec
