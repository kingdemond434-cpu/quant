"""EVERY CONVERSION IN THE FUNNEL, ITS RATE, AND THE NAMED REASON THE REST WAS LOST.

    "and is mining conversions n all types of conversions maximised make sure they r too"
                                                            -- the principal, 2026-09-05

THE FUNNEL, AND WHY A RATE PER STAGE IS THE ONLY USEFUL VIEW OF IT. This desk mines the world and
puts what it finds through a funnel; every stage transition is a CONVERSION and every conversion
has a rate. `reports/RESEARCH_PRODUCTIVITY.json` already counts the stages and names a
bottleneck, and `data/intelligence/survivor_funnel.json` already carries five stage totals -- but
neither carries a RATE with a CAUSE beside it, and a count without a cause produces no work. A
reader learns nothing actionable from "47,150 cards, 66 certificates"; a reader learns exactly
what to do from "55% of every gauntlet trial went to a cell type that certifies at 0.03% while
the type that certifies at 14.8% got a quarter of one per cent".

    world sources -> mined item -> hypothesis -> compiled proposal -> research-queue candidate
      -> gauntlet cell -> ten-gate certificate -> forward clock -> promotion candidate
      -> live sleeve -> allocated capital

WHAT EACH ROW OWES. Count in, count out, the rate, the window the counts cover, and the DOMINANT
REASON for the loss -- read out of the desk's own artifacts, never assumed. Three rules make the
ledger honest rather than flattering:

  1. A STAGE WHOSE LOSS REASON CANNOT BE DERIVED SAYS `UNKNOWN`. Not a guess, not a plausible
     story. "REJECTED" is a verdict, not a cause, and thirty thousand rows carrying it is why
     `libs/research/search_populations.graveyard_derived` correctly produced nothing from the
     desk's largest dataset.
  2. AN UNMEASURED STAGE IS A FINDING, NOT A BLANK. `measured: false` carries the artifact that
     is missing and why, because "no certificates are blocked" and "I could not read the
     certificates" are opposite facts.
  3. THE DENOMINATOR IS THE MT5/FUSION UNIVERSE ONLY. The crypto-exchange universe is retired
     (mandate 2026-08-18) and may never be hunted; Fusion-executable crypto CFDs (BTCUSD,
     ETHUSD...) ARE part of the MT5 universe and are counted as the CFDs they are. The ledger
     asserts the fence rather than assuming it: `crypto_fence` reports which symbols in the
     denominator read as crypto and whether each is a Fusion CFD in the registry.

THE BINDING STAGE IS NAMED, AND THE RULE FOR NAMING IT IS STATED. One stage is the constraint;
raising any other rate does nothing until that one moves. The rule here is: among stages ON THE
CRITICAL PATH (every unit of the desk's output must pass through them) and actually MEASURED, the
binding stage is the one with the lowest conversion rate, and the tie-break is the amount of work
it destroys. Tributaries -- stages whose output is not required for a certificate to exist -- are
measured and reported but cannot be named binding, however bad they look: the deepening queue
converts at 0.0% and unblocking it would not add one certificate this week, because nothing
downstream is waiting on it.

A CONVERSION IS NEVER RAISED BY MOVING A BAR. The authority is `max_h E[log W | the entire
current world information set]`. Converting more candidates by converting worse ones lowers it.
Every fix this ledger points at is an allocation, a wiring or a measurement fix; where a gate
looks mis-specified it is named in `gate_notes` with the evidence and left exactly alone.

    python3 research/conversion_ledger.py            # write the ledger and print the funnel
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "data" / "conversion_ledger.json"

#: Stage transitions, in funnel order. `critical` marks the stages every certificate must pass:
#: only those may be named binding, because unblocking a tributary adds nothing downstream.
UNKNOWN = "UNKNOWN"


@dataclass
class Stage:
    """One conversion: what went in, what came out, and WHY the rest did not."""

    name: str
    count_in: int | None = None
    count_out: int | None = None
    #: True when this stage is on the path every certificate must take.
    critical: bool = False
    measured: bool = True
    #: The dominant reason for the loss, read from the data. UNKNOWN when it cannot be derived.
    loss_reason: str = UNKNOWN
    #: Every loss cause found, with its count. Empty is a statement that none was derivable.
    loss_breakdown: dict[str, int] = field(default_factory=dict)
    window: str = ""
    source: str = ""
    note: str = ""

    @property
    def rate(self) -> float | None:
        if not self.measured or not self.count_in or self.count_out is None:
            return None
        return self.count_out / self.count_in

    @property
    def destroyed(self) -> int | None:
        if self.count_in is None or self.count_out is None:
            return None
        return max(0, self.count_in - self.count_out)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["rate"] = None if self.rate is None else round(self.rate, 6)
        d["destroyed"] = self.destroyed
        return d


# ------------------------------------------------------------------------------- readers

def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
                if limit and len(rows) >= limit:
                    break
    except OSError:
        return rows
    return rows


def _window(rows: list[dict[str, Any]], *keys: str) -> str:
    stamps = [str(r.get(k))[:19] for r in rows for k in keys if r.get(k)]
    return f"{min(stamps)} .. {max(stamps)}" if stamps else ""


# ------------------------------------------------------------------------------- the stages

def stage_world_to_mined(base: Path) -> Stage:
    """Grounds worked against grounds that yielded a row. A tributary: the sweeps do not wait."""
    reg = _json(base / "data" / "intelligence" / "coverage_registry.json")
    if not isinstance(reg, dict) or not isinstance(reg.get("platforms"), dict):
        return Stage("world_source -> mined_item", measured=False,
                     source="data/intelligence/coverage_registry.json",
                     loss_reason="coverage registry absent or unreadable on this host")
    plats = reg["platforms"]
    yielded = [p for p, r in plats.items() if int((r or {}).get("best_rows") or 0) > 0]
    states = Counter(str((r or {}).get("last_state") or UNKNOWN)
                     for p, r in plats.items() if int((r or {}).get("best_rows") or 0) <= 0)
    dominant = states.most_common(1)[0][0] if states else UNKNOWN
    return Stage("world_source -> mined_item", len(plats), len(yielded),
                 loss_reason=dominant, loss_breakdown=dict(states),
                 source="data/intelligence/coverage_registry.json",
                 note="a ground that has never yielded a row is not a dead ground; the registry "
                      "keeps it OPEN and the canary searches stand")


def stage_mined_to_rule(base: Path) -> Stage:
    """Deepening tasks against tasks a worker actually turned into a falsifiable rule."""
    q = _json(base / "data" / "hypotheses" / "miner_deepening_queue.json")
    tasks = (q or {}).get("tasks") if isinstance(q, dict) else None
    if not isinstance(tasks, list):
        return Stage("mined_item -> falsifiable_rule", measured=False,
                     source="data/hypotheses/miner_deepening_queue.json",
                     loss_reason="deepening queue absent or unreadable on this host")
    worked = _jsonl(base / "data" / "hypotheses" / "deepening_worked.jsonl")
    dispositions = Counter(str(t.get("disposition") or UNKNOWN)
                           for t in tasks if isinstance(t, dict))
    pending = {k: v for k, v in dispositions.items() if str(k).startswith("NEEDS_")}
    dominant = (max(pending, key=lambda k: pending[k]) if pending
                else (dispositions.most_common(1)[0][0] if dispositions else UNKNOWN))
    return Stage("mined_item -> falsifiable_rule", len(tasks), len(worked),
                 loss_reason=dominant, loss_breakdown=dict(dispositions),
                 source="data/hypotheses/miner_deepening_queue.json + deepening_worked.jsonl",
                 note="TRIBUTARY, not the critical path: the family sweeps reach the gauntlet "
                      "without passing through here, so a 0% rate costs the desk the ideas in "
                      "the queue and not this week's certificates")


def stage_stagea_to_card(base: Path, judged: int, total_cards: int) -> Stage:
    """External Stage-A survivors against gauntlet cards. An EXPANSION, not a loss."""
    surv = _json(base / "data" / "hypotheses" / "external_survivors.json")
    n = len(surv) if isinstance(surv, list) else None
    if n is None:
        return Stage("stage_A_survivor -> queue_card", count_out=total_cards, measured=False,
                     critical=True, source="data/hypotheses/external_survivors.json",
                     loss_reason="external survivor docket absent on this host")
    return Stage("stage_A_survivor -> queue_card", n, total_cards, critical=True,
                 loss_reason="NONE: this stage expands rather than loses -- one Stage-A survivor "
                             "becomes several exactly-parameterised cards",
                 source="data/hypotheses/external_survivors.json + data/research_queue.json",
                 note=f"{judged} of the cards carry a canonical verdict")


def stage_card_to_verdict(rows: list[dict[str, Any]]) -> Stage:
    """Cards queued against cards the gauntlet actually ruled on."""
    judged = [r for r in rows if r.get("canonical_verdict") in ("PASSED", "REJECTED")]
    unjudged = [r for r in rows if r.get("canonical_verdict") not in ("PASSED", "REJECTED")]
    causes = Counter(str(r.get("blocked_on") or r.get("status") or UNKNOWN)[:110]
                     for r in unjudged)
    return Stage("queue_card -> gauntlet_verdict", len(rows), len(judged), critical=True,
                 loss_reason=(causes.most_common(1)[0][0] if causes
                              else "NONE: every card was judged"),
                 loss_breakdown=dict(causes.most_common(8)),
                 window=_window(rows, "created_at"),
                 source="data/research_queue.json",
                 note="an unjudged card is work not yet done, never a failure -- it is counted "
                      "out of the numerator AND the denominator of the gate below")


def stage_verdict_to_certificate(rows: list[dict[str, Any]], yields: list[Any]) -> Stage:
    """THE GATE. Judged cells against ten-gate certificates -- and where the trials went.

    THE LOSS REASON IS AN ALLOCATION FACT, NOT A GATE FACT, and that distinction is the whole
    finding. The gauntlet is not refusing good candidates; it is being handed, overwhelmingly,
    candidates from the cell types where it has never certified anything. The breakdown below is
    certified/tried per (family x asset class), so the reason a reader takes away is "the trials
    went to the wrong ground", which is fixable, rather than "the gates are strict", which would
    invite the one repair that is forbidden.
    """
    judged = [r for r in rows if r.get("canonical_verdict") in ("PASSED", "REJECTED")]
    passed = [r for r in judged if r.get("canonical_verdict") == "PASSED"]
    top = sorted(yields, key=lambda y: (-y.tried))[:8]
    breakdown = {f"{y.family} x {y.asset_class}": y.tried for y in top}
    best = max(yields, key=lambda y: y.lower, default=None)
    biggest = max(yields, key=lambda y: y.tried, default=None)
    reason = UNKNOWN
    if best is not None and biggest is not None and len(judged):
        ratio = (best.rate / biggest.rate) if biggest.rate > 0 else float("inf")
        reason = (f"TRIAL MISALLOCATION: {biggest.family} x {biggest.asset_class} took "
                  f"{biggest.tried / len(judged):.1%} of every trial ever spent and certifies at "
                  f"{biggest.rate:.3%} ({biggest.certified}/{biggest.tried}), while "
                  f"{best.family} x {best.asset_class} certifies at {best.rate:.2%} "
                  f"({best.certified}/{best.tried}) on {best.tried / len(judged):.2%} of it -- "
                  f"{ratio:.0f}x the certificates per unit of compute, on ground the search "
                  f"barely visits")
    return Stage("gauntlet_verdict -> ten_gate_certificate", len(judged), len(passed),
                 critical=True, loss_reason=reason, loss_breakdown=breakdown,
                 window=_window(judged, "reconciled_at"),
                 source="data/research_queue.json canonical_verdict",
                 note="the ten gates are untouched and must stay untouched: this rate rises by "
                      "proposing where the bar is cleared, never by moving the bar")


def stage_certificate_to_enrollable(base: Path) -> Stage:
    """Certificates against certificates that can still enrol a clock, by named status."""
    canon = _json(base / "data" / "UNIVERSAL_SURVIVORS.canon.json")
    survivors = (canon or {}).get("survivors") if isinstance(canon, dict) else None
    if not isinstance(survivors, dict):
        return Stage("ten_gate_certificate -> enrollable", measured=False, critical=True,
                     source="data/UNIVERSAL_SURVIVORS.canon.json",
                     loss_reason="canon absent or unreadable on this host")
    statuses = Counter(str(r.get("status") or "ALIVE") for r in survivors.values()
                       if isinstance(r, dict))
    dead = {k: v for k, v in statuses.items() if k not in ("ALIVE", "UNIVERSAL")}
    alive = len(survivors) - sum(dead.values())
    return Stage("ten_gate_certificate -> enrollable", len(survivors), alive, critical=True,
                 loss_reason=(max(dead, key=lambda k: dead[k]) if dead
                              else "NONE: every certificate is still enrollable"),
                 loss_breakdown=dict(statuses),
                 source="data/UNIVERSAL_SURVIVORS.canon.json",
                 note="LOCKBOX_FAILED is a certificate that failed a REAL held-out test once "
                      "gate 9 stopped reading gate 7's numbers; UNTRADEABLE is a certificate on "
                      "an instrument the desk cannot trade. Neither is a gate to loosen")


def stage_enrollable_to_clock(base: Path) -> Stage:
    """Enrollable certificates against the ones the forward engine can actually replay.

    THE THREE CAUSES ARE THE ENGINE'S OWN, read through the same resolver `shadow_forward`
    uses, so this row cannot drift from what the engine does: a side that is neither LONG nor
    SHORT, a SHORT whose family constructor this engine cannot resolve (a ROUTING or resolver
    question, not a capability gap), and a SHORT whose family genuinely takes no `side` --
    which is refused because enrolling it LONG would accrue forward evidence for the opposite
    direction under an identity claiming LONG.
    """
    canon = _json(base / "data" / "UNIVERSAL_SURVIVORS.canon.json")
    survivors = (canon or {}).get("survivors") if isinstance(canon, dict) else None
    if not isinstance(survivors, dict):
        return Stage("enrollable -> forward_clock", measured=False, critical=True,
                     source="data/UNIVERSAL_SURVIVORS.canon.json",
                     loss_reason="canon absent or unreadable on this host")
    try:
        import shadow_forward as sf
    except Exception as exc:
        return Stage("enrollable -> forward_clock", len(survivors), measured=False, critical=True,
                     source="research/shadow_forward.py",
                     loss_reason=f"forward engine not importable here ({type(exc).__name__}); "
                                 f"the replayability of a certificate is the ENGINE's fact and "
                                 f"is not guessed from the certificate")
    runnable, causes = 0, Counter()
    for row in survivors.values():
        if not isinstance(row, dict) or str(row.get("status") or "ALIVE") not in (
                "ALIVE", "UNIVERSAL"):
            continue
        spec = row.get("shadow_spec") or {}
        fam = str(spec.get("family") or "")
        side = str(spec.get("side") or "").upper()
        fn = sf._family_fn(fam)
        if side not in ("", "LONG", "SHORT"):
            causes["side_neither_long_nor_short"] += 1
        elif side == "SHORT" and fn is None:
            causes["short_constructor_unresolved_here"] += 1
        elif side == "SHORT" and not sf._accepts_side(fn):
            causes["short_family_takes_no_side"] += 1
        elif fn is None:
            causes["constructor_unresolved_here"] += 1
        else:
            runnable += 1
    total = runnable + sum(causes.values())
    top = max(causes, key=lambda k: causes[k]) if causes else ""
    detail = {
        "short_constructor_unresolved_here":
            "a SHORT certificate whose family this engine's resolver cannot see. Check the OTHER "
            "lane before calling it a resolver gap: qquant_shadow owns hunt16's families and may "
            "already hold the clock, in which case resolving it here mints a SECOND clock for "
            "one certificate -- two states, two verdicts, both feeding promotion",
        "short_family_takes_no_side":
            "a SHORT certificate on a family with no `side` parameter. Correctly refused: "
            "enrolling it LONG would accrue forward evidence for the opposite direction under "
            "an identity claiming LONG. The fix is engineering (thread `side` through the spec "
            "tuple, the frozen identity and fam_fn), never an admission",
        "side_neither_long_nor_short":
            "a certificate declaring a side the engine cannot read; refused rather than guessed",
        "constructor_unresolved_here":
            "the family constructor is not in either registry this engine resolves",
    }
    return Stage("enrollable -> forward_clock", total, runnable, critical=True,
                 loss_reason=(f"{top}: {detail.get(top, '')}" if top
                              else "NONE: every enrollable certificate is replayable here"),
                 loss_breakdown=dict(causes),
                 source="data/UNIVERSAL_SURVIVORS.canon.json + research/shadow_forward.py",
                 note="a certificate this engine cannot resolve may still hold a clock in "
                      "ANOTHER lane (qquant_shadow owns hunt16's families); resolving it here "
                      "would mint a SECOND clock for the same certificate, which is why the "
                      "engine calls that a routing question and not a resolver gap")


def stage_clock_to_sleeve(base: Path) -> Stage:
    """Forward clocks against LIVE sleeves. Needs the box's own shadow state."""
    health = base / "reports" / "shadow" / "shadow_health.json"
    doc = _json(health)
    if not isinstance(doc, dict):
        return Stage("forward_clock -> live_sleeve", measured=False, critical=True,
                     source="reports/shadow/shadow_health.json",
                     loss_reason="the shadow state is written on the live box and `reports/` is "
                                 "git-ignored, so no host that has only the repository can "
                                 "measure this stage; read it on Contabo or from the "
                                 "MT5-ShadowSync commit")
    clocks = doc.get("n_sleeves") or doc.get("sleeves") or None
    promoted = doc.get("promoted_live_sleeves")
    n_clocks = len(clocks) if isinstance(clocks, list | dict) else clocks
    n_live = len(promoted) if isinstance(promoted, list | dict) else promoted
    if not isinstance(n_clocks, int) or not isinstance(n_live, int):
        return Stage("forward_clock -> live_sleeve", measured=False, critical=True,
                     source="reports/shadow/shadow_health.json",
                     loss_reason="shadow health present but carries no sleeve/promotion counts")
    return Stage("forward_clock -> live_sleeve", n_clocks, n_live, critical=True,
                 loss_reason="a clock that has not matured is work in progress, not a loss",
                 source="reports/shadow/shadow_health.json")


