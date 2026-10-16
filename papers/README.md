# Papers

Two manuscripts are drafted from this repository. Every number in them comes from the pipeline
outputs (`outputs/analysis/summary.json`, `outputs/gis/summary.json` and the CSVs beside them), and every reference has
been checked against Crossref or the publisher page.

| | Paper 1 | Paper 2 |
|---|---|---|
| File | [paper1_siting_open_data.md](paper1_siting_open_data.md) | [paper2_economics_equity.md](paper2_economics_equity.md) |
| Question | Where should e-boda swap stations and e-car fast chargers go, how good is the siting, what do sites need from terrain and grid, and who do the networks reach? | How do the economics of e-bodas and e-cars vary across the city, and what network size, fuel price and vehicle use make electrification pay, for whom? |
| Core methods | Suitability indices with Dirichlet robustness; Moran's I and Gi* with FDR; greedy vs exact MCLP (HiGHS) on a 15,868 km road graph; Sentinel-2/DEM/wetland/grid site screening; concentration index | Rider daily cost model with detours and queueing; e-car 5-year NPV for private and ride-hail use; Monte Carlo and tornado; spatial coupling to network size; petrol-price × network scenarios |
| First-choice journal | Journal of Transport Geography | Energy for Sustainable Development |
| Alternatives | Computers, Environment and Urban Systems; Transportation Research Part D | Energy Policy; Transport Policy |
| Main figures | fig01–fig06, fig11, fig14, gis01–gis10 | fig07, fig09, fig10, fig12, fig13, fig15 |

The two papers cite each other and share the same data and networks; they do not overlap in
results. Paper 1 owns siting, robustness, site screening and coverage equity; Paper 2 owns
economics and the distribution of savings.

## What reviewers at these journals are likely to ask, and how to strengthen each paper

Q1 acceptance is not guaranteed by the analysis alone. These are the gaps a careful reviewer
will raise, in rough order of importance, with what would close them.

1. **No ground-truth adoption or demand data.** Both papers rest on suitability proxies.
   *Strengthen with:* any operator data (swap volumes by station, even aggregated monthly), or a
   validation of the e-boda index against the locations of existing Spiro/Zembo/Gogo stations
   (`collect_stations_google.py` or a field survey). A simple test, such as whether existing stations
   sit in higher-index cells than random points, would be a strong addition to Paper 1.
2. **Assumed economic inputs.** Paper 2 flags maintenance, earnings, waiting time, public DC price
   and the EV purchase premium as assumptions. *Strengthen with:* a short structured survey of
   50–150 boda riders (daily km, fuel spend, maintenance, swap waits) and quotes from 3–5 car
   importers. This is the single biggest upgrade for Paper 2.
3. **Position against Kimuli et al. (2026).** Both drafts cite it; read the full paper and add a
   short comparison table (data, methods, scope, findings).
4. **Literature depth.** Each draft has a focused reference list. Add 10–20 references from a
   structured search (Scopus/Web of Science) on battery-swap location, two-wheeler electrification
   in Africa and Asia, and charging equity.
5. **Travel time instead of distance.** Reviewers may ask for congestion-aware access. An optional
   extension is to weight road classes by typical speeds.
6. **Author details.** Add affiliation, funding, ORCID, and (if co-authors join) CRediT roles.

## Submission checklist

- [ ] Convert to the journal template (Word or LaTeX). With pandoc installed: `pandoc paper1_siting_open_data.md -o paper1.docx`.
- [ ] Figures: 300 dpi PNGs are in `../figures/`. Some journals want TIFF/EPS; re-export with `savefig(..., format="tiff")`.
- [ ] Graphical abstract: `../figures/gis01_satellite_proposed_networks.png` (Paper 1) and `../figures/fig07_access_by_ring.png` (Paper 2) work well.
- [ ] Data availability: cite the repository with a Zenodo DOI. Connect the GitHub repo to Zenodo and create a release to mint one.
- [ ] Preprint (optional): SSRN, EarthArXiv or arXiv (physics.soc-ph) before submission.
- [ ] Suggested reviewers: authors of the cited Kampala and Kenya studies, and of the EV-equity and facility-location papers.
