"""CONDITIONAL-ALPHA LIFECYCLE -- stage SECOND of the pre-DeepSeek gate, on EXISTING machinery.

WHAT THIS IS. The mandate's III (regime-conditional alpha preservation) demands five lifecycle
states -- ACTIVE, THROTTLED, HIBERNATING, PROBATION, RETIRED -- and three behaviors the desk did
not have: a weak-unconditional candidate with robust conditional edge must reach a CONDITIONAL
track instead of incorrect rejection (gate item 5); a conditional survivor must hibernate
preserving FULL state (item 6); reactivation must route through canonical revalidation, never
straight back to ACTIVE (item 7). This module is that lifecycle, as an append-only ledger plus a
router.

WHAT THIS DELIBERATELY IS NOT, and both refusals are load-bearing:

  * NOT A SECOND SURVIVOR REGISTRY. The Two-Stage Discovery Law stands: Stage B forward clocks
    (slot_registry / paper_sleeves) remain the SOLE promotion authority. Nothing here promotes,
    sizes, or touches capital. `reactivate()` does not even exist -- the only exit from
    HIBERNATING is REVALIDATION_PENDING, whose named consumer is the existing forward-clock
    spawner. A lifecycle that could promote would be the parallel universe the mandate forbids.

  * NOT A LOOSENING. A candidate rejected unconditionally does not get rescued by this module --
    it gets a NEW HYPOTHESIS record (mandate III-B: post-hoc regime discovery is a new
    hypothesis, never retroactive validation), stamped with the regime search breadth so the
    multiplicity charge is carried, not hidden. The statistical bars are the existing ones and
    they are not touched here.

REGIME EVIDENCE comes from the machinery the desk already owns: libs/research/crypto_regime
labels days by lagged trend/vol/funding axes (no look-ahead). This module consumes those labels'
VOCABULARY -- a regime signature is a dict over those axes -- and never invents its own regime
classifier (mandate 0: reuse behaviorally equivalent machinery).

STORAGE follows the desk idiom: append-only JSONL, rows never rewritten, current state derived
by folding the ledger. History is evidence; a lifecycle whose past can be edited cannot support
failure attribution (III-G).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "LEDGER", "STATES", "LifecycleError", "conditional_track", "current_states",
    "hibernate", "mark_revalidation_pending", "reality_gaps", "record",
]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "data/alpha_lifecycle.jsonl"

#: The mandate's five states plus the one transitional state that keeps promotion authority where
#: it already lives. REVALIDATION_PENDING is deliberately NOT "active": it means "the favorable
#: economics credibly returned and the CANONICAL machinery now owes this name a fresh forward
#: clock" -- the clock, not this ledger, decides what happens next.
STATES: tuple[str, ...] = (
    "ACTIVE", "THROTTLED", "HIBERNATING", "PROBATION", "RETIRED", "REVALIDATION_PENDING",
)

#: Conditional-track admission floors. These are ADMISSION-TO-A-TRACK floors, not promotion bars
#: -- promotion still costs a full forward clock. They exist so the track cannot become a dumping
#: ground: a "conditional edge" seen on 9 days in one hand-picked regime is not evidence, it is
#: the curve-fitting III-B names.
MIN_CONDITIONAL_OBS = 60          #: fewer in-regime observations is UNDERPOWERED, not "an edge"
MIN_REGIMES_DECLARED = 1          #: the searched-breadth field is mandatory, never defaulted


class LifecycleError(ValueError):
    """A transition the lifecycle refuses. Raised loudly -- a refused transition that returns
    None would let a caller believe the state changed (fail-visible, mandate II-D)."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class _Row:
    name: str
    state: str
    why: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"ts": _now(), "name": self.name, "state": self.state,
                "why": self.why, **self.payload}


def record(row: _Row, root: Path | None = None) -> dict[str, Any]:
    """Append one lifecycle event. The ledger is the state; there is no other store to drift."""
    base = root or _ROOT
    if row.state not in STATES:
        raise LifecycleError(f"unknown lifecycle state {row.state!r}; valid: {STATES}")
    doc = row.as_dict()
    path = base / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return doc


