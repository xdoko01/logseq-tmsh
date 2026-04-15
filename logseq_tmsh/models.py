from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

TASK_STATUSES: frozenset[str] = frozenset(
    {"TODO", "DOING", "DONE", "LATER", "WAITING", "CANCELLED", "NOW"}
)


@dataclass
class ClockEntry:
    start: datetime
    end: datetime | None   # None = running clock (no end timestamp recorded)
    is_running: bool       # True when end is None


@dataclass
class Block:
    indent_level: int
    content: str
    properties: dict[str, str] = field(default_factory=dict)
    logbook: list[ClockEntry] = field(default_factory=list)
    children: list[Block] = field(default_factory=list)


@dataclass
class Task:
    raw_title: str                   # everything after the status marker
    status: str                      # one of TASK_STATUSES
    tags: list[str]                  # e.g. ["ori", "meeting"]  (# prefix stripped)
    page_refs: list[str]             # e.g. ["OrisalesRetirement"]  ([[ ]] stripped)
    clock_entries: list[ClockEntry]
    time_spent_override: int | None  # minutes from time_spent:: property; replaces CLOCK time
    started: date | None             # from started:: property
    completed: date | None           # from completed:: property
    description: list[str]           # flattened child block text
    source_file: str                 # e.g. "2026_04_15.md"
    source_date: date                # parsed from filename


@dataclass
class AttributedTask:
    """A Task with computed time attribution for a specific query period."""
    task: Task
    period_seconds: int    # seconds of work that fall within the query period
    total_seconds: int     # seconds across ALL clock entries (ignores period)
    has_running_clock: bool
