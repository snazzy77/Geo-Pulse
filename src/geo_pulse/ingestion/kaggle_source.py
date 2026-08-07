from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

import pandas as pd

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.ingestion.property_loader import load_table

CANONICAL_CANDIDATES: dict[str, tuple[str, ...]] = {
    "property_id": ("property_id", "zpid", "id", "listing_id", "parcel_id"),
    "price": ("price", "latest_price", "latestprice", "sale_price", "sold_price", "list_price"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "lng", "long"),
    "neighborhood": ("neighborhood", "zipcode", "zip_code", "postal_code", "zcta"),
    "postal_code": ("postal_code", "zipcode", "zip_code", "zip", "zcta"),
    "square_feet": (
        "square_feet",
        "living_area",
        "livingarea",
        "living_area_sq_ft",
        "livingareasqft",
        "sqft",
        "area",
    ),
    "beds": ("beds", "bedrooms", "num_of_bedrooms", "numofbedrooms"),
    "baths": ("baths", "bathrooms", "num_of_bathrooms", "numofbathrooms"),
    "year_built": ("year_built", "yearbuilt", "built_year"),
}
REQUIRED_CANONICAL = {
    "price",
    "latitude",
    "longitude",
    "neighborhood",
    "postal_code",
    "square_feet",
    "beds",
    "baths",
}
MAX_EXTRACTED_BYTES = 500 * 1024 * 1024


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _materialize_downloaded_file(path: Path, requested_filename: str) -> Path:
    if not zipfile.is_zipfile(path):
        return path
    with zipfile.ZipFile(path) as archive:
        requested = Path(requested_filename).name
        matches = [
            member for member in archive.infolist() if Path(member.filename).name == requested
        ]
        if len(matches) != 1:
            raise DataValidationError(
                f"Kaggle archive does not contain exactly one {requested!r} member"
            )
        member = matches[0]
        if member.is_dir() or member.file_size > MAX_EXTRACTED_BYTES:
            raise DataValidationError(
                "Kaggle archive member is empty or exceeds the 500 MB safety limit"
            )
        destination = path.parent / "extracted" / requested
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)
    return destination


def download_kaggle_file(
    dataset: str,
    filename: str,
    output_dir: str | Path,
) -> Path:
    try:
        import kagglehub
    except ImportError as exc:
        raise DataValidationError("Kaggle support requires the kagglehub package") from exc
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        downloaded = Path(
            kagglehub.dataset_download(dataset, path=filename, output_dir=str(destination))
        )
    except Exception as exc:
        raise DataValidationError(
            "Kaggle download failed. Confirm the dataset handle/file and, if required, set "
            "KAGGLE_API_TOKEN from your free Kaggle account. "
            f"Provider response: {exc}"
        ) from exc
    if downloaded.is_file():
        return _materialize_downloaded_file(downloaded, filename)
    direct = downloaded / filename
    if direct.is_file():
        return _materialize_downloaded_file(direct, filename)
    matches = list(downloaded.rglob(Path(filename).name)) if downloaded.exists() else []
    if len(matches) != 1:
        raise DataValidationError(f"Could not uniquely locate {filename!r} in Kaggle download")
    return _materialize_downloaded_file(matches[0], filename)


def _resolve_mapping(frame: pd.DataFrame, overrides: dict[str, str] | None) -> dict[str, str]:
    normalized_columns = {_normalized(column): column for column in frame.columns}
    mapping = dict(overrides or {})
    for canonical, candidates in CANONICAL_CANDIDATES.items():
        if canonical in mapping:
            continue
        for candidate in candidates:
            if candidate in normalized_columns:
                mapping[canonical] = normalized_columns[candidate]
                break
    missing = sorted(REQUIRED_CANONICAL - set(mapping))
    if missing:
        raise DataValidationError(
            "Kaggle dataset columns could not be inferred for: "
            + ", ".join(missing)
            + ". Supply a canonical-to-source column_mapping."
        )
    unknown = sorted({source for source in mapping.values() if source not in frame.columns})
    if unknown:
        raise DataValidationError("Mapped Kaggle columns do not exist: " + ", ".join(unknown))
    return mapping


def normalize_kaggle_properties(
    frame: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
    max_rows: int = 500,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, str]]:
    mapping = _resolve_mapping(frame, column_mapping)
    normalized = pd.DataFrame({canonical: frame[source] for canonical, source in mapping.items()})
    if "property_id" not in normalized:
        normalized.insert(0, "property_id", [f"kaggle-{index + 1}" for index in range(len(frame))])
    for column in ("price", "latitude", "longitude", "square_feet", "beds", "baths", "year_built"):
        if column in normalized:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    postal = normalized["postal_code"].astype(str).str.extract(r"(\d{5})", expand=False)
    normalized["postal_code"] = postal
    normalized["neighborhood"] = (
        normalized["neighborhood"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    normalized = normalized.dropna(subset=list(REQUIRED_CANONICAL)).copy()
    normalized = normalized[
        normalized["latitude"].between(18, 72)
        & normalized["longitude"].between(-180, -60)
        & (normalized["price"] > 0)
        & (normalized["square_feet"] > 0)
    ]
    normalized = normalized.drop_duplicates("property_id").reset_index(drop=True)
    if len(normalized) < 20:
        raise DataValidationError(
            f"Only {len(normalized)} valid U.S. property rows remain after normalization"
        )
    if len(normalized) > max_rows:
        normalized = (
            normalized.sample(max_rows, random_state=seed).sort_index().reset_index(drop=True)
        )
    return normalized, mapping


def acquire_kaggle_properties(
    dataset: str,
    filename: str,
    output_dir: str | Path,
    column_mapping: dict[str, str] | None,
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, Path, dict[str, str]]:
    path = download_kaggle_file(dataset, filename, output_dir)
    frame = load_table(path)
    normalized, mapping = normalize_kaggle_properties(frame, column_mapping, max_rows, seed)
    return normalized, path, mapping
