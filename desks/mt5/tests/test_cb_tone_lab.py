"""CENTRAL-BANK TONE ROLE: native-language statements become PIT series and guarded cells.

  * each language's lexicon reads hawkish as positive and dovish as negative;
  * a model reading is typed and must quote the text verbatim, or it is discarded;
  * a closed terms row is never fetched; a challenge page or 403 is BLOCKED and cooled, never retried;
  * the series carries an `available_time` stamp the conditioner family reads;
  * contaminated model readings (documents older than the model's evidence_from) never enter the
    donated `tone_llm_clean` column;
  * only lexicon and clean-model columns are donated, and the compiler admits them as EXACT_RECIPE.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cb_tone_lab as cb  # noqa: E402
import llm_lab as lab  # noqa: E402

UNI = {"USDJPY": "forex", "EURJPY": "forex", "AUDUSD": "forex", "AUDJPY": "forex",
       "USDCNH": "forex", "USDZAR": "forex", "EURZAR": "forex", "USDTRY": "forex",
       "EURTRY": "forex"}
HAWK_EN = "The Board decided to raise interest rates; policy remains restrictive. " * 4
DOVE_EN = "The Board judged that accommodative settings and a rate cut support the recovery. " * 4
BOJ_DOC = ("日本銀行は本日の金融政策決定会合において、利上げを決定した。物価の上昇圧力が続いており、"
           "緩和の度合いを調整することが適当と判断した。") * 4


@pytest.fixture()
def tone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, rel in {"STATE_DIR": "cb", "DOCS": "cb/docs.jsonl",
                      "SOURCES_CONFIG": "cb/sources.json", "SOURCE_STATE": "cb/source_state.json",
                      "MODEL_FIRST_USED": "cb/model_first_used.json", "SERIES_DIR": "series",
                      "TEXT_CACHE": "text", "BIS_ZIP": "bis/speeches.zip",
                      "DONATE_DIR": "intelligence/llm_lab"}.items():
        monkeypatch.setattr(cb, name, tmp_path / rel)
    monkeypatch.setattr(lab, "MODEL_CUTOFFS", tmp_path / "cutoffs.json")
    monkeypatch.setattr(lab, "universe", lambda: dict(UNI))
    monkeypatch.setattr(cb, "_robots_ok", lambda url, timeout: True)
    monkeypatch.setattr(lab, "gauntlet_trims", lambda: True)
    monkeypatch.setattr(lab, "STATE_DIR", tmp_path / "lab_state")
    return tmp_path


def _bis_zip(path: Path, n: int) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["url", "title", "description", "date", "text", "author"])
    w.writeheader()
    for i in range(n):
        w.writerow({"url": f"https://www.bis.org/review/r{i:05d}.htm",
                    "title": f"Speech {i}", "description": "Speech by the Governor of the Reserve "
                    "Bank of Australia, at a dinner", "date": f"2019-{1 + i % 12:02d}-{1 + i // 12:02d}",
                    "text": HAWK_EN if i % 3 else DOVE_EN, "author": "Governor"})
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("speeches.csv", buf.getvalue())


RSS = ("<?xml version='1.0'?><rss><channel>"
       "<item><title>総裁講演：金融政策の運営</title><link>https://www.boj.or.jp/doc1.htm</link>"
       "<pubDate>Mon, 12 Oct 2026 06:00:00 +0900</pubDate></item>"
       "<item><title>統計の公表</title><link>https://www.boj.or.jp/stat.htm</link>"
       "<pubDate>Mon, 12 Oct 2026 06:00:00 +0900</pubDate></item>"
       "</channel></rss>").encode()


def _fake_get(pages: dict[str, tuple[int, bytes]]):
    def get(url: str, timeout: float) -> tuple[int, bytes, str]:
        code, body = pages.get(url, (404, b""))
        return code, body, "text/html; charset=utf-8"
    return get


@dataclass
class _Reply:
    text: str
    provider: str = "openrouter_free"
    model: str = "qwen:free"
    tier: str = "model_free"


def _chat(system: str, user: str, **kw: Any) -> _Reply:
    body = user.split("TEXT:\n", 1)[1]
    quote = body[:40]
    stance = 0.6 if ("利上げ" in body or "raise interest" in body) else -0.5
    return _Reply(json.dumps({"stance": stance, "shift": "more_hawkish" if stance > 0 else
                              "more_dovish", "quote": quote}, ensure_ascii=False))


def test_lexicons_read_direction_in_each_language() -> None:
    assert cb.score_lex("中国人民银行决定降准，实施适度宽松的货币政策", "zh")[2] == -1.0
    assert cb.score_lex(BOJ_DOC, "ja")[2] == 1.0
    assert cb.score_lex("Kurul politika faizinin düşürülmesine karar verdi", "tr")[2] == -1.0
    assert cb.score_lex("Kurul sıkı para politikası duruşunu korudu", "tr")[2] == 1.0
    assert cb.score_lex(HAWK_EN, "en")[2] == 1.0
    assert cb.score_lex("no policy words here", "en") == (0, 0, None)


def test_model_reading_is_typed_and_must_quote_the_text() -> None:
    text = "The Board decided to lift the cash rate to 4.35 per cent."
    ok, why = cb.parse_reading('{"stance": 0.7, "shift": "more_hawkish", '
                               '"quote": "lift the cash rate to 4.35"}', text)
    assert ok and ok["stance"] == 0.7 and not why
    assert cb.parse_reading('{"stance": 0.7, "shift": "more_hawkish", "quote": "cut rates '
                            'sharply today"}', text)[1] == "quote not found verbatim in the text"
    assert cb.parse_reading('{"stance": 3, "shift": "unchanged", "quote": "lift the cash"}',
                            text)[1] == "stance outside [-1, 1]"
    assert cb.parse_reading('{"stance": 0.1, "shift": "maybe", "quote": "lift the cash"}',
                            text)[0] is None
    assert cb.parse_reading("I think it is hawkish", text)[1] == "no JSON object"


def test_closed_terms_and_blocks_are_never_fetched_again(tone: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    hits: list[str] = []
    pboc = cb.BANKS["PBOC"].sources[0].url
    cbrt = cb.BANKS["CBRT"].sources[0].url

    def get(url: str, timeout: float) -> tuple[int, bytes, str]:
        hits.append(url)
        if url == pboc:
            return 200, b"<html><script>wzws challenge</script></html>", "text/html"
        if url == cbrt:
            return 403, b"", "text/html"
        return 404, b"", "text/html"

    monkeypatch.setattr(cb, "_get", get)
    # The terms gate still binds a row the config holds back.
    cb.SOURCES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    cb.SOURCES_CONFIG.write_text(json.dumps({"sarb_speeches": {"terms": "to_confirm"}}))
    state: dict[str, Any] = {}
    out = cb.fetch_new({}, state, deadline=1e12, max_fetch=5)
    assert out["sarb_speeches"]["state"] == "TERMS_CLOSED"
    assert cb.BANKS["SARB"].sources[0].url not in hits
    assert out["pboc_news"]["state"] == "BLOCKED" and "challenge" in out["pboc_news"]["why"]
    assert out["cbrt_press_tr"]["state"] == "BLOCKED" and "403" in out["cbrt_press_tr"]["why"]
    hits.clear()
    again = cb.fetch_new({}, state, deadline=1e12, max_fetch=5)
    assert again["pboc_news"]["state"] == again["cbrt_press_tr"]["state"] == "COOLING"
    assert pboc not in hits and cbrt not in hits


def test_full_pass_writes_pit_series_and_guarded_cells(tone: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    _bis_zip(cb.BIS_ZIP, 40)
    boj = cb.BANKS["BOJ"].sources[0].url
    monkeypatch.setattr(cb, "_get", _fake_get({
        boj: (200, RSS), "https://www.boj.or.jp/doc1.htm": (200, f"<p>{BOJ_DOC}</p>".encode())}))
    doc = cb.run(budget_s=120, max_llm=60, chat=_chat)

    assert doc["bis"]["state"] == "INGESTED" and doc["bis"]["added"] == 40
    assert doc["fetch"]["boj_whatsnew_ja"] == {"state": "OK", "listed": 1, "new": 1,
                                                "fetched": 1, "owed": 0}
    live = next(d for d in cb._jsonl(cb.DOCS) if d["source_id"] == "boj_whatsnew_ja")
    assert live["lang"] == "ja" and live["original"] and live["tone_lex"] == 1.0
    assert live["available_time"] == "2026-10-11T21:00:00+00:00"
    assert "text" not in live, "the tracked ledger never holds the document text"
    assert live["llm"]["lookahead_guard"]["evidence_from"] == lab._now()[:10]

    # The conditioner family reads the written series on its own PIT stamp.
    from mt5desk import family_exogenous_conditioner as fec
    s = fec.conditioner("cb_tone_rba", "tone_lex", "level_z", root=cb.SERIES_DIR)
    assert s is not None and len(s) >= 30
    with (cb.SERIES_DIR / "cb_tone_rba.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["available_time"] == "2019-01-08T00:00:00+00:00"   # speech date + 7d
    # 2019 BIS readings were scored by a model first used today: contaminated, never clean.
    assert all(r["tone_llm"] != "" and r["tone_llm_clean"] == "" for r in rows)

    donated = json.loads(next(cb.DONATE_DIR.glob("discoveries_cbtone_*.json")).read_text())
    cells = donated["discoveries"]
    assert cells and {c["params"]["signal"] for c in cells} == {"tone_lex"}
    assert {c["symbol"] for c in cells} == {"AUDUSD", "AUDJPY"}
    assert all(c["params"]["side_when_high"] == 1 for c in cells)
    owed = {(o["bank"], o["signal"]) for o in doc["owed"]}
    assert ("RBA", "tone_llm_clean") in owed and ("BOJ", "tone_lex") in owed

    import miner_candidate_compiler as mc
    cands, disp = mc.compile_row("llm_lab", cells[0], set(UNI))
    assert disp == "EXACT_RECIPE" and cands[0]["family"] == "exogenous_conditioner"

    # A second pass re-reads nothing new and donates nothing twice.
    again = cb.run(budget_s=120, max_llm=60, chat=_chat)
    assert again["bis"]["state"] == "CURRENT" and again["cells_donated"] == 0


def test_quote_sense_follows_the_banks_currency() -> None:
    assert cb.BANKS["BOJ"].symbols["USDJPY"] == -1
    assert cb.BANKS["CBRT"].symbols["USDTRY"] == -1
    assert cb.BANKS["RBA"].symbols["AUDUSD"] == 1
    assert {b.lang for b in cb.BANKS.values()} == {"zh", "ja", "en", "tr"}
    assert all(s.terms == "confirmed" for b in cb.BANKS.values() for s in b.sources), \
        "public official pages are read politely; none is held back by default"
