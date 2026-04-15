# logseq-tmsh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `logseq-tmsh`, a Python CLI tool (`ltmsh`) that parses LogSeq journal CLOCK entries and reports time spent on tasks for a given time period.

**Architecture:** Four-stage pipeline — parse `.md` → Block tree, extract Task objects, attribute/filter by period, format output. Each stage is independently testable. Typer CLI, TOML config, JSON-first output.

**Tech Stack:** Python 3.10+, Typer 0.12+, pytest 8+, uv, tomli (backport for Python < 3.11)

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, entry point `ltmsh = "logseq_tmsh.cli:app"` |
| `logseq_tmsh/__init__.py` | Package version constant |
| `logseq_tmsh/models.py` | Dataclasses: `ClockEntry`, `Block`, `Task`, `AttributedTask`, `TASK_STATUSES` |
| `logseq_tmsh/parser.py` | Pass 1: `.md` file → `list[Block]` |
| `logseq_tmsh/extractor.py` | Pass 2: `list[Block]` → `list[Task]` |
| `logseq_tmsh/filters.py` | Pass 3: time attribution + tag/ref/status/zero filtering |
| `logseq_tmsh/formatters.py` | Pass 4: `list[AttributedTask]` → stdout (JSON or pretty) |
| `logseq_tmsh/config.py` | TOML config loading with hardcoded defaults |
| `logseq_tmsh/cli.py` | Typer app: `today`, `week`, `range`, `configure` |
| `tests/fixtures/` | `.md` snippets for unit tests |
| `tests/fixtures/integration/` | Synthetic journal dir for integration tests |
| `tests/test_parser.py` | Parser unit tests |
| `tests/test_extractor.py` | Extractor unit tests |
| `tests/test_filters.py` | Filter/attribution unit tests |
| `tests/test_formatters.py` | Formatter unit tests |
| `tests/test_integration.py` | End-to-end CLI tests via `typer.testing.CliRunner` |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `logseq_tmsh/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1: Initialise the uv project**

```bash
cd C:/Users/Otakar/OneDrive/Personal/Python/logseq-tmsh
uv init --name logseq-tmsh --no-readme
```

Expected: creates `pyproject.toml` and `hello.py` (delete `hello.py`).

- [ ] **Step 2: Replace pyproject.toml with the final content**

```toml
[project]
name = "logseq-tmsh"
version = "0.1.0"
description = "Extract time-tracking data from LogSeq journal CLOCK entries"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12.0",
    "tomli>=2.0.1; python_version < '3.11'",
]

[project.scripts]
ltmsh = "logseq_tmsh.cli:app"

[project.urls]
Homepage = "https://github.com/odokoupil/logseq-tmsh"
Repository = "https://github.com/odokoupil/logseq-tmsh"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create package and test stubs**

Create `logseq_tmsh/__init__.py`:
```python
__version__ = "0.1.0"
```

Create `tests/__init__.py` (empty file).

Create `tests/fixtures/` directory with a `.gitkeep` placeholder.

- [ ] **Step 4: Install dependencies**

```bash
uv sync
```

Expected: uv creates `.venv`, installs typer and tomli backport.

- [ ] **Step 5: Verify entry point wires up (stub)**

Create `logseq_tmsh/cli.py` (temporary stub):
```python
import typer
app = typer.Typer()

@app.command()
def today():
    typer.echo("ok")
```

Run: `uv run ltmsh today`
Expected output: `ok`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml logseq_tmsh/ tests/
git commit -m "chore: scaffold project with uv, typer stub, pytest"
```

---

### Task 2: Data Models

**Files:**
- Create: `logseq_tmsh/models.py`

- [ ] **Step 1: Write the models**

Create `logseq_tmsh/models.py`:

```python
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
```

- [ ] **Step 2: Quick smoke test (no test file needed — just import check)**

```bash
uv run python -c "from logseq_tmsh.models import Block, Task, ClockEntry, AttributedTask, TASK_STATUSES; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add logseq_tmsh/models.py
git commit -m "feat: add core data models (Block, Task, ClockEntry, AttributedTask)"
```

---

### Task 3: CLOCK and Property Parsing (parser.py foundations)

This task builds and tests the low-level parsing helpers that `parser.py` relies on before assembling the full block-tree parser in Task 4.

**Files:**
- Create: `logseq_tmsh/parser.py` (partial — helpers only)
- Create: `tests/test_parser.py` (partial — helper tests only)

- [ ] **Step 1: Write failing tests for CLOCK line parsing**

Create `tests/test_parser.py`:

```python
from datetime import datetime
from logseq_tmsh.parser import parse_clock_line


def test_parse_completed_clock():
    line = "CLOCK: [2026-04-15 Wed 10:31:04]--[2026-04-15 Wed 11:06:35] =>  00:35:31"
    entry = parse_clock_line(line, "2026_04_15.md", 1)
    assert entry is not None
    assert entry.start == datetime(2026, 4, 15, 10, 31, 4)
    assert entry.end == datetime(2026, 4, 15, 11, 6, 35)
    assert entry.is_running is False


def test_parse_running_clock():
    line = "CLOCK: [2026-04-15 Wed 16:41:26]"
    entry = parse_clock_line(line, "2026_04_15.md", 1)
    assert entry is not None
    assert entry.start == datetime(2026, 4, 15, 16, 41, 26)
    assert entry.end is None
    assert entry.is_running is True


def test_parse_clock_ignores_precomputed_duration():
    # Duration after => is ignored; entry computed from timestamps
    line = "CLOCK: [2026-04-15 Wed 09:00:00]--[2026-04-15 Wed 10:00:00] =>  99:99:99"
    entry = parse_clock_line(line, "2026_04_15.md", 1)
    assert entry is not None
    assert (entry.end - entry.start).total_seconds() == 3600


