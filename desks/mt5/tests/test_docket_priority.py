"""H2 originality, H4 cross-source and H5 information gain: the leg, and the bounded tilt it feeds.

The tilt may change the ORDER of the judge's kept cells and nothing else -- same cells, same
count, no cell moved up by more than TILT_MAX of the docket -- and a missing, stale or disabled
lookup must leave the sealed order exactly as it was.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cross_source_synthesis as XS  # noqa: E402
import docket_priority as DP  # noqa: E402
import information_gain as IG  # noqa: E402
import judge_docket_order as O  # noqa: E402
import originality_share as OS  # noqa: E402


def _row(sym: str, fam: str, src: str, first: str, **params) -> dict:
    return {"symbol": sym, "family": fam, "source": src, "first_seen": first,
            "params": dict(params), "mechanism_note": ""}


def test_originality_classes_follow_the_declared_rule() -> None:
    rows = [_row("EURUSD", "fam_a", "miner:inventor", "2026-01-01", rr=1.5),
            _row("GBPUSD", "fam_a", "miner:inventor", "2026-01-03", rr=3.0),
            _row("EURUSD", "fam_a", "miner:other", "2026-01-02", rr=2.0),
            _row("EURUSD", "fam_b", "miner:video_anchor_exit", "2026-01-01", k=1),
            _row("USDJPY", "fam_b", "miner:other", "2026-01-05", k=2),
            {**_row("XAUUSD", "fam_c", "miner:other", "2026-01-01", z=1),
             "mechanism_note": "converted from a public video whose Sharpe ..."}]
    o = OS.Originality()
    for r in rows:
        o.observe(r)
    got = [o.classify(r)[0] for r in rows]
    assert got == [OS.ORIGINAL, OS.ORIGINAL, OS.VARIANT, OS.COPIED, OS.VARIANT, OS.COPIED]
    # a parameter VALUE change is the same hypmax fingerprint; a new parameter NAME is not
    assert OS.mechanism_fingerprint(rows[0]) == OS.mechanism_fingerprint(rows[2])
    assert OS.mechanism_fingerprint(rows[0]) != OS.mechanism_fingerprint(
        _row("EURUSD", "fam_a", "x", "", rr=1.5, ttl=3))
    assert OS.producer_of({"source": "ext_reddit_EURUSD_session_range_breakout"}) == "ext:reddit"


def test_independent_sources_collapse_one_host_and_one_generator() -> None:
    a = {"symbol": "EURUSD", "family": "f", "source": "miner:asia:rba",
         "source_url": "https://www.rba.gov.au/x", "contributing_sources": ["asia:rba"]}
    b = {"symbol": "EURUSD", "family": "f", "source": "miner:asia:rbnz",
         "source_url": "https://rba.gov.au/y", "contributing_sources": ["asia:rbnz"]}
    c = {"symbol": "EURUSD", "family": "f", "source": "ext_reddit_EURUSD_f"}
    d = {"symbol": "EURUSD", "family": "f", "source": "miner:reddit"}
    cs = XS.CrossSource()
    for i, r in enumerate((a, b, c, d)):
        cs.observe(r, f"k{i}")
    # host:rba.gov.au + asia (one seat namespace) + reddit (ext_ folded onto miner:reddit)
    assert cs.n_mechanism(a) == 3
    assert XS.roots_of(c) == XS.roots_of(d) == {"reddit"}


def test_information_gain_falls_as_a_family_is_ruled() -> None:
    assert IG.expected_gain(2.0, 8.0) > IG.expected_gain(20.0, 80.0) > IG.expected_gain(
        200.0, 800.0) > 0
    counts = {("busy", "H1"): [10, 4000], ("new", "H1"): [0, 3]}
    t = IG.score_table(counts, {("busy", "H1"): 10, ("new", "H1"): 10, ("never", "M5"): 2})
    rows = t["rows"]
    assert rows["busy|H1"]["score"] < rows["new|H1"]["score"] <= 1.0
    # UNMEASURED: no verdicts -> every family sits on the same prior -> one score for all
    flat = IG.score_table({}, {("a", "H1"): 1, ("b", "M5"): 9})["rows"]
    assert {r["score"] for r in flat.values()} == {1.0}
    assert IG.chart_of_cell("XAUUSD@M5.carry.p=ab") == "M5"


def _docket(tmp: Path) -> Path:
    rows = []
    for i in range(30):
        rows.append(_row(f"S{i % 5}", "copied_fam", "miner:video_anchor_exit",
                         f"2026-01-{1 + i % 9:02d}", n=i))
    for i in range(10):
        rows.append(_row(f"S{i % 5}", "own_fam", "miner:inventor", "2026-01-01", n=i))
    rows.append({**_row("S0", "copied_fam", "miner:forexfactory", "2026-01-02", n=0),
                 "timeframe": "M15"})
    p = tmp / "external_survivors.json"
    p.write_text(json.dumps(rows), "utf-8")
    return p


def test_the_leg_writes_three_reports_and_a_lookup_the_tilt_can_key(tmp_path: Path) -> None:
    gates = tmp_path / "gates.json"
    gates.write_text(json.dumps({"verdicts": [
        {"family": "copied_fam", "cell": "S0.copied_fam.p=1", "passed": False},
        {"family": "copied_fam", "cell": "S1.copied_fam.p=2", "passed": True},
        {"family": "own_fam", "cell": "S1.own_fam.p=2", "unmeasured": True}]}), "utf-8")
    out = DP.run(docket=_docket(tmp_path), certs=tmp_path / "none.json", gates=gates,
                 canon=tmp_path / "none2.json",
                 out_originality=tmp_path / "O.json", out_cross=tmp_path / "X.json",
                 out_info=tmp_path / "I.json", lookup=tmp_path / "L.json")
    assert out["rows"] == 41 and out["original_rows"] == 10
    o = json.loads((tmp_path / "O.json").read_text("utf-8"))
    assert o["docket"]["by_producer"]["inventor"]["share_original"] == 1.0
    assert o["certificates"]["status"] == "UNMEASURED"
    i = json.loads((tmp_path / "I.json").read_text("utf-8"))
    assert i["status"] == "MEASURED" and i["ruled_total"] == 2
    lk = json.loads((tmp_path / "L.json").read_text("utf-8"))
    assert lk["version"] == O.PRIORITY_VERSION and len(lk["original"]) == 10
    # the forexfactory row and the video rows on S0 are two independent roots
    assert lk["agreement"].get("S0|copied_fam") == 2
    spec = {"sym": "S0", "family": "own_fam", "params": {"n": 0}}
    assert DP.cell_key(spec["sym"], spec["family"], spec["params"]) in set(lk["original"])


def _keep(n: int) -> list[dict]:
    return [{"sym": f"S{i % 7}", "family": "own_fam" if i % 10 == 9 else "copied_fam",
             "params": {"n": i}, "tf": "H1"} for i in range(n)]


def _prio(keep: list[dict], *, info: dict | None = None) -> dict:
    orig = [DP.cell_key(sp["sym"], sp["family"], sp["params"]) for sp in keep
            if sp["family"] == "own_fam"]
    return {"version": 1, "at_epoch": time.time(), "original": orig,
            "agreement": {"S3|copied_fam": 3}, "info_gain": info or {}}


def test_tilt_keeps_every_cell_and_moves_none_further_than_its_bound(
        monkeypatch: pytest.MonkeyPatch) -> None:
    keep = _keep(400)
    monkeypatch.setattr(O, "ORIGINAL_QUOTA", 0.0)
    new, c = O.priority_tilt(keep, _prio(keep, info={"copied_fam|H1": 0.2, "own_fam|H1": 1.0}))
    assert c["status"] == "APPLIED"
    assert sorted(map(id, new)) == sorted(map(id, keep)) and len(new) == len(keep)
    assert c["max_up"] <= O.TILT_MAX * (len(keep) - 1) + 1
    assert c["head_original_share"] >= c["head_original_share_before"]


def test_the_original_quota_raises_the_head_share(monkeypatch: pytest.MonkeyPatch) -> None:
    keep = _keep(400)
    monkeypatch.setattr(O, "TILT_MAX", 0.0)
    monkeypatch.setattr(O, "ORIGINAL_QUOTA", 0.2)
    new, c = O.priority_tilt(keep, _prio(keep))
    head = new[:100]
    # 10% of the sealed order is ORIGINAL; the quota holds 20% of the head (within its reach)
    assert sum(1 for sp in keep[:100] if sp["family"] == "own_fam") == 10
    assert sum(1 for sp in head if sp["family"] == "own_fam") >= 20
    assert c["quota_pulls"] > 0 and sorted(map(id, new)) == sorted(map(id, keep))


def test_missing_stale_or_disabled_lookup_leaves_the_sealed_order(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    keep = _keep(50)
    G = SimpleNamespace(BASE=tmp_path)
    prio = O.load_priority(G)
    assert prio and prio["_unmeasured"]
    assert O.priority_tilt(keep, prio)[0] == keep
    path = tmp_path.joinpath(*O.PRIORITY_LOOKUP)
    path.parent.mkdir(parents=True)
    stale = {**_prio(keep), "at_epoch": time.time() - O.PRIORITY_MAX_AGE_S - 60}
    path.write_text(json.dumps(stale), "utf-8")
    assert "old" in O.load_priority(G)["_unmeasured"]
    path.write_text(json.dumps(_prio(keep)), "utf-8")
    assert O.load_priority(G).get("_unmeasured") is None
    monkeypatch.setenv("JUDGE_DOCKET_TILT", "0")
    new, c = O.priority_tilt(keep, O.load_priority(G))
    assert new == keep and c["status"] == "DISABLED"
    monkeypatch.delenv("JUDGE_DOCKET_TILT")
    tmp_path.joinpath(*O.TILT_DISABLED_FILE).write_text("", "utf-8")
    assert O.priority_tilt(keep, O.load_priority(G))[1]["status"] == "DISABLED"


def test_the_leg_is_on_the_hourly_core_clock_with_a_layer() -> None:
    import hourly_cycle as H

    from libs.research.layers import LEG_LAYER
    assert "docket_priority" in H.CORE_LEGS
    assert LEG_LAYER.get("docket_priority") == "meta"
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("docket_priority"' in src and '"research/docket_priority.py"' in src
