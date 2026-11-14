#!/usr/bin/env python3
"""RE-JUDGE ON A COST-BASIS CHANGE: when a symbol's registry cost basis moves, the cells whose
verdict was decided by it are judged again first (2026-10-21).

WHY. The judge's cell cache is keyed by symbol, family, params, the chart's data-day and the replay
code (`external_gauntlet._cache_key`). The registry's cost fields are NOT in that key, and a cell
already judged is re-judged only when its rotation comes round. So when a symbol's cost basis
changes (a spread re-measured, an observed zero stamped by the tape), the verdicts it decided
stand until rotation reaches them. Two sets are decided by the basis directly:

  * cells whose last verdict FAILED AT `swap_cost`, the gate that reads the registry basis. It is
    the last gate in the order (`CELL_LOCAL_TAIL`), so these cells passed every other gate and
    were refused on the basis alone. The 14 zero-spread majors were refused here as UNMEASURED;
  * cells whose last verdict PASSED: a certificate priced on the old basis is re-minted on the
    new one.

WHAT THIS DOES. Once an hour it reads every symbol's basis, meaning the six `COST_BASIS_FIELDS`,
whether a zero carries the tape's observed-zero stamp, and the sealed `registry_cost_basis`'s own
verdict on the row (so a re-signed rule that reads the same numbers differently is a change too: a
zero stamped before the v2 gate is signed is re-judged again once it is). It compares each
fingerprint with the last reading, finds those cells on any symbol that changed (from the judge's
own `gate_verdict_index.json`), and lists them in the judge's re-mint queue,
`data/hypotheses/priority_remint.json`. The sealed judge already reads that queue. `attestation_remint` writes it
too; each producer keeps the other's cells under the same attestation. Those cells are judged FIRST, are not set aside as twins of themselves, and
are not trimmed by the yield allocation. Every re-judge is an ordinary docket cell, counted in the
trial census and the gate ledger, and `tier_s` dedups the repeat.

NOT BEFORE THE CACHE CAN SERVE THE NEW COST. When a cost NUMBER moved, a cell re-judged on the same
data-day reads its cached series, which was built at the OLD cost. So that cell is HELD until its
own chart's last data-day is later than it was when the change was seen: that is when the cell's
cache key rolls and the series is rebuilt at the new cost. A re-judge before then would spend a
sweep slot on a verdict it already has. A change in how the basis is READ (a stamp, the gate's
verdict) moves no number in the series and swap_cost reads the registry at judge time, so those
cells are released at once. A released cell stays in the queue for HOLD_DATA_DAYS of its chart's
data-days, which outlasts a plan made just before release (the judge resumes a plan for up to 24
h), and then leaves the queue.

REPORT AND QUEUE ONLY. It writes no verdict, retires nothing, charges no trial and puts no
certificate in `stale_certificate_keys`; whether a certificate stands is still the judge's
decision, made on the re-judge. An unreadable registry, index or attestation is UNMEASURED and
writes no queue.

    python desks/mt5/research/cost_basis_rejudge.py --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
REGISTRY = UNI / "universe.json"
GATE_INDEX = DESK / "data" / "hypotheses" / "gate_verdict_index.json"
PRIORITY_REMINT = DESK / "data" / "hypotheses" / "priority_remint.json"
STATE = DESK / "data" / "cost_basis_state.json"
REPORT = DESK / "reports" / "COST_BASIS_REJUDGE.json"
PRODUCER = "desks/mt5/research/cost_basis_rejudge.py"

#: The registry fields the sealed swap_cost gate reads (`external_gauntlet.COST_BASIS_FIELDS`),
#: mirrored; `desks/mt5/tests/test_observed_zero_stamp_and_rejudge.py` and
#: `desks/mt5/tests/test_promoter_observed_zero_basis.py` fail if the two ever differ.
COST_BASIS_FIELDS = (
    "median_spread_pts",
    "tick_size",
    "tick_value",
    "contract_size",
    "swap_long",
    "swap_short",
)
#: The verdict-index keys (`<terminal_gate>|<passed>`) a basis change can decide directly.
DECIDED_BY_BASIS = ("swap_cost|0",)
#: How many of a cell's own chart data-days a released cell stays queued. One is not enough: the
#: judge resumes a plan for up to 24 h, so a plan cut just before release could miss the cell.
HOLD_DATA_DAYS = 2
ZERO_SOURCE = "fusion_zero_m1_tape"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def zero_stamped(row: dict[str, Any]) -> bool:
    """The registry zero carries the tape's observed-zero stamp (the only zero the gate takes)."""
    prov = row.get("_provenance")
    entry = prov.get("median_spread_pts") if isinstance(prov, dict) else None
    return bool(
        isinstance(entry, dict)
        and entry.get("source") == ZERO_SOURCE
        and entry.get("zero_spread") is True
    )


