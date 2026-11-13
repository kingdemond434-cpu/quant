"""Conversion debt: every unconverted mined row is typed, and the fetchable part reaches the
world crawler -- on hosts its frontier already holds, and nowhere else."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK / "side_channels"), str(DESK),
           str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conversion_debt as cd  # noqa: E402
import world_crawler as wc  # noqa: E402
import world_frontier as wf  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _task(source: str, disposition: str, url: str = "", title: str = "t", **kw: object) -> dict:
    return {"source": source, "disposition": disposition, "url": url, "title": title, **kw}


def _fixture(tmp_path: Path, tasks: list[dict], worked: list[dict],
             frontier: dict | None) -> dict[str, Path]:
    q = tmp_path / "queue.json"
    q.write_text(json.dumps({"built_at": "2026-11-10T11:00:00+00:00", "tasks": tasks}), "utf-8")
    w = tmp_path / "worked.jsonl"
    w.write_text("".join(json.dumps(r) + "\n" for r in worked), "utf-8")
    f = tmp_path / "frontier.json"
    if frontier is not None:
        f.write_text(json.dumps({"sources": frontier}), "utf-8")
    return {"queue": q, "worked": w, "frontier_path": f, "backlog": tmp_path / "absent.json"}


def test_each_label_maps_to_the_class_it_owes() -> None:
    assert cd.classify_queue({"disposition": "EMPTY_CAPTURE"}) == "NEEDS_DATA"
    assert cd.classify_queue({"disposition": "NEEDS_EXACT_RULE_EXTRACTION"}) == "NEEDS_RULE"
    assert cd.classify_queue({"disposition": "NEEDS_SYMBOL_EXTRACTION"}) == "NEEDS_RULE"
    assert cd.classify_queue({"disposition": "OPERATIONAL_ROW"}) == "NONE"
    assert cd.classify_queue({"disposition": "SOMETHING_NEW"}) == "UNCLASSIFIED"
    assert cd.classify_worked("REFUSED_NO_BODY_CAPTURED: the miner captured a LINK") == "NEEDS_DATA"
    assert cd.classify_worked("RECOVERED_TEXT_EXTRACTED", 2) == "NONE"
    assert cd.classify_worked("REFUSED_BANNED_FAMILY: x") == "NONE"
    assert cd.classify_worked("BLOCKED_SEAT_UNAVAILABLE: no seat") == "NEEDS_RULE"
    assert cd.classify_worked("RULE_BASED_NO_MATCH: nothing") == "NEEDS_RULE"


def test_task_identity_is_the_deepening_workers() -> None:
    import hashlib
    assert cd.task_id("s", "https://a/b", "T") == hashlib.sha256(
        b"s|https://a/b|T").hexdigest()[:16]


def test_pit_is_owed_only_without_a_producer_stamp() -> None:
    assert cd.needs_pit({"retrieved_at": "x", "retrieved_at_basis": "artifact_mtime"}) is True
    assert cd.needs_pit({"retrieved_at_basis": ""}) is True
    assert cd.needs_pit({"retrieved_at": "x", "retrieved_at_basis": "row:retrieved_at"}) is False
    # A task queued by a build that wrote no basis cannot say: UNMEASURED, never assumed clean.
    assert cd.needs_pit({"retrieved_at": "2026-11-01T00:00:00+00:00"}) is None
    assert cd.needs_pit({}) is True


def test_debt_is_typed_routed_and_offered_oldest_first(tmp_path: Path) -> None:
    tasks = [
        _task("fx_forum", "EMPTY_CAPTURE", "https://known.example/a", "A",
              retrieved_at="2026-11-09T00:00:00+00:00", retrieved_at_basis="artifact_mtime"),
        _task("fx_forum", "EMPTY_CAPTURE", "https://known.example/done", "D",
              retrieved_at="2026-11-01T00:00:00+00:00", retrieved_at_basis="row:retrieved_at"),
        _task("fx_forum", "EMPTY_CAPTURE", "https://stranger.example/x", "X",
              retrieved_at="2026-11-09T00:00:00+00:00", retrieved_at_basis="row:retrieved_at"),
        _task("seat", "EMPTY_CAPTURE", "", "no address",
              retrieved_at_basis="row:published"),
        _task("blog", "NEEDS_EXACT_RULE_EXTRACTION", "https://known.example/r", "R",
              retrieved_at="2026-11-09T00:00:00+00:00", retrieved_at_basis="row:published"),
        _task("ops", "OPERATIONAL_ROW", "https://known.example/o", "O"),
    ]
    worked = [
        # An old refusal no longer in the queue: still NEEDS_DATA, still offered, and older.
        {"id": "aaaa", "at": "2026-10-01T00:00:00+00:00", "source": "old_miner",
         "url": "https://known.example/old",
         "disposition": "REFUSED_NO_BODY_CAPTURED: the miner captured a LINK"},
        # A row that was blocked and later recovered owes nothing: the latest decision wins.
        {"id": "bbbb", "at": "2026-10-01T00:00:00+00:00", "source": "m", "url": "",
         "disposition": "BLOCKED_SEAT_UNAVAILABLE: no seat"},
        {"id": "bbbb", "at": "2026-10-02T00:00:00+00:00", "source": "m", "url": "",
         "disposition": "RECOVERED_TEXT_EXTRACTED", "n_candidates": 1},
    ]
    frontier = {
        "https://known.example/": {"url": "https://known.example/", "host": "known.example",
                                   "fetches": 3, "last_fetched": "2026-11-10T00:00:00+00:00"},
        "https://known.example/done": {"url": "https://known.example/done",
                                       "host": "known.example", "fetches": 1,
                                       "last_fetched": "2026-11-05T00:00:00+00:00"},
    }
    report, seeds = cd.build(now=NOW, **_fixture(tmp_path, tasks, worked, frontier))
    assert report["status"] == "OK"
    assert report["debt"]["NEEDS_DATA"]["rows"] == 5
    assert report["debt"]["NEEDS_RULE"]["rows"] == 1
    assert report["debt"]["NEEDS_PIT"]["rows"] == 1            # only the mtime-stamped row
    assert report["rows_owing_nothing"] == 2                   # operational + recovered
    drive = report["drive"]
    assert drive["NEEDS_DATA"] == {"OFFERED": 2, "RECAPTURED": 1, "UNROUTED_HOST": 1, "NO_URL": 1}
    assert drive["unrouted_hosts"] == [{"host": "stranger.example", "rows": 1}]
    assert drive["no_url_owed_by_source"] == [{"source": "seat", "rows": 1}]
    assert drive["undriven_needs_data_rows"] == 2
    assert drive["NEEDS_RULE"]["status"] == "UNMEASURED"       # no backlog artifact here
    # Oldest debt first, and never a host the frontier does not hold.
    assert seeds["urls"] == ["https://known.example/old", "https://known.example/a"]
    assert all("stranger" not in u for u in seeds["urls"])


def test_no_frontier_is_unmeasured_and_offers_nothing(tmp_path: Path) -> None:
    tasks = [_task("m", "EMPTY_CAPTURE", "https://known.example/a",
                   retrieved_at_basis="row:published")]
    report, seeds = cd.build(now=NOW, **_fixture(tmp_path, tasks, [], None))
    assert report["inputs"]["frontier"]["status"] == "UNMEASURED"
    assert report["drive"]["NEEDS_DATA"] == {"UNMEASURED": 1}
    assert seeds["urls"] == []
    assert report["drive"]["undriven_needs_data_rows"] == 1


def test_absent_inputs_are_unmeasured_not_zero_debt(tmp_path: Path) -> None:
    report, seeds = cd.build(now=NOW, queue=tmp_path / "q.json", worked=tmp_path / "w.jsonl",
                             frontier_path=tmp_path / "f.json", backlog=tmp_path / "b.json")
    assert report["status"] == "UNMEASURED"
    assert seeds["urls"] == []


def test_crawler_takes_debt_seeds_only_on_hosts_it_holds(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    urls = ([f"https://known.example/p{i}" for i in range(wc.DEBT_SEEDS_PER_RUN + 20)]
            + ["https://stranger.example/x", "ftp://known.example/y", "https://known.example/"])
    (tmp_path / "data" / "hypotheses" / "conversion_debt_seeds.json").write_text(
        json.dumps({"urls": urls}), "utf-8")
    monkeypatch.setattr(wc, "BASE", tmp_path)
    sources = {"https://known.example/": wf.Source(url="https://known.example/")}
    got = wc.conversion_debt_seeds(sources)
    assert len(got) == wc.DEBT_SEEDS_PER_RUN                    # the per-run cap binds
    assert got[0] == "https://known.example/p0"                # the file's order is kept
    assert all(u.startswith("https://known.example/p") for u in got)
    # At the frontier cap the debt adds nothing.
    monkeypatch.setattr(wc, "MAX_FRONTIER", len(sources))
    assert wc.conversion_debt_seeds(sources) == ()


def test_crawler_runs_without_a_seeds_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(wc, "BASE", tmp_path)
    assert wc.conversion_debt_seeds({}) == ()
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    (tmp_path / "data" / "hypotheses" / "conversion_debt_seeds.json").write_text("{not json")
    assert wc.conversion_debt_seeds({}) == ()


def test_main_writes_both_artifacts(tmp_path: Path, monkeypatch) -> None:
    fx = _fixture(tmp_path, [_task("m", "EMPTY_CAPTURE", "https://known.example/a",
                                   retrieved_at_basis="row:published")], [],
                  {"https://known.example/": {"host": "known.example", "fetches": 1}})
    monkeypatch.setattr(cd, "QUEUE", fx["queue"])
    monkeypatch.setattr(cd, "WORKED", fx["worked"])
    monkeypatch.setattr(cd, "FRONTIER", fx["frontier_path"])
    monkeypatch.setattr(cd, "BACKLOG", fx["backlog"])
    monkeypatch.setattr(cd, "OUT", tmp_path / "out" / "CONVERSION_DEBT.json")
    monkeypatch.setattr(cd, "SEEDS", tmp_path / "out" / "seeds.json")
    assert cd.main(["--budget-s", "30"]) == 0
    assert json.loads(cd.SEEDS.read_text("utf-8"))["urls"] == ["https://known.example/a"]
    assert json.loads(cd.OUT.read_text("utf-8"))["drive"]["seeds_offered"] == 1
    cd.OUT.unlink()
    assert cd.main(["--dry-run"]) == 0 and not cd.OUT.exists()
