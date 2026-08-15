"""Single source of truth for the CONCURRENT forward-confirmation slot cohort (the Holm `m`).

Under the TWO-STAGE DISCOVERY LAW the backtest gauntlet has ZERO promotion authority; promotion to
capital comes only from pre-registered FORWARD evidence, and the only multiplicity that applies
there is the number of CONCURRENTLY ACCRUING clocks -- Holm-corrected, capped at
MAX_FORWARD_SLOTS=12. That cohort size is therefore the single most load-bearing integer on the
desk's only path from research to capital.

It was being counted three different ways by three different files:
  * scripts/run_axis_shadows.py -- holm_bar(len(_AXES)) => m=4, the AXIS clocks only
  * scripts/run_alerts.py       -- len(registry) + a hardcoded `_standing = 6` + the axis count
  * data/shadow_sleeves.json    -- [], and it is a RUN-ROSTER of derivative sleeve names
                                   (scripts/run_derivative_shadow.py:77-81), never a cohort registry
Measured 2026-07-30: the axis clocks applied holm_bar(4)=2.24 while the true cohort was 12-13
(bar 2.64-2.67) -- alpha 0.0125 per clock against an intended 0.05/13=0.0038, a realized
family-wise error rate ~3.2x the design. Understating m LOOSENS the bar, so the error ran in the
PHANTOM-EDGE direction. Three deep sweeps (2026-07-26/28/29) each found this and each carried it.

FAIL-SAFE DIRECTION (deliberate, and the reason this is not a plain `len()`): a missing or
unreadable source silently SHRINKS m and loosens every bar, so unknown sources never count as
zero -- they mark the cohort `complete=False`, which run_alerts surfaces. Likewise a dormant clock
is counted until it is RETIRED by an explicit ledgered decision: over-counting only tightens the
bar (the safe error), under-counting admits noise as edge.

Stdlib plus TWO in-repo imports, and each is the price of not guessing something that cannot be
guessed safely. `libs.ops.desk_host` answers whether this box owns the runtime state under
`data/`: that cannot be settled from the artifacts themselves -- on a clone the evidence and its
absence look identical -- and guessing it wrong publishes a small cohort as MEASURED, a LOOSER
bar. `libs.research.clock_retirement` carries the tracked ledger of clocks that have LEFT the
cohort by explicit decision, which is the only sanctioned way `m` may ever fall.

import from libs.research.slot_registry.
"""
from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.desk_host import is_owning_host
from libs.research.clock_retirement import multiplicity_high_water, retired_names

_ROOT = Path(__file__).resolve().parents[2]

#: Law cap -- the fixed-for-life forward bar is only fixed while the cohort stays at/below this.
MAX_FORWARD_SLOTS = 12

#: Standing sleeve clocks, each proven by its own on-disk state file carrying a `shadow_start`.
#: Named explicitly (not globbed) so that ADDING a clock is a visible code change and REMOVING one
#: cannot happen by a file quietly disappearing -- a vanished source becomes `unknown`, not absent.
_STANDING_STATES: dict[str, str] = {
    "cashcarry": "data/cashcarry_shadow_state.json",
    "crossasset": "data/crossasset_shadow_state.json",
    "crypto_combined": "data/crypto_shadow_state.json",
    "trend_30d": "data/trend_shadow_state.json",
    "trend_regime": "data/trend_regime_shadow_state.json",
    "legacy_shadow": "data/shadow_state.json",
}

#: Built-in derivative-shadow sleeves (scripts/run_derivative_shadow.py:77). Extras registered in
#: data/shadow_sleeves.json are added on top -- that file is the RUN roster, and every sleeve it
#: schedules is also a live clock, so it feeds the cohort even though it does not define it.
_DERIVATIVE_BUILTIN: tuple[str, ...] = ("oi_divergence", "ls_contrarian")

_AXIS_STATE = "data/axis_shadow_state.json"
_SLEEVE_ROSTER = "data/shadow_sleeves.json"
_OUT = "data/forward_slots.json"

