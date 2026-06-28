import typer

from pictrip_data.master.load_codes import load_codes
from pictrip_data.sync.daily import sync_daily, sync_full

app = typer.Typer(help="pictrip-data — KTO ETL CLI")


@app.command("sync-daily")
def sync_daily_cmd() -> None:
    """Daily incremental sync of spots from areaBasedSyncList2 (cron 04:00 KST)."""
    sync_daily()


@app.command("sync-full")
def sync_full_cmd() -> None:
    """Full reconcile — no modifiedtime filter (weekly; quota-aware)."""
    sync_full()


@app.command("load-codes")
def load_codes_cmd() -> None:
    """One-shot load of region/classification master codes."""
    load_codes()
