"""LLM lab seats: every free model of every family, credited to the seat that answered.

Every test runs in a temporary root; nothing here writes the repository's own state."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from libs.ops import llm_lab_core as core
from libs.ops import llm_lab_seats as seats

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def families() -> dict[str, list[str]]:
    fams = core.family_specs(REPO)
    assert "formula" in fams, "the registered formula family is the exact-candidate IR"
    return fams


@pytest.fixture
def root(tmp_path: Path, families, monkeypatch) -> Path:
    uni = tmp_path / "desks/mt5/data/universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "GBPUSD": {"asset_class": "Forex"},
        "USDJPY": {"asset_class": "Forex"}, "XAUUSD": {"asset_class": "Commodities"},
    }), "utf-8")
    (tmp_path / "desks/mt5/data/data_registry.json").write_text(
        json.dumps({"datasets": {"cot_tff": {}}}), "utf-8")
    monkeypatch.setattr(core, "family_specs", lambda _root: families)
    return tmp_path


def _ctx(root: Path) -> dict[str, Any]:
    return core.context(root)


EXACT = {
    "object_type": "EXACT_CANDIDATE", "title": "USD driver impulse fades on EURUSD in NY",
    "symbols": ["eurusd"], "family": "formula",
    "params": {"expr": "mul(sign(delta(usd, 5)), ts_rank(vol, 48))", "norm": 240,
               "entry_z": 1.5, "side_mode": "fade", "hold_bars": 8, "stop_atr": 2.0, "rr": 1.5},
    "timeframe": "H1", "session": "ny", "direction": "both",
    "entry_rule": "enter at next open when |z| of expr over 240 bars >= 1.5, against its sign",
    "exit_rule": "exit after 8 bars or at target/stop", "stop_rule": "2.0 ATR(20)",
    "target_rule": "1.5 R", "holding_horizon": "8 H1 bars",
    "falsifier": "fade return <= 0 net of costs over the dev sample",
    "economic_mechanism": "dealers hedge USD index moves late in NY and over-shoot EURUSD",
    "forced_actor": "USD index hedgers", "mechanism_class": "inventory_hedging",
    "data_inputs": [{"series_id": "usd", "source": "desk driver"}],
}


def _packet(**sections: Any) -> dict[str, Any]:
    base = {"universe": {"symbols": 4}, "data_and_features": {"dirs": 1},
            "research_frontier": {"docket_rows": 1}, "conversion_inventory": {"queue": 1},
            "empirical_memory": {"rows": 1}, "portfolio_opportunity_state": {"sleeves": 1},
            "point_in_time_metadata": {"a": 1}, "resource_state": {"cpu": 4}}
    base.update(sections)
    return {"status": "MEASURED", "packet_hash": "p" * 64, "sections": base}


REG = {"data": [
    {"id": "deepseek/deepseek-chat-v4:free", "pricing": {"prompt": "0", "completion": "0"},
     "created": 2, "supported_parameters": ["response_format"]},
    {"id": "deepseek/deepseek-r2:free", "pricing": {"prompt": "0", "completion": "0"},
     "created": 3, "supported_parameters": ["reasoning"]},
    {"id": "qwen/qwen3:free", "pricing": {"prompt": "0", "completion": "0"}, "created": 9},
]}




def test_registry_seats_every_free_model_of_every_family_and_never_a_paid_one(root: Path) -> None:
    paid = {"id": "openai/gpt-9", "pricing": {"prompt": "0.01", "completion": "0.02"}}
    reg = seats.refresh_models(root, fetch=lambda _u: {"data": [*REG["data"], paid]}, now=NOW)
    assert reg["status"] == "MEASURED"
    assert {m["id"] for m in reg["models"]} == {"deepseek/deepseek-chat-v4:free",
                                                "deepseek/deepseek-r2:free", "qwen/qwen3:free"}
    assert reg["families"] == ["deepseek", "qwen"]


def test_coverage_slot_goes_to_the_least_called_seat_then_yield_ranks(root: Path) -> None:
    reg = seats.refresh_models(root, fetch=lambda _u: REG, now=NOW)
    attrib = {"by_model": {
        "deepseek/deepseek-chat-v4:free": {"calls": 10, "compiled": 9, "passed": 2},
        "deepseek/deepseek-r2:free": {"calls": 10, "compiled": 0},
        "qwen/qwen3:free": {"calls": 0}}}
    cov = seats.plan_seats("bulk", reg, attrib, coverage=True)
    assert cov["seats"][0] == "qwen/qwen3:free" and "coverage" in cov["why"]
    best = seats.plan_seats("bulk", reg, attrib)
    assert best["seats"][0] == "deepseek/deepseek-chat-v4:free"       # the producing seat leads
    spread = seats.plan_seats("bulk", reg, attrib, used={"deepseek/deepseek-chat-v4:free"})
    assert spread["seats"][-1] == "deepseek/deepseek-chat-v4:free"     # used seats drop behind
    assert seats.model_rate(attrib, "qwen/qwen3:free") == (1.0, "PROBATION")


def test_the_job_is_credited_to_the_seat_that_answered(root: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import llm_seat
    reg = seats.refresh_models(root, fetch=lambda _u: REG, now=NOW)
    tried: list[str] = []

    def fake_chat(_u: str, **kw: Any) -> tuple[str, str | None]:
        tried.append(kw["seat"].model)
        return ("", "429 rate limited") if len(tried) == 1 else ('{"objects": []}', None)

    monkeypatch.setattr(llm_seat, "chat", fake_chat)
    chat = seats.make_chat({"OPENROUTER_API_KEY": "k"}, reg, {})
    out = chat("u", "s", "bulk")
    assert out["model"] == tried[1] != tried[0]
    assert out["attempts"] == [{"provider": "openrouter", "model": tried[0],
                                "error": "429 rate limited"}]
    assert out["family"] == seats.model_family(tried[1])


def test_a_seat_swapped_inside_llm_seat_is_credited_to_the_model_that_answered(
        root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import llm_seat
    reg = seats.refresh_models(root, fetch=lambda _u: REG, now=NOW)
    monkeypatch.setattr(llm_seat, "chat", lambda _u, **_k: ('{"objects": []}', None))
    monkeypatch.setattr(llm_seat, "last_resolved", lambda _s: "qwen/qwen3-next:free",
                        raising=False)
    out = seats.make_chat({"OPENROUTER_API_KEY": "k"}, reg, {})("u", "s", "bulk")
    assert out["model"] == "qwen/qwen3-next:free" and out["family"] == "qwen"
    assert out["attempts"][0]["swapped_to"] == "qwen/qwen3-next:free"


def test_no_free_seat_listed_is_model_unavailable_not_a_paid_route(root: Path) -> None:
    reg = seats.refresh_models(root, fetch=lambda _u: {"data": [
        {"id": "openai/gpt-9", "pricing": {"prompt": "0.01"}}]}, now=NOW)
    assert seats.plan_seats("bulk", reg, {}, pin="openai/gpt-9")["seats"] == []
    dark = {"status": "UNMEASURED"}
    assert seats.plan_seats("bulk", dark, {}, pin="openai/gpt-9")["seats"] == []


def test_an_unreachable_registry_is_unmeasured_and_keeps_the_pin(root: Path) -> None:
    def boom(_u: str) -> Any:
        raise OSError("403")
    reg = seats.refresh_models(root, fetch=boom, now=NOW)
    assert reg["status"] == "UNMEASURED"
    assert seats.plan_seats("bulk", reg, {}, pin="deepseek/x:free")["seats"] == ["deepseek/x:free"]


def test_the_local_seat_takes_any_open_weight_family() -> None:
    assert seats.local_seat({"LLM_LAB_LOCAL_BASE_URL": "http://127.0.0.1:11434/v1",
                           "LLM_LAB_LOCAL_MODEL": "qwen3:14b"}) == (
        "http://127.0.0.1:11434/v1", "qwen3:14b")
    old = {"DEEPSEEK_LOCAL_BASE_URL": "u", "DEEPSEEK_LOCAL_MODEL": "m"}
    assert seats.local_seat(old) == ("u", "m")


def test_the_local_rung_refuses_anything_but_loopback() -> None:
    text, err = seats._local_chat("u", "s", "deepseek-r1:14b", "http://10.0.0.5:11434/v1")
    assert text == "" and err and err.startswith("LOCAL_REFUSED")
