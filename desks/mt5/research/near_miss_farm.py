#!/usr/bin/env python3
"""NEAR-MISS FARM -- paper-forward every near miss and every lane-less certificate, no authority.

WHY (principal 2026-10-13, idea 4: "paper-forward every near-miss cell 24/7 so untouched evidence
accumulates while the judge works")

`reports/FORWARD_CURE_ROSTER.json` holds every cell that cleared ALL FIVE validity gates and
missed only on power -- 1,240 of them on 2026-09-24, every one failing `deflated_sharpe`. Since
the power-cure lane was deleted from `shadow_admission` (principal 2026-09-24, "delete the
other") those cells gather no evidence at all: the honest relief valve the deletion named is
"MORE HISTORY", and the only history that does not exist yet is the history after the judge
looked. Each day un-farmed is a day of out-of-sample evidence the desk will never be able to
collect retroactively.

WHAT THIS IS, and every line below is a fence:

  * ONE ENGINE. Rows go through `shadow_forward.main(rows=..., ledger=...)`, the parameterised
    entry point that exists so no second forward evaluator is ever written: same bars, costs,
    side resolution, banned-family door, universe-policy door and clock-breach fence.
  * ITS OWN LEDGER, OUTSIDE EVERY CLOCK STORE. `reports/shadow/farm/near_miss_farm.json` -- a
    subdirectory and a name that no `*shadow_state.json` / `*_state.json` glob, no
    `retired_clocks.CLOCK_STORES` entry, and no promoter, enrolment census or allocator reads.
  * NO AUTHORITY. Every row is passed with `promotion_authority=False` and admission
    `NEAR_MISS_FARM`, a label `pipeline/promote.py` matches to no branch. A farm clock is not a
    certificate, is not counted as one, and joins no multiplicity cohort: this is exactly the
    distinction whose absence got the 2026-09-24 lane deleted (120 cure clocks reported as
    certificates). The farm adds evidence; the judge's bar, trial counts and verdicts are
    untouched.
  * ITS OWN WATERMARK. `shadow_forward.main` records `leg:enrol_clocks` progress; the farm
    records `leg:near_miss_farm` instead, so the certified lane's stall detector never reads a
    farm count.

AND EVERY CERTIFICATE WITHOUT A LANE CLOCK (principal 2026-10-13: "all certis must always be put
in forward lanes"). `admission_integrity` keeps a new certificate out of the promoting lanes until
an independent rebuild REPLICATES it; measured on the box that day, 127 certificates sat there
27.7h to 448h with no clock at all, 102 of them in families the replication lane has no written
rule for, so for them the wait had no end. Each such certificate is farmed here from the pass it
appears, admission `CERT_AWAITING_LANE`, with the same no-authority fences as a near miss. The
door is untouched: a certificate still enters a promoting lane only when it opens, and the farm
row drops out on the pass after it does (it is built from "certified and not in a lane").

WHAT IT PUBLISHES: `reports/NEAR_MISS_FARM.json` -- per cell the forward n, expectancy, drawdown
and days, and whether that forward record alone already meets the gate spec's
`forward_cure_thresholds`. That flag is EVIDENCE for the judge and the research loop (which
near-miss mechanisms hold up on data nobody fitted), never a promotion.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = BASE / "reports"
ROSTER = REPORTS / "FORWARD_CURE_ROSTER.json"
SNAPSHOT = REPORTS / "POWER_CURE_CANDIDATES.json"
FARM_SUBDIR = "farm"
LEDGER_NAME = "near_miss_farm.json"
LEDGER_REL = f"{FARM_SUBDIR}/{LEDGER_NAME}"
OUT = REPORTS / "NEAR_MISS_FARM.json"
ADMISSION = "NEAR_MISS_FARM"
#: A CERTIFICATE THE INTEGRITY DOOR HAS NOT LET INTO A LANE YET (principal 2026-10-13: "all certis
#: must always be put in forward lanes"). `admission_integrity` holds a new certificate's clock
#: shut until an independent rebuild REPLICATES it, and the promoter honours that only because
#: the door stands at clock creation. So the farm runs those certificates from the day they exist
#: -- evidence, no authority -- and the door still decides when one enters a promoting lane.
CERT_ADMISSION = "CERT_AWAITING_LANE"
UNMEASURED = "UNMEASURED"
#: The gate spec's cure thresholds, read from the spec; these literals are the fallback and are
#: byte-identical to policy/gate_spec.yaml today.
FALLBACK_CURE = {"min_trades": 50, "min_exp_r": 0.05, "max_dd_r": -25.0, "min_days_active": 14}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def cure_thresholds() -> dict[str, float]:
    try:
        import yaml
        spec = yaml.safe_load((BASE / "policy" / "gate_spec.yaml").read_text("utf-8"))
        found = _find(spec, "forward_cure_thresholds")
        if isinstance(found, dict) and all(k in found for k in FALLBACK_CURE):
            return {k: float(found[k]) for k in FALLBACK_CURE}
    except Exception:
        pass
    return {k: float(v) for k, v in FALLBACK_CURE.items()}


def _find(doc: Any, key: str) -> Any:
    if isinstance(doc, dict):
        if key in doc:
            return doc[key]
        for v in doc.values():
            hit = _find(v, key)
            if hit is not None:
                return hit
    return None


def roster_rows() -> tuple[dict[str, dict[str, Any]], str]:
    """The cumulative roster, else this sweep's snapshot, else nothing (and say which)."""
    doc = _read(ROSTER)
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if isinstance(rows, dict) and rows:
        return rows, "reports/FORWARD_CURE_ROSTER.json"
    snap = _read(SNAPSHOT)
    rows = snap.get("candidates") if isinstance(snap, dict) else None
    if isinstance(rows, dict) and rows:
        return rows, "reports/POWER_CURE_CANDIDATES.json (roster absent)"
    return {}, f"{UNMEASURED}: neither the cure roster nor the snapshot is on disk"


