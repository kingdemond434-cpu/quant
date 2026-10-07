"""Keep the in-git CFTC files current: refetch when a released report is missing from them.

    python mt5desk/fetch_cot_latest.py [--force] [--json]

A FETCHER (it writes the CFTC datasets and joins nothing to bars), named `fetch_*` like its
three siblings; it reads no report except to compare its newest week with the schedule.

THE DEFECT (2026-10-07 audit). `cot/`, `cot_tff/` and `cot_disagg/` were written once by hand
and nothing ever ran their fetchers again: every file stopped at the 2026-08-11 report, so the
positioning-change cells were judged on a history that silently aged by a week every Friday, and
the TFF NZD file had stopped at 2022-02-01 when the contract was renamed. No organ noticed,
because a stale parquet reads exactly like a current one.

WHAT A PASS DOES. It asks `cot_frames.release_schedule` for the newest report week whose TRUE
release (holiday and shutdown delays included) is already past, and compares it with the newest
report week stored in each family's files. Only a family that is BEHIND is fetched, and at most
once per `RETRY_HOURS` (the CFTC is sometimes late beyond its own schedule; hammering it changes
nothing). Each file is written only when the fetch holds at least every report week the stored
file holds -- never overwritten with less -- so a partial or failed download leaves the file as
it was. Network failure is recorded, never raised: this runs inside the hourly
`cot_positioning_flow` leg and must not cost it its pass.

FRESHNESS IS PER FILE, NOT PER FAMILY (#238 audit, 2026-10-07). The family used to read as
current when ANY of its files held the due report, so the TFF NZD file sat at 2022-02-01 behind
eight current siblings and nothing fetched it. A family is now behind when ANY file is, and only
the behind files are refetched (`plan["slugs"]`). A file a successful fetch did not advance is
STALLED (a contract the CFTC no longer reports, e.g. legacy S&P 500 after 2021) and waits
`STALLED_RETRY_HOURS` instead of costing the family a full refetch every `RETRY_HOURS`.

HOLES ARE BACKFILLED FROM THE ANNUAL FILES (#238 audit, 2026-10-07). The old TFF step fetched only
this year and last, so a hole further back -- the 2018-2024 weeks the cross-rate dedup had cost
EUR, GBP, JPY and the index files, and NZD's 2022-2025 after its rename -- could never close.
`tff_hole_years` lists, per file, the years holding a report week missing between the file's
first report and the newest released one; those years are fetched from the CFTC's historical
annual files (`fetch_tff.load_year`, the same source `fetch_tff` uses) and merged in, never
overwriting with less. A year that downloaded and still leaves the hole is recorded as UNFILLABLE
for that file and not asked for again (until `--force`), so a week the CFTC never published
cannot become a download every six hours.

State: `data/cot_latest_state.json` (last attempt per family and file, and what it found).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))
from mt5desk.config import DATA  # noqa: E402

STATE = DATA / "cot_latest_state.json"
RETRY_HOURS = 6.0
#: A file a successful fetch did not advance waits this long before it is asked for again.
STALLED_RETRY_HOURS = 7 * 24.0
#: ...and only when it was already this far behind the due week before the fetch.
STALLED_AFTER_DAYS = 28
FAMILIES = ("legacy", "tff", "disagg")
DIRS = {"legacy": "cot", "tff": "cot_tff", "disagg": "cot_disagg"}


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def latest_released_week(now: pd.Timestamp | None = None) -> pd.Timestamp | None:
    """The W-FRI Friday of the newest report whose release label is at or before `now`."""
    from mt5desk import cot_frames
    t = now if now is not None else _now()
    sched = cot_frames.release_schedule()
    past = sched[sched <= t]
    return None if past.empty else pd.Timestamp(past.index[-1])


def _file_week(path: Path) -> pd.Timestamp | None:
    """The W-FRI Friday of the newest report in one file (None when unreadable or empty)."""
    from mt5desk import cot_frames
    try:
        dates = pd.to_datetime(pd.read_parquet(path, columns=["report_date"])["report_date"],
                               utc=True, errors="coerce").dropna()
    except Exception:
        return None
    return None if dates.empty else cot_frames._week_friday(dates.max())


def stored_weeks(family: str, data: Path = DATA) -> dict[str, pd.Timestamp | None]:
    """{file slug: W-FRI Friday of its newest report} for every file of `family`."""
    return {path.stem: _file_week(path)
            for path in sorted((data / DIRS[family]).glob("*.parquet"))}


def stored_week(family: str, data: Path = DATA) -> pd.Timestamp | None:
    """The newest report week of the STALEST file of `family` (None when any file is empty or
    unreadable, or there are no files). Per file, not per family: one current file no longer
    hides a sibling that stopped years ago."""
    weeks = list(stored_weeks(family, data).values())
    if not weeks or any(w is None for w in weeks):
        return None
    return min(w for w in weeks if w is not None)


def behind_files(family: str, due: pd.Timestamp | None, data: Path = DATA) -> list[str]:
    """Slugs of `family` whose newest report is older than `due` (or unreadable)."""
    if due is None:
        return []
    return sorted(slug for slug, wk in stored_weeks(family, data).items()
                  if wk is None or wk < due)


def _asof_year(friday: pd.Timestamp) -> int:
    """The calendar year of a report week's as-of TUESDAY -- the annual file that carries it."""
    return int((pd.Timestamp(friday) - pd.Timedelta(days=3)).year)


