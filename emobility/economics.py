"""Petrol vs electric boda operating economics, and how swap-station access changes them by place.

Every parameter carries a base value, a plausible range and its source. Values marked ASSUMPTION
have no Kampala-specific measurement behind them and are the first things to replace with survey
or operator data.
"""

import numpy as np
import pandas as pd

PARAMS = {
    "petrol_price_ugx_per_l": dict(
        base=6650, low=5100, high=7000,
        source="Daily Monitor market surveillance, Kampala, 8 Sep 2026 (6,650); range from Apr-Sep 2026 reporting",
    ),
    "petrol_km_per_l": dict(
        base=40, low=30, high=50,
        source="ASSUMPTION: 125-150cc commuter motorcycle in stop-start urban traffic",
    ),
    "daily_km": dict(
        base=65, low=40, high=120,
        source="~18 trips/day x ~3 km (Transitec & Transport for Cairo for AFD/KCCA, Analysis of Boda-Boda Operations, 2020) plus empty running",
    ),
    "swap_price_ugx_per_full": dict(
        base=8400, low=5000, high=8500,
        source="Spiro Shs 84 per % charge = 8,400 per full battery (Sep 2026); Gogo ~5,000 and Zembo ~6,000 (2024)",
    ),
    "battery_range_km": dict(
        base=90, low=75, high=100,
        source="Operators quote ~100 km per full battery; a Jinja riders' association reports ~85 km",
    ),
    "petrol_maintenance_ugx_per_day": dict(
        base=2500, low=1500, high=4000,
        source="ASSUMPTION: oil, filters, chain, plugs, engine repairs averaged per working day",
    ),
    "electric_maintenance_ugx_per_day": dict(
        base=1000, low=500, high=2000,
        source="ASSUMPTION: no engine oil/fuel system; battery maintenance borne by the swap operator",
    ),
    "rider_earnings_ugx_per_hour": dict(
        base=3500, low=2500, high=5000,
        source="ASSUMPTION: ~35,000 net per 10-hour day; values detour and queueing time",
    ),
    "swap_wait_min": dict(
        base=8, low=3, high=20,
        source="ASSUMPTION: time at the station per swap (queue + exchange)",
    ),
    "detour_speed_kmh": dict(
        base=20, low=15, high=25,
        source="ASSUMPTION: average urban boda speed when riding empty to a station",
    ),
}

BASE = {k: v["base"] for k, v in PARAMS.items()}


def daily_costs(p: dict, detour_m=0.0):
    """Daily operating cost (UGX) for petrol and electric bodas.

    detour_m is the one-way road distance from where the rider works to the nearest swap station.
    Each swap costs a round trip of empty riding (charged as energy + lost earnings) plus waiting time.
    """
    detour_km = 2 * np.asarray(detour_m, dtype=float) / 1000
    petrol = p["daily_km"] / p["petrol_km_per_l"] * p["petrol_price_ugx_per_l"] + p["petrol_maintenance_ugx_per_day"]

    swaps = p["daily_km"] / p["battery_range_km"]  # pay-per-% pricing makes partial swaps proportional
    total_km = p["daily_km"] + swaps * detour_km
    energy = total_km * p["swap_price_ugx_per_full"] / p["battery_range_km"]
    hours_lost = swaps * (detour_km / p["detour_speed_kmh"] + p["swap_wait_min"] / 60)
    electric = energy + hours_lost * p["rider_earnings_ugx_per_hour"] + p["electric_maintenance_ugx_per_day"]
    return petrol, electric


def daily_saving(p: dict, detour_m=0.0):
    petrol, electric = daily_costs(p, detour_m)
    return petrol - electric


def break_even_petrol_price(p: dict, detour_m=0.0) -> float:
    """Petrol price (UGX/L) at which electric and petrol cost the same per day."""
    _, electric = daily_costs(p, detour_m)
    litres = p["daily_km"] / p["petrol_km_per_l"]
    return float((electric - p["petrol_maintenance_ugx_per_day"]) / litres)


def break_even_detour_m(p: dict) -> float:
    """One-way distance to a swap station at which electric stops being cheaper (bisection)."""
    lo, hi = 0.0, 50_000.0
    if daily_saving(p, lo) <= 0:
        return 0.0
    if daily_saving(p, hi) > 0:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if daily_saving(p, mid) > 0 else (lo, mid)
    return lo


def monte_carlo(n: int = 5000, detour_m: float = 0.0, seed: int = 0) -> pd.DataFrame:
    """Draw every parameter from a triangular(low, base, high) distribution."""
    rng = np.random.default_rng(seed)
    draws = {k: rng.triangular(v["low"], v["base"], v["high"], n) for k, v in PARAMS.items()}
    petrol, electric = daily_costs(draws, detour_m)
    return pd.DataFrame({**draws, "petrol_cost": petrol, "electric_cost": electric, "saving": petrol - electric})


def tornado(detour_m: float = 0.0) -> pd.DataFrame:
    """Daily saving when each parameter alone moves to its low and high value."""
    base = daily_saving(BASE, detour_m)
    rows = []
    for k, v in PARAMS.items():
        lo = daily_saving({**BASE, k: v["low"]}, detour_m)
        hi = daily_saving({**BASE, k: v["high"]}, detour_m)
        rows.append({"parameter": k, "saving_at_low": lo, "saving_at_high": hi, "swing": abs(hi - lo), "base": base})
    return pd.DataFrame(rows).sort_values("swing", ascending=False)


def parameter_table() -> pd.DataFrame:
    return pd.DataFrame([{"parameter": k, **v} for k, v in PARAMS.items()])
