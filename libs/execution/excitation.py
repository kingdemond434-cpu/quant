"""EXECUTION EXCITATION -- bounded, pre-registered randomisation of the desk's OWN order knobs.

WHY THIS EXISTS (capability hunt 2026-08-01, control-theory transfer: dual control / persistent
excitation, Feldbaum 1960; Astrom-Wittenmark). The desk runs a CERTAINTY-EQUIVALENCE controller:
it estimates execution cost from its own fills, then GATES on that estimate. A controller that
only ever regulates converges to a SELF-CONFIRMING model -- correct on-policy, arbitrarily wrong
off-policy -- and when the controller also gates on it, the reachable set becomes ABSORBING.

The cycle, every file individually correct (verified 2026-08-01):

    run_recorder.py:96      _universe() = [_BENCH, _book_symbols(), _recently_traded(), _CORE][:32]
    run_cost_model.py:27    walks data/moat/{spot,fut}/SYM only -- only RECORDED symbols measurable
    executor:_rt_bps        unmeasured -> _DEFAULT_RT_BPS = 39.5 (p90, fail-closed)
    executor:_entry_gate    funding*1e4*periods > _rt_bps(sym)

    => never traded => never recorded => never measured => expensive => never traded. FOREVER.

`traded -> recorded -> measured -> cheap -> traded` is a closed cycle with no entry path; the only
ways in are two hardcoded tuples. The fail-closed default is GOOD engineering (its own comment
reasons it correctly: "'Unmeasured' is NOT a random subset"). Its COMPOSITION with the recorder's
traded-set universe is what welds the gate, and no single-file review can see that.

THE SECOND HALF, and it is the one that makes this a law rather than a patch: the desk is
fanatical about exploration in RESEARCH (L1.9, L1.25a "null streaks throttle nothing", L1.31
"exploration is resource-bound, never information-bound") and ran ZERO exploration in EXECUTION.
L1.11(b) mandates an Execution Reality Model built from our own fills; every artifact read that as
RECORD WHAT HAPPENS. Nothing read it as MAKE WHAT HAPPENS INFORMATIVE.

WHAT AN ARM MAY VARY -- and this boundary is the whole safety argument:

    IT VARIES *HOW*, NEVER *HOW MUCH*.

`maker_wait_s` -- how long a post-only quote may rest before crossing -- and nothing else. Position
size, leverage, the entry gate, the bleed denylist, the stop plan and every rail are untouched by
construction: this module has no vocabulary for size. The worst case of a wait arm is a fill a few
seconds later at a marginally different price; that is the entire downside, and it is bounded by
`daily_notional_cap_usd`.

CLOSES ARE NEVER EXCITED. `assign()` refuses the close side outright. A close is a CERTAINTY
problem, not a fee problem (executor:1235, incident #6: post-only closes bought a short through
zero into a +916,772 long, twice). The risk path must never be slowed for an experiment.

THE OBSERVATIONAL DATA CANNOT ANSWER THIS, WHICH IS THE POINT. Today `_MAKER_WAIT_OPEN=240.0` is
used iff spot_side == "BUY" and `_MAKER_WAIT=8.0` iff spot_side == "SELL" (executor:1246). Wait is
a DETERMINISTIC FUNCTION of side, so wait and side are perfectly collinear and no regression on
own fills can ever separate "opens cost less because they wait" from "opens cost less because they
are opens". No quantity of observational fills fixes that -- only intervention does.

A CELL WITH n_observed == 0 REPORTS UNIDENTIFIED, NEVER A PRIOR (L1.28a: unmeasured counts as
zero, applied to the cost surface). That refusal is the module's core discipline: the failure this
whole file exists to prevent is a confident number standing in for an unmeasured one.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESIGN = Path("data/excitation_design.json")

# The baseline arm reproduces TODAY'S behaviour exactly. It must always exist and must always be
# the modal assignment: excitation is a bounded perturbation of a working controller, never a
# replacement for it.
BASELINE_ARM = "baseline"

# Bounded epsilon. At 0.25, three quarters of opens run exactly as they do today; the quarter that
# does not is what buys the identifying variation. This is a DESIGN parameter, pre-registered in
# the artifact and never chosen per-order.
DEFAULT_EPSILON = 0.25

# Hard daily cap on the NOTIONAL placed under a non-baseline arm (L1.28a: a declared, capped,
# reported budget -- a ceiling that must be spent or explained). Not a risk limit: the arm cannot
# change size, so this caps the notional EXPOSED TO A DIFFERENT WAIT, which is the only thing an
# arm can influence.
DEFAULT_DAILY_CAP_USD = 2000.0


@dataclass(frozen=True)
class Arm:
    """One assigned experimental condition. `baseline` is True iff this reproduces today's path."""

    name: str
    maker_wait_s: float
    cell: str
    seed: str
    baseline: bool
    reason: str

    def as_tape_fields(self) -> dict[str, Any]:
        """The fields persisted onto the execution tape -- the identification dataset itself.

        Written on EVERY order including baseline ones: an experiment whose control arm is not
        recorded has no control. `exc_baseline` is what lets the fit separate the assigned
        condition from the ambient one.
        """
        return {
            "exc_arm": self.name,
            "exc_wait_s": self.maker_wait_s,
            "exc_cell": self.cell,
            "exc_seed": self.seed,
            "exc_baseline": self.baseline,
        }


