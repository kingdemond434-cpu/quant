"""Principal 2026-11-24 18:31Z ("I removed the e8 gold only rule ages ago") and 18:34Z ("make sure
all promoted strategies get to EA and FTMO, and the rule never intervenes or anything, no blockers
for anything. Only exotics are blocked"). These pin the lift itself and the guardian that keeps it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import kelly_sizing  # noqa: E402
from prop import e8_book  # noqa: E402

LIFTED_GOLD = {"gold_london_am", "gold_afternoon"}


def test_the_gold_only_order_is_lifted_in_code_on_every_venue() -> None:
    assert frozenset() == dc.GOLD_ASIA_ONLY_ZERO
    for venue in ("e8", "fusion", "ftmo"):
        assert dc.SUPERSEDED_CERT_ZEROS[venue] >= LIFTED_GOLD, venue
        assert not LIFTED_GOLD & dc.PRINCIPAL_ZERO.get(venue, frozenset()), venue
    assert dc.SUPERSEDED_CERT_ZEROS["e8"] == e8_book.SUPERSEDED_E8_ZEROS


def test_a_stale_box_cert_book_cannot_re_pin_a_lifted_window(tmp_path, monkeypatch) -> None:
    """The box's CERT_BOOK_LIVE.json still writes gold_london_am / gold_afternoon at 0.0 (box
    state, re-pushed every pass). Those zeros must not bind on any door."""
    p = tmp_path / "CERT_BOOK_LIVE.json"
    p.write_text(json.dumps({"enabled": True,
                             "e8": {"gold_asia": 0.006, "gold_london_am": 0.0,
                                    "gold_afternoon": 0.0, "EURCHF_formula_asia": 0.0},
                             "fusion": {"gold_london_am": 0.0, "gold_afternoon": 0.0}}),
                 encoding="utf-8")
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", p)
    for venue in ("e8", "fusion"):
        for name in LIFTED_GOLD:
            assert not dc.cert_book_zero(name, venue), (venue, name)
            assert not dc.cert_book_zero(f"{name}_v2".upper(), venue), (venue, name)
    # An explicit zero the principal wrote on a sleeve that was never lifted still binds.
    assert dc.cert_book_zero("EURCHF_formula_asia", "e8")
    assert dc.lifted_rule_breaches() == []
    raw = kelly_sizing.load_cert_book(p, "e8")
    assert e8_book.principal_e8_book(raw) == {"gold_asia": 0.006, "EURCHF_formula_asia": 0.0}


def test_the_guardian_names_a_re_pinned_rule(monkeypatch) -> None:
    monkeypatch.setattr(dc, "GOLD_ASIA_ONLY_ZERO", frozenset({"gold_london_am"}))
    monkeypatch.setattr(dc, "PRINCIPAL_ZERO", {**dc.PRINCIPAL_ZERO,
                                               "e8": frozenset({"gold_london_am"})})
    out = dc.lifted_rule_breaches()
    assert "e8: gold_london_am is lifted but still in PRINCIPAL_ZERO" in out
    assert any(line.startswith("GOLD_ASIA_ONLY_ZERO re-pinned") for line in out)
    import desk_self_heal as dsh
    f = dsh.check_lifted_rules(ROOT.parents[1], datetime.now(UTC))
    assert f.ok is False and "gold_london_am" in f.detail and f.fixable is False


def test_the_guardian_reads_clean_on_the_shipped_code() -> None:
    import desk_self_heal as dsh
    f = dsh.check_lifted_rules(ROOT.parents[1], datetime.now(UTC))
    assert f.ok is True, f.detail


@pytest.mark.parametrize("symbol,exotic", [
    ("USDSGD", True), ("EURZAR", True), ("USDNOK", True), ("EURUSD", False), ("AUDCHF", False),
    ("XAUUSD", False), ("NAS100", False), ("USDJPY", False)])
def test_exotics_are_the_one_refusal(symbol: str, exotic: bool) -> None:
    assert e8_book.is_exotic_pair(symbol) is exotic


def test_evidence_sizes_and_never_zeroes() -> None:
    prior = e8_book.fill_shrink(e8_book.CERT_PRIOR_N)
    d = e8_book.DOUBT_MULT
    assert e8_book.evidence_mult({"n": 50.0, "adjR": 0.3}, "x")[0] == e8_book.fill_shrink(50)
    assert e8_book.evidence_mult(None, "x")[0] == prior
    fam = next(iter(e8_book.FORWARD_FAILING_FAMILIES), None)
    if fam:
        assert e8_book.evidence_mult(None, fam)[0] == prior * d
    assert e8_book.evidence_mult(None, "x", ["replication MISMATCH"])[0] == prior * d
    losing = e8_book.evidence_mult(None, "x", (), {"n": 30.0, "adjR": -0.1})
    assert losing[0] == prior * d * d > 0 and "not positive after costs" in losing[1][0]


def test_a_losing_fill_record_is_read_from_the_same_fresh_artifact(tmp_path) -> None:
    p = tmp_path / "FILL_PROVEN.json"
    p.write_text(json.dumps({"schema": e8_book.FILL_PROVEN_SCHEMA,
                             "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                             "sleeves": [{"sleeve": "a", "n_out": 20, "adjR_out": 0.2},
                                         {"sleeve": "b", "n_out": 20, "adjR_out": -0.2},
                                         {"sleeve": "c", "n_out": 3, "adjR_out": -0.9}]}),
                 encoding="utf-8")
    assert set(e8_book.load_fill_proven(p)) == {"a"}
    assert set(e8_book.load_fill_losers(p)) == {"b"}
    assert e8_book.load_fill_losers(tmp_path / "absent.json") == {}


class _Gate:
    def __init__(self, alarm: bool = False, verdict: str = "REPLICATED") -> None:
        self.alarm = {"blocks": alarm, "why": "placebo"}
        self._verdict = verdict

    def replication(self, cert: str, fingerprint: str) -> tuple[str, str]:
        return self._verdict, "fixture"


class _Door:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    def block(self, cert: str) -> str | None:
        return self.reason


def _doors(sym="EURUSD", key="EURUSD_x_asia", cert=None, excl=None, gate=None, door=None,
           notes=()):
    from prop.e8_executor import entry_doors
    return entry_doors(sym, key, cert or {}, excl or {}, gate or _Gate(), door or _Door(),
                       "c1", "fp", notes)


def test_the_e8_executor_book_is_no_longer_a_whitelist() -> None:
    """The Nov-12 box code refused all 13,452 certified sleeves as 'not named with positive risk
    in the E8 principal book'. An unnamed sleeve now passes every door at full size."""
    assert _doors() == ("", "", [], 1.0)


