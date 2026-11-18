from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from research import asia_github_miner as m  # noqa: E402


def test_exact_analogue_and_no_analogue_and_clues() -> None:
    ex = m.extract("双均线 策略 沪金 主力合约, data from akshare and 同花顺")
    assert ex["families"] == {"trend_ma_cross": "双均线"}
    assert ex["symbols"] == {"XAUUSD": "沪金"}
    assert {"akshare", "同花顺"} <= set(ex["clues"])
    ex2 = m.extract("螺纹钢 突破 策略")
    assert "螺纹" in ex2["no_analogue"] and not ex2["symbols"]


def test_classic_chinese_systems_map_to_breakout_families() -> None:
    assert "failed_breakout" in m.extract("R-Breaker 日内策略")["families"]
    assert "session_range_breakout" in m.extract("Dual Thrust 策略")["families"]
    assert "level_breakout" in m.extract("海龟交易法则")["families"]
    assert "rsi" not in str(m.extract("first strategy")["families"])  # word boundary


def test_rows_translate_or_keep_as_ideas() -> None:
    repo = {"full_name": "a/b", "html_url": "u", "stargazers_count": 3}
    text = "R-Breaker 策略"
    hyps, ideas = m.rows_for(repo, "cn", text, m.extract(text), "t")
    assert {h["symbols"][0] for h in hyps} == set(m.REGION_DEFAULT["cn"])
    assert all(h["translation"] == "instrument_agnostic_region_market" for h in hyps)
    text = "ORB 전략 코스피 opening range"
    hyps, ideas = m.rows_for(repo, "kr", text, m.extract(text), "t")
    assert not hyps and ideas
    text = "螺纹钢 突破 策略"
    hyps, ideas = m.rows_for(repo, "cn", text, m.extract(text), "t")
    assert not hyps and ideas                         # a no-analogue market never gets a proxy


def test_path_text_reads_vnpy_strategy_names() -> None:
    t = m.path_text("strategies/DualThrustStrategy.py")
    assert "session_range_breakout" in m.extract(t)["families"]


def test_offline_pass_donates_through_the_door(tmp_path: Path, monkeypatch) -> None:
    from research import proposer_common as pc
    for name in ("REPORT", "STATE", "CLUES", "IDEAS"):
        monkeypatch.setattr(m, name, tmp_path / name)
    monkeypatch.setattr(m, "CODE_QUERIES", ())
    monkeypatch.setattr(m, "search", lambda q: [{"full_name": "x/y", "html_url": "u",
                                                 "pushed_at": "p", "description": "",
                                                 "stargazers_count": 1}])
    monkeypatch.setattr(m, "readme", lambda n: "布林 策略 白银")
    got = {}
    monkeypatch.setattr(pc, "donate", lambda src, rows, tests_run, **k: got.update(
        src=src, rows=rows, tests_run=tests_run))
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(got["rows"])})
    doc = m.run(queries=(("cn", "q"),))
    assert got["src"] == "asia_github" and got["tests_run"] == 1
    assert got["rows"][0]["family"] == "mean_reversion_bollinger"
    assert got["rows"][0]["symbols"] == ["XAGUSD"]
    assert doc["repos_read"] == 1
    assert m.run(queries=(("cn", "q"),))["repos_read"] == 0   # an unchanged repo is not re-read


def test_missing_gh_binary_does_not_kill_the_leg(monkeypatch) -> None:
    def boom(*a, **k):
        raise FileNotFoundError("gh")
    monkeypatch.setattr(m.subprocess, "run", boom)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    assert m.search("q") == [] and m.readme("a/b") == "" and m.code_hits("q") == []
