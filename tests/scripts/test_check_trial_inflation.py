"""The bar never rises with a trial count (principal, 2026-10-13), and the fence that keeps it so."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import check_trial_inflation as fence  # noqa: E402

from libs.research import trial_count_guard as tcg  # noqa: E402

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    return tmp_path


def _check(doc: dict, metric: str) -> dict:
    return next(c for c in doc["checks"] if c["metric"] == metric)


def test_bar_n_is_fixed_whatever_it_is_handed() -> None:
    assert tcg.BAR_N == 5
    assert {tcg.bar_n(n) for n in (1, 5, 109, 597, 234_977, None)} == {5}


def test_the_same_spec_is_one_trial_however_it_is_rerun() -> None:
    a = {"family": "Carry", "sym": "eurusd", "tf": "h1", "params": {"lb": 20, "z": 1.5}}
    b = {"family": "carry", "symbol": "EURUSD", "timeframe": "H1",
         "params": {"z": 1.5, "lb": 20.0, "sweep": 7, "run_id": "x"}, "at": "2026-10-13"}
    assert tcg.canonical_trial_id(a) == tcg.canonical_trial_id(b)
    assert tcg.canonical_trial_id(a) != tcg.canonical_trial_id({**a, "params": {"lb": 21}})


def test_a_new_file_with_its_own_trial_count_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"desks/mt5/research/new_miner.py": (
        "from libs.validation.dsr import deflated_sharpe_ratio\n"
        "def judge(arr, n):\n"
        "    return deflated_sharpe_ratio(arr, n_trials=len(arr) * 40)\n")})
    doc = fence.judge(root, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert _check(doc, "unpinned_bar_calls")["sites"][0]["file"] == "desks/mt5/research/new_miner.py"


def test_pinned_calls_pass_including_locals_and_conditionals(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"libs/x.py": (
        "from libs.research.trial_count_guard import bar_n, BAR_N\n"
        "def a(arr, n, pc):\n"
        "    k = 1 if pc else bar_n(n)\n"
        "    deflated_sharpe_ratio(arr, n_trials=k)\n"
        "    deflate_t(2.0, bar_n(n))\n"
        "    expected_max_z(BAR_N)\n"
        "    return expected_max_sharpe(1, 0.1)\n"
        "def expected_max_z(n):\n"
        "    return n and expected_max_t(n)\n")})
    assert fence.judge(root, now=NOW)["verdict"] == "PASS"


def test_a_function_that_pins_inside_frees_its_callers_only_if_every_definition_does(
        tmp_path: Path) -> None:
    pinned = ("def trials_penalty(effective_trials):\n"
              "    return bar_n(effective_trials)\n")
    caller = "def f(n):\n    return trials_penalty(n * 9)\n"
    root = _tree(tmp_path, {"a.py": pinned, "b.py": caller})
    assert fence.judge(root, now=NOW)["verdict"] == "PASS"
    _tree(tmp_path, {"c.py": "def trials_penalty(effective_trials):\n    return effective_trials\n"})
    assert fence.judge(root, now=NOW)["verdict"] == "FAIL"


def test_sealed_sites_are_owed_until_the_deadline_then_fail(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"desks/mt5/scripts/external_gauntlet.py": (
        "def charged_lifetime_trials(campaign, family, lifetime, raw):\n"
        "    return max(campaign, lifetime['lifetime_trials'])\n")})
    owed = _check(fence.judge(root, now=NOW), "sealed_trial_charge")
    assert owed["state"] == "WARN" and owed["owner"] == fence.T8_PATCH
    late = _check(fence.judge(root, now=fence.SEALED_DEADLINE), "sealed_trial_charge")
    assert late["state"] == "FAIL"


def test_an_unowned_lifetime_union_fails_at_once(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"libs/elsewhere.py": (
        "def charged_lifetime_trials(c, f, l, r):\n    return l\n")})
    assert _check(fence.judge(root, now=NOW), "sealed_trial_charge")["state"] == "FAIL"


def test_the_rerun_share_is_published_and_ratchets_only_after_the_dedupe(tmp_path: Path) -> None:
    import json
    d = tmp_path / "desks/mt5/data/intelligence/seat"
    d.mkdir(parents=True)
    for i in range(3):                       # the same pass written three times
        (d / f"discoveries_{i}.json").write_text(json.dumps(
            {"tests_run": 100, "discoveries": [{"family": "carry", "sym": "EURUSD"}]}), "utf-8")
    rr = _check(fence.judge(tmp_path, now=NOW, prior={"rerun_share": 0.1}), "ledger_rerun_share")
    assert rr["state"] == "OK" and rr["n_charged"] == 300 and rr["n_distinct"] == 100
    (tmp_path / "desks/mt5/data/TRIAL_DEDUPE_LANDED").write_text("", "utf-8")
    rr = _check(fence.judge(tmp_path, now=NOW, prior={"rerun_share": 0.1}), "ledger_rerun_share")
    assert rr["state"] == "FAIL"


def test_the_live_tree_passes_its_own_fence() -> None:
    doc = fence.judge(ROOT, now=NOW)
    assert _check(doc, "unpinned_bar_calls")["state"] == "OK", \
        _check(doc, "unpinned_bar_calls")["sites"][:5]
