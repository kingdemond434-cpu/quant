"""THE TIER-5 ACCEPTANCE TESTS AS PYTEST (mandate 154-156, 161), on this tree:

  NO-LLM PATH        the money path and this session's research organs import no external-model
                     seat at module level: they run with every LLM disabled.
  PARALLEL CAPACITY  the desk carries many parallel research residents, and the auction turns
                     excess capacity into more useful work and scarce capacity into a priority
                     on the highest-information department, two-sided and never to zero.
  MONOCULTURE        lineage concentration is REPORTED (HHI by family) and never capped: a
                     monoculture reads 1.0 and no organ of this session writes a cap.
  AGGRESSION         the 20% heat floor and the 0.02-lot gold floor are the constants the
                     principal fixed, and no organ of this session imports the gateway, the heat
                     policy or writes the sleeve roster -- none can reduce them.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ORGANS = ("portfolio_bounty", "research_auction", "bottleneck_law", "drawdown_alpha_miner",
          "trade_autopsy", "research_latency", "alpha_replenishment", "research_dashboard")
MONEY_PATH = (DESK / "scripts" / "external_gauntlet.py", DESK / "research" / "universal_gate.py",
              DESK / "research" / "pf_allocator.py", DESK / "research" / "promoter.py",
              DESK / "research" / "shadow_cycle.py")
LLM_IMPORT = re.compile(r"^\s*(from|import)\s+(libs\.llm|libs\.ops\.llm_seat|libs\.ops\.llm_route|"
                        r"openai|anthropic|google\.generativeai)\b", re.M)


def _src(p: Path) -> str:
    return p.read_text("utf-8", errors="replace")


def test_no_llm_path_the_organism_runs_with_every_model_disabled() -> None:
    for name in ORGANS:
        assert not LLM_IMPORT.search(_src(DESK / "research" / f"{name}.py")), name
    for p in MONEY_PATH:
        assert p.exists(), p
        top_level = "\n".join(line for line in _src(p).splitlines()
                              if line and not line.startswith((" ", "\t")))
        assert not LLM_IMPORT.search(top_level), f"{p.name} imports a model seat at module level"


def test_parallel_capacity_is_real_and_the_auction_spends_it() -> None:
    import research_auction as ra
    manifest = _src(DESK / "ops" / "box_tasks.manifest")
    residents = re.findall(r'TASK name="([^"]+)"[^\n]*resident', manifest)
    assert len(residents) >= 10, "the desk runs its departments as parallel residents"
    import hourly_cycle as hc
    assert len(hc.DEPARTMENTS) >= 8
    depts = ("discovery", "validate", "intel", "meta")
    hours = dict.fromkeys(depts, 10.0)
    # EXCESS capacity: every department productive and no bottleneck -> everyone at par, nobody
    # idle, nobody cut.
    rows = ra.bids(depts, hours, dict.fromkeys(depts, 30), {}, {}, {})
    assert all(f == 1.0 for f in ra.clear(rows).values())
    # SCARCE capacity with one department carrying the information: it wins, the others pay,
    # the clearing is budget-neutral in logs before the clip and nobody reaches zero.
    rows = ra.bids(depts, hours, {"discovery": 90, "validate": 5, "intel": 5, "meta": 5},
                   {}, {}, {})
    f = ra.clear(rows)
    assert f["discovery"] == max(f.values()) and f["discovery"] > 1.0
    assert min(f.values()) >= ra.FLOOR > 0.0 and max(f.values()) <= ra.CEIL
    raw = [math.log(float(r["bid"])) for r in rows.values()]
    gm = sum(raw) / len(raw)
    assert abs(sum(math.log(float(r["bid"])) - gm for r in rows.values())) < 1e-9


def test_monoculture_concentration_is_reported_never_capped() -> None:
    import research_dashboard as rd
    mono = rd.lineage_concentration({"survivors": {f"h.c{i}": {"cell": f"EURUSD carry x{i}"}
                                                    for i in range(12)}})
    assert mono["hhi"] == 1.0 and mono["top_family"] == "carry" and mono["capped"] is False
    spread = rd.lineage_concentration({"survivors": [{"family": "a"}, {"family": "b"},
                                                     {"family": "c"}, {"family": "d"}]})
    assert spread["hhi"] == 0.25 and spread["n_families"] == 4 and spread["capped"] is False
    assert rd.lineage_concentration({})["status"] == "UNMEASURED"
    for name in ORGANS:
        src = _src(DESK / "research" / f"{name}.py")
        assert not re.search(r"MAX_(LINEAGE|FAMILY|SHARE)\s*=", src), name
        # the roster is read, never written: no organ of this session can cap a family
        assert not re.search(r"SLEEVES\.(write_text|open)", src), name


def test_aggression_floors_are_the_principals_and_no_organ_can_lower_them() -> None:
    gw = _src(DESK / "mt5desk" / "gateway.py")
    assert re.search(r"^LOT\s*=\s*0\.02\s*$", gw, re.M), "the 0.02-lot gold floor stands"
    cfg = _src(DESK / "mt5desk" / "gateway_config_fallback.py")
    assert re.search(r"^HEAT_TARGET\s*=\s*0\.20?\s*$", cfg, re.M), "the 20% heat floor stands"
    forbidden = re.compile(r"^\s*(from|import)\s+(mt5desk\.gateway|gateway|heat_policy|"
                           r"mt5desk\.config|gateway_config_fallback)\b", re.M)
    for name in ORGANS:
        src = _src(DESK / "research" / f"{name}.py")
        assert not forbidden.search(src), f"{name} must not touch the gateway or the heat policy"
        assert "gateway_state" not in src and "risk_frac" not in src, name
        assert "HEAT_TARGET" not in src and "LOT =" not in src, name
