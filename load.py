
import sqlite3
from pathlib import Path


def load_hospitals(df):
    """Load transformed hospital data into SQLite."""

    # Create a data folder if it doesn't exist
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Database location
    database_path = data_dir / "health.db"

    # Connect to SQLite
    with sqlite3.connect(database_path) as conn:

        # Load DataFrame into a table
        df.to_sql(
            name="hospitals",
            con=conn,
            if_exists="replace",
            index=False
        )

    print(f"Loaded {len(df)} hospitals into {database_path}")

    return database_path


def load_table(df, table_name):
    """Load any DataFrame into health.db as its own table (replaces old data)."""

    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    database_path = data_dir / "health.db"

    with sqlite3.connect(database_path) as conn:
        df.to_sql(name=table_name, con=conn, if_exists="replace", index=False)

        # Index the join keys so map queries stay fast
        for key in ("reporting_unit_code", "measure_code", "reported_measure_code"):
            if key in df.columns:
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS idx_{table_name}_{key} '
                    f'ON "{table_name}" ("{key}")'
                )

    print(f"Loaded {len(df)} rows into {table_name}")
    return database_path


def load_measure_tables(categories, measures, reported_measures, measure_values):
    """Load the four MyHospitals measure tables."""
    load_table(categories, "measure_categories")
    load_table(measures, "measures")
    load_table(reported_measures, "reported_measures")
    return load_table(measure_values, "measure_values")
