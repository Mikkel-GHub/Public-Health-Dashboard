"""Quick checks on the measure tables after running pipeline.py."""
import sqlite3
from pathlib import Path

import pandas as pd

db = Path(__file__).resolve().parent / "data" / "health.db"

with sqlite3.connect(db) as conn:
    for table in ("measure_categories", "measures", "reported_measures", "measure_values"):
        n = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"{table:<20} {n} rows")

    values = pd.read_sql("SELECT * FROM measure_values", conn)
    hospitals = pd.read_sql("SELECT hospital_id FROM hospitals", conn)

print("\nColumns in measure_values:")
print(values.columns.tolist())

orphans = ~values["reporting_unit_code"].isin(hospitals["hospital_id"])
print(f"\nRows with no matching hospital: {orphans.sum()} (should be 0)")
print(f"Hospitals with at least one value: {values['reporting_unit_code'].nunique()}")

if "is_suppressed" in values.columns:
    print(f"Suppressed values: {values['is_suppressed'].mean():.1%}")

print("\nSample rows:")
print(values.head())