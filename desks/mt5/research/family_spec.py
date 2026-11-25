"""A PRODUCER'S STRUCTURED RULE, IN THE KEYWORDS THE FAMILY ACTUALLY READS -- or a named reason
why it has none.

THE DEFECT (measured on the trading box 2026-11-25). 28 sandbox generators had about 29.4k rows
in `research_candidates`, every one judged and none surviving. The sampled `sandbox:alpha101` row
carried its rule as PROSE in `exact_rules` and EMPTY params, so the gauntlet built the family's
DEFAULTS and judged those -- a cell the system never proposed. Other adapters wrote real numbers
under their OWN names (`fast`/`slow`, `window`/`k`, a factor's `w`), which no family reads: the
family is called with `**params`, so an unread keyword is either a build failure or, once a
repair strips it, the defaults again. Either way the judge slot and the trial were spent on
something that cannot represent the system's edge.

WHAT THIS IS. One small, declared translation from a producer's structured output to the
family's own keyword arguments, read off the family's signature (`mt5desk.families` /
`families_orthogonal`, the same functions the gauntlet calls) -- never a hand list of defaults
that can drift from the code. A value is coerced to the type of the family's default; anything
the family does not read is reported by name, never silently dropped.

THE VERDICTS (`to_executable`), and every one but EXECUTABLE is a NAMED non-executable:

    EXECUTABLE            at least one family argument differs from its default
    DEFAULTS_ONLY         nothing the family reads, or only its defaults restated: the judge
                          would score the family's defaults, not the system's rule
    PROSE_ONLY            no structured parameters at all; the rule exists only as text
    UNREGISTERED_FAMILY   the family is not one the desk can build
    SIGNATURE_UNREADABLE  the family's constructor cannot be inspected on this host

The same reading answers the guardian's question about rows ALREADY judged (`judged_quality`).
"""
from __future__ import annotations

import inspect
import json
import re
from functools import lru_cache
from typing import Any

EXECUTABLE = "EXECUTABLE"
DEFAULTS_ONLY = "DEFAULTS_ONLY"
PROSE_ONLY = "PROSE_ONLY"
UNREGISTERED_FAMILY = "UNREGISTERED_FAMILY"
SIGNATURE_UNREADABLE = "SIGNATURE_UNREADABLE"
NO_SYMBOLS = "NO_SYMBOLS"
NOT_EXECUTABLE = (DEFAULTS_ONLY, PROSE_ONLY, UNREGISTERED_FAMILY, SIGNATURE_UNREADABLE,
                  NO_SYMBOLS)

#: THE DECLARED TRANSLATION, per family: a producer's parameter name -> the family's keyword.
#: Only names whose MEANING is that keyword are listed (an EMA/SMA pair's two windows are the
#: cross's two windows; a z-score's window is the band's window). A name with no faithful target
#: is left unread and reported -- a guessed mapping would judge a rule nobody proposed.
ALIASES: dict[str, dict[str, str]] = {
    "trend_ma_cross": {"fast": "fast_ema", "slow": "slow_ema", "fast_n": "fast_ema",
                       "slow_n": "slow_ema"},
    "mean_reversion_bollinger": {"window": "bb_n", "w": "bb_n", "k": "bb_k", "n": "bb_n"},
    "volatility_squeeze": {"window": "bb_n", "k": "bb_k"},
    "mean_reversion_rsi": {"w": "rsi_n", "window": "rsi_n", "period": "rsi_n"},
    "pullback_entry": {"period": "rsi_n"},
    "range_reversion": {"w": "range_n", "window": "range_n"},
    "volume_spike": {"w": "vol_lookback", "window": "vol_lookback"},
    "momentum_volgate": {"h": "mom_n", "lookback": "mom_n"},
    "vol_mean_reversion": {"window": "lookback", "w": "lookback"},
    "drawdown_conditional": {"window": "lookback"},
    "overnight_drift": {"hold": "hold_bars"},
}
#: A single-window family's own window IS its lookback (and a Bollinger "period" is its window):
#: added 2026-11-25 for the discovery compiler's parents, whose seats name a window `lookback`.
#: `volatility_squeeze` is left out on purpose -- it has TWO windows (bands, squeeze history) and
#: a bare lookback does not say which.
for _fam, _target in (("mean_reversion_bollinger", "bb_n"), ("range_reversion", "range_n"),
                      ("volume_spike", "vol_lookback"), ("mean_reversion_rsi", "rsi_n"),
                      ("pca_residual", "window")):
    ALIASES.setdefault(_fam, {}).setdefault("lookback", _target)