@dataclass
class Design:
    """The pre-registered design, loaded from data/excitation_design.json.

    PRE-REGISTERED means the arms, the epsilon and the cap are fixed in the artifact BEFORE the
    fills arrive. Choosing an arm per-order from a live estimate would be an adaptive policy whose
    own selection is confounded with the outcome -- the identification failure this module exists
    to remove, re-created one level up.
    """

    arms: dict[str, float]
    epsilon: float
    daily_notional_cap_usd: float
    cells: dict[str, dict[str, Any]] = field(default_factory=dict)
    loaded: bool = True
    note: str = ""

    @property
    def real_cells(self) -> dict[str, dict[str, Any]]:
        """The design grid proper. `_`-prefixed keys are METADATA, not cells.

        The artifact carries `_measured_symbols` (a map) and `_measured_note` (a string) inside
        `cells` so the tiering data travels with the grid it tiers. Treating those as cells
        crashed this property on its first run -- and a crash here is the benign direction; the
        dangerous one would have been counting a note as an observed cell and reporting a design
        better identified than it is.
        """
        return {k: v for k, v in self.cells.items()
                if not k.startswith("_") and isinstance(v, dict)}

    @property
    def unidentified_cells(self) -> list[str]:
        """Cells with zero observations. These report UNIDENTIFIED and never yield a coefficient."""
        return sorted(k for k, v in self.real_cells.items()
                      if int(v.get("n_observed", 0) or 0) <= 0)


def _fallback_design(note: str) -> Design:
    """A design that CANNOT excite. Used when the artifact is missing or malformed.

    epsilon=0.0 means every assignment returns baseline, so an unreadable design degrades to
    exactly today's behaviour rather than to random behaviour. The reason is carried on every Arm
    so the tape records WHY a run produced no variation -- check_excitation.py reads that and
    reports NO-EXCITATION rather than OK. An unreadable design must never look like a healthy one.
    """
    return Design(arms={BASELINE_ARM: 240.0}, epsilon=0.0,
                  daily_notional_cap_usd=0.0, loaded=False, note=note)


def load_design(path: Path = _DESIGN) -> Design:
    """Read the pre-registered design. Never raises -- degrades to a non-exciting design."""
    if not path.exists():
        return _fallback_design(f"design artifact absent: {path}")
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _fallback_design(f"design unreadable: {e!r}")
    try:
        arms = {str(k): float(v) for k, v in dict(raw["arms"]).items()}
        eps = float(raw.get("epsilon", DEFAULT_EPSILON))
        cap = float(raw.get("daily_notional_cap_usd", DEFAULT_DAILY_CAP_USD))
    except (KeyError, TypeError, ValueError) as e:
        return _fallback_design(f"design malformed: {e!r}")
    if BASELINE_ARM not in arms:
        # Without a control arm the design cannot identify anything; refuse rather than run a
        # treatment-only experiment whose effect has nothing to be measured against.
        return _fallback_design("design has no baseline arm -- refusing to excite")
    if not (0.0 <= eps <= 1.0):
        return _fallback_design(f"epsilon {eps} outside [0,1] -- refusing to excite")
    cells = raw.get("cells") if isinstance(raw.get("cells"), dict) else {}
    return Design(arms=arms, epsilon=eps, daily_notional_cap_usd=cap, cells=dict(cells))


