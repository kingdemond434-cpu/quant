"""Regression tests for the primary-market creation-flow collector and its Stage-A screen.

WHAT THESE PIN, AND WHY EACH ONE EXISTS. The mechanism class under test is the census's #2 ranked
untested one, and the reason it has never been screened is not missing data -- the data is free and
keyless -- it is that ETF CREATION DATA IS STAMPED BY TRADE DATE AND PUBLISHED A BUSINESS DAY
LATER. A screen that joins the stamp to a same-day price looks perfectly ordinary and is trading a
number that did not exist yet. So the tests are about the four things that decide whether this
screen is worth anything:

  * the parser refuses to read a not-yet-published placeholder as a zero (the source renders it
    with a numeric Total of 0.0, and so does every US market holiday);
  * the alignment is strictly causal -- no screened row uses information published after its own
    decision instant, and the forward window is measured in calendar days from that instant rather
    than in rows;
  * a flow that genuinely LEADS is still detected end to end through the audited harness, and one
    that merely COINCIDES is killed as an artifact rather than published;
  * an unreachable source produces a status record carrying its reason, never a fabricated row.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
import scripts.collect_primary_market_flow as C
import scripts.screen_primary_market_flow as S

from libs.research.primary_market_flow import (
    Alignment,
    align_to_publication,
    as_of_series,
    horizon_targets,
    net_mint,
    parse_farside_table,
    parse_llama_chart,
    publication_day_map,
    scaled_flow,
    trailing_z,
)

FLOAT_UNITS = 19_000_000.0
P0 = 50_000.0


# --------------------------------------------------------------------------- synthetic fixtures

def _series(n: int, *, lead: int, phi: float = 0.0, g: float = 0.12, rho: float = 0.7,
            c: float = 0.0, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    """(observed flow pressure, daily return) where the answer is known BY CONSTRUCTION.

    `lead > 0` -- an AR(1) latent flow drives the return `lead` days later. TWO is the number the
                  causal alignment must recover: flow for trade date t is published on t+1 and the
                  first return it can be traded against is the one over t+2. ONE is the
                  publication-lag trap -- only the naive build can see it.
    `lead = 0`  -- the observed flow is PURE CONCURRENCY with the same day's return (c) while
                  returns are autocorrelated (phi). That combination fakes a forward IC for the
                  naive build: contaminated flow at t correlates with r[t], and r[t] correlates
                  with r[t+1]. It is the coinbase/turkey/kimchi shape, generated deliberately.

    `g` is deliberately small. A large one drives |IC| past the harness's own credibility ceiling
    and the fixture would then test the lookahead rail rather than the alignment.
    """
    rng = np.random.default_rng(seed)
    s = np.zeros(n)
    u = rng.normal(size=n)
    for k in range(1, n):
        s[k] = rho * s[k - 1] + u[k]
    s /= s.std()
    eps = rng.normal(size=n)
    r = np.zeros(n)
    for k in range(1, n):
        drive = g * s[k - lead] if lead > 0 and k >= lead else 0.0
        r[k] = phi * r[k - 1] + drive + eps[k]
    r = r / r.std() * 0.02
    rz = r / r.std()
    x = (s if lead > 0 else np.zeros(n)) + c * rz + 0.6 * rng.normal(size=n)
    return x, r


def _ledger_records(pressure: np.ndarray, ret: np.ndarray, *,
                    start: date = date(2012, 1, 2)) -> list[dict[str, object]]:
    """A synthetic collector ledger built to the DECLARED alignment.

    Trade dates are consecutive calendar days, so `publication_day_map` maps t -> t+1 and the whole
    causal chain (trade date -> publication day -> forward window) is checkable by hand.

    The ETF row for trade date t is written as the dollar flow that reproduces `pressure[t]` given
    that day's float and close, so the construction under test is the identity on the fixture and
    any correlation the screen reports is the alignment's doing rather than the scaling's.
    """
    n = len(pressure)
    days = [start + timedelta(days=i) for i in range(n)]
    px = P0 * np.cumprod(1.0 + np.asarray(ret, dtype="float64"))
    rng = np.random.default_rng(3)
    supply = 1e11 * np.cumprod(1.0 + rng.normal(0.0, 0.002, n))
    recs: list[dict[str, object]] = []
    for i, d in enumerate(days):
        iso = d.isoformat()
        recs.append({"kind": "observation", "series": "price_btc", "stamp": iso,
                     "value": float(px[i])})
        recs.append({"kind": "observation", "series": "float_btc", "stamp": iso,
                     "value": FLOAT_UNITS})
        recs.append({"kind": "observation", "series": "etf_flow_btc", "stamp": iso,
                     "value": float(pressure[i]) * FLOAT_UNITS * float(px[i])})
        recs.append({"kind": "observation", "series": "stablecoin_usdt", "stamp": iso,
                     "value": float(supply[i])})
        recs.append({"kind": "observation", "series": "stablecoin_usdc", "stamp": iso,
                     "value": float(supply[i]) * 0.4})
    return recs


def _write_ledger(path, recs) -> object:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    return path


def _run(tmp_path, pressure, ret):
    ledger = _write_ledger(tmp_path / "ledger.jsonl", _ledger_records(pressure, ret))
    out = tmp_path / "screen.json"
    assert S.main(["--ledger", str(ledger), "--out", str(out)]) == 0
    return json.loads(out.read_text("utf-8"))


def _pick(doc, construction: str, form: str, horizon: int) -> dict[str, object]:
    hits = [r for r in doc["rows"] if r["construction"] == construction
            and r["form"] == form and r["horizon_days"] == horizon]
    assert len(hits) == 1, f"expected exactly one {construction}/{form}/h{horizon}"
    return hits[0]


# ------------------------------------------------------ the parser refuses to fabricate a zero

_FARSIDE = """
<table>
<tr><td>Date</td><td>IBIT</td><td>FBTC</td><td>GBTC</td><td>Total</td></tr>
<tr><td>11 Jan 2024</td><td>111.7</td><td>227.0</td><td>(95.1)</td><td>243.6</td></tr>
<tr><td>12 Jan 2024</td><td>0.0</td><td>0.0</td><td>0.0</td><td>0.0</td></tr>
<tr><td>15 Jan 2024</td><td>-</td><td>-</td><td>-</td><td>0.0</td></tr>
<tr><td>16 Jan 2024</td><td>1,234.5</td><td>10.0</td><td>-</td><td>1244.5</td></tr>
<tr><td>17 Jan 2024</td><td>-</td><td>-</td><td>-</td><td>0.0</td></tr>
<tr><td>Total</td><td>1,346.2</td><td>237.0</td><td>(95.1)</td><td>1488.1</td></tr>
</table>
"""


def test_placeholder_rows_are_never_read_as_zero_flow():
    """THE LOAD-BEARING PARSE CLAIM. A holiday and a not-yet-published day both render as a row of
    em-dashes whose Total column still says 0.0. Reading that Total writes a fabricated zero into
    the middle of the series -- and on the CURRENT day it writes a number that is not knowable at
    all. Only rows where an ISSUER actually reported survive."""
    t = parse_farside_table(_FARSIDE)
    got = t.by_date()

    assert sorted(got) == [date(2024, 1, 11), date(2024, 1, 12), date(2024, 1, 16)]
    assert date(2024, 1, 15) not in got, "a US market holiday was read as a zero-flow day"
    assert date(2024, 1, 17) not in got, "an unpublished day was read as a zero-flow day"
    # A genuine zero -- every issuer reported and every issuer reported 0.0 -- IS kept. The
    # distinction between "nobody reported" and "everybody reported nothing" is the whole rule.
    assert got[date(2024, 1, 12)] == pytest.approx(0.0)
    assert t.dropped["no_issuer_reported"] == 2


def test_accounting_parentheses_are_negative_and_thousands_separators_survive():
    t = parse_farside_table(_FARSIDE).by_date()
    assert t[date(2024, 1, 11)] == pytest.approx(243.6)
    assert t[date(2024, 1, 16)] == pytest.approx(1244.5)
    row = next(r for r in parse_farside_table(_FARSIDE).rows if r.trade_date == date(2024, 1, 11))
    assert row.per_issuer["GBTC"] == pytest.approx(-95.1), "(95.1) must be a redemption"
    assert row.n_issuers_reported == 3


def test_total_column_disagreeing_with_the_issuer_sum_is_counted_not_silently_used():
    bad = _FARSIDE.replace("<td>243.6</td>", "<td>999.9</td>")
    assert parse_farside_table(bad).total_mismatch == 1


def test_llama_chart_drops_rows_with_no_usable_circulating_figure():
    rows = parse_llama_chart([
        {"date": "1704067200", "totalCirculating": {"peggedUSD": 1.0e11},
         "totalUnreleased": {"peggedUSD": 5.0e9}},
        {"date": "1704153600", "totalCirculating": {"peggedUSD": 0.0}},
        {"date": "1704240000"},
        {"date": "not-a-timestamp", "totalCirculating": {"peggedUSD": 1.0e11}},
    ])
    assert [r.day for r in rows] == [date(2024, 1, 1)]
    assert rows[0].unreleased_usd == pytest.approx(5.0e9)


# ------------------------------------------------------------------------------ alignment is law

def test_publication_day_is_the_next_trade_date_and_the_last_row_is_dropped():
    """The publication calendar is DERIVED FROM THE DATA. A Friday's flow is published on Monday
    because Monday is the next trade date the table contains -- no holiday table to drift, no
    business-day rule to get wrong. The newest row has no observed successor, so it is dropped
    rather than assigned a guessed publication day."""
    trade = [date(2024, 1, 11), date(2024, 1, 12), date(2024, 1, 16), date(2024, 1, 17)]
    m = publication_day_map(trade)

    assert m[date(2024, 1, 12)] == date(2024, 1, 16), "Friday publishes on the next OPEN day"
    assert m[date(2024, 1, 11)] == date(2024, 1, 12)
    assert date(2024, 1, 17) not in m, "the newest trade date must not get a publication day"
    assert all(stamp < pub for stamp, pub in m.items()), "a row may never publish before it exists"


def test_causal_placement_never_places_a_value_on_or_before_its_own_stamp():
    """THE CAUSALITY INVARIANT, stated as the property the whole screen rests on: every screened
    row's signal carries a stamp STRICTLY EARLIER than the decision instant it is used at."""
    trade = [date(2024, 3, d) for d in (1, 4, 5, 6, 7)]
    m = publication_day_map(trade)
    placed = align_to_publication({d: float(i) for i, d in enumerate(trade)}, m)
    inverse = {pub: stamp for stamp, pub in m.items()}

    assert set(placed) == set(m.values())
    for decision_day in placed:
        assert inverse[decision_day] < decision_day


