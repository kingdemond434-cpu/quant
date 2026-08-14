"""PAPER-SLEEVE AUTO-SPAWN LOGIC (R0102) -- every Stage-A survivor gets a forward clock, LAWFULLY.

THE GAP THIS CLOSES. A SCREEN-INTERESTING verdict that survives the annualization correction and
the campaign multiplicity bar (scripts/finalize_axis_screens.py, `verdict_adjusted`) is the desk's
scarcest research output -- and until now NOTHING converted it into a paper sleeve. Conversion was
a by-hand step, and by-hand steps run at zero when nobody is looking (the desk's most expensive
recurring defect class: built-never-wired). A paper sleeve is costless -- it tests the execution
path and accrues forward evidence, it never touches capital -- so every survivor should get one
AUTOMATICALLY.

THE CONSTRAINT THAT MAKES THIS NON-TRIVIAL (found at triage, 2026-08-05): the forward cohort is at
the Holm cap, 12/12 (libs/research/slot_registry.MAX_FORWARD_SLOTS). A naive auto-spawn would push
`over_cap` and RAISE EVERY STANDING CANDIDATE'S BAR -- each new concurrent clock tightens the Holm
correction for all of them. So the mechanism must QUEUE behind slot retirements, never spawn over
cap, and the fail-safe direction is inherited from the registry: an INCOMPLETE cohort measurement
(any unreadable source) means m is a lower bound, so free slots are treated as ZERO rather than
guessed.

QUEUE ORDER IS THE DEPLOYMENT-RACE LAW (L1.18a, same rule run_promotion_queue.py applies one stage
later): shortest capacity runway first. A long-runway edge loses nothing by waiting a month; a
short-runway edge loses everything -- arrival order systematically sacrifices exactly the edges
that cannot afford to wait. Candidates with UNKNOWN capacity sort LAST (runway inf), because an
unknown-runway edge must never jump ahead of one measurably about to expire.

Pure logic -- no I/O beyond what the caller hands in. The organ is
scripts/run_paper_sleeve_spawner.py.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from libs.research.capacity_policy import growth_runway

__all__ = [
    "Candidate",
    "decide",
    "dedupe",
    "order_queue",
    "parse_full_sweep_candidates",
    "parse_screen_verdicts",
    "slug",
    "standing_names",
]

#: The verdict prefix the desk regards as its STRONGEST Stage-A read. It is a RANKING label and no
#: longer an admission gate -- see ADMISSION below.
QUALIFYING_PREFIX = "SCREEN-INTERESTING"

#: ADMISSION IS BY EV-RANK, NOT BY A STAGE-A VERDICT (the two-stage law, finally implemented).
#:
#: Until 2026-08-05 a candidate was admitted only if `verdict_adjusted` began with
#: SCREEN-INTERESTING. That is a SIGNIFICANCE GATE at Stage A, and the law is explicit that Stage A
#: is a ranking device with ZERO promotion authority -- so the gate handed the ranking device the
#: authority the law withholds from it. The cost was total: of 120 scored cells on disk NONE
#: carried that verdict, so ten of twelve forward slots sat idle and not one clock had ever
#: started. Nothing could survive because nothing was ever tested.
#:
#: What still cannot be admitted is a BROKEN MEASUREMENT, which is a different thing from a weak
#: one: a cell whose alignment gate fired is not a small edge, it is a number that does not mean
#: what it says. SCREEN-WEAK and SCREEN-UNDERPOWERED stay admissible -- "underpowered" means the
#: screen could not see, not that it looked and found nothing (L1.49), and of the desk's 228
#: recorded negatives only 50 were POWERED.
NON_ADMISSIBLE_PREFIXES: tuple[str, ...] = (
    "NOT-A-CANDIDATE", "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD", "NOT-READABLE-HERE",
)

#: Where uncoverted screens live, used to record a candidate's origin artifact.
_AXIS_REL = "reports/axis_screens"

#: Tokens dropped when reducing a trial name to its signal FAMILY. Horizons and parameter settings
#: are variations of one hypothesis, and spending a Holm slot on each is paying multiplicity to
#: learn the same thing twice.
_HORIZON_TOKEN = re.compile(
    r"^(?:h|d|w)?\d+(?:\.\d+)?(?:min|[smhdwy])?$"
    r"|^(?:horizon|window|interval|bar|lag)[_a-z]*\d+(?:\.\d+)?$", re.I)

#: BUILD FORMS -- how one hypothesis was measured, not which hypothesis it is. A causal build and
#: its look-ahead control are the same signal family; spawning both would spend two Holm slots to
#: test one idea (and one of them is a control that can never be promoted anyway).
_FORM_SEGMENT = frozenset({"causal", "naive", "control", "lookahead_control", "shift_control",
                           "per_market", "pooled"})


def slug(text: str) -> str:
    """Sleeve-safe name: lowercase, [a-z0-9_], collapsed. Deterministic so dedupe is stable."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text).lower())).strip("_")


