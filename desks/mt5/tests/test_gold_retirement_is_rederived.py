"""A standing gold retirement is re-derived from admissible evidence, never merely trusted.

MEASURED 2026-09-08 on this tree. data/GOLD_RETIRED.json holds gold_asia, retired 2026-09-02T23:38Z
on `roll20 exp -0.834R <= 0`, n=30, exp -0.842, max_dd -24.26. `decision_core.roster` skips the
whole asia window on that key, so the four XAUUSD.asia registry rows marked LIVE placed nothing
(check_gold_live: "4 XAUUSD sleeve(s) marked LIVE but REFUSED"). The record fails the promoter's
own laws twice over: `degenerate_evidence` names this very entry as the near-constant defect it
was written to refuse (its rule landed AFTER the entry, which was never re-judged; the 09-01
twin was undone by hand in bdbb712c), and the live account has recorded no fill at all, so no
ledger `load_ledger` admits can hold the thirty rows the record claims.

The promoter's own second defect made this permanent: it asked `mt5.account_info()` in a process
that never held a terminal connection (the gateway loop shuts the terminal at the end of every
pass; daily_cycle never opens one), read UNKNOWN, and therefore an EMPTY ledger, on every pass.
`account_in_hand` now measures the account the way the gateway does.

What is pinned: (a) an entry whose n cannot be reproduced from the account in hand's rows is
voided into the sibling audit file and the window is emitted again; (b) a dispersed, losing,
admissible ledger keeps it retired; (c) a near-constant ledger voids it on the degenerate reason
and does not re-retire; (d) a void is re-judged on the SAME pass by the unchanged thresholds;
(e) an UNKNOWN account judges nothing; (f) absence of evidence never voids.
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
from mt5desk import decision_core as _dc  # noqa: E402
from mt5desk import provenance  # noqa: E402

_ACC = {"login": 5551234, "server": "FusionMarkets-Live", "kind": provenance.LIVE}
_OTHER = {"login": 9990001, "server": "FusionMarkets-Demo", "kind": provenance.DEMO}

#: The 2026-09-02 entry, verbatim from the tree's data/GOLD_RETIRED.json.
_ENTRY = {"retired_at": "2026-09-02T23:38:34+00:00", "reason": "roll20 exp -0.834R <= 0",
          "n": 30, "exp": -0.8420000000000001, "roll20_exp": -0.8335000000000001,
          "max_dd": -24.26}

#: Thirty dispersed losses: a real loser, roll20 <= 0, no modal value near 80%.
_DISPERSED_LOSER = [-1.3, -0.6, -1.1, 0.4, -0.9, -1.7, 0.2, -0.5, -1.4, -0.8,
                    -1.2, 0.3, -0.7, -1.6, -0.4, -1.0, 0.5, -1.5, -0.3, -1.1,
                    -0.9, 0.1, -1.3, -0.6, -1.8, 0.6, -0.2, -1.4, -0.7, -1.0]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    shadow_dir = tmp_path / "reports" / "shadow"
    shadow_dir.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(promoter, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(promoter, "LEDGER", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(promoter, "LOG", tmp_path / "logs" / "promoter.log")
    monkeypatch.setattr(promoter, "ALLOCATION", tmp_path / "reports" / "pf_allocation.json")
    monkeypatch.setattr(promoter, "RECERT_AUDIT", tmp_path / "reports" / "recert.json")
    retired = tmp_path / "data" / "GOLD_RETIRED.json"
    voided = tmp_path / "data" / "GOLD_RETIRED_VOIDED.json"
    monkeypatch.setattr(promoter, "GOLD_RETIRED_FILE", retired)
    monkeypatch.setattr(promoter, "GOLD_RETIRED_VOIDED_FILE", voided)
    monkeypatch.setattr(promoter, "authorized_specs", lambda _base=None: set())
    account = dict(_ACC)
    # MetaTrader5 is absent on this host, so `account_in_hand` falls to current_account(None);
    # the fixture answers for the terminal.
    monkeypatch.setattr(promoter.provenance, "current_account", lambda _acc: dict(account))

    class Desk:
        def retire(self, **entries: dict) -> None:
            retired.write_text(json.dumps(entries, indent=2), "utf-8")

        def retired(self) -> dict:
            return json.loads(retired.read_text("utf-8")) if retired.exists() else {}

        def voided(self) -> dict:
            return json.loads(voided.read_text("utf-8")) if voided.exists() else {}

        def ledger(self, values: list[float], name: str = "gold_asia",
                   acc: dict | None = None) -> None:
            stamp = provenance.stamp(acc or _ACC)
            (tmp_path / "data" / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps({**stamp, "sleeve": name, "r_multiple": v})
                          for v in values), "utf-8")

        def account(self, acc: dict) -> None:
            account.clear()
            account.update(acc)

        def roster_names(self) -> list[str]:
            sleeves, _notes = _dc.roster(_dc.load_retired_gold(retired), [])
            return [s["name"] for s in sleeves]

    return Desk()


# ------------------------------------------------------------------ (a) the entry on the tree
def test_a_ledger_with_no_admissible_row_keeps_the_entry_standing(desk) -> None:
    """CORRECTED 2026-09-08 (verifier): the live account has no fills, and the FIRST version of
    the rule voided on exactly that -- an admissible count below the recorded n -- which is true
    of an empty ledger, a missing file, a torn file and an account that has not traded. Absence
    of evidence re-opened the one-way door. It no longer does: the entry stands until something
    POSITIVE says the number was wrong."""
    desk.retire(gold_asia=dict(_ENTRY))
    assert desk.roster_names() == ["gold_london_am", "gold_afternoon"]
    promoter.main()                                    # no ledger file at all
    assert desk.retired()["gold_asia"] == _ENTRY and desk.voided() == {}
    desk.ledger([])                                    # a ledger with nothing in it
    promoter.main()
    assert desk.retired()["gold_asia"] == _ENTRY and desk.voided() == {}
    desk.ledger(_DISPERSED_LOSER[:5])                  # a few admissible rows, fewer than n
    promoter.main()
    assert desk.retired()["gold_asia"] == _ENTRY and desk.voided() == {}
    assert desk.roster_names() == ["gold_london_am", "gold_afternoon"]


def test_rows_from_another_account_are_not_this_account_s_evidence(desk) -> None:
    """Thirty rows exist in the file, every one from a demo login: the number that retired the
    window was another account's. That is POSITIVE evidence, and the entry is void."""
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER, acc=_OTHER)
    promoter.main()
    assert "gold_asia" not in desk.retired()
    why = desk.voided()["gold_asia"]["voided_why"]
    assert "all stamped to another account" in why and "9990001@FusionMarkets-Demo/demo" in why
    assert "login=5551234" in why and "kind=live" in why
    assert desk.voided()["gold_asia"]["voided_at"] > _ENTRY["retired_at"]
    assert desk.roster_names() == ["gold_asia", "gold_london_am", "gold_afternoon"]


