"""THE REGISTRY THAT DECIDES WHAT THE DESK THINKS IT OWNS -- 306 statements, zero tests until now.

Every number this module produces feeds a judgement about which data is worth keeping, which feed
is quietly dead, and which asset carries a moat. It shipped unmeasured, which means the failure it
was written to prevent -- an inventory drifting from reality -- was live in the inventory itself.

WHAT IS ASSERTED HERE, and why these and not line coverage:

  * UNMEASURED IS NEVER ZERO. The module's whole discipline is that `None` means "nobody looked"
    and 0.0 means "looked, found nothing". Collapsing the two is how a dead recorder reads as a
    healthy one, so every absent-path test asserts the distinction rather than just a falsy value.
  * MOAT AND RESEARCH VALUE MOVE ON DIFFERENT INPUTS. A 26-year public panel must score ZERO moat
    and high research value. If length ever leaks into the moat score, the desk starts believing it
    owns an advantage it merely noticed.
  * THE GREP-DERIVED OWNER MAP DISTINGUISHES WRITERS FROM READERS. That map is the reason the
    lineage is trustworthy; if a reader is recorded as a writer, `dependencies` inverts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import data_registry as R

# ------------------------------------------------------------------- _iso_day: the unit parser


@pytest.mark.parametrize(("raw", "want"), [
    ("2026-08-06", "2026-08-06"),
    ("2026-08-06T11:22:33Z", "2026-08-06"),
    (1767225600, "2026-01-01"),            # seconds
    (1767225600_000, "2026-01-01"),        # milliseconds
    (1767225600_000_000, "2026-01-01"),    # microseconds
    (1767225600_000_000_000, "2026-01-01"),  # nanoseconds
])
def test_iso_day_infers_the_epoch_unit_from_magnitude(raw, want) -> None:
    """A tape carries seconds, a venue REST feed carries ms, parquet often carries ns. Guessing
    wrong by 1000x lands the row in 1970 or 55000 and silently destroys the span."""
    assert R._iso_day(raw) == want


@pytest.mark.parametrize("raw", [None, "", "   ", "not-a-date", float("nan"), 12345])
def test_iso_day_returns_None_rather_than_a_wrong_date(raw) -> None:
    """12345 is inside no plausible epoch band. Returning None keeps it out of the span; coercing
    it would put 1970-01-01 in `first` and make every span look decades long."""
    assert R._iso_day(raw) is None


# ------------------------------------------------------------------- span assembly

def test_no_days_is_no_date_column_not_an_empty_span() -> None:
    s = R._span_from_days([])
    assert s.status == "no-date-column"
    assert s.first is None and s.days is None
    assert not s.measured, "an unmeasured span must never report itself as measured"


def test_span_is_inclusive_of_both_endpoints() -> None:
    """A one-day file spans one day, not zero. Off-by-one here understates every archive."""
    assert R._span_from_days(["2026-01-01"]).days == 1
    assert R._span_from_days(["2026-01-01", "2026-01-31"]).days == 31


def test_span_takes_the_extremes_regardless_of_input_order() -> None:
    s = R._span_from_days(["2026-03-05", "2026-01-01", "2026-02-02"])
    assert (s.first, s.last, s.days) == ("2026-01-01", "2026-03-05", 64)


# ------------------------------------------------------------------- measure_span dispatch

def test_a_missing_file_is_absent_and_carries_no_counts(tmp_path: Path) -> None:
    span, rows, breadth = R.measure_span(tmp_path / "nope.jsonl")
    assert span.status == "absent"
    assert rows is None and breadth is None, "absent must not report 0 rows -- that is a count"


def test_an_unknown_extension_says_so_instead_of_guessing(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", "utf-8")
    assert R.measure_span(p)[0].status == "unsupported-format"


def _jsonl(p: Path, recs: list[dict]) -> Path:
    p.write_text("".join(json.dumps(r) + "\n" for r in recs), "utf-8")
    return p


def test_jsonl_span_rows_and_breadth_are_measured_together(tmp_path: Path) -> None:
    p = _jsonl(tmp_path / "f.jsonl", [
        {"date": "2026-01-01", "symbol": "BTCUSDT", "v": 1},
        {"date": "2026-01-05", "symbol": "ETHUSDT", "v": 2},
        {"date": "2026-01-03", "symbol": "BTCUSDT", "v": 3},
    ])
    span, rows, breadth = R.measure_span(p)
    assert (span.first, span.last, span.days) == ("2026-01-01", "2026-01-05", 5)
    assert rows == 3
    assert breadth == 2, "breadth is DISTINCT symbols, not row count"


def test_a_corrupt_line_is_skipped_but_still_counted_as_a_row(tmp_path: Path) -> None:
    """A truncated final line is the normal state of a file a recorder is appending to. It must
    not abort the measurement, and it must not vanish from the row count either -- a silently
    shorter count is how a half-written file reads as a healthy small one."""
    p = tmp_path / "f.jsonl"
    p.write_text('{"date": "2026-01-01"}\n{"date": "2026-01-02"\n', "utf-8")
    span, rows, _ = R.measure_span(p)
    assert rows == 2
    assert span.last == "2026-01-01", "the unparseable row contributes no date"


def test_jsonl_with_no_recognised_date_column_reports_no_date_column(tmp_path: Path) -> None:
    p = _jsonl(tmp_path / "f.jsonl", [{"value": 1}, {"value": 2}])
    span, rows, _ = R.measure_span(p)
    assert span.status == "no-date-column"
    assert rows == 2, "rows are still countable when the date is not"


# ------------------------------------------------------------------- quality

def test_quality_is_unmeasured_for_jsonl_rather_than_partially_scored(tmp_path: Path) -> None:
    """A PARTIAL score invites the same false confidence a partial map does -- the module says so
    in its own docstring, and this pins it."""
    p = _jsonl(tmp_path / "f.jsonl", [{"date": "2026-01-01"}])
    span, rows, breadth = R.measure_span(p)
    q = R.measure_quality(p, span, rows, breadth)
    assert q.dqs is None and not q.measured


def test_quality_catches_a_recorder_echoing_its_last_value(tmp_path: Path) -> None:
    """THE FAILURE A ROW COUNT CANNOT SEE. A live recorder writing the same number every day has
    perfect completeness and zero information. `stale_frac` is the only component that notices."""
    pd = pytest.importorskip("pandas")
    p = tmp_path / "echo.parquet"
    pd.DataFrame({"date": [f"2026-01-{d:02d}" for d in range(1, 11)],
                  "v": [7.0] * 10}).to_parquet(p)
    span, rows, breadth = R.measure_span(p)
    q = R.measure_quality(p, span, rows, breadth)
    assert q.stale_frac == 1.0, "every consecutive row identical must read as fully stale"
    assert q.dqs is not None and q.dqs < 100.0


def test_quality_scores_a_healthy_series_higher_than_a_stale_one(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    days = [f"2026-01-{d:02d}" for d in range(1, 11)]
    live = tmp_path / "live.parquet"
    dead = tmp_path / "dead.parquet"
    pd.DataFrame({"date": days, "v": list(range(10))}).to_parquet(live)
    pd.DataFrame({"date": days, "v": [1.0] * 10}).to_parquet(dead)

    def dqs(p: Path) -> float:
        s, r, b = R.measure_span(p)
        got = R.measure_quality(p, s, r, b).dqs
        assert got is not None
        return got

    assert dqs(live) > dqs(dead)


def test_nulls_are_counted_against_the_score(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    p = tmp_path / "holes.parquet"
    pd.DataFrame({"date": [f"2026-01-{d:02d}" for d in range(1, 11)],
                  "v": [1.0, None, 3.0, None, 5.0, None, 7.0, None, 9.0, None]}).to_parquet(p)
    s, r, b = R.measure_span(p)
    q = R.measure_quality(p, s, r, b)
    assert q.null_frac is not None and q.null_frac > 0.0


# ------------------------------------------------------------------- classification + scoring

@pytest.mark.parametrize(("aid", "want"), [
    ("moat_depth", R.REPL_PROPRIETARY),
    ("orderbook_snapshots", R.REPL_PROPRIETARY),
    ("funding_history", R.REPL_PERISHABLE),
    ("liquidation_prints", R.REPL_PERISHABLE),
    ("cot_source", R.REPL_REFETCHABLE),
    ("ohlcv_daily", R.REPL_REFETCHABLE),
])
def test_replication_class_decides_the_moat_not_the_size(aid, want) -> None:
    assert R.classify_replication(aid) == want


def test_proprietary_wins_over_perishable_when_both_match() -> None:
    """`moat_funding` matches both lists. Precedence must be deterministic and must favour the
    STRONGER claim, because our own timestamps are not re-acquirable at any price."""
    assert R.classify_replication("moat_funding") == R.REPL_PROPRIETARY


def _asset(**kw) -> R.DataAsset:
    kw.setdefault("id", "a")
    kw.setdefault("path", "data/a.parquet")
    return R.DataAsset(**kw)


def test_a_26_year_public_panel_scores_ZERO_moat_however_long_it_is() -> None:
    """26 years of CFTC COT is not an advantage the desk OWNS, it is one the desk NOTICED. If
    length ever leaks into the moat score, the registry starts flattering re-fetchable data."""
    a = _asset(span=R.AssetSpan("2000-01-01", "2026-01-01", 9497, "measured"),
               breadth=40, replication=R.REPL_REFETCHABLE)
    moat, research = R.score(a)
    assert moat == 0.0
    assert research > 50.0, "and it must still rank high on what can be TESTED on it"


def test_proprietary_data_starts_at_a_high_floor_even_when_young() -> None:
    a = _asset(span=R.AssetSpan("2026-08-01", "2026-08-06", 6, "measured"),
               replication=R.REPL_PROPRIETARY)
    assert R.score(a)[0] >= 70.0


def test_a_short_perishable_archive_scores_its_head_start_honestly() -> None:
    """A 28-day funding archive is ~4.6/60, and saying so is the point -- rounding it up to
    'we hold funding history' is how a four-week head start gets sized like a moat."""
    a = _asset(span=R.AssetSpan("2026-07-09", "2026-08-06", 28, "measured"),
               replication=R.REPL_PERISHABLE)
    moat = R.score(a)[0]
    assert 3.0 < moat < 6.0


def test_moat_grows_with_length_only_for_perishable_feeds() -> None:
    short = _asset(span=R.AssetSpan(days=30, status="measured"), replication=R.REPL_PERISHABLE)
    long_ = _asset(span=R.AssetSpan(days=900, status="measured"), replication=R.REPL_PERISHABLE)
    assert R.score(long_)[0] > R.score(short)[0]

    ref_s = _asset(span=R.AssetSpan(days=30, status="measured"))
    ref_l = _asset(span=R.AssetSpan(days=900, status="measured"))
    assert R.score(ref_l)[0] == R.score(ref_s)[0] == 0.0


def test_an_unread_long_asset_gets_the_paralysis_bonus() -> None:
    """Long history nobody consumes is the desk's most common failure, so the registry surfaces it
    rather than letting it sit at the same rank as a read one."""
    kw = {"span": R.AssetSpan(days=800, status="measured"), "breadth": 5}
    unread = R.score(_asset(**kw))[1]
    read = R.score(_asset(consumers=["scripts/x.py"], **kw))[1]
    assert unread == pytest.approx(read + 10.0)


def test_scores_are_bounded_to_the_declared_0_100_range() -> None:
    huge = _asset(span=R.AssetSpan(days=100_000, status="measured"), breadth=100_000,
                  replication=R.REPL_PROPRIETARY)
    moat, research = R.score(huge)
    assert 0.0 <= moat <= 100.0 and 0.0 <= research <= 100.0


def test_alpha_contribution_defaults_to_None_and_not_to_zero() -> None:
    """With zero validated alphas, 0.0 would read as 'measured and worthless'. None reads as
    'nothing attributed yet', which is the true state -- and organs must not have to guess."""
    assert _asset().alpha_contribution is None


def test_to_json_flattens_the_nested_dataclasses() -> None:
    d = _asset(span=R.AssetSpan(days=3, status="measured")).to_json()
    assert d["span"]["days"] == 3 and d["quality"]["dqs"] is None
    json.dumps(d)                       # must be serialisable -- it is written to an artifact


# ------------------------------------------------------------------- owner map + lineage

def _tree(root: Path) -> Path:
    (root / "scripts").mkdir(parents=True)
    (root / "libs").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    return root


def test_a_writer_is_distinguished_from_a_reader_by_the_call_around_it(tmp_path: Path) -> None:
    """If a reader is recorded as a writer, `dependencies` inverts and the lineage lies about
    which asset can never be longer than which."""
    root = _tree(tmp_path)
    (root / "scripts/collect.py").write_text(
        'import json\nrows=[]\nopen("data/out.jsonl","a").write(json.dumps(rows))\n', "utf-8")
    (root / "scripts/study.py").write_text(
        'import json\nrows=[json.loads(x) for x in open("data/out.jsonl")]\n', "utf-8")
    writers, readers = R._writers_and_readers(root)
    assert writers.get("data/out.jsonl") == "scripts/collect.py"
    assert readers.get("data/out.jsonl") == ["scripts/study.py"]


def test_dependencies_are_the_other_paths_the_collector_reads(tmp_path: Path) -> None:
    readers = {"data/raw.jsonl": ["scripts/derive.py"],
               "data/other.jsonl": ["scripts/unrelated.py"],
               "data/derived.jsonl": ["scripts/derive.py"]}
    deps = R._dependencies_of("scripts/derive.py", "data/derived.jsonl", readers)
    assert deps == ["raw"], "its own output is never its own dependency"


def test_an_asset_with_no_collector_has_no_dependencies() -> None:
    assert R._dependencies_of(None, "data/x.jsonl", {"data/y.jsonl": ["s.py"]}) == []


def test_a_collector_touching_secrets_is_flagged_as_credential_dependent(tmp_path: Path) -> None:
    """These are the feeds that die silently on key expiry -- the file keeps existing and the span
    keeps looking long."""
    root = _tree(tmp_path)
    (root / "scripts/keyed.py").write_text('K=open("data/secrets/x.json").read()\n', "utf-8")
    (root / "scripts/open.py").write_text("X = 1\n", "utf-8")
    assert R._needs_credentials(root, "scripts/keyed.py") is True
    assert R._needs_credentials(root, "scripts/open.py") is False
    assert R._needs_credentials(root, "scripts/missing.py") is False


# ------------------------------------------------------------------- cadence

@pytest.mark.parametrize(("line", "want"), [
    ("*/15 * * * * python scripts/a.py", 0.25),
    ("0 */6 * * * python scripts/a.py", 6.0),
    ("0 * * * * python scripts/a.py", 1.0),
    ("30 4 * * * python scripts/a.py", 24.0),
])
def test_cadence_is_parsed_into_hours_between_runs(tmp_path: Path, line, want) -> None:
    root = _tree(tmp_path)
    (root / "ops").mkdir()
    (root / "ops/crontab.manifest").write_text(line + "\n", "utf-8")
    assert R._cadence_hours(root)["scripts/a.py"] == want


def test_cadence_keeps_the_most_frequent_schedule_for_a_script(tmp_path: Path) -> None:
    """A script on two schedules runs at the FASTER one; taking the slower understates the
    recurring maintenance cost, which is the number this feeds."""
    root = _tree(tmp_path)
    (root / "ops").mkdir()
    (root / "ops/crontab.manifest").write_text(
        "0 */6 * * * python scripts/a.py\n*/15 * * * * python scripts/a.py\n", "utf-8")
    assert R._cadence_hours(root)["scripts/a.py"] == 0.25


def test_comments_and_env_lines_are_not_parsed_as_schedules(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / "ops").mkdir()
    (root / "ops/crontab.manifest").write_text(
        "# 0 * * * * python scripts/ghost.py\nQUANT_ROOT=/home/quant\n", "utf-8")
    assert R._cadence_hours(root) == {}


def test_a_missing_manifest_is_an_empty_map_not_a_crash(tmp_path: Path) -> None:
    assert R._cadence_hours(_tree(tmp_path)) == {}


# ------------------------------------------------------------------- partitioned lake

def test_a_partitioned_tree_is_discovered_where_a_flat_scan_sees_nothing(tmp_path: Path) -> None:
    """ROW #77's CASE. `data/lake/bronze/crypto/<SYM>/D1/*.parquet` is one directory per symbol, so
    a flat scan of data/ misses the desk's widest panel entirely."""
    pd = pytest.importorskip("pandas")
    root = _tree(tmp_path)
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        d = root / R._LAKE / "crypto" / sym / "D1"
        d.mkdir(parents=True)
        pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "c": [1.0, 2.0]}).to_parquet(
            d / "part.parquet")
    found = R._partitioned_assets(root)
    assert len(found) == 1
    aid, _, files = found[0]
    assert aid == "lake_crypto" and len(files) == 3


