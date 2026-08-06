"""THE MODE-COLLAPSE INSTRUMENTS -- 218 statements across three modules, zero tests until now.

"420 candidates tested, 0 survivors" and "one question asked 420 ways" are identical from a count,
and every dashboard here counts candidates -- so mode collapse reads as productivity. These three
modules are what tell them apart:

    mechanism_fingerprint   feature family + signal transform + horizon bucket, bucketed COARSELY
    variation_blocker       refuses a reparameterisation BEFORE compute, and logs the refusal
    collapse_detector       measures whether a whole batch was one idea wearing many hats

`mechanism_fingerprint.py` was ALSO the module a partial cherry-pick dropped on this branch while
keeping both of its importers, so the two below were a live ImportError until 2026-08-06. It is
tested first here for that reason: everything downstream is built on it.

THE TWO FAILURE DIRECTIONS, and both are live risks rather than theory:

  * TOO LOOSE -- every reparameterisation is charged as a fresh trial, the multiplicity budget is
    consumed by one question asked repeatedly, and DSR deflates against a count that means nothing.
  * TOO TIGHT -- a genuinely new question is silently deleted. The module's own docstring records
    this happening: without the horizon bucket, a 7-day and a 90-day carry signal produced
    identical token sets, scored Jaccard 1.00, and the 90-day version was BLOCKED despite their
    fingerprints differing. That regression is pinned below by name.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from libs.research import collapse_detector as D
from libs.research import mechanism_fingerprint as MF
from libs.research import variation_blocker as VB


def _hyp(*, family: str = "funding", subtype: str = "carry", edge_source: str = "funding/binance",
         mechanism: str = "carry", symbol: str | None = "BTCUSDT", **params) -> NS:
    return NS(family=family, subtype=subtype, edge_source=edge_source, mechanism=mechanism,
              symbol=symbol, params=params)


# ===================================================================== mechanism_fingerprint

#: Bucket edges are 1/5/21/63/252 days, so a "nearby" pair must sit INSIDE one band -- 7 and 5
#: straddle the days/weeks edge and are correctly different questions.
@pytest.mark.parametrize(("days", "want_same_as"), [(7, 14), (25, 40), (90, 80)])
def test_nearby_lookbacks_land_in_the_SAME_horizon_bucket(days, want_same_as) -> None:
    """A 20-day and a 21-day lookback are the same hypothesis; treating them as two is the
    forking-paths failure with a knob on it."""
    assert MF.horizon_bucket(days) == MF.horizon_bucket(want_same_as)


def test_distant_horizons_land_in_DIFFERENT_buckets() -> None:
    """Coarse is not the same as blind. A week and a quarter are different questions."""
    assert MF.horizon_bucket(7) != MF.horizon_bucket(90)


@pytest.mark.parametrize("bad", [None, 0, -5])
def test_an_absent_horizon_is_unspecified_rather_than_defaulted(bad) -> None:
    """Defaulting an unstated horizon to a real bucket would merge two ideas on a fact neither
    of them stated."""
    assert MF.horizon_bucket(bad) == "unspecified"


def test_the_symbol_is_NOT_part_of_the_fingerprint() -> None:
    """40 symbols on one mechanism is ONE idea, not forty. Including the symbol would let a
    universe sweep buy 40x the trial budget for a single question."""
    btc = _hyp(symbol="BTCUSDT", horizon_days=7)
    eth = _hyp(symbol="ETHUSDT", horizon_days=7)
    assert MF.fingerprint(btc) == MF.fingerprint(eth)
    assert MF.fingerprint_hash(btc) == MF.fingerprint_hash(eth)


def test_a_retuned_knob_inside_one_bucket_is_the_SAME_fingerprint() -> None:
    assert MF.fingerprint(_hyp(horizon_days=20)) == MF.fingerprint(_hyp(horizon_days=21))


def test_a_different_transform_is_a_DIFFERENT_fingerprint() -> None:
    carry = _hyp(subtype="carry", mechanism="carry", horizon_days=7)
    rev = _hyp(subtype="mean-revert", mechanism="reversal", edge_source="funding/binance",
               horizon_days=7)
    assert MF.fingerprint(carry) != MF.fingerprint(rev)


def test_the_transform_order_is_meaningful_and_first_match_wins() -> None:
    """Specific mechanics before generic shapes -- the order of _TRANSFORMS is load-bearing, so a
    reordering that changed classifications would be caught here."""
    assert MF.signal_transform("cross-sectional rank of funding") == "rank"
    assert MF.signal_transform("nothing recognisable at all") == "unclassified"


def test_the_family_falls_back_to_the_edge_source_stem_never_the_symbol() -> None:
    assert MF.feature_family(NS(edge_source="orderflow/binance/BTCUSDT")) == "orderflow"
    assert MF.feature_family(NS(edge_source="")) == "unknown"


def test_an_enum_like_family_is_unwrapped_to_its_value() -> None:
    assert MF.feature_family(NS(family=NS(value="onchain"))) == "onchain"


def test_a_non_numeric_horizon_param_is_skipped_rather_than_crashing() -> None:
    assert MF.horizon_bucket(MF._horizon_of(_hyp(horizon_days="soon"))) == "unspecified"


def test_stopwords_are_removed_so_the_similarity_metric_can_move() -> None:
    """Without this the Jaccard proxy scores every pair as similar on English scaffolding alone
    and the metric never moves -- a similarity score that is always high is not a detector."""
    assert MF.tokens("the price of the market data") == frozenset()
    assert "funding" in MF.tokens("funding basis carry")


def test_jaccard_is_1_for_two_empty_sets_and_0_for_disjoint_ones() -> None:
    """Two ideas that both reduce to nothing ARE the same idea by this proxy; treating the empty
    case as 0.0 would make every unclassifiable pair look maximally novel."""
    assert MF.jaccard(frozenset(), frozenset()) == 1.0
    assert MF.jaccard(frozenset("ab"), frozenset("cd")) == 0.0
    assert MF.jaccard(frozenset("abc"), frozenset("abd")) == pytest.approx(0.5)


def test_the_HORIZON_IS_IN_THE_DESCRIPTION_and_a_7d_and_90d_carry_are_distinguishable() -> None:
    """THE NAMED REGRESSION. Without the horizon bucket in `describe`, a 7-day and a 90-day carry
    signal produced identical token sets, so the near-duplicate check scored them at Jaccard 1.00
    and BLOCKED the 90-day version -- despite their fingerprints differing (carry/carry/weeks vs
    carry/carry/quarters). The semantic proxy was overriding the structured dimension it exists to
    complement, and silently deleting a genuinely different question."""
    wk = _hyp(horizon_days=7)
    qtr = _hyp(horizon_days=90)
    assert MF.fingerprint(wk) != MF.fingerprint(qtr), "precondition: the fingerprints differ"
    sim = MF.jaccard(MF.tokens(MF.describe(wk)), MF.tokens(MF.describe(qtr)))
    assert sim < VB.NEAR_DUP_JACCARD, (
        f"the semantic proxy scores them {sim:.2f} and would block the 90-day version")


def test_describe_excludes_the_symbol() -> None:
    assert "btcusdt" not in MF.describe(_hyp(symbol="BTCUSDT")).lower()


# ===================================================================== variation_blocker

def test_an_exact_fingerprint_repeat_is_BLOCKED_before_any_compute(tmp_path: Path) -> None:
    """#3's blocker blocks before compute, and the saving is STATISTICAL before it is
    computational: every look charges multiplicity against DSR and the stepdown, so a
    reparameterisation actively consumes the budget a genuinely new idea would have needed."""
    led = tmp_path / "v.jsonl"
    first = _hyp(horizon_days=20)
    v1 = VB.screen(first, path=led)
    assert v1.allowed
    VB.record(first, v1, hyp_id="h1", path=led)

    v2 = VB.screen(_hyp(horizon_days=21), path=led)      # same bucket, different knob
    assert not v2.allowed
    assert v2.duplicate_of == "h1" and v2.similarity == 1.0
    assert "different parameters" in v2.reason


def test_a_genuinely_new_mechanism_is_ALLOWED(tmp_path: Path) -> None:
    """The other half. A blocker that blocked everything would be a blocker."""
    led = tmp_path / "v.jsonl"
    carry = _hyp(horizon_days=20)
    VB.record(carry, VB.screen(carry, path=led), hyp_id="h1", path=led)
    other = _hyp(family="orderflow", subtype="liquidation flow imbalance",
                 edge_source="orderflow/bybit", mechanism="flow", horizon_days=1)
    assert VB.screen(other, path=led).allowed


def test_a_BLOCKED_idea_does_not_itself_become_a_blocker(tmp_path: Path) -> None:
    """Only ACCEPTED rows gate. Otherwise the first rejection of an idea would permanently exclude
    the corrected version of it, and the ledger would ratchet the funnel shut."""
    led = tmp_path / "v.jsonl"
    h = _hyp(horizon_days=20)
    VB.record(h, VB.Verdict(False, "blocked earlier", MF.fingerprint(h)), hyp_id="bad", path=led)
    assert VB.screen(_hyp(horizon_days=20), path=led).allowed


def test_a_BLOCK_is_recorded_as_fully_as_an_ALLOW(tmp_path: Path) -> None:
    """Blocked ideas are the MAP OF THE SPACE ALREADY SEARCHED -- exactly the input the breeder
    needs the day it unblocks. Dropping them discards the record of the work."""
    led = tmp_path / "v.jsonl"
    h = _hyp(horizon_days=20)
    VB.record(h, VB.screen(h, path=led), hyp_id="h1", path=led)
    row = VB.record(_hyp(horizon_days=21), VB.screen(_hyp(horizon_days=21), path=led),
                    hyp_id="h2", stage="pre-compute", generator="seat-3", path=led)
    assert row["allowed"] is False
    assert row["tokens"] and row["fingerprint"] and row["reason"]
    assert row["generator"] == "seat-3"
    assert len(led.read_text("utf-8").splitlines()) == 2


def test_the_ledger_survives_a_corrupt_line(tmp_path: Path) -> None:
    """An append-only file being written to is routinely mid-line. Aborting would take the blocker
    offline, and taking the blocker offline means every reparameterisation flows through."""
    led = tmp_path / "v.jsonl"
    led.write_text('{"allowed": true, "fingerprint": "x/y/z", "id": "ok", "tokens": []}\n'
                   '{"allowed": true, "fingerprint": \n', "utf-8")
    assert len(VB._seen(led)) == 1


def test_a_missing_ledger_screens_everything_as_novel(tmp_path: Path) -> None:
    assert VB.screen(_hyp(horizon_days=7), path=tmp_path / "absent.jsonl").allowed


def test_the_caller_may_supply_the_prior_instead_of_reading_the_ledger() -> None:
    h = _hyp(horizon_days=20)
    prior = [{"allowed": True, "fingerprint": MF.fingerprint(h), "id": "p1", "tokens": []}]
    assert not VB.screen(h, prior=prior).allowed


def test_telemetry_reports_the_HONEST_generation_yield(tmp_path: Path) -> None:
    """novel_rate is the share of produced ideas that were genuinely NEW questions rather than
    reparameterisations. Volume without it is throughput, not information."""
    led = tmp_path / "v.jsonl"
    a = _hyp(horizon_days=22)
    VB.record(a, VB.screen(a, path=led), hyp_id="h1", generator="g1", path=led)
    for i, h in enumerate([_hyp(horizon_days=23), _hyp(horizon_days=24)]):
        VB.record(h, VB.screen(h, path=led), hyp_id=f"d{i}", generator="g1", path=led)
    t = VB.telemetry(path=led)
    assert t["n"] == 3 and t["n_blocked"] == 2 and t["n_novel"] == 1
    assert t["novel_rate"] == pytest.approx(1 / 3, abs=1e-4)   # reported rounded to 4dp
    assert t["distinct_fingerprints"] == 1
    assert sum(t["blocked_by_stage"].values()) == 2
    assert t["most_attempted_fingerprints"][0][1] == 3


def test_telemetry_on_an_empty_ledger_says_so_rather_than_dividing_by_zero(
        tmp_path: Path) -> None:
    t = VB.telemetry(path=tmp_path / "nothing.jsonl")
    assert t["n"] == 0 and "no generation screened" in t["note"]


def test_the_verdict_is_serialisable() -> None:
    d = VB.screen(_hyp(horizon_days=7), prior=[]).as_dict()
    json.dumps(d)
    assert set(d) >= {"allowed", "reason", "fingerprint", "duplicate_of", "similarity"}


# ===================================================================== collapse_detector

def test_entropy_is_normalised_by_ITEM_count_not_category_count() -> None:
    """THE ARITHMETIC THAT DECIDES WHETHER COLLAPSE IS VISIBLE AT ALL. Dividing by
    log(n_categories) reports a batch of 50 ideas sharing 2 fingerprints as PERFECTLY diverse --
    both categories equally used, score 1.0. Against log(n_items) it scores ~0.18, which is the
    reading that matches what actually happened."""
    got = D._normalised_entropy([25, 25])
    assert got < 0.25, f"a 50-idea batch on 2 fingerprints scored {got:.3f} -- collapse invisible"


def test_total_collapse_prints_as_positive_zero() -> None:
    """A single-category batch produces -0.0, which reads like a bug in the report."""
    got = D._normalised_entropy([40])
    assert got == 0.0 and str(got) == "0.0"


def test_a_fully_distinct_batch_scores_near_one() -> None:
    assert D._normalised_entropy([1] * 20) == pytest.approx(1.0)


def test_entropy_of_a_single_item_is_1_rather_than_undefined() -> None:
    assert D._normalised_entropy([1]) == 1.0
    assert D._normalised_entropy([]) == 1.0


def test_a_cross_sectional_idea_is_not_scored_as_the_NARROWEST(monkeypatch) -> None:
    """A cross-sectional family RANKS a universe. Counting its single `symbol` field would score
    the broadest ideas as the narrowest -- and market_breadth is one of the three metrics whose
    drop triggers an audit."""
    xs = NS(family="funding", subtype="rank cross-section", edge_source="funding/binance",
            mechanism="rank", symbol="BTCUSDT",
            params={"cross_sectional": True, "universe_size": 40})
    assert len(D._universe_size(xs)) == 40
    single = _hyp(symbol="BTCUSDT")
    assert D._universe_size(single) == {"BTCUSDT"}


def test_an_explicit_universe_wins_over_everything() -> None:
    assert D._universe_size(NS(universe=["A", "B", "C"])) == {"A", "B", "C"}


def test_an_idea_with_no_symbol_at_all_spans_nothing() -> None:
    assert D._universe_size(NS(family="x", params={})) == set()


def test_a_collapsed_batch_measures_as_collapsed() -> None:
    """The instrument's whole job: 20 reparameterisations of one idea must not read as 20 ideas."""
    # 22..41 all land in the "months" bucket: twenty knobs, one question.
    batch = [_hyp(horizon_days=22 + i) for i in range(20)]
    d = D.measure(batch)
    assert d.n == 20 and d.n_fingerprints == 1
    assert d.mechanism_entropy == 0.0
    assert d.feature_breadth == pytest.approx(0.05)
    assert d.semantic_distinctness < 0.2


