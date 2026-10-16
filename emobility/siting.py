"""Greenfield battery-swap station siting by greedy maximal coverage.

Picks sites one at a time from a candidate pool, each time choosing the candidate that covers the
most not-yet-covered demand within SITING_COVER_ROAD_M along the road network. Greedy selection is within (1 - 1/e)
of the optimal coverage and yields a ranked build order, which is what an operator needs.
"""

import geopandas as gpd
import numpy as np
import pandas as pd

import config


def candidate_sites(layers: dict, metric_crs: str, layer_names=None) -> gpd.GeoDataFrame:
    layer_names = layer_names or config.SITING_CANDIDATE_LAYERS
    pts = pd.concat([layers[name].assign(site_type=name) for name in layer_names], ignore_index=True)
    pts = gpd.GeoDataFrame(pts, geometry="geometry", crs="EPSG:4326").to_crs(metric_crs)
    # Snap to a coarse lattice to drop near-duplicates (e.g. a taxi stage beside a market).
    key = (pts.geometry.x // config.SITING_CANDIDATE_DEDUP_M).astype(int).astype(str) + "_" + (
        pts.geometry.y // config.SITING_CANDIDATE_DEDUP_M
    ).astype(int).astype(str)
    return pts.loc[~key.duplicated()].reset_index(drop=True)


def demand_weights(g: gpd.GeoDataFrame, index_col: str = "boda_suitability") -> pd.Series:
    return (g["pop_2025"] * g[index_col].fillna(0) / 100).where(g["active"], 0.0)


def _xy(geoms):
    return np.column_stack([geoms.x.to_numpy(), geoms.y.to_numpy()])


def greedy_max_coverage(g: gpd.GeoDataFrame, candidates: gpd.GeoDataFrame, graph, existing: gpd.GeoDataFrame = None,
                        index_col: str = "boda_suitability", cover_m: float = None, max_sites: int = None):
    cover_m = cover_m or config.SITING_COVER_ROAD_M
    max_sites = max_sites or config.SITING_MAX_SITES
    demand = demand_weights(g, index_col).to_numpy()
    keep = demand > 0
    cells_xy = _xy(g.geometry.centroid[keep])
    w = demand[keep]

    def cover_of(points):
        return graph.within(_xy(points.geometry), cells_xy, cover_m)

    cover = cover_of(candidates)
    covered = np.zeros(len(w), dtype=bool)
    if existing is not None and not existing.empty:
        covered |= cover_of(existing.to_crs(g.crs)).any(axis=0)

    total = w.sum()
    first_rank = np.zeros(len(w), dtype=int)  # 0 = never covered; -1 = covered by an existing station
    first_rank[covered] = -1
    rows = []
    chosen = np.zeros(len(candidates), dtype=bool)
    for rank in range(1, max_sites + 1):
        gain = (cover & ~covered) @ w
        gain[chosen] = -1
        best = int(np.argmax(gain))
        if gain[best] <= 0:
            break
        chosen[best] = True
        first_rank[cover[best] & ~covered] = rank
        covered |= cover[best]
        c = candidates.iloc[best]
        rows.append(
            {
                "rank": rank,
                "site_type": c["site_type"],
                "name": c.get("name"),
                "osm_id": c.get("osm_id"),
                "marginal_demand_pct": round(100 * gain[best] / total, 2),
                "cumulative_coverage_pct": round(100 * w[covered].sum() / total, 2),
                "geometry": c.geometry,
            }
        )
    sites = gpd.GeoDataFrame(rows, geometry="geometry", crs=g.crs)
    # Build-order rank of the site that first brings each cell into coverage (for the network animation).
    cover_rank = pd.Series(0, index=g.index)
    cover_rank[keep] = first_rank
    return sites, cover_rank
