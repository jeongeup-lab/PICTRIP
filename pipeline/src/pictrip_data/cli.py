"""pictrip-data CLI — entrypoint for sync jobs."""

import typer

from pictrip_data.master.load_codes import load_codes
from pictrip_data.sync.daily import sync_daily

app = typer.Typer(help="PicTrip KTO ETL pipeline")


@app.command("sync-daily")
def sync_daily_cmd() -> None:
    """Daily sync of spots from KTO areaBasedSyncList2 (cron 04:00 KST)."""
    sync_daily()


@app.command("load-codes")
def load_codes_cmd() -> None:
    """One-shot load of region/classification master codes."""
    load_codes()


if __name__ == "__main__":
    app()
