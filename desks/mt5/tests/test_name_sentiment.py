"""Per-share news sentiment (QG25-25): lexicon, negation, NER guard, PIT, refusal, contract."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import sensor_contract as sc  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402
from research import name_sentiment as ns  # noqa: E402

NAMES = ["Apple", "Alphabet-A", "Alphabet-C", "NVIDIA", "Target", "Walmart", "MorganStanley",
         "JPMorganChase", "Microsoft", "Tesla", "Netflix", "Pfizer"]


def _s(text: str) -> float:
    return ns.score_tokens(ns.tokens(text))[0]


def test_lexicon_ngrams_negation_and_emoji() -> None:
    assert _s("Company cuts guidance") == -2.5          # the phrase, not "cuts" + "guidance"
    assert _s("raises guidance") == 2.5 and _s("beats estimates") == 2.5
    assert _s("did not beat estimates") == -2.5
    assert _s("didn't beat estimates") == -2.5          # contraction expands to "not"
    assert _s("failed to beat") == -2.0
    assert _s("not that it was a beat") == 2.0          # negator four tokens back: out of window
    assert _s("downgraded to sell rating") == -2.0 - 1.5
    assert _s("upgrade") == 2.0 and _s("miss") == -2.0
    assert ns.emoji_score("to the moon \U0001F680") == 1.5
    assert ns.emoji_score("\U0001F4C9\U0001F43B") == -2.0
    assert len(ns.lexicon_version()) == 12


def test_ner_guard_maps_companies_not_words() -> None:
    t = ns.build_aliases(NAMES)
    assert ns.score_document("APPLE was delicious", "", t) == {}
    assert ns.score_document("apple pie recipe wins award", "", t) == {}
    assert set(ns.score_document("Apple shares rally after earnings", "", t)) == {"Apple"}
    # the ticker anywhere in the story releases the guard for the name in another sentence
    got = ns.score_document("Apple beats estimates.", "Analysts on $AAPL were upbeat.", t)
    assert got["Apple"] == pytest.approx(math.tanh((2.5 + 1.5) / 3.0))
    assert ns.score_document("Shoppers target bargains", "", t) == {}
    assert set(ns.score_document("Target cuts guidance as sales slump", "", t)) == {"Target"}
    assert ns.score_document("Target cuts guidance as sales slump", "", t)["Target"] < -0.8
    # one company, two share classes: the name goes to the first class only
    assert set(ns.score_document("Google parent Alphabet upgraded", "", t)) == {"Alphabet-A"}
    assert set(ns.score_document("GOOG gains", "", t)) == {"Alphabet-C"}
    # tickers that are ordinary abbreviations need the $
    assert ns.score_document("MS office suite", "", t) == {}
    assert set(ns.score_document("$MS upgraded", "", t)) == {"MorganStanley"}
    assert set(ns.score_document("JPMorgan Chase posts record revenue", "", t)) == {
        "JPMorganChase"}
    assert ns.score_document("NVIDIA did not beat estimates", "", t)["NVIDIA"] < 0


def test_documents_refuse_social_and_respect_the_cut(tmp_path: Path) -> None:
    led = sc.SensorLedger(tmp_path / "sensors")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    rows = [sc.make(sensor_id="news:rss", source_id="reuters", metric="document",
                    kind="document", text="NVIDIA beats estimates",
                    knowable_at="2026-10-06T09:00:00+00:00", knowable_basis="printed_stamp",
                    received_at="2026-10-06T09:05:00+00:00"),
            sc.make(sensor_id="news:social", source_id="reddit_wsb", metric="document",
                    kind="document", text="NVIDIA to the moon",
                    knowable_at="2026-10-06T09:00:00+00:00", knowable_basis="printed_stamp",
                    received_at="2026-10-06T09:05:00+00:00")]
    assert led.append(rows, now=now)["appended"] == 2
    cap = tmp_path / "news_captures.jsonl"
    cap.write_text("\n".join(json.dumps(r) for r in [
        {"title": "Tesla misses estimates", "published_utc": "2026-10-06T08:00:00Z",
         "received_at": "2026-10-06T08:01:00Z", "url": "https://example.com/a"},
        {"title": "Tesla thread", "url": "https://stocktwits.com/x",
         "received_at": "2026-10-06T08:01:00Z"},
        {"title": "From the future", "published_utc": "2026-10-06T11:00:00Z",
         "received_at": "2026-10-06T13:00:00Z"},
        {"title": "NVIDIA beats estimates", "published_utc": "2026-10-06T07:00:00Z",
         "received_at": "2026-10-06T07:30:00Z"}]) + "\n", "utf-8")
    docs, acc = ns.load_documents(now, 2, led, cap)
    assert acc["social_refused"] == 2 and acc["after_now"] == 1
    assert [d["title"] for d in docs] == ["NVIDIA beats estimates", "Tesla misses estimates"]
    assert docs[0]["held_at"] == datetime(2026, 10, 6, 7, 30, tzinfo=UTC)   # earliest copy kept
    # held by the cut -> that day; after the cut -> the next weekday (Friday -> Monday)
    assert ns.decision_day(datetime(2026, 10, 6, 12, 59, tzinfo=UTC)) == date(2026, 10, 6)
    assert ns.decision_day(datetime(2026, 10, 9, 13, 1, tzinfo=UTC)) == date(2026, 10, 12)


def test_cross_section_needs_enough_names() -> None:
    assert ns.cross_z({"A": (0.1, 1), "B": (0.2, 1)}) == {}
    z = ns.cross_z({s: (float(i), 1) for i, s in enumerate("ABCDEF")})
    assert z["F"] > 0 > z["A"] and abs(sum(z.values())) < 1e-9


# ------------------------------------------------------------------ the contract
def _days(n: int) -> list[date]:
    out, d = [], date(2024, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _world(n_days: int, planted: float, seed: int = 2
           ) -> tuple[dict[date, dict[str, float]], dict[str, list[tuple[str, float]]]]:
    rng = np.random.default_rng(seed)
    days = _days(n_days + 1)
    names = [f"N{i}" for i in range(12)]
    zs: dict[date, dict[str, float]] = {}
    px = {s: [100.0] for s in names}
    for d in days[:-1]:
        z = {s: float(rng.normal()) for s in names}
        zs[d] = z
        for s in names:
            px[s].append(px[s][-1] * math.exp(planted * z[s] + rng.normal(0.0, 0.01)))
    # px[s][i] is close(days[i]); the planted return runs close(d) -> close(d+1)
    closes = {s: [(d.isoformat(), p) for d, p in zip(days, px[s], strict=True)] for s in names}
    return zs, closes


def test_spread_contract_gain_noise_and_short_sample() -> None:
    zs, closes = _world(400, planted=0.004)
    got = ns.spread_contract(zs, closes, n_perm=100)
    assert got["verdict"] == se.GAIN, got
    assert got["alpha_t"] > 2 and got["mean_spread_bp"] > 0 and got["cards"] == ["QG25-25"]
    zs0, closes0 = _world(400, planted=0.0, seed=3)
    assert ns.spread_contract(zs0, closes0, n_perm=100)["verdict"] == se.NO_GAIN
    zs1, closes1 = _world(120, planted=0.004)
    assert ns.spread_contract(zs1, closes1, n_perm=20)["verdict"] == se.UNMEASURED


def test_a_score_that_is_only_reversal_is_not_a_gain() -> None:
    rng = np.random.default_rng(5)
    days = _days(402)
    names = [f"N{i}" for i in range(12)]
    rets = {s: rng.normal(0.0, 0.01, len(days)) for s in names}
    for s in names:                                      # planted cross-sectional reversal
        for i in range(1, len(days)):
            rets[s][i] += -0.4 * rets[s][i - 1]
    closes = {s: [(d.isoformat(), 100.0 * math.exp(float(np.cumsum(rets[s])[i])))
                  for i, d in enumerate(days)] for s in names}
    # the "sentiment" is minus yesterday's return: reversal wearing another name
    zs = {d: {s: -float(rets[s][i]) for s in names} for i, d in enumerate(days[:-1]) if i > 0}
    got = ns.spread_contract(zs, closes, n_perm=50)
    assert got["verdict"] != se.GAIN


def test_run_end_to_end_writes_lake_and_ledger_and_emits_no_share_cells(tmp_path: Path) -> None:
    names = ["NVIDIA", "Microsoft", "Tesla", "Netflix", "Walmart", "Pfizer"]
    rng = np.random.default_rng(1)
    days = _days(301)
    docs: list[dict[str, Any]] = []
    px = {s: [100.0] for s in names}
    for d in days[:-1]:
        for s in names:
            good = rng.random() < 0.5
            docs.append({"held_at": datetime(d.year, d.month, d.day, 10, tzinfo=UTC),
                         "title": f"{s} {'beats' if good else 'misses'} estimates", "text": ""})
            px[s].append(px[s][-1] * math.exp((0.006 if good else -0.006)
                                              + rng.normal(0.0, 0.008)))
    closes = {s: [(d.isoformat(), p) for d, p in zip(days, px[s], strict=True)] for s in names}
    now = datetime.combine(days[-1], datetime.min.time(), tzinfo=UTC) + timedelta(hours=20)
    led = sc.SensorLedger(tmp_path / "sensors")
    doc = ns.run(now=now, docs=docs, symbols=names, ledger=led,
                 closes_fn=lambda s, n: closes[s], lake_root=tmp_path / "lake",
                 contracts_root=tmp_path / "c", report=tmp_path / "R.json", n_perm=40)
    assert doc["days_ranked"] == 300
    assert doc["contracts"][0]["verdict"] == se.GAIN, doc["contracts"][0]
    assert doc["cells"]["status"] == "NONE_EMITTED" and "cross_sectional_class_score" in doc[
        "class_book_needs"]
    assert (tmp_path / "lake" / "ws_name_sentiment_nvidia.csv").exists()
    assert (tmp_path / "lake" / "ws_name_sentiment_panel.csv").exists()
    assert doc["ledger"]["appended"] == len(names) and doc["ledger"]["refused"] == 0
    assert (tmp_path / "R.json").exists()


@pytest.mark.parametrize("bad", ["reddit", "stocktwits.com", "twitter.com", "x.com/abc"])
def test_social_sources_are_refused(bad: str) -> None:
    assert ns._social({"url": f"https://{bad}/post"})
