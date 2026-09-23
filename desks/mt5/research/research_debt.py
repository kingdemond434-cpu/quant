"""RESEARCH DEBT -- for every mechanism the desk has tested, what it has NOT tested and owes.

THE ASYMMETRY THIS MEASURES. A mechanism reaches this desk once, gets tested on the instrument and
the chart and the session it happened to arrive on, and is thereafter treated as SETTLED. It is
not settled. `session_handover` judged on XAUUSD x H1 x asia is one point of a space the same
economics licenses: every hypothesis-lane asset class, three charts, three session windows, four
conditioning regimes, the residual expression, the four execution expressions. One cell tested out
of a couple of thousand defensible ones, and the other cells are not "future work" -- they are the
cells with the highest information gain the desk owns, because nobody has spent a trial on them.

"WE ALREADY LOOKED AT THAT" IS A CLAIM REQUIRING EVIDENCE (L1.51, and the sealed core's
seat-exhaustion clause). This file is the evidence, per axis, per mechanism: what was measured,
what was not, and how many cells sit between them. It is a number that can only be argued with by
running the cells.

TWO SECTIONS, TWO DIFFERENT DEBTS.

  MECHANISMS        the untested extensions of every mechanism that has any tested cell. Closure
                    is the SAME logic the compiler uses -- `transformation_miners.compatible`, so
                    a session mechanism's debt never contains D1 and a month-end flow claim's
                    debt never contains a cross with neither leg. A debt computed over the
                    cartesian product would be a bigger number and a worse one: it would hide the
                    defensible cells inside noise nobody could act on.
  CONVERSION_DEBT   the registry's own ledger (`registry.conversion_debt`): cells owed by every
                    DISCOVERY, whether or not its mechanism was ever tested. Its
                    `unexplained_missing_cells` is the number that must go to zero -- not because
                    every cell must be tested today, but because every cell must have a
                    disposition today.

UNMEASURED IS A VERDICT HERE TOO. A mechanism with zero tested cells is NOT listed with a debt of
its closure size: it appears in `untested_mechanisms`, because "never tested" and "tested and
found wanting on 2,159 untried cells" are different states and rendering them identically is how
an unmined mechanism disappears into an average.

    python desks/mt5/research/research_debt.py
    python desks/mt5/research/research_debt.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import transformation_miners as TM  # noqa: E402

OUT = BASE / "reports" / "RESEARCH_DEBT.json"

#: A candidate has been TESTED when a judge has spoken about it. `queued` and `claimed` have not
#: been judged; counting them would let a full queue read as a covered axis, which is the
#: denominator trick the laws forbid.
TESTED_STATUSES: frozenset[str] = frozenset({"judged", "survived", "tested", "rejected",
                                             "certified", "promoted", "live"})
#: The axes a mechanism's debt is counted over. `symbol` is deliberately NOT one: instrument
#: breadth inside a class is the asset-transfer miner's job and counting it here would make every
#: debt a function of how many exotics the broker listed this month.
DEBT_AXES: tuple[str, ...] = ("asset_class", "chart", "session", "regime", "execution",
                              "expression")
MAX_TOP_UNTESTED = 12
MAX_MECHANISMS = 60

RULE = ("a mechanism tested on one coordinate is not a mechanism that has been searched; the debt "
        "is every economically compatible coordinate the same contract licenses and no trial has "
        "reached, and 'we already looked' is a claim requiring evidence")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(body, encoding="utf-8")


def _norm(value: Any, default: str = "") -> str:
    out = " ".join(str(value or "").strip().lower().replace("_", " ").split())
    return out or default


def mechanism_of(row: Mapping[str, Any]) -> str:
    """The canonical mechanism id for a candidate row, recovering the historic ones.

    Rows this compiler wrote carry the id already. Rows every other organ wrote carry PROSE in
    `mechanism`, and dropping them would make the debt a statement about this organ's own output
    rather than about the desk -- so the prose goes through the same interpreter the compiler
    uses and lands on a contract or on UNKNOWN, counted either way.
    """
    raw = str(row.get("mechanism") or "")
    key = raw.strip().lower()
    if key in TM.CONTRACTS:
        return key
    try:
        from research.discovery_compiler import interpret
    except Exception:
        return TM.UNKNOWN_MECHANISM
    return interpret(raw, "")[0]


def _coordinate(row: Mapping[str, Any]) -> dict[str, str]:
    params = row.get("params_json")
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    params = params if isinstance(params, dict) else {}
    return {
        "asset_class": _norm(row.get("asset_class"), "unknown"),
        "chart": str(row.get("chart") or "").upper() or "UNKNOWN",
        "session": _norm(row.get("session"), "all"),
        "regime": _norm(row.get("regime"), "unconditional") or "unconditional",
        "execution": f"{params.get('entry_timing') or 'instant'}/"
                     f"{params.get('execution_style') or 'market'}",
        "expression": ("residual" if params.get("residual_tag") == "residual"
                       else "inverse" if str(params.get("side_mode") or "") == "revert"
                       else "base"),
    }


def admissible(mechanism_id: str, classes: Iterable[str]) -> dict[str, list[str]]:
    """Every axis value the mechanism's CONTRACT licenses. The closure, per axis.

    An unknown mechanism gets the conservative closure (every chart the desk keeps bars for, the
    unconditional session, no regime claim) rather than the widest one: guessing wide would put
    debt on cells nobody could defend, and the debt's whole value is that each of its cells is
    defensible out loud.
    """
    contract = TM.CONTRACTS.get(mechanism_id)
    klasses = sorted({_norm(c) for c in classes if c and "equit" not in _norm(c)
                      and "share" not in _norm(c)})
    if contract is None:
        return {"asset_class": klasses or ["unknown"], "chart": list(TM.CHART_LADDER),
                "session": ["all"], "regime": ["unconditional"],
                "execution": [f"{t}/{s}" for t, s in TM.EXECUTION_VARIANTS],
                "expression": ["base"]}
    if contract.asset_classes != ("*",):
        klasses = [c for c in klasses if c in contract.asset_classes] or \
                  [_norm(c) for c in contract.asset_classes]
    expression = ["base"]
    if contract.residualisable:
        expression.append("residual")
    if contract.symmetric:
        expression.append("inverse")
    return {"asset_class": klasses or ["unknown"], "chart": list(contract.charts),
            "session": list(contract.sessions), "regime": ["unconditional", *contract.regimes],
            "execution": [f"{t}/{s}" for t, s in TM.EXECUTION_VARIANTS],
            "expression": expression}


def plausible_cells(mechanism_id: str, axes: Mapping[str, list[str]]) -> list[dict[str, str]]:
    """The mechanism's compatible closure, enumerated. (chart, session) pairs the window forbids
    are dropped HERE, which is why a session mechanism's debt never contains a D1 cell."""
    contract = TM.CONTRACTS.get(mechanism_id)
    out: list[dict[str, str]] = []
    for klass in axes["asset_class"]:
        for chart in axes["chart"]:
            for session in axes["session"]:
                ok, _why = TM.compatible(contract, chart=chart, session=session,
                                         asset_class=klass)
                if not ok:
                    continue
                for regime in axes["regime"]:
                    if regime != "unconditional":
                        ok2, _w2 = TM.compatible(contract, chart=chart, session=session,
                                                 regime=regime, asset_class=klass)
                        if not ok2:
                            continue
                    for execution in axes["execution"]:
                        for expression in axes["expression"]:
                            out.append({"asset_class": klass, "chart": chart, "session": session,
                                        "regime": regime, "execution": execution,
                                        "expression": expression})
    return out


