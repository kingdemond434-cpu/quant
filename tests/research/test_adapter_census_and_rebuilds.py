"""The 2026-11-13 adapter audit, pinned: no adapter is a silent import probe; the rebuilt engines
donate EXACT family recipes; the data adapters are DataHub contracts on a clock; the lean and
nautilus engines replay certificates under their own fill semantics; the census measures it all
and publishes exception type names only."""
from __future__ import annotations

import ast
import importlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from libs.research import adapter_kit as K
from libs.research import adapters as A

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REBUILT = ("qlib", "finrl", "rd_agent", "ml_quant_trading", "kronos", "ai_hedge_fund",
           "tradingagents", "quantagent", "autohedge", "alphaquanter", "atlas_gic",
           "autohypothesis", "inalpha", "nexquant", "ai_scientist", "alpha_search")
VERDICT = ("dexter", "finrobot", "fingpt", "vnpy", "arcticdb", "zvt", "dspy", "quantifact",
           "quantrocket")
DATA = ("akshare", "tushare", "openbb")


def _family_signatures() -> dict[str, set[str]]:
    tree = ast.parse((DESK / "mt5desk" / "families.py").read_text("utf-8"))
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name.startswith("family_"):
            out[n.name[len("family_"):]] = {a.arg for a in n.args.kwonlyargs}
    return out


def test_the_kit_recipes_name_each_familys_own_keywords() -> None:
    sigs = _family_signatures()
    for fam, kws in K.FAMILY_KWARGS.items():
        assert fam in A.FAMILIES
        assert set(kws) == sigs[fam], f"{fam}: the kit drifted from mt5desk/families.py"
    for kind in K.KINDS:
        fam, params = K.recipe(kind, window=30, horizon=10)
        assert fam in A.FAMILIES
        assert set(params) <= sigs[fam], (kind, set(params) - sigs[fam])


@pytest.mark.parametrize("name", REBUILT)
def test_every_rebuilt_adapter_runs_in_process_and_donates_exact_recipes(name: str) -> None:
    mod = importlib.import_module(f"libs.research.adapters.{name}")
    assert getattr(mod, "RUNS_WITHOUT_LIBRARY", False)
    assert mod.CENSUS_CLASS == "b"
    sigs = _family_signatures()
    donated = 0
    for seed in (1, 3, 4, 7):
        bundle = A.synthetic_bundle(seed=seed, n=1600, budget_s=30,
                                    symbols=("XAUUSD", "EURUSD", "USDJPY"))
        pkt = mod.run(bundle)
        assert pkt.trials_charged > 0, f"{name} charged no trials"
        assert pkt.representations, f"{name} left no representation of what it measured"
        assert "api_surface" not in {str(r.get("kind")) for r in pkt.research_methods}
        for c in pkt.candidates:
            params = c["evidence"]["parameters"]
            assert c["family"] in A.FAMILIES
            assert set(params) <= sigs[c["family"]], (name, c["family"], params)
            donated += 1
    assert donated, f"{name} donated nothing on four planted bundles"


def test_kind_signals_never_read_a_later_bar() -> None:
    bundle = A.synthetic_bundle(seed=2, n=900)
    f = bundle.frames("H1")[0]
    a = K.arrays(f)
    cut = 600
    b = {k: v.copy() for k, v in a.items()}
    for k in ("o", "h", "l", "c", "v"):
        b[k][cut:] = b[k][cut:] * 1.7 + 3.0
    for kind in K.KINDS:
        if kind == "squeeze":
            continue  # its tercile is a whole-frame quantile by design; scored, never donated raw
        s1, s2 = K.kind_signal(kind, a, 24), K.kind_signal(kind, b, 24)
        assert np.array_equal(s1[:cut], s2[:cut]), kind


@pytest.mark.parametrize("name", VERDICT)
def test_every_cannot_work_adapter_names_its_measured_reason(name: str,
                                                            monkeypatch: Any) -> None:
    mod = importlib.import_module(f"libs.research.adapters.{name}")
    assert mod.CENSUS_CLASS == "c"
    assert len(mod.VERDICT_REASON) > 40
    assert any(w in mod.VERDICT_REASON for w in ("LICENCE", "UNINSTALLABLE", "TERMS",
                                                 "NON-MT5", "LLM"))
    for lib in (None, object()):
        monkeypatch.setattr(A, "library", lambda _n, lib=lib: lib)
        pkt = mod.run(A.synthetic_bundle(seed=1, n=400, budget_s=2))
        assert A.is_unmeasured(pkt)
        assert "CANNOT_WORK_HERE" in str(pkt.research_methods[0]["why"])


