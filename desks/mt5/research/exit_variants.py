"""EXIT_VARIANTS.json: where each in-trade management policy for the live gold sleeve stands.

THE QUESTION (principal 2026-11-03): do the live accounts manage a trade like a human trader --
breakeven, trailing, partials, time stops, market conditions? The live ratchet
(`mt5desk/position_manager.py`) already moves the stop to costed breakeven at +0.85R and trails
it on ATR. Every other policy is a claim, and `family_session_exit_overlay` puts each one in
front of the gauntlet as one charged trial on the identical entries.

This file publishes, per policy:
  state             BUILT (registered, no verdict yet), JUDGED (terminal gate on the ledger),
                    or PROMOTED (a certified survivor)
  dlogw_vs_static   E[log W] summed over the full in-sample history at the sleeve's live risk,
                    minus the same sum for the parent's static stop/target exit, on the same
                    trades. In-sample only, so it is a screen and NEVER a promotion reason:
                    promotion is the gauntlet's verdict, then a forward beat of the parent.
  dlogw_vs_live     the same against `ratchet`, the closest the engine gets to the live exit

Read hourly by the hourly pass. Pure bookkeeping: nothing here can place, size or move an order.
"""
from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORT = DESK / "reports" / "EXIT_VARIANTS.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
FAMILY = "session_exit_overlay"
PARENT = "session_range_breakout"
SYMBOL = "XAUUSD"
#: The live parameterisation (decision_core GOLD_WINDOWS asia, RR, ATR_N) and the smallest live
#: risk on the sleeve (E8 gold_asia 0.006), so the growth figure is never flattered by a bigger
#: account's risk.
PARENT_PARAMS = {"range_start": 7, "wait_bars": 8, "atr_n": 20, "ttl_bars": 12, "rr": 2.0}
RISK_FRAC = 0.006
LEDGER_TAIL_BYTES = 8 << 20


def _sum_logw(rs: list[float], f: float = RISK_FRAC) -> float:
    return float(sum(math.log1p(f * r) for r in rs if f * r > -1.0))


def _verdicts() -> dict[str, dict[str, Any]]:
    """Latest ledger row per policy, read from the tail (the ledger is large and append-only)."""
    out: dict[str, dict[str, Any]] = {}
    try:
        size = GATE_LEDGER.stat().st_size
        with GATE_LEDGER.open("rb") as fh:
            fh.seek(max(0, size - LEDGER_TAIL_BYTES))
            lines = fh.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return out
    from mt5desk.families import SESSION_EXIT_POLICIES
    for line in lines:
        if FAMILY not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        cell = str(row.get("cell") or "")
        for p in SESSION_EXIT_POLICIES:
            if p in cell:
                out[p] = {"terminal_gate": row.get("terminal_gate"), "passed": row.get("passed"),
                          "at": row.get("at"), "cell": cell}
    return out


def _promoted() -> set[str]:
    try:
        doc = json.loads(SURVIVORS.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    from mt5desk.families import SESSION_EXIT_POLICIES
    names = " ".join(str(k) for k in (doc.get("survivors") or {}))
    return {p for p in SESSION_EXIT_POLICIES if FAMILY in names and p in names}


def screen(meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """In-sample R per trade for the parent and every policy, through the gauntlet's own cell
    builder and the desk's engine, so costs are the ones the judge charges."""
    import sys
    for p in (DESK, DESK / "scripts", DESK / "research"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import external_gauntlet as eg
    from mt5desk.engine import run_backtest
    from mt5desk.families import SESSION_EXIT_POLICIES
    if meta is None:
        meta = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))

    def _rs(fam: str, params: dict[str, Any]) -> list[float] | None:
        cell = eg.build_cell(SYMBOL, fam, params, meta)
        if not cell or not cell.get("sigs"):
            return None
        res = run_backtest(cell["df"], cell["sigs"], cell["costs"])
        return [float(t.r_multiple) for t in res.trades]

    parent = _rs(PARENT, dict(PARENT_PARAMS))
    rows = {p: _rs(FAMILY, dict(PARENT_PARAMS, exit_policy=p)) for p in SESSION_EXIT_POLICIES}
    return {"parent": parent, "variants": rows}


def publish(now: datetime | None = None) -> dict[str, Any]:
    """Write EXIT_VARIANTS.json. Never raises: a failed screen publishes UNMEASURED rows."""
    from mt5desk.families import SESSION_EXIT_POLICIES
    t = now or datetime.now(UTC)
    try:
        got = screen()
        err = None
    except Exception as exc:
        got, err = {"parent": None, "variants": {}}, f"{type(exc).__name__}: {exc}"[:200]
    parent = got["parent"]
    base = _sum_logw(parent) if parent else None
    live_rs = got["variants"].get("ratchet")
    live = _sum_logw(live_rs) if live_rs else None
    verdicts, promoted = _verdicts(), _promoted()
    rows = []
    for p in SESSION_EXIT_POLICIES:
        rs = got["variants"].get(p)
        lw = _sum_logw(rs) if rs else None
        v = verdicts.get(p)
        rows.append({
            "policy": p,
            "state": ("PROMOTED" if p in promoted else "JUDGED" if v else "BUILT"),
            "verdict": v,
            "trades": len(rs) if rs else None,
            "mean_r": round(sum(rs) / len(rs), 4) if rs else None,
            "dlogw_vs_static": (round(lw - base, 5) if lw is not None and base is not None
                                else None),
            "dlogw_vs_live": (round(lw - live, 5) if lw is not None and live is not None
                              else None),
        })
    doc = {
        "at": t.isoformat(timespec="seconds"),
        "sleeve": "gold_asia", "symbol": SYMBOL, "family": FAMILY, "parent": PARENT,
        "parent_params": PARENT_PARAMS, "risk_frac": RISK_FRAC,
        "parent_trades": len(parent) if parent else None,
        "screen_error": err,
        "basis": ("dlogw_* are IN-SAMPLE sums over the full history at the sleeve's smallest live "
                  "risk. A screen, never a promotion reason: promotion is the gauntlet's verdict "
                  "(charged trial, Tier S bar) and then a forward beat of the parent."),
        "not_yet_expressible": [
            "mid-trade exits on market state (reversal, adverse momentum, regime flip, news "
            "shock, spread blowout): the engine walks a fixed stop/target/trail per signal and "
            "has no hook for an exit decided by bars after the fill",
            "the +0.85R costed break-even floor of the live ratchet has no engine field",
        ],
        "variants": rows,
    }
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, REPORT)
    except OSError:
        pass
    return doc
