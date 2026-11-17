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


LEGACY = (109, 0.0647, "campaign_trials_x_sweep_variance")
FIXED_BASIS = "fixed_per_cell_bar(N=5) + null_variance(1/(T-1))"


def _policy(monkeypatch, *, helper: bool, basis: str | None) -> None:
    fake = types.ModuleType("gate_policy")
    if helper:
        fake.__dict__["dsr_hurdle_inputs"] = lambda n: (5, 1.0 / (n - 1), f"fixed(N=5,T={n})")
    if basis is not None:
        fake.__dict__["ATTESTATION"] = {"trial_count_basis": basis}
    monkeypatch.setitem(sys.modules, "gate_policy", fake)


def test_the_fixed_bar_is_used_when_the_policy_declares_it(monkeypatch) -> None:
    _policy(monkeypatch, helper=True, basis=FIXED_BASIS)
    n, var, basis = qg.dsr_bar(319, 109, 0.0647)
    assert (n, var) == (5, 1.0 / 318) and basis == "fixed(N=5,T=319)"


def test_the_legacy_charge_stands_where_the_fixed_bar_is_not_in_force(monkeypatch) -> None:
    _policy(monkeypatch, helper=False, basis=None)
    assert qg.dsr_bar(319, 109, 0.0647) == LEGACY


def test_the_helper_alone_does_not_switch_the_bar_it_must_be_attested(monkeypatch) -> None:
    """Audit of #351 (SF-c): a `dsr_hurdle_inputs` that lands ahead of its attestation must not
    judge on a bar no certificate declares."""
    for basis in (None, "", "effective_campaign_trials(109) + fixed_variance_of_sharpes(0.0002)"):
        _policy(monkeypatch, helper=True, basis=basis)
        assert qg.dsr_bar(319, 109, 0.0647) == LEGACY


def test_an_attestation_alone_does_not_switch_the_bar_either(monkeypatch) -> None:
    _policy(monkeypatch, helper=False, basis=FIXED_BASIS)
    assert qg.dsr_bar(319, 109, 0.0647) == LEGACY


def test_the_real_policy_at_this_revision_judges_on_the_basis_it_attests() -> None:
    """Against the REAL `gate_policy`, no fake: the bar applied and the bar stamped agree. Where
    the attestation declares the campaign charge the legacy basis is what `dsr_bar` returns; it
    may return the fixed bar only once the attestation itself opens with the fixed-bar prefix."""
    import gate_policy as gp
    attested_fixed = str(gp.ATTESTATION["trial_count_basis"]).startswith(
        qg.FIXED_BAR_BASIS_PREFIX)
    out = qg.dsr_bar(319, 109, 0.0647)
    if attested_fixed and hasattr(gp, "dsr_hurdle_inputs"):
        assert out == tuple(gp.dsr_hurdle_inputs(319))
    else:
        assert out == LEGACY and out[2] == qg.LEGACY_DSR_BASIS


def test_the_gate_records_the_basis_it_used() -> None:
    src = Path(qg.__file__).read_text("utf-8")
    assert '"n_trials": dsr_trials, "basis": dsr_basis' in src
    assert "deflated_sharpe_ratio(arr, n_trials=dsr_trials, variance_of_sharpes=dsr_var" in src
