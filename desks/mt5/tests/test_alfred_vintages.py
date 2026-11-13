"""ALFRED vintages on a clock: PIT layout, the key path the box uses, mint-once, the wiring."""
from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alfred_vintages as av  # noqa: E402
import fetch_alfred as fa  # noqa: E402
import hourly_cycle  # noqa: E402


def _vintages() -> pd.DataFrame:
    """Monthly series; each vintage publishes the next month and revises the previous one."""
    rows = []
    obs = pd.date_range("2018-01-01", periods=40, freq="MS")
    for k in range(14, 40):
        v = obs[k] + pd.Timedelta(days=45)                      # published ~45 days later
        for j in range(k + 1):
            val = 100.0 + j + (0.5 if j == k - 1 else 0.0)       # the previous month revised
            rows.append({"observation_date": obs[j], "realtime_date": v, "value": val})
    return pd.DataFrame(rows)


def test_pit_frame_reads_each_vintage_as_it_was_printed() -> None:
    f = av.pit_frame(_vintages())
    assert len(f) == 26
    # available at the END of the vintage date, never its start
    assert (f["available_time"] == f["realtime_date"].dt.tz_localize(UTC)
            + pd.Timedelta(days=1)).all()
    # the newest observation is never later than what that vintage could know
    assert (f["observation_date"] < f["realtime_date"]).all()
    last = f.iloc[-1]
    assert abs(last["yoy_pit"] - (139.0 / 127.0 - 1.0)) < 1e-9
    assert f["revision_pct"].iloc[0] != f["revision_pct"].iloc[0]   # NaN: no prior vintage
    assert (f["revision_pct"].iloc[1:] != 0).any()


def test_the_box_key_file_is_read(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    root = tmp_path
    (root / "data" / "secrets").mkdir(parents=True)
    (root / "data" / "secrets" / "fred.json").write_text(json.dumps({"key": "k123"}), "utf-8")
    fake = root / "desks" / "mt5" / "research" / "fetch_alfred.py"
    fake.parent.mkdir(parents=True)
    monkeypatch.setattr(fa, "__file__", str(fake))
    assert fa.api_key() == "k123"


def test_no_key_is_unmeasured_and_never_relabels_the_revised_series(tmp_path, monkeypatch
                                                                     ) -> None:
    monkeypatch.setattr(av, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(av, "VINTAGES", tmp_path / "alfred")
    monkeypatch.setattr(av, "SERIES_DIR", tmp_path / "series")
    monkeypatch.setattr(av, "STATE", tmp_path / "minted.json")
    monkeypatch.setattr(av, "lay_into_lake",
                        lambda series: {s: {"status": "UNMEASURED"} for s in series})
    doc = av.run(key="", dry_run=True)
    assert doc["status"] == "UNMEASURED" and doc["fetch"]["status"] == "UNMEASURED"
    assert not (tmp_path / "series").exists()
    assert json.loads((tmp_path / "r.json").read_text("utf-8"))["status"] == "UNMEASURED"


def test_refresh_refuses_a_single_vintage_and_keeps_fresh_files(tmp_path) -> None:
    now = datetime.now(tz=UTC)
    (tmp_path / "CPIAUCSL.parquet").write_bytes(b"x")       # fresh: not re-pulled
    one = _vintages()
    one = one[one["realtime_date"] == one["realtime_date"].max()]
    asked: list[str] = []

    def fetch(sid, key, gate=None):
        asked.append(sid)
        return one if sid == "GDPC1" else _vintages()
    rep = av.refresh(["CPIAUCSL", "GDPC1", "PAYEMS"], "k", budget_s=60, now=now,
                     fetch=fetch, out_dir=tmp_path)
    assert asked == ["GDPC1", "PAYEMS"]
    assert rep["fresh"] == ["CPIAUCSL"] and "GDPC1" in rep["failed"]
    assert rep["refreshed"] == ["PAYEMS"] and (tmp_path / "PAYEMS.parquet").exists()


def test_cells_are_minted_once(tmp_path, monkeypatch) -> None:
    import proposer_common as pc
    donated: list[int] = []
    monkeypatch.setattr(pc, "donate", lambda source, candidates, tests_run: (
        donated.append(len(candidates)) or tmp_path / "c.json"))
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": donated[-1]})
    lake = {"PAYEMS": {"status": "OK", "non_null": {"yoy_pit": 200, "revision_pct": 5}}}
    cells = av.grid(lake)
    assert len(cells) == len(av.SYMBOLS) * 2                   # revision_pct too short
    assert all(c["family"] == "exogenous_conditioner" for c in cells)
    assert all(c["params"]["source"] == "alfred_payems" for c in cells)
    st = tmp_path / "m.json"
    first = av.mint(cells, dry_run=False, state_path=st)
    again = av.mint(cells, dry_run=False, state_path=st)
    assert first["minted"] == len(cells) and again["new"] == 0 and donated == [len(cells)]


def test_the_leg_is_wired() -> None:
    src = inspect.getsource(hourly_cycle.main)
    assert '_costed("alfred_vintages"' in src and '"alfred_vintages": alfv' in src
    assert hourly_cycle.department_of("alfred_vintages") == "macro"
    assert hourly_cycle.LEG_BUDGET_SEC["alfred_vintages"] > 600
