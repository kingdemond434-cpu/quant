"""A pinned model id the provider has retired is learned once and swapped, never trusted forever.

The box finding of 2026-10-20: MT5-DeepSeek exited rc0 every hour while every call 404'd with
"No endpoints found for deepseek/deepseek-r1:free", because `discover_model` returned any pin the
guard accepted without asking whether it was still served.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from libs.ops import llm_seat

OR = "https://openrouter.ai/api/v1"
DEAD = "deepseek/deepseek-r1:free"
_404 = f'HTTP 404: {{"error":{{"message":"No endpoints found for {DEAD}.","code":404}}}}'
LISTED = ["deepseek/deepseek-chat-v3.1:free", "deepseek/deepseek-r1-0528:free",
          "deepseek/deepseek-v3.2", "qwen/qwen3-235b-a22b:free", "openai/gpt-5"]


@pytest.fixture(autouse=True)
def _free(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(llm_seat, "SWAP_LEDGER", tmp_path / "llm_model_swaps.jsonl")
    monkeypatch.delenv("QUANT_LLM_LAB_PAID", raising=False)
    monkeypatch.setattr(llm_seat, "free_tier_only", lambda: True)
    monkeypatch.setattr(llm_seat, "_RESOLVED", {})


def _seat(model: str = DEAD) -> llm_seat.Seat:
    return llm_seat.Seat(name="deepseek_bulk", base_url=OR, key="k", model=model)


def _listing(monkeypatch: pytest.MonkeyPatch, ids: list[str]) -> list[str]:
    calls: list[str] = []

    def get(url: str, key: str, *, timeout: float) -> tuple[dict[str, Any], str | None]:
        calls.append(url)
        return {"data": [{"id": i} for i in ids]}, None
    monkeypatch.setattr(llm_seat, "_get", get)
    return calls


def _rows() -> list[dict[str, Any]]:
    if not llm_seat.SWAP_LEDGER.exists():
        return []
    return [json.loads(x) for x in llm_seat.SWAP_LEDGER.read_text().splitlines()]


def test_a_live_pin_is_used_without_asking_the_provider(monkeypatch):
    calls = _listing(monkeypatch, LISTED)
    assert llm_seat.discover_model(_seat()) == (DEAD, None)
    assert calls == []


def test_the_refusal_wording_is_recognised_and_a_busy_model_is_not():
    assert llm_seat.is_dead_endpoint(_404)
    assert llm_seat.is_dead_endpoint('HTTP 400: {"error":{"message":"x is not a valid model ID"}}')
    assert not llm_seat.is_dead_endpoint("HTTP 429: rate limited upstream")
    assert not llm_seat.is_dead_endpoint("HTTP 503: No endpoints found")   # not a 400/404
    assert not llm_seat.is_dead_endpoint(None)


def test_a_dead_pin_swaps_to_the_best_free_id_of_the_same_vendor(monkeypatch):
    _listing(monkeypatch, LISTED)
    llm_seat.note_dead(_seat(), DEAD, _404)
    model, err = llm_seat.discover_model(_seat())
    assert err is None
    assert model.startswith("deepseek/") and model.endswith(":free")
    assert model != DEAD
    swap = [r for r in _rows() if r["kind"] == "swap"]
    assert swap and swap[-1]["from"] == DEAD and swap[-1]["to"] == model
    assert all("key" not in r for r in _rows())


def test_a_free_pin_never_swaps_to_a_paid_id_even_when_paid_is_allowed(monkeypatch):
    monkeypatch.setattr(llm_seat, "free_tier_only", lambda: False)
    _listing(monkeypatch, ["deepseek/deepseek-v3.2", "qwen/qwen3-235b-a22b:free"])
    llm_seat.note_dead(_seat(), DEAD, _404)
    model, err = llm_seat.discover_model(_seat())
    assert err is None
    assert model.endswith(":free")


def test_a_vendor_with_nothing_left_falls_through_to_every_free_family(monkeypatch):
    _listing(monkeypatch, ["qwen/qwen3-235b-a22b:free", "openai/gpt-5"])
    llm_seat.note_dead(_seat(), DEAD, _404)
    model, err = llm_seat.discover_model(_seat())
    assert (model, err) == ("qwen/qwen3-235b-a22b:free", None)


def test_a_dead_row_expires_so_a_relisted_id_comes_back(monkeypatch):
    calls = _listing(monkeypatch, LISTED)
    old = datetime.now(UTC) - timedelta(hours=llm_seat.DEAD_TTL_H + 1)
    llm_seat.note_dead(_seat(), DEAD, _404, now=old)
    assert llm_seat.discover_model(_seat()) == (DEAD, None)
    assert calls == []


def test_a_dead_row_is_per_provider(monkeypatch):
    _listing(monkeypatch, LISTED)
    llm_seat.note_dead(llm_seat.Seat(name="x", base_url="https://other/v1", key="k"), DEAD, _404)
    assert llm_seat.discover_model(_seat()) == (DEAD, None)


def test_chat_learns_the_refusal_swaps_and_answers_on_the_same_call(monkeypatch):
    _listing(monkeypatch, LISTED)
    sent: list[str] = []

    def post(url: str, key: str, req: dict[str, Any], *, timeout: float):
        sent.append(req["model"])
        if req["model"] == DEAD:
            return {}, _404
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}, None
    monkeypatch.setattr(llm_seat, "_post_with_degrade", post)
    booked: list[str] = []
    monkeypatch.setattr(llm_seat, "_record_spend", lambda s, m, b: booked.append(m))
    text, err = llm_seat.chat("hi", seat=_seat())
    assert (text, err) == ("ok", None)
    assert sent[0] == DEAD and sent[1].startswith("deepseek/") and len(sent) == 2
    assert booked == [sent[1]]                    # the spend books the model that answered
    # The next call goes straight to the replacement: one wasted request a day, not every call.
    sent.clear()
    assert llm_seat.chat("again", seat=_seat()) == ("ok", None)
    assert DEAD not in sent


def test_a_swap_that_also_fails_returns_the_error_and_does_not_loop(monkeypatch):
    _listing(monkeypatch, [DEAD])
    sent: list[str] = []

    def post(url: str, key: str, req: dict[str, Any], *, timeout: float):
        sent.append(req["model"])
        return {}, _404
    monkeypatch.setattr(llm_seat, "_post_with_degrade", post)
    text, err = llm_seat.chat("hi", seat=_seat())
    assert text == "" and err and "No endpoints found" in err
    assert sent == [DEAD]


def test_last_resolved_names_the_model_that_answered_not_the_pin(monkeypatch):
    _listing(monkeypatch, LISTED)

    def post(url: str, key: str, req: dict[str, Any], *, timeout: float):
        if req["model"] == DEAD:
            return {}, _404
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}, None
    monkeypatch.setattr(llm_seat, "_post_with_degrade", post)
    monkeypatch.setattr(llm_seat, "_record_spend", lambda s, m, b: None)
    seat = _seat()
    assert llm_seat.chat("hi", seat=seat) == ("ok", None)
    got = llm_seat.last_resolved(seat)
    assert got.startswith("deepseek/") and got != DEAD


def test_a_vendor_locked_seat_never_crosses_to_another_family(monkeypatch):
    _listing(monkeypatch, ["qwen/qwen3-235b-a22b:free", "openai/gpt-5"])
    llm_seat.note_dead(_seat(), DEAD, _404)
    locked = llm_seat.Seat(name="deepseek_bulk", base_url=OR, key="k", model=DEAD,
                           lock_vendor=True)
    model, err = llm_seat.discover_model(locked)
    assert model == "" and err and "vendor-locked" in err


def test_the_deepseek_cycle_goes_red_on_zero_proposals():
    from scripts.run_deepseek_cycle import red_exit
    assert red_exit({"status": "CALL_FAILED", "why": _404}) == 1
    assert red_exit({"status": "OK", "n_findings": 0}) == 1
    assert red_exit({"status": "OK", "n_findings": 3}) == 0
    for hold in ("DARK", "BUDGET_EXHAUSTED", "MODEL_UNAVAILABLE", "BLOCKED_POLICY"):
        assert red_exit({"status": hold}) == 0
