"""Burn-in telemetry: a row per pass, a streak that counts evidence and never silence.

The review's fourth defect was that release correctness is newer than its evidence. The bar it
set is thirty days of running-SHA == sealed-SHA with fills recorded against it; these tests pin
that a pass without its own fresh identity verdict breaks the streak, that a pause is a pause,
and that the summary is a subtraction, not a memory.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import burn_in  # noqa: E402

NOW = datetime(2026, 9, 9, 10, 0, tzinfo=UTC)
SHA = "b3ccb14baff6a89bb45e04ea808fa903ca4ebf5c"


@pytest.fixture
def box(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "RELEASE.json").write_text(json.dumps({"code_sha": SHA}), "utf-8")
    return tmp_path


def _identity(box: Path, *, ok: bool, at: datetime, allows=None) -> None:
    (box / "data" / "release_identity.json").write_text(json.dumps({
        "ok": ok, "measured": True, "verdict": "OK" if ok else "REFUSED",
        "allows_new_risk": ok if allows is None else allows,
        "running_sha": SHA, "release_sha": SHA, "reason": "" if ok else "drift",
        "at": at.isoformat()}), "utf-8")


def _deals(box: Path, times: list[datetime]) -> None:
    (box / "data" / "live_ledger.jsonl").write_text(
        "\n".join(json.dumps({"time": t.isoformat(), "pl_quote": 10.0, "r_multiple": 0.5})
                  for t in times) + "\n", "utf-8")


def test_a_fresh_ok_identity_on_the_sealed_head_is_burning_in(box: Path) -> None:
    _identity(box, ok=True, at=NOW - timedelta(minutes=5))
    _deals(box, [NOW - timedelta(hours=3), NOW - timedelta(hours=30)])
    row = burn_in.observe(NOW, base=box, repo=box, head=SHA)
    assert row["verdict"] == "BURNING_IN" and row["head_is_sealed"] is True
    assert row["deals_24h"] == 1 and row["pl_quote_24h"] == 10.0 and row["r_24h"] == 0.5


def test_a_stale_identity_is_unmeasured_not_a_pass(box: Path) -> None:
    _identity(box, ok=True, at=NOW - timedelta(hours=5))
    assert burn_in.observe(NOW, base=box, repo=box, head=SHA)["verdict"] == "UNMEASURED"
    (box / "data" / "release_identity.json").unlink()
    assert burn_in.observe(NOW, base=box, repo=box, head=SHA)["verdict"] == "UNMEASURED"


def test_a_refusing_identity_is_refusing_and_a_pause_file_is_paused(box: Path) -> None:
    _identity(box, ok=False, at=NOW - timedelta(minutes=5))
    assert burn_in.observe(NOW, base=box, repo=box, head=SHA)["verdict"] == "REFUSING"
    (box / "data" / "GATEWAY_PAUSED").write_text("x", "utf-8")
    assert burn_in.observe(NOW, base=box, repo=box, head=SHA)["verdict"] == "PAUSED"


def test_absent_inputs_are_none_never_zero_or_true(box: Path) -> None:
    row = burn_in.observe(NOW, base=box, repo=box, head=None)
    assert row["head"] is None and row["head_is_sealed"] is None
    assert row["armed"] is None and row["attributed_share"] is None
    assert row["deals_24h"] == 0 and row["verdict"] == "UNMEASURED"


def test_the_streak_counts_consecutive_evidence_and_silence_breaks_it(box: Path) -> None:
    t0 = NOW - timedelta(days=3)
    rows = [{"at": (t0 + timedelta(hours=h)).isoformat(),
             "verdict": "BURNING_IN"} for h in range(72)]
    rows[10]["verdict"] = "UNMEASURED"                      # a silent hour, 62 hours ago
    _deals(box, [t0 + timedelta(hours=20), t0 + timedelta(hours=5)])
    s = burn_in.summarise(rows, NOW, base=box)
    assert s["streak_passes"] == 61
    assert s["streak_started_at"] == rows[11]["at"]
    assert s["fills_in_burn_in"] == 1, "a fill before the streak started is not evidence for it"
    assert 2.5 < s["days_in_burn_in"] < 2.6 and s["target_met"] is False
    assert burn_in.summarise([], NOW, base=box)["verdict"] == "UNMEASURED"


def test_main_appends_a_row_and_writes_the_summary(box: Path, monkeypatch) -> None:
    monkeypatch.setattr(burn_in, "BASE", box)
    monkeypatch.setattr(burn_in, "REPO", box)
    monkeypatch.setattr(burn_in, "OUT_ROWS", box / "reports" / "burn_in.jsonl")
    monkeypatch.setattr(burn_in, "OUT", box / "reports" / "burn_in.json")
    monkeypatch.setattr(burn_in, "_git_head", lambda repo: SHA)
    _identity(box, ok=True, at=datetime.now(UTC))
    assert burn_in.main([]) == 0
    assert burn_in.main([]) == 0
    assert len((box / "reports" / "burn_in.jsonl").read_text("utf-8").splitlines()) == 2
    summary = json.loads((box / "reports" / "burn_in.json").read_text("utf-8"))
    assert summary["streak_passes"] == 2 and summary["verdict"] == "BURNING_IN"
    assert summary["target_days"] == 30.0
