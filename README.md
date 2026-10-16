# Kampala E-Mobility Atlas

**Where electric bodas and electric cars can take hold in Greater Kampala, where their battery-swap stations and fast chargers should go, what each site needs, and who the networks serve. Built entirely from open data.**

🗺️ **Interactive atlas:** https://gavacharles.github.io/kampala-emobility-atlas/
🍃 **Leaflet map with all layers:** https://gavacharles.github.io/kampala-emobility-atlas/map.html
📄 **Papers (drafts):** [papers/](papers/) · ✍️ **Posts:** [outreach/](outreach/)

| Swap network build-out | Fast-charger build-out | Population 2020 → 2030 |
|---|---|---|
| ![](figures/anim_network_buildout.gif) | ![](figures/anim_charger_buildout.gif) | ![](figures/anim_population_growth.gif) |

> Scores are **suitability indices**, not adoption probabilities. No operator data were used; only 3 swap/charging stations are mapped in OpenStreetMap, so the proposed networks are greenfield designs. Economic inputs marked *ASSUMPTION* in the code are the first things to replace with survey data.

## Headline results

| | E-bodas (battery swapping) | E-cars (DC fast charging) |
|---|---|---|
| Most suitable areas | Bwaise–Kawempe–Mulago–Wandegeya–Kisenyi–Katwe band | CBD, Nakasero, Kololo, Kamwokya |
| Proposed network | 60 swap sites (53 at fuel stations) | 30 fast-charging sites (21 fuel stations, 9 car parks) |
| Coverage | 28% / 55% / 75% of demand within 2.5 km by road with 10 / 30 / 60 sites | 44% / 62% / 81% of demand within 5 km with 5 / 10 / 20 sites |
| Distance from optimal | Within 1.3–2.7 points of the exact MCLP optimum (HiGHS) | Within 1.8–3.0 points |
| Economics | UGX 5,903/day saving with a station on the route; 2,029 / 3,849 / 4,489 across the city with 10 / 30 / 60 sites | Ride-hail repays a UGX 12M premium in ~8 months (96% chance of positive 5-yr NPV); private car 52% |
| Who's left out | Peri-urban riders lose UGX 3,552/day with 10 sites; coverage 93% in the core vs 11% beyond 20 km | No coverage beyond 20 km with 10 sites; home charging concentrated in the wealthiest areas |
| Grid | 17.5 MW and 21 medium-voltage connections at 25% motorcycle electrification | 5.9 MW and 98 ports for 2,000 e-ride-hail cars |

## Proposed locations

Every proposed site has coordinates, a build-order rank, its catchment by road, daily demand, equipment and grid connection, slope and height above the valley floor:

- [`outputs/gis/swap_station_plan.csv`](outputs/gis/swap_station_plan.csv): 60 e-boda swap sites
- [`outputs/gis/charger_station_plan.csv`](outputs/gis/charger_station_plan.csv): 30 e-car fast-charging sites
- [`outputs/gis/kampala_emobility_gis.gpkg`](outputs/gis/kampala_emobility_gis.gpkg): all GIS layers for QGIS/ArcGIS (grid scores and environment, proposed sites, power lines and points, wetlands)

![Central Kampala: proposed sites on Sentinel-2 imagery](figures/gis02_satellite_central_kampala.png)

## Maps and figures

**GIS, satellite, terrain and infrastructure**

| | |
|---|---|
| ![](figures/gis01_satellite_proposed_networks.png) Satellite overview, both networks | ![](figures/gis03_remote_sensing_indices.png) NDVI, NDBI, MNDWI (Sentinel-2) |
| ![](figures/gis04_terrain_elevation_slope.png) Elevation and slope (Copernicus DEM) | ![](figures/gis05_flood_wetland_screen.png) Flood and wetland screen |
| ![](figures/gis06_power_infrastructure.png) Grid infrastructure and connection needs | ![](figures/gis07_swap_catchments.png) Swap catchments and throughput |
| ![](figures/gis08_charger_catchments.png) Charger catchments and ports | ![](figures/gis09_road_network.png) Road network |

**Analysis**

