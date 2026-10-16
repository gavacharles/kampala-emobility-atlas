"""GIS, satellite, remote-sensing, terrain, infrastructure and operations maps (PNG, 300 dpi).

Usage:  .venv/bin/python make_gis_maps.py   (after run_gis.py)
Writes figures/gis*.png.
"""

import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

import config  # noqa: E402
from emobility import fetch, infrastructure as inf, remote_sensing as rs  # noqa: E402
from make_figures import BLUE, CAT, CM_BLUE, CM_ORANGE, INK, INK2, INK3, PLACES, cbar, grid_array, save, scalebar  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
GIS = OUT / "gis"
CM_NDVI = LinearSegmentedColormap.from_list("ndvi", ["#8c6d46", "#d9c99a", "#f2f0d8", "#9ccf86", "#3d8c40", "#14532d"])
CM_ELEV = LinearSegmentedColormap.from_list("elev", ["#2f6f73", "#7fb39a", "#e3dca5", "#c99a5b", "#8a5a34", "#f2efe9"])
CM_SLOPE = LinearSegmentedColormap.from_list("slope", ["#fff7ec", "#fdd49e", "#fc8d59", "#d7301f", "#7f0000"])
GRID_CLASS_COLORS = {"LV supply": CAT[2], "dedicated transformer": CAT[0], "MV connection": CAT[1]}


def extent(transform, shape):
    return (transform.c, transform.c + transform.a * shape[1], transform.f + transform.e * shape[0], transform.f)


def frame(ax, g, zoom=None):
    if zoom:
        cx, cy, half = zoom
        ax.set_xlim(cx - half, cx + half), ax.set_ylim(cy - half, cy + half)
    else:
        x0, y0, x1, y1 = g.total_bounds
        ax.set_xlim(x0 + 2000, x1 - 2000), ax.set_ylim(y0 + 1000, y1 - 1000)
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    km = 2 if zoom else 10
    scalebar(ax, x0 + (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05, km)
    ax.annotate("N", xy=(0.96, 0.95), xytext=(0.96, 0.87), xycoords="axes fraction", ha="center", fontsize=9, fontweight="bold",
                color=INK, arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2))


def labels(ax, g, color=INK, only=None):
    pts = gpd.GeoSeries(gpd.points_from_xy([v[1] for v in PLACES.values()], [v[0] for v in PLACES.values()]), crs=4326).to_crs(g.crs)
    xl, yl = ax.get_xlim(), ax.get_ylim()
    for name, p in zip(PLACES, pts):
        if (only and name not in only) or not (xl[0] < p.x < xl[1] and yl[0] < p.y < yl[1]):
            continue
        ax.annotate(name, (p.x, p.y), fontsize=7, color=color, ha="center", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))


def plot_sites(ax, swap, chg, size=22, with_legend=True):
    ax.scatter(swap.geometry.x, swap.geometry.y, s=size, marker="o", c=CAT[0], edgecolor="white", linewidth=0.7, zorder=10)
    ax.scatter(chg.geometry.x, chg.geometry.y, s=size + 6, marker="s", c=CAT[1], edgecolor="white", linewidth=0.7, zorder=10)
    if with_legend:
        ax.legend(handles=[
            Line2D([], [], marker="o", ls="", color=CAT[0], markeredgecolor="white", label="Proposed e-boda swap site (60)"),
            Line2D([], [], marker="s", ls="", color=CAT[1], markeredgecolor="white", label="Proposed e-car DC charger site (30)"),
        ], loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)


def sites(csv):
    df = pd.read_csv(csv)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(config.METRIC_CRS)


