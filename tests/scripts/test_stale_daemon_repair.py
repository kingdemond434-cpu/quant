"""The stale-daemon repairer's gating -- every skip is a named verdict, and the two hard gates
(ruin tier, sterile window) can never be reasoned around by the repair path.

The actuator exists because daemon-stale-code recurred 4x in 12 days with every closure done by
hand; the DANGEROUS failure modes of an automatic restarter are (a) restarting the ruin rail and
(b) shipping code into the money path mid-freeze. Both are pinned here as pure decisions, so no
systemd mock is needed and no refactor can silently widen the repair set.
"""

from __future__ import annotations

from scripts.run_stale_daemon_repair import _money_path, decide

from libs.ops.deploy_plan import TIER_RUIN

_MONEY = ("scripts/run_cashcarry_executor.py", "libs/execution/",
          "scripts/run_deadman_switch.py")


def test_fresh_daemon_is_never_touched_regardless_of_window():
    assert decide("scripts/run_cashcarry_executor.py", 0, window_status="OPEN",
                  tier=1, money=_MONEY) == "SKIP-FRESH"
    assert decide("scripts/run_cashcarry_executor.py", 0, window_status="STERILE",
                  tier=1, money=_MONEY) == "SKIP-FRESH"


def test_ruin_tier_is_skipped_even_when_stale_and_window_open():
    assert decide("scripts/run_deadman_switch.py", 3, window_status="OPEN",
                  tier=TIER_RUIN, money=_MONEY) == "SKIP-RUIN-TIER"


def test_sterile_window_holds_money_path_but_not_the_rest():
    assert decide("scripts/run_cashcarry_executor.py", 2, window_status="STERILE",
                  tier=1, money=_MONEY) == "SKIP-STERILE"
    assert decide("scripts/liquidation_listener.py", 2, window_status="STERILE",
                  tier=1, money=_MONEY) == "REPAIR"


def test_unmeasured_window_is_treated_like_sterile_not_open():
    """A broken window fence must fail toward holding the money path, never toward shipping."""
    assert decide("scripts/run_cashcarry_executor.py", 2, window_status="UNMEASURED",
                  tier=1, money=_MONEY) == "SKIP-STERILE"


def test_open_window_repairs_a_stale_money_path_unit():
    assert decide("scripts/run_cashcarry_executor.py", 2, window_status="OPEN",
                  tier=1, money=_MONEY) == "REPAIR"


def test_unknown_tier_is_named_not_repaired():
    assert decide("scripts/whatever.py", 1, window_status="OPEN",
                  tier=None, money=_MONEY) == "SKIP-UNKNOWN-TIER"


def test_money_path_matches_directory_prefixes():
    assert _money_path("libs/execution/binance_live.py", _MONEY)
    assert not _money_path("libs/executionish.py", _MONEY)
    assert not _money_path("scripts/serve_dashboard.py", _MONEY)
