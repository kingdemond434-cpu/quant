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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from scripts.build_data_registry import main as build_registry

from libs.research.capability_ratchet import read_capability
from libs.research.data_registry import (
    _DATE_COLS,
    NOT_READABLE_HERE,
    REPL_PERISHABLE,
    REPL_PROPRIETARY,
    REPL_REFETCHABLE,
    AssetSpan,
    DataAsset,
    _days_from_epoch,
    _iso_day,
    build,
    classify_replication,
    measure_gaps,
    measure_span,
    score,
)

REPO = Path(__file__).resolve().parents[2]


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


# ------------------------------------------------------------------------------------------
# 2026-08-05: SPANS CARRY THEIR HOLES, AND ABSENCE CARRIES AN ADDRESS.
#
# Row #77's overstatement had a second home the original fix did not close: `first..last` is
# ELAPSED time, and an organ choosing what to test deeply reads it as EVIDENCE. `t = SR*sqrt(years)`
# is the only lever gate_power_audit.md found moves power, and 119 of 228 recorded negatives are
# already UNDERPOWERED, so a span quoted 60x too long (data/exchange_announcements.jsonl reads 6.45
# elapsed years over 38 observed days) is not a cosmetic error -- it is a test that was never
# powered being planned as though it were.
# ------------------------------------------------------------------------------------------


def _jsonl(p: Path, days: list[str], per_day: int = 1) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps({"ts": d, "v": i}) + "\n"
                         for d in days for i in range(per_day)), "utf-8")


def _repo(root: Path, *, asset: str = "data/feed.jsonl", days: list[str] | None = None) -> None:
    """A minimal checkout: one collector that WRITES an asset, one organ that READS it."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/collector.py").write_text(
        f'import json\n\ndef go(rec):\n    open("{asset}", "a").write(json.dumps(rec))\n', "utf-8")
    (root / "scripts/organ.py").write_text(f'PATH = "{asset}"\n', "utf-8")
    if days is not None:
        _jsonl(root / asset, days)


class TestAnInternalGapIsSubtractedFromEvidence:
    """A 5-year span with a 2-year hole is 3 years of evidence and must never be quoted as 5."""

    def test_a_hole_is_reported_with_its_size_and_its_dates(self, tmp_path: Path) -> None:
        p = tmp_path / "gappy.jsonl"
        _jsonl(p, ["2026-01-01", "2026-01-02", "2026-02-01", "2026-02-02"])
        span = measure_span(p)[0]
        assert span.measured and span.days == 33, "elapsed time is still reported"
        assert span.gapped and span.gap_days == 29
        assert span.n_gaps == 1
        assert span.largest_gap_days == 29
        assert span.largest_gap_from == "2026-01-03" and span.largest_gap_to == "2026-01-31"

    def test_evidence_years_is_observed_time_not_elapsed_time(self, tmp_path: Path) -> None:
        p = tmp_path / "gappy.jsonl"
        # 2 years elapsed, ~10 days of it observed: the exact shape that oversizes a t-stat
        _jsonl(p, ["2024-01-01", "2024-01-02", "2024-01-03", "2025-12-30", "2025-12-31"])
        span = measure_span(p)[0]
        assert span.years is not None and span.years > 1.9, "elapsed is ~2y"
        assert span.evidence_years is not None
        assert span.evidence_years < 0.02, "5 observed days is 0.014y of evidence, never 2y"
        assert span.evidence_years < span.years

    def test_gap_days_and_observed_days_can_never_quietly_disagree(self, tmp_path: Path) -> None:
        p = tmp_path / "g.jsonl"
        _jsonl(p, ["2026-03-01", "2026-03-05", "2026-03-06", "2026-03-20"])
        span = measure_span(p)[0]
        assert span.days is not None and span.observed_days is not None
        assert span.gap_days == span.days - span.observed_days, "the identity IS the guard"

    def test_a_contiguous_series_reports_zero_gap_and_full_evidence(self, tmp_path: Path) -> None:
        p = tmp_path / "clean.jsonl"
        _jsonl(p, [f"2026-01-0{i}" for i in range(1, 10)])
        span = measure_span(p)[0]
        assert span.gap_days == 0 and span.n_gaps == 0 and not span.gapped
        assert span.evidence_years == span.years, "no holes means elapsed IS evidence"

    def test_many_rows_on_few_days_cannot_manufacture_evidence(self, tmp_path: Path) -> None:
        """Row #77's own overstatement, restated against the new field: rows are not days."""
        p = tmp_path / "dense.jsonl"
        _jsonl(p, ["2026-01-01", "2026-06-30"], per_day=5_000)
        span, rows, _ = measure_span(p)
        assert rows == 10_000
        assert span.observed_days == 2, "10k rows over 2 days is 2 days"
        assert span.evidence_years is not None and span.evidence_years < 0.01

    def test_the_row_says_the_overstatement_out_loud(self, tmp_path: Path) -> None:
        _repo(tmp_path, days=["2020-01-01", "2026-01-01"])
        a = next(x for x in build(tmp_path) if x.id == "feed")
        note = "\n".join(a.notes)
        assert "GAPPED" in note, "a reader must not have to join two fields to see the hole"
        assert "of evidence, NOT" in note

    def test_a_sampled_span_leaves_gaps_unmeasured_rather_than_clean(self, tmp_path: Path) -> None:
        """UNMEASURED and MEASURED-AND-CONTINUOUS are the pair this module refuses to conflate."""
        for s in range(9):
            _parquet(tmp_path / f"data/lake/bronze/crypto/S{s}/D1/p.parquet", days=30, rows=30)
        sampled = next(x for x in build(tmp_path) if x.id == "lake_crypto")
        assert sampled.span.measured
        assert sampled.span.gap_days is None, "a 3-of-9 sample cannot prove the other 6 are whole"
        assert sampled.span.evidence_years is None
        assert not sampled.span.gapped, (
            "'gapped' means holes were FOUND, never merely never looked for")
        deep = next(x for x in build(tmp_path, deep=True) if x.id == "lake_crypto")
        assert deep.span.gap_days == 0, "reading every member CAN prove it"