def _key(cell: Mapping[str, str]) -> str:
    return "|".join(str(cell.get(a, "")) for a in DEBT_AXES)


def tested_rows(conn: Any = None, limit: int = 20000) -> list[dict[str, Any]]:
    rows = R.candidates(limit=limit, conn=conn)
    return [r for r in rows if str(r.get("status") or "").lower() in TESTED_STATUSES
            or r.get("judged_at") or r.get("terminal_gate")]


def build(*, classes: Iterable[str] | None = None, conn: Any = None,
          limit: int = MAX_MECHANISMS) -> dict[str, Any]:
    """The whole ledger: per-mechanism debt, the conversion debt, and the named gaps."""
    close = conn is None
    c = conn if conn is not None else R.connect()
    try:
        if classes is None:
            try:
                import axis_registry as ar
                classes = list(ar.instruments_by_class())
            except Exception:
                classes = []
        classes = list(classes)
        rows = tested_rows(conn=c)
        by_mech: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            by_mech.setdefault(mechanism_of(row), []).append(_coordinate(row))

        mechanisms: list[dict[str, Any]] = []
        total = 0
        for mid in sorted(by_mech, key=lambda m: (-len(by_mech[m]), m))[:limit]:
            coords = by_mech[mid]
            axes = admissible(mid, classes)
            plausible = plausible_cells(mid, axes)
            seen = {_key(x) for x in coords}
            untested = [x for x in plausible if _key(x) not in seen]
            tested_axes = {a: sorted({x.get(a, "") for x in coords if x.get(a)})
                           for a in DEBT_AXES}
            unmeasured_axes = {a: sorted(set(axes[a]) - set(tested_axes.get(a) or []))
                               for a in DEBT_AXES}
            total += len(untested)
            mechanisms.append({
                "mechanism_id": mid, "tested_cells": len(coords),
                "plausible_cells": len(plausible), "debt_cells": len(untested),
                "coverage": None if not plausible else round(
                    1.0 - len(untested) / len(plausible), 4),
                "tested": tested_axes, "unmeasured": unmeasured_axes,
                "top_untested": untested[:MAX_TOP_UNTESTED],
                "contract": (None if mid not in TM.CONTRACTS else
                             {"actor": TM.CONTRACTS[mid].actor,
                              "rationale": TM.CONTRACTS[mid].rationale,
                              "falsifier": TM.CONTRACTS[mid].falsifier}),
            })

        never = sorted(set(TM.CONTRACTS) - set(by_mech))
        debt = R.conversion_debt(conn=c)
        unmeasured: list[dict[str, str]] = []
        if not rows:
            unmeasured.append({
                "what": "tested cells", "why": "the registry holds no candidate a judge has "
                                               "spoken about, so mechanism-level debt is "
                                               "UNMEASURED rather than zero"})
        if not classes:
            unmeasured.append({
                "what": "asset classes", "why": "the instrument registry did not resolve on this "
                                                "host; the asset-class axis of every debt is a "
                                                "placeholder and the totals understate"})
        return {
            "at": _now(), "n_mechanisms": len(mechanisms), "mechanisms": mechanisms,
            "total_debt": total,
            "untested_mechanisms": [
                {"mechanism_id": m, "plausible_cells": len(plausible_cells(m,
                                                                          admissible(m, classes))),
                 "why": "no cell of this mechanism has ever been judged; it is UNMEASURED, which "
                        "is a different state from a mechanism with a measured debt"}
                for m in never],
            "conversion_debt": debt, "unmeasured": unmeasured, "rule": RULE,
        }
    finally:
        if close:
            c.close()