def family_root(trial_name: str) -> str:
    """The signal FAMILY a trial belongs to -- horizons and parameters stripped.

    `root = slug(name.split('->')[0])` was too literal: it left
    liq_reversion_BTCUSDT_5m_S=order-side, _15m_S=order-side and _30m_S=position-side as three
    distinct families, so one hypothesis measured at three horizons and two side-mappings would
    have consumed SIX of twelve forward slots and charged the cohort six times for one bet.

    TAKING THE FIRST SEGMENT WAS THE OPPOSITE ERROR and cost more. It assumed segment one is
    always the signal name -- true for `etf_creation_pressure|causal|h1d`, false for the
    vol-risk-premium vocabulary, where `per_market|AVAX:t90|iv_level|short_vol_carry` begins with
    the LEVEL. Every one of 64 distinct market/construction/target combinations collapsed to the
    single root `per_market`, so 64 independent hypotheses competed for ONE forward slot and 63
    were discarded as duplicates of each other.

    The rule that survives both: drop the segments and tokens that describe HOW a hypothesis was
    measured -- horizons, build forms, parameter settings -- and keep everything that describes
    WHICH hypothesis it is. Different assets, tenors and constructions stay different bets.

    `->` AND `|` ARE NOT THE SAME SEPARATOR, and treating them alike broke a live dedupe. In this
    desk's harness vocabulary `->` means SIGNAL -> TARGET, so everything before it is the signal
    family by construction and `stablecoin_supply_momentum->btc_1d` must match a standing clock
    named `stablecoin_supply_momentum`. `|` is a plain field separator carrying no such ordering,
    which is why its segments have to be filtered rather than truncated.
    """
    raw = str(trial_name)
    if "->" in raw:
        raw = raw.split("->")[0]
    segments = [s for s in raw.split("|") if s.strip()]
    kept_segments: list[str] = []
    for seg in segments:
        low = seg.strip().lower()
        if low in _FORM_SEGMENT or _HORIZON_TOKEN.match(low):
            continue
        toks = [t for t in seg.split("_")
                if t and "=" not in t and not _HORIZON_TOKEN.match(t)
                and t.lower() not in _FORM_SEGMENT]
        if toks:
            kept_segments.append("_".join(toks))
    return slug("_".join(kept_segments) or str(trial_name))


@dataclass(frozen=True)
class Candidate:
    """One qualifying screen survivor. `name` is the sleeve identity; `root` is the signal family
    (trial name before '->'), used for dedupe so two horizons of one signal are one sleeve."""

    name: str
    axis: str
    trial: str
    ic_t: float = 0.0
    sharpe_corrected: float = 0.0
    capacity_usd: float | None = None
    verdict: str = ""
    source: str = ""
    root: str = field(default="")
    #: Carried so slot_admission can price the FORWARD COST of this candidate -- how many calendar
    #: days a clock needs to settle it. Without these the ranker can only see how strong Stage A
    #: thought the effect was, which is the very reading the two-stage law forbids relying on.
    # NONE, NOT 0.0, and the difference is the whole L1.41 rule applied to this dataclass. A
    # default of 0.0 turns "this screen reported no IC" into "this screen measured an IC of zero",
    # and the ranker then prices the cell as UNAFFORDABLE (inf rows to resolve a zero effect) and
    # excludes it on economics -- an exclusion that reads as a judgement when nothing was judged.
    ic: float | None = None
    horizon_days: float | None = None
    n_eff: float = 0.0
    mechanism: str = ""
    decontam_passed: bool = True
    implausible_leak: bool = False
    #: The artifact the cell was SCREENED from, and the key its rows live under. A forward clock
    #: has to re-read that same source every day to accrue, and a sleeve that cannot name its
    #: origin is a clock nobody can run -- born, registered, paying multiplicity, never breathing.
    origin_artifact: str = ""
    origin_key: str = ""
    #: Identifies how the forward runner re-reads this candidate. Axis screens use canonical JSON
    #: rows; the full sweep uses a provenance-carrying NPZ return panel.
    source_kind: str = "axis_screen"
    pnl_key: str = ""
    baseline_window_end: str = ""

    def dedupe_keys(self) -> set[str]:
        # AXIS IS NOT A DEDUPE KEY. It once was, and with conversion in place a single converted
        # artifact carries dozens of independent hypotheses under one axis name -- so the first
        # candidate spawned would have blocked every other cell in its own file.
        return {k for k in (self.name, self.root) if k}

    def as_rank_row(self, book_usd: float | None = None) -> dict[str, Any]:
        return {"name": self.name, "axis": self.axis, "mechanism_class": self.mechanism,
                "ic": self.ic, "horizon_days": self.horizon_days, "n_eff": self.n_eff,
                "decontam_passed": self.decontam_passed,
                "implausible_leak": self.implausible_leak,
                # L1.18a deployment race, handed to the ranker as its tie-break rather than
                # applied afterwards -- a re-sort of the ADMITTED list cannot change who was
                # admitted, which is the decision the law is actually about.
                "runway": runway_of(self, book_usd)}


