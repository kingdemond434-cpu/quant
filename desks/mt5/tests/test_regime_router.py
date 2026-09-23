"""REGIME ROUTER -- the claim is "alpha is state dependent", so these tests try to break it.

What is fenced here, and why each one is worth a test:

  * A PLANTED state dependence must be FOUND: positive R in high vol, negative in low vol, the
    bucket posteriors separating and the router earning its place out of sample after tax.
  * THE SAME MACHINE MUST STAY QUIET ON NOISE. A sleeve whose R owes the state nothing is the
    two-sided half of the rule: a router that activated there would hand the allocator a state
    story about a coin, and the zoo's tax exists so a mixture cannot buy its way in.
  * DRIFT FIRES ON A SHIFT AND ONLY ON A SHIFT. The permutation null is what separates "the
    state distribution moved" from "twenty trades landed differently"; an adaptation that fires
    on nothing is a refit spent on noise and a `representation_adapted: true` nobody can read.
  * THIN BUCKETS SHRINK TO THE UNCONDITIONAL, to the closed form -- two trades at +3R is the
    exact shape of a number someone would size on.
  * UNMEASURED SURVIVES: no ledger, no bars, no varying feature. Each is a verdict, not a zero.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.posterior_alpha import UNMEASURED  # noqa: E402

from libs.models.zoo import TAX  # noqa: E402
from research import regime_router as rr  # noqa: E402

BAR0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)          # a Monday, so the dow axis is readable
HOUR_NS = 3_600_000_000_000
DAY_NS = 24 * HOUR_NS
#: Realised-vol multiplier per block, cycling. Six distinct levels means the tercile cut fitted
#: on the pre-trade window lands BETWEEN them, so the two extremes label cleanly.
LEVELS = (0.25, 0.45, 0.8, 1.6, 2.8, 5.0)
#: 48 bars, so every offset whose trailing 24-bar vol window is wholly inside the block (24..47)
#: maps to a distinct hour of the day -- the session axis is then ours to set exactly.
BLOCK = 48
PRE_BLOCKS = 12                                        # pre-trade tape: two full level cycles
OFFSETS = (26, 30, 34)                                 # hours 2, 6 and 10 of the block's day
ASIA = (1, 2, 3)
NY = (16, 17, 18)
NOW = BAR0 + timedelta(hours=(PRE_BLOCKS + 60) * BLOCK)   # inside the tape, so bars are fresh


# ------------------------------------------------------------------------------ synthetic tape
def _h1_tape(n_blocks: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """An H1 close series whose realised vol cycles through LEVELS, one level per block."""
    rng = np.random.default_rng(seed)
    mult = np.repeat([LEVELS[b % len(LEVELS)] for b in range(n_blocks)], BLOCK)
    close = np.exp(np.cumsum(rng.normal(0.0, 1e-4, mult.size) * mult))
    return np.arange(mult.size, dtype="int64") * HOUR_NS + rr._ns(BAR0), close


def _d1_tape(n_days: int, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    close = np.exp(np.cumsum(rng.normal(0.0, 0.004, n_days)))
    return np.arange(n_days, dtype="int64") * DAY_NS + rr._ns(BAR0), close


def _when(index: int) -> datetime:
    return BAR0 + timedelta(hours=int(index))


def _offsets(hours: tuple[int, ...]) -> list[int]:
    """Block offsets landing on those hours of the day (BLOCK is a whole number of days)."""
    return [24 + hour for hour in hours]


def _planted(cycles: int = 10, seed: int = 7, hours: tuple[int, ...] | None = None,
             recent_hours: tuple[int, ...] | None = None, recent: int = 0,
             flat: bool = False) -> list[tuple[int, float]]:
    """Trades alternating a low-vol block and a high-vol block; R follows the vol unless `flat`.

    `recent_hours` moves the LAST `recent` trades into another session, so the state
    distribution shifts while the vol -> R rule is untouched. That is the only honest way to
    test the adaptation: it cannot be confounded with a change in what the router is scored on.
    """
    rng = np.random.default_rng(seed)
    offsets = list(OFFSETS) if hours is None else _offsets(hours)
    rows: list[tuple[int, float]] = []
    for cycle in range(cycles):
        base = PRE_BLOCKS + cycle * len(LEVELS)
        for kind, block in (("low", base), ("high", base + 5)):
            for off in offsets:
                mean = 0.0 if flat else (0.5 if kind == "high" else -0.5)
                rows.append((block * BLOCK + off, float(rng.normal(mean, 0.25))))
    rows.sort()
    if recent and recent_hours is not None:
        moved = _offsets(recent_hours)
        rows = rows[:-recent] + [(index // BLOCK * BLOCK + moved[i % len(moved)], value)
                                 for i, (index, value) in enumerate(rows[-recent:])]
        rows.sort()
    return rows


def _low_vol_only(cycles: int = 8, seed: int = 11) -> list[tuple[int, float]]:
    """Trades in low-vol blocks only, so a single high-vol bucket can be made deliberately thin."""
    rng = np.random.default_rng(seed)
    return [((PRE_BLOCKS + cycle * len(LEVELS)) * BLOCK + off, float(rng.normal(-0.2, 0.2)))
            for cycle in range(cycles) for off in OFFSETS]


@dataclass
class Desk:
    root: Path
    tapes: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)

    def live(self, name: str, symbol: str, trades: list[tuple[int, float]]) -> None:
        rr.SLEEVES.write_text(json.dumps({"sleeves": [
            {"name": name, "symbol": symbol, "status": "LIVE", "family": "planted"}]}), "utf-8")
        rows = [{"sleeve": name, "symbol": symbol, "r_multiple": value, "pl_quote": 10.0 * value,
                 "r_unreconstructible": False, "time": _when(index).isoformat()}
                for index, value in trades]
        rr.LIVE_LEDGER.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Desk:
    """An empty desk tree with every input path redirected and the tape seam under our hand."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    shadow, uni = reports / "shadow", data / "universe"
    for folder in (data, shadow, uni):
        folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rr, "SLEEVES", data / "sleeves.json")
    monkeypatch.setattr(rr, "LIVE_LEDGER", data / "live_ledger.jsonl")
    monkeypatch.setattr(rr, "SHADOW_DIR", shadow)
    monkeypatch.setattr(rr, "SHADOW_STATE", shadow / "shadow_state.json")
    monkeypatch.setattr(rr, "UNI", uni)
    monkeypatch.setattr(rr, "OUT", reports / "REGIME_ROUTER.json")
    out = Desk(tmp_path)
    out.tapes[("EURUSD", "H1")] = _h1_tape(PRE_BLOCKS + 70)
    out.tapes[("USDX", "H1")] = _h1_tape(PRE_BLOCKS + 70, seed=3)
    out.tapes[("US500", "D1")] = _d1_tape(240)
    monkeypatch.setattr(rr, "bars",
                        lambda symbol, timeframe="H1": out.tapes.get((symbol, timeframe)))
    rr.reset_caches()
    return out