def test_the_two_forms_differ_only_in_alignment_never_in_which_rows_they_carry():
    """The control is a leak MEASUREMENT, and it only measures the leak if the alignment is the
    only difference. Letting the control keep the newest stamp -- which the causal build must drop
    -- would make the two forms differ by an observation as well."""
    trade = [date(2024, 3, d) for d in (1, 4, 5, 6, 7)]
    m = publication_day_map(trade)
    stamped = {d: float(i) for i, d in enumerate(trade)}

    causal = S.placements(stamped, m, "causal")
    control = S.placements(stamped, m, "lookahead_control")

    assert sorted(causal.values()) == sorted(control.values())
    assert set(control) == set(m)                       # keyed by the stamp itself
    assert set(causal) == set(m.values())               # keyed by the publication day
    assert set(causal) != set(control)


def test_signal_at_a_decision_day_cannot_move_when_a_later_trade_date_changes():
    """PERTURB THE FUTURE AND THE PAST MUST NOT MOVE. This is the test that would catch a
    full-sample z-score, a forward-filled denominator, or a publication map that leaked -- all of
    which look like preprocessing rather than like a decision."""
    pressure, ret = _series(400, lead=2)
    base = _ledger_records(pressure, ret)
    poked = [dict(r) for r in base]
    hit = [r for r in poked if r["series"] == "etf_flow_btc"][300]
    hit["value"] = float(hit["value"]) * 25.0 + 1e12

    def _causal(recs):
        series: dict[str, dict[date, float]] = {}
        for r in recs:
            series.setdefault(str(r["series"]), {})[date.fromisoformat(str(r["stamp"]))] = float(
                r["value"])
        sig = S.etf_signals(series)["etf_creation_pressure"]
        return S.placements(sig, publication_day_map(series["etf_flow_btc"]), "causal")

    before, after = _causal(base), _causal(poked)
    poked_stamp = date.fromisoformat(str(hit["stamp"]))
    earlier = [d for d in sorted(before) if d <= poked_stamp]
    later = [d for d in sorted(before) if d > poked_stamp]

    assert len(earlier) > 100 and len(later) > 50, "the fixture must straddle the poke"
    assert all(before[d] == after[d] for d in earlier), \
        "a decision day moved because of a trade date that had not happened yet"
    assert any(before[d] != after[d] for d in later), \
        "the poke must matter from its own publication day onward, or the test proves nothing"


