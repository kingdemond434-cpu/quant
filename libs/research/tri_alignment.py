"""Hypothesis, mechanism and code must be the same claim. Checked before a trial is spent.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

    Hypothesis: dealer gamma hedging causes continuation
    Code:       RSI < 30 -> buy
    -> REJECT. No backtest.

    Hypothesis: the London fix causes temporary imbalance
    Code:       uses today's completed daily high/low
    -> REJECT. Lookahead.

Neither of those is caught by any gate this desk runs. The gauntlet tests whether a SIGNAL
survives; it has no opinion on whether that signal is the one the hypothesis described. So a
candidate can carry an impeccable economic story, implement something completely unrelated, pass
ten gates on the strength of the implementation, and enter the book with a rationale that is
fiction. Every later decision -- what to allocate, what to mine next, what to retire when the
regime turns -- then rests on a mechanism that was never tested.

THIS IS THE CHEAPEST GATE IN THE FUNNEL and it runs first, on text and AST, before any bars are
loaded. Rejecting a misaligned candidate costs microseconds; discovering the misalignment after
certification costs a slot in the book and every conclusion drawn from it.

THREE CHECKS, EACH CATCHING A DIFFERENT FAILURE:

  MECHANISM->CODE   does the implementation reference anything the mechanism names? A gamma story
                    whose code mentions neither options, hedging, gamma, nor the close is not an
                    implementation of that story.
  CLOCK CONSISTENCY does a session/event claim actually condition on time? "The London fix causes
                    X" implemented without any time filter is not that claim.
  LOOKAHEAD         does the code use a completed-period aggregate the claim's horizon could not
                    have known? This is the specific error the blueprint names, and it is
                    invisible to a backtest that computes it the same wrong way every bar.

WHAT IT IS NOT. It is not a semantic model and does not judge whether the economics are RIGHT --
only whether the three descriptions are the same description. A wrong-but-aligned hypothesis
proceeds to the gauntlet, which is what the gauntlet is for.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

#: Mechanism vocabulary -> tokens an honest implementation of it would contain. Deliberately
#: generous: this must catch "gamma story, RSI code", not enforce a house style.
_MECHANISM_TOKENS: dict[str, tuple[str, ...]] = {
    # NOTE: bare "close" is deliberately ABSENT from both of these. It is an OHLC column name
    # that appears in essentially every strategy, so including it made the mechanism check pass
    # `signal = rsi(close, 14) < 30` as an implementation of a gamma-hedging story -- the exact
    # misalignment this module exists to catch. A token only discriminates if code that does NOT
    # implement the mechanism would lack it.
    "options_hedging": ("gamma", "vega", "hedge", "option", "iv", "implied", "expiry",
                        "dealer", "session_close", "final_"),
    "benchmark_flow": ("fix", "fixing", "benchmark", "rebalance", "window", "session_close"),
    "liquidity_shock": ("spread", "liquidity", "depth", "volume", "illiq", "impact"),
    "macro_release": ("event", "news", "surprise", "calendar", "release", "macro"),
    "session_transition": ("session", "hour", "open", "close", "asia", "london", "ny", "handoff"),
    "forced_deleveraging": ("margin", "liquidation", "unwind", "forced", "stop"),
    "inventory_rebalance": ("inventory", "rebalance", "position", "imbalance", "flow"),
    "volatility_shock": ("vol", "atr", "realized", "variance", "sigma", "range"),
    "carry_change": ("carry", "swap", "rate", "differential", "roll", "basis"),
    "cross_market_move": ("peer", "factor", "cross", "correlation", "lead", "lag", "resid"),
    "positioning_extreme": ("cot", "positioning", "crowd", "net_long", "net_short", "extreme"),
}

#: Session/time words that mean the claim is clock-bound and the code must be too.
_CLOCK_WORDS = re.compile(
    r"\b(fix|fixing|close|open|session|asia|tokyo|london|new york|ny|overnight|intraday|"
    r"final \d+|last \d+|first \d+)\b", re.I)

#: Attribute/call patterns that read a COMPLETED period aggregate. Using a daily high inside an
#: intraday claim means the bar being traded already knows how its own day ended.
_LOOKAHEAD = (
    re.compile(r"\.resample\(", re.I),
    re.compile(r"\bdaily_(high|low|close|open)\b", re.I),
    re.compile(r"\.groupby\([^)]*date[^)]*\)\s*\.\s*(max|min|last)\b", re.I),
    re.compile(r"\bshift\(\s*-\s*\d+", re.I),        # negative shift = reaching forward
)

#: Horizons for which a completed-DAY aggregate is a lookahead. A daily-horizon claim may
#: legitimately use daily bars; a 15m claim may not use its own day's completed range.
_INTRADAY = ("1m", "5m", "15m", "1h", "4h")


@dataclass(frozen=True)
class Alignment:
    ok: bool
    verdict: str          # PASS | REJECT
    reasons: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.ok


def _tokens_in(text: str) -> set[str]:
    return set(re.findall(r"[a-z_]{2,}", text.lower()))


def check(*, hypothesis: str, mechanism: str, code: str, horizon: str = "",
          coordinate_context: str = "") -> Alignment:
    """Do the story, the mechanism and the implementation describe one thing?

    `code` is the implementation SOURCE, not a path -- the check is on what will run.
    """
    reasons: list[str] = []
    code_l = code.lower()
    code_tokens = _tokens_in(code)

    # 1. MECHANISM -> CODE. The implementation must reference something the mechanism is about.
    expected = _MECHANISM_TOKENS.get(mechanism)
    if expected:
        hits = [t for t in expected if t in code_l]
        if not hits:
            reasons.append(
                f"mechanism '{mechanism}' appears nowhere in the implementation: none of "
                f"{list(expected)[:6]} occur in the code. An economic story the code does not "
                f"implement is a rationale for something that was never tested.")
    elif mechanism:
        reasons.append(
            f"mechanism '{mechanism}' is not in the known vocabulary, so alignment cannot be "
            f"checked. UNMEASURED is a real answer -- add it to _MECHANISM_TOKENS deliberately "
            f"rather than letting an unknown mechanism pass unchecked.")

    # 2. CLOCK CONSISTENCY. A claim about a session or a fix must condition on time.
    claims_clock = bool(_CLOCK_WORDS.search(hypothesis) or _CLOCK_WORDS.search(coordinate_context))
    if claims_clock:
        time_aware = any(t in code_tokens for t in
                         ("hour", "time", "index", "session", "between_time", "dt", "clock",
                          "window", "minute"))
        if not time_aware:
            reasons.append(
                "the hypothesis is clock-bound (it names a fix, session or close) but the "
                "implementation contains no time conditioning at all -- it is testing the claim "
                "at every hour, which is a different and weaker claim")

    # 3. LOOKAHEAD against the claim's own horizon.
    if horizon in _INTRADAY:
        for pat in _LOOKAHEAD:
            if pat.search(code):
                reasons.append(
                    f"intraday horizon '{horizon}' with a completed-period aggregate "
                    f"({pat.pattern}) -- the bar being traded would already know how its own "
                    f"period ended. This passes a backtest because the backtest makes the same "
                    f"error on every bar.")
                break

    if reasons:
        return Alignment(False, "REJECT", tuple(reasons))
    return Alignment(True, "PASS", ("hypothesis, mechanism and implementation describe one claim",))


def check_source_file(path: str, *, hypothesis: str, mechanism: str,
                      horizon: str = "", coordinate_context: str = "") -> Alignment:
    """Same check over a file, with a parse failure treated as a REJECT rather than a pass."""
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        ast.parse(src)
    except (OSError, SyntaxError) as exc:
        return Alignment(False, "REJECT",
                         (f"implementation could not be read or parsed ({type(exc).__name__}); "
                          f"an unreadable implementation cannot be aligned with anything, and "
                          f"absence is never permission",))
    return check(hypothesis=hypothesis, mechanism=mechanism, code=src, horizon=horizon,
                 coordinate_context=coordinate_context)