def tff_hole_years(due: pd.Timestamp | None, data: Path = DATA,
                   skip: dict[str, list[int]] | None = None) -> dict[str, list[int]]:
    """{slug: years} holding a report week missing from that TFF file, between the file's first
    report (no earlier than `fetch_tff.FIRST_YEAR`) and `due`. Only files on disk are read (a
    file the desk never fetched is `fetch_tff`'s full-history job, not a hole); an unreadable or
    empty one reads as every year from FIRST_YEAR. `skip` removes years already proven
    unfillable per slug."""
    from mt5desk import cot_frames, fetch_tff
    if due is None:
        return {}
    due_wk = cot_frames.week_ordinal(due)
    floor = pd.Timestamp(f"{fetch_tff.FIRST_YEAR}-01-01", tz="UTC")
    out: dict[str, list[int]] = {}
    for slug, _code, _prefixes in fetch_tff.TARGETS:
        path = data / DIRS["tff"] / f"{slug}.parquet"
        if not path.exists():
            continue
        try:
            dates = pd.to_datetime(pd.read_parquet(path, columns=["report_date"])["report_date"],
                                   utc=True, errors="coerce").dropna()
        except Exception:
            dates = pd.Series(dtype="datetime64[ns, UTC]")
        start = max(floor, dates.min()) if not dates.empty else floor
        have = {cot_frames.week_ordinal(d) for d in dates}
        epoch = pd.Timestamp("1970-01-02", tz="UTC")
        years = sorted({_asof_year(epoch + pd.Timedelta(weeks=w))
                        for w in range(cot_frames.week_ordinal(start), due_wk + 1)
                        if w not in have})
        gone = set((skip or {}).get(slug) or [])
        years = [y for y in years if y not in gone]
        if years:
            out[slug] = years
    return out


def _weeks(df: pd.DataFrame) -> set[int]:
    from mt5desk import cot_frames
    dates = pd.to_datetime(df["report_date"], utc=True, errors="coerce").dropna()
    return {cot_frames.week_ordinal(d) for d in dates}


def write_if_not_less(path: Path, new: pd.DataFrame | None) -> str:
    """Write `new` over `path` only when it holds every report week the stored file holds."""
    if new is None or new.empty or "report_date" not in new.columns:
        return "NO_ROWS"
    if path.exists():
        try:
            old = pd.read_parquet(path, columns=["report_date"])
            if not _weeks(old) <= _weeks(new):
                return "KEPT_STORED_HAS_MORE"
        except Exception:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(path, index=False)
    return "WRITTEN"


