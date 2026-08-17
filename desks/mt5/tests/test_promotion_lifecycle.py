"""The promote/retire lifecycle, exercised end to end rather than grepped.

test_state_chain.py pins the SHAPE of the chain by reading source. This file runs it: real
shadow state in, real sleeves.json out, so a rule that reads correctly but behaves wrongly is
still caught.

The bug that motivated it is the retire half of the same defect the promote half already had.
Promotion was fixed to parse three-part keys; retirement still REBUILT the key from two fields
and threw the third away.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter  # noqa: E402
from mt5desk import provenance  # noqa: E402

#: The account these fixtures pretend to be trading. Ledger rows are stamped with it, because the
#: promoter now counts only trades from the account in hand -- an unstamped row is evidence about
#: nothing, which is the entire point of `test_account_provenance.py`.
_ACC = {"login": 5551234, "server": "FusionMarkets-Live", "kind": provenance.LIVE}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A promoter pointed entirely at tmp_path, trading a known account."""
    shadow_dir = tmp_path / "reports" / "shadow"
    shadow_dir.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(promoter, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(promoter, "LEDGER", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(promoter, "LOG", tmp_path / "logs" / "promoter.log")
    monkeypatch.setattr(promoter.provenance, "current_account", lambda _acc: _ACC)

    class Desk:
        root = tmp_path

        def shadow(self, blob: dict) -> None:
            (shadow_dir / "shadow_state.json").write_text(json.dumps(blob), encoding="utf-8")

        def read_shadow(self) -> dict:
            return json.loads((shadow_dir / "shadow_state.json").read_text(encoding="utf-8"))

        def ledger(self, rows: list[dict]) -> None:
            (tmp_path / "data" / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps({**provenance.stamp(_ACC), **r}) for r in rows),
                encoding="utf-8")

        def ledger_raw(self, rows: list[dict]) -> None:
            """Unstamped rows, as written before provenance existed."""
            (tmp_path / "data" / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows), encoding="utf-8")

        def sleeves(self) -> list[dict]:
            p = tmp_path / "data" / "sleeves.json"
            if not p.exists():
                return []
            return json.loads(p.read_text(encoding="utf-8"))["sleeves"]

    return Desk()


_GOOD = {"status": "PROMOTION CANDIDATE", "exp_r": 0.276, "n": 40, "max_dd_r": -8.0}


# --------------------------------------------------------------------- promote

def test_a_conditioned_candidate_promotes_carrying_its_state(desk):
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["name"] == "CADJPY.asia.FAILED_BREAK"
    assert s["symbol"] == "CADJPY" and s["window"] == "asia"
    assert s["state"] == "FAILED_BREAK", "the gateway would trade this unconditioned"


def test_an_unconditioned_candidate_promotes_with_a_null_state(desk):
    desk.shadow({"CADJPY.asia": dict(_GOOD)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["state"] is None


def test_promotion_is_idempotent(desk):
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    promoter.main()
    assert len(desk.sleeves()) == 1, "the same sleeve promoted twice"


# ---------------------------------------------------------------------- retire

def _losing(name: str, n: int = 12) -> list[dict]:
    return [{"sleeve": name, "r_multiple": -1.0} for _ in range(n)]


def test_retiring_a_conditioned_sleeve_kills_THAT_sleeve_in_shadow(desk):
    """THE BUG. The retire path rebuilt the shadow key as f"{symbol}.{window}", dropping the
    state. Retiring CADJPY.asia.FAILED_BREAK therefore wrote KILL onto "CADJPY.asia" -- a
    DIFFERENT sleeve, which is itself in the shadow set and had done nothing wrong -- while the
    conditioned sleeve kept its PROMOTION CANDIDATE status untouched."""
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD),
                 "CADJPY.asia": {"status": "ACTIVE", "exp_r": 0.163, "n": 30}})
    promoter.main()
    desk.ledger(_losing("CADJPY.asia.FAILED_BREAK"))
    promoter.main()

    (s,) = desk.sleeves()
    assert s["status"] == "RETIRED"
    after = desk.read_shadow()
    assert after["CADJPY.asia.FAILED_BREAK"]["status"] == "KILL"
    assert after["CADJPY.asia"]["status"] == "ACTIVE", (
        "retiring the conditioned sleeve killed the unconditioned one")


