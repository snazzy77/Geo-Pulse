from geo_pulse.core.exceptions import DataValidationError


def require_network_support() -> None:
    raise DataValidationError(
        "Network-distance calculation requires a configured OSMnx graph. "
        "The default pipeline uses geodesic distance."
    )