def _rows(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or _ROOT
    out: list[dict[str, Any]] = []
    try:
        text = (base / LEDGER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue                      # preserved on disk; unreadable rows are still history
    return out


def current_states(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """name -> latest lifecycle row. Derived by folding, so the ledger stays append-only."""
    out: dict[str, dict[str, Any]] = {}
    for row in _rows(root):
        name = str(row.get("name", ""))
        if name:
            out[name] = row
    return out


# ------------------------------------------------------------------ gate item 5: the track
def conditional_track(name: str, *,
                      unconditional_verdict: str,
                      regime_signature: dict[str, str],
                      conditional_obs: int,
                      conditional_sharpe: float | None,
                      regimes_searched: int,
                      mechanism: str,
                      root: Path | None = None) -> dict[str, Any]:
    """Route a weak-unconditional candidate onto the CONDITIONAL track -- as a NEW HYPOTHESIS.

    THE POINT (gate item 5): before this existed, 'failed unconditionally' was a terminal verdict
    and a genuine specialist edge died with it -- the exact false negative L1.49 (weak is not
    dead) and mandate III name. This does NOT overturn the unconditional verdict, which stands
    unchanged in its own artifact. It opens a separately-charged hypothesis whose regime is part
    of the identity, so the forward clock that tests it tests THE CONDITIONAL CLAIM.

    REFUSALS, all fail-visible:
      * an empty regime signature -- "works sometimes" is not an identifiable regime;
      * conditional_obs below the floor -- an UNDERPOWERED cell is unknown, not an edge;
      * regimes_searched not declared -- the multiplicity charge travels with the hypothesis or
        the hypothesis does not travel (III-B: regime search cannot become curve fitting).
    """
    if not regime_signature or not all(str(v).strip() for v in regime_signature.values()):
        raise LifecycleError(
            f"{name}: conditional track needs an IDENTIFIABLE regime signature; got "
            f"{regime_signature!r}. 'Works sometimes' is not a regime (mandate III-A)")
    if conditional_obs < MIN_CONDITIONAL_OBS:
        raise LifecycleError(
            f"{name}: {conditional_obs} in-regime observations is below the "
            f"{MIN_CONDITIONAL_OBS}-obs admission floor -- UNDERPOWERED, not an edge. The track "
            "is not a place to park hope (III-B)")
    if regimes_searched < MIN_REGIMES_DECLARED:
        raise LifecycleError(
            f"{name}: regimes_searched must be declared (got {regimes_searched}). The search "
            "breadth is the multiplicity charge and it travels with the hypothesis or the "
            "hypothesis does not travel (III-B)")
    return record(_Row(
        name=name, state="PROBATION",
        why=("CONDITIONAL-TRACK ADMISSION as a NEW HYPOTHESIS (mandate III-B: post-hoc regime "
             "discovery is never retroactive validation). The unconditional verdict "
             f"({unconditional_verdict!r}) stands unchanged. Promotion authority remains the "
             "Stage-B forward clock alone"),
        payload={
            "track": "CONDITIONAL",
            "unconditional_verdict": unconditional_verdict,
            "regime_signature": regime_signature,
            "conditional_obs": conditional_obs,
            "conditional_sharpe": conditional_sharpe,
            "regimes_searched": regimes_searched,
            "mechanism": mechanism,
            "next_consumer": ("scripts/run_paper_sleeve_spawner.py -- a forward clock scoped to "
                              "the regime signature; this ledger cannot promote"),
        }), root)


# ------------------------------------------------------------------ gate item 6: hibernation
#: Everything hibernation must carry to be reversible. A hibernation that loses any of these is
#: a retirement wearing a softer name -- III-E lists them and the list is enforced, not advised.
_HIBERNATE_REQUIRED: tuple[str, ...] = (
    "regime_signature", "evidence_artifacts", "parameters",
    "reactivation_conditions", "shadow_monitor",
)


def hibernate(name: str, *, why: str, state_snapshot: dict[str, Any],
              root: Path | None = None) -> dict[str, Any]:
    """HIBERNATE preserving full state (gate item 6). Refuses a lossy snapshot loudly."""
    missing = [k for k in _HIBERNATE_REQUIRED
               if k not in state_snapshot or state_snapshot[k] in (None, "", [], {})]
    if missing:
        raise LifecycleError(
            f"{name}: hibernation snapshot is LOSSY -- missing {missing}. A hibernation that "
            "cannot name its reactivation conditions or its evidence is a retirement wearing a "
            "softer name (mandate III-E), and the desk would rediscover that only when "
            "reactivation is impossible")
    return record(_Row(
        name=name, state="HIBERNATING",
        why=f"HIBERNATED, state preserved: {why}",
        payload={"snapshot": state_snapshot}), root)


# ------------------------------------------------------------------ gate item 7: reactivation
def mark_revalidation_pending(name: str, *, evidence: str,
                              root: Path | None = None) -> dict[str, Any]:
    """The ONLY exit from HIBERNATING -- and it is not ACTIVE.

    Gate item 7: reactivation routes through canonical revalidation. This function refuses to
    run unless the name is currently HIBERNATING, and the state it grants is
    REVALIDATION_PENDING: an IOU against the existing forward-clock machinery, which alone can
    make anything active again. There is deliberately no reactivate() in this module.
    """
    cur = current_states(root).get(name, {})
    if cur.get("state") != "HIBERNATING":
        raise LifecycleError(
            f"{name}: revalidation can only be requested from HIBERNATING (currently "
            f"{cur.get('state') or 'UNTRACKED'!s}). Anything else would let this ledger mint "
            "active alphas, which is Stage B's authority and nobody else's")
    snapshot = cur.get("snapshot", {})
    return record(_Row(
        name=name, state="REVALIDATION_PENDING",
        why=(f"reactivation conditions credibly met: {evidence}. NOT reactivated -- routed to "
             "canonical revalidation. A hibernated alpha re-enters through a fresh forward "
             "clock or not at all (mandate III-F)"),
        payload={"snapshot": snapshot,
                 "next_consumer": "scripts/run_paper_sleeve_spawner.py (fresh forward clock; "
                                  "prior accrual is context, never credit)"}), root)


# ------------------------------------------------------------------ gate item 8 (local half)
def reality_gaps(root: Path | None = None, *,
                 regime_now: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Regime-policy reality gaps, as data a fence can consume (gate item 8's detector).

    Three gap classes from mandate III-J, each one a named defect rather than prose:
      * REVALIDATION_STALLED  -- REVALIDATION_PENDING with no forward clock started; the IOU is
                                 being ignored, which quietly converts hibernation to retirement.
      * REACTIVATION_DUE      -- HIBERNATING whose recorded regime signature matches the current
                                 regime labels; favorable conditions returned and nothing moved.
      * SNAPSHOT_LOSSY        -- a HIBERNATING row whose snapshot lost required keys (can only
                                 happen to rows written outside hibernate(); still a defect).
    """
    gaps: list[dict[str, str]] = []
    states = current_states(root)
    base = root or _ROOT
    for name, row in states.items():
        state = row.get("state")
        if state == "REVALIDATION_PENDING":
            # The canonical consumer marks progress by starting a shadow clock for the name.
            if not (base / "data" / f"{name}_shadow_state.json").exists():
                gaps.append({"name": name, "gap": "REVALIDATION_STALLED",
                             "why": "REVALIDATION_PENDING but no forward clock has started -- "
                                    "the IOU against Stage B is being ignored, which quietly "
                                    "converts a hibernation into a retirement (III-J)"})
        elif state == "HIBERNATING":
            snap = row.get("snapshot", {})
            missing = [k for k in _HIBERNATE_REQUIRED if k not in snap]
            if missing:
                gaps.append({"name": name, "gap": "SNAPSHOT_LOSSY",
                             "why": f"hibernation snapshot missing {missing} -- reactivation "
                                    "is impossible without them (III-E)"})
            elif regime_now:
                sig = snap.get("regime_signature", {})
                if sig and all(regime_now.get(k) == v for k, v in sig.items()):
                    gaps.append({"name": name, "gap": "REACTIVATION_DUE",
                                 "why": f"current regime {regime_now} matches the recorded "
                                        f"favorable signature {sig} and no revalidation has "
                                        "been requested -- favorable conditions returned and "
                                        "nothing moved (III-F/III-J)"})
    return gaps
