"""Publication figures (PNG, 300 dpi) and animations (GIF) for the papers, README and posts.

Usage:  .venv/bin/python make_figures.py   (after run_baseline.py and run_analysis.py)
Writes figures/*.png and figures/*.gif.
"""

import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import animation  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

import config  # noqa: E402
from emobility import economics, fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
FIG = ROOT / "figures"
AN = OUT / "analysis"

# Palette (validated reference palette from the dataviz method): sequential blue, second sequential
# orange, categorical slots in fixed order, diverging blue <-> red through neutral grey.
BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ORANGE = ["#fde3d6", "#f8c0a4", "#f29a72", "#eb6834", "#c4501f", "#963a13", "#6a280b"]
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, INK3, GRID, EMPTY = "#15171a", "#4c5157", "#7b8087", "#eceeec", "#eef0ee"
CM_BLUE = LinearSegmentedColormap.from_list("blue", BLUE)
CM_ORANGE = LinearSegmentedColormap.from_list("orange", ORANGE)
CM_DIV = LinearSegmentedColormap.from_list("div", ["#184f95", "#6da7ec", "#f0efec", "#ec8a8a", "#a32b2b"])

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK3, "axes.labelcolor": INK2,
    "xtick.color": INK3, "ytick.color": INK3, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 10, "axes.titlecolor": INK, "figure.dpi": 110,
    "savefig.dpi": 300, "savefig.bbox": "tight", "legend.frameon": False,
})

PLACES = {"CBD": (0.3136, 32.5811), "Kawempe": (0.375, 32.558), "Ntinda": (0.354, 32.615), "Nansana": (0.364, 32.528),
          "Kira": (0.398, 32.640), "Mukono": (0.353, 32.755), "Entebbe": (0.064, 32.475), "Kajjansi": (0.215, 32.550),
          "Wakiso": (0.404, 32.459), "Munyonyo": (0.245, 32.620)}


# ---------------------------------------------------------------- map helpers

def load():
    g = gpd.read_file(OUT / "grid_scores.gpkg")
    roads = fetch.fetch_major_roads()
    roads = roads[roads["highway"].isin(["motorway", "trunk", "primary", "secondary"])].to_crs(g.crs)
    return g, roads


def grid_array(g, values, active_only=True):
    arr = np.full((g["row"].max() + 1, g["col"].max() + 1), np.nan)
    v = np.asarray(values, float).copy()
    if active_only:
        v[~g["active"].astype(bool).to_numpy()] = np.nan
    arr[g["row"], g["col"]] = v
    return arr


def basemap(ax, g, roads, labels=True):
    x0, y0, x1, y1 = g.total_bounds
    ax.imshow(np.where(np.isnan(grid_array(g, g["active"])), np.nan, 0.0), origin="lower", extent=(x0, x1, y0, y1),
              cmap=LinearSegmentedColormap.from_list("e", [EMPTY, EMPTY]), zorder=0)
    roads.plot(ax=ax, color=INK, linewidth=0.35, alpha=0.45, zorder=3)
    if labels:
        pts = gpd.GeoSeries(gpd.points_from_xy([v[1] for v in PLACES.values()], [v[0] for v in PLACES.values()]), crs=4326).to_crs(g.crs)
        for name, p in zip(PLACES, pts):
            ax.annotate(name, (p.x, p.y), fontsize=6.5, color=INK, ha="center", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
    ax.set_xlim(x0 + 2000, x1 - 2000)
    ax.set_ylim(y0 + 1000, y1 - 1000)
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    scalebar(ax, x0 + 4000, y0 + 3500)


def scalebar(ax, x, y, km=10):
    ax.plot([x, x + km * 1000], [y, y], color="white", lw=3.5, zorder=7)
    ax.plot([x, x + km * 1000], [y, y], color=INK, lw=1.5, zorder=7)
    ax.text(x + km * 500, y + 900, f"{km} km", ha="center", fontsize=7, color=INK, zorder=7,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))


def layer(ax, g, values, cmap, vmin=None, vmax=None, norm=None):
    x0, y0, x1, y1 = g.total_bounds
    return ax.imshow(grid_array(g, values), origin="lower", extent=(x0, x1, y0, y1), cmap=cmap,
                     vmin=vmin, vmax=vmax, norm=norm, zorder=1, interpolation="nearest")


