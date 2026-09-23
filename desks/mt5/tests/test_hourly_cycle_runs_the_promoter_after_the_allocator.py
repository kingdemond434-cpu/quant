"""The hourly roster runs the promoter right after the allocator leg, so a measured admission
is READ within the hour it was taken.

MEASURED 2026-09-08 (trace of the promoted-scalp money path). A promoted row reaches the gateway
only at status LIVE (decision_core.load_sleeves keeps LIVE alone), and LIVE is written only by
the promoter: on a fresh MEASURED admission scan that admits the sleeve, and for a STANDBY row on
PROMOTE_ADMIT_STREAK consecutive such readings, one reading per promoter pass
(promoter.reconcile_capital). The promoter had two schedulers -- the 22:00 UTC gateway pass
(run_gateway_loop) and the daily cycle -- so an admission the allocator measured at 13:00 waited
until 22:00 for its first reading and until the next day for its second, while the scan aged
toward the 26h the promoter accepts. Three scalp sleeves sat at PROMOTION_CANDIDATE for seventeen
days with every artifact reading healthy.

The leg is a cadence change only: `promoter.main` skips names already on the roster, records the
current reading on every standing row, and moves a row only on the asymmetric rule it already
holds. PROMOTE_ADMIT_STREAK, the admission margin, the 26h max age and every threshold are the
promoter's own and untouched here.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SRC = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
TREE = ast.parse(SRC)
MAIN = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "main")


def _producer_lines() -> dict[str, int]:
    """leg name -> line of its `_producer(<name>, ...)` call inside main()."""
    out: dict[str, int] = {}
    for n in ast.walk(MAIN):
        if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_producer"
                and n.args and isinstance(n.args[0], ast.Constant)):
            out.setdefault(str(n.args[0].value), n.lineno)
    return out


def test_the_promoter_leg_runs_after_the_allocator_and_before_the_marker_is_written() -> None:
    legs = _producer_lines()
    assert legs["pf_allocator"] < legs["promoter"], "the promoter reads the allocator's scan"
    marker = next(n.lineno for n in ast.walk(MAIN)
                  if isinstance(n, ast.Constant) and n.value == "sync_marker.json")
    assert legs["promoter"] < marker
    publish = next(n.lineno for n in ast.walk(MAIN)
                   if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_costed"
                   and isinstance(n.args[0], ast.Constant) and n.args[0].value == "publish_state")
    assert legs["promoter"] < publish, "publication delivers the roster this pass produced"


def test_the_promoter_leg_is_the_module_s_own_main_run_as_a_bounded_subprocess() -> None:
    assert '_producer("promoter", "research/promoter.py")' in SRC
    assert (DESK / "research" / "promoter.py").exists()


def test_the_promoter_leg_is_costed_and_recorded_in_the_marker() -> None:
    main_src = ast.get_source_segment(SRC, MAIN)
    leg = 'pr = _costed("promoter", lambda: _producer("promoter", "research/promoter.py"))'
    assert leg in main_src
    assert '"promoter": pr' in main_src


def test_the_leg_changes_no_promoter_law() -> None:
    """Cadence, not thresholds: the constants the promoter judges by are unchanged."""
    import promoter

    assert promoter.PROMOTE_ADMIT_STREAK == 2
    assert promoter.ADMISSION_MAX_AGE_H == 26.0
    assert promoter.PROMOTED_RISK_FRAC == 0.03
    assert (promoter.RETIRE_MIN_N, promoter.RETIRE_MAX_DD,
            promoter.RETIRE_MIN_EXP) == (10, -25.0, 0.05)