def test_data_adapters_are_contracts_on_the_desk_hub_with_known_clocks() -> None:
    from libs.data.datahub import desk_hub
    from libs.data.datahub_adapters import CONTRACTS, RESERVED_PREFIXES
    hub = desk_hub()
    names = set(hub.contracts())
    for c in CONTRACTS:
        assert c.name in names
        assert not c.name.startswith(RESERVED_PREFIXES), c.name
    leg_src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for name in DATA:
        mod = importlib.import_module(f"libs.research.adapters.{name}")
        assert mod.CENSUS_CLASS == "a" and mod.CONTRACTS
        assert set(mod.CONTRACTS) <= names
        assert f'_costed("{mod.CLOCK.split(":", 1)[1]}"' in leg_src


def test_the_census_finds_no_probe_only_adapter() -> None:
    from research import adapter_census as C
    rows = C.adapter_rows()
    assert len(rows) >= 140
    assert not [r["name"] for r in rows if r["class"] == "PROBE_ONLY"]
    assert not [r["name"] for r in rows if r["class"] == "c" and not r["reason"]]
    assert {r["class"] for r in rows} <= {"a", "b", "c"}


def test_the_census_counts_cells_and_verdicts_from_the_registry(tmp_path: Path) -> None:
    from research import adapter_census as C
    db = tmp_path / "reg.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE research_candidates (id TEXT, generator TEXT, params_json TEXT, "
                "judged_at TEXT, survived INTEGER)")
    rows = [("1", "sandbox:qlib", "{}", "2026-11-13", 0),
            ("2", "sandbox:qlib", "{}", None, None),
            ("3", "sandbox:cell:coevolution_cell", "{}", "2026-11-13", 1),
            ("4", "free_stack", '{"source": "fs_akshare", "signal": "x"}', "2026-11-13", 0),
            ("5", "adapter_data", '{"source": "oecd_cli_usa", "signal": "cli"}', None, 0)]
    con.executemany("INSERT INTO research_candidates VALUES (?,?,?,?,?)", rows)
    con.commit()
    con.close()
    doc = C.build(registry_path=db)
    by = {r["name"]: r for r in doc["rows"]}
    assert (by["qlib"]["cells_donated"], by["qlib"]["judged"]) == (2, 1)
    assert by["alphagen"]["cells_donated"] == 1 and by["alphagen"]["survived"] == 1
    assert by["akshare"]["cells_donated"] == 1 and by["akshare"]["judged"] == 1
    assert by["openbb"]["cells_donated"] == 1
    assert by["dexter"]["class"] == "c" and by["dexter"]["reason"]
    assert doc["status"] == "MEASURED" and doc["probe_only"] == []


def test_an_absent_registry_is_unmeasured_never_zero(tmp_path: Path) -> None:
    from research import adapter_census as C
    doc = C.build(registry_path=tmp_path / "absent.sqlite")
    assert doc["registry"]["status"] == "UNMEASURED"
    assert all(r["cells_donated"] == "UNMEASURED" for r in doc["rows"])


# ------------------------------------------------------------------ adapter_data (OECD CLI)

def _csv(values: dict[str, float]) -> str:
    return "DATAFLOW,REF_AREA,FREQ,TIME_PERIOD,OBS_VALUE\n" + "".join(
        f"X,{k.split('|')[0]},M,{k.split('|')[1]},{v}\n" for k, v in values.items())


def _series(eco: str, n: int, bump: float = 0.0) -> dict[str, float]:
    out = {}
    for i in range(n):
        y, m = 2018 + i // 12, i % 12 + 1
        out[f"{eco}|{y}-{m:02d}"] = 100.0 + 0.1 * np.sin(i / 3) + 0.01 * i + bump
    return out


