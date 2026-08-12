"""Regression guards for the max_audit reconciliation checks (charter §31 coverage-not-volume,
§32 depth-breadth parity). These are standing laws -- lock their monitor behavior."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import scripts.max_audit as m

from libs.risk import capital_events


def _mk(tmp: Path) -> None:
    (tmp / "data/lake/bronze").mkdir(parents=True)
    (tmp / "reports/reconstructed_oos").mkdir(parents=True)
    (tmp / "web").mkdir(parents=True)


class TestDepthParity:
    def test_flags_shallow_unbackfilled_axes(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/kimchi_premium.jsonl").write_text("\n".join(["{}"] * 30))
        (tmp_path / "data/cny_premium.jsonl").write_text("\n".join(["{}"] * 40))
        (tmp_path / "data/stablecoin_supply.jsonl").write_text("\n".join(["{}"] * 200))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_depth_parity(defects)
        assert defects and defects[0][0] == "depth-parity"
        msg = defects[0][1]
        assert "kimchi_premium(30d)" in msg and "cny_premium(40d)" in msg
        assert "stablecoin_supply" not in msg  # deep -> exempt
        assert "§32" in msg

    def test_backfilled_axis_is_exempt(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/onchain_activity.jsonl").write_text("\n".join(["{}"] * 20))
        (tmp_path / "data/kimchi_premium.jsonl").write_text("\n".join(["{}"] * 20))
        (tmp_path / "data/cny_premium.jsonl").write_text("\n".join(["{}"] * 20))
        # onchain has a reconstructed-OOS report -> backfilled -> deep -> exempt
        (tmp_path / "reports/reconstructed_oos/onchain_activity.json").write_text("{}")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_depth_parity(defects)
        msg = defects[0][1] if defects else ""
        assert "onchain_activity" not in msg  # backfilled -> not flagged

    def test_too_few_clocks_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/kimchi_premium.jsonl").write_text("{}")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_depth_parity(defects)
        assert defects == []  # < 3 clocks -> not enough to judge


class TestDataUtilizationCoverage:
    def test_fires_on_idle_axes_with_coverage_not_volume_remedy(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _mk(tmp_path)
        for a in ["cny_premium", "onchain_activity", "dev_factor", "npm_downloads",
                  "pypi_downloads", "funding_skew", "basis_term", "options_flow", "social_vel"]:
            (tmp_path / "data/lake/bronze" / a).mkdir()
        # only 3 converted via a forward-shadow registry
        (tmp_path / "web/axis_shadows.json").write_text(json.dumps({"axes": [
            {"axis": "cny_premium"}, {"axis": "onchain_activity"}, {"axis": "dev_factor"}]}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_data_utilization(defects)
        assert defects and defects[0][0] == "data-utilization-paralysis"
        msg = defects[0][1]
        assert "MECHANISM-FIRST" in msg and "Do NOT clear this by" in msg
        # the old volume-machine remedy must never come back
        assert "combinatorial/mutation/forced-mechanism generation" not in msg

    def test_converted_axes_credit_all_three_sources(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/axis_shadows.json").write_text(json.dumps(
            {"axes": [{"axis": "kimchi_premium"}]}))
        (tmp_path / "reports/reconstructed_oos/onchain_throughput.json").write_text(
            json.dumps({"results": [{"sleeve": "onchain_activity"}]}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        conv = m._converted_axes()
        assert "kimchi_premium" in conv  # forward shadow
        assert "onchain_activity" in conv  # OOS sleeve
        assert "onchain_throughput" in conv  # OOS report stem


class TestRejectionShadowCheck:
    def test_flags_over_strict_gate(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/reject_shadow.json").write_text(json.dumps({
            "n_eligible": 6, "n_pending_rescore": 0,
            "audit": {"over_strict": True, "n_rejects": 6, "n_would_have_paid": 4,
                      "leak_frac": 0.667}}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        ids = [d[0] for d in defects]
        assert "rejection-shadow-overstrict" in ids
        assert "leaking survivors" in dict(defects)["rejection-shadow-overstrict"]

    def test_flags_unscored_backlog(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/reject_shadow.json").write_text(json.dumps({
            "n_eligible": 8, "n_pending_rescore": 8,
            "audit": {"over_strict": False}}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        assert "rejection-shadow-unscored" in [d[0] for d in defects]

    def test_no_report_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        assert defects == []

    def test_calibrated_gate_no_defect(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/reject_shadow.json").write_text(json.dumps({
            "n_eligible": 6, "n_pending_rescore": 0,
            "audit": {"over_strict": False, "n_rejects": 6, "n_would_have_paid": 0}}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        assert defects == []


class TestPostGate0Activation:
    def test_pre_gate0_silent(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)  # no data/gate0_complete
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_post_gate0_activation(defects)
        assert defects == []  # freeze correctly holds; manifest not due

    def test_gate0_done_but_unactivated_fires(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/gate0_complete").write_text("")
        (tmp_path / "data/cadence_state.json").write_text(json.dumps({"stage": "S0"}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_post_gate0_activation(defects)
        assert defects and defects[0][0] == "post-gate0-activation"
        assert "un-built" in defects[0][1]

    def test_activated_clears(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/gate0_complete").write_text("")
        (tmp_path / "data/cadence_state.json").write_text(
            json.dumps({"post_gate0_activated": True}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_post_gate0_activation(defects)
        assert defects == []


class TestSourceBacklog:
    def test_no_watchlist_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_source_backlog(defects)
        assert defects == []

    def test_all_resolved_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        wf = tmp_path / "docs/research/data_axis_watchlist.md"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("### 1. X — grade: verified-clean\n")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_source_backlog(defects)
        assert defects == []

    def test_pending_but_fresh_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        wf = tmp_path / "docs/research/data_axis_watchlist.md"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("### 1. X — grade: UNVERIFIED\n")  # just written -- fresh mtime
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "NOW", time.time())
        defects: list[tuple[str, str]] = []
        m.check_source_backlog(defects)
        assert defects == []

    def test_pending_and_stale_fires(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        wf = tmp_path / "docs/research/data_axis_watchlist.md"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("### 1. X — grade: UNVERIFIED\n")
        old = time.time() - 20 * 86400
        os.utime(wf, (old, old))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "NOW", time.time())
        defects: list[tuple[str, str]] = []
        m.check_source_backlog(defects)
        assert defects and defects[0][0] == "source-backlog-stale"
        assert "outrunning verification" in defects[0][1]


class TestBookAbsorbingState:
    """The 2026-07-29 find: a book the ruin rail can never release reads as a healthy flat book.

    Locks BOTH directions. A monitor that only proves it fires can silently become a
    fire-always alarm, which is the same zero-information failure as never firing at all.
    """

    @staticmethod
    def _write(tmp: Path, monkeypatch, *, fut_leg_net, realized: float, n_carries: int,
               deployed: float, start: float = 5000.0, peak: float = 5061.38,
               events: list[dict] | None = None, risk: object = "omit") -> None:
        """Fixture state AND the capital-events ledger the inception is read through.

        The ledger is pinned per-test on purpose. `capital_events.LEDGER` is an absolute path
        fixed at import, so before this these fixtures monkeypatched max_audit's ROOT and then
        read the LIVE desk ledger for the inception -- a test whose verdict moved with whatever
        the principal happened to have deposited. Empty ledger = `effective_start_equity` is the
        identity, which is what every case below except the capital-event ones wants.
        """
        (tmp / "web").mkdir(parents=True, exist_ok=True)
        (tmp / "data").mkdir(parents=True, exist_ok=True)
        feed: dict = {"fut_leg_net": fut_leg_net, "n_carries": n_carries,
                      "deployed_notional": deployed}
        if risk != "omit":
            feed["risk"] = risk
        (tmp / "web/cashcarry_live.json").write_text(json.dumps(feed), "utf-8")
        (tmp / "data/cashcarry_positions.json").write_text(json.dumps(
            {"start_futures_equity": start, "realized_spot_pnl": realized,
             "peak_combined_equity": peak}), "utf-8")
        led = tmp / "data/capital_events.jsonl"
        led.write_text("".join(json.dumps(e) + "\n" for e in (events or [])), "utf-8")
        monkeypatch.setattr(capital_events, "LEDGER", led)

    def test_fires_when_flat_book_still_reads_flatten(self, tmp_path: Path, monkeypatch) -> None:
        # The live 2026-07-29 state: equity 3139.86 vs 5000 inception = -37.2%, book flat.
        self._write(tmp_path, monkeypatch, fut_leg_net=-4790.57, realized=2930.43,
                    n_carries=0, deployed=0.0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects and defects[0][0] == "book-absorbing-state"
        msg = defects[0][1]
        assert "ruin-floor breach" in msg
        assert "ABSORBING" in msg
        assert "TIER-3" in msg          # the remedy must never read as "self-clear it"

    def test_silent_when_flatten_but_inventory_remains(self, tmp_path: Path, monkeypatch) -> None:
        # Same breach, but the book still holds carries -> the rail is mid-unwind, not absorbing.
        self._write(tmp_path, monkeypatch, fut_leg_net=-4790.57, realized=2930.43,
                    n_carries=3, deployed=1200.0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects == []

    def test_silent_on_healthy_flat_book(self, tmp_path: Path, monkeypatch) -> None:
        # Flat and solvent (no breach) -> an ordinary idle book, not this check's business.
        self._write(tmp_path, monkeypatch, fut_leg_net=-50.0, realized=10.0,
                    n_carries=0, deployed=0.0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects == []

    def test_silent_when_futures_equity_unmeasured(self, tmp_path: Path, monkeypatch) -> None:
        # A failed venue read must never manufacture a defect (2026-07-26 lesson).
        self._write(tmp_path, monkeypatch, fut_leg_net=None, realized=2930.43,
                    n_carries=0, deployed=0.0)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects == []

    def test_the_monitor_measures_against_the_SAME_inception_as_the_book(
            self, tmp_path: Path, monkeypatch) -> None:
        """R0364. The docstring promises the same pure function; it was fed a different input.

        `fut_leg_net` is published as `fut_eq - effective_start_equity`, so pairing it with the
        RAW inception adds a delta measured against one baseline to another baseline. Measured on
        the live book 2026-08-12: the monitor believed $13,472.67 while the book published
        $8,682.22 -- over by $4,790.70, the ledgered deposit to the cent.

        The direction is the dangerous one, which is what this case pins: a book 36% below its
        EFFECTIVE inception (the rail firing) reads as a 19.6% gain against the raw one, so the
        absorbing-state alarm goes silent exactly when the state is absorbing.
        """
        # A principal restart re-based the inception DOWN, 10000 -> 8000 (the live shape:
        # 10547.78 -> 5757.08). fut_leg_net is published relative to the EFFECTIVE 8000.
        ev = [{"kind": "restart", "deposit_usd": 0.0, "start_equity_after": 8000.0}]
        self._write(tmp_path, monkeypatch, fut_leg_net=-2880.0, realized=0.0,
                    n_carries=0, deployed=0.0, start=10000.0, peak=8000.0, events=ev)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        # EFFECTIVE:  8000 - 2880 =  5120, /8000  = -36.0%  -> ruin breach, book is absorbing.
        # RAW (old): 10000 - 2880 =  7120, /10000 = -28.8%  -> no breach, monitor stays SILENT.
        # Same book, same tick: the mixed baseline is the difference between an escalation and
        # an all-clear, and it fails toward the all-clear.
        assert defects and defects[0][0] == "book-absorbing-state"
        assert "-36.0%" in defects[0][1], defects[0][1]

    def test_a_deposit_does_not_manufacture_an_absorbing_state(
            self, tmp_path: Path, monkeypatch) -> None:
        """The other direction, and the one a careless fix breaks: honouring the capital event
        must not let the monitor invent a breach on a book the executor calls healthy."""
        ev = [{"kind": "deposit", "deposit_usd": 3000.0, "start_equity_after": 8000.0}]
        self._write(tmp_path, monkeypatch, fut_leg_net=-100.0, realized=0.0,
                    n_carries=0, deployed=0.0, start=5000.0, peak=8000.0, events=ev)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_book_absorbing_state(defects)
        assert defects == []          # 7900/8000 = -1.25%, nowhere near the ruin floor


class TestRailVerdictPublished:
    """R0364: the rail state every consumer reads must be one something actually evaluated.

    A heartbeat proves the loop is alive, never that the pipe is -- the desk's most expensive
    recurring lesson, here pointed at a rail. Both failure modes leave the feed's own freshness
    perfectly green, which is why nothing caught either.
    """

    def test_fires_on_the_2026_08_05_frozen_verdict(self, tmp_path: Path, monkeypatch) -> None:
        """The measured incident: a published pause that reproduces only against the RAW
        inception, on a feed whose mtime kept advancing every 600s."""
        ev = [{"kind": "restart", "deposit_usd": 4790.70, "start_equity_after": 5757.08}]
        TestBookAbsorbingState._write(
            tmp_path, monkeypatch, fut_leg_net=3.54, realized=2921.35, n_carries=0,
            deployed=0.0, start=10547.78, peak=8700.49, events=ev,
            risk={"action": "pause_opens", "dd_from_start_pct": -17.64,
                  "reasons": ["drawdown -17.6%<=-15%: pausing new opens"]})
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rail_verdict_published(defects)
        assert defects and defects[0][0] == "rail-verdict-stale"
        msg = defects[0][1]
        assert "-17.64%" in msg and "+50.81%" in msg
        assert "Do NOT re-baseline" in msg

    def test_fires_when_no_verdict_is_published_at_all(
            self, tmp_path: Path, monkeypatch) -> None:
        """`_book_snapshot()` has no "risk" key, so `_emit` publishes null on every tick that did
        not rebalance -- ~9 in 10 at --interval 600 against a 60s heartbeat."""
        TestBookAbsorbingState._write(
            tmp_path, monkeypatch, fut_leg_net=-50.0, realized=10.0, n_carries=0,
            deployed=0.0, risk=None)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rail_verdict_published(defects)
        assert defects and defects[0][0] == "rail-verdict-absent"
        assert "UNMEASURED IS NOT OK" in defects[0][1]

    def test_silent_when_the_published_verdict_matches_its_inputs(
            self, tmp_path: Path, monkeypatch) -> None:
        """The half that decides whether anyone keeps the alarm switched on."""
        ev = [{"kind": "restart", "deposit_usd": 4790.70, "start_equity_after": 5757.08}]
        TestBookAbsorbingState._write(
            tmp_path, monkeypatch, fut_leg_net=3.54, realized=2921.35, n_carries=0,
            deployed=0.0, start=10547.78, peak=8700.49, events=ev,
            risk={"action": "ok", "dd_from_start_pct": 50.81, "reasons": []})
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rail_verdict_published(defects)
        assert defects == []

    def test_silent_when_futures_equity_unmeasured(self, tmp_path: Path, monkeypatch) -> None:
        """An unmeasurable feed must never manufacture a RAIL defect -- the loudest defect class
        on the desk is the worst possible place to guess."""
        TestBookAbsorbingState._write(
            tmp_path, monkeypatch, fut_leg_net=None, realized=10.0, n_carries=0,
            deployed=0.0, risk=None)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rail_verdict_published(defects)
        assert defects == []

    def test_the_check_is_registered(self) -> None:
        """Four checks once sat defined-and-unregistered in this module. A rail monitor nothing
        calls is a claim the desk cannot cash (L1.49)."""
        assert ("rail-verdict-published", m.check_rail_verdict_published) in m.CHECKS
