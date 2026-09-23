"""A card that spawns the WRONG child is worse than a card that spawns none.

Every child this organ queues spends a trial, and it does it under the authority of a cell that
already works -- the shape of claim nobody re-checks. So these pin the properties that make a
child a MEASUREMENT of its parent's mechanism rather than a sweep wearing its name, and each one
is a mistake the build could plausibly have made:

  * THE TRIAL FAMILY IS THE CARD. If a child carried its own family the desk would be paying a
    fresh family-wise error charge for every coordinate of one already-proven mechanism, which is
    precisely the multiplicity leak `universe_policy` exists to stop.
  * COMPATIBILITY PRUNES. A session-window mechanism never takes D1 (one bar a day cannot resolve
    an eight-hour window), a date-anchored mechanism gets calendar variants and no session child,
    and a residual form is built only for a family whose observable is the price level.
  * THE TWO-LANE MANDATE ON EVERY AXIS. A single-name equity may not appear as a child, as a
    residual factor, as a cross-asset proxy or as a card.
  * A KNOB THE FAMILY DOES NOT HAVE IS A REFUSAL. `normalize_grid` filters a cell's params to the
    signature, so a regime param on a family with no regime knob is deleted downstream and the
    child executes identically to its parent while holding its own registry row.
  * THE SAME RULE TWICE IS ONE CANDIDATE. Content-hash dedupe, against the parent as well as
    against every sibling.
  * THE BUDGET AND THE CAP MUST SAY SO. A card not walked is UNMEASURED, never covered.

The synthetic desk is entirely on tmp_path: an eight-instrument registry, bar files that exist or
do not, six toy families with real desk names (so the mechanism table is the desk's own), and a
registry file created fresh with no backup to restore from.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

mce = pytest.importorskip("research.moat_card_explosion", reason="the organ ships with the desk")
ar = pytest.importorskip("research.axis_registry")
reg = pytest.importorskip("libs.moat.registry")

#: Eight instruments, four classes, one single-name equity that must never be proposed anywhere.
REGISTRY: dict[str, dict[str, Any]] = {
    "XAUUSD": {"asset_class": "Commodities", "bars": 9000},
    "XAGUSD": {"asset_class": "Commodities", "bars": 8000},
    "XPTUSD": {"asset_class": "Commodities", "bars": 7000},
    "EURUSD": {"asset_class": "Forex", "bars": 9000},
    "GBPUSD": {"asset_class": "Forex", "bars": 8000},
    "USDX": {"asset_class": "Indices", "bars": 6000},
    "US500": {"asset_class": "Indices", "bars": 6000},
    "Apple": {"asset_class": "Equities", "bars": 9000},
}
#: Which charts have bars ON DISK. XPTUSD has no H4 on purpose: a chart with no bars is
#: UNMEASURED and must be refused rather than emitted as a cell that cannot be run.
BARS: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("M5", "M15", "H1", "H4", "D1"), "XAGUSD": ("M15", "H1", "H4", "D1"),
    "XPTUSD": ("H1", "D1"), "EURUSD": ("H1", "H4", "D1"), "GBPUSD": ("H1",),
    "USDX": ("H1", "H4"), "US500": ("H1", "H4"), "Apple": ("H1", "H4", "D1"),
}
EQUITIES = {"APPLE"}


# Toy constructors with the desk's real family NAMES, so `classify_family` returns the desk's own
# mechanism and the compatibility table under test is the real one. The signatures are what
# `knobs()` reads, so each one declares exactly the knobs its axis needs.
def f_asia(df: Any, *, ttl_bars: int = 12, rr: float = 1.5) -> list[Any]:
    return []


def f_trend(df: Any, *, ttl_bars: int = 12, fast_ema: int = 12, slow_ema: int = 50) -> list[Any]:
    return []


def f_tom(df: Any, *, days_before: int = 2, days_after: int = 3, ttl_bars: int = 48,
          side_bias: int = 1) -> list[Any]:
    return []


def f_level(df: Any, *, ttl_bars: int = 12, vol_filter: str = "all", wait_bars: int = 12,
            trail_k: float = 0.0) -> list[Any]:
    return []


def f_resid(df: Any, *, factor_symbols: Any = None, ttl_bars: int = 72,
            side_mode: str = "revert") -> list[Any]:
    return []


def f_corr(df: Any, *, peer_symbol: Any = None, ttl_bars: int = 48) -> list[Any]:
    return []


def f_ens(df: Any, *, members: Any = None, threshold: float = 0.5,
          hold_bars: int = 12) -> list[Any]:
    return []


FAMILIES: dict[str, Any] = {"asia_momentum": f_asia, "trend_ma_cross": f_trend,
                            "turn_of_month": f_tom, "level_breakout": f_level,
                            "cross_asset_residual": f_resid, "correlation_regime": f_corr,
                            "ensemble": f_ens}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A whole desk on tmp_path: a fresh registry with no backup, a universe, bars, families."""
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps(REGISTRY), "utf-8")
    for sym, charts in BARS.items():
        for tf in charts:
            (uni / f"{sym}_{tf}.parquet").write_bytes(b"")
    import research.universe_policy as up
    monkeypatch.setattr(up, "UNIVERSE", uni / "universe.json")
    up._registry.cache_clear()
    monkeypatch.setattr(ar, "UNIVERSE", uni / "universe.json")
    monkeypatch.setattr(mce, "UNIVERSE", uni)
    monkeypatch.setattr(mce, "_REGISTRY", dict(FAMILIES))
    monkeypatch.setattr(mce, "OUT", tmp_path / "reports" / "MOAT_CARD_EXPLOSION.json")
    monkeypatch.setattr(reg, "BACKUP", tmp_path / "no_backup")
    reg.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    reg.set_path(None)
    up._registry.cache_clear()


