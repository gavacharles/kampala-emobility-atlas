#!/usr/bin/env bash
# Rebuild every output, figure, map, animation and the website from scratch.
# First run downloads ~1 GB of open data (cached in data/raw/); see README "Data".
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

$PY -W ignore run_baseline.py      # indices, siting, economics -> outputs/
$PY -W ignore run_analysis.py      # spatial statistics, exact MCLP, robustness, equity -> outputs/analysis/
$PY -W ignore run_gis.py           # remote sensing, terrain, grid, catchments, operations -> outputs/gis/
$PY -W ignore make_figures.py      # paper figures + GIF animations -> figures/
$PY -W ignore make_gis_maps.py     # GIS / satellite / terrain / infrastructure maps -> figures/
$PY -W ignore make_social.py       # question-led social animations (GIF + MP4) and Substack cover -> figures/
$PY -W ignore build_dashboard.py   # interactive atlas -> outputs/ and docs/ (GitHub Pages)
