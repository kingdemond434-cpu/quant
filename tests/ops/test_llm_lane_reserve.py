"""Lane reservations: no organ can starve the Chinese-model lanes of the free day (2026-11-20)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.ops import cn_ensemble as cn
from libs.ops import llm_seat

NOON = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
LATE = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_seat, "FREE_CEILING", tmp_path / "ceiling.json")
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", tmp_path / "spend.jsonl")
    monkeypatch.setattr(llm_seat, "LANE_RESERVE_FILE", tmp_path / "reserve.json")
    monkeypatch.setattr(llm_seat.openrouter_guard, "daily_limit", lambda **_: None)
    monkeypatch.setenv("QUANT_FREE_DAILY_MAX", "100")


def _spend(organ: str, n: int, when: datetime = NOON) -> None:
    with llm_seat.SPEND_LEDGER.open("a", encoding="utf-8") as fh:
        for _ in range(n):
            fh.write(json.dumps({"utc": when.isoformat(), "organ": organ}) + "\n")


def test_a_busy_organ_cannot_eat_the_reserved_lanes(monkeypatch) -> None:
    monkeypatch.setattr(llm_seat, "DEFAULT_LANE_RESERVE", {"run_cn_ensemble": 0.3})
    _spend("deepening_worker", 70)
    assert llm_seat.free_budget_left(NOON) == 30
    assert llm_seat.lane_budget_left("deepening_worker", NOON) == 0
    assert llm_seat.lane_budget_left("run_cn_ensemble", NOON) == 30


def test_the_reserve_shrinks_as_the_lane_spends_it(monkeypatch) -> None:
    monkeypatch.setattr(llm_seat, "DEFAULT_LANE_RESERVE", {"run_cn_ensemble": 0.3})
    _spend("run_cn_ensemble", 10)
    _spend("deepening_worker", 50)
    assert llm_seat.lane_budget_left("deepening_worker", NOON) == 40 - 20


def test_unspent_reserve_is_released_late_in_the_day(monkeypatch) -> None:
    monkeypatch.setattr(llm_seat, "DEFAULT_LANE_RESERVE", {"run_cn_ensemble": 0.3})
    _spend("deepening_worker", 70, LATE)
    assert llm_seat.lane_budget_left("deepening_worker", LATE) == 30


def test_box_file_overrides_and_can_never_reserve_everything() -> None:
    llm_seat.LANE_RESERVE_FILE.write_text(json.dumps({"a": 0.9, "b": 0.9}), "utf-8")
    table = llm_seat.lane_reserve()
    assert set(table) == {"a", "b"} and sum(table.values()) <= 0.8 + 1e-9
    llm_seat.LANE_RESERVE_FILE.write_text("not json", "utf-8")
    assert llm_seat.lane_reserve() == llm_seat.DEFAULT_LANE_RESERVE


def test_chat_skips_with_a_named_reason_when_the_lane_is_held(monkeypatch) -> None:
    monkeypatch.setattr(llm_seat, "DEFAULT_LANE_RESERVE", {"run_cn_ensemble": 0.5})
    monkeypatch.setenv("QUANT_LLM_ORGAN", "deepening_worker")
    _spend("deepening_worker", 50, datetime.now(UTC).replace(hour=0))
    monkeypatch.setattr(llm_seat, "RESERVE_RELEASE_HOUR_UTC", 25)
    seat = llm_seat.Seat(name="openrouter", base_url="https://x/v1", key="k", model="m:free")
    text, err = llm_seat.chat("hi", seat=seat)
    assert text == "" and err and "lane budget held" in err


def test_extra_provider_plugs_in_from_the_box_file(tmp_path: Path) -> None:
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    (tmp_path / cn.EXTRA_PROVIDERS_FILE).write_text(json.dumps([
        {"name": "acme", "base_url": "https://api.acme.cn/v1", "key": "sekret",
         "models": ["qwen-max"]},
        {"name": "Bad Name", "base_url": "https://x/v1", "key": "k"},
        {"name": "plain", "base_url": "http://insecure/v1", "key": "k"},
        {"name": "openrouter", "base_url": "https://dup/v1", "key": "k"},
        {"name": "envkey", "base_url": "https://e.cn/v1", "key_env": "MY_KEY"},
    ]), "utf-8")
    extras, overlay = cn.extra_providers(tmp_path, {"MY_KEY": "fromenv"})
    assert [p.name for p in extras] == ["acme", "envkey"]
    assert all(p.relay for p in extras)
    seat = cn.seat_for(extras[0], overlay)
    assert seat.lit and seat.models == ("qwen-max",) and seat.key == "sekret"
    assert overlay["CN_EXTRA_ENVKEY_KEY"] == "fromenv"


def test_run_lists_the_extra_provider_without_its_key(tmp_path: Path) -> None:
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    (tmp_path / cn.EXTRA_PROVIDERS_FILE).write_text(json.dumps([
        {"name": "acme", "base_url": "https://api.acme.cn/v1", "key": "sekret",
         "models": ["qwen-max"]}]), "utf-8")
    rep = cn.run(NOON, root=tmp_path, env={}, chat=lambda *a: ("[]", None),
                 quotas={"acme": 1})
    assert rep["providers"]["acme"]["lit"] is True
    assert "sekret" not in json.dumps(rep)
