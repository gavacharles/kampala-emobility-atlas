"""Satellite imagery (Sentinel-2 L2A) and terrain (Copernicus GLO-30 DEM) for Greater Kampala.

Both are read as windows from public cloud-optimised GeoTIFFs on AWS and cached locally, already
reprojected to the study's metric CRS (UTM 36N):
  Sentinel-2 L2A, scene S2A_36NVF_20260629 (1.1% cloud), via the Element 84 Earth Search STAC API.
  Copernicus DEM GLO-30 (2021 release), tile N00 E032 (ESA / Airbus, free licence).

Derived layers: true colour, NDVI, NDBI, MNDWI (water), elevation, slope, hillshade and
height above the local valley floor (HAND-like flood screen).
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from scipy import ndimage

import config

RS_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "remote_sensing"
S2_ITEM = "S2A_36NVF_20260629_0_L2A"
STAC = "https://earth-search.aws.element84.com/v1"
DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N00_00_E032_00_DEM/"
           "Copernicus_DSM_COG_10_N00_00_E032_00_DEM.tif")
S2_RES = 20  # m; 10 m bands are averaged to 20 m to keep the study-area mosaic manageable
DEM_RES = 30
S2_BANDS = {"blue": "blue", "green": "green", "red": "red", "nir": "nir", "swir16": "swir16", "scl": "scl"}
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES", GDAL_HTTP_MULTIRANGE="YES")


def _target_grid(res):
    s, w, n, e = config.BBOX
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", config.METRIC_CRS, w, s, e, n)
    width, height = int((x1 - x0) // res), int((y1 - y0) // res)
    return from_origin(x0, y1, res, res), (height, width)


def _warp_to_grid(src_path, res, resampling, band=1):
    transform, shape = _target_grid(res)
    out = np.full(shape, np.nan, dtype="float32")
    with rasterio.Env(**ENV), rasterio.open(src_path) as src:
        reproject(
            source=rasterio.band(src, band), destination=out, src_transform=src.transform, src_crs=src.crs,
            dst_transform=transform, dst_crs=config.METRIC_CRS, resampling=resampling, src_nodata=src.nodata, dst_nodata=np.nan,
        )
    return out, transform


def _save(path, arr, transform):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32",
                       crs=config.METRIC_CRS, transform=transform, compress="deflate", nodata=np.nan) as dst:
        dst.write(arr.astype("float32"), 1)


def _load(path):
    with rasterio.open(path) as src:
        return src.read(1), src.transform


def _s2_assets():
    cache = RS_DIR / f"{S2_ITEM}.json"
    if not cache.exists():
        RS_DIR.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(["curl", "-s", f"{STAC}/collections/sentinel-2-l2a/items/{S2_ITEM}"], capture_output=True, text=True).stdout
        cache.write_text(out)
    item = json.loads(cache.read_text())
    return {k: item["assets"][v]["href"] for k, v in S2_BANDS.items()}, item["properties"]


def sentinel2():
    """Dict of 20 m reflectance arrays (0-1) on the study grid, plus transform and scene metadata."""
    assets, props = _s2_assets()
    bands = {}
    for name, href in assets.items():
        path = RS_DIR / f"s2_{name}.tif"
        if not path.exists():
            print(f"  reading Sentinel-2 {name} ...")
            arr, tr = _warp_to_grid("/vsicurl/" + href, S2_RES, Resampling.nearest if name == "scl" else Resampling.average)
            _save(path, arr, tr)
        bands[name], transform = _load(path)
    for k in ("blue", "green", "red", "nir", "swir16"):
        # The STAC metadata declares a -0.1 offset, but these COGs are already offset-corrected: applying it
        # pushes most land pixels below zero (red median DN 595 = 0.06 reflectance as delivered).
        bands[k] = np.clip(bands[k] / 10000.0, 0, 1)
    bands["transform"], bands["props"] = transform, props
    return bands


def spectral_indices(b):
    eps = 1e-6
    ndvi = (b["nir"] - b["red"]) / (b["nir"] + b["red"] + eps)
    ndbi = (b["swir16"] - b["nir"]) / (b["swir16"] + b["nir"] + eps)
    mndwi = (b["green"] - b["swir16"]) / (b["green"] + b["swir16"] + eps)
    cloud = np.isin(b["scl"], [3, 8, 9, 10])  # cloud shadow, medium/high cloud, cirrus
    for a in (ndvi, ndbi, mndwi):
        a[cloud] = np.nan
    return {"ndvi": ndvi, "ndbi": ndbi, "mndwi": mndwi, "cloud": cloud}


def true_colour(b, low=2, high=98, gamma=1.15):
    """Percentile-stretched RGB; percentiles are taken over land so the lake does not flatten contrast."""
    land = (b["nir"] > b["green"]) & np.isfinite(b["red"])
    out = []
    for k in ("red", "green", "blue"):
        lo, hi = np.nanpercentile(b[k][land], [low, high])
        out.append(np.clip((b[k] - lo) / (hi - lo), 0, 1))
    return np.dstack(out) ** (1 / gamma)


def dem():
    path = RS_DIR / "cop30_dem.tif"
    if not path.exists():
        print("  reading Copernicus DEM ...")
        arr, tr = _warp_to_grid("/vsicurl/" + DEM_URL, DEM_RES, Resampling.bilinear)
        _save(path, arr, tr)
    return _load(path)


def terrain(elev, res=DEM_RES):
    """Slope (degrees), hillshade (0-1) and height above the local valley floor (m)."""
    z = np.where(np.isfinite(elev), elev, np.nanmean(elev))
    dzdy, dzdx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    az, alt = np.radians(315), np.radians(45)
    aspect = np.arctan2(-dzdx, dzdy)
    shade = np.sin(alt) * np.cos(np.radians(slope)) + np.cos(alt) * np.sin(np.radians(slope)) * np.cos(az - aspect)
    # Height above the lowest point within ~1.5 km: a simple HAND-like proxy. Kampala's flood-prone
    # papyrus valleys (Nakivubo, Lubigi, Kinawataka, Nalukolongo) sit within a few metres of it.
    window = int(round(1500 / res)) * 2 + 1
    above_floor = z - ndimage.minimum_filter(z, size=window)
    return {"slope": slope, "hillshade": np.clip(shade, 0, 1), "above_floor": above_floor}


def sample(arr, transform, x, y):
    """Values of arr at metric coordinates (nearest pixel); NaN outside."""
    inv = ~transform
    col, row = inv * (np.asarray(x), np.asarray(y))
    row, col = np.floor(row).astype(int), np.floor(col).astype(int)
    ok = (row >= 0) & (row < arr.shape[0]) & (col >= 0) & (col < arr.shape[1])
    out = np.full(len(row), np.nan)
    out[ok] = arr[row[ok], col[ok]]
    return out


def zonal_mean(arr, transform, grid, stat="mean"):
    """Per-grid-cell statistic of a raster aligned to the study CRS (pixel centres binned into cells)."""
    rows_i, cols_i = np.indices(arr.shape)
    xs = transform.c + (cols_i + 0.5) * transform.a
    ys = transform.f + (rows_i + 0.5) * transform.e
    x0, y0 = grid.total_bounds[:2]
    gr = ((ys - y0) // config.CELL_SIZE_M).astype(int).ravel()
    gc = ((xs - x0) // config.CELL_SIZE_M).astype(int).ravel()
    v = arr.ravel().astype(float)
    shape = (grid["row"].max() + 1, grid["col"].max() + 1)
    ok = np.isfinite(v) & (gr >= 0) & (gr < shape[0]) & (gc >= 0) & (gc < shape[1])
    key = gr[ok] * shape[1] + gc[ok]
    if stat == "mean":
        s = np.bincount(key, v[ok], minlength=shape[0] * shape[1])
        n = np.bincount(key, minlength=shape[0] * shape[1])
        res = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    else:  # range (max - min)
        mx = np.full(shape[0] * shape[1], -np.inf)
        mn = np.full(shape[0] * shape[1], np.inf)
        np.maximum.at(mx, key, v[ok])
        np.minimum.at(mn, key, v[ok])
        res = np.where(np.isfinite(mx), mx - mn, np.nan)
    res = res.reshape(shape)
    return res[grid["row"], grid["col"]]
