"""THE COT_FX CLOCK -- CFTC legacy positioning, refreshed weekly after Friday's release.

WHY THIS EXISTS (measured 2026-11-03). `data/cot/*.parquet` -- the `cot_fx` dataset that
`cot_positioning`, `orthogonal_sweep`, `edge_search`, `free_shadows`, `run_cot_macro_sweep`,
`owned_data` and the feature store all read -- held a newest report_date of 2026-08-11 on the
trading box itself, newest file write 09-11. Its writer, `mt5desk/fetch_cot.py`, was a one-shot
ingest (2026-08-16) that ran on the retired laptop and was never put on a clock on Contabo: no box
task, no hourly or daily leg, no VPS timer (`quant-cot-fetch.timer` runs `scripts/fetch_cot.py`,
which writes a different root's crypto COT). Two sync scripts carried the directory in a CIRCLE
(`desks/mt5/scripts/sync_to_vps.ps1` box -> VPS, `ops/run_external_pipeline.sh` VPS -> box), so
the files kept being "synced" while nothing ever wrote a new row. The dataset-usage census
(reports/DATASET_USAGE.json) reported it STARVED.

THE CADENCE IS THE SOURCE'S. CFTC snapshots positions on Tuesday and publishes on Friday at
15:30 ET (19:30/20:30 UTC). This runs every hour on the core clock and fetches only when a newer
report should exist: when now is past the Friday 21:00 UTC that follows the next Tuesday after
the newest report on disk. Otherwise it writes a NOT_DUE receipt and returns in milliseconds. A
pass that fetched and found nothing newer (a holiday or shutdown slip) backs off BACKOFF_H.

POLITE AND FAIL-CLOSED. The desk's honest UA, robots.txt read first (unreadable -> refused), and a
401 / 403 / 429 / WAF page is a HARD STOP: `data/COT_FX_HARD_STOP.json` is written and every later
pass holds until a person removes that file. Free, keyless, no crypto host (the legacy schema's
FX, metals and index contracts only; `side_channels/fetch_cot.py`, the BTC/ETH twin, is not run).

    python desks/mt5/research/cot_fx_refresh.py [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "COT_FX_FETCH.json"
COT_DIR = DESK / "data" / "cot"
HARD_STOP_FILE = DESK / "data" / "COT_FX_HARD_STOP.json"
#: After a fetch that found nothing newer, or failed, wait this long before the next try.
BACKOFF_H = 6.0
#: Report Tuesday -> the NEXT report's publication Friday, 21:00 UTC (after 15:30 ET in both
#: daylight regimes): +7 days to the next Tuesday, +3 days to its Friday.
NEXT_RELEASE_AFTER = timedelta(days=10, hours=21)


def newest_report(cot_dir: Path = COT_DIR) -> datetime | None:
    """The newest report_date over every contract file; None when there is none."""
    import pandas as pd
    best: datetime | None = None
    for p in sorted(cot_dir.glob("*.parquet")):
        try:
            s = pd.read_parquet(p, columns=["report_date"])["report_date"]
        except Exception:
            continue
        if s.empty:
            continue
        t = pd.Timestamp(s.max())
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        d = t.to_pydatetime()
        best = d if best is None or d > best else best
    return best


def next_release(newest: datetime) -> datetime:
    day = newest.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day + NEXT_RELEASE_AFTER


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def decide(newest: datetime | None, prev: dict[str, Any], now: datetime,
           held: dict[str, Any] | None) -> tuple[bool, str]:
    """(fetch?, why). Pure, so every branch is testable."""
    if held:
        return False, (f"HARD STOP held since {held.get('at')}: {held.get('why')} -- remove "
                       f"{HARD_STOP_FILE.relative_to(DESK).as_posix()} to clear")
    last = _ts(prev.get("attempted_at"))
    if last is not None and prev.get("status") in ("NO_NEW_REPORT", "FAILED") \
            and (now - last) < timedelta(hours=BACKOFF_H):
        return False, f"backoff: last attempt {last.isoformat()} was {prev.get('status')}"
    if newest is None:
        return True, "no COT file on this host: full fetch"
    due = next_release(newest)
    if now >= due:
        return True, f"newest report {newest.date()}; the next was due {due.isoformat()}"
    return False, f"newest report {newest.date()} is current; next release {due.isoformat()}"


def _write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, out)


def run(*, now: datetime | None = None, force: bool = False, cot_dir: Path = COT_DIR,
        out: Path = OUT, hard_stop: Path = HARD_STOP_FILE,
        fetch: Any = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    prev = _read(out)
    held = _read(hard_stop) or None
    newest = newest_report(cot_dir)
    go, why = decide(newest, prev, now, held)
    if force and not held:
        go, why = True, "forced"
    doc: dict[str, Any] = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/cot_fx_refresh.py",
        "writer": "desks/mt5/mt5desk/fetch_cot.py",
        "dataset": "cot_fx", "cadence": "weekly",
        "terms_basis": ("publicreporting.cftc.gov has no SOURCE_POLICY row: the policy's "
                        "PUBLIC_PAGE default for an unlisted host; libs.data.terms_fence.check_url "
                        "is consulted whenever it is on this tree"),
        "newest_before": newest.isoformat() if newest else "UNMEASURED",
        "decision": why,
        "attempted_at": prev.get("attempted_at"),
        "status": prev.get("status") if not go else None,
    }
    if not go:
        doc["status"] = "HELD" if held else "NOT_DUE"
        print(f"WRITE_OR_EXPLAIN: NO_OP {why}", flush=True)
        doc["elapsed_s"] = round(time.monotonic() - t0, 3)
        _write(doc, out)
        return doc
    if fetch is None:
        from mt5desk import fetch_cot as _fc
        fetch = _fc
    doc["attempted_at"] = now.isoformat(timespec="seconds")
    try:
        got = fetch.fetch_all(out=cot_dir)
    except fetch.HardStop as exc:
        stop = {"at": now.isoformat(timespec="seconds"), "why": str(exc),
                "rule": "a 401/403/429, a WAF page or a robots refusal is a hard stop; "
                        "a person clears it by deleting this file"}
        hard_stop.parent.mkdir(parents=True, exist_ok=True)
        hard_stop.write_text(json.dumps(stop, indent=1), "utf-8")
        doc.update(status="HARD_STOP", error=str(exc))
    except Exception as exc:
        doc.update(status="FAILED", error=f"{type(exc).__name__}: {exc}"[:400])
    else:
        after = newest_report(cot_dir)
        doc["contracts"] = got
        doc["newest_after"] = after.isoformat() if after else "UNMEASURED"
        doc["status"] = ("FETCHED" if after is not None and (newest is None or after > newest)
                         else "NO_NEW_REPORT")
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    _write(doc, out)
    print(json.dumps({k: doc.get(k) for k in ("status", "decision", "newest_before",
                                                "newest_after", "error")}), flush=True)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--force", action="store_true", help="fetch now unless a hard stop holds")
    a = ap.parse_args(argv)
    doc = run(force=a.force)
    # A failure and the pass that HIT a hard stop are loud; a pass that holds behind one is not.
    return 1 if doc.get("status") in ("FAILED", "HARD_STOP") else 0


if __name__ == "__main__":
    sys.exit(main())
