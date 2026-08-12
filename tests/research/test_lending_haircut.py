"""R0375 -- the lending haircut is derived from measured base rates, or it refuses.

The behaviour under test is not "does it return a number". It is the DIRECTION of every failure:
a broken, stale or partial input must return the LARGE refusal value, never a plausible small one,
because a small haircut OPENS a yield band and a fabricated one would open it on nothing.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from scripts.collect_lending_risk_base_rates import (
    _top_level_array,
    _tvl_years,
    collect_withdrawal_queue,
)

from libs.research.lending_haircut import (
    LAST_RESORT_HAIRCUT_BPS,
    Haircut,
    derive_haircut,
    haircut_bps,
    poisson_upper,
)


def _payload(**over: Any) -> dict[str, Any]:
    """A base-rate artifact shaped exactly like the collector's output."""
    base: dict[str, Any] = {
        "generated": "2999-01-01T00:00:00+00:00",
        "status": "READ",
        "losses": {
            "status": "READ",
            "blue_chip_events": [
                {"date": "2021-09-29", "name": "Compound V2", "net_usd": 147_000_000.0},
                {"date": "2026-03-12", "name": "Aave V3", "net_usd": 0.0},
            ],
            "blue_chip_net_usd": 147_000_000.0,
        },
        "exposure": {"complete": True, "total_tvl_years_usd": 120_191_130_333.93,
                     "n_protocols_read": 6, "n_protocols_declared": 6},
        "peg": {"status": "READ", "per_asset": {
            "USDC": {"status": "READ", "mean_shortfall_bps": 3.2061, "n_days": 2046,
                     "first": "2020-12-30", "last": "2026-08-12", "worst_price": 0.961065,
                     "worst_date": "2023-03-12", "pct_days_below_0995": 0.6351},
            "DAI": {"status": "READ", "mean_shortfall_bps": 3.6900, "n_days": 2046,
                    "first": "2020-12-30", "last": "2026-08-12", "worst_price": 0.9625,
                    "worst_date": "2023-03-12", "pct_days_below_0995": 0.54},
        }},
        "withdrawal_queue": {"status": "READ", "per_pool": {
            "aave-v3/USDC/aa70268e": {"n": 311, "max": 1.0001, "pct_ge_99": 23.8},
        }},
    }
    base.update(over)
    return base


def _root(tmp_path: Path, payload: dict[str, Any] | None) -> Path:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    if payload is not None:
        (tmp_path / "data/lending_risk_base_rates.json").write_text(
            json.dumps(payload), "utf-8")
    return tmp_path


class TestPoissonUpper:
    def test_k0_is_the_rule_of_three(self) -> None:
        """The closed form at zero events: -ln(0.05) = 2.9957. Pins the solver's calibration."""
        assert poisson_upper(0) == pytest.approx(-math.log(0.05), abs=1e-6)

    def test_k2_matches_the_chi_square_closed_form(self) -> None:
        """chi2(0.95, 2k+2)/2 at k=2 is 12.5916/2 = 6.2958."""
        assert poisson_upper(2) == pytest.approx(6.2958, abs=1e-3)

    def test_bound_always_exceeds_the_observation(self) -> None:
        for k in range(0, 40):
            assert poisson_upper(k) > k

    def test_refuses_a_negative_count(self) -> None:
        with pytest.raises(ValueError, match="negative event count"):
            poisson_upper(-1)

    def test_refuses_a_degenerate_confidence(self) -> None:
        with pytest.raises(ValueError, match="strictly inside"):
            poisson_upper(2, confidence=1.0)


