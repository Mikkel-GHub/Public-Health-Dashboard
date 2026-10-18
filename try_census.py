from extract import extract_census
from transform import transform_census, add_map_code

TABLES = [
    "C21_G02_LGA",
    "C21_G04_LGA",
    "C21_G18_LGA",
    "C21_G19_LGA",
    "ABS_SEIFA2021_LGA",
]

raw = {}
for table in TABLES:
    print("Downloading", table, "...")
    raw[table] = extract_census(table)

clean = add_map_code(transform_census(raw))

print()
print(clean.groupby("metric")["value"].describe().round(1).to_string())
print()
print("Total NSW population:", int(clean[clean["metric"] == "population"]["value"].sum()))

clean.to_csv("census_clean.csv", index=False)
print("Saved census_clean.csv")
