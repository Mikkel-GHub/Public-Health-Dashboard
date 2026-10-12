
import sqlite3
from pathlib import Path

database_path = Path(__file__).resolve().parent / "data" / "health.db"

with sqlite3.connect(database_path) as conn:

    # Count hospital records
    count = conn.execute(
        "SELECT COUNT(*) FROM hospitals"
    ).fetchone()[0]

    print("Hospitals in database:", count)

    # Display first five hospitals
    rows = conn.execute("""
        SELECT hospital_id, hospital_name, latitude, longitude
        FROM hospitals
        LIMIT 5
    """).fetchall()

    for row in rows:
        print(row)
