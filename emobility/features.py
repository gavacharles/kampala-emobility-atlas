"""Build the analysis grid and per-cell features from the fetched layers."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box

import config
from emobility import buildings, car_economics, population

MANUAL_DIR = Path(__file__).resolve().parent.parent / "data" / "manual"
# Hand-entered field/app records, and the output of collect_stations_google.py.
MANUAL_STATION_FILES = [MANUAL_DIR / "ev_stations.csv", MANUAL_DIR / "ev_stations_google.csv"]

TRIP_GENERATORS = ["shop", "market", "food_drink", "education", "health"]
AFFLUENCE_PROXIES = ["bank", "office", "food_drink"]


def build_grid() -> gpd.GeoDataFrame:
    s, w, n, e = config.BBOX
    bounds = gpd.GeoSeries([box(w, s, e, n)], crs="EPSG:4326").to_crs(config.METRIC_CRS).total_bounds
    size = config.CELL_SIZE_M
    xs = np.arange(bounds[0], bounds[2], size)
    ys = np.arange(bounds[1], bounds[3], size)
    cells, rows, cols = [], [], []
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            cells.append(box(x, y, x + size, y + size))
            rows.append(r)
            cols.append(c)
    grid = gpd.GeoDataFrame({"row": rows, "col": cols}, geometry=cells, crs=config.METRIC_CRS)
    grid["cell_id"] = grid["row"].astype(str) + "_" + grid["col"].astype(str)
    return grid


def load_manual_stations() -> gpd.GeoDataFrame:
    """Stations missing from OSM (field records, Google Places). Only rows with coordinates are used."""
    frames = [pd.read_csv(f) for f in MANUAL_STATION_FILES if f.exists()]
    df = pd.concat(frames, ignore_index=True).dropna(subset=["lat", "lon"]) if frames else pd.DataFrame()
    if df.empty:
        return gpd.GeoDataFrame(columns=["name", "operator", "layer", "geometry"], geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame(
        {"name": df["name"], "operator": df["operator"], "layer": "ev_station", "source": df.get("source")},
        geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )


def count_points(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.Series:
    if points.empty:
        return pd.Series(0, index=grid.index)
    joined = gpd.sjoin(points.to_crs(grid.crs), grid[["geometry"]], predicate="within")
    return joined.groupby("index_right").size().reindex(grid.index, fill_value=0)


def road_km(grid: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> pd.Series:
    if roads.empty:
        return pd.Series(0.0, index=grid.index)
    pieces = gpd.overlay(
        roads.to_crs(grid.crs), grid[["cell_id", "geometry"]], how="intersection", keep_geom_type=True
    )
    km = pieces.geometry.length.groupby(pieces["cell_id"]).sum() / 1000
    return grid["cell_id"].map(km).fillna(0.0)


def _window_sum(grid: gpd.GeoDataFrame, values: pd.Series, radius_cells: int) -> pd.Series:
    """Sum of values in the (2r+1)x(2r+1) block of cells around each cell."""
    arr = np.zeros((grid["row"].max() + 1, grid["col"].max() + 1))
    arr[grid["row"], grid["col"]] = values.to_numpy()
    padded = np.pad(arr, radius_cells)
    k = 2 * radius_cells + 1
    csum = padded.cumsum(0).cumsum(1)
    csum = np.pad(csum, ((1, 0), (1, 0)))
    block = csum[k:, k:] - csum[:-k, k:] - csum[k:, :-k] + csum[:-k, :-k]
    return pd.Series(block[grid["row"], grid["col"]], index=grid.index)


def nearest_distance_m(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.Series:
    if points.empty:
        return pd.Series(np.inf, index=grid.index)
    centroids = gpd.GeoDataFrame(geometry=grid.geometry.centroid, crs=grid.crs)
    nearest = gpd.sjoin_nearest(centroids, points.to_crs(grid.crs)[["geometry"]], distance_col="d")
    return nearest.groupby(level=0)["d"].min().reindex(grid.index)


def build_features(grid: gpd.GeoDataFrame, layers: dict, roads: gpd.GeoDataFrame, graph=None) -> gpd.GeoDataFrame:
    g = grid.copy()
    for name, pts in layers.items():
        g[f"n_{name}"] = count_points(g, pts)

    cell_km2 = (config.CELL_SIZE_M / 1000) ** 2
    g["trip_generators_density"] = g[[f"n_{x}" for x in TRIP_GENERATORS]].sum(axis=1) / cell_km2
    g["affluence_proxy_density"] = g[[f"n_{x}" for x in AFFLUENCE_PROXIES]].sum(axis=1) / cell_km2
    g["transport_hub_density"] = g["n_transport_hub"] / cell_km2
    g["fuel_density"] = g["n_fuel"] / cell_km2
    g["parking_density"] = g["n_parking"] / cell_km2
    g["car_trade_density"] = g["n_car_trade"] / cell_km2
    g["major_road_km"] = road_km(g, roads)

    for year in (2020, 2025, 2030):
        g[f"pop_{year}"] = population.population_per_cell(g, year)
    g["pop_density_2025"] = g["pop_2025"] / cell_km2
    # Absolute rather than percentage growth, so near-empty cells with a few new houses don't dominate.
    g["pop_growth_2020_2025"] = (g["pop_2025"] - g["pop_2020"]) / cell_km2
    g["pop_growth_2025_2030"] = (g["pop_2030"] - g["pop_2025"]) / cell_km2
    g = g.join(buildings.building_features(g))
    g["home_charging_potential"] = car_economics.home_charging_potential(
        g["open_space_per_building_m2"], g["building_density"] >= buildings.MIN_URBAN_BUILDINGS_PER_KM2)

    # Centrality: half proximity to the CBD, half activity within ~2 km (5x5 cells).
    cbd = gpd.GeoSeries([Point(config.CBD_LATLON[1], config.CBD_LATLON[0])], crs="EPSG:4326").to_crs(g.crs).iloc[0]
    g["dist_cbd_km"] = g.geometry.centroid.distance(cbd) / 1000
    g["activity_2km"] = _window_sum(g, g["trip_generators_density"] + g["n_transport_hub"], radius_cells=2)
    g["centrality"] = 0.5 * (-g["dist_cbd_km"]).rank(pct=True) + 0.5 * g["activity_2km"].rank(pct=True)

    if graph is not None:
        c = g.geometry.centroid
        st = layers["ev_station"].to_crs(g.crs)
        g["dist_ev_station_m"] = graph.nearest_distance(np.column_stack([c.x, c.y]), np.column_stack([st.geometry.x, st.geometry.y]))
    else:
        g["dist_ev_station_m"] = nearest_distance_m(g, layers["ev_station"])
    g["active"] = (
        (g["trip_generators_density"] + g["major_road_km"]) >= config.MIN_ACTIVITY_FOR_SCORING
    ) | (g["pop_density_2025"] >= config.MIN_POP_FOR_SCORING)
    return g
