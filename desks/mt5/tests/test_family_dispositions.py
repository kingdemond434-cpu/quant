"""The fourteen family names the judge can never build: each has ONE named disposition.

Pins (a) the alias is an exact spelling of the registered family (signature, sleeve identity,
causality of the built signals), (b) the anti_* names are the sign-flipped twins of the scalp
lane's own signals and have no main-registry twin to alias, (c) every other name carries a
named never_judged_reason, and the docket keeps every row.
"""
from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import family_dispositions as fd  # noqa: E402

#: Measured in JUDGE_COVERAGE.json 2026-11-17: judged_total 0 on every reading, no builder.
NEVER_BUILT = ("anti_donchian_breakout", "anti_three_bar_momentum", "carry_rollover",
               "conditioning_model", "execution_microstructure", "fair_value_gap",
               "fx_fixing_flow", "macro_release", "ny_open@M15", "positioning_crowding",
               "regional_information", "relative_value_dislocation", "unknown",
               "volatility_shock")


def _registry() -> dict:
    from mt5desk import families
    from mt5desk import families_orthogonal as fo
    out = {n[len("family_"):]: getattr(families, n) for n in dir(families)
           if n.startswith("family_") and callable(getattr(families, n))}
    for k, v in fo.ORTHOGONAL_FAMILIES.items():
        out.setdefault(k, v)
    return out


def _identity(row: dict) -> str:
    p = row.get("params") or {}
    return json.dumps({"symbol": row.get("symbol"), "family": row.get("family"),
                       "params": {k: p[k] for k in sorted(p)}}, sort_keys=True, default=str)