#: Slot -> (evidence artifact, day-count field). The STATE files above prove a clock was BORN;
#: these prove it is still BREATHING, and the two are not the same question. Measured 2026-08-01:
#: the standing states are birth-certificate stubs carrying nothing but `shadow_start` and are
#: never rewritten, while the derivative slots' state was the hardcoded string literal "ACCRUING"
#: -- so `derive_slots()` ASSERTED that 12 of 12 clocks were accruing without reading a single day
#: count. Five were not: crossasset frozen 41 days at day 1 with NO scheduler line anywhere,
#: cny_premium pinned at 0/40 for 9 days (every z20 null, skipped at run_axis_shadows.py:131),
#: walcl re-stamping one 07-29 observation daily, defi_utilisation 4 days of exactly-zero returns,
#: and cashcarry silently missing its 08-01 run. `idle_slots: 0` then suppressed every idleness
#: alert. This is the L1.28a rule turned on the desk's own evidence pipeline: UNMEASURED
#: UTILISATION COUNTS AS ZERO, and a capability is proven by its ARTIFACT, never by a flag.
_EVIDENCE: dict[str, tuple[str, str]] = {
    "cashcarry": ("web/cashcarry_shadow.json", "forward_days"),
    "crossasset": ("web/crossasset_shadow.json", "forward_days"),
    "crypto_combined": ("web/crypto_shadow.json", "forward_days"),
    "trend_30d": ("web/trend_shadow.json", "forward_days"),
    "trend_regime": ("web/trend_regime_shadow.json", "forward_days"),
    "legacy_shadow": ("web/shadow.json", "forward_days"),
    "oi_divergence": ("web/derivative_shadow.json", "days_accumulated"),
    "ls_contrarian": ("web/derivative_shadow.json", "days_accumulated"),
}

#: A forward clock advances once per day. Past this its artifact is not evidence, it is a fossil.
STALE_AFTER_H = 36.0


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _sleeve_verdict(name: str) -> str:
    """The Stage-B verdict a sleeve's own runner published, or "" when it publishes none.

    THE FIVE `FAILING FORWARD -> kill` VERDICTS WERE INERT BECAUSE THEY NEVER REACHED A SLOT ROW.
    `forward_verdict()` (libs/research/event_density.py) is shared by five shadow runners and each
    writes its string into `web/<sleeve>_shadow.json`. `derive_slots` read those artifacts for
    `forward_days` and `updated` and dropped the verdict on the floor, so every sleeve slot
    reached `slot_displacement.classify_slot` carrying `state="since <date>"` -- a birth date,
    never an outcome. The classifier could not see a kill because a kill was never in the row.

    Axis rows already carry their verdict (the axis branch reads `row["verdict"]`), which is why
    the axis half of the cohort could be reclaimed and the sleeve half could not.
    """
    ref = _EVIDENCE.get(name)
    if ref is None:
        return ""
    doc = _read_json(ref[0])
    return str(doc.get("verdict", "")) if isinstance(doc, dict) else ""


def _evidence(name: str, now: datetime, *, days: object = None,
              updated: object = None) -> dict[str, Any]:
    """Is this clock BREATHING? Never asserts -- reports UNMEASURED when it cannot tell.

    Axis slots pass their own row's `days`/`updated`; everything else is looked up in _EVIDENCE.
    NO-EVIDENCE (day count 0) is kept DISTINCT from STALLED (artifact not rewritten): a clock can
    run perfectly on schedule and still accrue nothing, which is exactly how cny_premium sat at
    0/40 for nine days while its collector reported green every morning.
    """
    src = "(axis row)"
    if days is None and updated is None:
        ref = _EVIDENCE.get(name)
        if ref is None:
            # NOT A DEAD END, and treating it as one is what left every auto-spawned clock at
            # UNMEASURED forever. `_EVIDENCE` is a fixed eight-name map written when eight clocks
            # existed; a sleeve spawned afterwards appears in none of it, so it could never
            # publish a day count, never accrue, and never resolve -- born, registered, charged
            # its multiplicity, and structurally unable to finish. Paper sleeves publish through
            # ONE artifact keyed by name, so a sleeve spawned tomorrow is covered with no map to
            # edit (nothing hardcoded).
            return _paper_sleeve_evidence(name, now)
        src = ref[0]
        doc = _read_json(src)
        if not isinstance(doc, dict):
            return {"evidence": "UNMEASURED", "why": f"{src} missing or unreadable", "source": src}
        days, updated = doc.get(ref[1]), doc.get("updated")
    ts = _parse_ts(updated)
    if ts is None:
        return {"evidence": "UNMEASURED", "why": f"{src} carries no parseable `updated`",
                "source": src}
    age_h = round((now - ts).total_seconds() / 3600.0, 1)
    try:
        # `days` is object-typed off a JSON dict, so narrow before converting rather than
        # silencing. The old `# type: ignore[arg-type]` had stopped matching the real error
        # (call-overload) and mypy then flagged the ignore itself as unused -- two errors from
        # one stale suppression, and CI red on master until it was removed.
        n_days = int(days) if isinstance(days, (int, float, str)) else int(str(days))
    except (TypeError, ValueError):
        return {"evidence": "UNMEASURED", "why": f"{src} carries no day count",
                "source": src, "age_h": age_h}
    state = ("NO-EVIDENCE" if n_days <= 0 else
             "STALLED" if age_h > STALE_AFTER_H else "ACCRUING")
    return {"evidence": state, "days": n_days, "age_h": age_h, "source": src}


