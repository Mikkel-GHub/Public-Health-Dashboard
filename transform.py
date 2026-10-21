
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



# ---------- helpers ----------

def _check_no_duplicates(df, label):
    """Stop with a clear message if a council area appears twice for a measure."""
    if df.duplicated(subset=["lga_code", "metric"]).any():
        raise ValueError(f"{label}: some council areas appear more than once. "
                         "A filter is too loose.")


# ---------- one function per table ----------

def transform_medians(rows):
    """C21_G02: median age and median household income."""
    wanted = {
        "1": "median_age",
        "4": "median_household_income_weekly",
    }
    df = pd.DataFrame(rows, dtype=str)
    df = df[(df["STATE"] == "1") & (df["MEDAVG"].isin(wanted))].copy()   # STATE 1 = NSW

    df["metric"] = df["MEDAVG"].map(wanted)
    df["value"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.rename(columns={"REGION": "lga_code"})[["lga_code", "metric", "value"]]
    df = df.dropna(subset=["value"])

    _check_no_duplicates(df, "medians")
    return df


def transform_age(rows):
    """C21_G04: total population and % of people aged 65+."""
    under_65 = ["0_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34",
                "35_39", "40_44", "45_49", "50_54", "55_59", "60_64"]
    over_65 = ["65_69", "70_74", "75_79", "80_84", "85_89", "90_94", "95_99", "GE100"]

    df = pd.DataFrame(rows, dtype=str)
    # NSW, all persons, and ONLY the 5-year groups (this avoids double counting)
    df = df[
        (df["STATE"] == "1")
        & (df["SEXP"] == "3")
        & (df["AGEINGP"].isin(under_65 + over_65))
    ].copy()
    df["count"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")

    population = df.groupby("REGION")["count"].sum()
    older = (df[df["AGEINGP"].isin(over_65)]
             .groupby("REGION")["count"].sum()
             .reindex(population.index, fill_value=0))
    pct_older = older / population * 100

    out = pd.concat([
        population.rename("value").reset_index().assign(metric="population"),
        pct_older.rename("value").reset_index().assign(metric="pct_aged_65_plus"),
    ])
    out = out.rename(columns={"REGION": "lga_code"})[["lga_code", "metric", "value"]]
    out = out.dropna(subset=["value"])

    _check_no_duplicates(out, "age")
    return out


def transform_health_conditions(rows, age_df):
    """C21_G19: % of people with each long-term health condition."""
    conditions = {
        "11": "pct_arthritis",
        "21": "pct_asthma",
        "31": "pct_cancer",
        "41": "pct_dementia",
        "51": "pct_diabetes",
        "61": "pct_heart_disease",
        "71": "pct_kidney_disease",
        "81": "pct_lung_condition",
        "91": "pct_mental_health",
        "101": "pct_stroke",
    }
    df = pd.DataFrame(rows, dtype=str)
    df = df[
        (df["STATE"] == "1")        # NSW
        & (df["SEXP"] == "3")       # all persons
        & (df["AGEP"] == "_T")      # all ages
        & (df["LTHP"].isin(conditions))
    ].copy()

    df["count"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df["metric"] = df["LTHP"].map(conditions)
    df = df.rename(columns={"REGION": "lga_code"})

    # Divide by each area's population (from the age table) to get a percentage
    population = (age_df[age_df["metric"] == "population"]
                  .set_index("lga_code")["value"])
    df["population"] = df["lga_code"].map(population)
    df["value"] = df["count"] / df["population"] * 100

    out = df.dropna(subset=["value"])[["lga_code", "metric", "value"]]
    _check_no_duplicates(out, "health conditions")
    return out


def transform_assistance(rows):
    """C21_G18: % of people who need help with daily activities."""
    df = pd.DataFrame(rows, dtype=str)
    df = df[
        (df["STATE"] == "1")
        & (df["SEXP"] == "3")
        & (df["AGEP"] == "_T")
        & (df["ASSNP"].isin(["1", "_T"]))   # 1 = needs help, _T = total
    ].copy()
    df["count"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")

    counts = df.pivot(index="REGION", columns="ASSNP", values="count")
    pct = counts["1"] / counts["_T"] * 100

    out = pct.rename("value").reset_index().rename(columns={"REGION": "lga_code"})
    out["metric"] = "pct_needs_assistance"
    out = out.dropna(subset=["value"])[["lga_code", "metric", "value"]]

    _check_no_duplicates(out, "assistance")
    return out


def transform_seifa(rows):
    """ABS_SEIFA2021: disadvantage score. LOWER score = MORE disadvantaged."""
    df = pd.DataFrame(rows, dtype=str)
    df = df[
        (df["SEIFAINDEXTYPE"] == "IRSD")      # Index of Relative Socio-economic Disadvantage
        & (df["SEIFA_MEASURE"] == "SCORE")
        & (df["LGA_2021"].str.startswith("1"))    # NSW council codes start with 1
    ].copy()

    df["value"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df["metric"] = "seifa_disadvantage_score"
    df = df.rename(columns={"LGA_2021": "lga_code"})[["lga_code", "metric", "value"]]
    df = df.dropna(subset=["value"])

    _check_no_duplicates(df, "seifa")
    return df


# ---------- put them all together ----------

def transform_census(raw):
    """raw is a dictionary: table ID -> rows from extract_census."""
    age = transform_age(raw["C21_G04_LGA"])
    return pd.concat([
        transform_medians(raw["C21_G02_LGA"]),
        age,
        transform_health_conditions(raw["C21_G19_LGA"], age),
        transform_assistance(raw["C21_G18_LGA"]),
        transform_seifa(raw["ABS_SEIFA2021_LGA"]),
    ], ignore_index=True)

def add_map_code(df):
    """Add 'abscode', the code the map file uses for each council area."""
    df = df.copy()
    df["abscode"] = df["lga_code"].astype(int) - 10000
    return df
