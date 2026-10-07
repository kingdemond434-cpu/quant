"""Written replication rules for `dav_range_filter_adx`, `hunt16_cell` and `carry`.

THE STALL THESE CLOSE (2026-09-30). The admission door holds a new certificate until the
replication lane says REPLICATED under its spec, and a family the spec book has no rule for can
only ever come back UNMEASURED -- held for ever. These three had none. Each test pins:

  * FIDELITY -- the lane's own rebuild, written from the rule text, emits exactly the orders the
    desk's implementation emits (the test may import the implementation; the lane may not);
  * THE GATE -- a certificate whose recorded Sharpe the rebuild reproduces is REPLICATED, one it
    contradicts is MISMATCH, and (when `admission_integrity` is on this tree) the door admits the
    first and holds the second.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

META = {"contract_size": 100000.0, "tick_size": 0.00001, "median_spread_pts": 5.0,
        "tick_value": 1.0}
TERMS = {"symbol": "TESTFX", "swap_mode": 1, "point": 0.00001, "contract_size": 100000,
         "swap_long": 5.0, "swap_short": -12.0}


def _frame(seed: int = 3, days: int = 260, start: float = 1.1, vol: float = 0.0015) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    c = start + np.cumsum(rng.normal(0, vol, len(idx)))
    df = pd.DataFrame({"open": c, "close": c + rng.normal(0, vol / 3, len(idx))}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) + rng.uniform(0, vol, len(idx))
    df["low"] = df[["open", "close"]].min(axis=1) - rng.uniform(0, vol, len(idx))
    return df


def _bars(df: pd.DataFrame) -> rc.Bars:
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy())


def _same(orig: list, ours: list) -> bool:
    return len(orig) == len(ours) and all(
        pd.Timestamp(o.time).value == q.t_ns and int(o.side) == q.side
        and abs(float(o.stop) - q.stop) < 1e-9 and abs(float(o.target) - q.target) < 1e-9
        and int(o.ttl_bars) == q.ttl_bars for o, q in zip(orig, ours, strict=True))


@pytest.fixture
def terms(monkeypatch):
    from mt5desk import families_orthogonal as fo
    monkeypatch.setattr(fo, "_swap_terms", lambda s: dict(TERMS))
    monkeypatch.setattr(rc, "swap_terms", lambda s, terms_dir=None: dict(TERMS))


def test_dav_range_filter_adx_and_day_labels_match_the_hunt16_code() -> None:
    from research.run_hunt12 import day_states
    from research.run_hunt16 import dav_range_filter_adx
    df = _frame()
    b = _bars(df)
    for side in (1, -1):
        assert _same(dav_range_filter_adx(df, side), rc._range_filter_adx_orders(b, side))
    want = {int(pd.Timestamp(d).value // 86_400_000_000_000): v
            for d, v in day_states(df).items()}
    assert want and rc._prior_ny_day_state(b) == want


def test_hunt16_cell_rule_matches_the_registered_family() -> None:
    from mt5desk import families_orthogonal as fo
    df = _frame(seed=11)
    params = {"base_family": "dav_range_filter_adx", "direction": "SHORT", "signal_at": 17,
              "day_state": "NORMAL_DAY"}
    orig = fo.family_hunt16_cell(df, side=1, **params)
    p, why = rc.resolve_spec("hunt16_cell", params, None, None)
    assert why == "ok"
    assert _same(orig, rc._build_hunt16_cell(_bars(df), p))


def test_carry_rule_matches_the_registered_family(terms) -> None:
    from mt5desk import families_orthogonal as fo
    df = _frame(seed=5)
    orig = fo.family_carry(df, symbol="TESTFX")
    p, _ = rc.resolve_spec("carry", {}, "continuous", None, symbol="TESTFX")
    ours = rc._build_carry(_bars(df), p)
    assert orig and _same(orig, ours)


def _cert(family: str, spec: dict[str, Any], sharpe: float) -> dict[str, Any]:
    return {"certificate": f"external.TESTFX.{family}.test", "cell": f"TESTFX.{family}",
            "shadow_spec": {"symbol": "TESTFX", "family": family, **spec},
            "gates": {"in_sample_screen": {"passed": True, "sharpe": sharpe}}}


CASES = [
    ("dav_range_filter_adx", {"side": "SHORT", "selector": "afternoon", "condition": None}),
    ("hunt16_cell", {"selector": "continuous", "params": {
        "base_family": "dav_range_filter_adx", "direction": "SHORT", "signal_at": 17,
        "day_state": None}}),
    ("carry", {"selector": "continuous", "params": {"symbol": "TESTFX"}}),
]


@pytest.mark.parametrize(("family", "spec"), CASES)
def test_a_replicating_certificate_passes_and_a_contradicted_one_is_held(
        family: str, spec: dict[str, Any], terms, tmp_path: Path) -> None:
    b = _bars(_frame(seed=21, days=320))
    probe = rc.replicate_certificate(_cert(family, spec, 1.0), meta=META, bars=b)
    ours = probe["ours"].get("sharpe")
    assert ours is not None and abs(ours) >= 2 * rc.SHARPE_NOISE, probe
    good = rc.replicate_certificate(_cert(family, spec, ours), meta=META, bars=b)
    bad = rc.replicate_certificate(_cert(family, spec, -ours), meta=META, bars=b)
    assert good["verdict"] == rc.REPLICATED, good
    assert bad["verdict"] == rc.MISMATCH, bad
    # THE DOOR ITSELF, where it exists on this tree (PR #67's admission_integrity): fed this
    # lane's verdict, it admits the replicated certificate and holds the contradicted one.
    try:
        import admission_integrity as ai
    except ImportError:
        return
    sp = {"symbol": "TESTFX", "family": family, **spec}
    fp = ai.spec_fingerprint("TESTFX", family, sp.get("selector"), sp.get("side"),
                             sp.get("params"))
    for row, admitted in ((good, True), (bad, False)):
        book = tmp_path / f"verdicts_{admitted}.json"
        cert = f"external.TESTFX.{family}.test"
        book.write_text(json.dumps({"certificates": {cert: {"verdict": row["verdict"],
                                                            "fp": fp}}}))
        gate = ai.IntegrityGate.load(placebo=tmp_path / "no_placebo.json", verdicts=book)
        held = gate.hold(cert, symbol="TESTFX", family=family, selector=sp.get("selector"),
                         side=sp.get("side"), params=sp.get("params"))
        assert (held is None) is admitted, held
