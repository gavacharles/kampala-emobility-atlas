# Data sources, licences and attribution

The code in this repository is MIT-licensed (see `LICENSE`). The derived data in `outputs/`,
`figures/` and `docs/` combine the sources below and inherit their terms. In particular, any
database derived from OpenStreetMap or the Microsoft building footprints is shared under the
**Open Database License (ODbL) 1.0**, and you must keep that licence and the attributions if you reuse it.

| Source | Used for | Licence / terms | Attribution |
|---|---|---|---|
| OpenStreetMap (via Overpass API) | Roads and routing graph, points of interest, fuel stations, power lines, substations, transformers, wetlands | ODbL 1.0 | © OpenStreetMap contributors |
| WorldPop Global2 R2025A, constrained 100 m (2020, 2025, 2030) | Population, growth | CC BY 4.0 | WorldPop (www.worldpop.org), University of Southampton |
| Microsoft Global ML Building Footprints (2026-02 release) | Wealth and home-charging proxies | ODbL 1.0 | © Microsoft |
| Copernicus Sentinel-2 L2A, scene S2A_36NVF_20260629 (Element 84 Earth Search, AWS) | Satellite imagery, NDVI, NDBI, MNDWI | Copernicus free, full and open data policy | Contains modified Copernicus Sentinel data (2026) |
| Copernicus DEM GLO-30 (tile N00 E032) | Elevation, slope, valley-floor flood screen | Copernicus DEM licence (free use with attribution) | © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA; all rights reserved |
| Published prices and statistics (fuel, tariffs, swap prices, EV imports) | Economics model inputs | Cited in `emobility/economics.py`, `emobility/car_economics.py` and the papers | See those files |

Google Places results produced by `collect_stations_google.py` are **not** included and must
not be committed: Google's terms allow caching coordinates for at most 30 days.
