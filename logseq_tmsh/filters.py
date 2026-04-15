from __future__ import annotations

import sys
from datetime import date, datetime, timedelta

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
    if midnight_split not in ("split", "start", "end"):
        raise ValueError(
            f"midnight_split must be 'split', 'start', or 'end'; got {midnight_split!r}"
        )

    total = int((end - start).total_seconds())
    if total <= 0:
        return 0

    if midnight_split == "start":
        return total if period_start <= start.date() <= period_end else 0

    if midnight_split == "end":
        return total if period_start <= end.date() <= period_end else 0

    # Default: "split" — clip interval to [period_start 00:00, period_end+1 00:00)
    window_start = datetime.combine(period_start, datetime.min.time())
    window_end = datetime.combine(period_end + timedelta(days=1), datetime.min.time())
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
