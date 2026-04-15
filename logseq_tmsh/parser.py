from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from .models import Block, ClockEntry

# ── Timestamp patterns ────────────────────────────────────────────────────────
_TS = r"\d{4}-\d{2}-\d{2} \w{3} \d{2}:\d{2}:\d{2}"
_CLOCK_COMPLETED_RE = re.compile(
    r"^CLOCK: \[(" + _TS + r")\]--\[(" + _TS + r")\]"
)
_CLOCK_RUNNING_RE = re.compile(r"^CLOCK: \[(" + _TS + r")\]\s*$")
_TS_FMT = "%Y-%m-%d %a %H:%M:%S"

# ── Property pattern ──────────────────────────────────────────────────────────
# Used by _parse_lines (added in Task 4) — defined here to co-locate all line-level patterns.
_PROPERTY_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*):: (.*)$")


def parse_clock_line(line: str, source_file: str, lineno: int) -> ClockEntry | None:
    """Parse a single CLOCK: line into a ClockEntry.

    Returns None and writes a WARNING to stderr if the line cannot be parsed.
    The precomputed '=> HH:MM:SS' suffix is intentionally ignored; duration
    is always recomputed from the start/end timestamps to guard against drift
    from manual edits.
    """
    stripped = line.strip()

    # Completed clock: CLOCK: [start]--[end] ...
    m = _CLOCK_COMPLETED_RE.search(stripped)
    if m:
        try:
            start = datetime.strptime(m.group(1), _TS_FMT)
            end = datetime.strptime(m.group(2), _TS_FMT)
            return ClockEntry(start=start, end=end, is_running=False)
        except ValueError as exc:
            print(
                f"WARNING: {source_file}:{lineno}: unparseable CLOCK timestamps: {exc}",
                file=sys.stderr,
            )
            return None

    # Running clock: CLOCK: [start]
    m = _CLOCK_RUNNING_RE.search(stripped)
    if m:
        try:
            start = datetime.strptime(m.group(1), _TS_FMT)
            return ClockEntry(start=start, end=None, is_running=True)
        except ValueError as exc:
            print(
                f"WARNING: {source_file}:{lineno}: unparseable CLOCK timestamp: {exc}",
                file=sys.stderr,
            )
            return None

    # Line started with CLOCK: but matched neither pattern
    print(
        f"WARNING: {source_file}:{lineno}: unrecognised CLOCK line: {stripped!r}",
        file=sys.stderr,
    )
    return None
