"""RANK 4 data registry: it must not be able to repeat EITHER half of GAP_REGISTER row #77.

Row #77 was a map that was wrong in both directions at once:
  * OVERSTATED -- 33,867 rows read as a large dataset; it is 17 days. Tests here assert rows and
    span can never be conflated, on data built to have exactly that shape.
  * UNDERSTATED -- the desk's best panel (267 per-symbol directories) was invisible to a flat scan.
    Tests here build a partitioned tree and assert it is discovered with EXACT breadth.
Plus the third failure the row notes separately: 26 years of CFTC COT that nothing read. Long
history with no consumer must be surfaced, not silently carried.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from libs.research.data_registry import (
    REPL_PERISHABLE,
    REPL_PROPRIETARY,
    REPL_REFETCHABLE,
    AssetSpan,
    DataAsset,
    build,
    classify_replication,
    measure_span,
    score,
)


def _parquet(p: Path, days: int, rows: int, symbols: int = 1) -> None:
    """A file with MANY rows over FEW days -- row #77's overstatement shape, on purpose."""
    p.parent.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    per = max(1, rows // (days * symbols))
    recs = [{"date": d.date().isoformat(), "symbol": f"S{s}", "v": 1.0}
            for d in dates for s in range(symbols) for _ in range(per)]
    pd.DataFrame(recs).to_parquet(p)


class TestRowsAreNeverMistakenForSpan:
    """THE row-#77 overstatement. 33,867 rows / 17 days must read as 17 days."""

    def test_a_dense_short_file_reports_its_real_span(self, tmp_path: Path) -> None:
        p = tmp_path / "liquidations.parquet"
        _parquet(p, days=17, rows=33_867, symbols=15)
        span, rows, breadth = measure_span(p)
        assert span.days == 17, "span must come from dates, never from row count"
        assert rows is not None and rows > 10_000, "rows are still reported -- just separately"
        assert breadth == 15

    def test_span_and_rows_are_different_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "x.parquet"
        _parquet(p, days=3, rows=9_000)
        span, rows, _ = measure_span(p)
        assert span.days == 3 and rows != span.days

    def test_a_long_thin_file_outranks_a_short_dense_one(self, tmp_path: Path) -> None:
        """The ranking row #77 got backwards: 3 years of daily beats 17 days of everything."""
        thin, dense = tmp_path / "thin.parquet", tmp_path / "dense.parquet"
        _parquet(thin, days=1095, rows=1095)
        _parquet(dense, days=17, rows=40_000, symbols=15)
        a_thin = DataAsset(id="thin", path="thin", span=measure_span(thin)[0],
                           breadth=1, rows=1095)
        a_dense = DataAsset(id="dense", path="dense", span=measure_span(dense)[0],
                            breadth=15, rows=40_000)
        assert score(a_thin)[1] > score(a_dense)[1]


class TestAbsentIsNeverZero:
    """An honest hole is navigable; a confident wrong number is not."""

    def test_a_missing_file_is_absent_not_a_zero_span(self, tmp_path: Path) -> None:
        span, rows, breadth = measure_span(tmp_path / "nope.parquet")
        assert span.status == "absent"
        assert span.days is None and span.first is None
        assert rows is None and breadth is None

    def test_a_dateless_file_says_so_rather_than_spanning_nothing(self, tmp_path: Path) -> None:
        p = tmp_path / "nodate.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"a": 1}, {"a": 2}]).to_parquet(p)
        span, rows, _ = measure_span(p)
        assert span.status == "no-date-column" and span.days is None
        assert rows == 2, "rows are still countable without a date column"

    def test_a_corrupt_file_is_unreadable_not_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.parquet"
        p.write_bytes(b"not a parquet file at all")
        assert measure_span(p)[0].status == "unreadable"

    def test_an_unmeasured_span_is_never_marked_measured(self) -> None:
        for st in ("absent", "unreadable", "no-date-column", "unsupported-format"):
            assert not AssetSpan(status=st).measured


class TestPartitionedTreesAreDiscovered:
    """THE row-#77 understatement: 267 per-symbol dirs were invisible to a flat scan."""

    def _lake(self, root: Path, symbols: int, days: int) -> None:
        for s in range(symbols):
            _parquet(root / f"data/lake/bronze/crypto/SYM{s}/D1/part.parquet", days=days, rows=days)

    def test_a_per_symbol_tree_is_found_at_all(self, tmp_path: Path) -> None:
        self._lake(tmp_path, symbols=12, days=30)
        ids = [a.id for a in build(tmp_path)]
        assert "lake_crypto" in ids, "the flat inventory's blind spot must be covered"

    def test_breadth_is_the_exact_partition_count_not_a_sample(self, tmp_path: Path) -> None:
        # spans are sampled for affordability; breadth must NOT be, or 267 symbols reads as 3
        self._lake(tmp_path, symbols=40, days=10)
        a = next(x for x in build(tmp_path) if x.id == "lake_crypto")
        assert a.breadth == 40

    def test_it_is_marked_partitioned_and_says_the_span_was_sampled(self, tmp_path: Path) -> None:
        self._lake(tmp_path, symbols=8, days=10)
        a = next(x for x in build(tmp_path) if x.id == "lake_crypto")
        assert a.kind == "partitioned"
        assert any("breadth exact" in n for n in a.notes), "sampling must be disclosed"

    def test_deep_measures_every_member_and_reports_rows(self, tmp_path: Path) -> None:
        self._lake(tmp_path, symbols=6, days=10)
        shallow = next(x for x in build(tmp_path) if x.id == "lake_crypto")
        deep = next(x for x in build(tmp_path, deep=True) if x.id == "lake_crypto")
        assert shallow.rows is None, "a sampled row count would be a fabricated total"
        assert deep.rows == 60

    def test_the_measured_span_covers_the_real_range(self, tmp_path: Path) -> None:
        self._lake(tmp_path, symbols=5, days=100)
        a = next(x for x in build(tmp_path) if x.id == "lake_crypto")
        assert a.span.measured and a.span.days == 100


class TestMoatIsNotResearchValue:
    """Conflating them mis-ranks in BOTH directions; row #77's cot_zcache is the proof case."""

    def test_a_26_year_public_panel_has_zero_moat(self) -> None:
        # CFTC COT: anyone can re-download all of it. Scoring it as a moat would be a lie.
        cot = DataAsset(id="cot_zcache", path="p", span=AssetSpan("2000-01-01", "2026-01-01",
                                                                 9497, "measured"), breadth=11)
        moat, value = score(cot)
        assert moat == 0.0
        assert value > 50.0, "and yet it is among the most valuable rows the desk owns"

    def test_our_own_recorded_snapshots_score_high_moat(self) -> None:
        moat, _ = score(DataAsset(id="moat", path="p", replication=REPL_PROPRIETARY,
                                  span=AssetSpan("2026-01-01", "2026-07-01", 180, "measured")))
        assert moat > 70.0

    def test_a_short_perishable_archive_earns_only_a_little_moat(self) -> None:
        # a 28-day funding archive is a real but small head start -- it must not read as a moat
        moat, _ = score(DataAsset(id="hyperliquid_funding", path="p",
                                  replication=REPL_PERISHABLE,
                                  span=AssetSpan("2026-07-01", "2026-07-28", 28, "measured")))
        assert 0.0 < moat < 10.0

    def test_a_long_perishable_archive_earns_real_moat(self) -> None:
        moat, _ = score(DataAsset(id="oi_ls_history", path="p", replication=REPL_PERISHABLE,
                                  span=AssetSpan("2023-01-01", "2026-01-01", 1095, "measured")))
        assert moat > 40.0, "being early IS the moat for a recent-only feed"

    def test_classification_reads_the_asset_kind(self) -> None:
        assert classify_replication("moat") == REPL_PROPRIETARY
        assert classify_replication("hyperliquid_funding") == REPL_PERISHABLE
        assert classify_replication("kimchi_premium") == REPL_PERISHABLE
        assert classify_replication("cot_zcache") == REPL_REFETCHABLE

    def test_length_alone_never_manufactures_a_moat(self) -> None:
        # 30 years of a refetchable public series is still zero moat
        moat, _ = score(DataAsset(id="fred_series", path="p", replication=REPL_REFETCHABLE,
                                  span=AssetSpan("1996-01-01", "2026-01-01", 10957, "measured")))
        assert moat == 0.0


class TestUnreadLongHistoryIsSurfaced:
    """Row #77's third defect: 26 years of COT on disk that nothing queried."""

    def test_long_history_with_no_consumer_gets_the_paralysis_bonus(self) -> None:
        span = AssetSpan("2000-01-01", "2026-01-01", 9497, "measured")
        unread = DataAsset(id="a", path="p", span=span, breadth=11, consumers=[])
        read = DataAsset(id="a", path="p", span=span, breadth=11, consumers=["scripts/x.py"])
        assert score(unread)[1] > score(read)[1], "idle paid-for history must rank UP for attention"

    def test_short_unread_data_gets_no_bonus(self) -> None:
        span = AssetSpan("2026-01-01", "2026-01-10", 10, "measured")
        a = DataAsset(id="a", path="p", span=span, consumers=[])
        b = DataAsset(id="a", path="p", span=span, consumers=["scripts/x.py"])
        assert score(a)[1] == score(b)[1], "10 days nobody reads is not a paralysis finding"


class TestTheBuilderIsSafeToRunAnywhere:
    def test_an_empty_repo_yields_an_empty_registry_not_a_crash(self, tmp_path: Path) -> None:
        assert build(tmp_path) == []

    def test_results_are_deterministic(self, tmp_path: Path) -> None:
        _parquet(tmp_path / "data/lake/bronze/x/S1/D1/p.parquet", days=5, rows=5)
        assert [a.id for a in build(tmp_path)] == [a.id for a in build(tmp_path)]

    def test_every_asset_serialises_to_json(self, tmp_path: Path) -> None:
        _parquet(tmp_path / "data/lake/bronze/x/S1/D1/p.parquet", days=5, rows=5)
        for a in build(tmp_path):
            json.dumps(a.to_json())          # must not raise -- the artifact is written as JSON


class TestTheRealRepo:
    """The registry must be honest about THIS box, which has no data lake."""

    def test_it_runs_on_the_real_repo(self) -> None:
        assets = build()
        assert assets, "the desk's collectors declare data paths -- discovery must find them"

    def test_absent_assets_are_flagged_not_scored_as_empty(self) -> None:
        absent = [a for a in build() if a.span.status == "absent"]
        if not absent:
            pytest.skip("this box has every declared asset present")
        for a in absent:
            assert a.span.days is None, f"{a.id}: absent must never read as a zero-day span"
            assert any("NOT PRESENT" in n for n in a.notes)
