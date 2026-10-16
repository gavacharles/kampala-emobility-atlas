"""How much do the suitability rankings depend on the judgement-based weights?

Redraws each index's weights many times from a Dirichlet centred on the configured weights and
records how often each cell lands in the top SENSITIVITY_TOP_SHARE of active cells. A cell with
robustness near 1 is a top cell under almost any reasonable weighting; near 0.5 means its status
hinges on the weights chosen.
"""

import geopandas as gpd
import numpy as np

import config


def top_share_frequency(g: gpd.GeoDataFrame, weights: dict, seed: int = 0) -> np.ndarray:
    active = g["active"].to_numpy()
    features = list(weights)
    ranks = np.column_stack([g.loc[active, f].rank(pct=True).fillna(0).to_numpy() for f in features])
    base = np.array([weights[f] for f in features])

    rng = np.random.default_rng(seed)
    draws = rng.dirichlet(base * config.SENSITIVITY_CONCENTRATION, size=config.SENSITIVITY_DRAWS)
    scores = ranks @ draws.T  # cells x draws
    cutoff = np.quantile(scores, 1 - config.SENSITIVITY_TOP_SHARE, axis=0)
    freq = (scores >= cutoff).mean(axis=1)

    out = np.full(len(g), np.nan)
    out[active] = freq
    return out


def add_robustness(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = g.copy()
    g["boda_top10_robustness"] = top_share_frequency(g, config.BODA_WEIGHTS)
    g["car_top10_robustness"] = top_share_frequency(g, config.CAR_WEIGHTS, seed=1)
    return g
