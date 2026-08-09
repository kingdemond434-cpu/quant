"""R0095 (E-6/E-13): the intelligence cycle must report what actually happened.

Two honesty defects fixed here, both of the crash-reported-as-data-gap class:
  * _subprocess_cap labelled ANY nonzero exit NO-INPUT -- the label factory crashed daily
    for weeks and the cycle reported it as an absent-input condition.
  * _research_priority ranked HARDCODED constants while reporting ACTIVE ("ranked N
    categories by decay pressure"), indistinguishable from a measured ranking.
"""

from __future__ import annotations

from unittest import mock

import scripts.run_intelligence_cycle as ic


class TestSubprocessCapStatus:
    def test_nonzero_exit_is_error_not_no_input(self) -> None:
        fake = mock.Mock(returncode=3, stdout="Traceback ...\nValueError: boom", stderr="")
        with mock.patch.object(ic.subprocess, "run", return_value=fake):
            out = ic._subprocess_cap("x", "scripts/build_labels.py", timeout_s=5)
        assert out["status"] == "ERROR", "a crash is a crash, not an absent input"
        assert "exit=3" in out["detail"]

    def test_zero_exit_is_active(self) -> None:
        fake = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(ic.subprocess, "run", return_value=fake):
            out = ic._subprocess_cap("x", "scripts/build_labels.py", timeout_s=5)
        assert out["status"] == "ACTIVE"


class TestResearchPriorityWiring:
    def test_ranks_from_mechanism_board_when_kpis_lack_families(self) -> None:
        def reader(rel: str):
            if rel == "data/mechanism_board.json":
                return {"verdicts": {"M_PRICE_PATTERN": "FAMILY KILL",
                                     "M_FORCED_DELEVERAGE": "ALIVE",
                                     "M_LIQUIDITY_WITHDRAWAL": "UNTESTED"}}
            return {}
        with mock.patch.object(ic, "_read", side_effect=reader):
            out = ic._research_priority()
        assert out["status"] == "ACTIVE"
        assert "mechanism_board" in out["detail"], "the source must be named, not implied"
        top = {t["category"]: t["score"] for t in out["top"]}
        assert top["M_PRICE_PATTERN"] > top["M_FORCED_DELEVERAGE"], (
            "a killed family carries more decay pressure than a live one"
        )

    def test_no_measured_record_is_data_free_not_active(self) -> None:
        with mock.patch.object(ic, "_read", return_value=None):
            out = ic._research_priority()
        assert out["status"] == "NO-INPUT"
        assert "DATA-FREE" in out["detail"], "constants must never masquerade as a ranking"


class TestPhantomInputPaths:
    """R0228 and the second instance found by generalising it.

    THE CLASS. `_read` returns None for a missing file exactly as it does for an empty one, and
    the callers spend that None through `or {}`. So a path that NOTHING IN THE REPO EVER WRITES
    reads as a valid default forever, and the capability goes on to report a confident verdict
    built on it. R0228 was `web/regime.json` (the regime engine writes `web/regime_engine.json`);
    `data/alpha_registry.json` was the same bug one function down, and it was laundering an
    unreadable artifact into "registry holds 0" -- a claim about the DESK'S ALPHA COUNT.

    The structural test below is the part that outlives both fixes: it is the grep that proved
    R0228 ("no writer of web/regime.json anywhere"), run as a gate instead of once by hand.
    """

    def test_every_read_path_has_a_writer_in_the_repo(self) -> None:
        """A literal input path no other module writes is a phantom BY CONSTRUCTION.

        Existence on THIS box cannot be the assertion -- web/ and most of data/ are gitignored
        runtime artifacts, so a fresh checkout would fail on paths that are perfectly real. Having
        a producer somewhere in the tree is the invariant that holds in both worlds, and it is the
        one the phantom paths broke.
        """
        import ast
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[2]
        src = root / "scripts/run_intelligence_cycle.py"
        tree = ast.parse(src.read_text("utf-8"))

        # EVERY artifact-shaped literal in the module, not just the ones passed directly to
        # `_read`. Scoping the scan to `_read(...)` arguments was this test's own first blind
        # spot: `reg = "web/alpha_lifecycle.json"` followed by `_read(reg)` is the identical bug
        # and the argument-only scan could not see it. A guard that enumerates a subset of its
        # input space is exactly the failure this file exists to catch.
        artifact = re.compile(r"^(?:data|web|docs|reports)/[\w./-]+\.(?:json|jsonl|sqlite|csv)$")
        reads = {n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and artifact.match(n.value)}
        assert reads, "the AST scan found no artifact paths -- the test has gone blind"

        producers = [
            p for p in (*(root / "scripts").rglob("*.py"), *(root / "libs").rglob("*.py"))
            if p != src
        ]
        blobs = [p.read_text("utf-8", errors="ignore") for p in producers]
        phantoms = []
        for rel in sorted(reads):
            # Whole-token match. A bare `in` substring test was the second blind spot: it scored
            # the phantom `web/regime.json` as produced because "regime.json" sits inside
            # "crypto_regime.json", which is a DIFFERENT artifact written by a different organ.
            name = re.compile(r"(?<![\w.-])" + re.escape(rel.rsplit("/", 1)[-1]))
            if not any(name.search(text) for text in blobs):
                phantoms.append(rel)
        assert not phantoms, (
            f"phantom input path(s) with no producer anywhere in scripts/ or libs/: {phantoms}. "
            "This organ will read them as an empty default forever and report a verdict built "
            "on nothing (R0228)."
        )

    def test_meta_learning_says_no_input_when_regime_artifact_is_absent(self) -> None:
        """Missing regime labels must NOT degrade into a regime literally named 'unlabelled'."""
        with mock.patch.object(ic, "_read", return_value={"returns": [0.01] * 25}), \
             mock.patch.object(ic, "_absent", return_value=["web/regime_engine.json"]):
            out = ic._meta_learning()
        assert out["status"] == "NO-INPUT", "an unreadable input is never an ACTIVE measurement"
        assert "regime_engine.json" in out["detail"], "name the artifact that was missing"

    def test_meta_learning_uses_the_real_regime_label(self) -> None:
        def reader(rel: str):
            if rel == "web/regime_engine.json":
                return {"regime": "bull/low_vol"}
            return {"returns": [0.01, -0.02] * 15}
        with mock.patch.object(ic, "_read", side_effect=reader), \
             mock.patch.object(ic, "_absent", return_value=[]):
            out = ic._meta_learning()
        assert out["status"] == "ACTIVE"
        assert "bull/low_vol" in out["detail"], (
            "the label must come from the artifact the regime engine actually writes"
        )
        assert "unlabelled" not in out["detail"]

    def test_health_monitor_separates_absent_registry_from_zero_alphas(self) -> None:
        """'No registry on disk' is a claim about this BOX; 'holds 0' is a claim about the DESK."""
        with mock.patch.object(ic, "_absent", return_value=["web/alpha_lifecycle.json"]):
            out = ic._health_monitor()
        assert out["status"] == "NO-INPUT"
        assert "NOT a measurement" in out["detail"], (
            "an artifact-absence must never be reported as a measured alpha count"
        )
