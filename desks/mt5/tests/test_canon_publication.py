"""The canonical seal is republished after the judge, atomically, and mints nothing.

THE DEFECT THESE PIN (measured on the trading box 2026-09-24):
`desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json` carried `swept_at 2026-09-03T08:45:17` while the
sealed judge had appended 146,359 verdicts and republished `reports/UNIVERSAL_SURVIVORS.json`
since. Nothing on any clock copied the judge's report into the seal, and the seal's MTIME was
recent because other organs heal and prune it -- so a freshness check on the file was green while
its sweep stamp was twenty-one days old.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.gate_policy import ATTESTATION, GATES  # noqa: E402

from research import canon_publication as cp  # noqa: E402


def _passing_gates() -> dict[str, dict[str, bool]]:
    return {name: {"passed": True} for name in GATES}


def _report(survivors: dict[str, dict], swept_at: str) -> dict:
    return {"n": len(survivors), "survivors": survivors, "gate_policy": dict(ATTESTATION),
            "note": "UNIVERSAL 10-GATE PASS ONLY.", "swept_at": swept_at}


def _row(sym: str = "XAUUSD") -> dict:
    return {"hunt": "external_discoveries", "cell": f"{sym}.session_range_breakout",
            "sym": sym, "days": 420, "gates": _passing_gates(),
            "shadow_spec": {"symbol": sym, "selector": "asia",
                            "family": "session_range_breakout", "params": {"rr": 1.5}}}


@pytest.fixture()
def desk(tmp_path: Path) -> Path:
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    return tmp_path


def test_seal_takes_the_judges_sweep_stamp_not_its_own(desk: Path) -> None:
    """The seal must date the RUN, never the publication. That conflation hid 21 days."""
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    report.write_text(json.dumps(_report({"external.A": _row("XAUUSD")},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    seal.write_text(json.dumps({"n": 0, "survivors": {}, "swept_at": "2026-09-03T08:45:17+00:00"}),
                    "utf-8")

    rec = cp.publish(report, seal)

    assert rec["status"] == "SEALED"
    doc = json.loads(seal.read_text("utf-8"))
    assert doc["swept_at"] == "2026-09-23T05:42:42+00:00"
    assert doc["published_by"] == "research/canon_publication.py"
    # published_at and swept_at are different facts and both are recorded.
    assert doc["published_at"] != doc["swept_at"]
    assert rec["seal_lag_hours_before"] is not None


def test_never_shrinks_the_seal(desk: Path) -> None:
    """A sweep that certified nothing preserves what stands (the certifier wipe, 2026-08-26)."""
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    standing = {"external.OLD": _row("EURUSD")}
    seal.write_text(json.dumps({"n": 1, "survivors": standing,
                                "swept_at": "2026-09-03T00:00:00+00:00"}), "utf-8")
    report.write_text(json.dumps(_report({}, "2026-09-23T05:42:42+00:00")), "utf-8")

    rec = cp.publish(report, seal)

    assert rec["status"] == "SEALED"
    doc = json.loads(seal.read_text("utf-8"))
    assert set(doc["survivors"]) == {"external.OLD"}
    assert rec["admitted"] == 0


def test_mints_nothing_a_row_without_ten_passes_is_refused(desk: Path) -> None:
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    partial = _row("GBPUSD")
    partial["gates"] = {**_passing_gates(), GATES[2]: {"passed": False}}
    report.write_text(json.dumps(_report({"external.NEW": partial},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    seal.write_text(json.dumps({"n": 0, "survivors": {}}), "utf-8")

    rec = cp.publish(report, seal)

    assert json.loads(seal.read_text("utf-8"))["survivors"] == {}
    assert rec["refused_rows"]["not_all_ten_pass"] == 1


def test_a_retired_key_is_never_revived(desk: Path) -> None:
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    report.write_text(json.dumps(_report({"external.GONE": _row("USDJPY")},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    seal.write_text(json.dumps({
        "n": 0, "survivors": {},
        "retired_certificates": {"external.GONE": {"retired_reason": "symbol untradeable"}},
    }), "utf-8")

    rec = cp.publish(report, seal)

    doc = json.loads(seal.read_text("utf-8"))
    assert "external.GONE" not in doc["survivors"]
    assert "external.GONE" in doc["retired_certificates"]
    assert rec["refused_rows"]["retired"] == 1


def test_an_evicted_unrunnable_row_is_never_re_admitted(desk: Path) -> None:
    """MEASURED ON THIS ORGAN'S FIRST REAL RUN (2026-09-24), and it is why the test exists.

    It admitted six keys and ALL SIX were rows `certificate_hygiene` had already moved to
    reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json. Eviction is not revocation, so those rows still
    stand in the judge's report -- a republisher that does not read `unrunnable_evicted` undoes
    the hygiene pass every hour while reporting six new certificates.
    """
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    report.write_text(json.dumps(_report({"external.EVICTED": _row("CADJPY"),
                                          "external.FINE": _row("EURUSD")},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    seal.write_text(json.dumps({"n": 0, "survivors": {},
                                "unrunnable_evicted": ["external.EVICTED"]}), "utf-8")

    rec = cp.publish(report, seal)

    doc = json.loads(seal.read_text("utf-8"))
    assert "external.EVICTED" not in doc["survivors"]
    assert "external.FINE" in doc["survivors"]
    assert rec["refused_rows"]["unrunnable_evicted"] == 1


def test_a_row_the_engine_cannot_enrol_is_refused_by_the_shared_judge(desk: Path) -> None:
    """`unrunnable_evicted` is the RECORD; survivor_publication.unrunnable_reason is the RULE.

    A row that became unenrollable since the last hygiene pass is on no eviction list, and
    without the shared predicate it would enter the seal and wait an hour to be evicted again.
    """
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    no_spec = _row("EURUSD")
    no_spec.pop("shadow_spec")
    report.write_text(json.dumps(_report({"external.NOSPEC": no_spec},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    seal.write_text(json.dumps({"n": 1, "survivors": {"external.OLD": _row("AUDUSD")}}), "utf-8")

    rec = cp.publish(report, seal)

    assert "external.NOSPEC" not in json.loads(seal.read_text("utf-8"))["survivors"]
    assert rec["refused_rows"]["unrunnable_spec"] == 1


def test_carried_records_of_other_organs_survive_publication(desk: Path) -> None:
    """The retirers', the healer's and the hygiene pass's records are not erased by a republish."""
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    report.write_text(json.dumps(_report({"external.A": _row()},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    seal.write_text(json.dumps({
        "n": 0, "survivors": {}, "revoked_at": "2026-09-21T10:08:50+00:00",
        "unrunnable_evicted": ["external.X"], "unrunnable_note": "moved to their own file",
        "healed_at": "2026-09-23T09:04:07+00:00", "healed_by": "certificate_truth",
    }), "utf-8")

    cp.publish(report, seal)

    doc = json.loads(seal.read_text("utf-8"))
    for key in cp.CARRIED:
        if key != "retired_certificates":
            assert key in doc, f"{key} was dropped by a republication"


def test_unattested_report_leaves_the_seal_untouched(desk: Path) -> None:
    """A canonical store overwritten from an unattested source is the certifier wipe again."""
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    report.write_text(json.dumps({"n": 1, "survivors": {"external.A": _row()},
                                  "gate_policy": {"version": "something-else"},
                                  "swept_at": "2026-09-23T05:42:42+00:00"}), "utf-8")
    before = json.dumps({"n": 1, "survivors": {"external.OLD": _row("EURUSD")},
                         "swept_at": "2026-09-03T08:45:17+00:00"})
    seal.write_text(before, "utf-8")

    rec = cp.publish(report, seal)

    assert rec["status"] == "UNATTESTED_REPORT"
    assert rec["sealed"] is False
    assert seal.read_text("utf-8") == before


def test_missing_report_is_named_not_treated_as_an_empty_sweep(desk: Path) -> None:
    """UNMEASURED is a real answer (L1.28a); absence never empties a certificate store."""
    seal = desk / "data" / "canon.json"
    seal.write_text(json.dumps({"n": 1, "survivors": {"external.OLD": _row("EURUSD")}}), "utf-8")

    rec = cp.publish(desk / "reports" / "absent.json", seal)

    assert rec["status"] == "NO_REPORT"
    assert rec["sealed"] is False
    assert json.loads(seal.read_text("utf-8"))["survivors"]


def test_write_is_atomic_no_partial_file_is_ever_visible(desk: Path, monkeypatch) -> None:
    """A reader sees the old seal or the new one. A crash mid-write leaves the old one."""
    report, seal = desk / "reports" / "u.json", desk / "data" / "canon.json"
    report.write_text(json.dumps(_report({"external.A": _row()},
                                         "2026-09-23T05:42:42+00:00")), "utf-8")
    before = json.dumps({"n": 1, "survivors": {"external.OLD": _row("EURUSD")}})
    seal.write_text(before, "utf-8")

    real_replace = cp.os.replace

    def _boom(src, dst):
        raise OSError("disk went away mid-publication")

    monkeypatch.setattr(cp.os, "replace", _boom)
    with pytest.raises(OSError):
        cp.publish(report, seal)
    assert seal.read_text("utf-8") == before, "a failed rename must leave the old seal intact"
    assert not list(seal.parent.glob(".canon.json.*")), "the temp file must be cleaned up"

    monkeypatch.setattr(cp.os, "replace", real_replace)
    assert cp.publish(report, seal)["status"] == "SEALED"


def test_derived_view_is_labelled_and_carries_no_promotion_authority(tmp_path: Path) -> None:
    """When the judge did not republish, the fallback must be unmistakably derived."""
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(row) for row in [
        {"at": "2026-09-23T05:42:44+00:00", "cell": "GBPJPY@M1.srb.p=1", "sym": "GBPJPY",
         "family": "session_range_breakout", "passed": False, "terminal_gate": "in_sample_screen"},
        {"at": "2026-09-23T05:42:45+00:00", "cell": "XAUUSD.srb.p=2", "sym": "XAUUSD",
         "family": "session_range_breakout", "passed": True, "terminal_gate": "PASSED"},
    ]) + "\n", "utf-8")

    view = cp.derive_from_ledger(ledger)

    assert view["derived"] is True
    assert view["promotion_authority"] is False
    assert view["n"] == 1 and "XAUUSD.srb.p=2" in view["cells"]
    # THE POINT: no row here can satisfy the ten-gate predicate, so nothing may be promoted.
    from research.gate_policy import all_ten_pass
    for row in view["cells"].values():
        assert not all_ten_pass(row.get("gates"))
    assert "NOT A CERTIFICATE STORE" in view["note"]


def test_absent_ledger_is_unmeasured_not_zero(tmp_path: Path) -> None:
    view = cp.derive_from_ledger(tmp_path / "nope.jsonl")
    assert view["status"] == "UNMEASURED"
    assert view["n"] == 0


def test_the_funnel_joins_the_admission_census_to_the_seal(tmp_path: Path) -> None:
    """Raw -> admissible -> judged -> certified -> sealed, in one artifact.

    The two halves were published by two organs into two files and nothing put them side by side,
    which is how a 244,275-row BANK came to be read as a backlog the gates were failing to clear.
    """
    screen = tmp_path / "ADMISSION_SCREEN.json"
    screen.write_text(json.dumps({"status": "MEASURED", "measured_at": "2026-09-24T00:00:00+00:00",
                                  "raw_cells": 244275, "admissible_cells": 212924,
                                  "refused_cells": 31351,
                                  "refused_by_reason": {"untradeable_symbol": 12562}}), "utf-8")
    out = cp._funnel(screen)
    assert out["raw_cells"] == 244275 and out["admissible_cells"] == 212924


def test_an_absent_admission_census_is_unmeasured_not_an_empty_docket(tmp_path: Path) -> None:
    out = cp._funnel(tmp_path / "absent.json")
    assert out["status"] == "UNMEASURED"
    assert "raw_cells" not in out


def test_the_leg_is_on_a_clock_and_belongs_to_a_layer() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16). Done means it runs and leaves an artifact."""
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["canon_publication"] == "prediction"
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"canon_publication", "research/canon_publication.py"' in cycle
    assert '"canon_publication": cpub' in cycle
