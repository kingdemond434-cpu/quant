"""The sealed judge's speed paths compute exactly what the lines they replaced computed.

    python -m pytest desks/mt5/tests/test_gauntlet_speed_equivalence.py -q

`judging/gauntlet_speed/external_gauntlet_speed.patch` (2026-10-14) adds to
`desks/mt5/scripts/external_gauntlet.py` a handful of helpers that replace slow but authoritative
calls with exact equivalents. Every test here SKIPS until that sealed patch is applied, then pins
each helper against the call it stands in for:

  1. `_cpcv_test_sets(n)` is element-for-element `CPCV(6, 2).split(n)`'s test arrays;
  2. `_split_at(s, cut)` is the two boolean masks, on every index shape (and falls back on the
     shapes a binary search cannot serve);
  3. `_UnionDates.of(series)` hands `gate_policy.lockbox_cut` the same calendar key;
  4. the content memo returns fresh, equal values and never shares a mutable dict;
  5. `_program_reads` uses a shard's reads only at the same bar, length and tail.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(scope="module")
def eg():
    import external_gauntlet
    if not hasattr(external_gauntlet, "_cpcv_test_sets"):
        pytest.skip("external_gauntlet_speed.patch is not applied to the sealed judge")
    return external_gauntlet


def test_cpcv_test_sets_are_the_splitters_own(eg) -> None:
    from libs.validation.cpcv import CPCV
    for n in [*range(6, 400), 997, 1500, 2203, 4096]:
        ref = [np.asarray(sp.test) for sp in CPCV(n_groups=6, n_test_groups=2).split(n)]
        got = eg._cpcv_test_sets(n)
        assert len(got) == len(ref)
        for a, b in zip(got, ref, strict=True):
            assert a.dtype == b.dtype and np.array_equal(a, b)


def test_cpcv_test_sets_refuse_a_short_series_like_the_splitter(eg) -> None:
    from libs.validation.errors import ValidationError
    with pytest.raises(ValidationError):
        eg._cpcv_test_sets(5)


def _series(idx) -> pd.Series:
    return pd.Series(np.arange(len(idx), dtype=float), index=idx)


@pytest.mark.parametrize("unit", ["ns", "us", "s"])
def test_split_at_is_the_two_masks(eg, unit) -> None:
    idx = pd.bdate_range("2020-01-01", periods=300).as_unit(unit)
    dup = idx.append(idx[100:110]).sort_values()          # sorted, with repeats
    for ix in (idx, dup):
        s = _series(ix)
        for cut in (ix[0], ix[57], ix[105], ix[-1], ix[-1] + pd.Timedelta(days=3),
                    ix[0] - pd.Timedelta(days=1), pd.Timestamp("2020-03-04 13:00")):
            dev, held = eg._split_at(s, cut)
            assert dev.equals(s[s.index < cut]) and held.equals(s[s.index >= cut])


def test_split_at_falls_back_on_shapes_a_search_cannot_serve(eg) -> None:
    py = _series([date(2020, 1, 1) + timedelta(days=i) for i in range(50)])
    cut_d = date(2020, 1, 20)
    dev, held = eg._split_at(py, cut_d)
    assert dev.equals(py[py.index < cut_d]) and held.equals(py[py.index >= cut_d])
    unsorted = _series(pd.DatetimeIndex(["2020-01-03", "2020-01-01", "2020-01-02"]))
    cut = pd.Timestamp("2020-01-02")
    dev, held = eg._split_at(unsorted, cut)
    assert dev.equals(unsorted[unsorted.index < cut])
    aware = _series(pd.date_range("2020-01-01", periods=20, tz="UTC"))
    cut = pd.Timestamp("2020-01-05", tz="UTC")
    dev, held = eg._split_at(aware, cut)
    assert held.equals(aware[aware.index >= cut])


def test_union_dates_gives_lockbox_cut_the_same_key(eg) -> None:
    from research.gate_policy import lockbox_cut
    rng = np.random.default_rng(3)
    series = []
    for _ in range(40):
        n = int(rng.integers(30, 900))
        end = pd.Timestamp("2026-10-09") - pd.Timedelta(days=int(rng.integers(0, 200)))
        idx = pd.to_datetime(pd.bdate_range(end=end, periods=n).asi8)   # ns, as the cache loads
        series.append(_series(idx))
    series.insert(3, None)
    union = eg._UnionDates.of(series)
    assert union is not None
    for frac in (0.2, 0.25, 0.3):
        assert lockbox_cut([union], frac=frac) == lockbox_cut(series, frac=frac)
    mixed = [series[0], _series(series[1].index.as_unit("us"))]
    assert eg._UnionDates.of(mixed) is None                  # two units: the series themselves
    assert eg._UnionDates.of([None]) is None


def test_memo_hands_out_fresh_equal_values(eg) -> None:
    arr = np.random.default_rng(1).normal(0.05, 1.0, 500)
    held = pd.Series(np.random.default_rng(2).normal(0.0, 1.0, 120))
    a = eg._lockbox_read(held, arr, 0.05)
    b = eg._lockbox_read(held, arr.copy(), 0.05)
    assert a == b and a is not b
    a["cut"] = "mutated"
    assert "cut" not in eg._lockbox_read(held, arr, 0.05)
    assert eg._dsr_read(arr, 0.95) == eg._dsr_read(arr.copy(), 0.95)
    assert eg._local_pure(arr) == eg._local_pure(arr.copy())
    flipped = arr.copy()
    flipped[0] = np.nextafter(flipped[0], np.inf)             # one ulp is another input
    assert eg._fp(flipped) != eg._fp(arr)


def test_program_reads_take_a_shards_reads_only_when_they_match(eg) -> None:
    arr = np.random.default_rng(4).normal(0.05, 1.0, 400)
    held = pd.Series(np.random.default_rng(5).normal(0.0, 1.0, 100))
    dsr, lock = eg._program_reads(arr, held, None, threshold=0.95)
    sentinel = {"dsr_bar": 0.95, "n": len(arr), "n_held": len(held),
                "dsr": (True, 9.0, 0.0), "lockbox": {"passed": True, "marker": 1}}
    assert eg._program_reads(arr, held, sentinel, threshold=0.95)[1]["marker"] == 1
    for bad in ({**sentinel, "dsr_bar": 0.96}, {**sentinel, "n": 399},
                {**sentinel, "n_held": 99}, {**sentinel, "dsr": [True, 9.0, 0.0]}):
        assert eg._program_reads(arr, held, bad, threshold=0.95) == (dsr, lock)


# ---------------------------------------------------------------- audit on b879ac50 (2026-10-20)
@pytest.mark.parametrize("idx_unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("cut", ["2020-01-09 10:00:00.5", "2020-01-09 10:00:00.000001",
                                 "2020-01-09 10:00:00.000000001", "2020-01-09"])
def test_split_at_is_the_masks_when_the_cut_is_finer_than_the_index(eg, idx_unit, cut) -> None:
    """pandas 3 `searchsorted` refuses a cut it cannot convert losslessly; the masks do not."""
    idx = pd.date_range("2020-01-01 10:00", periods=30, freq="D").as_unit(idx_unit)
    c = pd.Timestamp(cut)
    for s in (_series(idx), _series(idx[:0])):
        dev, held = eg._split_at(s, c)
        assert dev.equals(s[s.index < c]) and held.equals(s[s.index >= c])


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_daily_index_is_the_original_expression_dtype_included(eg, unit) -> None:
    idx = pd.date_range("2020-01-01 13:00", periods=40, freq="D").as_unit(unit)
    ref = pd.DatetimeIndex(pd.to_datetime(list(idx))).normalize()
    got = eg._daily_index(_series(idx))
    assert got.dtype == ref.dtype and got.equals(ref)


def test_the_content_memo_lives_for_one_judging_call(eg) -> None:
    import inspect
    for fn in (eg.run_gauntlet, eg._shard_rule):
        assert "_PURE_MEMO.clear()" in inspect.getsource(fn)


def test_the_digest_facts_are_the_full_reads_facts(eg, tmp_path) -> None:
    rows = [{"sym": "EURUSD", "family": f"f{i % 3}", "params": {"i": i % 4},
             "stages": ({} if i % 5 == 0 else {"cpcv": {"passed": i % 2 == 0}}),
             **({"unmeasured": True} if i % 7 == 0 else {}),
             **({"cell_id": f"c{i}"} if i % 4 == 0 else {})} for i in range(60)]
    rows += ["junk", 5, {"family": ""}]
    report = tmp_path / "reports" / "universal_gates_external.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"verdicts": rows}), encoding="utf-8")
    eg._write_report_digest(report, {"verdicts": rows})
    facts = eg._report_facts(tmp_path)
    assert facts is not None
    rt = json.loads(report.read_text("utf-8"))["verdicts"]
    ruled, power_def = eg._yield_counts(rt)
    assert facts["unjudged"] == sorted(eg._unjudged_cells(rt))
    assert list(facts["ruled"].items()) == list(ruled.items())
    assert list(facts["power_def"].items()) == list(power_def.items())