def cell_of(symbol: str, notional: float, design: Design) -> str:
    """The design cell this order lands in: (symbol-tier x size-bucket).

    Tier is by MEASURED status, which is the axis the absorbing cycle runs along: a symbol is
    'measured' iff the cost model has it, and the whole defect is that unmeasured names can never
    become measured. Keeping the tier in the cell means the fit can report separately on the two
    populations instead of averaging the cheap measured names over the expensive unmeasured ones.
    """
    tier = "measured" if symbol in design.cells.get("_measured_symbols", {}) else "unmeasured"
    if notional < 250:
        size = "xs"
    elif notional < 1000:
        size = "s"
    elif notional < 5000:
        size = "m"
    else:
        size = "l"
    return f"{tier}:{size}"


def _draw(seed: str) -> float:
    """Deterministic uniform in [0,1) from a seed string.

    Deterministic BY DESIGN, not for convenience: a pre-registered experiment must be replayable.
    Given the tape's recorded seed, any auditor can recompute the exact assignment and verify the
    desk did not choose arms after seeing outcomes. `random.Random()` (executor:1466) is seeded
    from entropy and its draw is unrecoverable, which is precisely why that jitter -- genuine
    exogenous variation on the live path since day one -- has been worthless as evidence.
    """
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / float(1 << 64)


def assign(
    symbol: str,
    side: str,
    notional: float,
    *,
    design: Design | None = None,
    spent_today_usd: float = 0.0,
    now: datetime | None = None,
    sequence: int = 0,
) -> Arm:
    """Assign this order an arm. ALWAYS returns an Arm -- the baseline one when it must not excite.

    Refuses to excite (returns baseline, with the reason recorded) when ANY of:
      - side is a CLOSE: the risk path is never slowed for an experiment (incident #6).
      - the design failed to load: an unreadable design degrades to today's behaviour.
      - epsilon is 0: excitation switched off; the fence reports NO-EXCITATION, not OK.
      - the daily notional cap is already spent: a declared budget is a real ceiling.
      - the draw exceeds epsilon: the ordinary 1-epsilon case.

    The reason string is persisted, so "why did this order not vary" is always answerable from the
    tape. A silent non-assignment would make an inert experiment indistinguishable from a running
    one -- the built-never-wired failure, wearing an experiment's costume.
    """
    d = design if design is not None else load_design()
    now = now or datetime.now(tz=UTC)
    cell = cell_of(symbol, notional, d)
    seed = f"{now.date().isoformat()}|{symbol}|{side}|{sequence}"
    base_wait = d.arms.get(BASELINE_ARM, 240.0)

    def _baseline(reason: str) -> Arm:
        return Arm(name=BASELINE_ARM, maker_wait_s=base_wait, cell=cell, seed=seed,
                   baseline=True, reason=reason)

    # CLOSES ARE NEVER EXCITED. Structural, not a config: a close is a certainty problem.
    if str(side).upper() == "SELL":
        return _baseline("close side -- never excited (risk path)")
    if not d.loaded:
        return _baseline(f"design not loaded: {d.note}")
    if d.epsilon <= 0.0:
        return _baseline("epsilon=0 -- excitation disabled")
    if spent_today_usd + max(0.0, notional) > d.daily_notional_cap_usd:
        return _baseline(f"daily excitation budget spent ({spent_today_usd:.0f}/"
                         f"{d.daily_notional_cap_usd:.0f} USD)")

    if _draw(seed) >= d.epsilon:
        return _baseline("draw outside epsilon -- ordinary baseline order")

    # Inside epsilon: pick among the NON-baseline arms with a second, independent draw.
    treatments = sorted(k for k in d.arms if k != BASELINE_ARM)
    if not treatments:
        return _baseline("design has no treatment arms")
    pick = treatments[int(_draw(seed + "|arm") * len(treatments)) % len(treatments)]
    return Arm(name=pick, maker_wait_s=float(d.arms[pick]), cell=cell, seed=seed,
               baseline=False, reason="assigned within epsilon")


