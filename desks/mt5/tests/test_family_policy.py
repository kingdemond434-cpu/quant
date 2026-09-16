"""A banned family is banned everywhere it could re-enter (2026-09-16, `discovered`)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import family_policy as fp  # noqa: E402
import promoter  # noqa: E402

from research import miner_candidate_compiler as mcc  # noqa: E402


def _ban_file(tmp_path: Path, *families: str) -> Path:
    f = tmp_path / "banned_families.json"
    f.write_text(json.dumps({"banned": {x: {"since": "2026-09-16", "by": "principal",
                                            "why": "no live edge"} for x in families}}), "utf-8")
    return f


def test_the_policy_reads_the_file_and_an_absent_file_bans_nothing(tmp_path: Path) -> None:
    f = _ban_file(tmp_path, "discovered")
    assert fp.family_banned("discovered", f) and fp.family_banned("DISCOVERED", f)
    assert not fp.family_banned("carry", f) and not fp.family_banned("", f)
    assert "banned since 2026-09-16 by principal: no live edge" in fp.ban_reason("discovered", f)
    assert fp.banned_families(tmp_path / "missing.json") == {}
    assert not fp.family_banned("discovered", tmp_path / "missing.json")


def test_the_desk_file_bans_the_discovered_family_and_nothing_gold() -> None:
    assert fp.family_banned("discovered")
    for fam in ("carry", "overnight_gap_decay", "session_range_breakout", "gold_asia", ""):
        assert not fp.family_banned(fam)


def test_the_promoter_retires_rows_of_a_banned_family_and_queues_their_close(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fp, "BANNED_FAMILIES_FILE", _ban_file(tmp_path, "discovered"))
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    promoter._DOOR_EVENTS.clear()
    rows = [{"name": "eurchf_discovered_x", "status": "LIVE", "family": "discovered",
             "risk_frac": 0.03},
            {"name": "audcad_discovered_y", "status": "STANDBY", "family": "discovered"},
            {"name": "chfnok_carry_z", "status": "LIVE", "family": "carry", "risk_frac": 0.03},
            {"name": "old_discovered", "status": "RETIRED", "family": "discovered"}]
    assert promoter.retire_banned(rows) is True
    by = {r["name"]: r for r in rows}
    assert by["eurchf_discovered_x"]["status"] == "RETIRED"
    assert by["audcad_discovered_y"]["status"] == "RETIRED"
    assert "banned" in by["eurchf_discovered_x"]["retire_reason"]
    assert by["chfnok_carry_z"]["status"] == "LIVE"
    queue = json.loads((tmp_path / "RETIRED_CLOSE_QUEUE.json").read_text("utf-8"))["names"]
    assert set(queue) == {"eurchf_discovered_x", "audcad_discovered_y"}
    assert {e["name"] for e in promoter._DOOR_EVENTS} == {"eurchf_discovered_x",
                                                          "audcad_discovered_y"}
    promoter._DOOR_EVENTS.clear()
    # Nothing left to retire: no change, no second queue write.
    assert promoter.retire_banned(rows) is False


def test_the_compiler_refuses_a_banned_family(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fp, "BANNED_FAMILIES_FILE", _ban_file(tmp_path, "discovered"))
    cands, why = mcc.compile_row("edge_search", {"family": "discovered", "symbols": ["EURCHF"],
                                                 "params": {"feature": "x"}}, {"EURCHF"})
    assert cands == [] and why == "BANNED_FAMILY"