class TestARaggedPanelIsNotItsUnion:
    """25 symbols whose union spans 5.7 years is not a 25-symbol 5.7-year panel."""

    def _panel(self, root: Path, long_syms: int, short_syms: int) -> None:
        for s in range(long_syms):
            _parquet(root / f"data/lake/bronze/crypto/L{s}/D1/p.parquet", days=400, rows=400)
        for s in range(short_syms):
            p = root / f"data/lake/bronze/crypto/S{s}/D1/p.parquet"
            p.parent.mkdir(parents=True, exist_ok=True)
            dates = pd.date_range("2026-06-01", periods=60, freq="D")
            pd.DataFrame([{"date": d.date().isoformat(), "v": 1.0} for d in dates]).to_parquet(p)

    def test_the_balanced_window_is_the_one_every_partition_covers(self, tmp_path: Path) -> None:
        self._panel(tmp_path, long_syms=3, short_syms=2)
        a = next(x for x in build(tmp_path, deep=True) if x.id == "lake_crypto")
        assert a.span.days == 400, "the union is still reported"
        assert a.span.balanced_days is not None and a.span.balanced_days < a.span.days
        assert a.span.balanced_first == "2026-06-01"

    def test_a_ragged_panel_says_so(self, tmp_path: Path) -> None:
        self._panel(tmp_path, long_syms=3, short_syms=2)
        a = next(x for x in build(tmp_path, deep=True) if x.id == "lake_crypto")
        assert any("RAGGED PANEL" in n for n in a.notes)

    def test_a_square_panel_is_not_flagged(self, tmp_path: Path) -> None:
        self._panel(tmp_path, long_syms=4, short_syms=0)
        a = next(x for x in build(tmp_path, deep=True) if x.id == "lake_crypto")
        assert a.span.balanced_days == a.span.days
        assert not any("RAGGED PANEL" in n for n in a.notes)


