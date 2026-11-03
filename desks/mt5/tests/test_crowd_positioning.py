"""crowd_positioning: PIT retail long share from Myfxbook's API, and contrarian cells on it."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import crowd_positioning as cp  # noqa: E402

AT = datetime(2026, 10, 13, 17, 0, tzinfo=UTC)
DOC = {"error": False, "symbols": [
    {"name": "EURUSD", "longPercentage": 62, "shortPercentage": 38, "longVolume": 300.0,
     "shortVolume": 100.0, "totalPositions": 5000},
    {"name": "XAUUSD", "longPercentage": 71, "longVolume": 0, "shortVolume": 0}]}


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp, "SERIES", tmp_path / "series" / "myfxbook_outlook.parquet")
    monkeypatch.setattr(cp, "SESSION_CACHE", tmp_path / "secrets" / "session.json")
    monkeypatch.setattr(cp, "STATE", tmp_path / "state.json")
    for env in (cp.ENV_SESSION, cp.ENV_EMAIL, cp.ENV_PASSWORD):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(cp, "read_key", lambda name: cp.os.environ.get(name, ""))


def test_one_outlook_is_one_stamped_wide_row() -> None:
    row = cp.outlook_row(DOC, AT)
    assert row["available_time"] == AT.isoformat() and row["source_id"] == cp.SOURCE
    assert row["EURUSD_long_pct"] == 62.0 and row["EURUSD_long_vol_pct"] == 75.0
    assert row["EURUSD_positions"] == 5000.0
    assert row["XAUUSD_long_pct"] == 71.0 and "XAUUSD_long_vol_pct" not in row


def test_rows_append_and_history_counts_per_symbol() -> None:
    for h in range(3):
        cp.append_row(cp.outlook_row(DOC, AT.replace(hour=h)))
    cp.append_row(cp.outlook_row(DOC, AT.replace(hour=2)))          # same stamp: not twice
    assert cp.history() == {"EURUSD": 3, "XAUUSD": 3}


def test_no_credentials_is_blocked_on_key_by_name() -> None:
    with pytest.raises(cp.SessionError, match="BLOCKED_ON_KEY"):
        cp.session()


def test_login_errors_never_carry_the_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cp.ENV_EMAIL, "me@example.org")
    monkeypatch.setenv(cp.ENV_PASSWORD, "hunter2-secret")

    def refuse(req: Any, timeout: float = 0) -> Any:
        raise cp.urllib.error.URLError("boom " + req.full_url)

    monkeypatch.setattr(cp.urllib.request.OpenerDirector, "open", lambda self, req,
                        timeout=0: refuse(req))
    with pytest.raises(OSError) as err:
        cp.session()
    assert "hunter2" not in str(err.value) and "example.org" not in str(err.value)


def test_an_invalid_session_relogs_in_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cp.ENV_EMAIL, "me@example.org")
    monkeypatch.setenv(cp.ENV_PASSWORD, "pw")
    cp._write(cp.SESSION_CACHE, {"session": "stale"})
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(endpoint: str, query: dict[str, str], timeout: float = 25.0) -> dict:
        calls.append((endpoint, query))
        if endpoint == "login.json":
            return {"error": False, "session": "fresh%2B1"}
        if query["session"] == "stale":
            return {"error": True, "message": "Invalid session."}
        return DOC

    monkeypatch.setattr(cp, "_get", fake_get)
    assert cp.outlook() == DOC
    assert [c[0] for c in calls] == ["get-community-outlook.json", "login.json",
                                     "get-community-outlook.json"]
    assert calls[-1][1]["session"] == "fresh+1"
    assert json.loads(cp.SESSION_CACHE.read_text())["session"] == "fresh+1"


def test_cells_wait_on_history_then_donate_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import proposer_common as pc
    sent: list[list[dict]] = []
    monkeypatch.setattr(pc, "donate", lambda src, rows, n: sent.append(rows) or Path("x"))
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(sent[-1])})
    state: dict[str, Any] = {}
    early = cp.mint({"EURUSD": cp.MIN_OBSERVATIONS - 1}, {"EURUSD"}, state)
    assert early["donated"] == 0 and early["symbols_waiting"] == {"EURUSD": 29}
    ready = cp.mint({"EURUSD": cp.MIN_OBSERVATIONS, "NOTMT5": 99}, {"EURUSD"}, state)
    assert ready["symbols_ready"] == ["EURUSD"] and ready["donated"] == len(cp.grid("EURUSD"))
    fades = [r for r in sent[0] if r["family"] == "exogenous_conditioner"]
    assert {r["params"]["side_when_high"] for r in fades} == {-1, 1}
    assert all(r["params"]["signal"] == "EURUSD_long_pct" and r["params"]["lag_hours"] == 4
               for r in sent[0])
    again = cp.mint({"EURUSD": 99}, {"EURUSD"}, state)
    assert again["cells_due"] == 0 and len(sent) == 1


def test_the_call_cadence_respects_the_free_tier(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    cp._write(cp.STATE, {"last_call_at": datetime.now(tz=UTC).isoformat()})
    monkeypatch.setattr(cp, "outlook", lambda: pytest.fail("called inside the gap"))
    rec = cp.run(out=tmp_path / "out.json")
    assert rec["record"]["status"] == "NOT_DUE"


def test_hourly_leg_is_wired() -> None:
    text = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("crowd_positioning"' in text
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["crowd_positioning"] == "prediction"
