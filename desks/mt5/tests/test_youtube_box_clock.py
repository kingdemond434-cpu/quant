"""YouTube's two producers get a box clock and a quota-safe cadence (2026-11-03).

Both had only VPS clocks (`ops/quant-youtube-corpus.timer`, `run_all_miners`), so the box's
judge saw no YouTube row for a week after the VPS went quiet.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
HOURLY = DESK / "research" / "hourly_cycle.py"


def _load(name: str, path: Path):
    """By path: a repo-root `youtube_miner.py` shadows the desk's module on sys.path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_both_legs_run_in_the_cycle_and_the_intel_department() -> None:
    src = HOURLY.read_text("utf-8")
    assert '_producer(\n        "youtube_corpus", "scripts/collect_youtube_corpus.py")' in src
    assert '_producer(\n        "youtube_miner", "side_channels/youtube_miner.py")' in src
    assert '"youtube_corpus": ytc, "youtube_miner": ytm' in src
    table = src[src.index("LEG_DEPARTMENT: dict[str, str] = {"):]
    intel = re.search(r"dict\.fromkeys\(\((.*?)\),\s*\n?\s*\"intel\"\)", table, re.S)
    assert intel is not None
    assert {"youtube_corpus", "youtube_miner"} <= set(re.findall(r'"([^"]+)"', intel.group(1)))


def test_both_legs_declare_a_layer() -> None:
    sys.path.insert(0, str(ROOT))
    from libs.research import layers
    assert layers.LEG_LAYER["youtube_corpus"] == "information"
    assert layers.LEG_LAYER["youtube_miner"] == "information"


@pytest.fixture()
def ytm(tmp_path, monkeypatch):
    m = _load("desk_youtube_miner", DESK / "side_channels" / "youtube_miner.py")
    monkeypatch.setattr(m, "STATE", tmp_path / "_box_miner_state.json")
    monkeypatch.setattr(m, "ERRORS", [])
    return m


def test_miner_is_gated_to_its_interval(ytm, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(ytm, "API_KEY", "SEKRET-zz9")
    monkeypatch.setattr(ytm, "run_and_save", lambda: calls.append(1) or [{"x": 1}])
    assert ytm.box_main([]) == 0
    st = json.loads(ytm.STATE.read_text("utf-8"))
    assert st["discoveries"] == 1 and st["key_present"] is True
    assert "SEKRET-zz9" not in json.dumps(st)
    assert ytm.box_main([]) == 0          # inside the interval: NOT_DUE, no second run
    assert len(calls) == 1
    st["last_run_epoch"] = time.time() - ytm.MIN_INTERVAL_S - 1
    ytm.STATE.write_text(json.dumps(st), "utf-8")
    ytm.box_main([])
    assert len(calls) == 2


def test_miner_without_a_key_records_a_blocker(ytm, monkeypatch) -> None:
    monkeypatch.setattr(ytm, "API_KEY", "")
    monkeypatch.setattr(ytm, "run_and_save", lambda: pytest.fail("must not run keyless"))
    ytm.box_main([])
    st = json.loads(ytm.STATE.read_text("utf-8"))
    assert st["key_present"] is False and st["blocker"].startswith("NO_KEY")


def test_quota_refusal_stops_the_run_and_is_recorded(ytm, monkeypatch) -> None:
    class R:
        status_code = 403
        text = '{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
    asked = []
    monkeypatch.setattr(ytm, "API_KEY", "SEKRET-zz9")
    monkeypatch.setattr(ytm.requests, "get", lambda *a, **k: asked.append(1) or R())
    assert ytm.mine() == []
    assert len(asked) == 1                 # the first refusal ends the run
    assert ytm.ERRORS and ytm.ERRORS[0].startswith("quota")


def test_corpus_collector_is_gated(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    c = _load("collect_youtube_corpus_t", ROOT / "scripts" / "collect_youtube_corpus.py")
    cov = tmp_path / "cov.json"
    monkeypatch.setattr(c, "COVERAGE", cov)
    now = datetime.now(tz=UTC)
    assert c._not_due(now) is None                       # never swept: due
    cov.write_text(json.dumps({"last_sweep": (now - timedelta(seconds=60)).isoformat()}))
    assert c._not_due(now) is not None                   # a minute ago: not due
    cov.write_text(json.dumps({"last_sweep": (now - timedelta(hours=2)).isoformat()}))
    assert c._not_due(now) is None
    monkeypatch.setattr(c, "KEYFILE", tmp_path / "absent")
    monkeypatch.setenv("YOUTUBE_API_KEY", "env-key")
    assert c._key() == "env-key"                         # the box's only carrier
    monkeypatch.delenv("YOUTUBE_API_KEY")
    assert c._key() == ""
    cov.write_text(json.dumps({"last_sweep": (now - timedelta(seconds=60)).isoformat()}))
    monkeypatch.setattr(sys, "argv", ["x"])
    assert c.main() == 0


def test_seed_handles_include_the_config_channels(tmp_path, monkeypatch) -> None:
    c = _load("collect_youtube_corpus_s", ROOT / "scripts" / "collect_youtube_corpus.py")
    cfg = tmp_path / "ch.json"
    cfg.write_text(json.dumps({"channels": [{"handle": "@NewOne"}, {"handle": "@QuantGuild"},
                                            {"handle": "no-at"}, "junk"]}))
    monkeypatch.setattr(c, "CHANNEL_CONFIG", cfg)
    seeds = c.seed_queries()
    assert {"@QuantGuild", "@Algovibes", "@saleh.m", "@NewOne"} <= set(seeds)
    assert seeds.count("@QuantGuild") == 1 and "no-at" not in seeds
    monkeypatch.setattr(c, "CHANNEL_CONFIG", tmp_path / "absent.json")
    assert "@saleh.m" in c.seed_queries()
