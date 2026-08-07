import argparse

from geo_pulse.ingestion.boundary_loader import load_geojson

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a GeoJSON boundary file")
    parser.add_argument("path")
    args = parser.parse_args()
    document = load_geojson(args.path)
    feature_count = (
        len(document.get("features", [])) if document["type"] == "FeatureCollection" else 1
    )
    print(f"Valid GeoJSON with {feature_count} feature(s)")