def cbar(fig, ax, im, label):
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.01, shrink=0.8)
    cb.outline.set_visible(False)
    cb.set_label(label, color=INK2, fontsize=8)
    cb.ax.tick_params(labelsize=7, color=INK3)
    return cb


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.png", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------- figures

def fig_study_area(g, roads):
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    basemap(ax, g, roads)
    im = layer(ax, g, g["pop_density_2025"], CM_ORANGE, 0, np.nanpercentile(g["pop_density_2025"][g.active == 1], 98))
    cbar(fig, ax, im, "Residents per km² (WorldPop 2025)")
    ax.set_title("Greater Kampala study area: 1 km grid, scored cells and major roads", loc="left")
    save(fig, "fig01_study_area")


def fig_indices(g, roads):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    for ax, col, title in zip(axes, ["boda_suitability", "car_suitability"], ["E-boda suitability index", "E-car suitability index"]):
        basemap(ax, g, roads, labels=ax is axes[0])
        im = layer(ax, g, g[col], CM_BLUE, 0, 100)
        ax.set_title(title, loc="left")
    cbar(fig, axes[1], im, "Index (0–100, percentile-weighted)")
    save(fig, "fig02_suitability_indices")


def fig_robust_hotspots(g, roads):
    gi = pd.read_csv(AN / "getis_ord.csv")
    gg = g.merge(gi[["cell_id", "gi_boda_suitability"]], on="cell_id", how="left")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    basemap(axes[0], gg, roads)
    im = layer(axes[0], gg, gg["boda_top10_robustness"], CM_BLUE, 0, 1)
    axes[0].set_title("Share of 1,000 weight draws placing the cell in the top 10%", loc="left")
    cbar(fig, axes[0], im, "Robustness")
    basemap(axes[1], gg, roads, labels=False)
    z = gg["gi_boda_suitability"]
    im = layer(axes[1], gg, z, CM_DIV, norm=TwoSlopeNorm(0, np.nanmin(z), np.nanmax(z)))
    axes[1].set_title("Getis-Ord Gi* z-score, e-boda suitability", loc="left")
    cbar(fig, axes[1], im, "Gi* z (|z| ≳ 3 significant after FDR)")
    save(fig, "fig03_robustness_hotspots")


def fig_wealth(g, roads):
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    basemap(ax, g, roads)
    im = layer(ax, g, g["housing_wealth_proxy"], CM_BLUE, 0, 1)
    cbar(fig, ax, im, "Housing wealth proxy (rank)")
    ax.set_title("Building-footprint wealth proxy (open space per building + home size)", loc="left")
    save(fig, "fig04_wealth_proxy")


