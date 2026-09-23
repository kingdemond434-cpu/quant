"""A failing gauntlet must not stop every certificate the desk has ever earned from enrolling.

THE DEFECT, measured 2026-09-05 from the live dashboard. `authorized_runs` read ONE artifact --
`reports/UNIVERSAL_SURVIVORS.json`, the external gauntlet's OUTPUT -- and nothing else. So when
the gauntlet crashes the file goes stale or missing, an absent file reads as `gate_policy = None`,
and the whole-canon policy refusal returns ZERO authorized runs. Not "the newest certificates
cannot enrol": NOTHING can enrol, including cells that passed all ten gates days earlier and sit
in the sealed canon with a valid attestation.

The dashboard showed it as four unrelated faults:

    GAUNTLET: canon last swept 60.8h ago -- the desk gauntlet or the cert pull stopped
    healed: FAILING MT5-Gauntlet: last result 1
    CERTIFIED-NOT-ENROLLED: external.USDZAR.overnight_gap_decay, 91 hours, no forward clock
    CERTIFIED-NOT-ENROLLED: AUDCHF / CADCHF / GBPCHF, 117-142 hours, no forward clock

One cause. Measured on this tree: 0 authorized runs before, 48 after, with all four of those
cells among them.

NOT A LOOSENING, and this is the line the tests below hold. `is_exact_policy` still runs on
whichever artifact is used and `all_ten_pass` still runs per row -- a canon without the exact
ten-gate attestation is refused whole, from either path. What changed is WHICH artifact may carry
that attestation: the sealed canon is the same certificates under the same policy, and is already
what the promoter, the allocator and alpha_genome read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sa = pytest.importorskip("shadow_admission")
gp = pytest.importorskip("gate_policy")


def _tree(tmp_path: Path, *, report: dict | None, canon: dict | None) -> Path:
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    if report is not None:
        (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(report), "utf-8")
    if canon is not None:
        (tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json").write_text(
            json.dumps(canon), "utf-8")
    return tmp_path


def _doc(n: int = 1, *, policy: object) -> dict:
    return {"n": n, "gate_policy": policy, "survivors": {f"external.S{i}.f": {} for i in range(n)}}


class TestTheSealedCanonIsTheFallback:
    def test_a_missing_gauntlet_report_falls_back_to_the_seal(self, tmp_path) -> None:
        """THE DEFECT, directly: the gauntlet is down and the desk still has certificates."""
        base = _tree(tmp_path, report=None, canon=_doc(3, policy=gp.ATTESTATION))
        doc, src = sa._canon(base)
        assert "canon.json" in src and len(doc["survivors"]) == 3

    def test_an_unstamped_report_falls_back_rather_than_refusing_everything(self, tmp_path):
        """A stale or half-written report carries no attestation. That is a reason to read the
        seal, not a reason to stop the desk."""
        base = _tree(tmp_path, report=_doc(0, policy=None), canon=_doc(5, policy=gp.ATTESTATION))
        doc, src = sa._canon(base)
        assert "canon.json" in src and len(doc["survivors"]) == 5

    def test_a_fresh_stamped_report_is_still_preferred(self, tmp_path) -> None:
        """The seal is a FALLBACK. When the gauntlet is healthy its sweep is the newer truth."""
        base = _tree(tmp_path, report=_doc(9, policy=gp.ATTESTATION),
                     canon=_doc(2, policy=gp.ATTESTATION))
        doc, src = sa._canon(base)
        assert "reports/" in src and len(doc["survivors"]) == 9


class TestTheGateStillBinds:
    def test_neither_artifact_stamped_still_refuses_the_whole_canon(self, tmp_path) -> None:
        """The fallback may only find the same certificates elsewhere. It may never admit a canon
        the primary would have refused."""
        base = _tree(tmp_path, report=_doc(4, policy=None), canon=_doc(4, policy={"version": "x"}))
        assert sa.authorized_runs(base) == []
        assert sa.DROPPED_CERTIFICATES, "a whole-canon refusal must still be named"

    def test_the_refusal_names_every_artifact_it_tried(self, tmp_path) -> None:
        """The old message named one file, so a reader chased the wrong artifact. It now lists the
        order and says to check the seal first when the gauntlet is failing."""
        base = _tree(tmp_path, report=_doc(1, policy=None), canon=_doc(1, policy=None))
        sa.authorized_runs(base)
        why = sa.DROPPED_CERTIFICATES[0]["why"]
        assert "reports/UNIVERSAL_SURVIVORS.json" in why
        assert "data/UNIVERSAL_SURVIVORS.canon.json" in why
        assert "SEALED canon" in why

    def test_a_wrong_policy_in_the_seal_is_not_admitted_by_being_second(self, tmp_path) -> None:
        base = _tree(tmp_path, report=None, canon=_doc(3, policy={"version": "something-else"}))
        assert sa.authorized_runs(base) == []

    def test_both_sources_are_declared_in_order(self) -> None:
        rels = [rel for rel, _ in sa.CANON_SOURCES]
        assert rels == ["reports/UNIVERSAL_SURVIVORS.json", "data/UNIVERSAL_SURVIVORS.canon.json"]


def test_the_four_dashboard_cells_can_enrol_on_this_tree() -> None:
    """THE MEASUREMENT THAT MOTIVATED THIS, kept as a fence. These four certificates passed all
    ten gates between 91 and 142 hours before the dashboard reported them with no forward clock,
    and the cause was that NOTHING could enrol at all."""
    runs = sa.authorized_runs(_DESK)
    if not runs:
        pytest.skip("no canon on this host")
    got = {str(r.get("symbol")) for r in runs if str(r.get("family")) == "overnight_gap_decay"}
    assert {"USDZAR", "AUDCHF", "CADCHF", "GBPCHF"} <= got, (
        f"the cells the dashboard named still cannot enrol: {sorted(got)}")
