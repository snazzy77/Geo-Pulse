install:
	python -m pip install -e ".[dev]"

sample:
	python scripts/download_sample_data.py

run:
	geo-pulse analyze --question "How does park distance affect price?" --properties data/samples/properties.csv --amenities data/samples/amenities.csv

api:
	uvicorn geo_pulse.api.app:app --reload

test:
	pytest