def fig_siting(g, roads, summary):
    sites = pd.read_csv(OUT / "swap_sites_greenfield.csv")
    sp = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326).to_crs(g.crs)
    curves = pd.read_csv(AN / "coverage_curves.csv")
    rnd = pd.read_csv(AN / "coverage_random_baseline.csv")
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.5, 5.4), gridspec_kw={"width_ratios": [1.05, 1]})
    basemap(ax, g, roads)
    rank = g["cover_rank"].where(g["cover_rank"] > 0)
    im = layer(ax, g, rank, LinearSegmentedColormap.from_list("r", BLUE[::-1]), 1, 60)
    ax.scatter(sp.geometry.x, sp.geometry.y, s=14, c=INK, edgecolor="white", linewidth=0.6, zorder=8)
    for _, r in sp.head(10).iterrows():
        ax.annotate(str(r["rank"]), (r.geometry.x, r.geometry.y), xytext=(3, 3), textcoords="offset points", fontsize=6.5, color=INK, zorder=9)
    cbar(fig, ax, im, "Build-order rank of the site that first covers the cell")
    ax.set_title("Greedy swap-network build order (2.5 km by road)", loc="left")

    n = curves["n_sites"]
    bx.fill_between(rnd["n_sites"], 100 * rnd["p2.5"], 100 * rnd["p97.5"], color=INK3, alpha=0.15, lw=0)
    bx.plot(rnd["n_sites"], 100 * rnd["mean"], color=INK3, lw=1.5, ls="--")
    bx.annotate("random sites (95% band)", (rnd["n_sites"].iloc[-1], 100 * rnd["mean"].iloc[-1]), xytext=(-4, -12), textcoords="offset points", ha="right", fontsize=7.5, color=INK2)
    for (col, lab), color in zip([("greedy_1500m", "1.5 km"), ("greedy_2500m", "2.5 km"), ("greedy_3500m", "3.5 km")], [CAT[2], CAT[0], CAT[6]]):
        bx.plot(n, 100 * curves[col], color=color, lw=2)
        bx.annotate(f"greedy, {lab}", (n.iloc[-1], 100 * curves[col].iloc[-1]), xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=INK, va="center")
    bx.plot(n, 100 * curves["greedy_fuel_only_2500m"], color=CAT[1], lw=1.2, ls=":")
    bx.annotate("fuel stations only, 2.5 km", (40, 100 * curves["greedy_fuel_only_2500m"].iloc[39]), xytext=(4, -12), textcoords="offset points", fontsize=7.5, color=INK2)
    for k in (10, 30, 60):
        opt = 100 * summary["coverage"][f"n{k}"]["exact_optimum"]
        bx.scatter([k], [opt], marker="D", s=26, color=INK, zorder=5)
    bx.scatter([], [], marker="D", s=26, color=INK, label="exact MCLP optimum (2.5 km)")
    bx.legend(loc="upper left", fontsize=7.5)
    bx.set_xlabel("Number of swap sites")
    bx.set_ylabel("E-boda demand covered (%)")
    bx.set_xlim(0, 72), bx.set_ylim(0, 100)
    bx.grid(axis="y", color=GRID)
    bx.set_title("Coverage curves and benchmarks", loc="left")
    save(fig, "fig05_siting_coverage")


def fig_site_robustness(g, roads):
    c = pd.read_csv(AN / "candidate_selection_frequency.csv")
    cp = gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(c.lon, c.lat), crs=4326).to_crs(g.crs)
    fig, ax = plt.subplots(figsize=(6.4, 6.2))
    basemap(ax, g, roads)
    sel = cp[cp.selection_frequency > 0]
    ax.scatter(cp.geometry.x, cp.geometry.y, s=3, color=INK3, alpha=0.4, zorder=4)
    sc = ax.scatter(sel.geometry.x, sel.geometry.y, s=10 + 70 * sel.selection_frequency, c=sel.selection_frequency, cmap=CM_BLUE,
                    vmin=0, vmax=1, edgecolor="white", linewidth=0.5, zorder=8)
    cbar(fig, ax, sc, "Selection frequency in 100 weight draws (top 30)")
    ax.set_title("How often each candidate site is chosen when index weights are redrawn", loc="left")
    save(fig, "fig06_site_robustness")


def fig_access(summary):
    a = pd.read_csv(AN / "access_by_network_size.csv")
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 4.2))
    rings = ["core <5 km", "inner 5-10 km", "outer 10-20 km", "peri-urban >20 km"]
    for lvl, color in zip(rings, CAT[:4]):
        d = a[(a.group == "ring") & (a.level == lvl)]
        ax.plot(d.n_sites, 100 * d.share_pop_covered, color=color, lw=2)
        ax.annotate(lvl, (d.n_sites.iloc[-1], 100 * d.share_pop_covered.iloc[-1]), xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=INK, va="center")
        bx.plot(d.n_sites, d.pop_weighted_saving_ugx / 1000, color=color, lw=2)
        bx.annotate(lvl, (d.n_sites.iloc[-1], d.pop_weighted_saving_ugx.iloc[-1] / 1000), xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=INK, va="center")
    al = a[a.group == "all"]
    bx.plot(al.n_sites, al.pop_weighted_saving_ugx / 1000, color=INK, lw=1.2, ls="--")
    bx.annotate("all residents", (al.n_sites.iloc[-1], al.pop_weighted_saving_ugx.iloc[-1] / 1000), xytext=(4, -9), textcoords="offset points", fontsize=7.5, color=INK2)
    bx.axhline(0, color=INK3, lw=0.8)
    bx.axhline(economics.daily_saving(economics.BASE) / 1000, color=INK3, lw=0.8, ls=":")
    bx.annotate("saving with a station on the route", (2, economics.daily_saving(economics.BASE) / 1000), xytext=(0, 4), textcoords="offset points", fontsize=7, color=INK2)
    ax.set(xlabel="Number of swap sites", ylabel="Residents within 2.5 km by road (%)", xlim=(0, 78), ylim=(0, 100))
    bx.set(xlabel="Number of swap sites", ylabel="Rider daily saving, '000 UGX (pop-weighted)", xlim=(0, 78))
    ax.set_title("Coverage by distance from the CBD", loc="left")
    bx.set_title("Rider running-cost saving by distance from the CBD", loc="left")
    for x in (ax, bx):
        x.grid(axis="y", color=GRID)
    save(fig, "fig07_access_by_ring")


