
import pandas as pd


def get_state(unit):
    """Find the state associated with a reporting unit."""

    for mapping in unit.get("mapped_reporting_units") or []:
        map_type = mapping.get("map_type") or {}
        mapped_unit = mapping.get("mapped_reporting_unit") or {}

        if map_type.get("mapped_reporting_unit_code") == "STATE_MAPPING":
            return mapped_unit.get("reporting_unit_code")

    return None


def transform_hospitals(reporting_units):
    """Transform raw AIHW data into clean NSW hospital records."""

    records = []

    for unit in reporting_units:

        # 1. Only keep hospitals
        unit_type = unit.get("reporting_unit_type") or {}

        if unit_type.get("reporting_unit_type_code") != "H":
            continue

        # 2. Only keep NSW hospitals
        state = get_state(unit)

        if state != "NSW":
            continue

        # 3. Extract relevant fields
        records.append({
            "hospital_id": unit.get("reporting_unit_code"),
            "hospital_name": unit.get("reporting_unit_name"),
            "state": state,
            "latitude": unit.get("latitude"),
            "longitude": unit.get("longitude"),
            "private": unit.get("private"),
            "closed": unit.get("closed")
        })

    # 4. Convert records to a DataFrame
    df = pd.DataFrame(records, columns=[
        "hospital_id", "hospital_name", "state",
        "latitude", "longitude", "private", "closed"
    ])

    # 5. Convert coordinates to numeric values
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    # 6. Remove missing and invalid coordinates
    df = df.dropna(subset=[
        "hospital_id", "hospital_name", "latitude", "longitude"
    ])

    df = df[
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    ]

    # 7. Remove duplicate hospital IDs
    df = df.drop_duplicates(subset="hospital_id")

    return df
