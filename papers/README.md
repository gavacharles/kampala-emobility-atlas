# Papers

Two manuscripts are drafted from this repository. Every number in them comes from the pipeline
outputs (`outputs/analysis/summary.json`, `outputs/gis/summary.json` and the CSVs beside them), and every reference has
been checked against Crossref or the publisher page.

| | Paper 1 | Paper 2 |
|---|---|---|
| File | [paper1_siting_open_data.md](paper1_siting_open_data.md) | [paper2_economics_equity.md](paper2_economics_equity.md) |
| Question | Where should e-boda swap stations and e-car fast chargers go, how good is the siting, what do sites need from terrain and grid, and who do the networks reach? | How do the economics of e-bodas and e-cars vary across the city, and what network size, fuel price and vehicle use make electrification pay, for whom? |
| Core methods | Suitability indices with Dirichlet robustness; Moran's I and Gi* with FDR; greedy vs exact MCLP (HiGHS) on a 15,868 km road graph; Sentinel-2/DEM/wetland/grid site screening; concentration index | Rider daily cost model with detours and queueing; e-car 5-year NPV for private and ride-hail use; Monte Carlo and tornado; spatial coupling to network size; petrol-price × network scenarios |
| Main figures | fig01–fig06, fig11, fig14, gis01–gis10 | fig07, fig09, fig10, fig12, fig13, fig15 |

The two papers cite each other and share the same data and networks; they do not overlap in
results. Paper 1 owns siting, robustness, site screening and coverage equity; Paper 2 owns
economics and the distribution of savings.
