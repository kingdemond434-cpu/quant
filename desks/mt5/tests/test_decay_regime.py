"""Regime-aware decay: BOCPD + Markov-switching, calibrated on simulated sleeves.

The detectors move decay_monitor's ladder one step, two-sided. These tests pin the CALIBRATION
(false fades on a healthy i.i.d. edge stay rare, breaks are caught, dead sleeves are not
rescued) so a threshold change that loosens either side reddens, plus the rails the adjuster
must never move.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import decay_monitor as M  # noqa: E402
from research import decay_regime as D  # noqa: E402

WIN, LOSS = 1.5, -1.0


def _iid(rnd: random.Random, p: float, n: int) -> list[float]:
    return [WIN if rnd.random() < p else LOSS for _ in range(n)]


def _faded_from_healthy(gen, n_sims: int = 200, seed: int = 11) -> tuple[int, int]:
    rnd = random.Random(seed)
    healthy = faded = 0
    for _ in range(n_sims):
        rs = gen(rnd)
        s = M.stats(rs)
        v, why = M.verdict(s)
        if v != "HEALTHY":
            continue
        healthy += 1
        v2, _, _ = D.adjust("s", v, why, s, D.classify(rs))
        faded += v2 == "FADE"
    return faded, healthy


def test_a_healthy_iid_edge_is_rarely_faded() -> None:
    faded, healthy = _faded_from_healthy(lambda r: _iid(r, 0.5, 40))
    assert healthy > 150
    assert faded / healthy <= 0.10, (faded, healthy)


def test_a_break_is_caught_while_the_ladder_still_reads_healthy() -> None:
    faded, healthy = _faded_from_healthy(
        lambda r: _iid(r, 0.55, 30) + _iid(r, 0.15, 10))
    assert healthy > 50
    assert faded / healthy >= 0.40, (faded, healthy)


def test_a_dead_sleeve_is_never_rescued_from_retirement() -> None:
    rnd = random.Random(7)
    retired = rescued = 0
    for _ in range(200):
        rs = _iid(rnd, 0.25, 30)
        s = M.stats(rs)
        v, why = M.verdict(s)
        if v != "RETIRE":
            continue
        retired += 1
        v2, _, _ = D.adjust("s", v, why, s, D.classify(rs))
        rescued += v2 != "RETIRE"
    assert retired > 20
    assert rescued / retired <= 0.05, (rescued, retired)


def test_too_few_trades_is_unmeasured_and_moves_nothing() -> None:
    rc = D.classify([LOSS] * (D.MIN_N - 1))
    assert rc["class"] == "UNMEASURED"
    assert D.adjust("s", "HEALTHY", "w", {"max_dd_r": 0.0}, rc)[0] == "HEALTHY"


def test_bocpd_finds_a_clean_break() -> None:
    rs = [WIN, LOSS] * 15 + [LOSS] * 8
    cp = D.bocpd(rs)
    assert cp["p_recent_break"] >= D.BREAK_P_RECENT
    assert cp["run_p_neg"] >= D.BREAK_P_NEG
    assert (cp["before_mean_r"] or 0) > 0
    assert D.classify(rs)["class"] == "STRUCTURAL_BREAK"


def test_markov_switching_reads_a_sticky_bad_state() -> None:
    rs = [WIN, WIN, LOSS] * 10 + [LOSS] * 10
    ms = D.ms2(rs)
    assert ms["win_bad"] < ms["win_good"]
    assert ms["sticky"] and ms["p_bad_now"] >= D.MS_P_BAD


def _rc(cls: str) -> dict:
    return {"class": cls, "why": "test"}


def test_transient_regime_softens_a_t_rule_retire_one_step() -> None:
    v, why, step = D.adjust("s", "RETIRE", "t", {"max_dd_r": -10.0}, _rc("TRANSIENT_REGIME"))
    assert (v, step) == ("FADE", "RETIRE->FADE")


def test_the_drawdown_rail_is_never_softened() -> None:
    v, _, step = D.adjust("s", "RETIRE", "dd", {"max_dd_r": -25.0}, _rc("TRANSIENT_REGIME"))
    assert v == "RETIRE" and step is None


@pytest.mark.parametrize("cls", ["STRUCTURAL_BREAK", "PERSISTENT_BAD_REGIME"])
def test_a_break_or_bad_regime_fades_a_healthy_sleeve(cls: str) -> None:
    assert D.adjust("s", "HEALTHY", "h", {"max_dd_r": 0.0}, _rc(cls))[0] == "FADE"


@pytest.mark.parametrize("cls", ["STRUCTURAL_BREAK", "PERSISTENT_BAD_REGIME", "STABLE"])
def test_nothing_else_retires_or_unfades(cls: str) -> None:
    assert D.adjust("s", "RETIRE", "r", {"max_dd_r": 0.0}, _rc(cls))[0] == "RETIRE"
    assert D.adjust("s", "FADE", "f", {"max_dd_r": 0.0}, _rc(cls))[0] == "FADE"


@pytest.mark.parametrize("name", ["gold_asia", "XAUUSD.asia", "GOLD_ASIA"])
def test_gold_asia_is_exempt_both_ways(name: str) -> None:
    for verdict, cls in (("RETIRE", "TRANSIENT_REGIME"), ("HEALTHY", "STRUCTURAL_BREAK")):
        v, _, step = D.adjust(name, verdict, "w", {"max_dd_r": 0.0}, _rc(cls))
        assert v == verdict and step is None


def test_the_monitor_falls_back_to_the_ladder_when_a_detector_raises(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_rs):
        raise ValueError("x")
    monkeypatch.setattr(D, "classify", boom)
    rc, why = M._regime("s", [WIN] * 20)
    assert rc is None and why is not None and why.startswith("UNMEASURED")
