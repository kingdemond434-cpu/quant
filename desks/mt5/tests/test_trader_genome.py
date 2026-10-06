"""The public trader genome with its graveyard (Asia directive PART XIV, audit row 35).

Fixtures reproduce the documented shapes of the harvested corpora:
  * FX Blue statements as `fxblue_harvest` writes them to intelligence/fxblue/track_records*.jsonl
    (user, status live|has_data|shell|dead, overview{balance, closed_profit, account_type,
    last_update 'YYYY/MM/DD'}, charts{ch_tradedurationprofit [[duration, profit]...],
    ch_hourtrades [['HH:00', n]...], ch_symboltrades, ch_balancedrawdown [['m/d/YYYY', pct]...],
    ch_lotstradedmonthly_bysymbol [['YYYY/MM', lots]...]}, harvested_utc);
  * a competition ranking table in the layout of the 期货日报 实盘大赛 ranking pages
    (名次 / 参赛者 / 组别 / 净值 / 累计净值增长率 / 最大回撤 / 状态).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import book_forensics as bf  # noqa: E402
import failure_prior as fp  # noqa: E402
import provider_reverse as pr  # noqa: E402

from research import deep_forest_miner as dfm  # noqa: E402

HARVEST = "2026-08-27T10:00:00Z"


def _statement(user: str, *, profits: list[float], last_month: str, balance: float,
               closed: float, dd: float, sym: str = "EURUSD.p", status: str = "has_data",
               last_update: str = "2026/08/20") -> dict:
    months = ["2025/01", "2025/02", "2025/03", "2025/04", last_month]
    return {
        "user": user, "status": status, "harvested_utc": HARVEST,
        "overview": {"balance": balance, "equity": balance, "closed_profit": closed,
                     "currency": "USD", "account_type": "Real", "last_update": last_update},
        "charts": {
            "ch_tradedurationprofit": {"columns": ["Duration", "Profitability"],
                                       "rows": [[str(0.5 + i % 7), p]
                                                for i, p in enumerate(profits)]},
            "ch_hourtrades": {"columns": ["Hour of day", "Number of trades"],
                              "rows": [[f"{h:02d}:00", 5.0 if 8 <= h < 12 else 1.0]
                                       for h in range(24)]},
            "ch_symboltrades": {"columns": ["Symbol", "Number of trades"],
                                "rows": [[sym, float(len(profits))]]},
            "ch_balancedrawdown": {"columns": ["Day", "Balance drawdown %"],
                                   "rows": [["1/1/2025", 0.0], ["3/1/2025", dd]]},
            "ch_lotstradedmonthly_bysymbol": {"columns": ["Month"],
                                              "rows": [[m, 1.0] for m in months]},
        }}


def _martingale_profits() -> list[float]:
    return [10.0] * 27 + [-200.0, -180.0, -150.0]          # 90% wins, payoff tiny, skew < -1


def _trend_profits() -> list[float]:
    return [-10.0] * 18 + [40.0] * 9 + [400.0, 300.0, 250.0]   # positive skew


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    rows = []
    for i in range(12):                              # martingales: the graveyard
        rows.append(_statement(f"m-{i}", profits=_martingale_profits(), last_month="2025/05",
                               balance=0.5, closed=-990.0, dd=-99.0))
    for i in range(12):                              # trend followers: mostly alive
        alive = i < 9
        rows.append(_statement(f"t-{i}", profits=_trend_profits(),
                               last_month="2026/08" if alive else "2025/05",
                               balance=1500.0, closed=500.0 if alive else -100.0, dd=-12.0,
                               sym="XAUUSD"))
    rows.append({"user": "gone-1", "charts": {}, "status": "dead", "bytes": 90,
                 "harvested_utc": HARVEST})
    rows.append({"user": "shell-1", "status": "shell", "harvested_utc": HARVEST,
                 "overview": {"balance": 0.0, "last_update": "2024/01/01"},
                 "charts": {"ch_lotstradedmonthly_bysymbol": {"rows": []}}})
    p = tmp_path / "track_records_fixture.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    return p


COMPETITION_PAGE = """<html><head><meta name="publishdate" content="2026-09-30"></head><body>
<table><tr><th>名次</th><th>参赛者</th><th>组别</th><th>净值</th><th>累计净值增长率</th>
<th>最大回撤</th><th>状态</th></tr>
<tr><td>1</td><td>稳健一号</td><td>轻量组</td><td>3.21</td><td>221.0%</td><td>18.5%</td><td></td></tr>
<tr><td>2</td><td>趋势猎人</td><td>轻量组</td><td>2.10</td><td>110.0%</td><td>25.0%</td><td></td></tr>
<tr><td>-</td><td>重仓王</td><td>重量组</td><td>0.02</td><td>-98.0%</td><td>99.0%</td><td>爆仓</td></tr>
</table></body></html>"""


def test_summary_signature_reads_the_martingale_shape() -> None:
    sig = pr.summary_signature(trade_profits=_martingale_profits(), max_dd_pct=-99.0,
                               symbol_trades={"EURUSD": 30})
    assert "martingale_signature" in sig["tags"]
    assert "no_hard_stop" in sig["tags"] and "negative_skew" in sig["tags"]
    assert sig["win_rate"] == pytest.approx(0.9)


def test_summary_signature_says_unmeasured_not_zero() -> None:
    sig = pr.summary_signature(trade_profits=[1.0, -1.0])
    assert sig["win_rate"] is None and sig["skew"] is None and sig["tags"] == []


def test_genome_keeps_the_graveyard_and_stamps_publication(corpus: Path) -> None:
    rows, _census = bf.build_genome([corpus], competition_path=corpus.parent / "none.jsonl")
    by = {r["trader_id"]: r for r in rows}
    assert by["fxblue:m-0"]["outcome"] == "BLOWN" and by["fxblue:m-0"]["dead"]
    assert by["fxblue:t-0"]["outcome"] == "ALIVE"
    assert by["fxblue:t-10"]["outcome"] == "DORMANT"
    assert by["fxblue:gone-1"]["outcome"] == "DELISTED"
    assert by["fxblue:shell-1"]["outcome"] == "SHELL"
    # PIT: knowable from the statement's own publication date, not the harvest
    assert by["fxblue:t-0"]["knowable_from"].startswith("2026-08-20")
    assert by["fxblue:gone-1"]["knowable_from"].startswith("2026-08-27")
    assert all(r["terms_status"] == "to_confirm" for r in rows)


def test_as_of_drops_rows_not_yet_published(corpus: Path) -> None:
    rows, _ = bf.build_genome([corpus], competition_path=corpus.parent / "none.jsonl")
    early = bf.as_of(rows, datetime(2026, 8, 21, tzinfo=UTC))
    assert early and all(not r["trader_id"].endswith("gone-1") for r in early)
    assert bf.as_of(rows, datetime(2020, 1, 1, tzinfo=UTC)) == []


def test_refused_source_never_enters(corpus: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(bf.TERMS, "fxblue", ("refused", "test"))
    rows, census = bf.build_genome([corpus], competition_path=corpus.parent / "none.jsonl")
    assert rows == [] and census["refused_rows"]["fxblue"] == 26
    assert bf.TERMS["mql5_signals"][0] == "refused"
    assert "3.7" in bf.TERMS_EVIDENCE["mql5_signals"]["quote"]


def _paths(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setattr(bf, "GENOME", tmp / "trader_genome.parquet")
    monkeypatch.setattr(bf, "GENOME_REPORT", tmp / "TRADER_GENOME.json")
    monkeypatch.setattr(bf, "PRIORS", tmp / "trader_genome_priors.json")
    monkeypatch.setattr(bf, "INTEL", tmp / "intelligence")
    monkeypatch.setattr(bf, "ROOT", tmp)


def test_terms_gate_fails_closed(corpus: Path, tmp_path: Path,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    _paths(monkeypatch, tmp_path)
    doc = bf.genome(write=True, fxblue_paths=[corpus],
                    competition_path=tmp_path / "none.jsonl")
    assert doc["status"] == "BLOCKED_ON_TERMS" and doc["base_rates"] == "UNMEASURED"
    assert doc["proposer"]["tests_run"] == 0
    pri = json.loads((tmp_path / "trader_genome_priors.json").read_text("utf-8"))
    assert pri["status"] == "BLOCKED_ON_TERMS"
    assert fp.public_graveyard(tmp_path / "trader_genome_priors.json")["status"] == "UNMEASURED"
    assert (tmp_path / "trader_genome.parquet").exists()


def test_population_base_rates_feed_failure_memory(corpus: Path, tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    _paths(monkeypatch, tmp_path)
    monkeypatch.setitem(bf.TERMS, "fxblue", ("confirmed", "test"))
    monkeypatch.setattr(bf, "propose", lambda *a, **k: {"tests_run": 0, "cells_proposed": 0})
    doc = bf.genome(write=True, fxblue_paths=[corpus],
                    competition_path=tmp_path / "none.jsonl")
    assert doc["status"] == "OK"
    rates = doc["base_rates"]
    assert rates["unattributable_dead"] == 1 and rates["n_contrasts"] > 0
    m = rates["by_style"]["martingale_signature"]
    assert m["n"] == 12 and m["alive"] == 0 and m["p_success_population"] == 0.0
    ps = rates["by_style"]["positive_skew"]
    # survivor-only reads 9/9 profitable; over alive + dead it is 9/12
    assert ps["p_success_survivor_only"] == 1.0
    assert ps["p_success_population"] == pytest.approx(0.75)
    assert ps["survivorship_inflation"] == pytest.approx(0.25)
    assert ps["p_alive_floor"] < ps["p_alive"]
    # THE CONSUMER: failure_prior reads the priors the genome wrote
    pg = fp.public_graveyard(tmp_path / "trader_genome_priors.json")
    assert pg["status"] == "MEASURED"
    assert any(f["style"] == "martingale_signature" for f in pg["failure_memory"])
    pri = json.loads((tmp_path / "trader_genome_priors.json").read_text("utf-8"))
    assert pri["crowding_prior"]["symbol_share"]["EURUSD"] == pytest.approx(12 / 24)


def test_proposer_charges_every_look(corpus: Path, tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    from research import proposer_common as pc
    monkeypatch.setitem(bf.TERMS, "fxblue", ("confirmed", "test"))
    rows, _ = bf.build_genome([corpus], competition_path=tmp_path / "none.jsonl")
    rates = bf.base_rates(rows)
    monkeypatch.setattr(pc, "UNI", tmp_path / "no_bars")
    rep = bf.propose(rows, rates, bf.priors(rows, rates), write=False)
    assert rep["tests_run"] == 0 and rep["cells_proposed"] == 0
    assert rep["n_looks_charged"] == rates["n_contrasts"]
    assert "positive_skew" in rep["skipped"]


def test_competition_table_keeps_the_blown(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    rows = dfm.competition_rows(COMPETITION_PAGE, ground="期货日报 全国期货实盘交易大赛",
                                url="https://example.invalid/rank", published_time="2026-09-30",
                                available_time="2026-10-06T00:00:00+00:00", region="cn",
                                language="zh")
    assert [r["outcome"] for r in rows] == ["ALIVE", "ALIVE", "BLOWN"]
    assert rows[2]["max_dd_pct"] == -99.0 and rows[0]["return_pct"] == 221.0
    led = tmp_path / "comp.jsonl"
    led.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", "utf-8")
    g = bf._competition_rows(led)
    assert sum(1 for r in g if r["dead"]) == 1
    assert all(r["knowable_from"] == "2026-09-30" for r in g)
    assert bf.terms_of(g[0]["source"]) == "to_confirm"


def test_miner_appends_competition_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dfm, "COMPETITION_LEDGER", tmp_path / "comp.jsonl")
    monkeypatch.setattr(dfm, "LOCKS", tmp_path / "locks")
    run = dfm._Run.__new__(dfm._Run)
    import threading
    run._lock = threading.Lock()
    run.counts = {}
    run.status = []
    n = run._competition(COMPETITION_PAGE, ground={"name": "g", "region": "cn",
                                                   "language": "zh", "kind": "competition"},
                         url="https://example.invalid/rank")
    assert n == 3
    assert len((tmp_path / "comp.jsonl").read_text("utf-8").splitlines()) == 3


def test_daily_cycle_runs_the_genome() -> None:
    src = (DESK / "research" / "daily_cycle.py").read_text("utf-8")
    assert '"book_forensics"' in src
    assert callable(bf.run)
