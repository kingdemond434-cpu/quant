"""A banned-family certificate is never counted: hygiene evicts it, reason on the row.

MEASURED 2026-09-30: the canon held 24 `discovered` certificates -- a family the principal
banned permanently (2026-09-22: "all discovery certificates are discarded n removed") -- and
every one was counted in the survivor total. `certificate_hygiene` now lists each with its
decision (EVICTED, re-home REFUSED with the reason) and, on --apply, moves it into the seal's
`retired_certificates` (which the canon publisher never revives) in the same pass that drops
`n`. The re-judge organ never re-queues a banned family.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import certificate_hygiene as ch  # noqa: E402
import rejudge_evicted as rj  # noqa: E402


def _row(sym: str, fam: str, params: dict | None) -> dict:
    spec = {"symbol": sym, "family": fam, "selector": "asia"}
    if params is not None:
        spec["params"] = params
    return {"sym": sym, "days": 300, "gated_at": "2026-09-03T11:06:39",
            "gates": {"in_sample_screen": {"passed": True, "sharpe": 0.2}},
            "shadow_spec": spec}


@pytest.fixture
def reg(tmp_path, monkeypatch):
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    paths = {"SURVIVORS": tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json",
             "CANON": tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json",
             "EVICTED": tmp_path / "reports" / "UNIVERSAL_SURVIVORS_UNRUNNABLE.json",
             "OUT": tmp_path / "reports" / "CERTIFICATE_HYGIENE.json",
             "BANNED_ARCHIVE": tmp_path / "reports" / "UNIVERSAL_SURVIVORS_BANNED.json"}
    for k, v in paths.items():
        monkeypatch.setattr(ch, k, v)
    monkeypatch.setattr(ch, "ROOT", tmp_path)
    surv = {"external.EURCHF.discovered.p=6c79": _row("EURCHF", "discovered",
                                                      {"feature": "dd_12", "band": [0.75, 0.9],
                                                       "horizon": 1, "side": -1}),
            "external.XAUUSD.session_range_breakout.rr=2.5_wb=12":
                _row("XAUUSD", "session_range_breakout", {"rr": 2.5, "wait_bars": 12}),
            "external.CADJPY.session_range_breakout": _row("CADJPY", "session_range_breakout",
                                                          None)}
    for p in (paths["SURVIVORS"], paths["CANON"]):
        p.write_text(json.dumps({"n": 3, "survivors": surv, "retired_certificates": {}}))
    return paths


def test_banned_rows_are_listed_with_a_decision_and_not_counted(reg) -> None:
    doc = ch.build()
    assert doc["n_banned"] == 1 and doc["n_unrunnable"] == 1
    assert doc["n_counted"] == 1                       # 3 held - 1 unrunnable - 1 banned
    b = doc["banned"][0]
    assert b["key"] == "external.EURCHF.discovered.p=6c79" and b["decision"] == "EVICTED"
    assert b["reason"] and b["rehome"].startswith("REFUSED")
    # A banned row is never also reported as an unrunnable zombie to be re-judged.
    assert all(z["family"] != "discovered" for z in doc["unrunnable"])


def test_apply_moves_banned_rows_to_retired_with_the_reason_and_drops_n(reg) -> None:
    doc = ch.build()
    out = ch.evict_banned(doc)
    assert out["evicted"] == 1
    for p in (reg["SURVIVORS"], reg["CANON"]):
        d = json.loads(p.read_text())
        assert "external.EURCHF.discovered.p=6c79" not in d["survivors"]
        assert d["n"] == 2 == len(d["survivors"])
        r = d["retired_certificates"]["external.EURCHF.discovered.p=6c79"]
        assert r["retired_reason"] and r["retired_by"] == "certificate_hygiene"
        assert r["shadow_spec"]["params"]["feature"] == "dd_12"      # kept whole, auditable
        assert d["banned_evicted"] == ["external.EURCHF.discovered.p=6c79"]
    assert json.loads(reg["BANNED_ARCHIVE"].read_text())["n"] == 1
    # Idempotent: the next pass finds nothing banned and changes nothing.
    again = ch.build()
    assert again["n_banned"] == 0 and ch.evict_banned(again) == {"evicted": 0}


def test_the_rejudge_organ_never_requeues_a_banned_family() -> None:
    rec = rj.recover("external.EURCHF.discovered.p=x", _row("EURCHF", "discovered", None), {})
    assert rec["ok"] is False and "banned" in rec["why"]
