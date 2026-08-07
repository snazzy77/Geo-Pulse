class GeoPulseError(Exception):
    """Base error for expected Geo-Pulse failures."""


class ConfigurationError(GeoPulseError):
    pass


class DataValidationError(GeoPulseError):
    pass


class ModelingError(GeoPulseError):
    pass


class PipelineError(GeoPulseError):
    pass
