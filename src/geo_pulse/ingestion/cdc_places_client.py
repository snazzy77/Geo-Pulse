from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.storage.cache import JsonCache

CDC_PLACES_DOMAIN = "https://data.cdc.gov"
CDC_PLACES_TRACT_DATASET_ID = "cwsq-ngmh"
CDC_PLACES_RELEASE = "2025"


def _coordinates(value: object) -> tuple[float | None, float | None]:
    if not isinstance(value, dict):
        return None, None
    coordinates = value.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        try:
            return float(coordinates[1]), float(coordinates[0])
        except (TypeError, ValueError):
            return None, None
    location = value.get("human_address")
    if location:
        return None, None
    try:
        return float(value["latitude"]), float(value["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, None


def fetch_cdc_places_measure(
    county_fips: str,
    measure_id: str = "CASTHMA",
    cache_dir: str | Path = ".cache/cdc-places",
    app_token: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch one CDC PLACES measure for every available tract in a county.

    PLACES prevalence estimates are modeled adult estimates, not observed case logs. Estimated
    counts therefore use the dataset's adult-population denominator and remain estimates.
    """
    if len(county_fips) != 5 or not county_fips.isdigit():
        raise DataValidationError("County FIPS must contain exactly five digits")
    normalized_measure = measure_id.strip().upper()
    if not normalized_measure.replace("_", "").isalnum():
        raise DataValidationError("CDC PLACES measure ID is invalid")

    cache = JsonCache(cache_dir)
    cache_key = f"places:{CDC_PLACES_TRACT_DATASET_ID}:{county_fips}:{normalized_measure}"
    records = cache.get(cache_key)
    cached = records is not None
    if records is None:
        headers = {"Accept": "application/json", "User-Agent": "Geo-Pulse/0.1 research tool"}
        if app_token:
            headers["X-App-Token"] = app_token
        params = {
            "$select": (
                "year,stateabbr,statedesc,countyname,countyfips,locationname,measure,"
                "measureid,data_value,data_value_unit,data_value_type,totalpopulation,"
                "totalpop18plus,geolocation"
            ),
            "$where": (
                f"countyfips = '{county_fips}' AND measureid = '{normalized_measure}' "
                "AND data_value_type = 'Crude prevalence'"
            ),
            "$order": "locationname",
            "$limit": "5000",
        }
        endpoint = f"{CDC_PLACES_DOMAIN}/resource/{CDC_PLACES_TRACT_DATASET_ID}.json"
        try:
            with httpx.Client(timeout=60, transport=transport) as client:
                response = client.get(endpoint, params=params, headers=headers)
                response.raise_for_status()
                records = response.json()
        except httpx.HTTPStatusError as exc:
            raise DataValidationError(
                f"CDC PLACES request failed: HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError as exc:
            raise DataValidationError(f"CDC PLACES request failed: {type(exc).__name__}") from None
        except ValueError:
            raise DataValidationError("CDC PLACES returned invalid JSON") from None
        if not isinstance(records, list):
            raise DataValidationError("CDC PLACES returned an unexpected response")
        cache.set(cache_key, records)
    if not records:
        raise DataValidationError(
            f"CDC PLACES returned no {normalized_measure} tract records for county {county_fips}"
        )

    rows: list[dict[str, Any]] = []
    for record in records:
        latitude, longitude = _coordinates(record.get("geolocation"))
        try:
            prevalence = float(record["data_value"])
            adult_population = int(float(record["totalpop18plus"]))
            total_population = int(float(record["totalpopulation"]))
        except (KeyError, TypeError, ValueError):
            continue
        tract_fips = str(record.get("locationname", "")).zfill(11)
        if len(tract_fips) != 11 or not tract_fips.isdigit() or adult_population <= 0:
            continue
        rows.append(
            {
                "tract_fips": tract_fips,
                "record_id": tract_fips,
                "county_fips": county_fips,
                "state_abbr": record.get("stateabbr"),
                "county_name": record.get("countyname"),
                "measure_id": normalized_measure,
                "measure": record.get("measure"),
                "data_year": record.get("year"),
                "prevalence_pct": prevalence,
                "total_population": total_population,
                "adult_population": adult_population,
                "estimated_cases": round(prevalence / 100 * adult_population),
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        raise DataValidationError("CDC PLACES records contained no usable tract estimates")
    frame = frame.drop_duplicates("tract_fips").reset_index(drop=True)
    metadata = {
        "provider": "CDC PLACES",
        "dataset_id": CDC_PLACES_TRACT_DATASET_ID,
        "release": CDC_PLACES_RELEASE,
        "measure_id": normalized_measure,
        "county_fips": county_fips,
        "row_count": len(frame),
        "cached": cached,
        "source_url": f"{CDC_PLACES_DOMAIN}/d/{CDC_PLACES_TRACT_DATASET_ID}",
        "license": "Public Domain",
        "count_method": "prevalence_pct multiplied by totalpop18plus and rounded",
    }
    return frame, metadata
