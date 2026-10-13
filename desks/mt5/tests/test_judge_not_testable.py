"""A cell the judge could not test for want of observations leaves the backlog, named, until its
history grows -- and a cell with a fixable defect does not.

MEASURED ON THE TRADING BOX 2026-10-07: JUDGE_COVERAGE read 1,389,434 unjudged cells, GROWING,
while the latest sweep's UNKNOWN rows were mostly "never fires" (174,024) and "too rare"
(10,188): cells that WERE judged and came back with under the 60 daily observations CPCV and
walk-forward need. They were parked in the unrunnable bank with a re-admission rule, yet still
counted as backlog, so the count could only rise. These tests pin the NOT_TESTABLE class: out of
the backlog, counted per family and per reason, back in when the bank re-admits the cell, and
never applied to the defect classes (`series_exception`, `missing_identity_input`).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402
from research import judging_burndown as jb  # noqa: E402

NOW = datetime(2026, 10, 7, 2, 0, tzinfo=UTC)


def _rows(n: int, fam: str = "alpha") -> list[dict]:
    seen = (NOW - timedelta(hours=5)).isoformat()
    return [{"symbol": f"S{i}", "family": fam, "params": {"rr": 1.0 + i}, "first_seen": seen}
            for i in range(n)]


@pytest.fixture()
def bank(tmp_path, monkeypatch):
    path = tmp_path / "unrunnable_specs.json"
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", path)
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    return path


def _park(path: Path, cells: dict[str, str]) -> None:
    path.write_text(json.dumps({c: {"reason": r, "sym": "S", "family": "alpha", "tf": "H1",
                                    "days": 0, "bar_bytes": 10, "parked_at": NOW.isoformat()}
                                for c, r in cells.items()}), "utf-8")


def test_not_testable_cells_leave_the_backlog_and_are_counted(bank, tmp_path) -> None:
    rows = _rows(5)
    ids = [jc._cell_id(r) for r in rows]
    _park(bank, {ids[0]: "never_fires", ids[1]: "too_rare", ids[2]: "series_exception"})
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json", now=NOW)
    t = doc["totals"]
    assert t["unjudged_total"] == 3                     # the defect stays owed, as do 2 fresh cells
    assert t["not_testable_total"] == 2
    assert t["not_testable_by_reason"] == {"never_fires": 1, "too_rare": 1}
    # NO CELL ENDS UNTESTABLE: all three parked cells are handed to the converter, by class.
    f = t["judging_failures"]
    assert f["parked"] == {"no_series": 1, "untestable_as_specified": 2}
    assert f["handed_to_converter"] == 3
    assert doc["families"]["alpha"]["not_testable"] == 2


def test_the_defect_classes_are_never_not_testable() -> None:
    assert "series_exception" not in jc.NOT_TESTABLE_REASONS
    assert "missing_identity_input" not in jc.NOT_TESTABLE_REASONS
    assert "missing_bars" not in jc.NOT_TESTABLE_REASONS


def test_an_unreadable_bank_counts_everything_as_backlog(bank, tmp_path) -> None:
    bank.write_text("{not json", "utf-8")
    doc = jc.build(_rows(3), ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json",
                   now=NOW)
    assert doc["totals"]["unjudged_total"] == 3
    assert doc["totals"]["not_testable_total"] == 0


def test_a_readmitted_cell_is_backlog_again(bank, tmp_path) -> None:
    """The class is the bank's state, so `readmit_due` decides when a cell is owed again."""
    rows = _rows(1)
    _park(bank, {jc._cell_id(rows[0]): "never_fires"})
    assert jc.not_testable_index() == {jc._cell_id(rows[0]): "never_fires"}
    bank.write_text("{}", "utf-8")                       # re-admitted by the bank
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json", now=NOW)
    assert doc["totals"]["unjudged_total"] == 1


def test_burndown_counts_a_first_not_testable_reading_as_drain(tmp_path) -> None:
    at = (NOW - timedelta(hours=1)).isoformat()
    rows = [
        {"cell": "a", "terminal_gate": "UNKNOWN", "unknown_reason": "no_signals"},
        {"cell": "b", "terminal_gate": "UNKNOWN", "unknown_reason": "too_rare"},
        {"cell": "c", "terminal_gate": "UNKNOWN", "unknown_reason": "series_exception"},
        {"cell": "d", "terminal_gate": "cpcv", "passed": False},
        {"cell": "b", "terminal_gate": "walk_forward", "passed": False},   # b ruled later
    ]
    led = tmp_path / "gate.jsonl"
    led.write_text("".join(json.dumps({**r, "at": at}) + "\n" for r in rows), "utf-8")
    bank = tmp_path / "unrunnable_specs.json"
    bank.write_text(json.dumps({"a": {"reason": "no_signals"}, "b": {"reason": "too_rare"}}),
                    "utf-8")
    d = jb.drain(NOW, led, bank)
    assert d["first_rulings"]["24h"] == 2               # d, b
    assert d["first_settled"]["24h"] == 3               # a, b (once), d -- never c
    assert d["rows"]["24h"]["not_testable"] == 2
    assert d["rows"]["24h"]["unknown"] == 1