def test_trailing_z_reads_strictly_prior_observations():
    x = np.arange(200, dtype="float64") + np.sin(np.arange(200))
    base = trailing_z(x, win=20)
    poked = x.copy()
    poked[150] += 500.0
    after = trailing_z(poked, win=20)

    assert np.array_equal(base[:150], after[:150], equal_nan=True)
    assert not np.array_equal(base[150:], after[150:], equal_nan=True)
    assert np.isnan(base[:20]).all(), "warmup must be NaN, never a manufactured 0.0"


def test_target_window_is_calendar_days_from_the_decision_not_one_row():
    """THE WEEKEND TRAP. Publication days are US business days but the asset trades seven days a
    week, so a row-spaced target quietly hands the Monday rows a three-day return and calls it
    h = 1. The window must open at the PREVIOUS decision instant and close exactly `horizon`
    calendar days later."""
    closes = {date(2024, 3, d): 100.0 + d for d in range(1, 12)}
    decisions = [date(2024, 3, 1), date(2024, 3, 4), date(2024, 3, 5)]   # Fri, Mon, Tue

    t1 = horizon_targets(decisions, closes, horizon=1)
    assert np.isnan(t1[0]), "the first row has no previous decision instant"
    # Row 1's target opens at Friday and closes ONE calendar day later (Saturday), not at Monday.
    assert t1[1] == pytest.approx(closes[date(2024, 3, 2)] / closes[date(2024, 3, 1)] - 1.0)
    assert t1[2] == pytest.approx(closes[date(2024, 3, 5)] / closes[date(2024, 3, 4)] - 1.0)

    t5 = horizon_targets(decisions, closes, horizon=5)
    assert t5[1] == pytest.approx(closes[date(2024, 3, 6)] / closes[date(2024, 3, 1)] - 1.0)


