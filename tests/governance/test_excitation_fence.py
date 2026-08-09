"""L1.45 EXECUTION EXCITATION -- the design, the fence, the fit, and the executor WIRING.

The wiring tests at the bottom are the load-bearing ones. This desk's most expensive recurring
defect is a mechanism that is built, unit-tested green, and called by NOBODY -- unit tests prove
the mechanism works and say nothing about whether anything runs it. Every test in the final class
fails if the executor wiring is torn out, so excitation cannot silently become decorative.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.check_excitation import build_report

from libs.execution import excitation as ex

_ROOT = Path(__file__).resolve().parent.parent.parent
_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _design(**over) -> ex.Design:
    base = {"arms": {"baseline": 240.0, "brief": 15.0}, "epsilon": 0.5,
            "daily_notional_cap_usd": 1000.0, "cells": {}}
    base.update(over)
    return ex.Design(**base)


# --------------------------------------------------------------------------- assignment


def test_baseline_arm_reproduces_todays_wait() -> None:
    """The baseline arm MUST equal _MAKER_WAIT_OPEN, or excitation silently re-times every open."""
    d = ex.load_design(_ROOT / "data/excitation_design.json")
    assert d.loaded
    assert d.arms[ex.BASELINE_ARM] == 240.0


def test_closes_are_never_excited() -> None:
    """A close is a certainty problem (incident #6). The refusal is structural, not configured."""
    for seq in range(50):
        arm = ex.assign("AAVEUSDT", "SELL", 500.0, design=_design(epsilon=1.0),
                        now=_NOW, sequence=seq)
        assert arm.baseline is True
        assert "close side" in arm.reason


def test_epsilon_bounds_the_treatment_share() -> None:
    d = _design(epsilon=0.25)
    arms = [ex.assign("AAVEUSDT", "BUY", 60.0, design=d, now=_NOW, sequence=i)
            for i in range(600)]
    treated = sum(1 for a in arms if not a.baseline)
    assert 0.15 < treated / len(arms) < 0.35, treated / len(arms)


def test_daily_cap_refuses_and_says_so() -> None:
    arm = ex.assign("AAVEUSDT", "BUY", 60.0, design=_design(epsilon=1.0),
                    spent_today_usd=999.0, now=_NOW, sequence=1)
    assert arm.baseline is True
    assert "budget spent" in arm.reason


def test_assignment_is_deterministic_and_replayable() -> None:
    """A pre-registered experiment must be auditable: same seed inputs => same arm, forever."""
    d = _design(epsilon=0.5)
    a = ex.assign("AAVEUSDT", "BUY", 60.0, design=d, now=_NOW, sequence=7)
    b = ex.assign("AAVEUSDT", "BUY", 60.0, design=d, now=_NOW, sequence=7)
    assert (a.name, a.maker_wait_s, a.seed) == (b.name, b.maker_wait_s, b.seed)


@pytest.mark.parametrize("raw", [
    "{not json",
    '{"epsilon": 0.5}',                                   # no arms
    '{"arms": {"brief": 15.0}, "epsilon": 0.5}',          # no BASELINE arm
    '{"arms": {"baseline": 240.0}, "epsilon": 5.0}',      # epsilon out of range
])
def test_malformed_design_degrades_to_no_excitation(tmp_path: Path, raw: str) -> None:
    """An unreadable design must degrade to TODAY'S behaviour, never to random behaviour."""
    p = tmp_path / "d.json"
    p.write_text(raw, "utf-8")
    d = ex.load_design(p)
    assert d.loaded is False
    assert d.epsilon == 0.0
    arm = ex.assign("AAVEUSDT", "BUY", 60.0, design=d, now=_NOW, sequence=1)
    assert arm.baseline is True


def test_absent_design_degrades_to_no_excitation(tmp_path: Path) -> None:
    d = ex.load_design(tmp_path / "nope.json")
    assert d.loaded is False and d.epsilon == 0.0


def test_metadata_keys_are_not_design_cells() -> None:
    """REGRESSION: `_measured_symbols` and `_measured_note` live inside `cells` as metadata.

    Counting them as cells crashed the first run; the dangerous direction would have been
    counting a note as an OBSERVED cell and reporting a design better identified than it is.
    """
    d = _design(cells={"_measured_symbols": {"BTCUSDT": 1}, "_measured_note": "prose",
                       "measured:s": {"n_observed": 0}, "measured:m": {"n_observed": 4}})
    assert sorted(d.real_cells) == ["measured:m", "measured:s"]
    assert d.unidentified_cells == ["measured:s"]


# --------------------------------------------------------------------------- L1.16a re-entry


def _reentry(**over) -> dict:
    row = {"named_change": "incident #6 fix", "probe_after": "2026-07-01T00:00:00+00:00",
           "max_probes": 3}
    row.update(over)
    return {"COOKIEUSDT": row}


def test_reentry_default_is_deny() -> None:
    ok, why = ex.reentry_allowed("COOKIEUSDT", {}, [], now=_NOW)
    assert ok is False and "no recorded re-entry condition" in why


@pytest.mark.parametrize("over,expect", [
    ({"named_change": ""}, "no named enabling change"),
    ({"probe_after": "not-a-date"}, "no usable probe_after"),
    ({"max_probes": 0}, "not armed"),
    ({"probe_after": "2026-12-01T00:00:00+00:00"}, "probe window opens"),
])
def test_reentry_refuses_incomplete_rows(over: dict, expect: str) -> None:
    """L1.16a: re-opening needs a NAMED enabling change and a date. Recording is not arming."""
    ok, why = ex.reentry_allowed("COOKIEUSDT", _reentry(**over), [], now=_NOW)
    assert ok is False and expect in why


def test_reentry_allows_a_bounded_probe_then_stops() -> None:
    tape = []
    for _ in range(3):
        ok, why = ex.reentry_allowed("COOKIEUSDT", _reentry(), tape, now=_NOW)
        assert ok is True, why
        tape.append({"event": "open", "symbol": "COOKIEUSDT",
                     "opened": (_NOW - timedelta(hours=1)).isoformat()})
    ok, why = ex.reentry_allowed("COOKIEUSDT", _reentry(), tape, now=_NOW)
    assert ok is False and "budget exhausted" in why


def test_probes_before_the_window_do_not_consume_the_budget() -> None:
    """Opens BEFORE probe_after are ordinary history, not probes -- counting them would let a
    symbol's own pre-block trades exhaust the budget the re-entry condition just granted."""
    old = [{"event": "open", "symbol": "COOKIEUSDT", "opened": "2026-06-01T00:00:00+00:00"}]
    assert ex.probes_used("COOKIEUSDT", old,
                          datetime(2026, 7, 1, tzinfo=UTC)) == 0


def test_the_two_denylisted_symbols_have_recorded_reentry_conditions() -> None:
    """Both blocked names are the incident-#6 symbols; each needs its named change on disk."""
    data = json.loads((_ROOT / "data/execution_reentry.json").read_text("utf-8"))
    for sym in ("COOKIEUSDT", "1000CATUSDT"):
        assert sym in data, sym
        assert "incident #6" in data[sym]["named_change"].lower()
        assert data[sym]["max_probes"] > 0


# --------------------------------------------------------------------------- the fence


def _fixture(tmp_path: Path, *, design: dict | None, tape: list[dict],
             forensics: list[dict], reentry: dict | None) -> Path:
    (tmp_path / "data/moat/execution_tape").mkdir(parents=True)
    (tmp_path / "web").mkdir(parents=True)
    if design is not None:
        (tmp_path / "data/excitation_design.json").write_text(json.dumps(design), "utf-8")
    if reentry is not None:
        (tmp_path / "data/execution_reentry.json").write_text(json.dumps(reentry), "utf-8")
    (tmp_path / "web/trade_forensics.json").write_text(
        json.dumps({"worst_symbols": forensics}), "utf-8")
    (tmp_path / "data/moat/execution_tape/cashcarry_trades.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tape), "utf-8")
    return tmp_path


_GOOD_DESIGN = {"arms": {"baseline": 240.0, "brief": 15.0}, "epsilon": 0.25,
                "daily_notional_cap_usd": 2000.0,
                "cells": {"measured:s": {"n_observed": 5}}}
_BLED = [{"symbol": "COOKIEUSDT", "n": 7, "bps": -53.7}]


def test_fence_never_reports_ok_on_an_empty_desk(tmp_path: Path) -> None:
    """THE ONE THING THIS FENCE MAY NEVER DO. Nothing to look at is LOUDER, not quieter."""
    root = _fixture(tmp_path, design=None, tape=[], forensics=[], reentry=None)
    assert build_report(root=root, now=_NOW)["status"] == "NO-DATA"


def test_fence_reports_no_excitation_when_switched_off(tmp_path: Path) -> None:
    d = dict(_GOOD_DESIGN, epsilon=0.0)
    root = _fixture(tmp_path, design=d, tape=[], forensics=[], reentry=None)
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] == "NO-EXCITATION"
    assert "idleness defect" in rep["detail"]


def test_fence_reports_absorbing_for_a_block_with_no_way_back(tmp_path: Path) -> None:
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=[], forensics=_BLED, reentry=None)
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] == "ABSORBING"
    assert rep["absorbing_exclusions"][0]["symbol"] == "COOKIEUSDT"