def test_a_not_testable_reading_the_bank_never_took_is_not_drain(tmp_path) -> None:
    """Audit of PR #290: parking is drain only through the bank that removes it."""
    at = (NOW - timedelta(hours=1)).isoformat()
    led = tmp_path / "gate.jsonl"
    led.write_text("".join(json.dumps({**r, "at": at}) + "\n" for r in [
        {"cell": "a", "terminal_gate": "UNKNOWN", "unknown_reason": "no_signals"},
        {"cell": "b", "terminal_gate": "UNKNOWN", "unknown_reason": "too_rare"}]), "utf-8")
    bank = tmp_path / "unrunnable_specs.json"
    bank.write_text(json.dumps({"a": {"reason": "no_signals"},
                                "b": {"reason": "series_exception"}}), "utf-8")
    assert jb.drain(NOW, led, bank)["first_settled"]["24h"] == 1
    gone = jb.drain(NOW, led, tmp_path / "absent.json")
    assert gone["first_settled"]["24h"] == 0 and gone["parking_basis"].startswith("UNMEASURED")


def test_a_missing_or_stale_readmission_log_is_unmeasured_never_zero(tmp_path) -> None:
    """Audit of PR #290 (M1): a measured zero here would tip the burn-down to DRAINING."""
    log = tmp_path / "not_testable_readmissions.jsonl"
    assert jb.readmissions(NOW, log)["status"] == jb.UNMEASURED
    log.write_text(json.dumps({"at": (NOW - timedelta(hours=30)).isoformat(),
                               "readmitted": 0}) + "\n", "utf-8")
    assert jb.readmissions(NOW, log)["status"] == jb.UNMEASURED
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": (NOW - timedelta(hours=1)).isoformat(),
                             "readmitted": 0}) + "\n")
    assert jb.readmissions(NOW, log)["status"] == "MEASURED"


def test_draining_on_unknown_readmissions_is_unmeasured() -> None:
    b = {"status": "MEASURED", "unjudged": 1000}
    d = {"status": "MEASURED", "first_rulings_per_hour": {"7d": 50.0},
         "first_settled_per_hour": {"7d": 50.0}}
    i = {"status": "MEASURED", "created_per_hour": {"7d": 10.0},
         "readmitted": {"status": jb.UNMEASURED, "why": "log absent"}}
    assert jb.verdict(b, d, i)["status"] == jb.UNMEASURED
    i["readmitted"] = {"status": "MEASURED", "readmitted": {"7d": 0}}
    assert jb.verdict(b, d, i)["status"] == "DRAINING"


def test_classify_names_only_data_scarcity_as_not_testable() -> None:
    for why in jb.NOT_TESTABLE_UNKNOWN:
        assert jb.classify({"terminal_gate": "UNKNOWN", "unknown_reason": why}) == "not_testable"
    for why in ("series_exception", "no_series", "no_terminal_gate_recorded", ""):
        assert jb.classify({"terminal_gate": "UNKNOWN", "unknown_reason": why}) == "unknown"


def test_the_verdict_divides_by_the_backlogs_own_outflow() -> None:
    b = {"status": "MEASURED", "unjudged": 1000}
    i = {"status": "MEASURED", "created_per_hour": {"7d": 10.0, "24h": 10.0},
         "readmitted": {"status": "MEASURED", "readmitted": {"7d": 0, "24h": 0}}}
    d = {"status": "MEASURED", "first_rulings_per_hour": {"7d": 5.0, "24h": 5.0},
         "first_settled_per_hour": {"7d": 20.0, "24h": 20.0}}
    v = jb.verdict(b, d, i, "7d")
    assert v["status"] == "DRAINING" and v["first_settled_per_hour"] == 20.0
    assert v["first_rulings_per_hour"] == 5.0


def test_fetch_universe_writes_the_swap_reading() -> None:
    src = (DESK / "research" / "fetch_universe.py").read_text("utf-8")
    assert '("swap_long", "swap_short", "swap_mode")' in src


# ------------------------------------------------------------------ audit of PR #290 (2026-10-13)
from research import rejection_throughput as rt  # noqa: E402

