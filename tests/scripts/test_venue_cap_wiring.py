"""GAP #54 / R0096 -- the venue cap, WIRED. The library was never the defect.

`libs/risk/risk_controls.VENUE_CAP`, the `venue_equity`/`venue_cap` arguments and 12 tests have
existed since 2026-07-29. The branch was UNREACHABLE IN PRODUCTION anyway: the executor's sole
`risk_controls.evaluate` call omitted `venue_equity`, it defaulted to None, and the breach branch
is guarded by `if venue_equity and eq > 0` -- so only the test suite ever entered it. A control
that no production call site can reach is a control the desk does not have, and a green library
suite is exactly what made that invisible for a week. Everything here therefore asserts on the
PRODUCTION path: the recorded `evaluate` call, the returned decision, and the opens it stops.

THE FAIL-CLOSED DECISION, AND WHY. An unreadable venue map degrades to CONCENTRATED -- 100% of
equity charged to the one counterparty this book is executed against -- never to None and never
to {}. Both of those are the *same value* to `evaluate` as "no venue is over the cap", so a
missing artifact would silently re-create the exact defect this row exists to close, by a
different route. Unknown is not zero (L1.41); for a CONCENTRATION measurement the honest unknown
is the worst case. Two doors are held shut, not one:

  * ABSENT / STALE / TRUNCATED feed -> concentrated, plus an UNMEASURED reason recorded on the
    decision (published in web/cashcarry_live.json) and a stale_read event for the fence.
  * FRESH feed publishing a split that UNDER-ACCOUNTS for the book -> the unattributed remainder
    is charged to the routing venue, so an unnamed remainder can never dilute every fraction
    toward zero. Same defect, fresh timestamp.

Nothing here changes VENUE_CAP (1.0) or any other threshold; the sub-cap cases pass `venue_cap`
explicitly, exactly as tests/risk/test_venue_cap.py already does.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import scripts.run_cashcarry_executor as ex

from libs.ops.fresh import REGISTRY_REL
from libs.risk import capital_events as CE
from libs.risk import risk_controls

_FILTERS: dict[str, dict[str, float]] = {
    "BTCUSDT": {"step": 1e-05, "min_qty": 1e-05, "qty_prec": 6, "min_notional": 10.0,
                "tick": 0.01, "price_prec": 2},
}
_PRICES = {"BTCUSDT": 60_000.0}
_EQUITY = 10_000.0            # both fake accounts; eq_c = futures equity + spot leg P&L (0)
_FUNDING = {"BTCUSDT": 0.005}  # clears _entry_gate against the pessimistic unmeasured cost


class _Venue:
    """A venue that records every order it is asked to send, and is asked for none of them."""

    def __init__(self, equity: float) -> None:
        self._equity = equity
        self.orders: list[tuple[Any, ...]] = []

    def has_keys(self) -> bool:
        return True

    def account_summary(self) -> dict[str, float]:
        return {"equity": self._equity}

    def account_value_usdt(self) -> float:
        return self._equity

    def exchange_filters(self) -> dict[str, dict[str, float]]:
        return {k: dict(v) for k, v in _FILTERS.items()}

    def prices(self) -> dict[str, float]:
        return dict(_PRICES)

    def mark_prices(self) -> dict[str, float]:
        return dict(_PRICES)

    def balances(self) -> dict[str, float]:
        return {}

    def positions(self) -> dict[str, float]:
        return {}

    def quote_depth(self, sym: str, side: str) -> float:
        return 1e12

    def book_ticker(self) -> dict[str, tuple[float, float]]:
        return {s: (p, p) for s, p in _PRICES.items()}

    def force_orders(self, hours: float) -> dict[str, int]:
        return {}

    def open_orders(self, sym: str) -> list[dict[str, Any]]:
        return []

    def income_summary(self, start_ms: int) -> dict[str, float]:
        return {"realized_pnl": 0.0}

    # --- writes (must stay empty on every path exercised here) -------------------------------
    def place_market(self, sym: str, side: str, qty: float) -> None:
        self.orders.append(("market", sym, side, qty))

    def place_post_only(self, sym: str, side: str, qty: float, px: float) -> None:
        self.orders.append(("post_only", sym, side, qty))

    def place_stop_market(self, sym: str, side: str, qty: float, stop: float) -> None:
        self.orders.append(("stop", sym, side, qty))

    def cancel_all(self, sym: str) -> None:
        pass

    def set_leverage(self, sym: str, lev: int) -> None:
        pass


@pytest.fixture
def froot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp artifact root for the PURE `_venue_equity` tests.

    Mandatory, not hygiene: `read_fresh` resolves relative paths against cwd and appends its
    self-building contract registry there, so a helper test run from the repo would write a
    genuine-looking `unreadable_read` for web/venue_equity.json into data/freshness_contracts.jsonl
    and page scripts/check_freshness.py about a feed nothing actually failed to read.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_FRESH_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """One real `_rebalance` tick on a tmp root, with the `evaluate` call recorded.

    The spy delegates to the REAL `risk_controls.evaluate`, so the decision under assertion is
    the production one -- the spy only makes the arguments visible. Every artifact root is
    redirected into tmp (QUANT_FRESH_ROOT + cwd + the two risk_controls paths + the capital
    ledger) so no test can read or write desk state.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_FRESH_ROOT", str(tmp_path))
    monkeypatch.setattr(CE, "LEDGER", tmp_path / "data/capital_events.jsonl")
    monkeypatch.setattr(risk_controls, "INCOME_ARTIFACT", tmp_path / "web/cashcarry_live.json")
    monkeypatch.setattr(risk_controls, "BURN_WINDOW_FILE", tmp_path / "data/fee_burn_window.json")
    spot, fut = _Venue(_EQUITY), _Venue(_EQUITY)
    monkeypatch.setattr(ex, "spot", spot)
    monkeypatch.setattr(ex, "fut", fut)
    monkeypatch.setattr(ex, "current_funding", lambda: dict(_FUNDING))
    calls: list[dict[str, Any]] = []
    real = risk_controls.evaluate

    def _spy(*a: Any, **kw: Any) -> risk_controls.RiskDecision:
        calls.append(dict(kw))
        return real(*a, **kw)

    monkeypatch.setattr(risk_controls, "evaluate", _spy)
    return SimpleNamespace(calls=calls, spot=spot, fut=fut, root=tmp_path)


