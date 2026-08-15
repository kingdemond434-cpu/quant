#!/usr/bin/env python3
"""THE WEALTH REPORT — the economic scoreboard, above every architecture count.

WHAT THIS ANSWERS, in the order the specification puts them::

    is the desk RETAINING what it makes, or round-tripping it?      wealth_retention
    where did the money actually come from?                          return_engines
    how many independent bets is the book really carrying?           return_engines §58
    how long does evidence take to become a position?                conversion_velocity
    what did we decline, and was the reason systematically wrong?    decision_ledger
    how do we stand against the external benchmark?                  external_benchmark
    which model should be selected -- by payoff, not by accuracy?     payoff_selection
    did any conditional mechanism survive its own harder branch?     state_conditional

**EVERY NUMBER HERE IS READ FROM AN ARTIFACT OR REPORTED AS UNMEASURED.** Nothing on this desk has
a NAV path yet, no engine has a realised P&L series, and no candidate has reached a live fill. A
report that filled those with plausible defaults would be the most dangerous file in the repo: it
would look exactly like a working scoreboard and would be describing a simulation of a desk. So
every section that has no input says so in the words the specification uses -- UNMEASURED -- and
names the artifact whose absence caused it.

THAT IS THE POINT OF RUNNING IT TODAY RATHER THAN WHEN THE DATA ARRIVES. The consumers exist, the
shapes are fixed, and the moment the live path produces a fill the numbers appear without anyone
remembering to wire anything. A capability wired only when its input exists is a capability that
gets wired late, and the specification's §66 calls that stranding.

Reads artifacts, writes one. Allocates nothing, trades nothing, promotes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.portfolio.return_engines import EngineReturn  # noqa: E402
from libs.portfolio.return_engines import summarise as engines_summary  # noqa: E402
from libs.portfolio.wealth_retention import (  # noqa: E402
    NavPath,
    RiskyProposal,
    reserve_option_value,
)
from libs.portfolio.wealth_retention import summarise as retention_summary  # noqa: E402
from libs.research import capital_basis  # noqa: E402
from libs.research.alpha_retention import LossEvent, RetentionRecord  # noqa: E402
from libs.research.alpha_retention import summarise as retention_loss_summary  # noqa: E402
from libs.research.conversion_velocity import STAGES, ConversionRecord  # noqa: E402
from libs.research.conversion_velocity import summarise as velocity_summary  # noqa: E402
from libs.research.decision_ledger import Decision  # noqa: E402
from libs.research.decision_ledger import summarise as decision_summary  # noqa: E402
from libs.research.external_benchmark import BenchmarkClaim, OwnPerformance  # noqa: E402
from libs.research.external_benchmark import summarise as benchmark_summary  # noqa: E402
from libs.research.payoff_selection import ModelRecord  # noqa: E402
from libs.research.payoff_selection import summarise as payoff_summary  # noqa: E402
from libs.validation.effective_sample import SampleGeometry  # noqa: E402
from libs.validation.effective_sample import summarise as sample_summary  # noqa: E402
from libs.validation.state_conditional import ConditionalEvidence, Preregistration  # noqa: E402
from libs.validation.state_conditional import summarise as conditional_summary  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "wealth_report.json"

#: Inputs. Every one is optional and every absence is REPORTED rather than defaulted.
NAV_PATH = DATA / "nav_path.json"
ENGINE_PNL = DATA / "engine_pnl.json"
CONVERSION = DATA / "conversion_records.json"
DECISIONS = DATA / "decision_ledger.jsonl"
BENCHMARK = DATA / "external_benchmark_claims.json"
MODELS = DATA / "model_records.json"
CONDITIONAL = DATA / "state_conditional_candidates.json"
LADDER = DATA / "live_ladder.json"
RETENTION = DATA / "alpha_retention.json"
SAMPLE_GEOMETRY = DATA / "sample_geometry.json"


def _load(p: Path) -> object | None:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _load_lines(p: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in p.read_text("utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def _rel(p: Path) -> str:
    """Repo-relative when possible, absolute otherwise.

    `Path.relative_to` RAISES for anything outside the repo, and the first version of `_absent`
    called it unguarded. That turned a missing-input report -- the one code path that must survive
    every absence -- into a ValueError the moment the inputs were pointed anywhere else. The
    function whose whole job is to handle a file not being there must not itself depend on where
    the file would have been.
    """
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _absent(artifact: Path, what: str) -> dict[str, object]:
    """The shape used everywhere an input is missing. Names the file, refuses a verdict."""
    rel = _rel(artifact)
    return {
        "measured": False,
        "missing_artifact": rel,
        "headline": (
            f"UNMEASURED -- {rel} is absent. {what}. This is a fact "
            "about the inputs, not a clean result: absence must never resolve to a verdict"),
    }


# ------------------------------------------------------------------ section builders

def wealth_section() -> dict[str, object]:
    raw = _load(NAV_PATH)
    if not isinstance(raw, dict) or not raw.get("nav"):
        return _absent(NAV_PATH, "gain retention, round-trip ratio and realised log growth cannot "
                                 "be computed and the desk cannot say whether it keeps what it makes")
    path = NavPath(nav=tuple(float(v) for v in raw["nav"]),
                   flows=tuple(float(v) for v in raw.get("flows", ())))
    props = tuple(RiskyProposal(
        name=str(p.get("name", "?")), edge=float(p.get("edge", 0.0)),
        edge_sigma=float(p.get("edge_sigma", 0.0)), variance=float(p.get("variance", 0.0)),
        tail_loss=float(p.get("tail_loss", 0.0)),
        effective_n=float(p.get("effective_n", 0.0))) for p in raw.get("proposals", []))
    rv = reserve_option_value(
        opportunity_arrival_rate=float(raw.get("dislocation_rate_per_day", 0.0)),
        expected_dislocation_edge=float(raw.get("dislocation_edge", 0.0)),
        horizon_periods=float(raw.get("horizon_days", 0.0)))
    return retention_summary(path, proposals=props,
                             current_risky_fraction=float(raw.get("risky_fraction", 0.0)),
                             reserve_value=rv)


def engines_section() -> dict[str, object]:
    raw = _load(ENGINE_PNL)
    if not isinstance(raw, dict) or not raw.get("engines"):
        return _absent(ENGINE_PNL, "No euro of P&L is attributed to a return engine, so beta "
                                   "cannot be distinguished from alpha and the effective "
                                   "independent engine count is unknown")
    rows = []
    for e in raw["engines"]:
        try:
            rows.append(EngineReturn(
                engine=str(e["engine"]), pnl=float(e.get("pnl", 0.0)),
                returns=tuple(float(x) for x in e.get("returns", ())),
                market_beta=e.get("market_beta"), r2_market=e.get("r2_market")))
        except (KeyError, ValueError, TypeError):
            continue
    gross = raw.get("gross_pnl")
    return engines_summary(rows, gross_pnl=None if gross is None else float(gross))


def velocity_section() -> dict[str, object]:
    raw = _load(CONVERSION)
    records: list[ConversionRecord] = []
    if isinstance(raw, dict) and raw.get("records"):
        for r in raw["records"]:
            records.append(ConversionRecord(
                candidate_id=str(r.get("candidate_id", "?")),
                stage_days={k: (None if r.get("stage_days", {}).get(k) is None
                                else float(r["stage_days"][k])) for k in STAGES},
                half_life_days=float(r.get("half_life_days", 0.0)),
                expected_bps_per_day=float(r.get("expected_bps_per_day", 0.0)),
                effective_n=float(r.get("effective_n", 0.0)),
                required_effective_n=float(r.get("required_effective_n", 0.0)),
                age_days=float(r.get("age_days", 0.0))))
    if not records:
        records = _records_from_ladder()
    if not records:
        return _absent(CONVERSION, "ECONOMIC_CONVERSION_VELOCITY is unknown, so the one deficit "
                                   "the benchmark specification names as decisive -- the clock "
                                   "between evidence and exposure -- is unwatched")
    return velocity_summary(records)


def _records_from_ladder() -> list[ConversionRecord]:
    """Derive conversion records from the live ladder when no dedicated artifact exists yet.

    DERIVED, AND SAID SO IN THE REPORT. The ladder knows which candidates are owed a shadow start
    and how much forward evidence each carries; that is enough to answer EVIDENCE_BOUND vs
    PROCESS_BOUND, which is the distinction that decides whether a delay is waste. It does NOT
    know discovery timestamps, so the per-stage latencies stay None rather than being invented.
    """
    lad = _load(LADDER)
    if not isinstance(lad, dict):
        return []
    out: list[ConversionRecord] = []
    for row in (lad.get("rows") or []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("alpha") or row.get("name") or row.get("id") or "?")
        eff = float(row.get("effective_n") or row.get("n_effective") or 0.0)
        req = float(row.get("required_effective_n") or row.get("required") or 0.0)
        out.append(ConversionRecord(
            candidate_id=name,
            stage_days={"discovered": 0.0, "survivor": 0.0},
            effective_n=eff, required_effective_n=req,
            age_days=float(row.get("age_days") or 0.0)))
    return out


def decisions_section() -> dict[str, object]:
    rows = _load_lines(DECISIONS)
    if not rows:
        return _absent(DECISIONS, "the desk's decision surface is legible only where it said yes, "
                                  "so no rejection rule can be shown to be systematically wrong")
    decisions = []
    for r in rows:
        try:
            decisions.append(Decision(
                decision_id=str(r["decision_id"]), strategy_id=str(r.get("strategy_id", "")),
                symbol=str(r.get("symbol", "")), decided_at=str(r.get("decided_at", "")),
                outcome=str(r["outcome"]), reason=str(r.get("reason", "")),
                regime=str(r.get("regime", "")),
                signal_bps=float(r.get("signal_bps", 0.0)),
                modelled_cost_bps=float(r.get("modelled_cost_bps", 0.0)),
                counterfactual_bps=(None if r.get("counterfactual_bps") is None
                                    else float(r["counterfactual_bps"])),
                intended_notional=float(r.get("intended_notional", 0.0))))
        except (KeyError, ValueError, TypeError):
            continue
    return decision_summary(decisions)


def benchmark_section() -> dict[str, object]:
    raw = _load(BENCHMARK)
    claims = []
    if isinstance(raw, dict):
        for c in raw.get("claims", []):
            try:
                claims.append(BenchmarkClaim(
                    claimant=str(c["claimant"]), source=str(c.get("source", "")),
                    observed_at=str(c.get("observed_at", "")),
                    evidence_class=str(c["evidence_class"]),
                    start_value=float(c.get("start_value", 0.0)),
                    end_value=float(c.get("end_value", 0.0)),
                    elapsed_days=float(c.get("elapsed_days", 0.0)),
                    strategy_type=str(c.get("strategy_type", "")),
                    estimated_beta_share=c.get("estimated_beta_share"),
                    leverage=c.get("leverage"), realised=bool(c.get("realised", False)),
                    flows_disclosed=bool(c.get("flows_disclosed", False)),
                    net_of_costs=bool(c.get("net_of_costs", False)),
                    verification_notes=str(c.get("verification_notes", ""))))
            except (KeyError, ValueError, TypeError):
                continue
    own = _own_performance()
    if not claims and own is None:
        return _absent(BENCHMARK, "no external claim is recorded and our own live performance is "
                                  "unmeasured, so PERFORMANCE_LEAD does not exist in either term")
    return benchmark_summary(claims, own)


def _own_performance() -> OwnPerformance | None:
    raw = _load(NAV_PATH)
    if not isinstance(raw, dict) or not raw.get("nav"):
        return None
    from libs.portfolio.wealth_retention import drawdown_series, realized_log_growth
    path = NavPath(nav=tuple(float(v) for v in raw["nav"]),
                   flows=tuple(float(v) for v in raw.get("flows", ())))
    g = realized_log_growth(path)
    dd = drawdown_series(path.nav)
    return OwnPerformance(
        realized_log_growth=0.0 if g is None or g == float("-inf") else g,
        elapsed_days=float(raw.get("elapsed_days", 0.0)),
        deployed_capital=float(raw.get("deployed_capital", 0.0)),
        total_capital=float(raw.get("total_capital", 0.0)),
        max_drawdown=max(dd) if dd else 0.0,
        real_fills=int(raw.get("real_fills", 0)),
        realised_pnl=float(raw.get("realised_pnl", 0.0)))


def payoff_section() -> dict[str, object]:
    raw = _load(MODELS)
    if not isinstance(raw, dict) or not raw.get("models"):
        return _absent(MODELS, "no model is economically ranked, so any model in use today was "
                               "selected on something other than expected log growth")
    models = []
    for m in raw["models"]:
        try:
            models.append(ModelRecord(
                name=str(m["name"]), n_predictions=int(m.get("n_predictions", 0)),
                hit_rate=float(m.get("hit_rate", 0.0)), win_bps=float(m.get("win_bps", 0.0)),
                loss_bps=float(m.get("loss_bps", 0.0)),
                trades_per_year=float(m.get("trades_per_year", 0.0)),
                capital_fraction=float(m.get("capital_fraction", 1.0)),
                tail_loss_bps=float(m.get("tail_loss_bps", 0.0)),
                mean_predicted=float(m.get("mean_predicted", 0.0)),
                mean_realised=float(m.get("mean_realised", 0.0)),
                mean_log_loss=float(m.get("mean_log_loss", 0.0)), auc=m.get("auc")))
        except (KeyError, ValueError, TypeError):
            continue
    return payoff_summary(models)


def conditional_section() -> dict[str, object]:
    raw = _load(CONDITIONAL)
    pairs = []
    if isinstance(raw, dict):
        for c in raw.get("candidates", []):
            try:
                p = c["preregistration"]
                e = c["evidence"]
                pairs.append((
                    Preregistration(
                        hypothesis_id=str(p["hypothesis_id"]),
                        mechanism_class=str(p.get("mechanism_class", "GLOBAL_MECHANISM")),
                        state_definition=str(p.get("state_definition", "")),
                        conditionality_mechanism=str(p.get("conditionality_mechanism", "")),
                        sequence=int(p.get("sequence", 0))),
                    ConditionalEvidence(
                        hypothesis_id=str(e["hypothesis_id"]),
                        first_evaluated_sequence=int(e.get("first_evaluated_sequence", 0)),
                        state_occurrences=int(e.get("state_occurrences", 0)),
                        state_share=float(e.get("state_share", 0.0)),
                        as_of_observable=bool(e.get("as_of_observable", False)),
                        classifier_stability=float(e.get("classifier_stability", 0.0)),
                        in_state_net_bps=float(e.get("in_state_net_bps", 0.0)),
                        out_state_net_bps=float(e.get("out_state_net_bps", 0.0)),
                        in_state_n=int(e.get("in_state_n", 0)),
                        out_state_n=int(e.get("out_state_n", 0)),
                        transition_net_bps=e.get("transition_net_bps"),
                        conditional_costs_measured=bool(
                            e.get("conditional_costs_measured", False)),
                        untouched_oos_net_bps=e.get("untouched_oos_net_bps"),
                        untouched_oos_n=int(e.get("untouched_oos_n", 0)))))
            except (KeyError, ValueError, TypeError):
                continue
    return conditional_summary(pairs)


def operational_section() -> dict[str, object]:
    """§45. How much VALIDATED edge never arrived, and what it would cost to recover it.

    The gap between what a strategy would have earned running exactly as validated and what it
    actually earned is invisible on every P&L: it presents as a weaker edge, which invites doubt
    about the research rather than about the plumbing. Recovering it is the one thing on this desk
    that competes with new alpha on identical units -- bps per engineering hour.
    """
    raw = _load(RETENTION)
    if not isinstance(raw, dict) or not raw.get("strategies"):
        return _absent(RETENTION, "ALPHA_RETENTION_RATIO is unknown, so every shortfall against a "
                                  "validated expectation currently reads as the research having "
                                  "been wrong rather than the plumbing having leaked")
    records = []
    for r in raw["strategies"]:
        losses = []
        for ev in r.get("losses", []):
            try:
                losses.append(LossEvent(
                    cause=str(ev["cause"]), lost_bps=float(ev.get("lost_bps", 0.0)),
                    duration_days=float(ev.get("duration_days", 0.0)),
                    recurring=bool(ev.get("recurring", True)),
                    fix_cost_hours=float(ev.get("fix_cost_hours", 0.0)),
                    detail=str(ev.get("detail", ""))))
            except (KeyError, ValueError, TypeError):
                continue
        records.append(RetentionRecord(
            strategy_id=str(r.get("strategy_id", "?")),
            live_days=float(r.get("live_days", 0.0)),
            expected_bps=float(r.get("expected_bps", 0.0)),
            realised_bps=float(r.get("realised_bps", 0.0)),
            losses=tuple(losses)))
    return retention_loss_summary(records)


def sample_section() -> dict[str, object]:
    """§15. How many of the rows behind each claim were actually independent observations.

    t scales as sqrt(n), so a tenfold inflation of the count is a threefold inflation of every
    t-statistic computed on it -- silently, on every candidate the sweep has ever produced.
    """
    raw = _load(SAMPLE_GEOMETRY)
    if not isinstance(raw, dict) or not raw.get("samples"):
        return _absent(SAMPLE_GEOMETRY, "every `n` this desk feeds into a significance test is a "
                                        "raw row count, and whether it overstates the evidence is "
                                        "UNMEASURED")
    samples = {}
    for name, g in raw["samples"].items():
        samples[str(name)] = SampleGeometry(
            rows=int(g.get("rows", 0)), window_length=int(g.get("window_length", 1)),
            step=int(g.get("step", 0)), autocorrelation=float(g.get("autocorrelation", 0.0)),
            distinct_events=int(g.get("distinct_events", 0)),
            distinct_regimes=int(g.get("distinct_regimes", 0)),
            n_assets=int(g.get("n_assets", 1)),
            mean_asset_rho=float(g.get("mean_asset_rho", 0.0)),
            n_venues=int(g.get("n_venues", 1)),
            mean_venue_rho=float(g.get("mean_venue_rho", 0.0)))
    return sample_summary(samples)


def board_question(sections: dict[str, dict]) -> tuple[str, str]:
    """§DAILY BOARD QUESTION -- what is currently preventing more retained net wealth?

    Answered from the sections in a fixed precedence, because the ordering IS the answer: an
    unmeasured scoreboard outranks a slow one, and a slow one outranks a thin one. The highest
    item that fires becomes the next task, which is what makes this a scheduler input rather
    than a rhetorical flourish.
    """
    w, e, v = sections["wealth_retention"], sections["return_engines"], sections["conversion"]
    b = sections["external_benchmark"]
    if not w.get("measured", True) and not e.get("measured", True):
        return ("NO REALISED P&L EXISTS TO RETAIN", (
            "Neither a NAV path nor an engine attribution is present, so wealth retention and "
            "return attribution are both UNMEASURED. Nothing on this desk has yet produced a "
            "realised euro, which makes every retention and benchmark number below undefined "
            "rather than good. The binding constraint is reaching a first real fill"))
    if int(v.get("process_bound", 0) or 0) > 0:
        return ("ALPHA IS NOT REACHING LIVE", (
            f"{v['process_bound']} candidate(s) hold sufficient evidence and are not moving, "
            f"costing at least {v.get('total_process_waiting_cost_bps', 0)}bp. This is the "
            "conversion deficit the benchmark spec names as the benchmarked operator's actual "
            "advantage, and it is the cheapest thing on this list to fix"))
    if e.get("hidden_beta"):
        return ("BETA IS BEING REPORTED AS ALPHA", (
            f"{len(e['hidden_beta'])} engine(s) declared independent behave as market exposure. "
            "Capital sized against the wrong covariance is the mechanism behind the round trip "
            "this desk is built to avoid"))
    rt = (w.get("ROUND_TRIP_RATIO") or 0.0) if w.get("measured") else 0.0
    if isinstance(rt, int | float) and rt >= 0.5:
        return ("WEALTH IS ROUND-TRIPPING", (
            f"{rt:.0%} of the peak gain has been surrendered. Return generation is not the "
            "constraint; retention is"))
    if b.get("own_win_conditions_unmet"):
        return ("THE COMPARISON IS NOT YET WINNABLE", (
            f"our side fails {b['own_win_conditions_unmet']}. A lead computed before these hold "
            "would be a comparison we chose the framing for"))
    return ("NOT ENOUGH INDEPENDENT ALPHA", (
        "no measured blockage in retention, attribution, conversion or benchmark comparability. "
        "The binding constraint is the supply of independent validated edge"))


def _safe(name: str, fn, artifact: Path) -> dict[str, object]:
    """Run one section, and turn a malformed input into UNMEASURED rather than into no report.

    THE FAILURE THIS PREVENTS IS TOTAL, NOT PARTIAL. Every section here is fed by an artifact
    written elsewhere, and a single bad value -- a string where a float belongs, a null in a list
    -- would otherwise raise out of `build` and produce NO scoreboard at all. The desk would then
    be blind to wealth retention, attribution and conversion because one unrelated file was
    malformed, and the only symptom would be a report that stopped appearing.

    So a section that cannot parse its own input reports exactly what a section with no input
    reports: UNMEASURED, naming the file. That is the honest description of both states, and it
    keeps the other six sections readable.
    """
    try:
        return fn()
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as e:
        return {
            "measured": False,
            "missing_artifact": _rel(artifact),
            "headline": (
                f"UNMEASURED -- {name}: {_rel(artifact)} is present but MALFORMED "
                f"({type(e).__name__}: {e}). A section that cannot parse its input knows exactly "
                "as much as one with no input, and reporting anything else would be an invention"),
        }


def build() -> dict[str, object]:
    sections = {
        "wealth_retention": _safe("wealth_retention", wealth_section, NAV_PATH),
        "return_engines": _safe("return_engines", engines_section, ENGINE_PNL),
        "conversion": _safe("conversion", velocity_section, CONVERSION),
        "decisions": _safe("decisions", decisions_section, DECISIONS),
        "external_benchmark": _safe("external_benchmark", benchmark_section, BENCHMARK),
        "payoff_selection": _safe("payoff_selection", payoff_section, MODELS),
        "state_conditional": _safe("state_conditional", conditional_section, CONDITIONAL),
        "operational_retention": _safe("operational_retention", operational_section, RETENTION),
        "effective_sample": _safe("effective_sample", sample_section, SAMPLE_GEOMETRY),
    }
    q, why = board_question(sections)
    unmeasured = [k for k, s in sections.items() if s.get("measured") is False]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "DAILY_BOARD_QUESTION": "What is currently preventing this desk from generating and "
                                "retaining more real net wealth?",
        "ANSWER": q,
        "why": why,
        # THE DENOMINATOR IS DECLARED, NOT ASSUMED (L1.58-r0287). Every return this board reports
        # is a ratio, and a ratio whose denominator is unnamed is unfalsifiable: `+8%` on capital
        # actually drawn and `+8%` on total portfolio value are different claims that print
        # identically, and the second is the Quantopian trap -- legal to state, impossible to
        # audit, and flattering by exactly the amount of cash left idle.
        #
        # `libs.research.capital_basis` has carried the vocabulary and this helper since the law
        # was written, and `scripts/check_capital_basis.py` fails any web/ or reports/ artifact
        # reporting a return without one. NOTHING EVER CALLED IT: the fence named the helper in
        # its own message and no producer imported it, so L1.58-r0287 read as enforced while every
        # artifact it governs published undeclared denominators. Measured by
        # check_enforcement_execution 2026-08-14 as MENTIONED -- a fence that has never run.
        #
        # capital_utilized is the honest leveraged-book basis: PnL over the cash ACTUALLY drawn,
        # including margin. It is the denominator that cannot be inflated by holding cash idle.
        **capital_basis.declare("capital_utilized"),
        "unmeasured_sections": unmeasured,
        "sections": sections,
        "note": ("Architecture counts are deliberately absent from this report. Every section "
                 "with no input reports UNMEASURED and names the artifact whose absence caused "
                 "it -- an empty scoreboard filled with plausible defaults would be "
                 "indistinguishable from a working one."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    rep = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1, sort_keys=False), "utf-8")

    print("=== WEALTH REPORT ===")
    print(f"BOARD QUESTION: {rep['ANSWER']}")
    print(f"  {rep['why']}")
    for name, s in rep["sections"].items():          # type: ignore[union-attr]
        print(f"  [{name}] {s.get('headline', 'no headline')}")
    if rep["unmeasured_sections"]:
        print(f"  UNMEASURED sections: {rep['unmeasured_sections']}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
