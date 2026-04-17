from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .config import load_config
from .extractor import extract_tasks
from .filters import attribute_tasks, filter_tasks
from .formatters import format_json, format_pretty
from .models import Task
from .parser import parse_file

app = typer.Typer(help="Extract time-tracking data from LogSeq journal CLOCK entries.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ltmsh {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


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
_SCAN_FROM_OPT = typer.Option(
    None, "--scan-from",
    help="Ignore journal files dated before this date (YYYY-MM-DD). "
         "Default: scan all files. Use to speed up queries when old tasks are irrelevant.",
)


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
    scan_from: str | None,
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

    # Resolve the effective scan_from lower bound.
    # CLI flag takes precedence over config; both are optional.
    effective_scan_from: date | None = cfg.scan_from
    if scan_from is not None:
        try:
            effective_scan_from = date.fromisoformat(scan_from)
        except ValueError:
            typer.echo(f"ERROR: --scan-from must be YYYY-MM-DD, got: {scan_from!r}", err=True)
            raise typer.Exit(1)

    # Collect .md files to parse.
    #
    # By default we scan ALL journal files regardless of their date, because a
    # task created long ago can have CLOCK entries added recently (the CLOCK
    # lives in the same file as the task block, not in today's journal).
    #
    # We keep an upper-bound skip: files dated after period_end + buffer cannot
    # contain CLOCKs relevant to the query period.
    #
    # A 2-day buffer handles CLOCKs that straddle midnight (e.g. forgotten to
    # clock out Friday, stopped Monday morning).
    #
    # Users who know their tasks are recent can pass --scan-from to skip old
    # files and speed up large vaults.
    all_tasks: list[Task] = []
    buffer = timedelta(days=2)
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

            # Skip files created after the query period (can't have relevant CLOCKs).
            if file_date > period_end + buffer:
                continue
            # Honour the optional scan_from lower bound.
            if effective_scan_from is not None and file_date < effective_scan_from:
                continue

            try:
                blocks = parse_file(md_file)
            except OSError as exc:
                # Exit 3 = journal file I/O error; malformed CLOCK lines are
                # handled gracefully as warnings inside parse_file(), not here.
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
    scan_from: Optional[str] = _SCAN_FROM_OPT,
) -> None:
    """Show tasks worked on today."""
    today_date = date.today()
    _run_query(
        today_date, today_date,
        tag, ref, status, include_zero, pretty, indent, fields,
        strip_tags, strip_refs, config, scan_from,
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
    scan_from: Optional[str] = _SCAN_FROM_OPT,
) -> None:
    """Show tasks worked on during the current week (Monday to today)."""
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    _run_query(
        monday, today_date,
        tag, ref, status, include_zero, pretty, indent, fields,
        strip_tags, strip_refs, config, scan_from,
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
    scan_from: Optional[str] = _SCAN_FROM_OPT,
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
        strip_tags, strip_refs, config, scan_from,
    )


@app.command()
def configure() -> None:
    """Interactive setup wizard — creates or updates ~/.logseq-tmsh/config.toml."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]

    config_dir = Path.home() / ".logseq-tmsh"
    config_path = config_dir / "config.toml"
    config_dir.mkdir(exist_ok=True)

    # Load existing values as defaults for prompts
    existing: dict = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                existing = tomllib.load(f)
        except Exception as exc:
            typer.echo(
                f"Warning: existing config could not be parsed ({exc}). Starting from defaults.",
                err=True,
            )

    def _get(section: str, key: str, fallback):
        return existing.get(section, {}).get(key, fallback)

    typer.echo("logseq-tmsh configuration wizard")
    typer.echo("Press Enter to keep the current value shown in [brackets].\n")

    journals = typer.prompt(
        "Journal directory path",
        default=_get("paths", "journals", ""),
    )
    extra_dirs_raw = typer.prompt(
        "Extra directories to scan (comma-separated, leave empty for none)",
        default=",".join(_get("paths", "extra_dirs", [])),
    )
    extra_dirs = [d.strip() for d in extra_dirs_raw.split(",") if d.strip()]
    scan_from_cfg = typer.prompt(
        "Oldest journal file date to scan (YYYY-MM-DD, leave empty to scan all files)",
        default=_get("paths", "scan_from", "") or "",
    )
    scan_from_cfg = scan_from_cfg.strip() or None

    midnight_split = typer.prompt(
        "Midnight-crossing CLOCK strategy [split/start/end]",
        default=_get("parsing", "midnight_split", "split"),
    )
    time_spent_property = typer.prompt(
        "Property name for time override (minutes)",
        default=_get("parsing", "time_spent_property", "time_spent"),
    )
    completed_property = typer.prompt(
        "Property name for completion date",
        default=_get("parsing", "completed_property", "completed"),
    )
    started_property = typer.prompt(
        "Property name for start date",
        default=_get("parsing", "started_property", "started"),
    )
    date_format = typer.prompt(
        "Date output format (strftime)",
        default=_get("output", "date_format", "%Y-%m-%d"),
    )
    datetime_format = typer.prompt(
        "Datetime output format (strftime)",
        default=_get("output", "datetime_format", "%Y-%m-%d %H:%M"),
    )
    default_fields_raw = typer.prompt(
        "Default output fields (comma-separated)",
        default=",".join(
            _get("output", "default_fields", ["title", "status", "time_period", "started", "completed", "tags"])
        ),
    )
    default_fields = [f.strip() for f in default_fields_raw.split(",") if f.strip()]
    include_zero = typer.confirm(
        "Include tasks with 0 time logged by default?",
        default=_get("output", "include_zero", False),
    )

    # Write config using manual TOML serialisation (no toml-write dependency)
    def _toml_str(v: str) -> str:
        return (
            '"'
            + v.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            + '"'
        )

    def _toml_list(lst: list[str]) -> str:
        return "[" + ", ".join(_toml_str(x) for x in lst) + "]"

    scan_from_line = f"scan_from = {_toml_str(scan_from_cfg)}\n" if scan_from_cfg else ""
    toml_content = f"""\
[paths]
journals = {_toml_str(journals)}
extra_dirs = {_toml_list(extra_dirs)}
{scan_from_line}
[parsing]
midnight_split = {_toml_str(midnight_split)}
time_spent_property = {_toml_str(time_spent_property)}
completed_property = {_toml_str(completed_property)}
started_property = {_toml_str(started_property)}

[output]
date_format = {_toml_str(date_format)}
datetime_format = {_toml_str(datetime_format)}
default_fields = {_toml_list(default_fields)}
include_zero = {"true" if include_zero else "false"}
"""

    config_path.write_text(toml_content, encoding="utf-8")
    typer.echo(f"\nConfiguration saved to {config_path}")
