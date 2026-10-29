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
    monkeypatch.setattr(llm_seat, "_SWAP_NOTED", {})
    monkeypatch.setattr(llm_seat, "_LEDGER_CACHE", {"key": None, "rows": []})


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
    assert llm_seat.is_dead_endpoint(_404, DEAD)
    assert llm_seat.is_dead_endpoint(
        f'HTTP 400: {{"error":{{"message":"{DEAD} is not a valid model ID"}}}}', DEAD)
    # Not retirement, though the words overlap: the account, a capability, a parameter, a key.
    for body in (
        "HTTP 404: No endpoints found matching your data policy (Free model publication)",
        "HTTP 404: No endpoints found that can handle the requested parameters.",
        "HTTP 404: No endpoints found that support tool use.",
        "HTTP 404: No endpoints found that support image input.",
        f"HTTP 400: The model `{DEAD}` does not exist or you do not have access to it.",
        f"HTTP 404: model {DEAD} not found",
        "HTTP 429: rate limited upstream",
        f"HTTP 503: No endpoints found for {DEAD}.",          # not a 400/404
        "HTTP 404: No endpoints found for deepseek/deepseek-r1:free-beta.",  # another id
    ):
        assert not llm_seat.is_dead_endpoint(body, DEAD), body
    assert not llm_seat.is_dead_endpoint(_404, "")
    assert not llm_seat.is_dead_endpoint(None, DEAD)


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


def test_a_data_policy_404_writes_off_nothing(monkeypatch):
    _listing(monkeypatch, LISTED)
    policy = "HTTP 404: No endpoints found matching your data policy (Free model publication)"
    sent: list[str] = []

    def post(url: str, key: str, req: dict[str, Any], *, timeout: float):
        sent.append(req["model"])
        return {}, policy
    monkeypatch.setattr(llm_seat, "_post_with_degrade", post)
    for _ in range(4):
        assert llm_seat.chat("hi", seat=_seat())[1] == policy
    assert sent == [DEAD] * 4 and _rows() == []


def test_more_than_the_hourly_cap_of_retirements_stops_swapping(monkeypatch):
    seat = _seat()
    for m in ("deepseek/a:free", "deepseek/b:free"):
        assert llm_seat.note_dead(seat, m, _404)
    assert not llm_seat.note_dead(seat, DEAD, _404)       # the account, not a catalogue
    assert DEAD not in llm_seat.dead_models(OR)


def test_a_corrupt_ledger_never_raises_through_chat(monkeypatch):
    _listing(monkeypatch, LISTED)
    llm_seat.SWAP_LEDGER.write_bytes(b'{"kind":"dead"\xff\xfe torn\n' + json.dumps(
        {"kind": "dead", "ts": datetime.now(UTC).isoformat(), "base_url": OR,
         "model": DEAD}).encode() + b"\n")
    assert llm_seat.dead_models(OR) == {DEAD}              # the good line survives
    monkeypatch.setattr(llm_seat, "_post_with_degrade", lambda *a, **k: (
        {"choices": [{"message": {"content": "ok"}}], "usage": {}}, None))
    monkeypatch.setattr(llm_seat, "_record_spend", lambda s, m, b: None)
    assert llm_seat.chat("hi", seat=_seat()) == ("ok", None)


def test_a_free_seat_never_falls_through_to_a_paid_flagship(monkeypatch):
    seat = llm_seat.Seat(name="x", base_url="https://direct.example/v1", key="k", model=DEAD)
    monkeypatch.setattr(llm_seat, "free_tier_only", lambda: False)
    _listing(monkeypatch, ["openai/gpt-5", "deepseek/deepseek-v3.2"])
    llm_seat.note_dead(seat, DEAD, _404)
    model, err = llm_seat.discover_model(seat)
    assert model == "" and err and "free-only" in err


def test_the_vendor_lock_holds_on_every_path(monkeypatch):
    _listing(monkeypatch, ["qwen/qwen3-235b-a22b:free"])
    paid_pin = llm_seat.Seat(name="deepseek_bulk", base_url=OR, key="k",
                             model="deepseek/deepseek-v3.2", lock_vendor=True)
    model, err = llm_seat.discover_model(paid_pin)          # a guard-refused pin, not a dead one
    assert model == "" and err and "vendor-locked" in err


def test_a_distill_is_not_a_same_vendor_replacement(monkeypatch):
    _listing(monkeypatch, ["deepseek/deepseek-r1-distill-llama-70b:free",
                           "deepseek/deepseek-chat-v3.1:free"])
    llm_seat.note_dead(_seat(), DEAD, _404)
    assert llm_seat.discover_model(_seat()) == ("deepseek/deepseek-chat-v3.1:free", None)


def test_a_failed_call_clears_the_last_resolved_name(monkeypatch):
    _listing(monkeypatch, LISTED)
    replies = iter([({"choices": [{"message": {"content": "ok"}}], "usage": {}}, None),
                    ({}, "HTTP 500: upstream")])
    monkeypatch.setattr(llm_seat, "_post_with_degrade", lambda *a, **k: next(replies))
    monkeypatch.setattr(llm_seat, "_record_spend", lambda s, m, b: None)
    seat = _seat()
    assert llm_seat.chat("hi", seat=seat) == ("ok", None)
    assert llm_seat.last_resolved(seat) == DEAD
    assert llm_seat.chat("hi", seat=seat)[1] == "HTTP 500: upstream"
    assert llm_seat.last_resolved(seat) == ""


def test_a_swap_is_written_once_an_hour_not_once_a_call(monkeypatch):
    _listing(monkeypatch, LISTED)
    llm_seat.note_dead(_seat(), DEAD, _404)
    for _ in range(5):
        assert llm_seat.discover_model(_seat())[0] != DEAD
    assert len([r for r in _rows() if r["kind"] == "swap"]) == 1


def test_a_failed_call_maps_to_a_hold_or_a_red_status():
    from libs.ops.deepseek_cycle import call_status
    from scripts.run_deepseek_cycle import red_exit
    budget = "free-tier daily request budget exhausted: 50 call(s) today. This is a SKIP"
    assert call_status(budget) == "BUDGET_EXHAUSTED"
    assert call_status("monthly LLM spend cap reached ($20.00 of $20.00)") == "BUDGET_EXHAUSTED"
    assert call_status("HTTP 429: rate limited upstream") == "RATE_LIMITED"
    assert call_status("model discovery failed: x ... vendor-locked ...") == "MODEL_RETIRED"
    assert call_status("HTTP 500: upstream") == "CALL_FAILED"
    assert red_exit({"status": "MODEL_RETIRED"}) == 1
    assert red_exit({"status": "RATE_LIMITED"}) == 0
    assert red_exit({"status": "BUDGET_EXHAUSTED"}) == 0
