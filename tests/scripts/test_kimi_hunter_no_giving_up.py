"""L1.54 NO GIVING UP, pinned on the organ that proved why the law was needed.

THE MEASUREMENT THAT MOTIVATES THIS SUITE. kimi_hunter is the desk's widest non-Claude lens,
scheduled every three hours plus two deep runs a week -- 56 firings a week. It had produced
EXACTLY NOTHING since it was built: no data/kimi_hunt.json, no data/hunt_coverage.json, no
suggestion-ledger row. Not because the Deep Forest protocol is wrong (it is good, and its
admission gates selftest 9/9) but because the file named ONE model string and every route past
that string was an exit:

    absent from the roster        -> SystemExit(2)
    out of credit                 -> SystemExit(3)
    any transport error mid-wave  -> SystemExit(3), discarding completed waves held in memory only

And it failed in the worst way available: SILENTLY, with no artifact. An organ firing 56 times a
week was indistinguishable from an organ nobody had scheduled -- the desk could not tell a bill to
pay from a thing to build.

Each test below pins one operative clause, and each guards a regression that would look like
reasonable tidying: collapsing the chain back to one preferred model, letting a failed stage abort
the run, deferring the coverage write to the end "so it is written once", or dropping the BLOCKED
artifact because "the exit code already says it failed".
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
import scripts.kimi_hunter as K

_SRC = Path("scripts/kimi_hunter.py")


def _code() -> str:
    """The module's CODE, comments stripped.

    Every assertion below describes the deleted construct in prose directly above the line that
    replaced it, so searching the raw file finds the explanation and reports the bug as still
    present. Stripping comments first is not a convenience -- without it these change-detectors
    fail on their own documentation.
    """
    return "\n".join(ln for ln in _SRC.read_text("utf-8").splitlines()
                      if not ln.lstrip().startswith("#"))


def _wave_loop() -> ast.For:
    """The wave loop, located by PARSING rather than by slicing the file on marker strings.

    A string slice was tried first and was wrong in the quiet direction: it captured setup code
    from above the loop, so an assertion about what the loop does was really an assertion about
    the whole function. Nothing failed loudly -- it just stopped testing what it named. The AST
    knows where the loop starts and ends; nothing else here does.
    """
    tree = ast.parse(_SRC.read_text("utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    for node in ast.walk(main):
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "(1, 2, 3)":
            return node
    raise AssertionError("the wave loop `for w in (1, 2, 3)` is gone from main()")


class TestAChainNeverASingleName:
    def test_the_chain_has_real_depth_and_a_free_tier_at_the_end(self) -> None:
        assert len(K.MODEL_CHAIN) >= 4, "one or two routes is not a chain"
        assert any(m.endswith(":free") for m in K.MODEL_CHAIN), (
            "a free tier must be present -- 'the account is unfunded' is a reason to hunt "
            "cheaper, never a reason to stop hunting")
        free_at = min(i for i, m in enumerate(K.MODEL_CHAIN) if m.endswith(":free"))
        paid_at = max(i for i, m in enumerate(K.MODEL_CHAIN) if not m.endswith(":free"))
        assert free_at > paid_at, "free tiers belong at the END of the chain, not the front"

    def test_the_chain_spans_more_than_one_model_family(self) -> None:
        """Same-family fallbacks share a prior about what is under-observed, and the hunt's whole
        value is a DIFFERENT prior. A chain of four Kimi versions is one opinion, four times."""
        families = {m.split("/")[0] for m in K.MODEL_CHAIN}
        assert len(families) >= 3, f"only {families} -- the fallback must change the lens too"

    def test_a_roster_seat_can_route_a_chain_model_it_is_not_named_as(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The exact dead end that produced zero hunts: a roster holding OpenRouter seats, none of
        them literally named `moonshotai/kimi-k3`, yielded "not in the seated roster" and exit 2.
        OpenRouter routes by the `model` field, not by which model the credential was filed under.
        """
        keys = tmp_path / "llm_panel.json"
        keys.write_text(json.dumps({"providers": [
            {"model": "some/other-model", "base_url": "https://openrouter.ai/api/v1",
             "key": "sk-test"}]}), "utf-8")
        monkeypatch.setattr(K, "KEYS", keys)
        chain = K._providers()
        assert chain, "an OpenRouter seat must be able to route the chain models"
        assert K.MODEL_CHAIN[0] in {m for m, _, _ in chain}, "the preferred model must be tried"

    def test_no_credential_anywhere_yields_an_empty_chain_not_an_invention(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(K, "KEYS", tmp_path / "absent.json")
        assert K._providers() == []

    def test_a_malformed_roster_is_survived(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bad = tmp_path / "llm_panel.json"
        bad.write_text("{not json", "utf-8")
        monkeypatch.setattr(K, "KEYS", bad)
        assert K._providers() == [], "a broken roster must not raise out of a scheduled organ"

    def test_seats_without_a_key_or_base_url_are_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        keys = tmp_path / "llm_panel.json"
        keys.write_text(json.dumps({"providers": [
            {"model": "a/b", "base_url": "https://openrouter.ai/api/v1"},   # no key
            {"model": "c/d", "key": "sk-x"}]}), "utf-8")                    # no base_url
        monkeypatch.setattr(K, "KEYS", keys)
        assert K._providers() == []


class TestABlockedAttemptLeavesEvidence:
    def test_the_blocked_artifact_names_the_blocker_and_the_chain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        out = tmp_path / "kimi_hunt.json"
        monkeypatch.setattr(K, "OUT", out)
        K._blocked("no credential",
                   attempts=[{"wave": 1, "model": "x/y", "error": "HTTPError 402"}])
        doc = json.loads(out.read_text("utf-8"))
        assert doc["status"] == "BLOCKED"
        assert "no credential" in doc["blocker"]
        assert doc["model_chain"] == list(K.MODEL_CHAIN), (
            "the routes tried must be recorded, or nobody can tell a dead account from a dead "
            "protocol")
        assert doc["attempts"][0]["error"] == "HTTPError 402"

    def test_blocked_is_distinguishable_from_a_hunt_that_found_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The distinction the whole artifact exists for. 'Could not attempt' and 'attempted and
        the forest was thin' are opposite facts, and only the second is evidence about the world.
        An empty findings list alone cannot tell them apart."""
        out = tmp_path / "kimi_hunt.json"
        monkeypatch.setattr(K, "OUT", out)
        K._blocked("unfunded")
        doc = json.loads(out.read_text("utf-8"))
        assert doc["findings"] == [] and doc["status"] == "BLOCKED"
        assert "different fact" in doc["note"]

    def test_the_real_entrypoint_writes_that_artifact_rather_than_exiting_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End to end on the state this box is actually in: no roster, no credit. The old code
        printed a line and exited 2, leaving nothing on disk for 56 firings a week."""
        out = tmp_path / "kimi_hunt.json"
        monkeypatch.setattr(K, "OUT", out)
        monkeypatch.setattr(K, "KEYS", tmp_path / "absent.json")
        monkeypatch.setattr(K, "BUDGET", tmp_path / "absent_budget.json")
        monkeypatch.setattr(sys, "argv", ["kimi_hunter.py"])
        with pytest.raises(SystemExit) as ex:
            K.main()
        assert ex.value.code == 2
        assert out.exists(), "the organ exited without leaving any evidence it had tried"
        assert json.loads(out.read_text("utf-8"))["status"] == "BLOCKED"


class TestPartialWorkIsKept:
    def test_the_wave_loop_persists_coverage_inside_the_loop(self) -> None:
        """Pinned at source: the failure mode is invisible to a unit test with no live model, but
        it is the most expensive one here. Coverage used to be written only after Wave 3 returned,
        so a hunt dying late discarded the territory memory of the waves that HAD succeeded, and
        the next run re-hunted the same forest -- the 45-day vector cooldown silently defeated by
        its own failure path."""
        body = ast.unparse(_wave_loop())
        assert "_COVERAGE.write_text" in body, (
            "coverage must be persisted INSIDE the wave loop, not only after the last wave")

    def test_a_dead_wave_breaks_rather_than_exits(self) -> None:
        """A Wave-3 outage must leave Waves 1 and 2 on disk. `raise SystemExit` inside the loop
        would throw away a completed herd map that costs a full run to rebuild."""
        loop = _wave_loop()
        raises = [n for n in ast.walk(loop) if isinstance(n, ast.Raise)]
        assert not raises, (
            "a failed wave must not abort the run -- a Wave-3 outage has to leave Waves 1 and 2 "
            "on disk, and a completed herd map costs a full run to rebuild")
        assert any(isinstance(n, ast.Break) for n in ast.walk(loop))

    def test_partial_is_a_first_class_status(self) -> None:
        assert '"PARTIAL"' in _code(), (
            "a run that mapped the herd and mined negative space but could not reach Wave 3 did "
            "real work; calling that a failure throws it away")


class TestDegradationIsNeverLeniency:
    def test_the_model_that_produced_a_run_is_recorded(self) -> None:
        """A fallback buys ATTEMPTS, not a lower bar. Attribution is what keeps that true: a
        fallback hunt must be re-runnable on the preferred model later."""
        assert '"models_used": models_used' in _code()

    def test_the_admission_gate_is_untouched_by_the_chain(self) -> None:
        """The forbidden zones and the 7-field charter are the bar. No fallback path may bypass
        them -- selftest covers the gate itself; this pins that it still exists and still runs."""
        assert K._selftest() == 0
        assert len(K.FORBIDDEN_SETS) >= 15


class TestTheDepthReadoutIsRealRatherThanObfuscated:
    def test_the_territory_count_reads_the_key_the_coverage_file_actually_uses(self) -> None:
        """`cov.get(chr(34)+chr(118)+...)` asked for a key spelled WITH quotation marks, missed
        every time, and printed '0 territories hunted to date' unconditionally. The desk's only
        depth-accumulation readout was hardcoded to zero by an obfuscation -- the worst possible
        place for one, since a hunter whose depth always reads nothing gives nobody a reason to
        check whether depth is accruing at all."""
        code = _code()
        assert "chr(34)" not in code, "the obfuscated (and wrong) coverage lookup came back"
        assert 'cov.get("vectors", {})' in code
        assert K._load_coverage().get("vectors") == {} or isinstance(
            K._load_coverage()["vectors"], dict)
