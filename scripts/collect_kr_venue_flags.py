#!/usr/bin/env python3
"""KR VENUE FLAG RECORDER (R0299) -- Upbit market_event + Bithumb warning/asset rails.

MECHANISM (stated before any screen): the Korean venues publish ADMINISTRATIVE state that
directly sets the barrier height behind the KR premium -- Upbit's warning + 5 caution flags
(including CONCENTRATION_OF_SMALL_ACCOUNTS and GLOBAL_PRICE_DIFFERENCES, i.e. the venue's OWN
kimchi-premium detector), Bithumb's market_warning, and Bithumb's per-asset deposit/withdrawal
open-closed rails. Bithumb rail state is an INDEPENDENT barrier-height regressor: every prior
KR premium study inferred the barrier FROM the premium; this surface breaks that circularity.

WHY A RECORDER AND NOT A FETCHER: ALL THREE SURFACES ARE SNAPSHOT-ONLY WITH NO HISTORY
ENDPOINT. Every unrecorded transition is permanently lost (L1.46) -- the archive this file
builds is baseline + transition rows, from which the full flag state at any past instant is
reconstructible. Nobody, including the venue, sells this series retroactively.

CLOCK PROVENANCE (L1.46, libs/research/clock_provenance.py convention): neither venue stamps
the payload with an event time, so the observation clock is OURS: every row carries
recv = receipt time and clock = "recv_only" -- a VENUE LIMITATION recorded as such, never a
desk defect. Transition timestamps therefore inherit the poll cadence (+/- one tick).

THE FAILURE MODE THIS FILE REFUSES (L1.51 absence-looks-like-health): a failed fetch must
NEVER be diffed -- diffing an empty snapshot against yesterday's state would record every flag
as CLEARED and every market as DELISTED. A venue that did not answer keeps its prior state
untouched, its error is recorded in the status artifact, and the tick is DEGRADED (all three
down = UNMEASURED, because an unmeasured hour must never look like a quiet one).

SOURCES (s13: keyless, first-party, documented public APIs; 3 GETs per run, no pagination):
  * https://api.upbit.com/v1/market/all?isDetails=true          (market_event per market)
  * https://api.bithumb.com/v1/market/all?isDetails=true        (market_warning per market)
  * https://api.bithumb.com/public/assetsstatus/ALL             (deposit/withdrawal per asset)

    .venv/bin/python scripts/collect_kr_venue_flags.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = "data/kr_venue_flags.jsonl"
_STATE = "data/kr_venue_flags_state.json"
_STATUS = "data/kr_venue_flags_status.json"
_UA = "quant-desk-research/1.0 (public-endpoint reader)"
_TIMEOUT = 20

Flags = dict[str, Any]          # flag name -> value ("warning": False, "deposit_status": 1)
Snapshot = dict[str, Flags]     # market/asset -> flags


def _get(url: str) -> tuple[Any, str]:
    """(payload, error). Never raises -- one dead venue must not kill the tick."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore")), ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:120]}"


def _norm_upbit(doc: Any) -> Snapshot | None:
    """market/all?isDetails=true -> {market: {"warning": bool, "caution.<NAME>": bool}}.
    None on an unrecognised shape -- unparseable is a failed fetch, never an empty venue."""
    if not isinstance(doc, list):
        return None
    out: Snapshot = {}
    for m in doc:
        if not (isinstance(m, dict) and m.get("market")):
            continue
        ev = m.get("market_event") or {}
        flags: Flags = {"warning": bool(ev.get("warning", False))}
        caution = ev.get("caution")
        if isinstance(caution, dict):
            for k, val in sorted(caution.items()):
                flags[f"caution.{k}"] = bool(val)
        out[str(m["market"])] = flags
    return out or None


def _norm_bithumb_markets(doc: Any) -> Snapshot | None:
    """v1/market/all?isDetails=true -> {market: {"market_warning": "NONE"|...}}."""
    if not isinstance(doc, list):
        return None
    out: Snapshot = {}
    for m in doc:
        if isinstance(m, dict) and m.get("market"):
            out[str(m["market"])] = {"market_warning": str(m.get("market_warning", "NONE"))}
    return out or None


def _norm_bithumb_assets(doc: Any) -> Snapshot | None:
    """public/assetsstatus/ALL -> {asset: {"deposit_status": 0|1, "withdrawal_status": 0|1}}."""
    if not (isinstance(doc, dict) and isinstance(doc.get("data"), dict)):
        return None
    out: Snapshot = {}
    for sym, st in doc["data"].items():
        if isinstance(st, dict):
            out[str(sym)] = {"deposit_status": int(st.get("deposit_status", 1)),
                             "withdrawal_status": int(st.get("withdrawal_status", 1))}
    return out or None