def test_fewer_foreign_rows_than_the_record_claims_prove_nothing(desk) -> None:
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER[:20], acc=_OTHER)     # 20 foreign rows against n=30
    promoter.main()
    assert "gold_asia" in desk.retired() and desk.voided() == {}


def test_rows_stamped_unknown_are_not_proof_of_another_account(desk) -> None:
    """A row with no provenance is a real trade on some account the desk cannot name. It is
    admissible for nobody -- and it is not proof the retirement came from elsewhere either."""
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER, acc={"login": 5551234, "server": "FusionMarkets-Live",
                                       "kind": provenance.UNKNOWN})
    promoter.main()
    assert "gold_asia" in desk.retired() and desk.voided() == {}


def test_a_torn_final_line_does_not_blind_the_ledger(desk) -> None:
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER, acc=_OTHER)
    ledger = promoter.LEDGER
    ledger.write_text(ledger.read_text("utf-8") + '\n{"sleeve": "gold_asia", "r_mul', "utf-8")
    rows = promoter._all_ledger_rows()
    assert rows is not None and len(rows) == 30            # the torn line is skipped, not fatal
    promoter.main()
    assert "gold_asia" not in desk.retired()               # the thirty foreign rows still count


def test_a_dispersed_losing_admissible_ledger_keeps_the_retirement(desk) -> None:
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER)
    fs = promoter.sleeve_forward_stats(
        [{"sleeve": "gold_asia", "r_multiple": v} for v in _DISPERSED_LOSER], "gold_asia")
    assert fs["n"] == 30 and fs["roll20_exp"] <= 0.0, "fixture must be a genuine loser"
    assert not promoter.degenerate_evidence(
        [{"sleeve": "gold_asia", "r_multiple": v} for v in _DISPERSED_LOSER], "gold_asia")
    promoter.main()
    assert desk.retired()["gold_asia"] == _ENTRY          # untouched, byte for byte
    assert desk.voided() == {}
    assert desk.roster_names() == ["gold_london_am", "gold_afternoon"]


