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

State: `data/cot_latest_state.json` (last attempt per family, and what it found).
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


def stored_week(family: str, data: Path = DATA) -> pd.Timestamp | None:
    """The W-FRI Friday of the newest report held by ANY file of `family` (None when empty)."""
    from mt5desk import cot_frames
    best: pd.Timestamp | None = None
    for path in sorted((data / DIRS[family]).glob("*.parquet")):
        try:
            dates = pd.to_datetime(pd.read_parquet(path, columns=["report_date"])["report_date"],
                                   utc=True, errors="coerce").dropna()
        except Exception:
            continue
        if dates.empty:
            continue
        wk = cot_frames._week_friday(dates.max())
        best = wk if best is None or wk > best else best
    return best


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


def _socrata(family: str, data: Path, deadline: float) -> dict[str, str]:
    """Refetch every contract of the legacy or disaggregated fetcher (full history per call)."""
    if family == "legacy":
        from mt5desk import fetch_cot as mod
    else:
        from mt5desk import fetch_cot_disagg as mod
    out: dict[str, str] = {}
    for slug, candidates in mod.TARGETS:
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


def _tff(data: Path, deadline: float) -> dict[str, str]:
    from mt5desk import fetch_tff
    year = datetime.now(tz=UTC).year
    doc = fetch_tff.run([year - 1, year], keep_existing=True, out=data / DIRS["tff"])
    out = {slug: str(f.get("status")) for slug, f in doc["files"].items()}
    if doc.get("failed"):
        out["_download_failed"] = ",".join(str(y) for y in doc["failed"])
    return out


Fetcher = Callable[[str, Path, float], dict[str, str]]


def _default_fetch(family: str, data: Path, deadline: float) -> dict[str, str]:
    return _tff(data, deadline) if family == "tff" else _socrata(family, data, deadline)


def _load_state(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def run(*, now: pd.Timestamp | None = None, force: bool = False, budget_s: float = 120.0,
        data: Path = DATA, state_path: Path | None = None,
        fetch: Fetcher = _default_fetch) -> dict[str, Any]:
    """One pass. Fetches only a family that is behind the release schedule and not tried within
    RETRY_HOURS (`force` ignores both). Returns what it found and did; never raises on I/O."""
    t = now if now is not None else _now()
    state_file = state_path or (data / STATE.name)
    state = _load_state(state_file)
    deadline = time.monotonic() + max(1.0, float(budget_s))
    due = latest_released_week(t)
    fams: dict[str, Any] = {}
    for fam in FAMILIES:
        have = stored_week(fam, data)
        behind = due is not None and (have is None or have < due)
        prev = state.get(fam) if isinstance(state.get(fam), dict) else {}
        last = pd.to_datetime(prev.get("attempted_at"), utc=True, errors="coerce")
        recent = (last is not None and not pd.isna(last)
                  and (t - last) < pd.Timedelta(hours=RETRY_HOURS))
        row: dict[str, Any] = {"stored_week": None if have is None else str(have.date()),
                               "due_week": None if due is None else str(due.date()),
                               "behind": bool(behind)}
        if not (behind or force):
            row["action"] = "CURRENT"
        elif recent and not force:
            row["action"] = "WAITING_RETRY"
            row["last_attempt"] = prev.get("attempted_at")
        elif time.monotonic() > deadline:
            row["action"] = "SKIPPED_BUDGET"
        else:
            try:
                files = fetch(fam, data, deadline)
            except Exception as exc:
                files = {"_error": f"{type(exc).__name__}: {exc}"[:200]}
            after = stored_week(fam, data)
            row.update({"action": "FETCHED", "files": files,
                        "stored_week_after": None if after is None else str(after.date()),
                        "caught_up": bool(due is not None and after is not None
                                          and after >= due)})
            state[fam] = {"attempted_at": t.isoformat(), "caught_up": row["caught_up"],
                          "stored_week_after": row["stored_week_after"]}
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
