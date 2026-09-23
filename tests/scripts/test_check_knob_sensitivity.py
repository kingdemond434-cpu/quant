"""THE KNOB-SENSITIVITY FENCE WAS GOVERNED BY L1.41 AND NAMED BY NO TEST.

`check_build_standard` reported BELOW-STANDARD on `check_knob_sensitivity.py` with one violation:
"UNTESTED (L2.2): no test file references it -- wiring nothing proves". `libs/validation/
knob_sensitivity.py` (the mechanism) was well tested; the ORGAN that builds the probe roster,
writes the artifact and chooses the exit code was not, so nothing pinned the part that decides
whether the desk hears about an overclaimed knob.

FOUND BY DELETING A MIRROR (R0552). The hand-typed `GOVERNED` roster in
test_build_standard_contract.py listed all 89 organ filenames, and "is this organ named by a
test?" was answered by searching tests/ -- so THE MIRROR SATISFIED THE PROPERTY ON EVERY ORGAN'S
BEHALF. A second copy of a registry, kept to prove coverage, was manufacturing the coverage it
claimed to prove. Deleting it made this gap visible, and `build_report()` had been saying the
same thing independently the whole time.

THE ASSERTION THAT MATTERS MOST IS THE ORGAN'S OWN POSITIVE CONTROL. Its roster carries a probe
that MUST read LOAD_BEARING, and its docstring is explicit about why: "A run where this probe
reads DECORATIVE means the fence itself is broken, not that the desk got safer." A fence whose
every probe reads inert looks exactly like a fence measuring nothing -- so that one probe is the
difference between a measurement and a rubber stamp, and it is pinned here.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from scripts import check_knob_sensitivity as organ


class TestThePositiveControlStillFires:
    """~4s: runs the real walk-forward consumer over the real probe stream. Worth it -- this is
    the only assertion that can tell a working fence from a silent one."""

    def test_the_walk_forward_embargo_reads_load_bearing(self) -> None:
        from libs.validation.knob_sensitivity import measure_knob
        from libs.validation.revalidation import WalkForwardEngine

        arr, engine = organ._stream(), WalkForwardEngine()
        verdict = measure_knob(
            lambda v: round(float(engine.evaluate(
                arr, n_splits=4, test_size=300, embargo=int(v)).is_sharpe), 12),
            (0, 1, 50, 500), name="pc", knob="embargo", consumer="wf")
        assert verdict.status == "LOAD_BEARING", (
            "the fence's own positive control went inert -- the instrument is broken, which is "
            "NOT the same news as the desk having got safer")

    def test_the_probe_stream_is_serially_correlated_or_the_control_proves_nothing(self) -> None:
        """On an IID stream a purge would have nothing to remove even in a consumer that read the
        train set, so every probe would read inert for a reason that is not the knob's fault."""
        import numpy as np
        arr = organ._stream()
        assert len(arr) == 3000
        assert float(np.corrcoef(arr[:-1], arr[1:])[0, 1]) > 0.15

    def test_the_stream_is_fixed_so_a_moved_output_is_attributable_to_the_knob(self) -> None:
        import numpy as np
        assert np.array_equal(organ._stream(), organ._stream())


class TestThePatchIsAlwaysRestored:
    """`_patched` mutates a module constant on the SHIPPED consumer. A patch left behind would
    silently change every later probe -- and every later test in the same process."""

    def test_the_constant_is_restored_after_a_normal_call(self) -> None:
        import libs.autodiscovery.validation as av
        before = av._CPCV_PURGE
        organ._patched(av, "_CPCV_PURGE", 999, lambda: None)
        assert before == av._CPCV_PURGE

    def test_the_constant_is_restored_even_when_the_consumer_raises(self) -> None:
        import libs.autodiscovery.validation as av
        before = av._CPCV_PURGE

        def _boom() -> None:
            raise RuntimeError("consumer blew up mid-probe")

        with pytest.raises(RuntimeError):
            organ._patched(av, "_CPCV_PURGE", 999, _boom)
        assert before == av._CPCV_PURGE, "a raising probe left the desk's constant mutated"


class TestTheExitCodeMatchesTheVerdict:
    """The organ's whole effect on the world is its exit code. OVERCLAIMED is its only defect,
    and UNMEASURED must never ride out as a clean board (L1.28a)."""

    @pytest.fixture
    def _report(self, monkeypatch, tmp_path):
        def _run(status: str, n_probes: int, *argv: str) -> int:
            rep: dict[str, Any] = {
                "status": status, "n_probes": n_probes, "probes": [],
                "n_load_bearing": 0, "n_declared_inert": 0, "n_overclaimed": 0,
                "why": "w", "next_action": "n",
            }
            monkeypatch.setattr(organ, "build", lambda: rep)
            monkeypatch.setattr(organ, "_OUT", tmp_path / "knob_sensitivity.json")
            monkeypatch.setattr("sys.argv", ["check_knob_sensitivity.py", *argv])
            monkeypatch.setattr(organ, "_law_guard", lambda *a, **k: None)
            return organ.main()
        return _run

    def test_ok_exits_zero(self, _report) -> None:
        assert _report("OK", 5) == 0

    @pytest.mark.parametrize("status", ["OVERCLAIMED", "UNMEASURED"])
    def test_a_defect_status_exits_nonzero(self, _report, status: str) -> None:
        assert _report(status, 5) != 0

    def test_a_pass_over_zero_probes_is_refused_as_vacuous(self, _report) -> None:
        """L1.57: this fence's denominator is its roster size, so an OK computed over nothing
        must not read as a clean board -- `all([])` is True and that is the whole hazard."""
        assert _report("OK", 0) != 0

    def test_report_only_always_exits_zero(self, _report) -> None:
        assert _report("OVERCLAIMED", 5, "--report-only") == 0

    def test_it_writes_its_artifact(self, monkeypatch, tmp_path) -> None:
        out = tmp_path / "knob_sensitivity.json"
        monkeypatch.setattr(organ, "build", lambda: {
            "status": "OK", "n_probes": 1, "probes": [], "n_load_bearing": 1,
            "n_declared_inert": 0, "n_overclaimed": 0, "why": "w", "next_action": "n"})
        monkeypatch.setattr(organ, "_OUT", out)
        monkeypatch.setattr(organ, "_law_guard", lambda *a, **k: None)
        monkeypatch.setattr("sys.argv", ["check_knob_sensitivity.py", "--report-only"])
        organ.main()
        assert json.loads(out.read_text("utf-8"))["status"] == "OK"


class TestTheRosterIsDeclaredHonestly:
    def test_every_swept_range_spans_off_to_aggressive(self) -> None:
        """A knob swept over a narrow range can read inert because the range was too small to
        move anything -- which would be a defect in the probe, reported as a defect in the desk."""
        assert min(organ._PURGE_VALUES) == 0 and max(organ._PURGE_VALUES) >= 500
        assert min(organ._EMBARGO_VALUES) == 0.0 and max(organ._EMBARGO_VALUES) >= 0.4

    def test_only_ok_is_a_passing_status(self) -> None:
        assert organ._PASSING == ("OK",)
