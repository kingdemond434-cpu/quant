"""The Tier-5 audit ledger cannot claim what the repository does not hold: a LIVE row needs an
existing file, a known clock and an artifact; a refusal needs its sentence; a duplicate needs
its canonical; the section counts must match the blueprints."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_tier5_audit as ck  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops" / "quant-x.timer").write_text("[Timer]\n", "utf-8")
    (tmp_path / "desks" / "mt5" / "ops").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "ops" / "box_tasks.manifest").write_text(
        'TASK name="MT5-Hourly" trigger="hourly (keep-alive of a 24/7 resident)" runs="x"\n'
        'TASK name="MT5-Gauntlet" trigger="every 10 minutes" runs="y"\n', "utf-8")
    (tmp_path / "desks" / "mt5" / "research").mkdir()
    (tmp_path / "desks" / "mt5" / "research" / "hourly_cycle.py").write_text(
        '_costed("bottleneck_law", lambda: 1)\n', "utf-8")
    (tmp_path / "desks" / "mt5" / "research" / "daily_cycle.py").write_text(
        'for name in ("drawdown_alpha",):\n    pass\n', "utf-8")
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "thing.py").write_text("a\nb\nc\n", "utf-8")
    return tmp_path


def _ledger(*rows: dict[str, Any], expected: dict[str, int] | None = None) -> dict[str, Any]:
    base = {"source": "mandate", "id": "1", "title": "x", "status": "EXISTS+WIRED+LIVE",
            "files": ["libs/thing.py:2"], "clock": "hourly_cycle:bottleneck_law",
            "artifact": "desks/mt5/reports/X.json"}
    items = []
    for r in rows or ({},):
        d = dict(base)
        d.update(r)
        items.append(d)
    return {"updated": "2026-09-22", "sections": items,
            "expected_counts": expected if expected is not None else {}}


def test_a_true_ledger_passes_and_counts(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    problems, census = ck.check(_ledger(
        {}, {"id": "2", "clock": "daily_cycle:drawdown_alpha"},
        {"id": "3", "clock": "MT5-Gauntlet"}, {"id": "4", "clock": "resident:MT5-Hourly"},
        {"id": "5", "clock": "quant-x.timer"},
        {"id": "6", "status": "DORMANT", "why": "no clock names it", "clock": ""},
        {"id": "7", "status": "PARTIAL", "gap": "no consumer"},
        {"id": "8", "status": "MISSING", "files": []},
        {"id": "9", "status": "DUPLICATIVE", "canonical": "libs/thing.py"},
        {"id": "10", "status": "REFUSED_CONSERVATIVE",
         "why": "it would lower the 20% heat floor the principal fixed"},
        expected={"mandate": 10}), root)
    assert problems == []
    assert census["n_sections"] == 10 and census["total"]["EXISTS+WIRED+LIVE"] == 5


def test_every_kind_of_lie_is_named(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    problems, _ = ck.check(_ledger(
        {"files": ["libs/nothing.py"]},
        {"id": "2", "files": ["libs/thing.py:9"]},
        {"id": "3", "clock": "hourly_cycle:not_a_leg"},
        {"id": "4", "artifact": ""},
        {"id": "5", "status": "DORMANT"},
        {"id": "6", "status": "PARTIAL"},
        {"id": "7", "status": "REFUSED_CONSERVATIVE", "why": "because"},
        {"id": "8", "status": "DUPLICATIVE"},
        {"id": "9", "status": "LANDED"},
        {"id": "10", "status": "PARTIAL", "gap": "x", "files": []},
        expected={"mandate": 99}), root)
    text = "\n".join(problems)
    for needle in ("does not exist", "beyond its 3 lines", "not a known", "no artifact",
                   "DORMANT must say why", "PARTIAL must name", "REFUSED_CONSERVATIVE must",
                   "DUPLICATIVE must name", "not in", "cites no file", "99 expected"):
        assert needle in text, needle


def test_render_and_main_round_trip(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    ledger = tmp_path / "audit.json"
    ledger.write_text(json.dumps(_ledger()), "utf-8")
    out = tmp_path / "AUDIT.md"
    assert ck.main(["--ledger", str(ledger), "--root", str(root), "--render",
                    "--out", str(out)]) == 0
    page = out.read_text("utf-8")
    assert page.startswith("# Tier-5 institution audit (derived") and "| 1 | x |" in page
    ledger.write_text(json.dumps(_ledger({"status": "MISSING", "files": ["libs/thing.py"]},
                                         {"id": "2", "clock": "nowhere"})), "utf-8")
    assert ck.main(["--ledger", str(ledger), "--root", str(root)]) == 1


def test_the_real_ledger_tells_no_lie() -> None:
    ledger = json.loads(ck.LEDGER.read_text("utf-8"))
    problems, census = ck.check(ledger, ck.ROOT)
    assert problems == [], problems[:10]
    assert census["by_source"]["blueprint"] and census["by_source"]["mandate"]
    assert sum(census["by_source"]["blueprint"].values()) == 102
    assert sum(census["by_source"]["mandate"].values()) == 170
