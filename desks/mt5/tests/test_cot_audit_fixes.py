"""The #238 COT audit repairs (2026-10-07), each pinned by the defect it removes.

  * TFF files hold ONE contract, chosen by CFTC code (the name token used to admit cross-rates,
    and the dedup then kept whichever contract sorted last).
  * A positioning change is never a difference across a missing report week.
  * A report is labelled at its TRUE release: holiday weeks and appropriation lapses.
  * The verdict reader joins the gauntlet's ledger on prereg hash, cell id and graph id.
  * The refetch step fetches only a family behind the release schedule, and never writes less.
  * The NZD contract's 2022 rename ("NEW ZEALAND DOLLAR" -> "NZ DOLLAR") does not end its file.
  * The leg's runtime birth row exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import (  # noqa: E402
    cot_frames,
    cot_refetch,
    fetch_tff,
)
from mt5desk import families_orthogonal as fo  # noqa: E402

UTC = "UTC"


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=UTC)


# ---------------------------------------------------------------- TFF: one contract per file
def _raw(rows: list[tuple[str, str, str, int]]) -> pd.DataFrame:
    """A raw CFTC TFF frame: (date, market name, code, leveraged long)."""
    return pd.DataFrame({
        "Market_and_Exchange_Names": [r[1] for r in rows],
        "Report_Date_as_YYYY-MM-DD": [r[0] for r in rows],
        "CFTC_Contract_Market_Code": [r[2] for r in rows],
        "Open_Interest_All": ["100"] * len(rows),
        "Dealer_Positions_Long_All": ["0"] * len(rows),
        "Dealer_Positions_Short_All": ["0"] * len(rows),
        "Asset_Mgr_Positions_Long_All": ["0"] * len(rows),
        "Asset_Mgr_Positions_Short_All": ["0"] * len(rows),
        "Lev_Money_Positions_Long_All": [str(r[3]) for r in rows],
        "Lev_Money_Positions_Short_All": ["0"] * len(rows),
    })


EUR = ("099741", ("EURO FX - ",))
XGBP = "EURO FX/BRITISH POUND XRATE - CHICAGO MERCANTILE EXCHANGE"
XJPY = "EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE"


def test_tff_selects_the_outright_contract_by_code_not_by_name_token():
    raw = _raw([("2026-08-04", "EURO FX - CHICAGO MERCANTILE EXCHANGE", "099741", 10),
                ("2026-08-04", XGBP, "299741", 999),
                ("2026-08-04", XJPY, "399741", 777)])
    out = fetch_tff.pick(raw, *EUR)
    assert list(out["lm_l"]) == [10] and set(out["cftc_code"]) == {"099741"}


def test_tff_name_fallback_never_admits_a_cross_rate():
    stored = pd.DataFrame({"report_date": pd.to_datetime(["2026-07-28", "2026-08-04"] * 2,
                                                         utc=True),
                           "market": ["EURO FX - CHICAGO MERCANTILE EXCHANGE"] * 2 + [XGBP] * 2,
                           "lm_l": [1, 2, 9, 9]})
    out = fetch_tff.merge(stored, [], *EUR)
    assert list(out["lm_l"]) == [1, 2]
    assert out["report_date"].is_unique


def test_tff_merge_refuses_two_contracts():
    a = pd.DataFrame({"report_date": pd.to_datetime(["2026-07-28"], utc=True),
                      "market": ["X"], "cftc_code": ["099741"], "lm_l": [1]})
    b = a.assign(cftc_code="299741", report_date=pd.to_datetime(["2026-08-04"], utc=True))
    with pytest.raises(ValueError):
        fetch_tff.merge(None, [a, b], *EUR)


def test_nzd_rename_keeps_one_continuous_file(tmp_path):
    years = {2021: _raw([("2021-12-28", "NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE",
                          "112741", 1)]),
             2022: _raw([("2022-02-08", "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE", "112741", 2)])}
    doc = fetch_tff.run([2021, 2022], keep_existing=False, out=tmp_path, loader=years.get)
    assert doc["files"]["nzd"]["last"] == "2022-02-08"
    df = pd.read_parquet(tmp_path / "nzd.parquet")
    assert list(df["lm_l"]) == [1, 2]
    # and the in-git reader admits both names for NZDUSD
    assert {"NEW ZEALAND DOLLAR - ", "NZ DOLLAR - "} <= set(cot_frames.SOURCES["NZDUSD"][1][1])


def test_tff_failed_download_never_overwrites_with_less(tmp_path):
    keep = pd.DataFrame({"report_date": pd.to_datetime(["2026-08-04"], utc=True),
                         "market": ["EURO FX - CHICAGO MERCANTILE EXCHANGE"],
                         "cftc_code": ["099741"], "lm_l": [5]})
    keep.to_parquet(tmp_path / "eur.parquet", index=False)
    doc = fetch_tff.run([2026], keep_existing=True, out=tmp_path, loader=lambda _y: None)
    assert doc["failed"] == [2026]
    assert list(pd.read_parquet(tmp_path / "eur.parquet")["lm_l"]) == [5]


def test_committed_tff_files_hold_one_contract_per_date():
    for slug, code, prefixes in fetch_tff.TARGETS:
        path = cot_frames.TFF / f"{slug}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        assert df["report_date"].is_unique, slug
        want = tuple(p.upper() for p in prefixes)
        names = df["market"].astype(str).str.upper()
        assert all(m.startswith(want) for m in names), slug
        if "cftc_code" in df.columns:
            assert set(df["cftc_code"].astype(str)) == {code}, slug


# --------------------------------------------------------- no change across a missing week
def _bars(weeks: int = 200) -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=weeks * 120, freq="h", tz=UTC)
    close = 1.0 + np.cumsum(np.random.default_rng(1).normal(0, 0.001, len(idx)))
    return pd.DataFrame({"open": close, "high": close + 0.002, "low": close - 0.002,
                         "close": close, "volume": 1.0}, index=idx)


def test_change_is_nan_across_a_missing_report_week():
    idx = pd.to_datetime(["2026-07-06", "2026-07-13", "2026-08-10", "2026-08-17"], utc=True)
    cot = pd.DataFrame({"lev_net": [0.0, 1.0, 50.0, 52.0],
                        cot_frames.REPORT_WEEK: [100, 101, 105, 106]}, index=idx)
    ch = fo._adjacent_change(cot, "lev_net", 1)
    assert list(ch.index) == [idx[1], idx[3]]          # the 101 -> 105 jump is not a change
    assert list(ch) == [1.0, 2.0]
    two = fo._adjacent_change(cot, "lev_net", 2)
    assert two.empty                                    # no pair is exactly two weeks apart


def test_change_without_week_column_falls_back_to_label_gaps():
    idx = pd.to_datetime(["2026-07-06", "2026-07-13", "2026-08-10", "2026-08-18"], utc=True)
    cot = pd.DataFrame({"lev_net": [0.0, 1.0, 50.0, 52.0]}, index=idx)
    ch = fo._adjacent_change(cot, "lev_net", 1)
    # a 4-week gap is dropped; an 8-day gap (holiday-delayed label) is kept
    assert list(ch) == [1.0, 2.0]


def test_frame_carries_report_week_and_the_family_ignores_it_as_a_series():
    f = cot_frames.frame("USDJPY")
    assert f is not None and cot_frames.REPORT_WEEK in f.columns
    assert f.index.is_monotonic_increasing and f.index.is_unique
    sigs = fo.family_cot_positioning(_bars(), cot=f, series="lev_net", transform="change",
                                     extreme_pct=0.8)
    assert isinstance(sigs, list)
    assert cot_frames.REPORT_WEEK not in cot_frames.available("USDJPY")


# ------------------------------------------------------------------- true release labels
def _label(asof: str) -> pd.Timestamp:
    return cot_frames.release_label(_ts(asof))


def test_normal_week_label_is_unchanged():
    assert _label("2026-08-11") == _ts("2026-08-17")    # Monday after Friday's release


def test_monday_holiday_before_the_asof_date_moves_nothing():
    assert _label("2026-09-08") == _ts("2026-09-14")    # Labor Day Mon Sep 7


def test_tuesday_holiday_monday_asof_keeps_the_friday_release():
    assert _label("2023-07-03") == _ts("2023-07-10")    # Jul 4 2023 was a Tuesday


@pytest.mark.parametrize("asof,released_et", [
    ("2024-11-26", "2024-12-02 15:30"),                 # Thanksgiving Thu: release Monday
    ("2026-06-16", "2026-06-22 15:30"),                 # Juneteenth Fri Jun 19 2026
    ("2026-06-30", "2026-07-06 15:30"),                 # Jul 3 2026 (observed Jul 4)
    ("2026-11-10", "2026-11-16 15:30"),                 # Veterans Day Wed Nov 11 2026
    ("2025-01-07", "2025-01-13 15:30"),                 # Carter day of mourning Thu Jan 9
])
def test_holiday_week_is_labelled_after_its_true_release(asof, released_et):
    true = pd.Timestamp(released_et).tz_localize(cot_frames.ET).tz_convert(UTC)
    lab = _label(asof)
    assert lab >= true and lab - true < pd.Timedelta(hours=1)
    assert lab > _ts(asof) + pd.Timedelta(days=6)        # later than the old Monday label


@pytest.mark.parametrize("asof,published", [
    ("2025-10-07", "2025-11-21"),
    ("2019-01-08", "2019-02-08"),
    ("2013-10-01", "2013-10-25"),
])
def test_shutdown_report_is_labelled_after_its_catch_up_publication(asof, published):
    end_of_day = pd.Timestamp(f"{published} 23:59").tz_localize(cot_frames.ET).tz_convert(UTC)
    assert _label(asof) >= end_of_day


def test_schedule_is_strictly_increasing():
    sched = cot_frames.release_schedule()
    assert sched.is_monotonic_increasing and sched.is_unique
    assert (sched.values > sched.index.values).all()


def test_to_release_clock_uses_the_true_release():
    s = cot_frames.to_release_clock(pd.Series([1.0], index=[_ts("2024-11-26")]))
    assert s.index[0] > _ts("2024-12-02 20:00")


# -------------------------------------------------------------------- the verdict join
def test_verdicts_join_on_prereg_hash_cell_and_graph_id(tmp_path, monkeypatch):
    from research.frontier_identity import cell_id

    from libs.research.hypothesis_graph import node_id_for_spec
    from research import cot_positioning_flow as cpf
    seat = tmp_path / "seat"
    seat.mkdir()
    pa = {**cpf.PARAMS, "series": "mm_net", "mode": "fade"}
    pb = {**cpf.PARAMS, "series": "mm_net", "mode": "follow"}
    pc = {**cpf.PARAMS, "series": "swap_net", "mode": "fade"}
    (seat / "discoveries_20261006_0000.json").write_text(json.dumps({"discoveries": [
        {"symbol": "XAUUSD", "family": "cot_positioning", "params": pa, "prereg_hash": "abc123"},
        {"symbol": "XAUUSD", "family": "cot_positioning", "params": pb},
        {"symbol": "XAGUSD", "family": "cot_positioning", "params": pc}]}))
    monkeypatch.setattr(cpf, "SEAT", seat)
    ledger = tmp_path / "ledger.jsonl"
    spec_b = {"sym": "XAUUSD", "family": "cot_positioning", "params": pb}
    spec_c = {"sym": "XAGUSD", "family": "cot_positioning", "params": pc}
    rows = [
        {"family": "cot_positioning", "cell": "docket-name", "prereg_hash": "abc123",
         "terminal_gate": "in_sample_screen", "passed": False},
        {"family": "cot_positioning", "cell": cell_id(spec_b), "terminal_gate":
         "deflated_sharpe", "passed": False},
        {"family": "cot_positioning", "cell": "other", "graph_id": node_id_for_spec(spec_c),
         "terminal_gate": "deflated_sharpe", "passed": False},
        {"family": "cot_positioning", "cell": "XAUUSD.cot_positioning.p=deadbeef",
         "terminal_gate": "lockbox", "passed": True},           # not a donated cell
    ]
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(cpf, "VERDICTS", ledger)
    v = cpf.verdicts()
    assert v["status"] == "MEASURED" and v["cells_donated"] == 3 and v["cells_judged"] == 3
    assert v["joined_by"] == {"prereg_hash": 1, "cell": 1, "graph_id": 1}
    assert v["by_terminal_gate"] == {"in_sample_screen": 1, "deflated_sharpe": 2}
    assert v["passed"] == []


# ------------------------------------------------------------------------ the refetch step
def _store(data: Path, family: str, slug: str, dates: list[str]) -> Path:
    path = data / cot_refetch.DIRS[family] / f"{slug}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"report_date": pd.to_datetime(dates, utc=True), "x": range(len(dates))}
                 ).to_parquet(path, index=False)
    return path


def test_refetch_fetches_only_a_family_behind_the_release_schedule(tmp_path):
    now = _ts("2026-08-25 12:00")                         # Aug 18 report released Fri Aug 21
    _store(tmp_path, "legacy", "gold", ["2026-08-11"])     # behind
    _store(tmp_path, "tff", "eur", ["2026-08-18"])         # current
    _store(tmp_path, "disagg", "gold", ["2026-08-18"])     # current
    calls: list[str] = []

    def fetch(fam, data, _deadline):
        calls.append(fam)
        _store(data, fam, "gold", ["2026-08-11", "2026-08-18"])
        return {"gold": "WRITTEN"}
    doc = cot_refetch.run(now=now, data=tmp_path, fetch=fetch)
    assert calls == ["legacy"]
    assert doc["due_week"] == "2026-08-21"
    fams = doc["families"]
    assert fams["legacy"]["action"] == "FETCHED" and fams["legacy"]["caught_up"]
    assert fams["tff"]["action"] == fams["disagg"]["action"] == "CURRENT"


def test_refetch_waits_out_its_retry_window_and_never_raises(tmp_path):
    now = _ts("2026-08-25 12:00")
    _store(tmp_path, "legacy", "gold", ["2026-08-11"])
    calls: list[str] = []

    def boom(fam, _data, _deadline):
        calls.append(fam)
        raise OSError("cftc.gov unreachable")
    first = cot_refetch.run(now=now, data=tmp_path, fetch=boom)
    assert first["families"]["legacy"]["files"]["_error"].startswith("OSError")
    again = cot_refetch.run(now=now + pd.Timedelta(hours=1), data=tmp_path, fetch=boom)
    assert again["families"]["legacy"]["action"] == "WAITING_RETRY"
    later = cot_refetch.run(now=now + pd.Timedelta(hours=7), data=tmp_path, fetch=boom)
    assert later["families"]["legacy"]["action"] == "FETCHED"
    assert calls.count("legacy") == 2


def test_refetch_holds_a_holiday_delayed_report_until_its_release(tmp_path):
    # Thanksgiving 2024: the Nov 26 report is released Mon Dec 2 15:30 ET, not Fri Nov 29.
    _store(tmp_path, "legacy", "gold", ["2024-11-19"])
    doc = cot_refetch.run(now=_ts("2024-12-02 12:00"), data=tmp_path,
                          fetch=lambda *_a: {})
    assert doc["families"]["legacy"]["action"] == "CURRENT"
    doc = cot_refetch.run(now=_ts("2024-12-02 22:00"), data=tmp_path,
                          fetch=lambda *_a: {})
    assert doc["families"]["legacy"]["action"] == "FETCHED"


def test_write_if_not_less(tmp_path):
    path = _store(tmp_path, "legacy", "gold", ["2026-08-04", "2026-08-11"])
    short = pd.DataFrame({"report_date": pd.to_datetime(["2026-08-11", "2026-08-18"], utc=True)})
    assert cot_refetch.write_if_not_less(path, short) == "KEPT_STORED_HAS_MORE"
    full = pd.DataFrame({"report_date": pd.to_datetime(
        ["2026-08-04", "2026-08-11", "2026-08-18"], utc=True)})
    assert cot_refetch.write_if_not_less(path, full) == "WRITTEN"
    assert cot_refetch.write_if_not_less(path, None) == "NO_ROWS"


def test_the_leg_runs_the_refetch_step(monkeypatch, tmp_path):
    from research import cot_positioning_flow as cpf
    seen: dict = {}

    def fake_run(**kw):
        seen.update(kw)
        return {"families": {}}
    monkeypatch.setattr(cot_refetch, "run", fake_run)
    assert cpf.refetch(budget_s=5.0, dry_run=False)["status"] == "RAN" and seen["budget_s"] == 5.0
    assert cpf.refetch(budget_s=5.0, dry_run=True)["status"] == "SKIPPED_DRY_RUN"


# --------------------------------------------------------------------------- birth row
def test_leg_has_its_runtime_birth_row():
    doc = json.loads((_ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    assert "leg:cot_positioning_flow" in json.dumps(doc)
