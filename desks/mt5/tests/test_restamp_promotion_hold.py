"""A re-stamped certificate's clock keeps running but cannot earn a PROMOTE verdict.

MEASURED 2026-11-13: `lockbox_recert` exited 3 three times on seven RESTAMPED certificates
(USDJPY and XAUUSD session_range_breakout, gated 2026-08-26, wearing the v4 header). The writer was
`forward_reconcile`, which stamped the current attestation over the whole store whenever it added
a row. These tests pin the hold, its scope (PROMOTE only, never KILL, never a demotion) and the
writer fix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_forward as sf  # noqa: E402


def _ledgers(tmp: Path, lockbox: dict | None, remint: dict | None) -> tuple[Path, Path]:
    lb, rm = tmp / "lb.json", tmp / "rm.json"
    if lockbox is not None:
        lb.write_text(json.dumps(lockbox), "utf-8")
    if remint is not None:
        rm.write_text(json.dumps(remint), "utf-8")
    return lb, rm


def test_restamped_certificates_read_both_ledgers(tmp_path: Path) -> None:
    lb, rm = _ledgers(tmp_path, {"certificates": {
        "a": {"after": {"state": "RESTAMPED", "key": "external.A"}},
        "b": {"after": {"state": "REMINTED", "key": "external.B"}}}},
        {"restamped_not_rejudged": ["external.C"]})
    assert sf.restamped_certificates(lb, rm) == {"external.A", "external.C"}


def test_absent_ledgers_hold_nothing(tmp_path: Path) -> None:
    lb, rm = _ledgers(tmp_path, None, None)
    assert sf.restamped_certificates(lb, rm) == set()
    (tmp_path / "lb.json").write_text("{not json", "utf-8")
    assert sf.restamped_certificates(lb, rm) == set()


@pytest.fixture()
def held(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(sf, "RESTAMP_HELD", {"USDJPY.asia#rr=2.0": "external.USDJPY.x"})
    monkeypatch.setattr(sf, "slog", lambda *_a, **_k: None)
    return sf.RESTAMP_HELD


def test_hold_marks_the_row(held: dict[str, str]) -> None:
    st = {"status": "ACTIVE"}
    assert sf.restamp_hold("USDJPY.asia#rr=2.0", st) is True
    assert st["promotion_hold"] == sf.RESTAMP_HOLD
    assert st["promotion_hold_certificate"] == "external.USDJPY.x"
    assert st["status"] == "ACTIVE"


def test_an_existing_candidate_is_marked_never_demoted(held: dict[str, str]) -> None:
    st = {"status": "PROMOTION CANDIDATE"}
    assert sf.restamp_hold("USDJPY.asia#rr=2.0", st) is True
    assert st["status"] == "PROMOTION CANDIDATE"
    assert st["promotion_hold"] == sf.RESTAMP_HOLD


def test_a_released_certificate_drops_the_stale_mark(held: dict[str, str]) -> None:
    st = {"status": "ACTIVE", "promotion_hold": sf.RESTAMP_HOLD,
          "promotion_hold_certificate": "external.USDJPY.x"}
    assert sf.restamp_hold("XAUUSD.asia#rr=1.5", st) is False
    assert "promotion_hold" not in st and "promotion_hold_certificate" not in st


def test_a_foreign_hold_is_left_alone(held: dict[str, str]) -> None:
    st = {"status": "ACTIVE", "promotion_hold": "SOMETHING_ELSE"}
    assert sf.restamp_hold("XAUUSD.asia#rr=1.5", st) is False
    assert st["promotion_hold"] == "SOMETHING_ELSE"


def test_the_verdict_clause_holds_promote_only() -> None:
    """The PROMOTE branch is guarded by the hold; the KILL branch is not."""
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    i = src.index("held = restamp_hold(key, st)")
    block = src[i:i + 1400]
    assert "if held and st[\"exp_r\"] > PROMOTE_MIN_EXP" in block
    assert block.index("if held and") < block.index('st["status"] = "PROMOTION CANDIDATE"')
    assert 'st["status"] = "KILL"' in block


def test_reconcile_never_flips_a_stale_header() -> None:
    src = (DESK / "research" / "forward_reconcile.py").read_text("utf-8")
    assert '"gate_policy": ATTESTATION, "survivors": survivors' not in src
    assert '"gate_policy": header, "survivors": survivors' in src


def test_a_held_promote_writes_one_missed_growth_line_a_day(tmp_path: Path,
                                                             held: dict[str, str]) -> None:
    from datetime import UTC, datetime
    ledger = tmp_path / "missed_growth.jsonl"
    st = {"status": "ACTIVE", "n": 40, "exp_r": 0.21, "max_dd_r": -3.0}
    sf.restamp_hold("USDJPY.asia#rr=2.0", st)
    t = datetime(2026, 11, 14, 1, tzinfo=UTC)
    assert sf.record_restamp_missed_growth("USDJPY.asia#rr=2.0", st, t, ledger) is True
    assert sf.record_restamp_missed_growth("USDJPY.asia#rr=2.0", st, t, ledger) is False
    rows = [json.loads(x) for x in ledger.read_text("utf-8").splitlines()]
    assert len(rows) == 1
    r = rows[0]
    assert r["rail"] == sf.RESTAMP_RAIL and r["value"] == 0.21 and r["n"] == 40
    assert r["certificate"] == "external.USDJPY.x" and r["held_since"]
    nxt = datetime(2026, 11, 15, 1, tzinfo=UTC)
    assert sf.record_restamp_missed_growth("USDJPY.asia#rr=2.0", st, nxt, ledger) is True


def test_a_negative_expectancy_forgoes_nothing(tmp_path: Path, held: dict[str, str]) -> None:
    ledger = tmp_path / "mg.jsonl"
    st = {"exp_r": -0.4}
    sf.record_restamp_missed_growth("K", st, ledger=ledger)
    assert json.loads(ledger.read_text("utf-8"))["value"] == 0.0


def test_the_held_promote_branch_writes_the_line() -> None:
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    i = src.index("VERDICT PROMOTE HELD")
    assert "record_restamp_missed_growth(key, st)" in src[i:i + 300]


def test_hold_since_is_kept_across_passes(held: dict[str, str]) -> None:
    st = {"status": "ACTIVE"}
    sf.restamp_hold("USDJPY.asia#rr=2.0", st)
    first = st["promotion_hold_since"]
    st["promotion_hold_since"] = "2026-11-01T00:00:00+00:00"
    sf.restamp_hold("USDJPY.asia#rr=2.0", st)
    assert st["promotion_hold_since"] == "2026-11-01T00:00:00+00:00" != first


def test_remint_status_counts_the_holds(tmp_path: Path) -> None:
    from research import attestation_remint as ar
    p = tmp_path / "shadow_state.json"
    p.write_text(json.dumps({
        "A": {"promotion_hold": ar.RESTAMP_HOLD, "promotion_hold_since": "2026-11-13T01:00:00Z",
              "promotion_hold_certificate": "external.A", "n": 30},
        "B": {"promotion_hold": ar.RESTAMP_HOLD, "promotion_hold_since": "2026-11-12T01:00:00Z"},
        "C": {"status": "ACTIVE"}}), "utf-8")
    out = ar.restamp_holds(p)
    assert out["n"] == 2 and out["oldest_held_since"].startswith("2026-11-12T01:00:00")
    assert [c["key"] for c in out["clocks"]] == ["A", "B"]
    assert ar.restamp_holds(tmp_path / "absent.json")["status"] == "UNMEASURED"
    assert sf.RESTAMP_HOLD == ar.RESTAMP_HOLD
