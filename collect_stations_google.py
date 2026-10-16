"""Collect e-boda swap / EV charging stations in Greater Kampala from the Google Places API (New).

Usage:
    export GOOGLE_MAPS_API_KEY=...        # key with "Places API (New)" enabled
    .venv/bin/python collect_stations_google.py

Writes data/manual/ev_stations_google.csv, which run_baseline.py merges into the station layer.

Cost: Text Search (Pro fields) is billed per request. 16 tiles x len(QUERIES) queries x up to 3 pages
is at most ~500 requests (typically far fewer, as most tiles return one page).
Terms: Google allows storing place IDs indefinitely but latitude/longitude only for up to 30 days;
re-run this script to refresh rather than treating the CSV as a permanent dataset.
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import config

OUT = Path(__file__).resolve().parent / "data" / "manual" / "ev_stations_google.csv"
ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.types,places.businessStatus,nextPageToken"

QUERIES = {
    "Spiro": "Spiro battery swap station",
    "Zembo": "Zembo battery swap",
    "Gogo": "Gogo Electric swap station",
    "Roam": "Roam electric motorcycle",
    "Bodawerk": "Bodawerk",
    "Kiira Motors": "Kiira Motors charging",
    "generic swap": "electric motorcycle battery swap",
    "generic charging": "electric vehicle charging station",
}
# A result is kept only if its name matches one of these (Google returns loosely related places).
NAME_FILTER = re.compile(
    r"\b(spiro|zembo|gogo electric|roam|bodawerk|kiira|swap|charging|charge point|ev charg|e-?mobility)\b", re.I
)
TILES_PER_SIDE = 4


def tiles():
    s, w, n, e = config.BBOX
    dy, dx = (n - s) / TILES_PER_SIDE, (e - w) / TILES_PER_SIDE
    for i in range(TILES_PER_SIDE):
        for j in range(TILES_PER_SIDE):
            yield (s + i * dy, w + j * dx, s + (i + 1) * dy, w + (j + 1) * dx)


def search(key: str, text: str, tile, page_token=None) -> dict:
    body = {
        "textQuery": text,
        "pageSize": 20,
        "locationRestriction": {
            "rectangle": {
                "low": {"latitude": tile[0], "longitude": tile[1]},
                "high": {"latitude": tile[2], "longitude": tile[3]},
            }
        },
    }
    if page_token:
        body["pageToken"] = page_token
    # curl rather than requests: macOS system Python's LibreSSL fails modern TLS handshakes.
    proc = subprocess.run(
        ["curl", "-s", "--max-time", "60", "-X", "POST", ENDPOINT,
         "-H", "Content-Type: application/json", "-H", f"X-Goog-Api-Key: {key}",
         "-H", f"X-Goog-FieldMask: {FIELDS}", "-d", json.dumps(body)],
        capture_output=True, text=True,
    )
    data = json.loads(proc.stdout or "{}")
    if "error" in data:
        raise RuntimeError(data["error"].get("message"))
    return data


def main():
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        sys.exit("Set GOOGLE_MAPS_API_KEY (Google Cloud key with Places API (New) enabled).")

    found, requests_made = {}, 0
    for operator, text in QUERIES.items():
        for tile in tiles():
            token = None
            for _ in range(3):  # Places returns at most 60 results (3 pages) per query
                data = search(key, text, tile, token)
                requests_made += 1
                for p in data.get("places", []):
                    name = p.get("displayName", {}).get("text", "")
                    if not NAME_FILTER.search(name) or p.get("businessStatus") == "CLOSED_PERMANENTLY":
                        continue
                    found.setdefault(p["id"], {
                        "name": name,
                        "operator": operator if not operator.startswith("generic") else "",
                        "station_type": "charging" if "charg" in name.lower() else "swap",
                        "lat": p["location"]["latitude"],
                        "lon": p["location"]["longitude"],
                        "address": p.get("formattedAddress", ""),
                        "source": "google_places",
                        "place_id": p["id"],
                        "verified_on": date.today().isoformat(),
                    })
                token = data.get("nextPageToken")
                if not token:
                    break
                time.sleep(2)  # page tokens take a moment to become valid

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["name", "operator", "station_type", "lat", "lon", "address", "source", "place_id", "verified_on"]
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(found.values())
    print(f"{requests_made} requests; {len(found)} stations written to {OUT}")


if __name__ == "__main__":
    main()
