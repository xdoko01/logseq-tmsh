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
# Note: requires a space after '::' (e.g. 'key:: value'). LogSeq always emits this space,
# but manually edited files omitting the space will silently skip the property.
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


def parse_file(path: Path) -> list[Block]:
    """Parse a LogSeq journal .md file into a flat list of top-level Blocks.

    LogSeq indentation convention:
      - Bullet lines:        N tabs + '- ' + content
      - Continuation lines:  N tabs + '  ' + content  (properties, LOGBOOK)
      - Child bullet lines:  (N+1) tabs + '- ' + content
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return _parse_lines(lines, path.name)


def _parse_lines(lines: list[str], source_name: str) -> list[Block]:
    """Build a list of top-level Blocks from raw markdown lines."""
    root_blocks: list[Block] = []
    # Stack of (indent_level, Block) — top is the most recently opened block
    stack: list[tuple[int, Block]] = []
    in_logbook = False

    for lineno, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped:
            continue
        # Skip section headers (## ...) — they are structural markers, not blocks
        if stripped.startswith("#"):
            continue

        tab_count = len(raw) - len(raw.lstrip("\t"))
        rest = raw[tab_count:]  # content after leading tabs

        if rest.startswith("- "):
            # ── New block ────────────────────────────────────────────────────
            in_logbook = False
            content = rest[2:]  # strip leading '- '

            # Skip section-header bullets (e.g. '- ## New Tasks') — structural
            # markers only; their children are promoted to the enclosing scope.
            if content.startswith("#"):
                # Pop the stack as if this indent level were closed, so the
                # header's children will be added to the correct parent or root.
                while stack and stack[-1][0] >= tab_count:
                    stack.pop()
                continue

            block = Block(indent_level=tab_count, content=content)

            # Pop blocks at same or deeper indent (they are now closed)
            while stack and stack[-1][0] >= tab_count:
                stack.pop()

            if stack:
                stack[-1][1].children.append(block)
            else:
                root_blocks.append(block)

            stack.append((tab_count, block))

        elif stack:
            # ── Continuation line ─────────────────────────────────────────────
            # Belongs to the most recently opened block (top of stack).
            current = stack[-1][1]

            if stripped == ":LOGBOOK:":
                in_logbook = True
            elif stripped == ":END:":
                in_logbook = False
            elif in_logbook and stripped.startswith("CLOCK:"):
                entry = parse_clock_line(stripped, source_name, lineno)
                if entry is not None:
                    current.logbook.append(entry)
            elif in_logbook:
                pass  # other LOGBOOK lines (e.g. blank or future formats) — ignore
            else:
                m = _PROPERTY_RE.match(stripped)
                if m:
                    current.properties[m.group(1)] = m.group(2)

    return root_blocks