def summary_lines(report: Mapping[str, Any]) -> list[str]:
    lines = [f"research debt {report.get('total_debt')} cell(s) over "
             f"{report.get('n_mechanisms')} tested mechanism(s)"]
    for m in (report.get("mechanisms") or [])[:12]:
        cov = m.get("coverage")
        lines.append(f"  {m['mechanism_id']:30} tested {m['tested_cells']:5}  "
                     f"debt {m['debt_cells']:6}  coverage "
                     f"{'UNMEASURED' if cov is None else format(cov, '.2%')}")
        for axis, vals in (m.get("unmeasured") or {}).items():
            if vals:
                lines.append(f"      untested {axis:12} {', '.join(map(str, vals[:8]))}")
    never = report.get("untested_mechanisms") or []
    if never:
        lines.append(f"  NEVER TESTED: {', '.join(m['mechanism_id'] for m in never)}")
    cd = report.get("conversion_debt") or {}
    lines.append(f"  conversion coverage {cd.get('conversion_coverage')}; unexplained missing "
                 f"{cd.get('unexplained_missing_cells')}; unprocessed discoveries "
                 f"{cd.get('unprocessed_discoveries')}")
    for u in report.get("unmeasured") or []:
        lines.append(f"  UNMEASURED {u.get('what')}: {u.get('why')}")
    return lines


def run(*, dry_run: bool = False, out: Path | None = None,
        classes: Iterable[str] | None = None) -> dict[str, Any]:
    report = build(classes=classes)
    if not dry_run:
        _write_atomic(out if out is not None else OUT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    args = ap.parse_args(argv)
    report = run(dry_run=args.dry_run)
    for line in summary_lines(report):
        print(line)
    print("dry run -- nothing written" if args.dry_run else f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
