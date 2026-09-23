"""Gate item 15: an elite-factory capability is benchmarked, not admired."""
from __future__ import annotations

from pathlib import Path

from libs.research.capability_challenger import (
    EVIDENCE_GRADES,
    Capability,
    adopt,
    chain_gaps,
    record,
    register,
    rows,
)

_CAP = Capability(
    name="checkpointable_preemptible_rnd",
    public_capability="elite factories checkpoint long research jobs so preemption never destroys "
                      "completed computation",
    evidence_grade="FIRST_PARTY_TECHNICAL_DISCLOSURE",
    economic_mechanism="a rate-limited unit re-executed after a crash is paid for twice and "
                       "deepens the throttle that caused the crash",
    desk_analogue="the miner sweep, which restarted from zero on any failure",
    gap="no durable state existed between attempts",
    solo_scale_implementation="libs/ops/checkpoint.py",
    controlled_test="units executed with vs without durable state at an identical failure point",
    chain={"producer": "checkpoint.run", "state": "data/checkpoints/*.json",
           "consumer": "the miner sweep", "decision_consequence": "which queries are re-issued",
           "controlled_benchmark": "tests/ops/test_checkpoint.py::test_controlled_benchmark",
           "runtime_evidence": ""},
)


# ------------------------------------------------------------------ registration
def test_a_complete_walk_registers_with_a_prior_not_a_verdict() -> None:
    out = register(_CAP)
    assert out["status"] == "REGISTERED"
    assert out["prior_strength"] == 1.0 and out["falsification_burden"] == "LOW"


def test_a_blank_station_is_incomplete_and_names_which() -> None:
    """A capability registered with blank stations is worse than an unregistered one: it looks
    analysed."""
    out = register(Capability(**{**_CAP.__dict__, "gap": "", "controlled_test": "  "}))
    assert out["status"] == "INCOMPLETE"
    assert set(out["missing_stations"]) == {"gap", "controlled_test"}


def test_an_unknown_evidence_grade_is_refused_not_coerced() -> None:
    """Coercing a typo to the weakest grade would silently downgrade a first-party disclosure."""
    out = register(Capability(**{**_CAP.__dict__, "evidence_grade": "SOMEONE_SAID_SO"}))
    assert out["status"] == "REFUSED" and "unknown evidence grade" in out["why"]


def test_a_rumour_grade_registers_with_a_high_falsification_burden_not_a_rejection() -> None:
    """The grade sets the PRIOR, never the verdict -- a rumoured capability whose economic
    mechanism stands on its own is still replicable."""
    out = register(Capability(**{**_CAP.__dict__, "evidence_grade": "ANONYMOUS_RUMOR"}))
    assert out["status"] == "REGISTERED"
    assert out["falsification_burden"] == "HIGH" and out["prior_strength"] == 0.0


def test_evidence_grades_are_ordered_strongest_first() -> None:
    assert EVIDENCE_GRADES[0] == "FIRST_PARTY_TECHNICAL_DISCLOSURE"
    assert EVIDENCE_GRADES[-1] == "ANONYMOUS_RUMOR"


# ------------------------------------------------------------------ the ladder
def _ladder(**kw):
    base = {"name": "c", "metric": "units_executed", "higher_is_better": False,
            "simple_baseline": 100.0, "current_champion": 90.0, "candidate": 60.0,
            "runtime_evidence": "live run 2026-08-12"}
    return adopt(**{**base, **kw})


def test_a_measured_winner_with_runtime_evidence_is_adopted() -> None:
    assert _ladder()["verdict"] == "ADOPT"


def test_beating_the_champion_but_not_the_dumb_baseline_is_rejected() -> None:
    """THE ANTI-CARGO-CULT RUNG. 'Beats the current champion' is satisfied equally by a good
    candidate and by a bad champion; only the simple baseline separates those two cases."""
    out = _ladder(simple_baseline=50.0, current_champion=90.0, candidate=70.0)
    assert out["verdict"] == "REJECTED_NO_GAIN_OVER_SIMPLE_BASELINE"
    assert "elite fund" in out["why"]


def test_a_holding_champion_rejects_the_candidate() -> None:
    assert _ladder(candidate=95.0)["verdict"] == "REJECTED_CHAMPION_HOLDS"


def test_a_real_gain_that_costs_more_than_it_earns_is_rejected() -> None:
    out = _ladder(gain_unit="usd", cost_unit="usd", total_cost=40.0,
                  simple_baseline=100.0, current_champion=90.0, candidate=70.0)
    assert out["verdict"] == "REJECTED_COST_EXCEEDS_GAIN"


def test_incommensurable_units_are_unmeasured_never_netted() -> None:
    """'30% faster' minus '$40/mo' is not a comparison, it is two numbers next to each other."""
    out = _ladder(gain_unit="pct_faster", cost_unit="usd_per_month", total_cost=40.0)
    assert out["verdict"] == "UNMEASURED" and "incommensurable" in out["why"]


def test_unstated_units_do_not_grant_permission_to_subtract() -> None:
    out = _ladder(total_cost=5.0)
    assert out["verdict"] == "UNMEASURED"


def test_a_missing_rung_is_unmeasured_not_a_pass() -> None:
    out = _ladder(current_champion=None)
    assert out["verdict"] == "UNMEASURED" and "current_champion" in out["missing"]


def test_higher_is_better_direction_is_honoured() -> None:
    out = adopt(name="c", metric="elogw", higher_is_better=True, simple_baseline=0.01,
                current_champion=0.02, candidate=0.05, runtime_evidence="live")
    assert out["verdict"] == "ADOPT" and out["gain_vs_champion"] == 0.03


# ------------------------------------------------------------------ V-C completion
def test_a_bench_win_without_runtime_evidence_is_only_provisional() -> None:
    """V-C: a bench win is a PREDICTION about production, not an observation of it."""
    out = _ladder(runtime_evidence="")
    assert out["verdict"] == "PROVISIONAL_PENDING_RUNTIME_EVIDENCE"


def test_chain_gaps_names_every_missing_link() -> None:
    assert chain_gaps(_CAP) == ["runtime_evidence"]


def test_a_capability_with_chain_gaps_is_never_marked_complete(tmp_path: Path) -> None:
    row = record(_CAP, _ladder(), root=tmp_path)
    assert row["benchmark"]["verdict"] == "ADOPT"
    assert row["chain_gaps"] == ["runtime_evidence"]
    assert row["complete"] is False, "V-C completion requires every link, not just a bench win"


def test_recorded_rows_are_readable_back(tmp_path: Path) -> None:
    record(_CAP, _ladder(), root=tmp_path)
    got = rows(tmp_path)
    assert len(got) == 1 and got[0]["capability"]["name"] == _CAP.name


def test_a_missing_ledger_reads_as_empty_not_a_crash(tmp_path: Path) -> None:
    assert rows(tmp_path) == []
