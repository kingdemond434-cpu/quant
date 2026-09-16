"""VALUE OF DATA -- the ratio is the product, so these pin the arithmetic and the boundary.

    python -m pytest desks/mt5/tests/test_value_of_data.py -q -p no:cacheprovider

What is fenced here, and why each one is worth a test:

  * THE PROJECTION NEVER WIDENS A POSTERIOR. The obvious way to price "k more trades" -- hold the
    per-observation dispersion fixed and re-run the NIG update -- makes sd RISE for n = 1, because
    a one-trade row has no dispersion evidence at all and the added trades supply some. A negative
    value on the thinnest sleeve on the book is exactly backwards, and it is invisible until
    somebody reads the queue and finds the sleeve that needs data ranked last;
  * A THIN SLEEVE GAINS MORE THAN A THICK ONE from the same k. That is the whole claim of the
    organ: information is worth most where there is least of it, and if the arithmetic ever stops
    saying so the ranking is noise wearing a decimal point;
  * COST IS NEVER ZERO. An unpriced need dividing by an absence sorts straight to the top of a
    ratio, which is how "we never costed it" becomes "it is the best thing on the list" (L1.28a);
  * every source is enumerated -- research_os blocks, information_value blind spots, posterior
    rows, axis findings, coverage gaps -- because a source that silently contributes nothing is
    a wire that reads as a measurement of zero need;
  * ABSENT INPUTS ARE NAMED. RESIDUAL_QUEUE.json does not exist on this box, and "no residual
    findings" and "no residual report" must not print the same;
  * the targets file is in the format the acquisition side already reads, and the append into the
    prospector's file is idempotent and drops nobody else's rows;
  * IT FETCHES NOTHING -- no network module is imported, and --dry-run writes no byte.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research_os import store  # noqa: E402
from research import value_of_data as vod  # noqa: E402


# ------------------------------------------------------------------------------- the fixtures
def _sleeve(name: str, n: int, sd: float) -> dict[str, Any]:
    """One POSTERIOR_ALPHA row, in the artifact's own shape."""
    return {"name": name, "lane": "forward", "family": "carry", "symbol": name[:6],
            "status": "ACTIVE", "n": n, "mu_mean": 0.2, "mu_sd": sd, "basis": "shadow_moments"}


POSTERIOR_DOC = {"at": "2026-09-16T00:00:00+00:00", "n_sleeves": 4, "sleeves": [
    _sleeve("THIN.carry.asia", 3, 0.21),          # thin and wide -- the row that needs data
    _sleeve("THICK.carry.asia", 240, 0.20),       # thick and (implausibly) just as wide
    _sleeve("FUNDED.carry.asia", 12, 0.19),       # the allocator has capital on this one
    _sleeve("SETTLED.carry.asia", 400, 0.02),     # already inside the desk's own bar
]}
SLEEVES_DOC = {"sleeves": [
    {"name": "FUNDED.carry.asia", "risk_frac": 0.02, "status": "LIVE"},
    {"name": "OTHER.live", "risk_frac": 0.01, "status": "LIVE"},
    {"name": "THIN.carry.asia", "risk_frac": 0.0, "status": "STANDBY"},
]}
STANDING_DOC = {"at": "2026-09-16T00:00:00+00:00", "questions": {"Q3": {
    "status": "OK", "n": 3, "findings": [
        {"symbol": "XAUUSD", "axis": "ecb:eur_usd_ref", "corr": 0.31},
        {"symbol": "GBPSEK", "axis": "ecb:eur_usd_ref", "corr": -0.19},
        {"symbol": "XAUUSD", "axis": "fred:dgs10", "corr": 0.11},
    ]}}}