def fig_equity():
    a = pd.read_csv(AN / "access_by_network_size.csv")
    lv = ["Q1 (least)", "Q2", "Q3", "Q4", "Q5 (most)"]
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    width = 0.26
    for j, (n, color) in enumerate(zip([10, 30, 60], [BLUE[2], BLUE[4], BLUE[6]])):
        d = a[(a.group == "wealth") & (a.n_sites == n)].set_index("level").reindex(lv)
        x = np.arange(len(lv)) + (j - 1) * width
        ax.bar(x, 100 * d.share_pop_covered, width - 0.03, color=color, label=f"{n} sites")
        for xi, v in zip(x, 100 * d.share_pop_covered):
            ax.text(xi, v + 1, f"{v:.0f}", ha="center", fontsize=6.5, color=INK2)
    ax.set_xticks(np.arange(len(lv)), lv)
    ax.set(ylabel="Residents within 2.5 km by road (%)", ylim=(0, 90))
    ax.set_xlabel("Housing-wealth quintile of the cell (built-up cells)")
    ax.legend(ncol=3, loc="upper right", fontsize=7.5)
    ax.grid(axis="y", color=GRID)
    ax.set_title("Swap-network coverage by housing-wealth quintile", loc="left")
    save(fig, "fig08_equity_wealth")


def fig_economics():
    t = economics.tornado()
    mc = economics.monte_carlo()
    pretty = {"petrol_price_ugx_per_l": "Petrol price", "petrol_km_per_l": "Petrol km/L", "daily_km": "Km per day",
              "swap_price_ugx_per_full": "Swap price", "battery_range_km": "Battery range",
              "petrol_maintenance_ugx_per_day": "Petrol maintenance", "electric_maintenance_ugx_per_day": "E-boda maintenance",
              "rider_earnings_ugx_per_hour": "Rider earnings/hour", "swap_wait_min": "Wait per swap", "detour_speed_kmh": "Detour speed"}
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 4.2))
    base = t["base"].iloc[0] / 1000
    t = t.iloc[::-1]
    for i, r in enumerate(t.itertuples()):
        lo, hi = sorted([r.saving_at_low / 1000, r.saving_at_high / 1000])
        ax.barh(i, hi - lo, left=lo, color=CAT[0], height=0.62)
    ax.set_yticks(range(len(t)), [pretty[p] for p in t.parameter])
    ax.axvline(base, color=INK, lw=1.2)
    ax.set_xlabel("Daily saving, '000 UGX (each input low → high)")
    ax.set_title("One-at-a-time sensitivity", loc="left")
    ax.grid(axis="x", color=GRID)
    bx.hist(mc.saving / 1000, bins=40, color=CAT[0], edgecolor="white", linewidth=0.6)
    for q, lab in zip(mc.saving.quantile([0.05, 0.5, 0.95]) / 1000, ["5%", "median", "95%"]):
        bx.axvline(q, color=INK, lw=1 if lab == "median" else 0.8, ls="-" if lab == "median" else ":")
        bx.annotate(f"{lab}\n{q:.1f}k", (q, bx.get_ylim()[1] * 0.92), ha="center", fontsize=7, color=INK)
    bx.set(xlabel="Daily saving, '000 UGX", ylabel="Draws (of 5,000)")
    bx.set_title("Monte Carlo over all inputs (station on route)", loc="left")
    save(fig, "fig09_economics_uncertainty")


