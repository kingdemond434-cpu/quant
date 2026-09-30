#!/usr/bin/env python3
"""THE ANALYST PANEL: TradingAgents' four analysts and its bull/bear debate as a cell generator.

    python desks/mt5/research/analyst_panel.py --once [--budget-s 420] [--symbols 1]
    python desks/mt5/research/analyst_panel.py --once --dry-run      # propose + screen, no donation

WHERE THIS CAME FROM. github.com/TauricResearch/TradingAgents (Apache-2.0) runs four analysts
(market, sentiment, news, fundamentals), a bull and a bear researcher who argue in turn, a trader
and a three-way risk team, and lets the result place a trade. `committees.py` already took its
adversarial half (2026-09-25): roles that speak in turn, a judge that is arithmetic. This module
takes the OTHER half, the analysts, and puts them where a language model is competent -- in front
of the gauntlet as a source of hypotheses -- and nowhere else.

WHAT IT REFUSES FROM THE SOURCE, and why:
  * the trader and the portfolio manager (a per-trade BUY/HOLD/SELL). A model that has read the
    history cannot be backtested point-in-time: its decision on 2021-03-04 already knows 2022.
    So no model output here reaches a position, a size or a veto. It reaches the docket.
  * the aggressive / conservative / neutral risk debate. Sizing is the allocator's, by
    Delta E[log W] (Growth Governance); a model voting on risk would be a cap without a ledger.

WHAT A PASS DOES:
  1. Picks the next hypothesis-lane symbol(s) in rotation and describes them to the panel from
     the bars in the store only: returns, realised vol, range position, trend and gap structure,
     all up to the last closed bar. No news text, no prices after the last bar, nothing sealed.
  2. Each of the four analysts proposes cells in the desk's OWN grammar: one registered price-only
     family, its parameters, the mechanism in its lens, and a falsifier. `_valid_cell` refuses an
     unregistered family, an unknown parameter, a value off its type or outside 1/4x..4x of the
     family default, and a cell with no falsifier. A mechanism no family can express is kept as
     an UNEXPRESSED row in the report -- a family gap for the builders, never a candidate.
  3. The bear sees every accepted cell and attacks it: a failure class from the committees'
     vocabulary and the cheapest test that would kill it. The attack rides on the donated row as
     a preregistered falsifier. It removes nothing; the gauntlet decides.
  4. Every accepted cell is screened by `proposer_common.screen` (forward return at its own TTL,
     net of the round trip, non-overlapping), and the ones that clear cost on >= MIN_TRADES
     independent trades are donated through `proposer_common.donate` into
     `data/intelligence/analyst_panel/` for `miner_candidate_compiler` (EXACT_RECIPE).
  5. Writes `reports/ANALYST_PANEL.json`: calls, proposals, acceptance and refusal reasons per
     analyst, screen t tails against the null, donations, and the unexpressed mechanisms.

HINDSIGHT. The model has read the sample it proposes on, so the in-sample screen of a proposal is
contaminated in a way a machine-drawn cell's is not. Every row carries `proposed_at` and
`hindsight_prior: true`: evidence after `proposed_at` is the clean part. Every proposal is also
charged as a trial by the seat (`proposer_seat.charge_trials`), so the panel pays for its volume.

OPTIONAL BY CONSTRUCTION. The transport is `proposer_seat.ask` (OpenRouter / the free panel). When
no seat resolves, the pass writes UNMEASURED and returns; nothing else on the desk changes.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "analyst_panel"
ORGAN = "analyst_panel"
OUT = BASE / "reports" / "ANALYST_PANEL.json"
STATE = BASE / "data" / "analyst_panel_state.json"
UNMEASURED = "UNMEASURED"
MIN_TRADES = 30
MIN_BARS = 3_000
ORIGIN = "github.com/TauricResearch/TradingAgents (Apache-2.0): analyst roles + bull/bear debate"

#: Families a proposal may not name: `generic` executes a free-form semantic coordinate, which
#: would let a model write a strategy the registry never reviewed.
EXCLUDED_FAMILIES = frozenset({"generic"})

#: The analysts, as LENSES on mechanism, because the desk's executable grammar is price-only: a
#: fundamentals analyst here proposes the price footprint of a flow or a macro cause, not a P/E.
#: (role, participant structure its mechanisms usually rest on, the ask)
ANALYSTS: dict[str, tuple[str, str]] = {
    "market_analyst": ("mixed",
                       "You are the market (technical) analyst. Propose cells whose mechanism is "
                       "price structure itself: trend persistence, range and breakout behaviour, "
                       "volatility clustering, gaps."),
    "fundamentals_analyst": ("institutional",
                             "You are the fundamentals / macro analyst. Propose cells whose "
                             "mechanism is a flow or a macro cause with a PRICE footprint: "
                             "month-end rebalancing, fixings, hedging demand, carry, policy "
                             "sessions."),
    "news_analyst": ("mixed",
                     "You are the news analyst. Propose cells whose mechanism is how this "
                     "instrument absorbs information: which session processes news first, how "
                     "jumps continue or reverse, how overnight gaps decay."),
    "sentiment_analyst": ("retail_heavy",
                          "You are the sentiment analyst. Propose cells whose mechanism is "
                          "crowd behaviour: chasing breakouts, capitulation after drawdowns, "
                          "bubbles and their bursts, crowded retail levels."),
}

#: The bear's vocabulary is the committees' failure classes, so an attack here and a committee
#: explanation there are the same kind of object.
FAILURE_CLASSES: tuple[str, ...] = ("COST_DEATH", "NO_EDGE", "SELECTION_BIAS", "STATE_FRAGILE",
                                    "LEAKAGE", "LOW_SAMPLE", "EXECUTION_FAILURE",
                                    "CORRELATION_DUPLICATE", "TAIL_FAILURE")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(path)


def identity(symbol: str, family: str, params: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": family, "p": dict(params)},
                                     sort_keys=True, default=str).encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------- the grammar
def catalogue() -> dict[str, dict[str, Any]]:
    """Every registered price-only family: its defaults, the strings a mode may take, one line."""
    from mt5desk import families_orthogonal as fo
    grids: dict[str, dict[str, Any]] = {}
    for mod in ("families_elitequant", "families_cn_cta"):
        try:
            m = __import__(f"mt5desk.{mod}", fromlist=["PARAM_GRID"])
            grids.update(getattr(m, "PARAM_GRID", {}) or {})
        except Exception:                                  # pragma: no cover - optional module
            continue
    out: dict[str, dict[str, Any]] = {}
    for name, inputs in fo.FAMILY_INPUTS.items():
        if name in EXCLUDED_FAMILIES or not inputs or inputs[0] != "price only":
            continue
        fn = fo.ORTHOGONAL_FAMILIES.get(name)
        if fn is None:
            continue
        sig: Any = fn
        defaults = {k: p.default for k, p in inspect.signature(sig).parameters.items()
                    if p.default is not inspect.Parameter.empty}
        choices = {k: sorted({str(v) for v in vals}) for k, vals in (grids.get(name) or {}).items()
                   if isinstance(defaults.get(k), str)}
        doc = (fn.__doc__ or "").strip().splitlines()
        out[name] = {"defaults": defaults, "choices": choices,
                     "doc": (doc[0] if doc else name.replace("_", " "))[:140]}
    return out


def _grammar(cat: Mapping[str, Mapping[str, Any]]) -> str:
    fams = "; ".join(f"{k}({', '.join(f'{p}={v!r}' for p, v in c['defaults'].items())}): "
                     f"{c['doc']}" for k, c in cat.items())
    return ('Return JSON objects {"family": "<one registered family, or NONE>", '
            '"params": {<only that family\'s parameter names>}, "mechanism": "<the cause, '
            '<=300 chars>", "falsifier": "<what observation would prove it wrong, <=200 chars>"}. '
            "Parameters you omit keep their default; numbers must stay within 1/4x..4x of the "
            "default. If no family can express the mechanism, set family to NONE and still give "
            f"mechanism and falsifier. Registered families: {fams}")


def _valid_cell(cat: Mapping[str, Mapping[str, Any]]) -> Callable[[Any], str | None]:
    def valid(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return "not a JSON object"
        mech = str(payload.get("mechanism") or "").strip()
        if len(mech) < 12:
            return "mechanism shorter than 12 characters is a label, not a cause"
        if not str(payload.get("falsifier") or "").strip():
            return "no falsifier: a cause nothing could refute is not a claim"
        fam = str(payload.get("family") or "").strip()
        if fam.upper() == "NONE":
            return None                                    # an unexpressed mechanism, kept
        if fam not in cat:
            return f"family {fam[:40]!r} is not a registered price-only family"
        params = payload.get("params") or {}
        if not isinstance(params, dict):
            return "params is not an object"
        spec = cat[fam]
        for k, v in params.items():
            if k not in spec["defaults"]:
                return f"{fam} has no parameter {str(k)[:30]!r}"
            why = _valid_value(spec["defaults"][k], v, spec["choices"].get(k))
            if why:
                return f"{fam}.{k}: {why}"
        return None
    return valid


def _valid_value(default: Any, v: Any, choices: Sequence[str] | None) -> str | None:
    if isinstance(default, bool):
        return None if isinstance(v, bool) else "must be true/false"
    if isinstance(default, str):
        allowed = set(choices or ()) | {default}
        return None if isinstance(v, str) and v in allowed else f"must be one of {sorted(allowed)}"
    if isinstance(default, (int, float)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            return "must be a finite number"
        if isinstance(default, int) and float(v) != int(v):
            return "must be an integer"
        d = float(default)
        if d != 0 and not (min(d / 4, d * 4) <= float(v) <= max(d / 4, d * 4)):
            return f"{v} is outside 1/4x..4x of the default {default}"
        return None
    return "only numeric, boolean or mode parameters may be proposed" if v != default else None


def normalise(payload: Mapping[str, Any], cat: Mapping[str, Mapping[str, Any]]
              ) -> dict[str, Any]:
    """The params the family will run with: its defaults, overridden by the proposal, typed."""
    spec = cat[str(payload["family"])]
    params: dict[str, Any] = {}
    for k, v in (payload.get("params") or {}).items():
        d = spec["defaults"][k]
        params[k] = int(v) if isinstance(d, int) and not isinstance(d, bool) else v
    return params


# ---------------------------------------------------------------------------- the context
def describe(symbol: str, d: Any) -> list[str]:
    """What the panel may see: facts from the stored bars up to the last closed bar, and no more."""
    import numpy as np
    c = d["close"].astype(float)
    daily = c.resample("1D").last().dropna()
    r = np.log(daily).diff().dropna()
    last = daily.index[-1].date().isoformat()

    def ret(n: int) -> str:
        if len(daily) <= n:
            return "n/a"
        return f"{(daily.iloc[-1] / daily.iloc[-n - 1] - 1) * 100:+.1f}%"

    hi, lo = float(daily.iloc[-250:].max()), float(daily.iloc[-250:].min())
    pos = (float(daily.iloc[-1]) - lo) / (hi - lo) if hi > lo else 0.5
    o = d["open"].astype(float)
    gap = (o / c.shift(1) - 1).abs()
    big_gaps = int((gap > 4 * gap.rolling(500, min_periods=50).median()).iloc[-2000:].sum())
    return [f"instrument: {symbol} (hourly bars, last closed bar {last})",
            f"returns: 20d {ret(20)}, 120d {ret(120)}, 250d {ret(250)}",
            f"realised vol (daily, annualised): 20d {r.iloc[-20:].std() * 15.87 * 100:.1f}%, "
            f"250d {r.iloc[-250:].std() * 15.87 * 100:.1f}%",
            f"position in the 250-day range: {pos:.2f} (0 = low, 1 = high)",
            f"skew of daily returns, 250d: {float(r.iloc[-250:].skew()):+.2f}",
            f"large hourly gaps in the last 2,000 bars: {big_gaps}"]


# ---------------------------------------------------------------------------- the pass
def symbols() -> list[str]:
    from research import proposer_common as pc
    from research import universe_policy as up
    return [s for s in pc.universe_meta() if up.may_hypothesise(s)]


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    if not isinstance(doc, dict):
        doc = {}
    doc.setdefault("cursor", 0)
    doc.setdefault("cells", {})
    doc.setdefault("unexpressed", [])
    return doc


def debate(symbol: str, context: list[str], cat: Mapping[str, Mapping[str, Any]], *,
           ask: Callable[..., Any], calls_left: int, n: int = 3
           ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """The four analysts propose, the bear attacks. Returns (cells, unexpressed, meter)."""
    meter: dict[str, Any] = {"calls": 0, "trials_charged": 0.0, "by_analyst": {},
                             "reasons": Counter()}
    grammar, valid = _grammar(cat), _valid_cell(cat)
    cells: list[dict[str, Any]] = []
    unexpressed: list[dict[str, Any]] = []
    for role, (_, task) in ANALYSTS.items():
        if meter["calls"] >= calls_left:
            break
        reply = ask(ORGAN, "candidates", task=f"{task} Instrument: {symbol}.", grammar=grammar,
                    context=context, n=n, validate=valid)
        meter["calls"] += 1
        meter["trials_charged"] += float(getattr(reply, "trials_charged", 0.0) or 0.0)
        items = [i for i in (getattr(reply, "items", None) or []) if isinstance(i, dict)]
        meter["by_analyst"][role] = {"verdict": getattr(reply, "verdict", UNMEASURED),
                                     "accepted": len(items),
                                     "discarded": int(getattr(reply, "discarded", 0) or 0)}
        for why in getattr(reply, "reasons", []) or []:
            meter["reasons"][str(why)[:100]] += 1
        if getattr(reply, "verdict", UNMEASURED) != "RAN" and meter["calls"] == 1:
            meter["why"] = str(getattr(reply, "why", "") or "seat dark")[:200]
            break                                            # a dark seat stays dark this pass
        for it in items:
            row: dict[str, Any] = {"analyst": role, "symbol": symbol,
                   "mechanism": str(it.get("mechanism"))[:300],
                   "falsifier": str(it.get("falsifier"))[:200]}
            if str(it.get("family") or "").upper() == "NONE":
                unexpressed.append(row)
            else:
                row["family"] = str(it["family"])
                row["params"] = normalise(it, cat)
                if "symbol" in cat[row["family"]]["defaults"]:
                    row["params"]["symbol"] = symbol       # a family keyed by its own cell
                cells.append(row)
    if cells and meter["calls"] < calls_left:
        listing = [f"[{i}] {c['analyst']}: {c['family']} {json.dumps(c['params'])} -- "
                   f"{c['mechanism'][:160]}" for i, c in enumerate(cells)]
        reply = ask(ORGAN, "candidates",
                    task=("You are the bear researcher. Attack each proposed cell below: name the "
                          "most likely reason it fails and the cheapest deterministic test that "
                          "would show it. Do not grade, rank or score anything."),
                    grammar=('{"idx": <the cell number>, "failure_class": "<one of '
                             f'{", ".join(FAILURE_CLASSES)}>", "attack": "<=240 chars", '
                             '"kill_test": "<=200 chars"}'),
                    context=context + listing, n=len(cells), validate=_valid_attack(len(cells)))
        meter["calls"] += 1
        meter["trials_charged"] += float(getattr(reply, "trials_charged", 0.0) or 0.0)
        attacks = [a for a in (getattr(reply, "items", None) or []) if isinstance(a, dict)]
        meter["bear"] = {"verdict": getattr(reply, "verdict", UNMEASURED), "attacks": len(attacks)}
        for a in attacks:
            cells[int(a["idx"])].setdefault("red_team", []).append(
                {"failure_class": a["failure_class"], "attack": str(a["attack"])[:240],
                 "kill_test": str(a.get("kill_test") or "")[:200]})
    meter["reasons"] = dict(meter["reasons"].most_common(8))
    return cells, unexpressed, meter


def _valid_attack(n_cells: int) -> Callable[[Any], str | None]:
    def valid(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return "not a JSON object"
        try:
            idx = int(payload.get("idx"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return "idx is not an integer"
        if not 0 <= idx < n_cells:
            return "idx names no proposed cell"
        if payload.get("failure_class") not in FAILURE_CLASSES:
            return "failure_class outside the committees' vocabulary"
        if len(str(payload.get("attack") or "").strip()) < 12:
            return "attack shorter than 12 characters"
        return None
    return valid


def run(*, budget_s: float = 420.0, n_symbols: int = 1, calls: int = 10, dry_run: bool = False,
        only: Sequence[str] | None = None, ask: Callable[..., Any] | None = None
        ) -> dict[str, Any]:
    from mt5desk import families_orthogonal as fo

    from research import proposer_common as pc
    from research.multiplicity import deflate_t

    started = time.monotonic()
    if ask is None:
        try:
            from libs.research import proposer_seat as ps
        except Exception as exc:
            return {"status": UNMEASURED, "why": f"proposer seat unimportable: {exc!r}"[:200]}
        if not ps.enabled():
            return {"status": UNMEASURED,
                    "why": "no seat resolves on this host; the desk runs as it does without it"}
        ask = ps.ask
    cat = catalogue()
    state = _load_state()
    try:
        pool = [s for s in symbols() if not only or s in only]
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"universe unreadable: {type(exc).__name__}"}
    if not pool:
        return {"status": UNMEASURED, "why": "no hypothesis-lane symbol with bars"}
    meta = pc.universe_meta()
    at = _now()
    all_cells: list[dict[str, Any]] = []
    all_unexpressed: list[dict[str, Any]] = []
    meters: dict[str, Any] = {}
    calls_left, seen = calls, 0
    while seen < min(n_symbols, len(pool)) and calls_left > 0 \
            and time.monotonic() - started < budget_s:
        sym = pool[int(state["cursor"]) % len(pool)]
        state["cursor"] = int(state["cursor"]) + 1
        seen += 1
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            meters[sym] = {"why": "bars absent or short"}
            continue
        cells, unexpressed, meter = debate(sym, describe(sym, d), cat, ask=ask,
                                           calls_left=calls_left)
        calls_left -= int(meter["calls"])
        meters[sym] = meter
        cost = pc.cost_frac(sym, meta, d["close"])
        for c in cells:
            c["proposed_at"] = at
            if cost is None:
                c["screen"] = {"held_back": "no cost model"}
                continue
            try:
                fam_fn: Any = fo.ORTHOGONAL_FAMILIES[c["family"]]
                sig = fam_fn(d, **c["params"])
                c["screen"] = pc.screen(d, sig, cost) or {"n_independent": 0}
            except Exception as exc:
                c["screen"] = {"error": f"{type(exc).__name__}: {str(exc)[:80]}"}
        all_cells += cells
        all_unexpressed += unexpressed
        if meter.get("why") and not meter["calls"] > 1:
            break

    donate = [c for c in all_cells
              if int((c.get("screen") or {}).get("n_independent") or 0) >= MIN_TRADES
              and (c.get("screen") or {}).get("clears_cost")
              and identity(c["symbol"], c["family"], c["params"]) not in state["cells"]]
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if donate and not dry_run:
        rows = []
        for c in donate:
            row = pc.candidate(SOURCE, c["symbol"], c["family"], dict(c["params"]),
                               f"{c['mechanism']} Falsifier: {c['falsifier']}",
                               f"{c['symbol']} {c['family']} ({c['analyst']})",
                               {"screen_t_gross": c["screen"].get("t_gross"),
                                "n_independent": c["screen"].get("n_independent"),
                                "origin": ORIGIN, "analyst": c["analyst"],
                                "red_team": c.get("red_team") or [],
                                "proposed_at": c["proposed_at"], "hindsight_prior": True})
            culture = {"source_culture": "GLOBAL/llm",
                       "participant_structure": ANALYSTS[c["analyst"]][0],
                       "crowding_prior": "high",
                       "failure_mode_hypothesis": c["falsifier"][:200]}
            row.update(culture)
            row["culture_derivation"] = dict.fromkeys(culture, "declared")
            rows.append(row)
        path = pc.donate(SOURCE, rows, len(all_cells))
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, "n": int(counts.get("donated") or 0),
                    "refused_wrong_lane": counts.get("refused_wrong_lane")}
        if path:
            for c in donate:
                state["cells"][identity(c["symbol"], c["family"], c["params"])] = {
                    "donated_at": at, "analyst": c["analyst"], "symbol": c["symbol"],
                    "family": c["family"], "t_gross": c["screen"].get("t_gross")}
    if not dry_run:
        state["unexpressed"] = (state["unexpressed"] + all_unexpressed)[-500:]
        _atomic(STATE, state)

    ts = [float(c["screen"]["t_gross"]) for c in all_cells
          if isinstance((c.get("screen") or {}).get("t_gross"), (int, float))
          and math.isfinite(c["screen"]["t_gross"])]
    by_analyst: dict[str, Counter[str]] = {a: Counter() for a in ANALYSTS}
    for c in all_cells:
        by_analyst[c["analyst"]]["proposed"] += 1
        by_analyst[c["analyst"]]["clears_screen"] += int(c in donate)
    for u in all_unexpressed:
        by_analyst[u["analyst"]]["unexpressed"] += 1
    best = max(ts, default=None)
    return {
        "status": "OK" if any(a.get("verdict") == "RAN" for m in meters.values()
                              for a in (m.get("by_analyst") or {}).values()) else UNMEASURED,
        "dry_run": bool(dry_run), "elapsed_s": round(time.monotonic() - started, 2),
        "calls": calls - calls_left, "symbols": meters, "families_offered": len(cat),
        "cells_proposed": len(all_cells), "by_analyst": {k: dict(v) for k, v in by_analyst.items()},
        "screen_tails": {"n": len(ts), "t_gt_2": sum(t > 2 for t in ts),
                         "null_expected": round(0.0228 * len(ts), 2),
                         "best_t": best,
                         "best_t_deflated_by_panel_lifetime": None if best is None else round(
                             deflate_t(best, max(len(ts), len(state["cells"]) + len(ts))), 3)},
        "candidates_this_pass": len(donate), "donation": donation,
        "unexpressed_this_pass": all_unexpressed,
        "unexpressed_total": len(state["unexpressed"]),
        "contract": ("the panel earns its calls by the ten gates' verdicts on its donated cells "
                     "against machine-drawn cells of the same families; its screen tails say only "
                     "whether it proposes better than a null of its size. Unexpressed mechanisms "
                     "are family gaps for the builders, never candidates."),
        "refused_from_source": ["trader / portfolio manager per-trade decision (not "
                                "point-in-time backtestable)", "risk-team sizing debate "
                                "(sizing is the allocator's)"],
        "origin": ORIGIN,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=420.0)
    ap.add_argument("--symbols", type=int, default=1, help="symbols per pass, in rotation")
    ap.add_argument("--calls", type=int, default=10, help="seat calls per pass")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = {"generated_at": _now(), "source": SOURCE,
           **run(budget_s=a.budget_s, n_symbols=a.symbols, calls=a.calls, dry_run=a.dry_run,
                 only=a.only)}
    if not a.dry_run:
        _atomic(OUT, rep)
    print(f"analyst_panel: {rep.get('status')} calls={rep.get('calls', 0)} "
          f"proposed={rep.get('cells_proposed', 0)} donated="
          f"{(rep.get('donation') or {}).get('status')} {rep.get('why', '')}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
