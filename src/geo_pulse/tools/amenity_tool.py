from geo_pulse.ingestion.osm_client import fetch_amenities_for_place
from geo_pulse.ingestion.property_loader import load_table

load_amenities = load_table
fetch_osm_amenities = fetch_amenities_for_place
