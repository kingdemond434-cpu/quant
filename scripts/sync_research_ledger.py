"""Bridge the desk's real results into the research store, so credit and A/B stop reading zeros.

WHY THIS EXISTS (2026-08-30)

`store.record_experiment` had ZERO callers. The `experiments` table -- the one holding expectancy,
stage and pass/fail -- was created, indexed, and never written. Everything downstream of it read
an empty table and returned a well-formed answer about nothing:

    trajectory credit   every asset scored on MEASURED_* alone, so the ranking could not tell a
                        candidate that survived the cost gauntlet from one that was merely looked
                        at. The ladder existed and had one rung.
    brain A/B           permanently pinned to `attributable_measured`, the shallowest rung,
                        because no deeper rung ever had a single observation in either arm.

Both were built to promote themselves automatically as the desk matures. Neither could, because
nothing fed them. THIS is the wiring that makes "ready, and fires once we have survivors" true
rather than aspirational: when a sleeve's forward verdict flips to PROMOTION CANDIDATE, its
experiment row becomes FORWARD_SURVIVED, credit switches from SHAPED to TERMINAL basis, and the
A/B promotes to the terminal rung -- with no code change and no human in the loop.

IT READS RESULTS, IT DOES NOT PRODUCE THEM. Every number written here already exists in an
artifact some other job computed under the canonical gates. This script joins, it never judges:
inventing an expectancy for a sleeve that has none would poison the credit ranking with fiction
that looks exactly like evidence.

THE TWO SOURCES, and why each maps where it does:

    UNIVERSAL_SURVIVORS.canon.json   42 cells past all ten gates. `expected_value.ev` is the
                                     expectancy the gauntlet measured; `stress_costs.exp_x3` is
                                     that expectancy under TRIPLE costs. exp_x3 is booked as the
                                     net figure -- it is stricter than net, which is the correct
                                     direction to be wrong in.
    sleeve_registry.json + ledgers   sleeves with a forward clock. The verdict comes from
                                     `forward_verdict`, the SAME engine the promotion path uses,
                                     so this can never disagree with the thing that promotes.

FAMILIES COME FROM `shadow_spec`/`identity`, NEVER from parsing a key. Parsing produced mechanisms
called `json` and `5_wait_bars=8` once already, and an allocator spent real budget on them.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
SHADOW = DESK / "reports" / "shadow"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))

OUT = ROOT / "data" / "research_ledger_sync.json"

#: A survivor that cleared every gate but has no forward clock has proven a backtest, not a desk.
_STAGE_BACKTEST = "BACKTEST_POSITIVE"
_STAGE_COST = "COST_SURVIVED"
_STAGE_ENROLLED = "FORWARD_ENROLLED"
_STAGE_SURVIVED = "FORWARD_SURVIVED"


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _survivor_rows() -> list[dict[str, Any]]:
    """Gauntlet survivors, mapped to experiment rows without inventing a single number."""
    blob = _load(DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    out = []
    for key, s in (blob.get("survivors") or {}).items():
        spec = s.get("shadow_spec") or {}
        gates = s.get("gates") or {}
        ev = (gates.get("expected_value") or {}).get("ev")
        x3 = (gates.get("stress_costs") or {}).get("exp_x3")
        passed = all(bool(g.get("passed")) for g in gates.values()) if gates else False

        # STAGE FROM WHAT THE GATES ACTUALLY SHOW. A cell only reaches COST_SURVIVED if its
        # expectancy stayed positive under the stress gate -- the gate is the evidence, and a
        # cell without that gate does not get the rung for free.
        stage = _STAGE_BACKTEST
        if isinstance(x3, (int, float)) and x3 > 0:
            stage = _STAGE_COST
        out.append({
            "hypothesis_id": key,
            "generator": str(s.get("hunt") or "unknown"),
            "mechanism": str(spec.get("family") or ""),
            "symbol": str(spec.get("sym") or spec.get("symbol") or s.get("sym") or ""),
            "coordinate": ".".join(str(spec.get(k) or "") for k in
                                   ("family", "selector", "condition", "side")),
            "exp_r_gross": float(ev) if isinstance(ev, (int, float)) else None,
            "exp_r_net": float(x3) if isinstance(x3, (int, float)) else None,
            "stage": stage, "passed": passed, "n_trades": 0,
        })
    return out


def _forward_rows() -> list[dict[str, Any]]:
    """Sleeves with a forward clock, judged by the canonical verdict engine.

    THIS is the line that fires when the first survivor appears. Nothing else has to change.
    """
    import forward_verdict as fv
    from build_family_evidence import _forward_trades, _ledger_for, _registry_identities

    rows = []
    for key, ident in (_registry_identities() or {}).items():
        path = _ledger_for(ident["symbol"], ident["family"], ident["selector"])
        if path is None:
            continue
        trades = _forward_trades(path)
        if not trades:
            # A REGISTERED SLEEVE WITH NO FORWARD TRADE IS ENROLLED, NOT FAILED. Recording it as
            # a zero would let an empty ledger vote in the credit ranking as though the desk had
            # tested something and found nothing.
            rows.append({"hypothesis_id": key, "mechanism": ident["family"],
                         "symbol": ident["symbol"], "stage": _STAGE_ENROLLED,
                         "exp_r_gross": None, "exp_r_net": None, "n_trades": 0,
                         "passed": False, "generator": "forward_shadow",
                         "coordinate": f"{ident['family']}.{ident.get('selector') or ''}"})
            continue
        rs = [r for _, r in trades]
        start = _load(DESK / "data" / "sleeve_registry.json") or {}
        meta = (start.get("sleeves") or {}).get(key) or {}
        try:
            days = fv.days_between(
                datetime.fromisoformat(str(meta.get("forward_start"))), datetime.now(tz=UTC))
        except (TypeError, ValueError):
            days = 0
        v = fv.verdict(rs, days)
        survived = str(v.get("verdict", "")).upper().replace("_", " ") == fv.PROMOTION_CANDIDATE
        rows.append({
            "hypothesis_id": key, "mechanism": ident["family"], "symbol": ident["symbol"],
            "stage": _STAGE_SURVIVED if survived else _STAGE_ENROLLED,
            "exp_r_gross": None,
            "exp_r_net": round(sum(rs) / len(rs), 6),
            "n_trades": len(rs), "passed": survived, "generator": "forward_shadow",
            "coordinate": f"{ident['family']}.{ident.get('selector') or ''}",
        })
    return rows


def _classify(mechanism: str, symbol: str) -> tuple[str, str]:
    """The measurement class the adapter registry gives this mechanism on this symbol.

    Returns ("UNAVAILABLE", "") when no adapter is registered. That is not a defect to paper
    over: it names a family whose results cannot speak about its own mechanism, which is the
    single most useful thing the desk can learn about where to write the next adapter.
    """
    try:
        from libs.research_os.adapters import REGISTRY
    except ImportError:
        return "UNAVAILABLE", ""
    adapter = REGISTRY.get(mechanism)
    if adapter is None:
        return "UNAVAILABLE", ""
    bars_path = DESK / "data" / "universe" / f"{symbol}_H1.parquet"
    if not bars_path.exists():
        return "UNAVAILABLE", type(adapter).__name__
    try:
        import pandas as pd
        bars = pd.read_parquet(bars_path).rename(columns=str.lower).tail(2000)
        res = adapter.measure({"mechanism": mechanism, "symbol": symbol}, bars)
        return str(res.status), str(res.adapter or type(adapter).__name__)
    except Exception:
        return "UNAVAILABLE", type(adapter).__name__


def main() -> int:
    from libs.research_os import store
    from libs.research_os.brain_ab import assign_arm

    now = datetime.now(tz=UTC)
    print(f"RESEARCH LEDGER SYNC {now.isoformat(timespec='seconds')}")

    rows = _survivor_rows()
    try:
        rows += _forward_rows()
    except Exception as exc:
        print(f"  forward leg unavailable ({type(exc).__name__}: {str(exc)[:70]}) -- survivors "
              f"still synced. Reported, never swallowed silently.")

    # IDEMPOTENT. These tables are append-only, so re-running would otherwise multiply every
    # candidate's weight in the credit ranking by the number of times the timer has fired --
    # a fertility count dressed as evidence, which is the exact failure GAMMA exists to prevent.
    with store.connect() as conn:
        known = {str(r[0]) for r in conn.execute(
            "SELECT hypothesis_id FROM hypotheses").fetchall()}
        latest = {str(r[0]): (str(r[1] or ""), r[2])
                  for r in conn.execute(
                      "SELECT hypothesis_id, stage, exp_r_net FROM experiments "
                      "ORDER BY id ASC").fetchall()}
        measured_ids = {str(r[0]): str(r[1] or "") for r in conn.execute(
            "SELECT hypothesis_id, status FROM measurements ORDER BY id ASC").fetchall()}

    new_hyp = new_exp = unchanged = 0
    no_adapter: dict[str, int] = {}
    reclassified = 0
    for r in rows:
        hid = r["hypothesis_id"]
        if hid not in known:
            store.record_hypothesis(
                hypothesis_id=hid, origin="ledger_sync", generator=r["generator"],
                mechanism=r["mechanism"], coordinate=r["coordinate"], parent_ids=[],
                generation=0, brain_version=assign_arm(hid),
                spec={"symbol": r["symbol"]})
            known.add(hid)
            new_hyp += 1
        # CLASSIFY THE MEASUREMENT, so mechanism credit can flow -- or honestly cannot.
        # A gauntlet result is a direct measurement of the STRATEGY's P&L; whether it says
        # anything about the MECHANISM depends on whether the mechanism's own observable is
        # what the rule reads. That judgement already exists in the adapter registry and is
        # argued there, so it is reused rather than re-decided here. Families with no adapter
        # resolve to UNAVAILABLE and their mechanism accrues no credit at all, which is the
        # correct answer and a standing list of adapters worth writing.
        if r["mechanism"]:
            cls, adapter = _classify(r["mechanism"], r["symbol"])
            # RE-CLASSIFY WHEN THE ANSWER CHANGES, not once and forever. The registry improves --
            # a new adapter, a new alias, a data file that finally arrived -- and a candidate
            # measured UNAVAILABLE last week may be attributable today. Recording once would
            # freeze every result at the desk's worst historical capability and quietly deny
            # credit to mechanisms it can now genuinely measure. Append-only plus latest-wins
            # means a changed class propagates on the next tick with no backfill.
            if measured_ids.get(hid) != cls:
                store.record_measurement(
                    hypothesis_id=hid, mechanism=r["mechanism"], adapter=adapter,
                    status=cls, attributable=cls in ("VALIDATED_PROXY", "DIRECT"),
                    pit_safe=True, missing_observable="" if adapter else r["mechanism"],
                    notes="classified at ledger sync via the adapter registry")
                measured_ids[hid] = cls
                reclassified += 1
            no_adapter[r["mechanism"]] = no_adapter.get(r["mechanism"], 0) + (0 if adapter else 1)

        prev = latest.get(hid)
        if prev is not None and prev[0] == r["stage"] and prev[1] == r["exp_r_net"]:
            unchanged += 1
            continue
        store.record_experiment(
            hypothesis_id=hid, mechanism=r["mechanism"], coordinate=r["coordinate"],
            symbol=r["symbol"], n_trades=r["n_trades"], exp_r_gross=r["exp_r_gross"],
            exp_r_net=r["exp_r_net"], t_stat=None, stage=r["stage"], passed=r["passed"])
        new_exp += 1

    from libs.research_os import brain_ab, credit
    cr = credit.from_store()
    ab = brain_ab.report()

    by_stage: dict[str, int] = {}
    for r in rows:
        by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
    print(f"  {len(rows)} result row(s): {by_stage}")
    print(f"  +{new_hyp} hypothes(es), +{new_exp} experiment(s), {unchanged} unchanged, "
          f"{reclassified} re-classified")
    print(f"  credit basis: {cr['basis'][:88]}")
    for a in cr["assets"][:6]:
        flag = "" if a["confident"] else "  (thin)"
        print(f"    {a['kind']:11s} {a['name'][:30]:30s} adv={a['advantage']:+.4f} "
              f"n={a['n']}{flag}")
    h = ab["headline"]
    print(f"  A/B rung {h.get('metric')}: {h.get('verdict')}")
    gaps = sorted((m for m, n in no_adapter.items() if n), key=str)
    if gaps:
        print(f"  NO ADAPTER for {len(gaps)} famil(ies) -- their results cannot speak about "
              f"their own mechanism: {', '.join(gaps[:6])}"
              + (f" (+{len(gaps) - 6} more)" if len(gaps) > 6 else ""))

    OUT.write_text(json.dumps(
        {"ran_at": now.isoformat(timespec="seconds"), "rows": len(rows), "by_stage": by_stage,
         "new_hypotheses": new_hyp, "new_experiments": new_exp,
         "credit": cr, "brain_ab": ab,
         "families_without_adapter": sorted(m for m, n in no_adapter.items() if n)}, indent=1, default=str), "utf-8")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