def _feed(root: Path, obj: Any, *, age_s: float = 0.0) -> Path:
    """Write web/venue_equity.json. `age_s` ages the MTIME -- the feed carries `updated`, not
    `generated`, so libs.ops.fresh measures it by mtime (verified by the staleness test)."""
    p = root / "web/venue_equity.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), "utf-8")
    if age_s:
        old = time.time() - age_s
        os.utime(p, (old, old))
    return p


def _scalar_feed() -> dict[str, Any]:
    """Today's real publication (run_live_combined): a SINGLE SCALAR dead-man value, futures
    scope, with no per-exchange breakdown anywhere in it."""
    return {"updated": datetime.now(tz=UTC).isoformat(), "equity": 5_169.0,
            "high_water": 5_400.0, "fire_line": 3_510.0, "breaches": 0, "fired": False,
            "kind": "dead-man measure: fut margin + tracked spot legs + USDT delta"}


def _tick() -> dict[str, Any]:
    return ex._rebalance(top=1, hold_top=1, capital=5_000.0, dry=True)


def _events(root: Path) -> list[dict[str, Any]]:
    p = root / REGISTRY_REL
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


# ==============================================================================================
# (a) THE ARGUMENT ITSELF -- asserted on the CALL, because the file existing proves nothing
# ==============================================================================================

