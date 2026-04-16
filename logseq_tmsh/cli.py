from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import typer

from .config import load_config
from .extractor import extract_tasks
from .filters import attribute_tasks, filter_tasks
from .formatters import format_json, format_pretty
from .models import Task
from .parser import parse_file

app = typer.Typer(help="Extract time-tracking data from LogSeq journal CLOCK entries.")


# ── Shared option definitions ──────────────────────────────────────────────────
_TAG_OPT = typer.Option(None, "--tag", help="Filter by tag (AND logic, repeatable)")
_REF_OPT = typer.Option(None, "--ref", help="Filter by page ref (AND logic, repeatable)")
_STATUS_OPT = typer.Option(None, "--status", help="Filter by status (OR logic, repeatable)")
_INCLUDE_ZERO_OPT = typer.Option(False, "--include-zero", help="Include tasks with 0 time in period")
_PRETTY_OPT = typer.Option(False, "--pretty", help="Human-readable output instead of JSON")
_INDENT_OPT = typer.Option(None, "--indent", help="Pretty-print JSON with N spaces (e.g. --indent 2)")
_FIELDS_OPT = typer.Option(None, "--fields", help="Comma-separated field list, overrides default_fields config")
_STRIP_TAGS_OPT = typer.Option(False, "--strip-tags", help="Remove #tags from title")
_STRIP_REFS_OPT = typer.Option(False, "--strip-refs", help="Convert [[Ref]] to plain Ref in title")
_CONFIG_OPT = typer.Option(None, "--config", help="Path to an additional config TOML file")


def _run_query(
    period_start: date,
    period_end: date,
    tag: list[str] | None,
    ref: list[str] | None,
    status: list[str] | None,
    include_zero: bool,
    pretty: bool,
    indent: int | None,
    fields: str | None,
    strip_tags: bool,
    strip_refs: bool,
    config_path: Path | None,
) -> None:
    cfg = load_config(config_path)

    # Resolve journal paths to scan
    scan_dirs: list[Path] = []
    if cfg.journals:
        scan_dirs.append(Path(cfg.journals))
    for d in cfg.extra_dirs:
        scan_dirs.append(Path(d))

    if not scan_dirs:
        typer.echo(
            "ERROR: No journal path configured. Run 'ltmsh configure' to set up.",
            err=True,
        )
        raise typer.Exit(1)

    # Resolve output fields
    output_fields = [f.strip() for f in fields.split(",")] if fields else cfg.default_fields

    # Collect .md files within the date range
    all_tasks: list[Task] = []
    buffer = timedelta(days=1)
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            typer.echo(f"ERROR: Journal path not found: {scan_dir}", err=True)
            raise typer.Exit(2)

        for md_file in sorted(scan_dir.glob("*.md")):
            # Try to parse date from filename YYYY_MM_DD.md
            try:
                stem = md_file.stem  # e.g. "2026_04_15"
                parts = stem.split("_")
                if len(parts) != 3:
                    continue
                file_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                continue  # skip non-journal files

            # Only parse files that could contain relevant CLOCKs.
            # Use a 1-day buffer on each side to capture midnight-crossing CLOCKs.
            if file_date < period_start - buffer or file_date > period_end + buffer:
                continue

            try:
                blocks = parse_file(md_file)
            except OSError as exc:
                typer.echo(f"ERROR: Cannot read {md_file}: {exc}", err=True)
                raise typer.Exit(3)

            tasks = extract_tasks(
                blocks,
                md_file.name,
                file_date,
                time_spent_property=cfg.time_spent_property,
                completed_property=cfg.completed_property,
                started_property=cfg.started_property,
            )
            all_tasks.extend(tasks)

    # Attribute and filter
    attributed = attribute_tasks(
        all_tasks, period_start, period_end, midnight_split=cfg.midnight_split
    )
    filtered = filter_tasks(
        attributed,
        tags=list(tag) if tag else None,
        refs=list(ref) if ref else None,
        statuses=list(status) if status else None,
        include_zero=include_zero or cfg.include_zero,
    )

    # Format and output
    if pretty:
        print(format_pretty(filtered, output_fields, strip_tags, strip_refs, cfg.date_format))
    else:
        print(format_json(filtered, output_fields, indent, strip_tags, strip_refs, cfg.date_format))


@app.command()
def today(
    tag: Optional[list[str]] = _TAG_OPT,
    ref: Optional[list[str]] = _REF_OPT,
    status: Optional[list[str]] = _STATUS_OPT,
    include_zero: bool = _INCLUDE_ZERO_OPT,
    pretty: bool = _PRETTY_OPT,
    indent: Optional[int] = _INDENT_OPT,
    fields: Optional[str] = _FIELDS_OPT,
    strip_tags: bool = _STRIP_TAGS_OPT,
    strip_refs: bool = _STRIP_REFS_OPT,
    config: Optional[Path] = _CONFIG_OPT,
) -> None:
    """Show tasks worked on today."""
    today_date = date.today()
    _run_query(
        today_date, today_date,
        tag, ref, status, include_zero, pretty, indent, fields,
        strip_tags, strip_refs, config,
    )


@app.command()
def week(
    tag: Optional[list[str]] = _TAG_OPT,
    ref: Optional[list[str]] = _REF_OPT,
    status: Optional[list[str]] = _STATUS_OPT,
    include_zero: bool = _INCLUDE_ZERO_OPT,
    pretty: bool = _PRETTY_OPT,
    indent: Optional[int] = _INDENT_OPT,
    fields: Optional[str] = _FIELDS_OPT,
    strip_tags: bool = _STRIP_TAGS_OPT,
    strip_refs: bool = _STRIP_REFS_OPT,
    config: Optional[Path] = _CONFIG_OPT,
) -> None:
    """Show tasks worked on during the current week (Monday to today)."""
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    _run_query(
        monday, today_date,
        tag, ref, status, include_zero, pretty, indent, fields,
        strip_tags, strip_refs, config,
    )


def _parse_date_arg(value: str, option_name: str) -> date:
    """Parse a YYYY-MM-DD string into a date, exiting on error."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        typer.echo(f"ERROR: {option_name} must be YYYY-MM-DD, got: {value!r}", err=True)
        raise typer.Exit(1)


@app.command(name="range")
def range_cmd(
    from_date: str = typer.Option(..., "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="End date (YYYY-MM-DD)"),
    tag: Optional[list[str]] = _TAG_OPT,
    ref: Optional[list[str]] = _REF_OPT,
    status: Optional[list[str]] = _STATUS_OPT,
    include_zero: bool = _INCLUDE_ZERO_OPT,
    pretty: bool = _PRETTY_OPT,
    indent: Optional[int] = _INDENT_OPT,
    fields: Optional[str] = _FIELDS_OPT,
    strip_tags: bool = _STRIP_TAGS_OPT,
    strip_refs: bool = _STRIP_REFS_OPT,
    config: Optional[Path] = _CONFIG_OPT,
) -> None:
    """Show tasks worked on in a specific date range."""
    start = _parse_date_arg(from_date, "--from")
    end = _parse_date_arg(to_date, "--to")
    if start > end:
        typer.echo("ERROR: --from date must not be after --to date", err=True)
        raise typer.Exit(1)
    _run_query(
        start, end,
        tag, ref, status, include_zero, pretty, indent, fields,
        strip_tags, strip_refs, config,
    )
