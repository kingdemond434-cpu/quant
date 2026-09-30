"""The desk wiring for both parts: the organs publish to the three doors (axis, lake, allocation
intel) in the shapes their readers take, the exogenous conditioner can execute a published lake
frame, and the direct cells carry the full schema through the donor door."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blog_social_mining as bsm  # noqa: E402
import nlp_event_factors as nef  # noqa: E402
import nlp_social_cells as nsc  # noqa: E402

from libs.data import blog_social_sources as bss  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "nlp_blog_social"
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def test_blog_organ_fetches_once_stamps_first_seen_and_publishes_three_doors(
        tmp_path: Path) -> None:
    body = (FIX / "hatena_search.rdf").read_text("utf-8")
    spec = bss.BY_ID["hatena_hotentry_economics_rss"]
    store = tmp_path / "store"
    a = bsm.fetch_pass(NOW, store=store, get=lambda url: body, sources=(spec,), pause_s=0,
                       feeds_cfg=tmp_path / "none.json")
    b = bsm.fetch_pass(NOW + timedelta(hours=1), store=store, get=lambda url: body,
                       sources=(spec,), pause_s=0, feeds_cfg=tmp_path / "none.json")
    assert a["new_posts"] == 2 and b["new_posts"] == 0          # the cursor holds
    rows = [json.loads(x) for x in (store / "posts.jsonl").read_text("utf-8").splitlines()]
    assert {r["first_seen_at"] for r in rows} == {NOW.isoformat()}  # never re-stamped
    assert json.loads((store / "observed_days.json").read_text("utf-8"))["2026-09-30"]
    rep = bsm.build(NOW + timedelta(days=1), store=store, axis_out=tmp_path / "axes.json",
                    series_dir=tmp_path / "series", intel_out=tmp_path / "intel.json")
    assert rep["n_posts"] == 2 and rep["index_rows"] > 0
    axis = json.loads((tmp_path / "axes.json").read_text("utf-8"))
    assert axis["id"] == "blog_social" and isinstance(axis["series"], dict)
    frame = pd.read_parquet(tmp_path / "series" / "blog_social_USDJPY.parquet")
    assert {"available_time", "attention_delta_z", "attention_shock_signed"} <= set(frame)
    intel = json.loads((tmp_path / "intel.json").read_text("utf-8"))
    assert intel["use"] == "allocation_intel" and "USDJPY" in intel["instruments"]
    assert intel["instruments"]["USDJPY"]["crowd_state"] == "UNMEASURED"   # no trailing history


def test_nlp_organ_publishes_the_axis_door_with_the_knowable_date(tmp_path: Path) -> None:
    cb = tmp_path / "cb.jsonl"
    bis = tmp_path / "bis.jsonl"
    cb.write_text("\n".join(json.dumps({"published_utc": (NOW - timedelta(days=d)).isoformat(),
                                        "title": ("Bank of Japan raises the policy rate" if d % 2
                                                  else "BoJ keeps monetary easing"),
                                        "currency": "JPY", "link": f"https://boj/{d}"})
                            for d in range(1, 40)), "utf-8")
    bis.write_text(json.dumps({"date": "2026-06-19", "currency": "JPY", "title": "BoJ: rate hike",
                               "url": "https://www.bis.org/review/r260624c.htm"}), "utf-8")
    assert nef.bis_published("https://www.bis.org/review/r970211c.pdf") == datetime(
        1997, 2, 11, tzinfo=UTC)
    paths = {"store": tmp_path / "store", "axis": tmp_path / "axes" / "nlp_events.json",
             "series": tmp_path / "series", "report": tmp_path / "r.json",
             "intel": tmp_path / "intel.json", "cb": cb, "bis": bis}
    rep = nef.run(NOW, news=False, llm_max=0, paths=paths)
    assert rep["docs_by_source"] == {"cb_press": 39, "bis_review": 1}
    axis = json.loads(paths["axis"].read_text("utf-8"))
    pts = axis["series"]["lexicon.JP.monetary_tone_intensity"]["points"]
    # d is the KNOWABLE date: one day after the period it describes.
    assert all(p["d"] == (datetime.fromisoformat(p["period"]) + timedelta(days=1)).date()
               .isoformat() for p in pts)
    frame = pd.read_parquet(paths["series"] / "nlp_events_JP.parquet")
    assert {"available_time", "monetary_tone_drift", "monetary_tone_count"} <= set(frame)
    intel = json.loads(paths["intel"].read_text("utf-8"))
    usdjpy = intel["instruments"]["USDJPY"]["factors"]["monetary_tone"][0]
    assert usdjpy["orientation"] == -1 and usdjpy["drift_on_instrument"] == -usdjpy["drift"]


def _lake(series: Path, name: str, col: str, n: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-06-02", periods=n)
    series.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"period": days.strftime("%Y-%m-%d"),
                  "available_time": (days + pd.Timedelta(days=1)).strftime(
                      "%Y-%m-%dT00:00:00+00:00"),
                  col: rng.normal(size=n)}).to_parquet(series / f"{name}.parquet", index=False)


def test_the_exogenous_conditioner_executes_a_published_lake_frame(tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner

    _lake(tmp_path, "blog_social_USDJPY", "attention_shock_signed", 300, 1)
    idx = pd.date_range("2025-06-01", periods=24 * 300, freq="h", tz="UTC")
    px = 150 + np.cumsum(np.random.default_rng(2).normal(0, 0.05, len(idx)))
    bars = pd.DataFrame({"open": px, "high": px + 0.05, "low": px - 0.05, "close": px},
                        index=idx)
    sig = family_exogenous_conditioner(bars, source="blog_social_USDJPY",
                                       signal="attention_shock_signed", transform="level_z",
                                       threshold=1.5, side_when_high=-1, series_root=tmp_path)
    assert sig, "a published frame the family cannot read is a direct cell nothing executes"


def test_cells_carry_the_full_schema_and_go_through_the_donor_door(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    series = tmp_path / "series"
    _lake(series, "nlp_events_JP", "monetary_tone_drift", 200, 3)
    _lake(series, "blog_social_USDJPY", "attention_shock_signed", 30, 4)   # too short yet
    days = pd.bdate_range("2025-06-02", periods=260)
    close = pd.Series(150 * np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.005, 260))),
                      index=days)
    monkeypatch.setattr(nsc, "daily_closes", lambda sym: close if sym in ("USDJPY",
                                                                          "JPN225") else None)
    donated: dict[str, Any] = {}

    def fake_donate(source: str, cands: list[dict[str, Any]], tests_run: int) -> Path:
        donated.update(source=source, cands=cands, tests_run=tests_run)
        return tmp_path / "discoveries.json"

    from research import proposer_common as pc
    monkeypatch.setattr(pc, "donate", fake_donate)
    rep = nsc.run(dry_run=False, refresh=False, series_dir=series, out=tmp_path / "r.json",
                  n_placebo=50, n_boot=50)
    assert rep["admission"]["verdict"] in ("GAIN", "NO_GAIN_SHOWN")
    assert rep["admission"]["n_trials"] >= 2
    assert rep["cells_proposed"] == 2                          # JP policy drift on USDJPY, JPN225
    waiting = {(w["cell"], w["symbol"]) for w in rep["cells_waiting_for_history"]}
    assert ("attention_shock_reversal", "USDJPY") in waiting
    assert donated["source"] == nsc.SOURCE and donated["tests_run"] == rep["tests_run"]
    assert donated["tests_run"] >= rep["admission"]["n_trials"] + 2
    for c in donated["cands"]:
        assert c["family"] == "exogenous_conditioner"
        assert {"source", "signal", "transform", "threshold", "side_when_high"} <= set(c["params"])
        for key in ("mechanism", "payer", "constraint", "economic_actor", "source_culture",
                    "participant_structure", "failure_mode_hypothesis", "crowding_prior",
                    "falsifier", "required_data"):
            assert c[key], key
        assert c["provenance"]["source_culture"] == "JP/ja"
        assert c["evidence"]["gain_test"], "the admission evidence rides on the cell"
    assert {c["symbol"]: c["params"]["side_when_high"] for c in donated["cands"]} == {
        "USDJPY": -1, "JPN225": -1}


def test_share_cfds_are_never_direct_cells() -> None:
    direct = set(nsc.ATTENTION_SYMBOLS) | {s for _c, s, _side in nsc.POLICY_CELLS}
    assert not {"NVIDIA", "MicronTechnology", "TSMC", "AMD", "Intel"} & direct