def _socrata(family: str, data: Path, deadline: float,
             plan: dict[str, Any] | None = None) -> dict[str, str]:
    """Refetch the legacy or disaggregated contracts named in `plan["slugs"]` (every contract
    when the plan names none); full history per call, written only when not less."""
    if family == "legacy":
        from mt5desk import fetch_cot as mod
    else:
        from mt5desk import fetch_cot_disagg as mod
    wanted = set((plan or {}).get("slugs") or [])
    out: dict[str, str] = {}
    for slug, candidates in mod.TARGETS:
        if wanted and slug not in wanted:
            continue
        if time.monotonic() > deadline:
            out[slug] = "SKIPPED_BUDGET"
            continue
        df = None
        try:
            for cand in candidates:
                df = mod.fetch_contract(cand)
                if df is not None:
                    break
        except Exception as exc:
            out[slug] = f"FETCH_FAILED {type(exc).__name__}"
            continue
        out[slug] = write_if_not_less(data / DIRS[family] / f"{slug}.parquet", df)
    if family == "legacy" and out.get("gold") == "WRITTEN":
        import shutil
        shutil.copy(data / "cot" / "gold.parquet", data / "cot_gold.parquet")
    return out


def _tff(data: Path, deadline: float, plan: dict[str, Any] | None = None) -> dict[str, str]:
    """Fetch the plan's years from the CFTC annual TFF files and merge them into every file.

    The years are the hole years (`tff_hole_years`, which include the tail of any file behind
    the schedule); with none named, this year and last. A year past the deadline is not
    downloaded and reads as failed, so the budget is never overrun by a long backfill."""
    from mt5desk import fetch_tff
    year = datetime.now(tz=UTC).year
    years = sorted({int(y) for y in ((plan or {}).get("years") or [])}) or [year - 1, year]

    def guarded(y: int) -> pd.DataFrame | None:
        return None if time.monotonic() > deadline else fetch_tff.load_year(y)

    doc = fetch_tff.run(years, keep_existing=True, out=data / DIRS["tff"], loader=guarded)
    out = {slug: str(f.get("status")) for slug, f in doc["files"].items()}
    out["_years_fetched"] = ",".join(str(y) for y in doc.get("fetched") or [])
    if doc.get("failed"):
        out["_download_failed"] = ",".join(str(y) for y in doc["failed"])
    return out


Fetcher = Callable[[str, Path, float, dict[str, Any]], dict[str, str]]


def _default_fetch(family: str, data: Path, deadline: float,
                   plan: dict[str, Any] | None = None) -> dict[str, str]:
    return (_tff(data, deadline, plan) if family == "tff"
            else _socrata(family, data, deadline, plan))