def test_recording_a_reentry_condition_clears_absorbing(tmp_path: Path) -> None:
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=[], forensics=_BLED,
                    reentry=_reentry())
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] != "ABSORBING"
    assert rep["absorbing_exclusions"] == []


def _write_executor(root: Path, *, wired: bool) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    body = ("arm = _excitation_arm(sym, spot_side, qty)" if wired
            else "_w = _MAKER_WAIT_OPEN  # excitation torn out")
    (root / "scripts/run_cashcarry_executor.py").write_text(body, "utf-8")


def test_fence_says_UNWIRED_when_the_executor_does_not_call_the_design(tmp_path: Path) -> None:
    """The design can be perfect and the artifact healthy while nothing assigns an arm."""
    tape = [{"event": "open", "symbol": "AAVEUSDT", "notional": 60.0,
             "opened": _NOW.isoformat()}]
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=tape, forensics=[], reentry=None)
    _write_executor(root, wired=False)
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] == "UNIDENTIFIED"
    assert rep["executor_wired"] is False
    assert "arms are assigned by nobody" in rep["detail"]
    assert "Wire libs/execution/excitation.assign()" in rep["next_action"]


def test_fence_says_ACCRUE_FILLS_when_wired_but_the_book_has_not_traded(tmp_path: Path) -> None:
    """REGRESSION: 'no stamped fills' has two causes with OPPOSITE fixes. Reporting 'go wire it'
    at a wired executor sends the next session to redo finished work -- the same mis-diagnosis
    this build already hit once on the TCA epoch."""
    tape = [{"event": "open", "symbol": "AAVEUSDT", "notional": 60.0,
             "opened": _NOW.isoformat()}]
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=tape, forensics=[], reentry=None)
    _write_executor(root, wired=True)
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] == "UNIDENTIFIED"
    assert rep["executor_wired"] is True
    assert "needs FILLS" in rep["detail"]
    assert "ACCRUE FILLS" in rep["next_action"]


