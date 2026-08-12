"""Regression guards for `check_clock_saturation` after the 2026-08-12 welded-gate repair.

THE DEFECT THIS LOCKS. The first cut graded `gen_done_<axis>` (cadence_state) as a recency clock.
That key is a one-way PRESENCE latch whose own producer refuses to re-stamp it when a run
pre-registers nothing new (run_axis_generate.py:196 -- "the same lie in a quieter file"), so seven
days after the last NEW axis the check fired on every axis forever and the only remedy available
was a fabricated timestamp. It also read the wrong QUANTITY: `crossasset` was reported as having
NO hypothesis accruing while data/forward_slots.json carried a standing crossasset clock ACCRUING
since 2026-06-21.

The shape being locked cuts both ways, and both directions matter equally:
  * it must be SILENT when the duty is satisfied -- a gate that rejects 100% carries zero
    information (L1.43) and gets acked into permanent silence, which is how the real instance is
    missed;
  * it must still FIRE on the two genuine breaches, or the repair would have been a loosening.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.max_audit as m


def _lake(tmp: Path, *axes: str) -> None:
    for ax in axes:
        (tmp / "data/lake/bronze" / ax).mkdir(parents=True, exist_ok=True)


def _slots(tmp: Path, *, accruing: tuple[str, ...] = (), idle: int = 0) -> None:
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    (tmp / "data/forward_slots.json").write_text(json.dumps({
        "idle_slots": idle,
        "slots": [{"name": n, "kind": "axis", "state": "ACCRUING"} for n in accruing],
    }), "utf-8")


def _agenda(tmp: Path, *axes: str) -> None:
    (tmp / "research_agenda.json").write_text(json.dumps({
        "queue_ranked_by_expected_research_roi": [
            {"id": f"h_{a}", "source_kill": f"REJECTED by EV gate; axis={a}."} for a in axes
        ]}), "utf-8")


def _run(tmp: Path, monkeypatch) -> list[tuple[str, str]]:
    monkeypatch.setattr(m, "ROOT", tmp)
    defects: list[tuple[str, str]] = []
    m.check_clock_saturation(defects)
    return defects


class TestSilentWhenTheDutyIsSatisfied:
    def test_the_real_2026_08_12_state_is_not_a_breach(self, tmp_path: Path, monkeypatch) -> None:
        """The measured instance that exposed the weld: 9 axes, every one ledgered, cohort full.

        Reported as "9/9 verified axes have NO hypothesis accruing". In fact crossasset held a
        52-day-old standing clock and all nine held dated EV-gate cards, while idle_slots was 0 --
        the clocks were saturated, which is the condition this check is named for.
        """
        nine = ("cme", "crossasset", "energy", "equity", "etf_flows",
                "fed", "metal", "mining", "wikipedia")
        _lake(tmp_path, *nine)
        _slots(tmp_path, accruing=("crossasset",), idle=0)
        _agenda(tmp_path, *nine)
        assert _run(tmp_path, monkeypatch) == []

    def test_an_accruing_clock_alone_satisfies_it(self, tmp_path: Path, monkeypatch) -> None:
        """A live forward clock IS the duty discharged -- no agenda entry should be required."""
        _lake(tmp_path, "crossasset")
        _slots(tmp_path, accruing=("crossasset",), idle=3)
        (tmp_path / "research_agenda.json").write_text("{}", "utf-8")
        assert _run(tmp_path, monkeypatch) == []

    def test_input_stores_are_not_axes(self, tmp_path: Path, monkeypatch) -> None:
        """Raw price/metrics lakes cannot carry a hypothesis; constructions built FROM them do."""
        _lake(tmp_path, "fx", "index", "crypto", "binance_metrics", "futclose_daily", "oi_ls_daily")
        _slots(tmp_path, idle=5)
        (tmp_path / "research_agenda.json").write_text("{}", "utf-8")
        assert _run(tmp_path, monkeypatch) == []

    def test_ledgered_but_unclocked_is_silent_when_the_cohort_is_full(
            self, tmp_path: Path, monkeypatch) -> None:
        """The Holm cap binding is not researcher idleness.

        With zero idle slots no axis can start a clock without displacing another, and
        MAX_FORWARD_SLOTS is a validation bar -- never widened to clear a defect.
        """
        _lake(tmp_path, "metal", "mining")
        _slots(tmp_path, accruing=("something_else",), idle=0)
        _agenda(tmp_path, "metal", "mining")
        assert _run(tmp_path, monkeypatch) == []


class TestStillFires:
    def test_an_ingested_axis_nobody_ever_authored_against(
            self, tmp_path: Path, monkeypatch) -> None:
        """Ingest cost paid, zero hypotheses ever written: the duty's core breach."""
        _lake(tmp_path, "cme", "brand_new_axis")
        _slots(tmp_path, accruing=("cme",), idle=0)
        _agenda(tmp_path, "cme")
        defects = _run(tmp_path, monkeypatch)
        assert len(defects) == 1
        kind, msg = defects[0]
        assert kind == "clock-saturation"
        assert "brand_new_axis" in msg
        assert "1/2" in msg
        assert "NEITHER" in msg
        # must NOT accuse the axis that is genuinely accruing
        assert "cme" not in msg

    def test_idle_slot_beside_a_ready_hypothesis(self, tmp_path: Path, monkeypatch) -> None:
        """The literal L1.28a instance: free forward capacity next to an authored hypothesis."""
        _lake(tmp_path, "metal", "mining")
        _slots(tmp_path, accruing=("something_else",), idle=2)
        _agenda(tmp_path, "metal", "mining")
        defects = _run(tmp_path, monkeypatch)
        assert len(defects) == 1
        kind, msg = defects[0]
        assert kind == "clock-saturation"
        assert "2 forward slot(s) sit IDLE" in msg
        assert "metal" in msg and "mining" in msg
        assert "idle research capital" in msg

    def test_both_breaches_are_reported_separately(self, tmp_path: Path, monkeypatch) -> None:
        """Two different failures with two different fixes must not be collapsed into one line."""
        _lake(tmp_path, "metal", "brand_new_axis")
        _slots(tmp_path, idle=1)
        _agenda(tmp_path, "metal")
        msgs = [msg for _, msg in _run(tmp_path, monkeypatch)]
        assert len(msgs) == 2
        assert any("NEITHER" in m_ and "brand_new_axis" in m_ for m_ in msgs)
        assert any("sit IDLE" in m_ and "metal" in m_ for m_ in msgs)


class TestUnmeasured:
    def test_absent_cohort_store_reads_unmeasured_not_healthy(
            self, tmp_path: Path, monkeypatch) -> None:
        """WS-005: absence must never resolve to a clean verdict -- nor to a fabricated breach."""
        _lake(tmp_path, "cme", "metal")
        _agenda(tmp_path, "cme", "metal")
        defects = _run(tmp_path, monkeypatch)
        assert len(defects) == 1
        kind, msg = defects[0]
        assert kind == "clock-saturation"
        assert msg.startswith("UNMEASURED")
        assert "2 verified axes" in msg
        # It must not present itself as an idleness breach: the remedy is repairing the producer.
        assert "OBJECTIVE #2 breach" not in msg

    def test_no_bronze_lake_at_all_is_not_graded(self, tmp_path: Path, monkeypatch) -> None:
        """No ingested axes means nothing to grade -- a clone without the lake is not a breach."""
        assert _run(tmp_path, monkeypatch) == []
