
from extract import extract_reporting_units
from transform import transform_hospitals
from load import load_hospitals


def main():
    print("Starting ETL pipeline...")

    # EXTRACT
    raw_data = extract_reporting_units()
    print(f"Extracted {len(raw_data)} reporting units")

    # TRANSFORM
    hospitals = transform_hospitals(raw_data)
    print(f"Transformed {len(hospitals)} NSW hospitals")

    # LOAD
    database_path = load_hospitals(hospitals)

    print(f"ETL completed successfully: {database_path}")


if __name__ == "__main__":
    main()