def test_target_is_nan_rather_than_carried_when_a_close_is_missing():
    closes = {date(2024, 3, 1): 100.0, date(2024, 3, 3): 110.0}
    got = horizon_targets([date(2024, 3, 1), date(2024, 3, 2)], closes, horizon=1)
    assert np.isnan(got[1]), "a missing close must not be filled from a neighbour"


def test_as_of_never_reads_forward_and_never_carries_a_dead_feed_forever():
    values = {date(2024, 1, 1): 1.0, date(2024, 1, 5): 2.0}
    got = as_of_series(values, [date(2023, 12, 31), date(2024, 1, 4), date(2024, 1, 5),
                                date(2024, 1, 20)], max_staleness_days=7)
    assert np.isnan(got[0]), "nothing was published yet"
    assert got[1] == pytest.approx(1.0), "the 5 Jan value must not be visible on 4 Jan"
    assert got[2] == pytest.approx(2.0)
    assert np.isnan(got[3]), "a value 15 days stale must not be presented as current"


def test_alignment_is_echoed_and_names_its_own_hazard():
    d = Alignment(form="causal", horizon=5, stamp_kind="etf_trade_date",
                  publication_rule="next trade date").as_dict()
    assert d["is_lookahead_control"] is False
    assert d["horizon_calendar_days"] == 5
    assert d["placeholder_rows_dropped"] and d["most_recent_stamp_dropped"]
    assert Alignment(form="lookahead_control", horizon=1, stamp_kind="x",
                     publication_rule="y").is_lookahead_control is True


@pytest.mark.parametrize("bad", [{"form": "whatever", "horizon": 1},
                                 {"form": "causal", "horizon": 0}])
def test_alignment_rejects_impossible_rules(bad):
    with pytest.raises(ValueError):
        Alignment(stamp_kind="x", publication_rule="y", **bad)


def test_scaling_primitives_reject_mismatched_inputs_and_never_invent_a_denominator():
    with pytest.raises(ValueError, match="length mismatch"):
        scaled_flow(np.zeros(3), np.zeros(4), np.zeros(3))
    got = scaled_flow(np.array([1.0, 1.0]), np.array([0.0, 2.0]), np.array([1.0, 1.0]))
    assert np.isnan(got[0]) and got[1] == pytest.approx(0.5)
    mint = net_mint(np.array([100.0, 110.0, 0.0, 50.0]))
    assert np.isnan(mint[0]) and mint[1] == pytest.approx(0.10) and np.isnan(mint[3])


# ------------------------------------------------------------- the two verdicts that matter

def test_every_preregistered_cell_produces_a_row(tmp_path):
    """Clause 3: a construction that silently vanishes is indistinguishable from one never tried."""
    pressure, ret = _series(400, lead=2)
    doc = _run(tmp_path, pressure, ret)
    got = {(r["construction"], r["form"], r["horizon_days"]) for r in doc["rows"]}
    assert got == {(c, f, h) for c in S.CONSTRUCTIONS for f in S.FORMS for h in S.HORIZONS_DAYS}
    assert doc["hypotheses"] == S.PREREGISTERED_FAMILY == 30


def test_every_construction_declares_the_grid_and_publication_rule_it_was_aligned_under():
    """The alignment table and the construction set must not drift apart. A construction with no
    declared grid would either crash the run or -- worse, if someone later made the lookup lenient
    -- be screened under a rule the artifact does not name, which is the definition of unstated
    alignment."""
    assert set(S._GRID) == set(S.CONSTRUCTIONS)
    for cname, (grid, stamp, rule) in S._GRID.items():
        assert grid and stamp and rule, cname
        assert S.pre_registration()["grids"][cname]["publication_rule"] == rule


def test_a_leading_flow_is_detected_end_to_end(tmp_path):
    """THROUGH THE REAL LEDGER, THE REAL ALIGNMENT AND THE AUDITED HARNESS: a flow that genuinely
    leads by the two days the publication lag imposes must survive, be POWERED, and clear the
    family-wise bar. Without this the screen could be trivially safe by finding nothing ever."""
    pressure, ret = _series(5200, lead=2)
    doc = _run(tmp_path, pressure, ret)
    causal = _pick(doc, "etf_creation_pressure", "causal", 1)

    assert causal["verdict"] == "SCREEN-INTERESTING"
    assert causal["powered"] is True
    assert abs(float(causal["ic"])) > S.IC_MIN
    assert causal["clears_family_wise"] is True
    assert causal["decontam_passed"] is True

    assert any(s["construction"] == "etf_creation_pressure" and s["horizon_days"] == 1
               for s in doc["survivors"])
    # A survivor is not one of this run's recorded NEGATIVES, so the power headline -- a statement
    # about what the nulls know -- must not count it as an underpowered one.
    assert (doc["power_counts_at_family_charge"]["negatives"]
            == doc["scored"] - len(doc["survivors"]))
    assert doc["powered_cells_unadjusted"] > 0