def _is_active(v: Any) -> bool:
    """Non-default flag state. Defaults per surface: bool False (no warning/caution),
    str "NONE" (no market_warning), int 1 (deposit/withdrawal OPEN)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v != "NONE"
    if isinstance(v, int):
        return v != 1
    return False


def diff_venue(venue: str, old: Snapshot | None, new: Snapshot, recv: str) -> list[dict[str, Any]]:
    """Rows this tick appends for one venue. First sight of a venue emits a BASELINE (active
    flags only -- 600 rows of 'NONE' carry no information); after that, one row per changed
    flag plus market_present rows for appearing/vanishing markets (listing/delisting for free)."""
    rows: list[dict[str, Any]] = []
    base = {"recv": recv, "clock": "recv_only", "venue": venue}
    if old is None:
        active = {mkt: sorted(k for k, val in flags.items() if _is_active(val))
                  for mkt, flags in new.items()}
        rows.append({**base, "kind": "baseline", "n_markets": len(new),
                     "active": {m: f for m, f in active.items() if f}})
        return rows
    for mkt in sorted(new.keys() - old.keys()):
        rows.append({**base, "kind": "transition", "market": mkt,
                     "field": "market_present", "old": False, "new": True})
        for k in sorted(k for k, val in new[mkt].items() if _is_active(val)):
            rows.append({**base, "kind": "transition", "market": mkt, "field": k,
                         "old": None, "new": new[mkt][k]})
    for mkt in sorted(old.keys() - new.keys()):
        rows.append({**base, "kind": "transition", "market": mkt,
                     "field": "market_present", "old": True, "new": False})
    for mkt in sorted(new.keys() & old.keys()):
        for k in sorted(new[mkt].keys() | old[mkt].keys()):
            o, n = old[mkt].get(k), new[mkt].get(k)
            if o != n:
                rows.append({**base, "kind": "transition", "market": mkt, "field": k,
                             "old": o, "new": n})
    return rows


def _load_state(root: Path) -> dict[str, Any]:
    try:
        st = json.loads((root / _STATE).read_text("utf-8"))
        return st if isinstance(st, dict) else {}
    except FileNotFoundError:
        return {}                                # first run ever: every venue baselines
    except (OSError, ValueError):
        # Corrupt state is a REAL event: rebaselining silently would bury it. Record loudly
        # in the status artifact (collect() sees the empty dict and says so) and rebaseline.
        return {"_state_error": "state file unreadable -- rebaselined this tick"}


def _write_state(root: Path, state: dict[str, Any]) -> None:
    """Atomic (tempfile + os.replace): truncate-then-write on a state file is the crash mode
    this desk has already paid for on the dead-man rail."""
    p = root / _STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".krflags_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, p)


def collect(root: Path, snapshots: dict[str, Snapshot | None],
            errors: dict[str, str]) -> dict[str, Any]:
    """Diff healthy venues against prior state, append rows, persist state. A venue whose
    snapshot is None is NOT diffed and its prior state is retained verbatim."""
    now = datetime.now(tz=UTC).isoformat()
    prior = _load_state(root)
    state_error = prior.pop("_state_error", None)
    rows: list[dict[str, Any]] = []
    new_state: dict[str, Any] = {}
    census: dict[str, Any] = {}
    for venue, snap in snapshots.items():
        old = prior.get(venue)
        if snap is None:                          # failed fetch: prior state survives untouched
            if isinstance(old, dict):
                new_state[venue] = old
            census[venue] = "UNMEASURED-THIS-TICK"
            continue
        rows.extend(diff_venue(venue, old if isinstance(old, dict) else None, snap, now))
        new_state[venue] = snap
        census[venue] = {"n_markets": len(snap),
                         "n_active_flags": sum(1 for flags in snap.values()
                                               for v in flags.values() if _is_active(v))}
    if rows:
        p = root / _OUT
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    _write_state(root, {**new_state, "recv": now})

    n_venues = len(snapshots)
    status = ("UNMEASURED" if len(errors) >= n_venues else   # nothing observed: hour is LOST
              "DEGRADED" if errors else "OK")
    rep = {
        "generated": now, "status": status, "clock": "recv_only",
        "n_transitions": sum(1 for r in rows if r["kind"] == "transition"),
        "n_baselines": sum(1 for r in rows if r["kind"] == "baseline"),
        "venue_census": census, "source_errors": errors,
        "why_recorded": ("all three surfaces are snapshot-only with no history endpoint -- "
                         "an unrecorded transition is permanently lost (L1.46), and Bithumb "
                         "rail state is the independent barrier-height regressor that breaks "
                         "the KR-premium circularity (R0299)"),
    }
    if state_error:
        rep["state_error"] = state_error
    return rep


def fetch_all() -> tuple[dict[str, Snapshot | None], dict[str, str]]:
    """Every surface, failures RECORDED per venue (never silently absent)."""
    specs: tuple[tuple[str, str, Any], ...] = (
        ("upbit", "https://api.upbit.com/v1/market/all?isDetails=true", _norm_upbit),
        ("bithumb_markets", "https://api.bithumb.com/v1/market/all?isDetails=true",
         _norm_bithumb_markets),
        ("bithumb_assets", "https://api.bithumb.com/public/assetsstatus/ALL",
         _norm_bithumb_assets),
    )
    snaps: dict[str, Snapshot | None] = {}
    errors: dict[str, str] = {}
    for venue, url, norm in specs:
        doc, err = _get(url)
        snap = None if err else norm(doc)
        if err:
            errors[venue] = err
        elif snap is None:
            errors[venue] = "unrecognised payload shape -- treated as a failed fetch, NOT as " \
                            "an empty venue (diffing it would record every flag as cleared)"
        snaps[venue] = snap
    return snaps, errors


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    snaps, errors = fetch_all()
    rep = collect(_ROOT, snaps, errors)
    (_ROOT / _STATUS).write_text(json.dumps(rep, indent=2, ensure_ascii=False), "utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False) if args.json else
          f"kr_venue_flags (R0299): {rep['status']} -- {rep['n_transitions']} transition(s), "
          f"{rep['n_baselines']} baseline(s), {len(errors)} source error(s)")
    return 0                     # a dead venue is recorded, never a build failure


if __name__ == "__main__":
    sys.exit(main())
