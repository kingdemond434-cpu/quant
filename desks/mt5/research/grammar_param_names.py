"""THE COEVOLUTION GRAMMAR'S PARAMETER NAMES, TRANSLATED INTO EACH REGISTERED FAMILY'S OWN.

WHY THIS EXISTS (2026-11-13, measured). `research/sandboxes/coevolution_cell.py` names a survivor
by its dominant factor's registered family -- range position is `range_reversion`, an RSI is
`mean_reversion_rsi`, a z-score is `mean_reversion_bollinger` -- and then donated the GRAMMAR's
parameter names as the recipe: `{"w": 48}`, `{"fast": 8, "slow": 50}`, `{"h": 12}`. No family
takes any of them. Every such cell therefore died in the sealed judge's `build_cell` as

    range_reversion raised TypeError: family_range_reversion() got an unexpected keyword
    argument 'w'

and was parked as `build_failed`, re-asked every seven days (`BUILD_FAILED_RETRY_DAYS`), failed
again, forever. Reproduced on this tree through `external_gauntlet.build_cell` itself on a docket
row (`CHFJPY range_reversion {"representation": "external_engine", "w": 48}`); all seven ops of
the grammar fail the same way.

ONE TABLE, TWO READERS. The producer translates before it donates, so a new survivor is born
buildable; `conversion_handoff_consumer` translates a PARKED cell's params and re-emits the
repaired rule as a new cell tagged with its parent. A rule this table cannot translate FAITHFULLY
is refused by name -- never approximated into a different claim.
"""
from __future__ import annotations

from typing import Any

#: grammar op -> the registered family the producer names it under (mirrors
#: `coevolution_cell.FAMILY_OF_OP`; a test pins the two together).
FAMILY_OF_OP: dict[str, str] = {
    "ema_diff": "trend_ma_cross", "zscore": "mean_reversion_bollinger",
    "rsi": "mean_reversion_rsi", "range_pos": "range_reversion",
    "vol_ratio": "vol_mean_reversion", "volume_z": "volume_spike", "ret": "momentum_volgate",
}

#: family -> {grammar key: the family's own keyword}. Each is the SAME window the grammar
#: measured: a z-score's window is the Bollinger band's `bb_n`, an RSI's is `rsi_n`, a return
#: horizon is the momentum lookback `mom_n`, a volume z-score's window is `vol_lookback`, a
#: range position's window is the range lookback `range_n`, an EMA difference's two spans are the
#: two EMA spans.
PARAM_NAMES: dict[str, dict[str, str]] = {
    "trend_ma_cross": {"fast": "fast_ema", "slow": "slow_ema"},
    "mean_reversion_bollinger": {"w": "bb_n"},
    "mean_reversion_rsi": {"w": "rsi_n"},
    "range_reversion": {"w": "range_n"},
    "volume_spike": {"w": "vol_lookback"},
    "momentum_volgate": {"h": "mom_n"},
}

#: `vol_mean_reversion` takes ONE `lookback` and derives its short window as `lookback // 4`; the
#: grammar's vol ratio is std(w1) / std(w2). Only a pair with w1 == w2 // 4 is the same rule.
VOL_RATIO_FAMILY = "vol_mean_reversion"


def grammar_keys(family: str) -> frozenset[str]:
    """The grammar names a parked cell of `family` may carry instead of the family's own."""
    if family == VOL_RATIO_FAMILY:
        return frozenset({"w1", "w2"})
    return frozenset(PARAM_NAMES.get(family, {}))


def translate(family: str, params: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    """(params in the family's own names, why). None when there is nothing to translate or the
    translation would test a different claim; the reason says which.

    Keys that are not grammar names (the chart, the session, a label) ride through unchanged, and
    a family keyword the row already carries is never overwritten by a grammar alias."""
    p = dict(params or {})
    keys = grammar_keys(family)
    present = [k for k in sorted(keys) if k in p]
    if not present:
        return None, "no grammar parameter name on this row"
    if family == VOL_RATIO_FAMILY:
        try:
            w1, w2 = int(p["w1"]), int(p["w2"])
        except (KeyError, TypeError, ValueError):
            return None, "vol_ratio needs both w1 and w2"
        if w1 * 4 != w2:
            return None, (f"vol_ratio w1={w1}, w2={w2}: {VOL_RATIO_FAMILY} derives its short "
                          "window as lookback // 4, so only w1 == w2 // 4 is the same rule")
        p.pop("w1")
        p.pop("w2")
        p.setdefault("lookback", w2)
        return p, "w1/w2 -> lookback (w1 == lookback // 4)"
    names = PARAM_NAMES[family]
    moved = []
    for k in present:
        v = p.pop(k)
        if names[k] not in p:
            p[names[k]] = v
            moved.append(f"{k}->{names[k]}")
    return p, ", ".join(moved) or "grammar keys dropped (family keywords already present)"