def test_fence_does_not_claim_wiring_it_could_not_read(tmp_path: Path) -> None:
    """No executor source at all: say so, never guess in either direction."""
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=[], forensics=[], reentry=None)
    rep = build_report(root=root, now=_NOW)
    assert rep["executor_wired"] is None
    assert "UNREADABLE" in rep["detail"]


def test_the_real_executor_is_wired() -> None:
    """The live wiring marker exists in the real tree -- this fails if someone removes it."""
    from scripts.check_excitation import _executor_wired
    assert _executor_wired(_ROOT) is True


def test_fence_reports_unidentified_when_every_arm_is_baseline(tmp_path: Path) -> None:
    """Stamped but never randomised: the wait coefficient stays confounded with side."""
    tape = [{"event": "open", "symbol": "AAVEUSDT", "notional": 60.0, "opened": _NOW.isoformat(),
             "exc_arm": "baseline", "exc_baseline": True} for _ in range(5)]
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=tape, forensics=[], reentry=None)
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] == "UNIDENTIFIED"
    assert "ZERO randomised arms" in rep["detail"]


def test_fence_reaches_ok_only_with_randomised_arms_and_filled_cells(tmp_path: Path) -> None:
    tape = [{"event": "open", "symbol": "AAVEUSDT", "notional": 60.0, "opened": _NOW.isoformat(),
             "exc_arm": "brief", "exc_baseline": False}]
    root = _fixture(tmp_path, design=_GOOD_DESIGN, tape=tape, forensics=[], reentry=None)
    rep = build_report(root=root, now=_NOW)
    assert rep["status"] == "OK", rep["detail"]
    assert rep["n_randomised"] == 1


def test_spent_today_counts_only_todays_non_baseline_notional() -> None:
    tape = [
        {"exc_baseline": False, "notional": 100.0, "opened": _NOW.isoformat()},
        {"exc_baseline": False, "notional": 500.0, "opened": "2026-07-01T00:00:00+00:00"},
        {"exc_baseline": True, "notional": 900.0, "opened": _NOW.isoformat()},
        {"notional": 700.0, "opened": _NOW.isoformat()},
    ]
    assert ex.spent_today(tape, now=_NOW) == 100.0


# --------------------------------------------------------------------------- the fit


