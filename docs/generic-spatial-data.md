# Generic Spatial Data

## Canonical contract

The inspection and mapping stage is the only component that reads source-specific column names. It converts every accepted source into:

| Canonical column | Purpose |
| --- | --- |
| `record_id` | Stable row identifier; generated when no source ID is mapped |
| `target` | Numeric outcome modeled by Geo-Pulse |
| `latitude` | WGS84 latitude |
| `longitude` | WGS84 longitude |
| `group_id` | Repeated geographic unit used for the random intercept |
| mapped numeric features | Fixed effects with formula-safe names |

The GIS, modeling, diagnostic, visualization, and reporting layers consume only this canonical contract.

## Mapping format

~~~json
{
  "target_variable": "DiseaseRate",
  "lat_col": "Latitude",
  "lon_col": "Longitude",
  "geometry_col": null,
  "group_col": "CommunityArea",
  "fixed_features": ["Pollution", "Income"],
  "id_col": "CaseNumber",
  "source_crs": "EPSG:4326"
}
~~~

Use either `lat_col` plus `lon_col`, or `geometry_col`. Geometry values may be Shapely/GeoPandas geometry, GeoJSON geometry objects, or WKT. Non-point geometry is represented by its centroid.

When coordinates use a projected CRS, set `source_crs` to its EPSG or PROJ definition. Geo-Pulse transforms the canonical coordinates to WGS84 for maps and chooses the appropriate northern or southern UTM zone for metric neighborhood calculations. Polar data uses a local azimuthal-equidistant CRS.

## Automatic inspection

`POST /datasets/inspect` returns:

- column names and row count;
- up to five preview rows;
- a suggested mapping when every required role can be inferred;
- per-role confidence scores;
- warnings for ambiguous or missing roles.

Aliases are maintained in `configs/default_schema.yaml`. Numeric columns that are not assigned to target, location, group, or identifier roles become candidate fixed effects. ID-, URL-, date-, and timestamp-like columns are excluded from automatic fixed-effect selection.

Inference never invents missing coordinates or silently chooses a target when no recognized target alias exists. Edit the suggested mapping or provide one explicitly when domain semantics require human judgment.

## Target transformations

- `none`: fit the outcome on its original scale.
- `log`: require a positive outcome and model its natural logarithm.
- `auto`: use a log transform only when all values are positive and the outcome is materially skewed; otherwise retain the original scale.

The original housing workflow defaults to `log`. Generic analysis defaults to `auto`.

## Housing enrichment boundary

Generic mode does not assume real-estate fields and does not automatically call Census or OpenStreetMap amenity enrichment. The `analyze-free` workflow remains the specialized path for Kaggle properties, Census demographics, and OSM parks, schools, and transit.