def _bars(n: int, freq: str = "15min", seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-05", periods=n, freq=freq, tz="UTC")
    idx = idx[idx.dayofweek < 5][:n]
    close = 2000.0 + np.cumsum(rng.normal(0.0, 1.5, len(idx)))
    opn = np.r_[close[0], close[:-1]]
    hi = np.maximum(opn, close) + rng.uniform(0.1, 1.5, len(idx))
    lo = np.minimum(opn, close) - rng.uniform(0.1, 1.5, len(idx))
    return pd.DataFrame({"open": opn, "high": hi, "low": lo, "close": close,
                         "tick_volume": rng.uniform(50, 500, len(idx))}, index=idx)


def _sigs(signals) -> list[tuple]:
    return [(pd.Timestamp(s.time), int(s.side), round(float(s.stop), 8),
             round(float(s.target), 8)) for s in signals]


# ------------------------------------------------------------------ the table is whole and named
def test_every_unbuilt_family_has_exactly_one_named_disposition() -> None:
    table = fd.table()
    assert set(NEVER_BUILT) <= set(table)
    for fam in NEVER_BUILT:
        d = table[fam]
        assert d["disposition"] in (fd.ALIAS, fd.NEVER_JUDGED)
        assert d["never_judged_reason"] in fd.REASON_CODES
        assert d["why"]
        assert not (fam in fd.ALIASES and fam in fd.NEVER_JUDGED_FAMILIES)


def test_no_disposed_name_is_already_registered() -> None:
    """A name the judge can build needs no disposition; one here would hide a working family."""
    reg = _registry()
    assert not [f for f in fd.table() if f in reg]


def test_builder_needs_closure_names_a_real_closure_file() -> None:
    closure = set((_ROOT / "ops" / "money_closure.txt").read_text("utf-8").split())
    for fam, nj in fd.NEVER_JUDGED_FAMILIES.items():
        if nj.code == fd.BUILDER_NEEDS_CLOSURE_EDIT:
            assert nj.closure_file in closure, fam
            assert (_ROOT / str(nj.closure_file)).exists()


def test_mechanism_labels_map_to_several_expressions_never_one_alias() -> None:
    for lbl in fd.MECHANISM_LABELS:
        assert fd.never_judged_reason(lbl) == fd.MECHANISM_LABEL_NOT_A_RULE
        assert lbl not in fd.ALIASES
    assert len(fd.expressions_of("relative_value_dislocation")) > 1


# ----------------------------------------------------------------------------- the alias
def test_alias_target_is_registered_and_takes_every_base_param() -> None:
    reg = _registry()
    for name, alias in fd.ALIASES.items():
        fn = reg[alias.target]
        params = set(inspect.signature(fn).parameters)
        for k in alias.base_params:
            assert k in params or k == "timeframe", (name, k)


def test_ny_open_alias_matches_every_sleeve_identity_it_was_read_from() -> None:
    path = _DESK / "data" / "sleeve_registry.json"
    if not path.exists():
        pytest.skip("sleeve registry is box state, absent here")
    sleeves = json.loads(path.read_text("utf-8")).get("sleeves") or {}
    hits = {k: v["identity"] for k, v in sleeves.items()
            if isinstance(v, dict) and ".ny_open@M15" in k and v.get("identity")}
    if not hits:
        pytest.skip("no ny_open@M15 clock in this registry")
    for key, ident in hits.items():
        row = {"symbol": ident["symbol"], "family": "ny_open@M15", "params": {}, "parent": key}
        assert fd.ALIASES["ny_open@M15"].target == ident["family"]
        assert fd.alias_params(row) == ident["params"], key


def test_alias_descendant_keeps_original_overlays_variant_and_is_idempotent() -> None:
    orig = {"symbol": "XAUUSD", "family": "ny_open@M15",
            "params": {"timeframe": "H1", "entry_style": "limit"},
            "parent_ids": ["XAUUSD.ny_open@M15#rr=1.5_wait_bars=8"],
            "source": "graveyard_resurrection", "exp_r": 0.3}
    rows = [dict(orig)]
    snapshot = json.dumps(rows, sort_keys=True)
    now = datetime(2026, 11, 17, tzinfo=UTC)
    kids, rep = fd.alias_descendants(rows, identity=_identity, now=now)
    assert json.dumps(rows, sort_keys=True) == snapshot          # inputs never mutated
    assert rep["targets"] == 1 and rep["created"] == 1
    (kid,) = kids
    assert kid["family"] == "session_range_breakout"
    assert kid["params"] == {"timeframe": "H1", "range_start": 13, "range_end": 14,
                             "signal_at": 14, "wait_bars": 8, "ttl_bars": 12, "rr": 1.5,
                             "entry_style": "limit"}
    assert "exp_r" not in kid                                    # no evidence inherited
    assert kid["alias_descendant"]["alias_of"] == "ny_open@M15"
    again, rep2 = fd.alias_descendants(rows + kids, identity=_identity, now=now)
    assert again == [] and rep2["already_present"] == 1


def test_alias_builds_causal_signals() -> None:
    """A future bar never changes a past signal of the aliased cell."""
    fn = _registry()["session_range_breakout"]
    params = {k: v for k, v in fd.ALIASES["ny_open@M15"].base_params.items()
              if k != "timeframe"}
    full = _bars(4000)
    cut = full.index[2600]
    past = _sigs(fn(full.loc[:cut], **params))
    shocked = full.copy()
    after = shocked.index > cut
    shocked.loc[after, ["open", "high", "low", "close"]] *= 1.07
    late = [s for s in _sigs(fn(shocked, **params)) if s[0] <= cut - pd.Timedelta("1D")]
    early = [s for s in past if s[0] <= cut - pd.Timedelta("1D")]
    assert early, "the alias must fire on synthetic bars or the test proves nothing"
    assert late == early


# ------------------------------------------------------------------ the anti_* scalp twins
def test_anti_twins_are_exact_sign_flips_and_have_no_main_lane_twin() -> None:
    from desks.mt5.research import scalp_family_expansion as sfe
    bars = _bars(3000)
    sig = sfe._base_signals(bars)
    for base in ("donchian_breakout", "three_bar_momentum"):
        assert np.array_equal(sig[f"anti_{base}"], -sig[base])
        assert np.any(sig[base] != 0)
        assert base not in _registry()           # nothing on the main lane to alias to


def test_anti_builder_direction_is_opposite_to_its_base_bar_for_bar() -> None:
    from mt5desk import scalp_families as sf
    bars = _bars(3000)
    kw = {"session": "all", "stop_atr": 1.0, "target_atr": 1.5, "max_hold": 6}
    for base in ("donchian_breakout", "three_bar_momentum"):
        b = {pd.Timestamp(s.time): s.side for s in sf.family_scalp(bars, family=base, **kw)}
        a = {pd.Timestamp(s.time): s.side for s in sf.family_scalp(bars, family=f"anti_{base}",
                                                                  **kw)}
        assert b and set(a) == set(b)
        assert all(a[t] == -b[t] for t in a)


def test_anti_builder_is_causal() -> None:
    from mt5desk import scalp_families as sf
    full = _bars(3000)
    cut = full.index[2000]
    kw = {"family": "anti_donchian_breakout", "session": "all", "stop_atr": 1.0,
          "target_atr": 1.5, "max_hold": 6}
    shocked = full.copy()
    shocked.loc[shocked.index > cut, ["open", "high", "low", "close"]] += 50.0
    a = [s for s in _sigs(sf.family_scalp(full, **kw)) if s[0] < cut]
    b = [s for s in _sigs(sf.family_scalp(shocked, **kw)) if s[0] < cut]
    assert a and a == b


def test_fair_value_gap_is_not_ict_fvg() -> None:
    """ict_fvg takes neither the gap filter nor the resting limit entry fair_value_gap needs."""
    sig = set(inspect.signature(_registry()["ict_fvg"]).parameters)
    assert not ({"min_gap_atr", "fill_depth", "wait_bars"} & sig)
    assert "ema_slow" in sig                                     # the trend filter it adds
    assert fd.never_judged_reason("fair_value_gap") == fd.BUILDER_NEEDS_CLOSURE_EDIT


# ------------------------------------------------------------------ rows are kept and named
def test_stamp_never_judged_keeps_every_row_and_names_the_reason() -> None:
    rows = [{"symbol": "EURUSD", "family": f, "params": {}} for f in NEVER_BUILT]
    rows.append({"symbol": "EURUSD", "family": "carry", "params": {}})
    census = fd.stamp_never_judged(rows)
    assert len(rows) == len(NEVER_BUILT) + 1
    assert census["stamped"] == len(NEVER_BUILT)
    assert "never_judged_reason" not in rows[-1]
    by = {r["family"]: r for r in rows}
    assert by["ny_open@M15"]["alias_of"] == "session_range_breakout"
    assert by["unknown"]["never_judged_reason"] == fd.NO_FAMILY_NAMED


def test_buildability_and_judge_coverage_name_the_reason() -> None:
    import gauntlet_buildability as gb

    from research import judge_coverage as jc
    gb.family_verdict.cache_clear()
    verdict, why = gb.family_verdict("conditioning_model")
    assert verdict == gb.NO_IMPLEMENTATION and fd.CONDITIONER_NOT_A_SLEEVE in why
    table = {"fair_value_gap": {"unjudged": 17}, "carry": {"unjudged": 3}}
    block = jc._never_judged_annotate(table)
    assert block["status"] == "MEASURED" and block["unjudged_named"] == 17
    assert table["fair_value_gap"]["never_judged_reason"] == fd.BUILDER_NEEDS_CLOSURE_EDIT
    assert "never_judged_reason" not in table["carry"]