class TestNotReadableHereNeverCountsAsMeasured:
    """The moat tape and the recorder output live on the VPS. This box must say so, with a path."""

    def test_an_absent_path_is_flagged_unreadable_and_names_itself(self, tmp_path: Path) -> None:
        span = measure_span(tmp_path / "data/moat/execution_tape/trades.jsonl")[0]
        assert not span.readable_here
        assert span.missing_path is not None
        assert span.missing_path.endswith("data/moat/execution_tape/trades.jsonl")
        assert not span.measured and span.days is None and span.observed_days is None

    def test_the_note_carries_the_exact_missing_path(self, tmp_path: Path) -> None:
        _repo(tmp_path, asset="data/moat/execution_tape/cashcarry_trades.jsonl")
        a = next(x for x in build(tmp_path) if x.id == "cashcarry_trades")
        note = "\n".join(a.notes)
        assert NOT_READABLE_HERE in note
        assert "data/moat/execution_tape/cashcarry_trades.jsonl" in note, "an address, not a shrug"
        assert a.span.missing_path == "data/moat/execution_tape/cashcarry_trades.jsonl"

    def test_it_is_never_counted_among_the_measured(self, tmp_path: Path) -> None:
        _repo(tmp_path, asset="data/gone.jsonl")
        assets = build(tmp_path)
        assert assets, "the asset is still DECLARED -- it must appear, just not as measured"
        assert not any(a.span.measured for a in assets)
        assert all(a.span.days is None for a in assets), "absent is never a zero-day span"

    def test_zero_is_never_substituted_for_unknown(self, tmp_path: Path) -> None:
        _repo(tmp_path, asset="data/gone.jsonl")
        a = next(x for x in build(tmp_path) if x.id == "gone")
        for value in (a.span.days, a.span.years, a.span.observed_days, a.span.gap_days,
                      a.span.evidence_years, a.rows, a.bytes):
            assert value is None, "a guess of 0 is the failure this whole module exists to prevent"


class TestTheNpzPanelIsDiscoveredAndMeasured:
    """Row #77's understatement, third instance. ``data/binance_vision`` is 55 files of USD-M perp
    history -- the LONGEST thing this checkout can measure -- and both existing sweeps were blind
    to it: the flat scan only knows parquet/jsonl, the lake sweep only walks data/lake/bronze."""

    def _npz(self, p: Path, days: list[str]) -> None:
        import numpy as np
        p.parent.mkdir(parents=True, exist_ok=True)
        ms = [datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp() * 1000.0 for d in days]
        np.savez_compressed(p, open_time=np.asarray(ms, dtype="float64"),
                            close=np.ones(len(ms), dtype="float64"))

    def _days(self, first: str, n: int, skip: set[str] | None = None) -> list[str]:
        start = date.fromisoformat(first)
        out = [(start + timedelta(days=i)).isoformat() for i in range(n)]
        return [d for d in out if d not in (skip or set())]

    def test_a_cache_dir_becomes_one_asset_per_interval(self, tmp_path: Path) -> None:
        self._npz(tmp_path / "data/binance_vision/BTCUSDT-1d-2020-12-2026-07.npz",
                  self._days("2020-12-01", 60))
        self._npz(tmp_path / "data/binance_vision/BTCUSDT-5m-2023-08-2026-07.npz",
                  self._days("2023-08-01", 30))
        ids = [a.id for a in build(tmp_path)]
        assert "binance_vision_1d" in ids and "binance_vision_5m" in ids, (
            "a daily panel and a 5-minute panel bound different studies -- one span for both "
            "would be the same conflation row #77 was about")

    def test_a_partition_hole_survives_into_the_note(self, tmp_path: Path) -> None:
        """The union span HIDES a per-symbol hole: BTC's dead month is covered by the other 24."""
        hole = {(date(2021, 1, 1) + timedelta(days=i)).isoformat() for i in range(31)}
        self._npz(tmp_path / "data/binance_vision/BTCUSDT-1d-2020-12-2026-07.npz",
                  self._days("2020-12-01", 120, skip=hole))
        self._npz(tmp_path / "data/binance_vision/ETHUSDT-1d-2020-12-2026-07.npz",
                  self._days("2020-12-01", 120))
        a = next(x for x in build(tmp_path) if x.id == "binance_vision_1d")
        assert a.span.gap_days == 0, "the UNION really is whole -- ETH covers BTC's dead month"
        assert any("PARTITION HOLES" in n for n in a.notes), (
            "and that is exactly why the per-partition holes must be named separately")
        assert any("BTCUSDT" in n for n in a.notes)

    def test_breadth_is_the_symbol_count_and_rows_are_real(self, tmp_path: Path) -> None:
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            self._npz(tmp_path / f"data/binance_vision/{sym}-1d-2023-08-2026-07.npz",
                      self._days("2023-08-01", 40))
        a = next(x for x in build(tmp_path) if x.id == "binance_vision_1d")
        assert a.breadth == 3
        assert a.rows == 120, "every npz member is opened, so the row total is real, not sampled"
        assert a.span.observed_days == 40


