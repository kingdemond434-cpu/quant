"""KNOWN-BY-DATE / PIT DISCIPLINE, folded into the data OS.

    python -m pytest desks/mt5/tests/test_known_by_date.py -q

WHAT MUST NOT REGRESS:

  1. every registered dataset declares a publication lag (data_os.PUBLICATION_LAGS or its own
     registry pit block); a cadence default is not a declaration
  2. an undeclared source cannot be given a knowledge time or put in the store
  3. `store_from_series` + `latest_known` admit a value only after valid time + lag
  4. `run_macro_conditioned_sweep` reads its macro state through the store: a signal on the
     morning of a favourable day is refused (the day's close was not yet printed), the next
     day's is admitted, and the old same-date join's look-ahead is counted
  5. the lint names a reader that joins by date without a lag, passes one routed through the
     store, and fails only on a NEW offender (the floor only shrinks)
  6. `check_pit` fails on a registered dataset with no declared lag
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_known_by_date as kbd  # noqa: E402
import run_macro_conditioned_sweep as mcs  # noqa: E402

from libs.tiers import data_os  # noqa: E402
from scripts import check_pit as P  # noqa: E402


def _registry() -> dict[str, Any]:
    doc = json.loads((DESK / "data" / "data_registry.json").read_text("utf-8"))
    return dict(doc["datasets"])


# ----------------------------------------------------------------------------- 1-3 the registry
def test_every_registered_dataset_declares_a_lag() -> None:
    census = data_os.lag_census(_registry())
    assert census["undeclared"] == [], census["undeclared"]
    assert census["n"] >= 15


def test_registry_pit_block_wins_and_cadence_is_not_a_declaration() -> None:
    lag = data_os.declared_lag("anything", {"pit": {"publication_lag_days": 2}})
    assert lag is not None and lag["lag_s"] == 2 * 86400
    assert data_os.declared_lag("no_such_source", {"cadence": "monthly"}) is None
    assert data_os.lag_census({"new_ds": {"cadence": "daily"}})["undeclared"] == ["new_ds"]


def test_undeclared_source_has_no_knowledge_time() -> None:
    with pytest.raises(KeyError):
        data_os.knowledge_time("no_such_source", datetime(2026, 1, 1, tzinfo=UTC))
    with pytest.raises(KeyError):
        data_os.store_from_series(pd.Series([1.0]), source="no_such_source", entity="e",
                                  attribute="a")
    assert data_os.knowledge_time("cot_fx", datetime(2026, 1, 6, tzinfo=UTC)) == \
        datetime(2026, 1, 10, tzinfo=UTC)


def test_store_admits_only_after_the_lag() -> None:
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-05", "2026-01-06"]))
    store = data_os.store_from_series(s, source="fred_macro", entity="DGS10", attribute="v")
    lag = timedelta(seconds=data_os.PUBLICATION_LAGS["fred_macro"]["lag_s"])
    t0 = datetime(2026, 1, 5, tzinfo=UTC)
    got = store.latest_known("DGS10", "v", [t0 + timedelta(hours=12), t0 + lag,
                                            t0 + timedelta(days=1) + lag])
    assert got[0] is None
    assert got[1] is not None and got[1].value == 1.0
    assert got[2] is not None and got[2].value == 2.0


# ------------------------------------------------------------------------------ 4 the reader
def test_macro_sweep_reads_point_in_time() -> None:
    days = pd.to_datetime(["2026-03-02", "2026-03-03", "2026-03-04"])
    fav = pd.Series([False, True, False], index=days)
    sigs = [SimpleNamespace(time=pd.Timestamp("2026-03-03 03:00", tz="UTC")),   # same day
            SimpleNamespace(time=pd.Timestamp("2026-03-04 04:00", tz="UTC")),   # after the lag
            SimpleNamespace(time=pd.Timestamp("2026-03-05 05:00", tz="UTC"))]   # next state
    cond, pit = mcs.pit_conditioned(sigs, fav, "DXY")
    assert [s.time.day for s in cond] == [4]
    assert pit["date_join_admitted"] == 1 and pit["lookahead_refused"] == 1
    assert pit["pit_admitted"] == 1
    assert mcs.MACRO_SOURCE in data_os.PUBLICATION_LAGS


def test_both_macro_sweeps_read_one_declaration() -> None:
    import run_edges_macro_fusion_sweep as emf
    assert pd.Timedelta(
        seconds=data_os.PUBLICATION_LAGS[mcs.MACRO_SOURCE]["lag_s"]) == emf.MACRO_KNOWABLE_AFTER


def test_macro_sweep_is_an_hourly_leg() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("macro_conditioned_sweep", "research/run_macro_conditioned_sweep.py")' \
        in src
    import hourly_cycle as hc
    assert hc.department_of("macro_conditioned_sweep") == "macro"


# ------------------------------------------------------------------------------- 5 the lint
def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    base = tmp_path / "desks" / "mt5" / "research"
    base.mkdir(parents=True)
    for name, body in files.items():
        (base / name).write_text(body, "utf-8")
    return tmp_path


OFFENDER = """
def f(hist, sigs):
    fav = hist  # macro_regime.load_history
    dates = set(fav.index.date)
    return [s for s in sigs if s.time.date() in dates]
