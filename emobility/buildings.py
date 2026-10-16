"""Building-footprint features per grid cell, used as a household-wealth proxy for the e-car index.

Source: Microsoft Global ML Building Footprints (2026-02 release, ODbL), quadkey 122323332, which
covers the whole study area. Larger residential footprints are a widely used, if imperfect, proxy
for household wealth where income data are unavailable at neighbourhood scale.
"""

import gzip
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

import config

BUILDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "raw" / "buildings" / "ms_buildings_122323332.csv.gz"
CACHE = BUILDINGS_FILE.with_suffix("").with_suffix(".parquet")

# Footprints outside this range are mostly sheds/kiosks or commercial/industrial halls, not homes.
RESIDENTIAL_AREA_M2 = (20, 600)
LARGE_HOME_M2 = 150
# The proxy is only defined for built-up cells; in farmland "space per building" measures plot size, not wealth.
MIN_URBAN_BUILDINGS_PER_KM2 = 200
M_PER_DEG = 111_320


def _load_footprints() -> pd.DataFrame:
    """Centroid and area of every footprint in the study bbox (cached as parquet after first parse)."""
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    s, w, n, e = config.BBOX
    lons, lats, areas = [], [], []
    with gzip.open(BUILDINGS_FILE, "rt") as f:
        for line in f:
            ring = json.loads(line)["geometry"]["coordinates"][0]
            xs = np.fromiter((c[0] for c in ring), float)
            ys = np.fromiter((c[1] for c in ring), float)
            cx, cy = xs.mean(), ys.mean()
            if not (w <= cx <= e and s <= cy <= n):
                continue
            # Shoelace area on a local equirectangular projection (exact enough at 1-2 m scale).
            kx = M_PER_DEG * np.cos(np.radians(cy))
            areas.append(0.5 * abs(np.dot(xs * kx, np.roll(ys, 1) * M_PER_DEG) - np.dot(ys * M_PER_DEG, np.roll(xs, 1) * kx)))
            lons.append(cx)
            lats.append(cy)
    df = pd.DataFrame({"lon": lons, "lat": lats, "area_m2": areas})
    df.to_parquet(CACHE)
    return df


def building_features(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    df = _load_footprints()
    x, y = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True).transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    x0, y0 = grid.total_bounds[:2]
    df["row"] = ((y - y0) // config.CELL_SIZE_M).astype(int)
    df["col"] = ((x - x0) // config.CELL_SIZE_M).astype(int)

    cell_km2 = (config.CELL_SIZE_M / 1000) ** 2
    agg = df.groupby(["row", "col"])["area_m2"].agg(n_buildings="size", built_m2="sum")
    homes = df[df["area_m2"].between(*RESIDENTIAL_AREA_M2)]
    agg = agg.join(
        homes.groupby(["row", "col"])["area_m2"].agg(
            median_home_m2="median",
            large_home_share=lambda a: (a >= LARGE_HOME_M2).mean(),
            n_homes="size",
        )
    )
    out = grid[["row", "col"]].merge(agg.reset_index(), on=["row", "col"], how="left").set_index(grid.index)
    out["building_density"] = out["n_buildings"].fillna(0) / cell_km2
    out["built_up_share"] = out["built_m2"].fillna(0) / (cell_km2 * 1e6)
    out["open_space_per_building_m2"] = cell_km2 * 1e6 * (1 - out["built_up_share"]) / out["n_buildings"]

    # Wealth proxy: open space around buildings (gardens, compounds) weighted above home size, because
    # the footprint model merges adjoining roofs in dense informal areas into large "homes"; size alone
    # rated Kisenyi like Kololo. Checked against known neighbourhoods: Kololo, Bugolobi, Naguru, Muyenga
    # rank high; Bwaise, Kawempe, Namuwongo, Kisaasi low. Cells mixing an estate with a hospital or
    # airstrip (Katanga/Mulago, Kamwokya/Kololo airstrip) are over-rated at 1 km resolution.
    urban = (out["building_density"] >= MIN_URBAN_BUILDINGS_PER_KM2) & (out["n_homes"].fillna(0) >= 30)
    out.loc[~urban, ["median_home_m2", "large_home_share", "open_space_per_building_m2"]] = np.nan
    out["housing_wealth_proxy"] = 0.6 * out["open_space_per_building_m2"].rank(pct=True) + 0.4 * out["median_home_m2"].rank(pct=True)
    return out[[
        "n_buildings", "building_density", "built_up_share", "median_home_m2", "large_home_share",
        "open_space_per_building_m2", "housing_wealth_proxy",
    ]]
