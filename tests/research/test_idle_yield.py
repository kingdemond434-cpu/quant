"""Tests for the reachable-yield floor and idle-capital pricing (L1.51).

THE REGRESSIONS THESE EXIST TO CATCH, each one a defect that was live or one edit away:

  * `hurdle_rate.json:risk_free` is a PERIOD return, not an annual rate. Reading it raw
    understates the desk's idle cost by ~10.8x, silently, in the direction nothing alarms on.
  * A dollar cost derived from a MOLDED/SIMULATED equity curve looks exactly like a measurement.
    Every refusal path here asserts `None`, never `0.0` -- pricing idle capital at zero is the
    precise assumption L1.28a exists to destroy.
  * The lending rung's verdict is decided entirely by an underived 300bps constant. If a future
    edit lets the netted scalar hide the gross comparison, the desk loses the ability to notice
    the day the rungs cross.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research import idle_yield as iy


def _nav(root: Path, *, equity: float = 10_000.0, deployed: float = 0.0,
         n: int = 0, mode: str = "PAPER (testnet) -- pre-Gate-0", rows: int = 1) -> None:
    p = root / "data/nav_attestation.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(rows):
        out.append(json.dumps({
            "date": f"2026-08-0{i + 1}",
            "ts": (datetime.now(tz=UTC) - timedelta(days=rows - i)).isoformat(),
            "molded_curve_usd": equity, "equity_marked": equity,
            "deployed_notional": deployed, "n_carries": n, "mode": mode}))
    p.write_text("\n".join(out) + "\n", "utf-8")


def _live(root: Path, *, deployed: float = 0.0, n: int = 0) -> None:
    p = root / "web/cashcarry_live.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"deployed_notional": deployed, "n_carries": n}), "utf-8")


def _hurdle(root: Path, *, period: float = 0.0034663, days: float = 33.92) -> None:
    p = root / "data/hurdle_rate.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                             "risk_free": period, "days": days}), "utf-8")


def _defi(root: Path, pools: list[dict[str, object]] | None = None,
          *, age_h: float = 0.5) -> None:
    ts = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat()
    pools = pools if pools is not None else [
        {"symbol": "USDC", "supply_apy": 3.7847, "tvl_usd": 162_057_606.0,
         "project": "aave-v3", "chain": "Ethereum"}]
    p = root / "data/defi_lending.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps({"ts": ts, **pool}) + "\n" for pool in pools), "utf-8")


def _full(root: Path, **kw: object) -> None:
    _nav(root, **kw)  # type: ignore[arg-type]
    _hurdle(root)
    _defi(root)


class TestRiskFreeDeannualisation:
    """The 10.8x trap. These fail the moment someone returns the stored field unchanged."""

    def test_period_return_is_converted_to_an_annual_rate(self, tmp_path: Path) -> None:
        _hurdle(tmp_path, period=0.0034663, days=33.92)
        rate, why = iy.risk_free_annual(tmp_path)
        assert rate is not None
        # 0.0034663 * 365 / 33.92 = 0.0373 -- NOT the stored 0.0034663.
        assert rate == pytest.approx(0.0373, abs=1e-4)
        assert rate > 0.0034663 * 10, "the stored field was returned raw -- a 10.8x understatement"
        assert "de-annualised" in why

    def test_a_full_year_window_is_left_alone(self, tmp_path: Path) -> None:
        _hurdle(tmp_path, period=0.04, days=365.0)
        rate, _ = iy.risk_free_annual(tmp_path)
        assert rate == pytest.approx(0.04)

    def test_zero_days_refuses_rather_than_dividing(self, tmp_path: Path) -> None:
        _hurdle(tmp_path, period=0.004, days=0.0)
        rate, why = iy.risk_free_annual(tmp_path)
        assert rate is None and "de-annualise" in why

    def test_absent_artifact_refuses(self, tmp_path: Path) -> None:
        rate, why = iy.risk_free_annual(tmp_path)
        assert rate is None and "absent" in why

    def test_stale_artifact_is_not_evidence(self, tmp_path: Path) -> None:
        p = tmp_path / "data/hurdle_rate.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        old = (datetime.now(tz=UTC) - timedelta(hours=iy.HURDLE_STALE_HOURS + 24)).isoformat()
        p.write_text(json.dumps({"updated": old, "risk_free": 0.004, "days": 30.0}), "utf-8")
        rate, why = iy.risk_free_annual(tmp_path)
        assert rate is None and "old" in why


class TestLendingRung:
    def test_best_stable_pool_is_found(self, tmp_path: Path) -> None:
        _defi(tmp_path)
        best, why = iy.best_stable_apy(tmp_path)
        assert best is not None
        assert best["apy"] == pytest.approx(0.037847)
        assert best["symbol"] == "USDC" and "aave-v3" in why

    def test_yield_bearing_derivatives_are_not_treated_as_dollars(self, tmp_path: Path) -> None:
        # sUSDe's quoted APY is a second strategy with its own unwind and depeg profile. Folding
        # it in would manufacture a higher floor out of a different risk.
        _defi(tmp_path, [
            {"symbol": "SUSDE", "supply_apy": 12.0, "tvl_usd": 500_000_000.0,
             "project": "aave-v3", "chain": "Ethereum"},
            {"symbol": "USDC", "supply_apy": 3.0, "tvl_usd": 50_000_000.0,
             "project": "aave-v3", "chain": "Ethereum"}])
        best, _ = iy.best_stable_apy(tmp_path)
        assert best is not None and best["symbol"] == "USDC"
        assert best["apy"] == pytest.approx(0.03), "a yield-bearing derivative set the floor"

    def test_pool_below_the_tvl_floor_is_not_quotable(self, tmp_path: Path) -> None:
        # aave-v3 FRAX at $9,881 was real in the 2026-08-05 snapshot: a deposit our size IS the
        # utilisation curve there, so the advertised APY is not the APY we would receive.
        _defi(tmp_path, [{"symbol": "FRAX", "supply_apy": 99.0, "tvl_usd": 9_881.0,
                          "project": "aave-v3", "chain": "Ethereum"}])
        best, why = iy.best_stable_apy(tmp_path)
        assert best is None and "TVL" in why

    def test_stale_snapshot_refuses(self, tmp_path: Path) -> None:
        _defi(tmp_path, age_h=iy.DEFI_STALE_HOURS + 10)
        best, why = iy.best_stable_apy(tmp_path)
        assert best is None and "old" in why

    def test_only_the_latest_cross_section_is_read(self, tmp_path: Path) -> None:
        # defi_lending.jsonl is a repeated CROSS-SECTION, not a series (R0042). Pooling every row
        # would average today's rate against last week's and quote a yield nobody can get.
        p = tmp_path / "data/defi_lending.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        old = (datetime.now(tz=UTC) - timedelta(hours=30)).isoformat()
        new = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        p.write_text(
            json.dumps({"ts": old, "symbol": "USDC", "supply_apy": 9.0,
                        "tvl_usd": 5e7, "project": "a", "chain": "e"}) + "\n"
            + json.dumps({"ts": new, "symbol": "USDC", "supply_apy": 3.0,
                          "tvl_usd": 5e7, "project": "a", "chain": "e"}) + "\n", "utf-8")
        best, _ = iy.best_stable_apy(tmp_path)
        assert best is not None and best["apy"] == pytest.approx(0.03)


class TestFloor:
    def test_floor_is_the_max_of_both_rungs(self, tmp_path: Path) -> None:
        _hurdle(tmp_path)
        _defi(tmp_path)
        fl = iy.reachable_floor(tmp_path)
        assert fl.measurable and fl.winner == "risk_free"
        assert fl.annual_rate == pytest.approx(0.0373, abs=1e-4)

    def test_the_gross_comparison_survives_the_netting(self, tmp_path: Path) -> None:
        """The haircut decides the verdict, so it may never hide inside a single scalar."""
        _hurdle(tmp_path)
        _defi(tmp_path)
        fl = iy.reachable_floor(tmp_path)
        assert fl.lending_gross_annual == pytest.approx(0.037847)
        assert fl.lending_net_annual == pytest.approx(0.007847)
        # Gross, lending WINS by ~5bps; net of 300bps it loses by ~295. Both must be visible.
        assert fl.lending_gross_annual > fl.risk_free_annual
        assert fl.lending_net_annual < fl.risk_free_annual
        assert fl.breakeven_haircut_bps == pytest.approx(5.5, abs=0.6)
        assert any("GROSS" in n for n in fl.notes)

    def test_a_small_enough_haircut_flips_the_winner(self, tmp_path: Path) -> None:
        _hurdle(tmp_path)
        _defi(tmp_path)
        fl = iy.reachable_floor(tmp_path, haircut_bps=1.0)
        assert fl.winner == "lending_net"

    def test_zero_haircut_is_refused(self, tmp_path: Path) -> None:
        _hurdle(tmp_path)
        _defi(tmp_path)
        with pytest.raises(ValueError, match="haircut_bps must be > 0"):
            iy.reachable_floor(tmp_path, haircut_bps=0.0)

    def test_the_haircut_is_imported_not_copied(self) -> None:
        """One definition. A second literal would drift silently -- both look reasonable."""
        from scripts.screen_collateral_allocation import DEFAULT_HAIRCUT_BPS
        assert iy.reachable_floor(_root_of_repo()).haircut_bps == float(DEFAULT_HAIRCUT_BPS)

    def test_no_measurable_rung_yields_no_floor_never_zero(self, tmp_path: Path) -> None:
        fl = iy.reachable_floor(tmp_path)
        assert fl.measurable is False
        assert fl.annual_rate is None, "a 0.0 floor prices idle capital as FREE (L1.28a)"


def _root_of_repo() -> Path:
    return Path(__file__).resolve().parents[2]


class TestBookState:
    def test_paper_attestation_refuses_to_be_measurable(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=13_151.52, mode="PAPER (testnet) -- pre-Gate-0")
        _live(tmp_path)
        bs = iy.book_state(tmp_path)
        assert bs.is_paper is True and bs.measurable is False
        assert "MOLDED" in bs.why and "never deployed live capital" in bs.why

    def test_live_book_is_measurable_and_idle_is_the_difference(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=10_000.0, mode="LIVE")
        _live(tmp_path, deployed=2_500.0, n=3)
        (tmp_path / "data/LIVE_ENABLE").write_text("1", "utf-8")
        bs = iy.book_state(tmp_path)
        assert bs.measurable is True and bs.is_paper is False
        assert bs.deployed_usd == 2_500.0 and bs.idle_usd == 7_500.0 and bs.n_positions == 3

    def test_live_mode_without_the_enable_flag_still_refuses(self, tmp_path: Path) -> None:
        # Gate 0 is a two-key lock: an attestation claiming LIVE without data/LIVE_ENABLE is not
        # a funded book, and treating it as one would price capital the desk cannot actually move.
        _nav(tmp_path, equity=10_000.0, mode="LIVE")
        _live(tmp_path, deployed=1_000.0, n=1)
        assert iy.book_state(tmp_path).measurable is False

    def test_deployment_and_equity_come_from_different_sources(self, tmp_path: Path) -> None:
        """THE WELD REGRESSION. `check_utilisation._capital()` read the same source twice, so its
        ratio was identically 1.0 and a zero-position book printed SATURATED."""
        _nav(tmp_path, equity=13_151.52, deployed=13_151.52, n=9, mode="LIVE")
        _live(tmp_path, deployed=0.0, n=0)          # the EXECUTED book disagrees with the chain
        (tmp_path / "data/LIVE_ENABLE").write_text("1", "utf-8")
        bs = iy.book_state(tmp_path)
        assert bs.deployed_usd == 0.0, "deployment was read from the equity source"
        assert bs.idle_usd == pytest.approx(13_151.52)

    def test_unreadable_live_artifact_does_not_assume_zero_deployment(
            self, tmp_path: Path) -> None:
        # Assuming zero would MAXIMISE reported idle cost on an unreadable file. A fence that
        # gets louder when its input breaks is a fence that gets muted.
        _nav(tmp_path, equity=10_000.0, deployed=4_000.0, n=2, mode="LIVE")
        (tmp_path / "data/LIVE_ENABLE").write_text("1", "utf-8")
        bs = iy.book_state(tmp_path)
        assert bs.deployed_usd == 4_000.0 and bs.source.endswith("nav_attestation.jsonl")

    def test_absent_chain_is_a_refusal_not_a_free_book(self, tmp_path: Path) -> None:
        bs = iy.book_state(tmp_path)
        assert bs.measurable is False and "unknown is never zero-cost" in bs.why


class TestIdleCost:
    def test_paper_book_refuses_a_number_but_keeps_the_counterfactual(
            self, tmp_path: Path) -> None:
        _full(tmp_path, equity=13_151.52)
        out = iy.idle_cost(tmp_path)
        assert out["status"] == "UNMEASURABLE-PAPER-BOOK"
        assert out["usd_per_day"] is None, "a paper book produced a real-looking cost"
        # Labelled `hypothetical_` so nothing can mistake it for a measurement.
        assert out["hypothetical_usd_per_year"] == pytest.approx(490.5, abs=2.0)

    def test_live_book_is_priced(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=10_000.0, mode="LIVE")
        _live(tmp_path, deployed=0.0, n=0)
        _hurdle(tmp_path)
        _defi(tmp_path)
        (tmp_path / "data/LIVE_ENABLE").write_text("1", "utf-8")
        out = iy.idle_cost(tmp_path)
        assert out["status"] == "PRICED"
        assert out["usd_per_year"] == pytest.approx(373.0, abs=2.0)
        assert out["usd_per_day"] == pytest.approx(373.0 / 365.0, abs=0.02)

    def test_no_floor_refuses_rather_than_pricing_at_zero(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=10_000.0, mode="LIVE")
        _live(tmp_path)
        (tmp_path / "data/LIVE_ENABLE").write_text("1", "utf-8")
        out = iy.idle_cost(tmp_path)
        assert out["status"] == "NO-FLOOR" and out["usd_per_day"] is None
