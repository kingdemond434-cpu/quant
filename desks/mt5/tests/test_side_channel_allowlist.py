"""The box runs clear-access side channels only; every other channel is SET_ASIDE by name."""
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


def test_the_box_runner_allows_no_scraper_and_no_youtube() -> None:
    text = RUNNER.read_text("utf-8")
    line = next(x for x in text.splitlines() if "QUANT_MINERS_ALLOW=" in x)
    allowed = set(line.split("=", 1)[1].strip('"').split(","))
    assert allowed == {"cot", "central_bank", "weather", "github", "seasonality",
                       "correlations", "sec_edgar"}


def test_latest_discoveries_is_written_atomically_even_over_a_read_only_file(tmp_path) -> None:
    out = tmp_path / "latest_discoveries.json"
    out.write_text("{}", "utf-8")
    os.chmod(out, stat.S_IREAD)
    ram.write_atomic(out, json.dumps({"ok": 1}))
    assert json.loads(out.read_text("utf-8")) == {"ok": 1}
    assert not (tmp_path / "latest_discoveries.json.tmp").exists()


def test_a_blank_edgar_contact_is_not_configured_and_nothing_is_fetched(monkeypatch) -> None:
    """A whitespace-only value is not a contact: the channel is set aside, and the miner itself
    sends nothing (there is no placeholder User-Agent to fall back to)."""
    import sec_edgar_miner as sem
    _fake(monkeypatch, ["sec_edgar"])
    monkeypatch.delenv("QUANT_MINERS_ALLOW", raising=False)
    for n in sem.EDGAR_UA_NAMES:
        monkeypatch.setenv(n, "   ")
    assert ram.run_all_miners()["sec_edgar"]["status"] == "SET_ASIDE"
    assert sem.edgar_user_agent() == ""
    sent: list[str] = []
    monkeypatch.setattr(sem.requests, "get", lambda *a, **k: sent.append(a[0]))
    assert sem.mine_13f() == [] and sent == []
    monkeypatch.setenv("SEC_EDGAR_UA", " desk research contact@example.org ")
    assert sem.edgar_user_agent() == "desk research contact@example.org"
    assert "example.com" not in sem.__dict__.get("HEADERS", {}).get("User-Agent", "")