def stage_sleeve_to_capital(base: Path) -> Stage:
    """Live sleeves against sleeves carrying REALISED growth evidence in the attribution."""
    att = _json(base / "reports" / "allocator_attribution.json")
    if not isinstance(att, dict):
        return Stage("live_sleeve -> allocated_capital", measured=False, critical=True,
                     source="reports/allocator_attribution.json",
                     loss_reason="allocator attribution absent on this host")
    with_ev = att.get("sleeves_with_realized_evidence")
    per = (att.get("per_sleeve") or {}).get("n_sleeves")
    if not isinstance(with_ev, int) or not isinstance(per, int) or per <= 0:
        return Stage("live_sleeve -> allocated_capital", count_out=with_ev, measured=False,
                     critical=True, source="reports/allocator_attribution.json",
                     loss_reason=str(att.get("realized_basis") or UNKNOWN) + ": the attribution "
                     "reports UNMEASURED rather than zero when the realised evidence is absent")
    return Stage("live_sleeve -> allocated_capital", per, with_ev, critical=True,
                 loss_reason=str(att.get("realized_basis") or UNKNOWN),
                 source="reports/allocator_attribution.json")


def stage_expressible_search_space(base: Path) -> Stage:
    """The conversion NO funnel measurement can see: states the generator cannot express.

    A stage's conversion rate says nothing about ideas that were never born. The scalp lane
    sweeps four sessions -- `all`, `london`, `new_york` and the London/NY overlap -- so three of
    the four are London/NY-centric and the fourth is unconditional. There is no Asia session in
    the search space, and no early-European or late-NY one. Meanwhile the lane's best measured
    forward sleeve, `xau_m15_anti_breakout`, earns its best expectancy in ASIA_MID (hours 02-05)
    and reaches those hours only because its session happens to be `all`. The lane has therefore
    never once asked whether an Asia-conditioned version of any family works.

    THE COUNT IN IS THE PHASES THE DESK MEASURES; the count out is the phases the scalp search
    can target. Widening it is not loosening a gate -- a new candidate faces every gate -- but it
    DOES multiply the search space, so it may only land together with the matching rise in the
    multiplicity census (`mt5desk.scalp_families.swept_grid`), or the deflated-Sharpe charge
    would silently fall behind the search and the bar would drop. That is why this row is a
    measurement here and not a change.
    """
    try:
        import scalp_family_expansion as sfe
        sessions = tuple(sfe.SESSIONS)
        proposed = tuple(getattr(sfe, "PROPOSED_SESSIONS", ()))
    except Exception as exc:
        return Stage("measured_phase -> targetable_session", measured=False,
                     source="research/scalp_family_expansion.py",
                     loss_reason=f"scalp expansion not importable here ({type(exc).__name__})")
    curve = _json(base / "reports" / "OPPORTUNITY_CURVE.json")
    phases = (curve or {}).get("by_phase") if isinstance(curve, dict) else None
    alive = {p: r for p, r in (phases or {}).items()
             if isinstance(r, dict) and r.get("verdict") == "ALIVE"}
    conditioned = [s for s in sessions if s != "all"]
    covered = _covered_utc_hours(sfe, conditioned)
    unreachable = sorted(p for p, r in alive.items()
                         if covered is not None
                         and not (_phase_hours(str(r.get("hours") or "")) & covered))
    reachable = len(alive) - len(unreachable)
    reason = (f"SEARCH SPACE CANNOT EXPRESS THE STATE: {', '.join(unreachable)} "
              f"measure ALIVE, and no session the scalp sweep can target "
              f"({', '.join(conditioned)}) covers those hours"
              if unreachable else
              ("every ALIVE phase is reachable by some swept session" if covered is not None
               else UNKNOWN))
    return Stage("measured_phase -> targetable_session", len(alive) or None,
                 reachable if covered is not None else None,
                 measured=covered is not None, loss_reason=reason,
                 loss_breakdown={"sessions_swept": len(sessions),
                                 "sessions_conditioned": len(conditioned),
                                 "sessions_implemented_not_swept": len(proposed),
                                 "phases_measured_alive": len(alive),
                                 "phases_unreachable": len(unreachable)},
                 source="research/scalp_family_expansion.py + reports/OPPORTUNITY_CURVE.json",
                 note="a generator that cannot express a state has a conversion rate of zero on "
                      "it, and no funnel measurement that starts at 'candidate' can see that")


