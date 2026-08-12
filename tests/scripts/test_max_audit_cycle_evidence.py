"""The two cycle-quality fences, after the R0336 repair.

THE DEFECT THIS LOCKS. On 2026-08-01 `check_interrogation` reported that 20260801_1445.log showed
"no self-interrogation evidence" while `check_rubberstamp_enforcement` reported that the same
log's "interrogation lacks verified-read evidence". Those two statements cannot both be true: one
asserts the interrogation did not happen, the other assumes it did and faults its citations. The
cycle had in fact interrogated well and cited badly. Both defects were acked for 14 days.

The shape being locked cuts both ways:
  * the pair must be SILENT on a cycle that genuinely interrogated AND cited, or it gets acked
    into permanent silence (L1.43);
  * each must still FIRE on its own genuine breach, or the repair would have been a loosening;
  * and they must never again disagree about the same cycle.
"""
from __future__ import annotations

from pathlib import Path

import scripts.max_audit as m

_PAD = "\n" + ("filler line to clear the 2000-byte successful-cycle bar. " * 45)


def _cycle(tmp: Path, name: str, body: str) -> None:
    logs = tmp / "data/cro_ai_logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / name).write_text(body + _PAD, "utf-8")


def _armed(tmp: Path, *, antirubberstamp: bool = True) -> None:
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    (tmp / "data/interrogation_baseline").write_text("0")
    if antirubberstamp:
        (tmp / "data/ANTIRUBBERSTAMP_ACTIVE").write_text("active for the test")


def _run(tmp: Path, monkeypatch) -> list[str]:
    monkeypatch.setattr(m, "ROOT", tmp)
    monkeypatch.setattr(m, "LOGS", tmp / "data/cro_ai_logs")
    defects: list[tuple] = []
    m.check_interrogation(defects)
    m.check_rubberstamp_enforcement(defects)
    return [d[0] for d in defects]


_CITED = "\n".join([
    "read web/growth_audit.json, capital_util=1.005",
    "read data/forward_slots.json, m_concurrent=15 against cap 12",
    "read scripts/max_audit.py:1315, the citation regex counts 5 unique tokens",
    "read libs/ops/fresh.py, max_age_h=0.25",
    "read data/fill_quality.json, maker rate 60.0% on 30 legs",
])


class TestSilentWhenTheCycleDidTheWork:
    def test_a_cited_interrogating_cycle_raises_nothing(self, tmp_path: Path, monkeypatch) -> None:
        _armed(tmp_path)
        _cycle(tmp_path, "20260812_1200.log", _CITED)
        assert _run(tmp_path, monkeypatch) == []

    def test_no_magic_word_is_required(self, tmp_path: Path, monkeypatch) -> None:
        """THE 2026-08-01 FALSE POSITIVE, at fence level. This log contains none of the five
        words the old grep demanded ('interrogat', 'probe', 'verified with a fresh read',
        'self-interrog', 'angle') and must still pass both fences."""
        _armed(tmp_path)
        _cycle(tmp_path, "20260812_1200.log", _CITED)
        body = (tmp_path / "data/cro_ai_logs/20260812_1200.log").read_text()
        assert not any(w in body.lower() for w in ("interrogat", "probe", "self-interrog",
                                                   "angle", "verified with a fresh read"))
        assert _run(tmp_path, monkeypatch) == []


class TestEachStillFiresOnItsOwnBreach:
    def test_a_cycle_that_asserted_and_never_checked_fires_interrogation(
            self, tmp_path: Path, monkeypatch) -> None:
        _armed(tmp_path)
        _cycle(tmp_path, "20260812_1200.log", "Everything looks good. All systems fine. Verified.")
        assert "cycle-skipped-interrogation" in _run(tmp_path, monkeypatch)

    def test_five_uncited_filenames_no_longer_buy_a_pass(
            self, tmp_path: Path, monkeypatch) -> None:
        """The exact gaming the old count permitted: paths with no values."""
        _armed(tmp_path)
        _cycle(tmp_path, "20260812_1200.log", "\n".join([
            "Reviewed scripts/max_audit.py", "Reviewed libs/ops/fresh.py",
            "Reviewed data/forward_slots.json", "Reviewed docs/CONSTITUTION.md",
            "Reviewed ops/deploy.sh", "The premise was refuted by the import graph."]))
        assert "rubberstamp-enforced" in _run(tmp_path, monkeypatch)

    def test_the_flag_still_gates_the_citation_fence(self, tmp_path: Path, monkeypatch) -> None:
        _armed(tmp_path, antirubberstamp=False)
        _cycle(tmp_path, "20260812_1200.log", "The premise was refuted by the import graph.")
        assert "rubberstamp-enforced" not in _run(tmp_path, monkeypatch)


class TestTheyCanNeverContradictAgain:
    def test_interrogated_well_but_cited_badly_fires_exactly_one_fence(
            self, tmp_path: Path, monkeypatch) -> None:
        """The real 2026-08-01 cycle's shape: substance in its own words, citations by bare
        module name. Exactly one fence may speak, and it is the citation one."""
        _armed(tmp_path)
        _cycle(tmp_path, "20260812_1200.log",
               "The premise was refuted by the import graph. My own claim was wrong and is "
               "withdrawn. Checked max_audit.CHECKS -- 12 entries. Hypothesis generation: "
               "not done, named as a debt.")
        raised = _run(tmp_path, monkeypatch)
        assert raised == ["rubberstamp-enforced"]

    def test_both_fences_judge_the_same_log(self, tmp_path: Path, monkeypatch) -> None:
        """Two fences that select their own log by their own window cannot be prevented from
        disagreeing. The older, larger log must be ignored by BOTH."""
        _armed(tmp_path)
        _cycle(tmp_path, "20260801_0000.log", _CITED)
        _cycle(tmp_path, "20260812_1200.log", "Everything looks good. All systems fine.")
        import os
        logs = tmp_path / "data/cro_ai_logs"
        os.utime(logs / "20260801_0000.log", (1_000_000, 1_000_000))
        raised = _run(tmp_path, monkeypatch)
        assert "cycle-skipped-interrogation" in raised
        assert "rubberstamp-enforced" in raised, "same log, both fences, consistent verdicts"


class TestUnmeasuredIsRaisedNotSwallowed:
    def test_no_judgeable_log_is_a_defect_not_a_clean_pass(
            self, tmp_path: Path, monkeypatch) -> None:
        """THE VACUOUS PASS (L1.57). Both predecessors returned silently when their glob found
        nothing, so 'no cycle ran at all' was byte-identical to 'the cycle cited well'."""
        _armed(tmp_path)
        (tmp_path / "data/cro_ai_logs").mkdir(parents=True, exist_ok=True)
        assert _run(tmp_path, monkeypatch) == ["cycle-evidence-unmeasured"]

    def test_a_stub_log_below_the_success_bar_is_unmeasured_not_healthy(
            self, tmp_path: Path, monkeypatch) -> None:
        """The live 2026-08-12 state: the newest log is a 108-byte shell stub."""
        _armed(tmp_path)
        logs = tmp_path / "data/cro_ai_logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "20260812_1336.log").write_text("=== cro_ai attempt ===\n=== exit 1 ===\n")
        assert _run(tmp_path, monkeypatch) == ["cycle-evidence-unmeasured"]

    def test_the_citation_fence_does_not_double_report_unmeasured(
            self, tmp_path: Path, monkeypatch) -> None:
        _armed(tmp_path)
        (tmp_path / "data/cro_ai_logs").mkdir(parents=True, exist_ok=True)
        assert _run(tmp_path, monkeypatch).count("cycle-evidence-unmeasured") == 1
