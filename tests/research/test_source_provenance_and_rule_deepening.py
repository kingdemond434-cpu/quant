"""Source provenance end to end, the no-key deepening path, and the free-model batch seat.

    python -m pytest tests/research/test_source_provenance_and_rule_deepening.py -q

Six-event trace 2026-09-30: 0 of 53,174 candidates carried a source_url, and the deepening worker
produced 0 candidates from 28,686 rows because no key reached it. What must not regress:

  1. a compiled candidate names its source: URL or source id, retrieval time, content hash;
  2. the provenance share of NEW candidates only ratchets up, and the fence fails below it;
  3. a missing key never means zero output: the rule-based reader turns a multilingual claim into
     a STRUCTURED_HYPOTHESIS the compiler admits, labelled fidelity=rule_based, with culture;
  4. blocked rows whose task left the queue are found again by the compiler's identity through a
     cursor that resumes and does not re-read its own misses;
  5. the free seat rotates models on 429/404, batches rows, and validates EACH row's quote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for p in (str(ROOT), str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import deepening_worker as dw  # noqa: E402
import miner_candidate_compiler as mcc  # noqa: E402

from libs.ops import openrouter_free as orf  # noqa: E402
from libs.research import rule_deepening as rd  # noqa: E402
from libs.research import source_provenance as sp  # noqa: E402
from scripts import check_provenance_floor as fence  # noqa: E402

U = {"XAUUSD", "EURUSD", "USDJPY", "GBPUSD"}


def _reg(_f: str) -> bool:
    return True


# ------------------------------------------------------------------------ 1. provenance
def test_extract_prefers_the_rows_own_url_time_and_hash() -> None:
    row = {"link": "https://example.org/a", "found_at": "2026-09-29T10:00:00+00:00",
           "source_hash": "abc", "host": "example.org"}
    p = sp.extract(row, artifact="data/x.json", row_index=3)
    assert p["source_url"] == "https://example.org/a"
    assert p["retrieved_at"] == "2026-09-29T10:00:00+00:00"
    assert p["retrieved_at_basis"] == "row:found_at"
    assert p["content_hash"] == "abc" and p["ground"] == "example.org"
    assert p["source_id"] == "data/x.json#3"


def test_extract_falls_back_to_the_artifact_coordinate_and_mtime_and_row_hash() -> None:
    row = {"symbol": "EURUSD", "url": "kimi://2026-09-29/wave1/ab"}
    p = sp.extract(row, artifact="d/f.json", row_index=0, artifact_mtime=0.0)
    assert p["source_url"] == "", "a seat id is not a web page"
    assert p["source_id"] == "kimi://2026-09-29/wave1/ab"
    assert p["retrieved_at_basis"] == "artifact_mtime"
    assert p["content_hash"] == sp.row_hash(row)
    assert sp.has_provenance(p)


def test_stamp_candidate_never_overwrites_with_empty() -> None:
    c = {"source_url": "https://a.org/x"}
    sp.stamp_candidate(c, {"source_url": "", "source_id": "f#1", "retrieved_at": "t",
                           "content_hash": "h"})
    assert c["source_url"] == "https://a.org/x" and c["source_id"] == "f#1"


def test_stamp_row_existing_values_win_and_hash_is_stable() -> None:
    a = sp.stamp_row({"title": "x", "url": "https://q.org"}, ground="g", retrieved_at="t1")
    b = sp.stamp_row({"title": "x", "url": "https://q.org"}, ground="g", retrieved_at="t2")
    assert a["content_hash"] == b["content_hash"]
    assert a["source_url"] == "https://q.org" and a["retrieved_at"] == "t1"
    c = sp.stamp_row({"title": "y", "retrieved_at": "keep"}, retrieved_at="other")
    assert c["retrieved_at"] == "keep"


def test_compiler_stamps_the_intake_coordinate_on_every_candidate(tmp_path,
                                                                  monkeypatch) -> None:
    art = tmp_path / "seat" / "discoveries_1.json"
    art.parent.mkdir()
    art.write_text("[]", "utf-8")
    monkeypatch.setattr(mcc, "_POSITIONS", [(str(art), 7)])
    monkeypatch.setattr(mcc, "_DIGESTS", ["d" * 64])
    prov = mcc._row_provenance(0, {"title": "no url here"})
    assert prov["source_id"].endswith("discoveries_1.json#7")
    assert prov["content_hash"] == "d" * 64 and prov["retrieved_at"]


# ------------------------------------------------------------------------ 2. the ratchet
def test_the_floor_only_rises_and_a_drop_is_reported_not_recorded(tmp_path) -> None:
    f = tmp_path / "floor.json"
    assert sp.ratchet(f, 0.9)["status"] == "OK"
    assert sp.ratchet(f, 1.0)["floor"] == 1.0
    low = sp.ratchet(f, 0.5)
    assert low["status"] == "BELOW_FLOOR"
    assert json.loads(f.read_text())["floor"] == 1.0, "a regression never lowers the floor"
    assert sp.ratchet(f, None)["status"] == "UNMEASURED"


def test_the_fence_fails_below_the_floor_and_is_unmeasured_when_absent(tmp_path) -> None:
    art, floor = tmp_path / "mc.json", tmp_path / "floor.json"
    code, msg = fence.check(art, floor)
    assert code == 0 and msg.startswith("UNMEASURED")
    floor.write_text(json.dumps({"floor": 1.0}))
    art.write_text(json.dumps({"provenance": {"new": {"n": 10, "provenanced": 5, "share": 0.5},
                                              "all": {}}}))
    code, msg = fence.check(art, floor)
    assert code == 1 and "FAIL" in msg
    art.write_text(json.dumps({"provenance": {"new": {"n": 10, "provenanced": 10,
                                                      "share": 1.0}, "all": {}}}))
    assert fence.check(art, floor)[0] == 0


def test_provenance_block_measures_new_candidates_against_the_last_pass(tmp_path,
                                                                        monkeypatch) -> None:
    monkeypatch.setattr(mcc, "PROVENANCE_FLOOR", tmp_path / "floor.json")
    monkeypatch.setattr(mcc, "PROVENANCE_SEEN", tmp_path / "seen.json")
    good = {"symbol": "EURUSD", "family": "f", "params": {}, "source": "miner:a",
            "source_id": "x#1", "retrieved_at": "t", "content_hash": "h"}
    from datetime import UTC, datetime
    blk = mcc._provenance_block([good], datetime.now(tz=UTC))
    assert blk["new"]["share"] == 1.0 and blk["floor"]["floor"] == 1.0
    blk2 = mcc._provenance_block([good], datetime.now(tz=UTC))
    assert blk2["new"]["n"] == 0, "the same candidate is not new on the next pass"


# ------------------------------------------------------------------------ 3. rule-based
@pytest.mark.parametrize(("text", "family", "culture"), [
    ("黄金夜盘开盘后的假突破往往在一小时内回落", "failed_breakout", "CN/zh"),
    ("ドル円は東京時間のレンジブレイクで上昇しやすい", "session_range_breakout", "JP/ja"),
    ("Золото: пробой азиатского диапазона часто продолжается в течение дня",
     "session_range_breakout", "RU/ru"),
    ("금값은 갭 메우기 이후 반등한다", "overnight_gap_decay", "KR/ko"),
])
def test_multilingual_claims_map_to_registered_families_with_culture(text, family,
                                                                     culture) -> None:
    res = rd.deepen({"title": text, "source": "deep_forest"}, U, registered=_reg)
    fams = [h["family"] for h in res["hypotheses"]]
    assert family in fams, res
    h = next(h for h in res["hypotheses"] if h["family"] == family)
    assert h["fidelity"] == "rule_based" and h["kind"] == "hypothesis"
    assert h["source_culture"] == culture
    for k in ("participant_structure", "failure_mode_hypothesis", "crowding_prior"):
        assert h[k], k
    assert h["crowding_prior"] in ("low", "medium")


def test_a_rule_based_hypothesis_is_admitted_by_the_compiler_as_structured() -> None:
    res = rd.deepen({"title": "ドル円は東京時間のレンジブレイクで上昇しやすい"}, U,
                    registered=mcc._registered_cached)
    h = res["hypotheses"][0]
    cands, disp = mcc.compile_row(h["source"], h, U)
    assert disp == "STRUCTURED_HYPOTHESIS"
    assert cands and cands[0]["params"] == {"range_start": 7}, "the session the text names"


def test_calendar_needs_both_a_month_and_a_direction_and_crypto_venues_are_refused() -> None:
    assert not rd.deepen({"title": "XAUUSD seasonality is strong"}, U,
                         registered=_reg)["hypotheses"]
    ok = rd.deepen({"title": "XAUUSD historically bullish in month 9"}, U, registered=_reg)
    assert ok["hypotheses"][0]["family"] == "calendar_month"
    assert "crypto" in rd.deepen({"title": "binance futures XAUUSD range breakout"}, U,
                                 registered=_reg)["why"]


def test_no_instrument_is_never_invented() -> None:
    res = rd.deepen({"title": "区间突破策略很好用"}, U, registered=_reg)
    assert res["hypotheses"] == [] and "instrument" in res["why"]


def test_rule_work_donates_only_what_compiles(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dw, "RULE_DONATIONS", tmp_path / "don")
    task = {"source": "deep_forest", "title": "黄金夜盘开盘后的假突破往往在一小时内回落",
            "url": "https://xueqiu.com/1", "retrieved_at": "2026-09-29T00:00:00+00:00"}
    cands, disp, hyps = dw.rule_work(task, U)
    assert disp == "RECOVERED_RULE_BASED" and cands and hyps
    assert all(c["fidelity"] == "rule_based" for c in cands)
    assert dw.donate(hyps) == len(hyps)
    rows = [json.loads(ln) for f in (tmp_path / "don").glob("*.jsonl")
            for ln in f.read_text("utf-8").splitlines()]
    assert rows[0]["source_url"] == "https://xueqiu.com/1"
    assert rows[0]["content_hash"] and rows[0]["served_by"] == "rule_based"
    miss = dw.rule_work({"source": "x", "title": "FX Blue user abc"}, U)
    assert miss[0] == [] and miss[1].startswith("RULE_BASED_NO_MATCH")


def test_trial_census_charges_every_rule_based_cell() -> None:
    got = dw.charge_trials([{"symbol": "EURUSD", "family": "failed_breakout", "params": {}},
                            {"symbol": "XAUUSD", "family": "failed_breakout", "params": {}}])
    assert got["n_raw"] == 2 and got["n_effective"] is not None


# ------------------------------------------------------------------------ 4. the replay
def test_replay_finds_blocked_rows_by_compiler_identity_and_resumes(tmp_path,
                                                                    monkeypatch) -> None:
    monkeypatch.setattr(dw, "RULE_CURSOR", tmp_path / "cur.json")
    monkeypatch.setattr(dw, "_story_tasks", lambda: [])
    f = tmp_path / "seat" / "rows.jsonl"
    f.parent.mkdir()
    hit = {"source": "forum", "title": "黄金夜盘开盘后的假突破往往在一小时内回落", "url": "u1"}
    miss = {"source": "forum", "title": "FX Blue user abc", "url": "u2"}
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in (miss, hit)), "utf-8")
    ids = {mcc._deepening_task_id("forum", hit), mcc._deepening_task_id("forum", miss)}
    _res, note = dw.replay_blocked(ids, U, 60.0, paths=[f])
    assert note["matched"] == 2 and note["recovered"] == 1 and note["wrapped"]
    cur = json.loads((tmp_path / "cur.json").read_text())
    assert cur["tried"] == [mcc._deepening_task_id("forum", miss)], "only the miss is remembered"
    res2, note2 = dw.replay_blocked({mcc._deepening_task_id("forum", miss)}, U, 60.0, paths=[f])
    assert res2 == [] and note2["already_tried_this_lexicon"] == 1
    monkeypatch.setattr(rd, "LEXICON_VERSION", "next")
    res3, _ = dw.replay_blocked({mcc._deepening_task_id("forum", miss)}, U, 60.0, paths=[f])
    assert len(res3) == 1, "a new lexicon re-reads its misses"


# ------------------------------------------------------------------------ 5. the free seat
def test_key_is_resolved_by_name_env_first_then_panel(tmp_path) -> None:
    panel = tmp_path / "llm_panel.json"
    panel.write_text(json.dumps({"providers": [{"name": "OpenRouter",
                                                "base_url": "https://openrouter.ai/api/v1",
                                                "key": "sk-test"}]}))
    assert orf.resolve_key({"OPENROUTER_API_KEY": "sk-env"}, (panel,)) == \
        ("sk-env", "env:OPENROUTER_API_KEY")
    key, src = orf.resolve_key({}, (panel,))
    assert key == "sk-test" and src == "file:llm_panel.json:OpenRouter"
    assert "sk-" not in src, "the source is a NAME, never the value"
    assert orf.resolve_key({}, (tmp_path / "none.json",)) == ("", "")


def test_free_models_come_from_pricing_zero_and_fall_back_when_unreadable(tmp_path) -> None:
    body = {"data": [{"id": "a/x:free", "pricing": {"prompt": "0", "completion": "0"},
                      "context_length": 10},
                     {"id": "b/paid", "pricing": {"prompt": "0.001", "completion": "0.002"}},
                     {"id": "c/y:free", "pricing": {"prompt": "0", "completion": "0"},
                      "context_length": 99}]}
    models, basis = orf.free_models("k", get=lambda *a, **k: (body, None),
                                    cache=tmp_path / "m.json")
    assert models == ["c/y:free", "a/x:free"] and basis.startswith("live")
    again, basis2 = orf.free_models("k", get=lambda *a, **k: ({}, "HTTP 500"),
                                    cache=tmp_path / "m.json")
    assert again == models and basis2.startswith("cache")
    fb, basis3 = orf.free_models("k", get=lambda *a, **k: ({}, "HTTP 500"),
                                 cache=tmp_path / "other.json")
    assert fb == list(orf.FALLBACK_FREE_MODELS) and basis3.startswith("fallback")


def test_quota_is_read_never_assumed() -> None:
    q = orf.quota("k", get=lambda url, key: ({"data": {"limit_remaining": 7,
                                                       "is_free_tier": True}}, None))
    assert q["status"] == "MEASURED" and q["limit_remaining"] == 7
    assert orf.daily_request_ceiling(q)[0] == 50
    q2 = orf.quota("k", get=lambda url, key: ({}, "HTTP 404"))
    assert q2["status"] == "UNMEASURED"


def test_complete_rotates_on_429_and_404_and_persists_the_cursor(tmp_path) -> None:
    calls: list[str] = []
    replies = iter([({}, "HTTP 429: slow down"), ({}, "HTTP 404: gone"),
                    ({"choices": [{"message": {"content": "[]"}}]}, None)])

    def post(url, key, req, **kw):
        calls.append(req["model"])
        return next(replies)

    st = orf.load_state(tmp_path / "s.json")
    text, model, err = orf.complete([{"role": "user", "content": "x"}], key="k",
                                    models=["m1", "m2", "m3"], state=st, post=post,
                                    sleep=lambda s: None, state_path=tmp_path / "s.json")
    assert err is None and text == "[]" and calls == ["m1", "m2", "m3"] and model == "m3"
    saved = json.loads((tmp_path / "s.json").read_text())
    assert saved["model_index"] == 2 and saved["rate_limited"] == 1
    assert saved["per_model"]["m3"]["ok"] == 1


def test_batch_extract_validates_each_row_against_its_own_text() -> None:
    t1 = {"source": "forum", "title": "EURUSD London open range breakout works"}
    t2 = {"source": "forum", "title": "Nothing to see"}
    reply = json.dumps([
        {"row": 1, "symbols": ["EURUSD"], "family": "session_range_breakout", "params": {},
         "evidence": "EURUSD London open range breakout"},
        {"row": 2, "symbols": ["EURUSD"], "family": None, "params": None,
         "evidence": "a quote that is not in row two"}])
    out, _model, err = dw.batch_extract([t1, t2], U,
                                       complete=lambda msgs: (reply, "m", None))
    assert err is None and len(out) == 2
    assert out[0][2].startswith(("RECOVERED_", "STILL_"))
    assert out[1][2].startswith("REJECTED: evidence span is not in the source text")


def test_free_seat_lane_batches_and_names_the_provider(tmp_path) -> None:
    class FakeOrf:
        def resolve_key(self):
            return "k", "env:OPENROUTER_API_KEY"

        def free_models(self, key):
            return ["m1"], "fallback"

        def quota(self, key):
            return {"status": "UNMEASURED"}

        def daily_request_ceiling(self, q):
            return None, "UNMEASURED"

        def load_state(self):
            return {"requests": 0}

        def save_state(self, st):
            pass

        def complete(self, messages, **kw):
            n = messages[-1]["content"].count("[ROW ")
            return json.dumps([{"row": i, "symbols": [], "family": None, "why_not": "none"}
                               for i in range(1, n + 1)]), "m1", None

        def publish(self, st, **kw):
            return {"requests_today": 1, "rows_served_today": st.get("rows_served")}

    seen: list[tuple[str, str]] = []
    tasks = [{"source": "s", "title": f"row {i}", "url": f"u{i}"} for i in range(20)]
    note = dw.free_seat_lane(tasks, U, lambda t, c, d, w, via="": seen.append((d, via)),
                             lambda: False, orf=FakeOrf())
    assert note["status"] == "RAN" and len(note["served_ids"]) == 20
    assert {v for _d, v in seen} == {"llm:openrouter/m1"}
    assert all(d.startswith("REJECTED: nothing extractable") for d, _v in seen)


def test_the_chain_moves_to_the_next_seat(monkeypatch) -> None:
    from libs.ops import llm_seat
    a = llm_seat.Seat(name="first", base_url="https://a", key="ka")
    b = llm_seat.Seat(name="second", base_url="https://b", key="kb")
    monkeypatch.setattr(dw, "seat_chain", lambda: [a, b])
    monkeypatch.setattr(llm_seat, "chat", lambda prompt, seat=None, **kw:
                        ("", "HTTP 503") if seat is a else ("{}", None))
    _text, err = dw.chain_chat("p")
    assert err is None and dw.served_by() == "llm:second"
