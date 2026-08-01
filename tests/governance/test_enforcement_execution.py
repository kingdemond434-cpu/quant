"""ENFORCEMENT EXECUTION fence (L1.43/L2.0) -- the matrix proved citations EXIST; nothing proved
they RUN.

The wiring tests below are the point: they fail if `libs/research/dist_shift.py` loses its
production caller again. That module was built, unit-tested green, cited as the enforcement of two
laws, and called by nothing for three days -- with its own unit tests passing the whole time. A
unit test proves a mechanism works and says NOTHING about whether anything runs it, which is
exactly how the defect stayed invisible.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_enforcement_execution import (  # noqa: E402
    _Corpus,
    _public_symbols,
    _resolve,
    _strip_citation,
    evaluate,
)


# --------------------------------------------------------------------------- citation parsing
@pytest.mark.parametrize(("raw", "want"), [
    ("run_deadman_switch.py (Tier-3)", "run_deadman_switch.py"),
    ("scripts/max_audit.py (all 57 fences)", "scripts/max_audit.py"),
    ("libs/autodiscovery/validation.py:capacity_status", "libs/autodiscovery/validation.py"),
    ("libs/research/dist_shift.py", "libs/research/dist_shift.py"),
])
def test_citation_prose_is_stripped(raw: str, want: str) -> None:
    assert _strip_citation(raw) == want


def test_resolve_kinds() -> None:
    assert _resolve("docs/graveyard.md")[0] == "standing"
    assert _resolve("tests/validation/test_capacity_parity.py")[0] == "test"
    assert _resolve("libs/research/dist_shift.py")[0] == "module"
    assert _resolve("check_gate_optimality")[0] == "fence"
    # a bare script name resolves into scripts/, not the repo root
    kind, path = _resolve("revalidate_clocks.py")
    assert kind == "script" and path is not None and path.name == "revalidate_clocks.py"


# ------------------------------------------------------------------- the fence's own blind spots
def test_corpus_excludes_the_fence_itself() -> None:
    """Found on the fence's second run: its _MANUAL registry contains the literal string
    'scripts/deep_review.py', so scanning scripts/ found the fence's own exemption entry and
    reported that tool as invoked. A checker that counts itself as evidence launders any mention
    -- a docstring, a registry key -- into proof of execution."""
    corpus = _Corpus()
    assert not any(p.name == "check_enforcement_execution.py" for p in corpus.files)


def test_unenforced_never_over_claims() -> None:
    """A law is 'enforced by nothing' only when EVERY citation is broken. The first draft flagged
    L1.7 on one broken citation while two others executed -- an over-claiming gate is one nobody
    believes the second time."""
    res = evaluate()
    per_law: dict[str, list[str]] = {}
    for row in res["citations"]:
        for law in row["laws"]:
            per_law.setdefault(law, []).append(row["verdict"])
    for law in res["laws_unenforced"]:
        assert all(v in ("DECORATIVE", "MISSING") for v in per_law[law]), (
            f"{law} reported unenforced while one of its citations executes")
    # L1.7 has executing citations, so it must never appear as unenforced
    assert "L1.7" not in res["laws_unenforced"]


def test_unmeasured_is_not_ok() -> None:
    """L1.28a: an unmeasured thing must never report fine -- the exact bug that let dist_shift
    sit orphaned behind a green matrix."""
    assert evaluate()["status"] in {"OK", "DECORATIVE", "MISSING", "UNMEASURED"}
    # the fence must have a real UNMEASURED path, not just a docstring promising one
    src = (_ROOT / "scripts/check_enforcement_execution.py").read_text("utf-8")
    assert "UNMEASURED" in src


def test_public_symbols_ignores_privates() -> None:
    syms = _public_symbols(_ROOT / "libs/research/dist_shift.py")
    assert {"distribution_shift", "split_and_check"} <= syms
    assert not any(s.startswith("_") for s in syms)


# ------------------------------------------------------------------------------- the wiring itself
def _references(module_path: Path, symbols: set[str]) -> bool:
    corpus = _Corpus()
    init = module_path.parent / "__init__.py"
    return corpus.references(symbols, exclude=module_path,
                             package_init=init if init.exists() else None) is not None


def test_dist_shift_has_a_production_caller() -> None:
    """THE REGRESSION TEST FOR THE DEFECT ITSELF. Delete the call in revalidate_clocks.py and this
    fails -- which is the only thing that stops the orphan growing back."""
    mod = _ROOT / "libs/research/dist_shift.py"
    assert _references(mod, {"distribution_shift", "split_and_check"}), (
        "dist_shift.py has no production caller again; it is cited as the enforcement of "
        "L1.19 and L2.10, so both laws are enforced by nothing")


def test_revalidate_clocks_wires_shift_to_the_controller() -> None:
    """The producer must actually reach the CONSUMER. Importing dist_shift and discarding its
    verdict would satisfy the test above while enforcing nothing."""
    src = (_ROOT / "scripts/revalidate_clocks.py").read_text("utf-8")
    tree = ast.parse(src)
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "libs.research.dist_shift" in imported
    assert "libs.validation.revalidation" in imported
    # the verdict must feed the controller's hard trigger, not just be printed
    assert "structural_break=" in src
    assert "RevalidationController()" in src


def test_shift_verdict_maps_to_hard_triggers() -> None:
    """SHIFT -> structural_break, and the direction is downward only: a passing axis can be
    downgraded, never promoted. (DRIFT is deliberately NOT wired -- see the test below.)"""
    from libs.validation.revalidation import (
        RevalidationController,
        WalkForwardReport,
        WalkForwardStatus,
    )
    passing = WalkForwardReport(status=WalkForwardStatus.PASSED, walk_forward_score=80.0,
                                n_windows=5, oos_sharpe=1.5, oos_mean_return=0.01,
                                stability=0.8, message="t")
    clean = RevalidationController().assess(passing)
    assert clean.production_capital_allowed
    broken = RevalidationController().assess(passing, structural_break=True)
    assert not broken.production_capital_allowed
    assert broken.status is WalkForwardStatus.STALE


def test_zscore_transform_kills_the_trend_false_positive() -> None:
    """The first wiring fed RAW LEVELS and got SHIFT on both axes with an identical haircut --
    the welded-gate signature. A deterministic constant-increment ramp has no distributional
    change at all, yet reports SHIFT on levels; the z-scored form is what the strategy consumes
    and what the test must see."""
    import numpy as np
    from scripts.revalidate_clocks import _z

    from libs.research.dist_shift import split_and_check

    rng = np.random.default_rng(7)
    # A drifting random walk -- what supply/price LEVELS actually look like, with no regime change.
    lvl = 1e6 + np.cumsum(rng.normal(100, 40, 900))
    assert split_and_check(lvl, name="lvl")["verdict"] == "SHIFT"        # the false positive
    # Cured where it matters: the HARD trigger no longer fires on a pure trend artifact.
    assert split_and_check(_z(lvl), name="lvl")["verdict"] != "SHIFT"

    # ...and a genuine mean/variance regime change is still caught.
    genuine = np.concatenate([rng.normal(0, 1, 700), rng.normal(3, 4, 200)])
    assert split_and_check(genuine, name="g")["verdict"] == "SHIFT"


def test_only_shift_strips_capital_not_drift() -> None:
    """DRIFT is a member of _HARD_TRIGGERS, and it fires on a single marginal indicator -- at
    n~900 the KS test is overpowered and a benign drifting random walk returns DRIFT. Passing that
    through would strip capital from healthy axes on noise. The caller maps only SHIFT."""
    src = (_ROOT / "scripts/revalidate_clocks.py").read_text("utf-8")
    assert "drift=" not in src, "a bare DRIFT verdict must not reach a capital-blocking trigger"

    from libs.validation.revalidation import (
        RevalidationController,
        WalkForwardReport,
        WalkForwardStatus,
    )
    passing = WalkForwardReport(status=WalkForwardStatus.PASSED, walk_forward_score=80.0,
                                n_windows=5, oos_sharpe=1.5, oos_mean_return=0.01,
                                stability=0.8, message="t")
    assert RevalidationController().assess(passing).production_capital_allowed


def test_z_refuses_short_series() -> None:
    import numpy as np
    from scripts.revalidate_clocks import _z
    assert len(_z(np.arange(5.0))) == 0


# ------------------------------------------------------------------------------------ end to end
def test_fence_runs_and_writes_its_artifact(tmp_path: Path) -> None:
    r = subprocess.run([sys.executable, "scripts/check_enforcement_execution.py", "--json"],
                       cwd=_ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode in (0, 2), r.stderr[-2000:]
    payload = json.loads(r.stdout)
    assert payload["status"] in {"OK", "DECORATIVE", "MISSING", "UNMEASURED"}
    assert payload["citations"], "zero citations must report UNMEASURED, never a silent pass"
    assert (_ROOT / "data/enforcement_execution.json").exists()


def test_report_only_always_exits_zero() -> None:
    r = subprocess.run([sys.executable, "scripts/check_enforcement_execution.py", "--report-only"],
                       cwd=_ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0
