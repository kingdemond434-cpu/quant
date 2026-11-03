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


# ------------------------------------------------------------------ cot_tff, the sibling
def _tff_zip(dates: list[str]) -> bytes:
    import zipfile
    head = ('"Market_and_Exchange_Names","Report_Date_as_YYYY-MM-DD","Open_Interest_All",'
            '"Dealer_Positions_Long_All","Dealer_Positions_Short_All"\n')
    body = "".join(f'"EURO FX - CHICAGO MERCANTILE EXCHANGE","{d}",100,10,20\n' for d in dates)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("FinFutYY.txt", head + body)
    return buf.getvalue()


def _tff_opener(robots: str | int, files: dict[int, bytes | int], seen: list[str]) -> object:
    def op(req: object, timeout: float) -> _Resp:
        url = req.full_url  # type: ignore[attr-defined]
        assert "Mozilla" not in req.get_header("User-agent")  # type: ignore[attr-defined]
        seen.append(url)
        if url.endswith("robots.txt"):
            if isinstance(robots, int):
                raise urllib.error.HTTPError(url, robots, "x", None, None)  # type: ignore[arg-type]
            return _Resp(robots.encode())
        year = int(url.rsplit("_", 1)[1].split(".")[0])
        ans = files.get(year, 404)
        if isinstance(ans, int):
            raise urllib.error.HTTPError(url, ans, "x", None, None)  # type: ignore[arg-type]
        return _Resp(ans)
    return op


def test_tff_is_honest_and_verifies_certificates() -> None:
    from mt5desk import fetch_tff
    src = (DESK / "mt5desk" / "fetch_tff.py").read_text("utf-8")
    assert "CERT_NONE" not in src and "check_hostname = False" not in src
    assert '"User-Agent": "Mozilla' not in src and "\nOUT.mkdir(" not in src
    assert fetch_tff.UA == fc.UA


def test_tff_refresh_fetches_this_year_and_merges_into_the_store(tmp_path: Path) -> None:
    from mt5desk import fetch_tff
    now = datetime(2026, 11, 7, tzinfo=UTC)
    seen: list[str] = []
    files = {y: _tff_zip([f"{y}-03-03"]) for y in fetch_tff.YEARS}
    files[2026] = _tff_zip(["2026-10-27", "2026-11-03"])
    got = fetch_tff.fetch_all(tmp_path, _tff_opener("", files, seen), log=lambda m: None, now=now)
    assert got["years"] == fetch_tff.YEARS and got["eur"]["newest"] == "2026-11-03"
    assert seen[0] == "https://www.cftc.gov/robots.txt"
    # a second, weekly refresh reads only the current year and keeps the history
    seen.clear()
    files[2026] = _tff_zip(["2026-11-03", "2026-11-10"])
    got = fetch_tff.fetch_all(tmp_path, _tff_opener("", files, seen), log=lambda m: None,
                              now=datetime(2026, 11, 14, tzinfo=UTC))
    assert got["years"] == [2026] and [u for u in seen if u.endswith(".zip")] == [
        "https://www.cftc.gov/files/dea/history/fut_fin_txt_2026.zip"]
    eur = pd.read_parquet(tmp_path / "eur.parquet")
    assert len(eur) == len(fetch_tff.YEARS) - 1 + 3   # 2018-2025 history + three 2026 reports


def test_tff_refusals_are_hard_stops(tmp_path: Path) -> None:
    from mt5desk import fetch_tff
    now = datetime(2026, 11, 7, tzinfo=UTC)
    quiet = {"log": lambda m: None, "now": now}
    with pytest.raises(fc.HardStop, match="disallows"):
        fetch_tff.fetch_all(tmp_path, _tff_opener("User-agent: *\nDisallow: /files/\n", {}, []),
                            **quiet)
    with pytest.raises(fc.HardStop, match="403"):
        fetch_tff.fetch_all(tmp_path, _tff_opener("", {2018: 403}, []), **quiet)
    with pytest.raises(fc.HardStop, match="non-zip"):
        fetch_tff.fetch_all(tmp_path, _tff_opener("", {2018: b"<html>waf</html>"}, []), **quiet)
    with pytest.raises(fc.HardStop, match="fail closed"):
        fetch_tff.fetch_all(tmp_path, _tff_opener(503, {}, []), **quiet)


def test_tff_rides_the_cot_fx_clock_with_its_own_receipt_and_hard_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = {"cot_dir": tmp_path / "cot_tff", "out": tmp_path / "COT_TFF_FETCH.json",
         "hard_stop": tmp_path / "COT_TFF_HARD_STOP.json"}
    _cot(p["cot_dir"], TUE)
    doc = cfr.run(now=datetime(2026, 11, 7, 1, 0, tzinfo=UTC), dataset="cot_tff",
                  fetch=_fake(exc=fc.HardStop("HTTP 429")), **p)
    assert doc["dataset"] == "cot_tff" and doc["writer"].endswith("fetch_tff.py")
    assert doc["status"] == "HARD_STOP" and p["hard_stop"].exists()
    assert cfr.TFF_OUT.name == "COT_TFF_FETCH.json" and cfr.TFF_DIR.name == "cot_tff"
    assert cfr.TFF_HARD_STOP_FILE != cfr.HARD_STOP_FILE
    calls: list[str] = []
    monkeypatch.setattr(cfr, "run", lambda **kw: calls.append(kw.get("dataset", "cot_fx"))
                        or {"status": "NOT_DUE"})
    assert cfr.main([]) == 0 and calls == ["cot_fx", "cot_tff"]


def test_the_registry_carries_cot_tff_on_the_weekly_box_clock() -> None:
    rows = json.loads((DESK / "data" / "data_registry.json").read_text("utf-8"))["datasets"]
    assert rows["cot_tff"]["path"] == "data/cot_tff/*.parquet"
    assert rows["cot_tff"]["cadence"] == "weekly" and rows["cot_tff"]["produced_on"] == "box"
    assert rows["eur_cot_blocked"]["superseded_by"] == "cot_tff"
