"""Tiered pre-filter (HYPOTHESIS_MAX #1) -- the cheap stage must reject only the unambiguous,
escalate every borderline, charge every look to the ledger, and never certify anything."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from libs.research.pre_filter import audit_due, ledger_counts, pre_filter

_RNG = np.random.default_rng(7)


def _stream(n: int = 400, mu: float = 0.0, sd: float = 0.01,
            active_frac: float = 0.6) -> np.ndarray:
    r = _RNG.normal(mu, sd, n)
    mask = _RNG.random(n) < active_frac
    return np.where(mask, r, 0.0)


def test_good_candidate_escalates(tmp_path: Path) -> None:
    led = tmp_path / "led.jsonl"
    out = pre_filter(_stream(mu=0.002), name="good", rt_cost_per_trade=1e-4, ledger=led)
    assert out["verdict"] == "ESCALATE"
    assert led.exists() and len(led.read_text("utf-8").splitlines()) == 1


def test_wrong_sign_rejected(tmp_path: Path) -> None:
    out = pre_filter(_stream(mu=-0.003), name="bad", ledger=tmp_path / "l.jsonl")
    assert out["verdict"] == "REJECT"
    assert out["reason"] == "wrong-sign-insample"


def test_borderline_escalates_never_rejects(tmp_path: Path) -> None:
    # Tiny positive edge, not cheap-unambiguous in either direction -> full gauntlet decides.
    # Deterministic stream (alternating +11/-10 bps): t ~ +0.95 -- above zero, below anything
    # the gauntlet would bless. A random draw here can land t<0 and reject legitimately.
    r = np.tile([0.0011, -0.0010], 200)
    out = pre_filter(r, name="borderline", ledger=tmp_path / "l.jsonl")
    assert out["verdict"] == "ESCALATE"


def test_cost_floor_rejects_thin_edge(tmp_path: Path) -> None:
    # Deterministic: clearly positive t (mean +10 bps, tiny wobble so sd>0), many round-trips,
    # but gross-per-trade orders of magnitude under 2x a fat round-trip cost.
    block = [0.0012, 0.0008, 0.0012, 0.0008, 0.0012, 0.0, 0.0]
    out = pre_filter(np.tile(block, 60), name="thin", rt_cost_per_trade=0.02,
                     ledger=tmp_path / "l.jsonl")
    assert out["verdict"] == "REJECT"
    assert out["reason"] == "cost-exceeds-edge"


def test_degenerate_turnover_rejected(tmp_path: Path) -> None:
    r = np.zeros(400)
    r[5] = 0.04  # one trade in 400 periods
    out = pre_filter(r, name="lump", ledger=tmp_path / "l.jsonl")
    assert out["verdict"] == "REJECT"
    assert out["reason"] == "degenerate-turnover"


def test_single_window_concentration_rejected(tmp_path: Path) -> None:
    # All P&L in the first quarter of the active sample, noise-free elsewhere.
    r = np.concatenate([np.full(60, 0.01), _RNG.normal(0.0, 1e-05, 240)])
    out = pre_filter(r, name="one-event", ledger=tmp_path / "l.jsonl")
    assert out["verdict"] == "REJECT"
    assert out["reason"] == "single-window-concentration"


def test_no_pass_verdict_exists(tmp_path: Path) -> None:
    # The filter must never certify: only REJECT or ESCALATE can come out.
    for mu in (-0.003, 0.0, 0.0005, 0.005):
        out = pre_filter(_stream(mu=mu), name="v", ledger=tmp_path / "l.jsonl")
        assert out["verdict"] in {"REJECT", "ESCALATE"}


def test_every_look_charged_to_ledger(tmp_path: Path) -> None:
    led = tmp_path / "led.jsonl"
    for i in range(5):
        pre_filter(_stream(mu=0.002 if i % 2 else -0.002), name=f"c{i}", ledger=led)
    rows = [json.loads(x) for x in led.read_text("utf-8").splitlines()]
    assert len(rows) == 5  # rejects AND escalates both charge a row -- no free peeks
    c = ledger_counts(led)
    assert c["REJECT"] + c["ESCALATE"] == 5


def test_audit_cadence_tightens_on_volume(tmp_path: Path) -> None:
    led, st = tmp_path / "led.jsonl", tmp_path / "audit.json"
    assert audit_due(led, state=st)  # never audited -> due
    st.write_text(json.dumps({"last_audit": "2026-07-25T00:00:00+00:00"}), "utf-8")
    # <50 rejects -> weekly cadence: 4 days since last audit is NOT due.
    for i in range(3):
        pre_filter(_stream(mu=-0.003), name=f"r{i}", ledger=led)
    from datetime import UTC, datetime

    import libs.research.pre_filter as pf
    now = datetime(2026, 7, 29, tzinfo=UTC)

    real = pf.datetime

    class _Fixed:
        @staticmethod
        def now(tz: object = None) -> object:
            return now

        fromisoformat = staticmethod(real.fromisoformat)

    pf.datetime = _Fixed  # type: ignore[assignment, misc]
    try:
        assert not audit_due(led, state=st)
        # >=50 rejects -> 3-day cadence: the same 4-day gap IS due.
        for i in range(55):
            pre_filter(np.full(100, -0.001), name=f"m{i}", ledger=led)
        assert audit_due(led, state=st)
    finally:
        pf.datetime = real  # type: ignore[misc]
