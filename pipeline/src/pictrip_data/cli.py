import typer

from pictrip_data.master.load_codes import load_codes
from pictrip_data.overseas.backfill import backfill_overseas_descriptions
from pictrip_data.overseas.countries import COUNTRIES
from pictrip_data.overseas.sync import sync_overseas
from pictrip_data.sync.audit import format_counters
from pictrip_data.sync.daily import sync_daily, sync_full
from pictrip_data.sync.images import validate_images

app = typer.Typer(help="pictrip-data — KTO ETL CLI")


@app.command("sync-daily", help="KTO 일일 증분 동기화")
def sync_daily_cmd() -> None:
    typer.echo(format_counters("sync-daily", sync_daily()))


@app.command("sync-full", help="KTO 전량 동기화")
def sync_full_cmd() -> None:
    typer.echo(format_counters("sync-full", sync_full()))


@app.command("validate-images", help="이미지 URL 생존 검사")
def validate_images_cmd(
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit", min=1),
) -> None:
    result = validate_images(dry_run=dry_run, limit=limit)
    typer.echo(result)


@app.command("load-codes", help="지역·분류 마스터 코드 적재")
def load_codes_cmd() -> None:
    load_codes()


@app.command("sync-overseas", help="해외 스팟 동기화 (Wikidata)")
def sync_overseas_cmd(
    limit: int | None = typer.Option(None),
    country: list[str] = typer.Option([], "--country"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    selected = [c for c in COUNTRIES if c.code in country] if country else None
    typer.echo(
        format_counters(
            "sync-overseas", sync_overseas(countries=selected, limit=limit, dry_run=dry_run)
        )
    )


@app.command("backfill-overseas-descriptions", help="해외 설명 ko.wikipedia 백필")
def backfill_overseas_descriptions_cmd(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    result = backfill_overseas_descriptions(dry_run=dry_run)
    typer.echo(result)
