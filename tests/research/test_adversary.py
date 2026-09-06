"""THE ADVERSARIES (P48 / P49 / P58).

The canary suite's own correctness is the thing worth fencing, and it is easy to get wrong in a
way that feels safe: a suite that reports 100% rejection because nothing can ever pass is
indistinguishable, from the outside, from a suite guarding working gates. So these tests drive a
DELIBERATELY BROKEN gate through the suite and require it to be caught. A canary suite that has
never been shown to fail is L1.63 one level up -- the detector itself becomes a partition that
cannot fail, and therefore carries no information about the gates it claims to guard.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_adversary", _ROOT / "desks" / "mt5" / "research" / "adversary.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def adv():
    return _load()


# --------------------------------------------------------------------------- P49
def test_a_working_gate_rejects_every_canary(adv) -> None:
    out = adv.run_canaries(lambda name, sig, fwd: False)
    assert out["rejection_rate"] == 1.0
    assert out["intact"] is True
    assert out["survivors"] == []


def test_a_broken_gate_is_caught_and_named(adv) -> None:
    """THE PROPERTY THAT MATTERS. A suite that cannot catch a broken gate guards nothing."""
    out = adv.run_canaries(lambda name, sig, fwd: True)
    assert out["intact"] is False
    assert out["rejection_rate"] == 0.0
    assert set(out["survivors"]) == {c.name for c in adv.CANARIES}
    assert "A CANARY SURVIVED" in out["verdict"]


@pytest.mark.parametrize("leak", [c.name for c in _load().CANARIES])
def test_each_canary_is_individually_load_bearing(adv, leak) -> None:
    """One gate degrading must be caught even while the other four still work.

    A suite that only notices when EVERYTHING breaks would miss the realistic failure entirely:
    gates degrade one at a time, and the first one to go is the one worth catching.
    """
    out = adv.run_canaries(lambda name, sig, fwd: name == leak)
    assert out["intact"] is False, f"{leak} passing was not noticed"
    assert out["survivors"] == [leak]
    assert leak in out["verdict"] and "--" in out["verdict"], (
        "the alarm names the canary but not what its passing PROVES; an operator cannot triage "
        "on a name alone")


def test_a_crashing_gate_is_not_scored_as_a_rejection(adv) -> None:
    """A gate that throws has failed to JUDGE, not managed to reject.

    Scoring a crash as a rejection would let a completely broken gauntlet report a perfect canary
    record -- the most comfortable possible reading of the most serious possible failure.
    """
    def boom(name, sig, fwd):
        raise RuntimeError("gate exploded")
    out = adv.run_canaries(boom)
    assert out["intact"] is False, "a gate that crashes on every canary reported an intact suite"
    assert all(r["gate_error"] for r in out["canaries"])


def test_the_required_rate_is_total(adv) -> None:
    """Four of five canaries rejected is not 'mostly fine'. It is one blind gate."""
    assert adv.REQUIRED_REJECTION_RATE == 1.0
    out = adv.run_canaries(lambda name, sig, fwd: name == "lookahead")
    assert out["rejection_rate"] == 0.8
    assert out["intact"] is False, "80% was treated as acceptable; it means lookahead is admitted"


def test_the_lookahead_canary_actually_contains_the_answer(adv) -> None:
    """If the construction were wrong the canary would be unable to detect the bug it names."""
    sig, fwd = adv._series("lookahead")
    assert adv._corr(sig, fwd) > 0.99, (
        "the lookahead canary's signal is not the forward return, so a harness that permits "
        "lookahead would pass it and this canary would never fire")


def test_the_noise_canary_carries_no_signal(adv) -> None:
    sig, fwd = adv._series("pure_noise")
    assert abs(adv._corr(sig, fwd)) < 0.25, "the 'noise' canary has real signal in it"


def test_the_suite_is_seeded_so_a_pass_means_the_gate_changed(adv) -> None:
    """An unseeded canary cannot distinguish 'the gate broke' from 'this draw looked tradeable',
    which is the entire question it exists to answer."""
    a = adv._series("survivor_biased")
    b = adv._series("survivor_biased")
    assert a == b, "canary data is not deterministic; a failure could be the draw, not the gate"


def test_the_seed_survives_a_restart_not_merely_a_call(adv) -> None:
    """DETERMINISM HAS TO SURVIVE A RESTART OR IT IS NOT DETERMINISM.

    The first draft seeded on `hash(kind)`. Python randomises str hashing per process, so the
    canary data changed on every run -- and the test above still passed, because both calls were
    in the same process. An in-process equality check cannot see this class of bug at all.

    Asserting on the DERIVATION rather than on two samples is what closes it: the seed must come
    from a stable digest, and `hash()` must not appear in the module at all.
    """
    src = (_ROOT / "desks" / "mt5" / "research" / "adversary.py").read_text("utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "hashlib" in body and "sha1" in body, (
        "the canary seed is no longer derived from a stable digest")
    assert "hash(kind)" not in body and "random.seed()" not in body, (
        "the seed uses Python's per-process string hash again -- canary data will differ on every "
        "restart, so a canary that starts passing could be the draw rather than the gate and the "
        "suite can never tell you which")


def test_the_stand_in_gate_declares_itself(adv) -> None:
    """A 100% rejection rate from a gate that rejects unconditionally is false comfort."""
    doc = adv.run()
    assert "stand-in" in doc["gate_source"] and "proves nothing" in doc["gate_source"]
    injected = adv.run(gate=lambda n, s, f: False)
    assert injected["gate_source"] == "injected"


# --------------------------------------------------------------------------- P58
def test_reposts_of_one_source_count_once(adv) -> None:
    claims = [{"primary_source": "doi:10.1/abc", "title": t}
              for t in ("A", "A restated", "A, summarised", "thread on A")]
    out = adv.independent_weight(claims)
    assert out["independent_lineages"] == 1, "four reposts counted as four observations"
    assert out["echo_factor"] == 4.0
    assert out["largest_echo"] == 4


def test_genuinely_independent_claims_are_not_collapsed(adv) -> None:
    claims = [{"primary_source": "doi:10.1/abc"}, {"primary_source": "doi:10.2/xyz"},
              {"mechanism": "carry basis"}]
    assert adv.independent_weight(claims)["independent_lineages"] == 3


def test_lineage_ignores_the_title_because_reposters_change_it(adv) -> None:
    a = {"mechanism": "asia range breakout", "title": "Asia Range Breakout"}
    b = {"mechanism": "breakout range asia", "title": "The Tokyo Session Edge"}
    assert adv.lineage_key(a) == adv.lineage_key(b), (
        "the same mechanism under two titles read as two independent discoveries -- which is "
        "how volume gets mistaken for breadth")


# --------------------------------------------------------------------------- P48
def test_the_defect_hunter_finds_a_planted_shape(adv, tmp_path) -> None:
    (tmp_path / "bad.py").write_text(
        "def f():\n    try:\n        g()\n    except Exception:\n        pass\n", "utf-8")
    hits = adv.hunt_silent_defects(tmp_path)
    assert any(h["shape"] == "bare_except_pass" for h in hits)
    assert all("file" in h and "line" in h and "why" in h for h in hits), (
        "a finding without a file, a line and a reason is not actionable")


def test_the_hunter_reports_and_never_edits(adv, tmp_path) -> None:
    """Every one of these shapes is legitimate somewhere, so this produces a reading list."""
    src = "def f():\n    try:\n        g()\n    except Exception:\n        pass\n"
    p = tmp_path / "bad.py"
    p.write_text(src, "utf-8")
    adv.hunt_silent_defects(tmp_path)
    assert p.read_text("utf-8") == src, "the hunter modified a file; it is a reporter, not a fixer"
