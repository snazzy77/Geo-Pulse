from geo_pulse.agent.orchestrator import execute
from geo_pulse.agent.response_builder import as_text
from geo_pulse.schemas.requests import AnalysisRequest

if __name__ == "__main__":
    response = execute(
        AnalysisRequest(
            question="How does park distance affect home price?",
            property_path="data/samples/properties.csv",
            amenity_path="data/samples/amenities.csv",
        )
    )
    print(as_text(response))
