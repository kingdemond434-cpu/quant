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


def test_a_banned_family_is_paroled_only_by_its_pooled_forward_record(tmp_path: Path,
                                                                       monkeypatch) -> None:
    """Principal 2026-09-16: 'what if existing discovery sleeves actually pass?' They pass through
    their forward clocks: pooled n >= 40 at t >= 2.5 and a positive expectancy paroles the family;
    its rows then stay and its candidates may be promoted. Below the bar the ban holds."""
    import decay_monitor as dm
    monkeypatch.setattr(fp, "BANNED_FAMILIES_FILE", _ban_file(tmp_path, "discovered"))
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    monkeypatch.setattr(dm, "SHADOW_LEDGER_DIRS", (shadow,))
    ids = {"AUDCAD.discovered.asia": {"family": "discovered"},
           "EURCHF.discovered.asia": {"family": "discovered"},
           "CHFNOK.carry.asia": {"family": "carry"}}
    from datetime import UTC, datetime, timedelta
    t0 = datetime.now(tz=UTC) - timedelta(days=3)

    def _ledger(key: str, rs: list[float]) -> None:
        rows = [{"entry_time": (t0 + timedelta(hours=i)).isoformat(),
                 "exit_time": (t0 + timedelta(hours=i + 1)).isoformat(), "r_multiple": r}
                for i, r in enumerate(rs)]
        (shadow / f"ledger_{key.replace('.', '_')}.json").write_text(json.dumps(rows), "utf-8")

    # Below the bar: 30 forward trades, however good.
    _ledger("AUDCAD.discovered.asia", [0.6, 0.4, 0.5, 0.7, 0.3] * 3)
    _ledger("EURCHF.discovered.asia", [0.5, 0.4, 0.6, 0.3, 0.7] * 3)
    ok, why = promoter.family_parole("discovered", ids)
    assert not ok and "n=30" in why and "not paroled" in why
    rows = [{"name": "audcad_discovered_x", "status": "LIVE", "family": "discovered"}]
    assert promoter.retire_banned(rows, ids) is True and rows[0]["status"] == "RETIRED"
    promoter._DOOR_EVENTS.clear()
    # At the bar: 40 forward trades, strongly positive -> paroled, rows kept.
    _ledger("AUDCAD.discovered.asia", [0.6, 0.4, 0.5, 0.7, 0.3] * 4)
    _ledger("EURCHF.discovered.asia", [0.5, 0.4, 0.6, 0.3, 0.7] * 4)
    ok, why = promoter.family_parole("discovered", ids)
    assert ok and "PAROLED" in why and "n=40" in why
    rows = [{"name": "audcad_discovered_y", "status": "LIVE", "family": "discovered"}]
    assert promoter.retire_banned(rows, ids) is False and rows[0]["status"] == "LIVE"
    # A losing forward record never paroles, whatever its size.
    _ledger("AUDCAD.discovered.asia", [-0.3, 0.1, -0.4, -0.2, -0.5] * 8)
    _ledger("EURCHF.discovered.asia", [-0.2, -0.4, 0.1, -0.3, -0.6] * 8)
    ok, why = promoter.family_parole("discovered", ids)
    assert not ok


def test_blind_review_veto_matches_the_canon_prefixing_convention():
    verdicts = {"external.XAUUSD.session_range_breakout.rr=1.5": "VETO",
                "external.EURUSD.carry": "PASS"}
    assert promoter.blind_review_veto("XAUUSD.session_range_breakout.rr=1.5", verdicts) \
        == "external.XAUUSD.session_range_breakout.rr=1.5"
    assert promoter.blind_review_veto("EURUSD.carry", verdicts) is None
    assert promoter.blind_review_veto("GBPUSD.carry", {}) is None