#: Where scripts/run_paper_sleeve_forward.py publishes every paper sleeve's accrual, keyed by name.
_PAPER_FORWARD = "web/paper_sleeve_forward.json"


def _paper_sleeve_evidence(name: str, now: datetime) -> dict[str, Any]:
    """Accrual for an auto-spawned paper sleeve, read from the one artifact that carries them all.

    ROWS ARE THE CLOCK, not calendar days. A sleeve can sit alive for a week while its source
    artifact is never regenerated, and counting those days as forward evidence would credit the
    clock for observations that do not exist -- the fossil problem, one level in. So `days` here
    is rows added since baseline, and a sleeve with none reads NO-EVIDENCE (distinct from STALLED,
    which is about the artifact ageing).
    """
    # A SCREEN-SPAWNED CLOCK PUBLISHES SOMEWHERE ELSE, and reading only the paper-sleeve artifact
    # is what starved one (2026-08-14). `perpdex_funding::aster_BTCUSDT_level_rate::8h` was
    # reported NO-EVIDENCE with zero observations while SEVEN rows sat in
    # data/perpdex_funding_clock.jsonl -- its collector cronned, run all week, 184,753 rows. The
    # cohort read that zero as a MEASUREMENT, the sweep called the seat reclaimable, and the
    # unattended path retired a clock that had evidence.
    #
    # `stage_a_screen(clock=...)` announces every clock it starts into the axis clock registry, so
    # the registry is the one place that knows where a screen-spawned clock's rows actually live.
    # Checked FIRST, because a name present there is definitionally not a paper sleeve.
    reg_ev = _registered_clock_evidence(name, now)
    if reg_ev is not None:
        return reg_ev

    doc = _read_json(_PAPER_FORWARD)
    if not isinstance(doc, dict):
        return {"evidence": "UNMEASURED",
                "why": (f"{_PAPER_FORWARD} missing or unreadable -- no runner has published "
                        f"accrual for {name}. A spawned clock nothing runs can never resolve."),
                "source": _PAPER_FORWARD}
    sleeves = doc.get("sleeves")
    row = sleeves.get(name) if isinstance(sleeves, dict) else None
    if not isinstance(row, dict):
        return {"evidence": "UNMEASURED",
                "why": f"{_PAPER_FORWARD} carries no row for {name}", "source": _PAPER_FORWARD}
    ts = _parse_ts(row.get("observed_utc") or doc.get("updated"))
    age_h = round((now - ts).total_seconds() / 3600.0, 1) if ts else None
    state = str(row.get("evidence", "UNMEASURED"))
    if state == "ACCRUING" and age_h is not None and age_h > STALE_AFTER_H:
        state = "STALLED"                     # the runner stopped; a fossil is not evidence
    return {"evidence": state, "days": row.get("rows_added"), "age_h": age_h,
            "source": _PAPER_FORWARD,
            "progress_to_resolution": row.get("progress_to_resolution"),
            "why": row.get("why", "")}



#: Where stage_a_screen announces every clock it starts. A screen-spawned clock is NOT a paper
#: sleeve and does not publish through the paper-sleeve runner; this is the map from its name to
#: the JSONL its rows are actually written to.
_CLOCK_REGISTRY = "data/axis_clock_registry.json"


