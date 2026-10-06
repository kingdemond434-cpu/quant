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
  2. Each of the four analysts (plus, on the CN analogues, TradingAgents-CN's China-market
     analyst) proposes cells in the desk's OWN grammar: one registered price-only
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
contaminated in a way a machine-drawn cell's is not, and no screen of history before `proposed_at`
is evidence. So a proposal is NEVER donated on the pass that proposes it: it waits in the panel's
forward clock (`state["pending"]`) and reads UNMEASURED until it has FORWARD_DAYS trading days
after `proposed_at`. Then it is screened on the signals after `proposed_at` alone (bars before it
only warm the indicators), and donated only if THAT screen clears cost on >= MIN_TRADES trades; a
matured cell that has the trades and does not clear is retired as FAILED_FORWARD. The donated row
carries `proposed_at`, `clean_from`, `hindsight_prior: true` and the bear's `red_team`, and the
compiler carries all four onto the candidate. (The gauntlet itself still judges the whole series;
cutting its development window at `clean_from` is a sealed-judge change queued for the desktop
pass, `patches/elitequant_absorption/gauntlet_clean_from_cut.patch`.)

TRIALS. Every idea a seat returned is a trial whether it was accepted, discarded by the grammar or
unexpressed, and so is every forward look at a matured cell. Each pass appends one row to
`data/analyst_panel_trials.jsonl` -- dark, refused and time-capped passes included -- which
`experiment_ledger` joins into the lifetime union. A pass that donates charges its count on the
discovery file instead and records 0 here, so nothing is counted twice.

CALLS. The pass runs inside `proposer_seat.seat_policy`: `--calls` caps HTTP REQUESTS (each model
the free panel rotates through is one), not asks, and the paid seat is refused unless
`--paid-budget` names how many paid requests the pass may make (default 0).

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
TRIALS = BASE / "data" / "analyst_panel_trials.jsonl"
MIN_TRADES = 30
#: Trading days after `proposed_at` before a proposal may be screened at all (the gauntlet's own
#: development-window floor), and how often a matured cell short of MIN_TRADES is looked at again.
FORWARD_DAYS = 60
RELOOK_DAYS = 7
#: Forward looks per pass, so a long pending queue cannot crowd out proposing.
MAX_LOOKS = 200
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
    # TradingAgents-CN's 中国市场分析师 (Apache-2.0 part of hsliuping/TradingAgents-CN): the A-share
    # lens, asked only about the CN analogues the desk can trade (CNH, China50/HK50, copper,
    # gold, oil). Its rows carry source_culture CN/zh.
    "china_market_analyst": ("retail_heavy",
                             "您是专业的中国市场分析师 (China market analyst). Propose cells whose "
                             "mechanism is how Chinese participants move this instrument: "
                             "涨跌停/T+1 overnight carry-over, 北向资金 northbound flow "
                             "days, policy announcements, the 09:30/13:00 Beijing session "
                             "opens, retail breakout chasing on 期货 futures, PBoC fixing "
                             "for CNH."),
}
#: Lenses asked only about some instruments, and the culture their rows carry.
LENS_ONLY: dict[str, Callable[[str], bool]] = {"china_market_analyst": lambda s: _cn_analogue(s)}
LENS_CULTURE: dict[str, str] = {"china_market_analyst": "CN/zh"}

#: The bear's vocabulary is the committees' failure classes, so an attack here and a committee
#: explanation there are the same kind of object.
FAILURE_CLASSES: tuple[str, ...] = ("COST_DEATH", "NO_EDGE", "SELECTION_BIAS", "STATE_FRAGILE",
                                    "LEAKAGE", "LOW_SAMPLE", "EXECUTION_FAILURE",
                                    "CORRELATION_DUPLICATE", "TAIL_FAILURE")


def _cn_analogue(symbol: str) -> bool:
    try:
        from mt5desk.families_cn_cta import CN_ANALOGUES
    except Exception:                                      # pragma: no cover - optional module
        return False
    return symbol.upper() in {a.upper() for a in CN_ANALOGUES}


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
    doc.setdefault("pending", {})
    doc.setdefault("retired", {})
    return doc


