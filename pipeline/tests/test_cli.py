from unittest.mock import patch

from typer.testing import CliRunner

from pictrip_data.cli import app

runner = CliRunner()


def test_sync_daily_command_invokes_sync():
    with patch("pictrip_data.cli.sync_daily") as m:
        result = runner.invoke(app, ["sync-daily"])
    assert result.exit_code == 0
    m.assert_called_once()


def test_sync_full_command_invokes_full():
    with patch("pictrip_data.cli.sync_full") as m:
        result = runner.invoke(app, ["sync-full"])
    assert result.exit_code == 0
    m.assert_called_once()