def fig_scenarios():
    s = pd.read_csv(AN / "economics_scenarios.csv")
    p = s.pivot(index="petrol_price", columns="n_sites", values="pop_weighted_saving_ugx").sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    lim = np.abs(p.values).max()
    im = ax.imshow(p.values / 1000, cmap=CM_DIV.reversed(), norm=TwoSlopeNorm(0, -lim / 1000, lim / 1000), aspect="auto")
    for i in range(p.shape[0]):
        for j in range(p.shape[1]):
            v = p.values[i, j] / 1000
            ax.text(j, i, f"{v:+.1f}k", ha="center", va="center", fontsize=9, color="white" if abs(v) > lim / 2000 else INK)
    ax.set_xticks(range(p.shape[1]), [f"{c} sites" for c in p.columns])
    ax.set_yticks(range(p.shape[0]), [f"{int(r):,} UGX/L" for r in p.index])
    ax.spines[:].set_visible(False)
    ax.set_title("Population-weighted rider saving per day", loc="left")
    cbar(fig, ax, im, "'000 UGX")
    save(fig, "fig10_scenarios_petrol_network")


# ---------------------------------------------------------------- animations

def anim_buildout(g, roads):
    sites = pd.read_csv(OUT / "swap_sites_greenfield.csv")
    sp = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326).to_crs(g.crs)
    fig, ax = plt.subplots(figsize=(6.4, 6.6))
    basemap(ax, g, roads)
    x0, y0, x1, y1 = g.total_bounds
    demand = g["pop_2025"] * g["boda_suitability"].fillna(0) / 100
    vmax = np.nanpercentile(demand[g.active == 1], 98)
    im = ax.imshow(grid_array(g, np.full(len(g), np.nan)), origin="lower", extent=(x0, x1, y0, y1), cmap=CM_BLUE, vmin=0, vmax=vmax, zorder=1)
    dots = ax.scatter([], [], s=16, c=INK, edgecolor="white", linewidth=0.6, zorder=8)
    title = ax.set_title("", loc="left")
    big = ax.text(0.02, 0.97, "", transform=ax.transAxes, fontsize=20, fontweight="bold", color=INK, va="top", zorder=9)
    small = ax.text(0.02, 0.89, "", transform=ax.transAxes, fontsize=8, color=INK2, va="top", zorder=9)
    frames = list(range(0, len(sp) + 1)) + [len(sp)] * 12

    def update(k):
        covered = (g["cover_rank"] > 0) & (g["cover_rank"] <= k)
        im.set_data(grid_array(g, np.where(covered, demand, np.nan)))
        dots.set_offsets(np.column_stack([sp.geometry.x[:k], sp.geometry.y[:k]]) if k else np.empty((0, 2)))
        cov = sp["cumulative_coverage_pct"].iloc[k - 1] if k else 0
        big.set_text(f"{cov:.0f}%")
        small.set_text(f"of e-boda demand within 2.5 km by road · {k} swap sites")
        title.set_text("Building a Kampala battery-swap network, one site at a time")
        return im, dots, big, small

    anim = animation.FuncAnimation(fig, update, frames=frames, blit=False)
    anim.save(FIG / "anim_network_buildout.gif", writer=animation.PillowWriter(fps=6), dpi=100)
    plt.close(fig)
    print("wrote anim_network_buildout.gif")


def anim_population(g, roads):
    fig, ax = plt.subplots(figsize=(6.4, 6.6))
    basemap(ax, g, roads)
    x0, y0, x1, y1 = g.total_bounds
    vmax = np.nanpercentile(g["pop_2030"][g.active == 1], 98)
    im = ax.imshow(grid_array(g, g["pop_2020"]), origin="lower", extent=(x0, x1, y0, y1), cmap=CM_ORANGE, vmin=0, vmax=vmax, zorder=1)
    cbar(fig, ax, im, "Residents per km²")
    big = ax.text(0.02, 0.97, "", transform=ax.transAxes, fontsize=20, fontweight="bold", color=INK, va="top", zorder=9)
    small = ax.text(0.02, 0.89, "", transform=ax.transAxes, fontsize=8, color=INK2, va="top", zorder=9)
    ax.set_title("Greater Kampala population, WorldPop 2020 → 2030 (2030 projected)", loc="left")
    years = list(np.linspace(2020, 2030, 41)) + [2030] * 10

    def update(y):
        f = (y - 2020) / 5
        v = g["pop_2020"] + (g["pop_2025"] - g["pop_2020"]) * f if y <= 2025 else g["pop_2025"] + (g["pop_2030"] - g["pop_2025"]) * (f - 1)
        im.set_data(grid_array(g, v))
        big.set_text(f"{int(round(y))}")
        small.set_text(f"{v[g.active == 1].sum() / 1e6:.2f} million residents in scored cells")
        return im, big, small

    anim = animation.FuncAnimation(fig, update, frames=years, blit=False)
    anim.save(FIG / "anim_population_growth.gif", writer=animation.PillowWriter(fps=8), dpi=100)
    plt.close(fig)
    print("wrote anim_population_growth.gif")