def _phase_hours(spec: str) -> set[int]:
    """`"02-05"` -> {2, 3, 4}. An unparsable span is an empty set, never a guessed one."""
    try:
        lo, hi = (int(x) for x in str(spec).split("-", 1))
    except (TypeError, ValueError):
        return set()
    return {h % 24 for h in range(lo, hi)} if hi > lo else {lo % 24}


def _covered_utc_hours(sfe: Any, sessions: list[str]) -> set[int] | None:
    """UTC hours the swept sessions can reach, taken FROM THE MASK rather than from a table.

    Reading the windows out of `_session_mask` itself is the point: a hard-coded table of session
    hours here would be a second source of truth that drifts from the mask the executor runs, and
    that drift is the exact class of bug the scalp lane was quarantined for.
    """
    try:
        import pandas as pd
    except ImportError:
        return None
    idx = pd.date_range("2026-01-05", periods=24, freq="h", tz="UTC")
    out: set[int] = set()
    for name in sessions:
        try:
            mask = sfe._session_mask(idx, name)
        except Exception:
            return None
        out |= {int(ts.hour) for ts, on in zip(idx, mask, strict=False) if bool(on)}
    return out


# ---------------------------------------------------------------- the graveyard's own causes

def graveyard_causes(base: Path) -> dict[str, Any]:
    """How many buried rows name the GATE that killed them, rather than only that one did.

    `search_populations.graveyard_derived` chooses a mutation axis by matching vocabulary in a
    dead row's stated reason (cost -> horizon, leak -> lag, correlation -> residualisation). A
    row whose reason is the bare word REJECTED matches nothing, so the desk's largest dataset
    yields no research at all. This counts the two populations so the repair is a number.
    """
    path = base / "data" / "hypothesis_graph.jsonl"
    rows = _jsonl(path)
    if not rows:
        return {"measured": False, "why": f"{path.name} absent or empty on this host"}
    dead = [r for r in rows if str(r.get("fate") or "").upper() in ("FAILED", "RETIRED", "KILLED")]
    named = [r for r in dead
             if " at " in str(r.get("why") or "") and "canonical verdict" not in str(r.get("why"))]
    report_paths = Counter(
        str(((r.get("gates") or {}).get("canonical_report") or {}).get("path") or UNKNOWN)
        for r in dead if isinstance(r.get("gates"), dict))
    missing = {p: n for p, n in report_paths.items()
               if p != UNKNOWN and not (ROOT / p).exists()}
    return {
        "measured": True, "dead_rows": len(dead), "cause_named": len(named),
        "cause_named_rate": round(len(named) / len(dead), 6) if dead else None,
        "reports_named": dict(report_paths.most_common(4)),
        "reports_missing_on_this_host": missing,
        "why": ("the cause lives in the canonical gauntlet report a row points at, and "
                "`reports/` is git-ignored -- so on any host that has only the repository the "
                "gate that said no is UNRECOVERABLE, and scripts/backfill_hypothesis_graph.py "
                "can only repair rows on a host where that report exists"
                if missing else
                "every named report is present on this host, so the causes are recoverable"),
    }


