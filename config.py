"""Study area, grid and index settings for the Phase 1 baseline.

Everything that encodes a judgement call (weights, radii) lives here so it can be
reviewed and changed without touching the pipeline code.
"""

# Greater Kampala Metropolitan Area (approximate envelope: Kampala, Wakiso, Mukono,
# Entebbe, Mpigi fringe). (south, west, north, east) in WGS84.
BBOX = (0.03, 32.35, 0.55, 32.85)

# UTM zone 36N: metric CRS for distances and areas.
METRIC_CRS = "EPSG:32636"

CELL_SIZE_M = 1000

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Operators whose names identify e-motorcycle battery-swap or EV charging sites in OSM, matched
# as whole words. Deliberately excludes Umeme (the grid utility: thousands of transformers/poles)
# and Kiira (matches "Kiira Road"); add Kiira Motors sites via data/manual/ev_stations.csv.
EV_OPERATOR_PATTERN = "(^|[^a-z])(Spiro|Zembo|Gogo|Bodawerk|Roam|Ampersand|Ecobodaa?|Battery Swap|Swap Station)([^a-z]|$)"

# Point layers counted per cell. Each value is an Overpass filter applied to nodes, ways and relations.
POI_LAYERS = {
    "ev_station": [
        '["amenity"="charging_station"]',
        f'["name"~"{EV_OPERATOR_PATTERN}",i][!"highway"][!"power"]',
        f'["brand"~"{EV_OPERATOR_PATTERN}",i][!"highway"][!"power"]',
        f'["operator"~"{EV_OPERATOR_PATTERN}",i][!"highway"][!"power"]',
    ],
    "fuel": ['["amenity"="fuel"]'],
    "market": ['["amenity"="marketplace"]'],
    "shop": ['["shop"]'],
    "transport_hub": [
        '["amenity"~"^(bus_station|taxi|motorcycle_parking)$"]',
        '["public_transport"="station"]',
    ],
    "education": ['["amenity"~"^(university|college|school)$"]'],
    "health": ['["amenity"~"^(hospital|clinic)$"]'],
    "bank": ['["amenity"~"^(bank|atm|bureau_de_change)$"]'],
    "office": ['["office"]'],
    "parking": ['["amenity"="parking"]'],
    "car_trade": ['["shop"~"^(car|car_repair|car_parts)$"]'],
    "food_drink": ['["amenity"~"^(restaurant|cafe|fast_food|bar)$"]'],
}

MAJOR_ROADS = "motorway|trunk|primary|secondary|tertiary"

# Suitability indices. Each feature is percentile-ranked (0-1) across cells before weighting,
# so weights express relative importance, not units. Weights in each index sum to 1.
# These are expert-judgement priors, NOT fitted to adoption data; see outputs/*robustness* for how
# much the rankings depend on them.
BODA_WEIGHTS = {
    "pop_density_2025": 0.20,  # where riders and passengers live
    "trip_generators_density": 0.20,  # shops, markets, food, education, health
    "major_road_km": 0.15,
    "transport_hub_density": 0.10,
    "fuel_density": 0.10,  # proxy for existing motorised activity
    "centrality": 0.10,  # closeness to the CBD and to activity overall
    "pop_growth_2020_2025": 0.15,  # where demand is emerging
}

CAR_WEIGHTS = {
    "housing_wealth_proxy": 0.25,  # larger residential footprints (Microsoft building footprints)
    "affluence_proxy_density": 0.15,  # banks, offices, cafes/restaurants
    "major_road_km": 0.15,
    "centrality": 0.10,
    "car_trade_density": 0.10,
    "parking_density": 0.10,
    "pop_growth_2020_2025": 0.10,
    "fuel_density": 0.05,
}

# Weight-sensitivity analysis: weights are redrawn from a Dirichlet centred on the values above.
# Higher concentration = smaller perturbations (40 gives roughly +/-0.05 on a 0.15 weight).
SENSITIVITY_DRAWS = 1000
SENSITIVITY_CONCENTRATION = 40
SENSITIVITY_TOP_SHARE = 0.10  # robustness = share of draws in which a cell is in the top 10%

# Kampala CBD reference point (Constitution Square area) for the centrality feature.
CBD_LATLON = (0.3136, 32.5811)

# Infrastructure-gap scoring: a cell with an EV station within this distance counts as fully served.
SERVED_DISTANCE_M = 1000
# Beyond this distance the access penalty is at its maximum.
UNSERVED_DISTANCE_M = 5000

# A cell is scored ("active") if it has mapped activity or a major road, or enough residents.
# The population criterion keeps under-mapped peri-urban settlements in the analysis.
MIN_ACTIVITY_FOR_SCORING = 1
MIN_POP_FOR_SCORING = 500  # people per km2 (WorldPop 2025)

# Greenfield battery-swap siting (maximal coverage, greedy).
# Demand weight per cell = 2025 population x boda suitability / 100.
SITING_CANDIDATE_LAYERS = ["fuel", "market", "transport_hub"]  # sites that can plausibly host a swap cabinet
SITING_CANDIDATE_DEDUP_M = 250  # merge candidates closer than this
SITING_COVER_ROAD_M = 2500  # a cell is covered if a site is within this distance along the road network
SITING_MAX_SITES = 60
# E-car public charging siting. Most e-car charging happens at home; public DC chargers serve
# ride-hail/taxi fleets and households without off-street parking, so reach is longer and networks smaller.
# Demand weight per cell = 2025 population x car suitability / 100.
CAR_SITING_CANDIDATE_LAYERS = ["fuel", "parking", "car_trade"]  # forecourts, car parks (malls, offices), dealers
CAR_SITING_COVER_ROAD_M = 5000
CAR_SITING_MAX_SITES = 30
CAR_ECONOMICS_NETWORK_SIZES = [5, 10, 20]

# Network sizes for which per-cell rider economics are mapped (first N sites of the build order).
ECONOMICS_NETWORK_SIZES = [10, 30, 60]
# When a verified station inventory exists, set True to treat known stations as already built.
SITING_INCLUDE_EXISTING = False
