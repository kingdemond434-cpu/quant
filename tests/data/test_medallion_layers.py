"""The layer is a property of the ROW, and `promote` refuses rather than guessing.

WHY THIS FILE EXISTS. `libs/data/lake.py` gained ~400 lines that decide whether a row may be
trusted as point-in-time, and a promoter that fills a missing `event_time` with the ingestion
time produces a lake in which every backtest passes and none of them mean anything. The
refusals are the load-bearing half of that code, so they are what is checked here: a skipped
layer, an unresolvable event time, a normaliser that raises or returns nothing, a feature that
cannot name its inputs, an edited bronze payload. Each is a way a row could become a
lookahead-free-looking lie.

The census is checked for the same reason it was written: a blended stamped fraction hides which
half of the lake is missing, so a layer holding nothing must read UNMEASURED and never as a pass
or a zero (L1.28a), and a row is filed under the layer it CLAIMS with `keeps_promise` saying how
often the claim is good.
"""
from __future__ import annotations

import gzip
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data import lake  # noqa: E402
from libs.data.lake import Layer  # noqa: E402

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
T2 = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _bronze(payload: dict | str | bytes, *, source: str = "acme", now: datetime = T0, **extra):
    """A bronze row holding `payload` byte-for-byte, with `extra` as top-level fields.

    THE DISTINCTION MATTERS AND IS NOT COSMETIC. Bronze is BYTES: the arrived payload lives in
    `raw` as an opaque string, so a `published_at` inside it is invisible to `promote` until a
    normaliser parses it out. Producers therefore either lift the parsed fields onto the row
    (that is what `extra` is) or hand `promote` a normaliser -- and both paths are exercised
    below, because a test that only ever used one would leave the other unmeasured.
    """
    return lake.to_bronze(payload, source, source_version="v1", now=now, **extra)


def _dated(when: str = "2026-08-20T09:00:00+00:00", *, now: datetime = T0, **extra):
    """A bronze row whose producer supplied an EVENT date and no availability claim.

    `event_date` deliberately, not `published_at`: `pit.AVAILABLE_KEYS` carries `published_at`,
    so a row dated that way is treated as knowable from the moment it was published, while
    `event_date` leaves `available_time` at ingestion. Which of those a producer writes decides
    what a backtest may read, and the difference is pinned below.
    """
    return _bronze({"body": "x", **extra}, now=now, event_date=when, **extra)


# ------------------------------------------------------------------- bronze is byte-faithful
def test_bronze_hands_back_exactly_the_bytes_that_arrived():
    for arrived in (b'{"a": 1}', '{"a": 1}', {"a": 1}):
        row = _bronze(arrived)
        assert lake.verify_bronze(row)
        assert lake.bronze_bytes(row) == lake._arrival_bytes(arrived)
        assert row["layer"] == "bronze"


def test_bronze_survives_bytes_that_are_not_utf8():
    """A gzipped rollup or a latin-1 scrape must survive the JSON round trip every store here
    performs, or `raw` is a claim the file cannot support."""
    body = gzip.compress(b"a,b\n1,2\n")
    row = _bronze(body)
    assert row["raw_encoding"] == "base64"
    assert lake.bronze_bytes(row) == body and lake.verify_bronze(row)
    assert gzip.decompress(lake.bronze_bytes(row)) == b"a,b\n1,2\n"


def test_a_bronze_row_edited_in_place_fails_verification_instead_of_reading_pristine():
    row = _bronze({"a": 1})
    row["raw"] = '{"a": 2}'
    assert not lake.verify_bronze(row), "an edited payload verified as byte-faithful"


def test_bronze_makes_no_claim_about_when_the_event_happened():
    """Bronze knows when the desk wrote a thing down, not when it happened. If `to_bronze` ever
    starts setting event_time, silver's refusal becomes unreachable and the whole ladder is
    decorative."""
    row = _bronze({"a": 1})
    assert not row.get("event_time")
    assert lake.layer_of(row) is Layer.BRONZE


# ----------------------------------------------------------------- the layer is on the row
def test_a_row_is_the_layer_whose_promises_it_keeps_not_the_one_it_is_labelled():
    row = _bronze({"a": 1})
    row["layer"] = "gold"                       # the label lies
    assert lake.layer_of(row) is None, "a mislabelled row was believed"
    assert lake.missing_for(row, Layer.GOLD), "gold's promises were reported as kept"


def test_missing_for_names_every_promise_the_row_does_not_keep():
    miss = lake.missing_for({}, Layer.SILVER)
    for required in ("event_time", "available_time", "normalisation", "promoted_from"):
        assert required in miss


