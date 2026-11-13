"""SNB sight deposits (idea N5) in the futures-state factory.

Tested on what makes the series honest: the CSV's empty calendar scaffold is never read as data,
an observation is public only from the Monday 10:00 Zurich after its Friday, the cube is read at
most once a day and never against robots, a refusal is a hard stop, and the held seed gives the
series its history so it reaches cells before the first live read.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import futures_state as fs  # noqa: E402


@pytest.fixture
def tmp_desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fs, "RAW", tmp_path / "raw")
    monkeypatch.setattr(fs, "SERIES", tmp_path / "series")
    monkeypatch.setattr(fs, "ROOT", tmp_path)
    return tmp_path


def _csv(n_weeks: int = 60, start: str = "2024-01-05") -> str:
    """The cube's shape: two preamble lines, a header, and a daily scaffold with values only on
    Fridays."""
    lines = ['"CubeId";"snbgwdchfsgw"', '"PublishingDate";"2025-03-03 10:00"', "",
             '"Date";"D0";"Value"']
    fridays = set(pd.date_range(start, periods=n_weeks, freq="7D"))
    rng = np.random.default_rng(3)
    tg = 450000.0
    for d in pd.date_range(start, periods=n_weeks * 7, freq="D"):
        if d in fridays:
            tg += float(rng.normal(0, 2000))
            lines.append(f'"{d.date()}";"TG";"{tg:.0f}"')
            lines.append(f'"{d.date()}";"GI";"{tg * 0.9:.0f}"')
            lines.append(f'"{d.date()}";"UEB";"{tg * 0.1:.0f}"')
        else:
            for dim in ("TG", "GI", "UEB"):
                lines.append(f'"{d.date()}";"{dim}";""')
    return "\n".join(lines) + "\n"


def _reg(**extra: object) -> dict[str, object]:
    row = {"id": "snb_sight_deposits", "adapter": "snb_cube", "terms": "OPEN",
           "url": "https://data.snb.ch/api/cube/snbgwdchfsgw/data/csv/en",
           "targets": ["EURCHF", "USDCHF", "XAUUSD"]}
    row.update(extra)
    return {"sources": [row]}


def _robots_404(url: str) -> str:
    raise urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]


def test_scaffold_rows_are_not_observations() -> None:
    held = fs.snb_csv(_csv(60))
    assert len(held) == 60, "only the Fridays carry values"
    assert list(held.columns) == ["TG", "GI", "UEB"]
    assert (held.index.weekday == 4).all()
    assert fs.snb_csv("<html>maintenance</html>").empty


def test_an_observation_is_public_from_the_monday_10_zurich() -> None:
    obs = pd.Series(pd.to_datetime(["2025-01-03", "2025-07-04"]))   # winter and summer Fridays
    at = fs.snb_available(obs)
    assert str(at.iloc[0]) == "2025-01-06 09:00:00+00:00"   # CET = UTC+1
    assert str(at.iloc[1]) == "2025-07-07 08:00:00+00:00"   # CEST = UTC+2
    assert (at > pd.to_datetime(obs).dt.tz_localize("UTC")).all()


def _zurich(at: object) -> str:
    return str(pd.Timestamp(at).tz_convert("Europe/Zurich"))


def test_easter_monday_rolls_the_release_to_tuesday() -> None:
    assert fs._easter(2025).isoformat() == "2025-04-20"
    assert fs._easter(2024).isoformat() == "2024-03-31"
    at = fs.snb_available(pd.Series(pd.to_datetime(["2025-04-18"])))   # Friday of Easter week
    assert _zurich(at.iloc[0]) == "2025-04-22 10:00:00+02:00"           # Tuesday, not Monday


def test_whit_monday_and_1_august_roll_forward() -> None:
    at = fs.snb_available(pd.Series(pd.to_datetime(["2025-06-06", "2022-07-29"])))
    assert _zurich(at.iloc[0]) == "2025-06-10 10:00:00+02:00"   # Whit Monday 2025-06-09
    assert _zurich(at.iloc[1]) == "2022-08-02 10:00:00+02:00"   # 1 Aug 2022 was a Monday


def test_christmas_monday_rolls_past_both_christmas_holidays() -> None:
    at = fs.snb_available(pd.Series(pd.to_datetime(["2023-12-22"])))   # 25 Dec 2023 = Monday
    assert _zurich(at.iloc[0]) == "2023-12-27 10:00:00+01:00"


def test_new_year_monday_and_2_january_roll_to_3_january() -> None:
    at = fs.snb_available(pd.Series(pd.to_datetime(["2023-12-29"])))   # 1 Jan 2024 = Monday
    assert _zurich(at.iloc[0]) == "2024-01-03 10:00:00+01:00"


def test_an_ordinary_week_stays_on_monday() -> None:
    at = fs.snb_available(pd.Series(pd.to_datetime(["2025-03-07", "2025-10-17"])))
    assert _zurich(at.iloc[0]) == "2025-03-10 10:00:00+01:00"
    assert _zurich(at.iloc[1]) == "2025-10-20 10:00:00+02:00"


def test_publishing_date_is_used_only_when_later_and_only_for_the_latest_week() -> None:
    obs = pd.Series(pd.to_datetime(["2025-02-28", "2025-03-07"]))
    late = fs.snb_available(obs, "2025-03-11 14:30")        # a delayed release: later, kept
    assert _zurich(late.iloc[1]) == "2025-03-11 14:30:00+01:00"
    assert _zurich(late.iloc[0]) == "2025-03-03 10:00:00+01:00", "older weeks untouched"
    early = fs.snb_available(obs, "2025-03-10 09:00")       # earlier than computed: never used
    assert _zurich(early.iloc[1]) == "2025-03-10 10:00:00+01:00"
    stale = fs.snb_available(obs, "2025-03-03 10:00")       # the previous week's stamp
    assert _zurich(stale.iloc[1]) == "2025-03-10 10:00:00+01:00"
    assert fs.snb_available(obs, "not a date").equals(fs.snb_available(obs))
    assert fs.snb_publishing_date(_csv(3)) == "2025-03-03 10:00"
    assert fs.snb_publishing_date("<html/>") is None


def test_the_cached_csv_publishing_date_reaches_the_latest_stamp(tmp_desk: Path) -> None:
    text = _csv(80).replace("2025-03-03 10:00", "2025-07-15 16:00")   # last Friday 2025-07-11

    def get_text(url: str) -> str:
        return _robots_404(url) if url.endswith("robots.txt") else text

    _b, frames, _n = fs.build_market_series(_reg(), get=None, state={}, bars=lambda s: None,
                                            get_text=get_text)
    f = frames["snb_chf_sd"]
    last = pd.to_datetime(f["available_time"]).iloc[-1]
    assert _zurich(last) == "2025-07-15 16:00:00+02:00"
    assert (pd.to_datetime(f["available_time"]).iloc[:-1].dt.tz_convert("Europe/Zurich")
            .dt.hour == 10).all()


def test_features_are_weekly_changes_in_chf_billions_and_causal() -> None:
    held = fs.snb_csv(_csv(80))
    feat = fs.snb_features(held)
    tg = held["TG"] / 1000.0
    assert feat["snb_sd_w"].iloc[5] == pytest.approx(tg.iloc[6] - tg.iloc[5])
    assert "snb_sd_4w" in feat.columns and "snb_sd_gi_w" in feat.columns
    bumped = held.copy()
    bumped.iloc[60:, :] += 99999.0
    pd.testing.assert_frame_equal(fs.snb_features(held).iloc[:58],
                                  fs.snb_features(bumped).iloc[:58])


def test_build_mints_cells_for_the_named_targets_only(tmp_desk: Path) -> None:
    text = _csv(80)

    def get_text(url: str) -> str:
        return _robots_404(url) if url.endswith("robots.txt") else text

    built, frames, _n = fs.build_market_series(_reg(), get=None, state={}, bars=lambda s: None,
                                               get_text=get_text)
    f = frames["snb_chf_sd"]
    assert built["snb_chf_sd"]["targets"] == ["EURCHF", "USDCHF", "XAUUSD"]
    lag = pd.to_datetime(f["available_time"]) - pd.to_datetime(f["event_time"])
    assert (lag >= pd.Timedelta(days=3)).all()
    plan = fs.cell_plan(built, frames, frozenset({"EURCHF", "USDCHF", "XAUUSD", "EURUSD"}))
    assert plan and {p[3] for p in plan} == {"EURCHF", "USDCHF", "XAUUSD"}
    # Headline columns lead the queue.
    assert plan[0][1] in ("snb_sd_w", "snb_sd_4w")


def test_robots_disallow_means_no_data_read(tmp_desk: Path) -> None:
    calls: list[str] = []

    def get_text(url: str) -> str:
        calls.append(url)
        if url.endswith("robots.txt"):
            return "User-agent: *\nDisallow: /\n"
        return _csv(80)

    notes: list[dict[str, object]] = []
    held = fs.snb_collect(_reg()["sources"][0], get_text, {}, notes)  # type: ignore[index]
    assert held.empty
    assert all(u.endswith("robots.txt") for u in calls)
    assert any(n.get("why") == "robots disallows" for n in notes)


def test_refusal_is_a_hard_stop_and_reads_are_once_a_day(tmp_desk: Path) -> None:
    state: dict[str, object] = {}

    def refuse(url: str) -> str:
        if url.endswith("robots.txt"):
            return _robots_404(url)
        raise fs.HardStop(403, url)

    fs.snb_collect(_reg()["sources"][0], refuse, state, [])  # type: ignore[index]
    assert "snb_sight_deposits" in state["hard_stops"]  # type: ignore[operator]

    calls: list[str] = []

    def ok(url: str) -> str:
        calls.append(url)
        return _robots_404(url) if url.endswith("robots.txt") else _csv(80)

    state2: dict[str, object] = {}
    now = datetime(2026, 11, 13, 12, tzinfo=UTC)
    src = _reg()["sources"][0]  # type: ignore[index]
    fs.snb_collect(src, ok, state2, [], now)
    n = len(calls)
    fs.snb_collect(src, ok, state2, [], now)
    assert len(calls) == n, "a second read the same day is not made"
    held = fs.snb_collect(src, None, state2, [], now)
    assert len(held) == 80, "the cached CSV is served offline"


def test_seed_gives_history_before_the_first_live_read(tmp_desk: Path) -> None:
    fridays = pd.date_range("2020-01-03", periods=60, freq="7D")
    seed = {"data": {"TG": {str(d.date()): 500000.0 + 100 * i for i, d in enumerate(fridays)}}}
    (tmp_desk / "seed.json").write_text(json.dumps(seed), encoding="utf-8")
    held = fs.snb_collect(_reg(seed_path="seed.json")["sources"][0],  # type: ignore[index]
                          None, {}, [])
    assert len(held) == 60 and "TG" in held.columns
    built, _f, _n = fs.build_market_series(_reg(seed_path="seed.json"), get=None, state={},
                                           bars=lambda s: None, get_text=None)
    assert "snb_chf_sd" in built


def test_terms_not_open_yields_no_series_and_no_cells(tmp_desk: Path) -> None:
    """Terms-clean data only: a non-OPEN source mints nothing, the held seed included, makes no
    request, and says why in the report."""
    fridays = pd.date_range("2020-01-03", periods=60, freq="7D")
    seed = {"data": {"TG": {str(d.date()): 500000.0 + 100 * i for i, d in enumerate(fridays)}}}
    (tmp_desk / "seed.json").write_text(json.dumps(seed), encoding="utf-8")
    calls: list[str] = []

    def get_text(url: str) -> str:
        calls.append(url)
        return _csv(80)

    reg = _reg(terms="TO_CONFIRM", seed_path="seed.json", terms_clause="non-commercial clause",
               terms_url="https://www.snb.ch/en/srv/disclaimer_copyright",
               terms_read="2026-11-13")
    state: dict[str, object] = {}
    built, frames, notes = fs.build_market_series(reg, get=None, state=state,
                                                  bars=lambda s: None, get_text=get_text)
    assert "snb_chf_sd" not in built and "snb_chf_sd" not in frames
    assert calls == [], "no robots read, no data read"
    assert fs.cell_plan(built, frames, frozenset({"EURCHF", "USDCHF", "XAUUSD"})) == []
    minted = fs.mint(built, frames, frozenset({"EURCHF", "USDCHF", "XAUUSD"}), state,
                     dry_run=True)
    assert not minted.get("minted_by_series")
    assert {"source": "snb_sight_deposits",
            "status": "TERMS_BLOCKED: non-commercial clause "
                      "(https://www.snb.ch/en/srv/disclaimer_copyright, read 2026-11-13)"} in notes
    assert fs.snb_collect(reg["sources"][0], get_text, {}, []).empty  # type: ignore[index]
    assert not (tmp_desk / "series").exists()


def test_the_registry_row_is_terms_blocked() -> None:
    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    built, _f, notes = fs.build_market_series(
        {"sources": [s for s in reg["sources"] if s["id"] == "snb_sight_deposits"]},
        get=None, state={}, bars=lambda s: None, get_text=None)
    assert "snb_chf_sd" not in built
    assert any(str(n.get("status", "")).startswith("TERMS_BLOCKED: non-commercial clause "
               "(https://www.snb.ch/en/srv/disclaimer_copyright, read 2026-11-13)")
               for n in notes)


def test_registry_row_and_desk_seed_are_present() -> None:
    reg = json.loads(fs.REGISTRY.read_text(encoding="utf-8"))
    row = next(s for s in reg["sources"] if s["id"] == "snb_sight_deposits")
    assert row["adapter"] == "snb_cube"
    # Terms read 2026-11-13: non-commercial use only. Never OPEN until the principal rules.
    assert row["terms"] != "OPEN" and row.get("missed_growth") is True
    assert "disclaimer_copyright" in row["note"] and "non-commercial" in row["note"]
    assert set(row["targets"]) == {"EURCHF", "USDCHF", "XAUUSD"}
    seed = ROOT / row["seed_path"]
    if seed.exists():
        held = fs.snb_seed(json.loads(seed.read_text(encoding="utf-8")))
        assert len(held) >= 700
        assert len(fs.snb_features(held)) >= fs.MIN_ROWS