def _registered_clock_evidence(name: str, now: datetime) -> dict[str, Any] | None:
    """Accrual for a clock announced by `stage_a_screen`, or None when this name is not one.

    RETURNS None RATHER THAN A ZERO when the name is unregistered: None means "not my kind of
    clock, ask the next reader", and a zero would mean "measured, and it has nothing" -- which is
    exactly the substitution that retired a clock holding seven observations.
    """
    doc = _read_json(_CLOCK_REGISTRY)
    axes = doc.get("axes") if isinstance(doc, dict) else None
    rec = axes.get(name) if isinstance(axes, dict) else None
    if not isinstance(rec, dict) or not rec.get("clock"):
        return None
    rel = str(rec["clock"])
    p = _ROOT / rel
    if not p.exists():
        return {"evidence": "UNMEASURED", "source": rel,
                "why": (f"{name} is registered against {rel}, which does not exist on this host. "
                        "Registered-but-absent is UNKNOWN, never a measured zero -- a clock whose "
                        "rows cannot be found has not been shown to have none")}
    try:
        lines = [ln for ln in p.read_text("utf-8", errors="ignore").splitlines() if ln.strip()]
    except OSError:
        return {"evidence": "UNMEASURED", "source": rel, "why": f"{rel} unreadable"}
    age_h = None
    with contextlib.suppress(OSError):
        age_h = round((now.timestamp() - p.stat().st_mtime) / 3600.0, 1)
    state = ("NO-EVIDENCE" if not lines else
             "STALLED" if (age_h is not None and age_h > STALE_AFTER_H) else "ACCRUING")
    return {"evidence": state, "days": len(lines), "age_h": age_h, "source": rel,
            "why": f"{len(lines)} clock row(s) in {rel} (screen-spawned clock, not a paper sleeve)"}

def _read_json(rel: str) -> Any | None:
    """Return parsed JSON, or None when the source cannot be trusted (missing/unreadable)."""
    doc, _ = _read_source(rel)
    return doc


def _read_source(rel: str) -> tuple[Any | None, str]:
    """(document, state) where state is OK / ABSENT / UNREADABLE.

    THE DISTINCTION THIS DRAWS, and it was collapsed for the module's whole life. A file that does
    NOT EXIST has never been written, so the clocks it would record were never born -- that is a
    MEASURED ZERO. A file that exists and does not parse could hold anything -- that is genuinely
    UNKNOWN. Treating both as unknown looks conservative and is not: it is what froze slot
    admission permanently. On 2026-08-05 all eight "unknown" sources were simply ABSENT (no clock
    had ever been started on this box), `complete` was therefore False forever, and
    `paper_sleeves.free_slots` collapses to zero on an incomplete cohort -- so ten idle slots could
    never be filled, no forward clock could ever start, and nothing could ever survive. An unknown
    that can be RESOLVED must be resolved, not surrendered to (L1.54).
    """
    path = _ROOT / rel
    if not path.exists():
        return None, "ABSENT"
    try:
        return json.loads(path.read_text("utf-8")), "OK"
    except (OSError, json.JSONDecodeError):
        return None, "UNREADABLE"