ALIASES["mean_reversion_bollinger"].setdefault("period", "bb_n")

#: Keywords every family takes for risk geometry; restating only these is not a rule.
GEOMETRY_ONLY: frozenset[str] = frozenset({"atr_n", "rr", "ttl_bars", "stop_atr"})


@lru_cache(maxsize=256)
def _signature(family: str) -> tuple[tuple[str, Any], ...] | None:
    try:
        from mt5desk import families as fam
        from mt5desk import families_orthogonal as fo
    except Exception:
        return None
    entry: Any = getattr(fo, "ORTHOGONAL_FAMILIES", {}).get(family)
    if entry is None:
        entry = getattr(fam, "FAMILY_REGISTRY", {}).get(family)
        entry = entry.get("func") if isinstance(entry, dict) else entry
    if entry is None:
        entry = getattr(fam, f"family_{family}", None)
    if not callable(entry):
        return ()
    try:
        params = list(inspect.signature(entry).parameters.values())
    except (TypeError, ValueError):
        return None
    return tuple((p.name, p.default) for p in params
                 if p.kind is inspect.Parameter.KEYWORD_ONLY
                 and p.default is not inspect.Parameter.empty)


def signature(family: str) -> dict[str, Any] | None:
    """{keyword: default} the family reads; {} when it is not a family; None when unreadable."""
    got = _signature(str(family or ""))
    return None if got is None else dict(got)


def _coerce(value: Any, default: Any) -> tuple[bool, Any]:
    """(ok, value) cast to the type of the family's default, or (False, why)."""
    if value is None:
        return False, "null"
    try:
        if isinstance(default, bool):
            return (True, value) if isinstance(value, bool) else (False, "not a bool")
        if isinstance(default, int):
            f = float(value)
            if f != f or abs(f - round(f)) > 1e-9:
                return False, "not an integer"
            return True, round(f)
        if isinstance(default, float):
            f = float(value)
            return (True, f) if f == f else (False, "NaN")
        if isinstance(default, tuple):
            if isinstance(value, list | tuple):
                return True, tuple(value)
            return False, "not a sequence"
        if isinstance(default, str):
            return (True, value) if isinstance(value, str) and value else (False, "not a string")
    except (TypeError, ValueError):
        return False, f"cannot be read as {type(default).__name__}"
    return True, value


def to_executable(family: str, raw: Any, *, prose: str = "") -> dict[str, Any]:
    """The family's executable params from a producer's structured `raw`, with the verdict.

    Returns {"status", "params", "reason", "mapped", "unread"}. Only EXECUTABLE carries params a
    judge slot should be spent on."""
    family = str(family or "")
    sig = signature(family)
    out: dict[str, Any] = {"status": EXECUTABLE, "params": {}, "reason": "", "mapped": {},
                           "unread": []}
    if sig is None:
        out.update(status=SIGNATURE_UNREADABLE,
                   reason=f"the constructor of {family!r} cannot be inspected on this host")
        return out
    if not sig:
        out.update(status=UNREGISTERED_FAMILY,
                   reason=f"{family!r} is not a family the desk can build")
        return out
    src = dict(raw) if isinstance(raw, dict) else {}
    if not src:
        out.update(status=PROSE_ONLY if prose.strip() else DEFAULTS_ONLY,
                   reason=("the rule exists only as text: no structured parameter was emitted"
                           if prose.strip() else "no parameter was emitted at all"))
        return out
    alias = ALIASES.get(family, {})
    params: dict[str, Any] = {}
    unread: list[str] = []
    for k, v in src.items():
        key = k if k in sig else alias.get(k, "")
        if not key or key not in sig:
            unread.append(str(k))
            continue
        ok, val = _coerce(v, sig[key])
        if not ok:
            unread.append(f"{k} ({val})")
            continue
        if key in params and params[key] != val:
            unread.append(f"{k} (conflicts with an earlier {key})")
            continue
        params[key] = val
        if key != k:
            out["mapped"][str(k)] = key
    out["unread"] = unread
    differs = {k for k, v in params.items() if v != sig[k]}
    if not differs:
        out.update(status=DEFAULTS_ONLY, params=params,
                   reason=(f"none of {sorted(src)} is an argument of {family}"
                           if not params else
                           f"the declared {sorted(params)} restate {family}'s defaults"))
        return out
    if differs <= GEOMETRY_ONLY:
        out.update(status=DEFAULTS_ONLY, params=params,
                   reason=f"only risk geometry {sorted(differs)} differs from {family}'s "
                          f"defaults; its signal is the default one")
        return out
    out["params"] = params
    return out