def test_a_merely_coincident_flow_is_killed_as_an_artifact(tmp_path):
    """THE FAILURE MODE THIS SCREEN EXISTS TO SURVIVE. The flow carries NO forward information --
    it is pure concurrency with the day's own return -- but returns are autocorrelated, so the
    naive trade-date build shows a healthy forward IC. It must die on the angle-20 gate, the
    causal build must find nothing, and NOTHING may survive.

    `phi = 0.12` is bounded on BOTH sides and neither bound is a tuning knob. It must be large
    enough that the naive build shows a fake forward IC -- otherwise the fixture tests nothing, and
    the first assertion below fails loudly if it drifts under. It must also be small enough that
    the RETURNS do not themselves carry family-significant two-day-forward information: at
    phi = 0.30 they do (phi-squared = 0.09), and `etf_creation_absorption` -- which subtracts the
    price leg by construction -- then legitimately finds that price autocorrelation and survives.
    That would be the screen reporting a real relationship in the fixture, not a leak, but it would
    make this test's claim ("nothing may survive") false for a reason that has nothing to do with
    the alignment under test.
    """
    pressure, ret = _series(5200, lead=0, phi=0.12, c=0.9)
    doc = _run(tmp_path, pressure, ret)
    control = _pick(doc, "etf_creation_pressure", "lookahead_control", 1)
    causal = _pick(doc, "etf_creation_pressure", "causal", 1)

    assert abs(float(control["ic"])) > S.IC_MIN, \
        "fixture must fake a forward IC for the naive build, or it tests nothing"
    assert control["verdict"] == "TIMING-ARTIFACT"
    assert abs(float(control["same_period_corr"])) > S.CONTAM_MAX
    assert control["decontam_passed"] is False
    assert abs(float(causal["ic"])) < abs(float(control["ic"]))

    assert doc["survivors"] == []
    killed = [g for g in doc["graveyard"] if g["construction"] == "etf_creation_pressure"
              and g["horizon_days"] == 1 and g["verdict"] == "TIMING-ARTIFACT"]
    assert killed, "a resolved artifact is graveyard-grade knowledge and must be recorded"
    assert killed[0]["detection_floor_ic_unadjusted"] is not None
    assert killed[0]["detection_floor_ic_family_wise"] is not None
    assert "de-contamination" in killed[0]["reason"]
    assert "RESOLVED" in killed[0]["resolved_by"]

    # The CAUSAL twin is the other half of the finding: it looked, on a sample that could have
    # resolved an effect at ic_min, and found nothing. That is graveyard-grade in its own right,
    # and it must arrive with its floor rather than as a bare zero.
    powered_null = [g for g in doc["graveyard"] if g["construction"] == "etf_creation_pressure"
                    and g["horizon_days"] == 1 and g["verdict"] == "SCREEN-WEAK"]
    assert powered_null and powered_null[0]["form"] == "causal"
    assert "powered at ic_min" in powered_null[0]["resolved_by"]

    diag = next(d for d in doc["alignment_diagnostics"]
                if d["construction"] == "etf_creation_pressure" and d["horizon_days"] == 1)
    assert diag["control_failed_decontam"] is True
    assert diag["causal_failed_decontam"] is False
    assert diag["contamination_jump"] > 0.0


def test_a_one_day_lead_is_visible_only_to_the_look_ahead_control(tmp_path):
    """THE PUBLICATION-LAG TRAP ITSELF. A flow that leads by exactly ONE day is tradeable only if
    the trade-date stamp were knowable that day -- which it is not. The naive build sees it; the
    causal build must not, and must not be talked into it.

    `rho = 0` -- a WHITE-NOISE latent flow -- is load-bearing here and not a tuning knob. With an
    autocorrelated flow a "one-day lead" is genuinely also a two-day lead, because today's flow
    predicts tomorrow's flow; the causal build would then find it and be RIGHT to. Only an
    uncorrelated flow isolates the pure publication-lag trap.
    """
    pressure, ret = _series(5200, lead=1, rho=0.0)
    doc = _run(tmp_path, pressure, ret)
    control = _pick(doc, "etf_creation_pressure", "lookahead_control", 1)
    causal = _pick(doc, "etf_creation_pressure", "causal", 1)

    assert abs(float(control["ic"])) > abs(float(causal["ic"])), \
        "the naive build must be the one that sees a one-day lead"
    assert not any(s["construction"] == "etf_creation_pressure" and s["horizon_days"] == 1
                   for s in doc["survivors"])


