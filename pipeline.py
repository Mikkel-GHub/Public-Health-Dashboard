from extract import (
    extract_reporting_units,
    extract_measure_categories,
    extract_measures,
    extract_reported_measures,
    extract_all_flat_data_extracts,
)
from transform import (
    transform_hospitals,
    transform_measure_categories,
    transform_measures,
    transform_reported_measures,
    transform_measure_values,
)
from load import load_hospitals, load_measure_tables

START_DATE = "2024-01-01"   # always date-filter: unfiltered ED waits alone is ~45k rows


def main():
    print("Starting ETL pipeline...")

    # --- Hospitals (Liam) ---
    raw_data = extract_reporting_units()
    print(f"Extracted {len(raw_data)} reporting units")
    hospitals = transform_hospitals(raw_data)
    print(f"Transformed {len(hospitals)} NSW hospitals")
    database_path = load_hospitals(hospitals)

    # --- Measures + values ---
    print(f"Extracting measure data from {START_DATE} (this can take a few minutes)...")
    categories = transform_measure_categories(extract_measure_categories())
    measures = transform_measures(extract_measures())
    reported = transform_reported_measures(extract_reported_measures())
    raw_values = extract_all_flat_data_extracts(start_date=START_DATE)
    print(f"Extracted {sum(len(v) for v in raw_values.values())} raw value rows")

    values = transform_measure_values(raw_values, hospitals["hospital_id"])
    print(f"Transformed {len(values)} NSW hospital value rows")

    load_measure_tables(categories, measures, reported, values)

    print(f"ETL completed successfully: {database_path}")


if __name__ == "__main__":
    main()
