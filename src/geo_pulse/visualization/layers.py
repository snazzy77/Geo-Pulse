import folium
import pandas as pd

from geo_pulse.visualization.styles import residual_color
from geo_pulse.visualization.tooltips import property_tooltip


def add_property_layer(map_object: folium.Map, frame: pd.DataFrame, target: str) -> None:
    group = folium.FeatureGroup(name="Properties", show=True)
    for _, row in frame.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5,
            color=residual_color(float(row["residual"])),
            fill=True,
            fill_opacity=0.8,
            tooltip=property_tooltip(row, target),
        ).add_to(group)
    group.add_to(map_object)


def add_amenity_layer(map_object: folium.Map, frame: pd.DataFrame) -> None:
    group = folium.FeatureGroup(name="Amenities", show=False)
    for _, row in frame.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3,
            color="#2ca25f",
            fill=True,
            tooltip=f"{row['amenity_type']}: {row['amenity_id']}",
        ).add_to(group)
    group.add_to(map_object)
