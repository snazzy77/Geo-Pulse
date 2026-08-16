from pathlib import Path

import numpy as np
import pandas as pd

from geo_pulse.gis.distance_calculator import nearest_distance_m, pairwise_haversine_m


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


def generate_health_sample_data(output_dir: str | Path, seed: int = 42) -> tuple[Path, Path]:
    """Create deterministic tract-like respiratory counts and industrial hazard locations."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    counties = {
        "King-North": (47.68, -122.33, 0.10, "98103"),
        "King-Central": (47.61, -122.33, 0.20, "98104"),
        "King-South": (47.53, -122.29, 0.35, "98108"),
        "Pierce-North": (47.36, -122.25, 0.25, "98001"),
    }
    hazard_rows: list[dict[str, object]] = []
    for index, (latitude, longitude) in enumerate(
        [(47.604, -122.321), (47.595, -122.310), (47.525, -122.285),
         (47.515, -122.275), (47.365, -122.245), (47.350, -122.260)],
        start=1,
    ):
        hazard_rows.append(
            {
                "record_id": f"industrial-{index:02d}",
                "feature_type": "factory" if index % 2 else "power_plant",
                "name": f"Industrial site {index}",
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    hazards = pd.DataFrame(hazard_rows)
    outcome_rows: list[dict[str, object]] = []
    for county, (latitude, longitude, deprivation_shift, postal_code) in counties.items():
        for index in range(15):
            outcome_rows.append(
                {
                    "record_id": f"tract-{county.lower()}-{index + 1:02d}",
                    "county": county,
                    "postal_code": postal_code,
                    "latitude": latitude + rng.normal(0, 0.018),
                    "longitude": longitude + rng.normal(0, 0.018),
                    "pm2_5": float(np.clip(rng.normal(9.5 + deprivation_shift * 5, 1.2), 4, 20)),
                    "deprivation_index": float(
                        np.clip(rng.normal(0.35 + deprivation_shift, 0.12), 0, 1)
                    ),
                    "population_thousands": float(np.clip(rng.normal(4.5, 0.7), 2, 7)),
                }
            )
    outcomes = pd.DataFrame(outcome_rows)
    distances = pairwise_haversine_m(
        outcomes[["latitude", "longitude"]].to_numpy(),
        hazards[["latitude", "longitude"]].to_numpy(),
    )
    exposure = (distances <= 2000).sum(axis=1)
    log_rate = (
        0.8
        + 0.24 * exposure
        + 0.045 * outcomes["pm2_5"]
        + 0.65 * outcomes["deprivation_index"]
        + 0.10 * outcomes["population_thousands"]
    )
    outcomes.insert(1, "asthma_cases", rng.poisson(np.exp(log_rate)).astype(int))
    outcome_path = output / "health_outcomes.csv"
    hazard_path = output / "industrial_hazards.csv"
    outcomes.to_csv(outcome_path, index=False)
    hazards.to_csv(hazard_path, index=False)
    return outcome_path, hazard_path