class TestMeasureGapsIsHonestAtTheEdges:
    def test_a_single_day_has_no_measurable_gap(self) -> None:
        assert measure_gaps(["2026-01-01"]) is None, "one point cannot prove or disprove a hole"

    def test_an_empty_day_set_is_none_not_zero(self) -> None:
        assert measure_gaps([]) is None

    def test_unparseable_days_do_not_fabricate_a_gap(self) -> None:
        assert measure_gaps(["not-a-date", "also-not"]) is None

    def test_the_largest_run_is_the_one_reported(self) -> None:
        g = measure_gaps(["2026-01-01", "2026-01-03", "2026-01-20"])
        assert g is not None
        assert g.n_gaps == 2 and g.gap_days == 17
        assert g.largest_gap_days == 16
        assert g.largest_gap_from == "2026-01-04" and g.largest_gap_to == "2026-01-19"


class TestTheArtifactSchemaIsStable:
    """The registry is read by the capability ratchet, knowledge_engine and check_utilisation.
    Its top-level shape is a contract, and new fields may only be ADDED beside the old ones."""

    #: keys the artifact carried before the span work, none of which may disappear
    LEGACY = ("generated", "deep", "counts", "longest_span_days", "widest_breadth",
              "proprietary", "unread_long_history", "unscheduled_collectors", "assets")
    #: the ratchet's own contract: libs/research/capability_ratchet._data_coverage reads exactly
    #: counts.measured over counts.assets, and nothing else in this file
    RATCHET = ("assets", "measured", "absent")

    def _payload(self, tmp_path: Path) -> dict[str, Any]:
        _repo(tmp_path, days=["2026-01-01", "2026-01-02", "2026-03-01"])
        (tmp_path / "scripts/ghost.py").write_text('P = "data/vanished.jsonl"\n', "utf-8")
        assert build_registry(["--root", str(tmp_path)]) == 0
        return json.loads((tmp_path / "data/data_assets.json").read_text("utf-8"))

    def test_every_legacy_key_survives(self, tmp_path: Path) -> None:
        doc = self._payload(tmp_path)
        for key in self.LEGACY:
            assert key in doc, f"{key} is read by an organ that this pass does not own"

    def test_the_ratchets_counts_contract_is_intact(self, tmp_path: Path) -> None:
        counts = self._payload(tmp_path)["counts"]
        for key in self.RATCHET:
            assert isinstance(counts[key], int)
        assert counts["measured"] <= counts["assets"]
        assert counts["absent"] + counts["measured"] <= counts["assets"]

    def test_measured_and_absent_are_disjoint_and_add_up(self, tmp_path: Path) -> None:
        doc = self._payload(tmp_path)
        rows = doc["assets"]
        assert doc["counts"]["assets"] == len(rows)
        assert doc["counts"]["measured"] == sum(1 for r in rows
                                                if r["span"]["status"] == "measured")
        assert doc["counts"]["absent"] == sum(1 for r in rows if not r["span"]["readable_here"])

    def test_every_span_row_carries_the_depth_fields(self, tmp_path: Path) -> None:
        doc = self._payload(tmp_path)
        assert doc["spans"], "at least one asset is measurable in the fixture"
        for row in doc["spans"]:
            for key in ("id", "years", "evidence_years", "days", "observed_days", "gap_days",
                        "n_gaps", "largest_gap_days", "rows", "first", "last"):
                assert key in row

    def test_every_unreadable_row_names_its_missing_path(self, tmp_path: Path) -> None:
        doc = self._payload(tmp_path)
        assert doc["not_readable_here"], "the fixture declares a path that is not on disk"
        for row in doc["not_readable_here"]:
            assert row["status"] == NOT_READABLE_HERE
            assert row["missing_path"], "a count with no address is not actionable"

    def test_the_artifact_is_valid_json_and_ranked_deepest_first(self, tmp_path: Path) -> None:
        spans = self._payload(tmp_path)["spans"]
        years = [r["evidence_years"] or 0.0 for r in spans]
        assert years == sorted(years, reverse=True), (
            "'which source is long enough to test on' must be answerable by reading the top row")


