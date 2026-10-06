"""BREADTH LAW COVERAGE: every row of the 2026-10-05 breadth law, against THIS tree, per pass.

The completion audit of 2026-10-06 cut the breadth law into 635 rows (BREADTH-0001..0635) and read
each against LIVE. This organ re-reads every row against the code that is actually checked out, on
every hourly pass, and publishes `reports/BREADTH_LAW_COVERAGE.json` for the CRO:

    COVERED    the requirement is implemented; `where` is a file:line resolved NOW from an anchor
    PARTIAL    implemented in part (named), or implemented but only its UNMEASURED reading exists
    MISSING    nothing in this tree implements it (the blocker is named)
    REFUSED_BY_GROWTH_GOVERNANCE
               the row would act on capital, sizing, promotion or live status, which breadth never
               does (breadth decides what is hunted and judged next, never what passes); it is
               recorded, never built

AN ANCHOR IS `path::regex`, resolved to the first matching line each pass. A row claimed COVERED
whose anchors no longer resolve is DOWNGRADED to PARTIAL with the dead anchor named -- the claim
is only as good as the code still being there, so a deletion shows up as a coverage fall the same
hour, never as a stale green row. Rows this module does not classify explicitly keep the audit's
reading mapped mechanically (SCHEDULED and later -> COVERED when the audit's module still exists,
CODED/UNMEASURED -> PARTIAL, ABSENT -> MISSING), and say so in `basis`.

Facts only. Nothing here changes an order, a gate, a trial charge, capital or sizing.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
ROWS = ROOT / "docs" / "research" / "breadth_law_rows.json"
OUT = DESK / "reports" / "BREADTH_LAW_COVERAGE.json"

COVERED, PARTIAL, MISSING = "COVERED", "PARTIAL", "MISSING"
REFUSED = "REFUSED_BY_GROWTH_GOVERNANCE"
STATUSES = (COVERED, PARTIAL, MISSING, REFUSED)
#: The audit's states that already mean "runs on a clock" (L1.49: a built organ is not covered).
_RUNNING = frozenset({"SCHEDULED", "LIVE", "PROVEN", "PRODUCING_CELLS", "JUDGED", "FORWARD"})

CS = "desks/mt5/research/certificate_saturation.py"
ND = "desks/mt5/research/near_duplicate.py"
BD = "desks/mt5/research/breadth_debt.py"
JC = "desks/mt5/research/judge_coverage.py"
BL = "desks/mt5/research/breadth_ladder.py"
PB = "desks/mt5/research/producer_breadth.py"
RA = "desks/mt5/research/research_auction.py"
BO = "desks/mt5/research/portfolio_bounty.py"
AB = "desks/mt5/research/alpha_breadth.py"
HC = "desks/mt5/research/hourly_cycle.py"
CRO = "docs/cro/CRO_CYCLE.md"
PATCH = "gauntlet_consume_breadth_order.patch (sealed; desktop applies it)"

#: (ids, status, anchors, note). ids: "0007" or "0008-0028". First match wins, so a narrower
#: entry goes before a range that contains it.
CLASSIFICATION: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    # ------------------------------------------------------------ ANTI-SATURATION LAW
    ("0001", COVERED, (f"{CS}::^def build\\(", f"{AB}::def certificate_saturation_pass"),
     "the map, its debts and its docket stamp run hourly inside alpha_breadth"),
    ("0002", PARTIAL, (f"{CS}::\"n_independent_forward_streams\"",),
     "the target is published; positive-E[log W] per stream needs forward fills (matched_fills)"),
    ("0003-0005", COVERED, (f"{CS}::def expected_dk", f"{CS}::\"breadth_value\"",
                            f"{BD}::^def mode"),
     "P(survivor) x marginal k_eff per row; dk_eff never alone (the stamp orders survivors)"),
    ("0006", COVERED, (f"{CS}::^def is_quality_row", f"{JC}::^def quality_share"),
     "BREADTH (_sat) and QUALITY (_satq) are separate channels with their own docket share"),
    ("0007", COVERED, (f"{CS}::^def build\\(", f"{CS}::^REPORT ="), ""),
    ("0028", PARTIAL, (f"{CS}::\"realised_pnl_cluster\": UNMEASURED",),
     "axis represented; reads UNMEASURED until the forward panel clusters realised P&L"),
    ("0008-0027", COVERED, (f"{CS}::^AXES: tuple", f"{CS}::^def axes_of"),
     "every certificate carries all 21 axes"),
    ("0029", COVERED, (f"{CS}::^def factor_of", f"{ND}::return \"symbol\""),
     "symbols grouped by economic factor; a symbol-only twin is a near-duplicate"),
    ("0030", COVERED, (f"{CS}::^def similarity", f"{CS}::^WEIGHTS"), ""),
    ("0031", COVERED, (f"{ND}::return \"symbol\"", f"{CS}::near_duplicate_rule"), ""),
    ("0032", COVERED, (f"{ND}::return \"small_param\"", f"{CS}::near_duplicate_rule"), ""),
    ("0033", COVERED, (f"{ND}::return \"small_stop\"", f"{CS}::near_duplicate_rule"), ""),
    ("0034", COVERED, (f"{ND}::return \"minor_tf_shift\"", f"{CS}::near_duplicate_rule"), ""),
    ("0035", COVERED, (f"{ND}::return \"equivalent_indicator\"", f"{CS}::near_duplicate_rule"),
     ""),
    ("0036", COVERED, (f"{ND}::return \"renamed_source\"", f"{CS}::near_duplicate_rule"), ""),
    ("0037", COVERED, (f"{CS}::PREREGISTERED 2026-10-06",),
     "structural similarity reads spec axes only; weights preregistered"),
    ("0038", COVERED, (f"{CS}::^def forward_dependence",), ""),
    ("0039-0040", COVERED, (f"{CS}::out\\[\"k_eff_stress\"\\] = keff",),
     "conditional (stress-regime) correlation in book_breadth"),
    ("0041", COVERED, (f"{CS}::^RESIDUAL_LINK", f"{CS}::^def coupling_table"), ""),
    ("0042", COVERED, (f"{CS}::out\\[\"k_eff_tail\"\\]",), ""),
    ("0048", COVERED, (f"{CS}::^def factor_of",), ""),
    ("0050", COVERED, (f"{CS}::^def fisher_bounds", f"{CS}::^def shrink_abs_rho",
                       f"{CS}::^MIN_INDEPENDENCE_OBS"), ""),
    ("0045", MISSING, (), "drawdown-overlap dependence is not measured"),
    ("0046", MISSING, (), "event-overlap dependence is not measured"),
    ("0047", MISSING, (), "regime-overlap dependence is not measured"),
    ("0049", MISSING, (), "lead/lag dependence between held streams is not measured"),
    ("0056", PARTIAL, (f"{CS}::\"L6\":",),
     "level 6 exists; reads UNMEASURED until realised forward clusters exist"),
    ("0051-0055", COVERED, (f"{CS}::^def hierarchy", f"{CS}::^def cluster_key"), ""),
    ("0057", COVERED, (f"{CS}::\"n_payer_clusters\"", f"{CS}::\"n_temporal_clusters\""), ""),
    ("0058", COVERED, (f"{CS}::\"certificate_count\": n_k",), ""),
    ("0059", COVERED, (f"{CS}::\"effective_certificate_count\": round",), ""),
    ("0060-0061", COVERED, (f"{CS}::\"forward_count\": fwd_n",), ""),
    ("0062", COVERED, (f"{CS}::\"effective_trials_spent\": tri",), ""),
    ("0063-0064", COVERED, (f"{CS}::\"best_validated_edge\"", f"{CS}::\"median_validated_edge\""),
     ""),
    ("0065", COVERED, (f"{CS}::\"incremental_survivor_yield\": round",), ""),
    ("0066", COVERED, (f"{CS}::\"mean_intra_cluster_C\"",), ""),
    ("0067", PARTIAL, (f"{CS}::\"worst_stress_status\": UNMEASURED",),
     "field published UNMEASURED: needs per-cluster forward stress returns"),
    ("0068", PARTIAL, (f"{CS}::\"realised_marginal_status\": UNMEASURED",),
     "field published UNMEASURED: needs realised forward streams per cluster"),
    ("0069", COVERED, (f"{CS}::\"remaining_unexplored_axes\": unexplored",), ""),
    ("0070", COVERED, (f"{CS}::saturated = n_k >= 2",), ""),
    ("0071", PARTIAL, (f"{JC}::^def persist_breadth_order", f"{CS}::DUPLICATE TAX"),
     f"docket order and tax built; the judge consumes the order only once {PATCH}"),
    ("0072-0073", COVERED, (f"{BL}::^def split_budget", f"{BO}::breadth_debt",
                            f"{RA}::^def bounty_value"),
     "A/C/D producer budgets and the bounty auction move capacity toward empty/weak clusters"),
    ("0074-0081", COVERED, (f"{CS}::^def _breadth_debts", f"{BD}::^def boost_for"),
     "debts and the mode boost aim at new payer / info / horizon / clock / factor"),
    ("0082", COVERED, (f"{CS}::^EXPLORE_FLOOR",), ""),
    ("0083", COVERED, (f"{CS}::exc.append\\(\"A\"\\)",), ""),
    ("0084", COVERED, (f"{CS}::exc.append\\(\"B\"\\)",), ""),
    ("0085", COVERED, (f"{CS}::exc.append\\(\"C\"\\)",), ""),
    ("0086", COVERED, (f"{CS}::exc.append\\(\"D\"\\)",), ""),
    ("0087", COVERED, (f"{CS}::exc.append\\(\"E\"\\)",), ""),
    ("0088", COVERED, (f"{CS}::exc.append\\(\"F\"\\)",), ""),
    ("0089", COVERED, (f"{CS}::exc.append\\(\"G\"\\)",), ""),
    ("0090", COVERED, (f"{CS}::exc.append\\(\"H\"\\)",), ""),
    ("0091", COVERED, (f"{CS}::breadth_exception",),
     "a declared exception is read from the row before any evidence"),
    ("0092", COVERED, (f"{CS}::^INDEPENDENT_RHO", f"{CS}::^def fisher_bounds"),
     "distinctness needs the upper 95% bound within 0.3, never a point difference"),
    ("0096", PARTIAL, (f"{CS}::out\\[\"k_eff_stress\"\\] = keff",),
     "stress behaviour is measured for the book, not yet as a per-candidate exception"),
    ("0093-0099", COVERED, (f"{CS}::exc.append\\(\"F\"\\)", f"{CS}::exc.append\\(\"H\"\\)",
                            f"{CS}::\"factor_residual\": 1.0"),
     "exceptions A (payer), C (temporal), D (regime), F (measured), H (portfolio) and the "
     "factor-residual axis"),
    ("0100", COVERED, (f"{CS}::^MIN_PAIR_OBS", f"{CS}::^MIN_INDEPENDENCE_OBS"), ""),
    ("0101-0105", COVERED, (f"{CS}::^def factor_of", f"{CS}::^def coupling_table"), ""),
    ("0106", COVERED, (f"{CS}::\"payer\": 3.0",),
     "payer weighs 3.0, the cross-asset label 0.5"),
    ("0107", MISSING, (), "signal overlap between held streams is not measured"),
    ("0110", MISSING, (), "regime overlap between held streams is not measured"),
    ("0111", COVERED, (f"{CS}::\"timeframe\": 0.25",),
     "session 1.0 and chart 0.25 of the similarity: neither is assumed independent"),
    ("0112", COVERED, (f"{CS}::\"n_effective_certificates\": round",), ""),
    ("0113", COVERED, (f"{CS}::nominal certificates ->",), "the funnel line in the map"),
    ("0114", COVERED, (f"{CS}::\"n_effective_certificates\": round",
                       "scripts/check_breadth_mandate.py::NOMINAL_ALONE"), ""),
    ("0115", COVERED, (f"{CS}::def expected_dk",), ""),
    ("0116-0119", COVERED, (f"{BD}::^def boost_for", f"{BD}::unrepresented_asset_factor"),
     "breadth-constrained mode boosts empty payer / info / factor / clock rows"),
    ("0120", PARTIAL, (f"{JC}::^def persist_breadth_order",),
     f"value stamped and ordered on the docket; the judge consumes it only once {PATCH}"),
    ("0121", COVERED, (f"{JC}::^def quality_share", f"{JC}::^QUALITY_SHARE_BOUNDS"), ""),
    ("0122-0126", COVERED, (f"{BL}::^def budget_split", f"{BL}::^def split_budget"), ""),
    ("0127", COVERED, (f"{BL}::quality_degrading",), ""),
    ("0128", COVERED, (f"{JC}::^QUALITY_SHARE_BOUNDS", f"{BL}::^def budget_split"), ""),
    ("0129", COVERED, (f"{CS}::^def _empty_priors",), "continuous decay with effort"),
    ("0130-0131", COVERED, (f"{CS}::^def novelty_credit", f"{CS}::preregistered"), ""),
    ("0133", COVERED, (f"{CS}::\"champion\": ranked",), ""),
    ("0134", COVERED, (f"{CS}::\"_archive\":",), ""),
    ("0142-0151", COVERED, (f"{CS}::^MECHANISM_FAILURE", f"{CS}::^FACTOR_FAILURE",
                            f"{CS}::hedgers = sorted"),
     "declared failure modes per strategy; hedging mechanisms prioritised in the debts"),
    ("0155", COVERED, (f"{ND}::return \"small_param\"",), ""),
    ("0157", COVERED, (f"{ND}::return \"minor_tf_shift\"",), ""),
    ("0158", PARTIAL, (f"{CS}::\"session\": 1.0",),
     "session offset is priced in similarity; no explicit near-duplicate rule for it"),
    ("0159", COVERED, (f"{ND}::return \"small_stop\"",), ""),
    ("0160", COVERED, (f"{ND}::return \"equivalent_indicator\"",), ""),
    ("0161", COVERED, (f"{CS}::^INDEPENDENT_RHO",), ""),
    ("0154", COVERED, (f"{ND}::return \"renamed_source\"",), ""),
    ("0156", COVERED, (f"{ND}::return \"symbol\"",), ""),
    ("0162-0172", COVERED, (f"{CRO}::STEP 4D", f"{CRO}::BREADTH_LAW_COVERAGE"),
     "the noon CRO step reads the map, saturation, debts, split, mode and this table"),
    ("0175", COVERED, (f"{CS}::\"n_effective_certificates\": round",), ""),
    ("0176", COVERED, (f"{CS}::\"n_payer_clusters\"",), ""),
    ("0178", COVERED, (f"{CS}::\"n_independent_forward_streams\"",), ""),
    ("0179", COVERED, (f"{CS}::\"n_live_independent_streams\"",), ""),
    ("0181", PARTIAL, (f"{CS}::\"realised_marginal_status\": UNMEASURED",),
     "needs realised forward streams of recent admissions"),
    ("0182-0183", COVERED, (f"{CS}::\"median_validated_edge_recent\"",), ""),
    ("0185", COVERED, (f"{CS}::\"tail_k_eff_book\"",), ""),
    ("0186", MISSING, (), "source acquisition does not read the book's failure modes"),
    ("0187", COVERED, (f"{CS}::\"failure_modes_the_book_holds_most\"",), ""),
    ("0188-0189", COVERED, (f"{CS}::hedge = 1.5",), "debts priced up for hedging mechanisms"),
    ("0190", MISSING, (), "sandbox allocation does not read the book's failure modes"),
    ("0191", MISSING, (), "forward enrollment is the sealed promoter's; not touched by breadth"),
    ("0192", MISSING, (), "portfolio research does not read the book's failure modes"),
    ("0195", COVERED, (f"{CS}::^EXPLORE_FLOOR", f"{CS}::^DUPLICATE_TAX_FLOOR"), ""),
    # ------------------------------------------------------------ PRODUCER-WIDE ENFORCEMENT
    ("0203", PARTIAL, (f"{CS}::\"realised_return_clusters\"",),
     "delivered; reads UNMEASURED until realised clusters exist"),
    ("0196-0209", PARTIAL, (f"{CS}::^def _book_context", "scripts/kimi_hunter.py::producer_brief",
                            "scripts/run_deepseek_cycle.py::producer_brief"),
     "the full context is built; the kimi and deepseek seats read it, the other producers "
     "receive it only as docket order and budget split"),
    ("0210", PARTIAL, (f"{CS}::\"duplicate_budget\"", f"{PB}::^def duplicate_block"),
     "every producer is measured against a duplicate budget; no hard fence on count"),
    ("0213", COVERED, (f"{BD}::^def mode", f"{AB}::^def breadth_debt_pass"),
     "measured trigger, published in BREADTH_DEBT.json each pass"),
    ("0214-0216", COVERED, (f"{BD}::empty_payer_clusters", f"{BD}::^def boost_for",
                            f"{CS}::boost_for\\(s\\[\"cluster\"\\]"), ""),
    ("0217", PARTIAL, (f"{BD}::unrepresented_regimes",),
     "published to producers; the docket boost cannot see regime (not in the cluster key)"),
    ("0218-0220", COVERED, (f"{BD}::unrepresented_horizons", f"{BD}::^def boost_for"), ""),
    ("0222", PARTIAL, (f"{BD}::^def empty_clusters",),
     "empty alt-data clusters named with bounty and bids; missions come from #163"),
    ("0225", PARTIAL, (f"{BD}::^def empty_clusters",),
     "event_surprise / news_reaction named with bounty and bids; missions come from #163"),
    ("0221", MISSING, (), "low-overlap return geometry is not a priority target"),
    ("0223-0224", MISSING, (), "cross-asset residual / relative-value structures not targeted"),
    ("0243", PARTIAL, ("scripts/kimi_hunter.py::producer_brief",),
     "two seats query the map before generating; the rest do not"),
    ("0244", COVERED, (f"{CS}::^def is_quality_row",), ""),
    ("0246-0256", COVERED, (f"{ND}::^STRUCTURAL_KEY", f"{ND}::^def structural_key",
                            f"{CS}::structural_duplicate"),
     "each key component published; checked on the docket before any backtest"),
    ("0258-0262", COVERED, (f"{CS}::\"duplicate_candidates\": p",
                            f"{CS}::\"duplicate_compute_hours\"",
                            f"{CS}::\"duplicate_effective_trials\"",
                            f"{CS}::^def _survivor_share_for", f"{PB}::^def duplicate_block"),
     "per producer in BREADTH_FEEDBACK.json and PRODUCER_BREADTH"),
    ("0263", COVERED, (f"{CS}::^DUPLICATE_BUDGET_SHARE", f"{CS}::RETARGET"),
     "instructions change (budget block, retarget); volume is never cut"),
    ("0264", COVERED, (f"{CS}::\"delta_k_eff_per_compute_hour\"",), ""),
    ("0265", PARTIAL, (f"{CS}::\"quality_per_compute_hour\": None",),
     "UNMEASURED until execution.matched_fills > 0"),
    ("0266", PARTIAL, (f"{BL}::^def split_budget",),
     "budget is REDIRECTED (order, split) and never cut: NEVER REDUCE research volume"),
    ("0268", COVERED, (f"{CS}::\"new_structural_clusters\"",), ""),
    ("0274", PARTIAL, (f"{CS}::\"provisional_breadth_credit\"",),
     "provisional credit published; realised credit needs forward streams"),
    ("0276", COVERED, (f"{CS}::forward_adjusted_C",), ""),
    ("0277", COVERED, (f"{CS}::out\\[\"k_eff_stress\"\\] = keff",), ""),
    ("0278", MISSING, (), "marginal breadth against the candidate future book is not computed"),
    ("0281-0290", COVERED, (f"{CS}::^FACTOR_FAILURE", f"{CS}::^MECHANISM_FAILURE"),
     "declared per strategy; superseded by measured co-drawdown where ledgers carry it"),
    ("0293", MISSING, (), "joint drawdowns are not measured"),
    ("0295", MISSING, (), "co-crash frequency is not measured"),
    ("0296", COVERED, (f"{CS}::worst decile: lambda_ij",), ""),
    ("0297-0298", MISSING, (), "signal and position overlap are not measured per pair"),
    ("0301", MISSING, (), "event overlap is not measured"),
    ("0302-0316", COVERED, (f"{CS}::\"information_source\", \"family\"",
                            f"{CS}::\"n_information_sources\""),
     "information source is a map axis and an L2 level; empty sources are named debts"),
    ("0317", COVERED, (f"{CS}::exc.append\\(\"B\"\\)",), ""),
    ("0318-0324", COVERED, (f"{CS}::^def method_of", f"{CS}::^METHOD_TOKENS"),
     "method is recorded and carries zero similarity weight"),
    ("0325", COVERED, (f"{CS}::\"method\": p\\[\"method\"\\]",), ""),
    ("0326", REFUSED, (f"{CS}::champion_cap",),
     "research side built (champion cap counts breadth only); a cap on certificates reaching "
     "LIVE would act on promotion"),
    ("0327", COVERED, (f"{CS}::saturated = n_k >= 2 and value < MATERIAL_FALL",), ""),
    ("0329", COVERED, (f"{CS}::value = clone_credit \\* min\\(yield_ratio",), ""),
    ("0331", COVERED, (f"{CS}::local = \\(float",), ""),
    ("0328", PARTIAL, (f"{CS}::saturated = n_k >= 2",), "marginal dk_eff not in the threshold"),
    ("0330", PARTIAL, (f"{CS}::saturated = n_k >= 2",), "trials spent not in the threshold"),
    ("0332", PARTIAL, (f"{CS}::saturated = n_k >= 2",), "unexplored axes not in the threshold"),
    ("0333", COVERED, (f"{CS}::\"retarget_to\"",), "retargeted toward a debt's information source"),
    ("0335-0337", COVERED, (f"{CS}::\"retarget_to\"",), ""),
    ("0334", MISSING, (), "retarget does not name a region"),
    ("0338", MISSING, (), "retarget does not name a representation"),
    ("0341-0346", COVERED, (f"{JC}::^def quality_share", f"{BD}::^MODE_BOOST"),
     "the mode raises breadth rows only; the QUALITY share is untouched"),
    ("0348", COVERED, (f"{CS}::^def shrink_abs_rho",), ""),
    ("0349", COVERED, (f"{CS}::^MIN_INDEPENDENCE_OBS",), ""),
    ("0350", COVERED, (f"{ND}::return \"symbol\"",), ""),
    ("0351", COVERED, (f"{ND}::return \"minor_tf_shift\"",), ""),
    ("0352", COVERED, (f"{CS}::^def factor_of",), "country maps to its factor"),
    ("0353", COVERED, (f"{CS}::^def method_of",), ""),
    ("0354", COVERED, (f"{ND}::return \"small_param\"",), ""),
    ("0355-0356", COVERED, (f"{ND}::return \"renamed_source\"",), ""),
    ("0359-0360", COVERED, (f"{CS}::\"top_clusters\"", f"{CS}::\"duplicate_share\""), ""),
    ("0363", COVERED, (f"{CS}::\"expected_delta_k_eff\": \\(round",), ""),
    ("0364-0365", MISSING, (), "feedback does not carry per-candidate failure and its reason"),
    ("0366-0375", COVERED, (f"{CS}::\"economic_rationale\"", f"{CS}::\"current_nearest_exposure\"",
                            f"{CS}::\"failure_history\"", f"{CS}::\"reopen_trigger\": \\("),
     ""),
    ("0376", COVERED, (f"{RA}::^def bounty_bonus_of",), "bids sum each debt's priced value"),
    ("0377", COVERED, (f"{BO}::read_fresh",), "re-priced from the fresh map every pass"),
    ("0379", COVERED, (f"{CS}::\"n_effective_certificates\": round",), ""),
    ("0383", COVERED, (f"{CS}::\"tail_k_eff_book\"",), ""),
    ("0384", COVERED, (f"{CS}::\"n_payer_clusters\"",), ""),
    ("0385", COVERED, (f"{CS}::\"n_information_sources\"",), ""),
    ("0386", COVERED, (f"{CS}::\"n_factors\"",), ""),
    ("0388", COVERED, (f"{CS}::\"delta_k_eff_per_compute_hour\"",), ""),
    ("0389", COVERED, (f"{CS}::\"duplicate_compute_hours\"",), ""),
    ("0390", MISSING, (), "effective trials per new independent survivor is not published"),
    ("0391", PARTIAL, (f"{CS}::\"quality_per_compute_hour\": None",), "UNMEASURED by design"),
    ("0392", PARTIAL, (f"{CS}::\"_satq\"",),
     "saturated work rides as QUALITY or the duplicate tail; no per-organ justification record"),
    # ------------------------------------------------------------ OPEN-ENDED ALPHA BREADTH
    ("0400", COVERED, (f"{CS}::\"failure_mode_effective_count\"",), ""),
    ("0414", COVERED, (f"{CS}::\"economic_factor\": 1.0",), "breadth value's similarity"),
    ("0419", COVERED, (f"{CS}::\"information_source\": 2.0",), "breadth value's similarity"),
    ("0550", COVERED, (f"{BD}::unrepresented_regimes",), "BREADTH_DEBT.json priority targets"),
    ("0551", COVERED, (f"{CS}::hedgers = sorted",), ""),
    ("0574", COVERED, (f"{RA}::^def bounty_value", f"{CS}::\"value_units\""),
     "each debt priced on its own dk_eff; bids re-price when a debt is paid"),
    ("0580-0583", COVERED, (f"{CS}::^def duplicate_tax",),
     "density x duplicate rate x trials spent x yield decline"),
    ("0617", COVERED, (f"{CS}::^def build\\(",), ""),
    ("0618", COVERED, (f"{CS}::^def _breadth_debts",), ""),
    ("0621", COVERED, (f"{ND}::^def near_duplicate", f"{ND}::^def structural_key"), ""),
    ("0627", COVERED, (f"{AB}::def certificate_saturation_pass",), ""),
)


def _ids(spec: str) -> list[int]:
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def _index() -> dict[int, tuple[str, tuple[str, ...], str]]:
    out: dict[int, tuple[str, tuple[str, ...], str]] = {}
    for spec, status, anchors, note in CLASSIFICATION:
        for i in _ids(spec):
            out.setdefault(i, (status, anchors, note))
    return out


_FILES: dict[str, list[str] | None] = {}


def resolve(anchor: str, root: Path | None = None) -> str | None:
    """`path::regex` -> `path:line` of the first matching line, or None."""
    path, _, pat = anchor.partition("::")
    base = root or ROOT
    key = f"{base}/{path}"
    if key not in _FILES:
        try:
            _FILES[key] = (base / path).read_text("utf-8", errors="replace").splitlines()
        except OSError:
            _FILES[key] = None
    lines = _FILES[key]
    if lines is None:
        return None
    if not pat:
        return f"{path}:1"
    rx = re.compile(pat)
    for n, line in enumerate(lines, 1):
        if rx.search(line):
            return f"{path}:{n}"
    return None


def _audit_where(mods: list[str], root: Path) -> tuple[list[str], list[str]]:
    ok, dead = [], []
    for m in mods:
        path, _, line = str(m).partition(":")
        (ok if (root / path).exists() else dead).append(m if line else f"{path}:1")
    return ok, dead


def classify(row: dict[str, Any], idx: dict[int, tuple[str, tuple[str, ...], str]],
             root: Path) -> dict[str, Any]:
    n = int(str(row["id"]).rsplit("-", 1)[1])
    out: dict[str, Any] = {"id": row["id"], "section": row.get("section"),
                           "requirement": row.get("requirement"),
                           "audit_state": row.get("audit_state")}
    if n in idx:
        status, anchors, note = idx[n]
        where = [resolve(a, root) for a in anchors]
        dead = [a for a, w in zip(anchors, where, strict=True) if w is None]
        out.update(basis="classified", where=[w for w in where if w], note=note or None)
        if status == COVERED and (dead or not anchors):
            status = PARTIAL
            out["downgraded"] = f"anchor(s) no longer resolve: {dead}" if dead else "no anchor"
        elif dead:
            out["dead_anchors"] = dead
        out["status"] = status
        return out
    st = str(row.get("audit_state") or "")
    ok, dead = _audit_where(list(row.get("audit_module") or []), root)
    if st in _RUNNING and ok:
        status = COVERED
    elif st == "ABSENT" or (st in _RUNNING and not ok and dead):
        status = MISSING if st == "ABSENT" else PARTIAL
    else:
        status = PARTIAL if st else MISSING
    out.update(status=status, basis="audit_state_mapped", where=ok,
               note=row.get("audit_blocker") or None)
    if dead:
        out["dead_anchors"] = dead
    return out


def build(*, rows_path: Path | None = None, root: Path | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    base = root or ROOT
    _FILES.clear()
    try:
        src = json.loads((rows_path or ROWS).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300],
                "generated_utc": (now or datetime.now(tz=UTC)).isoformat()}
    idx = _index()
    table = [classify(r, idx, base) for r in src.get("rows") or []]
    counts = Counter(r["status"] for r in table)
    by_sec: dict[str, Counter[str]] = {}
    for r in table:
        sec = str(r.get("section") or "").split(" §")[0]
        by_sec.setdefault(sec, Counter())[r["status"]] += 1
    return {
        "status": "MEASURED",
        "generated_utc": (now or datetime.now(tz=UTC)).isoformat(),
        "mandate": src.get("mandate"), "rows_source": src.get("source"),
        "n_rows": len(table),
        "counts": {s: counts.get(s, 0) for s in STATUSES},
        "counts_by_basis": dict(Counter(r["basis"] for r in table)),
        "counts_by_part": {k: {s: v.get(s, 0) for s in STATUSES} for k, v in by_sec.items()},
        "downgraded": [r["id"] for r in table if r.get("downgraded")],
        "rule": ("COVERED needs a file:line resolved this pass; a dead anchor downgrades the row "
                 "to PARTIAL. Unclassified rows keep the audit's state, mapped mechanically. "
                 "REFUSED rows would act on capital, sizing, promotion or live status."),
        "rows": table,
    }


def publish(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    tmp.replace(p)
    return p


def main(argv: list[str] | None = None) -> int:
    doc = build()
    p = publish(doc)
    print(f"breadth_law_coverage: {doc.get('counts')} downgraded={doc.get('downgraded')} -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
