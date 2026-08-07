from __future__ import annotations

import os
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