class TestTheRatchetCountActuallyRises:
    """The point of the whole pass: data_coverage.assets_with_measured_span must be able to move,
    and it must move BECAUSE spans were measured -- never because the denominator was trimmed."""

    def _artifact(self, root: Path, *, measured: int, assets: int) -> None:
        (root / "data").mkdir(parents=True, exist_ok=True)
        (root / "data/data_assets.json").write_text(json.dumps({
            "generated": "2026-08-05T00:00:00+00:00", "deep": True,
            "counts": {"assets": assets, "measured": measured,
                       "absent": assets - measured, "not_readable_here": assets - measured},
            "assets": [], "spans": [], "not_readable_here": []}), "utf-8")

    def _score(self, root: Path) -> float:
        aspect = next(a for a in read_capability(root) if a.key == "data_coverage")
        comp = next(c for c in aspect.components if c.key == "assets_with_measured_span")
        return comp.score

    def test_measuring_more_assets_raises_the_component(self, tmp_path: Path) -> None:
        before, after = tmp_path / "before", tmp_path / "after"
        self._artifact(before, measured=2, assets=46)
        self._artifact(after, measured=16, assets=46)
        assert self._score(after) > self._score(before)

    def test_the_score_is_ten_times_the_measured_fraction(self, tmp_path: Path) -> None:
        self._artifact(tmp_path, measured=16, assets=98)
        assert self._score(tmp_path) == pytest.approx(10.0 * 16 / 98, abs=0.05)

    def test_the_real_artifact_on_this_box_is_readable_by_the_ratchet(self,
                                                                     tmp_path: Path) -> None:
        """End to end: what build_data_registry actually wrote is what the ratchet actually counts.

        The live artifact is COPIED first rather than scored in place -- the desk rebuilds it on a
        cron and inside run_intelligence_cycle, and a test that reads the file twice around a
        rebuild would fail on a race instead of on the contract it is guarding.
        """
        raw = (REPO / "data/data_assets.json").read_text("utf-8")
        (tmp_path / "data").mkdir(parents=True)
        (tmp_path / "data/data_assets.json").write_text(raw, "utf-8")
        doc = json.loads(raw)
        aspect = next(a for a in read_capability(tmp_path) if a.key == "data_coverage")
        comp = next(c for c in aspect.components if c.key == "assets_with_measured_span")
        assert comp.state == "MEASURED"
        assert comp.score == pytest.approx(
            10.0 * doc["counts"]["measured"] / doc["counts"]["assets"], abs=0.06)

    def test_an_unreadable_asset_cannot_inflate_the_numerator(self, tmp_path: Path) -> None:
        """The one way this score could be faked: counting declared-but-absent rows as measured."""
        _repo(tmp_path, asset="data/gone.jsonl")
        assert build_registry(["--root", str(tmp_path)]) == 0
        counts = json.loads(
            (tmp_path / "data/data_assets.json").read_text("utf-8"))["counts"]
        assert counts["measured"] == 0 and counts["assets"] >= 1
        assert self._score(tmp_path) == 0.0


