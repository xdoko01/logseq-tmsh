# logseq-tmsh — Design Specification

**Date:** 2026-04-15
**Status:** Approved

---

## Overview

`logseq-tmsh` is a Python CLI tool that reads LogSeq journal markdown files and extracts time-tracking information from LOGBOOK CLOCK entries. It is designed primarily for use by Claude Code (AI) as part of a timesheet skill, with human-readable output also supported.

Published as PyPI package `logseq-tmsh`, invoked via command `ltmsh`.

---

## Project Structure

```
logseq-tmsh/
├── pyproject.toml              # uv/pip metadata, entry point: ltmsh
├── logseq_tmsh/
│   ├── __init__.py
│   ├── cli.py                  # Typer app — all commands and flags
│   ├── config.py               # TOML config loading + defaults
│   ├── parser.py               # Pass 1: .md → Block tree
│   ├── extractor.py            # Pass 2: Block tree → Task objects
│   ├── filters.py              # Pass 3: Task list → filtered/attributed Task list
│   ├── formatters.py           # Pass 4: Task list → JSON / human output
│   └── models.py               # Dataclasses: Block, Task, ClockEntry, Config
├── tests/
│   ├── fixtures/               # Sample .md snippets for unit tests
│   └── test_*.py
└── docs/
    └── superpowers/specs/
```