def _load_state(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _recent(stamp: Any, t: pd.Timestamp, hours: float) -> bool:
    last = pd.to_datetime(stamp, utc=True, errors="coerce")
    return last is not None and not pd.isna(last) and (t - last) < pd.Timedelta(hours=hours)


def run(*, now: pd.Timestamp | None = None, force: bool = False, budget_s: float = 120.0,
        data: Path = DATA, state_path: Path | None = None,
        fetch: Fetcher = _default_fetch) -> dict[str, Any]:
    """One pass. Fetches only the files that are behind the release schedule (and, for TFF,
    the annual years that hold a hole), at most once per RETRY_HOURS per family and once per
    STALLED_RETRY_HOURS per stalled file (`force` ignores all three). Returns what it found and
    did; never raises on I/O."""
    t = now if now is not None else _now()
    state_file = state_path or (data / STATE.name)
    state = _load_state(state_file)
    deadline = time.monotonic() + max(1.0, float(budget_s))
    due = latest_released_week(t)
    fams: dict[str, Any] = {}
    for fam in FAMILIES:
        prev = state.get(fam) if isinstance(state.get(fam), dict) else {}
        stalled_prev = prev.get("stalled") if isinstance(prev.get("stalled"), dict) else {}
        unfillable = prev.get("unfillable") if isinstance(prev.get("unfillable"), dict) else {}
        before = stored_weeks(fam, data)
        lagging = behind_files(fam, due, data)
        stalled = sorted(f for f in lagging
                         if not force and _recent(stalled_prev.get(f), t, STALLED_RETRY_HOURS))
        slugs = [f for f in lagging if f not in stalled]
        holes = (tff_hole_years(due, data, None if force else unfillable)
                 if fam == "tff" else {})
        holes = {k: v for k, v in holes.items() if k not in stalled}
        have = stored_week(fam, data)
        behind = bool(slugs) or bool(holes)
        recent = _recent(prev.get("attempted_at"), t, RETRY_HOURS)
        row: dict[str, Any] = {"stored_week": None if have is None else str(have.date()),
                               "due_week": None if due is None else str(due.date()),
                               "behind": behind, "files_behind": slugs,
                               "files_stalled": stalled}
        if holes:
            row["hole_years"] = holes
        if not (behind or force):
            row["action"] = "CURRENT"
        elif recent and not force:
            row["action"] = "WAITING_RETRY"
            row["last_attempt"] = prev.get("attempted_at")
        elif time.monotonic() > deadline:
            row["action"] = "SKIPPED_BUDGET"
        else:
            plan = {"slugs": sorted(set(slugs) | set(holes)),
                    "years": sorted({y for ys in holes.values() for y in ys})}
            row["plan"] = plan
            failed = False
            try:
                files = fetch(fam, data, deadline, plan)
            except Exception as exc:
                failed = True
                files = {"_error": f"{type(exc).__name__}: {exc}"[:200]}
            after_by_file = stored_weeks(fam, data)
            after = stored_week(fam, data)
            new_stalled = dict(stalled_prev)
            if not failed:
                for f in slugs:
                    # STALLED only when the file was already far behind (a contract no longer
                    # reported); a report the CFTC is merely late with waits RETRY_HOURS.
                    old = before.get(f)
                    far = (due is not None and old is not None
                           and old < due - pd.Timedelta(days=STALLED_AFTER_DAYS))
                    if far and after_by_file.get(f) == old:
                        new_stalled[f] = t.isoformat()
                    else:
                        new_stalled.pop(f, None)
            new_unfillable = {k: list(v) for k, v in unfillable.items()}
            if fam == "tff" and not failed:
                fetched = {int(y) for y in str(files.get("_years_fetched") or "").split(",")
                           if y.strip().isdigit()}
                left = tff_hole_years(due, data)
                for f, ys in left.items():
                    dead = sorted(set(ys) & fetched & set(holes.get(f) or []))
                    if dead:
                        new_unfillable[f] = sorted(set(new_unfillable.get(f) or []) | set(dead))
                row["hole_years_after"] = left
            row.update({"action": "FETCHED", "files": files,
                        "stored_week_after": None if after is None else str(after.date()),
                        "caught_up": bool(due is not None and after is not None
                                          and after >= due)})
            state[fam] = {"attempted_at": t.isoformat(), "caught_up": row["caught_up"],
                          "stored_week_after": row["stored_week_after"],
                          "stalled": new_stalled, "unfillable": new_unfillable}
        fams[fam] = row
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, sort_keys=True), "utf-8")
        tmp.replace(state_file)
    except OSError:
        pass
    return {"at": t.isoformat(timespec="seconds"),
            "due_week": None if due is None else str(due.date()), "families": fams}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="fetch every family now")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = run(force=args.force, budget_s=args.budget_s)
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for fam, row in doc["families"].items():
            print(f"{fam:>7}: {row.get('action')} stored={row.get('stored_week')} "
                  f"due={row.get('due_week')} after={row.get('stored_week_after', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