RESIDUAL_DOC = {"rows": [{"target": "AUDCAD", "axis": "cot:AUDUSD.net_pct_oi"}]}
BLOCKING_ROWS = [
    {"observable": "cot positioning", "mechanisms_blocked": 4, "hypotheses_blocked": 11},
    {"observable": "calendar actual prints", "mechanisms_blocked": 2, "hypotheses_blocked": 5},
    {"observable": "", "mechanisms_blocked": 9, "hypotheses_blocked": 9},     # must be ignored
]
BLIND_SPOTS = [
    {"dataset": "cot_positioning", "tier": "research", "what": "CFTC COT net positioning",
     "blind_spots_closed": 3, "obtainable": True, "publication_lag": "3 days",
     "examples": [{"report": "A.json", "at": ".x"}]},
    {"dataset": "compute_history", "tier": "research", "what": "seven days of compute ledger",
     "blind_spots_closed": 1, "obtainable": False, "publication_lag": "none"},
    {"dataset": "financing_terms", "tier": "money", "what": "overnight swap by symbol and side",
     "blind_spots_closed": 0, "obtainable": True, "publication_lag": "none"},   # nothing to close
]
UNCOVERED = ["global=bull|session=ASIA|event=NORMAL|weekday=Mon|timeframe=H1",
             "global=bull|session=ASIA|event=NORMAL|weekday=Tue|timeframe=H1",
             "global=bear|session=NY|event=NORMAL|weekday=Fri|timeframe=M15"]
NEVER_TRIED = {"carry": 2, "event_reaction": 1}
CATALOGUE = [{"name": "cot_positioning", "implementation_cost": 3.0},
             {"name": "macro_release_calendar", "implementation_cost": 3.0},
             {"name": "yield_curves", "implementation_cost": 4.0}]
PROSPECTOR_DOC = {"generated_utc": "2026-09-04T20:18:38+00:00", "targets": [
    {"query": "UST10Y/UST05Y/UKGILT H1 bars", "why": "none has H1 bars here",
     "unlocks": ["dollar_real_rates"], "score": 3.0}]}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every input and output path of the organ pointed into a synthetic tree, and every
    cross-organ call replaced by a fixture -- so nothing here reads the live desk or the live
    research_os database, and nothing written lands in the repository."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    reports.mkdir()
    monkeypatch.setattr(vod, "POSTERIOR", reports / "POSTERIOR_ALPHA.json")
    monkeypatch.setattr(vod, "STANDING", reports / "STANDING_QUESTIONS.json")
    monkeypatch.setattr(vod, "RESIDUAL", reports / "RESIDUAL_QUEUE.json")
    monkeypatch.setattr(vod, "SLEEVES", data / "sleeves.json")
    monkeypatch.setattr(vod, "OUT", reports / "VALUE_OF_DATA.json")
    monkeypatch.setattr(vod, "TARGETS", data / "value_of_data_targets.json")
    monkeypatch.setattr(vod, "PROSPECTOR_TARGETS", data / "prospector_targets.json")
    monkeypatch.setattr(store, "blocking_observables", lambda: list(BLOCKING_ROWS))
    monkeypatch.setattr(vod.iv, "build", lambda: {"ranked_datasets": list(BLIND_SPOTS)})
    monkeypatch.setattr(vod.dp, "_coverage_gaps", lambda: (list(UNCOVERED), dict(NEVER_TRIED)))
    monkeypatch.setattr(vod.dp, "_catalogue", lambda: [dict(r) for r in CATALOGUE])
    vod.POSTERIOR.write_text(json.dumps(POSTERIOR_DOC), "utf-8")
    vod.STANDING.write_text(json.dumps(STANDING_DOC), "utf-8")
    vod.RESIDUAL.write_text(json.dumps(RESIDUAL_DOC), "utf-8")
    vod.SLEEVES.write_text(json.dumps(SLEEVES_DOC), "utf-8")
    vod.PROSPECTOR_TARGETS.write_text(json.dumps(PROSPECTOR_DOC), "utf-8")
    return tmp_path


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["need_id"]): r for r in rows}


