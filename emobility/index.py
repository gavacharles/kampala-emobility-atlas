"""Transparent suitability and infrastructure-gap indices.

These are weighted percentile-rank indices, not probabilities of adoption. They become a
predictive model only once observed adoption labels (operator fleet/swap data, registrations)
are available to fit and validate against.
"""

import geopandas as gpd
import numpy as np

import config


def _weighted_rank_index(g: gpd.GeoDataFrame, weights: dict) -> np.ndarray:
    assert abs(sum(weights.values()) - 1) < 1e-9, "index weights must sum to 1"
    active = g["active"]
    score = np.zeros(len(g))
    for feature, w in weights.items():
        ranks = g.loc[active, feature].rank(pct=True).fillna(0)  # missing proxy (e.g. no buildings) ranks lowest
        score[active.to_numpy()] += w * ranks.to_numpy()
    score = score * 100
    score[~active.to_numpy()] = np.nan
    return score


def access_penalty(dist_m) -> np.ndarray:
    """0 when a station is within SERVED_DISTANCE_M, rising linearly to 1 at UNSERVED_DISTANCE_M."""
    span = config.UNSERVED_DISTANCE_M - config.SERVED_DISTANCE_M
    return np.clip((np.asarray(dist_m, dtype=float) - config.SERVED_DISTANCE_M) / span, 0, 1)


def score(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = g.copy()
    g["boda_suitability"] = _weighted_rank_index(g, config.BODA_WEIGHTS)
    g["car_suitability"] = _weighted_rank_index(g, config.CAR_WEIGHTS)
    penalty = access_penalty(g["dist_ev_station_m"])
    # High suitability AND far from existing EV infrastructure -> high gap.
    g["boda_gap"] = g["boda_suitability"] * penalty
    g["car_gap"] = g["car_suitability"] * penalty
    return g
