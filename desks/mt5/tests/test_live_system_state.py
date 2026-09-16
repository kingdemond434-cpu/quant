"""The canonical join: one document, and every fact in it traceable to the file that owns it.

These pin the properties that make LIVE_SYSTEM_STATE.json worth reading at all:

  * with EVERY source absent the document is still written, and every section says UNMEASURED
    rather than zero, empty or False -- an absent input is a verdict, never a default (L1.28a);
  * with the sources present each fact lands in the section that owns it, and nothing the desk
    actually publishes is silently dropped;
  * `running_matches_sealed` is True/False only when BOTH shas are known, and None otherwise --
    a missing git is not evidence that the box is running the sealed release;
  * the provenance hashes are stable across two passes over identical inputs and move the moment
    an input moves, so two documents can be compared without re-reading the box;
  * `diff_since_previous` notices the live sleeve set changing, which is the one change that
    means the account is now trading something different;
  * git that cannot run is UNMEASURED, not a crash and not a clean tree.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import live_system_state as lss  # noqa: E402

#: Captured before any fixture swaps it out, so the git-is-broken test can exercise the real one.
_REAL_GIT = lss._git

NOW = datetime(2026, 9, 16, 18, 0, 0, tzinfo=UTC)
HEAD = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
SEALED = "1eba97937191820024aec61b296fb37413ef77d2"
SECTIONS = ("release", "risk", "sleeves", "allocator", "promotion", "execution", "attestation",
            "e8", "box")


def _fake_git(state: dict[str, Any]):
    def _run(*args: str) -> str | None:
        if args[:2] == ("rev-parse", "HEAD"):
            return state["head"]
        if args[0] == "rev-parse":
            return state["branch"]
        if args[0] == "status":
            return state["porcelain"]
        return None
    return _run


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Every path constant redirected into tmp_path: the live desk is never read or written."""
    data = tmp_path / "desk" / "data"
    reports = tmp_path / "desk" / "reports"
    shadow = reports / "shadow"
    arch = data / "architecture"
    for folder in (data, reports, shadow, arch, tmp_path / "reports", tmp_path / "data"):
        folder.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Any] = {
        "RELEASE_IDENTITY": data / "release_identity.json",
        "RELEASE_PATHS": (data / "RELEASE.json", tmp_path / "RELEASE.json"),
        "GATEWAY_STATE": data / "gateway_state.json",
        "SLEEVES": data / "sleeves.json",
        "PF_ALLOCATION": reports / "pf_allocation.json",
        "ALLOCATOR_PROOF_PATHS": (tmp_path / "reports" / "ALLOCATOR_PROOF.json",
                                  reports / "ALLOCATOR_PROOF.json"),
        "SYNC_MARKER": data / "sync_marker.json",
        "STALL_WATCH": data / "stall_watch.json",
        "BANNED_FAMILIES": data / "banned_families.json",
        "FORWARD_RECONCILE": data / "forward_reconcile.json",
        "SHADOW_STATE": shadow / "shadow_state.json",
        "LIVE_LEDGER": data / "live_ledger.jsonl",
        "GATE_ATTESTATION_PATHS": (data / "gate_attestation.json",
                                   tmp_path / "data" / "gate_attestation.json"),
        "CLOSED_LOOP": arch / "closed_loop_attestation.json",
        "E8_ARMED": data / "E8_GOLD_ARMED",
        "E8_GOLD": reports / "E8_GOLD.json",
        "OUT": data / "LIVE_SYSTEM_STATE.json",
    }
    for name, value in paths.items():
        monkeypatch.setattr(lss, name, value)
    git = {"head": HEAD, "branch": "claude/llm-auto-upgrade-verify-gcjac3", "porcelain": ""}
    monkeypatch.setattr(lss, "_git", _fake_git(git))
    monkeypatch.setattr(lss, "_now", lambda: NOW)
    return SimpleNamespace(paths=paths, git=git, tmp=tmp_path)


