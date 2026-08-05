"""R0321 + R0322 -- the two blind spots on the executed book's money path.

R0321: an OPEN-FAIL half-fill (`spot_ok=True fut_ok=False`) leaves a BOUGHT spot leg with no
`pos` entry at all. Every scan the desk had was keyed on something that orphan is missing from:
the SPOT-EXCESS branch iterates `pos` (so an untracked symbol has no `want` to exceed), the
futures orphan cover walks `fut.positions()` (venue SHORTS), and scripts/hedge_integrity.py's
ORPHAN class walks the same futures map. The wallet itself -- naked, unhedged, invisible to
`_mark` -- was read by nothing. The sweep added here is DETECT-AND-PAGE ONLY: selling spot is a
money path, and the futures cover carries confirm/cap/cooldown/circuit bounds precisely because
an automatic one fires live ammo into thin books.

R0322: portfolio.json (run_live_combined) read the RAW `start_futures_equity` while the executor
had already moved to the capital-events-aware inception. One ledgered deposit and the desk
publishes two books measuring from two different inceptions -- with the molded book, the one that
reads as the account of record, reporting the deposit itself as P&L.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import scripts.run_cashcarry_executor as ex
import scripts.run_live_combined as rlc

from libs.risk import capital_events as CE

_FILTERS: dict[str, dict[str, float]] = {
    "BTCUSDT": {"step": 1e-05, "min_qty": 1e-05, "qty_prec": 6, "min_notional": 10.0},
    "ETHUSDT": {"step": 0.0001, "min_qty": 0.0001, "qty_prec": 6, "min_notional": 10.0},
    "DUSTUSDT": {"step": 0.1, "min_qty": 0.1, "qty_prec": 2, "min_notional": 0.0},
}
_PRICES = {"BTCUSDT": 60_000.0, "ETHUSDT": 3_000.0, "DUSTUSDT": 1.0}


class _Venue:
    """A venue that records every order it is asked to send, and is asked for none of them."""

    def __init__(self, balances: dict[str, float], positions: dict[str, float]) -> None:
        self._bal, self._pos = balances, positions
        self.orders: list[tuple[str, str, str, float]] = []

    # --- reads -----------------------------------------------------------------------------
    def has_keys(self) -> bool:
        return True

    def balances(self) -> dict[str, float]:
        return dict(self._bal)

    def positions(self) -> dict[str, float]:
        return dict(self._pos)

    def exchange_filters(self) -> dict[str, dict[str, float]]:
        return {k: dict(v) for k, v in _FILTERS.items()}

    def prices(self) -> dict[str, float]:
        return dict(_PRICES)

    def mark_prices(self) -> dict[str, float]:
        return dict(_PRICES)

    def force_orders(self, hours: float) -> dict[str, int]:
        return {}

    def book_ticker(self) -> dict[str, tuple[float, float]]:
        return {s: (p, p) for s, p in _PRICES.items()}

    # --- writes (must stay empty) ----------------------------------------------------------
    def place_market(self, sym: str, side: str, qty: float) -> None:
        self.orders.append(("market", sym, side, qty))

    def place_post_only(self, sym: str, side: str, qty: float, px: float) -> None:
        self.orders.append(("post_only", sym, side, qty))

    def cancel_all(self, sym: str) -> None:
        pass

    def set_leverage(self, sym: str, lev: int) -> None:
        pass


def _run(monkeypatch: pytest.MonkeyPatch, *, wallet: dict[str, float],
         pos: dict[str, dict[str, Any]] | None = None,
         fut_pos: dict[str, float] | None = None) -> tuple[list[str], _Venue, _Venue]:
    spot = _Venue(wallet, {})
    fut = _Venue({}, fut_pos or {})
    monkeypatch.setattr(ex, "spot", spot)
    monkeypatch.setattr(ex, "fut", fut)
    acts = ex._reconcile(dict(pos or {}), dry=False)
    return acts, spot, fut


def _excess(acts: list[str]) -> list[str]:
    return [a for a in acts if a.startswith("SPOT-EXCESS")]


# ------------------------------------------------------------------------------------------
# R0321
# ------------------------------------------------------------------------------------------

class TestUntrackedSpotBalanceRaisesTheOrphanPath:
    def test_symbol_absent_from_pos_is_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The half-filled open: 0.05 BTC in the wallet, nothing in `pos`. $3,000 naked long."""
        acts, _s, _f = _run(monkeypatch, wallet={"BTC": 0.05, "USDT": 1_000.0}, pos={})
        hit = _excess(acts)
        assert len(hit) == 1, acts
        assert "BTCUSDT" in hit[0] and "NO tracked carry" in hit[0]
        assert "3,000" in hit[0], "the page must carry the size a human has to act on"

    def test_it_places_no_orders(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DETECT AND PAGE ONLY -- an automatic spot sale is a money path, not a reflex."""
        acts, spot, fut = _run(monkeypatch, wallet={"BTC": 0.05}, pos={})
        assert _excess(acts) and spot.orders == [] and fut.orders == []

    def test_the_pre_r0321_scan_could_never_have_seen_it(self,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
        """The old branch is keyed on `pos`: with no entry there is no `want` to exceed."""
        acts, _s, _f = _run(monkeypatch, wallet={"BTC": 0.05}, pos={})
        assert not [a for a in acts if "vs tracked" in a], "the tracked branch cannot fire here"

    def test_a_tracked_carry_is_not_double_reported(self,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
        pos = {"BTCUSDT": {"spot_qty": 0.05, "perp_qty": -0.05, "spot_cost": 60_000.0,
                           "perp_entry": 60_000.0, "funding": 0.0001}}
        acts, spot, fut = _run(monkeypatch, wallet={"BTC": 0.05}, pos=pos,
                               fut_pos={"BTCUSDT": -0.05})
        assert _excess(acts) == [] and spot.orders == [] and fut.orders == []

    def test_dust_below_the_venue_minimum_is_not_paged(self,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
        """$6 of BTC against a $10 published min_notional cannot even be sold."""
        acts, _s, _f = _run(monkeypatch, wallet={"BTC": 0.0001}, pos={})
        assert _excess(acts) == [], acts

    def test_the_dust_floor_is_the_files_existing_constant(self,
                                                           monkeypatch: pytest.MonkeyPatch
                                                           ) -> None:
        """With no published minimum the floor is `_RSP_TOL` -- no new threshold was minted."""
        assert ex._RSP_TOL == 5.0
        below, _s, _f = _run(monkeypatch, wallet={"DUST": ex._RSP_TOL - 0.01}, pos={})
        assert _excess(below) == []
        above, _s2, _f2 = _run(monkeypatch, wallet={"DUST": ex._RSP_TOL + 0.01}, pos={})
        assert len(_excess(above)) == 1 and "DUSTUSDT" in above[0]

    def test_quote_and_untradeable_assets_are_ignored(self,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
        """USDT is the quote, and an asset with no spot market was never a carry leg."""
        acts, _s, _f = _run(monkeypatch, wallet={"USDT": 9_999.0, "XYZ": 5_000.0}, pos={})
        assert _excess(acts) == [], acts

    def test_every_untracked_orphan_is_reported_not_just_the_first(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        acts, _s, _f = _run(monkeypatch, wallet={"BTC": 0.05, "ETH": 1.0}, pos={})
        assert len(_excess(acts)) == 2
        assert {"BTCUSDT" in a for a in _excess(acts)} == {True, False}


# ------------------------------------------------------------------------------------------
# R0322
# ------------------------------------------------------------------------------------------

class TestBothPublishedBooksMeasureFromOneInception:
    @pytest.fixture(autouse=True)
    def isolated_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(CE, "LEDGER", tmp_path / "capital_events.jsonl")

    def test_baselines_agree_with_no_ledger(self) -> None:
        st = {"start_futures_equity": 5_000.0}
        assert rlc._start_equity(st, 0.0) == ex._start_equity(st, 0.0) == 5_000.0

    def test_baselines_agree_after_a_ledgered_deposit(self) -> None:
        st = {"start_futures_equity": 5_000.0}
        CE.rebase(equity_now=4_000.0, start_equity=5_000.0, deposit_usd=2_000.0,
                  authorised_by="principal", reason="R0322 test: launch funding deposit")
        assert rlc._start_equity(st, 0.0) == ex._start_equity(st, 0.0) == 6_000.0

    def test_the_pre_r0322_read_disagreed_by_the_whole_deposit(self) -> None:
        """What portfolio.json used to publish: the deposit itself, as P&L."""
        st = {"start_futures_equity": 5_000.0}
        CE.rebase(equity_now=4_000.0, start_equity=5_000.0, deposit_usd=2_000.0,
                  authorised_by="principal", reason="R0322 test: launch funding deposit")
        raw = rlc._num(st.get("start_futures_equity"), 0.0)
        assert rlc._start_equity(st, 0.0) - raw == pytest.approx(1_000.0)

    def test_both_fall_back_identically_on_an_unusable_state(self) -> None:
        for st in ({}, {"start_futures_equity": None}, {"start_futures_equity": "x"}):
            assert rlc._start_equity(dict(st), 4_321.0) == ex._start_equity(dict(st), 4_321.0)