def farm_rows(roster: dict[str, dict[str, Any]]
              ) -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
    """Engine rows for every roster cell with a runnable spec; refusals named, never guessed."""
    from research import shadow_forward as sf
    rows: list[tuple[Any, ...]] = []
    refused: list[dict[str, Any]] = []
    for key, r in sorted(roster.items()):
        spec = r.get("shadow_spec") if isinstance(r, dict) else None
        if not isinstance(spec, dict) or not spec.get("symbol") or not spec.get("selector"):
            refused.append({"cell": key, "why": "no shadow_spec with a symbol and a selector"})
            continue
        fam = str(spec.get("family") or "session_range_breakout")
        params = dict(spec.get("params") or {})
        # THE SIDE LIVES IN PARAMS ON A JUDGE CELL. The gauntlet calls fn(bars, **params) when
        # `side` is a param, so a short cell is short there; the forward engine passes side as
        # its own argument, and a second `side` in params would raise. Moved, never dropped.
        if not spec.get("side") and "side" in params:
            raw = params.pop("side")
            spec = {**spec, "side": "SHORT" if str(raw).strip().upper() in ("-1", "SHORT")
                    else "LONG"}
        side = sf._runnable_side(spec, fam)
        if side is None:
            refused.append({"cell": key, "why": f"side {spec.get('side')!r} not runnable"})
            continue
        rows.append((str(spec["symbol"]), str(spec["selector"]), params, fam, side, ADMISSION,
                     tuple(r.get("failed_power_gates") or ()), False))
    return rows, refused


def clockless_cert_rows() -> tuple[list[tuple[Any, ...]], list[dict[str, Any]], str]:
    """Engine rows for every certificate with NO clock in any promoting lane, and why it has none.

    Built exactly as `shadow_forward.certified_sleeves` builds a lane row (window hours merged
    under the certificate's own params for a breakout, the certificate's params verbatim
    otherwise, the same side rule), so the farm replays the recipe that passed and the key it
    writes is the key the lane will use once the door opens.
    """
    from research import shadow_forward as sf
    from research.admission_integrity import lane_clock_keys
    from research.shadow_admission import authorized_runs
    try:
        runs = list(authorized_runs(BASE))
    except Exception as exc:
        return [], [], f"{UNMEASURED}: authorized_runs failed ({type(exc).__name__}: {exc})"
    clocked = lane_clock_keys(sf.SHADOW_DIR)
    rows: list[tuple[Any, ...]] = []
    refused: list[dict[str, Any]] = []
    for run in sorted(runs, key=lambda r: (str(r.get("symbol")), str(r.get("selector")))):
        if str(run.get("certificate") or "").startswith("scalp."):
            continue                        # scalp recipes run on their own lane's clock
        fam = str(run.get("family") or "")
        if fam == "session_range_breakout":
            if run.get("selector") not in sf.WINDOWS:
                refused.append({"cell": run.get("certificate"), "why": "no window mapping"})
                continue
            params = {**sf.WINDOWS[run["selector"]], **dict(run.get("params") or {})}
        else:
            params = dict(run.get("params") or {})
        side = sf._runnable_side(run, fam)
        if side is None:
            refused.append({"cell": run.get("certificate"), "why": "side not runnable"})
            continue
        key = sf.sleeve_key(run["symbol"], run["selector"], params, fam, side)
        if key in clocked:
            continue
        rows.append((str(run["symbol"]), str(run["selector"]), params, fam, side,
                     CERT_ADMISSION, tuple(run.get("power_deficiencies") or ()), False))
    return rows, refused, f"{len(runs)} certificates, {len(clocked)} lane clocks"


