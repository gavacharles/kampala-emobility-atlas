"""Total cost of ownership of a used imported battery-electric car vs a comparable petrol car in Kampala.

Two use cases with very different economics:
  private   ~40 km/day, mostly home-charged where the household has off-street parking and its own meter
  ridehail  ~180 km/day (Uber/Bolt/special hire), mostly public DC fast charging, time is lost fares

Uganda had only 17 fully electric cars imported 2022-Apr 2024 (URA), so no local fleet data exist:
inputs marked ASSUMPTION are the first to replace with dealer quotes and driver surveys.
"""

import numpy as np
import pandas as pd

from emobility.economics import PARAMS as BODA_PARAMS

PARAMS = {
    "petrol_price_ugx_per_l": BODA_PARAMS["petrol_price_ugx_per_l"],
    "ice_km_per_l": dict(base=12, low=9, high=16, source="ASSUMPTION: used 1.3-1.8 L Japanese import in Kampala traffic"),
    "ev_kwh_per_km": dict(base=0.17, low=0.14, high=0.22,
                          source="Nissan Leaf-class consumption incl. ~10% charging losses; hot climate, aged battery"),
    "home_tariff_ugx_per_kwh": dict(base=779.4, low=562, high=950,
                                    source="UEDCL domestic tariff above lifeline, Oct-Dec 2026 (Daily Monitor); low = commercial average"),
    "public_dc_ugx_per_kwh": dict(base=1500, low=1000, high=2500,
                                  source="ASSUMPTION: no published Kampala DC fast-charging price (pilot at Amber House)"),
    "ice_maint_ugx_per_km": dict(base=150, low=100, high=250, source="ASSUMPTION: service, oil, brakes, engine/gearbox repairs"),
    "ev_maint_ugx_per_km": dict(base=70, low=40, high=120, source="ASSUMPTION: tyres, brakes, suspension; no engine service"),
    "battery_reserve_ugx_per_km": dict(base=60, low=0, high=150,
                                       source="ASSUMPTION: provision for degradation/replacement of a used imported pack"),
    "range_per_charge_km": dict(base=150, low=110, high=200, source="Usable km per DC session (20-80%+) for a used 40 kWh-class car"),
    "dc_session_min": dict(base=40, low=25, high=70, source="ASSUMPTION: queue + 30-50 kW charge; pilot station offers 30-360 kW"),
    "ev_purchase_premium_ugx": dict(base=12e6, low=0, high=30e6,
                                    source="ASSUMPTION: landed price gap after 25% import duty (fully built EVs, reinstated 2024)"),
    "discount_rate": dict(base=0.15, low=0.10, high=0.22, source="ASSUMPTION: Ugandan vehicle-loan / opportunity cost of capital"),
    "horizon_years": dict(base=5, low=3, high=7, source="ASSUMPTION: holding period of a used import"),
}

PERSONAS = {
    "private": dict(daily_km=40, days=300, home_share=0.8, time_value_ugx_per_h=3000, label="Private car"),
    "ridehail": dict(daily_km=180, days=310, home_share=0.3, time_value_ugx_per_h=8000, label="Ride-hail / taxi"),
}

BASE = {k: v["base"] for k, v in PARAMS.items()}


def annual_costs(p, persona, home_share=None, detour_m=0.0):
    """Annual operating cost (UGX) of the petrol and electric car; detour_m is one-way road distance to a DC charger."""
    q = PERSONAS[persona]
    hs = q["home_share"] if home_share is None else home_share
    km = q["daily_km"] * q["days"]
    ice = km / p["ice_km_per_l"] * p["petrol_price_ugx_per_l"] + km * p["ice_maint_ugx_per_km"]

    public_km = km * (1 - np.asarray(hs, float))
    sessions = public_km / p["range_per_charge_km"]
    detour_km = sessions * 2 * np.asarray(detour_m, float) / 1000
    energy = (km * hs * p["home_tariff_ugx_per_kwh"] + (public_km + detour_km) * p["public_dc_ugx_per_kwh"]) * p["ev_kwh_per_km"]
    hours = sessions * (p["dc_session_min"] / 60 + 2 * np.asarray(detour_m, float) / 1000 / 25)  # 25 km/h urban
    ev = energy + (km + detour_km) * (p["ev_maint_ugx_per_km"] + p["battery_reserve_ugx_per_km"]) + hours * q["time_value_ugx_per_h"]
    return ice, ev


def annual_saving(p, persona, home_share=None, detour_m=0.0):
    ice, ev = annual_costs(p, persona, home_share, detour_m)
    return ice - ev


def npv(p, persona, home_share=None, detour_m=0.0):
    s = annual_saving(p, persona, home_share, detour_m)
    n, r = int(round(p["horizon_years"])), p["discount_rate"]
    annuity = (1 - (1 + r) ** -n) / r
    return s * annuity - p["ev_purchase_premium_ugx"]


def payback_years(p, persona, home_share=None, detour_m=0.0):
    s = annual_saving(p, persona, home_share, detour_m)
    return np.where(s > 0, p["ev_purchase_premium_ugx"] / np.maximum(s, 1e-9), np.inf)


def break_even_premium(p, persona, home_share=None, detour_m=0.0):
    """Largest purchase premium the operating saving repays within the horizon (NPV = 0)."""
    return npv({**p, "ev_purchase_premium_ugx": 0}, persona, home_share, detour_m)


def monte_carlo(persona, n=5000, seed=0, detour_m=0.0):
    rng = np.random.default_rng(seed)
    d = {k: rng.triangular(v["low"], v["base"], v["high"], n) for k, v in PARAMS.items()}
    d["horizon_years"] = np.round(d["horizon_years"])
    s = annual_saving(d, persona, detour_m=detour_m)
    r, h = d["discount_rate"], d["horizon_years"]
    v = s * (1 - (1 + r) ** -h) / r - d["ev_purchase_premium_ugx"]
    return pd.DataFrame({**d, "annual_saving": s, "npv": v})


def tornado(persona, metric="npv"):
    f = npv if metric == "npv" else annual_saving
    base = float(f(BASE, persona))
    rows = []
    for k, v in PARAMS.items():
        lo, hi = float(f({**BASE, k: v["low"]}, persona)), float(f({**BASE, k: v["high"]}, persona))
        rows.append({"parameter": k, "at_low": lo, "at_high": hi, "swing": abs(hi - lo), "base": base})
    return pd.DataFrame(rows).sort_values("swing", ascending=False)


def parameter_table():
    return pd.DataFrame([{"parameter": k, **v} for k, v in PARAMS.items()])


def home_charging_potential(open_space_per_building_m2, built_up: pd.Series):
    """Share of households likely to have off-street parking + own meter (ASSUMPTION mapping).

    Dense cells (<300 m2 open space per building) -> ~0; garden-plot suburbs (>2,000 m2) -> 1.
    Non-built-up cells (detached rural plots) default to 0.8.
    """
    x = np.clip((np.asarray(open_space_per_building_m2, float) - 300) / (2000 - 300), 0, 1)
    return pd.Series(np.where(built_up.to_numpy() & np.isfinite(x), x, 0.8), index=built_up.index)