def test_the_look_ahead_control_can_never_become_a_survivor():
    """Structural, not empirical: a control row carrying every credential a survivor needs must
    still be refused, because the form itself is disqualifying."""
    rows = [{"construction": "etf_creation_pressure", "horizon_days": 1,
             "form": "lookahead_control", "verdict": "SCREEN-INTERESTING", "ic": 0.42,
             "powered": True, "clears_family_wise": True, "min_detectable_ic": 0.02,
             "n_eff": 9000.0, "same_period_corr": 0.01}]
    survivors, _ = S.classify(rows)
    assert survivors == []


def test_underpowered_cells_are_never_graveyarded():
    """'Could not tell' must never be filed as 'it is dead' -- the graveyard is permanent."""
    rows = [{"construction": "etf_creation_pressure", "horizon_days": 1, "form": "causal",
             "verdict": "SCREEN-UNDERPOWERED", "ic": 0.001, "powered": False,
             "clears_family_wise": False, "min_detectable_ic": 0.9, "n_eff": 5.0}]
    survivors, graveyard = S.classify(rows)
    assert survivors == [] and graveyard == []


def test_an_unresolved_contamination_is_not_graveyarded_but_a_resolved_one_is():
    """A kill is filed only when ITS OWN TRIGGER is resolved. |same| = 0.21 against a 0.20 bar on a
    sample whose correlation band is 0.08 is a coin flip, not a finding; 0.45 is a finding. Both
    carry the identical verdict from the harness, so the distinction has to be made here."""
    common = {"construction": "etf_creation_pressure", "horizon_days": 1, "form": "causal",
              "verdict": "TIMING-ARTIFACT", "ic": 0.10, "powered": False,
              "min_detectable_ic": 0.08, "n_eff": 600.0}
    _, weak = S.classify([{**common, "same_period_corr": 0.21}])
    _, strong = S.classify([{**common, "same_period_corr": 0.45}])
    assert weak == []
    assert [g["verdict"] for g in strong] == ["TIMING-ARTIFACT"]
    assert "contamination RESOLVED" in strong[0]["resolved_by"]


def test_a_control_only_winner_is_recorded_as_a_publication_lag_artifact():
    """The pre-registered alignment null, confirmed: the naive build scored and the
    publication-aligned build did not, so the apparent forecast used a number that had not been
    published. The diagnosis must outrank the generic SCREEN-WEAK label -- 'why' is the finding."""
    common = {"construction": "etf_creation_pressure", "horizon_days": 1,
              "min_detectable_ic": 0.02, "n_eff": 9000.0}
    rows = [
        {**common, "form": "lookahead_control", "verdict": "SCREEN-INTERESTING", "ic": 0.21,
         "powered": True, "clears_family_wise": True},
        {**common, "form": "causal", "verdict": "SCREEN-WEAK", "ic": 0.004,
         "powered": True, "clears_family_wise": False},
    ]
    survivors, graveyard = S.classify(rows)
    assert survivors == []
    assert [g["verdict"] for g in graveyard] == ["PUBLICATION-LAG-ARTIFACT"]
    assert graveyard[0]["control_ic"] == 0.21
    assert graveyard[0]["detection_floor_ic_unadjusted"] == 0.02


def test_multiplicity_charge_never_shrinks_below_the_preregistration():
    """A run that reads less data than planned cannot buy significance by shrinking its family."""
    rows = [{"ic": 0.05, "n_eff": 1000.0, "horizon_days": 1} for _ in range(3)]
    S._significance(rows, n_family=max(S.PREREGISTERED_FAMILY, len(rows)))
    assert rows[0]["family_size"] == S.PREREGISTERED_FAMILY == 30
    assert rows[0]["family_z_critical"] > 1.96
    # The null is reported as a SCHEDULE, not a shrug: how many rows it would take to mean
    # anything, on BOTH bars. Refuting is always cheaper than discovering, and the pair says so.
    assert rows[0]["rows_needed_for_harness_powered"] > 1000
    assert (rows[0]["rows_needed_for_family_wise_at_ic_min"]
            > rows[0]["rows_needed_for_harness_powered"])


