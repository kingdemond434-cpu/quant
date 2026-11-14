"""VIX own-risk and GARCH arms, and the live wiring of the input re-test verdicts (2026-11-11)."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import input_arms as ia_lib  # noqa: E402
from libs.portfolio.latent_factors import CRISIS_SHARE_MAX  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence  # noqa: E402

ia = pytest.importorskip("research.input_ablation", reason="ships with the desk")
pa = pytest.importorskip("research.pf_allocator", reason="ships with the desk")


def _days(n: int, start: str = "2024-01-01") -> list[str]:
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _vix_world(n: int = 600, seed: int = 0):
    """High-VIX days are followed by the book's crashes; the rank is known a day early."""
    rng = np.random.default_rng(seed)
    days = _days(n)
    rank = rng.random(n)
    book = rng.normal(0.001, 0.01, n)
    for i in range(1, n):
        if rank[i - 1] >= 2 / 3 and rng.random() < 0.3:
            book[i] = -0.08
    return book, days, dict(zip(days, rank, strict=True))


def test_vix_share_is_two_sided() -> None:
    book, days, ranks = _vix_world()
    hi = next(d for d in reversed(days) if ranks[d] >= 0.9)
    lo = next(d for d in reversed(days) if ranks[d] <= 0.1)
    s_hi, d_hi = ia_lib.vix_crisis_share(book, days, ranks, hi, 0.06)
    s_lo, d_lo = ia_lib.vix_crisis_share(book, days, ranks, lo, 0.06)
    assert d_hi["status"] == "MEASURED" and s_hi > 0.06 and s_hi <= CRISIS_SHARE_MAX
    # A calm tercile whose measured crisis rate is below base LOWERS the share (two-sided), but
    # never below the log-mirrored floor.
    assert d_lo["status"] == "MEASURED" and s_lo < 0.06
    assert s_lo >= ia_lib.crisis_share_min(0.06) - 1e-12
    assert ia_lib.crisis_share_min(0.06) == pytest.approx(0.06 ** 2 / CRISIS_SHARE_MAX)


def test_vix_share_says_unmeasured_on_thin_or_missing_evidence() -> None:
    book, days, ranks = _vix_world(n=30)
    s, d = ia_lib.vix_crisis_share(book, days, ranks, days[-1], 0.06)
    assert s == 0.06 and d["status"] == "UNMEASURED"
    s, d = ia_lib.vix_crisis_share(book, days, {}, days[-1], 0.06)
    assert s == 0.06 and d["status"] == "UNMEASURED"


def test_vix_share_reads_only_the_previous_day() -> None:
    """A crash that the SAME day's VIX would 'predict' must not raise the share."""
    rng = np.random.default_rng(1)
    n = 600
    days = _days(n)
    rank = rng.random(n)
    book = np.where(rank >= 2 / 3, -0.08 * (rng.random(n) < 0.3), rng.normal(0.001, 0.01, n))
    ranks = dict(zip(days, rank, strict=True))
    hi = next(d for d in reversed(days) if ranks[d] >= 0.9)
    s, d = ia_lib.vix_crisis_share(book, days, ranks, hi, 0.06)
    assert d["status"] == "MEASURED"
    assert s < 0.10                               # same-day link is invisible to a lagged read


def test_garch_ratio_tracks_the_recent_volatility() -> None:
    rng = np.random.default_rng(2)
    calm_end = np.concatenate([rng.normal(0, 0.02, 300), rng.normal(0, 0.005, 60)])
    loud_end = np.concatenate([rng.normal(0, 0.005, 300), rng.normal(0, 0.03, 60)])
    r_calm, d_calm = ia_lib.garch_vol_ratio(calm_end)
    r_loud, d_loud = ia_lib.garch_vol_ratio(loud_end)
    assert d_calm["status"] == "MEASURED" and r_calm is not None and r_calm < 1.0
    assert d_loud["status"] == "MEASURED" and r_loud is not None and r_loud > 1.0
    assert ia_lib.garch_vol_ratio(rng.normal(0, 1, 50))[0] is None


def test_rescale_keeps_the_mean_and_the_gaps() -> None:
    r = np.array([0.1, np.nan, -0.1, 0.3])
    out = ia_lib.rescale(r, 2.0)
    assert np.isnan(out[1])
    assert np.nanmean(out) == pytest.approx(np.nanmean(r))
    assert np.nanstd(out) == pytest.approx(2.0 * np.nanstd(r))


