"""GAP 130 regression: hibernation must be woken by SHADOW evidence, not starved by live silence.

The failure this pins down: a hibernated sleeve stops producing live rows, so a live-only
monitor freezes at the values that hibernated it -- a one-way door wearing a reversible name.
The fix drives the wake from shadow replay, which keeps accruing while the sleeve is dark.
"""
import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "regime_monitor_under_test",
    Path(__file__).resolve().parents[2] / "desks/mt5/research/regime_monitor.py")
assert _SPEC is not None and _SPEC.loader is not None
rm = importlib.util.module_from_spec(_SPEC)
sys.modules["regime_monitor_under_test"] = rm
_SPEC.loader.exec_module(rm)

_BAD_LIVE = [-0.5] * 40          # trailing live expectancy -0.5 < -0.10 -> hibernate
_GOOD_SHADOW = [0.2] * 40        # shadow recovered: exp 0.2 >= WAKE_EXP
_BAD_SHADOW = [-0.5] * 40


def test_shadow_recovery_wakes_a_hibernated_sleeve() -> None:
    state = rm.compute_state({"XAUUSD|asia": _BAD_LIVE},
                             {"XAUUSD|asia": _GOOD_SHADOW}, now="t")
    row = state["sleeves"]["XAUUSD|asia"]
    assert row["flag"] == "ok" and row["woke_on_shadow"] is True


def test_bad_shadow_keeps_hibernation() -> None:
    state = rm.compute_state({"XAUUSD|asia": _BAD_LIVE},
                             {"XAUUSD|asia": _BAD_SHADOW}, now="t")
    row = state["sleeves"]["XAUUSD|asia"]
    assert row["flag"] == "hibernate" and row["woke_on_shadow"] is False


def test_thin_shadow_evidence_is_not_a_wake() -> None:
    # 10 shadow rows < MIN_N: absence of evidence is never a wake (L1.28a)
    state = rm.compute_state({"XAUUSD|asia": _BAD_LIVE},
                             {"XAUUSD|asia": [0.5] * 10}, now="t")
    assert state["sleeves"]["XAUUSD|asia"]["flag"] == "hibernate"


def test_shadow_tags_map_to_parent_sleeve_not_pseudo_sleeve(tmp_path: Path) -> None:
    # Regression for the old parser: 'shadow|XAUUSD|asia' must feed sleeve 'XAUUSD|asia',
    # never create a merged 'shadow|XAUUSD' pseudo-sleeve.
    ledger = tmp_path / "live_ledger.jsonl"
    ledger.write_text(
        '{"tag": "shadow|XAUUSD|asia", "r_multiple": 0.3}\n'
        '{"tag": "shadow|XAUUSD|london", "r_multiple": 0.1}\n'
        '{"tag": "XAUUSD|asia", "r_multiple": -0.2}\n')
    live, shadow = rm._read_live(ledger)
    assert set(live) == {"XAUUSD|asia"}
    assert set(shadow) == {"XAUUSD|asia", "XAUUSD|london"}


def test_shadow_only_sleeve_is_reported_but_never_hibernated() -> None:
    # No live evidence -> no hibernate authority from shadow alone (policy extension is
    # carded separately); the sleeve must still appear with its shadow stats.
    state = rm.compute_state({}, {"EURJPY|asia": _BAD_SHADOW}, now="t")
    row = state["sleeves"]["EURJPY|asia"]
    assert row["flag"] == "ok" and row["shadow_n"] == 40