def derive_slots() -> dict[str, Any]:
    """Enumerate every concurrently-accruing forward clock from the artifacts on disk.

    Returns a payload carrying the slots, the cohort size `m_concurrent`, and `complete` -- False
    whenever any source was unreadable, meaning m is a LOWER BOUND and the true bar may be higher.
    """
    now = datetime.now(tz=UTC)
    slots: list[dict[str, Any]] = []
    unknown: list[str] = []
    absent: list[str] = []
    #: Per-source UPPER BOUND on clocks an unreadable source could be hiding. A single named
    #: clock's state file can hide at most one; a CONTAINER (axis roster, sleeve roster) can hide
    #: any number, so it saturates the cap. Summed into `m_upper` below.
    bounds: dict[str, int] = {}

    axis_doc, axis_state = _read_source(_AXIS_STATE)
    if axis_state == "ABSENT":
        absent.append(_AXIS_STATE)
    elif axis_doc is None:
        unknown.append(_AXIS_STATE)
        bounds[_AXIS_STATE] = MAX_FORWARD_SLOTS      # container: unbounded, so saturate
    else:
        rows = axis_doc.get("axes", axis_doc) if isinstance(axis_doc, dict) else axis_doc
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            if str(row.get("verdict", "")).upper() == "RETIRED":
                continue
            slots.append({"name": str(row.get("axis", "?")), "kind": "axis",
                          "source": _AXIS_STATE, "state": str(row.get("verdict", "ACCRUING")),
                          # `started` is the clock's DECLARED birth date, carried as a first-class
                          # field so libs.research.promotion_history never has to parse it back out
                          # of the `state` prose. None where the artifact does not declare one --
                          # an absent start is UNKNOWN, never today (L1.30 phantom-birth rule).
                          "started": row.get("shadow_start") or row.get("start"),
                          # `decision_at_obs` is the clock's PRE-REGISTERED decision point in
                          # OBSERVATIONS (R0430), carried first-class for the same reason
                          # `started` is: a consumer must never have to re-derive it, because
                          # re-deriving it from today's data is precisely what makes it stop
                          # being pre-registered. None where the artifact declares none -- an
                          # undeclared decision point is UNKNOWN, and a horizon nobody wrote
                          # down can never be reported as reached.
                          "decision_at_obs": row.get("decision_at_obs"),
                          # DEFLATOR INPUTS, carried through so `information_rate` can compute a
                          # real rate rather than charging every clock the unmeasured penalty.
                          # PASSED THROUGH VERBATIM, including absence: a missing field must stay
                          # missing here, because the value each of them defaults to downstream is
                          # exactly the flattering one, and inventing it in the registry would put
                          # the substitution one layer further from where anyone would look.
                          "distinct_regimes": row.get("distinct_regimes"),
                          "autocorrelation": row.get("autocorrelation"),
                          **_evidence(str(row.get("axis", "?")), now,
                                      days=row.get("forward_days", row.get("n", 0)),
                                      updated=row.get("updated")
                                      or (axis_doc.get("updated")
                                          if isinstance(axis_doc, dict) else None))})

    for name, rel in _STANDING_STATES.items():
        doc, state = _read_source(rel)
        if state == "ABSENT":
            absent.append(rel)                       # this clock was never born on this box
            continue
        if doc is None:
            unknown.append(rel)
            bounds[rel] = 1                          # one named clock: at most one hidden
            continue
        if isinstance(doc, dict) and doc.get("shadow_start"):
            slots.append({"name": name, "kind": "standing", "source": rel,
                          # `state` stays the birth date: promotion_history and the dashboard
                          # parse it. The OUTCOME travels in its own field so neither has to
                          # change and neither can confuse a start with a verdict.
                          "state": f"since {doc['shadow_start']}",
                          "verdict": _sleeve_verdict(name),
                          "started": str(doc["shadow_start"]), **_evidence(name, now)})

    roster, roster_state = _read_source(_SLEEVE_ROSTER)
    if roster_state == "ABSENT":
        # The spawner's own convention, and the file it writes: `_spawn_one` reads an absent
        # roster as `[]`. A registry that called the same absence unknown disagreed with the organ
        # that owns the file.
        absent.append(_SLEEVE_ROSTER)
        names: list[str] = list(_DERIVATIVE_BUILTIN)
    elif roster is None:
        unknown.append(_SLEEVE_ROSTER)
        bounds[_SLEEVE_ROSTER] = MAX_FORWARD_SLOTS   # container: unbounded, so saturate
        names = list(_DERIVATIVE_BUILTIN)
    else:
        extras = [str(x) for x in roster if str(x).strip()] if isinstance(roster, list) else []
        names = sorted({*_DERIVATIVE_BUILTIN, *extras})
    for name in names:
        # A SPAWNED SLEEVE DOES DECLARE ITS BIRTH, and this loop could not see it. The spawner
        # writes data/<name>_shadow_state.json carrying `shadow_start` -- the same birth
        # certificate every standing clock uses -- but `started` was read only from the fixed
        # _STANDING_STATES map, so every auto-spawned clock reported started=None forever. A clock
        # with no birth date can never have its forward days counted, so it could never accrue and
        # never resolve: born, registered, paying multiplicity, and structurally unable to finish.
        #
        # Where no such file exists the answer stays None, and deliberately: the built-in
        # derivative sleeves publish only `days_accumulated`, and a start back-derived from an
        # accrual counter is an UPPER bound on the birth date (a stalled clock accrues nothing
        # while ageing), so it would make births look EARLIER and over-count forward evidence.
        started: str | None = None
        state_label = "roster"
        spawned_doc, spawned_state = _read_source(f"data/{name}_shadow_state.json")
        if spawned_state == "OK" and isinstance(spawned_doc, dict) and spawned_doc.get(
                "shadow_start"):
            started = str(spawned_doc["shadow_start"])
            state_label = f"since {started}"
        slots.append({"name": name, "kind": "derivative", "source": _SLEEVE_ROSTER,
                      "state": state_label, "verdict": _sleeve_verdict(name),
                      "started": started, **_evidence(name, now)})

    # m is deliberately UNCHANGED by any of this: a stalled clock stays in the cohort until it is
    # RETIRED by an explicit ledgered decision, because dropping it would SHRINK m and loosen every
    # bar -- the phantom-edge direction this module exists to prevent. What the measurement buys is
    # that a dead clock can no longer report itself as accruing, and that the desk can see it is
    # paying multiplicity for slots returning nothing.
    # THE ONE SANCTIONED EXIT, AND IT IS THE ONLY ONE (2026-08-14). Everything above deliberately
    # keeps a dormant clock counted; this is the single place a name may leave, and it leaves only
    # because `docs/research/CLOCK_RETIREMENTS.json` -- TRACKED, attributed, evidenced, and
    # writable only by an explicit human evidence decision (a live sweep proposal, or a recorded
    # principal account/jurisdiction ineligibility) -- says so.
    #
    # Applied HERE, after all three sources are assembled, so retirement means the same thing for
    # an axis clock, a standing sleeve and a derivative. The pre-existing `verdict: RETIRED` string
    # in the axis artifact covered ONE source and lived in gitignored state, which made it a
    # decision no clone could see and no audit could cite.
    #
    # A MALFORMED OR ABSENT LEDGER RETIRES NOTHING: the cohort stays larger and every bar stays
    # tighter, so the failure mode is seats that will not free rather than bars that quietly
    # loosened.
    _retired_names = retired_names(_ROOT)
    retired = [s for s in slots if str(s.get("name")) in _retired_names]
    slots = [s for s in slots if str(s.get("name")) not in _retired_names]

    dead = [s for s in slots if s.get("evidence") in ("STALLED", "NO-EVIDENCE")]
    unmeasured = [s for s in slots if s.get("evidence") == "UNMEASURED"]

    # ABSENT MEANS "NEVER BORN" ONLY ON THE HOST THAT OWNS THE ARTIFACTS (L1.28a / WS-005).
    #
    # A file never written records a clock never born -- true, and the reasoning the ABSENT/UNKNOWN
    # split is built on. It is false on every OTHER host: `data/` is gitignored, so a fresh clone
    # or a CI runner sees all six standing state files absent and derives `complete=True` with six
    # clocks "never born". Measured on a clone 2026-08-13: m=6, MEASURED, complete=True, with 7
    # absent sources, while the live desk cohort is ~12. The L1.6 fence then reports OK at bar 2.39
    # where the desk requires 2.64 -- absence resolving to the CLEAN verdict, on the single most
    # load-bearing integer, in the LOOSER direction.
    #
    # A host cannot distinguish "never written" from "not shipped here" file by file. It CAN
    # distinguish it in aggregate: a desk that has run has written at least one of these. Zero of
    # N present is not N independent measured zeros, it is a host with no desk state -- so the
    # whole set converts to UNKNOWN and each bounds itself, which floors m at the cap rather than
    # publishing a small number as measured.
    #
    # COSTS NOTHING WHERE IT MATTERS: on the VPS the files exist, no branch is taken, m is
    # unchanged. What it removes is a false green in CI, and a `MEASURED` provenance on a cohort
    # nobody measured.
    #
    # RESIDUAL, NAMED RATHER THAN PAPERED OVER: this catches the ALL-absent host, not the mixed
    # one. A clone where a single organ has run (writing, say, axis state and nothing else) still
    # reads the six missing sleeve births as measured zeros and publishes MEASURED at m=6 against
    # a live cohort near 12. Distinguishing that case needs a host-identity marker the registry
    # does not have, and GUESSING one would be worse than the gap -- a wrong "this is the owning
    # host" would restore exactly the false MEASURED this block removes. Tracked as a gap row;
    # the all-absent case is the one that is provable from here.
    # THE QUESTION IS NOW READ RATHER THAN INFERRED (GAP 111 closed). `desk_host` carries a marker
    # the running cycle stamps, so "absent" can mean a measured zero HERE and a fact about the
    # host everywhere else. The all-sources-unreadable test below is kept as a second, independent
    # trigger: it catches a box whose marker is missing AND whose state is gone, which is the
    # bare-clone case the marker was introduced to cover, so neither mechanism depends on the
    # other being correct.
    #
    # This closes the residual the first version named honestly and could not fix: a clone where
    # ONE organ has run used to read the six missing sleeve births as measured zeros and publish
    # MEASURED at m=6 against a live cohort near 12. That host now fails the marker check and
    # floors at the cap like any other non-owning box.
    _owns, _owns_why = is_owning_host(_ROOT)
    _all_sources = {_AXIS_STATE, *_STANDING_STATES.values(), _SLEEVE_ROSTER}
    if absent and (not _owns or not (_all_sources - set(absent) - set(unknown))):
        for rel in absent:
            bounds.setdefault(rel, MAX_FORWARD_SLOTS if rel in (_AXIS_STATE, _SLEEVE_ROSTER) else 1)
        unknown.extend(absent)
        absent = []

    # CAPACITY AND MULTIPLICITY ARE TWO NUMBERS, AND THIS FILE HAD ONLY EVER STORED ONE.
    #
    # `seats_upper` is a RESOURCE bound: how many concurrent forward clocks the box, the data and
    # the attention budget support. Retiring a dead clock frees one and that is pure gain.
    #
    # `m_upper` is how many times the desk LOOKED, and it is a HIGH-WATER MARK. A clock that ran
    # and failed consumed a trial; retiring it afterwards does not un-look, for the same reason a
    # p-value cannot be improved by forgetting an experiment. So it takes the max of the live
    # bound and every cohort size the retirement ledger has ever recorded, and it CANNOT FALL.
    #
    # This is what makes automatic seat reclamation safe. The standing objection to it -- that
    # dropping a row loosens every survivor's bar in the phantom-edge direction -- was an
    # objection to the BAR MOVING, not to the seat being freed, and the two only ever moved
    # together because they shared a variable.
    seats_upper = len(slots) + sum(bounds.values())
    m_upper = max(seats_upper, multiplicity_high_water(_ROOT))
    return {
        "updated": now.isoformat(),
        "m_concurrent": len(slots),
        "seats_used": len(slots),
        "seats_upper": seats_upper,
        "seats_free": max(0, MAX_FORWARD_SLOTS - seats_upper),
        "multiplicity_high_water": m_upper,
        # THE NUMBER EVERY BAR MUST BE COMPUTED FROM. `m_concurrent` counts only what was READ, so
        # it is a LOWER bound whenever a source is unreadable -- and understating m LOOSENS every
        # Holm bar, the phantom-edge direction this module exists to prevent. `complete=False` was
        # published next to the loose number rather than instead of it, and every caller of
        # concurrent_m() kept using the loose one. m_upper adds each unreadable source's own
        # maximum, so the bar is computed from the worst case and can only ever be too TIGHT.
        "m_upper": m_upper,
        "m_bounds": bounds,
        "complete": not unknown,
        "cap": MAX_FORWARD_SLOTS,
        # CAPACITY QUESTIONS ANSWER FROM SEATS, never from multiplicity. Asking "may another clock
        # start?" against a high-water mark would keep the desk permanently over cap on the
        # strength of clocks that have already been retired -- idleness bought with a number that
        # exists to protect the bar, which protects nothing and costs every candidate its clock.
        "over_cap": seats_upper > MAX_FORWARD_SLOTS,
        "idle_slots": max(0, MAX_FORWARD_SLOTS - seats_upper),
        "unknown_sources": unknown,
        # Published so a reader can tell a measured zero from a host without state, which is
        # the whole distinction the ABSENT/UNKNOWN split turns on (L1.28a).
        "owning_host": _owns, "owning_host_why": _owns_why,
        # ABSENT IS A MEASUREMENT, NOT AN UNKNOWN: the file was never written, so the clock it
        # would record was never born. Kept in its own list so the two can never be re-merged.
        "absent_sources": absent,
        "accruing": len(slots) - len(dead) - len(unmeasured),
        "not_accruing": [{"name": s["name"], "evidence": s.get("evidence"),
                          "days": s.get("days"), "age_h": s.get("age_h")} for s in dead],
        "unmeasured_slots": [s["name"] for s in unmeasured],
        # PUBLISHED, NEVER MERELY SUBTRACTED. A seat that vanished and a seat that was retired look
        # identical in a count, and only one of them is a decision somebody made and signed.
        "retired_slots": [s["name"] for s in retired],
        "evidence_stale_after_h": STALE_AFTER_H,
        "slots": slots,
        "note": ("Holm cohort for every Stage-B forward clock. UNREADABLE sources are bounded "
                 "into `m_upper` (never counted as zero: understating m loosens every bar); "
                 "ABSENT sources are a measured zero, because a file never written records a "
                 "clock never born, and calling that unknown is what froze slot admission. "
                 "Dormant clocks stay counted until RETIRED by an explicit ledgered decision -- "
                 "`not_accruing` names the slots paying multiplicity while returning no evidence, "
                 "which is a cost to fix upstream, never by shrinking m. `retired_slots` names "
                 "the ones that HAVE left, each by an attributed row in "
                 "docs/research/CLOCK_RETIREMENTS.json taken against a live sweep proposal or an "
                 "explicit principal account/jurisdiction ineligibility; that "
                 "tracked ledger is the only mechanism by which m may fall."),
    }


