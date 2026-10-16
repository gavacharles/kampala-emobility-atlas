"""Download OpenStreetMap layers for the study area via Overpass, with on-disk caching."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point

import config

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
USER_AGENT = "kampala-emobility-research/0.1"


def _overpass(query: str) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"overpass_{hashlib.sha1(query.encode()).hexdigest()[:12]}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    last_error = None
    for attempt in range(6):
        for url in config.OVERPASS_URLS:
            # curl rather than requests: macOS system Python links LibreSSL 2.8, which fails
            # the TLS handshake with overpass-api.de.
            proc = subprocess.run(
                ["curl", "-s", "-A", USER_AGENT, "--max-time", "900", "-w", "\n%{http_code}",
                 "--data-urlencode", f"data={query}", url],
                capture_output=True, text=True,
            )
            body, _, status = proc.stdout.rpartition("\n")
            if proc.returncode == 0 and status == "200":
                data = json.loads(body)
                cache.write_text(body)
                time.sleep(2)  # be polite to the shared public server
                return data
            last_error = f"{url} -> curl exit {proc.returncode}, HTTP {status}"
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Overpass query failed: {last_error}")


def _bbox_str() -> str:
    s, w, n, e = config.BBOX
    return f"{s},{w},{n},{e}"


def fetch_pois(layer: str) -> gpd.GeoDataFrame:
    """Return one point per OSM feature matching any of the layer's filters."""
    bbox = _bbox_str()
    parts = "".join(f"nwr{f}({bbox});" for f in config.POI_LAYERS[layer])
    data = _overpass(f"[out:json][timeout:240];({parts});out center tags;")

    rows = []
    for el in data.get("elements", []):
        if "lat" in el:
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        tags = el.get("tags", {})
        rows.append(
            {
                "osm_id": f"{el['type']}/{el['id']}",
                "name": tags.get("name"),
                "operator": tags.get("operator") or tags.get("brand"),
                "layer": layer,
                "geometry": Point(lon, lat),
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326") if rows else _empty_points(layer)
    return gdf.drop_duplicates("osm_id")


def _empty_points(layer: str) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"osm_id": [], "name": [], "operator": [], "layer": []}, geometry=[], crs="EPSG:4326"
    )


def fetch_major_roads() -> gpd.GeoDataFrame:
    query = f'[out:json][timeout:240];way["highway"~"^({config.MAJOR_ROADS})$"]({_bbox_str()});out geom tags;'
    data = _overpass(query)
    rows = []
    for el in data.get("elements", []):
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(coords) >= 2:
            rows.append({"highway": el.get("tags", {}).get("highway"), "geometry": LineString(coords)})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