#: Every UNKNOWN reason either organ can meet: the table's keys plus the sealed judge's whole
#: vocabulary (classify_unknown / unknown_row_reason), a blank and a reason nobody has named yet.
_JUDGE_VOCAB = ("no_signals", "signals_no_trades", "no_trades", "too_rare",
                "lockbox_consumed_history", "short_history_after_cut", "series_exception",
                "no_series", "observations_under_60_days", "no_terminal_gate_recorded")
ALL_REASONS = sorted(set(jc.UNKNOWN_REASON_CLASS) | set(_JUDGE_VOCAB) | {"", "brand_new_cause"})


def test_every_reason_is_classed_once_and_the_judges_vocabulary_is_covered() -> None:
    assert set(_JUDGE_VOCAB) <= set(jc.UNKNOWN_REASON_CLASS)
    assert set(jc.UNKNOWN_REASON_CLASS.values()) == {jc.NOT_TESTABLE, jc.DEFECT}
    assert jc.unknown_reason_class("") == jc.DEFECT
    assert jc.unknown_reason_class("brand_new_cause") == jc.DEFECT
    for absent in ("no_series", "observations_under_60_days", "no_terminal_gate_recorded",
                   "unnamed", "series_exception", "missing_bars", "missing_identity_input"):
        assert jc.unknown_reason_class(absent) == jc.DEFECT, absent


@pytest.mark.parametrize("reason", ALL_REASONS)
def test_both_organs_class_every_reason_identically(reason: str, bank, tmp_path) -> None:
    expect_nt = jc.unknown_reason_class(reason) == jc.NOT_TESTABLE
    # the burn-down, reading a gate-ledger row
    kind = jb.classify({"terminal_gate": "UNKNOWN", "unknown_reason": reason})
    assert (kind == "not_testable") is expect_nt
    # the coverage table, reading a bank row
    rows = _rows(1)
    _park(bank, {jc._cell_id(rows[0]): reason})
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=tmp_path / "r.json", now=NOW)
    assert doc["totals"]["not_testable_total"] == (1 if expect_nt else 0)
    assert doc["totals"]["unjudged_total"] == (0 if expect_nt else 1)


@pytest.mark.parametrize("declared", (*_JUDGE_VOCAB, ""))
def test_naming_keeps_the_judges_class(declared: str, tmp_path) -> None:
    """`name_unknowns` may refine a reason (never_fires, too_rare) but never move it from defect
    to not-testable: a blank or `no_series` at days == 0 is NOT parked as never_fires."""
    gates = tmp_path / "gates.json"
    v = {"cell": "XAUUSD.f.p=1", "sym": "XAUUSD", "family": "f", "days": 0, "unmeasured": True,
         **({"unknown_reason": declared} if declared else {})}
    gates.write_text(json.dumps({"verdicts": [v]}), "utf-8")
    named = jc.name_unknowns(gates)["XAUUSD.f.p=1"]
    if named["reason"] == "missing_bars":            # no XAUUSD bars on this checkout
        assert jc.unknown_reason_class("missing_bars") == jc.DEFECT
        return
    assert jc.unknown_reason_class(named["reason"]) == jc.unknown_reason_class(declared)
    if declared in ("", "no_series"):
        assert named["reason"] in ("unnamed", "no_series")


def _prior(path: Path, at: datetime, unjudged: int, basis: str | None) -> None:
    doc: dict = {"at": at.isoformat(timespec="seconds"),
                 "families": {"alpha": {"unjudged": unjudged, "queued": 0}}}
    if basis is not None:
        doc["backlog_basis"] = basis
    path.write_text(json.dumps(doc), "utf-8")


def test_a_prior_on_the_old_basis_is_rebased_not_drained(bank, tmp_path) -> None:
    rows = _rows(5)
    _park(bank, {jc._cell_id(rows[0]): "never_fires", jc._cell_id(rows[1]): "too_rare"})
    r = tmp_path / "r.json"
    _prior(r, NOW - timedelta(hours=1), unjudged=5, basis=None)      # pre-PR reading
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=r, now=NOW)
    t, fam = doc["totals"], doc["families"]["alpha"]
    assert t["backlog_rebased"] is True and t["backlog_basis"] == jc.BACKLOG_BASIS
    assert fam["drained"] is None and fam["carried"] is None
    assert t["drain_status"] != "DRAINING"


def test_parking_is_its_own_figure_never_drain(bank, tmp_path) -> None:
    rows = _rows(5)
    prior_at = NOW - timedelta(hours=1)
    ids = [jc._cell_id(x) for x in rows]
    bank.write_text(json.dumps({c: {"reason": "never_fires", "sym": "S", "family": "alpha",
                                    "tf": "H1", "days": 0, "bar_bytes": 10,
                                    "parked_at": prior_at.isoformat(timespec="seconds"),
                                    "not_testable_since": prior_at.isoformat(timespec="seconds")}
                                for c in ids[:2]}), "utf-8")
    r = tmp_path / "r.json"
    _prior(r, prior_at, unjudged=5, basis=jc.BACKLOG_BASIS)
    doc = jc.build(rows, ledger=tmp_path / "none.jsonl", ratchet=r, now=NOW)
    fam = doc["families"]["alpha"]
    assert fam["parked_since_prior"] == 2 and fam["carried"] == 3
    assert fam["drained"] == 0                       # nothing was judged
    assert doc["totals"]["parked_not_testable_since_prior"] == 2


