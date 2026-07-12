import typer

from pictrip_data.master.load_codes import load_codes
from pictrip_data.overseas.countries import COUNTRIES
from pictrip_data.overseas.sync import sync_overseas
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


@app.command("sync-overseas")
def sync_overseas_cmd(
    limit: int | None = typer.Option(None),
    country: list[str] = typer.Option([], "--country"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Sync overseas spots from Wikidata + Commons into overseas_spots."""
    selected = [c for c in COUNTRIES if c.code in country] if country else None
    sync_overseas(countries=selected, limit=limit, dry_run=dry_run)
