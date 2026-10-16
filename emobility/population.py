"""Aggregate WorldPop 100 m population rasters to the analysis grid.

Source: WorldPop Global2 R2025A, constrained, 100 m (https://hub.worldpop.org). 2020 and 2025
are modelled estimates; 2030 is a projection. None of them are census counts.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

import config

WORLDPOP_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "worldpop"
WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/{year}/UGA/v1/100m/"
    "constrained/uga_pop_{year}_CN_100m_R2025A_v1.tif"
)


def raster_path(year: int) -> Path:
    return WORLDPOP_DIR / f"uga_pop_{year}.tif"


def population_per_cell(grid: gpd.GeoDataFrame, year: int) -> pd.Series:
    """Sum the population of every 100 m pixel whose centre falls in each grid cell."""
    path = raster_path(year)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; download it from {WORLDPOP_URL.format(year=year)}")

    s, w, n, e = config.BBOX
    with rasterio.open(path) as src:
        window = from_bounds(w, s, e, n, src.transform)
        data = src.read(1, window=window, masked=True).filled(0).astype("float64")
        transform = src.window_transform(window)

    rows, cols = np.nonzero(data > 0)
    lon, lat = rasterio.transform.xy(transform, rows, cols, offset="center")
    x, y = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True).transform(np.asarray(lon), np.asarray(lat))

    x0, y0 = grid.total_bounds[:2]
    gr = ((np.asarray(y) - y0) // config.CELL_SIZE_M).astype(int)
    gc = ((np.asarray(x) - x0) // config.CELL_SIZE_M).astype(int)
    shape = (grid["row"].max() + 1, grid["col"].max() + 1)
    inside = (gr >= 0) & (gr < shape[0]) & (gc >= 0) & (gc < shape[1])

    totals = np.zeros(shape)
    np.add.at(totals, (gr[inside], gc[inside]), data[rows[inside], cols[inside]])
    return pd.Series(totals[grid["row"], grid["col"]], index=grid.index)