#: What the gate's own reading of a basis adds to the registry's fields: the verdict
#: `registry_cost_basis` gives it. A change here with no change in a cost NUMBER is a change in
#: how the basis is READ (a stamp, or a re-signed rule), so the cached series is still right.
GATE_KEYS = ("gate_measured", "gate_zero_spread")


def basis_changes(was: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """The fields on which two readings of one symbol's basis differ.

    A registry field or the zero stamp counts whenever it differs. A GATE key counts only when
    BOTH readings carry it (v2.1 audit should-fix): a reading taken while the sealed judge could
    not be imported has no gate keys, and the first gated reading after it must not mark every
    symbol in the registry changed for a verdict nobody saw move."""
    fields = {k for k in set(was) | set(now) if k not in GATE_KEYS and was.get(k) != now.get(k)}
    fields |= {k for k in GATE_KEYS if k in was and k in now and was[k] != now[k]}
    return sorted(fields)


def load_gate() -> Any:
    """The sealed judge's own `registry_cost_basis`, or None when it cannot be imported."""
    try:
        from scripts import external_gauntlet as eg
    except Exception:
        return None
    return getattr(eg, "registry_cost_basis", None)


def basis_of(row: Any, view: dict[str, Any] | None = None) -> dict[str, Any]:
    """The inputs the sealed gate prices a symbol's basis from, plus the gate's own verdict on
    them when it was read (`view`), as one comparable map."""
    if not isinstance(row, dict):
        return {"row": None}
    out: dict[str, Any] = {f: row.get(f) for f in COST_BASIS_FIELDS}
    out["zero_stamp"] = zero_stamped(row)
    if view is not None:
        out["gate_measured"] = bool(view.get("measured"))
        out["gate_zero_spread"] = bool(view.get("zero_spread"))
    return out


def fingerprint(basis: dict[str, Any]) -> str:
    blob = json.dumps(basis, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def sym_tf_of(cell: str) -> tuple[str, str]:
    """`<SYM>[@TF].<family>.<params>` -> (SYM, TF); `frontier_identity.cell_id`'s own shape."""
    head = str(cell).split(".", 1)[0]
    sym, _, tf = head.partition("@")
    return sym, (tf or "H1").upper()


def chart_last_day(sym: str, tf: str, universe: Path | None = None) -> str | None:
    """The last bar's day of `<sym>_<tf>.parquet`, read from the index column alone (the day
    the judge keys the cell's cache to), or None when it cannot be read."""
    pq_path = (universe or UNI) / f"{sym}_{tf}.parquet"
    if not pq_path.exists():
        return None
    try:
        import pandas as pd
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(pq_path)
        cols = (pf.schema_arrow.pandas_metadata or {}).get("index_columns") or []
        if len(cols) != 1 or not isinstance(cols[0], str):
            return None
        idx = pd.DatetimeIndex(pf.read(columns=[cols[0]]).column(0).to_pandas())
    except Exception:
        return None
    if len(idx) == 0:
        return None
    return str(idx.max().normalize().date())


def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def run(
    *,
    write: bool = True,
    now: datetime | None = None,
    universe: Path | None = None,
    gate: Any = "load",
) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    reg = _read_json(REGISTRY if universe is None else universe / "universe.json")
    rows = reg.get("symbols") if isinstance(reg, dict) and "symbols" in reg else reg
    if not isinstance(rows, dict):
        return {"status": "UNMEASURED", "at": at, "why": "registry unreadable or not a map"}
    state = _read_json(STATE)
    state = state if isinstance(state, dict) else {}
    prev_basis = state.get("basis") if isinstance(state.get("basis"), dict) else {}
    # THE BASIS AS THE GATE READS IT: the sealed `registry_cost_basis` over the same rows, so a
    # stamp the gate now accepts -- or a re-signed rule that reads the same numbers differently --
    # is a change, exactly as a moved number is. Unreadable here: the last reading of the gate's
    # verdict is carried, so an import failure never reads as every symbol changing at once.
    fn = load_gate() if gate == "load" else gate
    basis: dict[str, dict[str, Any]] = {}
    for s, r in rows.items():
        view = None
        if fn is not None:
            try:
                view = fn(str(s), rows)
            except Exception:
                view = None
        b = basis_of(r, view if isinstance(view, dict) else None)
        if "gate_measured" not in b and isinstance(prev_basis.get(s), dict):
            b.update({k: prev_basis[s][k] for k in GATE_KEYS if k in prev_basis[s]})
        basis[str(s)] = b
    current = {s: fingerprint(b) for s, b in basis.items()}
    prev = state.get("fingerprints") if isinstance(state.get("fingerprints"), dict) else None
    pending_syms: dict[str, Any] = dict(state.get("pending_symbols") or {})
    queue: dict[str, Any] = dict(state.get("cells") or {})
    report: dict[str, Any] = {
        "status": "MEASURED",
        "at": at,
        "producer": PRODUCER,
        "n_symbols": len(current),
        "gate_view": (
            "the sealed registry_cost_basis"
            if fn is not None
            else "UNMEASURED: the judge's registry_cost_basis could not be imported; the last "
            "reading of its verdict is carried"
        ),
    }
    if prev is None:
        report.update(
            verdict="BASELINE",
            changed=[],
            why=(
                "first reading: every symbol's basis is recorded, and nothing can have changed "
                "against a reading that does not exist"
            ),
        )
    else:
        moved: dict[str, list[str]] = {}
        for s, fp in current.items():
            if s not in prev or prev[s] == fp:
                continue
            was = prev_basis.get(s)
            # No recorded basis to compare field by field: the fingerprint is the reading.
            fields = basis_changes(was, basis[s]) if isinstance(was, dict) else sorted(basis[s])
            if fields:
                moved[s] = fields
        changed = sorted(moved)
        report["changed"] = changed
        for s in changed:
            fields = moved[s]
            pending_syms[s] = {
                "changed_at": at,
                "fields": fields,
                # ONLY A MOVED COST NUMBER WAITS FOR THE CACHE: the cached series was built at
                # the old number. A stamp or a rule change reads the same series differently,
                # and swap_cost reads the registry at judge time, so it is released at once.
                "hold": any(f in COST_BASIS_FIELDS for f in fields),
            }
    # Resolve pending symbols into cells from the judge's own verdict index.
    index = _read_json(GATE_INDEX)
    if pending_syms and not isinstance(index, dict):
        report["index"] = (
            f"UNMEASURED: {GATE_INDEX.name} unreadable; "
            f"{len(pending_syms)} changed symbol(s) wait for it"
        )
    elif pending_syms and isinstance(index, dict):
        for cell, key in index.items():
            sym, tf = sym_tf_of(cell)
            if sym not in pending_syms:
                continue
            k = str(key)
            if k in DECIDED_BY_BASIS or k.endswith("|1"):
                # queued again on a second change: the hold restarts, the cache rolls again
                queue[cell] = {
                    "sym": sym,
                    "tf": tf,
                    "verdict_key": k,
                    "changed_at": pending_syms[sym]["changed_at"],
                    "fields": pending_syms[sym]["fields"],
                    "last_day_at_change": chart_last_day(sym, tf, universe),
                    "released_on": None,
                    "hold": bool(pending_syms[sym].get("hold", True)),
                }
        report["resolved_symbols"] = sorted(pending_syms)
        pending_syms = {}
    # Release a held cell once its chart's data-day has rolled; drop it HOLD_DATA_DAYS later.
    held, released, dropped, unreadable = [], [], [], []
    for cell, q in sorted(queue.items()):
        day = chart_last_day(q["sym"], q["tf"], universe)
        if day is None:
            unreadable.append(cell)
            continue
        if q.get("last_day_at_change") is None:
            q["last_day_at_change"] = day  # the chart came back: the hold starts now
        if q.get("released_on") is None:
            if not q.get("hold", True) or _days_between(q["last_day_at_change"], day) >= 1:
                q["released_on"] = day
            else:
                held.append(cell)
                continue
        if _days_between(q["released_on"], day) >= HOLD_DATA_DAYS:
            dropped.append(cell)
        else:
            released.append(cell)
    for cell in dropped:
        queue.pop(cell, None)
    report.update(
        {
            "n_queued": len(queue),
            "n_held_for_the_cache": len(held),
            "n_released": len(released),
            "n_dropped_after_hold": len(dropped),
            "n_chart_unreadable": len(unreadable),
            "released": released[:200],
            "held": held[:200],
            "chart_unreadable": unreadable[:200],
            "by_symbol": _by_symbol(queue),
        }
    )
    # The judge's re-mint queue: released cells, merged with any other producer's.
    att: Any = None
    try:
        from research.gate_policy import ATTESTATION as _att

        att = _att
    except ImportError as exc:
        report["queue"] = f"UNMEASURED: gate_policy.ATTESTATION unimportable ({exc}); not written"
    if write and att is not None:
        old = _read_json(PRIORITY_REMINT)
        old = old if isinstance(old, dict) else {}
        mine_before = set(old.get("cost_basis_cells") or [])
        others = (
            [c for c in (old.get("cells") or []) if c not in mine_before]
            if old.get("attestation") == att
            else []
        )
        stale = (
            list(old.get("stale_certificate_keys") or []) if old.get("attestation") == att else []
        )
        doc = {
            "attestation": att,
            "cells": sorted(set(others) | set(released)),
            "stale_certificate_keys": stale,
            "cost_basis_cells": sorted(released),
            "cost_basis_producer": PRODUCER,
            "cost_basis_at": at,
        }
        if doc["cells"] or old:
            _write_json(PRIORITY_REMINT, doc)
        report["queue"] = (
            f"{len(released)} cost-basis cell(s) in {PRIORITY_REMINT.name}, "
            f"{len(others)} from other producers kept"
        )
    if write:
        _write_json(
            STATE,
            {
                "fingerprints": current,
                "basis": basis,
                "pending_symbols": pending_syms,
                "cells": queue,
                "at": at,
            },
        )
        _write_json(REPORT, report)
    return report


def _by_symbol(queue: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for q in queue.values():
        out[q["sym"]] = out.get(q["sym"], 0) + 1
    return dict(sorted(out.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = run(write=not a.no_write)
    if a.json:
        print(json.dumps(r, indent=1, default=str))
    else:
        print(
            f"cost-basis re-judge: {r.get('status')} changed={len(r.get('changed') or [])} "
            f"queued={r.get('n_queued')} released={r.get('n_released')} "
            f"held={r.get('n_held_for_the_cache')} {r.get('queue') or r.get('why') or ''}"
        )
    return 0 if r.get("status") == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