| | |
|---|---|
| ![](figures/fig02_suitability_indices.png) Suitability indices | ![](figures/fig03_robustness_hotspots.png) Robustness and Gi* hot spots |
| ![](figures/fig05_siting_coverage.png) Swap siting vs exact optimum | ![](figures/fig11_car_charger_siting.png) Charger siting vs exact optimum |
| ![](figures/fig07_access_by_ring.png) Access and saving by ring | ![](figures/fig14_equity_boda_vs_car.png) Who each network reaches |
| ![](figures/fig13_car_economics.png) E-car NPV: private vs ride-hail | ![](figures/fig10_scenarios_petrol_network.png) Petrol price × network size |

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# one-off downloads (see "Data" below), then:
./run_all.sh
```

| Step | Script | Output |
|---|---|---|
| Suitability, siting, economics | `run_baseline.py` | `outputs/` |
| Spatial statistics, exact MCLP, robustness, equity | `run_analysis.py` | `outputs/analysis/` |
| Remote sensing, terrain, grid, catchments, operations | `run_gis.py` | `outputs/gis/` |
| Paper figures and GIFs | `make_figures.py` | `figures/fig*.png`, `figures/anim_*.gif` |
| GIS maps | `make_gis_maps.py` | `figures/gis*.png` |
| Interactive atlas and website | `build_dashboard.py` | `outputs/kampala_emobility_atlas.html`, `docs/` |

All weights, radii and thresholds are in [`config.py`](config.py). Economic inputs and sources are in [`emobility/economics.py`](emobility/economics.py) (e-bodas) and [`emobility/car_economics.py`](emobility/car_economics.py) (e-cars).

### Data

OpenStreetMap layers, the Sentinel-2 scene and the Copernicus DEM are fetched and cached automatically. Two large files need a one-off download, because the WorldPop server is slow and doesn't support resuming:

```bash
mkdir -p data/raw/worldpop data/raw/buildings
for y in 2020 2025 2030; do curl -L -o data/raw/worldpop/uga_pop_$y.tif \
  "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/$y/UGA/v1/100m/constrained/uga_pop_${y}_CN_100m_R2025A_v1.tif"; done
curl -L -o data/raw/buildings/ms_buildings_122323332.csv.gz \
  "https://minedbuildings.z5.web.core.windows.net/global-buildings/2026-02-03/global-buildings.geojsonl/RegionName=Uganda/quadkey=122323332/part-00106-4feead82-d499-422b-94cb-c036c212127a.c000.csv.gz"
```

macOS's system Python links an old LibreSSL that can't reach the Overpass API, so the pipeline calls `curl` for HTTP.

### Adding real stations

1. **Google Maps (Places API):** `export GOOGLE_MAPS_API_KEY=...` then `.venv/bin/python collect_stations_google.py`. Google's terms limit caching coordinates to 30 days, so the output is git-ignored.
2. **By hand or field survey:** add rows to [`data/manual/ev_stations.csv`](data/manual/ev_stations.csv).

Then set `SITING_INCLUDE_EXISTING = True` in `config.py` so new sites fill gaps around existing ones.

## Method in brief

- **Grid:** 1 km cells in UTM 36N; 1,968 scored cells, 6.45 million residents.
- **Indices:** weighted percentile ranks; 1,000 Dirichlet weight redraws for robustness; Moran's I and Getis–Ord Gi* with FDR control; validated against Sentinel-2 NDBI/NDVI.
- **Proxies:** housing wealth and home-charging potential from open space per building and home size in 1.2 million building footprints. Building size alone failed validation, because merged informal roofs looked like mansions.
- **Siting:** greedy maximal coverage on a 652,196-node road graph, benchmarked against exact MCLP optima (SciPy HiGHS), random networks and a fuel-station-only pool, with robustness to the weights.
- **Screening:** slope ≤ 8°, ≥ 3 m above the local valley floor (HAND-like), outside mapped wetlands, and grid connection class graded by peak load.
- **Operations:** road-network catchments; swaps/day, cabinets and MW under 10/25/50% motorcycle electrification; DC ports for 500/2,000/5,000 e-ride-hail cars.
- **Economics:** e-boda daily running cost with detour and queue costs; e-car 5-year NPV for private and ride-hail use; Monte Carlo (5,000 draws), tornado sensitivity, petrol-price × network-size scenarios.

## Licence and citation

Code: MIT ([LICENSE](LICENSE)). Derived data inherit source licences, including ODbL for OpenStreetMap and Microsoft footprints ([DATA_LICENSE.md](DATA_LICENSE.md)). Please cite using [CITATION.cff](CITATION.cff).

Contains modified Copernicus Sentinel data (2026) and Copernicus DEM data. © OpenStreetMap contributors. Population: WorldPop (CC BY 4.0). Building footprints © Microsoft (ODbL).
