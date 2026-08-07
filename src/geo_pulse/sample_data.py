from pathlib import Path

import numpy as np
import pandas as pd

from geo_pulse.gis.distance_calculator import nearest_distance_m


def generate_sample_data(output_dir: str | Path, seed: int = 42) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    neighborhoods = {
        "Central": (30.2672, -97.7431, 120_000),
        "South": (30.2350, -97.7700, 35_000),
        "East": (30.2650, -97.7100, 10_000),
        "North": (30.3100, -97.7350, 55_000),
    }
    amenity_rows: list[dict] = []
    for name, (lat, lon, _) in neighborhoods.items():
        for kind, count in (("park", 3), ("school", 2), ("transit", 3)):
            for index in range(count):
                amenity_rows.append(
                    {
                        "amenity_id": f"{name.lower()}-{kind}-{index + 1}",
                        "amenity_type": kind,
                        "latitude": lat + rng.normal(0, 0.007),
                        "longitude": lon + rng.normal(0, 0.007),
                    }
                )
    amenities = pd.DataFrame(amenity_rows)
    park_coordinates = amenities.loc[
        amenities["amenity_type"] == "park", ["latitude", "longitude"]
    ].to_numpy()
    property_rows: list[dict] = []
    for name, (lat, lon, premium) in neighborhoods.items():
        for index in range(35):
            square_feet = float(np.clip(rng.normal(1_850, 420), 750, 3_500))
            beds = int(rng.integers(2, 6))
            baths = float(rng.choice([1.5, 2, 2.5, 3, 3.5]))
            year_built = int(rng.integers(1960, 2022))
            property_rows.append(
                {
                    "property_id": f"{name.lower()}-{index + 1:03d}",
                    "latitude": lat + rng.normal(0, 0.009),
                    "longitude": lon + rng.normal(0, 0.009),
                    "neighborhood": name,
                    "square_feet": round(square_feet, 1),
                    "beds": beds,
                    "baths": baths,
                    "year_built": year_built,
                    "neighborhood_premium": premium,
                }
            )
    properties = pd.DataFrame(property_rows)
    distances = nearest_distance_m(
        properties[["latitude", "longitude"]].to_numpy(), park_coordinates
    )
    age = 2026 - properties["year_built"]
    price = (
        95_000
        + 215 * properties["square_feet"]
        + 16_000 * properties["beds"]
        + 22_000 * properties["baths"]
        - 650 * age
        - 42 * distances
        + properties.pop("neighborhood_premium")
        + rng.normal(0, 28_000, len(properties))
    )
    properties.insert(1, "price", price.clip(lower=120_000).round(0))
    property_path = output / "properties.csv"
    amenity_path = output / "amenities.csv"
    properties.to_csv(property_path, index=False)
    amenities.to_csv(amenity_path, index=False)
    return property_path, amenity_path