def test_a_diverse_batch_measures_as_diverse() -> None:
    batch = [
        _hyp(family="funding", subtype="carry", mechanism="carry", horizon_days=7),
        _hyp(family="orderflow", subtype="liquidation imbalance", mechanism="flow",
             edge_source="orderflow/bybit", horizon_days=1),
        _hyp(family="onchain", subtype="stablecoin netflow", mechanism="flow",
             edge_source="onchain/eth", horizon_days=30),
        _hyp(family="vol", subtype="dispersion variance premium", mechanism="vol",
             edge_source="vol/deribit", horizon_days=90),
    ]
    d = D.measure(batch)
    assert d.n_fingerprints == 4
    assert d.mechanism_entropy == pytest.approx(1.0)
    assert d.feature_breadth == pytest.approx(1.0)


def test_an_empty_batch_reports_neutral_rather_than_collapsed() -> None:
    """Zero ideas is not a collapse -- it is nothing to measure, and scoring it 0.0 would fire an
    audit every time a generator produced nothing."""
    d = D.measure([])
    assert d.n == 0 and d.mechanism_entropy == 1.0 and d.market_breadth == 0


def test_cross_generator_duplication_is_measured_only_across_seats() -> None:
    """Separate seats producing the same idea is HERDING or shared-prompt drift, not independent
    search -- a distinct failure from one seat repeating itself, and the pairs are filtered so the
    two cannot be confused."""
    batch = [_hyp(horizon_days=22 + i) for i in range(4)]     # one bucket, one idea
    same_seat = D.measure(batch, generators=["g1"] * 4)
    two_seats = D.measure(batch, generators=["g1", "g1", "g2", "g2"])
    assert same_seat.cross_generator_dup_rate == 0.0, "no cross pairs exist within one seat"
    assert two_seats.cross_generator_dup_rate > D.CROSS_DUP_TRIGGER


