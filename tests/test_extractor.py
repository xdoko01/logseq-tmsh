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
