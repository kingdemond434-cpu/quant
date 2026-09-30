"""The UNKNOWN-share census is reproducible, reads the judge's scale, counts judged cells."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "scripts"), str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import unknown_share_census as usc  # noqa: E402


def test_wilson_interval_brackets_the_share_and_is_none_on_no_cells() -> None:
    lo, hi = usc.wilson(191, 549) or (None, None)
    assert lo is not None and hi is not None
    assert lo < 191 / 549 < hi and 0.30 < lo < 0.35 < hi < 0.40
    assert usc.wilson(0, 0) is None, "no judged cells is UNMEASURED, never 0%"
    assert usc.wilson(0, 10)[0] == 0.0 and usc.wilson(10, 10)[1] == 1.0


def test_the_census_classifies_on_the_judges_own_scale() -> None:
    """Same rule, same names as the sealed judge's `classify_unknown` (patch
    unknown_verdict_named), so a reading against an unpatched judge is comparable."""
    idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
    empty = pd.Series([], dtype=float)
    assert usc.classify(None, None, 5, errored=True) == "series_exception"
    assert usc.classify(None, None, None) == "no_series"
    assert usc.classify(empty, 219, 400) == "lockbox_consumed_history"
    assert usc.classify(empty, 0, 0) == "no_signals"
    assert usc.classify(empty, 0, 7) == "signals_no_trades"
    assert usc.classify(empty, 0, None) == "no_trades"
    assert usc.classify(pd.Series([0.1, 0.2], index=idx), 2, 9) == "too_rare"


def test_input_keys_match_the_compiler_that_completes_them() -> None:
    from research import discovery_compiler as dc
    from research import judge_coverage as jc
    want = dict(dc.PEER_KEY_BY_FAMILY)
    want.update(dict.fromkeys(dc.FACTOR_FAMILIES, "factor_symbols"))
    want.update({f: keys[0] for f, keys in dc.LEG_FAMILIES.items()})
    assert want == usc.INPUT_KEY == jc.REQUIRED_INPUT_KEY


def test_build_failures_aggregate_by_kind_not_by_symbol() -> None:
    k = usc.build_failure_kind
    assert k("no H4 bars for EURUSD") == k("no H4 bars for GBPUSD") == "no_bars:H4"
    assert k("formula raised TypeError: unexpected kwarg") == "family_raised:TypeError"
    assert k("factor basket incomplete: no H1 bars for X") == "factor_basket_incomplete"
    assert k("NOT_RUN_MODIFIER: regime='risk_off'") == "modifier_refused"
    assert k("relative_value: no peer_symbol on the candidate") == "no_peer_symbol_named"
    assert k("no H1 bars for peer FOO") == "no_bars_for_peer"


def test_the_sample_is_fixed_by_seed_whatever_the_row_order(tmp_path: Path) -> None:
    rows = [{"symbol": f"S{i}", "family": "trend_ma_cross", "params": {"fast": i}}
            for i in range(200)]
    rows.append(dict(rows[3]))                          # a duplicate row is one cell
    rows.append({"symbol": "S1", "family": "f", "timeframe": "M15", "params": {}})
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(rows), "utf-8")
    b.write_text(json.dumps(list(reversed(rows))), "utf-8")

    def _iter(p: Path):
        yield from json.loads(p.read_text("utf-8"))

    def _tf(params, family=""):
        return str((params or {}).get("timeframe") or "H1").upper()

    sa, na = usc.docket_sample(a, 25, 7, _iter, _tf)
    sb, nb = usc.docket_sample(b, 25, 7, _iter, _tf)
    assert na == nb == 201
    assert [c["key"] for c in sa] == [c["key"] for c in sb]
    assert len(sa) == 25
    other, _ = usc.docket_sample(a, 25, 8, _iter, _tf)
    assert [c["key"] for c in other] != [c["key"] for c in sa]
    full, _ = usc.docket_sample(a, 1000, 7, _iter, _tf)
    m15 = [c for c in full if c["sym"] == "S1" and c["family"] == "f"]
    assert m15 and m15[0]["timeframe"] == "M15", "the row's chart is folded into the cell"


def test_the_sample_is_sized_from_measured_memory() -> None:
    n_small, cap_small = usc.sized_sample(1_000.0, None)
    n_big, cap_big = usc.sized_sample(16_000.0, None)
    assert n_small < n_big and cap_small < cap_big
    assert usc.sized_sample(16_000.0, 50)[0] == 50
    assert usc.sized_sample(1_000.0, 10**9)[0] == n_small, "a request never exceeds the fit"


def test_judged_share_excludes_cells_that_never_reached_the_judge() -> None:
    recs = [
        {"stage": "gate0", "reason": "symbol_eligibility"},
        {"stage": "build_failed", "reason": "no_bars:H4"},
        {"stage": "built", "verdict": "judgeable", "tf": "H1"},
        {"stage": "built", "verdict": "UNKNOWN", "unknown_reason": "no_signals",
         "cause": "never_fires", "tf": "H1", "family": "f"},
        {"stage": "built", "verdict": "UNKNOWN", "unknown_reason": "too_rare",
         "cause": "too_rare", "tf": "H1", "family": "f", "sibling": True},
    ]
    s = usc.summarise(recs, siblings_too=False)
    assert s["judged_built"] == 2 and s["unknown"] == 1
    assert s["unknown_share_of_judged"] == 0.5
    assert s["build_failed"] == 1 and s["gate0_rejected"] == {"symbol_eligibility": 1}
    both = usc.summarise(recs, siblings_too=True)
    assert both["judged_built"] == 3 and both["unknown"] == 2
