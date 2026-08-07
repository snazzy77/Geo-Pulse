import pandas as pd

from geo_pulse.gis.amenity_extractor import normalize_amenity_types, select_amenity
from geo_pulse.gis.density_calculator import count_within_radius
from geo_pulse.gis.distance_calculator import nearest_distance_m
from geo_pulse.gis.geometries import coordinate_array


def add_spatial_features(
    properties: pd.DataFrame,
    amenities: pd.DataFrame,
    amenity_types: list[str],
    density_radius_m: float = 1000,
) -> pd.DataFrame:
    result = properties.copy()
    amenities = normalize_amenity_types(amenities)
    origins = coordinate_array(result)
    for amenity_type in amenity_types:
        selected = select_amenity(amenities, amenity_type)
        destinations = coordinate_array(selected)
        result[f"dist_to_{amenity_type}_m"] = nearest_distance_m(origins, destinations)
        result[f"{amenity_type}_count_{int(density_radius_m)}m"] = count_within_radius(
            origins, destinations, density_radius_m
        )
    return result
