# kampala-emobility-atlas

Python analysis and static website for an open-data atlas of electric boda and electric car adoption in Greater Kampala: suitability scoring, battery-swap and fast-charger siting, GIS and satellite screening, economics and equity.

Interactive atlas: https://gavacharles.github.io/kampala-emobility-atlas/ · Leaflet map: https://gavacharles.github.io/kampala-emobility-atlas/map.html

## Layout

| Path | What it is |
|---|---|
| `emobility/` | Package: data fetch, features, population, buildings, network, index, infrastructure, remote sensing, mapping, economics (e-boda and e-car), operations, analysis |
| `run_baseline.py` | Suitability, siting and economics → `outputs/` |
| `run_analysis.py` | Spatial statistics, exact MCLP, robustness, equity → `outputs/analysis/` |
| `run_gis.py` | Remote sensing, terrain, grid, catchments, operations → `outputs/gis/` |
| `make_figures.py`, `make_gis_maps.py`, `make_social.py` | Figures, GIS maps and social animations → `figures/` (not tracked) |
| `build_dashboard.py`, `dashboard_template.html` | Interactive atlas → `outputs/kampala_emobility_atlas.html` and `docs/` |
| `collect_stations_google.py` | Optional station collection helper |
| `config.py` | All weights, radii and thresholds |
| `run_all.sh` | Runs the full pipeline |
| `data/manual/ev_stations.csv` | Manually recorded stations |
| `outputs/` | Result tables and GeoPackages |
| `docs/` | GitHub Pages site |
| `papers/`, `outreach/` | Draft manuscripts and post notes |

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run_all.sh
```

Economic inputs and their sources are in `emobility/economics.py` (e-bodas) and `emobility/car_economics.py` (e-cars); values marked *ASSUMPTION* are placeholders.

## Licence and citation

Code: MIT ([LICENSE](LICENSE)). Derived data inherit source licences, including ODbL for OpenStreetMap and Microsoft footprints ([DATA_LICENSE.md](DATA_LICENSE.md)). Cite using [CITATION.cff](CITATION.cff).

Contains modified Copernicus Sentinel data (2026) and Copernicus DEM data. © OpenStreetMap contributors. Population: WorldPop (CC BY 4.0). Building footprints © Microsoft (ODbL).