# ------------------------------------------------------- (c) the defect shape voids, on its name
def test_a_near_constant_ledger_voids_on_the_degenerate_reason_and_is_not_re_retired(desk) -> None:
    """The 09-02 series as the promoter's own comment describes it: about twenty-five identical
    -1.000s and a few other values."""
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger([-1.0] * 27 + [-0.4, -0.7, 0.3])
    promoter.main()
    assert "gold_asia" not in desk.retired()
    why = desk.voided()["gold_asia"]["voided_why"]
    assert "27 of 30 r_multiples are exactly -1.000" in why
    assert "Refusing to retire on it" in why
    assert desk.roster_names()[0] == "gold_asia"


# ------------------------------------------- (d) the thresholds still bind on the same pass
def test_a_void_falls_through_to_the_unchanged_retire_rules_and_they_still_bite(desk) -> None:
    """A void by foreign evidence is followed, on the SAME pass, by the unchanged retire walk on
    the admissible rows -- with none, nothing re-retires (n=0 < RETIRE_MIN_N). Then twelve
    admissible dispersed losses arrive: n >= 10 and roll20 <= 0, and the window is retired AGAIN,
    on this account's own evidence, before the gateway reads the file. The thresholds did not
    move."""
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER, acc=_OTHER)
    promoter.main()
    assert "gold_asia" not in desk.retired() and desk.voided()["gold_asia"]["n"] == 30
    assert desk.roster_names() == ["gold_asia", "gold_london_am", "gold_afternoon"]
    twelve = _DISPERSED_LOSER[:12]
    assert promoter.RETIRE_MIN_N <= 12 and sum(twelve) / 12 <= 0.0
    foreign = [{**provenance.stamp(_OTHER), "sleeve": "gold_asia", "r_multiple": v}
               for v in _DISPERSED_LOSER]
    mine = [{**provenance.stamp(_ACC), "sleeve": "gold_asia", "r_multiple": v} for v in twelve]
    promoter.LEDGER.write_text("\n".join(json.dumps(r) for r in foreign + mine), "utf-8")
    promoter.main()
    entry = desk.retired()["gold_asia"]
    assert entry["n"] == 12 and entry["reason"].startswith("roll20 exp")
    assert entry["retired_at"] > _ENTRY["retired_at"]              # a NEW retirement
    assert desk.roster_names() == ["gold_london_am", "gold_afternoon"]
    # and a mixed file is not "all another account's": the new entry stands on the next pass
    promoter.main()
    assert desk.retired()["gold_asia"] == entry
    assert (promoter.RETIRE_MIN_N, promoter.RETIRE_MAX_DD,
            promoter.RETIRE_MIN_EXP) == (10, -25.0, 0.05)


def test_the_windows_the_record_names_are_the_ones_roster_gates() -> None:
    names = tuple(f"gold_{w[0]}" for w in _dc.GOLD_WINDOWS)
    assert names == promoter.GOLD_SLEEVE_NAMES


# --------------------------------------------------------------- (e) unknown is not empty
def test_an_unknown_account_judges_nothing(desk) -> None:
    """No terminal, no admissible rows: voiding on that would re-arm a window on a visibility
    outage. The entry stands and the pass says so."""
    desk.retire(gold_asia=dict(_ENTRY))
    desk.ledger(_DISPERSED_LOSER)
    desk.account({"login": None, "server": None, "kind": provenance.UNKNOWN})   # no terminal
    promoter.main()
    assert desk.retired()["gold_asia"] == _ENTRY
    assert desk.voided() == {}
    assert "RETIREMENT STANDS UNJUDGED gold_asia" in promoter.LOG.read_text("utf-8")