def test_adapter_data_keeps_the_first_vintage_and_mints_each_cell_once(tmp_path: Path) -> None:
    from research import adapter_data as AD
    body = {"text": _csv(_series("USA", 60))}

    def get(url: str) -> str:
        return "User-agent: *\nAllow: /\n" if url.endswith("robots.txt") else body["text"]

    got: list[dict[str, Any]] = []

    def enq(**kw: Any) -> tuple[str, bool]:
        got.append(kw)
        return "id", True

    kw = {"get": get, "enqueue": enq, "state_path": tmp_path / "s.json", "series_dir": tmp_path,
          "universe": frozenset({"US500", "XAUUSD"})}
    d1 = AD.build(**kw)
    assert d1["access"]["status"] == "FETCHED" and d1["access"]["backfill"] == 1
    assert d1["series"] == ["oecd_cli_usa"]
    n1 = d1["cells"]["cells_minted_this_pass"]
    assert n1 > 0 and all(g["family"] == "exogenous_conditioner" for g in got)
    assert {g["symbol"] for g in got} <= {"US500", "XAUUSD"}
    frame = pd.read_parquet(tmp_path / "oecd_cli_usa.parquet")
    first = frame["available_time"].iloc[0]
    assert pd.Timestamp(first) > pd.Timestamp("2018-01-31", tz="UTC") + pd.Timedelta(days=44)
    # a revised history is counted, never written over the first vintage
    state = json.loads((tmp_path / "s.json").read_text())
    state["last_success_at"] = "2000-01-01T00:00:00+00:00"
    (tmp_path / "s.json").write_text(json.dumps(state))
    body["text"] = _csv(_series("USA", 61, bump=5.0))
    d2 = AD.build(**kw)
    assert d2["access"]["revised_not_written"] == 60 and d2["access"]["new"] == 1
    held = json.loads((tmp_path / "s.json").read_text())["obs"]["USA"]
    assert held["2018-01"]["value"] < 101.0
    newest = held["2023-01"]
    assert newest["available_time"] >= newest["first_seen"][:19]
    assert d2["cells"]["cells_minted_this_pass"] == 0 or len(got) == n1 + d2["cells"][
        "cells_minted_this_pass"]


def test_adapter_data_obeys_robots_and_hard_stops_and_publishes_type_names(
        tmp_path: Path) -> None:
    from research import adapter_data as AD
    calls: list[str] = []

    def disallow(url: str) -> str:
        calls.append(url)
        return "User-agent: *\nDisallow: /\n"

    d = AD.build(get=disallow, enqueue=None, state_path=tmp_path / "a.json",
                 series_dir=tmp_path, universe=frozenset())
    assert d["access"]["status"] == "ROBOTS_DISALLOW"
    assert all(c.endswith("robots.txt") for c in calls)

    def refuse(url: str) -> str:
        if url.endswith("robots.txt"):
            return ""
        raise AD.HardStop(403)

    d = AD.build(get=refuse, enqueue=None, state_path=tmp_path / "b.json", series_dir=tmp_path,
                 universe=frozenset())
    assert d["access"]["status"] == "HARD_STOP"
    d = AD.build(get=refuse, enqueue=None, state_path=tmp_path / "b.json", series_dir=tmp_path,
                 universe=frozenset())
    assert d["access"]["status"] == "HARD_STOP"   # persisted: never retried by this leg

    def boom(url: str) -> str:
        if url.endswith("robots.txt"):
            return ""
        raise ValueError("secret token=abc at C:\\opt\\quant\\x")

    d = AD.build(get=boom, enqueue=None, state_path=tmp_path / "c.json", series_dir=tmp_path,
                 universe=frozenset())
    text = json.dumps(d)
    assert d["access"] == {"url_host": "sdmx.oecd.org", "status": "UNMEASURED",
                           "error_type": "ValueError"}
    assert "token" not in text and "opt" not in text


# ------------------------------------------------------------------ engine replicas

def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    ix = pd.date_range(datetime(2026, 1, 5, tzinfo=UTC), periods=len(rows), freq="h")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=ix)


META = {"spread_pts": 0.0, "tick_size": 0.01, "contract_size": 1.0, "tick_value": 0.01,
        "swap_long": 0.0, "swap_short": 0.0}


