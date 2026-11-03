"""The cot_fx clock: weekly after Friday's CFTC release, honest UA, robots first, a refusal is a
hard stop -- and the leg is on the hourly core clock (before it, nothing ran mt5desk/fetch_cot.py
and the box's newest COT report was 2026-08-11).

Every test roots the organ at temp paths and a fake fetcher; nothing touches the network.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import fetch_cot as fc  # noqa: E402

from research import cot_fx_refresh as cfr  # noqa: E402

# 2026-10-27 is a Tuesday; its report is published Friday 10-30; the NEXT report (Tue 11-03)
# is published Friday 11-06, so a refresh is due from 2026-11-06 21:00 UTC.
TUE = datetime(2026, 10, 27, tzinfo=UTC)


def _cot(dirp: Path, last: datetime) -> None:
    dirp.mkdir(parents=True, exist_ok=True)
    t = pd.date_range(end=pd.Timestamp(last), periods=4, freq="7D")
    pd.DataFrame({"report_date": t, "open_interest_all": range(4)}).to_parquet(
        dirp / "gold.parquet", index=False)


def _fake(new_last: datetime | None = None, exc: Exception | None = None) -> SimpleNamespace:
    calls: list[Path] = []

    def fetch_all(out: Path) -> dict:
        calls.append(out)
        if exc is not None:
            raise exc
        if new_last is not None:
            _cot(out, new_last)
        return {"gold": {"rows": 4}}
    return SimpleNamespace(fetch_all=fetch_all, HardStop=fc.HardStop, calls=calls)


def _paths(tmp: Path) -> dict:
    return {"cot_dir": tmp / "cot", "out": tmp / "COT_FX_FETCH.json",
            "hard_stop": tmp / "COT_FX_HARD_STOP.json"}


def test_not_due_before_the_next_release_writes_a_receipt_and_fetches_nothing(
        tmp_path: Path) -> None:
    p = _paths(tmp_path)
    _cot(p["cot_dir"], TUE)
    fake = _fake()
    doc = cfr.run(now=datetime(2026, 11, 6, 20, 0, tzinfo=UTC), fetch=fake, **p)
    assert doc["status"] == "NOT_DUE" and fake.calls == []
    assert json.loads(p["out"].read_text("utf-8"))["status"] == "NOT_DUE"


def test_due_after_friday_release_fetches_and_records_the_new_report(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    _cot(p["cot_dir"], TUE)
    fake = _fake(new_last=datetime(2026, 11, 3, tzinfo=UTC))
    doc = cfr.run(now=datetime(2026, 11, 6, 21, 5, tzinfo=UTC), fetch=fake, **p)
    assert fake.calls == [p["cot_dir"]]
    assert doc["status"] == "FETCHED" and doc["newest_after"].startswith("2026-11-03")


def test_the_frozen_tape_of_2026_08_11_is_due_at_once(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    _cot(p["cot_dir"], datetime(2026, 8, 11, tzinfo=UTC))
    go, why = cfr.decide(cfr.newest_report(p["cot_dir"]), {},
                         datetime(2026, 11, 3, 20, 0, tzinfo=UTC), None)
    assert go, why


def test_no_newer_report_backs_off(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    _cot(p["cot_dir"], TUE)
    now = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)
    assert cfr.run(now=now, fetch=_fake(), **p)["status"] == "NO_NEW_REPORT"
    fake = _fake()
    doc = cfr.run(now=now.replace(hour=23), fetch=fake, **p)
    assert doc["status"] == "NOT_DUE" and "backoff" in doc["decision"] and fake.calls == []


def test_a_refusal_is_a_hard_stop_that_holds_until_a_person_clears_it(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    _cot(p["cot_dir"], TUE)
    now = datetime(2026, 11, 7, 1, 0, tzinfo=UTC)
    doc = cfr.run(now=now, fetch=_fake(exc=fc.HardStop("HTTP 403")), **p)
    assert doc["status"] == "HARD_STOP" and p["hard_stop"].exists()
    fake = _fake(new_last=datetime(2026, 11, 3, tzinfo=UTC))
    later = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
    held = cfr.run(now=later, fetch=fake, force=True, **p)
    assert held["status"] == "HELD" and fake.calls == []
    p["hard_stop"].unlink()
    assert cfr.run(now=later, fetch=fake, **p)["status"] == "FETCHED"


# ------------------------------------------------------------------ the fetcher's manners
class _Resp(io.BytesIO):
    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        self.close()


def _opener(robots: str | int, body: bytes | int = b"[]") -> object:
    def op(req: object, timeout: float) -> _Resp:
        url = req.full_url  # type: ignore[attr-defined]
        assert "Mozilla" not in req.get_header("User-agent")  # type: ignore[attr-defined]
        ans = robots if url.endswith("robots.txt") else body
        if isinstance(ans, int):
            raise urllib.error.HTTPError(url, ans, "x", None, None)  # type: ignore[arg-type]
        return _Resp(ans.encode() if isinstance(ans, str) else ans)
    return op


def test_the_user_agent_is_the_desks_honest_one() -> None:
    assert fc.UA.startswith("quant-mt5-research-desk/") and "Mozilla" not in fc.UA
    src = (DESK / "mt5desk" / "fetch_cot.py").read_text("utf-8")
    assert '"User-Agent": "Mozilla' not in src


def test_robots_disallow_403_and_a_waf_page_each_stop_the_run(tmp_path: Path) -> None:
    with pytest.raises(fc.HardStop, match="disallows"):
        fc.fetch_all(tmp_path, _opener("User-agent: *\nDisallow: /resource/\n"), log=lambda m: None)
    with pytest.raises(fc.HardStop, match="403"):
        fc.fetch_all(tmp_path, _opener("", 403), log=lambda m: None)
    with pytest.raises(fc.HardStop, match="WAF"):
        fc.fetch_all(tmp_path, _opener("", b"<html>challenge</html>"), log=lambda m: None)
    with pytest.raises(fc.HardStop, match="fail closed"):
        fc.fetch_all(tmp_path, _opener(500), log=lambda m: None)


def test_importing_the_writer_creates_no_directory() -> None:
    src = (DESK / "mt5desk" / "fetch_cot.py").read_text("utf-8")
    assert "\nOUT.mkdir(" not in src


# ------------------------------------------------------------------ the wiring
def test_the_leg_is_on_the_core_clock_with_budget_layer_department_and_board() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["cot_fx"] == "information"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("cot_fx", "research/cot_fx_refresh.py")' in src
    assert '"cot_fx": cfx' in src
    # it runs before the census that judges it
    assert src.index('_costed("cot_fx"') < src.index('_costed("dataset_usage"')
    from research import hourly_cycle as hc
    assert "cot_fx" in hc.CORE_LEGS
    assert hc.LEG_DEPARTMENT["cot_fx"] == "data"
    assert hc.LEG_BUDGET_SEC["cot_fx"] >= 300
    from research import issue_board as ib
    assert ("cot_fx", "desks/mt5/reports/COT_FX_FETCH.json", 3600,
            "research/cot_fx_refresh.py") in ib.CADENCE
    from desks.mt5.ops.components import own_artifact
    assert own_artifact("desks/mt5/research/cot_fx_refresh.py") == (
        "desks/mt5/reports/COT_FX_FETCH.json",)
    state = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    assert any(r.get("organ") == "leg:cot_fx" for r in state["organs"])
