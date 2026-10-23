"""Social-media animations (square GIF for Substack/LinkedIn, MP4 for X) and the Substack cover image.

Usage:  .venv/bin/python make_social.py   (after make_figures.py and make_gis_maps.py)
Writes figures/social/q*.gif, figures/social/q*.mp4 and figures/cover_substack.png.

Each animation opens on a question, animates the answer from the model outputs, and ends on a
punchline card. Every frame carries the data sources and "Credit: Gava Charles".
"""

import json
import textwrap
from pathlib import Path

import geopandas as gpd
import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

import config  # noqa: E402
from emobility import car_economics as ce, economics, operations, remote_sensing as rs  # noqa: E402
from make_figures import (BLUE, BUILDINGS, CAT, CM_BLUE, CREDIT, INK, INK2, INK3, MODEL, ORANGE, OSM, PLACES, PRICES,  # noqa: E402
                          S2, WORLDPOP, basemap, grid_array, load)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
SOC = ROOT / "figures" / "social"
ATLAS = "gavacharles.github.io/kampala-emobility-atlas"
FPS = 12
SIZE_IN, DPI = 6.0, 180          # 1080 x 1080 px
GIF_PX = 720                     # GIFs are downscaled to keep them small enough for Substack
GOOD, BAD, BG = "#1baf7a", "#e34948", "white"
WORLD_BANK = "World Bank (2026)"
URA = "URA import data via Daily Monitor (2024)"


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def footer_text(sources):
    line = "Data: " + "; ".join(sources) + ".   " + CREDIT + "   ·   " + ATLAS
    return "\n".join(textwrap.wrap(line, 118))


def chrome(fig, question, sources, sub=None):
    """Question header, optional subhead and the source/credit footer shared by every frame."""
    fig.patch.set_facecolor(BG)
    fig.text(0.05, 0.955, "\n".join(textwrap.wrap(question, 34)), fontsize=21, fontweight="bold", color=INK, va="top")
    if sub:
        fig.text(0.05, 0.835, "\n".join(textwrap.wrap(sub, 80)), fontsize=9.5, color=INK2, va="top", linespacing=1.3)
    fig.add_artist(Line2D([0.05, 0.95], [0.062, 0.062], color="#dfe2e0", lw=0.8))
    fig.text(0.05, 0.05, footer_text(sources), fontsize=5.6, color=INK3, va="top", linespacing=1.35)