def test_underpowered_fit_publishes_no_ramp_evidence(tmp_path: Path) -> None:
    """THE LOAD-BEARING REFUSAL. cost_ratio gates SIZE INCREASES: publishing one from too few
    fills would step the book up on fiction, which is strictly worse than leaving it pinned."""
    from scripts.run_cost_identification import build_report as fit
    (tmp_path / "data/moat/execution_tape").mkdir(parents=True)
    (tmp_path / "data/cost_model.json").write_text(json.dumps(
        {"symbols": {"AAVEUSDT": {"pair": {"500": {"pair_open_bps": 1.0}}}}}), "utf-8")
    rows = [{"event": "open", "symbol": "AAVEUSDT", "notional": 500.0,
             "opened": _NOW.isoformat(), "spot_slip_bps": 1.0, "fut_slip_bps": 1.0}
            for _ in range(3)]
    (tmp_path / "data/moat/execution_tape/cashcarry_trades.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    rep = fit(now=_NOW, root=tmp_path)
    assert rep["status"] == "UNDERPOWERED"
    assert rep["ramp_evidence"] == {}


def test_epoch_is_not_poisoned_by_one_stray_instrumented_row(tmp_path: Path) -> None:
    """REGRESSION: a single instrumented fill nine days early dragged the epoch back and
    reported '60 fills uninstrumented' for a recorder then running at 6/6."""
    from scripts.run_cost_identification import _tca_coverage
    rows = [{"opened": "2026-07-22T00:00:00+00:00", "spot_slip_bps": 1.0}]
    rows += [{"opened": "2026-07-22T00:00:00+00:00"} for _ in range(46)]
    rows += [{"opened": "2026-07-31T00:00:00+00:00", "spot_slip_bps": 1.0} for _ in range(6)]
    cov = _tca_coverage(rows)
    assert cov["epoch"] == "2026-07-31"
    assert cov["uninstrumented_since_epoch"] == []


def test_ramp_merge_never_clobbers_another_producers_evidence(tmp_path: Path) -> None:
    """`evidence` is shared: live_sharpe and drill_pass_streak_weeks come from elsewhere."""
    from scripts.run_cost_identification import _merge_ramp
    p = tmp_path / "ramp_state.json"
    p.write_text(json.dumps({"size_fraction": 0.1,
                             "evidence": {"live_sharpe": 1.2, "cost_ratio": 9.9}}), "utf-8")
    _merge_ramp({"status": "OK", "ramp_evidence": {"cost_ratio": 1.1}}, p)
    ev = json.loads(p.read_text("utf-8"))["evidence"]
    assert ev["live_sharpe"] == 1.2
    assert ev["cost_ratio"] == 1.1


def test_nothing_published_leaves_ramp_state_untouched(tmp_path: Path) -> None:
    from scripts.run_cost_identification import _merge_ramp
    p = tmp_path / "ramp_state.json"
    p.write_text(json.dumps({"evidence": {"live_sharpe": 1.2}}), "utf-8")
    msg = _merge_ramp({"status": "UNDERPOWERED", "ramp_evidence": {}}, p)
    assert "left untouched" in msg
    assert json.loads(p.read_text("utf-8"))["evidence"] == {"live_sharpe": 1.2}


# --------------------------------------------------------------------------- THE WIRING
# These fail if the executor wiring is removed. A mechanism nothing calls is not built.


class TestExecutorWiring:
    SRC = (_ROOT / "scripts/run_cashcarry_executor.py").read_text("utf-8")

    def test_executor_imports_excitation(self) -> None:
        assert "from libs.execution import excitation" in self.SRC

    def test_open_path_takes_its_wait_from_the_assigned_arm(self) -> None:
        """If this reverts to the _MAKER_WAIT_OPEN constant, every open is baseline again and
        the whole design becomes decorative while the fence still reads a loaded artifact."""
        assert "arm = _excitation_arm(sym, spot_side, qty)" in self.SRC
        assert "_w = arm.maker_wait_s if spot_side == \"BUY\" else _MAKER_WAIT" in self.SRC

    def test_both_fill_paths_stamp_the_arm(self) -> None:
        """Maker AND taker-fallback. Dropping the taker stamp deletes exactly the observations
        where the maker path failed -- attrition correlated with the outcome."""
        assert self.SRC.count("_exc_fields(arm, spot_side)") == 2

    def test_the_stamp_reaches_the_permanent_tape(self) -> None:
        assert 'k.startswith("exc_")' in self.SRC

    def test_closes_are_not_stamped(self) -> None:
        assert 'if spot_side != "BUY":' in self.SRC

    def test_denylist_consults_the_reentry_condition(self) -> None:
        assert "excitation.reentry_allowed(sym, _reentry_conditions()" in self.SRC

    def test_cadence_jitter_is_persisted_not_discarded(self) -> None:
        assert '_EXC_CADENCE["last_jitter"]' in self.SRC
        assert '"exc_cadence_jitter"' in self.SRC

    def test_the_close_path_returns_before_any_io(self) -> None:
        """The risk path must not pay a design load + full tape read for an arm it discards.

        `_excitation_arm`'s close short-circuit must come BEFORE the try block that does I/O --
        an early return placed after it would still be correct and still be a latency regression
        on the path the rails exit through, and it would grow with the tape.
        """
        fn = self.SRC.index("def _excitation_arm(")
        nxt = self.SRC.index("def _exc_fields(")
        body = self.SRC[fn:nxt]
        early = body.index('if spot_side != "BUY":')
        io = body.index("excitation.load_design()")
        assert early < io, "close short-circuit must precede the design load / tape read"