# --------------------------------------------------------------------- 1. the NIG arithmetic
def test_the_projection_never_widens_a_posterior() -> None:
    """The n = 1 case is the one that bites: a one-trade row carries NO dispersion evidence, so
    the naive projection ADDS some and reports a wider posterior for more data."""
    for n in (0, 1, 2, 5, 13, 40, 400):
        for sd in (0.02, 0.1, 0.2):
            assert vod.projected_sd(n, sd, 20) <= sd + 1e-12, (n, sd)
            assert vod.sd_reduction(n, sd, 20) >= 0.0


def test_the_projection_is_monotone_in_k_and_starts_where_the_artifact_is() -> None:
    sd = 0.19
    assert vod.projected_sd(12, sd, 0) == pytest.approx(sd)
    seq = [vod.projected_sd(12, sd, k) for k in (0, 5, 20, 100)]
    assert seq == sorted(seq, reverse=True), seq


def test_a_thin_sleeve_gains_more_from_the_same_k_than_a_thick_one() -> None:
    """The whole claim of the organ: information is worth most where there is least of it."""
    thin = vod.sd_reduction(3, 0.20, vod.K_OBS)
    thick = vod.sd_reduction(240, 0.20, vod.K_OBS)
    assert thin > thick > 0.0, (thin, thick)
    assert thin > 3 * thick, "a 3-trade row must not be priced like a 240-trade row"


def test_the_prior_and_the_bar_are_derived_from_posterior_alpha_not_chosen() -> None:
    import research.posterior_alpha as pa
    prior = pa.summarise(pa.nig_update(0.0, 0.0, 0.0))["mu_sd"]
    assert float(prior) == pytest.approx(vod.PRIOR_SD)
    assert int(pa.CREDIBLE_N) == vod.K_OBS
    assert 0.0 < vod.SD_THRESHOLD < vod.PRIOR_SD
    gap = vod.PRIOR_SD - vod.SD_THRESHOLD
    assert gap == pytest.approx(vod.UNBLOCK_VALUE, abs=1e-6)


# --------------------------------------------------------- 2. one need kind per source of need
def test_posterior_rows_wider_than_the_bar_become_forward_trades_needs() -> None:
    fracs, median = vod._risk_fracs(SLEEVES_DOC)
    rows = _by_id(vod.needs_from_posterior(POSTERIOR_DOC, fracs, median))
    assert set(rows) == {"forward_trades:THIN.carry.asia", "forward_trades:THICK.carry.asia",
                         "forward_trades:FUNDED.carry.asia"}
    assert "forward_trades:SETTLED.carry.asia" not in rows, (
        "a sleeve already inside the desk's own credibility bar needs no more data")
    thin = rows["forward_trades:THIN.carry.asia"]
    assert thin["kind"] == "forward_trades" and thin["serves"] == 1
    assert thin["n"] == 3 and thin["sd_after"] < thin["sd_now"]
    assert "NIG sd reduction" in thin["value_basis"]


def test_a_funded_sleeve_is_never_priced_below_an_unfunded_one() -> None:
    """Rule 1 read the right way round: uncertainty about live capital is worth MORE."""
    fracs, median = vod._risk_fracs(SLEEVES_DOC)
    assert median == pytest.approx(0.015)
    rows = _by_id(vod.needs_from_posterior(POSTERIOR_DOC, fracs, median))
    funded = rows["forward_trades:FUNDED.carry.asia"]
    assert funded["stake_weight"] > 1.0 and funded["regret_stake"] > 0.0
    assert funded["regret_reduction"] > 0.0
    bare = vod.needs_from_posterior(POSTERIOR_DOC, {}, 0.0)
    unweighted = _by_id(bare)["forward_trades:FUNDED.carry.asia"]
    assert unweighted["stake_weight"] == 1.0
    assert funded["value"] > unweighted["value"]


def test_an_absent_book_invents_no_stake() -> None:
    fracs, median = vod._risk_fracs(None)
    assert fracs == {} and median == 0.0
    fracs, median = vod._risk_fracs({"sleeves": [{"name": "a", "risk_frac": 0.0}]})
    assert median == 0.0, "no FUNDED sleeve means no reference, not a reference of zero risk"