class TestTheFastAndSlowClockReadersAgree:
    """The npz path reads its clock vectorised; the jsonl path reads it per element. Two readers
    of the same instant are two chances to disagree, so the agreement is asserted, not assumed."""

    def test_they_return_the_same_days_across_every_epoch_unit(self) -> None:
        import numpy as np

        base = datetime(2024, 3, 1, 12, 0, tzinfo=UTC).timestamp()
        stamps = [base + 3600.0 * i for i in range(0, 24 * 40, 7)]
        for mult in (1.0, 1e3, 1e6, 1e9):     # seconds, ms, us, ns -- all legal in this desk's data
            arr = np.asarray([s * mult for s in stamps], dtype="float64")
            fast = _days_from_epoch(arr)
            slow = {d for d in (_iso_day(v) for v in arr.tolist()) if d}
            assert fast == slow, f"the two clock readers disagree at x{mult:g}"

    def test_a_non_numeric_clock_falls_back_rather_than_reading_dateless(self) -> None:
        import numpy as np

        assert _days_from_epoch(np.asarray(["2026-01-01", "2026-01-02"], dtype=object)) is None

    def test_an_empty_clock_is_an_empty_day_set_not_a_failure(self) -> None:
        import numpy as np

        assert _days_from_epoch(np.asarray([], dtype="float64")) == set()


class TestTheDateKeyListStaysMostSpecificFirst:
    """_DATE_COLS grows every time a readable asset turns out to key its clock differently. Order
    is load-bearing: the scan stops at the FIRST key present, so a generic name added ahead of a
    specific one silently re-dates every asset that carries both."""

    def test_a_record_with_two_clocks_is_read_on_the_specific_one(self, tmp_path: Path) -> None:
        p = tmp_path / "two.jsonl"
        p.write_text(json.dumps({"date": "2026-01-01", "at": "2020-05-05"}) + "\n"
                     + json.dumps({"date": "2026-01-02", "at": "2020-05-06"}) + "\n", "utf-8")
        span = measure_span(p)[0]
        assert span.first == "2026-01-01", "'at' is the fallback, never the override"

    def test_an_observation_stamp_beats_the_day_the_desk_first_saw_it(self,
                                                                     tmp_path: Path) -> None:
        """A backfilled feed's `first_seen_utc` is TODAY on every row -- reading the span off
        it would report 1 day for a 3-month series."""
        p = tmp_path / "flow.jsonl"
        p.write_text("".join(
            json.dumps({"stamp": d, "first_seen_utc": "2026-08-05T00:00:00+00:00"}) + "\n"
            for d in ("2026-06-01", "2026-06-02", "2026-06-03")), "utf-8")
        span = measure_span(p)[0]
        assert span.first == "2026-06-01" and span.observed_days == 3

    def test_every_key_in_the_list_is_actually_reachable(self) -> None:
        assert len(set(_DATE_COLS)) == len(_DATE_COLS), "a duplicate key is dead configuration"


class TestTheRegistryDoesNotDeclareItsOwnExamples:
    """It greps the corpus it is IN. A path written as an example in this module's own comments was
    discovered as a declared asset and reported NOT-READABLE-HERE -- the registry inflating its own
    denominator with a path nothing writes and nothing reads."""

    def test_no_asset_is_declared_solely_by_the_registry_module(self) -> None:
        for a in build(REPO):
            assert a.collector != "libs/research/data_registry.py"
            assert "libs/research/data_registry.py" not in a.consumers

    def test_a_module_that_only_names_a_path_in_prose_declares_nothing(self,
                                                                      tmp_path: Path) -> None:
        (tmp_path / "libs/research").mkdir(parents=True)
        (tmp_path / "libs/research/data_registry.py").write_text(
            'PAT = "data/example_only.jsonl"\n', "utf-8")
        assert not [a for a in build(tmp_path) if a.id == "example_only"]
