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
        params.update({"skip": skip, "top": page_size})
        payload = _get(path, params)

        # Bare list response
        if isinstance(payload, list):
            for item in payload:
                yield item
            return

        # Handle nested envelope: {"result": {"data": [...], "pagination": {...}}}
        if isinstance(payload.get("result"), dict):
            inner = payload["result"]
            items = inner.get("data") or []
            pg = inner.get("pagination") or {}
        else:
            # Flat envelope: {"result": [...]} or {"data": [...], "pagination": {...}}
            items = payload.get("data") or payload.get("result") or []
            pg = payload.get("pagination") or {}
        returned = pg.get("results_returned", len(items))
        total = pg.get("total_results_available", len(items))   # default to len, not 0
        
        for item in items:
            yield item

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


def extract_measure_categories() -> list[dict]:
    """The 12 category codes that group related measures."""
    return list(_paginate("/measure-categories"))


def extract_flat_data_extracts(
    category_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """
    Fetch ALL fact rows for one measure category.

    Args:
        category_code: e.g. "MYH-ED-WAITS" (from extract_measure_categories)
        start_date:    optional ISO date, e.g. "2024-01-01"
        end_date:      optional ISO date, e.g. "2026-12-31"

    Returns:
        List of fact dicts. No filtering — raw rows for the category.
    """
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return list(_paginate(f"/flat-data-extract/{category_code}", params=params))


def extract_all_flat_data_extracts(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, list[dict]]:
    """
    Fetch fact rows for ALL 12 categories.
    Returns a dict keyed by category code.
    """
    categories = extract_measure_categories()
    return {
        cat["measure_category_code"]: extract_flat_data_extracts(
            cat["measure_category_code"], start_date, end_date
        )
        for cat in categories
    }


if __name__ == "__main__":
    # --- Sanity check: reporting units ---
    hospitals = extract_reporting_units()
    print(f"Reporting units: {len(hospitals)}")

    # --- Sanity check: measures and reported measures ---
    measures = extract_measures()
    reported = extract_reported_measures()
    print(f"Measures: {len(measures)}")
    print(f"Reported measures: {len(reported)}")

    # --- Sanity check: measure categories ---
    categories = extract_measure_categories()
    print(f"Measure categories: {len(categories)}")
    for c in categories:
        print(f"  {c['measure_category_code']:<20} {c['measure_category_name']}")

    # --- Sanity check: ONE category of fact data ---
    print("\nFetching MYH-ED-WAITS (date-filtered to 2024+)...")
    ed_rows = extract_flat_data_extracts("MYH-ED-WAITS", start_date="2024-01-01")
    print(f"  Rows: {len(ed_rows)}")
    if ed_rows:
        r0 = ed_rows[0]
        print(f"  First row sample:")
        print(f"    reporting_unit_name: {r0.get('reporting_unit_name')}")
        print(f"    measure_name:        {r0.get('measure_name')}")
        print(f"    value:               {r0.get('value')}")
        print(f"    data_period:         {r0.get('data_period')}")