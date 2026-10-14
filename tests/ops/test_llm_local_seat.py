"""The keyless local seat in llm_seat, and the machine-scope key read (2026-10-14)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops import free_chain, llm_seat, machine_env

URL = "http://127.0.0.1:11434/v1"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var, _, _ in llm_seat.KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    for var in (llm_seat.LOCAL_URLS_ENV, llm_seat.LOCAL_MODEL_ENV, "QUANT_FREE_TIER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(llm_seat, "SECRETS", tmp_path / "llm_panel.json")
    monkeypatch.setattr(llm_seat, "SPEND_LEDGER", tmp_path / "spend.jsonl")
    gauntlet = tmp_path / "external_gauntlet.py"
    gauntlet.write_text("def evidence_trim(c, ds):\n    return ds\n", encoding="utf-8")
    monkeypatch.setattr(llm_seat, "GAUNTLET", gauntlet)
    monkeypatch.setattr(free_chain, "local_blocked", lambda: "")
    return gauntlet


def _local(monkeypatch: pytest.MonkeyPatch, url: str = URL) -> None:
    monkeypatch.setenv(llm_seat.LOCAL_URLS_ENV, url)


def test_the_local_seat_is_last_and_keyless(monkeypatch: pytest.MonkeyPatch) -> None:
    _local(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-xxxxxxxx")
    got = llm_seat.seats()
    assert [s.name for s in got] == ["openrouter", "local"]
    assert got[-1].key == "" and llm_seat.is_local(got[-1])
    assert "Authorization" not in llm_seat._headers("")


@pytest.mark.parametrize(
    "url",
    ["http://10.0.0.5:11434/v1", "https://api.example.com/v1", "http://127.0.0.1.evil.com/v1"],
)
def test_a_non_loopback_local_url_is_refused(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    _local(monkeypatch, url)
    assert llm_seat.seats() == []
    assert "loopback" in llm_seat.local_dark()
    assert not [p for p in free_chain._local_providers() if url in p.base_url]


def test_the_local_seat_is_dark_until_the_lookahead_guard_lands(
    monkeypatch: pytest.MonkeyPatch, _isolate: Path
) -> None:
    _local(monkeypatch)
    _isolate.write_text("def run():\n    pass\n", encoding="utf-8")
    assert llm_seat.seats() == []
    assert "look-ahead" in llm_seat.local_dark()
    text, err = llm_seat.chat("hi")
    assert text == "" and err and "look-ahead" in err


def test_downgrade_tokens_do_not_refuse_local_models(monkeypatch: pytest.MonkeyPatch) -> None:
    _local(monkeypatch)
    seat = llm_seat.seats()[0]
    monkeypatch.setattr(
        llm_seat,
        "_get",
        lambda *a, **k: (
            {
                "data": [
                    {"id": "qwen2.5:7b-instruct-q4_K_M"},
                    {"id": "qwen2.5:14b-instruct-q4_K_M"},
                    {"id": "nomic-embed-text"},
                ]
            },
            None,
        ),
    )
    assert llm_seat.discover_model(seat) == ("qwen2.5:14b-instruct-q4_K_M", None)
    monkeypatch.setenv(llm_seat.LOCAL_MODEL_ENV, "quant-lab")
    pinned = llm_seat.seats()[0]
    model, err = llm_seat.discover_model(pinned)
    assert model == "" and err and "quant-lab" in err


def test_a_local_call_spends_nothing_and_leaves_the_cloud_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _local(monkeypatch)
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(llm_seat, "_get", lambda *a, **k: ({"data": [{"id": "quant-lab"}]}, None))

    def post(url: str, key: str, payload: bytes, **kw: Any) -> tuple[dict[str, Any], None]:
        sent.append({"url": url, "key": key, "req": json.loads(payload)})
        return {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 900},
        }, None

    monkeypatch.setattr(llm_seat, "_post", post)
    assert llm_seat.chat("hi", max_tokens=64) == ("ok", None)
    assert sent[0]["key"] == "" and sent[0]["url"].startswith(URL)
    assert sent[0]["req"]["max_tokens"] == 64 and "max_completion_tokens" not in sent[0]["req"]
    row = json.loads(llm_seat.SPEND_LEDGER.read_text("utf-8").splitlines()[0])
    assert row["seat"] == "local" and row["usd"] == 0.0 and row["free"] is True
    assert llm_seat.calls_today() == 0


def test_a_spent_cloud_day_falls_over_to_the_local_seat(monkeypatch: pytest.MonkeyPatch) -> None:
    _local(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-xxxxxxxx")
    monkeypatch.setattr(llm_seat, "free_budget_left", lambda now=None: 0)
    seat, why = llm_seat._resolve(None)
    assert seat is not None and seat.name == "local" and why == ""
    cloud = llm_seat.seats()[0]
    seat, why = llm_seat._resolve(cloud)
    assert seat is None and "exhausted" in why


def test_a_busy_box_holds_the_local_seat(monkeypatch: pytest.MonkeyPatch) -> None:
    _local(monkeypatch)
    monkeypatch.setattr(free_chain, "local_blocked", lambda: "box busy (90% CPU > 35%)")
    text, err = llm_seat.chat("hi")
    assert text == "" and err and "box busy" in err


def test_the_machine_scope_key_is_read_for_seat_keys_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("QUANT_SANDBOX", raising=False)
    monkeypatch.delenv("QUANT_MACHINE_ENV", raising=False)
    monkeypatch.delenv("JQUANTS_API_KEY", raising=False)
    monkeypatch.setattr(machine_env, "_registry", lambda name: f"reg-{name}")
    assert machine_env.value("OPENROUTER_API_KEY") == "reg-OPENROUTER_API_KEY"
    assert machine_env.value("JQUANTS_API_KEY") == ""
    assert machine_env.value("FRED_API_KEY") == ""
    assert llm_seat.seats()[0].source == "env:OPENROUTER_API_KEY"
    monkeypatch.setenv("QUANT_SANDBOX", "1")
    assert machine_env.value("OPENROUTER_API_KEY") == ""
    assert llm_seat.seats() == []


def test_the_registry_is_never_read_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(machine_env, "_registry", lambda name: "real-box-key")
    assert machine_env.value("OPENROUTER_API_KEY") == ""


def test_local_threads_cap() -> None:
    assert free_chain.local_threads(18) == 4
    assert free_chain.local_threads(4) == 2