# --------------------------------------------------------------------------- the refusals
def test_skipping_a_layer_is_refused_outright_and_the_only_path_is_named():
    got = lake.promote([_bronze({"a": 1})], Layer.BRONZE, Layer.GOLD)
    assert got.counts == {"seen": 1, "promoted": 0, "refused": 1}
    assert "skips a layer" in got.refused[0]["why"]
    assert "bronze -> silver -> gold" in got.refused[0]["why"]


def test_a_row_with_no_resolvable_event_time_is_refused_and_never_stamped_with_now():
    """THE REFUSAL THE WHOLE FILE IS ABOUT. Measured over both intelligence trees on
    2026-09-09, event_time was present on 0.0% of 2,816 rows -- so a promoter that filled it in
    would have manufactured 2,816 rows that look free of lookahead and are not."""
    got = lake.promote([_bronze({"headline": "no date here"})], Layer.BRONZE, Layer.SILVER)
    assert got.counts["promoted"] == 0
    why = got.refused[0]["why"]
    assert "no resolvable event_time" in why and "REFUSED rather than stamped with now" in why


def test_event_time_and_available_time_are_two_different_facts():
    """One says when the thing happened, the other when the desk could have known it. A
    promotion that collapses them is the fabricated stamp `promote` exists to refuse."""
    row = _dated("2026-08-20T09:00:00+00:00", now=T0)
    got = lake.promote([row], Layer.BRONZE, Layer.SILVER, now=T1)
    (silver,) = got.rows
    assert silver["event_time"] == "2026-08-20T09:00:00+00:00"
    assert silver["available_time"] == row["ingested_time"] == T0.isoformat()
    assert silver["event_time"] != silver["available_time"]
    assert lake.layer_of(silver) is Layer.SILVER
    assert silver["promoted_from"] == row["payload_hash"]


def test_a_published_at_row_is_knowable_from_publication_and_that_is_an_exposure():
    """MEASURED, NOT ENDORSED (2026-09-09). `pit.AVAILABLE_KEYS` lists `published_at`, so a row
    carrying one is available from the moment it was PUBLISHED rather than from the moment this
    desk ingested it -- here, knowable twelve days before it was scraped.

    For a feed the desk actually subscribes to that is right: a press release was knowable when
    it was released. For a source the desk SCRAPES weeks later it is lookahead, and no field on
    the row distinguishes the two cases. The behaviour is pinned rather than changed, because
    `AVAILABLE_KEYS` is read by every producer on the desk and narrowing it is a decision about
    what every backtest may read -- recorded as a named gap on the ledger's PIT row instead.
    """
    row = _bronze({"body": "x"}, published_at="2026-08-20T09:00:00+00:00", now=T0)
    assert row["available_time"] == "2026-08-20T09:00:00+00:00" != row["ingested_time"]
    assert lake.read_as_of([row], datetime(2026, 8, 25, tzinfo=UTC)) == [row], (
        "the exposure has been closed; update this test and the ledger's PIT row together")


def test_a_normaliser_that_raises_or_returns_nothing_refuses_the_row_rather_than_the_run():
    rows = [_dated(i=i) for i in range(3)]

    def _boom(_r):
        raise KeyError("column the producer promised")

    got = lake.promote(rows, Layer.BRONZE, Layer.SILVER, normalise=_boom)
    assert got.counts == {"seen": 3, "promoted": 0, "refused": 3}
    assert "normalise raised KeyError" in got.refused[0]["why"]

    got = lake.promote(rows, Layer.BRONZE, Layer.SILVER, normalise=lambda _r: {})
    assert got.counts["promoted"] == 0
    assert "normalise produced nothing" in got.refused[0]["why"]


def test_a_gold_row_names_the_silver_rows_it_was_computed_from():
    silver = lake.promote([_dated()], Layer.BRONZE, Layer.SILVER).rows
    got = lake.promote(silver, Layer.SILVER, Layer.GOLD,
                       feature=lambda r: {**r, "score": 1.0}, feature_name="sentiment_v1")
    (g,) = got.rows
    assert lake.layer_of(g) is Layer.GOLD
    assert g["feature"] == "sentiment_v1"
    assert g["computed_from"] == [silver[0]["payload_hash"]]


def test_promote_many_names_every_input_row_not_just_the_last():
    """A feature usually reads many rows and emits one; `computed_from` naming only the last is
    an audit trail that cannot be walked back."""
    silver = lake.promote(
        [_dated(f"2026-08-2{i}T09:00:00+00:00", i=i) for i in range(3)],
        Layer.BRONZE, Layer.SILVER).rows
    assert len(silver) == 3
    got = lake.promote_many([silver], Layer.SILVER, Layer.GOLD,
                            feature=lambda r: {**r, "mean": 1.0}, feature_name="agg")
    (g,) = got.rows
    assert g["computed_from"] == [r["payload_hash"] for r in silver]
    assert g["payload_hash"] == lake.payload_hash(g)