def card(card_id: str, symbol: str, family: str, *, status: str = "live",
         params: dict[str, Any] | None = None, chart: str = "H1") -> None:
    reg.upsert_card(card_id, name=card_id, market=symbol, category="sleeve",
                    status=status, symbol=symbol, family=family,
                    params_json=dict(params or {}), chart=chart, lane="live")


def axes_of(rows: list[dict[str, Any]]) -> set[str]:
    return {r["axis"] for r in rows}


def symbols_of(rows: list[dict[str, Any]]) -> set[str]:
    return {r["spec"]["symbol"] for r in rows}


# ------------------------------------------------------------------ the axes
def test_a_level_family_gets_a_child_on_every_compatible_axis(desk: Any) -> None:
    """The trend card is level-based and not session-bound: asset, chart, session, horizon,
    residual and cross-asset all mean something for it, and `calendar` does not."""
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    got = axes_of(kept)
    assert {"asset", "chart", "session", "horizon", "residual", "cross_asset"} <= got
    assert "calendar" not in got
    assert rep["n_generated"] == len(kept) > 0


def test_a_session_family_keeps_sessions_and_never_takes_d1(desk: Any) -> None:
    """One bar a day cannot resolve an eight-hour window, and the refusal is NAMED."""
    card("sleeve:asia", "XAUUSD", "asia_momentum", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    charts = {r["spec"]["chart"] for r in kept if r["axis"] == "chart"}
    assert charts and "D1" not in charts
    assert {r["spec"]["session"] for r in kept if r["axis"] == "session"} == {"asia", "london",
                                                                             "ny"}
    assert any(u["what"].startswith("D1 refused") for u in rep["unmeasured"])


def test_a_calendar_family_keeps_calendar_variants_and_gets_no_session_child(desk: Any) -> None:
    """A month-end flow is anchored to a DATE; the Asia window is a coordinate it does not have."""
    card("sleeve:tom", "XAUUSD", "turn_of_month", params={"days_before": 2, "ttl_bars": 48})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert "calendar" in axes_of(kept)
    assert "session" not in axes_of(kept)
    assert "session" in rep["by_card"][0]["pruned_axes"]
    knobs = {k for r in kept if r["axis"] == "calendar"
             for k in ("days_before", "days_after")
             if r["spec"]["params"].get(k) != {"days_before": 2}.get(k)}
    assert knobs


def test_residual_form_is_only_built_for_a_level_based_family(desk: Any) -> None:
    """A residual of a residual is a second beta fitted to the same noise."""
    card("cell:resid", "XAUUSD", "cross_asset_residual", status="certified",
         params={"factor_symbols": ["XAGUSD"], "ttl_bars": 72})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert "residual" not in axes_of(kept)
    assert "cross_asset" not in axes_of(kept)
    pruned = set(rep["by_card"][0]["pruned_axes"])
    assert {"residual", "cross_asset"} <= pruned


def test_no_equity_ever_appears_as_a_child_a_factor_or_a_proxy(desk: Any) -> None:
    """The two-lane mandate on EVERY axis, not only the instrument one."""
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    _rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert not symbols_of(kept) & EQUITIES
    named = {str(v).upper() for r in kept for v in r["spec"]["params"].values()
             if isinstance(v, str)}
    named |= {str(x).upper() for r in kept for v in r["spec"]["params"].values()
              if isinstance(v, list) for x in v if isinstance(x, str)}
    assert not named & EQUITIES


def test_an_equity_card_spawns_nothing_and_is_named(desk: Any) -> None:
    """Refusing only the children would be worse than useless: the session, horizon and exit axes
    keep the card's own symbol, so every one of those is an equity cell the intake turns away
    after the slot has been spent on it."""
    card("sleeve:apple", "Apple", "trend_ma_cross", params={"ttl_bars": 12})
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert [r["card"] for r in rep["by_card"]] == ["sleeve:trend"]
    assert not symbols_of(kept) & EQUITIES
    refusal = next(u for u in rep["unmeasured"]
                   if u["what"] == "cards refused by the two-lane mandate")
    assert refusal["symbols"] == ["APPLE"] and "never hunted" in refusal["why"]


def test_a_regime_child_exists_only_where_the_family_exposes_the_knob(desk: Any) -> None:
    """`normalize_grid` strips a param the signature has no name for, so a regime child on a
    family with no regime knob would execute identically to its parent."""
    card("sleeve:level", "XAUUSD", "level_breakout", params={"ttl_bars": 12})
    _rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    regimes = {r["regime"] for r in kept if r["axis"] == "regime"}
    assert regimes == {"high_vol", "low_vol"}
    assert {r["spec"]["params"]["vol_filter"] for r in kept if r["axis"] == "regime"} == {"high",
                                                                                          "low"}


def test_a_family_with_no_regime_knob_gets_a_named_refusal(desk: Any) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert "regime" not in axes_of(kept)
    refusal = next(u for u in rep["unmeasured"] if u["what"] == "no regime knob on trend_ma_cross")
    assert "normalize_grid" in refusal["why"]


def test_the_horizon_axis_halves_and_doubles_the_cards_own_hold(desk: Any) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    _rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert {r["spec"]["params"]["ttl_bars"] for r in kept if r["axis"] == "horizon"} == {6, 24}


def test_the_inverse_axis_flips_the_familys_own_direction_knob(desk: Any) -> None:
    card("sleeve:tom", "XAUUSD", "turn_of_month", params={"side_bias": 1, "ttl_bars": 48})
    _rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert [r["spec"]["params"]["side_bias"] for r in kept if r["axis"] == "inverse"] == [-1]


def test_mechanism_combination_only_where_the_ontology_says_they_interact(desk: Any) -> None:
    """`session_handover` and `breakout_liquidity` interact; `calendar_seasonality` does not pair
    with either, so no ensemble is built for it."""
    card("sleeve:asia", "XAUUSD", "asia_momentum", params={"ttl_bars": 12})
    card("sleeve:level", "XAGUSD", "level_breakout", params={"ttl_bars": 12})
    card("sleeve:tom", "EURUSD", "turn_of_month", params={"ttl_bars": 48})
    _rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    combos = [r for r in kept if r["axis"] == "mechanism"]
    assert combos and all(r["spec"]["family"] == "ensemble" for r in combos)
    assert {r["card"] for r in combos} == {"sleeve:asia", "sleeve:level"}
    members = combos[0]["spec"]["params"]["members"]
    assert len(members) == 2 and {m["family"] for m in members} == {"asia_momentum",
                                                                    "level_breakout"}


# ------------------------------------------------------------------ the accounting
def test_trial_family_is_the_card_id_on_every_child(desk: Any) -> None:
    """One family-wise error budget per card, inherited. This is the whole point of the organ."""
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    card("cell:level", "XAGUSD", "level_breakout", status="certified", params={"ttl_bars": 12})
    _rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    assert kept
    assert all(r["trial_family"] == r["card"] for r in kept)
    assert all(r["parent_ids"] == [r["card"]] for r in kept)
    assert {r["origin"] for r in kept} == {"MOAT"}
    assert all(r["generator"] == f"card_explosion:{r['axis']}" for r in kept)


def test_the_same_rule_twice_is_one_candidate(desk: Any) -> None:
    """Two sibling cards each propose the other's exact spec on the asset axis; the second is a
    collision, not a second candidate, and the parent's own hash is seeded so a child cannot
    collapse back onto its card."""
    card("sleeve:a", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    card("sleeve:b", "XAGUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=40, budget_s=60.0, dry_run=True)
    hashes = [r["hash"] for r in kept]
    assert len(hashes) == len(set(hashes))
    assert rep["n_deduped"] > 0
    # sleeve:b's asset axis proposes sleeve:a's own spec (the card's hash is seeded before
    # it is walked) and the XPTUSD sibling sleeve:a already generated. Both are collisions,
    # so the axis yields NOTHING new -- one rule, one candidate, whichever card reaches it.
    assert [r for r in kept if r["card"] == "sleeve:b" and r["axis"] == "asset"] == []
    assert {r["spec"]["symbol"] for r in kept
            if r["card"] == "sleeve:a" and r["axis"] == "asset"} == {"XAGUSD", "XPTUSD"}


def test_max_per_card_caps_and_spreads_across_axes(desk: Any) -> None:
    """The cap is round-robin: one rich axis may not eat a card's whole budget."""
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=3, budget_s=60.0, dry_run=True)
    assert len(kept) == 3 == rep["n_generated"]
    assert len(axes_of(kept)) == 3
    assert rep["by_card"][0]["possible"] > 3


def test_pick_is_round_robin_and_deduped() -> None:
    rows = {a: [{"axis": a, "hash": f"{a}{i}"} for i in range(4)]
            for a in ("asset", "chart", "session")}
    kept, collisions = mce.pick(rows, {"asset0"}, 4)
    assert [r["axis"] for r in kept] == ["chart", "session", "asset", "chart"]
    assert collisions >= 1


def test_live_cards_are_exploded_before_certified_cells(desk: Any) -> None:
    card("cell:certified", "EURUSD", "trend_ma_cross", status="certified",
         params={"ttl_bars": 12})
    card("sleeve:standby", "XAGUSD", "trend_ma_cross", status="standby", params={"ttl_bars": 12})
    card("sleeve:live", "XAUUSD", "trend_ma_cross", status="live", params={"ttl_bars": 12})
    rep, _kept = mce.build(max_per_card=2, budget_s=60.0, dry_run=True)
    assert [r["status"] for r in rep["by_card"]] == ["live", "standby", "certified"]


def test_retired_and_crypto_cards_are_excluded_and_counted(desk: Any) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross")
    reg.upsert_card("crypto::funding", name="crypto::funding", market="BINANCE-PERP",
                    category="sleeve", status="candidate", symbol="BTCUSD",
                    family="trend_ma_cross", params_json={}, chart="H1")
    reg.upsert_card("sleeve:old", name="old", market="XAUUSD", category="sleeve",
                    status="retired", symbol="XAUUSD", family="trend_ma_cross",
                    params_json={}, chart="H1")
    rep, _kept = mce.build(max_per_card=4, budget_s=60.0, dry_run=True)
    assert [r["card"] for r in rep["by_card"]] == ["sleeve:trend"]
    what = {u["what"] for u in rep["unmeasured"]}
    assert "retired cards excluded" in what and "crypto-exchange cards excluded" in what


def test_the_budget_stop_is_named_and_nothing_is_claimed_as_covered(desk: Any) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=40, budget_s=-1.0, dry_run=True)
    assert kept == [] and rep["budget_stopped"] is True
    stop = next(u for u in rep["unmeasured"] if u["what"] == "cards not exploded")
    assert stop["n"] == 1 and "UNMEASURED" in stop["why"]


# ------------------------------------------------------------------ the registry
def test_a_discovery_is_recorded_per_card_with_its_conversion_counters(desk: Any) -> None:
    """EXPANDED -> COMPILED -> QUEUED, with the cell counts that make conversion debt auditable."""
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    rep, kept = mce.build(max_per_card=5, budget_s=60.0, dry_run=False)
    rows = reg.discoveries(origin="MOAT")
    assert len(rows) == 1
    d = rows[0]
    assert d["source_type"] == "alpha_card" and d["source_id"] == "sleeve:trend"
    assert d["state"] == "QUEUED" and d["generator"] == "card_explosion"
    assert d["possible_cells"] >= d["generated_cells"] == len(kept) == 5
    assert d["compiled_cells"] == 5 and d["queued_cells"] == rep["n_queued"] == 5


def test_every_queued_candidate_carries_the_card_as_its_trial_family(desk: Any) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    _rep, kept = mce.build(max_per_card=4, budget_s=60.0, dry_run=False)
    cands = reg.candidates(origin="MOAT")
    assert len(cands) == len(kept) == 4
    assert {c["trial_family"] for c in cands} == {"sleeve:trend"}
    assert {c["origin"] for c in cands} == {"MOAT"}
    assert all(json.loads(c["parent_ids_json"]) == ["sleeve:trend"] for c in cands)
    assert {c["status"] for c in cands} == {"queued"}
    assert all(c["generator"].startswith("card_explosion:") for c in cands)


def test_the_card_to_cell_provenance_edge_is_written(desk: Any) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    _rep, kept = mce.build(max_per_card=3, budget_s=60.0, dry_run=False)
    edges = reg.descendants_of("card", "sleeve:trend")
    assert len(edges) >= len(kept)
    assert all(e["relation"].startswith("explosion:") for e in edges)


def test_a_dry_run_writes_no_report_queues_nothing_and_donates_nothing(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    sent: list[Any] = []
    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": 0})
    assert mce.main(["--dry-run", "--max-per-card", "4"]) == 0
    assert sent == []
    assert not mce.OUT.exists()
    assert reg.candidates(origin="MOAT") == []
    assert reg.discoveries(origin="MOAT") == []


def test_the_cli_writes_the_report_and_donates_exact_recipes(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    card("sleeve:trend", "XAUUSD", "trend_ma_cross", params={"ttl_bars": 12})
    sent: list[tuple[Any, Any]] = []
    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate",
                        lambda source, rows, **k: sent.append((source, rows, k)) or None)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(sent[0][1])})
    assert mce.main(["--max-per-card", "4"]) == 0
    doc = json.loads(mce.OUT.read_text("utf-8"))
    assert doc["n_cards"] == 1 and doc["n_generated"] == 4 and doc["n_queued"] == 4
    assert doc["rule"].startswith("one card produces hundreds of registered trials")
    assert set(doc["by_axis"]) == set(mce.AXES)
    source, rows, kwargs = sent[0]
    assert source == "card_explosion" and len(rows) == 4 and kwargs["tests_run"] == 1
    assert all(r["family"] in FAMILIES and isinstance(r["params"], dict) for r in rows)
    assert all(r["trial_family"] == "sleeve:trend" for r in rows)
    assert all(r["source"].startswith("card_explosion:") for r in rows)


def test_the_compatibility_table_is_declared_for_every_desk_mechanism() -> None:
    """A mechanism the table does not name would silently take the default axis set."""
    for _fam, (mech, _i, _s) in ar.FAMILY_TABLE.items():
        assert mech in mce.COMPATIBILITY, mech
    assert mce.COMPATIBILITY["calendar_seasonality"] >= {"calendar"}
    assert "session" not in mce.COMPATIBILITY["forced_flow"]
    assert "residual" in mce.COMPATIBILITY["trend_persistence"]
    assert "residual" not in mce.COMPATIBILITY["macro_release"]
    assert "cross_asset" not in mce.COMPATIBILITY["cross_market_lead"]
