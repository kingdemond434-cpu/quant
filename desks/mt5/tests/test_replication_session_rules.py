"""The session of every non-window rule is the cell's own `session` parameter (plus a `selector`
modifier when the cell carries one), never the certificate's stamped selector -- checked against
the shared call the gauntlet, the clock and the executor use, which only this test may import.
And a hold raised under a rule that has since changed is re-judged ahead of the rotation."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

PARAM_SESSION = ["overnight_gap_decay", "dow_effect", "monday_gap", "mean_reversion_rsi",
                 "overnight_drift", "carry", "hunt16_cell", "formula", "cross_asset_residual"]


@pytest.mark.parametrize("family", PARAM_SESSION)
def test_the_session_is_the_cells_parameter_and_its_selector_modifier(family) -> None:
    spec = rc.SPEC_BOOK[family]
    assert spec.session_from_params and "own session parameter" in spec.text
    p, _ = rc.resolve_spec(family, {}, "asia", None)
    assert p is not None and p["_session"] is None          # the stamp is not a session
    p, _ = rc.resolve_spec(family, {"session": "london"}, "asia", None)
    assert p is not None and p["_session"] == (8, 16)
    p, _ = rc.resolve_spec(family, {"session": "london", "selector": "ny"}, "asia", None)
    assert p is not None and p["_session"] == (14, 16)      # the hours both allow
    p, _ = rc.resolve_spec(family, {"session": "asia", "selector": "london"}, "asia", None)
    assert p is not None and p["_session"] == (0, 0)        # none
    p, why = rc.resolve_spec(family, {"selector": "continuous"}, "asia", None)
    assert p is None and "names no session window" in why   # the gauntlet refuses it too


def test_a_hunt16_sweep_cells_selector_still_names_its_signal_hour() -> None:
    p, _ = rc.resolve_spec("dav_range_filter_adx", {"session": "london"}, "london_am", None)
    assert p is not None and p["_session"] is None and p["_selector"] == "london_am"


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 3000
    t = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 2e-3, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 4e-4, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 6e-4, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 6e-4, n)))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=t)


@pytest.mark.parametrize("family", ["dow_effect", "monday_gap", "mean_reversion_rsi",
                                    "overnight_drift"])
@pytest.mark.parametrize("params", [{"session": "london"}, {"session": "asia"},
                                    {"session": "all", "selector": "ny"}, {}])
def test_the_rebuild_keeps_the_hours_the_shared_call_keeps(family, params) -> None:
    from mt5desk import families
    from mt5desk.family_call import signals
    df = _frame()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        theirs = signals(getattr(families, f"family_{family}"), df, side=1, params=dict(params))
    bars = rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy())
    p, why = rc.resolve_spec(family, params, "asia", None)
    assert why == "ok" and p is not None
    ours, _ = rc.rebuild(family, bars, p, 0.0)
    assert theirs or params, "the planted bars must fire on every hour"
    assert [(int(pd.Timestamp(s.time).value), s.side) for s in theirs] == \
        [(o.t_ns, o.side) for o in ours]


def test_a_hold_raised_under_a_changed_rule_is_rejudged_ahead(tmp_path: Path,
                                                              monkeypatch) -> None:
    seen: list[str] = []

    def fake(row, *, meta, bars):
        seen.append(row["certificate"])
        return {"lane": "certificate", "key": row["certificate"], "family": "dow_effect",
                "certificate": row["certificate"], "verdict": rc.REPLICATED, "why": []}

    monkeypatch.setattr(rc, "replicate_certificate", fake)
    monkeypatch.setattr(rc, "certificate_fp", lambda r: "fp")
    monkeypatch.setattr(rc, "record", lambda rows, **_: {})      # no registry, no quarantine
    names = [f"R{i}" for i in range(6)] + ["OLD", "CURRENT", "PASSED"]
    certs = [{"certificate": k, "shadow_spec": {"symbol": "TESTFX", "family": "dow_effect"}}
             for k in names]
    base = {"fp": "fp", "sharpe_metric_version": rc.SHARPE_METRIC_VERSION, "why": ["x"]}
    book = {k: {**base, "verdict": rc.REPLICATED, "rule_fp": rc.rule_fingerprint("dow_effect")}
            for k in names[:6]}
    book["OLD"] = {**base, "verdict": rc.MISMATCH}                        # judged before the fix
    book["CURRENT"] = {**base, "verdict": rc.MISMATCH,
                       "rule_fp": rc.rule_fingerprint("dow_effect")}
    book["PASSED"] = {**base, "verdict": rc.REPLICATED}
    (tmp_path / rc.VERDICTS_NAME).write_text(json.dumps({"certificates": book}), "utf-8")
    doc = rc.build(certificates=certs, forward=[], universe_meta={},
                   bars_loader=lambda *_: None, cursor_path=tmp_path / "cursor.json",
                   dry_run=False, max_per_pass=2, report=tmp_path / "REPLICATION.json")
    assert seen[0] == "OLD" and "CURRENT" not in seen[:1] and "PASSED" not in seen[:1]
    assert doc["verdict_book"]["no_rule_backlog"] == 1
    saved = json.loads((tmp_path / rc.VERDICTS_NAME).read_text("utf-8"))["certificates"]
    assert saved["OLD"]["rule_fp"] == rc.rule_fingerprint("dow_effect")


def test_the_rule_fingerprint_moves_with_the_rule() -> None:
    a = rc.rule_fingerprint("dow_effect")
    assert a and a == rc.rule_fingerprint("dow_effect")
    assert rc.rule_fingerprint("cross_asset_residual") != rc.rule_fingerprint("formula")
    assert rc.rule_fingerprint("no_such_family") is None