class TestDerivation:
    def test_derives_from_measured_base_rates(self, tmp_path: Path) -> None:
        h = derive_haircut(_root(tmp_path, _payload()))
        assert h.measured is True
        # 147e6/120.19e9*1e4 = 12.23bps point; x3.148 frequency bound = 38.50; +3.21 depeg.
        assert h.components["exploit"]["point_bps"] == pytest.approx(12.231, abs=0.01)
        assert h.bps == pytest.approx(41.71, abs=0.05)
        assert h.point_bps == pytest.approx(15.44, abs=0.05)

    def test_published_number_exceeds_the_point_estimate(self, tmp_path: Path) -> None:
        """The bound must WIDEN. A haircut published at its point estimate off two events would
        open a yield band on a number the sample cannot support."""
        h = derive_haircut(_root(tmp_path, _payload()))
        assert h.point_bps is not None
        assert h.bps > h.point_bps

    def test_names_the_measured_but_unpriced_risk(self, tmp_path: Path) -> None:
        """The withdrawal queue is measured and deliberately not summed -- it must be VISIBLE,
        or a reader infers zero from its absence."""
        h = derive_haircut(_root(tmp_path, _payload()))
        assert any("utilisation >= 0.99" in u for u in h.unpriced)
        assert any("severity" in u for u in h.unpriced)

    def test_unknown_asset_takes_the_worst_peer_never_zero(self, tmp_path: Path) -> None:
        """PYUSD is what the floor actually quotes today and has no measured price history."""
        h = derive_haircut(_root(tmp_path, _payload()), asset="PYUSD")
        assert h.measured is True
        assert h.components["depeg"]["asset_used"] == "DAI"      # the worst measured peer
        assert h.components["depeg"]["bps"] == pytest.approx(3.69, abs=0.01)

    def test_haircut_bps_wrapper_agrees(self, tmp_path: Path) -> None:
        root = _root(tmp_path, _payload())
        assert haircut_bps(root) == derive_haircut(root).bps


class TestRefusalDirection:
    """Every one of these must return the LARGE value with measured=False."""

    def _assert_refused(self, h: Haircut) -> None:
        assert h.measured is False
        assert h.bps == LAST_RESORT_HAIRCUT_BPS
        assert h.point_bps is None
        assert any("UNMEASURED" in n for n in h.notes)

    def test_absent_artifact(self, tmp_path: Path) -> None:
        self._assert_refused(derive_haircut(_root(tmp_path, None)))

    def test_partial_exposure_is_not_a_measurement(self, tmp_path: Path) -> None:
        """A denominator missing protocols OVERSTATES the loss rate. It is still refused: a
        conservative wrong number is a wrong number (L1.57)."""
        p = _payload()
        p["exposure"] = {**p["exposure"], "complete": False, "n_protocols_read": 4}
        self._assert_refused(derive_haircut(_root(tmp_path, p)))

    def test_zero_exposure_denominator(self, tmp_path: Path) -> None:
        p = _payload()
        p["exposure"] = {**p["exposure"], "total_tvl_years_usd": 0.0}
        self._assert_refused(derive_haircut(_root(tmp_path, p)))

    def test_unreadable_losses(self, tmp_path: Path) -> None:
        p = _payload()
        p["losses"] = {"status": "UNREADABLE", "error": "no network"}
        self._assert_refused(derive_haircut(_root(tmp_path, p)))

    def test_zero_events_is_not_zero_risk(self, tmp_path: Path) -> None:
        """Zero observed exploits must NOT derive a ~0bps haircut and open the band."""
        p = _payload()
        p["losses"] = {"status": "READ", "blue_chip_events": [], "blue_chip_net_usd": 0.0}
        self._assert_refused(derive_haircut(_root(tmp_path, p)))

    def test_no_priced_stablecoin(self, tmp_path: Path) -> None:
        p = _payload()
        p["peg"] = {"status": "READ", "per_asset": {"USDC": {"status": "NO-DATA"}}}
        self._assert_refused(derive_haircut(_root(tmp_path, p)))

    def test_stale_artifact_is_refused(self, tmp_path: Path) -> None:
        p = _payload(generated="2000-01-01T00:00:00+00:00")
        self._assert_refused(derive_haircut(_root(tmp_path, p)))