def main():
    g = gpd.read_file(OUT / "grid_scores.gpkg")
    env = pd.read_csv(GIS / "grid_environment.csv")
    ge = g.merge(env, on="cell_id")
    swap = sites(OUT / "swap_sites_greenfield.csv")
    chg = sites(OUT / "charger_sites_greenfield.csv")
    plan_swap = pd.read_csv(GIS / "swap_station_plan.csv")
    plan_chg = pd.read_csv(GIS / "charger_station_plan.csv")
    roads_all = fetch.fetch_major_roads().to_crs(g.crs)
    roads = roads_all[roads_all["highway"].isin(["motorway", "trunk", "primary", "secondary"])]
    b = rs.sentinel2()
    idx = rs.spectral_indices(b)
    s2ext = extent(b["transform"], b["red"].shape)
    rgb = rs.true_colour(b)
    elev, dem_tr = rs.dem()
    terr = rs.terrain(elev)
    dext = extent(dem_tr, elev.shape)
    lines, points, wet = inf.power_lines().to_crs(g.crs), inf.power_points().to_crs(g.crs), inf.wetlands().to_crs(g.crs)
    cbd = gpd.GeoSeries(gpd.points_from_xy([PLACES["CBD"][1]], [PLACES["CBD"][0]]), crs=4326).to_crs(g.crs).iloc[0]
    zoom = (cbd.x + 2500, cbd.y + 2500, 9000)
    date = b["props"]["datetime"][:10]

    # gis01: satellite overview with both proposed networks
    fig, ax = plt.subplots(figsize=(7.4, 7.4))
    ax.imshow(rgb, extent=s2ext, zorder=0)
    roads.plot(ax=ax, color="white", lw=0.35, alpha=0.6, zorder=3)
    plot_sites(ax, swap, chg)
    frame(ax, g)
    labels(ax, g)
    ax.set_title(f"Sentinel-2 true colour ({date}) with the proposed e-boda swap and e-car charging networks", loc="left", fontsize=9)
    save(fig, "gis01_satellite_proposed_networks")

    # gis02: central Kampala satellite zoom with ranked sites
    fig, ax = plt.subplots(figsize=(7.4, 7.4))
    ax.imshow(rgb, extent=s2ext, zorder=0)
    roads.plot(ax=ax, color="white", lw=0.6, alpha=0.7, zorder=3)
    plot_sites(ax, swap, chg, size=46)
    frame(ax, g, zoom)
    for d, prefix, color in ((swap, "S", CAT[0]), (chg, "C", CAT[1])):
        for _, r in d.iterrows():
            if abs(r.geometry.x - zoom[0]) < zoom[2] and abs(r.geometry.y - zoom[1]) < zoom[2]:
                ax.annotate(f"{prefix}{r['rank']}", (r.geometry.x, r.geometry.y), xytext=(5, 4), textcoords="offset points",
                            fontsize=7, fontweight="bold", color="white", zorder=11,
                            bbox=dict(boxstyle="round,pad=0.12", fc=color, ec="none", alpha=0.9))
    labels(ax, g)
    ax.set_title("Central Kampala: proposed sites by build order (S = swap, C = charger)", loc="left")
    save(fig, "gis02_satellite_central_kampala")

    # gis03: remote-sensing indices
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, key, cmap, vmin, vmax, title in (
        (axes[0], "ndvi", CM_NDVI, -0.1, 0.85, "NDVI (vegetation)"),
        (axes[1], "ndbi", LinearSegmentedColormap.from_list("b", ["#f7fbff"] + BLUE[2:]), -0.35, 0.25, "NDBI (built-up)"),
        (axes[2], "mndwi", LinearSegmentedColormap.from_list("w", ["#f3f1ea", "#9ec5f4", "#0d366b"]), -0.5, 0.6, "MNDWI (open water)"),
    ):
        im = ax.imshow(idx[key], extent=s2ext, cmap=cmap, vmin=vmin, vmax=vmax, zorder=0)
        roads.plot(ax=ax, color=INK, lw=0.25, alpha=0.4, zorder=3)
        frame(ax, g)
        ax.set_title(f"{title}, Sentinel-2 {date}", loc="left")
        cbar(fig, ax, im, key.upper())
    labels(axes[0], g)
    save(fig, "gis03_remote_sensing_indices")

    # gis04: terrain: hillshaded elevation + slope
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].imshow(terr["hillshade"], extent=dext, cmap="gray", zorder=0)
    im = axes[0].imshow(elev, extent=dext, cmap=CM_ELEV, alpha=0.6, zorder=1)
    plot_sites(axes[0], swap, chg, size=14)
    frame(axes[0], g)
    labels(axes[0], g)
    cbar(fig, axes[0], im, "Elevation (m a.s.l., Copernicus GLO-30)")
    axes[0].set_title("Terrain: hillshaded elevation", loc="left")
    im = axes[1].imshow(terr["slope"], extent=dext, cmap=CM_SLOPE, vmin=0, vmax=20, zorder=0)
    roads.plot(ax=axes[1], color=INK, lw=0.25, alpha=0.5, zorder=3)
    steep = plan_swap["site_screen"].str.startswith("steep")
    sw = swap.reset_index(drop=True)
    axes[1].scatter(sw.geometry.x[~steep], sw.geometry.y[~steep], s=14, c=CAT[0], edgecolor="white", lw=0.6, zorder=10, label="swap site, slope ≤ 8°")
    axes[1].scatter(sw.geometry.x[steep], sw.geometry.y[steep], s=40, marker="^", c=INK, edgecolor="white", lw=0.6, zorder=11, label="swap site on slope > 8°")
    axes[1].legend(loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none")
    frame(axes[1], g)
    cbar(fig, axes[1], im, "Slope (degrees)")
    axes[1].set_title("Surface slope and steep proposed sites", loc="left")
    save(fig, "gis04_terrain_elevation_slope")

    # gis05: flood screen: low-lying valley floors + mapped wetlands
    fig, ax = plt.subplots(figsize=(7.4, 7.4))
    ax.imshow(terr["hillshade"], extent=dext, cmap="gray", alpha=0.55, zorder=0)
    low = np.where(terr["above_floor"] < 3, 1.0, np.nan)
    ax.imshow(low, extent=dext, cmap=LinearSegmentedColormap.from_list("l", ["#3987e5", "#3987e5"]), alpha=0.55, zorder=1)
    wet[wet["natural"] == "wetland"].plot(ax=ax, facecolor="#1baf7a", edgecolor="none", alpha=0.45, zorder=2)
    roads.plot(ax=ax, color=INK, lw=0.3, alpha=0.5, zorder=3)
    plot_sites(ax, swap, chg, size=16, with_legend=False)
    ax.legend(handles=[
        Line2D([], [], marker="s", ls="", color="#3987e5", alpha=0.6, label="< 3 m above local valley floor (DEM)"),
        Line2D([], [], marker="s", ls="", color="#1baf7a", alpha=0.6, label="Mapped wetland (OSM)"),
        Line2D([], [], marker="o", ls="", color=CAT[0], label="Proposed swap site"),
        Line2D([], [], marker="s", ls="", color=CAT[1], label="Proposed charger site"),
    ], loc="lower right", fontsize=7, frameon=True, facecolor="white", edgecolor="none")
    frame(ax, g, (zoom[0], zoom[1], 14000))
    labels(ax, g)
    ax.set_title("Flood and wetland screen: no proposed site falls on a valley floor or wetland", loc="left", fontsize=9)
    save(fig, "gis05_flood_wetland_screen")

    # gis06: electricity infrastructure + load class at 25% adoption
    fig, ax = plt.subplots(figsize=(7.4, 7.4))
    ax.imshow(terr["hillshade"], extent=dext, cmap="gray", alpha=0.35, zorder=0)
    lines[lines["power"] == "line"].plot(ax=ax, color=INK, lw=1.2, zorder=3)
    lines[lines["power"] != "line"].plot(ax=ax, color=INK3, lw=0.4, zorder=2)
    pp = points
    ax.scatter(pp[pp.power == "substation"].geometry.x, pp[pp.power == "substation"].geometry.y, marker="P", s=40, c=INK, zorder=6)
    ax.scatter(pp[pp.power == "transformer"].geometry.x, pp[pp.power == "transformer"].geometry.y, marker=".", s=8, c=INK2, zorder=5)
    for cls, color in GRID_CLASS_COLORS.items():
        m = plan_swap["grid_class_25pct"] == cls
        ax.scatter(swap.geometry.x.to_numpy()[m], swap.geometry.y.to_numpy()[m], s=8 + plan_swap.loc[m, "grid_kw_25pct"] / 6,
                   c=color, edgecolor="white", lw=0.6, zorder=10, alpha=0.9)
    ax.legend(handles=[
        Line2D([], [], color=INK, lw=1.2, label="Transmission line (OSM)"),
        Line2D([], [], color=INK3, lw=0.6, label="Distribution line (OSM, partial)"),
        Line2D([], [], marker="P", ls="", color=INK, label="Substation"),
        *[Line2D([], [], marker="o", ls="", color=c, label=f"Swap site: {k} (25% adoption)") for k, c in GRID_CLASS_COLORS.items()],
    ], loc="lower right", fontsize=6.8, frameon=True, facecolor="white", edgecolor="none")
    frame(ax, g)
    labels(ax, g)
    ax.set_title("Grid infrastructure and the connection each swap site would need (size = kW)", loc="left", fontsize=9)
    save(fig, "gis06_power_infrastructure")

    # gis07 / gis08: operational catchments for both networks
    cat_ = pd.read_csv(GIS / "catchments.csv")
    gc = g.merge(cat_, on="cell_id", how="left")
    for name, col, plan, pts, size_col, title, vcol, vlabel in (
        ("gis07_swap_catchments", "swap_site", plan_swap, swap, "swaps_day_25pct",
         "E-boda swap catchments by road (size = swaps/day at 25% adoption)", "pop_2025", "Residents per km²"),
        ("gis08_charger_catchments", "charger_site", plan_chg, chg, "dc_ports_2000cars",
         "E-car charger catchments by road (size = DC ports for 2,000 e-ride-hail cars)", "car_suitability", "E-car suitability"),
    ):
        fig, ax = plt.subplots(figsize=(7.4, 7.4))
        x0, y0, x1, y1 = g.total_bounds
        im = ax.imshow(grid_array(gc, gc[vcol]), origin="lower", extent=(x0, x1, y0, y1),
                       cmap=CM_ORANGE if vcol == "pop_2025" else CM_BLUE, vmax=np.nanpercentile(gc[vcol][gc.active == 1], 98), zorder=0)
        arr = grid_array(gc, gc[col].fillna(-1))
        edge_h = (arr[:, 1:] != arr[:, :-1]) & np.isfinite(arr[:, 1:]) & np.isfinite(arr[:, :-1])
        edge_v = (arr[1:, :] != arr[:-1, :]) & np.isfinite(arr[1:, :]) & np.isfinite(arr[:-1, :])
        r, c = np.nonzero(edge_h)
        for rr, cc in zip(r, c):
            xx = x0 + (cc + 1) * config.CELL_SIZE_M
            ax.plot([xx, xx], [y0 + rr * config.CELL_SIZE_M, y0 + (rr + 1) * config.CELL_SIZE_M], color=INK, lw=0.6, zorder=3)
        r, c = np.nonzero(edge_v)
        for rr, cc in zip(r, c):
            yy = y0 + (rr + 1) * config.CELL_SIZE_M
            ax.plot([x0 + cc * config.CELL_SIZE_M, x0 + (cc + 1) * config.CELL_SIZE_M], [yy, yy], color=INK, lw=0.6, zorder=3)
        sz = plan[size_col].fillna(0).to_numpy()
        ax.scatter(pts.geometry.x, pts.geometry.y, s=10 + 120 * sz / sz.max(), c=CAT[0] if "swap" in name else CAT[1],
                   edgecolor="white", lw=0.7, zorder=10)
        frame(ax, g)
        labels(ax, g)
        cbar(fig, ax, im, vlabel)
        ax.set_title(title, loc="left", fontsize=9)
        save(fig, name)

    # gis09: road network infrastructure by class
    fig, ax = plt.subplots(figsize=(7.4, 7.4))
    order = [("tertiary", 0.35, INK3), ("secondary", 0.6, CAT[0]), ("primary", 0.9, CAT[0]), ("trunk", 1.3, INK), ("motorway", 1.6, INK)]
    for hw, lw, color in order:
        roads_all[roads_all["highway"] == hw].plot(ax=ax, color=color, lw=lw, zorder=3)
    ax.legend(handles=[Line2D([], [], color=c, lw=l * 1.5, label=h) for h, l, c in order[::-1]], loc="lower right", fontsize=7,
              frameon=True, facecolor="white", edgecolor="none")
    frame(ax, g)
    labels(ax, g)
    ax.set_title("Major road network (OSM); routing uses all 15,868 km incl. residential and tracks", loc="left", fontsize=9)
    save(fig, "gis09_road_network")

    # gis10: land surface context: built-up vs e-boda suitability (remote-sensing validation)
    a = ge[ge.active == 1]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    axes[0].scatter(a["ndbi_mean"], a["boda_suitability"], s=5, c=CAT[0], alpha=0.5, lw=0)
    axes[0].set(xlabel="Mean NDBI of cell (Sentinel-2, independent of the index)", ylabel="E-boda suitability index")
    axes[1].scatter(a["ndvi_mean"], a["car_suitability"], s=5, c=CAT[1], alpha=0.5, lw=0)
    axes[1].set(xlabel="Mean NDVI of cell", ylabel="E-car suitability index")
    s = json.loads((GIS / "summary.json").read_text())["environment"]
    axes[0].set_title(f"Built-up surface vs e-boda index (Spearman ρ = {s['corr_ndbi_boda']:.2f})", loc="left")
    axes[1].set_title(f"Vegetation vs e-car index (ρ_NDBI,car = {s['corr_ndbi_car']:.2f})", loc="left")
    for x in axes:
        x.grid(color="#eceeec")
    save(fig, "gis10_remote_sensing_validation")


if __name__ == "__main__":
    main()
