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
    EXECUTABLE_VARIANT    the family's arguments are its defaults, but a variant the replay
                          really APPLIES around it is set to a non-neutral value: a session
                          window (asia / london / ny), a volatility or calendar regime, a side
                          (revert / long / short), a delayed entry, a session selector, a wired
                          `alt:` conditioner. A London-only breakout is a different, testable rule
                          from the all-hours one. TESTABLE, exactly like EXECUTABLE.
    UNHONOURED_VARIANT    a variant the replay REFUSES (`cell_modifiers.refusal`: residual,
                          a macro state, a publication-lagged transform, a regime or conditioner
                          with no desk definition, a non-market fill): the gauntlet records the
                          cell NOT_RUN whatever else it carries
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
EXECUTABLE_VARIANT = "EXECUTABLE_VARIANT"
UNHONOURED_VARIANT = "UNHONOURED_VARIANT"
NOT_EXECUTABLE = (DEFAULTS_ONLY, PROSE_ONLY, UNREGISTERED_FAMILY, SIGNATURE_UNREADABLE,
                  NO_SYMBOLS, UNHONOURED_VARIANT)
#: The verdicts a judge slot should be spent on. Every reader (funnel, judge_reach,
#: sandbox_runner, discovery_compiler, moat_candidate_compiler) tests membership HERE.
TESTABLE: tuple[str, ...] = (EXECUTABLE, EXECUTABLE_VARIANT)


def is_testable(status: Any) -> bool:
    return str(status or "") in TESTABLE

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


#: The replay's own vocabulary (`mt5desk.cell_modifiers`, `mt5desk.family_call.SESSIONS`),
#: copied here only as the fallback for a host where those modules cannot import.
_FALLBACK = {
    "MODIFIER_KEYS": frozenset({"regime", "side_mode", "entry_timing", "execution_style",
                                "entry_style", "representation", "cost_aware", "residual",
                                "residual_tag", "conditioner", "macro_axis", "macro_state",
                                "publication_lag_d", "transform", "selector"}),
    "NO_OP_REGIMES": frozenset({"", "unconditional", "all", "any"}),
    "APPLIED_REGIMES": frozenset({"high_vol", "high_volatility", "low_vol", "month_end",
                                  "quarter_end"}),
    "SESSIONS": frozenset({"asia", "london", "ny", "all"}),
}


@lru_cache(maxsize=1)
def _replay_vocab() -> dict[str, Any]:
    try:
        from mt5desk import cell_modifiers as cm
        from mt5desk.family_call import SESSIONS
    except Exception:
        return dict(_FALLBACK)
    return {"MODIFIER_KEYS": frozenset(cm.MODIFIER_KEYS),
            "NO_OP_REGIMES": frozenset(cm.NO_OP_REGIMES),
            "APPLIED_REGIMES": frozenset(set(cm.VOL_REGIMES) | set(cm.CALENDAR_REGIMES)),
            "SESSIONS": frozenset(SESSIONS), "alt": cm.alt_conditioner}