class TestTheProductionCallNowCarriesAVenueMap:
    def test_evaluate_receives_a_non_none_venue_map(self, desk: SimpleNamespace) -> None:
        """The one-line defect: `venue_equity` was absent, so the breach branch could not run."""
        _feed(desk.root, _scalar_feed())
        _tick()
        assert len(desk.calls) == 1, "the executor must evaluate risk exactly once per tick"
        book = desk.calls[0].get("venue_equity")
        assert book is not None, "None is what made the cap unreachable in production"
        assert book, "{} short-circuits `if venue_equity and eq > 0` exactly like None does"

    def test_the_map_is_in_the_same_ruler_evaluate_divides_by(self,
                                                              desk: SimpleNamespace) -> None:
        """NOT the feed's 5,169 scalar: that is the dead-man's FUTURES scope, and dividing it by
        the combined book is the unit error claim_verifier.py records as a 175% phantom."""
        _feed(desk.root, _scalar_feed())
        _tick()
        book = desk.calls[0]["venue_equity"]
        assert book == {ex._VENUE: pytest.approx(_EQUITY)}
        assert 5_169.0 not in book.values(), "a cross-scope divide would fabricate a breach"

    def test_spot_and_futures_are_one_counterparty_not_two(self, desk: SimpleNamespace) -> None:
        """An FTX-class failure takes both sub-accounts together; naming them separately would
        halve every fraction and turn the cap into decoration."""
        _feed(desk.root, _scalar_feed())
        _tick()
        assert list(desk.calls[0]["venue_equity"]) == [ex._VENUE]

    def test_a_published_split_is_honoured_verbatim(self, desk: SimpleNamespace) -> None:
        """R0096 asks for a per-venue map. The day the producer emits one, this needs no edit."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 6_000.0, "bybit": 4_000.0}})
        _tick()
        assert desk.calls[0]["venue_equity"] == {ex._VENUE: 6_000.0, "bybit": 4_000.0}

    def test_no_threshold_moved(self, desk: SimpleNamespace) -> None:
        _feed(desk.root, _scalar_feed())
        _tick()
        assert risk_controls.VENUE_CAP == 1.0
        assert "venue_cap" not in desk.calls[0], "the cap stays the library default, untouched"


# ==============================================================================================
# (b) A BREACH REALLY STOPS OPENS -- through the executor, not the library
# ==============================================================================================

class TestABreachTripsPauseOpensThroughTheExecutor:
    def test_the_control_tick_does_open(self, desk: SimpleNamespace) -> None:
        """Without this, every 'opens were stopped' assertion below is vacuous."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 5_000.0, "bybit": 5_000.0}})
        rb = _tick()
        assert rb["risk"]["action"] == "ok"
        assert rb["risk"]["venue_breaches"] == []
        assert [s for s, _ in rb["cands"]] == ["BTCUSDT"], "a candidate exists to be stopped"

    def test_a_breach_pauses_opens_and_empties_the_candidates(self,
                                                              desk: SimpleNamespace) -> None:
        """At the UNCHANGED cap of 1.0: one venue holding more than the whole book's equity."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 12_000.0, "bybit": 500.0}})
        rb = _tick()
        assert rb["risk"]["action"] == "pause_opens"
        assert rb["risk"]["venue_breaches"] == [ex._VENUE]
        assert rb["cands"] == [], "the breach must actually stop the opens, not just be logged"
        assert "FTX-class" in " ".join(rb["risk"]["reasons"])

    def test_the_pause_is_named_per_venue_not_only_globally(self,
                                                            desk: SimpleNamespace) -> None:
        """R0096 names this: the executor raises its OWN gate against the breaching venue it
        routes to, rather than only inheriting a global verdict -- so the venue is named in the
        actions and persisted in state, and opens stop here even if a future caller changes what
        the global action means."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 12_000.0}})
        rb = _tick()
        hits = [a for a in rb["actions"] if a.startswith(f"VENUE-CAP {ex._VENUE}")]
        assert len(hits) == 1, rb["actions"]
        assert "no new opens on this venue" in hits[0]
        assert rb["state"]["venue_breaches"] == [ex._VENUE], "persisted for the next tick/pager"

    def test_a_breach_elsewhere_is_attributed_elsewhere(self, desk: SimpleNamespace) -> None:
        """The per-venue gate is keyed on the venue, so a breach at bybit raises no VENUE-CAP
        line against the venue this book routes to.

        HONEST LIMIT, pinned deliberately: opens still stop, because `evaluate`'s GLOBAL
        pause_opens is unchanged and this executor may only ADD to it. Declining a global pause
        because the breach was at another venue would be a LOOSENING, and the per-venue gate
        exists to tighten -- it names the breaching venue and stops opens there independently of
        the global verdict; it never hands back opens the global verdict took away.
        """
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 1_000.0, "bybit": 12_000.0}})
        rb = _tick()
        assert rb["risk"]["venue_breaches"] == ["bybit"]
        assert not [a for a in rb["actions"] if a.startswith(f"VENUE-CAP {ex._VENUE}")]
        assert rb["risk"]["action"] == "pause_opens" and rb["cands"] == []

    def test_a_breach_never_flattens_and_places_no_orders(self, desk: SimpleNamespace) -> None:
        """Yanking capital off an exchange in a panic realises losses and converts a
        concentration problem into a solvency one."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 12_000.0}})
        rb = _tick()
        assert rb["risk"]["action"] != "flatten"
        assert rb["state"]["last_risk_action"] == "pause_opens"
        assert desk.spot.orders == [] and desk.fut.orders == []

    def test_the_breach_reaches_the_published_artifact(self, desk: SimpleNamespace) -> None:
        """A control nothing can page on fires into the void: `_emit` publishes rb['risk']."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 12_000.0}})
        rb = _tick()
        assert "venue_breaches" in rb["risk"] and rb["risk"]["venue_breaches"]


