from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import httpx
import numpy as np
import pandas as pd

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.storage.cache import JsonCache

ACS_VARIABLES = {
    "B01003_001E": "census_population",
    "B19013_001E": "census_median_household_income",
    "B25077_001E": "census_median_home_value",
}
HEALTH_ACS_VARIABLES = {
    "B19013_001E": "median_household_income",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "below_poverty",
    "B01001_001E": "age_population",
    **{f"B01001_{index:03d}E": f"age_65_plus_{index}" for index in range(20, 26)},
    **{f"B01001_{index:03d}E": f"age_65_plus_{index}" for index in range(44, 50)},
}
HEALTH_CONTROL_COLUMNS = {
    "median_household_income": "census_median_household_income_10k",
    "percent_below_poverty": "census_percent_below_poverty",
    "percent_age_65_plus": "census_percent_age_65_plus",
}


def latest_available_acs5_year(
    api_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
    start_year: int | None = None,
) -> int:
    """Discover the newest published ACS 5-year release instead of trusting a UI year."""
    key = api_key or os.getenv("CENSUS_API_KEY")
    if not key:
        raise DataValidationError("Latest ACS discovery requires CENSUS_API_KEY")
    newest_candidate = start_year or datetime.now(UTC).year
    with httpx.Client(timeout=20, transport=transport) as client:
        for year in range(newest_candidate, max(2008, newest_candidate - 7), -1):
            try:
                response = client.get(
                    f"https://api.census.gov/data/{year}/acs/acs5",
                    params={
                        "get": "NAME,B01003_001E",
                        "for": "zip code tabulation area:10001",
                        "key": key,
                    },
                )
                if response.status_code == 200 and len(response.json()) >= 2:
                    return year
            except (httpx.HTTPError, ValueError):
                continue
    raise DataValidationError("Could not discover an available ACS 5-year release")


