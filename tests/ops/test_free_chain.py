"""The shared free chain: every LLM key the host holds is one route, a new key lights with no
code, rotation spreads calls, relays stay public-only, weekly credit caps read CAPPED, and the
evidence never carries a key."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.ops import cn_ensemble as cn
from libs.ops import free_chain as fc

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
FAKE = "sk-fake-DO-NOT-LEAK-7f3a9c"


def _models(url: str, key: str) -> list[str]:
    if "cerebras" in url:
        return ["gpt-oss-120b", "llama-3.3-70b"]
    if "github" in url:
        return ["openai/gpt-4.1", "openai/gpt-4.1-mini"]
    return ["qwen-max", "m1", "m2"]


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import openrouter_free as orf
    monkeypatch.setattr(orf, "resolve_key", lambda *a, **k: ("", ""))
    monkeypatch.delenv("FREE_CHAIN_OFF", raising=False)
    fc.reset()


def _by(rs: list[fc.Route]) -> dict[str, fc.Route]:
    return {r.name: r for r in rs}


def test_a_new_key_lights_a_route_with_no_code(tmp_path: Path) -> None:
    env = {"FREE_LLM_ACME_KEY": FAKE, "FREE_LLM_ACME_BASE": "https://api.acme.example/v1",
           "FREE_LLM_ACME_MODELS": "m1,m2", "FREE_LLM_ACME_DAILY": "7",
           "FREE_LLM_NOBASE_KEY": FAKE}
    rs = _by(fc.discover(env=env, root=tmp_path, list_models=_models))
    acme = rs["acme"]
    assert acme.lit and acme.kind == "env" and acme.models == ("m1", "m2")
    assert acme.daily_cap == 7 and not acme.relay
    assert not rs["nobase"].lit and "BASE" in rs["nobase"].why
    # listed when no _MODELS is given: every id the base serves
    env2 = {"FREE_LLM_ZED_KEY": FAKE, "FREE_LLM_ZED_BASE": "https://z.example/v1",
            "FREE_LLM_ZED_RELAY": "1"}
    z = _by(fc.discover(env=env2, root=tmp_path, list_models=_models))["zed"]
    assert z.lit and z.relay and z.models == ("qwen-max", "m1", "m2")
    # an http base never lights
    env3 = {"FREE_LLM_BAD_KEY": FAKE, "FREE_LLM_BAD_BASE": "http://insecure.example/v1"}
    assert not _by(fc.discover(env=env3, root=tmp_path, list_models=_models))["bad"].lit


def test_cerebras_github_and_cloudflare_alias_are_dark_without_keys_and_lit_with(
        tmp_path: Path) -> None:
    dark = _by(fc.discover(env={}, root=tmp_path, list_models=_models))
    for name in ("cerebras", "github_models", "cloudflare", "groq", "siliconflow", "hcnsec",
                 "agentrouter", "yjs"):
        assert name in dark and not dark[name].lit and dark[name].why.startswith("DARK")
    env = {"CEREBRAS": FAKE, "GITHUB_TOKEN": FAKE, "CLOUDFLARE_API_TOKEN": FAKE,
           "CLOUDFLARE_ACCOUNT_ID": "0" * 32, "GROQ": FAKE}
    lit = _by(fc.discover(env=env, root=tmp_path, list_models=_models))
    assert lit["cerebras"].lit and lit["cerebras"].models == ("gpt-oss-120b", "llama-3.3-70b")
    assert lit["github_models"].lit and "openai/gpt-4.1" in lit["github_models"].models
    assert lit["cloudflare"].lit and lit["cloudflare"].relay
    # the principal's own keys are not filtered to Chinese-lab ids
    assert not lit["cerebras"].relay and not lit["github_models"].relay
    assert "CLOUDFLARE_API_TOKEN" in lit["cloudflare"].key_envs


def _route(name: str, *, relay: bool = False, kind: str = "owner", **kw: Any) -> fc.Route:
    return fc.Route(name, kind, f"https://{name}.example/v1", FAKE + name, ("m",),
                    relay=relay, lit=True, weekly_name=name, **kw)


def test_rotation_spreads_calls_over_every_lit_route(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[str] = []

    def call(r: fc.Route, model: str, system: str, user: str, **kw: Any):
        served.append(r.name)
        return "ok", model, None

    monkeypatch.setattr(fc, "_call", call)
    chain = [_route("a"), _route("b"), _route("c")]
    for _ in range(6):
        text, _who, err = fc.ask("job_x", "public", "public", chain=chain, root=tmp_path,
                                 now=NOW)
        assert err is None and text == "ok"
    assert set(served) == {"a", "b", "c"} and all(served.count(n) == 2 for n in "abc")


def test_a_paid_seat_is_only_the_failover_tail(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[str] = []
    monkeypatch.setattr(fc, "_call", lambda r, m, s, u, **k: (served.append(r.name) or "ok",
                                                              m, None))
    chain = [_route("paid", kind="seat", paid=True), _route("free1"), _route("free2")]
    for _ in range(4):
        fc.ask("job_y", "public", "public", chain=chain, root=tmp_path, now=NOW)
    assert "paid" not in served


def test_failover_and_the_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def call(r: fc.Route, model: str, system: str, user: str, **kw: Any):
        return ("", model, "HTTP 503") if r.name == "a" else ("answer", model, None)

    monkeypatch.setattr(fc, "_call", call)
    monkeypatch.setattr(fc, "rotation", lambda rs, organ, now: list(rs))
    text, who, err = fc.ask("job_z", "public", "public", chain=[_route("a"), _route("b")],
                            root=tmp_path, now=NOW, job="translator")
    assert (text, who, err) == ("answer", "b/m", None)
    rows = [json.loads(x) for x in (tmp_path / fc.LEDGER).read_text("utf-8").splitlines()]
    assert [(r["provider"], r["ok"], r["job"]) for r in rows] == [
        ("a", False, "translator"), ("b", True, "translator")]
    assert FAKE not in (tmp_path / fc.LEDGER).read_text("utf-8")


def test_a_relay_never_sees_a_private_prompt(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[str] = []
    monkeypatch.setattr(fc, "_call", lambda r, m, s, u, **k: (served.append(r.name) or "ok",
                                                              m, None))
    relay_only = [_route("hcn", relay=True, kind="cn")]
    text, _who, err = fc.ask("j", "system", "see desks/mt5/data", chain=relay_only,
                             root=tmp_path, now=NOW)
    assert text == "" and err and served == []
    text, _who, err = fc.ask("j", "public", "public", chain=relay_only, root=tmp_path,
                             now=NOW, public=False)
    assert text == "" and served == []                 # an explicit private flag holds too
    both = [_route("hcn", relay=True, kind="cn"), _route("own")]
    for _ in range(3):
        fc.ask("j", "system", "see desks/mt5/data", chain=both, root=tmp_path, now=NOW)
    assert served == ["own"] * 3


def _relay_rows(root: Path, name: str, rows: list[dict[str, Any]]) -> None:
    p = root / cn.RELAY_LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"relay": name, **r}) + "\n")


def test_a_weekly_credit_cap_reads_capped_and_the_chain_fails_over(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = (NOW - timedelta(days=8)).isoformat()
    t1 = (NOW - timedelta(days=3)).isoformat()
    _relay_rows(tmp_path, "hcnsec", [{"utc": old}, {"utc": t1, "credits": 2.5},
                                     {"at": NOW.isoformat(), "provider": "hcnsec"}])
    used, stamps = cn.ledger_credits(tmp_path / cn.RELAY_LEDGER, "hcnsec",
                                     NOW - timedelta(days=7))
    assert used == 3.5 and len(stamps) == 2            # the 8-day-old row left the window
    hcn = _route("hcnsec", relay=True, kind="cn", weekly_cap=3)
    why, reset = fc.cap_state(hcn, NOW, tmp_path)
    assert why.startswith("CAPPED: weekly") and reset == (
        datetime.fromisoformat(t1) + timedelta(days=7)).isoformat(timespec="seconds")
    served: list[str] = []
    monkeypatch.setattr(fc, "_call", lambda r, m, s, u, **k: (served.append(r.name) or "ok",
                                                              m, None))
    for _ in range(3):
        _t, _w, err = fc.ask("j", "public", "public", chain=[hcn, _route("own")],
                             root=tmp_path, now=NOW)
        assert err is None
    assert served == ["own"] * 3
    # the generic mechanism: any provider declaring weekly_cap / weekly_env, env-overridable
    p = cn.Provider("acme", "K", "B", "https://x", relay=True, weekly_cap=10, weekly_env="AW")
    assert cn.weekly_cap_of(p, {}) == 10 and cn.weekly_cap_of(p, {"AW": "4"}) == 4
    assert cn.weekly_left(tmp_path, p, {}, NOW) == (10, None)
    hp = next(x for x in cn.PROVIDERS if x.name == "hcnsec")
    assert cn.weekly_cap_of(hp, {}) == 500 and cn.weekly_cap_of(hp, {"HCNSEC_WEEKLY": "9"}) == 9


def test_provider_reported_credits_count_never_above_the_cap(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import llm_seat
    llm_seat._LAST_CALL.credits = None
    assert cn.credits_of_last_call(5) is None
    llm_seat._note_credits({"usage": {"credits": 7}})
    assert cn.credits_of_last_call(5) == 5.0 and cn.credits_of_last_call(0) == 7.0
    llm_seat._note_credits({"credits": 2})
    assert llm_seat.last_reported_credits() == 2.0
    llm_seat._LAST_CALL.credits = None


def test_the_report_lists_every_provider_and_never_a_key(tmp_path: Path) -> None:
    _relay_rows(tmp_path, "hcnsec", [{"utc": NOW.isoformat()}, {"utc": NOW.isoformat()}])
    led = tmp_path / fc.LEDGER
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text("\n".join(json.dumps(r) for r in [
        {"at": NOW.isoformat(), "provider": "cerebras", "organ": "conversion_lanes",
         "job": "translator", "ok": True},
        {"at": NOW.isoformat(), "provider": "cerebras", "organ": "kimi_hunt", "ok": False},
    ]) + "\n", "utf-8")
    env = {"CEREBRAS": FAKE, "HCNSEC": FAKE, "HCNSEC_WEEKLY": "2",
           "FREE_LLM_ACME_KEY": FAKE, "FREE_LLM_ACME_BASE": "https://a.example/v1"}
    path = tmp_path / fc.REPORT
    doc = fc.write_report(path=path, now=NOW, root=tmp_path, env=env, list_models=_models)
    text = path.read_text("utf-8")
    assert FAKE not in text
    rows = {r["provider"]: r for r in doc["providers"]}
    for name in ("openrouter_free", "cerebras", "github_models", "groq", "cloudflare",
                 "siliconflow", "hcnsec", "agentrouter", "yjs", "acme"):
        assert name in rows, name
    assert rows["cerebras"]["status"] == "LIT"
    assert rows["cerebras"]["calls_24h"] == 2 and rows["cerebras"]["ok_24h"] == 1
    assert rows["cerebras"]["by_job"] == {"translator": {"calls": 1, "ok": 1},
                                          "kimi_hunt": {"calls": 1, "ok": 0}}
    assert rows["hcnsec"]["status"] == "CAPPED" and rows["hcnsec"]["reset_at"]
    assert rows["hcnsec"]["public_prompts_only"] is True
    assert rows["github_models"]["status"] == "DARK"
    assert rows["acme"]["status"] == "LIT"
    assert doc["summary"]["lit"] >= 2 and doc["summary"]["capped"] == 1


def test_conversion_lanes_and_data_discovery_ride_the_shared_chain(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    if str(desk) not in sys.path:
        sys.path.insert(0, str(desk))
    from research import conversion_lanes as cl
    from research import data_discovery as dd
    seen: list[tuple[str, Any, Any]] = []

    def ask(organ: str, system: str, user: str, **kw: Any):
        seen.append((organ, kw.get("job"), kw.get("public")))
        return "text", "cerebras/m", None

    monkeypatch.setattr(fc, "ask", ask)
    assert cl.route_ask("s", "u") == ("text", "cerebras/m", None)
    assert cl.route_ask("s", "u", job="near_miss", public=False)[1] == "cerebras/m"
    assert seen[-1] == (cl.SEAT, "near_miss", False)
    monkeypatch.setattr(fc, "routes", lambda organ, **kw: [_route("cerebras")])
    assert len(dd.seat_chain()) == 1
    # the data-discovery prompt is public, so relays may serve it
    assert fc.is_public(dd.SYSTEM, dd.prompt_block())
    doc = dd.run_job(root=tmp_path, now=NOW)
    assert seen[-1][0] == dd.LANE and doc["served_by"] == "cerebras:m"
    assert doc["status"] in ("RAN", "NO_ANSWER") and doc["routes"] == 1


def test_the_chain_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FREE_CHAIN_OFF", "1")
    assert fc.ask("j", "s", "u", chain=[_route("a")])[2].startswith("free chain switched off")
