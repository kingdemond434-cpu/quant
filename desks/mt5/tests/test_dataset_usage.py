"""The dataset-usage census (BACKLOG row 61): FED / UNFED / STARVED / UNMEASURED, never clean
by default, a 24 h RED fence, no lookahead, and the leg wired onto a clock.

Every test roots the organ at a temp desk and a temp code tree, so nothing here reads or writes
the live registries.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import dataset_usage as du  # noqa: E402

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _bars(path: Path, last: datetime, n: int = 5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = pd.date_range(end=pd.Timestamp(last), periods=n, freq="h")
    pd.DataFrame({"time": t, "close": range(n)}).to_parquet(path, index=False)


def _tree(tmp: Path, *, reader: bool = True, clocked: bool = True,
          registry: dict | None = None) -> tuple[Path, Path]:
    """A temp repo: desks/mt5 with a data registry, and (optionally) one reader on a clock."""
    repo = tmp / "repo"
    desk = repo / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    (desk / "research").mkdir(parents=True)
    reg = registry if registry is not None else {"datasets": {
        "bars": {"lifecycle": "CORE", "path": "data/universe/*_H1.parquet", "symbols": 2,
                 "cadence": "hourly"},
        "lost": {"lifecycle": "DISCOVERED", "source": "nowhere"}}}
    (desk / "data" / "data_registry.json").write_text(json.dumps(reg), "utf-8")
    if reader:
        (desk / "research" / "bar_reader.py").write_text(
            'P = DESK / "data" / "universe"\nGLOB = "*_H1.parquet"\n', "utf-8")
    clock = '_producer("bar_reader", "research/bar_reader.py")\n' if clocked else "\n"
    (desk / "research" / "hourly_cycle.py").write_text(clock, "utf-8")
    return repo, desk


def _run(repo: Path, desk: Path, now: datetime = NOW) -> dict:
    return du.build(desk, repo, now=now, budget_s=60)


def _row(doc: dict, did: str) -> dict:
    return next(r for r in doc["datasets"] if r["id"] == did)


# ------------------------------------------------------------------ the verdict logic
def test_fresh_complete_and_read_by_a_clocked_organ_is_fed(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW - timedelta(minutes=30))
    doc = _run(repo, desk)
    r = _row(doc, "bars")
    assert r["verdict"] == "FED", r
    assert r["freshness_basis"] == "observation"
    assert r["n_scheduled_consumers"] == 1
    assert doc["fence"] == "GREEN"
    # a discovered-never-collected row is listed, never judged
    assert [n["id"] for n in doc["not_collected"]] == ["lost"]


def test_a_reader_no_clock_reaches_leaves_the_dataset_unfed(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, clocked=False)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW)
    r = _row(_run(repo, desk), "bars")
    assert r["verdict"] == "UNFED"
    assert "none reached by any clock" in r["why"]


def test_no_reader_at_all_is_unfed(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, reader=False)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW)
    assert _row(_run(repo, desk), "bars")["verdict"] == "UNFED"


def test_stale_data_with_a_reader_is_starved_and_red_past_24h(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW - timedelta(hours=40))
    doc = _run(repo, desk)
    r = _row(doc, "bars")
    assert r["verdict"] == "STARVED" and r["freshness"] == "STALE"
    # stale since newest + 2 x cadence = 38 h ago, which is past the 24 h line
    assert r["bad_for_h"] == pytest.approx(38.0, abs=0.01)
    assert doc["fence"] == "RED"
    assert doc["red"][0]["id"] == "bars"


def test_a_missing_declared_part_is_partial_and_starves(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    _bars(desk / "data" / "universe" / "AAA_H1.parquet", NOW)
    r = _row(_run(repo, desk), "bars")
    assert r["completeness"] == "PARTIAL"
    assert r["missing"] == ["files: 1 of the 2 declared"]
    assert r["verdict"] == "STARVED"


def test_unfed_turns_red_only_after_24h_carried_through_the_artifact(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, clocked=False)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW)
    first = _run(repo, desk)
    assert first["fence"] == "GREEN" and "pending_red" in first["fence_why"]
    assert [p["id"] for p in first["pending_red"]] == ["bars"]
    du.write(first, desk)
    later = NOW + timedelta(hours=25)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", later)
    second = _run(repo, desk, later)
    assert second["fence"] == "RED"
    assert _row(second, "bars")["bad_since"] == NOW.isoformat(timespec="seconds")


def test_a_never_written_dataset_is_unmeasured_never_clean(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    doc = _run(repo, desk)
    r = _row(doc, "bars")
    assert r["verdict"] == "UNMEASURED"
    assert r["missing"] == []          # parts are not judged against files that do not exist
    assert doc["fence"] == "UNMEASURED"


def test_unreadable_registries_read_unmeasured(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    (desk / "data" / "data_registry.json").write_text("{not json", "utf-8")
    doc = _run(repo, desk)
    assert doc["n_datasets"] == 0
    assert doc["fence"] == "UNMEASURED"
    assert doc["registries"]["data_registry"].startswith("UNMEASURED")
    assert all(v.startswith("UNMEASURED") for v in doc["registries"].values())


def test_a_reader_scan_that_did_not_run_is_unmeasured(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW)
    doc = du.build(desk, repo, now=NOW, scan=False)
    assert _row(doc, "bars")["verdict"] == "UNMEASURED"


def test_a_registry_row_without_cadence_names_the_fallback(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, registry={"datasets": {
        "bars": {"lifecycle": "CORE", "path": "data/universe/*_H1.parquet"}}})
    _bars(desk / "data" / "universe" / "AAA_H1.parquet", NOW - timedelta(hours=100))
    doc = _run(repo, desk)
    r = _row(doc, "bars")
    assert r["cadence_source"] == "UNDECLARED_FALLBACK"
    assert r["freshness"] == "FRESH"         # 100 h inside 2 x the 168 h fallback
    assert doc["cadence_undeclared"] == ["data_registry:bars"]


# ------------------------------------------------------------------ lookahead and secrets
def test_a_future_stamp_is_lookahead_and_never_freshness(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    for s in ("AAA", "BBB"):
        p = desk / "data" / "universe" / f"{s}_H1.parquet"
        _bars(p, NOW + timedelta(days=3))
        old = (NOW - timedelta(days=30)).timestamp()
        os.utime(p, (old, old))
    r = _row(_run(repo, desk), "bars")
    assert r["lookahead_stamps"] is True
    assert r["freshness"] != "FRESH"
    assert r["verdict"] == "STARVED"


def test_the_census_never_reads_secrets(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path)
    sec = repo / "data" / "secrets"
    sec.mkdir(parents=True)
    (sec / "key.py").write_text('KEY = "sk-live-do-not-print"  # data/universe\n', "utf-8")
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW)
    doc = _run(repo, desk)
    assert "sk-live" not in json.dumps(doc)
    assert all("secrets" not in c["path"] for r in doc["datasets"] for c in r.get("consumers", []))


# ------------------------------------------------------------------ the other registries
def test_free_stack_rows_need_both_files_and_a_column(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, registry={"datasets": {}})
    (desk / "data" / "free_stack_sources.json").write_text(json.dumps({"sources": [
        {"id": "gtrends", "cadence": "daily",
         "uses": {"direct": {"organ": "research/free_stack_proposer.py"}}}]}), "utf-8")
    (desk / "data" / "free_stack" / "obs").mkdir(parents=True)
    (desk / "data" / "free_stack" / "obs" / "gtrends.jsonl").write_text("{}\n", "utf-8")
    (desk / "data" / "free_stack" / "columns.json").write_text("{}", "utf-8")
    (desk / "research" / "free_stack_proposer.py").write_text('p = f"fs_{sid}"\n', "utf-8")
    (desk / "research" / "hourly_cycle.py").write_text(
        '_producer("x", "research/free_stack_proposer.py")\n', "utf-8")
    r = _row(du.build(desk, repo, now=datetime.now(UTC), budget_s=60), "gtrends")
    assert r["completeness"] == "PARTIAL"
    assert "files:fs_gtrends.parquet" in r["missing"]
    assert any("columns.json" in m for m in r["missing"])
    assert r["verdict"] == "STARVED"


def test_futures_state_staleness_is_its_owners_verdict(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, registry={"datasets": {}})
    (desk / "reports").mkdir()
    (desk / "reports" / "FUTURES_STATE.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(),
        "series": {"cftc_gold": {"kind": "cftc"}, "fred_us": {"kind": "fred"}},
        "notes": [{"series": "fred_us", "status": "UNMEASURED", "why": "STALE: silent 40d"}]}),
        "utf-8")
    for sid in ("cftc_gold", "fred_us"):
        _bars(desk / "data" / "lake" / "series" / f"{sid}.parquet", NOW)
    (desk / "research" / "cond.py").write_text('S = DESK / "lake" / "series"\n', "utf-8")
    (desk / "research" / "hourly_cycle.py").write_text('_producer("c", "research/cond.py")\n',
                                                        "utf-8")
    doc = _run(repo, desk)
    assert _row(doc, "cftc_gold")["verdict"] == "FED"
    assert _row(doc, "fred_us")["verdict"] == "STARVED"


def test_a_writer_is_not_its_own_consumer(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, registry={"datasets": {}})
    (desk / "data" / "acquired").mkdir(parents=True)
    (desk / "data" / "acquired" / "registry.json").write_text(json.dumps({"series": {
        "ecb_usd": {"path": "/home/quant/x/desks/mt5/data/acquired/ecb_usd.parquet"}}}),
        "utf-8")
    _bars(desk / "data" / "acquired" / "ecb_usd.parquet", NOW)
    (desk / "research" / "acquire_datasets.py").write_text('S = "data/acquired"\n', "utf-8")
    (desk / "research" / "hourly_cycle.py").write_text(
        '_producer("a", "research/acquire_datasets.py")\n', "utf-8")
    assert _row(_run(repo, desk), "ecb_usd")["verdict"] == "UNFED"


def test_a_reader_reached_through_imports_is_scheduled(tmp_path: Path) -> None:
    repo, desk = _tree(tmp_path, clocked=False)
    (desk / "research" / "leg.py").write_text("from research import bar_reader\n", "utf-8")
    (desk / "research" / "hourly_cycle.py").write_text('_producer("l", "research/leg.py")\n',
                                                        "utf-8")
    for s in ("AAA", "BBB"):
        _bars(desk / "data" / "universe" / f"{s}_H1.parquet", NOW)
    assert _row(_run(repo, desk), "bars")["verdict"] == "FED"


# ------------------------------------------------------------------ the wiring
def test_the_leg_is_on_the_core_clock_with_budget_layer_and_department() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["dataset_usage"] == "meta"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"dataset_usage", "research/dataset_usage.py", "--once"' in src
    assert '"dataset_usage": dsu' in src
    # after every collector it judges
    for leg in ("free_stack_hunt", "futures_state", "acquire_datasets"):
        assert src.index(f'_costed("{leg}"') < src.index('_costed("dataset_usage"')
    from research import hourly_cycle as hc
    assert "dataset_usage" in hc.CORE_LEGS
    assert hc.LEG_DEPARTMENT["dataset_usage"] == "data"
    assert hc.LEG_BUDGET_SEC["dataset_usage"] > 240


def test_the_artifact_is_declared_attested_and_on_the_board(tmp_path: Path) -> None:
    from desks.mt5.ops.components import own_artifact
    assert own_artifact("desks/mt5/research/dataset_usage.py") == (
        "desks/mt5/reports/DATASET_USAGE.json",)
    state = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    assert any(r.get("organ") == "leg:dataset_usage" for r in state["organs"])
    from research import issue_board as ib
    assert ("dataset_usage", "desks/mt5/reports/DATASET_USAGE.json", 3600,
            "research/dataset_usage.py") in ib.CADENCE
    rep = tmp_path / "desks" / "mt5" / "reports"
    rep.mkdir(parents=True)
    (rep / "DATASET_USAGE.json").write_text(json.dumps({
        "fence": "RED", "red": [{"registry": "free_stack", "id": "gtrends",
                                 "verdict": "STARVED"}]}), "utf-8")
    issues = ib.dataset_usage_issues(tmp_path)
    assert [i.key for i in issues] == ["dataset_usage:red"]
    assert "free_stack:gtrends STARVED" in issues[0].detail
    (rep / "DATASET_USAGE.json").write_text(json.dumps({"fence": "GREEN"}), "utf-8")
    assert ib.dataset_usage_issues(tmp_path) == []
    (rep / "DATASET_USAGE.json").write_text(json.dumps({"fence": "UNMEASURED",
                                                         "fence_why": "x"}), "utf-8")
    assert ib.dataset_usage_issues(tmp_path)[0].severity == "BLIND"
