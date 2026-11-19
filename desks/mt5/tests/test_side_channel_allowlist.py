"""Every side channel runs on the box (principal, 2026-11-19) except youtube, by standing rule;
a channel whose own site may not be fetched runs on its lawful feed, never on that site."""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_all_miners as ram  # noqa: E402

RUNNER = Path(__file__).resolve().parents[3] / "ops" / "run_side_channel_miners.cmd"


def _fake(monkeypatch, names):
    monkeypatch.setattr(ram, "ALL_MINERS", [(n, None) for n in names])
    monkeypatch.setattr(ram, "_run_miner", lambda name, fn: ("ok", [{"n": name}]))


def test_channels_outside_the_allowlist_are_set_aside_by_name_never_zero(monkeypatch) -> None:
    _fake(monkeypatch, ["cot", "tradingview", "youtube"])
    monkeypatch.setenv("QUANT_MINERS_ALLOW", "cot")
    r = ram.run_all_miners()
    assert r["cot"]["count"] == 1
    for name in ("tradingview", "youtube"):
        assert r[name]["status"] == "SET_ASIDE" and "count" not in r[name]
    assert r["summary"]["set_aside"] == ["tradingview", "youtube"] and r["summary"]["ran"] == 1


def test_sec_edgar_without_a_declared_user_agent_is_set_aside(monkeypatch) -> None:
    _fake(monkeypatch, ["sec_edgar"])
    monkeypatch.delenv("QUANT_MINERS_ALLOW", raising=False)
    monkeypatch.delenv("QUANT_EDGAR_UA", raising=False)
    assert ram.run_all_miners()["sec_edgar"]["status"] == "SET_ASIDE"
    monkeypatch.setenv("QUANT_EDGAR_UA", "desk research contact@example.org")
    assert ram.run_all_miners()["sec_edgar"]["count"] == 1


#: Channels that run their own module: an official API, open data, local computation, or a
#: host whose robots allows the path and whose terms are silent on automation (aaii).
OWN_ROUTE = {"cot", "central_bank", "weather", "github", "seasonality", "correlations", "aaii"}


def _allowed() -> set[str]:
    line = next(x for x in RUNNER.read_text("utf-8").splitlines() if "QUANT_MINERS_ALLOW=" in x)
    return set(line.split("=", 1)[1].strip('"').split(","))


def test_the_box_runner_runs_every_channel_but_youtube() -> None:
    names = {n for n, _ in ram.ALL_MINERS}
    assert len(names) == 25
    assert _allowed() == names - {"youtube"}


def test_every_allowed_channel_runs_its_own_lawful_route_or_its_substitute() -> None:
    import functools
    for name, fn in ram.ALL_MINERS:
        if name not in _allowed():
            continue
        if name in OWN_ROUTE:
            assert not isinstance(fn, functools.partial), name
        else:
            assert name in ram.SUBSTITUTES, f"{name} would fetch an unconfirmed or refused site"
            assert isinstance(fn, functools.partial) and fn.args == (name,), name


def test_the_box_key_name_edgar_ua_configures_sec_edgar_and_earnings(monkeypatch) -> None:
    import sec_edgar_miner
    _fake(monkeypatch, ["sec_edgar", "earnings"])
    monkeypatch.delenv("QUANT_MINERS_ALLOW", raising=False)
    for n in sec_edgar_miner.EDGAR_UA_NAMES:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr("libs.ops.env_keys.read_key", lambda n: os.environ.get(n, ""),
                        raising=False)
    r = ram.run_all_miners()
    assert r["sec_edgar"]["status"] == "SET_ASIDE" and r["earnings"]["status"] == "SET_ASIDE"
    monkeypatch.setenv("EDGAR_UA", "desk research contact@example.org")
    r = ram.run_all_miners()
    assert r["sec_edgar"]["count"] == 1 and r["earnings"]["count"] == 1


def test_latest_discoveries_is_written_atomically_even_over_a_read_only_file(tmp_path) -> None:
    out = tmp_path / "latest_discoveries.json"
    out.write_text("{}", "utf-8")
    os.chmod(out, stat.S_IREAD)
    ram.write_atomic(out, json.dumps({"ok": 1}))
    assert json.loads(out.read_text("utf-8")) == {"ok": 1}
    assert not (tmp_path / "latest_discoveries.json.tmp").exists()
