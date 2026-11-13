"""A source whose terms forbid commercial use does not reach the candidate compiler, and can
only be reopened with the permitting clause in hand."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mc  # noqa: E402
from research import terms_fences as tf  # noqa: E402


def _write(root: Path, rel: str, rows: list[dict]) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if rel.endswith(".jsonl"):
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    else:
        path.write_text(json.dumps({"discoveries": rows}), "utf-8")
    return path


@pytest.fixture
def roots(tmp_path, monkeypatch):
    a, b = tmp_path / "desk_intel", tmp_path / "repo_intel"
    a.mkdir()
    b.mkdir()
    monkeypatch.setattr(mc, "INTEL_ROOTS", (a, b))
    return a, b


def _titles() -> set[str]:
    return {str(r.get("title")) for _, r in mc.recent_rows(mc.datetime.now(tz=mc.UTC))}


def test_the_shipped_registry_fences_bis_and_congress_and_nothing_is_open() -> None:
    fences = tf.load()
    assert [f["id"] for f in fences] == ["bis_speeches", "congress_trades"]
    assert "noncommercial" in fences[0]["reason"] and "noncommercial" in fences[0]["clause"]
    assert tf.fence_for("bis_speeches/discoveries_20260901_0022.json", fences)
    assert tf.fence_for(Path("central_banks") / "bis_speech_tone.jsonl", fences)
    for free in ("central_banks/official_speech_tone.jsonl", "central_banks/cb_documents.jsonl",
                 "central_banks/discoveries_20260901_0002.json", "world/bis_speeches.json"):
        assert tf.fence_for(free, fences) is None, free
    assert not any(tf.is_open(f) for f in fences)


def test_bis_rows_are_parked_counted_and_left_on_disk(roots) -> None:
    a, b = roots
    p1 = _write(a, "bis_speeches/discoveries_1.json", [{"title": "bis one", "symbol": "EURUSD"}])
    p2 = _write(b, "central_banks/bis_speech_tone.jsonl", [{"title": "bis tone"}])
    _write(a, "central_banks/official_speech_tone.jsonl", [{"title": "fed own site"}])
    _write(a, "world/discoveries_1.json", [{"title": "other", "symbol": "XAUUSD"}])
    assert _titles() == {"fed own site", "other"}
    parked = mc._LAST_INTAKE["terms_fenced"]["bis_speeches"]
    assert parked["files_parked"] == 2 and parked["bytes_parked"] > 0
    assert "noncommercial" in parked["reason"] and parked["missed_growth"]
    assert p1.exists() and p2.exists()                      # parked, never deleted


def test_a_missing_or_emptied_registry_still_fences_bis(tmp_path: Path) -> None:
    for body in (None, "not json", json.dumps({"fences": []})):
        reg = tmp_path / "r.json"
        if body is None:
            reg.unlink(missing_ok=True)
        else:
            reg.write_text(body, "utf-8")
        fences = tf.load(reg)
        assert tf.fence_for("bis_speeches/x.json", fences) is not None, body


def test_reopening_needs_the_flag_and_the_pasted_clause(tmp_path: Path) -> None:
    reg = tmp_path / "r.json"
    row = {"id": "bis_speeches", "match": ["bis_speeches/*"], "reason": "x"}
    for extra in ({"open": True}, {"open": True, "permit_clause": "ok"},
                  {"open": "true", "permit_clause": "commercial use is permitted with credit"},
                  {"permit_clause": "commercial use is permitted with credit"}):
        reg.write_text(json.dumps({"fences": [{**row, **extra}]}), "utf-8")
        assert tf.fence_for("bis_speeches/x.json", tf.load(reg)) is not None, extra
    reg.write_text(json.dumps({"fences": [{
        **row, "open": True, "permit_clause": "commercial use is permitted with credit"}]}),
        "utf-8")
    assert tf.fence_for("bis_speeches/x.json", tf.load(reg)) is None


def test_one_predicate_answers_for_paths_and_seats() -> None:
    desk_intel = DESK / "data" / "intelligence"
    assert tf.path_fenced(desk_intel / "central_banks" / "bis_speech_tone.jsonl")
    assert tf.path_fenced(desk_intel / "central_banks" / "cb_tone_series.jsonl")   # built from BIS
    assert tf.path_fenced(ROOT / "data" / "intelligence" / "bis_speeches" / "d.json")
    assert tf.path_fenced(desk_intel / "central_banks" / "official_speech_tone.jsonl") is None
    assert tf.path_fenced(Path("somewhere") / "bis_speech_tone.jsonl") is None   # not a tree
    assert tf.seat_fenced("bis_speeches") and tf.seat_fenced("central_banks") is None


def test_every_reader_calls_the_shared_predicate_and_keeps_no_copy() -> None:
    sites = {"research/miner_candidate_compiler.py": "terms_fences.fence_for(",
             "research/deepening_worker.py": "terms_fences.fence_for(",
             "research/nlp_event_factors.py": "terms_fences.path_fenced(",
             "research/cb_tone_screen.py": "terms_fences.path_fenced(",
             "research/news_event_stream.py": "terms_fences.seat_fenced(",
             "research/evidence_router.py": "_terms_fences.seat_fenced(",
             "side_channels/bis_speech_tone.py": "terms_fences.seat_fenced(",
             "side_channels/seed_miners.py": "terms_fences.seat_fenced("}
    for rel, call in sites.items():
        src = (DESK / rel).read_text("utf-8")
        assert call in src, rel
        assert "noncommercial purposes" not in src or rel.endswith("bis_speech_tone.py"), rel


def test_the_bis_miner_does_not_fetch_and_says_why(tmp_path, monkeypatch) -> None:
    from side_channels import seed_miners as sm

    called: list[str] = []
    monkeypatch.setattr(sm, "MINERS", {"bis_speeches": lambda: called.append("bis") or [],
                                       "other": lambda: [sm.row("other", "x", "t")]})
    monkeypatch.setattr(sm, "SOURCE_WALLS", {})
    monkeypatch.setattr(sm, "INTEL", tmp_path)
    monkeypatch.setattr(sm, "STATE", tmp_path / "seed_miners_state.json")
    written: dict[str, list[dict]] = {}
    monkeypatch.setattr(sm, "_write_rows",
                        lambda name, rows, *a, **k: written.__setitem__(name, rows))
    sm.run_and_save()
    assert called == [] and "other" in written
    row = written["bis_speeches"][0]
    assert row["verdict"] == "TERMS_FENCED" and "noncommercial" in row["title"]


def test_the_deepening_replay_skips_fenced_files(tmp_path, monkeypatch) -> None:
    from research import deepening_worker as dw

    a = tmp_path / "intelligence"
    _write(a, "bis_speeches/discoveries_1.json", [{"title": "bis"}])
    keep = _write(a, "world/discoveries_1.json", [{"title": "other"}])
    monkeypatch.setattr(dw, "INTEL_ROOTS", (a,))
    assert dw._replay_paths() == [keep]


def test_a_registry_row_cannot_narrow_a_built_in_fence(tmp_path: Path) -> None:
    reg = tmp_path / "r.json"
    for row in ({"id": "bis_speeches", "match": []},
                {"id": "bis_speeches", "match": ["bis_speeches/only_this.json"], "seats": []},
                {"id": "bis_speeches", "match": "nonsense", "open": False},
                {"id": "bis_speeches"}):
        reg.write_text(json.dumps({"fences": [row]}), "utf-8")
        fences = tf.load(reg)
        assert tf.fence_for("bis_speeches/discoveries_1.json", fences), row
        assert tf.fence_for("central_banks/bis_speech_tone.jsonl", fences), row
        assert tf.fence_for("central_banks/cb_tone_series.jsonl", fences), row
        assert tf.seat_fenced("bis_speeches", fences), row
    reg.write_text(json.dumps({"fences": [{"id": "bis_speeches", "match": ["extra/*"]}]}),
                   "utf-8")
    assert tf.fence_for("extra/x.json", tf.load(reg))          # adding is allowed


def _congress_roster(tmp_path: Path) -> Path:
    from research import free_stack_hunter as fh
    doc = json.loads(fh.ROSTER.read_text("utf-8"))
    rows = [r for r in doc["sources"] if r.get("id") == "congress_trades"]
    assert rows, "the congress_trades roster row is still there, only fenced"
    path = tmp_path / "roster.json"
    path.write_text(json.dumps({**doc, "sources": rows}), "utf-8")
    return path


def test_congress_trades_is_fenced_by_default() -> None:
    fence = tf.seat_fenced("congress_trades")
    assert fence is not None and "13107" in fence["reason"]
    assert any(f["id"] == "congress_trades" for f in tf.BUILT_IN)


def test_the_free_stack_hunter_does_not_fetch_a_fenced_source(tmp_path, monkeypatch) -> None:
    from research import free_stack_hunter as fh

    def no_fetch(*_a, **_k):  # pragma: no cover - reaching it is the failure
        raise AssertionError("a fenced source was fetched")

    monkeypatch.setattr(fh, "run_source", no_fetch)
    store = fh.Store(tmp_path)
    fh.run(store=store, roster=_congress_roster(tmp_path), fetch=no_fetch,
           only=["congress_trades"], live=False)
    cursor = json.loads(store.cursor.read_text("utf-8"))
    assert cursor["congress_trades"]["last_status"] == "REFUSED_TERMS"
    assert cursor["congress_trades"]["missed_growth"]


def test_the_free_stack_proposer_mints_nothing_from_a_fenced_source(monkeypatch) -> None:
    from research import free_stack_proposer as fp
    monkeypatch.setattr(fp, "series_exists", lambda sid: True)
    columns = {"congress_trades": {"net_all": {"hypothesis": ["US500"]}},
               "other_src": {"x": {"hypothesis": ["US500"]}}}
    roster = {"congress_trades": {"id": "congress_trades"}, "other_src": {"id": "other_src"}}
    grid, skipped = fp.build_grid(columns, roster)
    assert "terms fence congress_trades" in skipped["congress_trades"]
    assert grid and all(r.get("evidence", {}).get("source_row") != "congress_trades"
                        for r in grid)


def _frame(path: Path, n: int = 60) -> None:
    """A real conditioner input: a PIT stamp and a signal column at an extreme."""
    lines = ["available_time,net_all"]
    lines += [f"2026-01-{1 + i // 24:02d}T{i % 24:02d}:00:00Z,{(i % 7) * 10.0}" for i in range(n)]
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _congress_roster_machine_use_true(tmp_path: Path) -> Path:
    """The money-path roster is no longer edited: its congress_trades row may say
    machine_use_allowed TRUE. The research-side fence must refuse it anyway."""
    path = _congress_roster(tmp_path)
    doc = json.loads(path.read_text("utf-8"))
    for r in doc["sources"]:
        r["machine_use_allowed"] = True
        r.pop("terms_note", None)
    path.write_text(json.dumps(doc), "utf-8")
    return path


def test_hunter_refuses_congress_even_when_the_roster_allows_machine_use(tmp_path,
                                                                         monkeypatch) -> None:
    from research import free_stack_hunter as fh

    def no_fetch(*_a, **_k):  # pragma: no cover - reaching it is the failure
        raise AssertionError("a fenced source was fetched")

    roster = _congress_roster_machine_use_true(tmp_path)
    row = fh.load_roster(roster)[0][0]
    assert row["machine_use_allowed"] is True and fh.access(row)["mined"]  # the roster says go
    monkeypatch.setattr(fh, "run_source", no_fetch)
    store = fh.Store(tmp_path)
    fh.run(store=store, roster=roster, fetch=no_fetch, only=["congress_trades"], live=False)
    st = json.loads(store.cursor.read_text("utf-8"))["congress_trades"]
    assert st["last_status"] == "REFUSED_TERMS" and "13107" in st["last_error"]


def test_proposer_mints_nothing_from_congress_whose_roster_row_allows_machine_use(
        tmp_path, monkeypatch) -> None:
    from research import free_stack_proposer as fp
    roster_doc = json.loads(_congress_roster_machine_use_true(tmp_path).read_text("utf-8"))
    roster = {r["id"]: r for r in roster_doc["sources"]}
    assert roster["congress_trades"]["machine_use_allowed"] is True
    monkeypatch.setattr(fp, "series_exists", lambda sid: True)
    grid, skipped = fp.build_grid({"congress_trades": {"net_all": {"hypothesis": ["US500"]}}},
                                  roster)
    assert grid == [] and "terms fence congress_trades" in skipped["congress_trades"]


def test_compiler_donates_nothing_from_congress_harvests(roots) -> None:
    a, b = roots
    p1 = _write(a, "congress_trades/discoveries_1.json", [{"title": "congress buy"}])
    p2 = _write(b, "free_stack/congress_trades_net.jsonl", [{"title": "congress net"}])
    _write(a, "world/discoveries_1.json", [{"title": "other", "symbol": "XAUUSD"}])
    assert _titles() == {"other"}
    parked = mc._LAST_INTAKE["terms_fenced"]["congress_trades"]
    assert parked["files_parked"] == 2 and "13107" in parked["reason"]
    assert p1.exists() and p2.exists()


def test_the_registry_carries_congress_with_its_statute() -> None:
    doc = json.loads(tf.REGISTRY.read_text("utf-8"))
    row = next(f for f in doc["fences"] if f["id"] == "congress_trades")
    assert "13107(c)" in row["reason"] and row["open"] is False and not row["permit_clause"]
    assert "congress_trades" in row["seats"] and row["missed_growth"]


def _sweep_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    series = tmp_path / "lake" / "series"
    series.mkdir(parents=True)
    return series, tmp_path / "quarantine", tmp_path / "quarantine.jsonl"


def test_sweep_moves_fenced_frames_only_keeping_bytes_and_sha(tmp_path) -> None:
    import hashlib
    from datetime import UTC, datetime
    series, q, ledger = _sweep_dirs(tmp_path)
    _frame(series / "fs_congress_trades.csv")
    (series / "fs_congress_trades.parquet").write_bytes(b"PAR1-not-really")
    _frame(series / "fs_other_src.csv")
    _frame(series / "congress_trades.csv")                    # not an fs_ frame: untouched
    (series / "fs_congress_trades.txt").write_text("x", "utf-8")  # not a frame: untouched
    before = {p.name: (p.read_bytes(), hashlib.sha256(p.read_bytes()).hexdigest())
              for p in series.glob("fs_congress_trades.*") if p.suffix in (".csv", ".parquet")}
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    lines = tf.quarantine_fenced_frames(series, q, ledger, now)
    assert sorted(Path(x["path"]).name for x in lines) == sorted(before)
    assert sorted(p.name for p in series.iterdir()) == [
        "congress_trades.csv", "fs_congress_trades.txt", "fs_other_src.csv"]
    for x in lines:
        dest = Path(x["quarantined_to"])
        assert dest.parent == q and dest.exists()
        raw, sha = before[Path(x["path"]).name]
        assert dest.read_bytes() == raw and x["sha256"] == sha
        assert x["fence"] == "congress_trades" and "13107" in x["reason"]
        assert x["at_utc"].startswith("2026-11-11T12:00:00")
    on_disk = [json.loads(s) for s in ledger.read_text("utf-8").splitlines()]
    assert on_disk == lines
    csv_line = next(x for x in lines if x["path"].endswith(".csv"))
    assert "exogenous_conditioner:fs_congress_trades" in csv_line["missed_growth"][
        "arms_lost_input"]
    assert "exogenous_conditioner:fs_congress_trades:net_all" in csv_line["missed_growth"][
        "arms_lost_input"]


def test_sweep_is_idempotent_and_never_overwrites(tmp_path) -> None:
    series, q, ledger = _sweep_dirs(tmp_path)
    _frame(series / "fs_congress_trades.csv")
    assert len(tf.quarantine_fenced_frames(series, q, ledger)) == 1
    size = ledger.stat().st_size
    assert tf.quarantine_fenced_frames(series, q, ledger) == []      # second run: nothing
    assert ledger.stat().st_size == size
    # the hunter republishes a frame before the fence was noticed: both copies are kept
    (series / "fs_congress_trades.csv").write_text("available_time,net_all\nnew,1\n", "utf-8")
    lines = tf.quarantine_fenced_frames(series, q, ledger)
    assert len(lines) == 1
    assert Path(lines[0]["quarantined_to"]).name == "fs_congress_trades.q1.csv"
    assert sorted(p.name for p in q.iterdir()) == ["fs_congress_trades.csv",
                                                   "fs_congress_trades.q1.csv"]
    assert "new,1" in (q / "fs_congress_trades.q1.csv").read_text("utf-8")
    assert len(ledger.read_text("utf-8").splitlines()) == 2


def test_sweep_on_a_missing_series_dir_does_nothing(tmp_path) -> None:
    assert tf.quarantine_fenced_frames(tmp_path / "nope", tmp_path / "q",
                                       tmp_path / "l.jsonl") == []
    assert not (tmp_path / "q").exists() and not (tmp_path / "l.jsonl").exists()


def test_the_default_sweep_paths_are_outside_the_series_dir_and_gitignored() -> None:
    import subprocess

    from mt5desk import family_exogenous_conditioner as fec
    assert tf.SERIES_DIR == fec.SERIES_DIR
    assert fec.SERIES_DIR not in tf.QUARANTINE_DIR.parents
    for p in (tf.QUARANTINE_DIR / "fs_congress_trades.parquet", tf.QUARANTINE_LEDGER):
        r = subprocess.run(["git", "check-ignore", "-q", str(p)], cwd=ROOT, check=False)
        assert r.returncode in (0, 128), p                  # 128: not a git checkout
        if r.returncode == 128:
            break


def test_the_hunter_sweeps_before_it_reads_anything(tmp_path, monkeypatch) -> None:
    from research import free_stack_hunter as fh
    store = fh.Store(tmp_path)
    store.series.mkdir(parents=True)
    _frame(store.series / "fs_congress_trades.csv")
    _frame(store.series / "fs_other_src.csv")
    order: list[str] = []
    real = fh.load_roster
    monkeypatch.setattr(fh, "load_roster", lambda *a, **k: (
        order.append("roster" if not (store.series / "fs_congress_trades.csv").exists()
                     else "roster-before-sweep"), real(*a, **k))[1])
    rep = fh.run(store=store, roster=_congress_roster_machine_use_true(tmp_path),
                 fetch=lambda *a, **k: None, only=["congress_trades"], live=False)
    assert order == ["roster"]
    assert rep["terms_quarantine"]["moved_this_pass"] == 1
    assert (store.root / "terms_quarantine" / "fs_congress_trades.csv").exists()
    assert (store.series / "fs_other_src.csv").exists()


def test_the_proposer_sweeps_at_the_start_of_its_pass(tmp_path, monkeypatch) -> None:
    from research import free_stack_proposer as fp
    series, q, ledger = _sweep_dirs(tmp_path)
    _frame(series / "fs_congress_trades.csv")
    monkeypatch.setattr(fp, "SERIES", series)
    # the proposer imports the package path, which is a different module object from `tf`
    monkeypatch.setattr(fp.terms_fences, "QUARANTINE_DIR", q)
    monkeypatch.setattr(fp.terms_fences, "QUARANTINE_LEDGER", ledger)
    monkeypatch.setattr(fp, "COLUMNS", tmp_path / "columns.json")    # absent: NO_COLUMNS
    monkeypatch.setattr(fp, "REPORT", tmp_path / "report.json")
    assert fp.main(["--once", "--dry-run"]) == 0
    doc = json.loads((tmp_path / "report.json").read_text("utf-8"))
    assert doc["terms_quarantine"]["moved_this_pass"] == 1
    assert not (series / "fs_congress_trades.csv").exists() and (q / "fs_congress_trades.csv"
                                                                 ).exists()


def test_the_conditioner_reads_unmeasured_once_the_frame_is_quarantined(tmp_path) -> None:
    """The money-path conditioner is NOT edited: it reads the series dir by name. After the sweep
    the fenced frame is absent, and absence is UNMEASURED -- no crash, no zero signal, nothing."""
    import pandas as pd
    from mt5desk import family_exogenous_conditioner as fec
    series, q, ledger = _sweep_dirs(tmp_path)
    _frame(series / "fs_congress_trades.csv", n=24 * 20)
    _frame(series / "fs_other_src.csv", n=24 * 20)
    assert fec.conditioner("fs_congress_trades", "net_all", "delta", root=series) is not None
    tf.quarantine_fenced_frames(series, q, ledger)
    assert fec.series_path("fs_congress_trades", series) is None
    assert fec.conditioner("fs_congress_trades", "net_all", "delta", root=series) is None
    assert fec.conditioner("fs_other_src", "net_all", "delta", root=series) is not None
    idx = pd.date_range("2026-01-01", periods=24 * 30, freq="h", tz="UTC")
    bars = pd.DataFrame({"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.0}, index=idx)
    assert fec.family_exogenous_conditioner(
        bars, source="fs_congress_trades", signal="net_all", transform="delta",
        threshold=0.0, series_root=series) == []


def test_alt_state_does_not_publish_a_fenced_source(tmp_path, monkeypatch) -> None:
    from datetime import UTC, datetime

    from research import free_stack_hunter as fh
    read: list[str] = []
    monkeypatch.setattr(fh, "first_vintage_frame", lambda p: read.append(p.stem))
    fh.build_alt_state(fh.Store(tmp_path), {"congress_trades": {"net_all": {}},
                                            "other_src": {"x": {}}}, datetime.now(UTC))
    assert read == ["other_src"]


def test_the_default_fences_are_cached_and_reread_on_change(tmp_path, monkeypatch) -> None:
    import os
    reg = tmp_path / "terms_fences.json"
    reg.write_text(json.dumps({"fences": []}), "utf-8")
    monkeypatch.setattr(tf, "REGISTRY", reg)
    monkeypatch.setattr(tf, "_CACHE", {"key": None, "fences": None})
    calls: list[int] = []
    real = tf.load
    monkeypatch.setattr(tf, "load", lambda *a, **k: calls.append(1) or real(*a, **k))
    for _ in range(5):
        assert tf.seat_fenced("congress_trades") is not None  # built-in, registry empty
    assert len(calls) == 1
    reg.write_text(json.dumps({"fences": [{"id": "x", "match": [], "seats": ["newseat"]}]}),
                   "utf-8")
    st = reg.stat()
    os.utime(reg, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert tf.seat_fenced("newseat") is not None
    assert len(calls) == 2
