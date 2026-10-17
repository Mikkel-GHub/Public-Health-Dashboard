
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

# Measures + fact data (MyHospitals)

import json


def _flatten(records):
    """
    Turn a list of nested API dicts into a flat DataFrame.
    Nested dicts become "parent.child" columns; any lists left over are
    stored as JSON text so SQLite can hold them.
    """
    df = pd.json_normalize(records)

    for col in df.columns:
        if df[col].apply(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].apply(
                lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v
            )

    # "reporting_unit.reporting_unit_code" -> "reporting_unit_code"
    # (only if the short name isn't already taken)
    renames = {}
    for col in df.columns:
        short = col.split(".")[-1]
        if "." in col and short not in df.columns and short not in renames.values():
            renames[col] = short
    return df.rename(columns=renames)


def transform_measure_categories(raw):
    """The 12 measure categories, e.g. MYH-ED-WAITS."""
    return _flatten(raw).drop_duplicates()


def transform_measures(raw):
    """Lookup table of the 33 measures (name, units, category...)."""
    df = _flatten(raw)
    if "measure_code" in df.columns:
        df = df.drop_duplicates(subset="measure_code")
    return df


def transform_reported_measures(raw):
    """Lookup table of the 693 reported measures (measure + sub-filter, e.g. adults/children)."""
    df = _flatten(raw)
    if "reported_measure_code" in df.columns:
        df = df.drop_duplicates(subset="reported_measure_code")
    return df


def _split_meta_tags(df):
    """
    Meta tag fields come as "TypeCode|Value;TypeCode|Value" strings.
    Split each pair into its own column, e.g. meta_AGE = "Adults".
    """
    meta_cols = [c for c in df.columns if "meta" in c.lower()]

    for col in meta_cols:
        def parse(cell):
            out = {}
            if isinstance(cell, str) and "|" in cell:
                for pair in cell.split(";"):
                    if "|" in pair:
                        key, value = pair.split("|", 1)
                        out[f"meta_{key.strip()}"] = value.strip()
            return out

        parsed = df[col].apply(parse).apply(pd.Series)
        if not parsed.empty:
            new_cols = [c for c in parsed.columns if c not in df.columns]
            df = pd.concat([df, parsed[new_cols]], axis=1)

    return df


def transform_measure_values(raw_by_category, hospital_ids):
    """
    Turn the raw flat-data-extract rows into one clean fact table.

    raw_by_category: dict of {category_code: [rows]} from
                     extract_all_flat_data_extracts(), or a single list of rows.
    hospital_ids:    hospital_id values from transform_hospitals() - used to
                     keep only NSW hospitals (the API ignores state filters).
    """
    if isinstance(raw_by_category, dict):
        frames = []
        for category, rows in raw_by_category.items():
            if not rows:
                continue
            part = _flatten(rows)
            part["measure_category_code"] = category
            frames.append(part)
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    else:
        df = _flatten(raw_by_category)

    if df.empty:
        return df

    # 1. Keep only rows for our NSW hospitals
    if "reporting_unit_code" not in df.columns:
        raise KeyError(
            "No reporting_unit_code column found. Columns are: "
            + ", ".join(df.columns)
        )
    df = df[df["reporting_unit_code"].isin(set(hospital_ids))].copy()

    # 2. Values to numbers. Null = suppressed (NOT missing) - keep those rows.
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["is_suppressed"] = df["value"].isna()

    # 3. Dates to proper dates where present
    for col in df.columns:
        if col.endswith("_date"):
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # 4. Split "TypeCode|Value" meta tag strings into columns
    df = _split_meta_tags(df)

    # 5. Drop exact duplicates
    df = df.drop_duplicates()

    return df.reset_index(drop=True)
