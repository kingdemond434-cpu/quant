"""EVICTED FOR MISSING PARAMS -> BACK ON THE DOCKET, FIRST, WITH THE PARAMS WRITTEN DOWN.

THE DEAD END THIS OPENS (2026-09-30). `certificate_hygiene` moves a certificate whose
`shadow_spec.params` was never recorded out of the canon into
`reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json`. That is correct -- nothing can replay it -- and its
own `why` says the only way back is "a FRESH pre-registered window, never by inheriting this row".
Nothing ever walked that way back. `requeue_unrunnable` reads the CANON, which no longer holds an
evicted row, and when it did hold one it queued `params: {}` -- the family defaults, a different
strategy from the one certified -- UNSTAMPED, which the sealed gauntlet's point-in-time ratchet
skips once any docket row is stamped. Six certificates gated 2026-08-23..25 (five
`session_range_breakout` asia cells and one hunt16 `dav_range_filter_adx` cell) sat in that file
with no route back to a judge.

WHAT THIS DOES. For every evicted row it writes ONE docket cell into
`data/hypotheses/external_survivors.json` (the only input the sealed gauntlet reads), at the FRONT
of the file, point-in-time stamped, carrying a COMPLETE executable parameterisation and the
provenance of every parameter:

  * session_range_breakout -- the certificate's own gate vector is matched against the
    parameterised certificates of the same symbol and family in the registry (report, canon and
    the eviction file). The evicted rows were minted by a sweep whose cell id dropped the
    parameters (`XAUUSD.session_range_breakout`) while its sibling rows kept them
    (`...rr=2.5_wb=12`); the same series produce the same `days`, Sharpe, CPCV, walk-forward,
    x3-cost and EV numbers. A unique nearest twin inside `FINGERPRINT_TOL` (and a runner-up at
    least `FINGERPRINT_MARGIN` times farther) supplies rr/wait_bars. The session hours come from
    the forward engine's own window for the certificate's selector (`shadow_forward.WINDOWS`), so
    the params are exactly what the forward clock would run. When no twin is unique, the window's
    own defaults are used and the row says so (`params_source: "window_default"`).
  * hunt16 cells -- the certificate's shadow_spec already names side, selector and condition;
    they become `families_orthogonal.hunt16_cell` params (base_family, direction, signal_at from
    the hunt16 window, day_state), the one family the sealed gauntlet can build a hunt16 cell with.

NEVER-JUDGED, AND WHY THE IDENTITY IS NEW. The params are COMPLETE (the window's hours are
written, not implied), so `frontier_identity.cell_id` gives a `p=<digest>` id that differs from
the legacy `rr=_wb=` twin's -- the sealed sort key's first term `_is_new` is 0 for it and it lands
in the never-judged tier, ahead of every re-judge. If the id IS already in
`gauntlet_seen_cells.json` that is reported per cell (`already_judged`), never hidden.

NO FREE TRIALS. The cell goes through the ordinary docket, so the sealed gauntlet counts it in
the program matrix, the deflated-Sharpe trial census and the gate ledger exactly like any other
cell. Nothing here carries an exemption, a threshold or a verdict.

NEVER REVIVES A CERTIFICATE. The evicted row stays evicted; only a new ten-gate pass on the
recorded params can put the mechanism back in the canon.

    python desks/mt5/research/rejudge_evicted.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVICTED = DESK / "reports" / "UNIVERSAL_SURVIVORS_UNRUNNABLE.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
SEEN_CELLS = DESK / "data" / "hypotheses" / "gauntlet_seen_cells.json"
#: The priority input: what was queued, with params and provenance -- read back by nobody but a
#: human or the next pass, and rewritten whole each pass (it is derived, never appended).
PRIORITY = DESK / "data" / "hypotheses" / "priority_rejudge.json"
OUT = DESK / "reports" / "REJUDGE_EVICTED.json"

SOURCE = "rejudge_evicted"
#: The gate statistics a certificate's fingerprint is read from, all reported to 4 dp.
FINGERPRINT_STATS = (("in_sample_screen", "sharpe"), ("cpcv", "mean_oos_sharpe"),
                     ("walk_forward", "oos_sharpe"), ("stress_costs", "exp_x3"),
                     ("expected_value", "ev"))
#: Largest |difference| on any stat for a twin. The twins were re-gated a few hours after the
#: bare rows on one more data-day, which moves the 3rd decimal at most (measured: 0.0012).
FINGERPRINT_TOL = 0.003
#: The runner-up must be at least this many times farther than the twin, or nothing is claimed.
FINGERPRINT_MARGIN = 2.0


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _survivors(doc: Any) -> dict[str, dict]:
    if isinstance(doc, dict) and isinstance(doc.get("survivors"), dict):
        return {str(k): v for k, v in doc["survivors"].items() if isinstance(v, dict)}
    return {}


def evicted_rows(evicted: Path | None = None, survivors: Path | None = None,
                 canon: Path | None = None) -> dict[str, dict]:
    """Every certificate evicted (or evictable) for an unrecorded parameterisation.

    The eviction file first; then any row of the report or canon that the shared judge
    (`survivor_publication.unrunnable_reason`) calls unrunnable, or that the canon lists under
    `unrunnable_evicted` -- so a host where hygiene has not yet run, or whose eviction file was
    lost, still finds them.
    """
    from survivor_publication import unrunnable_reason
    # Resolved at CALL time, never bound as defaults at import: a default argument would pin the
    # module's paths as they were when it was first imported.
    evicted, survivors, canon = evicted or EVICTED, survivors or SURVIVORS, canon or CANON
    out = dict(_survivors(_read(evicted)))
    canon_doc = _read(canon)
    listed = (set(canon_doc.get("unrunnable_evicted") or [])
              if isinstance(canon_doc, dict) else set())
    for doc in (_read(survivors), canon_doc):
        for key, row in _survivors(doc).items():
            if key in out:
                continue
            if key in listed or unrunnable_reason(row):
                out[key] = row
    return {k: v for k, v in out.items() if unrunnable_reason(v)}


def _fingerprint(row: dict) -> tuple[Any, list[float]] | None:
    gates = row.get("gates") or {}
    vals: list[float] = []
    for gate, stat in FINGERPRINT_STATS:
        v = (gates.get(gate) or {}).get(stat)
        if not isinstance(v, (int, float)):
            return None
        vals.append(float(v))
    return row.get("days"), vals


def match_twin(key: str, row: dict, registry: dict[str, dict]) -> dict[str, Any]:
    """The parameterised certificate this bare one IS, by gate fingerprint -- or why not."""
    spec = row.get("shadow_spec") or {}
    sym, fam = spec.get("symbol"), spec.get("family")
    fp = _fingerprint(row)
    if fp is None:
        return {"matched": False, "why": "the certificate carries no complete gate fingerprint"}
    scored: list[tuple[float, str, dict]] = []
    for k, r in registry.items():
        s = r.get("shadow_spec") or {}
        if k == key or s.get("symbol") != sym or s.get("family") != fam:
            continue
        if not isinstance(s.get("params"), dict) or not s["params"]:
            continue
        tfp = _fingerprint(r)
        if tfp is None or tfp[0] != fp[0]:
            continue                              # different `days` = different wait_bars/data
        dist = max(abs(a - b) for a, b in zip(fp[1], tfp[1], strict=True))
        scored.append((dist, k, dict(s["params"])))
    scored.sort(key=lambda t: (t[0], t[1]))
    if not scored:
        return {"matched": False, "why": f"no parameterised {sym}.{fam} certificate with "
                                         f"days={fp[0]} in the registry"}
    best = scored[0]
    runner = scored[1][0] if len(scored) > 1 else float("inf")
    if best[0] > FINGERPRINT_TOL:
        return {"matched": False, "why": f"nearest twin {best[1]} differs by {best[0]:.4f} "
                                         f"> {FINGERPRINT_TOL}"}
    if runner < FINGERPRINT_MARGIN * max(best[0], 1e-4):
        return {"matched": False, "why": f"ambiguous: {best[1]} at {best[0]:.4f}, runner-up "
                                         f"at {runner:.4f}"}
    return {"matched": True, "twin": best[1], "distance": round(best[0], 6),
            "runner_up_distance": None if runner == float("inf") else round(runner, 6),
            "params": best[2]}


def _windows() -> dict[str, dict]:
    from shadow_forward import WINDOWS
    return {str(k): dict(v) for k, v in WINDOWS.items()}


def _hunt16_windows() -> dict[str, dict]:
    from run_hunt16 import WINDOWS
    return {str(k): dict(v) for k, v in WINDOWS.items()}


def recover(key: str, row: dict, registry: dict[str, dict]) -> dict[str, Any]:
    """(family, params, provenance) for one evicted certificate, or a refusal with its reason."""
    spec = row.get("shadow_spec") or {}
    sym = str(spec.get("symbol") or row.get("sym") or "")
    fam = str(spec.get("family") or "")
    selector = str(spec.get("selector") or "")
    base = {"certificate_key": key, "symbol": sym, "evicted_family": fam,
            "gated_at": row.get("gated_at")}
    if not sym or not fam:
        return {**base, "ok": False, "why": "no symbol/family on the certificate"}
    try:
        from family_policy import family_banned
        if family_banned(fam):
            return {**base, "ok": False, "why": f"family {fam!r} is banned; never re-judged"}
    except ImportError:                                           # pragma: no cover - path only
        pass
    if fam == "session_range_breakout":
        windows = _windows()
        if selector not in windows:
            return {**base, "ok": False, "why": f"selector {selector!r} has no forward window"}
        params = dict(windows[selector])
        twin = match_twin(key, row, registry)
        if twin.get("matched"):
            tp = {k: v for k, v in twin["params"].items() if k in ("rr", "wait_bars")}
            params.update(tp)
            source = (f"rr/wait_bars from gate-fingerprint twin {twin['twin']} "
                      f"(max |d| {twin['distance']}); session hours and ttl from "
                      f"shadow_forward.WINDOWS[{selector!r}]")
            kind = "fingerprint"
        else:
            source = (f"shadow_forward.WINDOWS[{selector!r}] defaults -- the parameterisation "
                      f"that passed was NOT recovered ({twin.get('why')})")
            kind = "window_default"
        return {**base, "ok": True, "family": fam, "params": params,
                "params_source": kind, "provenance": source, "twin": twin}
    try:
        from mt5desk.executables import hunt16_families
        is_h16 = fam in hunt16_families()
    except Exception:
        is_h16 = False
    if is_h16:
        h16w = _hunt16_windows()
        if selector not in h16w:
            return {**base, "ok": False, "why": f"hunt16 selector {selector!r} is not a window"}
        w = h16w[selector]
        cond = spec.get("condition")
        params = {"base_family": fam,
                  "direction": str(spec.get("side") or "LONG").upper(),
                  "signal_at": int(w.get("signal_at") or w["range_start"]),
                  "day_state": (str(cond).upper() if cond else None)}
        return {**base, "ok": True, "family": "hunt16_cell", "params": params,
                "params_source": "certificate_spec",
                "provenance": (f"side/selector/condition from the certificate's own shadow_spec; "
                               f"signal hour from run_hunt16.WINDOWS[{selector!r}]; the family "
                               f"takes no other parameter (run_hunt16.{fam}(h1, side))")}
    return {**base, "ok": False,
            "why": f"no recovery rule for family {fam!r}; it is reported, never guessed"}


def _cell_id(sym: str, fam: str, params: dict) -> str:
    from frontier_identity import cell_id
    return str(cell_id({"sym": sym, "family": fam, "params": params}))


def _identity(row: dict) -> str:
    """merge_hypotheses._identity, restated: (symbol, family, sorted params)."""
    params = row.get("params") or {}
    return json.dumps({"symbol": str(row.get("symbol") or row.get("sym") or ""),
                       "family": str(row.get("family") or ""),
                       "params": {k: params[k] for k in sorted(params)}},
                      sort_keys=True, default=str)


def docket_row(rec: dict[str, Any], now: datetime) -> dict[str, Any]:
    from libs.data.pit import stamp
    body = {
        "symbol": rec["symbol"], "family": rec["family"], "params": dict(rec["params"]),
        "source": SOURCE, "producer": SOURCE,
        "priority": "REJUDGE_EVICTED",
        "judging_status": "NEVER_JUDGED",
        "certificate_key": rec["certificate_key"],
        "evicted_family": rec["evicted_family"],
        "params_source": rec["params_source"],
        "params_provenance": rec["provenance"],
        "mechanism_status": "NAMED",
        "mechanism_note": (f"re-judge of certificate {rec['certificate_key']} (gated "
                           f"{rec.get('gated_at')}), evicted for unrecorded params"),
        "requeued_utc": now.isoformat(timespec="seconds"),
        "first_seen": now.isoformat(timespec="seconds"),
    }
    return stamp(body, SOURCE, now=now)


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows = evicted_rows()
    registry: dict[str, dict] = {}
    for doc in (_read(SURVIVORS), _read(CANON), _read(EVICTED)):
        registry.update(_survivors(doc))
    seen = _read(SEEN_CELLS)
    seen = seen if isinstance(seen, dict) else None
    cells: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for key in sorted(rows):
        rec = recover(key, rows[key], registry)
        if not rec.get("ok"):
            refused.append(rec)
            continue
        cid = _cell_id(rec["symbol"], rec["family"], rec["params"])
        rec["cell_id"] = cid
        rec["already_judged"] = (None if seen is None else cid in seen)
        cells.append(rec)
    return {"at": now.isoformat(timespec="seconds"), "evicted": len(rows),
            "cells": cells, "refused": refused,
            "seen_cells": "UNMEASURED (no gauntlet_seen_cells.json on this host)"
            if seen is None else f"{len(seen)} known",
            "rule": ("each evicted certificate re-enters the ONE docket the sealed gauntlet reads, "
                     "first, stamped, with complete params and their provenance; charged to the "
                     "trial census like every cell; the evicted row itself is never revived")}


def apply(doc: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Put the recovered cells at the FRONT of the docket. Idempotent by executable identity."""
    now = now or datetime.now(tz=UTC)
    fresh = [docket_row(c, now) for c in doc.get("cells") or []]
    PRIORITY.parent.mkdir(parents=True, exist_ok=True)
    PRIORITY.write_text(json.dumps({"at": doc["at"], "rows": fresh}, indent=1, default=str),
                        encoding="utf-8")
    if not fresh:
        return {"queued": 0, "already_on_docket": 0}
    docket = _read(DOCKET)
    existing = [r for r in docket if isinstance(r, dict)] if isinstance(docket, list) else []
    want = {_identity(r) for r in fresh}
    present = {_identity(r) for r in existing} & want
    # THE DOCKET IS REWRITTEN ONLY WHEN A CELL IS MISSING FROM IT. It is the judge's whole input
    # (hundreds of thousands of rows on the box) and `merge_hypotheses` re-orders it every hour,
    # so re-inserting at the front on every pass would buy nothing: the sealed sort already puts
    # a never-judged cell in its first tier wherever it sits in the file. What must hold is that
    # the cell IS on the docket, stamped, with its params -- and the first write puts it first,
    # where the gauntlet's first-row-wins de-duplication keeps this copy over any other.
    if present == want:
        return {"queued": 0, "already_on_docket": len(present), "front_block": 0,
                "docket": str(DOCKET.relative_to(ROOT))}
    rest = [r for r in existing if _identity(r) not in want]
    DOCKET.parent.mkdir(parents=True, exist_ok=True)
    DOCKET.write_text(json.dumps(fresh + rest, indent=1, default=str), encoding="utf-8")
    return {"queued": len(want - present), "already_on_docket": len(present),
            "front_block": len(fresh), "docket": str(DOCKET.relative_to(ROOT))}


def run(apply_changes: bool, now: datetime | None = None) -> dict[str, Any]:
    doc = build(now)
    if apply_changes:
        doc["applied"] = apply(doc, now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the cells to the docket front")
    a = ap.parse_args(argv)
    doc = run(a.apply)
    print(f"rejudge evicted: {doc['evicted']} evicted, {len(doc['cells'])} re-queueable, "
          f"{len(doc['refused'])} refused")
    for c in doc["cells"]:
        print(f"  {c['symbol']:<8} {c['family']:<22} {c['params_source']:<15} {c['params']}")
    for r in doc["refused"]:
        print(f"  REFUSED {r.get('certificate_key')}: {r.get('why')}")
    if a.apply:
        print(f"  applied: {doc['applied']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