def main():
    g, roads = load()
    summary = json.loads((AN / "summary.json").read_text())
    fig_study_area(g, roads)
    fig_indices(g, roads)
    fig_robust_hotspots(g, roads)
    fig_wealth(g, roads)
    fig_siting(g, roads, summary)
    fig_site_robustness(g, roads)
    fig_access(summary)
    fig_equity()
    fig_economics()
    fig_scenarios()
    anim_buildout(g, roads)
    anim_population(g, roads)




# ---------------------------------------------------------------- e-car figures

def fig_car_siting(g, roads, summary):
    sites = pd.read_csv(OUT / "charger_sites_greenfield.csv")
    sp = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326).to_crs(g.crs)
    curves = pd.read_csv(AN / "car_coverage_curves.csv")
    rnd = pd.read_csv(AN / "car_coverage_random_baseline.csv")
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.5, 5.4), gridspec_kw={"width_ratios": [1.05, 1]})
    basemap(ax, g, roads)
    rank = g["car_cover_rank"].where(g["car_cover_rank"] > 0)
    im = layer(ax, g, rank, LinearSegmentedColormap.from_list("r", ORANGE[::-1]), 1, 30)
    ax.scatter(sp.geometry.x, sp.geometry.y, s=22, marker="s", c=INK, edgecolor="white", linewidth=0.6, zorder=8)
    for _, r in sp.head(10).iterrows():
        ax.annotate(str(r["rank"]), (r.geometry.x, r.geometry.y), xytext=(3, 3), textcoords="offset points", fontsize=6.5, color=INK, zorder=9)
    cbar(fig, ax, im, "Build-order rank of the charger that first covers the cell")
    ax.set_title("Greedy e-car DC charging network (5 km by road)", loc="left")
    n = curves["n_sites"]
    bx.fill_between(rnd["n_sites"], 100 * rnd["p2.5"], 100 * rnd["p97.5"], color=INK3, alpha=0.15, lw=0)
    bx.plot(rnd["n_sites"], 100 * rnd["mean"], color=INK3, lw=1.5, ls="--")
    bx.annotate("random sites (95% band)", (rnd["n_sites"].iloc[-1], 100 * rnd["mean"].iloc[-1]), xytext=(-4, -12), textcoords="offset points", ha="right", fontsize=7.5, color=INK2)
    for (col, lab), color in zip([("greedy_3000m", "3 km"), ("greedy_5000m", "5 km"), ("greedy_8000m", "8 km")], [CAT[2], CAT[1], CAT[6]]):
        bx.plot(n, 100 * curves[col], color=color, lw=2)
        bx.annotate(f"greedy, {lab}", (n.iloc[-1], 100 * curves[col].iloc[-1]), xytext=(4, 0), textcoords="offset points", fontsize=7.5, color=INK, va="center")
    for k in (5, 10, 20):
        bx.scatter([k], [100 * summary["car_coverage"][f"n{k}"]["exact_optimum"]], marker="D", s=26, color=INK, zorder=5)
    bx.scatter([], [], marker="D", s=26, color=INK, label="exact MCLP optimum (5 km)")
    bx.legend(loc="lower right", fontsize=7.5)
    bx.set(xlabel="Number of DC charging sites", ylabel="E-car demand covered (%)", xlim=(0, 37), ylim=(0, 100))
    bx.grid(axis="y", color=GRID)
    bx.set_title("Coverage curves and benchmarks", loc="left")
    save(fig, "fig11_car_charger_siting")