@dataclass(frozen=True)
class CohortM:
    """The cohort size a Holm bar must be computed against, with WHY attached.

    `m` is what you pass to holm_bar. `provenance` says how it was arrived at, because a bar
    computed from a degraded cohort is still a bar and the caller has to be able to say so in its
    own artifact.
    """
    m: int
    provenance: str          # MEASURED | INCOMPLETE-FLOORED | REFUSED-FLOORED
    detail: str

    @property
    def measured(self) -> bool:
        return self.provenance == "MEASURED"


def cohort_m_for_bar() -> CohortM:
    """THE cohort size for every Stage-B Holm bar on this desk. Call this, never `len(anything)`.

    EVERY FAILURE PATH TIGHTENS. This is the whole point of the function and the reason it is not
    `len(derive_slots()["slots"])`. Understating m LOOSENS the bar, which is the phantom-edge
    direction: at the measured 2026-08-05 values, judging the axis clocks at len(_AXES)=3 applies
    holm_bar(3)=2.13 where the true cohort of 11 requires 2.61 -- alpha 0.0167 per clock against a
    designed 0.0045, a family-wise error rate 3.67x the design, on the desk's only path from
    research to capital.

    So the degraded paths floor at the LAW CAP rather than falling back to a smaller number:
      * cohort incomplete (a source unreadable => m is a LOWER bound) -> max(m, m_upper, CAP)
      * registry unusable entirely                                    -> MAX_FORWARD_SLOTS
    Over-counting only costs us a real edge's promotion by a few days of clock; under-counting
    admits noise as edge and sizes capital on it. Those are not symmetric, and this function
    resolves every ambiguity toward the one that cannot manufacture an edge.
    """
    try:
        snap = derive_slots()
        derived = int(snap["m_concurrent"])
        complete = bool(snap["complete"])
        unknown = list(snap.get("unknown_sources") or [])
        upper = snap.get("m_upper")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return CohortM(
            MAX_FORWARD_SLOTS, "REFUSED-FLOORED",
            f"slot registry unusable ({type(exc).__name__}: {exc}) -- floored at the law cap "
            f"{MAX_FORWARD_SLOTS} because an unknown cohort must never produce a LOOSER bar than "
            "a known one")
    if not complete:
        # m_upper bounds each unreadable source at its own maximum, so where it is published it is
        # the TIGHTER honest floor; the law cap remains the minimum either way. Both directions
        # can only ever RAISE m above the loose lower bound, never lower it.
        floor = max(derived, int(upper) if isinstance(upper, int) else 0, MAX_FORWARD_SLOTS)
        return CohortM(
            floor, "INCOMPLETE-FLOORED",
            f"{derived} clocks counted but {len(unknown)} source(s) unreadable "
            f"({', '.join(unknown[:3])}) -- m is a LOWER bound, so it is floored at "
            f"{floor}; the true bar can only be higher, never lower")
    return CohortM(max(derived, 1), "MEASURED",
                   f"{derived} concurrently-accruing forward clocks, every source readable")


def concurrent_m() -> int:
    """The Holm cohort size. Never returns 0 -- a cohort of nothing would zero out multiplicity.

    Delegates to `cohort_m_for_bar()` so that the fail-safe flooring applies to EVERY caller by
    default. This function had zero callers for the whole period the axis clocks ran at a 3.67x
    inflated error rate; a bare `len()` here would have been a footgun waiting for its first user.
    """
    return cohort_m_for_bar().m


def write_snapshot() -> dict[str, Any]:
    """Persist the derived cohort to data/forward_slots.json and return it."""
    payload = derive_slots()
    (_ROOT / _OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    return payload


if __name__ == "__main__":  # pragma: no cover -- operator entry point
    snap = write_snapshot()
    print(f"m_concurrent={snap['m_concurrent']} complete={snap['complete']} "
          f"idle={snap['idle_slots']} over_cap={snap['over_cap']}")
    for s in snap["slots"]:
        print(f"  {s['kind']:11s} {s['name']:28s} {s['source']}")
    if snap["unknown_sources"]:
        print("  UNKNOWN:", ", ".join(snap["unknown_sources"]))