def _row(payload: dict[str, Any], name: str) -> dict[str, Any]:
    return next(r for r in payload["sleeves"] if r["name"] == name)


# -------------------------------------------------------------- the planted edge must be found
def test_a_planted_state_dependence_separates_the_buckets_and_activates_the_router(
        desk: Desk) -> None:
    desk.live("planted_vol", "EURUSD", _planted())
    row = _row(rr.run(write=False, now=NOW), "planted_vol")

    assert row["n"] == 60 and row["lane"] == "live" and row["basis"] == "live_ledger"
    high, low = row["by_state"]["vol=high"], row["by_state"]["vol=low"]
    assert high["n"] == 30 and low["n"] == 30
    # The buckets separate THROUGH the shrinkage: both are pulled toward the sleeve's own
    # near-zero unconditional mean and still land on opposite sides of it.
    assert high["mu"] > 0.2 > -0.2 > low["mu"]
    assert high["p_positive"] > 0.95 and low["p_positive"] < 0.05
    assert abs(float(row["unconditional"]["mu"])) < 0.1

    router = row["router"]
    assert router["active"] is True
    assert router["k"] in rr.K_GRID and router["folds"] >= 2
    assert router["oos_logscore_routed"] > router["oos_logscore_unrouted"]
    assert router["net"] > 0 and router["tax"] == pytest.approx(TAX["soft_moe"])
    assert "vol_z" in router["features"]
    # The now-read is the ROUTER's: an expert is named and its gate mass is a distribution.
    assert row["p_alpha_positive_basis"] == "router_expert"
    assert sum(router["gate_now"]) == pytest.approx(1.0, abs=1e-6)
    assert router["active_expert"] == max(range(router["k"]), key=lambda j: router["gate_now"][j])
    assert row["p_alpha_positive_now"] == pytest.approx(
        router["experts"][router["active_expert"]]["p_positive"], abs=1e-9)


