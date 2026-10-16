"""Road-network distances (shortest path along OSM roads) for Greater Kampala.

The graph is undirected: boda riders largely ignore one-way restrictions, and for car access the
error is small at the 1 km grid scale. Origins/destinations are snapped to the nearest graph node and
the straight-line snap distance is added to the path length.
"""

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

import config
from emobility.fetch import _overpass

ROAD_CLASSES = (
    "motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|"
    "tertiary|tertiary_link|unclassified|residential|living_street|service|track|road"
)
TILES_PER_SIDE = 3  # split the Overpass download so each request stays under the server's limits
MAX_SNAP_M = 1500  # beyond this a point is treated as off-network


class RoadGraph:
    def __init__(self, metric_crs: str):
        node_xy, edges = {}, set()
        s, w, n, e = config.BBOX
        dy, dx = (n - s) / TILES_PER_SIDE, (e - w) / TILES_PER_SIDE
        for i in range(TILES_PER_SIDE):
            for j in range(TILES_PER_SIDE):
                bbox = f"{s + i * dy},{w + j * dx},{s + (i + 1) * dy},{w + (j + 1) * dx}"
                data = _overpass(
                    f'[out:json][timeout:600];way["highway"~"^({ROAD_CLASSES})$"]({bbox});(._;>;);out skel qt;'
                )
                for el in data["elements"]:
                    if el["type"] == "node":
                        node_xy[el["id"]] = (el["lon"], el["lat"])
                    elif el["type"] == "way":
                        nds = el["nodes"]
                        edges.update((min(a, b), max(a, b)) for a, b in zip(nds[:-1], nds[1:]) if a != b)

        ids = np.fromiter(node_xy.keys(), dtype=np.int64)
        lonlat = np.array([node_xy[i] for i in ids])
        x, y = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform(lonlat[:, 0], lonlat[:, 1])
        xy = np.column_stack([x, y])
        index = pd.Series(np.arange(len(ids)), index=ids)

        e = np.array(list(edges))
        e = e[np.isin(e[:, 0], ids) & np.isin(e[:, 1], ids)]
        a, b = index[e[:, 0]].to_numpy(), index[e[:, 1]].to_numpy()
        length = np.hypot(*(xy[a] - xy[b]).T)
        graph = coo_matrix((np.r_[length, length], (np.r_[a, b], np.r_[b, a])), shape=(len(ids),) * 2).tocsr()

        # Keep the largest connected component; fragments (private compounds, unconnected tracks)
        # would otherwise make reachable places look unreachable.
        _, labels = connected_components(graph, directed=False)
        main = labels == np.bincount(labels).argmax()
        keep = np.flatnonzero(main)
        self.graph = graph[keep][:, keep]
        self.xy = xy[keep]
        self.tree = cKDTree(self.xy)
        self.n_edges = int(self.graph.nnz // 2)
        self.total_km = float(self.graph.sum() / 2 / 1000)

    def snap(self, x, y):
        d, node = self.tree.query(np.column_stack([x, y]))
        return node, d

    def nearest_distance(self, origins_xy, targets_xy) -> np.ndarray:
        """Network distance (m) from each origin to its nearest target."""
        if len(targets_xy) == 0:
            return np.full(len(origins_xy), np.inf)
        t_node, t_snap = self.snap(*np.asarray(targets_xy).T)
        o_node, o_snap = self.snap(*np.asarray(origins_xy).T)
        # Multi-source Dijkstra; target snap offsets are approximated by the smallest one at a node.
        dist = dijkstra(self.graph, directed=False, indices=np.unique(t_node), min_only=True)
        out = dist[o_node] + o_snap + np.median(t_snap)
        out[o_snap > MAX_SNAP_M] = np.inf
        return out

    def nearest_assign(self, origins_xy, targets_xy):
        """Index of the nearest target (by road) for each origin, and that distance (m). -1 if off-network."""
        t_node, t_snap = self.snap(*np.asarray(targets_xy).T)
        o_node, o_snap = self.snap(*np.asarray(origins_xy).T)
        uniq, first = np.unique(t_node, return_index=True)
        dist, _, src = dijkstra(self.graph, directed=False, indices=uniq, min_only=True, return_predecessors=True)
        node_to_target = dict(zip(uniq, first))
        src_o = src[o_node]
        idx = np.array([node_to_target.get(v, -1) for v in src_o])
        d = dist[o_node] + o_snap + t_snap[np.maximum(idx, 0)]
        bad = (o_snap > MAX_SNAP_M) | (idx < 0) | ~np.isfinite(d)
        idx[bad], d[bad] = -1, np.inf
        return idx, d

    def within(self, sources_xy, targets_xy, limit_m: float, chunk: int = 40) -> np.ndarray:
        """Boolean matrix [source, target]: target reachable from source within limit_m along roads."""
        s_node, s_snap = self.snap(*np.asarray(sources_xy).T)
        t_node, t_snap = self.snap(*np.asarray(targets_xy).T)
        out = np.zeros((len(s_node), len(t_node)), dtype=bool)
        for start in range(0, len(s_node), chunk):
            idx = slice(start, start + chunk)
            d = dijkstra(self.graph, directed=False, indices=s_node[idx], limit=limit_m)
            total = d[:, t_node] + s_snap[idx, None] + t_snap[None, :]
            out[idx] = total <= limit_m
        out[:, t_snap > MAX_SNAP_M] = False
        out[s_snap > MAX_SNAP_M, :] = False
        return out