def test_a_generator_list_of_the_wrong_length_is_ignored_rather_than_misaligned() -> None:
    """Zipping a mismatched list would attribute ideas to the wrong seats and produce a herding
    number about nothing."""
    batch = [_hyp(horizon_days=20), _hyp(horizon_days=21)]
    assert D.measure(batch, generators=["g1"]).cross_generator_dup_rate == 0.0


# --------------------------------------------------------------- assess

def test_a_small_batch_is_UNDER_SAMPLED_and_never_flagged(tmp_path: Path) -> None:
    """Entropy over three ideas is noise, and a detector that cries wolf on small batches gets
    muted before it ever sees a real collapse."""
    out = D.assess(D.measure([_hyp(horizon_days=7)] * (D.MIN_BATCH - 1)),
                   path=tmp_path / "h.jsonl")
    assert out["verdict"] == "UNDER-SAMPLED" and out["flags"] == []


def test_cross_generator_herding_alone_triggers_an_audit(tmp_path: Path) -> None:
    batch = [_hyp(horizon_days=22 + i) for i in range(6)]
    d = D.measure(batch, generators=["g1", "g1", "g1", "g2", "g2", "g2"])
    out = D.assess(d, path=tmp_path / "h.jsonl")
    assert out["verdict"] == "DIVERSITY-AUDIT"
    assert any("cross-generator" in f for f in out["flags"])


