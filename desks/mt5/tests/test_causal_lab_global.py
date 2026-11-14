"""The causal lab's GLOBAL STREAMS pass: every stream is read at its own known-by stamp (an
unstamped one is excluded and counted), a planted lead over an MT5 return is found under one BH
charge and becomes a state-conditioned cell under a family the gauntlet rebuilds, a cell in a style
the book already holds is refused, a cell already donated is never donated again, novelty with
neither the classifier nor the artifact is UNMEASURED (never blocked, never assumed novel), and an
empty host is UNMEASURED rather than zero. Fixtures only; no network.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import causal_lab as cl  # noqa: E402

N_DAYS = 600


def _days(n: int = N_DAYS) -> list[str]:
    d0 = datetime(2024, 1, 1, tzinfo=UTC)
    return [(d0 + timedelta(days=i)).date().isoformat() for i in range(n)]


def _stamped_series(values: np.ndarray, hour: int = 6) -> pd.Series:
    idx = pd.to_datetime(_days(len(values)), utc=True) + pd.Timedelta(hours=hour)
    return pd.Series(values, index=idx)


def _ctx(sn: object = None, repeat: tuple[str, ...] = cl.REPEAT_STYLES_BASE,
         per_family: dict | None = None, present: bool = False) -> dict:
    return {"artifact": "STYLE_NOVELTY.json", "artifact_present": present,
            "classifier": "fake" if sn else "UNAVAILABLE", "classifier_note": "",
            "dominant_style_counts": {}, "repeat_styles": list(repeat),
            "per_family": per_family or {}, "novel_t": 0.5, "_sn": sn}


@pytest.fixture(scope="module")
def planted():
    """`lake:alt_gdelt_cn.tone` leads EURUSD by one day; `lake:fs_noise.v` leads nothing."""
    rng = np.random.default_rng(7)
    days = _days()
    lead = cl.Stream(name="lake:alt_gdelt_cn.tone", store="lake",
                     series=_stamped_series(rng.normal(0, 1, N_DAYS)), z_window=250,
                     cell={"family": "exogenous_conditioner",
                           "params": {"source": "alt_gdelt_cn", "signal": "tone",
                                      "transform": "level_z"}})
    noise = cl.Stream(name="lake:fs_noise.v", store="lake",
                      series=_stamped_series(rng.normal(0, 1, N_DAYS)), z_window=250,
                      cell={"family": "exogenous_conditioner",
                            "params": {"source": "fs_noise", "signal": "v",
                                       "transform": "level_z"}})
    x = cl.asof_days(cl.stream_z(lead), days)
    r = 0.004 * rng.normal(0, 1, N_DAYS)
    r[1:] += 0.004 * np.nan_to_num(x[:-1])
    other = 0.004 * rng.normal(0, 1, N_DAYS)
    returns = {"EURUSD": (days, r), "XAUUSD": (days, other)}
    return {"streams": [lead, noise], "returns": returns}


def _run(planted: dict, **kw):
    args = {"streams": planted["streams"], "excluded": [], "census": {},
            "returns": planted["returns"], "targets": list(planted["returns"]),
            "novelty": _ctx(), "prior": set()}
    args.update(kw)
    return cl.build_global(**args)


# --------------------------------------------------------------------------- point in time

def test_asof_reads_a_value_only_from_the_day_after_it_was_knowable():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01T06:00", "2024-01-02T23:59"],
                                                     utc=True))
    out = cl.asof_days(s, ["2024-01-01", "2024-01-02", "2024-01-03"])
    assert np.isnan(out[0])                 # stamped 06:00 on day 1: not knowable at 00:00 day 1
    assert out[1] == 1.0 and out[2] == 2.0  # day 2 sees day 1's value; day 3 sees day 2's


def test_asof_never_carries_a_dead_stream_forever():
    s = pd.Series([1.0], index=pd.to_datetime(["2024-01-01"], utc=True))
    late = (datetime(2024, 1, 1, tzinfo=UTC)
            + timedelta(days=cl.MAX_STALE_DAYS + 5)).date().isoformat()
    assert np.isnan(cl.asof_days(s, [late])[0])


def test_a_frame_without_available_time_is_excluded_and_counted(tmp_path):
    pd.DataFrame({"period": ["2024-01-01"] * 40, "value": range(40)}).to_csv(
        tmp_path / "pack_x.csv", index=False)
    excluded: list[dict] = []
    assert cl.read_tabular(tmp_path / "pack_x.csv", "lake", excluded) == []
    assert excluded and "no available_time" in excluded[0]["why"]


def test_a_stamped_lake_frame_becomes_an_executable_stream_and_bad_stamps_are_counted(tmp_path):
    stamps = [f"2024-01-{d:02d}T06:00:00+00:00" for d in range(1, 29)] + \
        [f"2024-02-{d:02d}T06:00:00+00:00" for d in range(1, 11)] + ["garbage", ""]
    pd.DataFrame({"available_time": stamps, "event_time": stamps, "value": np.arange(40.0),
                  "pace": np.arange(40.0) * 2}).to_csv(tmp_path / "alt_gdelt_cn.csv",
                                                        index=False)
    excluded: list[dict] = []
    got = cl.read_tabular(tmp_path / "alt_gdelt_cn.csv", "lake", excluded)
    assert {s.name for s in got} == {"lake:alt_gdelt_cn.value", "lake:alt_gdelt_cn.pace"}
    assert all(s.cell and s.cell["family"] == "exogenous_conditioner" for s in got)
    assert all(len(s.series) == 38 for s in got)
    assert any(e.get("kind") == "rows" and "2 row(s)" in e["why"] for e in excluded)
    raw = cl.read_tabular(tmp_path / "alt_gdelt_cn.csv", "raw", [])
    assert raw and all(s.cell is None and "raw landing" in s.why_not_executable for s in raw)


def test_text_store_counts_posts_on_first_seen_and_counts_the_unstamped(tmp_path):
    forum = tmp_path / "cn_retail_posts"
    forum.mkdir()
    lines = []
    for i in range(40):
        day = (datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i))
        for k in range(1 + i % 3):
            lines.append(json.dumps({"source": "guba", "ident": f"{i}-{k}",
                                     "first_seen_at": (day + timedelta(hours=5)).isoformat()}))
    lines.append(json.dumps({"source": "guba", "ident": "x"}))           # no first_seen_at
    (forum / "posts.jsonl").write_text("\n".join(lines), "utf-8")
    excluded: list[dict] = []
    got = cl.read_text_store(tmp_path, excluded)
    assert [s.name for s in got] == ["text:cn_retail_posts.posts"]
    s = got[0].series
    assert s.index[0] == pd.Timestamp("2024-01-02", tz="UTC")           # knowable next 00:00
    assert s.iloc[0] == 1.0 and s.iloc[2] == 3.0
    assert any("1 post(s)" in e["why"] for e in excluded)
    assert got[0].cell is None


def test_cot_is_read_at_knowable_at_plus_one_day_and_only_against_its_own_instrument(tmp_path):
    rows = [{"symbol": "XAUUSD", "knowable_at": d, "net_pct_oi": float(i)}
            for i, d in enumerate(_days(40))] + [{"symbol": "XAUUSD", "knowable_at": "2024-01",
                                                  "net_pct_oi": 1.0}]
    (tmp_path / "cot.json").write_text(json.dumps({"rows": rows}), "utf-8")
    excluded: list[dict] = []
    got = cl.read_cot(tmp_path, excluded)
    assert got[0].targets == ("XAUUSD",) and got[0].store == "cot"
    assert cl.land_streams(got, tmp_path / "lake")["landed"] == []   # cot_* families trade it
    assert got[0].series.index[0] == pd.Timestamp("2024-01-02", tz="UTC")
    assert any("1 COT row(s)" in e["why"] for e in excluded)


# --------------------------------------------------------------------------- discovery

def test_the_planted_lead_is_found_at_lag_one_and_the_noise_is_not(planted):
    doc = _run(planted)
    assert doc["status"] == "OK"
    assert doc["n_tests"] == 2 * 2 * len(cl.GLOBAL_LAGS)                 # every test in BH
    found = {(ln["stream"], ln["instrument"], ln["lag"]) for ln in doc["links"]}
    assert ("lake:alt_gdelt_cn.tone", "EURUSD", 1) in found
    assert not any(s == "lake:fs_noise.v" for s, _, _ in found)
    assert all(ln["q"] <= cl.FDR_Q for ln in doc["links"])


def test_a_link_becomes_a_state_conditioned_executable_cell(planted):
    doc = _run(planted)
    ln = next(x for x in doc["links"] if x["instrument"] == "EURUSD" and x["lag"] == 1)
    assert ln["cell_status"] == "EMITTED"
    assert ln["cell"]["family"] == "exogenous_conditioner"
    p = ln["cell"]["params"]
    assert p["source"] == "alt_gdelt_cn" and p["signal"] == "tone"
    assert p["side_when_high"] == 1 and p["threshold"] == cl.REGIME_Z and p["lag_hours"] == 24
    assert ln["statement"].startswith("when lake:alt_gdelt_cn.tone is")
    cand = next(c for c in doc["candidates"] if c["symbol"] == "EURUSD")
    assert cand["source"] == cl.GLOBAL_SOURCE and cand["kind"] == "hypothesis"
    assert cand["falsifier"] and cand["evidence"]["tests_in_bh"] == doc["n_tests"]


def test_a_world_stream_cell_trades_only_its_band(planted):
    w = planted["streams"][0]
    world = cl.Stream(name="world:IMF.cn_reserves", store="world_datasets", series=w.series,
                      z_window=250, cell={"family": "world_macro_state",
                                          "params": {"series_key": "IMF.cn_reserves",
                                                     "z_obs": 24}})
    doc = _run(planted, streams=[world])
    ln = next(x for x in doc["links"] if x["cell_status"] == "EMITTED")
    p = ln["cell"]["params"]
    assert ln["cell"]["family"] == "world_macro_state"
    assert (p["z_lo"], p["z_hi"]) in ((cl.REGIME_Z, 99.0), (-99.0, -cl.REGIME_Z))
    assert p["direction"] in ("long", "short")


def test_a_stream_with_no_family_is_measured_and_handed_off_not_emitted(planted):
    text = cl.Stream(name="text:cn_retail_posts.posts", store="text_store",
                     series=planted["streams"][0].series, z_window=250,
                     why_not_executable="a raw forum count has no executable family")
    doc = _run(planted, streams=[text])
    assert doc["links"] and doc["candidates"] == []
    assert all(ln["cell_status"] == "NOT_EMITTED" for ln in doc["links"])
    assert doc["landing"]["status"] == "SKIPPED"


def test_a_forum_stream_is_landed_as_a_lake_series_and_becomes_executable(planted, tmp_path):
    text = cl.Stream(name="text:cn_retail_posts.guba.posts", store="text_store",
                     series=planted["streams"][0].series, z_window=250,
                     why_not_executable="a raw forum count has no executable family")
    doc = _run(planted, streams=[text], land=True, series_dir=tmp_path)
    sid = "cg_text__cn_retail_posts_guba_posts"
    assert doc["landing"]["landed"] == [f"{sid}.csv"]
    frame = pd.read_csv(tmp_path / f"{sid}.csv")
    assert {"available_time", "value"} <= set(frame.columns) and len(frame) == N_DAYS
    from mt5desk.family_exogenous_conditioner import conditioner
    assert conditioner(sid, "value", "level_z", root=tmp_path) is not None   # the family reads it
    cand = next(c for c in doc["candidates"] if c["symbol"] == "EURUSD")
    assert cand["family"] == "exogenous_conditioner" and cand["params"]["source"] == sid


def test_the_lake_reader_skips_this_organs_own_landings(tmp_path):
    lake = tmp_path / "lake"
    lake.mkdir()
    pd.DataFrame({"available_time": ["2024-01-01T00:00:00+00:00"] * 40,
                  "value": range(40)}).to_csv(lake / "cg_text__x_posts.csv", index=False)
    streams, excluded, _ = cl.load_streams(
        lake=lake, raw=tmp_path / "b", vault=tmp_path / "c", axes_dir=tmp_path / "d",
        text=tmp_path / "e", world=tmp_path / "f", targets=[])
    assert streams == [] and excluded[0]["kind"] == "own_landing"


# --------------------------------------------------------------------------- novelty and trials

def _fake_classifier(dominant: str | None, novelty_return: float):
    def style_matrix(close, index, sigs, high=None, low=None):
        return np.ones(len(sigs)), np.ones((len(sigs), 10))

    def project(y, X):
        return {"status": "MEASURED", "n": len(y), "dominant_style": dominant,
                "novelty_return": novelty_return}
    return SimpleNamespace(style_matrix=style_matrix, project=project, NOVEL_T=0.5)


def test_a_cell_in_a_style_the_book_already_holds_is_refused(planted):
    doc = _run(planted, novelty=_ctx(_fake_classifier("passive_window", 0.1)))
    assert doc["candidates"] == []
    assert doc["novelty_verdicts"].get("REPEAT_STYLE")
    assert all(ln["cell_status"] == "REFUSED_REPEAT_STYLE" for ln in doc["links"]
               if ln.get("cell"))


def test_a_novel_cell_is_emitted_with_its_verdict(planted):
    doc = _run(planted, novelty=_ctx(_fake_classifier(None, 0.9)))
    assert doc["candidates"]
    assert doc["candidates"][0]["evidence"]["novelty"]["verdict"] == "NOVEL"


def test_without_classifier_or_artifact_novelty_is_unmeasured_and_not_blocking(planted):
    doc = _run(planted)
    assert doc["candidates"]
    assert {c["evidence"]["novelty"]["verdict"] for c in doc["candidates"]} == {"UNMEASURED"}


def test_the_artifact_alone_refuses_a_saturated_family(planted):
    ctx = _ctx(per_family={"exogenous_conditioner": {"saturation": "SATURATED"}}, present=True)
    doc = _run(planted, novelty=ctx)
    assert doc["candidates"] == []
    assert doc["novelty_verdicts"] == {"REPEAT_STYLE": doc["n_links"]}


def test_novelty_context_reads_the_artifact_dominant_styles(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "_style_classifier", lambda: None)
    p = tmp_path / "STYLE_NOVELTY.json"
    p.write_text(json.dumps({"dominant_style_counts": {"trend_20d": 4, "abs_window": 0}}), "utf-8")
    ctx = cl.novelty_context(p)
    assert ctx["artifact_present"] and ctx["classifier"] == "UNAVAILABLE"
    assert "trend_20d" in ctx["repeat_styles"] and "abs_window" not in ctx["repeat_styles"]
    assert set(cl.REPEAT_STYLES_BASE) <= set(ctx["repeat_styles"])
    absent = cl.novelty_context(tmp_path / "missing.json")
    assert absent["artifact_present"] is False


def test_a_cell_already_donated_is_never_donated_again(planted):
    first = _run(planted)
    ids = {ln["identity"] for ln in first["links"] if ln.get("identity")}
    again = _run(planted, prior=ids)
    assert again["candidates"] == []
    assert again["cell_status"].get("ALREADY_DONATED") == len(ids)


def test_prior_identities_read_the_seats_own_contract(tmp_path, planted):
    doc = _run(planted)
    (tmp_path / "discoveries_20260101_0000.json").write_text(
        json.dumps({"discoveries": doc["candidates"]}), "utf-8")
    assert cl._prior_identities(tmp_path) == {ln["identity"] for ln in doc["links"]
                                              if ln["cell_status"] == "EMITTED"}


def test_donation_goes_through_the_shared_door(planted, monkeypatch):
    from research import proposer_common as pc
    seen: dict = {}

    def fake(source, cands, tests_run):
        seen.update(source=source, n=len(cands), tests=tests_run)
        pc.LAST_DONATION.clear()
        pc.LAST_DONATION.update({"donated": len(cands), "source": source})
        return Path("x.json")
    monkeypatch.setattr(pc, "donate", fake)
    doc = _run(planted)
    out = cl.donate_global(doc)
    assert seen == {"source": cl.GLOBAL_SOURCE, "n": len(doc["candidates"]),
                    "tests": doc["n_tests"]}
    assert out["donated"] == len(doc["candidates"])


# --------------------------------------------------------------------------- absence and wiring

def test_an_empty_host_is_unmeasured_not_zero(tmp_path):
    streams, excluded, census = cl.load_streams(
        lake=tmp_path / "a", raw=tmp_path / "b", vault=tmp_path / "c", axes_dir=tmp_path / "d",
        text=tmp_path / "e", world=tmp_path / "f", targets=["EURUSD"])
    assert streams == []
    assert census["named_families"]["gdelt"]["status"] == "ABSENT_ON_HOST"
    doc = cl.build_global(streams=streams, excluded=excluded, census=census,
                          returns={"EURUSD": (_days(), np.zeros(N_DAYS))}, targets=["EURUSD"],
                          novelty=_ctx(), prior=set())
    assert doc["status"] == "UNMEASURED" and "UNMEASURED" in doc["why"]


def test_cli_no_donate_writes_both_artifacts_and_donates_nothing(tmp_path, monkeypatch, planted):
    monkeypatch.setattr(cl, "OUT", tmp_path / "CAUSAL_LAB.json")
    monkeypatch.setattr(cl, "GLOBAL_OUT", tmp_path / "causal_global_links.json")
    monkeypatch.setattr(cl, "build", lambda **kw: {"status": "UNMEASURED", "why": "fixture",
                                                   "n_unmeasured": 0, "rule": cl.RULE})
    gdoc = _run(planted)
    monkeypatch.setattr(cl, "build_global", lambda **kw: gdoc)
    called: list[int] = []
    monkeypatch.setattr(cl, "donate_global", lambda d: called.append(1) or {})
    assert cl.main(["--no-donate"]) == 0
    g = json.loads((tmp_path / "causal_global_links.json").read_text("utf-8"))
    core = json.loads((tmp_path / "CAUSAL_LAB.json").read_text("utf-8"))
    assert g["n_links"] >= 1 and g["donation"]["donated"] == 0 and not called
    assert core["global_streams"]["n_links"] == g["n_links"]
    for key in ("streams_read", "streams_excluded", "n_tests", "n_cells_emitted",
                "novelty_verdicts", "census"):
        assert key in g


# --------------------------------------------------------------------------- audit 2026-10-13

@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_asof_is_unit_blind_and_never_looks_ahead(unit):
    """A January value read on January days, a June value only from June -- in every unit the
    stream's index can carry under the installed pandas (as_unit on both sides)."""
    idx = pd.to_datetime(["2024-01-10T06:00", "2024-06-10T06:00"], utc=True).as_unit(unit)
    s = pd.Series([1.0, 6.0], index=idx)
    out = cl.asof_days(s, ["2024-01-09", "2024-01-11", "2024-01-20", "2024-06-11"])
    assert np.isnan(out[0])                                   # nothing knowable yet
    assert out[1] == 1.0 and out[2] == 1.0                    # January reads January, never June
    assert out[3] == 6.0
    late = (datetime(2024, 6, 10, tzinfo=UTC)
            + timedelta(days=cl.MAX_STALE_DAYS + 5)).date().isoformat()
    assert np.isnan(cl.asof_days(s, [late])[0])               # the staleness limit, in ns