def crypto_fence(rows: list[dict[str, Any]], base: Path | None = None) -> dict[str, Any]:
    """The retired-universe fence, asserted rather than assumed (mandate 2026-08-18).

    No crypto-EXCHANGE universe may be hunted. Fusion-executable crypto CFDs are part of the MT5
    universe and are legitimately in the denominator, so this reports which symbols read as
    crypto and whether each one is in the desk's own instrument registry -- a crypto symbol that
    is NOT in the registry would be an exchange-native leak and a measurement bug.
    """
    try:
        from mt5desk.universe import asset_class
    except Exception as exc:
        return {"measured": False, "why": f"classifier unavailable ({type(exc).__name__})"}
    meta = _json((base or BASE) / "data" / "universe" / "universe.json") or {}
    known = {str(k).upper() for k in (meta if isinstance(meta, dict) else {})}
    seen: Counter[str] = Counter()
    for r in rows:
        cell = r.get("canonical_cell")
        if not isinstance(cell, str) or "." not in cell:
            continue
        sym = cell.split(".")[0]
        if asset_class(sym) == "crypto":
            seen[sym] += 1
    unregistered = sorted(s for s in seen if known and s.upper() not in known)
    stray = sum(seen[s] for s in unregistered)
    return {"measured": True, "crypto_cfd_symbols": len(seen), "cells": sum(seen.values()),
            "not_in_fusion_registry": unregistered,
            "not_in_fusion_registry_cells": stray,
            "verdict": ("FENCE HOLDS: every crypto symbol in the docket is a Fusion CFD"
                        if not unregistered else
                        f"REVIEW: {len(unregistered)} crypto symbol(s) carrying {stray} cell(s) "
                        f"are absent from TODAY's Fusion registry. That reads as a delisted or "
                        f"renamed CFD far more often than as an exchange-native leak -- but "
                        f"'reads as' is not measured, so it is named here and confirmed on the "
                        f"box against the live symbol list, never assumed either way"),
            "registry_readable": bool(known)}


