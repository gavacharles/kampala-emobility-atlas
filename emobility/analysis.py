"""Inferential and robustness analyses used in the papers.

- Spatial autocorrelation: global Moran's I (permutation inference) and local Getis-Ord Gi* with
  Benjamini-Hochberg FDR control, on the regular grid with queen contiguity.
- Siting: greedy maximal-coverage order on a precomputed cover matrix, compared with random and
  restricted candidate pools, across cover distances and across redrawn index weights.
- Access and economics by network size, and their distribution across wealth quintiles and rings.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

import config
from emobility import economics

# ---------------------------------------------------------------- spatial statistics


def _neighbours(rows, cols, radius=1):
    """Index lists of queen neighbours (Chebyshev distance <= radius), excluding self."""
    pos = {(r, c): i for i, (r, c) in enumerate(zip(rows, cols))}
    out = []
    for r, c in zip(rows, cols):
        nb = [pos[(r + dr, c + dc)] for dr in range(-radius, radius + 1) for dc in range(-radius, radius + 1)
              if (dr or dc) and (r + dr, c + dc) in pos]
        out.append(np.array(nb, dtype=int))
    return out


def morans_i(x, rows, cols, permutations=999, seed=0):
    x = np.asarray(x, float)
    nb = _neighbours(rows, cols)
    z = x - x.mean()
    s0 = sum(len(n) for n in nb)

    def stat(zz):
        lag = np.array([zz[n].sum() for n in nb])
        return len(zz) / s0 * (zz * lag).sum() / (zz**2).sum()

    i_obs = stat(z)
    rng = np.random.default_rng(seed)
    sims = np.array([stat(rng.permutation(z)) for _ in range(permutations)])
    p = (1 + (np.abs(sims - sims.mean()) >= abs(i_obs - sims.mean())).sum()) / (permutations + 1)
    return {"I": i_obs, "E[I]": -1 / (len(x) - 1), "z": (i_obs - sims.mean()) / sims.std(), "p_perm": p}


def getis_ord_gi_star(x, rows, cols, radius=1, alpha=0.05):
    """Gi* z-scores (self included, binary weights) and FDR-controlled hot/cold classification."""
    x = np.asarray(x, float)
    n = len(x)
    nb = _neighbours(rows, cols, radius)
    xbar, s = x.mean(), np.sqrt((x**2).mean() - x.mean() ** 2)
    z = np.empty(n)
    for i, nbi in enumerate(nb):
        idx = np.append(nbi, i)
        w = len(idx)
        z[i] = (x[idx].sum() - xbar * w) / (s * np.sqrt((n * w - w**2) / (n - 1)))
    p = 2 * norm.sf(np.abs(z))
    # Benjamini-Hochberg
    order = np.argsort(p)
    thresh = alpha * np.arange(1, n + 1) / n
    passed = p[order] <= thresh
    k = np.max(np.nonzero(passed)[0]) + 1 if passed.any() else 0
    sig = np.zeros(n, bool)
    sig[order[:k]] = True
    cls = np.where(sig & (z > 0), "hot", np.where(sig & (z < 0), "cold", "ns"))
    return z, p, cls


# ---------------------------------------------------------------- siting


def greedy_order(cover, w, n_max, covered0=None):
    """Greedy maximal coverage. Returns chosen candidate indices and cumulative coverage share."""
    covered = np.zeros(cover.shape[1], bool) if covered0 is None else covered0.copy()
    total = w.sum()
    chosen, cum = [], []
    avail = np.ones(cover.shape[0], bool)
    for _ in range(n_max):
        gain = (cover & ~covered) @ w
        gain[~avail] = -1
        b = int(np.argmax(gain))
        if gain[b] <= 0:
            break
        chosen.append(b)
        avail[b] = False
        covered |= cover[b]
        cum.append(w[covered].sum() / total)
    return np.array(chosen), np.array(cum)


def coverage_of(cover, w, idx):
    return w[cover[idx].any(axis=0)].sum() / w.sum() if len(idx) else 0.0


def random_baseline(cover, w, sizes, draws=200, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for n in sizes:
        vals = [coverage_of(cover, w, rng.choice(cover.shape[0], n, replace=False)) for _ in range(draws)]
        rows.append({"n_sites": n, "mean": np.mean(vals), "p2.5": np.percentile(vals, 2.5), "p97.5": np.percentile(vals, 97.5)})
    return pd.DataFrame(rows)


def weight_robust_sites(g_active, cover, n_sites=30, draws=100, seed=0):
    """Re-run greedy siting with boda-index weights redrawn from the Dirichlet used for robustness."""
    feats = list(config.BODA_WEIGHTS)
    ranks = np.column_stack([g_active[f].rank(pct=True).fillna(0).to_numpy() for f in feats])
    base = np.array([config.BODA_WEIGHTS[f] for f in feats])
    pop = g_active["pop_2025"].to_numpy()
    rng = np.random.default_rng(seed)
    counts = np.zeros(cover.shape[0])
    base_idx, _ = greedy_order(cover, pop * (ranks @ base), n_sites)
    jacc, covs = [], []
    for wdraw in rng.dirichlet(base * config.SENSITIVITY_CONCENTRATION, size=draws):
        idx, cum = greedy_order(cover, pop * (ranks @ wdraw), n_sites)
        counts[idx] += 1
        jacc.append(len(set(idx) & set(base_idx)) / len(set(idx) | set(base_idx)))
        # evaluate the redrawn network on the *base* demand, to see how much coverage is lost
        covs.append(coverage_of(cover, pop * (ranks @ base), idx))
    return counts / draws, np.array(jacc), np.array(covs), base_idx


# ---------------------------------------------------------------- access, economics, equity


def rings(dist_cbd_km):
    return pd.cut(dist_cbd_km, [0, 5, 10, 20, np.inf], labels=["core <5 km", "inner 5-10 km", "outer 10-20 km", "peri-urban >20 km"])


def wealth_quintiles(proxy):
    q = pd.qcut(proxy.rank(method="first"), 5, labels=["Q1 (least)", "Q2", "Q3", "Q4", "Q5 (most)"])
    return q.cat.add_categories("not built-up").fillna("not built-up")


def access_by_network_size(graph, cells_xy, sites_xy, pop, sizes, groups: dict, cover_m=None):
    """Population-weighted road distance and rider saving for the first N sites, overall and by group."""
    cover_m = cover_m or config.SITING_COVER_ROAD_M
    rows = []
    for n in sizes:
        d = graph.nearest_distance(cells_xy, sites_xy[:n])
        ok = np.isfinite(d)
        saving = np.where(ok, economics.daily_saving(economics.BASE, np.where(ok, d, 0)), np.nan)
        frame = pd.DataFrame({"d": d, "saving": saving, "pop": pop, "ok": ok, "covered": d <= cover_m, **groups})
        f = frame[frame.ok]
        rows.append(_summ(f, n, "all", "all"))
        for gname in groups:
            for level, sub in f.groupby(gname, observed=True):
                rows.append(_summ(sub, n, gname, level))
    return pd.DataFrame(rows)


def _summ(f, n, group, level):
    w = f["pop"]
    return {
        "n_sites": n, "group": group, "level": str(level), "population": w.sum(),
        "pop_weighted_km": (f["d"] * w).sum() / w.sum() / 1000,
        "pop_weighted_saving_ugx": (f["saving"] * w).sum() / w.sum(),
        "share_pop_covered": w[f["covered"]].sum() / w.sum(),
    }


def economics_scenarios(graph, cells_xy, sites_xy, pop, sizes=(10, 30, 60), petrol_prices=(5000, 6650, 8000)):
    rows = []
    for n in sizes:
        d = graph.nearest_distance(cells_xy, sites_xy[:n])
        ok = np.isfinite(d)
        for price in petrol_prices:
            p = {**economics.BASE, "petrol_price_ugx_per_l": price}
            s = economics.daily_saving(p, d[ok])
            w = pop[ok]
            rows.append({
                "n_sites": n, "petrol_price": price,
                "pop_weighted_saving_ugx": (s * w).sum() / w.sum(),
                "share_pop_saving_gt0": w[s > 0].sum() / w.sum(),
                "share_pop_saving_gt3000": w[s > 3000].sum() / w.sum(),
            })
    return pd.DataFrame(rows)


def concentration_index(outcome, rank_var, weights):
    """Wagstaff-style concentration index of outcome over rank_var (positive = pro-rich)."""
    df = pd.DataFrame({"y": outcome, "r": rank_var, "w": weights}).dropna().sort_values("r")
    w = df["w"] / df["w"].sum()
    frac = w.cumsum() - w / 2
    mu = (df["y"] * w).sum()
    return 2 * (w * (df["y"] - mu) * (frac - (w * frac).sum())).sum() / mu


def exact_mclp(cover, w, n_sites, time_limit=300):
    """Exact maximal covering location problem (Church & ReVelle 1974) via HiGHS MILP.

    max sum_i w_i y_i  s.t.  y_i <= sum_j a_ij x_j,  sum_j x_j = n_sites,  x, y binary.
    Returns (coverage share, chosen candidate indices, MIP gap reported by the solver).
    """
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csr_matrix, hstack, identity

    keep = cover.any(axis=0) & (w > 0)  # demand no candidate can reach is constant; drop it
    a = csr_matrix(cover[:, keep].T.astype(float))  # cells x candidates
    m, n = a.shape
    c = np.concatenate([np.zeros(n), -w[keep]])
    cons = [
        LinearConstraint(hstack([-a, identity(m)]), -np.inf, 0),  # y_i - sum_j a_ij x_j <= 0
        LinearConstraint(np.concatenate([np.ones(n), np.zeros(m)])[None, :], n_sites, n_sites),
    ]
    res = milp(c, constraints=cons, integrality=np.concatenate([np.ones(n), np.zeros(m)]),
               bounds=Bounds(0, 1), options={"time_limit": time_limit, "mip_rel_gap": 1e-4})
    x = res.x[:n] > 0.5
    return -res.fun / w.sum(), np.flatnonzero(x), getattr(res, "mip_gap", np.nan)
