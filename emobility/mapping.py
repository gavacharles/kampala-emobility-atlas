"""Interactive Leaflet map of the baseline indices."""

import folium
import geopandas as gpd
import numpy as np
from branca.colormap import LinearColormap

import config

BLUES = ["#f7fbff", "#6baed6", "#08306b"]
ORANGES = ["#fff5eb", "#fd8d3c", "#7f2704"]
GREENS = ["#f7fcf5", "#74c476", "#00441b"]

# (column, label, shown on load, palette, fixed vmax or None for the 98th percentile)
LAYERS = [
    ("boda_suitability", "E-boda suitability index (0-100)", True, BLUES, 100),
    ("car_suitability", "E-car suitability index (0-100)", False, BLUES, 100),
    ("boda_top10_robustness", "E-boda: share of weightings in top 10%", False, GREENS, 1),
    ("car_top10_robustness", "E-car: share of weightings in top 10%", False, GREENS, 1),
    ("pop_density_2025", "Population per km2, 2025 (WorldPop est.)", False, ORANGES, None),
    ("pop_growth_2020_2025", "Population added per km2, 2020-25 (WorldPop est.)", False, ORANGES, None),
    ("pop_growth_2025_2030", "Population added per km2, 2025-30 (WorldPop proj.)", False, ORANGES, None),
    ("boda_gap", "E-boda gap — PROVISIONAL, station inventory incomplete", False, BLUES, 100),
    ("car_gap", "E-car gap — PROVISIONAL, station inventory incomplete", False, BLUES, 100),
]

TOOLTIP_FIELDS = [
    "cell_id",
    "boda_suitability",
    "car_suitability",
    "boda_top10_robustness",
    "car_top10_robustness",
    "pop_density_2025",
    "pop_growth_2020_2025",
]


def build_map(g: gpd.GeoDataFrame, stations: gpd.GeoDataFrame, sites: gpd.GeoDataFrame, path) -> None:
    s, w, n, e = config.BBOX
    m = folium.Map(location=[(s + n) / 2, (w + e) / 2], zoom_start=11, tiles="CartoDB positron")
    cells = g[g["active"]].to_crs("EPSG:4326").copy()
    for col in {c for c, *_ in LAYERS} | set(TOOLTIP_FIELDS[1:]):
        cells[col] = cells[col].replace(np.inf, np.nan).round(2)

    for col, label, show, colors, vmax in LAYERS:
        vmax = vmax if vmax is not None else float(np.nanpercentile(cells[col].clip(lower=0), 98))
        cmap = LinearColormap(colors, vmin=0, vmax=vmax, caption=label)
        props = list(dict.fromkeys(TOOLTIP_FIELDS + [col]))
        layer = folium.FeatureGroup(name=label, show=show)
        folium.GeoJson(
            cells[props + ["geometry"]].to_json(),
            style_function=lambda f, col=col, cmap=cmap, vmax=vmax: {
                "fillColor": cmap(min(max(f["properties"][col], 0), vmax))
                if f["properties"][col] is not None
                else "#cccccc",
                "fillOpacity": 0.6,
                "weight": 0,
            },
            tooltip=folium.GeoJsonTooltip(fields=props),
        ).add_to(layer)
        layer.add_to(m)

    site_layer = folium.FeatureGroup(name=f"Proposed swap sites (greedy, {config.SITING_COVER_ROAD_M} m by road)", show=True)
    for _, r in sites.to_crs("EPSG:4326").iterrows():
        folium.Marker(
            [r.geometry.y, r.geometry.x],
            icon=folium.DivIcon(
                html=f'<div style="background:#08306b;color:#fff;border-radius:9px;font:11px sans-serif;'
                f'width:18px;height:18px;line-height:18px;text-align:center">{r["rank"]}</div>'
            ),
            popup=f"#{r['rank']} {r['name'] or 'unnamed'} ({r['site_type']})<br>"
            f"adds {r['marginal_demand_pct']}% demand, cumulative {r['cumulative_coverage_pct']}%",
        ).add_to(site_layer)
    site_layer.add_to(m)

    st_layer = folium.FeatureGroup(name=f"Known EV / swap stations in OSM ({len(stations)})", show=True)
    for _, r in stations.to_crs("EPSG:4326").iterrows():
        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=5,
            color="#d94801",
            fill=True,
            popup=f"{r.get('name') or 'unnamed'} ({r.get('operator') or 'operator unknown'})",
        ).add_to(st_layer)
    st_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(path))