def fig_home_charging(g, roads, summary):
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.5, 5.2), gridspec_kw={"width_ratios": [1.2, 1], "wspace": 0.45})
    basemap(ax, g, roads)
    im = layer(ax, g, g["home_charging_potential"], CM_BLUE, 0, 1)
    cbar(fig, ax, im, "Share of households able to charge at home (proxy)")
    ax.set_title("Home-charging potential from building footprints", loc="left")
    hw = summary["home_charging"]["by_wealth"]
    lv = ["Q1 (least)", "Q2", "Q3", "Q4", "Q5 (most)"]
    bx.bar(lv, [100 * hw[k] for k in lv], color=BLUE[4], width=0.6)
    for i, k in enumerate(lv):
        bx.text(i, 100 * hw[k] + 1.5, f"{100 * hw[k]:.0f}%", ha="center", fontsize=7.5, color=INK2)
    bx.set(ylabel="Home-charging potential (%)", ylim=(0, 105), xlabel="Housing-wealth quintile")
    bx.grid(axis="y", color=GRID)
    bx.set_title("Home-charging potential by housing-wealth quintile\n(both derived from footprints, so partly by construction)", loc="left", fontsize=9)
    save(fig, "fig12_home_charging")


def fig_car_economics(summary):
    from emobility import car_economics as ce
    pretty = {"petrol_price_ugx_per_l": "Petrol price", "ice_km_per_l": "Petrol car km/L", "ev_kwh_per_km": "EV kWh/km",
              "home_tariff_ugx_per_kwh": "Home tariff", "public_dc_ugx_per_kwh": "Public DC price", "ice_maint_ugx_per_km": "Petrol maintenance",
              "ev_maint_ugx_per_km": "EV maintenance", "battery_reserve_ugx_per_km": "Battery reserve", "range_per_charge_km": "Km per DC session",
              "dc_session_min": "DC session time", "ev_purchase_premium_ugx": "EV purchase premium", "discount_rate": "Discount rate", "horizon_years": "Holding period"}
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.6))
    for col, (persona, color) in enumerate([("private", CAT[0]), ("ridehail", CAT[1])]):
        mc = ce.monte_carlo(persona)
        ax = axes[0, col]
        ax.hist(mc.npv / 1e6, bins=40, color=color, edgecolor="white", linewidth=0.6)
        ax.axvline(0, color=INK, lw=1.2)
        share = (mc.npv > 0).mean()
        ax.set_title(f"{ce.PERSONAS[persona]['label']}: 5-year NPV of switching (positive in {100 * share:.0f}% of draws)", loc="left", fontsize=9)
        ax.set(xlabel="NPV, million UGX (operating savings minus purchase premium)", ylabel="Draws (of 5,000)")
        t = ce.tornado(persona).head(7).iloc[::-1]
        bx = axes[1, col]
        for i, r in enumerate(t.itertuples()):
            lo, hi = sorted([r.at_low / 1e6, r.at_high / 1e6])
            bx.barh(i, hi - lo, left=lo, color=color, height=0.62)
        bx.set_yticks(range(len(t)), [pretty[p] for p in t.parameter])
        bx.axvline(t["base"].iloc[0] / 1e6, color=INK, lw=1.2)
        bx.axvline(0, color=INK3, lw=0.8, ls=":")
        bx.set_xlabel("NPV, million UGX (each input low → high)")
        bx.set_title("What decides it", loc="left")
        bx.grid(axis="x", color=GRID)
    fig.tight_layout()
    save(fig, "fig13_car_economics")