def test_power_is_reported_beside_every_verdict(tmp_path):
    """A negative without its detection floor is not a finding. Every scored row carries both
    floors -- the harness's unadjusted one and the family-wise one -- plus a Type-II label."""
    pressure, ret = _series(400, lead=0)
    doc = _run(tmp_path, pressure, ret)
    scored = [r for r in doc["rows"] if isinstance(r.get("ic"), (int, float))]
    assert scored
    for r in scored:
        assert r["min_detectable_ic"] > 0
        assert r["type2"]["min_detectable_effect"] is not None
        assert r["type2_label"]
        assert r["rows_needed_for_harness_powered"] > 0
        assert r["rows_needed_for_family_wise_at_ic_min"] > 0
    assert doc["power_headline_at_family_charge"]
    assert doc["best_detection_floor_causal"] is not None
    # An underpowered null is only useful if it comes with the arithmetic for when it stops being
    # one. Refuting must always be cheaper than discovering, or the two bars have been swapped.
    res = doc["resolvability"]
    assert res["rows_available"] > 0
    assert res["rows_needed_to_find_at_ic_min"] > res["rows_needed_to_refute_at_ic_min"]
    assert "NOT A REFUTATION" in res["reading"]


# --------------------------------------------------------------------- the refusal to fabricate

def test_absent_ledger_yields_a_status_artifact_and_never_a_row(tmp_path):
    out = tmp_path / "artifact.json"
    assert S.main(["--ledger", str(tmp_path / "nope.jsonl"), "--out", str(out)]) == 0

    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "NOT-READABLE-HERE"
    assert doc["rows"] == [] and doc["survivors"] == [] and doc["graveyard"] == []
    assert "no synthetic flow is generated" in doc["refusal"]
    # The pre-registration travels with the honest empty result, so the record shows WHAT would
    # have been tested rather than only that nothing was.
    assert doc["pre_registration"]["family_preregistered"] == S.PREREGISTERED_FAMILY
    assert doc["pre_registration"]["alpha"] == 0.05
    assert doc["pre_registration"]["alignment"]["hazard"]


