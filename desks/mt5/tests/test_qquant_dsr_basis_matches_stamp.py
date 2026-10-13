"""qquant judges the deflated-Sharpe gate on the basis the attestation it stamps declares.

Audit 2026-10-13 (T8 blocker b): qquant judged at the campaign charge (109 trials, sweep variance)
while stamping an attestation that declares the fixed per-cell bar. `dsr_bar` reads the bar from
`gate_policy` itself, so the stamp and the judgement cannot disagree in either state.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import qquant_gates as qg  # noqa: E402


def test_the_fixed_bar_is_used_when_the_policy_declares_it(monkeypatch) -> None:
    fake = types.ModuleType("gate_policy")
    fake.__dict__["dsr_hurdle_inputs"] = lambda n: (5, 1.0 / (n - 1), f"fixed(N=5,T={n})")
    monkeypatch.setitem(sys.modules, "gate_policy", fake)
    n, var, basis = qg.dsr_bar(319, 109, 0.0647)
    assert (n, var) == (5, 1.0 / 318) and basis == "fixed(N=5,T=319)"


def test_the_legacy_charge_stands_where_the_fixed_bar_is_not_in_force(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "gate_policy", types.ModuleType("gate_policy"))
    assert qg.dsr_bar(319, 109, 0.0647) == (109, 0.0647, "campaign_trials_x_sweep_variance")


def test_the_gate_records_the_basis_it_used() -> None:
    src = Path(qg.__file__).read_text("utf-8")
    assert '"n_trials": dsr_trials, "basis": dsr_basis' in src
    assert "deflated_sharpe_ratio(arr, n_trials=dsr_trials, variance_of_sharpes=dsr_var" in src