**Technology stack:**
- Python 3.10+ (uses `tomllib` backport `tomli` for 3.10; stdlib `tomllib` for 3.11+)
- [Typer](https://typer.tiangolo.com/) — CLI framework
- [pytest](https://pytest.org/) — test runner
- [uv](https://github.com/astral-sh/uv) — package/project management

---

## Data Models (`models.py`)

```python
@dataclass
class ClockEntry:
    start: datetime
    end: datetime | None        # None = running clock (no end timestamp)
    is_running: bool            # True when end is None
    # duration_in_period is computed by filters.py, not stored here

@dataclass
class Task:
    raw_title: str              # everything after the status marker
    status: str                 # TODO / DOING / DONE / LATER / WAITING / CANCELLED / NOW
    tags: list[str]             # e.g. ["ori", "meeting"] (# prefix stripped)
    page_refs: list[str]        # e.g. ["OrisalesRetirement"] ([[]] stripped)
    clock_entries: list[ClockEntry]
    time_spent_override: int | None   # minutes from time_spent:: property; replaces CLOCK time
    started: date | None        # parsed from started:: [[LogSeq date]]
    completed: date | None      # parsed from completed:: [[LogSeq date]]
    description: list[str]      # flattened text of direct child blocks
    source_file: str            # journal filename (e.g. "2026_04_15.md")
    source_date: date           # date parsed from filename
```

---

## Pipeline

Data flows through four independent, testable stages:

```
.md files ──► parser.py ──► [Block tree]
                         ──► extractor.py ──► [Task list]
                                          ──► filters.py ──► [attributed Tasks]
                                                         ──► formatters.py ──► stdout
```

### Pass 1 — `.md` → Block tree (`parser.py`)

LogSeq markdown uses indentation (tab or 2-space) to express hierarchy. Each bullet (`- `) starts a new block. Non-bullet lines at the same indent level as the previous block are continuations (properties, LOGBOOK content).

**Block structure:**
```
Block(
  indent_level: int,
  content: str,                  # raw text after "- "
  properties: dict[str, str],    # key:: value pairs
  logbook: list[ClockEntry],     # parsed from :LOGBOOK: ... :END:
  children: list[Block]          # nested child blocks
)
```

**LOGBOOK parsing rules:**
- `CLOCK: [YYYY-MM-DD Day HH:MM:SS]` — running clock (no end time)
- `CLOCK: [start]--[end] => HH:MM:SS` — completed interval; the `=> HH:MM:SS` suffix is **ignored** and duration is always recomputed from timestamps (the precomputed value can drift after manual edits)
- Lines between `:LOGBOOK:` and `:END:` that don't match CLOCK patterns are silently ignored

### Pass 2 — Block tree → Tasks (`extractor.py`)

A block is recognised as a task if its content begins with one of:
`TODO`, `DOING`, `DONE`, `LATER`, `WAITING`, `CANCELLED`, `NOW`

From each task block:
- `status` — the opening marker word
- `raw_title` — all text after the marker
- `tags` — all `#word` tokens (regex: `#[a-zA-Z][a-zA-Z0-9_-]*`)
- `page_refs` — all `[[...]]` tokens, inner text extracted, `[[` and `]]` stripped
- `time_spent_override` — integer value of the configured `time_spent_property`; parsed as minutes
- `started` / `completed` — parsed from LogSeq date format `[[Mon Nth, YYYY]]` → Python `date`
- `clock_entries` — from the block's LOGBOOK
- `description` — flattened text of direct child blocks, one string per child; sub-nesting preserved as indented text
- `source_file`, `source_date` — derived from the journal filename `YYYY_MM_DD.md`

### Pass 3 — Time attribution (`filters.py`)

Given a query period `[period_start, period_end]` (both inclusive, day-granularity):

**Branch A — `time_spent_override` is set:**
1. Determine the attribution date:
   - If `completed` date is present and falls within the period → attribute override to that date
   - If `completed` date is present but outside the period → task contributes 0 time to this period
   - If `completed` date is absent → fall back to `source_date` (the journal file date)
2. Create a single synthetic ClockEntry representing the override minutes on the attribution date

**Branch B — no `time_spent_override`:**
For each ClockEntry in the task:
1. If running (no end time): use `datetime.now()` as provisional end; mark `is_running=True` on output
2. Apply midnight-split strategy (see below) to clip the interval to `[period_start, period_end]`
3. Sum only the intersecting duration

**Midnight-split strategies** (configured via `parsing.midnight_split`):

| Strategy | Behaviour |
|---|---|
| `split` (default) | Interval is split at midnight; only the portion within the query period counts |
| `start` | Entire interval attributed to the start day; counts only if start day is in period |
| `end` | Entire interval attributed to the end day; counts only if end day is in period |

**Post-attribution filtering:**
- Tasks with total attributed time = 0 are dropped unless `--include-zero` is set
- Tag filter (`--tag`): AND logic — task must have ALL specified tags
- Ref filter (`--ref`): AND logic — task must reference ALL specified pages
- Status filter (`--status`): OR logic — task must match ANY specified status

#### Edge Cases (documented explicitly)

| Scenario | Behaviour |
|---|---|
| Running clock (no end time) | Included with provisional duration using `now` as end; `has_running_clock: true` in output; `~` suffix on `time_period` in pretty output |
| CLOCK crossing midnight | Handled according to `midnight_split` config; default `split` divides at 00:00 |
| Multiple CLOCKs on one task spanning different days | Each CLOCK clipped independently; only in-period portions summed |
| `time_spent_override` with no `completed` date | Falls back to `source_date` (journal file date) for period attribution. **This fallback is always reported to stderr as a warning** so the user can add a `completed::` property if desired |
| `time_spent_override` with `completed` date outside query period | Task contributes 0 time; dropped unless `--include-zero` |
| Task with no LOGBOOK and no `time_spent_override` | Time = 0; dropped unless `--include-zero` |
| Malformed CLOCK line (unparseable timestamps) | Entry skipped; warning written to stderr with filename and line number; parsing continues |
| Malformed property value (e.g. unparseable date) | Property treated as absent; warning to stderr |

### Pass 4 — Formatting (`formatters.py`)

**JSON output** (default) — compact single-line array unless `--indent` is used:

```json
[{"title":"#ori [[Orisales]] Regular Daily Check","status":"DONE","time_period":"01:35:31"}]
```

With `--indent` (default 2 spaces):
```json
[
  {
    "title": "#ori [[Orisales]] Regular Daily Check",
    "status": "DONE",
    "time_period": "01:35:31"
  }
]
```

**Pretty output** (`--pretty`) — fixed-width columns, header row, order matches `--fields`:

```
SOURCE_DATE  STATUS  TIME_PERIOD  TITLE
2026-04-15   DONE    01:35:31     #ori [[Orisales]] Regular Daily Check
2026-04-15   DONE    00:18:47     #ori Share CIS offline payments with [[MensikDavid]]
2026-04-15   TODO    00:03:18~    #ori Study [[Windsurf]] workflows for [[Lumo]] pilot
```

`~` is appended to `time_period` in both JSON and pretty output when `has_running_clock` is true.

---

## Output Fields

| Field | Description |
|---|---|
| `title` | Task title; raw by default, modified by `--strip-tags` / `--strip-refs` |
| `status` | `TODO` / `DOING` / `DONE` / `LATER` / `WAITING` / `CANCELLED` / `NOW` |
| `time_period` | Time attributed to the queried period (format: `HH:MM:SS`); `~` suffix if running clock |
| `time_total` | Total time across all CLOCKs ever (not clipped to period) |
| `time_override` | Raw `time_spent` property value in minutes, if present |
| `started` | Value of `started::` property, formatted per `date_format` config |
| `completed` | Value of `completed::` property, formatted per `date_format` config |
| `tags` | List of `#tags` (without `#` prefix) |
| `refs` | List of `[[page refs]]` (brackets stripped) |
| `has_running_clock` | `true` if any CLOCK has no end time |
| `description` | Child block content (flattened); omitted unless included in `--fields` |
| `source_file` | Journal filename the task lives in |
| `source_date` | Date of that journal, formatted per `date_format` config |

Default field selection is controlled by `output.default_fields` in config.

**Title transformations:**
- `--strip-tags` — removes all `#tag` tokens from title entirely
- `--strip-refs` — converts `[[PageRef]]` to `PageRef` (plain text, brackets removed)
- Both flags can be combined

---

## CLI Reference

```bash
# Commands
ltmsh today      [OPTIONS]                     # query today
ltmsh week       [OPTIONS]                     # query current Mon → today
ltmsh range      --from DATE --to DATE [OPTIONS]  # query explicit range
ltmsh configure                                # interactive config setup

# Filter options (all commands)
--tag TEXT        # filter by tag; AND logic; repeatable
--ref TEXT        # filter by page ref; AND logic; repeatable
--status TEXT     # filter by status; OR logic; repeatable
--include-zero    # include tasks with 0 time in period

# Output options (all commands)
--pretty          # human-readable output (default: JSON)
--indent [N]      # pretty-print JSON; default N=2 when flag present
--fields TEXT     # comma-separated field list; overrides default_fields config
--strip-tags      # remove #tags from title
--strip-refs      # convert [[Ref]] to Ref in title
```

---

## Configuration

**Config file locations** (local takes precedence over user-level):
1. `./logseq-tmsh.toml` — project-local config
2. `~/.logseq-tmsh/config.toml` — user-level config (created by `ltmsh configure`)

```toml
[paths]
journals = "C:/Users/Otakar/OneDrive/Dokumenty/Logseq/journals"
extra_dirs = []               # additional directories to scan

[parsing]
midnight_split = "split"          # "split" | "start" | "end"
time_spent_property = "time_spent"
completed_property = "completed"  # load-bearing: required for time_spent override period attribution
started_property = "started"      # output-only: used for the started field, not for time calculation

[output]
date_format = "%Y-%m-%d"
datetime_format = "%Y-%m-%d %H:%M"
default_fields = ["title", "status", "time_period", "started", "completed", "tags"]
include_zero = false
```

**`ltmsh configure`** — interactive wizard that prompts for each config value and writes `~/.logseq-tmsh/config.toml`. Safe to re-run: merges new values, preserves unrelated existing keys.

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success (empty result set is still success) |
| `1` | Config or argument error |
| `2` | Journal path not found or unreadable |
| `3` | Parse error in a journal file (file + line number reported to stderr) |

Errors are always written to **stderr** as human-readable text. Stdout contains only data output. This keeps stdout clean for piping into `jq` or other tools.

---

## Testing Strategy

**Test runner:** `pytest` via `uv run pytest`

**Unit tests** — each pipeline stage tested in isolation with fixture `.md` files in `tests/fixtures/`:

- `test_parser.py` — given raw `.md` text, assert correct Block tree (indentation, properties, LOGBOOK)
- `test_extractor.py` — given a Block tree, assert correct Task fields (tags, refs, clock entries, properties)
- `test_filters.py` — given Tasks + a period, assert correct time attribution
- `test_formatters.py` — given Tasks, assert correct JSON shape and pretty-output columns

**Fixture files cover these edge cases explicitly:**
- Running (unclosed) CLOCK
- CLOCK crossing midnight (all three split strategies)
- Multiple CLOCKs on one task spanning different days
- `time_spent` override with `completed::` in period
- `time_spent` override with `completed::` outside period
- `time_spent` override with no `completed::` (fallback to source_date, warning emitted)
- Task with no LOGBOOK and no override (zero time)
- Task with `[[refs]]` and `#tags` in title
- Child blocks (description extraction)
- Malformed CLOCK line (graceful skip + stderr warning)
- Malformed property date value (graceful skip + stderr warning)

**Integration tests** — run `ltmsh today/week/range` against a synthetic journal directory and assert full stdout JSON output and exit codes.

---

## Publishing

- Package name: `logseq-tmsh`
- CLI command: `ltmsh`
- Entry point in `pyproject.toml`: `ltmsh = "logseq_tmsh.cli:app"`
- Installable via: `pip install logseq-tmsh` or `uv tool install logseq-tmsh`
- Public GitHub repository (MIT or similar open licence)
- Python 3.10+ required
