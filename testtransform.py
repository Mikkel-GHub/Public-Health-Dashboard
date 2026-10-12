
from extract import extract_reporting_units
from transform import transform_hospitals

# Extract the reporting units
raw_data = extract_reporting_units()

# Transform into NSW hospital records
nsw_hospitals = transform_hospitals(raw_data)

# Display results
print("Transformed NSW hospitals:", len(nsw_hospitals))

print("\nFirst five records:")
print(nsw_hospitals.head().to_string(index=False))

print("\nMissing values:")
print(nsw_hospitals.isnull().sum())

print("\nDuplicate hospital IDs:")
print(nsw_hospitals["hospital_id"].duplicated().sum())
