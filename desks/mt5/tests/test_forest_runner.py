"""The forest runner: eleven agents in parallel, one failing role costing the other ten nothing,
the scout floor under a one-worker allocation, absent packs named, and every write deduped."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import dedup_chain as dc  # noqa: E402
from libs.research import forests as F  # noqa: E402
from research import forest_runner as fr  # noqa: E402


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A registry in tmp_path, restored from nothing -- the fixture pattern of
    tests/moat/test_registry.py, so no test here can touch the desk's own store."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(fr, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(fr, "AXES", tmp_path / "axes")
    monkeypatch.setattr(fr, "RUNS_JSONL", tmp_path / "forest_runs.jsonl")
    yield tmp_path
    R.set_path(None)


def _fake_roles(monkeypatch: pytest.MonkeyPatch, **overrides):
    """Replace the eleven agents with fakes that record when they ran, on which thread."""
    seen: dict[str, dict] = {}

    def make(role: str):
        def fn(run: fr.Run, res: fr.RoleResult, budget_s: float) -> None:
            seen[role] = {"thread": threading.current_thread().name, "budget_s": budget_s,
                          "at": time.monotonic()}
            res.why = f"fake {role}"
            res.new += 1
        return fn

    table = {role: overrides.get(role) or make(role) for role in F.ROLES}
    monkeypatch.setattr(fr, "ROLE_FUNCS", table)
    return seen


def test_all_eleven_roles_run_in_one_pass_each_with_its_own_budget(reg, monkeypatch):
    seen = _fake_roles(monkeypatch)
    doc = fr.run_pass("korea", budget_s=110, workers=4)
    assert set(seen) == set(F.ROLES)
    assert doc["n_roles_ran"] == 11 and doc["n_roles_failed"] == 0
    assert {r["role"] for r in doc["roles"]} == set(F.ROLES)
    assert all(v["budget_s"] >= F.MIN_ROLE_S for v in seen.values())
    assert doc["forest"] == "korea" and doc["task"] == "MT5-Forest-Korea"
    assert doc["totals"]["new"] == 11
    assert len({v["thread"] for v in seen.values()}) > 1, "the roles run in PARALLEL"


def test_one_failing_role_never_stops_the_forest(reg, monkeypatch):
    def boom(run, res, budget_s):
        raise RuntimeError("the academic ground is on fire")

    seen = _fake_roles(monkeypatch, academic=boom)
    doc = fr.run_pass("china", budget_s=110, workers=4)
    rows = {r["role"]: r for r in doc["roles"]}
    assert rows["academic"]["ran"] is False
    assert "RuntimeError" in rows["academic"]["why"] and "on fire" in rows["academic"]["why"]
    assert rows["academic"]["unmeasured"], "a failed role is UNMEASURED, named, not silent"
    assert doc["n_roles_ran"] == 10 and doc["n_roles_failed"] == 1
    assert set(seen) == set(F.ROLES) - {"academic"}
    assert doc["totals"]["new"] == 10


def test_a_one_worker_allocation_still_scouts_first(reg, monkeypatch):
    order: list[str] = []
    lock = threading.Lock()

    def make(role: str):
        def fn(run, res, budget_s):
            with lock:
                order.append(role)
            res.why = role
        return fn

    monkeypatch.setattr(fr, "ROLE_FUNCS", {role: make(role) for role in F.ROLES})
    alloc = F.Allocation(forest="africa", workers=1, budget_s=110, scout_floor=True,
                         roi=0.0, why="no survivor yet")
    doc = fr.run_pass("africa", allocation=alloc)
    assert doc["allocation"]["workers"] == 1
    assert order[0] == F.SCOUT_ROLE, "a forest cut to one worker still scouts before anything"
    assert doc["plan"][0]["role"] == F.SCOUT_ROLE
    assert len(order) == 11


def test_the_scout_runs_even_when_the_caller_asks_for_other_roles_only(reg, monkeypatch):
    seen = _fake_roles(monkeypatch)
    doc = fr.run_pass("mena", budget_s=60, workers=2, roles=["failure_miners"])
    assert set(seen) == {F.SCOUT_ROLE, "failure_miners"}, "the scout floor is a law, not a knob"
    assert {r["role"] for r in doc["roles"]} == {F.SCOUT_ROLE, "failure_miners"}


def test_a_forest_with_no_pack_names_what_is_missing_and_is_never_idle(reg):
    doc = fr.run_pass("north_america", budget_s=60, workers=4, dry_run=True)
    rows = {r["role"]: r for r in doc["roles"]}
    assert len(rows) == 11
    assert rows[F.SCOUT_ROLE]["ran"] is True
    assert rows[F.SCOUT_ROLE]["new"] >= 1, "the scout works from the mandate's own terms"
    seeded = rows[F.SCOUT_ROLE]["seeded_by"]
    assert seeded, "the scout names what seeded it: polyglot, a pack, or the mandate"
    assert not any(s.startswith("country_lab") for s in seeded), "no pack to seed from"
    official = json.dumps(rows["official_data"])
    assert F.UNMEASURED in official and "country pack" in official
    failure = json.dumps(rows["failure_miners"])
    assert F.UNMEASURED in failure
    assert doc["unmeasured"], "absence is reported by name, never as a clean zero"
    assert all(u.get("why") for u in doc["unmeasured"])


def test_dry_run_writes_nothing_at_all(reg, monkeypatch):
    _fake_roles(monkeypatch)
    doc = fr.run_pass("latam", budget_s=60, workers=3, dry_run=True)
    assert doc["dry_run"] is True
    assert not (fr.REPORTS / "FOREST_LATAM.json").exists()
    assert not fr.RUNS_JSONL.exists()
    assert not fr.AXES.exists()
    assert R.counts()["discoveries"] == 0, "a dry run leaves no row in the registry"
    assert R.counts()["provenance"] == 0


def test_a_wet_run_publishes_its_report_and_appends_the_run_ledger(reg, monkeypatch):
    _fake_roles(monkeypatch)
    fr.run_pass("oceania", budget_s=60, workers=3)
    report = json.loads((fr.REPORTS / "FOREST_OCEANIA.json").read_text("utf-8"))
    assert report["forest"] == "oceania" and report["task"] == "MT5-Forest-Oceania"
    for row in report["roles"]:
        assert set(row) >= {"role", "ran", "seconds", "new", "duplicates", "descendants",
                            "unmeasured", "why"}
    assert report["dedup"]["thresholds"]["shingle_k"] == dc.SHINGLE_K
    lines = fr.RUNS_JSONL.read_text("utf-8").strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["forest"] == "oceania"
    fr.run_pass("oceania", budget_s=60, workers=3)
    assert len(fr.RUNS_JSONL.read_text("utf-8").strip().splitlines()) == 2


def test_every_write_passes_through_the_dedup_chain_first(reg, monkeypatch):
    calls: list[str] = []
    real = dc.dedup

    def spy(item, view):
        calls.append(item.item_id)
        return real(item, view)

    monkeypatch.setattr(fr.dc, "dedup", spy)
    recorded: list[tuple] = []
    real_record = R.record_discovery

    def watch(**kw):
        recorded.append((kw.get("source_id"), kw.get("mechanism")))
        return real_record(**kw)

    monkeypatch.setattr(fr.reg, "record_discovery", watch)

    def one(run, res, budget_s):
        for _ in range(3):                      # the same finding, offered three times
            fr.record(run, res, source_id="s:a", source_type="t", mechanism="gold into the fix",
                      url="https://a.example/1", title="fix", text="gold rallies into the fix",
                      instruments=["XAUUSD"], condition="london fix")

    monkeypatch.setattr(fr, "ROLE_FUNCS", {**{r: lambda *a: None for r in F.ROLES},
                                           "practitioner": one})
    doc = fr.run_pass("europe", budget_s=60, workers=2)
    assert len(calls) == 3, "the chain judged every offered write, not just the first"
    assert len(recorded) == 1, "two of three writes never reached the registry"
    row = {r["role"]: r for r in doc["roles"]}["practitioner"]
    assert row["new"] == 1 and row["duplicates"] == 2
    assert doc["totals"]["provenance_edges"] == 2, "a duplicate adds an EDGE, never a row"
    assert R.counts()["discoveries"] == 1


def test_a_descendant_is_admitted_and_carries_its_ancestor(reg, monkeypatch):
    def one(run, res, budget_s):
        anc = fr.record(run, res, source_id="s:a", source_type="t", mechanism="gold at the fix",
                        title="gold", text="gold rallies into the london pm fix at month end",
                        instruments=["XAUUSD"], condition="london fix", horizon="intraday")
        fr.record(run, res, source_id="s:b", source_type="t", mechanism="silver, one day early",
                  title="silver", text="the same month end rebalance reaches silver a day early",
                  instruments=["XAGUSD"], condition="london fix", horizon="multi_day",
                  parents=[anc])

    monkeypatch.setattr(fr, "ROLE_FUNCS", {**{r: lambda *a: None for r in F.ROLES},
                                           "practitioner": one})
    doc = fr.run_pass("asean", budget_s=60, workers=2)
    row = {r["role"]: r for r in doc["roles"]}["practitioner"]
    assert row["new"] == 1 and row["descendants"] == 1
    assert R.counts()["discoveries"] == 2, "a descendant branches and is tested on its own"
    conn = R.connect()
    try:
        edges = [dict(e) for e in conn.execute("SELECT * FROM provenance").fetchall()]
    finally:
        conn.close()
    assert any(e["relation"] in ("derived", "descendant") for e in edges)


def test_a_technique_is_recorded_with_a_method_spec(reg, monkeypatch):
    def one(run, res, budget_s):
        fr.record_technique(run, res, name="crowding_from_retail_board_slang",
                            source_class="retail_ecology boards in the local language",
                            procedure="count native slang terms for forced exits per week",
                            representation="weekly z-score per instrument")

    monkeypatch.setattr(fr, "ROLE_FUNCS", {**{r: lambda *a: None for r in F.ROLES},
                                           "source_scouts": one})
    doc = fr.run_pass("korea", budget_s=60, workers=2)
    assert doc["totals"]["techniques"] == 1
    spec = doc["techniques"][0]
    assert set(spec) == {"technique", "source_class", "extraction_procedure", "representation",
                         "region", "languages"}
    assert spec["region"] == "korea" and spec["languages"] == ["ko"]
    rows = R.discoveries(limit=10)
    assert any("TECHNIQUE" in str(r["mechanism"]) for r in rows)


def test_the_runner_names_the_boundary_it_keeps(reg, monkeypatch):
    _fake_roles(monkeypatch)
    doc = fr.run_pass("russia_cis", budget_s=60, workers=2, dry_run=True)
    # LAWS 5e (2026-09-23): the boundary the runner names changed from "a ground whose machine
    # use is not allowed is registered and never fetched" to "every registered ground is MINED
    # with its terms/robots note carried as a routing label". The five acts are what is left.
    assert "opens no socket" in doc["boundary"] and "routing label" in doc["boundary"]
    assert "MINED" in doc["boundary"] and "secret" in doc["boundary"]
    assert "never fetched" not in doc["boundary"]
    assert "HARD_BOUNDARY" in doc["boundary"]
    assert doc["department"] == "forest_russia_cis" and doc["leg"] == "forest_russia_cis"


def test_cli_lists_the_federation_and_refuses_an_unknown_forest(capsys):
    assert fr.main(["--list"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["n_forests"] == 17
    assert fr.main(["--forest", "atlantis", "--once"]) == 2
