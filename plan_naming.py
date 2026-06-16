"""Human-friendly default names for generated (`plan_versions`) plans.

Generated plans carry no stored name — a `plan_versions` row has only scope
dates + pattern. The athlete-facing label is *derived* from their target race
(`race_events.is_target_event`), falling back to a plain label when no target
race is set. Single source of truth so the plans list, the plan header, and the
dashboard all read the same string (#620).
"""
from datetime import date


def target_race_name(db, user_id: int) -> str | None:
    """The athlete's target-race name (`is_target_event=TRUE`), or None.

    A lightweight single-column read for display labels — deliberately avoids
    hydrating the full race payload (`race_events_repo.load_race_event_payload`),
    which fans out into route-locale + equipment + terrain queries we don't need
    just to print a name.
    """
    row = db.execute(
        "SELECT name FROM race_events WHERE user_id = ? AND is_target_event = TRUE LIMIT 1",
        (user_id,),
    ).fetchone()
    # `.get` (rows are dict-like `_PgRow`) so a fakeless render-test row without
    # the column degrades to "no target race" rather than KeyError-ing the page;
    # the production SELECT always carries `name`.
    return row.get("name") if row else None


def _coerce_date(value):
    """Coerce a DATE column to a `date`; tolerate ISO strings (the render
    harness's fake cursor hands those back) and return None for anything
    unparseable so a bad value just drops the week suffix rather than erroring.
    """
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _scope_weeks(scope_start, scope_end) -> int | None:
    """Whole-week span of a plan's scope, or None when the dates don't yield a
    sane (>=1) count."""
    start = _coerce_date(scope_start)
    end = _coerce_date(scope_end)
    if start is None or end is None:
        return None
    weeks = round((end - start).days / 7)
    return weeks if weeks >= 1 else None


def generated_plan_name(race_name, scope_start, scope_end) -> str:
    """Default display name for a generated plan.

    With a target race: ``"<race> — <N>-week build"`` (drops the suffix when the
    scope dates don't yield a sane week count). Without one: a plain
    ``"Training plan"`` — the athlete hasn't tied a race to their training yet.
    """
    race_name = (race_name or "").strip()
    if not race_name:
        return "Training plan"
    weeks = _scope_weeks(scope_start, scope_end)
    return f"{race_name} — {weeks}-week build" if weeks else race_name
