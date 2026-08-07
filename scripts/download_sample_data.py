from geo_pulse.sample_data import generate_sample_data

if __name__ == "__main__":
    properties, amenities = generate_sample_data("data/samples")
    print(f"Wrote {properties}")
    print(f"Wrote {amenities}")
