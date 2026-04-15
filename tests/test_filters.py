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