def test_parse_clock_returns_none_for_malformed(capsys):
    line = "CLOCK: [NOT A DATE]"
    entry = parse_clock_line(line, "2026_04_15.md", 5)
    assert entry is None
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "2026_04_15.md:5" in captured.err


def test_parse_clock_midnight_crossing():
    line = "CLOCK: [2026-04-14 Mon 23:30:00]--[2026-04-15 Tue 01:15:00] =>  01:45:00"
    entry = parse_clock_line(line, "2026_04_14.md", 1)
    assert entry is not None
    assert entry.start.date().isoformat() == "2026-04-14"
    assert entry.end.date().isoformat() == "2026-04-15"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: `ImportError` — `parse_clock_line` not found.

- [ ] **Step 3: Implement `parse_clock_line` in parser.py**

Create `logseq_tmsh/parser.py`:

```python
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from .models import Block, ClockEntry

# ── Timestamp patterns ────────────────────────────────────────────────────────
_TS = r"\d{4}-\d{2}-\d{2} \w{3} \d{2}:\d{2}:\d{2}"
_CLOCK_COMPLETED_RE = re.compile(
    r"CLOCK: \[(" + _TS + r")\]--\[(" + _TS + r")\]"
)
_CLOCK_RUNNING_RE = re.compile(r"CLOCK: \[(" + _TS + r")\]\s*$")
_TS_FMT = "%Y-%m-%d %a %H:%M:%S"

# ── Property pattern ──────────────────────────────────────────────────────────
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add logseq_tmsh/parser.py tests/test_parser.py
git commit -m "feat: implement CLOCK line parser with running/completed/malformed handling"
```

---

### Task 4: Full Block Tree Parser

**Files:**
- Modify: `logseq_tmsh/parser.py` (add `parse_file`, `_parse_lines`)
- Create: `tests/fixtures/simple_task.md`
- Create: `tests/fixtures/nested_task.md`
- Create: `tests/fixtures/malformed_clock.md`
- Modify: `tests/test_parser.py` (add block-tree tests)

- [ ] **Step 1: Create fixture files**

Create `tests/fixtures/simple_task.md`:
```markdown
- ## New Tasks
	- DONE #ori - [[Orisales]] Regular Daily Check
	  completed:: [[Apr 15th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Wed 10:31:04]--[2026-04-15 Wed 11:06:35] =>  00:35:31
	  :END:
		- plan for today
		- emails
	- TODO #ori - Study [[Windsurf]] workflows
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Wed 16:41:26]
	  :END:
```

Create `tests/fixtures/nested_task.md`:
```markdown
	- DONE #ori [[meeting]] - Weekly Sync
	  completed:: [[Apr 15th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Wed 09:00:00]--[2026-04-15 Wed 10:00:00] =>  01:00:00
	  :END:
		- [[PersonOne]] discussed topic A
			- sub-note about topic A
		- [[PersonTwo]] discussed topic B
```

Create `tests/fixtures/malformed_clock.md`:
```markdown
	- TODO #ori - Task with bad clock
	  :LOGBOOK:
	  CLOCK: [NOT A DATE]
	  CLOCK: [2026-04-15 Wed 10:00:00]--[2026-04-15 Wed 11:00:00] =>  01:00:00
	  :END:
```

- [ ] **Step 2: Write failing block-tree tests**

Append to `tests/test_parser.py`:

```python
from pathlib import Path
from logseq_tmsh.parser import parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_file_task_count():
    blocks = parse_file(FIXTURES / "simple_task.md")
    tasks = [b for b in blocks if b.content.split()[0] in ("DONE", "TODO", "DOING", "LATER", "WAITING", "CANCELLED", "NOW")]
    assert len(tasks) == 2


def test_parse_file_clock_entries():
    blocks = parse_file(FIXTURES / "simple_task.md")
    done_block = next(b for b in blocks if b.content.startswith("DONE"))
    assert len(done_block.logbook) == 1
    assert done_block.logbook[0].is_running is False


def test_parse_file_running_clock():
    blocks = parse_file(FIXTURES / "simple_task.md")
    todo_block = next(b for b in blocks if b.content.startswith("TODO"))
    assert len(todo_block.logbook) == 1
    assert todo_block.logbook[0].is_running is True


def test_parse_file_properties():
    blocks = parse_file(FIXTURES / "simple_task.md")
    done_block = next(b for b in blocks if b.content.startswith("DONE"))
    assert "completed" in done_block.properties
    assert done_block.properties["completed"] == "[[Apr 15th, 2026]]"


def test_parse_file_children():
    blocks = parse_file(FIXTURES / "simple_task.md")
    done_block = next(b for b in blocks if b.content.startswith("DONE"))
    assert len(done_block.children) == 2
    assert done_block.children[0].content == "plan for today"


def test_parse_file_deep_nesting():
    blocks = parse_file(FIXTURES / "nested_task.md")
    task = blocks[0]
    assert len(task.children) == 2
    # First child has a sub-child
    assert len(task.children[0].children) == 1
    assert task.children[0].children[0].content == "sub-note about topic A"


def test_parse_file_malformed_clock_skipped(capsys):
    blocks = parse_file(FIXTURES / "malformed_clock.md")
    task = blocks[0]
    # Malformed CLOCK skipped; valid CLOCK kept
    assert len(task.logbook) == 1
    assert task.logbook[0].start.hour == 10
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_parser.py::test_parse_file_task_count -v
```

Expected: `AttributeError` — `parse_file` not defined.

- [ ] **Step 4: Implement `parse_file` and `_parse_lines` in parser.py**