def debate(symbol: str, context: list[str], cat: Mapping[str, Mapping[str, Any]], *,
           ask: Callable[..., Any], left: Callable[[], int], n: int = 3
           ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """The four analysts propose, the bear attacks. Returns (cells, unexpressed, meter).

    `left()` is what the pass's call budget has left; no ask starts when it reads 0."""
    meter: dict[str, Any] = {"calls": 0, "trials_charged": 0.0, "by_analyst": {},
                             "ideas": 0, "attacks": 0, "reasons": Counter()}
    grammar, valid = _grammar(cat), _valid_cell(cat)
    cells: list[dict[str, Any]] = []
    unexpressed: list[dict[str, Any]] = []
    for role, (_, task) in ANALYSTS.items():
        if left() <= 0:
            meter.setdefault("why", "call budget spent")
            break
        if role in LENS_ONLY and not LENS_ONLY[role](symbol):
            continue
        reply = ask(ORGAN, "candidates", task=f"{task} Instrument: {symbol}.", grammar=grammar,
                    context=context, n=n, validate=valid)
        meter["calls"] += 1
        meter["trials_charged"] += float(getattr(reply, "trials_charged", 0.0) or 0.0)
        items = [i for i in (getattr(reply, "items", None) or []) if isinstance(i, dict)]
        discarded = int(getattr(reply, "discarded", 0) or 0)
        meter["ideas"] += len(items) + discarded
        meter["by_analyst"][role] = {"verdict": getattr(reply, "verdict", UNMEASURED),
                                     "accepted": len(items), "discarded": discarded}
        for why in getattr(reply, "reasons", []) or []:
            meter["reasons"][str(why)[:100]] += 1
        if getattr(reply, "verdict", UNMEASURED) != "RAN" and not meter["ideas"]:
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
    if cells and left() > 0:
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
        # A FALSIFIER ATTACK IS A LOOK TOO (audit PR166_v2; standing rule: any committee
        # falsifier counts as a trial): each attack the bear returned, plus any it returned that
        # failed validation, is charged alongside the analysts' ideas.
        meter["attacks"] += len(attacks) + int(getattr(reply, "discarded", 0) or 0)
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


def _post_days(d: Any, since: Any) -> int:
    """Trading days in `d` strictly after `since`."""
    after = d.index[d.index > since]
    return len(set(after.date)) if len(after) else 0


def _ts(at: str) -> Any:
    import pandas as pd
    t = pd.Timestamp(at)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def forward_screen(cell: Mapping[str, Any], d: Any, cost: float, fam_fn: Callable[..., Any],
                   ) -> dict[str, Any]:
    """The clean screen: the family's signals AFTER `proposed_at` only, on the same fill rules.

    Bars before `proposed_at` warm the indicators and are never evaluated. Returns
    {"post_days", "n_independent", "t_gross", "clears_cost", ...} or {"post_days": n} when the
    cell is still under FORWARD_DAYS."""
    from research import proposer_common as pc
    since = _ts(str(cell["proposed_at"]))
    days = _post_days(d, since)
    if days < FORWARD_DAYS:
        return {"post_days": days}
    sig = [s for s in (fam_fn(d, **cell["params"]) or []) if getattr(s, "time", since) > since]
    got = pc.screen(d, sig, cost) or {"n_independent": 0}
    return {**got, "post_days": days, "clean_from": str(cell["proposed_at"])}


def _charge(row: dict[str, Any]) -> None:
    """Append one pass's trial row. Never raises: a full disk must not stop the pass."""
    try:
        TRIALS.parent.mkdir(parents=True, exist_ok=True)
        with TRIALS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    except OSError:
        pass


def run(*, budget_s: float = 420.0, n_symbols: int = 1, calls: int = 10, dry_run: bool = False,
        only: Sequence[str] | None = None, ask: Callable[..., Any] | None = None,
        paid_budget: int = 0) -> dict[str, Any]:
    from contextlib import nullcontext

    from mt5desk import families_orthogonal as fo

    from research import proposer_common as pc
    from research.multiplicity import deflate_t

    started = time.monotonic()
    seat_why = ""
    policy: Any = nullcontext(None)
    if ask is None:
        try:
            from libs.research import proposer_seat as ps
        except Exception as exc:
            seat_why = f"proposer seat unimportable: {exc!r}"[:200]
        else:
            if ps.enabled():
                ask = ps.ask
                policy = ps.seat_policy(http_budget=calls, paid_budget=paid_budget)
            else:
                seat_why = "no seat resolves on this host; the desk runs as it does without it"
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
    spent = {"asks": 0}
    ideas = 0
    attacks = 0
    with policy as pol:
        def left() -> int:
            used = int(pol["http_calls"]) if pol is not None else spent["asks"]
            return max(0, calls - used)

        def counted(*a: Any, **k: Any) -> Any:
            spent["asks"] += 1
            return ask(*a, **k)  # type: ignore[misc]

        seen = 0
        while ask is not None and seen < min(n_symbols, len(pool)) and left() > 0 \
                and time.monotonic() - started < budget_s:
            sym = pool[int(state["cursor"]) % len(pool)]
            state["cursor"] = int(state["cursor"]) + 1
            seen += 1
            d = pc.bars(sym)
            if d is None or len(d) < MIN_BARS:
                meters[sym] = {"why": "bars absent or short"}
                continue
            cells, unexpressed, meter = debate(sym, describe(sym, d), cat, ask=counted,
                                               left=left)
            meters[sym] = meter
            ideas += int(meter["ideas"])
            attacks += int(meter.get("attacks") or 0)
            cost = pc.cost_frac(sym, meta, d["close"])
            for c in cells:
                c["proposed_at"] = at
                if cost is None:
                    c["screen"] = {"held_back": "no cost model"}
                    continue
                try:
                    fam_fn: Any = fo.ORTHOGONAL_FAMILIES[c["family"]]
                    # HINDSIGHT-CONTAMINATED: reported as the panel's tail, never donated on.
                    c["screen"] = pc.screen(d, fam_fn(d, **c["params"]), cost) \
                        or {"n_independent": 0}
                except Exception as exc:
                    c["screen"] = {"error": f"{type(exc).__name__}: {str(exc)[:80]}"}
            all_cells += cells
            all_unexpressed += unexpressed
            if meter.get("why") and not meter["ideas"]:
                break                                      # a dark seat stays dark this pass
        meter_http = dict(pol) if pol is not None else None

    # ---- the forward clock: queue this pass's cells, screen the matured ones after proposed_at
    queued = 0
    for c in all_cells:
        key = identity(c["symbol"], c["family"], c["params"])
        if key in state["cells"] or key in state["pending"] or key in state["retired"]:
            continue
        state["pending"][key] = {k: c.get(k) for k in (
            "symbol", "family", "params", "analyst", "mechanism", "falsifier", "proposed_at")}
        state["pending"][key]["red_team"] = c.get("red_team") or []
        state["pending"][key]["insample_t_gross"] = (c.get("screen") or {}).get("t_gross")
        queued += 1
    looks: Counter[str] = Counter()
    matured: list[tuple[str, dict[str, Any]]] = []
    forward: Counter[str] = Counter()
    frames: dict[str, Any] = {}
    now_ts = _ts(at)
    for key, p in sorted(state["pending"].items(), key=lambda kv: str(kv[1].get("proposed_at"))):
        if sum(looks.values()) >= MAX_LOOKS or time.monotonic() - started >= budget_s:
            forward["deferred"] += 1
            continue
        last = p.get("last_look")
        if last and (now_ts - _ts(str(last))).days < RELOOK_DAYS:
            forward["waiting_relook"] += 1
            continue
        if (now_ts - _ts(str(p["proposed_at"]))).days < FORWARD_DAYS:
            forward["under_forward_days"] += 1
            continue
        sym = str(p["symbol"])
        if sym not in frames:
            frames[sym] = pc.bars(sym)
        d = frames[sym]
        cost = None if d is None else pc.cost_frac(sym, meta, d["close"])
        fam_fn = fo.ORTHOGONAL_FAMILIES.get(str(p["family"]))
        if d is None or cost is None or fam_fn is None:
            forward["unreadable"] += 1
            continue
        try:
            fs = forward_screen(p, d, cost, fam_fn)
        except Exception as exc:
            p["forward_error"] = f"{type(exc).__name__}: {str(exc)[:80]}"
            forward["error"] += 1
            continue
        if "n_independent" not in fs:
            forward["under_forward_days"] += 1             # calendar-mature, bars not yet
            continue
        looks[str(p["family"])] += 1
        p["last_look"], p["forward_screen"] = at, fs
        n_ind = int(fs.get("n_independent") or 0)
        if n_ind >= MIN_TRADES and fs.get("clears_cost"):
            matured.append((key, p))
        elif n_ind >= MIN_TRADES:
            state["retired"][key] = {**p, "fate": "FAILED_FORWARD", "retired_at": at}
            forward["failed_forward"] += 1
        else:
            forward["short_of_trades"] += 1
    for key in state["retired"]:
        state["pending"].pop(key, None)

    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    tests_run = ideas + attacks + sum(looks.values())
    path = None
    if matured and not dry_run:
        rows = []
        for _, c in matured:
            fs = c["forward_screen"]
            row = pc.candidate(SOURCE, c["symbol"], c["family"], dict(c["params"]),
                               f"{c['mechanism']} Falsifier: {c['falsifier']}",
                               f"{c['symbol']} {c['family']} ({c['analyst']})",
                               {"screen_t_gross": fs.get("t_gross"),
                                "n_independent": fs.get("n_independent"),
                                "forward_days": fs.get("post_days"),
                                "insample_t_gross_contaminated": c.get("insample_t_gross"),
                                "origin": ORIGIN, "analyst": c["analyst"],
                                "red_team": c.get("red_team") or [],
                                "proposed_at": c["proposed_at"], "clean_from": c["proposed_at"],
                                "hindsight_prior": True})
            culture = {"source_culture": LENS_CULTURE.get(str(c["analyst"]), "GLOBAL/llm"),
                       "participant_structure": ANALYSTS[str(c["analyst"])][0],
                       "crowding_prior": "high",
                       "failure_mode_hypothesis": str(c["falsifier"])[:200]}
            row.update(culture)
            row["culture_derivation"] = dict.fromkeys(culture, "declared")
            rows.append(row)
        path = pc.donate(SOURCE, rows, tests_run)
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, "n": int(counts.get("donated") or 0),
                    "refused_wrong_lane": counts.get("refused_wrong_lane")}
        if path:
            for key, c in matured:
                state["cells"][key] = {
                    "donated_at": at, "analyst": c["analyst"], "symbol": c["symbol"],
                    "family": c["family"], "proposed_at": c["proposed_at"],
                    "t_gross_forward": c["forward_screen"].get("t_gross")}
                state["pending"].pop(key, None)

    by_family: Counter[str] = Counter(str(c["family"]) for c in all_cells)
    by_family["analyst_panel/unexpressed"] += len(all_unexpressed)
    by_family["analyst_panel/discarded"] += max(0, ideas - len(all_cells) - len(all_unexpressed))
    by_family["analyst_panel/falsifier_attacks"] += attacks
    by_family.update({f"{f}": k for f, k in looks.items()})
    by_family = Counter({f: k for f, k in by_family.items() if k})
    trial_row = {"at": at, "source": SOURCE, "ideas_proposed": ideas,
                 "falsifier_attacks": attacks,
                 "forward_looks": sum(looks.values()), "cells_screened": len(all_cells),
                 "asks": spent["asks"],
                 "http_calls": None if meter_http is None else meter_http["http_calls"],
                 "paid_calls": None if meter_http is None else meter_http["paid_calls"],
                 "trials_total": tests_run,
                 # charged ONCE: on the discovery file when this pass donated, else here
                 "tests_run": 0 if path else tests_run,
                 "charged_on": str(path) if path else "this_row",
                 "by_family": {} if path else dict(by_family), "dry_run": bool(dry_run)}
    if not dry_run:
        state["unexpressed"] = (state["unexpressed"] + all_unexpressed)[-500:]
        _atomic(STATE, state)
        _charge(trial_row)

    ts = [float(c["screen"]["t_gross"]) for c in all_cells
          if isinstance((c.get("screen") or {}).get("t_gross"), (int, float))
          and math.isfinite(c["screen"]["t_gross"])]
    by_analyst: dict[str, Counter[str]] = {a: Counter() for a in ANALYSTS}
    for c in all_cells:
        by_analyst[c["analyst"]]["proposed"] += 1
    for _, c in matured:
        by_analyst[str(c["analyst"])]["clears_forward_screen"] += 1
    for u in all_unexpressed:
        by_analyst[u["analyst"]]["unexpressed"] += 1
    best = max(ts, default=None)
    ran = any(a.get("verdict") == "RAN" for m in meters.values()
              for a in (m.get("by_analyst") or {}).values())
    why = seat_why or next((str(m["why"]) for m in meters.values() if m.get("why")), "")
    return {
        # A DARK SEAT IS NEVER OK: no analyst answered means the pass measured nothing new.
        "status": "OK" if ran else UNMEASURED,
        **({"why": why} if not ran and why else {}),
        "dry_run": bool(dry_run), "elapsed_s": round(time.monotonic() - started, 2),
        "calls": spent["asks"], "http": meter_http and {
            k: meter_http[k] for k in ("http_calls", "paid_calls", "refused_paid",
                                       "http_budget", "paid_budget")},
        "symbols": meters, "families_offered": len(cat),
        "cells_proposed": len(all_cells), "ideas_proposed": ideas,
        "by_analyst": {k: dict(v) for k, v in by_analyst.items()},
        "trials": trial_row,
        "forward_clock": {"queued_this_pass": queued, "pending": len(state["pending"]),
                          "pending_unmeasured": len(state["pending"]),
                          "forward_looks": sum(looks.values()), "matured": len(matured),
                          "retired_total": len(state["retired"]), **dict(forward),
                          "rule": (f"no proposal is donated until it has {FORWARD_DAYS} trading "
                                   "days after proposed_at, screened on its post-proposal "
                                   "signals only")},
        "screen_tails": {"n": len(ts), "t_gt_2": sum(t > 2 for t in ts),
                         "null_expected": round(0.0228 * len(ts), 2),
                         "best_t": best, "contaminated_by_hindsight": True,
                         "best_t_deflated_by_panel_lifetime": None if best is None else round(
                             deflate_t(best, max(len(ts), len(state["cells"])
                                                 + len(state["pending"])
                                                 + len(state["retired"]))), 3)},
        "candidates_this_pass": len(matured) if path else 0, "donation": donation,
        "unexpressed_this_pass": all_unexpressed,
        "unexpressed_total": len(state["unexpressed"]),
        "contract": ("the panel earns its calls by the ten gates' verdicts on its donated cells "
                     "against machine-drawn cells of the same families; its screen tails say only "
                     "whether it proposes better than a null of its size, and are contaminated by "
                     "hindsight. Only post-proposal evidence is donated on. Unexpressed mechanisms "
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
    ap.add_argument("--calls", type=int, default=10,
                    help="HTTP requests per pass (each rotated free model is one)")
    ap.add_argument("--paid-budget", type=int, default=0,
                    help="paid-seat requests this pass may make (default 0: never)")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = {"generated_at": _now(), "source": SOURCE,
           **run(budget_s=a.budget_s, n_symbols=a.symbols, calls=a.calls, dry_run=a.dry_run,
                 only=a.only, paid_budget=a.paid_budget)}
    if not a.dry_run:
        _atomic(OUT, rep)
    print(f"analyst_panel: {rep.get('status')} calls={rep.get('calls', 0)} "
          f"proposed={rep.get('cells_proposed', 0)} donated="
          f"{(rep.get('donation') or {}).get('status')} {rep.get('why', '')}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
