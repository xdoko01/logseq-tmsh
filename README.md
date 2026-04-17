# logseq-tmsh

Extract time-tracking data from [LogSeq](https://logseq.com/) journal CLOCK entries.

logseq-tmsh reads your LogSeq graph's daily journal files and sums up time from org-mode `CLOCK:` blocks, letting you query what you worked on today, this week, or any date range.

## Install

```bash
pip install logseq-tmsh
# or
uv tool install logseq-tmsh
```

## Quick Start

```bash
# Show version
ltmsh --version

# Configure once
ltmsh configure

# Show today's work
ltmsh today

# Show this week
ltmsh week

# Show a custom range (dates in YYYY-MM-DD format)
ltmsh range --from 2024-01-01 --to 2024-01-31

# Human-readable output
ltmsh today --pretty

# Filter by tag (AND logic)
ltmsh today --tag ori --tag meeting

# Pretty-print JSON
ltmsh today --indent 2
```

## Scanning Old Tasks

By default, **all** journal files are scanned — not just files within the queried period. This is intentional: in LogSeq, a task created years ago accumulates CLOCK entries in its original file, so restricting the file scan to the query window would silently miss recently-clocked work on old tasks.

```bash
# Correctly finds time logged today on a task created in 2023
ltmsh today
```

For large vaults where you know your active tasks are recent, use `--scan-from` to skip old files and speed up queries:

```bash
# Only scan files dated 2025-01-01 or later
ltmsh today --scan-from 2025-01-01
ltmsh week --scan-from 2025-01-01
ltmsh range --from 2026-04-01 --to 2026-04-17 --scan-from 2025-01-01
```

You can also set a permanent default in `~/.logseq-tmsh/config.toml`:

```toml
[paths]
journals = "/path/to/logseq/journals"
scan_from = "2025-01-01"   # omit to scan all files (default)
```

## Output Fields

`title`, `status`, `time_period`, `time_total`, `time_override`, `started`, `completed`, `tags`, `refs`, `has_running_clock`, `description`, `source_file`, `source_date`

## Configuration

`~/.logseq-tmsh/config.toml` — created by `ltmsh configure`.

## License

MIT
