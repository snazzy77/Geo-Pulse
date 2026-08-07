from pathlib import Path

import folium
import pandas as pd

from geo_pulse.visualization.layers import add_amenity_layer, add_property_layer


def build_map(
    predictions: pd.DataFrame,
    amenities: pd.DataFrame,
    target: str,
    output_path: str | Path,
) -> Path:
    center = [float(predictions["latitude"].mean()), float(predictions["longitude"].mean())]
    map_object = folium.Map(location=center, zoom_start=12, control_scale=True)
    add_property_layer(map_object, predictions, target)
    add_amenity_layer(map_object, amenities)
    folium.LayerControl(collapsed=False).add_to(map_object)
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    map_object.save(str(target_path))
    return target_path