def judged_quality(family: Any, params_json: Any, prose: Any = "") -> str:
    """EXECUTABLE / DEFAULTS_ONLY / PROSE_ONLY / UNMEASURED for a row already in the registry.

    UNMEASURED when the family cannot be read on this host or is not a constructor family
    (a non-family cell is not this test's to judge)."""
    if isinstance(params_json, dict):
        raw: Any = params_json
    else:
        try:
            raw = json.loads(params_json or "{}")
        except (TypeError, ValueError):
            raw = {}
    got = to_executable(str(family or ""), raw if isinstance(raw, dict) else {},
                        prose=str(prose or ""))
    st = got["status"]
    if st in (SIGNATURE_UNREADABLE, UNREGISTERED_FAMILY):
        return "UNMEASURED"
    return st


def carried_keys() -> frozenset[str]:
    """Keys a cell carries that are NOT the family's rule and must survive a translation: the
    transformation miners' variant keys (applied around the family by `cell_modifiers`) and the
    identity keys that name an input or a chart (`family_inputs.IDENTITY_KEYS`)."""
    try:
        from mt5desk.cell_modifiers import MODIFIER_KEYS
        from mt5desk.family_inputs import IDENTITY_KEYS
    except Exception:
        return frozenset({"session", "timeframe", "regime", "side_mode", "conditioner",
                          "representation", "residual", "residual_tag", "entry_timing",
                          "execution_style", "macro_axis", "macro_state", "peer_symbol",
                          "factor_symbols", "input_symbol", "input_source", "cost_aware"})
    return frozenset(MODIFIER_KEYS | IDENTITY_KEYS)


def translate(family: str, params: Any, *, prose: str = "") -> dict[str, Any]:
    """`to_executable` plus the cell's CALL params: the family's own keywords (producer names
    renamed through ALIASES) with the variant and identity keys carried unchanged. A key that is
    neither is dropped from the call and named in `unread` -- the gauntlet refuses an unknown
    keyword as NOT_RUN, so carrying it would only spend a judge slot to learn that.

    Returns the `to_executable` dict with `call` added. On an unreadable signature `call` is the
    params exactly as given: nothing is renamed or dropped on a host that cannot read the family."""
    src = dict(params) if isinstance(params, dict) else {}
    sig = signature(family)
    if sig is None:
        got = to_executable(family, src, prose=prose)
        got["call"] = src
        return got
    keep = carried_keys()
    # A keyword the family itself reads stays in the rule even when it is also a variant key
    # (`side_mode` is an argument of cross_asset_residual): the family, not this module, owns it.
    rule = {k: v for k, v in src.items() if k in sig or k not in keep}
    got = to_executable(family, rule, prose=prose)
    if src and not rule and got["status"] in (PROSE_ONLY, DEFAULTS_ONLY):
        # Params WERE emitted, just none of the family's: DEFAULTS_ONLY, as `to_executable`
        # reads the same row (the funnel's verdict), whatever prose rides beside it.
        got.update(status=DEFAULTS_ONLY,
                   reason=f"only variant / identity keys {sorted(src)} were emitted, so the "
                          "family would run at its defaults")
    call = dict(got["params"])
    call.update({k: v for k, v in src.items() if k in keep and k not in rule})
    got["call"] = call
    return got


#: `name=value` / `name: value` stated in a rule's text, and the indicator-call forms whose
#: argument IS a named window (`RSI(14)` is rsi_n=14). Nothing else in prose is read as a number:
#: "20-day" says nothing about which argument it sets, and a guessed mapping would judge a rule
#: nobody proposed.
_KV = re.compile(r"\b([a-z][a-z0-9_]{0,31})\s*[=:]\s*(-?\d+(?:\.\d+)?)(?![\w.])")
_CALL = {"rsi": "rsi_n", "bollinger": "bb_n", "bb": "bb_n", "atr": "atr_n"}
_CALL_RE = re.compile(r"\b(rsi|bollinger|bb|atr)\s*\(\s*(\d+)\s*[,)]", re.IGNORECASE)


def stated_numbers(text: Any) -> dict[str, Any]:
    """The parameters a rule's text STATES by name, as {name: number}; {} when it states none."""
    out: dict[str, Any] = {}
    s = str(text or "")
    for name, num in _CALL_RE.findall(s):
        out.setdefault(_CALL[name.lower()], int(num))
    for name, num in _KV.findall(s):
        val: Any = float(num) if "." in num else int(num)
        out.setdefault(name, val)
    return out
