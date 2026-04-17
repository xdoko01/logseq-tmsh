from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

_DEFAULTS: dict = {
    "paths": {
        "journals": "",
        "extra_dirs": [],
        "scan_from": None,
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
    scan_from: date | None  # optional lower bound on file scanning (YYYY-MM-DD in config)
    midnight_split: str
    time_spent_property: str
    completed_property: str
    started_property: str
    date_format: str
    datetime_format: str  # reserved — not yet used by formatters
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
    """Return config file paths in precedence order (last wins).

    Search order:
      1. ~/.logseq-tmsh/config.toml  (user-level)
      2. ./logseq-tmsh.toml          (project-local, overrides user-level)
      3. extra_path                   (explicit --config, highest precedence)
    """
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
        try:
            with open(path, "rb") as f:
                user_cfg = tomllib.load(f)
        except Exception as exc:
            print(f"WARNING: Could not parse config file {path}: {exc}", file=sys.stderr)
            continue
        merged = _deep_merge(merged, user_cfg)

    p = merged["paths"]
    pa = merged["parsing"]
    o = merged["output"]

    scan_from: date | None = None
    if p.get("scan_from"):
        try:
            scan_from = date.fromisoformat(p["scan_from"])
        except (ValueError, TypeError) as exc:
            print(f"WARNING: Invalid scan_from in config ({p['scan_from']!r}): {exc}", file=sys.stderr)

    return Config(
        journals=p["journals"],
        extra_dirs=p["extra_dirs"],
        scan_from=scan_from,
        midnight_split=pa["midnight_split"],
        time_spent_property=pa["time_spent_property"],
        completed_property=pa["completed_property"],
        started_property=pa["started_property"],
        date_format=o["date_format"],
        datetime_format=o["datetime_format"],
        default_fields=o["default_fields"],
        include_zero=o["include_zero"],
    )