#: Gates that look mis-specified. NAMED WITH EVIDENCE AND LEFT ALONE -- the standing rule is that
#: a gate is never moved to make a rate look better, and a gate that is too LOOSE is exactly the
#: kind whose repair would lower a conversion rate rather than raise it.
def gate_notes(base: Path) -> list[dict[str, Any]]:
    canon = _json(base / "data" / "UNIVERSAL_SURVIVORS.canon.json")
    policy = (canon or {}).get("gate_policy") if isinstance(canon, dict) else None
    out: list[dict[str, Any]] = []
    if isinstance(policy, dict) and "fixed_campaign_trials" in str(policy.get(
            "trial_count_basis", "")):
        out.append({
            "gate": "deflated_sharpe",
            "finding": "the multiplicity charge does not grow with the search",
            "evidence": str(policy.get("trial_count_basis"))[:220],
            "direction": "TOO LOOSE, not too strict",
            "action": "NONE TAKEN. Reported, not moved. Raising this charge would LOWER the "
                      "certificate count, so it can never be mistaken for a conversion fix -- "
                      "which is exactly why it is safe to name and unsafe to quietly leave "
                      "unnamed. It also means the reallocation this ledger recommends cannot "
                      "game the gate: the charge is identical whatever the trials are spent on.",
        })
    return out


