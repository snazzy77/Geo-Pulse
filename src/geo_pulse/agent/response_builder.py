from geo_pulse.schemas.reports import AnalysisResponse


def as_text(response: AnalysisResponse) -> str:
    findings = "\n".join(f"- {item}" for item in response.findings)
    artifacts = "\n".join(f"- {name}: {path}" for name, path in response.artifacts.items())
    return f"{response.summary}\n\nFindings:\n{findings}\n\nArtifacts:\n{artifacts}"
