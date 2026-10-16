"""Bundle outputs/dashboard_data.json + road context into the self-contained dashboard HTML.

Usage:  .venv/bin/python build_dashboard.py   (after run_baseline.py)
"""

import base64
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

import config
from emobility import fetch, remote_sensing as rs

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

# Neighbourhood labels for orientation on the canvas map (approximate centres).
PLACES = {
    "Kampala CBD": (0.3136, 32.5811), "Kololo": (0.330, 32.595), "Nakawa": (0.333, 32.617),
    "Ntinda": (0.354, 32.615), "Kawempe": (0.375, 32.558), "Nansana": (0.364, 32.528),
    "Kira": (0.398, 32.640), "Mukono": (0.353, 32.755), "Entebbe": (0.064, 32.475),
    "Kajjansi": (0.215, 32.550), "Wakiso": (0.404, 32.459), "Gayaza": (0.454, 32.613),
    "Munyonyo": (0.245, 32.620), "Makindye": (0.280, 32.590), "Rubaga": (0.300, 32.553),
    "Bweyogerere": (0.354, 32.665), "Kasangati": (0.440, 32.600), "Namugongo": (0.392, 32.652),
    "Lake Victoria": (0.150, 32.720),
}


def road_lines():
    roads = fetch.fetch_major_roads()
    roads = roads[roads["highway"].isin(["motorway", "trunk", "primary", "secondary"])]
    lines = []
    for geom, hw in zip(roads.geometry.simplify(0.0004), roads["highway"]):
        coords = [[round(y, 4), round(x, 4)] for x, y in geom.coords]
        if len(coords) >= 2:
            lines.append({"c": coords, "major": hw in ("motorway", "trunk", "primary")})
    return lines


def satellite_basemap(width=1600):
    """Sentinel-2 true colour warped to lon/lat over the study bbox, as a JPEG data URI."""
    b = rs.sentinel2()
    rgb = rs.true_colour(b)
    s, w, n, e = config.BBOX
    height = int(width * (n - s) / (e - w))
    dst_tr = from_bounds(w, s, e, n, width, height)
    out = np.zeros((3, height, width), dtype="float32")
    for i in range(3):
        reproject(rgb[:, :, i].astype("float32"), out[i], src_transform=b["transform"], src_crs=config.METRIC_CRS,
                  dst_transform=dst_tr, dst_crs="EPSG:4326", resampling=Resampling.average)
    img = Image.fromarray((np.clip(out.transpose(1, 2, 0), 0, 1) * 255).astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=72, optimize=True)
    return {"uri": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), "bounds": [s, w, n, e],
            "date": b["props"]["datetime"][:10]}


def site_plans():
    def clean(df, cols):
        df = df[[c for c in cols if c in df.columns]].copy()
        df = df.round({c: 5 if c in ("lat", "lon") else 2 for c in df.columns})
        return json.loads(df.replace({np.nan: None}).to_json(orient="records", double_precision=6))

    swap = pd.read_csv(OUT / "gis" / "swap_station_plan.csv")
    chg = pd.read_csv(OUT / "gis" / "charger_station_plan.csv")
    common = ["rank", "name", "site_type", "lat", "lon", "cumulative_coverage_pct", "catchment_pop", "slope_deg",
              "above_valley_floor_m", "site_screen", "dist_substation_m"]
    return {
        "swap": clean(swap, common + ["motorcycles", "swaps_day_10pct", "swaps_day_25pct", "cabinets_25pct", "grid_kw_25pct", "grid_class_25pct"]),
        "charger": clean(chg, common + ["kwh_day_2000cars", "dc_ports_2000cars", "grid_kw_2000cars", "grid_class_2000cars"]),
    }


def main():
    data = json.loads((OUT / "dashboard_data.json").read_text())
    data["roads"] = road_lines()
    data["places"] = [{"name": k, "lat": v[0], "lon": v[1]} for k, v in PLACES.items()]
    data["satellite"] = satellite_basemap()
    data["plans"] = site_plans()
    data["gis_summary"] = json.loads((OUT / "gis" / "summary.json").read_text())
    data["analysis_summary"] = json.loads((OUT / "analysis" / "summary.json").read_text())
    template = (ROOT / "dashboard_template.html").read_text()
    html = template.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    dest = OUT / "kampala_emobility_atlas.html"
    dest.write_text(html)
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    # GitHub Pages site (served from /docs). The template is body content; wrap it in a full document.
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / ".nojekyll").write_text("")
    split = html.index('<div class="wrap">')
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<meta name="description" content="Open-data atlas of electric boda and electric car adoption suitability, '
            'proposed battery-swap and fast-charging sites, and EV economics for Greater Kampala.">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
            'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>'
            + html[:split] + "</head><body>" + html[split:] + "</body></html>")
    (docs / "index.html").write_text(page)
    leaflet = OUT / "kampala_ev_baseline_map.html"
    if leaflet.exists():
        (docs / "map.html").write_text(leaflet.read_text())
    print(f"wrote {docs / 'index.html'}")


if __name__ == "__main__":
    main()
