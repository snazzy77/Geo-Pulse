from typer.testing import CliRunner

from geo_pulse.main import app


def test_dashboard_command_is_available():
    result = CliRunner().invoke(app, ["dashboard", "--help"])

    assert result.exit_code == 0
    assert "Start the Geo-Pulse web dashboard" in result.output