def test_research_os_blocked_observables_become_needs_with_a_kind() -> None:
    rows = _by_id(vod.needs_from_blocking(BLOCKING_ROWS))
    assert set(rows) == {"blocked:cot positioning", "blocked:calendar actual prints"}, (
        "an empty observable names nothing and must not become a purchase order")
    cot = rows["blocked:cot positioning"]
    assert cot["kind"] == "positioning" and cot["serves"] == 4
    assert cot["value"] == pytest.approx(vod.UNBLOCK_VALUE * 4, abs=1e-6)
    assert rows["blocked:calendar actual prints"]["kind"] == "event_actuals"


def test_information_value_blind_spots_become_needs_and_keep_their_kind() -> None:
    rows = _by_id(vod.needs_from_blind_spots(BLIND_SPOTS))
    assert set(rows) == {"blindspot:cot_positioning", "blindspot:compute_history"}, (
        "a dataset that closes no blind spot is not a need")
    assert rows["blindspot:cot_positioning"]["kind"] == "positioning"
    assert rows["blindspot:cot_positioning"]["value"] == pytest.approx(
        vod.UNBLOCK_VALUE * 3, abs=1e-6)
    assert rows["blindspot:compute_history"]["kind"] is None, (
        "compute is not a market observation; forcing it into one of the six would mis-price it")


def test_an_axis_a_finding_names_becomes_one_need_serving_every_correlate() -> None:
    rows = _by_id(vod.needs_from_axes([STANDING_DOC, RESIDUAL_DOC]))
    assert set(rows) == {"axis_series:ecb:eur_usd_ref", "axis_series:fred:dgs10",
                         "axis_series:cot:AUDUSD.net_pct_oi"}
    shared = rows["axis_series:ecb:eur_usd_ref"]
    assert shared["serves"] == 2 and shared["for_hypotheses"] == ["GBPSEK", "XAUUSD"]
    assert shared["value"] > rows["axis_series:fred:dgs10"]["value"], (
        "an axis two findings depend on is worth more than one only one depends on")
    assert shared["kind"] == "axis_series"


def test_an_absent_residual_report_still_yields_the_standing_axes() -> None:
    rows = vod.needs_from_axes([STANDING_DOC, None])
    assert {r["axis"] for r in rows} == {"ecb:eur_usd_ref", "fred:dgs10"}


def test_coverage_gaps_become_one_bars_need_per_timeframe() -> None:
    rows = _by_id(vod.needs_from_coverage(UNCOVERED, NEVER_TRIED))
    assert set(rows) == {"bars_timeframe:H1", "bars_timeframe:M15"}
    assert rows["bars_timeframe:H1"]["uncovered_buckets"] == 2
    assert rows["bars_timeframe:H1"]["serves"] == 2
    assert vod.needs_from_coverage(UNCOVERED, {}) == [], (
        "uncovered buckets with no never-tried family name no missing observation")


# ------------------------------------------------------------------- 3. cost, and never zero
def test_an_unmeasured_cost_is_the_kinds_default_and_is_flagged_not_zero() -> None:
    costs = vod.catalogue_costs()
    row = vod.price({"kind": "axis_series", "value": 0.2}, costs)
    assert row["cost"] == vod.COST_BY_KIND["axis_series"] > 0.0
    assert row["cost_unmeasured"] is True
    assert row["cost_basis"] == "declared_default:axis_series"
    assert row["ratio"] == pytest.approx(0.2 / vod.COST_BY_KIND["axis_series"], abs=1e-6)


def test_a_kindless_need_takes_the_most_expensive_default_not_the_cheapest(desk: Path) -> None:
    """An unpriced need must never sort to the top of a ratio for not having been costed."""
    row = vod.price({"kind": None, "value": 0.2}, vod.catalogue_costs())
    assert row["cost"] == max(vod.COST_BY_KIND.values())
    assert row["cost_unmeasured"] is True and "KINDLESS" in row["cost_basis"]
    cheap = vod.price({"kind": "cost_surface_dimension", "value": 0.2}, {})
    assert row["ratio"] < cheap["ratio"]


