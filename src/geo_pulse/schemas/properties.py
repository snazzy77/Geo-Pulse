from pydantic import BaseModel, Field


class PropertyRecord(BaseModel):
    property_id: str
    price: float = Field(gt=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    neighborhood: str
    square_feet: float = Field(gt=0)
    beds: float = Field(ge=0)
    baths: float = Field(ge=0)
    year_built: int | None = None


class AmenityRecord(BaseModel):
    amenity_id: str
    amenity_type: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
