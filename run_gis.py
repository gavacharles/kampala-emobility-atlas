"""GIS, remote-sensing, terrain, infrastructure and operations outputs for the proposed networks.

Usage:  .venv/bin/python run_gis.py   (after run_baseline.py)
Writes outputs/gis/*.csv, outputs/gis/*.gpkg and outputs/gis/summary.json.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

import config
from emobility import infrastructure as inf
from emobility import operations as ops
from emobility import remote_sensing as rs
from emobility.network import RoadGraph

OUT = Path(__file__).resolve().parent / "outputs"
GIS = OUT / "gis"


def sites_gdf(csv):
    df = pd.read_csv(csv)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).to_crs(config.METRIC_CRS)


def main():
    GIS.mkdir(parents=True, exist_ok=True)
    g = gpd.read_file(OUT / "grid_scores.gpkg")
    summary = {}

    print("terrain and remote sensing ...")
    elev, dem_tr = rs.dem()
    terr = rs.terrain(elev)
    terr["elev"] = elev
    b = rs.sentinel2()
    idx = rs.spectral_indices(b)
    env = pd.DataFrame({
        "cell_id": g["cell_id"],
        "elev_mean_m": rs.zonal_mean(elev, dem_tr, g),
        "relief_m": rs.zonal_mean(elev, dem_tr, g, stat="range"),
        "slope_mean_deg": rs.zonal_mean(terr["slope"], dem_tr, g),
        "low_lying_share": rs.zonal_mean((terr["above_floor"] < 3).astype(float), dem_tr, g),
        "ndvi_mean": rs.zonal_mean(idx["ndvi"], b["transform"], g),
        "ndbi_mean": rs.zonal_mean(idx["ndbi"], b["transform"], g),
        "water_share": rs.zonal_mean((idx["mndwi"] > 0).astype(float), b["transform"], g),
    })
    env.to_csv(GIS / "grid_environment.csv", index=False)
    ge = g.merge(env, on="cell_id")
    a = ge[ge["active"] == 1]
    w = a["pop_2025"]
    summary["environment"] = {
        "scene": rs.S2_ITEM, "scene_datetime": b["props"].get("datetime"), "scene_cloud_pct": b["props"].get("eo:cloud_cover"),
        "elev_range_m": [float(np.nanmin(elev)), float(np.nanmax(elev))],
        "pop_share_in_steep_cells_gt8deg": float(w[a["slope_mean_deg"] > 8].sum() / w.sum()),
        "pop_share_low_lying_gt25pct": float(w[a["low_lying_share"] > 0.25].sum() / w.sum()),
        "corr_ndbi_boda": float(a["ndbi_mean"].corr(a["boda_suitability"], method="spearman")),
        "corr_ndvi_boda": float(a["ndvi_mean"].corr(a["boda_suitability"], method="spearman")),
        "corr_ndbi_car": float(a["ndbi_mean"].corr(a["car_suitability"], method="spearman")),
    }

    print("infrastructure and site screening ...")
    lines, points, wet = inf.power_lines(), inf.power_points(), inf.wetlands()
    swap = sites_gdf(OUT / "swap_sites_greenfield.csv")
    chg = sites_gdf(OUT / "charger_sites_greenfield.csv")
    rs_layers = {"ndvi": idx["ndvi"], "ndbi": idx["ndbi"]}
    swap_s = inf.screen_sites(swap, lines, points, wet, terr, dem_tr, rs_layers, b["transform"])
    chg_s = inf.screen_sites(chg, lines, points, wet, terr, dem_tr, rs_layers, b["transform"])
    summary["screen_swap"] = swap_s["site_screen"].value_counts().to_dict()
    summary["screen_charger"] = chg_s["site_screen"].value_counts().to_dict()
    summary["median_dist_mapped_power_line_m"] = float(swap_s["dist_power_line_m"].median())

    print("catchments and operational sizing ...")
    graph = RoadGraph(config.METRIC_CRS)
    act = ge[ge["active"] == 1].reset_index(drop=True)
    cxy = np.column_stack([act.geometry.centroid.x, act.geometry.centroid.y])
    si, sd = graph.nearest_assign(cxy, np.column_stack([swap.geometry.x, swap.geometry.y]))
    ci, cd = graph.nearest_assign(cxy, np.column_stack([chg.geometry.x, chg.geometry.y]))
    plan_swap = ops.swap_station_plan(act, si, sd, swap_s.drop(columns="geometry"), config.SITING_COVER_ROAD_M)
    plan_chg = ops.charger_plan(act, ci, cd, chg_s.drop(columns="geometry"), config.CAR_SITING_COVER_ROAD_M)
    for tag in ("10pct", "25pct", "50pct"):
        plan_swap[f"grid_class_{tag}"] = inf.grid_connection_class(plan_swap[f"grid_kw_{tag}"])
    for n in ops.RIDEHAIL_EV_SCENARIOS:
        plan_chg[f"grid_class_{n}cars"] = inf.grid_connection_class(plan_chg[f"grid_kw_{n}cars"])
    summary["grid_class_swap"] = {t: plan_swap[f"grid_class_{t}"].value_counts().to_dict() for t in ("10pct", "25pct", "50pct")}
    summary["grid_class_charger"] = {f"{n}cars": plan_chg[f"grid_class_{n}cars"].value_counts().to_dict() for n in ops.RIDEHAIL_EV_SCENARIOS}
    plan_swap.round(3).to_csv(GIS / "swap_station_plan.csv", index=False)
    plan_chg.round(3).to_csv(GIS / "charger_station_plan.csv", index=False)
    act[["cell_id"]].assign(swap_site=si, swap_dist_m=sd.round(0), charger_site=ci, charger_dist_m=cd.round(0)).to_csv(
        GIS / "catchments.csv", index=False)
    summary["ops_swap"] = {
        f"{s}": {"swaps_day_total": float(plan_swap[f"swaps_day_{s}"].sum()), "cabinets_total": float(plan_swap[f"cabinets_{s}"].sum()),
                 "grid_mw_total": float(plan_swap[f"grid_kw_{s}"].sum() / 1000), "max_site_swaps": float(plan_swap[f"swaps_day_{s}"].max())}
        for s in ("10pct", "25pct", "50pct")}
    summary["ops_charger"] = {
        f"{n}cars": {"dc_ports_total": float(plan_chg[f"dc_ports_{n}cars"].sum()), "grid_mw_total": float(plan_chg[f"grid_kw_{n}cars"].sum() / 1000)}
        for n in ops.RIDEHAIL_EV_SCENARIOS}

    # A GeoPackage with every GIS layer, for QGIS/ArcGIS users
    gpkg = GIS / "kampala_emobility_gis.gpkg"
    ge.to_file(gpkg, layer="grid_scores_environment", driver="GPKG")
    gpd.GeoDataFrame(plan_swap, geometry=swap.geometry.values, crs=swap.crs).to_file(gpkg, layer="proposed_swap_sites", driver="GPKG")
    gpd.GeoDataFrame(plan_chg, geometry=chg.geometry.values, crs=chg.crs).to_file(gpkg, layer="proposed_charger_sites", driver="GPKG")
    lines.to_file(gpkg, layer="power_lines", driver="GPKG")
    points.to_file(gpkg, layer="power_points", driver="GPKG")
    wet.to_file(gpkg, layer="wetlands_water", driver="GPKG")

    (GIS / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
