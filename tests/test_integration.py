import json
from pathlib import Path

from typer.testing import CliRunner

from logseq_tmsh.cli import app

runner = CliRunner()
JOURNALS = Path(__file__).parent / "fixtures" / "integration"


def _cfg(tmp_path, journals_path=None):
    """Write a fully explicit config TOML pointing at the given journals dir.

    Writes all relevant keys so user-level (~/.logseq-tmsh/config.toml) or
    project-local (./logseq-tmsh.toml) files cannot bleed in and change test
    behaviour (e.g. include_zero=true, custom default_fields).
    """
    cfg = tmp_path / "config.toml"
    path = (journals_path or JOURNALS).as_posix()
    cfg.write_text(
        f'[paths]\njournals = "{path}"\nextra_dirs = []\n'
        '[parsing]\nmidnight_split = "split"\n'
        'time_spent_property = "time_spent"\ncompleted_property = "completed"\n'
        'started_property = "started"\n'
        '[output]\ndate_format = "%Y-%m-%d"\ndatetime_format = "%Y-%m-%d %H:%M"\n'
        'default_fields = ["title","status","time_period","started","completed","tags"]\n'
        'include_zero = false\n',
        encoding="utf-8",
    )
    return str(cfg)


def test_range_json_output(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
        "--indent", "2",
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


def test_range_apr15_task_count(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
        "--fields", "title,status,time_period",
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    data = json.loads(result.output)
    # 3 tasks on Apr 15 all have time > 0
    assert len(data) == 3


def test_range_two_day_window(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-14", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
        "--fields", "title,status,time_period",
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    data = json.loads(result.output)
    # 2 tasks on Apr 14 + 3 on Apr 15 = 5 total
    assert len(data) == 5


def test_range_tag_filter(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-14", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
        "--tag", "ori", "--tag", "meeting",
        "--fields", "title,status,tags",
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    data = json.loads(result.output)
    # Only the meeting task on Apr 14 has both #ori and #meeting
    assert len(data) == 1
    assert "meeting" in data[0].get("tags", [])


def test_range_pretty_output(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
        "--pretty",
        "--fields", "status,time_period,title",
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    lines = result.output.strip().splitlines()
    assert lines[0] == "STATUS  TIME_PERIOD  TITLE"


def test_missing_journals_returns_exit_2(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", _cfg(tmp_path, tmp_path / "nonexistent"),
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


def test_strip_tags_removes_hash_tags(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-15", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
        "--strip-tags",
        "--fields", "title",
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    data = json.loads(result.output)
    for item in data:
        assert "#" not in item["title"]


def test_invalid_date_returns_exit_1(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "not-a-date", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
    ])
    assert result.exit_code == 1


def test_inverted_date_range_returns_exit_1(tmp_path):
    result = runner.invoke(app, [
        "range", "--from", "2026-04-16", "--to", "2026-04-15",
        "--config", _cfg(tmp_path),
    ])
    assert result.exit_code == 1


def test_empty_result_set_returns_exit_zero(tmp_path):
    # A date range with no matching journal files → empty array, exit 0
    result = runner.invoke(app, [
        "range", "--from", "2020-01-01", "--to", "2020-01-01",
        "--config", _cfg(tmp_path),
    ])
    assert result.exit_code == 0, (result.output or repr(result.exception))
    data = json.loads(result.output)
    assert data == []