def test_a_sleeve_with_no_state_dependence_leaves_the_router_inactive(desk: Desk) -> None:
    """Two-sided honesty: the same trades, the same gate, R that owes the state nothing."""
    desk.live("no_signal", "EURUSD", _planted(flat=True))
    row = _row(rr.run(write=False, now=NOW), "no_signal")

    assert row["n"] == 60 and row["router"]["k"] in rr.K_GRID     # it WAS measured, not skipped
    assert row["router"]["active"] is False
    # AND THIS IS THE SHAPE THAT MATTERS. The mean OOS gain here is POSITIVE (+0.0005 nats) --
    # a SoftMoE will out-score the unrouted mean on a couple of folds of noise sooner or later,
    # and a rule reading only the sign of the mean would have routed a coin. The fold-level t
    # is what refuses it: the advantage does not clear its own standard error across folds.
    assert float(row["router"]["net"]) > 0.0
    assert float(row["router"]["t_gain"]) < rr.MIN_T_GAIN
    assert "unrouted mean explains it" in row["router"]["why"]
    # With no router the now-read falls back to the bucket the desk is actually standing in.
    assert row["p_alpha_positive_basis"] in ("state_bucket", "unconditional")
    assert row["representation_adapted"] is False


def test_the_active_router_prices_one_state_above_another_in_both_directions(desk: Desk) -> None:
    """The point of the organ: ONE sleeve, two prices, and the unconditional mean between them."""
    desk.live("planted_vol", "EURUSD", _planted())
    payload = rr.run(write=False, now=NOW)
    row = _row(payload, "planted_vol")

    ranked = sorted(row["router"]["experts"], key=lambda e: float(e["mu"]))
    assert float(ranked[0]["mu"]) < float(row["unconditional"]["mu"]) < float(ranked[-1]["mu"])
    assert float(ranked[-1]["p_positive"]) > 0.9 and float(ranked[0]["p_positive"]) < 0.1
    assert payload["rule"] == ("alpha value is state dependent; the router is active only where "
                              "it beats the unrouted model out of sample; never below the floor")


# ------------------------------------------------------------------------------ the drift half
def test_the_permutation_drift_test_fires_on_a_shift_and_not_without_one() -> None:
    steady = np.random.default_rng(0).normal(0.0, 1.0, (60, 4))
    calm = rr.drift(steady)
    assert float(calm["p"]) > rr.DRIFT_P

    shifted = steady.copy()
    shifted[-20:, 0] += 3.0
    moved = rr.drift(shifted)
    assert float(moved["p"]) <= rr.DRIFT_P and float(moved["t2"]) > float(calm["t2"])
    assert moved["n_recent"] == 20 and moved["n_past"] == 40
    assert moved["permutations"] == rr.DRIFT_PERMS
    assert "differs from its past" in moved["why"]

    thin = rr.drift(steady[:6])
    assert thin["p"] == UNMEASURED and thin["permutations"] == 0


def test_a_shifted_state_distribution_refits_the_gate_on_the_recent_window(desk: Desk) -> None:
    desk.live("drifting", "EURUSD", _planted(hours=ASIA, recent_hours=NY, recent=20))
    row = _row(rr.run(write=False, now=NOW), "drifting")

    assert row["router"]["active"] is True
    assert row["representation_adapted"] is True
    assert float(row["shift_stat"]["p"]) <= rr.DRIFT_P
    assert float(row["shift_stat"]["t2"]) > 0.0
    assert row["shift_stat"]["n_recent"] == rr.DRIFT_WINDOW
    assert row["router"]["fitted_on"] == "recent_window"