#: The capability-graph node this ledger owes, in the shape `libs/ops/capability_graph.Node`
#: takes. DECLARED HERE because the graph's registry lives outside this desk's research tree; the
#: entry is copied into `libs/ops/capability_graph.NODES` verbatim. Keeping the declaration beside
#: the code it describes is the same discipline the UNDECLARED check enforces upstream, and a test
#: asserts these paths are the ones this module actually touches.
CAPABILITY_NODE: dict[str, Any] = {
    "name": "conversion_ledger",
    "module": "desks/mt5/research/conversion_ledger.py",
    "writes": ("desks/mt5/data/conversion_ledger.json",),
    "reads": ("desks/mt5/data/research_queue.json",
              "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
              "desks/mt5/data/hypothesis_graph.jsonl",
              "desks/mt5/data/hypotheses/miner_deepening_queue.json",
              "desks/mt5/data/intelligence/coverage_registry.json",
              "desks/mt5/reports/OPPORTUNITY_CURVE.json",
              "desks/mt5/reports/allocator_attribution.json",
              "desks/mt5/reports/shadow/shadow_health.json"),
    # It measures. It admits nothing, promotes nothing and sizes nothing.
    "authority": (),
}


def _allocator_node() -> dict[str, Any]:
    try:
        import trial_allocator as ta
        return dict(ta.CAPABILITY_NODE)
    except Exception:
        return {"name": "trial_allocator", "note": "not importable on this host"}