def probes_used(symbol: str, tape_rows: list[dict[str, Any]], since: datetime) -> int:
    """Opens on `symbol` since `since` -- the re-entry probe count, derived from the tape.

    Derived, never stored: a probe counter held in a state file diverges from the tape the first
    time a write is lost or a restart lands mid-open, and it diverges SILENTLY in the permissive
    direction (a forgotten count re-grants probes forever). The tape is the record of what
    actually happened, so counting it cannot drift from it.
    """
    n = 0
    for r in tape_rows:
        if r.get("event") != "open" or str(r.get("symbol") or "") != symbol:
            continue
        try:
            when = datetime.fromisoformat(str(r.get("opened") or r.get("_taped") or ""))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when >= since:
            n += 1
    return n


def reentry_allowed(symbol: str, reentry: dict[str, Any], tape_rows: list[dict[str, Any]],
                    now: datetime | None = None) -> tuple[bool, str]:
    """May a denylisted symbol take ONE bounded re-entry probe? (allowed, reason).

    L1.16a: a rejection is a verdict on the evidence THEN AVAILABLE, not a permanent fact -- but
    the graveyard's door is NARROW. Re-opening requires a NAMED ENABLING CHANGE that addresses
    the ORIGINAL MECHANISM OF DEATH. This function enforces exactly that: no named change, no
    re-entry. It is not a general amnesty for losers.

    The execution denylist needed this because it is SELF-SEALING in a way the alpha graveyard is
    not: it blocks new OPENS, and `n` (the trade count its own verdict is conditioned on) can only
    grow through opens. So `n` freezes at the moment of the block and the verdict can never be
    revisited by any amount of waiting or evidence.

    DEFAULT IS DENY. An unreadable entry, a missing named change, an unparseable date and an
    exhausted probe budget all return False -- the fail-closed direction, exactly as before this
    function existed.
    """
    now = now or datetime.now(tz=UTC)
    row = reentry.get(symbol)
    if not isinstance(row, dict):
        return False, "no recorded re-entry condition (L1.16a) -- still absorbing"
    change = str(row.get("named_change") or "").strip()
    if not change:
        return False, "re-entry row has no named enabling change -- refusing (L1.16a)"
    try:
        after = datetime.fromisoformat(str(row["probe_after"]))
        if after.tzinfo is None:
            after = after.replace(tzinfo=UTC)
    except (KeyError, TypeError, ValueError) as e:
        return False, f"re-entry row has no usable probe_after ({e!r}) -- refusing"
    if now < after:
        return False, f"probe window opens {after.date().isoformat()}"
    try:
        max_probes = int(row.get("max_probes", 0))
    except (TypeError, ValueError):
        return False, "re-entry row has an unparseable max_probes -- refusing"
    if max_probes <= 0:
        return False, "max_probes=0 -- re-entry recorded but not armed"
    used = probes_used(symbol, tape_rows, after)
    if used >= max_probes:
        return False, f"probe budget exhausted ({used}/{max_probes}) -- verdict stands"
    return True, f"re-entry probe {used + 1}/{max_probes}: {change}"


def spent_today(tape_rows: list[dict[str, Any]], now: datetime | None = None) -> float:
    """Notional placed under a NON-baseline arm so far today (UTC).

    Reads the tape rather than holding state in the executor: the budget must survive a restart,
    and an executor that forgets its spend on every restart has no cap at all.
    """
    now = now or datetime.now(tz=UTC)
    today = now.date().isoformat()
    total = 0.0
    for r in tape_rows:
        if r.get("exc_baseline") is not False:
            continue
        stamp = str(r.get("opened") or r.get("_taped") or "")
        if stamp[:10] != today:
            continue
        try:
            total += abs(float(r.get("notional", 0.0)))
        except (TypeError, ValueError):
            continue
    return total
