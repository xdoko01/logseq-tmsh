from __future__ import annotations

import re
import sys
from datetime import date

from .models import Block, Task, TASK_STATUSES

# ── Regex helpers ─────────────────────────────────────────────────────────────
_STATUS_RE = re.compile(
    r"^(" + "|".join(sorted(TASK_STATUSES, key=len, reverse=True)) + r")\s+(.*)",
    re.DOTALL,
)
_TAG_RE = re.compile(r"#([a-zA-Z][a-zA-Z0-9_-]*)")
_REF_RE = re.compile(r"\[\[([^\]]+)\]\]")
# LogSeq date: [[Apr 15th, 2026]]
_LOGSEQ_DATE_RE = re.compile(
    r"\[\[(\w{3})\s+(\d{1,2})(?:st|nd|rd|th),\s+(\d{4})\]\]"
)
_MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_logseq_date(value: str, prop_name: str, source_file: str) -> date | None:
    """Parse a LogSeq date string like '[[Apr 15th, 2026]]' into a Python date.

    Returns None and logs a warning to stderr if the value cannot be parsed.
    """
    m = _LOGSEQ_DATE_RE.search(value)
    if not m:
        print(
            f"WARNING: {source_file}: unparseable date in '{prop_name}': {value!r}",
            file=sys.stderr,
        )
        return None
    try:
        month = _MONTH_MAP[m.group(1)]
        day = int(m.group(2))
        year = int(m.group(3))
        return date(year, month, day)
    except (KeyError, ValueError) as exc:
        print(
            f"WARNING: {source_file}: unparseable date in '{prop_name}': {exc}",
            file=sys.stderr,
        )
        return None


def _flatten_description(block: Block, indent: int = 0) -> list[str]:
    """Recursively flatten child blocks into a list of indented text strings."""
    result: list[str] = []
    for child in block.children:
        result.append("  " * indent + child.content)
        result.extend(_flatten_description(child, indent + 1))
    return result


def extract_tasks(
    blocks: list[Block],
    source_file: str,
    source_date: date,
    time_spent_property: str = "time_spent",
    completed_property: str = "completed",
    started_property: str = "started",
) -> list[Task]:
    """Walk a list of Blocks (and their children recursively) and return all Task objects."""
    tasks: list[Task] = []
    _walk(
        blocks,
        source_file,
        source_date,
        time_spent_property,
        completed_property,
        started_property,
        tasks,
    )
    return tasks


def _walk(
    blocks: list[Block],
    source_file: str,
    source_date: date,
    time_spent_property: str,
    completed_property: str,
    started_property: str,
    out: list[Task],
) -> None:
    for block in blocks:
        m = _STATUS_RE.match(block.content)
        if m:
            status = m.group(1)
            raw_title = m.group(2).strip()
            tags = _TAG_RE.findall(raw_title)
            page_refs = _REF_RE.findall(raw_title)

            # Parse time_spent_override
            override_raw = block.properties.get(time_spent_property)
            time_spent_override: int | None = None
            if override_raw is not None:
                try:
                    time_spent_override = int(override_raw.strip())
                except ValueError:
                    print(
                        f"WARNING: {source_file}: invalid {time_spent_property} value: {override_raw!r}",
                        file=sys.stderr,
                    )

            # Parse started / completed dates
            started = None
            started_raw = block.properties.get(started_property)
            if started_raw:
                started = _parse_logseq_date(started_raw, started_property, source_file)

            completed = None
            completed_raw = block.properties.get(completed_property)
            if completed_raw:
                completed = _parse_logseq_date(completed_raw, completed_property, source_file)

            description = _flatten_description(block)

            out.append(
                Task(
                    raw_title=raw_title,
                    status=status,
                    tags=tags,
                    page_refs=page_refs,
                    clock_entries=list(block.logbook),
                    time_spent_override=time_spent_override,
                    started=started,
                    completed=completed,
                    description=description,
                    source_file=source_file,
                    source_date=source_date,
                )
            )
        # Recurse into children regardless — nested tasks are valid
        _walk(
            block.children,
            source_file,
            source_date,
            time_spent_property,
            completed_property,
            started_property,
            out,
        )