def test_no_trailing_history_means_no_median_flags(tmp_path: Path) -> None:
    """Fewer than three prior batches cannot establish a median, and inventing one would flag the
    first three batches of every fresh deployment."""
    d = D.measure([_hyp(horizon_days=22 + i) for i in range(6)])
    assert D.assess(d, path=tmp_path / "h.jsonl")["verdict"] == "OK"


def test_a_drop_below_the_trailing_median_is_flagged(tmp_path: Path) -> None:
    hist = tmp_path / "h.jsonl"
    diverse = [
        _hyp(family="funding", subtype="carry", mechanism="carry", horizon_days=7),
        _hyp(family="orderflow", subtype="flow imbalance", mechanism="flow",
             edge_source="orderflow/x", horizon_days=1),
        _hyp(family="onchain", subtype="netflow", mechanism="flow",
             edge_source="onchain/y", horizon_days=30),
        _hyp(family="vol", subtype="variance premium", mechanism="vol",
             edge_source="vol/z", horizon_days=90),
        _hyp(family="basis", subtype="spread dislocation", mechanism="spread",
             edge_source="basis/w", horizon_days=5),
    ]
    for _ in range(4):
        D.record(D.measure(diverse), path=hist)

    collapsed = D.measure([_hyp(horizon_days=22 + i) for i in range(6)])
    out = D.assess(collapsed, path=hist)
    assert out["verdict"] == "DIVERSITY-AUDIT"
    assert any("below its trailing" in f for f in out["flags"])
    assert out["n_trailing"] == 4


