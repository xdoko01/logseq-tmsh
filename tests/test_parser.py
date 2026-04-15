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