def _capacity_of(trial: dict[str, Any]) -> float | None:
    for key in ("capacity_usd", "capacity"):
        v = trial.get(key)
        if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) > 0:
            return float(v)
    return None


def parse_screen_verdicts(reports_dir: Path) -> dict[str, Any]:
    """Read every axis-screen report carrying corrected verdicts; return candidates + provenance.

    The verdict store is the artifact scripts/finalize_axis_screens.py writes:
    reports/axis_screens/<axis>.json with per-trial `verdict_adjusted`. Files WITHOUT that field
    are raw harness output the correction layer never processed -- they are counted as scanned but
    can qualify nothing, because the uncorrected Sharpe is inflated up to 4.47x at 20d.

    Refusal is a RESULT, not an exception: `status` is REFUSED-NO-INPUT when the store is absent
    or holds no corrected verdicts, and the caller must not spawn from it.
    """
    import json

    files_scanned, files_with_verdicts, trials_seen = [], [], 0
    candidates: list[Candidate] = []
    if reports_dir.is_dir():
        for p in sorted(reports_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue                       # unreadable file cannot qualify anything
            files_scanned.append(p.name)
            trials = doc.get("trials") if isinstance(doc, dict) else None
            if not isinstance(trials, list):
                continue
            corrected = [t for t in trials
                         if isinstance(t, dict) and isinstance(t.get("verdict_adjusted"), str)]
            if not corrected:
                continue
            files_with_verdicts.append(p.name)
            axis = str(doc.get("axis", p.stem))
            mechanism = str(doc.get("mechanism_class") or doc.get("mechanism") or axis)
            for t in corrected:
                trials_seen += 1
                if t.get("is_candidate") is False:
                    continue                   # controls / diagnostics: never promotable
                verdict = str(t["verdict_adjusted"])
                if any(verdict.startswith(p_) for p_ in NON_ADMISSIBLE_PREFIXES):
                    continue                   # BROKEN measurement, not a weak one
                trial_name = str(t.get("name", ""))
                ic = t.get("residual_ic")
                ic = t.get("ic") if not isinstance(ic, (int, float)) else ic
                candidates.append(Candidate(
                    name=slug(f"{axis}_{trial_name}"), axis=axis, trial=trial_name,
                    ic_t=float(t.get("ic_t_stat") or 0.0),
                    sharpe_corrected=float(t.get("sharpe_best_corrected") or 0.0),
                    capacity_usd=_capacity_of(t), verdict=verdict, source=p.name,
                    root=family_root(trial_name),
                    ic=float(ic) if isinstance(ic, (int, float)) else None,
                    horizon_days=(float(t["horizon_days"])
                                  if isinstance(t.get("horizon_days"), (int, float)) else None),
                    n_eff=float(t.get("n_eff") or t.get("n") or 0.0),
                    mechanism=str(t.get("mechanism_class") or mechanism),
                    decontam_passed=bool(t.get("decontam_passed", True)),
                    implausible_leak=bool(t.get("implausible_leak", False)),
                    origin_artifact=str(doc.get("converted_from") or f"{_AXIS_REL}/{p.name}"),
                    origin_key=str(doc.get("converted_key") or "trials")))

    if not files_with_verdicts:
        return {"status": "REFUSED-NO-INPUT", "candidates": [],
                "files_scanned": files_scanned, "trials_seen": 0,
                "why": (f"{reports_dir} absent" if not reports_dir.is_dir() else
                        f"{len(files_scanned)} report(s) scanned, NONE carries verdict_adjusted "
                        "-- the correction layer (finalize_axis_screens) has not run, and raw "
                        "harness verdicts are inflated up to 4.47x at 20d, so nothing may spawn "
                        "from them")}

    # One sleeve per signal FAMILY: two horizons of one construction are one bet, and spawning
    # both would spend two Holm slots on one hypothesis. The keeper is the FASTEST-RESOLVING
    # member, not the strongest -- a slot's scarce resource is calendar time, and the family's
    # 30-minute variant settles the same question in 24 days that its 5-minute variant needs 45
    # for. Ties break on evidence, then name, so two runs always agree.
    by_root: dict[str, Candidate] = {}
    for c in sorted(candidates, key=lambda c: (_resolve_days_of(c), -c.ic_t, c.name)):
        by_root.setdefault(c.root or c.name, c)
    kept = sorted(by_root.values(), key=lambda c: c.name)
    return {"status": "OK" if kept else "NO-CANDIDATES", "candidates": kept,
            "files_scanned": files_scanned, "files_with_verdicts": files_with_verdicts,
            "trials_seen": trials_seen,
            "why": "" if kept else (
                f"{trials_seen} corrected trial(s), every one of them a CONTROL, a diagnostic, or "
                f"a broken measurement ({', '.join(NON_ADMISSIBLE_PREFIXES)}). Admission is by "
                "EV-rank, not by a Stage-A significance verdict, so a store with any intact "
                "candidate in it would produce one here -- this store has none.")}


def parse_full_sweep_candidates(report_path: Path) -> dict[str, Any]:
    """Convert full-sweep Stage-A inventory into one candidate per independent mechanism.

    The report's nine formulas are not nine bets: its own return clustering says two independent
    mechanisms. Paying nine Holm slots would reward formula duplication and tighten every clock.
    This converter therefore keeps the highest-|t| representative of each measured cluster. It
    grants no statistical or capital authority; a paper clock is a zero-capital measurement.
    """
    import json

    try:
        doc = json.loads(report_path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"status": "REFUSED-NO-INPUT", "candidates": [],
                "why": f"{report_path} absent or unreadable"}

    rows = doc.get("survivors") if isinstance(doc, dict) else None
    independence = doc.get("independence") if isinstance(doc, dict) else None
    clusters = independence.get("clusters") if isinstance(independence, dict) else None
    if not isinstance(rows, list) or not rows:
        return {"status": "NO-CANDIDATES", "candidates": [],
                "formula_survivors": 0, "independent_clusters": 0,
                "why": "full sweep carries no Stage-A survivors"}
    if not isinstance(clusters, list) or not clusters:
        return {"status": "REFUSED-UNMEASURED-INDEPENDENCE", "candidates": [],
                "formula_survivors": len(rows), "independent_clusters": None,
                "why": ("full sweep has Stage-A formulas but no measured independence clusters; "
                        "spawning one clock per formula would spend multiplicity on duplicates")}

    by_key = {"|".join(str(x) for x in r.get("key", [])): r
              for r in rows if isinstance(r, dict)}
    sample = doc.get("sample") if isinstance(doc.get("sample"), dict) else {}
    bar_s = float(sample.get("bar_seconds") or 0.0)
    window = sample.get("window") if isinstance(sample.get("window"), list) else []
    window_end = str(window[-1]) if window else ""
    out: list[Candidate] = []
    for cluster_i, raw_cluster in enumerate(clusters, 1):
        found = [by_key.get(str(k)) for k in raw_cluster] if isinstance(raw_cluster, list) else []
        members: list[dict[str, Any]] = [r for r in found if isinstance(r, dict)]
        if not members:
            continue
        # One measured cluster gets one clock. Highest |t| is a deterministic representative;
        # admission itself remains cost-ranked by decide().
        row = sorted(members, key=lambda r: -abs(float(r.get("t") or 0.0)))[0]
        key = "|".join(str(x) for x in row.get("key", []))
        h_bars = max(1.0, float(row.get("horizon_bars") or 1.0))
        horizon_days = h_bars * bar_s / 86400.0 if bar_s > 0 else None
        out.append(Candidate(
            name=slug("full_sweep_" + key)[:180],
            axis="full_sweep",
            trial=key,
            ic_t=float(row.get("t") or 0.0),
            sharpe_corrected=0.0,
            capacity_usd=None,
            verdict="STAGE-A F1-F6; ZERO PROMOTION AUTHORITY",
            source=report_path.name,
            root=f"full_sweep_cluster_{cluster_i}",
            ic=(float(row["ic"]) if isinstance(row.get("ic"), (int, float)) else None),
            horizon_days=horizon_days,
            n_eff=float(row.get("n") or 0.0) / h_bars,
            mechanism=f"full_sweep_independent_cluster_{cluster_i}",
            decontam_passed=True,
            implausible_leak=False,
            origin_artifact="data/full_sweep.json",
            origin_key="survivors",
            source_kind="full_sweep_npz",
            pnl_key=key,
            baseline_window_end=window_end,
        ))
    return {"status": "OK" if out else "NO-CANDIDATES", "candidates": out,
            "formula_survivors": len(rows), "independent_clusters": len(clusters),
            "why": "" if out else "independence clusters contained no resolvable survivor keys"}


def _resolve_days_of(c: Candidate) -> float:
    """Calendar days a forward clock needs, or inf when the cost is UNMEASURED. Both unmeasured
    and unaffordable sort last here; only the ranker distinguishes them, and it must."""
    import math

    from libs.research.slot_admission import forward_resolution_days
    if c.ic is None or c.horizon_days is None:
        return math.inf
    return forward_resolution_days(c.ic, c.horizon_days)[0]


def standing_names(slots_payload: dict[str, Any], data_dir: Path,
                   queue_doc: dict[str, Any] | None = None) -> set[str]:
    """Every sleeve identity already standing -- spawning one of these again is a duplicate.

    Three sources, union'd, because each covers a failure of the others: the derived cohort
    (axis + standing + derivative clocks, the registry's own occupancy), the on-disk
    `*_shadow_state.json` files (covers a sleeve whose roster write crashed mid-spawn), and the
    queue document's own `spawned` ledger (covers a state file swept away by a data reset).
    """
    names: set[str] = set()
    for s in slots_payload.get("slots", []) if isinstance(slots_payload, dict) else []:
        if isinstance(s, dict) and s.get("name"):
            names.add(slug(str(s["name"])))
    if data_dir.is_dir():
        for p in data_dir.glob("*_shadow_state.json"):
            stem = p.name[: -len("_shadow_state.json")]
            if stem:
                names.add(slug(stem))
    for row in (queue_doc or {}).get("spawned", []):
        if isinstance(row, dict) and row.get("name"):
            names.add(slug(str(row["name"])))
    return names


def dedupe(candidates: list[Candidate],
           standing: set[str]) -> tuple[list[Candidate], list[dict[str, Any]]]:
    """Split candidates into (fresh, duplicates). A candidate whose name, signal root, or axis is
    already a standing clock is a duplicate: its hypothesis is ALREADY accruing forward evidence,
    and a second clock on it would spend a Holm slot to learn nothing new."""
    fresh, dupes = [], []
    for c in candidates:
        hit = sorted(c.dedupe_keys() & standing)
        if hit:
            dupes.append({"name": c.name, "matched_standing": hit,
                          "why": "already accruing -- a second clock on one hypothesis spends a "
                                 "Holm slot to learn nothing new"})
        else:
            fresh.append(c)
    return fresh, dupes


def runway_of(c: Candidate, book_usd: float | None = None) -> float:
    """Capacity runway in multiples of the current book; inf when capacity is UNMEASURED.

    inf is the deliberate direction: an unknown-runway candidate must never jump the queue ahead
    of one measurably about to expire, and treating unknown as short would let every capacity-less
    screen cut the line.
    """
    if c.capacity_usd is None:
        return math.inf
    return float(growth_runway(c.capacity_usd, book_usd=book_usd))


def order_queue(candidates: list[Candidate],
                book_usd: float | None = None) -> list[Candidate]:
    """Deployment-race order: SHORTEST capacity runway first (L1.18a), then strongest evidence,
    then name -- fully deterministic so two runs agree on who is next."""
    return sorted(candidates, key=lambda c: (runway_of(c, book_usd), -c.ic_t, c.name))


def free_slots(cohort: dict[str, Any]) -> tuple[int, str]:
    """(spawnable count, why). NEVER positive on an incomplete or over-cap cohort.

    The registry's fail-safe carries through: `complete=False` means some source was unreadable and
    m_concurrent is a LOWER BOUND -- spawning against a lower bound is how a cap gets breached
    while every number on screen says it was not.
    """
    cap = int(cohort.get("cap", 0))
    # THE UPPER BOUND, not the counted one. `m_concurrent` omits whatever an unreadable source was
    # hiding, so spawning against it can breach the cap; `m_upper` adds each unreadable source's
    # own maximum, so `cap - m_upper` is a count of slots that are free NO MATTER what those
    # sources hold. Falls back to the counted value only for a registry payload predating the
    # bound, and then keeps the old blanket refusal.
    # SEATS, NOT MULTIPLICITY (2026-08-14). This is a CAPACITY question -- "is there room for
    # another clock?" -- and `m_upper` stopped being a capacity number when it became the
    # high-water mark that keeps the Holm bar from loosening on retirement. Reading it here would
    # hold the desk permanently over cap on the strength of clocks already retired: idleness
    # bought with a figure that exists to protect the bar, and it protects nothing by being spent
    # here. `seats_upper` carries the same fail-safe bounding of unreadable sources.
    m = int(cohort.get("seats_upper", cohort.get("m_upper", cohort.get("m_concurrent", cap))))
    if "seats_upper" not in cohort and "m_upper" not in cohort \
            and not cohort.get("complete", False):
        return 0, ("cohort INCOMPLETE and unbounded (registry payload carries no m_upper) -- "
                   f"m={m} is a lower bound, so free slots are treated as ZERO rather than guessed")
    if cohort.get("over_cap") or m >= cap:
        return 0, f"cohort at/over cap ({m}/{cap}) -- queue behind retirements, never spawn over"
    detail = ""
    if not cohort.get("complete", False):
        # NOT A REASON TO STOP. An unknown that can be BOUNDED must be bounded (L1.54): the
        # blanket zero here is what left ten slots idle and no clock ever started.
        detail = (f" -- {len(cohort.get('unknown_sources') or [])} unreadable source(s) bounded "
                  f"into m_upper={m}, so these slots are free whatever those sources hold")
    return cap - m, f"{cap - m} free slot(s) ({m}/{cap} at the upper bound){detail}"


def decide(candidates: list[Candidate], standing: set[str], cohort: dict[str, Any],
           book_usd: float | None = None) -> dict[str, Any]:
    """spawn-vs-queue for one run, by EV-RANK (the two-stage law's own admission rule).

    Ranking is by TIME-TO-RESOLUTION -- how many calendar days a forward clock needs to settle the
    cell against the cohort's own Holm bar -- with an orthogonality cap so a dozen slots cannot all
    go to one mechanism. Capacity runway (L1.18a) still breaks ties among candidates that resolve
    equally fast, because a short-runway edge loses everything by waiting while a long-runway one
    loses nothing.

    NO BAR MOVES HERE. The Holm z is READ from the cohort to price the wait; admitting clocks
    RAISES m and therefore TIGHTENS every standing candidate's bar.
    """
    from libs.research.slot_admission import rank as ev_rank

    fresh, dupes = dedupe(candidates, standing)
    n_free, why_free = free_slots(cohort)
    m_cohort = int(cohort.get("m_upper", cohort.get("cap", 12)) or 12)
    by_name = {c.name: c for c in fresh}
    ranking = ev_rank([c.as_rank_row(book_usd) for c in fresh], n_slots=n_free,
                      m_cohort=m_cohort)

    admitted = [by_name[r["name"]] for r in ranking["admitted"] if r["name"] in by_name]
    deferred_names = [r["name"] for r in ranking["deferred"] if r["name"] in by_name]
    queued = order_queue([by_name[n] for n in deferred_names], book_usd)
    return {
        "spawn": admitted, "queue": queued, "duplicates": dupes,
        "free_slots": n_free, "why_free": why_free,
        "ranking": ranking,
        "order_law": ("EV-rank by TIME-TO-RESOLUTION (two-stage law, slot admission): fastest "
                      "forward clock first, orthogonality-capped per mechanism. A Stage-A "
                      "significance verdict is NOT an admission gate -- Stage A has zero "
                      "promotion authority, so gating on it hands the ranking device the "
                      "authority the law withholds. Ties fall back to L1.18a deployment race: "
                      "shortest capacity runway first, unknown capacity LAST."),
    }