def read_variants(variants: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """({key: value} the replay APPLIES with a non-neutral effect, refusal-or-None).

    Mirrors `cell_modifiers.refusal` / `apply` and the gauntlet's `session_filter` key by key,
    WITHOUT touching disk: an `alt:` conditioner is honoured when it parses (whether its series is
    on THIS host is the compiler's `gate_executability`, a host fact, not the row's verdict).
    A neutral value (`regime=unconditional`, `side_mode=follow`, `session=all`, a label such as
    `representation`) changes nothing and is never a variant; a session name the filter does not
    know is IGNORED by it (every hour kept), so it is neutral too."""
    v = _replay_vocab()

    def low(x: Any) -> str:
        return str(x if x is not None else "").strip().lower()

    applied: dict[str, Any] = {}
    for key in ("residual", "residual_tag"):
        if key in variants:
            return applied, f"{key}={variants[key]!r}: the replay does not residualise"
    if "macro_axis" in variants or "macro_state" in variants:
        return applied, "a macro state: no point-in-time macro series is wired into the replay"
    if "publication_lag_d" in variants or "transform" in variants:
        return applied, "a publication-lagged transform: no PIT input series is wired for it"
    if "conditioner" in variants:
        alt = v.get("alt")
        text = str(variants["conditioner"] or "")
        ok = alt(text) is not None if alt else text.startswith("alt:")
        if not ok:
            return applied, (f"conditioner={variants['conditioner']!r}: no conditioning series "
                             "is wired for it")
        applied["conditioner"] = variants["conditioner"]
    if "selector" in variants:
        sel = low(variants["selector"])
        if sel not in v["SESSIONS"]:
            return applied, f"selector={variants['selector']!r}: no declared session window"
        if sel != "all":
            applied["selector"] = variants["selector"]
    if "regime" in variants:
        reg = low(variants["regime"])
        if reg in v["APPLIED_REGIMES"]:
            applied["regime"] = variants["regime"]
        elif reg not in v["NO_OP_REGIMES"]:
            return applied, f"regime={variants['regime']!r} has no desk definition"
    if "side_mode" in variants:
        side = low(variants["side_mode"])
        if side in ("revert", "long", "short"):
            applied["side_mode"] = variants["side_mode"]
        elif side not in ("", "follow"):
            return applied, f"side_mode={variants['side_mode']!r} has no declared meaning"
    if "entry_timing" in variants:
        timing = low(variants["entry_timing"])
        if timing == "delayed":
            applied["entry_timing"] = variants["entry_timing"]
        elif timing not in ("", "instant"):
            return applied, f"entry_timing={variants['entry_timing']!r} has no declared meaning"
    for key in ("execution_style", "entry_style"):
        if key in variants and low(variants[key]) not in ("", "market"):
            return applied, f"{key}={variants[key]!r}: the replay has no fill model for it"
    if "session" in variants:
        sess = low(variants["session"])
        if sess in v["SESSIONS"] and sess != "all":
            applied["session"] = variants["session"]
    return applied, None


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
    # THE VARIANTS, read the way the replay reads them: `session` is always popped and applied
    # as a window (never a family keyword), and a modifier key goes around the family only when
    # the family does not take it itself (`cell_modifiers.split`).
    mod_keys = _replay_vocab()["MODIFIER_KEYS"]
    variants = {k: v for k, v in src.items()
                if k == "session" or (k in mod_keys and k not in sig)}
    applied, refused = read_variants(variants)
    alias = ALIASES.get(family, {})
    params: dict[str, Any] = {}
    unread: list[str] = []
    for k, v in src.items():
        if k in variants:
            continue
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
    out["variants"] = dict(applied)
    full = {**params, **variants}         # the variants ride with the rule: the replay reads them
    if refused:
        out.update(status=UNHONOURED_VARIANT, params=full,
                   reason=f"the replay refuses {refused}; the gauntlet records it NOT_RUN")
        return out
    differs = {k for k, v in params.items() if v != sig[k]}
    if differs and not differs <= GEOMETRY_ONLY:
        out["params"] = full
        return out
    if applied:
        out.update(status=EXECUTABLE_VARIANT, params=full,
                   reason=f"{family} at its defaults under the applied variant "
                          f"{sorted(applied.items())}")
        return out
    if not differs:
        out.update(status=DEFAULTS_ONLY, params=full,
                   reason=(f"none of {sorted(src)} is an argument of {family} or an applied "
                           f"variant" if not params else
                           f"the declared {sorted(params)} restate {family}'s defaults"))
        return out
    out.update(status=DEFAULTS_ONLY, params=full,
               reason=f"only risk geometry {sorted(differs)} differs from {family}'s "
                      f"defaults; its signal is the default one")
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
    """Keys that NAME an input or a chart (`family_inputs.IDENTITY_KEYS`, minus `session`, which
    is a variant `to_executable` reads): carried into the call unchanged, never the rule."""
    try:
        from mt5desk.family_inputs import IDENTITY_KEYS
    except Exception:
        return frozenset({"timeframe", "peer_symbol", "factor_symbols", "input_symbol",
                          "input_source", "surface_generated_at", "fx_symbol"})
    return frozenset(IDENTITY_KEYS) - {"session"}


def with_cell_axes(params: Any, *, session: Any = "", chart: Any = "") -> dict[str, Any]:
    """The params a cell must carry for ITS OWN session window (and then its chart) to reach the
    replay. `miner_candidate_compiler.expand_axes` keeps a row whose params name `session` or
    `timeframe` exactly as given and fans every other row out over every session and chart -- so
    a child proposed for London, with London only in a top-level field, was judged in all four
    windows and its London variant never existed as such. Only a real window (asia / london /
    ny) is folded in; `all` leaves the fan-out exactly as it was. The chart rides along only with
    a folded session (H1 is the docket's unkeyed default), so nothing else loses its fan-out."""
    out = dict(params) if isinstance(params, dict) else {}
    sess = str(session or "").strip().lower()
    if sess in _replay_vocab()["SESSIONS"] and sess != "all" and "session" not in out:
        out["session"] = sess
        tf = str(chart or "").strip().upper()
        if tf and tf != "H1":
            out.setdefault("timeframe", tf)
    return out


def translate(family: str, params: Any, *, prose: str = "") -> dict[str, Any]:
    """`to_executable` plus the cell's CALL params: the family's own keywords (producer names
    renamed through ALIASES), the variants, and the identity keys carried unchanged. A key that is
    none of these is dropped from the call and named in `unread` -- the gauntlet refuses an
    unknown keyword as NOT_RUN, so carrying it would only spend a judge slot to learn that.

    THE SAME VERDICT as `to_executable` on the same params (the funnel's, judge_reach's and
    sandbox_runner's reading): identity keys are not arguments, so setting them aside changes
    nothing but the `unread` list. On an unreadable signature `call` is the params as given."""
    src = dict(params) if isinstance(params, dict) else {}
    sig = signature(family)
    if not sig:            # unreadable (None) or not a family ({}): the verdict says which
        got = to_executable(family, src, prose=prose)
        got["call"] = src
        return got
    keep = carried_keys()
    ident = {k: v for k, v in src.items() if k in keep and k not in sig}
    rule = {k: v for k, v in src.items() if k not in ident}
    got = to_executable(family, rule, prose=prose)
    if src and not rule and got["status"] in (PROSE_ONLY, DEFAULTS_ONLY):
        got.update(status=DEFAULTS_ONLY,
                   reason=f"only identity keys {sorted(src)} were emitted, so the family "
                          "would run at its defaults")
    call = dict(got["params"])
    call.update(ident)
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
