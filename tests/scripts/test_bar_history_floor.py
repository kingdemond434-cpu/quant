"""The registry got a ratchet and the bars did not.

    python -m pytest tests/scripts/test_bar_history_floor.py -q

`check_universe_floor.py` exists because universe.json collapsed from 251 symbols to a 23-symbol
stump and the gauntlet swept a tenth of the desk for hours reporting success. Measured 2026-09-04,
the same failure was sitting in the BARS and nothing was watching:

    AUDCAD  53,864 rows  2,246 days   2018-01-02 -> 2026-08-28
    AUDNZD     479 rows     20 days   2026-08-03 -> 2026-08-28

One per cent of its peers. The certificate `AUDNZD dav_range_filter_adx SHORT afternoon
NORMAL_DAY` claims 179 days and cannot be replayed on it at all -- the cell needs sixty signals at
the window hour and the stump yields two.

WHAT MUST NOT REGRESS:

  1. a first-ever stump is caught with NO high-water history to fall from
  2. the high-water mark only ever RISES -- a stump must not become the new standard
  3. a collapse against a known high water is caught by name, with both numbers
  4. normal churn does not fire
  5. an unreadable parquet is REPORTED, never skipped
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_bar_history_floor as bf  # noqa: E402


def _peers(n: int = 6, days: int = 2246) -> dict[str, dict[str, int]]:
    return {f"SYM{i}": {"rows": days * 24, "days": days} for i in range(n)}


# ------------------------------------------------- 1. the first stump, with no history

def test_a_first_ever_stump_is_caught_without_any_high_water() -> None:
    now = _peers()
    now["AUDNZD"] = {"rows": 479, "days": 20}
    breaches, _ = bf.evaluate(now, {})
    kinds = {b["symbol"]: b["kind"] for b in breaches}
    assert kinds.get("AUDNZD") == "STUMP_VS_PEERS", (
        "twenty days beside two thousand is a broken file, not a short history")
    assert len(breaches) == 1, "healthy peers must not be reported"


# ------------------------------------------------- 2. the ratchet cannot be walked down

def test_the_high_water_mark_only_rises() -> None:
    """Recording a collapsed value would let a stump become the standard on its second run."""
    prior = {"AUDNZD": {"days": 2246, "rows": 53864}}
    now = {"AUDNZD": {"rows": 479, "days": 20}}
    _, keep = bf.evaluate(now, prior)
    assert keep["AUDNZD"]["days"] == 2246
    assert keep["AUDNZD"]["rows"] == 53864


def test_a_genuine_new_high_is_recorded() -> None:
    prior = {"EURUSD": {"days": 2000, "rows": 48000}}
    now = {"EURUSD": {"rows": 53864, "days": 2246}}
    _, keep = bf.evaluate(now, prior)
    assert keep["EURUSD"] == {"days": 2246, "rows": 53864}


# ------------------------------------------------- 3. collapse against known history

def test_a_collapse_is_named_with_both_numbers() -> None:
    prior = {"EURUSD": {"days": 2246, "rows": 53864}}
    now = _peers()
    now["EURUSD"] = {"rows": 900, "days": 40}
    breaches, _ = bf.evaluate(now, prior)
    b = next(x for x in breaches if x["symbol"] == "EURUSD")
    assert b["kind"] == "COLLAPSED"
    assert b["days_now"] == 40 and b["days_high_water"] == 2246
    assert b["rows_now"] == 900 and b["rows_high_water"] == 53864


def test_normal_churn_does_not_fire() -> None:
    """Real history shrinks a little on delisting churn; a floor that fires on noise gets deleted."""
    prior = {s: {"days": 2246, "rows": 53864} for s in _peers()}
    now = {s: {"rows": 53000, "days": 2200} for s in _peers()}
    breaches, _ = bf.evaluate(now, prior)
    assert breaches == []


# ------------------------------------------------- 4. unreadable is reported, not skipped

def test_an_unreadable_parquet_is_reported() -> None:
    now = _peers()
    now["BROKEN"] = {"rows": -1, "days": -1, "error": "ArrowInvalid: bad magic"}
    breaches, _ = bf.evaluate(now, {})
    b = next(x for x in breaches if x["symbol"] == "BROKEN")
    assert b["kind"] == "UNREADABLE" and "ArrowInvalid" in b["why"]


def test_an_unreadable_symbol_does_not_poison_the_peer_median() -> None:
    """A -1 folded into the median would drag it down and hide every real stump."""
    now = _peers()
    now["BROKEN"] = {"rows": -1, "days": -1, "error": "x"}
    now["AUDNZD"] = {"rows": 479, "days": 20}
    breaches, _ = bf.evaluate(now, {})
    assert {b["symbol"] for b in breaches} == {"BROKEN", "AUDNZD"}