def test_ablate_hands_the_crisis_share_and_vol_ratio_to_the_solve() -> None:
    n = 270
    idx = _days(n)
    daily = pd.DataFrame({"A": np.linspace(-0.01, 0.01, n), "B": np.zeros(n) + 0.001},
                         index=idx)
    seen: dict[str, list] = {"crisis": [], "std": []}

    def evidence(hist):
        return [SleeveEvidence(name=c, daily_r=hist[c].to_numpy(dtype=float)) for c in hist]

    def arm_inputs(arm, asof, hist):
        if arm == "vix":
            return ia.ArmInputs(crisis_prob=0.2)
        if arm == "garch":
            return ia.ArmInputs(vol_ratio={"A": 3.0})
        return ia.ArmInputs()

    def solve(ev_t, cfg):
        seen["crisis"].append(cfg.crisis_prob)
        seen["std"].append(float(np.std(next(e for e in ev_t if e.name == "A").daily_r)))
        return {"A": 0.1, "B": 0.1}

    res = ia.ablate(daily, evidence, arm_inputs, solve=solve, arms=("plain", "vix", "garch"),
                    max_windows=1)
    assert res["n_windows"] == 1
    plain_c, vix_c, garch_c = seen["crisis"]
    assert vix_c == 0.2 and plain_c == garch_c != 0.2
    assert seen["std"][2] == pytest.approx(3.0 * seen["std"][0])


def test_the_desk_tests_every_input() -> None:
    assert set(ia.ARMS) >= {"plain", "regime", "macro", "vix", "garch"}
    assert "vix" not in ia.PIT_REQUIRED


def _daily(n: int = 400) -> pd.DataFrame:
    book, days, _ = _vix_world(n=n)
    return pd.DataFrame({"x": book}, index=days)


def test_vix_stays_shadow_until_a_terms_clean_source_exists() -> None:
    """#1023 audit HOLD: VIXCLS (Cboe via FRED) may not feed live sizing; a PROMOTE verdict is
    published with what it would do and moves nothing."""
    assert pa.INPUT_POLICY["vix"] == "shadow"
    daily = _daily()
    _, days, ranks = _vix_world(n=400)
    hi = next(d for d in reversed(days) if ranks[d] >= 0.9)
    out = pa.input_verdicts(daily, 0.06, verdict=lambda a: "PROMOTE" if a == "vix" else "X",
                            ranks=ranks, today=hi)
    assert out["inputs"]["vix"] == {"verdict": "PROMOTE", "policy": "shadow",
                                    "action": "switch on", "enforced": False}
    assert out["vix_share"] is None


def test_live_verdicts_enforce_macro_and_vix_and_shadow_hmm_and_garch(monkeypatch) -> None:
    # The enforce path itself, for when a terms-clean VIX source puts the arm back on.
    monkeypatch.setitem(pa.INPUT_POLICY, "vix", "enforce")
    daily = _daily()
    _, days, ranks = _vix_world(n=400)
    hi = next(d for d in reversed(days) if ranks[d] >= 0.9)
    v = {"macro": "DEMOTE", "vix": "PROMOTE", "regime": "DEMOTE", "garch": "PROMOTE"}
    out = pa.input_verdicts(daily, 0.06, verdict=v.__getitem__, ranks=ranks, today=hi)
    assert out["macro_off"] is True
    assert out["vix_share"] is not None and out["vix_share"] > 0.06
    assert out["inputs"]["regime"] == {"verdict": "DEMOTE", "policy": "shadow",
                                       "action": "switch off", "enforced": False}
    assert out["inputs"]["garch"]["enforced"] is False


def test_live_verdicts_change_nothing_without_a_verdict_or_a_fresh_vix(monkeypatch) -> None:
    monkeypatch.setitem(pa.INPUT_POLICY, "vix", "enforce")
    daily = _daily()
    _, days, ranks = _vix_world(n=400)
    out = pa.input_verdicts(daily, 0.06, verdict=lambda _a: "UNPROVEN", ranks=ranks,
                            today=days[-1])
    assert out["macro_off"] is False and out["vix_share"] is None
    assert not any(x["enforced"] for x in out["inputs"].values())
    late = (date.fromisoformat(days[-1]) + timedelta(days=10)).isoformat()
    out = pa.input_verdicts(daily, 0.06, verdict=lambda a: "PROMOTE" if a == "vix" else "X",
                            ranks=ranks, today=late)
    assert out["vix_share"] is None and out["vix"]["status"] == "UNMEASURED"