class TestStreamingExtractor:
    """The load path must be O(chunk), and it must not read the WRONG `tvl` key."""

    def test_finds_the_top_level_array_not_the_nested_one(self, tmp_path: Path) -> None:
        """DefiLlama puts `chainTvls` FIRST, and every chain inside carries its own `tvl` key.
        A naive scan for the first `"tvl":` reads Base-borrowed and calls it the protocol."""
        doc = {
            "chainTvls": {
                "Base-borrowed": {"tvl": [{"date": 1, "totalLiquidityUSD": 999.0}]},
                "Ethereum": {"tvl": [{"date": 1, "totalLiquidityUSD": 888.0}]},
            },
            "name": "x", "tvl": [{"date": 100, "totalLiquidityUSD": 1.0},
                                 {"date": 100 + 86400, "totalLiquidityUSD": 3.0}],
            "currentChainTvls": {"Ethereum": 5.0},
        }
        p = tmp_path / "p.json"
        p.write_text(json.dumps(doc), "utf-8")
        got = _top_level_array(p, "tvl")
        assert got is not None
        assert [r["totalLiquidityUSD"] for r in got] == [1.0, 3.0]

    def test_survives_a_key_split_across_chunk_boundaries(self, tmp_path: Path) -> None:
        """A 1MB chunk read can land mid-key. Padding forces the split at many offsets."""
        for pad in range(0, 64):
            doc = {"pad": "x" * pad, "chainTvls": {"A": {"tvl": [{"date": 1,
                                                                  "totalLiquidityUSD": 9.0}]}},
                   "tvl": [{"date": 100, "totalLiquidityUSD": 2.0}]}
            p = tmp_path / f"p{pad}.json"
            p.write_text(json.dumps(doc), "utf-8")
            got = _top_level_array(p, "tvl")
            assert got is not None, f"lost the array at pad={pad}"
            assert got[0]["totalLiquidityUSD"] == 2.0

    def test_braces_inside_strings_do_not_move_depth(self, tmp_path: Path) -> None:
        doc = {"methodology": 'counts {deposits} and [borrows] "quoted"',
               "tvl": [{"date": 1, "totalLiquidityUSD": 7.0}]}
        p = tmp_path / "s.json"
        p.write_text(json.dumps(doc), "utf-8")
        got = _top_level_array(p, "tvl")
        assert got is not None and got[0]["totalLiquidityUSD"] == 7.0

    def test_absent_key_is_none_not_empty(self, tmp_path: Path) -> None:
        """None and [] must not collapse: [] integrates to a zero denominator and would be
        published as a real exposure."""
        p = tmp_path / "n.json"
        p.write_text(json.dumps({"name": "x"}), "utf-8")
        assert _top_level_array(p, "tvl") is None

    def test_non_array_value_for_the_key_is_none(self, tmp_path: Path) -> None:
        p = tmp_path / "v.json"
        p.write_text(json.dumps({"tvl": 12345, "other": [{"a": 1}]}), "utf-8")
        assert _top_level_array(p, "tvl") is None


class TestTvlYears:
    def test_trapezoid_integration(self) -> None:
        """Two points a day apart at 365 and 365 -> exactly 1.0 TVL-year."""
        years, n, skipped, first, last = _tvl_years(
            [{"date": 0, "totalLiquidityUSD": 365.0},
             {"date": 86400, "totalLiquidityUSD": 365.0}])
        assert years == pytest.approx(1.0)
        assert (n, skipped) == (2, 0)
        assert first == "1970-01-01" and last == "1970-01-02"

    def test_long_gaps_are_not_bridged(self) -> None:
        """A protocol DefiLlama stopped tracking did not hold that TVL through the hole, and
        bridging inflates the denominator -- the direction that SHRINKS the haircut."""
        years, _n, _s, _f, _l = _tvl_years(
            [{"date": 0, "totalLiquidityUSD": 365.0},
             {"date": 86400 * 30, "totalLiquidityUSD": 365.0}])
        assert years == 0.0

    def test_unusable_rows_are_counted_not_dropped_in_silence(self) -> None:
        """L1.60: a loop feeding a denominator publishes what it lost."""
        _y, n, skipped, _f, _l = _tvl_years(
            [{"date": 0, "totalLiquidityUSD": 1.0}, {"date": None}, {"nope": 1}])
        assert (n, skipped) == (1, 2)


class TestWithdrawalQueue:
    def test_reports_no_data_rather_than_zero(self, tmp_path: Path) -> None:
        out = collect_withdrawal_queue(tmp_path)
        assert out["status"] == "NO-DATA"

    def test_measures_utilisation_and_counts_attrition(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        rows = [
            {"pool": "aa70268e", "project": "aave-v3", "symbol": "USDC",
             "utilisation": u, "tvl_usd": 1.0}
            for u in (0.5, 0.99, 1.0001)
        ]
        lines = [json.dumps(r) for r in rows] + ["{not json}", ""]
        (tmp_path / "data/defi_lending.jsonl").write_text("\n".join(lines), "utf-8")
        out = collect_withdrawal_queue(tmp_path)
        assert out["status"] == "READ"
        assert out["n_rows_unusable"] == 1
        slot = next(iter(out["per_pool"].values()))
        assert slot["n"] == 3
        assert slot["max"] == pytest.approx(1.0001)
        assert slot["pct_ge_99"] == pytest.approx(66.667, abs=0.01)