def test_a_pass_with_no_test_is_unmeasured_and_a_cut_pass_is_partial(planted):
    spent = _run(planted, budget_s=-1.0)                      # budget gone before any test
    assert spent["n_tests"] == 0 and spent["status"] == "UNMEASURED"
    assert "0 tests ran" in spent["why"] and spent["n_streams_not_reached"] == 2
    short = {k: (d[:5], r[:5]) for k, (d, r) in planted["returns"].items()}
    tiny = _run(planted, returns=short, targets=list(short))
    assert tiny["n_tests"] == 0 and tiny["status"] == "UNMEASURED"
    import time as _t
    real = _t.monotonic
    calls = {"n": 0}

    def clock() -> float:                                     # the second stream is past budget
        calls["n"] += 1
        return real() + (0.0 if calls["n"] <= 2 else 10_000.0)
    import unittest.mock as um
    with um.patch.object(_t, "monotonic", clock):
        cut = _run(planted, budget_s=100.0)
    assert cut["status"] == "PARTIAL" and cut["n_tests"] > 0
    assert cut["n_streams_not_reached"] == 1 and "1 of 2" in cut["why"]
    assert any("PARTIAL" in ln for ln in cl.global_lines(cut))


def test_one_stream_that_raises_is_excluded_and_the_pass_goes_on(planted):
    bad = cl.Stream(name="lake:broken.v", store="lake",
                    series=pd.Series(["x"] * 50, index=pd.to_datetime(_days(50), utc=True)),
                    z_window=250)
    doc = _run(planted, streams=[*planted["streams"], bad])
    errs = [e for e in doc["streams_excluded"] if e.get("kind") == "error"]
    assert [e["stream"] for e in errs] == ["lake:broken.v"]
    assert doc["status"] == "PARTIAL" and doc["n_streams_errored"] == 1   # counted, not OK
    assert doc["n_links"] >= 1                                # the good streams still tested
    assert all(t["stream"] != "lake:broken.v" for t in doc["links"])


