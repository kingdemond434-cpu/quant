"""The vol-control / risk-parity estimator: the math on synthetic prices, PIT, charge-once."""
from __future__ import annotations

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

import volcontrol_flow as vc  # noqa: E402


def _prices(n: int = 900, vols: tuple[float, float] = (0.08, 0.40), seed: int = 1,
            jump_at: int = 600) -> pd.Series:
    rng = np.random.default_rng(seed)
    daily = np.where(np.arange(n) < jump_at, vols[0], vols[1]) / np.sqrt(252)
    r = rng.standard_normal(n) * daily
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    return pd.Series(100 * np.exp(np.cumsum(r)), index=idx)


def test_exposure_is_target_over_vol_capped() -> None:
    v = pd.Series([0.05, 0.10, 0.20, 0.40])
    e = vc.vol_target_exposure(v, target=0.10, cap=1.5)
    assert list(e.round(6)) == [1.5, 1.0, 0.5, 0.25]


def test_ewma_vol_recovers_the_true_vol() -> None:
    p = _prices(n=1500, vols=(0.16, 0.16))
    v = vc.ewma_vol(np.log(p).diff(), 63).dropna()
    assert v.iloc[-500:].mean() == pytest.approx(0.16, rel=0.15)


def test_a_vol_jump_forces_selling() -> None:
    est = vc.estimate(_prices())
    before = est["exposure"].iloc[550:600].mean()
    after = est["exposure"].iloc[700:].mean()
    assert before == pytest.approx(1.25, abs=0.3)    # 10% / 8%, under the 1.5 cap
    assert after == pytest.approx(0.25, abs=0.12)    # 10% / 40%
    flow = est["flow"].iloc[600:640]
    assert flow.sum() < -0.5 and flow.min() < 0
    assert est["flow_z"].iloc[600:640].min() <= -2.0


def test_estimate_is_causal() -> None:
    p = _prices()
    full = vc.estimate(p)
    cut = vc.estimate(p.iloc[:650])
    pd.testing.assert_frame_equal(full.iloc[:650], cut, check_freq=False)


def test_available_time_is_never_before_the_close() -> None:
    idx = pd.DatetimeIndex(["2026-07-01", "2026-12-01"], tz="UTC")
    at = vc.available_time(idx)
    # broker close is D+1 00:00 broker = D 21:00 UTC (summer) / 22:00 UTC (winter)
    assert at[0] >= pd.Timestamp("2026-07-01 21:00", tz="UTC")
    assert at[1] >= pd.Timestamp("2026-12-01 22:00", tz="UTC")


def test_risk_parity_sheds_equity_when_equity_vol_rises() -> None:
    eq = _prices(seed=1)
    bond = _prices(vols=(0.05, 0.05), seed=2)
    gold = _prices(vols=(0.15, 0.15), seed=3)
    rp = vc.risk_parity({"US500": eq, "UST10Y": bond, "XAUUSD": gold}, equity="US500")
    assert rp is not None
    assert rp["rp_equity_exposure"].iloc[700:].mean() < rp["rp_equity_exposure"].iloc[500:600].mean()


def _loader(have: dict[str, pd.Series]):
    return lambda s: have.get(s)


def test_run_writes_frame_and_charges_each_hypothesis_once(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SERIES", "SIDECAR", "VINTAGES"):
        monkeypatch.setattr(vc, name, tmp_path / Path(str(getattr(vc, name))).name)
    monkeypatch.setattr(vc, "EMITTED", tmp_path / "emitted.jsonl")
    monkeypatch.setattr(vc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(vc, "DESK", tmp_path)
    monkeypatch.setattr(vc, "_lane", lambda s: True)
    have = {"US500": _prices(seed=1), "GER40": _prices(seed=4), "UST10Y": _prices(seed=2),
            "XAUUSD": _prices(seed=3)}
    emit_calls = []
    real_emit = vc.emit

    def spy(specs, now, **kw):
        emit_calls.append(len(specs))
        return real_emit(specs, now, emitted_path=vc.EMITTED, intel_dir=vc.INTEL)

    monkeypatch.setattr(vc, "emit", spy)
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    doc = vc.run(now=now, loader=_loader(have), symbols=["US500", "GER40", "JPN225"],
                 out_path=tmp_path / "out.json")
    assert doc["status"] == "OK" and doc["unmeasured"]["JPN225"] == "no bars on disk"
    wide = pd.read_csv(tmp_path / "volcontrol_flow.csv")
    for c in ("available_time", "US500__flow", "US500__exposure", "GER40__flow_z",
              "RP__equity_flow"):
        assert c in wide.columns
    keys = {s["key"] for s in vc.specs(wide.columns, lambda s: True)}
    assert keys == {"volcontrol_flow_follow", "volcontrol_exposure_rebuild",
                    "volcontrol_fx_riskoff", "riskparity_flow_follow"}
    # 2 per index x 2 + 2 FX + 1 risk parity
    assert doc["hypotheses"]["donated"] == 7
    for k in range(3):
        again = vc.run(now=now.replace(hour=13 + k), loader=_loader(have),
                       symbols=["US500", "GER40", "JPN225"], out_path=tmp_path / "out.json")
        assert again["hypotheses"]["donated"] == 0
        assert again["hypotheses"]["already_emitted"] == 7
    assert len((tmp_path / "emitted.jsonl").read_text("utf-8").splitlines()) == 7
    rows = json.loads(next((tmp_path / "intel").glob("*.json")).read_text("utf-8"))
    assert all(r["family"] == "exogenous_conditioner" and r["params"]["lag_hours"] == 3
               for r in rows)
    # vintages are append-only and one per (symbol, day)
    vint = pd.read_csv(tmp_path / "volcontrol_flow_vintages.csv")
    assert len(vint) == 2


def test_conditioner_reads_the_frame(tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    p = _prices(seed=1)
    wide, _latest, _missing = vc.build(["US500"], _loader({"US500": p}))
    (tmp_path / "volcontrol_flow.csv").write_text(wide.to_csv(index=False), encoding="utf-8")
    h1 = pd.DataFrame({"open": p, "high": p * 1.001, "low": p * 0.999, "close": p})
    sig = family_exogenous_conditioner(h1, series_root=tmp_path,
                                       **vc._cond("US500__flow", +1, 2.0, 24))
    assert sig, "the jump's forced selling must fire the follow-the-flow cell"
    window = [s.side for s in sig if p.index[600] <= s.time <= p.index[650]]
    assert window and sum(1 for x in window if x == -1) > len(window) / 2