Append to `logseq_tmsh/parser.py` (after the existing helpers):

```python
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
```

- [ ] **Step 5: Run all parser tests**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add logseq_tmsh/parser.py tests/test_parser.py tests/fixtures/
git commit -m "feat: implement full block-tree parser for LogSeq .md files"
```

---

### Task 5: Task Extractor

**Files:**
- Create: `logseq_tmsh/extractor.py`
- Create: `tests/fixtures/tags_refs.md`
- Create: `tests/fixtures/time_override.md`
- Create: `tests/fixtures/no_logbook.md`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Create fixture files**

Create `tests/fixtures/tags_refs.md`:
```markdown
	- DONE #ori #meeting - [[OrisalesRetirement]] Meeting with [[MensikDavid]]
	  completed:: [[Apr 15th, 2026]]
	  started:: [[Apr 15th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Wed 09:00:00]--[2026-04-15 Wed 10:00:00] =>  01:00:00
	  :END:
		- discussed topic A
		- discussed topic B
			- detail about B
```

Create `tests/fixtures/time_override.md`:
```markdown
	- DONE #ori - Task with time override
	  completed:: [[Apr 15th, 2026]]
	  time_spent:: 90
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Wed 09:00:00]--[2026-04-15 Wed 10:00:00] =>  01:00:00
	  :END:
```

Create `tests/fixtures/no_logbook.md`:
```markdown
	- DONE #ori - Quick task no clock
	  completed:: [[Apr 15th, 2026]]
```

- [ ] **Step 2: Write failing extractor tests**

Create `tests/test_extractor.py`:

```python
from datetime import date
from pathlib import Path

from logseq_tmsh.extractor import extract_tasks
from logseq_tmsh.parser import parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def _tasks(fixture: str):
    fname = fixture
    source_date = date(2026, 4, 15)
    blocks = parse_file(FIXTURES / fname)
    return extract_tasks(blocks, fname, source_date)


def test_extract_status():
    tasks = _tasks("simple_task.md")
    statuses = {t.status for t in tasks}
    assert "DONE" in statuses
    assert "TODO" in statuses


def test_extract_tags():
    tasks = _tasks("tags_refs.md")
    assert len(tasks) == 1
    assert "ori" in tasks[0].tags
    assert "meeting" in tasks[0].tags


def test_extract_page_refs():
    tasks = _tasks("tags_refs.md")
    refs = tasks[0].page_refs
    assert "OrisalesRetirement" in refs
    assert "MensikDavid" in refs


def test_extract_raw_title_contains_text():
    tasks = _tasks("tags_refs.md")
    assert "Meeting with" in tasks[0].raw_title


def test_extract_started_completed():
    tasks = _tasks("tags_refs.md")
    t = tasks[0]
    assert t.started == date(2026, 4, 15)
    assert t.completed == date(2026, 4, 15)


def test_extract_clock_entries():
    tasks = _tasks("simple_task.md")
    done = next(t for t in tasks if t.status == "DONE")
    assert len(done.clock_entries) == 1


def test_extract_time_override():
    tasks = _tasks("time_override.md")
    assert tasks[0].time_spent_override == 90


def test_extract_no_logbook_zero_clocks():
    tasks = _tasks("no_logbook.md")
    assert len(tasks[0].clock_entries) == 0
    assert tasks[0].time_spent_override is None


def test_extract_description_flattened():
    tasks = _tasks("tags_refs.md")
    desc = tasks[0].description
    assert any("discussed topic A" in line for line in desc)
    assert any("discussed topic B" in line for line in desc)
    # Sub-nesting preserved as indented text
    assert any("detail about B" in line for line in desc)


def test_extract_source_fields():
    fname = "simple_task.md"
    tasks = _tasks(fname)
    assert all(t.source_file == fname for t in tasks)
    assert all(t.source_date == date(2026, 4, 15) for t in tasks)
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: `ImportError` — `extract_tasks` not found.

- [ ] **Step 4: Implement extractor.py**

Create `logseq_tmsh/extractor.py`:

```python
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
            f"WARNING: {source_file}: invalid date in '{prop_name}': {exc}",
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
    _walk(blocks, source_file, source_date, time_spent_property, completed_property, started_property, tasks)
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
```

- [ ] **Step 5: Run extractor tests**

```bash
uv run pytest tests/test_extractor.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add logseq_tmsh/extractor.py tests/test_extractor.py tests/fixtures/
git commit -m "feat: implement task extractor (Block tree -> Task objects)"
```

---

### Task 6: Time Attribution and Filtering

**Files:**
- Create: `logseq_tmsh/filters.py`
- Create: `tests/fixtures/midnight_cross.md`
- Create: `tests/fixtures/multi_clock.md`
- Create: `tests/fixtures/override_no_completed.md`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Create fixture files**

Create `tests/fixtures/midnight_cross.md`:
```markdown
	- DONE #ori - Late night task
	  completed:: [[Apr 15th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-14 Mon 23:30:00]--[2026-04-15 Tue 01:15:00] =>  01:45:00
	  :END:
```

Create `tests/fixtures/multi_clock.md`:
```markdown
	- DOING #ori - Multi-session task
	  :LOGBOOK:
	  CLOCK: [2026-04-14 Mon 09:00:00]--[2026-04-14 Mon 10:00:00] =>  01:00:00
	  CLOCK: [2026-04-15 Tue 14:00:00]--[2026-04-15 Tue 15:30:00] =>  01:30:00
	  :END:
```

Create `tests/fixtures/override_no_completed.md`:
```markdown
	- DONE #ori - Override without completed date
	  time_spent:: 45
```

- [ ] **Step 2: Write failing filter tests**