def test_a_stable_state_distribution_does_not_adapt(desk: Desk) -> None:
    desk.live("stable", "EURUSD", _planted(hours=ASIA))
    row = _row(rr.run(write=False, now=NOW), "stable")

    assert row["router"]["active"] is True
    assert row["representation_adapted"] is False
    assert float(row["shift_stat"]["p"]) > rr.DRIFT_P
    assert row["router"]["fitted_on"] == "all_trades"
    # A session held constant is a FLAT feature: dropped, never fed to the gate as a column of
    # ones for the optimiser to spend degrees of freedom on.
    assert not any(name.startswith("sess_") for name in row["router"]["features"])
    assert row["by_state"]["session=asia"]["n"] == row["n"]


# ------------------------------------------------------------------------------- the shrinkage
def test_a_thin_bucket_shrinks_to_the_unconditional_posterior(desk: Desk) -> None:
    """Two trades at +3R do not make a state; the closed form says exactly how much they make."""
    fat = [((PRE_BLOCKS + 5) * BLOCK + off, 3.0) for off in (30, 34)]
    desk.live("thin_bucket", "EURUSD", sorted(_low_vol_only() + fat))
    row = _row(rr.run(write=False, now=NOW), "thin_bucket")

    unconditional = float(row["unconditional"]["mu"])
    bucket = row["by_state"]["vol=high"]
    assert bucket["n"] == 2 and row["by_state"]["vol=low"]["n"] == 24
    # mu_bucket = (n0 * mu_unconditional + n * mean_bucket) / (n0 + n), to the published digit.
    expected = (rr.BUCKET_N0 * unconditional + 2 * 3.0) / (rr.BUCKET_N0 + 2)
    assert float(bucket["mu"]) == pytest.approx(expected, abs=1e-6)
    assert abs(float(bucket["mu"]) - unconditional) < 0.25 * abs(3.0 - unconditional)
    # 26 trades cannot reach the 24-trade router floor's fold geometry with a bucket this thin.
    assert row["router"]["active"] is False or float(row["router"]["net"]) > 0


# ---------------------------------------------------------------------------------- UNMEASURED
def test_an_empty_desk_is_unmeasured_rather_than_a_clean_zero(desk: Desk) -> None:
    payload = rr.run(write=False, now=NOW)

    assert payload["n_sleeves"] == 0 and payload["sleeves"] == []
    joined = " ".join(payload["unmeasured"])
    assert "live sleeve registry unreadable or absent" in joined
    assert "live fills unreadable or absent" in joined
    assert "forward clocks unreadable or absent" in joined
    assert "UNMEASURED, which is a verdict and not a zero" in joined


def test_an_axis_the_box_cannot_measure_is_dropped_not_imputed(desk: Desk) -> None:
    desk.tapes.clear()                                   # no USD proxy and no US500 to read
    desk.tapes[("AUDCAD", "H1")] = _h1_tape(PRE_BLOCKS + 70)
    desk.live("planted_vol", "AUDCAD", _planted())
    payload = rr.run(write=False, now=NOW)
    row = _row(payload, "planted_vol")

    joined = " ".join(payload["unmeasured"])
    assert "usd axis UNMEASURED" in joined and "risk axis UNMEASURED" in joined
    assert payload["state_sources"]["usd"] == UNMEASURED
    assert payload["current_state"]["usd"] == UNMEASURED
    assert "usd_trend" not in row["router"]["features"]
    assert "risk_sign" not in row["router"]["features"]
    assert not any(key.startswith(("usd=", "risk=")) for key in row["by_state"])
    assert row["router"]["active"] is True               # the vol axis still carries the edge


def test_a_symbol_with_no_bars_keeps_its_posterior_and_loses_its_vol_axis(desk: Desk) -> None:
    desk.live("no_bars", "GBPNOK", _planted(cycles=5))
    row = _row(rr.run(write=False, now=NOW), "no_bars")

    assert row["n"] == 30 and row["unconditional"]["n"] == 30
    assert not any(key.startswith("vol=") for key in row["by_state"])
    assert row["current_bucket"] == f"vol={UNMEASURED}"
    assert "vol_z" not in row["router"]["features"]


