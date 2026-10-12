
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
