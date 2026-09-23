"""The kill-direction e-process rides on the verdict row and can only ever kill earlier.

What is asserted is the DIRECTION and the INDEPENDENCE, not the arithmetic (which
tests/research/test_anytime_valid.py owns): a losing ledger crosses, a winning one never does,
the fixed 14-day schedule and `promote` read none of it, and a ledger shorter than the e-process's
own floor says UNMEASURED with its count rather than a number.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import forward_verdict as fv  # noqa: E402


def _ledger(n: int, mean: float, sd: float, seed: int) -> list[float]:
    return [float(x) for x in np.random.default_rng(seed).normal(mean, sd, n)]


def test_a_losing_ledger_crosses_and_names_the_first_trade_it_became_a_valid_stop() -> None:
    rs = _ledger(200, -0.3, 1.0, 1)
    out = fv.e_process(rs)
    assert out["e_status"] == "MEASURED"
    assert out["e_value"] >= out["e_threshold"] == 100.0
    assert out["e_kill_supported"] is True
    t = out["e_crossed_at"]
    assert t is not None and 20 <= t <= 200
    from libs.research import anytime_valid as av
    neg = [-x for x in rs]
    assert av.e_value(neg[:t]) >= 100.0
    assert av.e_value(neg[:t - 1]) < 100.0, "it must be the FIRST crossing"


def test_a_winning_ledger_never_crosses_so_the_row_can_never_argue_for_a_pass() -> None:
    out = fv.e_process(_ledger(400, +0.4, 1.0, 2))
    assert out["e_status"] == "MEASURED"
    assert out["e_kill_supported"] is False and out["e_crossed_at"] is None
    assert out["e_value"] < 1.0, "a winning sleeve is evidence FOR the null 'not losing'"


def test_pure_noise_does_not_manufacture_a_kill() -> None:
    kills = sum(fv.e_process(_ledger(300, 0.0, 1.0, 100 + s))["e_kill_supported"]
                for s in range(10))
    assert kills <= 1


def test_too_short_a_ledger_is_UNMEASURED_with_its_count() -> None:
    out = fv.e_process(_ledger(12, -2.0, 0.1, 3))
    assert out["e_value"] == "UNMEASURED"
    assert out["e_n"] == 12
    assert out["e_status"].startswith("UNMEASURED: 12/")
    assert out["e_crossed_at"] is None and out["e_kill_supported"] is False


def test_the_null_is_written_on_the_row_so_the_direction_cannot_be_misread() -> None:
    out = fv.e_process(_ledger(30, 0.0, 1.0, 4))
    assert "kill-only" in out["e_null"] and out["e_alpha"] == 0.01


def test_stamps_name_the_crossing_trade() -> None:
    rs = _ledger(120, -0.5, 1.0, 5)
    stamps = [f"2026-09-{i:02d}T00:00" for i in range(1, 121)]
    out = fv.e_process(rs, stamps=stamps)
    assert out["e_crossed_at"] is not None
    assert out["e_crossed_stamp"] == stamps[out["e_crossed_at"] - 1]


def test_verdict_row_carries_the_e_process_beside_an_unchanged_schedule() -> None:
    rs = _ledger(60, -0.8, 1.0, 6)
    row = fv.verdict(rs, days_active=20)
    assert "e_value" in row and "e_crossed_at" in row
    # The fixed bar decided this on its own terms: matured, and killed by exp_r <= 0.
    assert row["matured"] is True and row["promote"] is False
    assert row["e_kill_supported"] is True, "the e-process supports the SAME negative verdict"
    assert row["e_crossed_at"] < row["n"], "and it had the answer before the ledger was full"
    assert fv.VERDICT_MIN_DAYS == 14


def test_promote_and_status_read_nothing_from_the_e_process(monkeypatch) -> None:
    """INDEPENDENCE, proven by substitution: feed the row an overwhelming e-value in both
    directions and every decision field is byte-identical."""
    rs = _ledger(60, +0.5, 1.0, 7)
    honest = fv.verdict(rs, days_active=30)
    decision = ("promote", "status", "matured", "significant", "independent", "reason",
                "n", "n_eff", "seq_lower_bound", "exp_r")
    for fake in ({"e_value": 1e300, "e_kill_supported": True, "e_crossed_at": 21},
                 {"e_value": 0.0, "e_kill_supported": False, "e_crossed_at": None}):
        monkeypatch.setattr(fv, "e_process", lambda _rs, _f=fake: dict(_f))
        forged = fv.verdict(rs, days_active=30)
        assert {k: forged[k] for k in decision} == {k: honest[k] for k in decision}


def test_an_unimportable_library_is_UNAVAILABLE_not_a_number(monkeypatch) -> None:
    def _boom() -> None:
        raise ImportError("no libs on this box")

    monkeypatch.setattr(fv, "_repo_root_on_path", _boom)
    out = fv.e_process(_ledger(50, -1.0, 1.0, 8))
    assert out["e_value"] == "UNMEASURED"
    assert out["e_status"].startswith("UNAVAILABLE: ImportError")
    assert out["e_kill_supported"] is False


def test_the_engines_stamp_the_e_process_beside_their_own_unchanged_rule() -> None:
    """shadow_forward keeps its inline schedule; the e-process is stamped on the row between the
    t-stat and the `enough` clause and never read by it. scalp_shadow carries it in its verdict
    diagnostics. Source-level, like the other engine wiring tests in this directory."""
    src = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    i_t = src.index('st["forward_t"] = round(t_stat, 3)')
    i_e = src.index("_fv.e_process(")
    i_enough = src.index("enough = (st[\"n\"] >= VERDICT_MIN_TRADES")
    assert i_t < i_e < i_enough
    assert "e_kill_supported" not in src[i_enough:], "the promotion clause must not read it"
    scalp = (DESK / "research" / "scalp_shadow.py").read_text(encoding="utf-8")
    assert '"e_value", "e_crossed_at"' in scalp