def _farm_watermark(enrolled: int, ledger: str) -> None:
    try:
        from libs.ops.control_plane import watermarks as wm
        wm.progress("leg:near_miss_farm", "forward_observations", enrolled, ledger=ledger)
    except Exception:
        pass


#: The engine's GLOBAL stores, and the module names each is reachable under. `shadow_forward`
#: imports `sleeve_registry` and `clock_ledger` both bare and as `research.*`, and a module
#: imported under two names is two module objects, so each is redirected under every name.
REGISTRY_MODULES = ("sleeve_registry", "research.sleeve_registry")
CLOCK_LEDGER_MODULES = ("clock_ledger", "research.clock_ledger")
FARM_REGISTRY = "sleeve_registry.json"
FARM_CLOCK_LEDGER = "forward_clock_ledger.json"


@contextlib.contextmanager
def farm_stores(farm_dir: Path) -> Iterator[None]:
    """Point EVERY store `shadow_forward.main` writes at `farm_dir` for one pass, then restore.

    AUDIT HOLD ON #487 (2026-10-29). Redirecting `SHADOW_DIR` alone left two global writers live:
    `clock_ledger.stamp` (its `path` default is bound when the module loads, and its rule is
    start = min(recorded, proposed)) and `sleeve_registry.freeze`, which creates every new row
    LIVE in the tracked registry. Measured: one farm pass on EURUSD H1 wrote a LIVE registry row
    and a clock for a near miss, and a later main-lane pass inherited the farm's `forward_start`
    with promotion authority -- in-sample bars counted as forward, from ~1,240 uncharged looks.
    The farm's registry and clock ledger are its own; a cell that later enters a promoting lane
    starts a FRESH clock there.
    """
    import importlib

    ledger_path = farm_dir / FARM_CLOCK_LEDGER
    saved: list[tuple[Any, str, Any]] = []
    for name in REGISTRY_MODULES:
        try:
            mod: Any = importlib.import_module(name)
        except Exception:
            continue
        if hasattr(mod, "REGISTRY"):
            saved.append((mod, "REGISTRY", mod.REGISTRY))
            mod.REGISTRY = farm_dir / FARM_REGISTRY
    for name in CLOCK_LEDGER_MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        real = mod.stamp

        def _farm_stamp(key: str, identity: str, proposed: Any, *, path: Path | None = None,
                        _real: Any = real, **kw: Any) -> Any:
            return _real(key, identity, proposed, path=ledger_path, **kw)

        saved.append((mod, "stamp", real))
        mod.stamp = _farm_stamp
        if hasattr(mod, "LEDGER"):
            saved.append((mod, "LEDGER", mod.LEDGER))
            mod.LEDGER = ledger_path
    try:
        yield
    finally:
        for mod, attr, value in reversed(saved):
            setattr(mod, attr, value)


def evaluate(rows: list[tuple[Any, ...]]) -> Path:
    """Run the one forward engine over the farm rows into the farm's own stores."""
    from research import shadow_forward as sf
    # THE ENGINE'S DIRECTORY IS THE FARM'S FOR THE RUN. `shadow_forward` writes per-trade ledgers
    # as `ledger_<sym>_<fam>_<win>.json` beside its state, keyed without params, so a farm row on
    # the same symbol, family and window as a certified clock would overwrite that clock's
    # ledger in `reports/shadow/`. Pointed at `reports/shadow/farm/`, both files stay apart, and
    # `farm_stores` does the same for the registry and the clock ledger.
    lane_dir = sf.SHADOW_DIR
    farm_dir = lane_dir / FARM_SUBDIR
    farm_dir.mkdir(parents=True, exist_ok=True)
    original = sf._enrolment_watermark
    sf._enrolment_watermark = _farm_watermark
    sf.SHADOW_DIR = farm_dir
    try:
        with farm_stores(farm_dir):
            sf.main(rows=rows, ledger=LEDGER_NAME)
    finally:
        sf.SHADOW_DIR = lane_dir
        sf._enrolment_watermark = original
    return farm_dir / LEDGER_NAME


