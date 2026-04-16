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
