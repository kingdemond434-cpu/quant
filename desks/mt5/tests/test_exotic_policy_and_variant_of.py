"""SF1 + SF2 (Auditor follow-ups to docket-supply-100k, 2026-11-24).

SF2: the desk has ONE exotic definition, `universe_policy.is_exotic_symbol` -- the registry class
OR an FX pair of two known fiat legs with one outside the eight majors -- and breadth_sweep's
`is_exotic` delegates to it, so a NOK/SEK pair the registry files as plain forex is still dropped.

SF1: every row the variant walk mints at rank > 0 carries `variant_of`, the judge's docket
identity (`frontier_identity.docket_cell_id`) of its rank-0 sibling: same family, symbol and chart
at the family's own defaults. Rank-0 rows carry none.

Every input is synthetic or redirected into `tmp_path`; nothing here reads or writes box state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.frontier_identity import docket_cell_id  # noqa: E402

from research import breadth_sweep as bs  # noqa: E402
from research import universe_policy as up  # noqa: E402

EXOTIC = ("USDNOK", "EURSEK", "NOKSEK", "USDTRY", "USDMXN", "USDCNH", "USDHKD", "USDSGD")
NOT_EXOTIC = ("EURUSD", "AUDNZD", "BTCUSD", "ETHUSD", "XAUUSD", "XAGUSD", "US500", "USOIL",
              "USTEC")


@pytest.fixture
def plain_forex_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every FX symbol filed as plain 'Forex' -- the case the class name alone misses."""
    rows = {s: {"asset_class": "Forex"} for s in (*EXOTIC, "EURUSD", "AUDNZD", "GBPUSD")}
    rows.update({"BTCUSD": {"asset_class": "Crypto"}, "ETHUSD": {"asset_class": "Crypto"},
                 "XAUUSD": {"asset_class": "Commodities"}, "XAGUSD": {"asset_class": "Commodities"},
                 "US500": {"asset_class": "Indices"}, "USTEC": {"asset_class": "Indices"},
                 "USOIL": {"asset_class": "Commodities"}, "AAPL": {"asset_class": "Equities"}})
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", uni)
    up._registry.cache_clear()
    yield uni
    up._registry.cache_clear()


@pytest.mark.parametrize("sym", EXOTIC)
def test_exotics_read_exotic_by_their_legs(sym: str) -> None:
    assert up.is_exotic_symbol(sym, asset_class="Forex")
    assert up.is_exotic_symbol(sym.lower(), asset_class="")


@pytest.mark.parametrize("sym", NOT_EXOTIC)
def test_majors_crypto_metals_indices_energy_never_read_exotic(sym: str) -> None:
    assert not up.is_exotic_symbol(sym, asset_class="")


def test_the_registry_class_alone_is_enough() -> None:
    assert up.is_exotic_symbol("ZZZZZZ", asset_class="Forex Exotics")
    assert up.is_exotic_symbol("EURUSD", asset_class="fx exotic")


def test_no_class_given_reads_the_registry(plain_forex_registry: Path) -> None:
    for s in EXOTIC:
        assert up.is_exotic_symbol(s), s
    for s in NOT_EXOTIC:
        assert not up.is_exotic_symbol(s), s


def test_breadth_sweep_delegates_and_drops_nok_sek_filed_as_plain_forex(
        plain_forex_registry: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for s in (*EXOTIC, *NOT_EXOTIC):
        assert bs.is_exotic(s) == up.is_exotic_symbol(s), s
    assert bs.is_exotic("USDNOK") and bs.is_exotic("EURSEK") and bs.is_exotic("NOKSEK")
    bars = tmp_path / "bars"
    bars.mkdir()
    for s in ("EURUSD", "GBPUSD", "USDNOK", "EURSEK", "NOKSEK", "XAUUSD", "BTCUSD"):
        (bars / f"{s}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(bs, "UNIVERSE", bars)
    monkeypatch.setattr(bs, "CORE", ("EURUSD", "GBPUSD", "USDNOK", "EURSEK", "XAUUSD"))
    syms = bs._with_bars()
    assert "EURUSD" in syms and "XAUUSD" in syms
    assert not {"USDNOK", "EURSEK", "NOKSEK"} & set(syms)
    pairs = bs.class_pairs(["EURUSD", "GBPUSD", "USDNOK", "EURSEK", "NOKSEK"])
    assert pairs and not [p for p in pairs if {"USDNOK", "EURSEK", "NOKSEK"} & set(p)]


# ------------------------------------------------------------------ SF1: variant_of
def _key(r: dict) -> str:
    return json.dumps([r.get("symbol"), r.get("family"), r.get("params") or {}],
                      sort_keys=True, default=str)


def test_every_variant_row_names_its_default_params_sibling(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "_charts_for", lambda sym: ["M15", "H1", "D1"])
    fams = ["trend_ma_cross", "mean_reversion_rsi"]
    w = bs.VariantWalk(fams, ["EURUSD", "XAUUSD"], cursor=0, budget_s=120, per_run=10**9)
    rows = w(set(), 10**9, _key)
    variants = [r for r in rows if r["variant_rank"] > 0]
    defaults = [r for r in rows if r["variant_rank"] == 0]
    assert variants and defaults
    for r in defaults:
        assert "variant_of" not in r, r
    clusters: dict[str, set[str]] = {}
    for r in variants:
        tf = (r["params"] or {}).get("timeframe", "H1")
        sib = {"symbol": r["symbol"], "family": r["family"],
               "params": {} if tf == "H1" else {"timeframe": tf}}
        assert r["variant_of"] == docket_cell_id(sib), r
        assert r["variant_of"] != docket_cell_id(r), "a variant is never its own sibling"
        clusters.setdefault(r["variant_of"], set()).add(docket_cell_id(r))
    # One cluster per (family, symbol, chart), each holding many distinct variant cells.
    assert len(clusters) == len({(r["family"], r["symbol"],
                                  (r["params"] or {}).get("timeframe", "H1")) for r in variants})
    assert min(len(v) for v in clusters.values()) > 1