def _row_key(row: tuple[Any, ...]) -> str:
    from research import shadow_forward as sf
    return str(sf.sleeve_key(row[0], row[1], row[2], row[3], row[4]))


def summarise(ledger: Path, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    """Per-cell forward record, and whether it alone meets the cure thresholds (evidence only)."""
    from research import shadow_forward as sf
    state = _read(ledger) or {}
    th = cure_thresholds()
    cells: list[dict[str, Any]] = []
    meets = with_trades = authority_leaks = 0
    for row in rows:
        key = sf.sleeve_key(row[0], row[1], row[2], row[3], row[4])
        st = state.get(key) if isinstance(state, dict) else None
        if not isinstance(st, dict):
            cells.append({"key": key, "status": UNMEASURED, "why": "not yet evaluated"})
            continue
        if st.get("promotion_authority"):
            authority_leaks += 1
        n = int(st.get("n") or 0)
        exp_r = st.get("exp_r")
        dd = float(st.get("max_dd_r") or 0.0)
        days = None
        try:
            first = datetime.fromisoformat(str(st.get("forward_start") or st.get("enrolled_at")))
            if first.tzinfo is None:
                first = first.replace(tzinfo=UTC)
            days = (datetime.now(tz=UTC) - first).days
        except ValueError:
            pass
        ok = (n >= th["min_trades"] and exp_r is not None and float(exp_r) > th["min_exp_r"]
              and dd > th["max_dd_r"] and days is not None and days >= th["min_days_active"])
        with_trades += n > 0
        meets += ok
        cells.append({"key": key, "symbol": row[0], "family": row[3], "side": row[4],
                      "admission": row[5],
                      "failed_power_gates": list(row[6]), "status": st.get("status"),
                      "n": n, "exp_r": exp_r, "max_dd_r": dd, "days": days,
                      "meets_forward_cure_thresholds": bool(ok)})
    cells.sort(key=lambda c: (-(c.get("n") or 0), str(c.get("key"))))
    by_admission: dict[str, int] = {}
    for row in rows:
        by_admission[str(row[5])] = by_admission.get(str(row[5]), 0) + 1
    return {"cells_farmed": len(rows), "cells_with_forward_trades": with_trades,
            "meeting_forward_cure_thresholds": meets, "thresholds": th,
            "by_admission": by_admission,
            "authority_leaks": authority_leaks, "cells": cells[:2000]}


def run(*, dry_run: bool = False, out: Path | None = None) -> dict[str, Any]:
    roster, source = roster_rows()
    rows, refused = farm_rows(roster)
    cert_rows, cert_refused, cert_source = clockless_cert_rows()
    # A certificate's row wins over a near-miss row with the same key: it is the stronger claim.
    cert_keys = {_row_key(r) for r in cert_rows}
    rows = cert_rows + [r for r in rows if _row_key(r) not in cert_keys]
    refused = cert_refused + refused
    doc: dict[str, Any] = {
        "generated_at": _now(), "producer": "desks/mt5/research/near_miss_farm.py",
        "source": source, "roster_rows": len(roster),
        "certificates_without_lane_clock": len(cert_rows), "certificate_source": cert_source,
        "refused": refused[:200],
        "n_refused": len(refused), "ledger": f"reports/shadow/{LEDGER_REL}",
        "authority": ("NONE. Every farm row is passed with promotion_authority=False and "
                      f"admission {ADMISSION}; the ledger is outside every clock store the "
                      "promoter, enrolment census or allocator reads. Evidence, never a "
                      "certificate."),
    }
    if rows and not dry_run:
        ledger = evaluate(rows)
        doc.update(summarise(ledger, rows))
    else:
        doc.update({"cells_farmed": len(rows),
                    "status": "DRY_RUN" if dry_run else f"{UNMEASURED}: no runnable rows"})
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(dry_run=args.dry_run, out=args.out)
    print(f"near_miss_farm: source={doc['source']} roster={doc['roster_rows']} "
          f"farmed={doc.get('cells_farmed')} with_trades={doc.get('cells_with_forward_trades')} "
          f"meets_cure={doc.get('meeting_forward_cure_thresholds')} "
          f"refused={doc['n_refused']} leaks={doc.get('authority_leaks')}")
    return 1 if doc.get("authority_leaks") else 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
