"""The 10-point autonomy spec, scored only from published artifacts; UNMEASURED never passes."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import autonomy_conformance as ac  # noqa: E402

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def iso(h_ago: float) -> str:
    return (NOW - timedelta(hours=h_ago)).isoformat()


def healthy(tmp: Path) -> Path:
    docs: dict[str, Any] = {
        "MERGE_PIPELINE.json": {"at": iso(0.2), "status": "GREEN", "red": []},
        "RELEASE_PIPELINE_PROOF.json": {
            "at": iso(0.5),
            "red": [],
            "box": {"ok": True},
            "human_touches": [{"at": iso(30), "kind": "APPROVE_MERGES", "issue": 453}],
            "autonomy_proof": {
                "verdict": "PROVEN",
                "consecutive_automatic_deployments": 2,
                "hours_since_human_touch": 30.0,
            },
        },
        "AUTHORITY_REPLAY.json": {"at": iso(1), "summary": {"need_zuck_root": []}},
        "process_health.json": {
            "at": iso(0.3),
            "n_needing_attention": 0,
            "claude_settings": {"status": "OK"},
        },
        "BOX_ACTIONS.json": {"at": iso(0.1), "failed": 0, "n_done": 4},
        "BRIDGE_STATUS.json": {"at": iso(0.1), "boot_start": "PROVEN"},
        "ARCH_HEALTH.json": {"at": iso(0.5), "duplicate_workers": 0},
    }
    for name, doc in docs.items():
        (tmp / name).write_text(json.dumps(doc), encoding="utf-8")
    return tmp


def by_point(rep: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {p["point"]: p for p in rep["points"]}


def test_all_ten_met_is_the_only_autonomous() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        rep = ac.score(NOW, healthy(Path(d)))
    assert rep["counts"] == {"MET": 10, "NOT_MET": 0, "UNMEASURED": 0}, rep["blockers"]
    assert rep["autonomous"] is True and rep["blockers"] == []


def test_a_stale_or_missing_source_is_unmeasured_never_met(tmp_path: Path) -> None:
    healthy(tmp_path)
    (tmp_path / "BOX_ACTIONS.json").unlink()
    doc = json.loads((tmp_path / "MERGE_PIPELINE.json").read_text())
    doc["at"] = iso(9)
    (tmp_path / "MERGE_PIPELINE.json").write_text(json.dumps(doc))
    rep = ac.score(NOW, tmp_path)
    p = by_point(rep)
    assert p[1]["status"] == "UNMEASURED" and p[1]["sources"]["MERGE_PIPELINE.json"] == 9.0
    assert p[5]["status"] == p[7]["status"] == "UNMEASURED"
    assert p[7]["blocker"] == "BOX_ACTIONS_NOT_RUNNING"
    assert rep["autonomous"] is False


def test_each_failure_names_its_blocker(tmp_path: Path) -> None:
    healthy(tmp_path)

    def patch(name: str, **kw: Any) -> None:
        doc = json.loads((tmp_path / name).read_text())
        doc.update(kw)
        (tmp_path / name).write_text(json.dumps(doc))

    patch("MERGE_PIPELINE.json", red=["CI_QUEUED #5: a check queued 40 min"])
    patch("RELEASE_PIPELINE_PROOF.json", red=["ADOPTION_BLOCKED: x"], box={"ok": False},
          human_touches=[{"at": iso(2), "kind": "APPROVE_MERGES", "issue": 453}],
          autonomy_proof={"verdict": "NOT_YET"})
    patch("process_health.json", claude_settings={"status": "BROKEN"})
    patch("BRIDGE_STATUS.json", boot_start="SESSION0")
    patch("ARCH_HEALTH.json", duplicate_workers=2)
    p = by_point(ac.score(NOW, tmp_path))
    assert p[1]["blocker"] == "CI_QUEUED"
    assert p[2]["blocker"] == "APPROVE_MERGES_TYPED" and p[2]["evidence"]["approve_merges_24h"] == 1
    assert p[4]["blocker"] == "SETTINGS_BROKEN"
    assert p[6]["blocker"] == "ADOPTION_BLOCKED"
    assert p[7]["blocker"] == "BOOT_START_UNPROVEN"
    assert p[8]["blocker"] == "DUPLICATE_WORKERS"
    assert p[10]["blocker"] == "ACCEPTANCE_NOT_YET"
    assert all(p[i]["status"] == "NOT_MET" for i in (1, 2, 4, 6, 7, 8, 10))


def test_root_prs_keep_point_2_open(tmp_path: Path) -> None:
    healthy(tmp_path)
    (tmp_path / "AUTHORITY_REPLAY.json").write_text(
        json.dumps({"at": iso(1), "summary": {"need_zuck_root": [1088, 816]}})
    )
    p = by_point(ac.score(NOW, tmp_path))
    assert p[2]["blocker"] == "ROOT_PRS_NEED_OWNER"
    assert p[2]["evidence"]["prs_needing_owner_root"] == 2


def test_point_9_reads_the_real_root_policy() -> None:
    p = by_point(ac.score(NOW, Path("/nonexistent")))
    assert p[9]["status"] == "MET", p[9]
    assert p[9]["evidence"]["authority_is_root"] is True


def test_the_report_carries_no_quoted_source_text(tmp_path: Path) -> None:
    healthy(tmp_path)
    doc = json.loads((tmp_path / "MERGE_PIPELINE.json").read_text())
    doc["red"] = ["CI_QUEUED SECRETHOST rdp-zuck@62.171.172.249"]
    (tmp_path / "MERGE_PIPELINE.json").write_text(json.dumps(doc))
    text = json.dumps(ac.score(NOW, tmp_path))
    assert "SECRETHOST" not in text and "62.171" not in text


def test_the_merge_watch_runs_the_board_beside_its_report(monkeypatch: Any) -> None:
    import merge_pipeline_watch as mpw

    seen: list[list[str]] = []
    monkeypatch.setattr(ac, "main", lambda argv: seen.append(argv) or 0)
    mpw._autonomy_conformance(Path("reports"))
    assert seen == [["--reports", "reports"]]

    def boom(argv: list[str]) -> int:
        raise RuntimeError("x")

    monkeypatch.setattr(ac, "main", boom)
    mpw._autonomy_conformance(Path("reports"))  # never raises
    code = (ROOT / "scripts" / "merge_pipeline_watch.py").read_text(encoding="utf-8")
    assert "_autonomy_conformance(a.out.parent)" in code
