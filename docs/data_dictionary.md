# Data Dictionary

## Required property fields

`property_id` is the unique record key. `price` is a positive monetary value. `latitude` and `longitude` are WGS84 coordinates. `neighborhood` is the default random-effect group. `square_feet`, `beds`, and `baths` are nonnegative structural attributes. `year_built` is optional.

## Required amenity fields

`amenity_id` is the unique amenity key. `amenity_type` is a normalized category. `latitude` and `longitude` are WGS84 coordinates.

## Derived fields

`property_age` is the current UTC year minus `year_built`. `dist_to_{type}_m` is the nearest haversine distance in meters. `{type}_count_{radius}m` is the number of matching amenities within the configured radius. `log_price`, predictions, and residuals are produced during modeling.

External-source runs also add `postal_code`, `census_population`, `census_median_household_income`, `census_median_home_value`, `census_log_population`, `census_income_10k`, and `census_home_value_100k`. Census fields are ACS 5-year ZCTA estimates for the configured vintage.