def test_a_known_source_is_costed_from_the_catalogue_and_says_so(desk: Path) -> None:
    costs = vod.catalogue_costs()
    assert costs["cot_positioning"] == 3.0
    row = vod.price({"kind": "positioning", "value": 0.2}, costs)
    assert row["cost_unmeasured"] is False
    assert row["cost_basis"] == "catalogue:cot_positioning"


def test_a_cost_of_zero_can_never_be_reached() -> None:
    assert min(vod.COST_BY_KIND.values()) > 0.0
    assert set(vod.COST_BY_KIND) == set(vod.KINDS), "every kind must carry a declared cost"
    for kind in (*vod.KINDS, None, "nonsense"):
        assert vod.price({"kind": kind, "value": 1.0}, {})["cost"] > 0.0


# ------------------------------------------------------------------ 4. the ranking and the doc
def test_the_queue_is_ranked_by_ratio_and_every_source_reaches_it(desk: Path) -> None:
    doc = vod.build(top=50)
    ratios = [r["ratio"] for r in doc["top"]]
    assert ratios == sorted(ratios, reverse=True), ratios
    sources = {r["source"] for r in doc["top"]}
    assert sources == {"posterior_alpha", "research_os.blocking_observables",
                       "information_value", "standing_questions/residual_queue",
                       "data_prospector.coverage_gaps"}
    assert doc["n_needs"] == len(doc["top"]) + doc["unmeasured"]["n_below_floor"]
    assert doc["unmeasured"]["n_below_floor"] == 1, (
        "THICK.carry.asia gains 0.007R from 20 more trades and must fall below the floor -- a "
        "queue full of near-zero rows is a queue nobody reads (L1.37)")
    assert doc["rule"] == ("one ratio per missing observation; the acquirer fetches, this only "
                           "prices")
    assert set(doc["top"][0]) >= {"need_id", "kind", "what", "value", "cost", "ratio",
                                  "serves", "why"}
    assert doc["by_kind"]["positioning"]["cost_basis"] == "catalogue:cot_positioning"


def test_the_top_is_capped_and_the_unmeasured_block_counts_what_was_declared(desk: Path) -> None:
    doc = vod.build(top=3)
    assert len(doc["top"]) == 3 and doc["n_needs"] > 3
    u = doc["unmeasured"]
    assert u["n_kindless"] == 1 and u["kindless"] == ["blindspot:compute_history"]
    assert 0 < u["n_cost_unmeasured"] < doc["n_needs"], (
        "the catalogue-costed rows must not be counted as unmeasured, nor the declared ones "
        "counted as measured")
    assert u["min_value"] == vod.MIN_VALUE


