"""Electricity-grid and wetland layers from OpenStreetMap, and site screening for proposed stations.

Grid: power lines (transmission and distribution), substations, transformers (largely Umeme
distribution transformers) and plants. Wetlands: natural=wetland and water polygons; Kampala's
papyrus valleys are flood-prone and protected (National Environment (Wetlands) Regulations).
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, Polygon

import config
from emobility.fetch import _bbox_str, _overpass


def _elements(query):
    return _overpass(f"[out:json][timeout:600];{query}")["elements"]


def power_lines() -> gpd.GeoDataFrame:
    rows = []
    for el in _elements(f'way["power"~"^(line|minor_line|cable)$"]({_bbox_str()});out geom tags;'):
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(coords) >= 2:
            t = el.get("tags", {})
            rows.append({"power": t.get("power"), "voltage": t.get("voltage"), "geometry": LineString(coords)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def power_points() -> gpd.GeoDataFrame:
    rows = []
    for el in _elements(f'nwr["power"~"^(substation|transformer|plant|generator)$"]({_bbox_str()});out center tags;'):
        lat, lon = (el["lat"], el["lon"]) if "lat" in el else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        if lat is None:
            continue
        t = el.get("tags", {})
        rows.append({"power": t.get("power"), "name": t.get("name"), "voltage": t.get("voltage"), "geometry": Point(lon, lat)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def wetlands() -> gpd.GeoDataFrame:
    rows = []
    for el in _elements(f'way["natural"~"^(wetland|water)$"]({_bbox_str()});out geom tags;'):
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(coords) >= 4 and coords[0] == coords[-1]:
            poly = Polygon(coords)
            if poly.is_valid and poly.area > 0:
                rows.append({"natural": el.get("tags", {}).get("natural"), "geometry": poly})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def screen_sites(sites: gpd.GeoDataFrame, lines, points, wet, terrain_layers, dem_transform, s2_layers=None, s2_transform=None):
    """Engineering screen for each proposed site: terrain and flood exposure, plus mapped-grid proximity.

    Thresholds are screening rules of thumb (ASSUMPTION), not design standards:
      terrain: slope at site <= 8 degrees for forecourt/cabinet works
      flood: site >= 3 m above the local valley floor and outside mapped wetland/water
    Distances to mapped power lines/transformers are reported for information only: OSM maps a small
    fraction of the UEDCL distribution network, so a large distance does not mean no supply. Grid needs
    are graded from the site's load instead (see grid_connection_class).
    """
    from emobility import remote_sensing as rs

    s = sites.to_crs(config.METRIC_CRS).copy()
    x, y = s.geometry.x.to_numpy(), s.geometry.y.to_numpy()
    lines_m, pts_m, wet_m = lines.to_crs(s.crs), points.to_crs(s.crs), wet.to_crs(s.crs)

    def nearest(gdf):
        if gdf.empty:
            return np.full(len(s), np.inf)
        j = gpd.sjoin_nearest(s[["geometry"]], gdf[["geometry"]], distance_col="d")
        return j.groupby(level=0)["d"].min().reindex(s.index).to_numpy()

    s["dist_power_line_m"] = nearest(lines_m)
    s["dist_transformer_m"] = nearest(pts_m[pts_m["power"] == "transformer"])
    s["dist_substation_m"] = nearest(pts_m[pts_m["power"] == "substation"])
    s["in_wetland"] = s.index.isin(gpd.sjoin(s[["geometry"]], wet_m[["geometry"]], predicate="within").index)
    s["elevation_m"] = rs.sample(terrain_layers["elev"], dem_transform, x, y)
    s["slope_deg"] = rs.sample(terrain_layers["slope"], dem_transform, x, y)
    s["above_valley_floor_m"] = rs.sample(terrain_layers["above_floor"], dem_transform, x, y)
    if s2_layers is not None:
        s["ndvi"] = rs.sample(s2_layers["ndvi"], s2_transform, x, y)
        s["ndbi"] = rs.sample(s2_layers["ndbi"], s2_transform, x, y)

    s["terrain_ok"] = s["slope_deg"] <= 8
    s["flood_ok"] = (s["above_valley_floor_m"] >= 3) & ~s["in_wetland"]
    s["site_screen"] = np.select([~s.flood_ok, ~s.terrain_ok], ["flood risk: relocate or raise", "steep: civil works"], "suitable")
    return s


def grid_connection_class(kw):
    """Indicative UEDCL connection for a site's peak load (ASSUMPTION: LV three-phase up to ~50 kW,
    dedicated 11 kV/LV transformer up to ~315 kVA, larger loads need an MV connection/own substation)."""
    kw = np.asarray(kw, float)
    return np.select([kw <= 50, kw <= 315], ["LV supply", "dedicated transformer"], "MV connection")
