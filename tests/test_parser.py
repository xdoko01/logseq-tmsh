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