def test_an_empty_desk_measures_zero_needs_and_names_every_absence(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UNMEASURED is a real answer: 'no residual findings' and 'no residual report' differ."""
    for name in ("POSTERIOR", "STANDING", "RESIDUAL", "SLEEVES", "OUT", "TARGETS",
                 "PROSPECTOR_TARGETS"):
        monkeypatch.setattr(vod, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(store, "blocking_observables", list)
    monkeypatch.setattr(vod.iv, "build", dict)
    monkeypatch.setattr(vod.dp, "_coverage_gaps", lambda: ([], {}))
    doc = vod.build()
    assert doc["n_needs"] == 0 and doc["top"] == [] and doc["by_kind"] == {}
    assert doc["sources"]["posterior_alpha"]["present"] is False
    assert doc["sources"]["residual_queue"]["present"] is False
    assert "no residual report" in doc["sources"]["residual_queue"]["why_absent"]
    assert doc["sources"]["posterior_alpha"]["median_funded_risk_frac"] == "UNMEASURED"


def test_the_summary_is_eight_lines(desk: Path) -> None:
    lines = vod.render(vod.build(top=5))
    assert len(lines) == 8, lines
    assert lines[0].startswith("VALUE OF DATA")


# --------------------------------------------------------- 5. the targets file, and no fetching
def test_the_targets_file_is_written_in_the_acquirers_own_format(desk: Path) -> None:
    doc = vod.build(top=5)
    payload = vod.write_targets(doc)
    on_disk = json.loads(vod.TARGETS.read_text("utf-8"))
    assert on_disk == payload
    assert set(on_disk) >= {"generated_utc", "targets"}
    row = on_disk["targets"][0]
    assert set(row) >= {"query", "why", "unlocks", "score"}, (
        "the prospector target format is query/why/unlocks/score; anything else the crawler "
        "cannot read")
    assert isinstance(row["unlocks"], list) and isinstance(row["score"], (int, float))
    assert row["score"] == doc["top"][0]["ratio"] and row["query"] == doc["top"][0]["what"]
    live = Path(vod.BASE) / "data" / "prospector_targets.json"
    if live.exists():
        real = json.loads(live.read_text("utf-8"))["targets"]
        if real:
            assert set(real[0]) <= set(row), (
                "the live prospector rows carry a key these targets do not")


def test_the_prospector_append_is_idempotent_and_drops_nobody_elses_rows(desk: Path) -> None:
    doc = vod.build(top=4)
    first = vod.append_prospector(doc)
    after_one = json.loads(vod.PROSPECTOR_TARGETS.read_text("utf-8"))
    vod.append_prospector(doc)
    after_two = json.loads(vod.PROSPECTOR_TARGETS.read_text("utf-8"))
    assert "APPENDED" in first
    assert after_one["targets"] == after_two["targets"], "a second run must not duplicate rows"
    assert after_one["targets"][0] == PROSPECTOR_DOC["targets"][0]
    assert sum(1 for t in after_two["targets"] if t.get("source") == "value_of_data") == 4
    assert after_two["generated_utc"] == PROSPECTOR_DOC["generated_utc"], (
        "the prospector's own stamp is its own; this only adds its append time")
    assert after_two["value_of_data_appended_utc"] == doc["at"]


def test_a_missing_prospector_file_is_skipped_rather_than_created(desk: Path) -> None:
    vod.PROSPECTOR_TARGETS.unlink()
    note = vod.append_prospector(vod.build(top=2))
    assert note.startswith("SKIPPED") and not vod.PROSPECTOR_TARGETS.exists()


def test_the_cli_dry_run_writes_no_byte(desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert vod.main(["--dry-run", "--top", "5"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 9 and out[0].startswith("VALUE OF DATA")
    assert "nothing written" in out[-1]
    assert not vod.OUT.exists() and not vod.TARGETS.exists()
    assert json.loads(vod.PROSPECTOR_TARGETS.read_text("utf-8")) == PROSPECTOR_DOC


def test_the_cli_writes_both_artifacts_and_the_report_round_trips(desk: Path) -> None:
    assert vod.main(["--top", "6"]) == 0
    doc = json.loads(vod.OUT.read_text("utf-8"))
    assert doc["n_needs"] > 0 and len(doc["top"]) == 6
    assert doc["targets"] == str(vod.TARGETS)
    assert json.loads(vod.TARGETS.read_text("utf-8"))["targets"][0]["need_id"] == \
        doc["top"][0]["need_id"]
    assert "NEVER fetches" in doc["boundary"]
    assert vod.OUT.with_name(vod.OUT.name + ".tmp").exists() is False


def test_it_reaches_no_network(desk: Path) -> None:
    """The acquirer fetches; this only prices. A pricer that also bought would be two organs."""
    src = (Path(vod.__file__)).read_text("utf-8")
    for banned in ("urllib", "requests", "http.client", "socket", "aiohttp"):
        assert banned not in src, f"{banned} has no business in a pricing organ"