class CensusClient:
    def __init__(
        self,
        year: int = 2024,
        api_key: str | None = None,
        cache_dir: str | Path = ".cache/census",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.year = year
        self.api_key = api_key or os.getenv("CENSUS_API_KEY")
        if not self.api_key:
            raise DataValidationError(
                "Census enrichment requires a free CENSUS_API_KEY. Request one at "
                "https://api.census.gov/data/key_signup.html and set it in your environment."
            )
        self.cache = JsonCache(cache_dir)
        self.endpoint = f"https://api.census.gov/data/{year}/acs/acs5"
        self.client = httpx.Client(
            timeout=30,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_zcta(self, postal_code: str) -> dict[str, Any]:
        zcta = str(postal_code).zfill(5)
        cache_key = f"acs5:{self.year}:zcta:{zcta}:{','.join(ACS_VARIABLES)}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        params = {
            "get": "NAME," + ",".join(ACS_VARIABLES),
            "for": f"zip code tabulation area:{zcta}",
            "key": self.api_key,
        }
        try:
            response = self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            rows = response.json()
        except httpx.HTTPStatusError as exc:
            raise DataValidationError(
                f"Census ACS request failed for ZIP {zcta}: HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError as exc:
            raise DataValidationError(
                f"Census ACS request failed for ZIP {zcta}: {type(exc).__name__}"
            ) from None
        except ValueError:
            raise DataValidationError(
                f"Census ACS returned an invalid JSON response for ZIP {zcta}"
            ) from None
        if len(rows) < 2:
            raise DataValidationError(f"Census ACS returned no record for ZIP {zcta}")
        record = dict(zip(rows[0], rows[1], strict=True))
        result: dict[str, Any] = {
            "postal_code": zcta,
            "census_geography_name": record.get("NAME", ""),
        }
        for variable, output_name in ACS_VARIABLES.items():
            try:
                value = float(record[variable])
                result[output_name] = value if value >= 0 else None
            except (KeyError, TypeError, ValueError):
                result[output_name] = None
        self.cache.set(cache_key, result)
        return result

    def fetch_zcta_health(
        self, postal_code: str, controls: list[str]
    ) -> dict[str, Any]:
        zcta = str(postal_code).zfill(5)
        cache_key = f"acs5-health:{self.year}:zcta:{zcta}:{','.join(sorted(controls))}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        params = {
            "get": "NAME," + ",".join(HEALTH_ACS_VARIABLES),
            "for": f"zip code tabulation area:{zcta}",
            "key": self.api_key,
        }
        try:
            response = self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            rows = response.json()
        except httpx.HTTPStatusError as exc:
            raise DataValidationError(
                f"Census ACS request failed for ZIP {zcta}: HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError as exc:
            raise DataValidationError(
                f"Census ACS request failed for ZIP {zcta}: {type(exc).__name__}"
            ) from None
        except ValueError:
            raise DataValidationError(
                f"Census ACS returned invalid JSON for ZIP {zcta}"
            ) from None
        if len(rows) < 2:
            raise DataValidationError(f"Census ACS returned no record for ZIP {zcta}")
        record = dict(zip(rows[0], rows[1], strict=True))

        def value(variable: str) -> float | None:
            try:
                parsed = float(record[variable])
                return parsed if parsed >= 0 else None
            except (KeyError, TypeError, ValueError):
                return None

        result: dict[str, Any] = {"postal_code": zcta}
        if "median_household_income" in controls:
            income = value("B19013_001E")
            result[HEALTH_CONTROL_COLUMNS["median_household_income"]] = (
                income / 10_000 if income is not None else None
            )
        if "percent_below_poverty" in controls:
            total, below = value("B17001_001E"), value("B17001_002E")
            result[HEALTH_CONTROL_COLUMNS["percent_below_poverty"]] = (
                100 * below / total if total and below is not None else None
            )
        if "percent_age_65_plus" in controls:
            total = value("B01001_001E")
            age_values = [
                value(f"B01001_{index:03d}E")
                for index in [*range(20, 26), *range(44, 50)]
            ]
            result[HEALTH_CONTROL_COLUMNS["percent_age_65_plus"]] = (
                100 * sum(item for item in age_values if item is not None) / total
                if total and any(item is not None for item in age_values)
                else None
            )
        self.cache.set(cache_key, result)
        return result


def enrich_with_census(
    properties: pd.DataFrame,
    year: int,
    cache_dir: str | Path,
    api_key: str | None = None,
    max_zip_codes: int = 100,
    transport: httpx.BaseTransport | None = None,
) -> pd.DataFrame:
    if "postal_code" not in properties:
        raise DataValidationError("Census enrichment requires a postal_code column")
    zip_codes = sorted(properties["postal_code"].dropna().astype(str).str.zfill(5).unique())
    if len(zip_codes) > max_zip_codes:
        raise DataValidationError(
            f"Census enrichment found {len(zip_codes)} ZIP codes; configured maximum is {max_zip_codes}"
        )
    with CensusClient(year, api_key, cache_dir, transport) as client:
        demographics = pd.DataFrame([client.fetch_zcta(code) for code in zip_codes])
    result = properties.copy()
    result["postal_code"] = result["postal_code"].astype(str).str.zfill(5)
    result = result.merge(demographics, on="postal_code", how="left", validate="many_to_one")
    result["census_log_population"] = np.log1p(result["census_population"])
    result["census_income_10k"] = result["census_median_household_income"] / 10_000
    result["census_home_value_100k"] = result["census_median_home_value"] / 100_000
    return result


def enrich_health_with_census(
    outcomes: pd.DataFrame,
    controls: list[str],
    cache_dir: str | Path,
    api_key: str | None = None,
    max_zip_codes: int = 100,
    transport: httpx.BaseTransport | None = None,
    year: int | None = None,
) -> tuple[pd.DataFrame, int]:
    unsupported = sorted(set(controls) - set(HEALTH_CONTROL_COLUMNS))
    if unsupported:
        raise DataValidationError("Unsupported demographic controls: " + ", ".join(unsupported))
    postal_column = next(
        (item for item in ("postal_code", "zip_code", "zipcode", "zip") if item in outcomes),
        None,
    )
    if postal_column is None:
        raise DataValidationError(
            "Selected Census demographic controls require postal_code, zip_code, zipcode, or zip"
        )
    resolved_year = year or latest_available_acs5_year(api_key, transport)
    result = outcomes.copy()
    result["postal_code"] = (
        result[postal_column]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(5)
    )
    zip_codes = sorted(result["postal_code"].dropna().unique())
    if len(zip_codes) > max_zip_codes:
        raise DataValidationError(
            f"Census enrichment found {len(zip_codes)} ZIP codes; maximum is {max_zip_codes}"
        )
    with CensusClient(resolved_year, api_key, cache_dir, transport) as client:
        demographics = pd.DataFrame(
            [client.fetch_zcta_health(code, controls) for code in zip_codes]
        )
    result = result.merge(demographics, on="postal_code", how="left", validate="many_to_one")
    return result, resolved_year


def fetch_county_tract_demographics(
    county_fips: str,
    controls: list[str],
    cache_dir: str | Path,
    api_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
    year: int | None = None,
) -> tuple[pd.DataFrame, int]:
    """Fetch selected ACS controls for all tracts in a county in one request."""
    if len(county_fips) != 5 or not county_fips.isdigit():
        raise DataValidationError("County FIPS must contain exactly five digits")
    unsupported = sorted(set(controls) - set(HEALTH_CONTROL_COLUMNS))
    if unsupported:
        raise DataValidationError("Unsupported demographic controls: " + ", ".join(unsupported))
    resolved_year = year or latest_available_acs5_year(api_key, transport)
    key = api_key or os.getenv("CENSUS_API_KEY")
    if not key:
        raise DataValidationError("Census tract demographics require CENSUS_API_KEY")
    cache = JsonCache(Path(cache_dir) / "tract-demographics")
    cache_key = f"acs5:{resolved_year}:county:{county_fips}:{','.join(sorted(controls))}"
    rows = cache.get(cache_key)
    if rows is None:
        params = {
            "get": "NAME," + ",".join(HEALTH_ACS_VARIABLES),
            "for": "tract:*",
            "in": f"state:{county_fips[:2]} county:{county_fips[2:]}",
            "key": key,
        }
        try:
            with httpx.Client(timeout=60, transport=transport) as client:
                response = client.get(
                    f"https://api.census.gov/data/{resolved_year}/acs/acs5", params=params
                )
                response.raise_for_status()
                rows = response.json()
        except httpx.HTTPStatusError as exc:
            raise DataValidationError(
                f"Census ACS tract request failed: HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError as exc:
            raise DataValidationError(
                f"Census ACS tract request failed: {type(exc).__name__}"
            ) from None
        except ValueError:
            raise DataValidationError("Census ACS tract request returned invalid JSON") from None
        cache.set(cache_key, rows)
    if not isinstance(rows, list) or len(rows) < 2:
        raise DataValidationError(f"Census ACS returned no tracts for county {county_fips}")
    records = [dict(zip(rows[0], row, strict=True)) for row in rows[1:]]

    def numeric(record: dict[str, str], variable: str) -> float | None:
        try:
            value = float(record[variable])
            return value if value >= 0 else None
        except (KeyError, TypeError, ValueError):
            return None

    output: list[dict[str, Any]] = []
    for record in records:
        item: dict[str, Any] = {
            "tract_fips": f"{record['state']}{record['county']}{record['tract']}",
            "census_geography_name": record.get("NAME", ""),
        }
        if "median_household_income" in controls:
            income = numeric(record, "B19013_001E")
            item[HEALTH_CONTROL_COLUMNS["median_household_income"]] = (
                income / 10_000 if income is not None else None
            )
        if "percent_below_poverty" in controls:
            total = numeric(record, "B17001_001E")
            below = numeric(record, "B17001_002E")
            item[HEALTH_CONTROL_COLUMNS["percent_below_poverty"]] = (
                100 * below / total if total and below is not None else None
            )
        if "percent_age_65_plus" in controls:
            total = numeric(record, "B01001_001E")
            age_values = [
                numeric(record, f"B01001_{index:03d}E")
                for index in [*range(20, 26), *range(44, 50)]
            ]
            item[HEALTH_CONTROL_COLUMNS["percent_age_65_plus"]] = (
                100 * sum(value for value in age_values if value is not None) / total
                if total and any(value is not None for value in age_values)
                else None
            )
        output.append(item)
    return pd.DataFrame.from_records(output), resolved_year


def fetch_county_tract_boundaries(
    county_fips: str,
    cache_dir: str | Path,
    transport: httpx.BaseTransport | None = None,
):
    """Fetch current Census tract polygons from the official TIGERweb service."""
    if len(county_fips) != 5 or not county_fips.isdigit():
        raise DataValidationError("County FIPS must contain exactly five digits")
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise DataValidationError("Census tract boundaries require geopandas") from exc
    cache = JsonCache(Path(cache_dir) / "tract-boundaries")
    cache_key = f"tigerweb-current:county:{county_fips}"
    payload = cache.get(cache_key)
    if payload is None:
        params = {
            "where": f"STATE='{county_fips[:2]}' AND COUNTY='{county_fips[2:]}'",
            "outFields": "GEOID,NAME,CENTLAT,CENTLON",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
        endpoint = (
            "https://tigerweb.geo.census.gov/arcgis/rest/services/"
            "TIGERweb/Tracts_Blocks/MapServer/0/query"
        )
        try:
            with httpx.Client(timeout=90, transport=transport) as client:
                response = client.get(endpoint, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise DataValidationError(
                f"Census TIGERweb request failed: HTTP {exc.response.status_code}"
            ) from None
        except httpx.HTTPError as exc:
            raise DataValidationError(
                f"Census TIGERweb request failed: {type(exc).__name__}"
            ) from None
        except ValueError:
            raise DataValidationError("Census TIGERweb returned invalid GeoJSON") from None
        cache.set(cache_key, payload)
    features = payload.get("features", []) if isinstance(payload, dict) else []
    if not features:
        raise DataValidationError(f"Census TIGERweb returned no tracts for county {county_fips}")
    frame = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    frame = frame.rename(
        columns={
            "GEOID": "tract_fips",
            "NAME": "tract_name",
            "CENTLAT": "latitude",
            "CENTLON": "longitude",
        }
    )
    frame["tract_fips"] = frame["tract_fips"].astype(str).str.zfill(11)
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    return frame[["tract_fips", "tract_name", "latitude", "longitude", "geometry"]]
