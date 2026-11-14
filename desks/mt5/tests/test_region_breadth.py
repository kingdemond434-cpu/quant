"""Region breadth (2026-11-03): the miners' symbol walks reach the dark regions -- TRY, ZAR, PLN,
MXN, CNH, INR, IDR, KRW ... wherever the broker's registry lists them -- by REGION read from the
registry, never a symbol list; single-name equities stay out of the statistical lanes; and the
per-region alt-data yield is published every pass with rule 23's RED flag."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_data_yield as ady  # noqa: E402
from research import universe_policy as up  # noqa: E402

#: A registry the tests own. The made-up exotic USDKZT and index KZX10 prove routing is read from
#: the registry's own fields: no code anywhere names them.
_REG = {
    "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
    "USDJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
    "EURGBP": {"asset_class": "Forex", "currency_profit": "GBP"},
    "USDTRY": {"asset_class": "Forex Exotics", "currency_profit": "TRY"},
    "EURPLN": {"asset_class": "Forex Exotics", "currency_profit": "PLN"},
    "ZARJPY": {"asset_class": "Forex Exotics", "currency_profit": "JPY"},
    "USDZAR": {"asset_class": "Forex Exotics", "currency_profit": "ZAR"},
    "USDKZT": {"asset_class": "Forex Exotics", "currency_profit": "KZT"},
    "USDCNH": {"asset_class": "Forex Exotics", "currency_profit": "CNH"},
    "JPN225": {"asset_class": "Indices", "currency_profit": "JPY"},
    "CHINAH": {"asset_class": "Indices", "currency_profit": "HKD"},
    "KZX10": {"asset_class": "Indices", "currency_profit": "KZT"},
    "USDX": {"asset_class": "Indices", "currency_profit": "USD"},
    "XAUUSD": {"asset_class": "Commodities", "currency_profit": "USD"},
    "XAUAUD": {"asset_class": "Commodities", "currency_profit": "AUD"},
    "COCOA": {"asset_class": "Soft Commodity", "currency_profit": "USD"},
    "AAPL": {"asset_class": "Equities", "currency_profit": "USD"},
    "NOTCLASSED": {},
}


@pytest.fixture
def registry(monkeypatch, tmp_path):
    p = tmp_path / "universe.json"
    p.write_text(json.dumps(_REG), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", p)
    up._registry_at.cache_clear()
    yield p
    up._registry_at.cache_clear()


def test_regions_come_from_the_registrys_own_fields(registry) -> None:
    assert up.region_of("USDTRY") == "tr" and up.region_of("EURPLN") == "pl"
    assert up.region_of("ZARJPY") == "za" and up.region_of("USDCNH") == "cn"
    assert up.region_of("USDJPY") == "jp" and up.region_of("EURGBP") == "gb"
    assert up.region_of("JPN225") == "jp" and up.region_of("CHINAH") == "hk"
    assert up.region_of("USDKZT") == "kz" and up.region_of("KZX10") == "kz"
    assert up.region_of("XAUUSD") == up.GLOBAL and up.region_of("USDX") == up.GLOBAL
    assert up.region_of("XAUAUD") == "au"
    assert up.region_of("NOT_A_SYMBOL") == up.GLOBAL


def test_hypothesis_regions_exclude_equities_and_the_unclassified(registry) -> None:
    got = up.hypothesis_regions()
    flat = {s for v in got.values() for s in v}
    assert "AAPL" not in flat and "NOTCLASSED" not in flat
    assert {"USDTRY", "USDZAR", "ZARJPY", "EURPLN", "USDCNH", "USDKZT", "KZX10"} <= flat
    assert got["za"] == ["USDZAR", "ZARJPY"]


def test_interleave_keeps_every_symbol_and_spans_regions_first(registry) -> None:
    names = sorted(s for v in up.hypothesis_regions().values() for s in v)
    out = up.region_interleave(names)
    assert sorted(out) == names and len(out) == len(set(out))
    n_regions = len({up.region_of(s) for s in names})
    assert len({up.region_of(s) for s in out[:n_regions]}) == n_regions
    # Alphabetical order puts the emerging tail last; interleaving reaches it inside a cap of 6.
    assert not {"USDTRY", "USDZAR", "ZARJPY"} & set(names[:6])
    assert {"tr", "za"} <= {up.region_of(s) for s in out[:n_regions]}
    assert up.region_interleave(names, rotation=1) != out


def test_a_kept_cap_publishes_its_missed_growth_line(registry) -> None:
    names = sorted(s for v in up.hypothesis_regions().values() for s in v)
    chosen, line = up.breadth_window(names, 4)
    assert len(chosen) == 4 and line["left_out"] == len(names) - 4
    assert line["verdict"] == "UNMEASURED" and line["regions_left_dark"]
    _c, free = up.breadth_window(names, 99)
    assert free["verdict"] == "NOT_BINDING" and free["left_out"] == 0


def test_cross_asset_graph_widens_past_the_alphabetical_book_prefix(registry, monkeypatch) -> None:
    from research import cross_asset_graph as cag
    monkeypatch.setattr(cag, "_book_symbols", lambda: ["EURUSD", "USDJPY", "AAPL"])
    have = set(_REG)
    syms, line = cag.swept_symbols(None, have, rotation=0)
    assert "AAPL" not in syms, "a share CFD is never a lead_lag cell"
    assert set(syms[:2]) == {"EURUSD", "USDJPY"}, "the book is still swept first"
    assert {"tr", "za", "pl", "cn", "kz"} <= {up.region_of(s) for s in syms}
    assert len(syms) <= cag.MAX_SYMBOLS and line["eligible"] >= len(syms)
    # explicit symbols are honoured as given
    assert cag.swept_symbols(["USDTRY"], have)[0] == ["USDTRY"]


def test_trend_core_walks_one_region_at_a_time_then_the_measured_only(registry) -> None:
    from research import trend_core as tc
    names = sorted(_REG)
    order = tc.breadth_order(names)
    assert sorted(order) == names
    hyp = [n for n in order if up.may_hypothesise(n)]
    assert order[:len(hyp)] == hyp, "hypothesis lane first, measured-only after"
    assert order.index("USDZAR") < names.index("USDZAR")


def test_forced_flow_fx_reads_every_fx_class_including_exotics(registry, monkeypatch) -> None:
    from research import forced_flow_calendar as ffc
    monkeypatch.setattr(ffc, "UNIVERSE", registry)
    monkeypatch.setattr(ffc, "_may_hypothesise", lambda: up.may_hypothesise)
    ffc._registry.cache_clear()                    # lru-cached: clear before AND after
    try:
        fx = set(ffc._fx_all())
    finally:
        ffc._registry.cache_clear()
    assert {"USDTRY", "USDZAR", "EURPLN", "USDKZT", "USDCNH", "EURUSD", "USDJPY"} <= fx
    assert "AAPL" not in fx and "XAUUSD" not in fx
    assert ffc._FX_CLASS_NAMES == up._FX_CLASSES


def test_the_live_registry_widens_forced_flow_fx(monkeypatch) -> None:
    reg = _DESK / "data" / "universe" / "universe.json"
    if not reg.exists():
        pytest.skip("no universe registry on this host")
    from research import forced_flow_calendar as ffc
    data = json.loads(reg.read_text("utf-8"))
    exotics = {k for k, v in data.items() if v.get("asset_class") == "Forex Exotics"}
    assert exotics and exotics <= set(ffc._fx_all())


# ----------------------------------------------------------------------------- the report
def _frontier(tmp: Path, vectors: dict) -> Path:
    p = tmp / "frontier.json"
    p.write_text(json.dumps({"vectors": vectors}), "utf-8")
    return p


def _stats(tmp: Path, vectors: dict) -> Path:
    p = tmp / "stats.json"
    p.write_text(json.dumps({"vectors": vectors}), "utf-8")
    return p


NOW = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


def test_per_region_counts_backends_and_the_red_rule(tmp_path) -> None:
    recent = (NOW - timedelta(days=1)).isoformat()
    old = (NOW - timedelta(days=9)).isoformat()
    fr = _frontier(tmp_path, {
        "tr_a": {"outcome": "YIELDED", "region": "tr", "last_attempt": recent},
        "tr_b": {"outcome": "BLOCKED", "region": "tr", "last_attempt": recent},
        "za_a": {"outcome": "EMPTY", "region": "za", "last_attempt": recent},
        "za_b": {"outcome": "BLOCKED", "region": "za", "last_attempt": old},
        "pl_a": {"outcome": "NAMED_ONLY", "region": "pl"},
    })
    st = _stats(tmp_path, {
        "tr_a": {"counted_since": old, "last_success": recent, "discovery_status": "YIELDED",
                 "yielded_via": ["gdelt_doc"]},
        "za_a": {"counted_since": old, "discovery_status": "EMPTY"},
        "za_b": {"counted_since": old},
    })
    doc = ady.build(frontier=fr, vector_stats=st, coverage=tmp_path / "none.json",
                    runs=tmp_path / "none.jsonl", compute_ledger=tmp_path / "none2.jsonl",
                    region_clock=tmp_path / "clock.json", now=NOW)
    reg = doc["regions"]["by_region"]
    tr, za, pl = reg["tr"], reg["za"], reg["pl"]
    assert (tr["named"], tr["attempted"], tr["YIELDED"], tr["BLOCKED"]) == (2, 2, 1, 1)
    assert tr["flag"] == "GREEN" and tr["backend_that_yielded"] == "gdelt_doc"
    assert (za["named"], za["attempted"], za["EMPTY"], za["BLOCKED"]) == (2, 1, 1, 1)
    # Za has counted since nine days ago and never yielded: RED on evidence, not on code age.
    assert za["flag"] == "RED" and za["days_at_zero"] >= 7 and "za" in doc["regions"]["red"]
    # Pl has no counters at all: the clock starts now, so it is WATCH, not RED.
    assert pl["flag"] == "WATCH" and pl["NAMED_ONLY"] == 1
    assert doc["summary"]["regions_red"] == ["za"]
    for r in reg.values():
        assert {"named", "attempted", "YIELDED", "EMPTY", "BLOCKED", "backend_that_yielded",
                "flag", "mt5_hypothesis_symbols"} <= set(r)


def test_the_clock_carries_a_streak_across_passes_and_turns_red_on_day_seven(tmp_path) -> None:
    fr = _frontier(tmp_path, {"pl_a": {"outcome": "EMPTY", "region": "pl"}})
    st = _stats(tmp_path, {})
    clock = tmp_path / "clock.json"
    kw = {"frontier": fr, "vector_stats": st, "coverage": tmp_path / "x.json",
          "runs": tmp_path / "x.jsonl", "compute_ledger": tmp_path / "y.jsonl",
          "region_clock": clock}
    ady.write(out=tmp_path / "a.json", **kw)
    first = json.loads(clock.read_text("utf-8"))["regions"]["pl"]["zero_since"]
    assert first
    later = _from(first) + timedelta(days=7, minutes=1)
    doc = ady.build(now=later, **kw)
    assert doc["regions"]["by_region"]["pl"]["flag"] == "RED"
    early = ady.build(now=_from(first) + timedelta(days=6), **kw)
    assert early["regions"]["by_region"]["pl"]["flag"] == "WATCH"


def _from(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_an_unreadable_frontier_is_unmeasured_and_never_resets_the_clock(tmp_path) -> None:
    clock = tmp_path / "clock.json"
    clock.write_text(json.dumps({"regions": {"tr": {"zero_since": "2026-10-01T00:00:00+00:00",
                                                     "last_yielded": None}}}), "utf-8")
    doc = ady.write(out=tmp_path / "a.json", frontier=tmp_path / "missing.json",
                    vector_stats=tmp_path / "missing2.json", coverage=tmp_path / "c.json",
                    runs=tmp_path / "r.jsonl", compute_ledger=tmp_path / "l.jsonl",
                    region_clock=clock)
    assert doc["regions"]["status"] == "UNMEASURED"
    assert doc["summary"]["regions"] == "UNMEASURED"
    assert json.loads(clock.read_text("utf-8"))["regions"]["tr"]["zero_since"].startswith(
        "2026-10-01")


# ----------------------------------------------------------------------------- audit HOLD fixes
def test_hourly_rotation_reaches_every_member_of_every_region(registry) -> None:
    names = sorted(s for v in up.hypothesis_regions().values() for s in v)
    buckets: dict[str, int] = {}
    for s in names:
        buckets[up.region_of(s)] = buckets.get(up.region_of(s), 0) + 1
    bound = len(buckets) * max(buckets.values())
    for cap in (1, 3):
        seen: set[str] = set()
        for hour in range(bound):
            seen |= set(up.breadth_window(names, cap, rotation=hour)[0])
        assert seen == set(names), (cap, set(names) - seen)


def test_cross_asset_graph_without_a_registry_sweeps_the_book_and_says_unmeasured(
        monkeypatch, tmp_path) -> None:
    from research import cross_asset_graph as cag
    from research import missed_growth as mg
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "absent.json")
    up._registry_at.cache_clear()
    monkeypatch.setattr(cag, "_book_symbols", lambda: ["USDJPY", "EURUSD"])
    syms, line = cag.swept_symbols(None, {"EURUSD", "USDJPY"})
    up._registry_at.cache_clear()
    assert syms == ["EURUSD", "USDJPY"], "the book is still swept, as before"
    assert line["status"] == "UNMEASURED" and "registry" in line["why"]
    # An empty sweep is UNMEASURED too, and its published line reads UNMEASURED downstream.
    _s, empty = cag.swept_symbols(None, set())
    assert empty["status"] == "UNMEASURED"
    rep = tmp_path / "cross_asset_graph.json"
    rep.write_text(json.dumps({"missed_growth": [{"rail": "x", **empty}]}), "utf-8")
    assert mg.organ_published_lines(rep)["verdict"] == "UNMEASURED"


def test_a_region_green_yesterday_is_one_day_at_zero_not_red(tmp_path) -> None:
    old = (NOW - timedelta(days=30)).isoformat()
    yday = (NOW - timedelta(days=1)).isoformat()
    fr = _frontier(tmp_path, {"tr_a": {"outcome": "EMPTY", "region": "tr"}})
    st = _stats(tmp_path, {"tr_a": {"counted_since": old}})
    clock = tmp_path / "clock.json"
    clock.write_text(json.dumps({"regions": {"tr": {"zero_since": None, "last_yielded": yday}}}),
                     "utf-8")
    doc = ady.build(frontier=fr, vector_stats=st, coverage=tmp_path / "c.json",
                    runs=tmp_path / "r.jsonl", compute_ledger=tmp_path / "l.jsonl",
                    region_clock=clock, now=NOW)
    tr = doc["regions"]["by_region"]["tr"]
    assert tr["flag"] == "WATCH" and 0.9 < tr["days_at_zero"] < 1.1


def test_an_unreadable_clock_is_unmeasured_and_never_overwritten(tmp_path) -> None:
    fr = _frontier(tmp_path, {"za_a": {"outcome": "EMPTY", "region": "za"},
                              "tr_a": {"outcome": "YIELDED", "region": "tr"}})
    clock = tmp_path / "clock.json"
    clock.write_text("{torn", "utf-8")
    doc = ady.write(out=tmp_path / "a.json", frontier=fr, vector_stats=_stats(tmp_path, {}),
                    coverage=tmp_path / "c.json", runs=tmp_path / "r.jsonl",
                    compute_ledger=tmp_path / "l.jsonl", region_clock=clock)
    reg = doc["regions"]
    assert reg["clock"].startswith("UNMEASURED") and reg["red"] == "UNMEASURED"
    assert reg["by_region"]["za"]["flag"] == "UNMEASURED"
    assert reg["by_region"]["tr"]["flag"] == "GREEN"
    assert clock.read_text("utf-8") == "{torn"


def test_the_box_local_state_files_are_gitignored() -> None:
    import shutil
    import subprocess
    if not shutil.which("git") or not (_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    paths = ["desks/mt5/data/discovery_host_holds.json",
             "desks/mt5/data/discovery_host_holds.json.4242.tmp",
             "desks/mt5/data/region_yield_clock.json",
             "desks/mt5/data/region_yield_clock.json.4242.tmp",
             "desks/mt5/data/.job_locks/.api.gdeltproject.org.slot",
             "desks/mt5/data/.job_locks/.api.gdeltproject.org.slot.lock",
             "desks/mt5/data/.job_locks/discovery_host_holds.lock"]
    out = subprocess.run(["git", "check-ignore", *paths], cwd=_ROOT, capture_output=True,
                         text=True, check=False).stdout.split()
    assert sorted(out) == sorted(paths)