def test_the_core_artifact_is_written_before_the_global_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "OUT", tmp_path / "CAUSAL_LAB.json")
    monkeypatch.setattr(cl, "GLOBAL_OUT", tmp_path / "causal_global_links.json")
    monkeypatch.setattr(cl, "build", lambda **kw: {"status": "UNMEASURED", "why": "fixture",
                                                   "n_unmeasured": 0, "rule": cl.RULE})
    seen: dict = {}

    def global_pass(**kw):
        seen["core_on_disk"] = (tmp_path / "CAUSAL_LAB.json").exists()
        raise KeyboardInterrupt                               # the cycle cap kills the pass
    monkeypatch.setattr(cl, "build_global", global_pass)
    with pytest.raises(KeyboardInterrupt):
        cl.main(["--no-donate"])
    assert seen["core_on_disk"]
    assert json.loads((tmp_path / "CAUSAL_LAB.json").read_text("utf-8"))["why"] == "fixture"


def test_a_tail_cut_forum_reads_its_early_days_as_missing_not_zero(tmp_path, monkeypatch):
    forum = tmp_path / "f"
    forum.mkdir()
    lines, observed = [], []
    for i in range(40):
        day = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i)
        observed.append(day.date().isoformat())
        for k in range(3):
            lines.append(json.dumps({"source": "s", "ident": f"{i}-{k}",
                                     "first_seen_at": (day + timedelta(hours=5)).isoformat()}))
    (forum / "posts.jsonl").write_text("\n".join(lines), "utf-8")
    (forum / "observed_days.json").write_text(json.dumps(observed), "utf-8")
    monkeypatch.setattr(cl, "MAX_TEXT_LINES", 3 * 30 + 1)     # keeps day 10's last post only
    excluded: list[dict] = []
    s = cl.read_text_store(tmp_path, excluded)[0].series
    assert (s > 0).all()                                      # no false zero, no split day
    assert s.index[0] == pd.Timestamp("2024-01-12", tz="UTC")  # day 11, knowable next 00:00
    assert any("MISSING, not zero" in e["why"] for e in excluded)


def test_without_the_lane_policy_no_symbol_is_admitted(tmp_path, monkeypatch):
    (tmp_path / "universe.json").write_text(json.dumps({"EURUSD": {"asset_class": "fx"}}),
                                            "utf-8")
    (tmp_path / "EURUSD_H1.parquet").write_bytes(b"")
    monkeypatch.setitem(sys.modules, "research.universe_policy", None)
    picked, refused = cl.global_targets(tmp_path)
    assert picked == [] and "nothing is admitted" in refused[0]["why"]


def test_prior_identities_read_the_disk_guard_rollups(tmp_path, planted):
    import gzip
    doc = _run(planted)
    emitted = {ln["identity"] for ln in doc["links"] if ln["cell_status"] == "EMITTED"}
    assert emitted
    # the exact shape scripts/disk_guard.py `rollup` writes: one aged file's JSON per line
    with gzip.open(tmp_path / "rollup_20260101.jsonl.gz", "at", encoding="utf-8") as out:
        out.write(json.dumps({"discoveries": doc["candidates"]}, separators=(",", ":")) + "\n")
    assert cl._prior_identities(tmp_path) == emitted
