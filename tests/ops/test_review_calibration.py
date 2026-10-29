"""Reviewer calibration canaries (2026-10-29, #485/#479): rule 1 needs a money-path or sizing diff.

qwen2.5-coder:7b FAILed #485 (CERT_BUDGET_SHARE, a compute-budget share in the replication
queue) as risk_increasing; the Auditor CLEARed it. The fix never overrules a model: on a diff
trusted code finds NO money-path or sizing file in, a rule-1-only FAIL is asked once more with
that fact, and the second verdict stands. Every other FAIL is unchanged.

False-positive canaries: the #485 answer on a non-money diff passes once re-asked.
False-negative canaries: the same answer on a money diff, a control flag, a non-risk FAIL, an
unclassifiable tree, and a second FAIL all stay FAIL.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ir_cal", ROOT / "ops/release/independent_review.py")
assert _spec is not None and _spec.loader is not None
ir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ir)


def _ans(verdict: str, risk: bool, control: bool = False, words: str = "ok") -> str:
    return json.dumps(
        {"verdict": verdict, "risk_increasing": risk, "touches_control": control,
         "findings": [words], "summary": words}
    )  # fmt: skip


#: qwen's answer on #485, verbatim in substance
R485 = _ans(
    "FAIL", True, words="The change introduces a new parameter CERT_BUDGET_SHARE which could "
    "increase risk by changing the budget allocation for certificate processing.",
)
OK = _ans("PASS", False)


def _model(*answers: str, seen: list[str] | None = None) -> Any:
    it = iter(answers)

    def ask(rubric: str, user: str) -> str:
        if seen is not None:
            seen.append(user)
        return next(it)

    return ask


def _vote(ladder: list[Any], money: bool) -> tuple[str, list[str]]:
    return ir.vote(
        "DIFF-BODY", ["scripts/replication_civilization.py"], ladder, budget_s=1000,
        sleep=lambda s: None, clock=iter(range(0, 10_000, 10)).__next__, money=money,
    )  # fmt: skip


def test_fp_canary_a_rule_one_fail_on_a_non_money_diff_is_asked_again_with_the_fact() -> None:
    seen: list[str] = []
    v, log = _vote([("qwen", "q", _model(R485, OK, seen=seen)), ("meta", "l", _model(OK))], False)
    assert v == "PASS"
    assert ir.NOT_MONEY_NOTE not in seen[0] and seen[1].startswith(ir.NOT_MONEY_NOTE)
    assert any("asked once more with that fact" in x for x in log)


def test_fn_canary_the_same_answer_on_a_money_diff_fails_at_once() -> None:
    seen: list[str] = []
    v, _ = _vote([("qwen", "q", _model(R485, OK, seen=seen)), ("meta", "l", _model(OK))], True)
    assert v == "FAIL" and len(seen) == 1


def test_fn_canary_a_second_fail_stands() -> None:
    v, _ = _vote([("qwen", "q", _model(R485, R485)), ("meta", "l", _model(OK))], False)
    assert v == "FAIL"


def test_fn_canary_a_control_flag_is_never_re_asked() -> None:
    seen: list[str] = []
    ctl = _ans("FAIL", True, control=True)
    v, _ = _vote([("qwen", "q", _model(ctl, OK, seen=seen)), ("meta", "l", _model(OK))], False)
    assert v == "FAIL" and len(seen) == 1


def test_fn_canary_a_non_risk_fail_is_never_re_asked() -> None:
    seen: list[str] = []
    leak = _ans("FAIL", False, words="look-ahead: uses tomorrow's close")
    v, _ = _vote([("qwen", "q", _model(leak, OK, seen=seen)), ("meta", "l", _model(OK))], False)
    assert v == "FAIL" and len(seen) == 1


def test_fn_canary_the_second_answer_must_still_pass_rules_two_to_six() -> None:
    v, _ = _vote(
        [("qwen", "q", _model(R485, _ans("FAIL", False, words="new network host"))),
         ("meta", "l", _model(OK))], False,
    )  # fmt: skip
    assert v == "FAIL"


def test_decide_drops_only_rule_one_off_the_money_path() -> None:
    risky_pass = json.loads(_ans("PASS", True, words="increases the max lot"))
    assert ir.decide(risky_pass, money=True)[0] is False
    assert ir.decide(risky_pass, money=False)[0] is True
    assert ir.decide(json.loads(R485), money=False)[0] is False  # its own FAIL still stands
    assert ir.decide(json.loads(_ans("PASS", False, control=True)), money=False)[0] is False


def test_an_unclassifiable_base_counts_every_file_as_money(tmp_path: Path) -> None:
    hits, why = ir.money_files(["scripts/x.py"], root=tmp_path)  # no money closure there
    assert hits == ["scripts/x.py"] and "could not be read" in why