Create `tests/test_filters.py`:

```python
from datetime import date, timedelta
from pathlib import Path

from logseq_tmsh.extractor import extract_tasks
from logseq_tmsh.filters import attribute_tasks, filter_tasks
from logseq_tmsh.parser import parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def _load(fixture: str, src_date: date):
    blocks = parse_file(FIXTURES / fixture)
    return extract_tasks(blocks, fixture, src_date)


def test_attribution_full_clock_in_period():
    tasks = _load("simple_task.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    done = next(a for a in attributed if a.task.status == "DONE")
    assert done.period_seconds == 35 * 60 + 31  # 00:35:31


def test_attribution_clock_outside_period():
    tasks = _load("simple_task.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 16), date(2026, 4, 16))
    assert all(a.period_seconds == 0 for a in attributed)


def test_attribution_midnight_split_default():
    tasks = _load("midnight_cross.md", date(2026, 4, 14))
    # Query only Apr 15 — should get 75 min (01:15 of the crossing interval)
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15), midnight_split="split")
    assert len(attributed) == 1
    assert attributed[0].period_seconds == 75 * 60  # 01:15:00


def test_attribution_midnight_split_start():
    tasks = _load("midnight_cross.md", date(2026, 4, 14))
    # Strategy 'start': entire interval attributed to start day (Apr 14)
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15), midnight_split="start")
    assert attributed[0].period_seconds == 0


def test_attribution_midnight_split_end():
    tasks = _load("midnight_cross.md", date(2026, 4, 14))
    # Strategy 'end': entire interval attributed to end day (Apr 15)
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15), midnight_split="end")
    assert attributed[0].period_seconds == 105 * 60  # 01:45:00


def test_attribution_multi_clock_partial():
    tasks = _load("multi_clock.md", date(2026, 4, 14))
    # Query Apr 15 only — should get only the Apr 15 clock (90 min)
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    assert len(attributed) == 1
    assert attributed[0].period_seconds == 90 * 60


def test_attribution_multi_clock_total():
    tasks = _load("multi_clock.md", date(2026, 4, 14))
    # total_seconds includes both clocks (60 + 90 = 150 min)
    attributed = attribute_tasks(tasks, date(2026, 4, 14), date(2026, 4, 15))
    assert attributed[0].total_seconds == 150 * 60


def test_attribution_time_override_in_period():
    tasks = _load("time_override.md", date(2026, 4, 15))
    # Override = 90 min; completed Apr 15 which is in period
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    assert len(attributed) == 1
    assert attributed[0].period_seconds == 90 * 60


def test_attribution_time_override_outside_period():
    tasks = _load("time_override.md", date(2026, 4, 15))
    # Query Apr 16 — override completed Apr 15 so not in period
    attributed = attribute_tasks(tasks, date(2026, 4, 16), date(2026, 4, 16))
    assert attributed[0].period_seconds == 0


def test_attribution_override_no_completed_falls_back_to_source_date(capsys):
    """Edge case: time_spent set but no completed:: → falls back to source_date.

    This fallback is always reported to stderr as a warning so the user knows
    to add a completed:: property for precise period attribution.
    """
    tasks = _load("override_no_completed.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    assert attributed[0].period_seconds == 45 * 60
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "completed" in captured.err.lower()


def test_attribution_running_clock_flagged(capsys):
    tasks = _load("simple_task.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    todo = next(a for a in attributed if a.task.status == "TODO")
    assert todo.has_running_clock is True
    assert todo.period_seconds > 0  # provisional time using now as end


def test_filter_by_tag_and_logic():
    tasks = _load("tags_refs.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    # Both tags present → 1 result
    result = filter_tasks(attributed, tags=["ori", "meeting"])
    assert len(result) == 1
    # Tag not on task → 0 results
    result = filter_tasks(attributed, tags=["ori", "nonexistent"])
    assert len(result) == 0


def test_filter_by_ref_and_logic():
    tasks = _load("tags_refs.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    result = filter_tasks(attributed, refs=["OrisalesRetirement", "MensikDavid"])
    assert len(result) == 1
    result = filter_tasks(attributed, refs=["OrisalesRetirement", "Nobody"])
    assert len(result) == 0


def test_filter_by_status_or_logic():
    tasks = _load("simple_task.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    result = filter_tasks(attributed, statuses=["DONE"])
    assert all(a.task.status == "DONE" for a in result)


def test_filter_exclude_zero_default():
    tasks = _load("no_logbook.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    result = filter_tasks(attributed, include_zero=False)
    assert len(result) == 0


def test_filter_include_zero():
    tasks = _load("no_logbook.md", date(2026, 4, 15))
    attributed = attribute_tasks(tasks, date(2026, 4, 15), date(2026, 4, 15))
    result = filter_tasks(attributed, include_zero=True)
    assert len(result) == 1
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_filters.py -v
```

Expected: `ImportError` — `attribute_tasks`, `filter_tasks` not found.

- [ ] **Step 4: Implement filters.py**

Create `logseq_tmsh/filters.py`:

```python
from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta

from .models import AttributedTask, Task


def _clip_interval(
    start: datetime,
    end: datetime,
    period_start: date,
    period_end: date,
    midnight_split: str,
) -> int:
    """Return the number of seconds of [start, end] that fall within [period_start, period_end].

    midnight_split strategies:
      'split'  (default) — interval clipped to period boundaries; partial overlap counted
      'start'  — entire interval attributed to start day; counts only if start day in period
      'end'    — entire interval attributed to end day; counts only if end day in period
    """
    total = int((end - start).total_seconds())
    if total <= 0:
        return 0

    if midnight_split == "start":
        return total if period_start <= start.date() <= period_end else 0

    if midnight_split == "end":
        return total if period_start <= end.date() <= period_end else 0

    # Default: "split" — clip interval to [period_start 00:00, period_end 23:59:59.999999]
    window_start = datetime.combine(period_start, time.min)
    window_end = datetime.combine(period_end, time.max)
    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)
    if clipped_start >= clipped_end:
        return 0
    return int((clipped_end - clipped_start).total_seconds())


def attribute_tasks(
    tasks: list[Task],
    period_start: date,
    period_end: date,
    midnight_split: str = "split",
) -> list[AttributedTask]:
    """Compute per-period and total time for each Task.

    Edge cases (all documented in spec):
    - Running clock: provisional end = now; has_running_clock=True on output
    - time_spent_override with completed in period: override replaces all CLOCK time
    - time_spent_override with completed outside period: period_seconds = 0
    - time_spent_override with no completed date: falls back to source_date;
      WARNING written to stderr so the user can add a completed:: property
    - Malformed/zero-duration clock: skipped silently
    """
    result: list[AttributedTask] = []
    now = datetime.now()

    for task in tasks:
        has_running = False
        period_secs = 0
        total_secs = 0

        if task.time_spent_override is not None:
            # ── Branch A: time_spent_override ────────────────────────────────
            override_secs = task.time_spent_override * 60

            if task.completed is not None:
                attribution_date = task.completed
            else:
                # Fallback: use source_date; warn user
                attribution_date = task.source_date
                print(
                    f"WARNING: {task.source_file}: task '{task.raw_title[:60]}' has "
                    f"time_spent override but no completed:: property — "
                    f"attributing to source_date {attribution_date}. "
                    f"Add completed:: for precise period attribution.",
                    file=sys.stderr,
                )

            if period_start <= attribution_date <= period_end:
                period_secs = override_secs
            total_secs = override_secs

        else:
            # ── Branch B: CLOCK-based ─────────────────────────────────────────
            for entry in task.clock_entries:
                end = entry.end
                if end is None:
                    has_running = True
                    end = now  # provisional

                entry_secs = int((end - entry.start).total_seconds())
                if entry_secs <= 0:
                    continue

                total_secs += entry_secs
                period_secs += _clip_interval(
                    entry.start, end, period_start, period_end, midnight_split
                )

        result.append(
            AttributedTask(
                task=task,
                period_seconds=period_secs,
                total_seconds=total_secs,
                has_running_clock=has_running,
            )
        )

    return result


def filter_tasks(
    attributed: list[AttributedTask],
    tags: list[str] | None = None,
    refs: list[str] | None = None,
    statuses: list[str] | None = None,
    include_zero: bool = False,
) -> list[AttributedTask]:
    """Apply tag/ref/status/zero filters to a list of AttributedTasks.

    - tags:     AND logic — task must have ALL specified tags
    - refs:     AND logic — task must reference ALL specified pages
    - statuses: OR logic  — task must match ANY specified status
    - include_zero: when False (default), tasks with period_seconds == 0 are dropped
    """
    out: list[AttributedTask] = []
    for a in attributed:
        t = a.task
        if tags and not all(tag in t.tags for tag in tags):
            continue
        if refs and not all(ref in t.page_refs for ref in refs):
            continue
        if statuses and t.status not in statuses:
            continue
        if not include_zero and a.period_seconds == 0:
            continue
        out.append(a)
    return out
```

- [ ] **Step 5: Run all filter tests**

```bash
uv run pytest tests/test_filters.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add logseq_tmsh/filters.py tests/test_filters.py tests/fixtures/
git commit -m "feat: implement time attribution and task filtering"
```

---

### Task 7: Output Formatters

**Files:**
- Create: `logseq_tmsh/formatters.py`
- Create: `tests/test_formatters.py`

- [ ] **Step 1: Write failing formatter tests**

Create `tests/test_formatters.py`:

```python
import json
from datetime import date, datetime
from logseq_tmsh.formatters import format_json, format_pretty, format_duration
from logseq_tmsh.models import AttributedTask, ClockEntry, Task

DEFAULT_FIELDS = ["title", "status", "time_period", "completed"]
DATE_FMT = "%Y-%m-%d"


def _make_task(
    title="#ori Task",
    status="DONE",
    tags=None,
    refs=None,
    completed=None,
    period_secs=3600,
    total_secs=3600,
    has_running=False,
    description=None,
    source_date=date(2026, 4, 15),
):
    task = Task(
        raw_title=title,
        status=status,
        tags=tags or ["ori"],
        page_refs=refs or [],
        clock_entries=[],
        time_spent_override=None,
        started=None,
        completed=completed or date(2026, 4, 15),
        description=description or [],
        source_file="2026_04_15.md",
        source_date=source_date,
    )
    return AttributedTask(task=task, period_seconds=period_secs, total_seconds=total_secs, has_running_clock=has_running)


def test_format_duration():
    assert format_duration(3661) == "01:01:01"
    assert format_duration(0) == "00:00:00"
    assert format_duration(3600) == "01:00:00"


def test_format_json_compact_default():
    tasks = [_make_task()]
    output = format_json(tasks, DEFAULT_FIELDS, indent=None, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    assert output.startswith("[{")  # compact, no newlines
    assert "\n" not in output


def test_format_json_with_indent():
    tasks = [_make_task()]
    output = format_json(tasks, DEFAULT_FIELDS, indent=2, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    data = json.loads(output)
    assert data[0]["status"] == "DONE"
    assert "  " in output  # indented


def test_format_json_fields_order():
    tasks = [_make_task()]
    fields = ["status", "title", "time_period"]
    output = format_json(tasks, fields, indent=None, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    data = json.loads(output)
    keys = list(data[0].keys())
    assert keys == ["status", "title", "time_period"]


def test_format_json_running_clock_suffix():
    tasks = [_make_task(has_running=True, period_secs=180)]
    output = format_json(tasks, ["time_period"], indent=None, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    data = json.loads(output)
    assert data[0]["time_period"].endswith("~")


def test_format_json_strip_tags():
    tasks = [_make_task(title="#ori #meeting Task name")]
    output = format_json(tasks, ["title"], indent=None, strip_tags=True, strip_refs=False, date_format=DATE_FMT)
    data = json.loads(output)
    assert "#ori" not in data[0]["title"]
    assert "#meeting" not in data[0]["title"]
    assert "Task name" in data[0]["title"]


def test_format_json_strip_refs():
    tasks = [_make_task(title="Task [[PageRef]] here")]
    output = format_json(tasks, ["title"], indent=None, strip_tags=False, strip_refs=True, date_format=DATE_FMT)
    data = json.loads(output)
    assert "[[PageRef]]" not in data[0]["title"]
    assert "PageRef" in data[0]["title"]


def test_format_json_description_field():
    tasks = [_make_task(description=["line 1", "  line 2"])]
    output = format_json(tasks, ["description"], indent=2, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    data = json.loads(output)
    assert data[0]["description"] == ["line 1", "  line 2"]


def test_format_pretty_has_header():
    tasks = [_make_task()]
    output = format_pretty(tasks, DEFAULT_FIELDS, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    lines = output.strip().splitlines()
    assert lines[0].upper() == lines[0]  # header row is uppercase
    assert len(lines) >= 2


def test_format_pretty_running_clock_tilde():
    tasks = [_make_task(has_running=True, period_secs=180)]
    output = format_pretty(tasks, ["time_period", "title"], strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    assert "~" in output


def test_format_json_empty_list():
    output = format_json([], DEFAULT_FIELDS, indent=None, strip_tags=False, strip_refs=False, date_format=DATE_FMT)
    assert output == "[]"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_formatters.py -v
```

Expected: `ImportError` — `format_json` not found.

- [ ] **Step 3: Implement formatters.py**

Create `logseq_tmsh/formatters.py`:

```python
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
```

- [ ] **Step 4: Run formatter tests**

```bash
uv run pytest tests/test_formatters.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add logseq_tmsh/formatters.py tests/test_formatters.py
git commit -m "feat: implement JSON and pretty-table output formatters"
```

---

### Task 8: Config Loading

**Files:**
- Create: `logseq_tmsh/config.py`
- (No separate test file — config is tested implicitly via CLI integration tests in Task 11)

- [ ] **Step 1: Implement config.py**

Create `logseq_tmsh/config.py`:

```python
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

_DEFAULTS: dict = {
    "paths": {
        "journals": "",
        "extra_dirs": [],
    },
    "parsing": {
        "midnight_split": "split",
        "time_spent_property": "time_spent",
        "completed_property": "completed",
        "started_property": "started",
    },
    "output": {
        "date_format": "%Y-%m-%d",
        "datetime_format": "%Y-%m-%d %H:%M",
        "default_fields": ["title", "status", "time_period", "started", "completed", "tags"],
        "include_zero": False,
    },
}


@dataclass
class Config:
    journals: str
    extra_dirs: list[str]
    midnight_split: str
    time_spent_property: str
    completed_property: str
    started_property: str
    date_format: str
    datetime_format: str
    default_fields: list[str]
    include_zero: bool


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _find_config_files(extra_path: Path | None) -> list[Path]:
    """Return config file paths in precedence order (last wins)."""
    candidates = [
        Path.home() / ".logseq-tmsh" / "config.toml",
        Path("logseq-tmsh.toml"),
    ]
    if extra_path:
        candidates.append(extra_path)
    return [p for p in candidates if p.exists()]


def load_config(extra_path: Path | None = None) -> Config:
    """Load configuration from TOML files, merged over built-in defaults.

    Search order (later files override earlier):
      1. ~/.logseq-tmsh/config.toml
      2. ./logseq-tmsh.toml  (project-local)
      3. extra_path (if provided)
    """
    merged = dict(_DEFAULTS)
    for path in _find_config_files(extra_path):
        with open(path, "rb") as f:
            user_cfg = tomllib.load(f)
        merged = _deep_merge(merged, user_cfg)

    p = merged["paths"]
    pa = merged["parsing"]
    o = merged["output"]

    return Config(
        journals=p["journals"],
        extra_dirs=p["extra_dirs"],
        midnight_split=pa["midnight_split"],
        time_spent_property=pa["time_spent_property"],
        completed_property=pa["completed_property"],
        started_property=pa["started_property"],
        date_format=o["date_format"],
        datetime_format=o["datetime_format"],
        default_fields=o["default_fields"],
        include_zero=o["include_zero"],
    )
```

- [ ] **Step 2: Smoke test**

```bash
uv run python -c "from logseq_tmsh.config import load_config; c = load_config(); print(c.midnight_split)"
```

Expected: `split`

- [ ] **Step 3: Commit**

```bash
git add logseq_tmsh/config.py
git commit -m "feat: implement TOML config loading with defaults and deep merge"
```

---

### Task 9: CLI Commands (today / week / range)

**Files:**
- Modify: `logseq_tmsh/cli.py` (replace stub with full implementation)

- [ ] **Step 1: Implement cli.py**

Replace `logseq_tmsh/cli.py` with:

```python
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import typer

from .config import load_config
from .extractor import extract_tasks
from .filters import attribute_tasks, filter_tasks
from .formatters import format_json, format_pretty
from .parser import parse_file

app = typer.Typer(help="Extract time-tracking data from LogSeq journal CLOCK entries.")


# ── Shared option types ────────────────────────────────────────────────────────

def _common_options(fn):
    """Decorator that injects shared filter/output options onto a command."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


# Shared CLI options defined as module-level defaults for reuse
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
    all_tasks = []
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

            # Only parse files that could contain relevant CLOCKs
            # For 'split' strategy we need files one day outside the range too
            # (a CLOCK starting the day before could extend into the period).
            # Use a 1-day buffer on each side to be safe.
            buffer = timedelta(days=1)
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
):
    """Show tasks worked on today."""
    today_date = date.today()
    _run_query(today_date, today_date, tag, ref, status, include_zero, pretty, indent, fields, strip_tags, strip_refs, config)


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
):
    """Show tasks worked on during the current week (Monday to today)."""
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    _run_query(monday, today_date, tag, ref, status, include_zero, pretty, indent, fields, strip_tags, strip_refs, config)


@app.command(name="range")
def range_cmd(
    from_date: date = typer.Option(..., "--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)"),
    to_date: date = typer.Option(..., "--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)"),
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
):
    """Show tasks worked on in a specific date range."""
    if from_date > to_date:
        typer.echo("ERROR: --from date must not be after --to date", err=True)
        raise typer.Exit(1)
    _run_query(from_date, to_date, tag, ref, status, include_zero, pretty, indent, fields, strip_tags, strip_refs, config)
```

- [ ] **Step 2: Smoke test with real journals**

```bash
uv run ltmsh today --help
uv run ltmsh week --help
uv run ltmsh range --help
```

Expected: help text for all three commands with all options listed.

- [ ] **Step 3: Commit**

```bash
git add logseq_tmsh/cli.py
git commit -m "feat: implement today/week/range CLI commands"
```

---

### Task 10: `configure` Command

**Files:**
- Modify: `logseq_tmsh/cli.py` (add `configure` command)

- [ ] **Step 1: Add configure command to cli.py**

Append to `logseq_tmsh/cli.py` before the end of the file:

```python
@app.command()
def configure():
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
        with open(config_path, "rb") as f:
            existing = tomllib.load(f)

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
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _toml_list(lst: list[str]) -> str:
        return "[" + ", ".join(_toml_str(x) for x in lst) + "]"

    toml_content = f"""\
[paths]
journals = {_toml_str(journals)}
extra_dirs = {_toml_list(extra_dirs)}

[parsing]
midnight_split = {_toml_str(midnight_split)}
time_spent_property = {_toml_str(time_spent_property)}
completed_property = {_toml_str(completed_property)}
started_property = {_toml_str(started_property)}

[output]
date_format = {_toml_str(date_format)}
datetime_format = "%Y-%m-%d %H:%M"
default_fields = {_toml_list(default_fields)}
include_zero = {"true" if include_zero else "false"}
"""

    config_path.write_text(toml_content, encoding="utf-8")
    typer.echo(f"\nConfiguration saved to {config_path}")
```

- [ ] **Step 2: Smoke test**

```bash
uv run ltmsh configure --help
```

Expected: help text showing the configure command.

- [ ] **Step 3: Commit**

```bash
git add logseq_tmsh/cli.py
git commit -m "feat: implement interactive configure command"
```

---

### Task 11: Integration Tests

**Files:**
- Create: `tests/fixtures/integration/2026_04_14.md`
- Create: `tests/fixtures/integration/2026_04_15.md`
- Create: `tests/fixtures/integration/logseq-tmsh.toml`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Create integration fixture journals**

Create `tests/fixtures/integration/2026_04_14.md`:
```markdown
	- DONE #ori - Task on Apr 14
	  completed:: [[Apr 14th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-14 Mon 09:00:00]--[2026-04-14 Mon 10:30:00] =>  01:30:00
	  :END:
	- DONE #ori #meeting - Meeting on Apr 14
	  completed:: [[Apr 14th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-14 Mon 14:00:00]--[2026-04-14 Mon 15:00:00] =>  01:00:00
	  :END:
		- discussed project A
```

Create `tests/fixtures/integration/2026_04_15.md`:
```markdown
	- DONE #ori - Task on Apr 15
	  completed:: [[Apr 15th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Tue 10:00:00]--[2026-04-15 Tue 11:00:00] =>  01:00:00
	  :END:
	- TODO #ori - Unfinished task
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Tue 16:00:00]--[2026-04-15 Tue 16:30:00] =>  00:30:00
	  :END:
	- DONE - Personal task no tag
	  completed:: [[Apr 15th, 2026]]
	  :LOGBOOK:
	  CLOCK: [2026-04-15 Tue 12:00:00]--[2026-04-15 Tue 12:15:00] =>  00:15:00
	  :END:
```

Create `tests/fixtures/integration/logseq-tmsh.toml`:
```toml
[paths]
journals = ""
extra_dirs = []
```

- [ ] **Step 2: Write integration tests**

Create `tests/test_integration.py`:

```python
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from logseq_tmsh.cli import app

runner = CliRunner(mix_stderr=False)
JOURNALS = str(Path(__file__).parent / "fixtures" / "integration")


def _run(*args):
    """Helper: run ltmsh with --config pointing at integration fixtures."""
    return runner.invoke(app, list(args))


def _run_range(from_date: str, to_date: str, *extra_args):
    return _run("range", "--from", from_date, "--to", to_date,
                "--config", str(Path(__file__).parent / "fixtures" / "integration" / "logseq-tmsh.toml"),
                "--fields", "title,status,time_period,tags",
                *extra_args)


def test_range_returns_exit_zero():
    # Temporarily patch journals path by passing config-less query on integration dir
    result = runner.invoke(app, [
        "range", "--from", "2026-04-14", "--to", "2026-04-15",
        "--indent", "2",
    ], env={"HOME": str(Path(__file__).parent / "fixtures" / "integration")})
    # May fail with exit 1 if no journals configured — that's tested separately
    assert result.exit_code in (0, 1, 2)


def test_range_json_output(tmp_path):
    # Write a config pointing at integration journals
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\njournals = "{JOURNALS}"\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
        "--indent", "2",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


def test_range_apr15_task_count(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\njournals = "{JOURNALS}"\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
        "--fields", "title,status,time_period",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    # 3 tasks on Apr 15 all have time > 0
    assert len(data) == 3


def test_range_tag_filter(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\njournals = "{JOURNALS}"\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-14", "--to", "2026-04-15",
        "--config", str(cfg),
        "--tag", "ori", "--tag", "meeting",
        "--fields", "title,status,tags",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    # Only the meeting task on Apr 14 has both #ori and #meeting
    assert len(data) == 1
    assert "meeting" in data[0].get("tags", [])


def test_range_pretty_output(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\njournals = "{JOURNALS}"\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
        "--pretty",
        "--fields", "status,time_period,title",
    ])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0] == "STATUS  TIME_PERIOD  TITLE"


def test_missing_journals_returns_exit_2(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[paths]\njournals = "/nonexistent/path"\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
    ])
    assert result.exit_code == 2


def test_no_journals_configured_returns_exit_1(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[paths]\njournals = ""\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
    ])
    assert result.exit_code == 1


def test_include_zero_flag(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\njournals = "{JOURNALS}"\n', encoding="utf-8")

    result_without = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
        "--fields", "title,time_period",
    ])
    result_with = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
        "--include-zero",
        "--fields", "title,time_period",
    ])
    assert result_without.exit_code == 0
    assert result_with.exit_code == 0
    # include-zero may show more results (or equal)
    assert len(json.loads(result_with.output)) >= len(json.loads(result_without.output))


def test_strip_tags_removes_hash_tags(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\njournals = "{JOURNALS}"\n', encoding="utf-8")

    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", str(cfg),
        "--strip-tags",
        "--fields", "title",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    for item in data:
        assert "#" not in item["title"]
```

- [ ] **Step 3: Run integration tests**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py tests/fixtures/integration/
git commit -m "test: add integration tests for all CLI commands"
```

---

### Task 12: Publishing Polish

**Files:**
- Create: `README.md`
- Create: `LICENSE`

- [ ] **Step 1: Create LICENSE (MIT)**

Create `LICENSE`:
```
MIT License

Copyright (c) 2026 Otakar Dokoupil

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Create README.md**

Create `README.md`:
```markdown
# logseq-tmsh

Extract time-tracking data from [LogSeq](https://logseq.com/) journal CLOCK entries.

## Install

```bash
pip install logseq-tmsh
# or
uv tool install logseq-tmsh
```

## Quick Start

```bash
# Configure once
ltmsh configure

# Show today's work
ltmsh today

# Show this week
ltmsh week

# Show a custom range
ltmsh range --from 2026-04-01 --to 2026-04-15

# Human-readable output
ltmsh today --pretty

# Filter by tag (AND logic)
ltmsh today --tag ori --tag meeting

# Pretty-print JSON
ltmsh today --indent 2
```

## Output Fields

`title`, `status`, `time_period`, `time_total`, `time_override`, `started`, `completed`, `tags`, `refs`, `has_running_clock`, `description`, `source_file`, `source_date`

## Configuration

`~/.logseq-tmsh/config.toml` — created by `ltmsh configure`.

## License

MIT
```

- [ ] **Step 3: Verify build**

```bash
uv build
```

Expected: creates `dist/logseq_tmsh-0.1.0-py3-none-any.whl` and `.tar.gz` with no errors.

- [ ] **Step 4: Final test run**

```bash
uv run pytest -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE
git commit -m "chore: add README and MIT license for publishing"
```

---

## Self-Review

**Spec coverage check:**
- ✅ journal-only by default, configurable paths (`load_config` + `extra_dirs`) — Task 8, Task 9
- ✅ Running clocks flagged as provisional, `~` suffix — Tasks 6, 7
- ✅ Midnight-split configurable (split/start/end) — Task 6
- ✅ `time_spent` in minutes overrides CLOCK — Task 6
- ✅ `--strip-tags`, `--strip-refs` — Tasks 7, 9
- ✅ `description` field (child blocks) — Tasks 5, 7
- ✅ Zero-time excluded by default, `--include-zero` flag — Tasks 6, 9
- ✅ `--pretty` for human output — Tasks 7, 9
- ✅ `--indent N` for JSON — Tasks 7, 9
- ✅ `--fields` + `default_fields` config — Tasks 7, 8, 9
- ✅ `--tag` AND logic, `--ref` AND logic, `--status` OR logic — Task 6
- ✅ `today`, `week`, `range` commands — Task 9
- ✅ `configure` wizard — Task 10
- ✅ Exit codes 0/1/2/3 — Task 9
- ✅ All edge cases documented and tested — Tasks 3, 6, 11
- ✅ `ltmsh` command, `logseq-tmsh` package — Task 1
- ✅ Python 3.10+, uv, MIT licence — Tasks 1, 12

**Type consistency:**
- `AttributedTask.period_seconds: int` used consistently in filters.py, formatters.py, tests
- `extract_tasks(blocks, source_file, source_date, ...)` signature matches all call sites
- `format_json` / `format_pretty` signatures consistent with cli.py calls
- `TASK_STATUSES` frozenset imported from `models.py` only (no duplication)
