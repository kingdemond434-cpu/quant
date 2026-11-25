"""The alt catalog: every executable `alt:` lake series reaches the free-model generators in the
exact spec syntax, gap-weighted, and comes back as a testable row the funnel counts per source.
Every input is synthetic and lives in `tmp_path`; no model is called."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_catalog as ac  # noqa: E402
from research import family_spec as fs  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
HEAD = "event_time,available_time,"


def _csv(path: Path, cols: str, n: int = 12, *, stamped: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    head = (HEAD if stamped else "event_time,") + cols
    k = len(cols.split(","))
    rows = [f"2026-01-{i + 1:02d}," + (f"2026-01-{i + 2:02d}T00:00:00Z," if stamped
                                       else "") + ",".join(str(i + j) for j in range(k))
            for i in range(n)]
    path.write_text("\n".join([head, *rows]) + "\n", "utf-8")


def _lake(tmp: Path, sub: str = "lake") -> Path:
    lake = tmp / sub
    _csv(lake / "ks_bok__exports.csv", "surprise_z,level")
    _csv(lake / "tick_news_EURUSD.csv", "chg_z")
    _csv(lake / "kr_exports_20d.csv", "level")
    _csv(lake / "unstamped.csv", "value_z", stamped=False)
    return lake


def _isolate(monkeypatch: Any, tmp: Path) -> None:
    monkeypatch.setattr(ac, "EXPOSURE", tmp / "exposure.json")
    monkeypatch.setattr(ac, "FUNNEL", tmp / "FUNNEL.json")
    monkeypatch.setattr(ac, "PRESCRIPTIONS", tmp / "PRODUCER_PRESCRIPTIONS.json")


# ------------------------------------------------------------------------------ catalog ---
def test_catalog_lists_stamped_series_with_measured_specs_only(tmp_path: Path) -> None:
    cat = ac.catalog(_lake(tmp_path), thresholds=True)
    assert cat["status"] == "READ"
    by = {r["series"]: r for r in cat["series"]}
    assert set(by) == {"ks_bok__exports", "tick_news_EURUSD", "kr_exports_20d"}
    assert "unstamped" in cat["refused"]                       # no PIT stamp, no honest join
    assert by["ks_bok__exports"]["source"] == "ks_bok"
    assert by["tick_news_EURUSD"]["source"] == "tick_news"
    assert by["tick_news_EURUSD"]["symbol"] == "EURUSD"
    assert "alt:ks_bok__exports:surprise_z:gt:0" in by["ks_bok__exports"]["specs"]
    # a level column's threshold is its own measured median, never an invented number
    lvl = [s for s in by["kr_exports_20d"]["specs"] if ":level:" in s]
    assert lvl and all(ac.parse_spec(s)[3] == 5.5 for s in lvl)
    # the cheap read offers z-shaped specs only
    cheap = {r["series"]: r for r in ac.catalog(tmp_path / "lake")["series"]}
    assert cheap["kr_exports_20d"]["specs"] == []


def test_an_absent_lake_is_unmeasured_never_an_empty_clean_catalog(tmp_path: Path) -> None:
    cat = ac.catalog(tmp_path / "nope")
    assert cat["status"] == ac.UNMEASURED and cat["series"] == []


def test_every_spec_is_one_the_gauntlet_parses(tmp_path: Path) -> None:
    from mt5desk.cell_modifiers import alt_conditioner
    for r in ac.catalog(_lake(tmp_path), thresholds=True)["series"]:
        for s in r["specs"]:
            assert alt_conditioner(s) is not None and ac.parse_spec(s) == alt_conditioner(s)


# ------------------------------------------------------------------------ gap weighting ---
def _flat(n: int) -> dict[str, Any]:
    return {"status": "READ", "series": [
        {"series": f"s{i}", "source": f"src{i}", "columns": ["z"], "specs": [f"alt:s{i}:z:gt:0"]}
        for i in range(n)]}


def test_untested_series_are_preferred_and_gap_targets_boosted() -> None:
    cat = _flat(20)
    tested = {f"s{i}": 500 for i in range(10)}            # s0..s9 heavily covered
    hits: dict[str, int] = {}
    for h in range(200):
        for r in ac.choose(cat, k=4, tested=tested, seed=f"t{h}", explore_share=0.0):
            hits[r["series"]] = hits.get(r["series"], 0) + 1
    covered = sum(v for k, v in hits.items() if int(k[1:]) < 10)
    assert covered < 0.05 * sum(hits.values())
    boosted: dict[str, int] = {}
    for h in range(400):
        for r in ac.choose(cat, k=1, gaps={"s19"}, seed=f"g{h}", explore_share=0.0):
            boosted[r["series"]] = boosted.get(r["series"], 0) + 1
    assert boosted.get("s19", 0) > 400 / 20                  # above its uniform share


def test_exploration_share_still_reshows_covered_series() -> None:
    cat = _flat(20)
    tested = {f"s{i}": 10_000 for i in range(19)}
    seen = set()
    for h in range(100):
        seen |= {r["series"] for r in ac.choose(cat, k=4, tested=tested, seed=f"e{h}")}
    assert len(seen) > 5                                      # not only the untested one
    assert ac.choose(cat, k=4, seed="x") == ac.choose(cat, k=4, seed="x")   # replayable


# ------------------------------------------------------------- prompt block and parsing ---
def test_prompt_block_carries_exact_specs_and_records_exposure(tmp_path: Path,
                                                                monkeypatch: Any) -> None:
    _isolate(monkeypatch, tmp_path)
    cat = ac.catalog(_lake(tmp_path), thresholds=True)
    block = ac.prompt_block("kimi_hunt", cat=cat, now=NOW)
    assert "alt:<series>:<column>:<gt|lt>:<threshold>" in block
    assert "ALT_CELL |" in block
    assert any(s in block for r in cat["series"] for s in r["specs"])
    exp = ac.read_exposure(tmp_path / "exposure.json")
    assert exp["organs"]["kimi_hunt"]["prompts"] == 1
    assert all("kimi_hunt" in v["organs"] for v in exp["series"].values())
    assert ac.prompt_block("kimi_hunt", cat=ac.catalog(tmp_path / "nope"), now=NOW) == ""


def test_parse_cells_keeps_catalog_specs_and_names_every_refusal(tmp_path: Path) -> None:
    cat = ac.catalog(_lake(tmp_path))
    text = "\n".join([
        "ALT_CELL | session_range_breakout | AUDUSD | alt:ks_bok__exports:surprise_z:gt:0 | "
        "Korean exporters must convert USD receipts, lifting AUD proxies",
        "ALT_CELL | session_range_breakout | AUDUSD | alt:not_a_series:z:gt:0 | some reason here",
        "ALT_CELL | not_a_family | AUDUSD | alt:ks_bok__exports:surprise_z:gt:0 | reason text x",
        "ALT_CELL | session_range_breakout | AUDUSD | macro | prose conditioner refused",
        "VERIFIED | something | else | that is not a cell",
    ])
    rows, why = ac.parse_cells(text, cat=cat, organ="kimi_hunt")
    assert len(rows) == 1 and len(why) == 3
    r = rows[0]
    assert r["family"] == "session_range_breakout" and r["symbols"] == ["AUDUSD"]
    assert r["params"] == {"conditioner": "alt:ks_bok__exports:surprise_z:gt:0"}
    assert r["alt_source"] == "ks_bok" and r["kind"] == "hypothesis"


def test_a_donated_alt_cell_compiles_as_an_exact_testable_recipe(tmp_path: Path) -> None:
    import miner_candidate_compiler as mcc
    rows, _ = ac.parse_cells(
        "ALT_CELL | session_range_breakout | AUDUSD | alt:ks_bok__exports:surprise_z:gt:0 | "
        "exporters convert receipts at the fix", cat=ac.catalog(_lake(tmp_path)))
    cands, disp = mcc.compile_row("kimi_k3_deep_forest", rows[0], {"AUDUSD"})
    assert disp == "EXACT_RECIPE"
    assert cands[0]["params"]["conditioner"] == "alt:ks_bok__exports:surprise_z:gt:0"
    assert fs.is_testable(fs.to_executable(cands[0]["family"], cands[0]["params"])["status"])


# ------------------------------------------------------------------------ family_spec -----
def test_an_alt_conditioner_on_family_defaults_is_executable_and_kept() -> None:
    got = fs.to_executable("session_range_breakout",
                           {"conditioner": "alt:ks_bok__exports:surprise_z:gt:0"})
    assert got["status"] == fs.EXECUTABLE_VARIANT
    assert got["params"]["conditioner"] == "alt:ks_bok__exports:surprise_z:gt:0"
    # a prose axis is still refused by the gauntlet, so it is still not a rule
    assert not fs.is_testable(fs.to_executable("session_range_breakout",
                                               {"conditioner": "macro"})["status"])
    both = fs.to_executable("trend_ma_cross", {"fast": 8, "conditioner": "alt:x:z:lt:0"})
    assert both["status"] == fs.EXECUTABLE and both["params"]["conditioner"] == "alt:x:z:lt:0"


# --------------------------------------------------------------------------- coverage -----
def test_coverage_counts_rows_testable_judged_certified_per_series(tmp_path: Path) -> None:
    from research import frontier_identity as fi
    cat = ac.catalog(_lake(tmp_path))
    row = {"symbol": "AUDUSD", "family": "session_range_breakout",
           "params": {"conditioner": "alt:ks_bok__exports:surprise_z:gt:0"}}
    cid = fi.cell_id(fi.docket_cell(row))
    rows = [row, dict(row, symbol="NZDUSD"),
            {"symbol": "EURUSD", "family": "carry", "params": {"conditioner": "macro"}},
            {"symbol": "EURUSD", "family": "session_range_breakout",
             "params": {"conditioner": "alt:ghost:z:gt:0"}}]
    cov = ac.coverage(cat, rows, judged={cid}, certified={cid},
                      exposure={"series": {"ks_bok__exports": {"organs": {"kimi_hunt": {}}}}})
    e = cov["series"]["ks_bok__exports"]
    assert (e["rows"], e["testable_rows"], e["judged"], e["certified"]) == (2, 2, 1, 1)
    assert e["generators_seeing"] == ["kimi_hunt"]
    assert cov["off_catalog"] == {"ghost": 1}
    assert "tick_news_EURUSD" in cov["zero_coverage_series"]
    assert "ks_bok__exports" not in cov["zero_coverage_series"]
    assert cov["by_source"]["ks_bok"]["testable_rows"] == 2
    blind = ac.coverage(cat, rows)
    assert blind["series"]["ks_bok__exports"]["judged"] == ac.UNMEASURED
    assert blind["n_series_seen_by_a_generator"] == ac.UNMEASURED


def test_funnel_publishes_by_alt_source(tmp_path: Path, monkeypatch: Any) -> None:
    from research import funnel as fn
    p = fn.Paths.at(tmp_path)
    lake = _lake(tmp_path / "data")
    monkeypatch.setattr(fn.Paths, "at", classmethod(lambda cls, d: p))
    p2 = fn.Paths(**{**p.__dict__, "lake": lake})
    row = {"symbol": "AUDUSD", "family": "session_range_breakout", "source": "miner:kimi",
           "params": {"conditioner": "alt:ks_bok__exports:surprise_z:gt:0"}}
    p2.compiler.parent.mkdir(parents=True, exist_ok=True)
    p2.compiler.write_text(json.dumps({"hypotheses": [row], "per_source": {}}), "utf-8")
    doc = fn.build(p2, now=NOW, budget_s=60, is_exotic=lambda s: False,
                   trades_of=lambda n: [])
    b = doc["by_alt_source"]
    assert b["series"]["ks_bok__exports"]["testable_rows"] == 1
    assert b["series"]["ks_bok__exports"]["generators_seeing"] == ac.UNMEASURED
    assert b["series"]["ks_bok__exports"]["judged"] == ac.UNMEASURED     # no seen-cells file
    assert set(b["zero_coverage_series"]) == {"tick_news_EURUSD", "kr_exports_20d"}
    # no compiler rows at all: the counts are UNMEASURED, never a clean zero
    p2.compiler.unlink()
    blind = fn.build(p2, now=NOW, budget_s=60, is_exotic=lambda s: False,
                     trades_of=lambda n: [])["by_alt_source"]
    assert blind["zero_coverage_series"] == ac.UNMEASURED


# ------------------------------------------------------------------------ gap targets -----
def test_producer_loop_carries_alt_gaps_to_every_producer(tmp_path: Path) -> None:
    from research import producer_loop as pl
    f = tmp_path / "FUNNEL.json"
    f.write_text(json.dumps({"by_alt_source": {"zero_coverage_series": ["b", "a"]}}), "utf-8")
    assert pl.alt_gaps(f) == ["a", "b"]
    assert pl.alt_gaps(tmp_path / "absent.json") == pl.UNMEASURED
    gaps = pl.coverage_gaps(None, None, None, {}, alt_sources=["a"])
    assert gaps["alt_sources"] == ["a"]
    assert pl.gap_target(None, gaps)["alt_sources"] == ["a"]           # no diagnosis needed
    assert pl.gap_target({"buckets": {}, "families": []}, gaps)["alt_sources"] == ["a"]


def test_the_seat_reads_its_alt_gap_target(tmp_path: Path) -> None:
    pr = tmp_path / "p.json"
    pr.write_text(json.dumps({"gap_target": {"kimi_hunt": {"alt_sources": ["s3"]},
                                             "other": {"alt_sources": ["s4"]}}}), "utf-8")
    assert ac.gap_series(pr, organ="kimi_hunt") == {"s3"}
    assert ac.gap_series(pr) == {"s3", "s4"}


# --------------------------------------------------------------- the generators' prompts --
def test_deepseek_prompt_carries_alt_specs_and_donates_the_recipe(tmp_path: Path,
                                                                  monkeypatch: Any) -> None:
    import libs.ops.deepseek_cycle as ds
    import libs.ops.llm_seat as seat
    _isolate(monkeypatch, tmp_path)
    _lake(tmp_path / "desks" / "mt5" / "data" / "lake", "series")
    monkeypatch.setattr(ds, "policy_gate", lambda root=None: {"ok": True, "policy_hash": "h"})
    monkeypatch.setattr(ds, "budget_gate", lambda: {"ok": True, "why": "ok"})
    seen: dict[str, str] = {}
    payload = json.dumps({"findings": [{
        "title": "exporter conversion lifts AUD on BOK surprise",
        "mechanism": "exporters must convert receipts", "testable_claim": "x",
        "symbols": ["AUDUSD"], "family": "session_range_breakout",
        "conditioner": "alt:ks_bok__exports:surprise_z:gt:0"}]})

    def chat(user: str, **kw: Any) -> tuple[str, None]:
        seen["user"] = user
        return payload, None

    monkeypatch.setattr(seat, "chat", chat)
    out = ds.run_role("cold_alpha_inventor", "brief", deep=False, root=tmp_path,
                      env={"OPENROUTER_API_KEY": "sk-test", "DEEPSEEK_BULK_MODEL": "m"})
    assert out["status"] == "OK"
    assert "alt:ks_bok__exports:surprise_z:gt:0" in seen["user"]
    don = json.loads(Path(out["donated_to"]).read_text("utf-8"))["discoveries"][0]
    assert don["params"] == {"conditioner": "alt:ks_bok__exports:surprise_z:gt:0"}


def test_kimi_shows_the_slice_to_waves_two_and_three_and_donates_recipes() -> None:
    src = (_ROOT / "scripts" / "kimi_hunter.py").read_text("utf-8")
    assert "ac.prompt_block(ALT_ORGAN" in src and "if w > 1" in src
    assert "ac.parse_cells(txt" in src and "_donate_alt(_cells)" in src
    sys.path.insert(0, str(_ROOT / "scripts"))
    import kimi_hunter as kh
    assert kh._alt_catalog() is not None
