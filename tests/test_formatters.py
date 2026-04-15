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