def test_the_detector_is_INSTRUMENTATION_and_says_so(tmp_path: Path) -> None:
    """Generation is never blocked by this result. Convergence in a genuinely dominant regime is a
    legitimate answer, and a gate here would delete it before anyone asked."""
    out = D.assess(D.measure([_hyp(horizon_days=22 + i) for i in range(6)]),
                   path=tmp_path / "h.jsonl")
    assert "never a gate" in out["note"]


def test_record_is_append_only_because_the_median_depends_on_it(tmp_path: Path) -> None:
    hist = tmp_path / "h.jsonl"
    d = D.measure([_hyp(horizon_days=22 + i) for i in range(6)])
    D.record(d, path=hist, batch_id="b1")
    D.record(d, path=hist, batch_id="b2")
    rows = [json.loads(x) for x in hist.read_text("utf-8").splitlines()]
    assert [r["batch_id"] for r in rows] == ["b1", "b2"]
    assert all("at" in r for r in rows)


def test_history_survives_a_corrupt_line(tmp_path: Path) -> None:
    hist = tmp_path / "h.jsonl"
    hist.write_text('{"batch": {"mechanism_entropy": 0.5}}\n{"batch": \n', "utf-8")
    assert len(D._history(hist)) == 1


def test_the_batch_record_is_serialisable() -> None:
    d = D.measure([_hyp(horizon_days=22 + i) for i in range(6)])
    json.dumps(d.as_dict())
    assert isinstance(d.as_dict()["top_fingerprints"][0], list), "tuples are not JSON"
