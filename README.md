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
| Social animations and Substack cover | `make_social.py` | `figures/social/q*.gif`, `figures/social/q*.mp4`, `figures/cover_substack.png` |
| Interactive atlas and website | `build_dashboard.py` | `outputs/kampala_emobility_atlas.html`, `docs/` |

All weights, radii and thresholds are in [`config.py`](config.py). Economic inputs and sources are in [`emobility/economics.py`](emobility/economics.py) (e-bodas) and [`emobility/car_economics.py`](emobility/car_economics.py) (e-cars).

## Licence and citation

Code: MIT ([LICENSE](LICENSE)). Derived data inherit source licences, including ODbL for OpenStreetMap and Microsoft footprints ([DATA_LICENSE.md](DATA_LICENSE.md)). Please cite using [CITATION.cff](CITATION.cff).

Contains modified Copernicus Sentinel data (2026) and Copernicus DEM data. © OpenStreetMap contributors. Population: WorldPop (CC BY 4.0). Building footprints © Microsoft (ODbL).
