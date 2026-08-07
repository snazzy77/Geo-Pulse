from geo_pulse.schemas.features import FeatureDefinition


def default_catalog(amenity_types: list[str], radius_m: int) -> list[FeatureDefinition]:
    catalog = [
        FeatureDefinition(
            name="square_feet", description="Interior living area", unit="ft²", source="property"
        ),
        FeatureDefinition(
            name="beds", description="Bedroom count", unit="count", source="property"
        ),
        FeatureDefinition(
            name="baths", description="Bathroom count", unit="count", source="property"
        ),
        FeatureDefinition(
            name="property_age",
            description="Analysis year minus build year",
            unit="years",
            source="derived",
        ),
    ]
    for kind in amenity_types:
        catalog.extend(
            [
                FeatureDefinition(
                    name=f"dist_to_{kind}_m",
                    description=f"Distance to nearest {kind}",
                    unit="meters",
                    source="amenity",
                ),
                FeatureDefinition(
                    name=f"{kind}_count_{radius_m}m",
                    description=f"{kind.title()} count within radius",
                    unit="count",
                    source="amenity",
                ),
            ]
        )
    return catalog
