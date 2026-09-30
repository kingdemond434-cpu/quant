"""cell_emitter: published strategy code -> family cells, tested on MARKED fixtures only.

Every file under tests/fixtures/cell_emitter is named in its MANIFEST as RECORDED_FIXTURE
(fetched verbatim, MIT-licensed vn.py) or SYNTHETIC_FIXTURE (desk-written in a ground's idiom).
Nothing here touches the network: the live route is exercised through a monkeypatched fetcher.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import cell_emitter as ce  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "cell_emitter"


def _manifest() -> dict[str, Any]:
    return json.loads((FIX / "MANIFEST.json").read_text("utf-8"))


def _grounds() -> dict[str, dict[str, Any]]:
    reg = json.loads(ce.SOURCES.read_text("utf-8"))
    return {g["name"]: g for g in reg["grounds"]}


def _read(name: str) -> str:
    return (FIX / name).read_text("utf-8")


def test_every_fixture_is_marked_and_hash_pinned() -> None:
    man = _manifest()
    assert "FIXTURE" in man["note"]
    names = {f["file"] for f in man["files"]}
    on_disk = {p.name for p in FIX.iterdir()
               if p.suffix in {".py", ".pine", ".mq5", ".mq4", ".mqh"}}
    assert names == on_disk, "a fixture file on disk is not declared in the MANIFEST"
    grounds = _grounds()
    for f in man["files"]:
        assert f["kind"] in {"RECORDED_FIXTURE", "SYNTHETIC_FIXTURE"}
        assert f["ground"] in grounds, f"fixture names an unregistered ground {f['ground']}"
        assert hashlib.sha256((FIX / f["file"]).read_bytes()).hexdigest() == f["sha256"]
        if f["kind"] == "RECORDED_FIXTURE":
            assert f["url"].startswith("https://") and "MIT" in f["license"]
        else:
            assert "SYNTHETIC FIXTURE" in _read(f["file"]).splitlines()[0]


def test_grounds_registry_is_data_and_every_route_is_known() -> None:
    reg = json.loads(ce.SOURCES.read_text("utf-8"))
    assert reg["grounds"], "the grounds registry is empty"
    for g in reg["grounds"]:
        assert g["route"] in {"github_repo", "gitee_repo", "github_code_search", "page_code"}
        assert g.get("default_instruments"), g["name"]
        if g.get("venue") == "crypto_exchange":
            assert all(ce._is_crypto(s) for s in g["default_instruments"]), g["name"]


def test_pine_ema_cross_is_an_exact_recipe() -> None:
    r = ce.parse_code(_read("synthetic_pine_ema_cross.pine"), "x.pine")
    assert r["language"] == "pinescript"
    assert r["map"]["family"] == "trend_ma_cross"
    assert r["map"]["params"] == {"fast_ema": 21, "slow_ema": 55}
    assert r["map"]["fidelity"] == "exact"


def test_mql_rsi_reads_inputs_and_orientation() -> None:
    r = ce.parse_code(_read("synthetic_mql5_rsi_reversion.mq5"), "x.mq5")
    assert r["language"] == "mql"
    assert r["map"]["family"] == "mean_reversion_rsi"
    assert r["map"]["params"] == {"rsi_n": 7, "oversold": 25, "overbought": 75}


def test_rsi_that_buys_strength_is_never_mean_reversion() -> None:
    """vn.py's ATR-RSI buys when RSI > 50 + rsi_entry: momentum. Mapping it to
    mean_reversion_rsi would hand the gauntlet the opposite rule."""
    r = ce.parse_code(_read("vnpy_vnpy_ctastrategy__atr_rsi_strategy.py"), "atr_rsi.py")
    assert r["map"]["family"] == "momentum_volgate"
    assert "MOMENTUM" in r["map"]["why"]


def test_vnpy_class_attributes_resolve_lookbacks() -> None:
    r = ce.parse_code(_read("vnpy_vnpy_ctastrategy__double_ma_strategy.py"), "double_ma.py")
    assert r["map"]["family"] == "trend_ma_cross"
    assert r["map"]["params"] == {"fast_ema": 10, "slow_ema": 20}
    assert r["map"]["fidelity"] == "analogue"            # SMA read, EMA family: said so
    boll = ce.parse_code(_read("vnpy_vnpy_ctastrategy__boll_channel_strategy.py"), "b.py")
    assert boll["map"]["family"] is None                  # a band BREAKOUT is not a band fade
    assert "BREAKOUT" in boll["map"]["why"] and "3.4" in boll["map"]["why"]
    turtle = ce.parse_code(_read("vnpy_vnpy_ctastrategy__turtle_signal_strategy.py"), "t.py")
    assert turtle["map"]["family"] == "level_breakout" and turtle["map"]["params"] is None


def test_symbol_table_does_not_read_one_line_into_the_next() -> None:
    tab = ce.symbol_table("    boll_window: int = 18\n    boll_dev: float = 3.4\n"
                          "    intra_trade_high: float = 0\n    rsi_entry: int = 16\n"
                          "    rsi_buy: float = 0\n    rsi_buy = 50 + rsi_entry\n")
    assert tab["boll_window"] == 18 and tab["boll_dev"] == 3.4
    assert "ra_trade_high" not in tab and tab["intra_trade_high"] == 0
    assert tab["rsi_buy"] == 66                          # the placeholder 0 is not the value


def test_unmapped_code_lands_as_a_familyless_hypothesis() -> None:
    g = _grounds()["backtrader samples"]
    uni = set(ce._universe())
    rows, _reading, _drops = ce.rows_for_file(_read("synthetic_backtrader_stoch.py"), "s.py", "",
                                            g, uni, fixture=True)
    assert len(rows) == 1 and rows[0]["kind"] == "hypothesis" and "family" not in rows[0]
    assert "stoch" in rows[0]["testable_claim"]


def test_crypto_exchange_ground_maps_only_onto_crypto_cfds() -> None:
    g = _grounds()["freqtrade strategies"]
    uni = set(ce._universe())
    rows, _, _ = ce.rows_for_file(_read("synthetic_freqtrade_ema.py"), "e.py", "", g, uni,
                                  fixture=True)
    assert rows and rows[0]["symbols"]
    assert all(ce._is_crypto(s) for s in rows[0]["symbols"])
    assert "ETHUSD" in rows[0]["symbols"] and rows[0]["instrument_basis"] == "named_in_code"
    # a default basket leaking a non-crypto symbol onto a crypto ground is dropped and counted
    leaky = {**g, "default_instruments": ["EURUSD", "BTCUSD"]}
    syms, _, drops = ce.map_instruments("no pair named", leaky, "trend_ma_cross", uni)
    assert syms == ["BTCUSD"] and drops["crypto_ground_non_crypto_cfd"] == 1


def test_venue_native_mechanism_is_dropped_and_counted() -> None:
    g = _grounds()["freqtrade strategies"]
    rows, _, drops = ce.rows_for_file(_read("synthetic_freqtrade_funding.py"), "f.py", "", g,
                                      set(ce._universe()), fixture=True)
    assert rows == [] and drops["crypto_venue_native_mechanism"] == 1


def test_share_cfds_only_reach_through_the_lane_law() -> None:
    import universe_policy as up
    uni = ce._universe()
    equity = next((s for s in uni if up.is_equity(s)), None)
    if equity is None:
        pytest.skip("no share CFD in this checkout's registry")
    g = {"name": "t", "default_instruments": [equity, "EURUSD"]}
    syms, _, drops = ce.map_instruments("", g, "trend_ma_cross", set(uni))
    assert syms == ["EURUSD"] and drops["lane_event"] == 1


def test_donated_rows_compile_through_the_compilers_own_doors() -> None:
    import miner_candidate_compiler as mcc
    uni_rows = ce._universe()
    uni = set(uni_rows)
    grounds = _grounds()
    seen: dict[str, str] = {}
    for f in _manifest()["files"]:
        rows, _, _ = ce.rows_for_file(_read(f["file"]), f["path"], f["url"],
                                      grounds[f["ground"]], uni, fixture=True)
        for r in rows:
            cands, disp = mcc.compile_row("cell_emitter", r, uni)
            seen[f["file"]] = disp
            if r["kind"] == "code_rule":
                assert disp == "EXACT_RECIPE" and cands
                assert all(c["params"] == r["params"] for c in cands)
            elif r.get("family"):
                assert disp == "STRUCTURED_HYPOTHESIS" and cands
            else:
                assert not cands and disp != "BANNED_FAMILY"
            assert all(c["family"] != "discovered" for c in cands)
    assert seen["synthetic_pine_ema_cross.pine"] == "EXACT_RECIPE"
    assert seen["vnpy_vnpy_ctastrategy__atr_rsi_strategy.py"] == "STRUCTURED_HYPOTHESIS"


def test_fixture_run_is_marked_and_donates_nothing(tmp_path: Path) -> None:
    doc = ce.run(fixtures=FIX, write=True, state_path=tmp_path / "state.json",
                 donate_dir=tmp_path / "donate", report_path=tmp_path / "CELL_EMITTER.json")
    assert doc["mode"] == "FIXTURE" and "NOT a live yield" in doc["fixture_note"]
    assert doc["donated_to"] is None and not (tmp_path / "donate").exists()
    assert not (tmp_path / "state.json").exists()
    vn = doc["per_source"]["vnpy CTA strategies"]
    assert vn["fetched"] == 6 and vn["donated"] == 6
    fq = doc["per_source"]["freqtrade strategies"]
    assert fq["dropped"] == {"crypto_venue_native_mechanism": 1}
    # a ground with no fixture reports UNMEASURED (None), never 0
    assert doc["per_source"]["TradingView open-source strategies"]["fetched"] is None
    assert doc["trial_census"]["n_raw"] == doc["yield"]["cells"]
    assert json.loads((tmp_path / "CELL_EMITTER.json").read_text())["mode"] == "FIXTURE"


def _fake_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """api.github.com answers 403 (as the recording container measured); raw serves fixtures."""
    by_name = {f["path"].rsplit("/", 1)[-1]: f["file"] for f in _manifest()["files"]}
    calls: list[str] = []

    def fake_get(url: str, *, accept: str = "", timeout: float = 20.0):
        calls.append(url)
        if "api.github.com" in url or "gitee.com" in url or "tradingview" in url:
            return 403, "", "HTTP 403"
        name = url.rsplit("/", 1)[-1]
        if url.startswith(ce.GITHUB_RAW) and name in by_name:
            return 200, _read(by_name[name]), ""
        return 404, "", "HTTP 404"

    monkeypatch.setattr(ce, "_get", fake_get)
    return calls


def test_live_route_falls_back_to_seeds_donates_and_advances_its_cursor(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_network(monkeypatch)
    kw = {"state_path": tmp_path / "state.json", "donate_dir": tmp_path / "donate",
          "report_path": tmp_path / "CELL_EMITTER.json"}
    doc = ce.run(write=True, **kw)
    assert doc["mode"] == "LIVE"
    vn = doc["per_source"]["vnpy CTA strategies"]
    assert vn["listing"] == "seed_paths" and "403" in vn["status"]
    assert vn["fetched"] == 6 and vn["donated"] == 6
    assert vn["dropped"] == {"fetch_404": 2}               # two seeds with no fixture
    assert doc["per_source"]["GitHub Pine strategy search"]["fetched"] is None
    files = list((tmp_path / "donate").glob("discoveries_cellemitter_*.json"))
    assert len(files) == 1
    rows = json.loads(files[0].read_text())
    assert rows and all(r["source"] == "cell_emitter" and r["code_copied"] is False
                        for r in rows)
    assert not any(r.get("fixture") for r in rows)
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["file_cursor"]["vnpy CTA strategies"] == 0   # 8 seeds, slice of 12 -> wraps
    assert st["seen"]
    # second pass: unchanged bytes are not re-donated
    doc2 = ce.run(write=True, **kw)
    assert doc2["per_source"]["vnpy CTA strategies"]["unchanged_skipped"] == 6
    assert doc2["per_source"]["vnpy CTA strategies"]["donated"] == 0


def test_budget_exhausted_grounds_are_unmeasured_not_zero(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_network(monkeypatch)
    doc = ce.run(budget_s=-1, write=False, state_path=tmp_path / "s.json",
                 donate_dir=tmp_path / "d", report_path=tmp_path / "r.json")
    assert doc["grounds_worked"] == 0
    assert all(st["fetched"] is None for st in doc["per_source"].values())
    assert doc["yield"]["fetched"] is None


def test_module_never_executes_what_it_reads() -> None:
    tree = ast.parse(Path(ce.__file__).read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"exec", "eval", "compile", "__import__"}
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
            assert not any(n in {"subprocess", "importlib", "runpy"} for n in names)


def test_the_leg_is_on_the_clock_with_a_layer_budget_and_department() -> None:
    from libs.research import layers
    assert layers.LEG_LAYER["cell_emitter"] == "information"
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("cell_emitter", cell_emitter)' in cycle
    assert '"research/cell_emitter.py", "--once"' in cycle
    import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["cell_emitter"] > 300
    assert hc.LEG_DEPARTMENT["cell_emitter"] == "intel"
