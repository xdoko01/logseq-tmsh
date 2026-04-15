from __future__ import annotations

import json
import re
from collections import OrderedDict

from .models import AttributedTask

_TAG_RE = re.compile(r"#[a-zA-Z][a-zA-Z0-9_-]*\s*")
_REF_RE = re.compile(r"\[\[([^\]]+)\]\]")


def format_duration(seconds: int) -> str:
    """Format a duration in seconds as HH:MM:SS."""
    seconds = max(0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _apply_title_transforms(title: str, strip_tags: bool, strip_refs: bool) -> str:
    if strip_tags:
        title = _TAG_RE.sub("", title)
    if strip_refs:
        title = _REF_RE.sub(r"\1", title)
    return title.strip()


def _task_to_dict(
    attributed: AttributedTask,
    fields: list[str],
    strip_tags: bool,
    strip_refs: bool,
    date_format: str,
) -> dict:
    t = attributed.task
    time_str = format_duration(attributed.period_seconds)
    if attributed.has_running_clock:
        time_str += "~"

    total_str = format_duration(attributed.total_seconds)

    row: dict = OrderedDict()
    for field in fields:
        if field == "title":
            row["title"] = _apply_title_transforms(t.raw_title, strip_tags, strip_refs)
        elif field == "status":
            row["status"] = t.status
        elif field == "time_period":
            row["time_period"] = time_str
        elif field == "time_total":
            row["time_total"] = total_str
        elif field == "time_override":
            row["time_override"] = t.time_spent_override
        elif field == "started":
            row["started"] = t.started.strftime(date_format) if t.started else None
        elif field == "completed":
            row["completed"] = t.completed.strftime(date_format) if t.completed else None
        elif field == "tags":
            row["tags"] = t.tags
        elif field == "refs":
            row["refs"] = t.page_refs
        elif field == "has_running_clock":
            row["has_running_clock"] = attributed.has_running_clock
        elif field == "description":
            row["description"] = t.description
        elif field == "source_file":
            row["source_file"] = t.source_file
        elif field == "source_date":
            row["source_date"] = t.source_date.strftime(date_format)
        # Unknown fields are silently skipped
    return row


def format_json(
    tasks: list[AttributedTask],
    fields: list[str],
    indent: int | None,
    strip_tags: bool,
    strip_refs: bool,
    date_format: str,
) -> str:
    """Serialise tasks to JSON. Compact when indent=None, pretty when indent is an int."""
    rows = [_task_to_dict(a, fields, strip_tags, strip_refs, date_format) for a in tasks]
    return json.dumps(rows, indent=indent, ensure_ascii=False)


def format_pretty(
    tasks: list[AttributedTask],
    fields: list[str],
    strip_tags: bool,
    strip_refs: bool,
    date_format: str,
) -> str:
    """Serialise tasks to a fixed-width human-readable table."""
    if not tasks:
        return "(no results)"

    rows = [_task_to_dict(a, fields, strip_tags, strip_refs, date_format) for a in tasks]

    # Compute column widths (at least as wide as header)
    widths: dict[str, int] = {f: len(f) for f in fields}
    for row in rows:
        for f in fields:
            val = row.get(f)
            if isinstance(val, list):
                cell = ", ".join(str(v) for v in val)
            elif val is None:
                cell = ""
            else:
                cell = str(val)
            widths[f] = max(widths[f], len(cell))

    def _render_row(row: dict, upper: bool = False) -> str:
        cells = []
        for f in fields:
            val = row.get(f)
            if isinstance(val, list):
                cell = ", ".join(str(v) for v in val)
            elif val is None:
                cell = ""
            else:
                cell = str(val)
            if upper:
                cell = f.upper()
            cells.append(cell.ljust(widths[f]))
        return "  ".join(cells).rstrip()

    header = _render_row({}, upper=True)
    data_rows = [_render_row(r) for r in rows]
    return "\n".join([header] + data_rows)
