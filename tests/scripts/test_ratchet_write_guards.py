"""A TEST RUN IS AN OBSERVATION AND MUST NEVER BE A WRITE TO THE THING OBSERVED (GAP 113).

Measured 2026-08-13: a full `pytest` on a clone rewrote three TRACKED files downward.

    docs/research/next_law_number.txt        60 -> 43   would hand the next two laws a number
                                                        already in use -- the exact collision the
                                                        file exists to prevent
    docs/research/trade_forensics_latest.json  n_closes 27 -> 0, every net zeroed, on a host
                                                        holding no trade data

The second is the worse one and the reason this file exists: an empty forensics document and a
desk that genuinely closed nothing are the SAME BYTES, so the damage is undetectable after the
fact. A ratchet that any host can recompute downward is not a ratchet.

Two different repairs, deliberately, because the two failures are different:
  * the law number is MONOTONE BY DEFINITION, so it becomes a max() against the stored value and
    is correct on every host -- including this one after a doc is renamed or briefly unreadable.
  * the forensics copy depends on data this host may not have, so it is guarded by OWNERSHIP.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.max_audit as m

from libs.ops import desk_host


class TestTheLawNumberOnlyEverRises:
    def _docs(self, tmp: Path, highest: int) -> None:
        d = tmp / "docs/research"
        d.mkdir(parents=True, exist_ok=True)
        (d / "laws.md").write_text(f"## {highest}. A LAW TITLE LONG ENOUGH TO MATCH\n", "utf-8")

    def test_a_host_seeing_fewer_laws_cannot_drive_the_marker_down(
            self, tmp_path: Path, monkeypatch) -> None:
        """THE MEASURED DEFECT. Absent or unreadable law docs are skipped, so the max falls with
        them -- and the file then hands out a number already in use."""
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "_LAW_DOCS", ["docs/research/laws.md"])
        marker = tmp_path / "docs/research/next_law_number.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("60\n\nprior high-water mark\n", "utf-8")

        self._docs(tmp_path, 42)                    # this host can only see up to §42
        m.check_law_numbers_unique([])

        assert marker.read_text("utf-8").split("\n")[0] == "60", (
            "the marker fell to a partial host's reading -- the next two laws would collide")

    def test_it_still_rises_when_a_genuinely_higher_law_lands(
            self, tmp_path: Path, monkeypatch) -> None:
        """NEGATIVE CONTROL: a ratchet that can only refuse is a frozen number, not a ratchet."""
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "_LAW_DOCS", ["docs/research/laws.md"])
        marker = tmp_path / "docs/research/next_law_number.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("60\n", "utf-8")

        self._docs(tmp_path, 77)
        m.check_law_numbers_unique([])

        assert marker.read_text("utf-8").split("\n")[0] == "78"

    def test_no_prior_marker_is_written_from_scratch(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "_LAW_DOCS", ["docs/research/laws.md"])
        self._docs(tmp_path, 12)
        m.check_law_numbers_unique([])
        assert (tmp_path / "docs/research/next_law_number.txt").read_text(
            "utf-8").split("\n")[0] == "13"


class TestForensicsNeverOverwritesRealEvidenceFromAHostWithoutTrades:
    def test_the_tracked_copy_is_guarded_by_OWNERSHIP_not_by_content(self) -> None:
        """Content cannot be the guard. A zero-close document is well-formed and indistinguishable
        from a real quiet period, which is exactly why this must be decided by WHO IS ASKING."""
        src = Path(__file__).resolve().parents[2] / "scripts/run_trade_forensics.py"
        text = src.read_text("utf-8")
        assert "is_owning_host()" in text
        # the untracked runtime copy must stay unconditional -- the executor's denylist reads it
        # and a stale denylist is the dangerous direction
        before_guard = text.split("owns, why = is_owning_host()")[0]
        assert "_OUT.write_text" in before_guard, (
            "the executor's denylist source must be written unconditionally; only the shared, "
            "committed copy is guarded")

    def test_a_non_owning_host_leaves_the_tracked_file_alone(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv(desk_host.ENV_OVERRIDE, raising=False)
        assert desk_host.is_owning_host(tmp_path)[0] is False

    @pytest.mark.parametrize("marker_present", [False, True])
    def test_ownership_is_the_only_thing_that_changes_the_answer(
            self, tmp_path: Path, monkeypatch, marker_present: bool) -> None:
        monkeypatch.delenv(desk_host.ENV_OVERRIDE, raising=False)
        if marker_present:
            desk_host.stamp(tmp_path)
        assert desk_host.is_owning_host(tmp_path)[0] is marker_present


def test_the_live_tracked_forensics_doc_is_not_an_empty_shell() -> None:
    """The artifact this defect actually damaged, asserted on the real committed file.

    A zero-close document that was ONCE real is the fingerprint of the bug having run here.
    """
    p = Path(__file__).resolve().parents[2] / "docs/research/trade_forensics_latest.json"
    if not p.exists():
        pytest.skip("no tracked forensics doc in this checkout")
    doc = json.loads(p.read_text("utf-8"))
    basis = doc.get("bleeding_basis") or {}
    assert basis.get("n_closes", 0) > 0, (
        "the committed forensics doc reports zero closes -- either the desk has genuinely never "
        "closed a trade, or a host without the trade log overwrote real evidence with an empty "
        "shell. The two are the same bytes, which is why the write is now ownership-guarded")