def test_the_promotion_reports_its_denominator():
    """A promotion that reports 40 rows without the 60 it refused is a coverage claim with the
    denominator removed."""
    rows = [_dated(), _bronze({"no": "date"})]
    rep = lake.promote(rows, Layer.BRONZE, Layer.SILVER).report()
    assert rep["counts"] == {"seen": 2, "promoted": 1, "refused": 1}
    assert rep["from"] == "bronze" and rep["to"] == "silver"
    assert rep["refusals"] and "fabricated stamp" in rep["rule"]


# ------------------------------------------------------------------------------ read_as_of
def test_read_as_of_hides_a_row_the_desk_could_not_have_known_yet():
    early = lake.promote([_dated("2026-08-20T09:00:00+00:00", now=T0)],
                         Layer.BRONZE, Layer.SILVER).rows
    late = lake.promote([_dated("2026-08-21T09:00:00+00:00", now=T2)],
                        Layer.BRONZE, Layer.SILVER).rows
    seen = lake.read_as_of(early + late, T1)
    assert [r["event_time"] for r in seen] == ["2026-08-20T09:00:00+00:00"]


def test_read_as_of_hides_an_unstamped_row_at_every_time_because_absence_is_not_permission():
    assert lake.read_as_of([{"value": 1}], T2) == []


def test_read_as_of_returns_the_vintage_current_then_not_the_newest_revision():
    """A backtest dated before a restatement must read the figure it would actually have
    traded on."""
    first = lake.promote([_dated(now=T0, series="cpi", value=1.0)],
                         Layer.BRONZE, Layer.SILVER).rows[0]
    revised = lake.promote([_dated(now=T2, series="cpi", value=2.0)],
                           Layer.BRONZE, Layer.SILVER).rows[0]
    at_t1 = lake.read_as_of([first, revised], T1, key_fields=("series",))
    assert [r["value"] for r in at_t1] == [1.0]
    at_t2 = lake.read_as_of([first, revised], datetime(2026, 9, 4, tzinfo=UTC),
                            key_fields=("series",))
    assert [r["value"] for r in at_t2] == [2.0]


# --------------------------------------------------------------------------- the census
def test_an_empty_layer_reads_unmeasured_and_never_as_a_pass_or_a_zero():
    census = lake.layer_census([_bronze({"a": 1})])
    per = census["per_layer"]
    assert per["bronze"]["status"] == "measured" and per["bronze"]["rows"] == 1
    for empty in ("silver", "gold"):
        assert per[empty]["status"] == "UNMEASURED"
        assert per[empty]["keeps_promise_frac"] is None and per[empty]["stamped_frac"] is None
        assert "neither a pass nor a zero" in per[empty]["_"]


def test_the_census_files_a_row_under_what_it_CLAIMS_and_scores_whether_the_claim_is_good():
    """Filing by the truth instead would make every census read 100% and measure nothing."""
    good = _bronze({"a": 1})
    liar = _bronze({"a": 2})
    liar["layer"] = "silver"                      # claims silver, keeps none of its promises
    per = lake.layer_census([good, liar])["per_layer"]
    assert per["bronze"]["rows"] == 1 and per["bronze"]["keeps_promise"] == 1
    assert per["silver"]["rows"] == 1 and per["silver"]["keeps_promise"] == 0
    assert per["silver"]["keeps_promise_frac"] == 0.0


def test_rows_the_lake_has_not_reached_are_counted_rather_than_averaged_away():
    census = lake.layer_census([{"value": 1}, _bronze({"a": 1})])
    assert census["unlayered"]["rows"] == 1 and census["unlayered"]["stamped"] == 0
    assert census["per_layer"]["bronze"]["rows"] == 1


def test_every_layer_publishes_the_promise_it_is_measured_against():
    per = lake.layer_census([])["per_layer"]
    assert "byte-faithful" in per["bronze"]["promise"]
    assert "event_time" in per["silver"]["promise"]
    assert "computed from" in per["gold"]["promise"]
    assert "never of a directory" in lake.layer_census([])["rule"]


def test_bronze_bytes_refuses_a_row_that_carries_no_payload():
    with pytest.raises(ValueError, match="not a bronze row"):
        lake.bronze_bytes({"layer": "bronze"})