def test_lean_gap_fills_a_gapped_stop_at_the_open_where_the_contract_fills_at_the_stop(
) -> None:
    from libs.validation import engine_replicas as ER
    from libs.validation import independent_replica as rep
    df = _bars([(100, 100.5, 99.5, 100), (100, 100.5, 99.8, 100.2), (100.2, 100.4, 99.9, 100),
                (97.0, 97.5, 96.5, 97.0), (97, 97.5, 96.8, 97.2), (97.2, 97.4, 97.0, 97.1)])
    sig = rep.Sig(df.index[0], 1, stop=99.0, target=103.0, ttl=4)
    base = rep.simulate(df, [sig], META)
    lean = ER.simulate(df, [sig], META, "lean_gap")
    assert base[0].exit == 99.0 and base[0].reason == "stop"
    assert lean[0].exit == 97.0 and lean[0].reason == "stop_gap"
    assert lean[0].r < base[0].r


def test_nautilus_path_resolves_a_two_sided_bar_by_the_nearer_extreme() -> None:
    from libs.validation import engine_replicas as ER
    from libs.validation import independent_replica as rep
    # bar 2 touches both: open 100.1 is nearer the high (101.2) than the low (98.8)
    df = _bars([(100, 100.2, 99.8, 100), (100, 100.3, 99.9, 100.1), (100.1, 101.2, 98.8, 100),
                (100, 100.1, 99.9, 100)])
    sig = rep.Sig(df.index[0], 1, stop=99.0, target=101.0, ttl=3)
    assert rep.simulate(df, [sig], META)[0].reason == "stop"
    nt = ER.simulate(df, [sig], META, "nautilus_path")
    assert nt[0].reason == "target" and nt[0].exit == 101.0
    out = ER.replay(df, [sig], META)
    assert out["nautilus_path"]["delta_sum_r"] > 0
    assert out["lean_gap"]["delta_sum_r"] == 0


def test_the_engine_replicas_import_nothing_from_the_original_implementation() -> None:
    tree = ast.parse((ROOT / "libs" / "validation" / "engine_replicas.py").read_text("utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mod = (n.module or "") if isinstance(n, ast.ImportFrom) else n.names[0].name
            assert not mod.startswith(("mt5desk", "research", "scripts", "desks")), mod


def test_engine_replicas_summary_counts_and_never_reports_free_text() -> None:
    from research import engine_replicas as E
    rows = [{"cell": "a", "status": "MEASURED", "promoted": True,
             "lean_gap": {"delta_sum_r": -1.0}, "nautilus_path": {"delta_sum_r": 0.5}},
            {"cell": "b", "status": "UNSUPPORTED", "promoted": False, "why": "x"}]
    doc = E.summarise(rows)
    assert doc["engines"]["lean_gap"]["flattered_by_contract"] == 1
    assert doc["engines"]["nautilus_path"]["penalised_by_contract"] == 1
    assert doc["tally"] == {"MEASURED": 1, "UNSUPPORTED": 1}
    bad = E.replay_one("k", {}, {}, spec_of=lambda _r: (_ for _ in ()).throw(
        OSError("C:\\opt\\quant\\secret")))
    assert bad["why"] == "certified_spec OSError"


# ------------------------------------------------------------------ wiring

def test_the_three_organs_are_hourly_legs_with_a_layer_and_a_department() -> None:
    from libs.research import layers
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("adapter_data", "engine_replicas", "adapter_census"):
        assert f'_costed("{leg}"' in src
        assert leg in layers.LEG_LAYER
        assert f'"{leg}": ' in src.split("LEG_BUDGET_SEC")[1].split("}")[0]
    assert layers.unassigned() == []


def test_the_roster_carries_each_adapters_census_class(tmp_path: Path) -> None:
    from research import sandbox_roster as SR
    census = tmp_path / "census.json"
    census.write_text(json.dumps({"rows": [{"name": "dexter", "class": "c",
                                            "reason": "LLM-ONLY test", "clock": ""}]}))
    doc = SR.build(state_path=tmp_path / "s.json", report_path=tmp_path / "r.json",
                   ledger_path=tmp_path / "l.json", fed_state_path=tmp_path / "f.json",
                   census_path=census)
    rows = {r["system_id"]: r for r in doc["rows"]}
    assert rows["dexter"]["census_class"] == "c"
    assert rows["qlib"]["census_class"] == "UNMEASURED"