def punchline(fig, lines, color=INK):
    """Answer card over the last frames, sized to its text."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts, y = [], 0.66
    for i, text in enumerate(lines):
        size, weight, width = (20, "bold", 26) if i == 0 else (12, "normal", 50)
        t = fig.text(0.5, y, "\n".join(textwrap.wrap(text, width)), ha="center", va="top", fontsize=size, fontweight=weight,
                     color=color if i == 0 else INK, zorder=51, linespacing=1.25)
        h = t.get_window_extent(renderer).height / fig.bbox.height
        y -= h + 0.035
        texts.append(t)
    top, bottom = 0.66 + 0.035, y + 0.01
    box = FancyBboxPatch((0.07, bottom), 0.86, top - bottom, boxstyle="round,pad=0.012,rounding_size=0.02", transform=fig.transFigure,
                         fc="white", ec=color, lw=2, alpha=0.97, zorder=50)
    fig.add_artist(box)
    return [box, *texts]


def grab(fig):
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()


def write(name, frames):
    """frames: list of (rgb array, n_repeats). GIF merges holds into longer frame durations; MP4 repeats frames."""
    SOC.mkdir(parents=True, exist_ok=True)
    ms = 1000 / FPS
    imgs = [Image.fromarray(f).resize((GIF_PX, GIF_PX), Image.LANCZOS).quantize(colors=192, method=Image.MEDIANCUT, dither=Image.NONE)
            for f, _ in frames]
    imgs[0].save(SOC / f"{name}.gif", save_all=True, append_images=imgs[1:], duration=[int(ms * n) for _, n in frames], loop=0,
                 optimize=True, disposal=1)
    h, w = frames[0][0].shape[:2]
    writer = imageio_ffmpeg.write_frames(str(SOC / f"{name}.mp4"), (w, h), fps=FPS, codec="libx264", pix_fmt_out="yuv420p",
                                         macro_block_size=8, quality=8)
    writer.send(None)
    for f, n in frames:
        for _ in range(n):
            writer.send(np.ascontiguousarray(f))
    writer.close()
    print(f"wrote social/{name}.gif ({(SOC / f'{name}.gif').stat().st_size / 1e6:.1f} MB) and .mp4")


def new_fig():
    return plt.figure(figsize=(SIZE_IN, SIZE_IN), dpi=DPI)


def run(name, setup, n, hold_start=FPS, hold_end=FPS * 4, answer=None, answer_color=INK):
    """setup(fig) -> update(i); frames 0..n-1; question-only hold at the start, punchline card held at the end."""
    fig = new_fig()
    update = setup(fig)
    frames = []
    update(0)
    frames.append((grab(fig), hold_start))
    for i in range(1, n):
        update(i)
        frames.append((grab(fig), 1))
    frames.append((grab(fig), FPS))
    if answer:
        punchline(fig, answer, answer_color)
        frames.append((grab(fig), hold_end))
    plt.close(fig)
    write(name, frames)


# ---------------------------------------------------------------- Q1: where would you put 60 swap stations?

def q1_where_60_stations(g, roads):
    plan = pd.read_csv(OUT / "gis" / "swap_station_plan.csv")
    sp = gpd.GeoDataFrame(plan, geometry=gpd.points_from_xy(plan.lon, plan.lat), crs=4326).to_crs(g.crs)
    fuel = (plan.site_type == "fuel").to_numpy()
    demand = g["pop_2025"] * g["boda_suitability"].fillna(0) / 100
    vmax = np.nanpercentile(demand[g.active == 1], 98)
    n_sites = len(sp)

    def setup(fig):
        chrome(fig, "Where would you put Kampala's first 60 battery-swap stations?", (OSM, WORLDPOP, MODEL),
               "A computer adds one site at a time, each time reaching the most riders within 2.5 km by road")
        ax = fig.add_axes([0.03, 0.08, 0.94, 0.68])
        basemap(ax, g, roads)
        x0, y0, x1, y1 = g.total_bounds
        im = ax.imshow(grid_array(g, np.full(len(g), np.nan)), origin="lower", extent=(x0, x1, y0, y1), cmap=CM_BLUE, vmin=0, vmax=vmax, zorder=1)
        dots_f = ax.scatter([], [], s=30, c=ORANGE[3], edgecolor="white", lw=0.7, zorder=8)
        dots_o = ax.scatter([], [], s=30, c=INK, edgecolor="white", lw=0.7, zorder=8)
        big = fig.text(0.62, 0.78, "", fontsize=30, fontweight="bold", color=BLUE[5], va="top")
        small = fig.text(0.62, 0.72, "", fontsize=9, color=INK2, va="top")
        fuel_t = fig.text(0.62, 0.655, "", fontsize=9, color=ORANGE[4], va="top", fontweight="bold")
        ax.legend(handles=[Line2D([], [], marker="o", ls="", color=ORANGE[3], label="at a petrol station"),
                           Line2D([], [], marker="o", ls="", color=INK, label="market or transport hub")],
                  loc="lower right", fontsize=7.5, frameon=True, facecolor="white", edgecolor="none")

        def update(k):
            covered = (g["cover_rank"] > 0) & (g["cover_rank"] <= k)
            im.set_data(grid_array(g, np.where(covered, demand, np.nan)))
            xy = np.column_stack([sp.geometry.x[:k], sp.geometry.y[:k]]) if k else np.empty((0, 2))
            f = fuel[:k]
            dots_f.set_offsets(xy[f] if k else xy)
            dots_o.set_offsets(xy[~f] if k else xy)
            cov = plan["cumulative_coverage_pct"].iloc[k - 1] if k else 0
            big.set_text(f"{cov:.0f}%")
            small.set_text(f"of e-boda demand reached\nwith {k} stations")
            fuel_t.set_text(f"{f.sum()} of {k} at petrol stations" if k else "")
        return update

    final_cov = plan["cumulative_coverage_pct"].iloc[-1]
    run("q1_where_60_stations", setup, n_sites + 1,
        answer=[f"{fuel.sum()} of {n_sites} are petrol stations.",
                f"Together they reach {final_cov:.0f}% of e-boda demand. Forecourts are where a swap network naturally lands.",
                "Should fuel retailers host the swap, or lose the rider?"], answer_color=ORANGE[4])


# ---------------------------------------------------------------- Q2: does it still pay 20 km out?

def q2_does_it_pay_far_out():
    a = pd.read_csv(OUT / "analysis" / "access_by_network_size.csv")
    rings = ["core <5 km", "inner 5-10 km", "outer 10-20 km", "peri-urban >20 km"]
    labels = ["Under 5 km", "5–10 km", "10–20 km", "Over 20 km"]
    curves = {r: a[(a.group == "ring") & (a.level == r)].sort_values("n_sites") for r in rings}
    ns = np.arange(1, 61)
    vals = {r: np.interp(ns, curves[r].n_sites, curves[r].pop_weighted_saving_ugx) for r in rings}
    route = economics.daily_saving(economics.BASE)

    def setup(fig):
        chrome(fig, "Does an electric boda still pay 20 km from the city centre?", (OSM, WORLDPOP, BUILDINGS, PRICES, MODEL),
               "Average daily saving for riders, by how far from the CBD they live, as the swap network grows")
        ax = fig.add_axes([0.20, 0.15, 0.72, 0.54])
        bars = ax.barh(range(4), [0] * 4, height=0.6, color=GOOD)
        ax.set_yticks(range(4), labels, fontsize=11, color=INK)
        ax.invert_yaxis()
        ax.set_xlim(-6500, 6500)
        ax.axvline(0, color=INK, lw=1)
        ax.axvline(route, color=INK3, lw=0.8, ls=":")
        ax.text(route, 3.75, "station on\nyour route", fontsize=7, color=INK2, ha="center", va="top")
        ax.set_xticks([-6000, -3000, 0, 3000, 6000], ["−6,000", "−3,000", "0", "+3,000", "+6,000"], fontsize=8)
        ax.set_xlabel("UGX per day vs petrol (negative = loses money)", fontsize=8.5, color=INK2)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
        texts = [ax.text(0, i, "", va="center", fontsize=10, fontweight="bold") for i in range(4)]
        big = fig.text(0.05, 0.725, "", fontsize=13, fontweight="bold", color=INK)

        def update(i):
            n = ns[min(i, len(ns) - 1)]
            for j, r in enumerate(rings):
                v = vals[r][n - 1]
                bars[j].set_width(v)
                bars[j].set_color(GOOD if v >= 0 else BAD)
                texts[j].set_position((v + (250 if v >= 0 else -250), j))
                texts[j].set_ha("left" if v >= 0 else "right")
                texts[j].set_text(f"{v:+,.0f}")
                texts[j].set_color(GOOD if v >= 0 else BAD)
            big.set_text(f"{n} swap stations")
        return update

    far = vals["peri-urban >20 km"]
    run("q2_does_it_pay_far_out", setup, len(ns),
        answer=["Only if the network reaches you.",
                f"Beyond 20 km, a rider loses about UGX {abs(far[9]):,.0f} a day with 10 stations, because of trips to swap. "
                f"With 60 stations they gain about UGX {far[59]:,.0f}.",
                "Who pays for stations where commercial networks arrive last?"], answer_color=BAD)


# ---------------------------------------------------------------- Q3: who does going electric pay off for?

def q3_who_pays_off():
    boda = (economics.monte_carlo().saving > 0).mean()
    taxi = (ce.monte_carlo("ridehail").npv > 0).mean()
    priv = (ce.monte_carlo("private").npv > 0).mean()
    groups = [("Boda rider", boda, "daily saving, station on route"), ("Taxi / ride-hail car", taxi, "5-year NPV, 180 km/day"),
              ("Private car", priv, "5-year NPV, 40 km/day")]
    rng = np.random.default_rng(3)
    orders = [rng.permutation(100) for _ in groups]
    n = 50

    def setup(fig):
        chrome(fig, "Going electric in Uganda: who actually comes out ahead?", (PRICES, URA, MODEL),
               "5,000 simulations each, with fuel, power, price and usage assumptions varied")
        squares, counters = [], []
        for c, (label, share, note) in enumerate(groups):
            ax = fig.add_axes([0.05 + c * 0.31, 0.17, 0.28, 0.42])
            ax.set_xlim(-0.5, 9.5), ax.set_ylim(-0.5, 9.5)
            ax.set_aspect("equal"), ax.axis("off")
            sq = [ax.add_patch(Rectangle((k % 10 - 0.42, k // 10 - 0.42), 0.84, 0.84, color="#eceeec")) for k in range(100)]
            squares.append(sq)
            fig.text(0.05 + c * 0.31 + 0.14, 0.73, label, ha="center", fontsize=11, fontweight="bold", color=INK)
            fig.text(0.05 + c * 0.31 + 0.14, 0.70, note, ha="center", fontsize=7, color=INK3)
            counters.append(fig.text(0.05 + c * 0.31 + 0.14, 0.61, "", ha="center", fontsize=24, fontweight="bold"))
        fig.text(0.05, 0.12, "■ comes out ahead", color=GOOD, fontsize=9, fontweight="bold")
        fig.text(0.30, 0.12, "■ loses money", color=BAD, fontsize=9, fontweight="bold")

        def update(i):
            t = ease(i / (n - 1))
            for sq, order, (_, share, _), cnt in zip(squares, orders, groups, counters):
                shown = int(round(100 * t))
                wins = int(round(100 * share))
                for rank, k in enumerate(order):
                    sq[k].set_color("#eceeec" if rank >= shown else (GOOD if rank < wins else BAD))
                cnt.set_text(f"{100 * share * t:.0f}%")
                cnt.set_color(GOOD if share > 0.8 else "#c48a00")
        return update

    run("q3_who_pays_off", setup, n,
        answer=[f"Bodas {100 * boda:.0f}%. Taxis {100 * taxi:.0f}%. Private cars {100 * priv:.0f}%.",
                "Electric pays for vehicles that work all day. For a family car it is a coin flip, decided by the purchase price, "
                "which a 25% import duty pushes up.",
                "Should incentives start with taxi fleets?"], answer_color=GOOD)


# ---------------------------------------------------------------- Q4: who can charge at home?

def q4_who_can_charge_at_home(summary):
    hw = summary["home_charging"]["by_wealth"]
    lv = ["Q1 (least)", "Q2", "Q3", "Q4", "Q5 (most)"]
    names = ["Least\nwealthy", "", "", "", "Most\nwealthy"]
    vals = np.array([100 * hw[k] for k in lv])
    n = 36

    def setup(fig):
        chrome(fig, "Who in Kampala could charge an electric car at home?", (BUILDINGS, OSM, MODEL),
               "Share of households with room to park and charge, from satellite-derived building outlines")
        ax = fig.add_axes([0.10, 0.21, 0.82, 0.50])
        bars = ax.bar(range(5), [0] * 5, width=0.62, color=[BLUE[1], BLUE[2], BLUE[3], BLUE[4], BLUE[6]])
        ax.set_xticks(range(5), [f"{q.split()[0]}\n{nm}" if nm else q for q, nm in zip(lv, names)], fontsize=9)
        ax.set_ylim(0, 105)
        ax.set_yticks([])
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.set_xlabel("Neighbourhoods grouped into fifths by housing wealth", fontsize=8.5, color=INK2)
        texts = [ax.text(i, 0, "", ha="center", fontsize=15, fontweight="bold", color=INK) for i in range(5)]

        def update(i):
            t = ease(i / (n - 1))
            for b, tx, v, k in zip(bars, texts, vals, range(5)):
                b.set_height(v * t)
                tx.set_position((k, v * t + 2))
                tx.set_text(f"{v * t:.0f}%")
        return update

    run("q4_who_can_charge_at_home", setup, n,
        answer=[f"{vals[0]:.0f}% vs {vals[-1]:.0f}%.",
                "Charging at home is the cheapest way to run an electric car, worth about UGX 1.6 million a year. "
                "It is mostly open to households that are already well off.",
                "Who are public chargers for, then?"], answer_color=BLUE[5])


# ---------------------------------------------------------------- Q5: can the grid keep up?

def q5_can_the_grid_keep_up(g, roads):
    plan = pd.read_csv(OUT / "gis" / "swap_station_plan.csv")
    gs = json.loads((OUT / "gis" / "summary.json").read_text())
    sp = gpd.GeoDataFrame(plan, geometry=gpd.points_from_xy(plan.lon, plan.lat), crs=4326).to_crs(g.crs)
    colors = {"LV supply": GOOD, "dedicated transformer": BLUE[3], "MV connection": BAD}
    stages = [10, 25, 50]
    seq = [(0, 0)]
    prev = 0
    for s in stages:                               # (adoption %, stage whose grid class is shown)
        seq += [(prev + (s - prev) * ease(k / 17), prev) for k in range(1, 18)] + [(s, s)] * 14
        prev = s
    mw_per_pct = gs["ops_swap"]["25pct"]["grid_mw_total"] / 25

    def setup(fig):
        chrome(fig, "If Kampala's bodas go electric, can the grid keep up?", (OSM, WORLDPOP, MODEL, WORLD_BANK),
               "Peak power for the 60 proposed swap stations, and the grid connection each one would need")
        ax = fig.add_axes([0.03, 0.08, 0.94, 0.68])
        basemap(ax, g, roads)
        dots = ax.scatter(sp.geometry.x, sp.geometry.y, s=10, c=INK3, edgecolor="white", lw=0.6, zorder=8)
        ax.legend(handles=[Line2D([], [], marker="o", ls="", color=c, label=k) for k, c in colors.items()],
                  loc="lower right", fontsize=7.5, frameon=True, facecolor="white", edgecolor="none", title="Connection needed", title_fontsize=7.5)
        big = fig.text(0.60, 0.78, "", fontsize=28, fontweight="bold", color=INK, va="top")
        small = fig.text(0.60, 0.72, "", fontsize=9, color=INK2, va="top")
        mv = fig.text(0.60, 0.665, "", fontsize=9.5, color=BAD, va="top", fontweight="bold")

        def update(i):
            a, stage = seq[i]
            big.set_text(f"{a * mw_per_pct:.1f} MW")
            small.set_text(f"peak load with {a:.0f}% of\nmotorcycles electric")
            if stage:
                cls = plan[f"grid_class_{stage}pct"]
                dots.set_color([colors[c] for c in cls])
                dots.set_sizes(8 + plan[f"grid_kw_{stage}pct"] / 5)
                mv.set_text(f"{(cls == 'MV connection').sum()} sites need medium voltage")
            else:
                mv.set_text("")
        return update

    run("q5_can_the_grid_keep_up", setup, len(seq),
        answer=[f"At 25%: {gs['ops_swap']['25pct']['grid_mw_total']:.1f} MW, and {gs['grid_class_swap']['25pct']['MV connection']} sites need medium voltage.",
                "Putting a station within reach of most riders concentrates load on a few inner-city sites. "
                "The World Bank projects EVs could add 60–99 MW to Uganda's peak.",
                "Who pays for the connections?"], answer_color=BAD)


# ---------------------------------------------------------------- Q6: what happens to the petrol station?

def q6_petrol_station():
    plan = pd.read_csv(OUT / "gis" / "swap_station_plan.csv")
    fuel = plan[plan.site_type == "fuel"]
    litres_per_boda = economics.BASE["daily_km"] / economics.BASE["petrol_km_per_l"]
    fleet = operations.GKMA_MOTORCYCLES
    swaps_per_pct = fuel["swaps_day_25pct"].sum() / 25
    ad = np.concatenate([np.linspace(0, 50, 40), [50] * 6])

    def setup(fig):
        chrome(fig, "When bodas go electric, what happens to the petrol station?", (PRICES, WORLD_BANK, MODEL),
               f"Greater Kampala's {fleet:,} motorcycles burn about {litres_per_boda:.1f} litres a day each")
        ax = fig.add_axes([0.08, 0.20, 0.84, 0.46])
        ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
        ax.text(0.0, 0.93, "Petrol no longer sold", fontsize=11, fontweight="bold", color=BAD)
        ax.text(0.0, 0.45, "Swaps a day at the 53 forecourt sites", fontsize=11, fontweight="bold", color=BLUE[4])
        bar1 = ax.add_patch(Rectangle((0, 0.70), 0, 0.14, color=BAD))
        bar2 = ax.add_patch(Rectangle((0, 0.22), 0, 0.14, color=BLUE[4]))
        t1 = ax.text(0, 0.62, "", fontsize=16, fontweight="bold", color=BAD, va="top")
        t2 = ax.text(0, 0.14, "", fontsize=16, fontweight="bold", color=BLUE[4], va="top")
        big = fig.text(0.05, 0.72, "", fontsize=13, fontweight="bold", color=INK)
        max_l = fleet * 0.5 * litres_per_boda
        max_s = swaps_per_pct * 50

        def update(i):
            a = ad[min(i, len(ad) - 1)]
            litres = fleet * a / 100 * litres_per_boda
            swaps = swaps_per_pct * a
            bar1.set_width(litres / max_l)
            bar2.set_width(swaps / max_s)
            t1.set_text(f"{litres:,.0f} litres a day  (≈ UGX {litres * economics.BASE['petrol_price_ugx_per_l'] / 1e9:.1f} bn)")
            t2.set_text(f"{swaps:,.0f} rider visits a day")
            big.set_text(f"{a:.0f}% of motorcycles electric")
        return update

    run("q6_petrol_station", setup, len(ad),
        answer=["Host the swap, or lose the rider.",
                "The boda litres go either way. A forecourt that hosts swaps keeps riders coming, who still buy airtime, "
                "mobile money, tyres and food. Cars and trucks will need petrol for years.",
                "Will Uganda's fuel retailers move first?"], answer_color=ORANGE[4])


# ---------------------------------------------------------------- cover image

def cover():
    b = rs.sentinel2()
    rgb = rs.true_colour(b)
    tr = b["transform"]
    ext = (tr.c, tr.c + tr.a * rgb.shape[1], tr.f + tr.e * rgb.shape[0], tr.f)
    swap = pd.read_csv(OUT / "swap_sites_greenfield.csv")
    chg = pd.read_csv(OUT / "charger_sites_greenfield.csv")
    to = lambda d: gpd.GeoSeries(gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(config.METRIC_CRS)  # noqa: E731
    sw, ch = to(swap), to(chg)
    cbd = gpd.GeoSeries(gpd.points_from_xy([PLACES["CBD"][1]], [PLACES["CBD"][0]]), crs=4326).to_crs(config.METRIC_CRS).iloc[0]

    fig = plt.figure(figsize=(14.56, 10.48), dpi=100, facecolor="#0f1012")    # 1456 x 1048, Substack's 14:10 header
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(rgb, extent=ext, zorder=0)
    ax.scatter(sw.x, sw.y, s=60, c=CAT[0], edgecolor="white", lw=1.0, zorder=5)
    ax.scatter(ch.x, ch.y, s=70, marker="s", c=CAT[1], edgecolor="white", lw=1.0, zorder=5)
    half_h, half_w = 15000, 15000 * 14.56 / 10.48
    cx = min(cbd.x + 9000, ext[1] - half_w)
    cy = min(max(cbd.y, ext[2] + half_h), ext[3] - half_h)
    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(cy - half_h, cy + half_h)
    ax.axis("off")
    ax.set_aspect("auto")
    grad = np.linspace(1, 0, 400)[None, :] ** 1.4
    ax.imshow(np.dstack([np.full((1, 400, 3), 0.06), grad[..., None] * 0.92]), extent=(*ax.get_xlim(), *ax.get_ylim()), aspect="auto", zorder=6)
    fig.text(0.05, 0.80, "TWO ELECTRIC\nREVOLUTIONS", fontsize=54, fontweight="bold", color="white", va="top", linespacing=1.0)
    fig.text(0.05, 0.58, "Why Uganda's bodas are going electric\nand its cars are not", fontsize=24, color="#dde3ea", va="top", linespacing=1.2)
    fig.text(0.05, 0.42, "350+", fontsize=40, fontweight="bold", color="#6da7ec", va="top")
    fig.text(0.05, 0.355, "battery-swap stations by late 2025", fontsize=13, color="white", va="top")
    fig.text(0.29, 0.42, "17", fontsize=40, fontweight="bold", color="#f29a72", va="top")
    fig.text(0.29, 0.355, "fully electric cars imported,\n2022 to April 2024", fontsize=13, color="white", va="top")
    fig.text(0.05, 0.23, "●  proposed swap station     ■  proposed fast charger", fontsize=12, color="white", va="top")
    src = "\n".join(textwrap.wrap(f"Data: {S2}; {OSM}; {WORLDPOP}; {WORLD_BANK}; {URA}; {MODEL}.", 110))
    fig.text(0.05, 0.10, f"{src}\n{CREDIT}", fontsize=10.5, color="#d5dae0", va="top", linespacing=1.4)
    with plt.rc_context({"savefig.bbox": "standard"}):    # exact 1456 x 1048, no tight padding
        fig.savefig(ROOT / "figures" / "cover_substack.png", dpi=100, facecolor="#0f1012")
    plt.close(fig)
    print("wrote cover_substack.png")


def main():
    g, roads = load()
    summary = json.loads((OUT / "analysis" / "summary.json").read_text())
    cover()
    q1_where_60_stations(g, roads)
    q2_does_it_pay_far_out()
    q3_who_pays_off()
    q4_who_can_charge_at_home(summary)
    q5_can_the_grid_keep_up(g, roads)
    q6_petrol_station()


if __name__ == "__main__":
    main()