def test_no_lake_directory_yields_no_partitioned_assets(tmp_path: Path) -> None:
    assert R._partitioned_assets(_tree(tmp_path)) == []


# ------------------------------------------------------------------- build, end to end

def test_build_measures_a_declared_but_absent_asset_without_inventing_a_span(
        tmp_path: Path) -> None:
    """THE DISTINCTION THAT MATTERS ON A NON-COLLECTING BOX. A collector naming a path this
    machine has never written must appear with an UNMEASURED span and a note saying why -- not
    with a zero-length span, which would read as 'we have it and it is empty'."""
    root = _tree(tmp_path)
    (root / "scripts/collect.py").write_text(
        'open("data/never.jsonl","a").write("x")\n', "utf-8")
    assets = R.build(root)
    a = next(x for x in assets if x.id == "never")
    assert a.span.status == "absent"
    assert a.span.days is None and a.rows is None
    assert any("NOT PRESENT" in n for n in a.notes)
    assert a.collector == "scripts/collect.py"


def test_build_measures_a_present_asset_and_links_its_consumers(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _jsonl(root / "data/funding_history.jsonl",
           [{"date": "2026-01-01", "symbol": "BTCUSDT"},
            {"date": "2026-02-01", "symbol": "ETHUSDT"}])
    (root / "scripts/rec.py").write_text(
        'open("data/funding_history.jsonl","a").write("{}")\n', "utf-8")
    (root / "scripts/study.py").write_text(
        'rows = open("data/funding_history.jsonl").read()\n', "utf-8")

    a = next(x for x in R.build(root) if x.id == "funding_history")
    assert a.span.measured and a.span.days == 32
    assert a.rows == 2 and a.breadth == 2
    assert a.consumers == ["scripts/study.py"]
    assert a.replication == R.REPL_PERISHABLE, "funding is recent-only at the venue"
    assert a.bytes and a.bytes > 0
    assert a.last_validated is not None


def test_build_sorts_by_research_value_so_the_untested_history_surfaces(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _jsonl(root / "data/long_series.jsonl",
           [{"date": "2010-01-01"}, {"date": "2026-01-01"}])
    _jsonl(root / "data/short_series.jsonl",
           [{"date": "2026-01-01"}, {"date": "2026-01-02"}])
    for n in ("long_series", "short_series"):
        (root / f"scripts/w_{n}.py").write_text(f'open("data/{n}.jsonl","a").write("x")\n', "utf-8")
    ids = [a.id for a in R.build(root)]
    assert ids.index("long_series") < ids.index("short_series")


def test_build_is_read_only(tmp_path: Path) -> None:
    """The registry MEASURES. A build that wrote would make every run a mutation of the thing it
    is describing, and the artifact would stop being reproducible from the tree."""
    root = _tree(tmp_path)
    _jsonl(root / "data/x.jsonl", [{"date": "2026-01-01"}])
    before = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    R.build(root)
    after = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    assert before == after, "build() modified the tree it was measuring"
