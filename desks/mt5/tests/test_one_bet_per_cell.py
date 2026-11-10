"""Copies of one executable are one bet at the gateway, whether or not the allocator priced them.

The Judge, 2026-11-10: carry certificates and forward clocks exist as copies of one executable
under different names (`input_symbol=GBPJPY` and `=eBay` are the same rule) -- 43 canon
certificates across 8 pairs. #708 folds the rows that join one allocator BOOK key; a copy the
book has not priced joined no key, so each LIVE copy took the base fraction.

Pinned here (#823, the Auditor's HOLD on 874c9ed84):
  * only TRUE copies fold -- the rows the Judge's published executable groups put together
    (certificate params minus the family's unread keys); a parameter variant, a family outside
    the Judge's table and a row with no certificate fold with nothing;
  * the alias stays ON the roster with its entry suppressed, so an open position or resting
    bracket of its own is still managed;
  * the oldest certificate, then the longest clock, carries; ties and counts are reported.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402

GBPJPY = "CHFDKK.carry.asia#input_symbol=GBPJPY"
EBAY = "CHFDKK.carry.asia#input_symbol=eBay"
OWN = "CHFDKK.carry.asia#input_symbol=CHFDKK"
VARIANT = "CHFDKK.carry.asia#input_symbol=CHFDKK_require_quiet=False"      # a distinct rule
OTHER = "nzdchf_clock_transition_asia_p_1"

#: The Judge's published shape: intake.executable_groups.sleeves.groups.
GROUPS = [
    {"symbol": "CHFDKK", "family": "carry", "copies": 3,
     "members": [{"name": GBPJPY, "state": "LIVE"}, {"name": EBAY, "state": "LIVE"},
                 {"name": OWN, "state": "LIVE"}]},
    {"symbol": "CHFDKK", "family": "carry", "copies": 1,
     "members": [{"name": VARIANT, "state": "LIVE"}]},
]


def _row(name: str, gated: str | None = None, days: float = 0.0) -> dict:
    row: dict = {"name": name, "status": "LIVE", "symbol": "CHFDKK", "family": "carry",
                 "selector": "asia", "shadow_days": days}
    if gated:
        row["certificate"] = {"gated_at": gated}
    return row


ROWS = [_row(GBPJPY, "2026-09-20T00:00:00+00:00", 30), _row(EBAY, "2026-09-02T00:00:00+00:00", 41),
        _row(OWN, "2026-09-02T00:00:00+00:00", 12), _row(VARIANT, "2026-09-01T00:00:00+00:00", 50),
        _row(OTHER)]


def test_only_the_judges_copy_groups_yield_a_key() -> None:
    keys = dc.executable_copy_keys(GROUPS)
    assert set(keys) == {GBPJPY, EBAY, OWN} and len(set(keys.values())) == 1
    assert VARIANT not in keys, "a parameter variant is a distinct rule: it folds with nothing"
    assert dc.executable_copy_keys(None) == {} and dc.executable_copy_keys([{"members": 3}]) == {}
    # a name the artifact lists in two groups is unjoinable, never guessed
    twice = [*GROUPS, {"symbol": "X", "family": "carry",
                       "members": [{"name": OWN}, {"name": "other_row"}]}]
    assert OWN not in dc.executable_copy_keys(twice)


def test_unpriced_copies_send_one_order_and_variants_keep_their_own() -> None:
    copies = dc.executable_copy_keys(GROUPS)
    keys = {r["name"]: copies.get(r["name"]) for r in ROWS}          # none is in the book
    ranks = {r["name"]: dc.carrier_rank(r) for r in ROWS}
    aliases = dc.fold_book_aliases(keys, ranks)
    # the oldest certificate carries; between two of the same date, the longest clock
    assert aliases == {GBPJPY: EBAY, OWN: EBAY}
    assert VARIANT not in aliases and OTHER not in aliases
    assert dc.carrier_ties(keys, ranks) == []
    tied = {GBPJPY: ("2026-09-02", -41.0), EBAY: ("2026-09-02", -41.0), OWN: ("2026-09-03", 0.0)}
    assert dc.carrier_ties(keys, tied) == [copies[GBPJPY]]


def test_with_no_published_groups_nothing_unpriced_is_folded() -> None:
    assert dc.fold_book_aliases({r["name"]: None for r in ROWS},
                                {r["name"]: dc.carrier_rank(r) for r in ROWS}) == {}
    assert dc.fold_book_aliases({"b": "K", "a": "K", "c": None}) == {"b": "a"}     # #708 as was


def test_the_gateway_reads_the_judges_artifact_and_refuses_a_stale_one(tmp_path) -> None:
    art = tmp_path / "HYPOTHESIS_FAMILIES.json"
    assert dc.executable_copies(art)[0] == {}                               # absent
    art.write_text(json.dumps({"intake": {}}), "utf-8")
    keys, why = dc.executable_copies(art)
    assert keys == {} and "no sleeve groups yet" in why                          # before #806
    art.write_text(json.dumps(
        {"intake": {"executable_groups": {"sleeves": {"groups": GROUPS}}}}), "utf-8")
    keys, why = dc.executable_copies(art)
    assert set(keys) == {GBPJPY, EBAY, OWN} and "1 copy group" in why
    old = time.time() - 4 * 3600
    os.utime(art, (old, old))
    keys, why = dc.executable_copies(art)
    assert keys == {} and "UNMEASURED" in why, "a stale grouping must not suppress an entry"
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    assert "_copies, _copies_why = executable_copies()" in src


def test_an_alias_stays_on_the_roster_with_its_entry_suppressed() -> None:
    """#823 audit MF2: the alias is never removed from the pass, so its own open position or
    resting bracket is still managed; only the new entry is withheld (sized by the book at 0)."""
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "sleeves = [_s for _s in sleeves\n               if not (str(_s[\"name\"]) in _aliases" \
        not in src
    i = src.index("_aliases = fold_book_aliases(_fold_keys, _ranks)")
    j = src.index("        elif str(_s[\"name\"]) in _aliases:\n")
    block = src[j:j + 900]
    assert i < j and "from_book = True" in block
    assert '_s["risk_frac"], _s["sized_by"] = 0.0, "allocator_book"' in block
    assert '_s["alias_of"] = _aliases[str(_s["name"])]' in block
    assert dc.promoted_lot(10_000.0, 500, dist_usd=0.005, symbol="EURUSD",
                           risk_frac=0.0, from_book=True) == 0.0
    assert 'st["alias_folded"] = {' in src and '"ties_decided_by_name"' in src

