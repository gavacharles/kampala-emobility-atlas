"""Paper analyses: spatial statistics, siting robustness, access/economics by network size, equity.

Usage:  .venv/bin/python run_analysis.py   (after run_baseline.py)
Writes outputs/analysis/*.csv and outputs/analysis/summary.json.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

import config
from emobility import analysis, car_economics, economics, fetch, siting
from emobility.network import RoadGraph

OUT = Path(__file__).resolve().parent / "outputs" / "analysis"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = gpd.read_file(OUT.parent / "grid_scores.gpkg")
    a = g[g["active"] == 1].reset_index(drop=True)
    rows, cols = a["row"].to_numpy(), a["col"].to_numpy()
    summary = {"n_active_cells": len(a), "pop_2025_active": float(a["pop_2025"].sum())}

    # ---- spatial autocorrelation
    print("spatial statistics ...")
    for col in ["boda_suitability", "car_suitability", "housing_wealth_proxy", "pop_growth_2020_2025"]:
        x = a[col].fillna(a[col].min() if col == "housing_wealth_proxy" else 0)
        summary[f"moran_{col}"] = analysis.morans_i(x, rows, cols)
        z, p, cls = analysis.getis_ord_gi_star(x, rows, cols, radius=1)
        a[f"gi_{col}"], a[f"gi_class_{col}"] = z, cls
        summary[f"gi_{col}"] = {k: int((cls == k).sum()) for k in ("hot", "cold", "ns")}
    a[["cell_id"] + [c for c in a.columns if c.startswith("gi_")]].to_csv(OUT / "getis_ord.csv", index=False)

    # ---- siting robustness
    print("building road graph and cover matrices ...")
    graph = RoadGraph(config.METRIC_CRS)
    layers = {name: fetch.fetch_pois(name) for name in config.SITING_CANDIDATE_LAYERS}
    cand = siting.candidate_sites(layers, g.crs)
    cand_xy = np.column_stack([cand.geometry.x, cand.geometry.y])
    cells_xy = np.column_stack([a.geometry.centroid.x, a.geometry.centroid.y])
    w = (a["pop_2025"] * a["boda_suitability"] / 100).to_numpy()

    curves, covers = {}, {}
    for radius in (1500, 2500, 3500):
        covers[radius] = graph.within(cand_xy, cells_xy, radius)
        idx, cum = analysis.greedy_order(covers[radius], w, config.SITING_MAX_SITES)
        curves[f"greedy_{radius}m"] = cum
    cover = covers[config.SITING_COVER_ROAD_M]
    base_idx, base_cum = analysis.greedy_order(cover, w, config.SITING_MAX_SITES)

    fuel = (cand["site_type"] == "fuel").to_numpy()
    _, fuel_cum = analysis.greedy_order(cover[fuel], w, config.SITING_MAX_SITES)
    curves["greedy_fuel_only_2500m"] = fuel_cum
    curve_df = pd.DataFrame({k: pd.Series(v) for k, v in curves.items()})
    curve_df.insert(0, "n_sites", np.arange(1, len(curve_df) + 1))
    curve_df.to_csv(OUT / "coverage_curves.csv", index=False)
    rnd = analysis.random_baseline(cover, w, [5, 10, 20, 30, 45, 60])
    rnd.to_csv(OUT / "coverage_random_baseline.csv", index=False)
    summary["coverage"] = {
        f"n{n}": {"greedy": float(base_cum[n - 1]), "fuel_only": float(fuel_cum[n - 1]),
                  "random_mean": float(rnd.loc[rnd.n_sites == n, "mean"].iloc[0])}
        for n in (10, 30, 60)
    }
    print("exact MCLP optimum ...")
    for n in (10, 30, 60):
        opt, _, gap = analysis.exact_mclp(cover, w, n)
        summary["coverage"][f"n{n}"].update({"exact_optimum": float(opt), "solver_gap": float(gap),
                                            "greedy_gap_pp": float(100 * (opt - base_cum[n - 1]))})
    summary["coverage_by_radius_n30"] = {r: float(curves[f"greedy_{r}m"][29]) for r in (1500, 2500, 3500)}

    print("weight-robust siting ...")
    freq, jacc, covs, _ = analysis.weight_robust_sites(a, cover, n_sites=30, draws=100)
    cand_out = cand.assign(selection_frequency=freq, in_base_top30=np.isin(np.arange(len(cand)), base_idx[:30]))
    ll = cand_out.to_crs(4326)
    cand_out.drop(columns="geometry").assign(lat=ll.geometry.y.round(5), lon=ll.geometry.x.round(5)).to_csv(
        OUT / "candidate_selection_frequency.csv", index=False)
    summary["weight_robust_siting"] = {
        "jaccard_mean": float(jacc.mean()), "jaccard_p5": float(np.percentile(jacc, 5)),
        "coverage_loss_mean_pp": float(100 * (base_cum[29] - covs.mean())),
        "sites_selected_ge80pct": int((freq >= 0.8).sum()), "base_sites_selected_ge80pct": int((freq[base_idx[:30]] >= 0.8).sum()),
    }

    # ---- access, economics and equity by network size
    print("access and equity by network size ...")
    sites_xy = cand_xy[base_idx]
    groups = {"wealth": analysis.wealth_quintiles(a["housing_wealth_proxy"]).to_numpy(),
              "ring": analysis.rings(a["dist_cbd_km"]).to_numpy()}
    acc = analysis.access_by_network_size(graph, cells_xy, sites_xy, a["pop_2025"].to_numpy(),
                                          [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50, 60], groups)
    acc.to_csv(OUT / "access_by_network_size.csv", index=False)
    scen = analysis.economics_scenarios(graph, cells_xy, sites_xy, a["pop_2025"].to_numpy())
    scen.to_csv(OUT / "economics_scenarios.csv", index=False)

    d30 = graph.nearest_distance(cells_xy, sites_xy[:30])
    covered30 = (d30 <= config.SITING_COVER_ROAD_M).astype(float)
    built = a["housing_wealth_proxy"].notna()
    summary["concentration_index_coverage_n30_by_wealth"] = float(analysis.concentration_index(
        covered30[built], a.loc[built, "housing_wealth_proxy"], a.loc[built, "pop_2025"]))
    summary["concentration_index_car_suitability_by_wealth"] = float(analysis.concentration_index(
        a.loc[built, "car_suitability"], a.loc[built, "housing_wealth_proxy"], a.loc[built, "pop_2025"]))
    summary["economics_base"] = {
        "daily_saving_ugx": float(economics.daily_saving(economics.BASE)),
        "break_even_petrol_price": economics.break_even_petrol_price(economics.BASE),
        "break_even_detour_km": economics.break_even_detour_m(economics.BASE) / 1000,
    }
    mc = economics.monte_carlo()
    summary["economics_mc"] = {"p_positive": float((mc.saving > 0).mean()), "q05": float(mc.saving.quantile(.05)),
                               "median": float(mc.saving.median()), "q95": float(mc.saving.quantile(.95))}
    # ---- e-car charging network: the same tests
    print("e-car charging analyses ...")
    car_layers = {name: fetch.fetch_pois(name) for name in config.CAR_SITING_CANDIDATE_LAYERS}
    ccand = siting.candidate_sites(car_layers, g.crs, config.CAR_SITING_CANDIDATE_LAYERS)
    ccand_xy = np.column_stack([ccand.geometry.x, ccand.geometry.y])
    cw = (a["pop_2025"] * a["car_suitability"] / 100).to_numpy()
    ccurves, ccovers = {}, {}
    for radius in (3000, 5000, 8000):
        ccovers[radius] = graph.within(ccand_xy, cells_xy, radius)
        _, ccurves[f"greedy_{radius}m"] = analysis.greedy_order(ccovers[radius], cw, config.CAR_SITING_MAX_SITES)
    ccover = ccovers[config.CAR_SITING_COVER_ROAD_M]
    cbase_idx, cbase_cum = analysis.greedy_order(ccover, cw, config.CAR_SITING_MAX_SITES)
    cdf = pd.DataFrame({k: pd.Series(v) for k, v in ccurves.items()})
    cdf.insert(0, "n_sites", np.arange(1, len(cdf) + 1))
    cdf.to_csv(OUT / "car_coverage_curves.csv", index=False)
    crnd = analysis.random_baseline(ccover, cw, [1, 3, 5, 10, 20, 30])
    crnd.to_csv(OUT / "car_coverage_random_baseline.csv", index=False)
    summary["car_coverage"] = {}
    for n in (5, 10, 20):
        opt, _, gap = analysis.exact_mclp(ccover, cw, n)
        summary["car_coverage"][f"n{n}"] = {"greedy": float(cbase_cum[n - 1]), "exact_optimum": float(opt), "solver_gap": float(gap),
                                            "random_mean": float(crnd.loc[crnd.n_sites == n, "mean"].iloc[0]) if n in crnd.n_sites.values else None}
    summary["car_coverage_by_radius_n10"] = {r: float(ccurves[f"greedy_{r}m"][9]) for r in (3000, 5000, 8000)}
    csites_xy = ccand_xy[cbase_idx]
    cacc = analysis.access_by_network_size(graph, cells_xy, csites_xy, a["pop_2025"].to_numpy(), [1, 2, 3, 5, 7, 10, 15, 20, 30],
                                           groups, cover_m=config.CAR_SITING_COVER_ROAD_M)
    # add ride-hail and private e-car savings by network size
    rows = []
    hs = a["home_charging_potential"].to_numpy()
    for n in [1, 2, 3, 5, 7, 10, 15, 20, 30]:
        d = graph.nearest_distance(cells_xy, csites_xy[:n])
        ok = np.isfinite(d)
        dd = np.where(ok, d, 0)
        rows.append({"n_sites": n,
                     "ridehail_saving": float(np.average(car_economics.annual_saving(car_economics.BASE, "ridehail", None, dd)[ok], weights=a["pop_2025"][ok])),
                     "private_saving": float(np.average(car_economics.annual_saving(car_economics.BASE, "private", hs, dd)[ok], weights=a["pop_2025"][ok]))})
    cacc = cacc.merge(pd.DataFrame(rows), on="n_sites")
    cacc.to_csv(OUT / "car_access_by_network_size.csv", index=False)
    d10 = graph.nearest_distance(cells_xy, csites_xy[:10])
    ccov10 = (d10 <= config.CAR_SITING_COVER_ROAD_M).astype(float)
    summary["concentration_index_car_coverage_n10_by_wealth"] = float(analysis.concentration_index(
        ccov10[built], a.loc[built, "housing_wealth_proxy"], a.loc[built, "pop_2025"]))
    summary["home_charging"] = {
        "pop_weighted_mean": float(np.average(hs, weights=a["pop_2025"])),
        "by_wealth": {str(k): float(np.average(hs[groups["wealth"] == k], weights=a["pop_2025"][groups["wealth"] == k]))
                      for k in pd.unique(groups["wealth"])},
    }
    summary["car_economics"] = {}
    for persona in car_economics.PERSONAS:
        mc = car_economics.monte_carlo(persona)
        summary["car_economics"][persona] = {
            "annual_saving": float(car_economics.annual_saving(car_economics.BASE, persona)),
            "npv": float(car_economics.npv(car_economics.BASE, persona)),
            "payback_years": float(car_economics.payback_years(car_economics.BASE, persona)),
            "break_even_premium": float(car_economics.break_even_premium(car_economics.BASE, persona)),
            "p_npv_positive": float((mc["npv"] > 0).mean()),
            "npv_q05_q50_q95": mc["npv"].quantile([.05, .5, .95]).tolist(),
            "top_drivers": car_economics.tornado(persona)["parameter"].head(4).tolist(),
        }
    # home-charging access sensitivity for private owners
    summary["car_economics"]["private_saving_by_home_share"] = {
        str(h): float(car_economics.annual_saving(car_economics.BASE, "private", h)) for h in (0, 0.25, 0.5, 0.75, 1)}

    # Rank correlation of e-boda vs e-car suitability, and index robustness counts
    summary["spearman_boda_car"] = float(a["boda_suitability"].corr(a["car_suitability"], method="spearman"))
    summary["robust_top10_cells"] = {
        f"{m}_ge{t}": int((a[f"{m}_top10_robustness"] >= t).sum()) for m in ("boda", "car") for t in (0.5, 0.7, 0.9)}

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