def test_an_entry_with_no_recorded_n_is_kept_unless_its_evidence_is_degenerate(desk) -> None:
    """A hand-written entry claims no sample; there is nothing to fail to reproduce."""
    desk.retire(gold_asia={"retired_at": "2026-09-01T00:00:00+00:00", "reason": "by hand"})
    promoter.main()
    assert "gold_asia" in desk.retired() and desk.voided() == {}


def test_the_void_reason_is_pure_and_names_its_outcomes() -> None:
    rows = [{"sleeve": "gold_asia", "r_multiple": v} for v in _DISPERSED_LOSER]
    unknown = provenance.current_account(None)
    foreign = [{**provenance.stamp(_OTHER), "sleeve": "gold_asia", "r_multiple": v}
               for v in _DISPERSED_LOSER]
    assert promoter.retirement_void_reason(_ENTRY, [], "gold_asia", unknown) == ""
    assert promoter.retirement_void_reason(_ENTRY, rows, "gold_asia", _ACC) == ""
    # absence proves nothing: no rows, an unreadable file, a short file
    assert promoter.retirement_void_reason(_ENTRY, [], "gold_asia", _ACC) == ""
    assert promoter.retirement_void_reason(_ENTRY, [], "gold_asia", _ACC, all_rows=None) == ""
    assert promoter.retirement_void_reason(_ENTRY, [], "gold_asia", _ACC, all_rows=[]) == ""
    assert promoter.retirement_void_reason(_ENTRY, [], "gold_asia", _ACC,
                                           all_rows=foreign[:29]) == ""
    # positive evidence: another account's rows, or a degenerate admissible series
    assert "another account" in promoter.retirement_void_reason(
        _ENTRY, [], "gold_asia", _ACC, all_rows=foreign)
    assert "computation defect" in promoter.retirement_void_reason(
        _ENTRY, [{"sleeve": "gold_asia", "r_multiple": -1.0}] * 30, "gold_asia", _ACC)


# ------------------------------------------------------ the account the promoter measures
def test_account_in_hand_opens_and_closes_its_own_connection(monkeypatch) -> None:
    """The promoter runs after `gateway.main()` has shut the terminal (run_gateway_loop) or with
    none open (daily_cycle): it must attach itself, read, and detach -- and leave an open
    connection alone."""
    import types
    calls: list[str] = []

    class _Acc:
        login, server, trade_mode = 5551234, "FusionMarkets-Live", 2

    fake = types.SimpleNamespace(
        terminal_info=lambda: None if "init" not in calls else object(),
        initialize=lambda path=None: calls.append("init") or True,
        account_info=lambda: _Acc(),
        shutdown=lambda: calls.append("shutdown"),
        last_error=lambda: (0, ""))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(promoter.provenance, "current_account", provenance.current_account)
    got = promoter.account_in_hand()
    assert got == {"login": 5551234, "server": "FusionMarkets-Live", "kind": provenance.LIVE}
    assert calls == ["init", "shutdown"]
    # already connected: read only, no shutdown
    calls.clear()
    fake.terminal_info = lambda: object()
    assert promoter.account_in_hand()["kind"] == provenance.LIVE
    assert calls == []
    # unreachable: UNKNOWN, never a guess
    fake.terminal_info = lambda: None
    fake.initialize = lambda path=None: False
    assert promoter.account_in_hand()["kind"] == provenance.UNKNOWN


def test_main_measures_the_account_once_and_hands_it_to_the_ledger() -> None:
    src = (_DESK / "research" / "promoter.py").read_text("utf-8")
    main_src = src[src.index("def main() -> None:"):]
    assert "acc = account_in_hand()" in main_src
    assert "ledger = load_ledger(acc)" in main_src
    assert main_src.index("acc = account_in_hand()") < main_src.index("ledger = load_ledger(acc)")
    assert "retirement_void_reason(gold_retired[gname], ledger, gname, acc," in main_src
    assert "all_rows=all_rows)" in main_src
    assert "all_rows = _all_ledger_rows()" in main_src