def fig_equity_compare():
    b = pd.read_csv(AN / "access_by_network_size.csv")
    c = pd.read_csv(AN / "car_access_by_network_size.csv")
    lv = ["Q1 (least)", "Q2", "Q3", "Q4", "Q5 (most)"]
    rings = ["core <5 km", "inner 5-10 km", "outer 10-20 km", "peri-urban >20 km"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, grp, levels, xlabel in ((axes[0], "wealth", lv, "Housing-wealth quintile"), (axes[1], "ring", rings, "Distance from the CBD")):
        bb = b[(b.group == grp) & (b.n_sites == 30)].set_index("level").reindex(levels)
        cc = c[(c.group == grp) & (c.n_sites == 10)].set_index("level").reindex(levels)
        x = np.arange(len(levels))
        ax.bar(x - 0.2, 100 * bb.share_pop_covered, 0.37, color=CAT[0], label="E-boda swap, 30 sites (2.5 km)")
        ax.bar(x + 0.2, 100 * cc.share_pop_covered, 0.37, color=CAT[1], label="E-car DC, 10 sites (5 km)")
        ax.set_xticks(x, levels, fontsize=7.5)
        ax.set(ylabel="Residents covered (%)", ylim=(0, 105), xlabel=xlabel)
        ax.grid(axis="y", color=GRID)
    axes[0].legend(fontsize=7.5, loc="upper right")
    axes[0].set_title("Who each network reaches: wealth", loc="left")
    axes[1].set_title("Who each network reaches: distance from the CBD", loc="left")
    save(fig, "fig14_equity_boda_vs_car")


def fig_car_network_size():
    c = pd.read_csv(AN / "car_access_by_network_size.csv")
    al = c[c.group == "all"]
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.plot(al.n_sites, al.ridehail_saving / 1e6, color=CAT[1], lw=2)
    ax.plot(al.n_sites, al.private_saving / 1e6, color=CAT[0], lw=2)
    ax.annotate("ride-hail / taxi", (al.n_sites.iloc[-1], al.ridehail_saving.iloc[-1] / 1e6), xytext=(4, 0), textcoords="offset points", fontsize=7.5, va="center")
    ax.annotate("private (with local home charging)", (al.n_sites.iloc[-1], al.private_saving.iloc[-1] / 1e6), xytext=(4, 0), textcoords="offset points", fontsize=7.5, va="center")
    ax.set(xlabel="Number of public DC charging sites", ylabel="Annual operating saving, million UGX\n(population-weighted)", xlim=(0, 42))
    ax.grid(axis="y", color=GRID)
    ax.set_title("E-car operating savings as the public charging network grows", loc="left")
    save(fig, "fig15_car_saving_network_size")


def anim_charger_buildout(g, roads):
    sites = pd.read_csv(OUT / "charger_sites_greenfield.csv")
    sp = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326).to_crs(g.crs)
    fig, ax = plt.subplots(figsize=(6.4, 6.6))
    basemap(ax, g, roads)
    x0, y0, x1, y1 = g.total_bounds
    demand = g["pop_2025"] * g["car_suitability"].fillna(0) / 100
    vmax = np.nanpercentile(demand[g.active == 1], 98)
    im = ax.imshow(grid_array(g, np.full(len(g), np.nan)), origin="lower", extent=(x0, x1, y0, y1), cmap=CM_ORANGE, vmin=0, vmax=vmax, zorder=1)
    dots = ax.scatter([], [], s=24, marker="s", c=INK, edgecolor="white", linewidth=0.6, zorder=8)
    ax.set_title("Building a Kampala e-car fast-charging network, one site at a time", loc="left")
    big = ax.text(0.02, 0.97, "", transform=ax.transAxes, fontsize=20, fontweight="bold", color=INK, va="top", zorder=9)
    small = ax.text(0.02, 0.89, "", transform=ax.transAxes, fontsize=8, color=INK2, va="top", zorder=9)
    frames = list(range(0, len(sp) + 1)) + [len(sp)] * 10

    def update(k):
        covered = (g["car_cover_rank"] > 0) & (g["car_cover_rank"] <= k)
        im.set_data(grid_array(g, np.where(covered, demand, np.nan)))
        dots.set_offsets(np.column_stack([sp.geometry.x[:k], sp.geometry.y[:k]]) if k else np.empty((0, 2)))
        big.set_text(f"{sp['cumulative_coverage_pct'].iloc[k - 1] if k else 0:.0f}%")
        small.set_text(f"of e-car demand within 5 km by road · {k} DC charging sites")
        return im, dots, big, small

    animation.FuncAnimation(fig, update, frames=frames).save(FIG / "anim_charger_buildout.gif", writer=animation.PillowWriter(fps=4), dpi=100)
    plt.close(fig)
    print("wrote anim_charger_buildout.gif")


def main_cars():
    g, roads = load()
    summary = json.loads((AN / "summary.json").read_text())
    fig_car_siting(g, roads, summary)
    fig_home_charging(g, roads, summary)
    fig_car_economics(summary)
    fig_equity_compare()
    fig_car_network_size()
    anim_charger_buildout(g, roads)


if __name__ == "__main__":
    main()
    main_cars()
