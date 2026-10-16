"""Phase 1 baseline: public-data EV suitability, swap-site and rider-economics analysis for Greater Kampala.

Usage:  .venv/bin/python run_baseline.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from emobility import car_economics, economics, features, fetch, index, mapping, sensitivity, siting
from emobility.network import RoadGraph
import config

OUT = Path(__file__).resolve().parent / "outputs"


def main():
    OUT.mkdir(exist_ok=True)

    layers = {}
    for name in config.POI_LAYERS:
        print(f"fetching {name} ...")
        layers[name] = fetch.fetch_pois(name)
    manual = features.load_manual_stations()
    if not manual.empty:
        layers["ev_station"] = pd.concat([layers["ev_station"], manual], ignore_index=True)
    print("fetching major roads ...")
    roads = fetch.fetch_major_roads()
    print("building road network ...")
    graph = RoadGraph(config.METRIC_CRS)
    print(f"road graph: {len(graph.xy):,} nodes, {graph.n_edges:,} edges, {graph.total_km:,.0f} km")

    inventory = pd.DataFrame({"layer": list(layers), "features": [len(v) for v in layers.values()]})
    inventory.loc[len(inventory)] = ["major_road_segments", len(roads)]
    inventory.loc[len(inventory)] = ["road_network_km", round(graph.total_km)]
    inventory.to_csv(OUT / "data_inventory.csv", index=False)
    print(inventory.to_string(index=False))

    grid = features.build_grid()
    g = index.score(features.build_features(grid, layers, roads, graph))
    g = sensitivity.add_robustness(g)

    candidates = siting.candidate_sites(layers, g.crs)
    existing = layers["ev_station"] if config.SITING_INCLUDE_EXISTING else None
    sites, g["cover_rank"] = siting.greedy_max_coverage(g, candidates, graph, existing)
    sites_ll = sites.to_crs("EPSG:4326")
    sites.drop(columns="geometry").assign(lat=sites_ll.geometry.y.round(5), lon=sites_ll.geometry.x.round(5)).to_csv(
        OUT / "swap_sites_greenfield.csv", index=False
    )
    print(f"{len(candidates)} candidate sites; top {len(sites)} cover {sites['cumulative_coverage_pct'].iloc[-1]}% of boda demand")

    # E-car public charging network (greenfield)
    car_candidates = siting.candidate_sites(layers, g.crs, config.CAR_SITING_CANDIDATE_LAYERS)
    car_sites, g["car_cover_rank"] = siting.greedy_max_coverage(
        g, car_candidates, graph, existing, index_col="car_suitability",
        cover_m=config.CAR_SITING_COVER_ROAD_M, max_sites=config.CAR_SITING_MAX_SITES)
    car_ll = car_sites.to_crs("EPSG:4326")
    car_sites.drop(columns="geometry").assign(lat=car_ll.geometry.y.round(5), lon=car_ll.geometry.x.round(5)).to_csv(
        OUT / "charger_sites_greenfield.csv", index=False)
    print(f"{len(car_candidates)} charger candidates; top {len(car_sites)} cover {car_sites['cumulative_coverage_pct'].iloc[-1]}% of e-car demand")
    for n in config.CAR_ECONOMICS_NETWORK_SIZES:
        first = car_sites.head(n)
        d = graph.nearest_distance(centroids_xy_all(g), np.column_stack([first.geometry.x, first.geometry.y]))
        g[f"dist_charger_n{n}_m"] = d
        ok = np.isfinite(d)
        dd = np.where(ok, d, 0)
        g[f"private_saving_n{n}_ugx"] = np.where(ok, car_economics.annual_saving(car_economics.BASE, "private", g["home_charging_potential"], dd), np.nan)
        g[f"ridehail_saving_n{n}_ugx"] = np.where(ok, car_economics.annual_saving(car_economics.BASE, "ridehail", None, dd), np.nan)
    write_car_economics()

    # Rider economics by place: road distance to the nearest of the first N proposed sites.
    centroids_xy = np.column_stack([g.geometry.centroid.x, g.geometry.centroid.y])
    for n in config.ECONOMICS_NETWORK_SIZES:
        first = sites.head(n)
        d = graph.nearest_distance(centroids_xy, np.column_stack([first.geometry.x, first.geometry.y]))
        g[f"dist_site_n{n}_m"] = d
        g[f"saving_n{n}_ugx"] = np.where(np.isfinite(d), economics.daily_saving(economics.BASE, d), np.nan)
    write_economics()

    g.to_file(OUT / "grid_scores.gpkg", driver="GPKG")
    layers["ev_station"].to_file(OUT / "ev_stations.gpkg", driver="GPKG")

    cols = [
        "cell_id", "boda_suitability", "car_suitability", "boda_top10_robustness", "car_top10_robustness",
        "pop_density_2025", "pop_growth_2020_2025", "housing_wealth_proxy", "boda_gap", "car_gap",
        "dist_ev_station_m", "dist_cbd_km",
    ]
    centroids = g.geometry.centroid.to_crs("EPSG:4326")
    g["lat"], g["lon"] = centroids.y.round(5), centroids.x.round(5)
    for col in ["boda_suitability", "car_suitability", "boda_gap", "car_gap"]:
        g.nlargest(25, col)[cols + ["lat", "lon"]].round({c: 2 for c in cols[1:]}).to_csv(OUT / f"top25_{col}.csv", index=False)

    mapping.build_map(g, layers["ev_station"], sites, OUT / "kampala_ev_baseline_map.html")
    write_dashboard_data(g, sites_ll, layers["ev_station"], car_ll)
    print(f"scored {int(g['active'].sum())} active cells of {len(g)}; outputs in {OUT}")


def centroids_xy_all(g):
    c = g.geometry.centroid
    return np.column_stack([c.x, c.y])


def write_car_economics():
    car_economics.parameter_table().to_csv(OUT / "car_economics_parameters.csv", index=False)
    for persona in car_economics.PERSONAS:
        car_economics.tornado(persona).round(0).to_csv(OUT / f"car_economics_tornado_{persona}.csv", index=False)
        mc = car_economics.monte_carlo(persona)
        print(f"e-car {persona}: NPV>0 in {100 * (mc['npv'] > 0).mean():.1f}% of draws; median NPV {mc['npv'].median() / 1e6:,.1f}M UGX")


def write_economics():
    economics.parameter_table().to_csv(OUT / "economics_parameters.csv", index=False)
    economics.tornado().round(0).to_csv(OUT / "economics_tornado.csv", index=False)
    mc = economics.monte_carlo()
    mc.round(1).to_csv(OUT / "economics_monte_carlo.csv", index=False)
    print(
        f"e-boda daily saving (UGX): median {mc['saving'].median():,.0f}, 90% range "
        f"{mc['saving'].quantile(.05):,.0f}-{mc['saving'].quantile(.95):,.0f}; "
        f"electric cheaper in {100 * (mc['saving'] > 0).mean():.1f}% of draws"
    )


def car_econ_block():
    out = {"params": car_economics.parameter_table().to_dict(orient="records"),
           "personas": car_economics.PERSONAS, "by_persona": {}}
    for persona in car_economics.PERSONAS:
        ice, ev = car_economics.annual_costs(car_economics.BASE, persona)
        mc = car_economics.monte_carlo(persona)
        hist, edges = np.histogram(mc["npv"], bins=40)
        out["by_persona"][persona] = {
            "ice": float(ice), "ev": float(ev), "saving": float(ice - ev),
            "npv": float(car_economics.npv(car_economics.BASE, persona)),
            "payback": float(car_economics.payback_years(car_economics.BASE, persona)),
            "break_even_premium": float(car_economics.break_even_premium(car_economics.BASE, persona)),
            "mc_hist": {"counts": hist.tolist(), "edges": edges.round(0).tolist()},
            "mc_share_positive": float((mc["npv"] > 0).mean()),
            "mc_quantiles": mc["npv"].quantile([0.05, 0.5, 0.95]).round(0).tolist(),
            "tornado": car_economics.tornado(persona).round(0).to_dict(orient="records"),
        }
    return out


def write_dashboard_data(g, sites_ll, stations, car_ll):
    """Compact JSON consumed by the interactive dashboard."""
    a = g[g["active"]]
    num = lambda s, d=2: [None if not np.isfinite(v) else round(float(v), d) for v in s]  # noqa: E731
    cells = {
        "lat": num(a["lat"], 5), "lon": num(a["lon"], 5),
        "boda": num(a["boda_suitability"], 1), "car": num(a["car_suitability"], 1),
        "boda_rob": num(a["boda_top10_robustness"]), "car_rob": num(a["car_top10_robustness"]),
        "pop2020": num(a["pop_2020"], 0), "pop2025": num(a["pop_2025"], 0), "pop2030": num(a["pop_2030"], 0),
        "wealth": num(a["housing_wealth_proxy"]),
        "cover_rank": a["cover_rank"].astype(int).tolist(),
        **{f"saving_n{n}": num(a[f"saving_n{n}_ugx"], 0) for n in config.ECONOMICS_NETWORK_SIZES},
        **{f"dist_n{n}": num(a[f"dist_site_n{n}_m"], 0) for n in config.ECONOMICS_NETWORK_SIZES},
        "car_rank_cover": a["car_cover_rank"].astype(int).tolist(),
        "home_charge": num(a["home_charging_potential"]),
        **{f"private_n{n}": num(a[f"private_saving_n{n}_ugx"], -3) for n in config.CAR_ECONOMICS_NETWORK_SIZES},
        **{f"ridehail_n{n}": num(a[f"ridehail_saving_n{n}_ugx"], -3) for n in config.CAR_ECONOMICS_NETWORK_SIZES},
        **{f"dist_car_n{n}": num(a[f"dist_charger_n{n}_m"], 0) for n in config.CAR_ECONOMICS_NETWORK_SIZES},
    }
    p = economics.BASE
    petrol, electric = economics.daily_costs(p)
    mc = economics.monte_carlo()
    hist, edges = np.histogram(mc["saving"], bins=40)
    detours = np.arange(0, 16001, 500)
    prices = np.arange(4000, 8001, 250)
    econ = {
        "base": {"petrol": float(petrol), "electric": float(electric), "saving": float(petrol - electric)},
        "breakdown": {
            "petrol_fuel": p["daily_km"] / p["petrol_km_per_l"] * p["petrol_price_ugx_per_l"],
            "petrol_maint": p["petrol_maintenance_ugx_per_day"],
            "electric_energy": p["daily_km"] * p["swap_price_ugx_per_full"] / p["battery_range_km"],
            "electric_wait": p["daily_km"] / p["battery_range_km"] * p["swap_wait_min"] / 60 * p["rider_earnings_ugx_per_hour"],
            "electric_maint": p["electric_maintenance_ugx_per_day"],
        },
        "params": economics.parameter_table().to_dict(orient="records"),
        "mc_hist": {"counts": hist.tolist(), "edges": edges.round(0).tolist()},
        "mc_share_positive": float((mc["saving"] > 0).mean()),
        "mc_quantiles": mc["saving"].quantile([0.05, 0.5, 0.95]).round(0).tolist(),
        "tornado": economics.tornado().round(0).to_dict(orient="records"),
        "by_detour": {"m": detours.tolist(), "saving": [round(float(economics.daily_saving(p, d))) for d in detours]},
        "by_petrol_price": {
            "price": prices.tolist(),
            "saving": [round(float(economics.daily_saving({**p, "petrol_price_ugx_per_l": x}))) for x in prices],
        },
        "break_even_petrol_price": economics.break_even_petrol_price(p),
        "break_even_detour_m": economics.break_even_detour_m(p),
    }
    st = stations.to_crs("EPSG:4326")
    data = {
        "cells": cells,
        "sites": sites_ll.assign(lat=sites_ll.geometry.y.round(5), lon=sites_ll.geometry.x.round(5))
        .drop(columns="geometry").replace({np.nan: None}).to_dict(orient="records"),
        "car_sites": car_ll.assign(lat=car_ll.geometry.y.round(5), lon=car_ll.geometry.x.round(5))
        .drop(columns="geometry").replace({np.nan: None}).to_dict(orient="records"),
        "car_economics": car_econ_block(),
        "stations": [{"lat": round(pt.y, 5), "lon": round(pt.x, 5), "name": nm} for pt, nm in zip(st.geometry, st["name"])],
        "economics": econ,
        "config": {
            "cell_size_m": config.CELL_SIZE_M, "cover_road_m": config.SITING_COVER_ROAD_M,
            "network_sizes": config.ECONOMICS_NETWORK_SIZES, "bbox": config.BBOX,
            "car_cover_road_m": config.CAR_SITING_COVER_ROAD_M, "car_network_sizes": config.CAR_ECONOMICS_NETWORK_SIZES,
        },
    }
    (OUT / "dashboard_data.json").write_text(json.dumps(data, separators=(",", ":"), default=float))


if __name__ == "__main__":
    main()