# ==============================================================================================
# (c) FAIL-CLOSED -- an unreadable feed must never read as "no breach"
# ==============================================================================================

class TestAnUnreadableFeedCannotSilentlyDisableTheCap:
    @pytest.mark.parametrize(
        ("name", "write"),
        [("missing", lambda root: None),
         ("stale", lambda root: _feed(root, _scalar_feed(), age_s=2 * 3600.0)),
         ("truncated", lambda root: _feed(root, {})),
         ("corrupt", lambda root: (root / "web/venue_equity.json").write_text("{oops", "utf-8")),
         ("not-an-object", lambda root: _feed(root, [1, 2, 3]))])
    def test_the_map_is_concentrated_never_none_or_empty(
            self, desk: SimpleNamespace, name: str, write: Any) -> None:
        (desk.root / "web").mkdir(parents=True, exist_ok=True)
        write(desk.root)
        _tick()
        book = desk.calls[0]["venue_equity"]
        assert book == {ex._VENUE: pytest.approx(_EQUITY)}, f"{name} must degrade CONCENTRATED"

    def test_the_unmeasured_reason_is_recorded_on_the_decision(self,
                                                               desk: SimpleNamespace) -> None:
        """Recorded, not swallowed: rb['risk'] is what `_emit` publishes every cycle."""
        rb = _tick()
        assert any("venue-split UNMEASURED" in r for r in rb["risk"]["reasons"]), rb["risk"]
        assert any("unknown is not zero" in r for r in rb["risk"]["reasons"])

    def test_a_stale_feed_says_stale_and_still_constrains(self, desk: SimpleNamespace) -> None:
        _feed(desk.root, _scalar_feed(), age_s=2 * 3600.0)
        rb = _tick()
        note = next(r for r in rb["risk"]["reasons"] if "venue-split UNMEASURED" in r)
        assert "STALE" in note
        assert desk.calls[0]["venue_equity"] == {ex._VENUE: pytest.approx(_EQUITY)}

    def test_the_fence_gets_a_stale_read_event(self, desk: SimpleNamespace) -> None:
        """The paging path: libs.ops.fresh records the refusal for scripts/check_freshness.py,
        so a dead venue feed is loud even though the reader is not the organ that screams."""
        _tick()
        mine = [e for e in _events(desk.root)
                if e["caller"] == "run_cashcarry_executor._venue_equity"]
        assert {e["event"] for e in mine} >= {"contract", "unreadable_read"}, mine
        assert all(e["path"] == "web/venue_equity.json" for e in mine)

    def test_the_max_age_is_the_desks_own_cadence_floor(self) -> None:
        """Reused, not minted: run_cadence._FLOORS_S0['web/venue_equity.json'] is 1.0, so the
        executor and the pager agree on when this feed is dead."""
        import scripts.run_cadence as cadence
        assert ex._VENUE_FEED_MAX_AGE_H == cadence._FLOORS_S0["web/venue_equity.json"] == 1.0

    def test_unmeasured_breaches_the_moment_the_cap_drops_below_one(self, froot: Path) -> None:
        """THE PROPERTY, stated as the thing it prevents. A dead feed must never be able to read
        as 'no breach'. It reads as 'everything is in one basket' -- which at cap 1.0 is at the
        cap (correct for a one-venue desk) and at any tighter cap PAUSES OPENS."""
        book, note = ex._venue_equity(_EQUITY)
        assert note is not None and "UNMEASURED" in note
        d = risk_controls.evaluate(
            _EQUITY, _EQUITY, _EQUITY, 0.0, ruin_cap_lev=3.0, venue_equity=book, venue_cap=0.5,
            fee_burn=risk_controls.FeeBurnWindow(0.0, 0.0, 1.0))
        assert d.action == "pause_opens" and d.venue_breaches == [ex._VENUE]

    def test_the_pre_r0096_call_could_not_have_breached_at_any_cap(self) -> None:
        """PIN the defect being closed: with `venue_equity` omitted -- the production call as it
        stood -- no cap, however tight, can produce a breach."""
        d = risk_controls.evaluate(
            _EQUITY, _EQUITY, _EQUITY, 0.0, ruin_cap_lev=3.0, venue_cap=0.01,
            fee_burn=risk_controls.FeeBurnWindow(0.0, 0.0, 1.0))
        assert d.venue_breaches == [] and d.action == "ok"