def test_a_thin_sleeve_is_published_with_its_router_unmeasured(desk: Desk) -> None:
    desk.live("young", "EURUSD", _planted(cycles=2))
    row = _row(rr.run(write=False, now=NOW), "young")

    assert row["n"] == 12 < rr.MIN_ROUTER_TRADES
    assert row["router"]["active"] is False
    assert row["router"]["oos_logscore_routed"] == UNMEASURED
    assert f"< {rr.MIN_ROUTER_TRADES} needed" in row["router"]["why"]
    assert row["by_state"]["vol=high"]["n"] == 6         # the posteriors are still published


def test_a_registry_sleeve_with_no_fill_is_counted_and_not_published(desk: Desk) -> None:
    rr.SLEEVES.write_text(json.dumps({"sleeves": [
        {"name": "idle", "symbol": "EURUSD", "status": "LIVE"}]}), "utf-8")
    payload = rr.run(write=False, now=NOW)

    assert payload["n_sleeves"] == 0
    assert payload["counts"]["sleeves_without_trades"] == 1


# ------------------------------------------------------------------------------- the evidence
def test_forward_clocks_contribute_forward_rows_only(desk: Desk) -> None:
    rr.SHADOW_STATE.write_text(json.dumps({"EURUSD.asia": {"status": "ACTIVE"}}), "utf-8")
    trades = _planted(cycles=5)
    rows = [{"exit_time": _when(i).isoformat(), "r_multiple": v, "phase": "forward"}
            for i, v in trades]
    rows += [{"exit_time": _when(i).isoformat(), "r_multiple": 99.0, "phase": "historical"}
             for i, _ in trades]
    (rr.SHADOW_DIR / "ledger_EURUSD_asia.json").write_text(json.dumps(rows), "utf-8")
    row = _row(rr.run(write=False, now=NOW), "EURUSD.asia")

    assert row["lane"] == "forward" and row["basis"] == "shadow_ledger_forward"
    assert row["n"] == len(trades)                       # historical rows are not evidence
    assert float(row["unconditional"]["mu"]) < 1.0


def test_an_unreconstructed_r_on_a_paying_fill_is_dropped(desk: Desk) -> None:
    desk.live("planted_vol", "EURUSD", _planted(cycles=5))
    paid = {"sleeve": "planted_vol", "symbol": "EURUSD", "r_multiple": 0.0, "pl_quote": 57.75,
            "r_unreconstructible": False, "time": _when(PRE_BLOCKS * BLOCK + 30).isoformat()}
    with rr.LIVE_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(paid) + "\n")
    payload = rr.run(write=False, now=NOW)

    assert _row(payload, "planted_vol")["n"] == 30
    assert payload["counts"]["live_rows_dropped"] == 1


# --------------------------------------------------------------------------------- the artifact
def test_the_cli_dry_run_prints_and_writes_nothing_then_the_real_pass_writes(
        desk: Desk, capsys: pytest.CaptureFixture[str]) -> None:
    desk.live("planted_vol", "EURUSD", _planted(cycles=5))

    assert rr.main(["--dry-run", "--limit", "3"]) == 0
    printed = capsys.readouterr().out
    assert "REGIME ROUTER" in printed and "planted_vol" in printed
    assert "(dry run, nothing written)" in printed
    assert not rr.OUT.exists()

    assert rr.main([]) == 0
    assert "written:" in capsys.readouterr().out
    payload = json.loads(rr.OUT.read_text("utf-8"))
    assert payload["rule"] == rr.RULE and payload["n_sleeves"] == 1
    assert set(payload) >= {"at", "n_sleeves", "current_state", "sleeves", "unmeasured", "rule"}
    assert set(payload["sleeves"][0]) >= {
        "name", "lane", "unconditional", "by_state", "router", "representation_adapted",
        "shift_stat", "current_bucket", "p_alpha_positive_now"}
    assert payload["router_spec"]["tax"] == pytest.approx(TAX["soft_moe"])
    assert payload["router_spec"]["model"] == "libs.models.router.SoftMoE"