def test_the_e8_executor_refuses_only_exotics_zeros_and_unlifted_exclusions() -> None:
    assert _doors(sym="USDSGD", key="USDSGD_x_asia")[0] == "EXOTIC_BANNED"
    assert _doors(cert={"EURUSD_x_asia": 0.0})[0] == "PRINCIPAL_ZERO"
    assert _doors(excl={"EURUSD_x_asia": "his words"})[:2] == ("PRINCIPAL_EXCLUDED", "his words")
    lifted = "USDJPY_session_range_breakout_asia"
    assert _doors(sym="USDJPY", key=lifted, excl={lifted: "Reddit-only lineage"})[0] == ""


def test_the_e8_executor_sizes_doubts_and_never_refuses_them() -> None:
    d = e8_book.DOUBT_MULT
    status, _, doubts, mult = _doors(gate=_Gate(alarm=True, verdict="MISMATCH"),
                                     door=_Door("not Tier S"))
    assert status == "" and len(doubts) == 3 and mult == d ** 3
    # A doubt the book already priced is not charged twice.
    _, _, _, mult = _doors(gate=_Gate(verdict="MISMATCH"),
                           notes=["replication MISMATCH: fixture: x0.5"])
    assert mult == 1.0
    # The principal's own number funds it: journaled, not sized.
    _, _, doubts, mult = _doors(cert={"EURUSD_x_asia": 0.004}, gate=_Gate(verdict="MISMATCH"))
    assert doubts and mult == 1.0