def _put(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def _populate(desk: SimpleNamespace) -> None:
    """One minimal, shape-faithful copy of each of the sixteen inputs."""
    recent = (NOW - timedelta(hours=1)).isoformat(timespec="seconds")
    _put(lss.RELEASE_IDENTITY, {"ok": False, "running_sha": HEAD, "release_sha": SEALED,
                                "verdict": "REFUSED", "allows_new_risk": False, "stale": False,
                                "at": recent, "tested_sha": "UNMEASURED",
                                "changed_paths": ["a.py", "b.py"], "drift": ["a.py"],
                                "reason": "x" * 400, "release_id": "d3624c6a6799"})
    _put(lss.RELEASE_PATHS[0], {"generated_utc": recent, "live_sha": SEALED, "code_sha": SEALED,
                                "tree_sha": "9da22e", "money_path_hash": "70428d",
                                "data_schema_version": "pit-1", "money_path": ["a", "b", "c"]})
    _put(lss.GATEWAY_STATE, {"armed": True, "equity": 557.09, "lot": 0.06,
                             "position": [{"ticket": 1}, {"ticket": 2}], "pending": [{"t": 3}],
                             "last_bracket_date": "2026-09-16", "placement_pass": recent,
                             "last_reconcile": recent, "bracket_cancelled": True,
                             "daily_loss_cap": 0.02})
    _put(lss.SLEEVES, {"sleeves": [
        {"name": "gold_asia", "family": "session_bracket", "symbol": "XAUUSD",
         "timeframe": "H1", "session": "asia", "risk_frac": 0.015246, "lot": "auto_ramp",
         "status": "LIVE"},
        {"name": "chfnok_carry_asia", "family": "carry", "symbol": "CHFNOK", "risk_frac": 0.04,
         "status": "STANDBY"},
        {"name": "eurgbp_discovered", "family": "discovered", "symbol": "EURGBP",
         "risk_frac": 0.0, "status": "RETIRED"}]})
    _put(lss.PF_ALLOCATION, {"generated_utc": recent, "mode": "normal", "armed": True,
                             "advisory": False,
                             "heat": {"total": 0.225, "resolved": 0.225, "held": False,
                                      "target": 0.2, "hard_ceiling": 0.225,
                                      "envelope": {"growth_ceiling": 0.225}},
                             "aggression": {"floor": 0.2, "ceiling": 0.225},
                             "book": {"gold_asia": 0.015246, "idle_sleeve": 0.0},
                             "proof": {"passed": True}})
    _put(lss.ALLOCATOR_PROOF_PATHS[0], {"at": recent, "passed": True, "best_baseline": "posterior",
                                        "why": "dynamic 0.018386 vs posterior 0.017819",
                                        "margin_frac": 0.02, "max_age_s": 93600,
                                        "hysteresis": {"holding_global": True},
                                        "book": {"gold_asia": 0.015246, "idle_sleeve": 0.0}})
    _put(lss.SYNC_MARKER, {"last_cycle": recent, "tape": {"exit_code": 0},
                           "search": {"exit_code": None}, "stamp": {"exit_code": 1}})
    _put(lss.STALL_WATCH, {"memory": {"total_phys_mb": 8186, "free_phys_mb": 1654,
                                      "free_commit_mb": 23970},
                           "checked_at": recent, "actions": ["FAILING MT5-Shadow"]})
    _put(lss.BANNED_FAMILIES, {"banned": {"discovered": {"since": "2026-09-16",
                                                         "why": "85 closes at mean -0.24R"}}})
    _put(lss.FORWARD_RECONCILE, {"checked_at": recent, "enrolled": 159, "certified_clocks": 151,
                                 "identity_unfrozen": 0,
                                 "unreachable_certified": {"n": 8, "by_cause": {}}})
    _put(lss.SHADOW_STATE, {"XAUUSD.asia": {"n": 14, "status": "ACTIVE"},
                            "USDJPY.asia": {"n": 15, "status": "ACTIVE"},
                            "GBPJPY.london_am": {"n": 8, "status": "RETIRED_ORPHAN"}})
    inside = (NOW - timedelta(hours=3)).isoformat(timespec="seconds")
    stale_row = (NOW - timedelta(days=5)).isoformat(timespec="seconds")
    lss.LIVE_LEDGER.write_text("\n".join([
        json.dumps({"time": inside, "sleeve": "gold_asia", "r_multiple": 1.5}),
        json.dumps({"time": inside, "sleeve": "gold_asia", "r_multiple": -1.0}),
        json.dumps({"time": stale_row, "sleeve": "gold_asia", "r_multiple": 9.0}),
        "",
    ]), encoding="utf-8")
    _put(lss.GATE_ATTESTATION_PATHS[0], {"at": recent, "tested_sha": "396ea4464b39",
                                         "gates": "fast", "result": "pass", "tree_clean": False,
                                         "dirty_paths": 3})
    _put(lss.CLOSED_LOOP, {"at": recent, "architecture_28_implemented": False,
                           "summary": {"true": 6, "false": 12, "unmeasured": 2,
                                       "open": ["truth.lost_candidates", "forward.lane_health"]}})
    lss.E8_ARMED.write_text("", encoding="utf-8")
    _put(lss.E8_GOLD, {"at": recent, "armed": False, "status": "OK", "equity": 99000.0,
                       "placed": [{"window": "gold_asia"}]})


def test_every_source_absent_is_unmeasured_and_the_document_is_still_written(desk) -> None:
    doc = lss.build()
    assert lss.write(doc) == lss.OUT
    on_disk = json.loads(lss.OUT.read_text(encoding="utf-8"))

    for section in SECTIONS:
        assert on_disk[section]["status"] == lss.UNMEASURED, section
    assert on_disk["sleeves"]["n_live"] == lss.UNMEASURED
    assert on_disk["sleeves"]["live"] == lss.UNMEASURED
    assert on_disk["execution"]["live_24h"]["deals"] == lss.UNMEASURED
    assert on_disk["risk"]["daily_loss"]["status"] == lss.UNMEASURED
    assert on_disk["promotion"]["banned_families"] == lss.UNMEASURED
    assert on_disk["e8"]["armed"] is False  # the marker's absence IS the unarmed state
    # sealed sha unknown -> the cross-fact is None, never a False that reads as "drifted"
    assert on_disk["envelope"]["running_matches_sealed"] is None
    assert on_disk["envelope"]["commit_sha"] == HEAD  # git still answered
    assert all(not row["present"] for row in on_disk["sources"].values())
    assert len(on_disk["sources"]) == 16
    named = set(on_disk["unmeasured"])
    assert {"release_identity", "sleeves", "gateway_state", "live_ledger"} <= named
    assert set(SECTIONS) <= named
    assert on_disk["changes_since_previous"][0].startswith(lss.UNMEASURED)
    assert on_disk["rule"]


def test_present_sources_land_in_the_section_that_owns_them(desk) -> None:
    _populate(desk)
    doc = lss.build()

    assert doc["unmeasured"] == []
    assert doc["release"]["sealed_sha"] == SEALED
    assert doc["release"]["running_sha"] == HEAD
    assert doc["release"]["changed_paths_n"] == 2
    assert doc["release"]["manifest"]["money_path_n"] == 3
    assert len(doc["release"]["why"]) == 300  # long reasons are clipped, never dropped

    assert (doc["sleeves"]["n_live"], doc["sleeves"]["n_standby"],
            doc["sleeves"]["n_retired"]) == (1, 1, 1)
    assert doc["sleeves"]["live"][0] == {"name": "gold_asia", "family": "session_bracket",
                                         "symbol": "XAUUSD", "timeframe": "H1",
                                         "session": "asia", "risk_frac": 0.015246,
                                         "lot": "auto_ramp"}

    assert doc["risk"]["heat"]["floor"] == 0.2
    assert doc["risk"]["heat"]["ceiling"] == 0.225
    assert doc["risk"]["risk_frac_by_live_sleeve"] == {"gold_asia": 0.015246}
    assert doc["risk"]["risk_frac_live_total"] == 0.015246
    assert doc["risk"]["daily_loss"]["params"] == {"gateway_state.daily_loss_cap": 0.02}

    assert doc["allocator"]["passed"] is True
    assert doc["allocator"]["stale"] is False
    assert doc["allocator"]["hysteresis"] == {"holding_global": True}
    assert doc["allocator"]["fractions"]["n_funded"] == 1
    assert doc["allocator"]["fractions"]["n"] == 2

    assert doc["promotion"]["banned_families"] == ["discovered"]
    assert doc["promotion"]["forward_clocks_by_status"] == {"ACTIVE": 2, "RETIRED_ORPHAN": 1}
    assert doc["promotion"]["identity_unfrozen"] == 0
    assert doc["promotion"]["unreachable_certified"] == 8

    assert doc["execution"]["positions"] == 2
    assert doc["execution"]["pending_orders"] == 1
    assert doc["execution"]["last_bracket_date"] == "2026-09-16"
    assert doc["execution"]["live_24h"]["deals"] == 2  # the 5-day-old deal is outside the window
    assert doc["execution"]["live_24h"]["sum_r"] == 0.5
    assert doc["execution"]["live_24h"]["by_sleeve"] == {"gold_asia": {"n": 2, "r": 0.5}}

    assert doc["attestation"]["gate"]["result"] == "pass"
    assert doc["attestation"]["gate"]["age_h"] == 1.0
    assert doc["attestation"]["closed_loop"]["true"] == 6
    assert doc["attestation"]["closed_loop"]["n_open"] == 2

    assert doc["e8"]["armed"] is True
    assert doc["e8"]["report_status"] == "OK"
    assert doc["box"]["memory"]["total_phys_mb"] == 8186
    assert (doc["box"]["cycle"]["ok"], doc["box"]["cycle"]["failed"],
            doc["box"]["cycle"]["unfinished"]) == (1, 1, 1)
    assert all(row["present"] and row["readable"] for row in doc["sources"].values())


def test_running_matches_sealed_needs_both_shas(desk) -> None:
    _populate(desk)
    assert lss.build()["envelope"]["running_matches_sealed"] is False

    desk.git["head"] = SEALED
    assert lss.build()["envelope"]["running_matches_sealed"] is True

    desk.git["head"] = None  # git answered nothing: unknown is not "drifted"
    doc = lss.build()
    assert doc["envelope"]["commit_sha"] == lss.UNMEASURED
    assert doc["envelope"]["running_matches_sealed"] is None
    assert "envelope.running_matches_sealed" in doc["unmeasured"]

    desk.git["head"] = HEAD
    lss.RELEASE_IDENTITY.unlink()
    lss.RELEASE_PATHS[0].unlink()
    doc = lss.build()
    assert doc["envelope"]["sealed_sha"] == lss.UNMEASURED
    assert doc["envelope"]["running_matches_sealed"] is None


def test_hashes_are_stable_over_identical_inputs_and_move_when_an_input_moves(desk) -> None:
    _populate(desk)
    first = lss.build()
    second = lss.build()
    for key in ("config_hash", "input_hash", "output_hash"):
        assert first["envelope"][key] == second["envelope"][key], key
    assert len(first["envelope"]["input_hash"]) == 64

    # output_hash is the document minus that one field: recomputable by any reader
    assert lss._document_hash(first) == first["envelope"]["output_hash"]

    _put(lss.SLEEVES, {"sleeves": [{"name": "gold_asia", "status": "LIVE", "risk_frac": 0.02}]})
    third = lss.build()
    assert third["envelope"]["input_hash"] != first["envelope"]["input_hash"]
    assert third["envelope"]["config_hash"] != first["envelope"]["config_hash"]
    assert third["envelope"]["output_hash"] != first["envelope"]["output_hash"]


def test_diff_since_previous_sees_the_live_sleeve_set_change(desk) -> None:
    _populate(desk)
    before = lss.build()
    lss.write(before)
    assert before["changes_since_previous"][0].startswith(lss.UNMEASURED)

    rows = json.loads(lss.SLEEVES.read_text(encoding="utf-8"))
    rows["sleeves"][1]["status"] = "LIVE"          # a standby sleeve is promoted
    rows["sleeves"][0]["status"] = "STANDBY"       # and the gold sleeve stands down
    _put(lss.SLEEVES, rows)
    after = lss.build()

    changes = after["changes_since_previous"]
    assert any("live sleeve added" in line and "chfnok_carry_asia" in line for line in changes)
    assert any("live sleeve removed" in line and "gold_asia" in line for line in changes)

    # a pass that changes nothing says so, rather than inventing a change
    lss.write(after)
    assert lss.build()["changes_since_previous"] == [
        f"no change in the key facts since {after['envelope']['at']}"]


def test_diff_since_previous_sees_sha_ban_and_allocator_changes(desk) -> None:
    _populate(desk)
    lss.write(lss.build())
    desk.git["head"] = "f" * 40
    _put(lss.BANNED_FAMILIES, {"banned": {"discovered": {}, "carry": {}}})
    _put(lss.ALLOCATOR_PROOF_PATHS[0],
         {"at": (NOW - timedelta(hours=1)).isoformat(timespec="seconds"), "passed": False})
    changes = lss.build()["changes_since_previous"]
    assert any(line.startswith("commit_sha:") for line in changes)
    assert any("banned family added" in line and "carry" in line for line in changes)
    assert any(line == "allocator_passed: True -> False" for line in changes)


def test_git_that_cannot_run_is_unmeasured(desk, monkeypatch: pytest.MonkeyPatch) -> None:
    _populate(desk)
    monkeypatch.setattr(lss, "_git", _REAL_GIT)

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise OSError("git is not on this box")

    monkeypatch.setattr(lss.subprocess, "run", _boom)
    doc = lss.build()
    envelope = doc["envelope"]
    assert envelope["commit_sha"] == lss.UNMEASURED
    assert envelope["branch"] == lss.UNMEASURED
    assert envelope["tree_clean"] == lss.UNMEASURED
    assert envelope["dirty_paths"] == lss.UNMEASURED
    assert envelope["running_matches_sealed"] is None
    assert {"envelope.commit_sha", "envelope.tree_clean"} <= set(doc["unmeasured"])
    # the rest of the document is unharmed
    assert doc["sleeves"]["n_live"] == 1


def test_unreadable_inputs_are_named_rather_than_crashing(desk) -> None:
    _populate(desk)
    lss.SLEEVES.write_bytes(b"\xef\xbb\xbf{not json at all")
    lss.PF_ALLOCATION.write_bytes(b"")
    lss.LIVE_LEDGER.write_text("not json\n{\"time\": \"nope\"}\n", encoding="utf-8")
    doc = lss.build()

    assert doc["sources"]["sleeves"]["present"] is True
    assert doc["sources"]["sleeves"]["readable"] is False
    assert "sleeves" in doc["unmeasured"]
    assert "pf_allocation" in doc["unmeasured"]
    assert doc["sleeves"]["status"] == lss.UNMEASURED
    assert doc["risk"]["heat"]["floor"] == lss.UNMEASURED
    # the ledger is readable but garbage: counted, never guessed at
    assert doc["execution"]["live_24h"]["unparsed_lines"] == 1
    assert doc["execution"]["live_24h"]["deals"] == 0
    # a utf-8-sig BOM on a good file is read, not rejected
    lss.SLEEVES.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        {"sleeves": [{"name": "x", "status": "LIVE"}]}).encode("utf-8"))
    assert lss.build()["sleeves"]["n_live"] == 1


def test_cli_writes_and_prints_twelve_lines_and_dry_run_writes_nothing(desk, capsys) -> None:
    _populate(desk)
    assert lss.main(["--dry-run"]) == 0
    printed = capsys.readouterr().out.strip().splitlines()
    assert len(printed) == 12
    assert printed[0].startswith("LIVE_SYSTEM_STATE")
    assert not lss.OUT.exists()

    assert lss.main([]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 12
    assert lss.OUT.exists()
    assert not lss.OUT.with_name(lss.OUT.name + ".tmp").exists()  # atomic: no debris left
    assert json.loads(lss.OUT.read_text(encoding="utf-8"))["envelope"]["generated_by"].endswith(
        "live_system_state.py")