"""
ROUTED = """
from libs.tiers import data_os
def f(fav, sigs):
    store = data_os.store_from_series(fav, source="cross_asset_anchors", entity="x",
                                      attribute="a")  # macro_regime.load_history
    known = store.latest_known("x", "a", [s.time for s in sigs])
    return fav.reindex([s.time for s in sigs]), known
"""


def test_lint_names_the_date_join_and_passes_the_store(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"bad.py": OFFENDER, "good.py": ROUTED,
                            "fetch_x.py": OFFENDER, "unrelated.py": "x = [1].index(1)\n"})
    doc = kbd.scan(root)
    assert set(doc["offenders"]) == {"desks/mt5/research/bad.py"}
    assert "cross_asset_anchors" in doc["offenders"]["desks/mt5/research/bad.py"]["sources"]
    assert "desks/mt5/research/good.py" in doc["routed"]


def test_lint_fails_only_on_arrival_and_floor_only_shrinks(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path, {"bad.py": OFFENDER, "old.py": OFFENDER})
    floor = tmp_path / "floor.json"
    monkeypatch.setattr(kbd, "FLOOR", floor)
    monkeypatch.setattr(kbd, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(kbd, "LAG_OUT", tmp_path / "lag.json")
    monkeypatch.setattr(kbd, "certificate_fence",
                        lambda root=None: {"providers": {}, "failures": [], "verdict": "OK"})
    # the producer census has its own ratchet (test_bitemporal_producers.py); held OK here so
    # this test exercises the reader floor alone, and its floor never touches the repo's
    monkeypatch.setattr(kbd, "PRODUCER_FLOOR", tmp_path / "producer_floor.json")
    kbd.write_producer_floor(set())
    monkeypatch.setattr(kbd, "producer_census", lambda root=None, floor=None: {
        "producers": {}, "counts": dict.fromkeys(kbd.PRODUCER_CLASSES, 0), "n": 0,
        "pit_routed": 0, "not_pit_routed": 0, "not_pit": [], "floor": [], "arrived": [],
        "healed": [], "verdict": "OK"})
    monkeypatch.setattr(kbd, "ROOT", root)
    real_scan = kbd.scan
    monkeypatch.setattr(kbd, "scan", lambda: real_scan(root))
    assert kbd.main([]) == 1                               # no floor: not a ratchet
    kbd.write_floor({"desks/mt5/research/old.py", "desks/mt5/research/healed.py"})
    assert kbd.main([]) == 1                               # bad.py ARRIVED
    assert "NEW OFFENDER desks/mt5/research/bad.py" in capsys.readouterr().out
    (root / "desks/mt5/research/bad.py").write_text(ROUTED, "utf-8")
    assert kbd.main(["--update"]) == 0
    assert kbd.read_floor(floor) == {"desks/mt5/research/old.py"}


def test_committed_floor_holds_and_the_repo_has_no_new_offender() -> None:
    floor = kbd.read_floor()
    assert floor is not None
    now = set(kbd.scan()["offenders"])
    assert now <= floor, sorted(now - floor)
    assert "desks/mt5/research/run_macro_conditioned_sweep.py" not in now


def test_lint_is_a_law_fence() -> None:
    src = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    law = src[src.index("_LAW_FENCES: tuple"):src.index("_STATE_FENCES: tuple")]
    assert '("check_known_by_date.py", ())' in law


# ------------------------------------------------------------------------------ 6 check_pit
def test_check_pit_fails_on_an_undeclared_dataset(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps({"datasets": {"fred_macro": {},
                                            "brand_new": {"cadence": "daily"}}}), "utf-8")
    monkeypatch.setattr(P, "REGISTRIES", (reg,))
    c = P.lag_census()
    assert c["status"] == "MEASURED" and c["undeclared"] == ["brand_new"]
    # main() fails on it even with a healthy stamped fraction
    from libs.data.pit import stamp
    intel = tmp_path / "intel" / "src"
    intel.mkdir(parents=True)
    rows = [stamp({"title": f"r{i}", "found_at": "2026-09-01T00:00:00+00:00"}, "src",
                  source_version="t") for i in range(4)]
    (intel / "discoveries_20260901_0000.json").write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(P, "INTEL", intel.parent)
    monkeypatch.setattr(P, "OUT", tmp_path / "PIT_CENSUS.json")
    monkeypatch.setattr(P, "CERTIFICATES", tmp_path / "no_certs")
    base = tmp_path / "hw.json"
    base.write_text(json.dumps({"stamped_frac": 1.0, "sealed_at": "x"}), "utf-8")
    assert P.main(["--baseline", str(base)]) == 1
    reg.write_text(json.dumps({"datasets": {"fred_macro": {}}}), "utf-8")
    assert P.main(["--baseline", str(base)]) == 0