def test_the_drain_status_adds_parking_back() -> None:
    at = NOW - timedelta(hours=1)
    d = jc.drain(3, 10.0, prior_backlog=5, prior_at=at, now=NOW, parked=2)
    assert d["backlog_growth_per_hour"] == 0.0 and d["status"] == "GROWING"
    d = jc.drain(3, 10.0, prior_backlog=5, prior_at=at, now=NOW, rebased="basis changed")
    assert d["status"] == "UNMEASURED"


def test_a_rename_keeps_the_first_parked_at(tmp_path) -> None:
    path = tmp_path / "bank.json"
    first = "2026-09-01T00:00:00+00:00"
    path.write_text(json.dumps({"c": {"reason": "series_exception", "sym": "S", "family": "a",
                                      "bar_bytes": 10, "parked_at": first}}), "utf-8")
    jc.update_unrunnable_bank({"c": {"reason": "never_fires", "sym": "S", "family": "a",
                                     "bar_bytes": 10}}, at=NOW.isoformat(), path=path)
    row = jc.unrunnable_bank(path)["c"]
    assert row["parked_at"] == first
    assert row["not_testable_since"] == NOW.isoformat()  # it LEFT the backlog now
    jc.update_unrunnable_bank({"c": {"reason": "too_rare", "sym": "S", "family": "a",
                                     "bar_bytes": 10}}, at=(NOW + timedelta(hours=1)).isoformat(),
                              path=path)
    row = jc.unrunnable_bank(path)["c"]
    assert row["parked_at"] == first and row["not_testable_since"] == NOW.isoformat()


def test_readmissions_are_logged_and_reach_the_burndown_inflow(tmp_path) -> None:
    path = tmp_path / "bank.json"
    old = "2026-06-01T00:00:00+00:00"                   # past READMIT_MAX_DAYS
    path.write_text(json.dumps({"c": {"reason": "never_fires", "sym": "NOSUCHSYM",
                                      "family": "a", "bar_bytes": 10, "parked_at": old},
                                "d": {"reason": "series_exception", "sym": "NOSUCHSYM",
                                      "family": "a", "bar_bytes": 10, "parked_at": old}}),
                    "utf-8")
    at = (NOW - timedelta(hours=1)).isoformat()
    out = jc.update_unrunnable_bank({}, at=at, path=path)
    assert out["readmitted_not_testable"] == 1          # only the not-testable one is inflow
    assert out["readmitted_not_testable_by_family"] == {"a": 1}
    log = tmp_path / jc.READMISSION_LOG.name
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([{"first_seen": at}]), "utf-8")
    i = jb.inflow(NOW, docket, readmission_log=log)
    assert i["readmitted"]["readmitted"]["24h"] == 1
    assert i["inflow_per_hour"]["24h"] == round(2 / 24.0, 3)


def test_rejection_throughput_names_not_testable() -> None:
    row = {"terminal_gate": "UNKNOWN", "unknown_reason": "too_rare", "passed": False}
    assert rt.outcome(row) == ("unconfident", "not_testable")


def test_the_verdicts_needed_rate_is_in_its_divisors_unit() -> None:
    b = {"status": "MEASURED", "unjudged": 1000}
    i = {"status": "MEASURED", "created_per_hour": {"7d": 10.0, "24h": 10.0},
         "readmitted": {"status": "MEASURED", "readmitted": {"7d": 0, "24h": 0}}}
    d = {"status": "MEASURED", "first_rulings_per_hour": {"7d": 5.0, "24h": 5.0},
         "first_settled_per_hour": {"7d": 20.0, "24h": 20.0}}
    v = jb.verdict(b, d, i, "7d")
    assert v["outflow_unit"] == "settled" and "needed_first_rulings_per_hour" not in v
    assert v["needed_multiple_of_today"] == round(v["needed_settled_per_hour"] / 20.0, 2)
    d2 = {"status": "MEASURED", "first_rulings_per_hour": {"7d": 5.0, "24h": 5.0}}
    v2 = jb.verdict(b, d2, i, "7d")
    assert v2["outflow_unit"] == "first_rulings"
    assert v2["needed_multiple_of_today"] == round(v2["needed_first_rulings_per_hour"] / 5.0, 2)