def test_a_ledger_missing_a_required_series_names_it_rather_than_substituting(tmp_path):
    """A construction built on a stand-in denominator is a DIFFERENT construction wearing a
    pre-registered name. The missing input is named and the screen declines to run."""
    pressure, ret = _series(120, lead=2)
    recs = [r for r in _ledger_records(pressure, ret) if r["series"] != "float_btc"]
    ledger = _write_ledger(tmp_path / "ledger.jsonl", recs)
    out = tmp_path / "artifact.json"

    assert S.main(["--ledger", str(ledger), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "INSUFFICIENT-SERIES"
    assert any("float_btc" in m for m in doc["missing"])
    assert doc["rows"] == []


def test_a_construction_with_no_inputs_is_reported_not_buildable_never_silently_dropped(tmp_path):
    """A missing input must be visible as a hole. A cell that simply disappears looks exactly like
    a cell that was never pre-registered."""
    pressure, ret = _series(120, lead=2)
    recs = _ledger_records(pressure, ret)
    for r in recs:
        if r["series"] == "stablecoin_usdc":
            r["stamp"] = date(1999, 1, 1).isoformat()      # one stamp, so net_mint has no pair
    ledger = _write_ledger(tmp_path / "ledger.jsonl", recs)
    out = tmp_path / "artifact.json"

    assert S.main(["--ledger", str(ledger), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    cells = [r for r in doc["rows"] if r["construction"] == "stablecoin_net_mint_usdc"]
    assert len(cells) == len(S.FORMS) * len(S.HORIZONS_DAYS)
    assert all(c["verdict"] == "NOT-BUILDABLE" for c in cells)
    assert all(c["type2"]["label"] for c in cells)


def test_an_unreachable_source_is_recorded_with_its_reason_and_writes_no_rows(tmp_path,
                                                                             monkeypatch):
    """THE COLLECTOR'S CONTRACT. A source this container cannot reach must produce a STATUS with
    the exception's own text -- never a silent skip, and above all never a zero row that a screen
    would later read as an observation."""
    def _boom(_budget):
        raise TimeoutError("blocked by the egress proxy")

    monkeypatch.setattr(C, "SOURCES", (
        ("etf_btc_farside", "the mechanism leg", _boom),
        ("price_btc_coinbase", "the target leg",
         lambda b: ([{"series": "price_btc", "stamp": "2024-01-11", "value": 46000.0}], {})),
    ))
    out = tmp_path / "ledger.jsonl"
    assert C.main(["--out", str(out), "--budget-s", "30"]) == 0

    recs = [json.loads(x) for x in out.read_text("utf-8").splitlines() if x.strip()]
    run = next(r for r in recs if r["kind"] == "run")
    failed = next(s for s in run["sources"] if s["source"] == "etf_btc_farside")

    assert failed["status"] == "FAILED"
    assert "TimeoutError" in failed["reason"] and "egress proxy" in failed["reason"]
    assert "never silently skipped" in failed["policy"]
    assert not [r for r in recs if r.get("series") == "etf_flow_btc"], \
        "a failed source wrote rows -- the one thing a collector must never do"
    assert [r["series"] for r in recs if r["kind"] == "observation"] == ["price_btc"]


def test_the_ledger_is_append_only_and_idempotent_across_runs(tmp_path, monkeypatch):
    """Re-running must append a run record and only observations never seen before. A collector
    that re-appends its whole history every night turns an audit trail into noise."""
    rows = [{"series": "price_btc", "stamp": "2024-01-11", "value": 46000.0},
            {"series": "price_btc", "stamp": "2024-01-12", "value": 46500.0}]
    monkeypatch.setattr(C, "SOURCES", (
        ("price_btc_coinbase", "target leg", lambda b: (rows, {})),))
    out = tmp_path / "ledger.jsonl"

    assert C.main(["--out", str(out), "--budget-s", "30"]) == 0
    first = out.read_text("utf-8").splitlines()
    assert C.main(["--out", str(out), "--budget-s", "30"]) == 0
    second = out.read_text("utf-8").splitlines()

    assert second[:len(first)] == first, "the ledger is append-only; earlier lines must not move"
    obs = [json.loads(x) for x in second if json.loads(x)["kind"] == "observation"]
    assert len(obs) == 2, "an already-seen stamp must not be appended again"
    runs = [json.loads(x) for x in second if json.loads(x)["kind"] == "run"]
    assert len(runs) == 2
    assert runs[0]["bootstrap"] is True and runs[1]["bootstrap"] is False
    # Bootstrap rows are marked, because their first_seen is when the ledger started -- NOT
    # evidence about when the source published them.
    assert all(o["backfilled"] is True for o in obs)


def test_budget_exhaustion_records_the_untried_sources_rather_than_dropping_them(tmp_path,
                                                                                monkeypatch):
    monkeypatch.setattr(C, "SOURCES", (
        ("a", "first", lambda b: ([{"series": "price_btc", "stamp": "2024-01-11",
                                    "value": 1.0}], {})),
        ("b", "second", lambda b: ([{"series": "price_btc", "stamp": "2024-01-12",
                                     "value": 2.0}], {})),
    ))
    out = tmp_path / "ledger.jsonl"
    assert C.main(["--out", str(out), "--budget-s", "0"]) == 0

    run = next(json.loads(x) for x in out.read_text("utf-8").splitlines()
               if json.loads(x)["kind"] == "run")
    assert [s["status"] for s in run["sources"]] == ["skipped_budget", "skipped_budget"]
    assert all("NOT attempted" in s["reason"] for s in run["sources"])


def test_the_screen_reads_the_collector_ledger_without_a_translation_layer(tmp_path, monkeypatch):
    """END TO END ACROSS THE TWO SCRIPTS. The collector's output format is the screen's input
    format; a mismatch here is the class of bug that leaves an organ reading a file nothing has
    ever written."""
    pressure, ret = _series(200, lead=2)
    payload: dict[str, list[dict[str, object]]] = {}
    for rec in _ledger_records(pressure, ret):
        payload.setdefault(str(rec["series"]), []).append(
            {"series": rec["series"], "stamp": rec["stamp"], "value": rec["value"]})
    def _static(rows):
        """Bind `rows` at definition time -- a closure over the loop variable would hand every
        source the LAST series, which is the bug this indirection exists to prevent."""
        return lambda _budget: (rows, {})

    monkeypatch.setattr(C, "SOURCES", tuple(
        (name, "synthetic", _static(rs)) for name, rs in sorted(payload.items())))

    ledger = tmp_path / "ledger.jsonl"
    assert C.main(["--out", str(ledger), "--budget-s", "60"]) == 0
    out = tmp_path / "screen.json"
    assert S.main(["--ledger", str(ledger), "--out", str(out)]) == 0

    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "SCREENED"
    assert doc["ledger"]["observation_rows"] == len(_ledger_records(pressure, ret))
    assert doc["ledger"]["run_rows"] == 1
    assert set(doc["ledger"]["series_seen"]) == set(payload)


def test_a_torn_ledger_line_is_counted_and_preserved_never_silently_dropped(tmp_path):
    """A crash mid-append can leave half a line. It must be COUNTED -- so a reader knows the
    ledger has a hole -- and the surrounding rows must still screen. Rewriting the file to tidy it
    would destroy the only record that the crash happened."""
    pressure, ret = _series(200, lead=2)
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger, _ledger_records(pressure, ret))
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "observation", "series": "price_btc", "stam\n')

    out = tmp_path / "artifact.json"
    assert S.main(["--ledger", str(ledger), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))

    assert doc["status"] == "SCREENED"
    assert doc["ledger"]["unparseable_lines"] == 1
    assert ledger.read_text("utf-8").endswith('"stam\n'), "the torn line must survive on disk"


def test_generated_utc_is_timezone_aware():
    doc = S._status_artifact("NOT-READABLE-HERE", "why", [], {})
    assert datetime.fromisoformat(doc["generated_utc"]).tzinfo is not None
    assert datetime.fromisoformat(doc["generated_utc"]).utcoffset() == timedelta(0)
    assert datetime.now(tz=UTC).tzinfo is UTC