# ==============================================================================================
# THE SECOND DOOR -- a FRESH feed that under-accounts for the book
# ==============================================================================================

class TestAnUnnamedRemainderCannotDiluteTheCap:
    def test_a_partial_split_charges_the_remainder_to_the_routing_venue(
            self, desk: SimpleNamespace) -> None:
        """`{"venues": {"bybit": 100}}` on a $10,000 book would otherwise make every fraction
        ~1% and the cap unreachable again -- the same defect with a fresh timestamp."""
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {"bybit": 100.0}})
        rb = _tick()
        assert desk.calls[0]["venue_equity"] == {"bybit": 100.0,
                                                 ex._VENUE: pytest.approx(_EQUITY - 100.0)}
        assert any("venue-split PARTIAL" in r for r in rb["risk"]["reasons"])

    def test_a_complete_split_raises_no_partial_note(self, desk: SimpleNamespace) -> None:
        _feed(desk.root, {"updated": datetime.now(tz=UTC).isoformat(),
                          "venues": {ex._VENUE: 5_000.0, "bybit": 5_000.0}})
        rb = _tick()
        assert not [r for r in rb["risk"]["reasons"] if "venue-split" in r]

    def test_rounding_noise_between_two_measures_is_not_a_partial(self, froot: Path) -> None:
        """The tolerance is `_RSP_TOL`, this file's existing dollar-noise floor -- no new
        threshold was minted. Two independent equity measures disagreeing by a few dollars must
        not emit a PARTIAL every tick (an alarm that always fires is an alarm nobody reads)."""
        assert ex._RSP_TOL == 5.0
        _feed(froot, {"updated": datetime.now(tz=UTC).isoformat(),
                      "venues": {ex._VENUE: _EQUITY - (ex._RSP_TOL - 1.0)}})
        book, note = ex._venue_equity(_EQUITY)
        assert note is None and book == {ex._VENUE: pytest.approx(_EQUITY - 4.0)}

    def test_a_shortfall_past_that_floor_is_a_partial(self, froot: Path) -> None:
        _feed(froot, {"updated": datetime.now(tz=UTC).isoformat(),
                      "venues": {ex._VENUE: _EQUITY - (ex._RSP_TOL + 1.0)}})
        book, note = ex._venue_equity(_EQUITY)
        assert note is not None and "PARTIAL" in note
        assert book == {ex._VENUE: pytest.approx(_EQUITY)}

    def test_a_split_over_the_book_is_left_alone_and_still_breaches(self, froot: Path) -> None:
        """Over-attribution is already the conservative direction -- never topped up, and never
        normalised back down to fit, which would erase the very breach it evidences."""
        _feed(froot, {"updated": datetime.now(tz=UTC).isoformat(),
                      "venues": {ex._VENUE: 12_000.0}})
        book, note = ex._venue_equity(_EQUITY)
        assert note is None and book == {ex._VENUE: 12_000.0}
        d = risk_controls.evaluate(_EQUITY, _EQUITY, _EQUITY, 0.0, ruin_cap_lev=3.0,
                                   venue_equity=book,
                                   fee_burn=risk_controls.FeeBurnWindow(0.0, 0.0, 1.0))
        assert d.action == "pause_opens" and d.venue_breaches == [ex._VENUE]


# ==============================================================================================
# (d) THE LIBRARY CONTRACT THIS WIRING DEPENDS ON -- unchanged
# ==============================================================================================

def test_the_short_circuit_that_hid_the_defect_still_exists() -> None:
    """This is WHY the fallback may never be None or {}: `evaluate` treats both as 'nothing to
    check'. The wiring above is what keeps production out of this branch."""
    base = {"equity": _EQUITY, "start_equity": _EQUITY, "peak_equity": _EQUITY,
            "gross_notional": 0.0, "ruin_cap_lev": 3.0,
            "fee_burn": risk_controls.FeeBurnWindow(0.0, 0.0, 1.0)}
    for empty in (None, {}):
        assert risk_controls.evaluate(**base, venue_equity=empty,   # type: ignore[arg-type]
                                      venue_cap=0.01).venue_breaches == []
