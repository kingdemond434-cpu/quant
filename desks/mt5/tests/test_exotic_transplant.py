"""exotic_transplant: exotic certificates' exact specs re-minted on tradable instruments only.

Every input is synthetic (certified set, universe registry, docket, registry DB in tmp_path).
Load-bearing: no exotic target ever, dedupe against the docket and the registry, the per-pass
budget and cursor reach the whole plan, and every minted cell names its source certificate.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.frontier_identity import docket_cell_id  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from research import exotic_transplant as M  # noqa: E402


def _fx(sym: str, swap_long: float = 0.0, swap_short: float = 0.0,
        klass: str = "Forex") -> dict[str, Any]:
    return {"symbol": sym, "asset_class": klass, "swap_long": swap_long,
            "swap_short": swap_short, "tick_value": 1.0, "tick_size": 0.00001, "digits": 5}


META: dict[str, Any] = {
    **{s: _fx(s) for s in ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF",
                           "USDCAD", "EURJPY", "EURGBP", "GBPJPY", "AUDJPY", "CADJPY")},
    "AUDJPY": _fx("AUDJPY", 9.0, -12.0), "GBPJPY": _fx("GBPJPY", 8.0, -20.0),
    "USDJPY": _fx("USDJPY", 6.0, -16.0),
    "USDZAR": _fx("USDZAR", -200.0, -50.0, "Forex Exotics"),
    "EURNOK": _fx("EURNOK", -95.0, 24.0, "Forex Exotics"),
    "USDSEK": _fx("USDSEK", 21.0, -87.0, "Forex"),        # filed as plain Forex: still exotic
    "XAUUSD": {"symbol": "XAUUSD", "asset_class": "Commodities"},
    "USDX": {"symbol": "USDX", "asset_class": "Indices"},
    "US500": {"symbol": "US500", "asset_class": "Indices"},
    "XTIUSD": {"symbol": "XTIUSD", "asset_class": "Energy"},
    "BTCUSD": {"symbol": "BTCUSD", "asset_class": "Crypto"},
    "AAPL": {"symbol": "AAPL", "asset_class": "Equities"},
    "CORN": {"symbol": "CORN", "asset_class": "Soft Commodity"},
}


def _cert(sym: str, fam: str, params: dict[str, Any], tag: str = "p") -> tuple[str, dict]:
    return (f"external.{sym}.{fam}.{tag}",
            {"sym": sym, "shadow_spec": {"symbol": sym, "family": fam, "params": params}})


def _surv(*rows: tuple[str, dict]) -> dict[str, Any]:
    return dict(rows)


def _elig(tmp_path: Path) -> dict[str, Any]:
    return M.eligible_targets(META, tmp_path)


def _run(tmp_path: Path, surv: dict[str, Any], docket: list[dict[str, Any]] | None = None,
         **kw: Any) -> dict[str, Any]:
    dp = tmp_path / "docket.json"
    dp.write_text(json.dumps(docket or []), encoding="utf-8")
    return M.build(survivors=surv, survivors_path="test", meta=META, universe_dir=tmp_path,
                   docket=dp, cursor_path=tmp_path / "cursor.json", **kw)


def test_eligible_set_never_holds_an_exotic_an_equity_or_a_soft(tmp_path: Path) -> None:
    elig = _elig(tmp_path)
    for bad in ("USDZAR", "EURNOK", "USDSEK", "AAPL", "CORN"):
        assert bad not in elig
    for good in ("EURUSD", "XAUUSD", "USDX", "XTIUSD", "BTCUSD"):
        assert good in elig


def test_leg_rule_maps_the_major_leg_and_never_an_exotic(tmp_path: Path) -> None:
    elig = _elig(tmp_path)
    t, rule, _ = M.targets_for({"family": "overnight_gap_decay", "symbol": "USDZAR",
                                "params": {}}, elig)
    assert rule == "leg"
    assert set(t) == {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"}
    t2, _, _ = M.targets_for({"family": "clock_transition", "symbol": "EURNOK",
                              "params": {}}, elig)
    assert set(t2) == {"EURUSD", "EURJPY", "EURGBP"}
    assert not any(M.is_exotic(x) for x in t + t2)


def test_carry_takes_the_largest_positive_swaps(tmp_path: Path) -> None:
    elig = _elig(tmp_path)
    t, rule, _ = M.targets_for({"family": "carry", "symbol": "USDZAR",
                                "params": {"input_symbol": "USDZAR"}}, elig)
    assert rule == "carry"
    assert t[:3] == ["AUDJPY", "GBPJPY", "USDJPY"]
    assert len(t) <= M.CARRY_TOP_K
    p = M.transplant_params({"input_symbol": "USDZAR"}, "USDZAR", "AUDJPY")
    assert p == {"input_symbol": "AUDJPY"}


def test_macro_and_formula_follow_their_declared_drivers(tmp_path: Path) -> None:
    elig = _elig(tmp_path)
    t, rule, drv = M.targets_for({"family": "macro_conditional", "symbol": "USDZAR",
                                  "params": {"macro_series": "DCOILWTICO"}}, elig)
    assert rule == "macro" and drv == "DCOILWTICO->oil"
    assert t == ["XTIUSD", "USDCAD", "CADJPY"]
    t, rule, drv = M.targets_for({"family": "formula", "symbol": "EURNOK",
                                  "params": {"expr": ["corr", "ret", "risk", 24]}}, elig)
    assert rule == "driver" and drv == "risk"
    assert "US500" in t and "BTCUSD" in t
    t, rule, _ = M.targets_for({"family": "formula", "symbol": "EURNOK",
                                "params": {"expr": "zscore(range, 24)"}}, elig)
    assert rule == "leg" and set(t) == {"EURUSD", "EURJPY", "EURGBP"}


def test_a_target_that_is_a_factor_is_skipped(tmp_path: Path) -> None:
    assert M.transplant_params({"factor_symbols": ["USDJPY", "USDX"]}, "USDZAR",
                               "USDJPY") is None


def test_non_exotic_certificates_are_not_sources(tmp_path: Path) -> None:
    plan, stats = M.build_plan(_surv(_cert("EURUSD", "overnight_gap_decay", {})),
                               _elig(tmp_path))
    assert plan == []
    assert stats["overnight_gap_decay"]["certificates_read"] == 1
    assert stats["overnight_gap_decay"]["exotic_sources"] == 0


def test_docket_dedupe_skips_cells_already_there(tmp_path: Path) -> None:
    surv = _surv(_cert("EURNOK", "overnight_gap_decay", {"timeframe": "H4"}))
    have = {"symbol": "EURUSD", "family": "overnight_gap_decay", "params": {"timeframe": "H4"}}
    doc = _run(tmp_path, surv, docket=[have], dry_run=True)
    fam = doc["by_family"]["overnight_gap_decay"]
    assert fam["targets_planned"] == 3
    assert fam["skipped_duplicate_docket"] == 1
    assert fam["would_mint"] == 2
    assert doc["docket_dedupe"] == "COMPLETE"


def test_duplicate_within_the_plan_is_minted_once(tmp_path: Path) -> None:
    surv = _surv(_cert("USDZAR", "overnight_gap_decay", {}),
                 _cert("USDSEK", "overnight_gap_decay", {}))
    plan, stats = M.build_plan(surv, _elig(tmp_path))
    assert len(plan) == 7
    assert stats["overnight_gap_decay"]["skipped_duplicate_in_plan"] == 7
    # first source in key order keeps the provenance
    assert {p["source_certificate"] for p in plan} == {"external.USDSEK.overnight_gap_decay.p"}


def test_mint_budget_cursor_provenance_and_registry_dedupe(tmp_path: Path) -> None:
    R.set_path(tmp_path / "alpha_registry.sqlite")
    try:
        surv = _surv(_cert("USDZAR", "overnight_gap_decay", {}),
                     _cert("EURNOK", "clock_transition", {"label": "london_fix",
                                                          "timeframe": "M15"}))
        seen: list[str] = []
        total = len(M.build_plan(surv, _elig(tmp_path))[0])
        assert total == 10
        for _ in range(4):
            doc = _run(tmp_path, surv, budget_cells=3)
            assert doc["minted_this_pass"] <= 3
            seen.extend([""] * doc["minted_this_pass"])
        assert len(seen) == total                     # every planned cell reached over passes
        # a further pass mints nothing new: the registry already holds every cell
        doc = _run(tmp_path, surv, budget_cells=50)
        assert doc["minted_this_pass"] == 0
        assert doc["totals"]["skipped_duplicate_registry"] == total
        c = sqlite3.connect(str(tmp_path / "alpha_registry.sqlite"))
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("SELECT * FROM research_candidates")]
        c.close()
        assert len(rows) == total
        for r in rows:
            assert not M.is_exotic(r["symbol"])
            assert r["origin"] == "exotic_transplant"
            lin = json.loads(r["lineage_json"])
            assert lin["source_certificate"].startswith("external.")
            assert lin["source_symbol"] in ("USDZAR", "EURNOK")
            assert r["source_id"] == lin["source_certificate"]
        m15 = [r for r in rows if r["family"] == "clock_transition"]
        assert m15 and all(r["chart"] == "M15" for r in m15)
        assert all(json.loads(r["params_json"]) == {"label": "london_fix", "timeframe": "M15"}
                   for r in m15)
    finally:
        R.set_path(None)


def test_no_exotic_target_ever_across_every_family(tmp_path: Path) -> None:
    fams = ("formula", "carry", "macro_conditional", "overnight_gap_decay",
            "cross_asset_residual", "clock_transition", "spread_state")
    rows = []
    for sym in ("USDZAR", "EURNOK", "USDSEK"):
        for fam in fams:
            rows.append(_cert(sym, fam, {"expr": ["mul", "usd", "oil"], "input_symbol": sym},
                              tag=f"{sym}{fam}"))
    plan, _ = M.build_plan(_surv(*rows), _elig(tmp_path))
    assert plan
    for p in plan:
        assert not M.is_exotic(p["symbol"])
        assert p["symbol"] in _elig(tmp_path)
        assert p["cell_id"] == docket_cell_id(p)


def test_dry_run_writes_no_cursor(tmp_path: Path) -> None:
    _run(tmp_path, _surv(_cert("USDZAR", "overnight_gap_decay", {})), dry_run=True)
    assert not (tmp_path / "cursor.json").exists()


def test_leg_is_on_core_with_a_declared_budget_the_kill_margin_can_see() -> None:
    """Pinned placement (Audit HOLD 8044d9b16): the leg stays on the core clock, and it declares a
    cycle budget >= its own --budget-s 300 + 15%, so the core plan's kill margin yields it rather
    than starting it into a pass that would overrun the task limit."""
    import hourly_cycle as hc

    assert "exotic_transplant" in hc.CORE_LEGS
    assert hc.LEG_BUDGET_SEC.get("exotic_transplant", 0) >= 345
