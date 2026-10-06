"""The health board: UNMEASURED is never GREEN, a failed leg is RED, and the desk is GREEN only
when every source is fresh and no organ is RED, AMBER or UNMEASURED."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import health_board as hb  # noqa: E402


def _now(h: float = 0.0) -> str:
    return (datetime.now(tz=UTC) - timedelta(hours=h)).isoformat()


def _write(p: Path, d: object) -> Path:
    p.write_text(json.dumps(d), "utf-8")
    return p


def _fixture(tmp: Path, organs: list[dict], events: list[dict], stall_age_h: float = 0.0,
             actions: list[str] | None = None) -> dict:
    rt = _write(tmp / "rt.json", {"generated_at": _now(), "organs": organs})
    ev = tmp / "ev.jsonl"
    ev.write_text("".join(json.dumps(e) + "\n" for e in events), "utf-8")
    acc = _write(tmp / "acc.json", {"at": _now(), "properties": {"AP1": {"status": "PASS",
                                                                         "measured": True}}})
    sw = _write(tmp / "sw.json", {"checked_at": _now(stall_age_h), "actions": actions or []})
    return hb.build(runtime=rt, events=ev, acceptance=acc, stall=sw, readers={})


def test_judge_verdicts() -> None:
    assert hb.judge({"state": "LIVE", "kind": "leg"}, {"kind": "LEG_DONE"})[0] == hb.GREEN
    assert hb.judge({"state": "LIVE", "kind": "leg"}, {"kind": "LEG_FAILED"})[0] == hb.RED
    assert hb.judge({"state": "LIVE", "kind": "leg"}, None)[0] == hb.AMBER
    assert hb.judge({"state": "MISSING"}, None)[0] == hb.RED
    assert hb.judge({"state": "STALE"}, {"kind": "LEG_DONE"})[0] == hb.RED
    assert hb.judge({"state": "NEVER"}, None)[0] == hb.UNMEASURED


def test_all_fresh_and_done_is_green(tmp_path: Path) -> None:
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"}],
                   [{"at": _now(), "kind": "LEG_DONE", "leg": "a"}])
    assert doc["desk_verdict"] == hb.GREEN


def test_unmeasured_organ_keeps_desk_off_green(tmp_path: Path) -> None:
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"},
                              {"organ": "leg:b", "kind": "leg", "state": "NEVER"}],
                   [{"at": _now(), "kind": "LEG_DONE", "leg": "a"}])
    assert doc["desk_verdict"] == hb.AMBER
    assert doc["counts"][hb.UNMEASURED] == 1


def test_failed_leg_is_red_and_stale_source_unmeasured(tmp_path: Path) -> None:
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"}],
                   [{"at": _now(), "kind": "LEG_FAILED", "leg": "a"}])
    assert doc["desk_verdict"] == hb.RED
    doc = _fixture(tmp_path, [{"organ": "leg:a", "kind": "leg", "state": "LIVE"}],
                   [{"at": _now(), "kind": "LEG_DONE", "leg": "a"}], stall_age_h=5.0,
                   actions=["FAILING MT5-Hourly"])
    assert doc["desk_verdict"] == hb.UNMEASURED            # stale watchdog: shown, not counted
    assert doc["box_tasks"]["stale_claims"] == ["FAILING MT5-Hourly"]
    assert "stall_watch" in doc["desk_verdict_why"]


def test_absent_sources_are_unmeasured(tmp_path: Path) -> None:
    doc = hb.build(runtime=tmp_path / "a", events=tmp_path / "b", acceptance=tmp_path / "c",
                   stall=tmp_path / "d", readers={"x": tmp_path / "X.json"})
    assert doc["desk_verdict"] == hb.UNMEASURED
    assert "Desk verdict: UNMEASURED" in hb.render_md(doc)


# ------------------------------------------------- audit 2026-10-06: readers and token matching


def test_reader_green_only_on_fresh_parseable_artifact_with_its_counter(tmp_path: Path) -> None:
    """Existence proved nothing: a stale FAIL file and a bare `{}` both read GREEN."""
    fresh = _write(tmp_path / "F.json", {"at": _now(), "status": "MEASURED", "n_trades": 151})
    r = hb.judge_reader("trade_pathology", fresh)
    assert r["verdict"] == hb.GREEN and r["counter_value"] == 151
    cases = {
        "absent": tmp_path / "ABSENT.json",
        "empty": _write(tmp_path / "E.json", {}),
        "stale": _write(tmp_path / "S.json", {"at": _now(30), "status": "MEASURED",
                                               "n_trades": 3}),
        "no_counter": _write(tmp_path / "N.json", {"at": _now(), "status": "MEASURED"}),
        "no_time": _write(tmp_path / "T.json", {"status": "MEASURED", "n_trades": 3}),
        "own_unmeasured": _write(tmp_path / "U.json", {"at": _now(), "status": "UNMEASURED",
                                                       "n_trades": 0}),
    }
    (tmp_path / "BAD.json").write_text("{not json", "utf-8")
    cases["unparseable"] = tmp_path / "BAD.json"
    for why, p in cases.items():
        assert hb.judge_reader("trade_pathology", p)["verdict"] == hb.UNMEASURED, why
    assert hb.judge_reader("unknown_reader", fresh)["verdict"] == hb.UNMEASURED


def test_reader_partial_or_failing_status_is_amber(tmp_path: Path) -> None:
    for st in ("PARTIAL", "FAILED"):
        p = _write(tmp_path / f"{st}.json", {"at": _now(), "status": st, "n_trades": 151})
        assert hb.judge_reader("trade_pathology", p)["verdict"] == hb.AMBER, st


def test_experiment_contracts_reader_needs_registered_not_a_status(tmp_path: Path) -> None:
    p = _write(tmp_path / "EC.json", {"at": _now(), "registered": 394})
    assert hb.judge_reader("experiment_contracts", p)["verdict"] == hb.GREEN


def test_fail_words_match_whole_tokens_never_substrings() -> None:
    """"RED" sits inside "MEASURED" and "UNMEASURED": substring matching scored them AMBER."""
    for ok in ("MEASURED", "UNMEASURED", "OK", "PASS", "REDUCED", "TIRED"):
        assert not hb.is_failure_reading(ok), ok
    for bad in ("FAIL", "FAILED", "RED", "status: RED", "BREACH", "leg_FAILED", "REJECTED"):
        assert hb.is_failure_reading(bad), bad
    row = {"state": "LIVE", "kind": "leg", "last_reading": "MEASURED"}
    assert hb.judge(row, {"kind": "LEG_DONE"})[0] == hb.GREEN
    row["last_reading"] = "RED"
    assert hb.judge(row, {"kind": "LEG_DONE"})[0] == hb.AMBER