def test_a_retired_sleeve_is_never_re_promoted(desk):
    """The consequence, and the docstring's own promise. With the status left on PROMOTION
    CANDIDATE the next run saw a candidate absent from `existing` -- because the retired entry
    still occupies the name -- and the desk oscillated: promote, retire, promote, forever."""
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    desk.ledger(_losing("CADJPY.asia.FAILED_BREAK"))
    promoter.main()
    for _ in range(3):
        promoter.main()
    names = [s["name"] for s in desk.sleeves()]
    assert names == ["CADJPY.asia.FAILED_BREAK"], f"re-promoted: {names}"
    assert all(s["status"] == "RETIRED" for s in desk.sleeves())


def test_retirement_reasons_are_recorded(desk):
    desk.shadow({"USDJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    desk.ledger(_losing("USDJPY.asia.FAILED_BREAK"))
    promoter.main()
    (s,) = desk.sleeves()
    assert s["retire_reason"] and s["retired_at"]


def test_a_winning_sleeve_is_not_retired(desk):
    desk.shadow({"EURJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    desk.ledger([{"sleeve": "EURJPY.asia.FAILED_BREAK", "r_multiple": r}
                 for r in [2.0, -1.0, 2.0, -1.0, 2.0, -1.0, 2.0, -1.0, 2.0, -1.0, 2.0, 2.0]])
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"


# ------------------------------------------------------------- gold challengers

def test_a_gold_challenger_waits_for_the_armed_book(desk):
    desk.shadow({"XAUUSD.asia.NORMAL_DAY": dict(_GOOD)})
    promoter.main()
    assert desk.sleeves() == [], "promoted with nothing to compare against"


def test_a_gold_challenger_that_loses_to_the_armed_book_is_killed_not_promoted(desk):
    desk.shadow({"XAUUSD.asia.NORMAL_DAY": {**_GOOD, "exp_r": 0.10}})
    desk.ledger([{"sleeve": "gold_asia", "r_multiple": 0.40} for _ in range(6)])
    promoter.main()
    assert desk.sleeves() == []
    assert desk.read_shadow()["XAUUSD.asia.NORMAL_DAY"]["status"] == "KILL"


def test_a_gold_challenger_that_beats_the_armed_book_promotes(desk):
    desk.shadow({"XAUUSD.asia.NORMAL_DAY": {**_GOOD, "exp_r": 0.40}})
    desk.ledger([{"sleeve": "gold_asia", "r_multiple": 0.10} for _ in range(6)])
    promoter.main()
    (s,) = desk.sleeves()
    assert s["name"] == "XAUUSD.asia.NORMAL_DAY" and s["state"] == "NORMAL_DAY"


def test_a_demo_fill_cannot_retire_a_live_sleeve(desk):
    """THE TRAP THE FUSION DEMO OPENS. The broker is switched by editing one line of
    data/terminal_path.txt, so demo fills land in the SAME live_ledger.jsonl the promoter reads to
    retire live sleeves -- and demo fills are optimistic, not conservative. A losing demo run must
    not retire a live edge, and a flattering one must not keep a dead one alive."""
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    demo = {"login": 999, "server": "FusionMarkets-Demo", "kind": provenance.DEMO}
    desk.ledger_raw([{**provenance.stamp(demo), "sleeve": "CADJPY.asia.FAILED_BREAK",
                      "r_multiple": -1.0} for _ in range(12)])
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE", "a demo losing streak retired a live sleeve"


def test_unstamped_legacy_rows_are_not_counted_as_evidence(desk):
    """Rows written before provenance are real trades on SOME account. The desk cannot say which,
    so they decide nothing -- rather than being credited to whatever account is connected today."""
    desk.shadow({"CADJPY.asia.FAILED_BREAK": dict(_GOOD)})
    promoter.main()
    desk.ledger_raw([{"sleeve": "CADJPY.asia.FAILED_BREAK", "r_multiple": -1.0}
                     for _ in range(12)])
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE"


def test_the_armed_gold_book_is_never_touched_by_the_promoter(desk):
    """gold_* sleeves are hunt5 authority, armed by a human. They live in gateway.sleeve_set,
    not sleeves.json -- but if one ever leaks in, the retire loop must not silently pull it."""
    desk.shadow({})
    desk.ledger(_losing("gold_asia", n=30))
    promoter.main()
    assert desk.sleeves() == []