# ------------------------------------------------------------------------------- assembly

def assemble(base: Path | None = None) -> dict[str, Any]:
    """Every stage, the binding one, and the evidence for both."""
    b = base or BASE
    rows = _json(b / "data" / "research_queue.json")
    rows = rows if isinstance(rows, list) else []
    judged = sum(1 for r in rows if r.get("canonical_verdict") in ("PASSED", "REJECTED"))
    try:
        import trial_allocator as ta
        yields = ta.observed(b / "data" / "research_queue.json")
    except Exception:
        yields = []
    stages = [
        stage_world_to_mined(b),
        stage_mined_to_rule(b),
        stage_stagea_to_card(b, judged, len(rows)),
        stage_card_to_verdict(rows),
        stage_verdict_to_certificate(rows, yields),
        stage_certificate_to_enrollable(b),
        stage_enrollable_to_clock(b),
        stage_clock_to_sleeve(b),
        stage_sleeve_to_capital(b),
        stage_expressible_search_space(b),
    ]
    binding = binding_stage(stages)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "authority": "max_h E[log W | entire current world information set]",
        "binding_rule": ("among stages on the critical path AND measured, the lowest conversion "
                         "rate; ties broken by work destroyed. A tributary cannot be binding: "
                         "unblocking it adds nothing downstream this week"),
        "binding_stage": None if binding is None else binding.name,
        "binding_rate": None if binding is None else (
            None if binding.rate is None else round(binding.rate, 6)),
        "binding_reason": None if binding is None else binding.loss_reason,
        "stages": [s.as_dict() for s in stages],
        "unmeasured_stages": [{"stage": s.name, "why": s.loss_reason}
                              for s in stages if not s.measured],
        "cell_type_yield": [y.as_dict() for y in sorted(yields, key=lambda y: -y.tried)[:20]],
        "graveyard_causes": graveyard_causes(b),
        "crypto_fence": crypto_fence(rows, b),
        "gate_notes": gate_notes(b),
        "law": ("no rate in this ledger may be raised by loosening a gate, a threshold, a floor "
                "or a law; a conversion that does not raise robust forward E[log W] is a leak"),
        "capability_nodes": [CAPABILITY_NODE, _allocator_node()],
    }
    try:
        import trial_allocator as ta2
        doc["rent"] = ta2.rent(yields)
    except Exception as exc:
        doc["rent"] = {"module": "trial_allocator", "verdict": "UNMEASURED",
                       "why": f"allocator not importable here ({type(exc).__name__})"}
    return doc


