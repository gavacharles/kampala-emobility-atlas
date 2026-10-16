"""Operational sizing of the proposed networks: catchments, daily throughput, equipment and grid load.

Every rider/car in a cell is assigned to the nearest proposed site by road (its catchment).
Fleet sizes and equipment ratings are scenario inputs (ASSUMPTION) and are reported as such.
"""

import numpy as np
import pandas as pd

from emobility import car_economics, economics

# Motorcycles in Greater Kampala: "over 400,000" (World Bank, Sep 2026). Not all are bodas; used as the
# addressable fleet, allocated to cells in proportion to e-boda demand (population x suitability).
GKMA_MOTORCYCLES = 400_000
BODA_ADOPTION_SCENARIOS = (0.10, 0.25, 0.50)
PACK_KWH = 2.9  # ASSUMPTION: swappable e-boda pack (~72 V x 40 Ah class)
CHARGER_EFFICIENCY = 0.90
CABINET_SWAPS_PER_DAY = 64  # ASSUMPTION: 8-slot cabinet, ~2.5 h charge per pack, ~8 cycles per slot per day
CHARGING_HOURS = 20  # packs charge round the clock except the evening peak
PEAK_FACTOR = 1.5

# E-car public fast charging: scenario fleet of electric ride-hail/taxi cars (ASSUMPTION).
RIDEHAIL_EV_SCENARIOS = (500, 2000, 5000)
DC_PORT_KW = 60
DC_UTILISATION = 0.35  # share of 24 h a port delivers energy


def swap_station_plan(cells: pd.DataFrame, site_idx: np.ndarray, site_dist: np.ndarray, sites: pd.DataFrame, cover_m: float):
    """cells needs pop_2025 and boda_suitability; site_idx/site_dist from RoadGraph.nearest_assign."""
    demand = cells["pop_2025"].to_numpy() * cells["boda_suitability"].fillna(0).to_numpy() / 100
    riders = GKMA_MOTORCYCLES * demand / demand.sum()
    swaps_per_rider = economics.BASE["daily_km"] / economics.BASE["battery_range_km"]
    df = pd.DataFrame({"site": site_idx, "riders": riders, "pop": cells["pop_2025"].to_numpy(),
                       "within_cover": site_dist <= cover_m, "dist_m": site_dist})
    df = df[df["site"] >= 0]
    agg = df.groupby("site").agg(
        catchment_cells=("riders", "size"), catchment_pop=("pop", "sum"), motorcycles=("riders", "sum"),
        share_within_cover=("within_cover", "mean"),
        mean_access_km=("dist_m", lambda d: d.mean() / 1000))
    out = sites.reset_index(drop=True).join(agg, how="left")
    for a in BODA_ADOPTION_SCENARIOS:
        tag = f"{int(a * 100)}pct"
        swaps = out["motorcycles"] * a * swaps_per_rider
        kwh = swaps * PACK_KWH / CHARGER_EFFICIENCY
        out[f"swaps_day_{tag}"] = swaps.round(0)
        out[f"cabinets_{tag}"] = np.ceil(swaps / CABINET_SWAPS_PER_DAY)
        out[f"kwh_day_{tag}"] = kwh.round(0)
        out[f"grid_kw_{tag}"] = (kwh / CHARGING_HOURS * PEAK_FACTOR).round(1)
    return out


def charger_plan(cells: pd.DataFrame, site_idx, site_dist, sites: pd.DataFrame, cover_m: float):
    demand = cells["pop_2025"].to_numpy() * cells["car_suitability"].fillna(0).to_numpy() / 100
    share = demand / demand.sum()
    q = car_economics.PERSONAS["ridehail"]
    public_kwh_per_car = q["daily_km"] * (1 - q["home_share"]) * car_economics.BASE["ev_kwh_per_km"]
    df = pd.DataFrame({"site": site_idx, "share": share, "pop": cells["pop_2025"].to_numpy(), "within_cover": site_dist <= cover_m})
    df = df[df["site"] >= 0]
    agg = df.groupby("site").agg(catchment_cells=("share", "size"), catchment_pop=("pop", "sum"),
                                 demand_share=("share", "sum"), share_within_cover=("within_cover", "mean"))
    out = sites.reset_index(drop=True).join(agg, how="left")
    for n in RIDEHAIL_EV_SCENARIOS:
        kwh = out["demand_share"] * n * public_kwh_per_car
        out[f"kwh_day_{n}cars"] = kwh.round(0)
        out[f"dc_ports_{n}cars"] = np.maximum(1, np.ceil(kwh / (DC_PORT_KW * 24 * DC_UTILISATION)))
        out[f"grid_kw_{n}cars"] = out[f"dc_ports_{n}cars"] * DC_PORT_KW
    return out
