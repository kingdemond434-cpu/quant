"""COT positioning as a cross-asset state: the due gate, point-in-time ranking, and the state
vector carrying it. Synthetic contract files in a temp dir; no network."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import fetch_cot as F  # noqa: E402

from libs.regime.state_vector import StateVector  # noqa: E402


def _contract(out: Path, slug: str, last_tuesday: str, n: int = 200, rising: bool = True) -> None:
    dates = pd.date_range(end=pd.Timestamp(last_tuesday, tz="UTC"), periods=n, freq="7D")
    long_ = [1000 + (i if rising else -i) * 10 for i in range(n)]
    pd.DataFrame({"report_date": dates, "open_interest_all": [10_000.0] * n,
                  "noncomm_positions_long_all": long_,
                  "noncomm_positions_short_all": [1000.0] * n}).to_parquet(
        out / f"{slug}.parquet", index=False)


def test_a_report_is_invisible_until_its_release_lag_has_passed(tmp_path: Path) -> None:
    _contract(tmp_path, "gold", "2026-10-06")                  # Tuesday
    before = F.positioning_state(datetime(2026, 10, 9, 22, tzinfo=UTC), out=tmp_path)
    after = F.positioning_state(datetime(2026, 10, 10, 0, 1, tzinfo=UTC), out=tmp_path)
    assert before["contracts"]["gold"]["report_date"] == "2026-09-29"
    g = after["contracts"]["gold"]
    assert g["report_date"] == "2026-10-06" and g["available_at"].startswith("2026-10-10")
    assert g["rank_3y"] == 1.0 and g["crowding"] == "long_extreme" and g["z_3y"] > 0
    assert g["chg_1w"] == pytest.approx(0.001)
    assert after["instruments"]["XAUUSD"][0]["signed_rank"] == 1.0


def test_signs_follow_the_instrument_and_short_histories_are_unmeasured(tmp_path: Path) -> None:
    _contract(tmp_path, "jpy", "2026-10-06")                   # specs ever longer yen
    _contract(tmp_path, "aud", "2026-10-06", n=20)
    pos = F.positioning_state(datetime(2026, 10, 13, tzinfo=UTC), out=tmp_path)
    usdjpy = next(r for r in pos["instruments"]["USDJPY"] if r["contract"] == "jpy")
    assert usdjpy["sign"] == -1 and usdjpy["signed_rank"] == 0.0     # long yen = short USDJPY
    assert "aud" not in pos["contracts"] and pos["gaps"]["aud"].startswith("UNMEASURED")
    assert pos["gaps"]["gold"].startswith("UNMEASURED")             # no file at all
    for sym in {s for m in F.CONTRACT_INSTRUMENTS.values() for s in m}:
        import json
        uni = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
        assert sym in uni, sym


def test_due_follows_the_newest_public_report_and_backs_off(tmp_path: Path) -> None:
    for slug, _ in F.TARGETS:
        _contract(tmp_path, slug, "2026-09-29", n=60)
    _contract(tmp_path, "sp500", "2021-09-14", n=60)           # a renamed contract: never due
    now = datetime(2026, 10, 13, 17, tzinfo=UTC)               # 2026-10-06 is public
    go, why = F.due(now, tmp_path)
    assert go and "2026-10-06" in why
    tried = {"last_attempt": (now - timedelta(hours=1)).isoformat()}
    assert F.due(now, tmp_path, tried)[0] is False
    for slug, _ in F.TARGETS:
        _contract(tmp_path, slug, "2026-10-06", n=60)
    assert F.due(now, tmp_path)[0] is False
    (tmp_path / "eur.parquet").unlink()
    go, why = F.due(now, tmp_path)
    assert go is False and "never resolved: eur" in why


def test_the_state_vector_carries_positioning_through_a_round_trip() -> None:
    pos = {"status": "MEASURED", "contracts": {"gold": {"rank_3y": 0.9}}}
    sv = StateVector(at=datetime.now(tz=UTC).isoformat(), positioning=pos)
    back = StateVector.from_dict(sv.to_dict())
    assert back.positioning == pos
    assert StateVector.from_dict({"at": sv.at}).positioning == {}


def test_the_build_names_positioning_gaps_rather_than_inventing_a_state(tmp_path: Path,
                                                                       monkeypatch) -> None:
    sys.path.insert(0, str(_DESK / "research"))
    import state_vector_build as svb
    monkeypatch.setattr(F, "OUT", tmp_path)
    monkeypatch.setattr(F.positioning_state, "__defaults__", (None, tmp_path))
    gaps: dict[str, str] = {}
    assert svb.positioning_block(datetime(2026, 10, 13, tzinfo=UTC), gaps)["status"] == (
        "UNMEASURED")
    assert gaps["positioning"].startswith("UNMEASURED") and "positioning:gold" in gaps


def test_the_leg_writes_its_report_when_every_contract_is_unreachable(tmp_path: Path,
                                                                      monkeypatch) -> None:
    import json
    out, rep = tmp_path / "cot", tmp_path / "reports" / "COT_REFRESH.json"
    out.mkdir()
    _contract(out, "gold", "2026-08-11")
    monkeypatch.setattr(F, "OUT", out)
    monkeypatch.setattr(F, "DATA", tmp_path)
    monkeypatch.setattr(F, "REPORT", rep)

    def refused(commodity: str):
        raise OSError("Tunnel connection failed: 403 Forbidden")
    monkeypatch.setattr(F, "fetch_contract", refused)
    now = datetime(2026, 10, 13, 17, tzinfo=UTC)
    first = F.refresh(if_due=True, now=now)
    assert first["due"] is True and first["fetched"]["gold"].startswith("FAILED: OSError")
    doc = json.loads(rep.read_text("utf-8"))
    assert doc["positioning"]["contracts"]["gold"]["report_date"] == "2026-08-11"
    assert doc["last_attempt"] == now.isoformat(timespec="seconds")
    second = F.refresh(if_due=True, now=now + timedelta(hours=1))
    assert second["due"] is False and "retry after" in second["why"]
    assert second["last_attempt"] == first["last_attempt"]          # the stamp is carried
    assert not (out / "refresh_state.json").exists()
