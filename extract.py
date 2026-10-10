import requests
import json
import time
from typing import Iterator

BASE_URL = "https://myhospitalsapi.aihw.gov.au"
API = f"{BASE_URL}/api/v1"

# Reuse a session for connection pooling
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
})

def _get(path: str, params: dict | None = None, retries: int = 3):
    """GET with basic retry/backoff."""
    url = f"{API}{path}"
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def _paginate(path: str, params: dict | None = None) -> Iterator[dict]:
    """
    Yields items from a paginated endpoint. Handles both:
      - {"data": [...], "pagination": {...}}
      - bare list  (non-paginated endpoints)
    """
    params = dict(params or {})
    skip = 0
    page_size = 1000  # tune based on observed behaviour

    while True:
        params.update({"skip": skip, "take": page_size})
        payload = _get(path, params)

        # Bare list response
        if isinstance(payload, list):
            for item in payload:
                yield item
            return

        # Envelope response
        items = payload.get("data") or payload.get("result") or []
        pg = payload.get("pagination") or {}
        returned = pg.get("results_returned", len(items))
        total = pg.get("total_results_available", len(items))   # default to len, not 0
        
        for item in items:
            yield item

        skip += returned
        if returned == 0 or skip >= total:
            return

        pg = payload.get("pagination") or {}
        returned = pg.get("results_returned", len(items))
        total = pg.get("total_results_available", 0)
        skip += returned

        if returned == 0 or skip >= total:
            return


def extract_reporting_units() -> list[dict]:
    """Hospitals + LHNs + PHNs (dimension table)."""
    return list(_paginate("/reporting-units"))


def extract_measures() -> list[dict]:
    return list(_paginate("/measures"))


def extract_reported_measures() -> list[dict]:
    return list(_paginate("/reported-measures"))


def extract_data_extracts(**filters) -> list[dict]:
    """
    Fact table. Pass filters like reported_measure_code=..., 
    reporting_unit_code=..., data_set_id=...
    """
    return list(_paginate("/data-extracts", params=filters))


if __name__ == "__main__":
    hospitals = extract_reporting_units()
    print(f"Fetched {len(hospitals)} reporting units")
    if hospitals:
        print(json.dumps(hospitals[0], indent=2))
        
        
#test
# 1. Distribution of unit types
from collections import Counter
types = Counter(u["reporting_unit_type"]["reporting_unit_type_code"] for u in hospitals)
print(types)
# Expect: {'H': ~700, 'LHN': ~30, 'PHN': ~31, 'S': ~8, ...}

# 2. How many have coordinates (needed for Leaflet)?
with_coords = sum(1 for u in hospitals if u.get("latitude") and u.get("longitude"))
print(f"{with_coords}/{len(hospitals)} have coordinates")

# 3. How many are private vs public?
print("Private:", sum(1 for u in hospitals if u.get("private")))
print("Closed:",  sum(1 for u in hospitals if u.get("closed")))