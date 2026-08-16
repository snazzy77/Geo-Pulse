from __future__ import annotations

import httpx
import numpy as np
import pandas as pd

from geo_pulse.core.exceptions import DataValidationError

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_current_air_quality(
    frame: pd.DataFrame,
    timeout_s: int = 30,
    chunk_size: int = 50,
) -> pd.DataFrame:
    """Attach current PM2.5 and NO2 readings to WGS84 point records without an API key."""
    required = {"latitude", "longitude"}
    if not required <= set(frame.columns):
        raise DataValidationError("Air-quality enrichment requires latitude and longitude")
    result = frame.copy()
    pm2_5: list[float] = []
    nitrogen_dioxide: list[float] = []
    observed_at: list[str | None] = []
    try:
        for start in range(0, len(result), chunk_size):
            chunk = result.iloc[start : start + chunk_size]
            response = httpx.get(
                AIR_QUALITY_URL,
                params={
                    "latitude": ",".join(chunk["latitude"].astype(str)),
                    "longitude": ",".join(chunk["longitude"].astype(str)),
                    "current": "pm2_5,nitrogen_dioxide",
                    "timezone": "UTC",
                },
                timeout=timeout_s,
                headers={"User-Agent": "Geo-Pulse/0.1 environmental-health surveillance"},
            )
            response.raise_for_status()
            payload = response.json()
            locations = payload if isinstance(payload, list) else [payload]
            if len(locations) != len(chunk):
                raise ValueError("air-quality response location count did not match request")
            for location in locations:
                current = location.get("current", {})
                pm2_5.append(float(current.get("pm2_5", np.nan)))
                nitrogen_dioxide.append(float(current.get("nitrogen_dioxide", np.nan)))
                observed_at.append(current.get("time"))
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        raise DataValidationError(f"Open-Meteo air-quality enrichment failed: {exc}") from None
    result["current_pm2_5"] = pm2_5
    result["current_nitrogen_dioxide"] = nitrogen_dioxide
    result["air_quality_observed_at"] = observed_at
    return result