def binding_stage(stages: list[Stage]) -> Stage | None:
    """The constraint: lowest measured rate on the critical path, ties on work destroyed."""
    live = [s for s in stages if s.critical and s.measured and s.rate is not None]
    if not live:
        return None
    return min(live, key=lambda s: (s.rate, -(s.destroyed or 0)))


def run(base: Path | None = None, write: bool = True) -> dict[str, Any]:
    """The organ entry point: measure the whole funnel and publish. Reads only.

    The artifact is written UNDER `base`, not at the module-level default, so a caller measuring
    a synthetic tree cannot overwrite the desk's real ledger -- the mistake a test would make
    once and nobody would notice until the dashboard read a fixture.
    """
    doc = assemble(base)
    if write:
        out = (base or BASE) / "data" / "conversion_ledger.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        doc["artifact"] = str(out)
    # The hourly pass reads its YIELD counters off the report. This organ produces knowledge,
    # not cells: `stages_measured` is what it actually bought, and it is never reported as
    # `candidates`, because an organ that inflates its yield with the wrong noun is the same
    # defect as a stage that counts promises as conversions.
    doc["stages_measured"] = sum(1 for s in doc["stages"] if s["measured"])
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    doc = run()
    if not args.quiet:
        print(f"{'stage':44s} {'in':>8s} {'out':>7s} {'rate':>10s}  reason")
        for s in doc["stages"]:
            rate = "UNMEASURED" if s["rate"] is None else f"{s['rate']:.5%}"
            mark = "*" if s["name"] == doc["binding_stage"] else " "
            print(f"{mark}{s['name']:43s} {s['count_in'] or '-'!s:>8s} "
                  f"{s['count_out'] if s['count_out'] is not None else '-'!s:>7s} "
                  f"{rate:>10s}  {s['loss_reason'][:90]}")
        print(f"\nBINDING: {doc['binding_stage']} at "
              f"{doc['binding_rate']}\n  {doc['binding_reason']}")
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
