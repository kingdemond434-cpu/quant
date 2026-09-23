"""FORWARD RECONCILER -- every clock is certified or retired, nothing squats (principal
2026-08-26: "shouldn't all be tested for certification and retired if the 10 gates don't work").

WHAT THE PRINCIPAL CAUGHT. The desk showed 37-41 "forward clocks" against 21 certificates and
the arithmetic never closed. Measured tonight, the gap is TWO different defects wearing one
label, and the smaller one is the honest one:

  1. ORPHANS (26 of 36 rows). `shadow_forward` enrols exactly 10 sleeves per cycle. The other 26
     rows in shadow_state.json are residue from retired experiments -- fair_value_gap,
     monday_gap, dow_effect, conditioned MACRO_FAV/FAILED_BREAK variants -- that NOTHING runs any
     more. They still read `status: ACTIVE` with frozen `days_active` and `n` (one sits at
     days=7, n=1). They are not slow clocks, they are STOPPED clocks: at day 14 the verdict rule
     would fire on a single ancient trade. A stopped clock counted as forward evidence is worse
     than no clock, because it looks like progress on the dashboard and can promote.

  2. UNCERTIFIED ENROLMENTS (5 of the 10 that do run). Grandfathered hunt6 sleeves carrying
     `gate_reason: "missing exact original universal ten-gate pass"`. They accrue real evidence
     but the admission door refuses them for ever, so the evidence can never cash. That is a
     sleeve doing work it is structurally barred from being paid for.

THE RULE THIS ENFORCES (RESEARCH §6d, the one-door law). A live forward clock must be BOTH
enrolled by a running engine AND backed by a ten-gate certificate. Anything else is retired with
its reason recorded -- not deleted, never silently. Specifically:

  * orphan (no engine enrols it)          -> RETIRED_ORPHAN
  * enrolled, no certificate, gauntlet PASS -> certificate written, clock keeps running
  * enrolled, no certificate, gauntlet FAIL -> RETIRED_GATE_FAIL, with the failing gates named
  * cannot be reconstructed exactly         -> RETIRED_UNRECONSTRUCTIBLE (never guessed:
    `shadow_admission` forbids inventing lost parameters from a display name, and a gauntlet run
    on guessed parameters certifies a strategy nobody is actually trading)

EVIDENCE IS NEVER DESTROYED. Retiring sets a status and a reason on the row; ledgers, trade
lists and day counts stay exactly as they were, so a retired row remains auditable and a future
certificate can revive it through a FRESH forward window (never by inheriting the old clock --
that clock was measured under no pre-registration).

ANYTIME-VALID MONITORING, BESIDE THE HOLM BARS (review R3, 2026-09-17)
---------------------------------------------------------------------
The desk enrols dozens of forward candidates against twelve slots and RE-READS their evidence
every hour. A fixed-sample t-stat is calibrated for ONE look: re-testing it on every pass spends
alpha the Holm bars do not price, and under continuous monitoring a nominal 5% test rejects a
true null with probability approaching 1. `forward_stats.holm_bar` says so in its own docstring
(measured on this desk's cohort: 0.0042 at one look, 0.0367 under daily peeking -- 8.8x nominal).

`anytime_monitor` therefore publishes, per ENROLLED clock, the peek-safe statistic beside the
peek-unsafe one:

  * `e_value`   -- `libs.research.anytime_valid.e_value` on the clock's forward R series, testing
                   H0: mean R <= 0. It is a non-negative supermartingale under H0, so by Ville's
                   inequality P(sup_t E_t >= 1/alpha) <= alpha AT EVERY t SIMULTANEOUSLY. That is
                   what makes hourly re-reading legitimate. `anytime_reject` is E >= 1/0.05 = 20.
  * `lower_cb`  -- `forward_verdict.sequential_lower_bound`, the desk's ONE always-valid lower
                   confidence bound on mean R (Robbins normal mixture at alpha 0.05, variance
                   proxy = max(sample sd, half the observed range)). A second implementation of a
                   confidence sequence is the last thing this desk needs.
  * `looks`     -- how many passes have READ this clock, persisted in data/forward_looks.json.
                   The count is the alpha the fixed test has been spending and never declaring.

IT CHANGES NO DECISION. The promoter keeps its bar, `verdict()` is untouched, and nothing above
reads these fields. What the desk gets is the DISAGREEMENT named: a candidate the fixed-sample
test passes and the e-process does not is listed by name, with both numbers and the look count
beside it. Below `ANYTIME_MIN_TRADES` trades the row is UNMEASURED (L1.28a) -- an e-value drawn
from four trades is a number that looks like evidence.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

SHADOW = BASE / "reports" / "shadow"
CERTS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
OUT = BASE / "data" / "forward_reconcile.json"
#: The persisted look counter, resolved from BASE at call time so a test that repoints BASE does
#: not write the box's own state file. Rows are never deleted: a clock that leaves and re-enrols
#: keeps its look count, because the alpha those looks spent was really spent.
LOOKS_NAME = "forward_looks.json"
RANKER = "FORWARD_SLOT_RANKER.json"

#: ONE alpha for both gates. `forward_stats.holm_alpha` converts it into a fixed-sample t bar and
#: Ville's inequality converts the same number into a wealth threshold 1/alpha; reading them from
#: one constant is what stops the two drifting apart.
ANYTIME_ALPHA = 0.05
ANYTIME_THRESHOLD = 1.0 / ANYTIME_ALPHA
#: Below this many forward trades a candidate is UNMEASURED rather than "not rejecting".
ANYTIME_MIN_TRADES = 5

TERMINAL = {"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED",
            "RETIRED_ORPHAN", "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE",
            "QUARANTINED_UNCERTIFIED"}


def _read(p: Path) -> dict:
    try:
        v = json.loads(p.read_text("utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_atomic(path: Path, doc: dict) -> bool:
    """Write a state file without ever leaving a half-written one. False on any OS refusal --
    this organ's monitoring must not take the reconcile down for a read-only directory."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        try:
            os.replace(tmp, path)
        except PermissionError:          # a read-only destination is WinError 5 on this box
            path.chmod(0o644)
            os.replace(tmp, path)
        return True
    except OSError:
        return False


def _engine_clock_families() -> dict[str, str]:
    """Every clock key the engine will build from a certificate, named by the ENGINE, mapped to
    the strategy family the engine runs it as.

    ARITY IS NOT UNPACKED POSITIONALLY. `certified_sleeves()` was widened from
    (sym, window, params) to (sym, window, params, family) and this reader still destructured
    three, so it raised `too many values to unpack` on EVERY pass from 2026-08-26 onward and
    `enrolled_keys` returned an empty set. Measured consequence: the reconciler ran blind for a
    full day -- orphan retirement (its whole purpose) silently disabled, while two certified,
    running overnight_gap_decay clocks were retired as UNRECONSTRUCTIBLE because the family-shaped
    key `SYM.family.window` parses as selector="overnight_gap_decay". Slicing with a default keeps
    this reader alive across the NEXT widening too; a second implementation of the engine's key
    format is the drift this whole function exists to avoid.
    """
    import shadow_forward as sf
    fams: dict[str, str] = {
        sf.sleeve_key(s, w, dict(sf.WINDOWS.get(w, {}))): "session_range_breakout"
        for s, w in sf.SLEEVES}
    for row in sf.certified_sleeves():
        sym, win, params = row[0], row[1], row[2]
        family = row[3] if len(row) > 3 else "session_range_breakout"
        # SIDE IS SLICED WITH A DEFAULT, for the same reason `family` is: this reader
        # destructured three when the engine widened to four and raised
        # `too many values to unpack` on EVERY pass for a full day, silently disabling
        # orphan retirement. Widening to five must not repeat that, and a default of
        # LONG here is correct rather than merely safe -- `sleeve_key` only appends a
        # side marker for SHORT, so a long key is unchanged either way.
        side = row[4] if len(row) > 4 else "LONG"
        try:
            key = sf.sleeve_key(sym, win, params, family, side)
        except TypeError:
            # AN ENGINE REVISION THAT PREDATES THE SIDE PARAMETER. Passing five
            # positionally to a four-argument `sleeve_key` is the same defect this
            # function's docstring is about, committed from the other end -- and it
            # would again return "nothing is enrolled" for the whole book.
            # Nothing is lost by falling back: a LONG key is identical either way,
            # and an engine that cannot take a side cannot be running a short clock.
            key = sf.sleeve_key(sym, win, params, family)
        fams[key] = str(family)
    return fams


def _engine_clock_keys() -> set[str]:
    """The key set of `_engine_clock_families` -- one reader of the engine's key format."""
    return set(_engine_clock_families())


def engine_clock_families() -> dict[str, str] | None:
    """{clock key: strategy family} as the engine names them, or None if unreadable."""
    try:
        return _engine_clock_families()
    except Exception as exc:
        print(f"  WARN: engine clock families unreadable ({exc}); family labels fall back to rows")
        return None


def _certificate_families() -> dict[str, str]:
    """{certificate id: declared family} from the survivors file's `shadow_spec`.

    The qquant lane's rows carry the certificate id and a display cell, neither of which names the
    family without parsing; the certificate itself declares it.
    """
    out: dict[str, str] = {}
    for key, row in (_read(CERTS).get("survivors") or {}).items():
        spec = row.get("shadow_spec") if isinstance(row, dict) else None
        fam = spec.get("family") if isinstance(spec, dict) else None
        if fam:
            out[str(key)] = str(fam)
    return out


def _family_name(key: str, row: dict | None, engine_fams: dict[str, str],
                 cert_fams: dict[str, str]) -> tuple[str, str]:
    """(the name to classify, where it came from). EXACT SOURCES FIRST, PARSING LAST, in the
    same spirit as the certificate match above: the engine's own map, then what the row declares,
    then the certificate it cites, then its display cell, and only then the key's text."""
    if key in engine_fams:
        return engine_fams[key], "engine"
    if isinstance(row, dict):
        if row.get("family"):
            return str(row["family"]), "row.family"
        choice = row.get("choice")
        if isinstance(choice, dict) and choice.get("family"):
            return str(choice["family"]), "row.choice.family"
        cert = str(row.get("certificate") or "")
        if cert in cert_fams:
            return cert_fams[cert], "certificate.shadow_spec.family"
        if row.get("cell"):
            return str(row["cell"]), "row.cell"
    return key, "key"


def family_budget(enrolled: set[str] | None, rows: dict[str, dict],
                  engine_fams: dict[str, str] | None) -> dict:
    """THE PARTITIONED MULTIPLE-TESTING BUDGET, AND WHAT IT NOW DECIDES.

    The desk corrects its forward cohort as ONE Holm family of `MAX_FORWARD_SLOTS` seats, so a new
    clock in one mechanism tightens the bar for every clock in every other. `libs.validation.
    family_multiplicity` holds the partitioned alternative -- each census family corrected against
    its own m -- and until now its only reader was a breadth report over slot names. This emits,
    per ENROLLED clock, the family the census places it in and that family's own BH bar, beside
    the flat cohort's numbers.

    UNCLASSIFIED is floored at the largest declared family (`effective_m`), so a clock whose
    mechanism the census cannot place pays the worst bar on the desk rather than a cheaper one --
    declining to declare must never be the cheaper path. UNKNOWN enrolment reports UNMEASURED:
    a clock that cannot be enumerated cannot be placed.

    THE ENROLMENT CAP -- WHAT REPLACED `"decides": "NOTHING"` (review R4, 2026-09-17)
    ---------------------------------------------------------------------------------
    A measured shadow price that decides nothing is a price nobody pays. The same Holm machinery
    that prices the bars prices the SEATS, and the arithmetic is stated rather than asserted:

        per_candidate_charge = holm_alpha(MAX_FORWARD_SLOTS, 1) = alpha / 12   (the desk's own
                               standing per-seat level -- what one forward seat costs today)
        family_alpha         = family_error_budget(F)["alpha_per_family"] = alpha
        spent                = n_members * per_candidate_charge
        remaining            = max(0, family_alpha - spent)
        caps[family]         = floor(remaining / per_candidate_charge)

    THIS IS AN EXPANSION, NOT A BRAKE, AND THE DIRECTION MATTERS (GROWTH_GOVERNANCE rule 2). The
    flat cohort gives the WHOLE desk twelve seats. Per-family budgets give twelve to EACH declared
    family, so a family under its own alpha is authorised to enrol clocks the flat cohort forbids
    outright. It bites only where a family has already enrolled past its own error budget, and
    `family_error_budget` publishes what partitioning costs globally in the same block, so the
    price is on the artifact rather than in someone's head.

    EVERY CAP CARRIES ITS MISSED-GROWTH LINE (`missed_growth_lines`), priced from the forward
    ranker's own waiting queue -- what the desk is NOT testing because the cap stands. Zero waiting
    candidates is a measured zero (NOT_BINDING), an unreadable ranker is UNMEASURED, and neither is
    ever read as "free". `libs.portfolio.rails` exposes no writer and registering a new Rail would
    need a `measure_*` in `research/missed_growth.py`, so the lines are published on the artifact
    exactly as `forward_slot_ranker` publishes its own.

    THE CONTRACT WITH THE ENROLMENT PATH (the promoter is NOT edited, and must not be)
    ---------------------------------------------------------------------------------
    Reader: `research/promoter.py` and any engine that enrols a new forward clock.
    Source: `desks/mt5/data/forward_reconcile.json` -> `family_budget`, and NOTHING else. This
            module never calls the promoter and the promoter never imports this one.
    Key:    `family_budget["caps"][<census family>]` -- an INTEGER count of NEW enrolments that
            family may take on this pass, where the family name is
            `libs.validation.family_multiplicity.family_of(<the candidate's declared mechanism>)`.
    Scope:  NEW enrolments only. It never retires, kills, resizes or unseats a running clock, and
            a clock already enrolled is never re-charged.
    Fail-open, deliberately: a missing artifact, `status != "MEASURED"`, a `checked_at` the reader
            judges stale, or a family absent from `caps` is NOT a cap of zero. The reader falls
            back to today's behaviour (uncapped). A research cap that fails CLOSED would let an
            unwritten file quietly stop the desk from testing anything, which is the timid failure
            the growth governance forbids.
    """
    if enrolled is None:
        return {"status": "UNMEASURED",
                "why": "enrolment unreadable this pass; no clock can be placed in a family"}
    try:
        root = str(BASE.parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research.slot_registry import MAX_FORWARD_SLOTS
        from libs.validation import family_multiplicity as fm
        from libs.validation.forward_stats import holm_alpha, holm_bar
    except Exception as exc:
        return {"status": "UNMEASURED",
                "why": f"family_multiplicity unavailable: {type(exc).__name__}: {exc}"}

    cert_fams = _certificate_families()
    clocks: dict[str, dict] = {}
    parts: dict[str, list[str]] = {}
    for key in sorted(enrolled):
        name, via = _family_name(key, rows.get(key), engine_fams or {}, cert_fams)
        fam = fm.family_of(name)
        parts.setdefault(fam, []).append(key)
        clocks[key] = {"family": fam, "declared_from": name, "declared_via": via}
    eff = fm.effective_m(parts)
    families: dict[str, dict] = {}
    for fam, members in sorted(parts.items()):
        m = eff[fam]
        families[fam] = {"n_members": len(members), "effective_m": m,
                         "bh_bar_rank1": fm.bh_bar(m, 1), "holm_bar_rank1": holm_bar(m, 1),
                         "floored_to_largest_declared": m > len(members)}
    for c in clocks.values():
        m = eff[c["family"]]
        c.update({"family_m": m, "bh_bar": fm.bh_bar(m, 1), "holm_bar": holm_bar(m, 1)})
    m_flat = max(1, len(enrolled))
    budget = fm.family_error_budget(len(parts))
    charge = float(holm_alpha(MAX_FORWARD_SLOTS, 1))
    alpha_family = float(budget.get("alpha_per_family") or 0.05)
    caps: dict[str, int] = {}
    cap_detail: dict[str, dict] = {}
    for fam, members in sorted(parts.items()):
        # CHARGED AT THE EFFECTIVE m, NOT THE RAW MEMBER COUNT, for the same reason the bars are:
        # UNCLASSIFIED is floored at the largest declared family, so a cohort of one undeclared
        # mechanism cannot buy eleven new seats while a declared family of four buys eight.
        # Declining to declare must never be the cheaper path -- on the seats as well as the bar.
        m = eff[fam]
        spent = m * charge
        remaining = max(0.0, alpha_family - spent)
        # THE EPSILON IS NOT COSMETIC. floor() on a quotient of two floats that divide exactly
        # loses a whole seat when the division lands at 10.999999999999998, and a seat lost to
        # float dust is a hypothesis the desk never tests. The published alphas carry nine
        # decimals for the same reason: a reader recomputing the cap from a six-decimal charge
        # gets a different integer than the one on the artifact.
        caps[fam] = max(0, math.floor(remaining / charge + 1e-9)) if charge > 0 else 0
        cap_detail[fam] = {
            "n_enrolled": len(members), "charged_m": m,
            "per_candidate_charge": round(charge, 9),
            "family_alpha": alpha_family, "spent_alpha": round(spent, 9),
            "remaining_alpha": round(remaining, 9), "cap": caps[fam],
            "seats_at_this_charge": round(alpha_family / charge) if charge > 0 else 0,
        }
    return {
        "status": "MEASURED",
        "decides": "ENROLMENT_CAP_PER_FAMILY",
        "caps": caps,
        "cap_detail": cap_detail,
        "cap_basis": ("floor(remaining_alpha / per_candidate_charge) per census family, where "
                      "per_candidate_charge = forward_stats.holm_alpha("
                      f"MAX_FORWARD_SLOTS={MAX_FORWARD_SLOTS}, 1) = {charge:.6f} -- the level one "
                      "forward seat already costs -- and the family's own budget is "
                      "family_multiplicity.family_error_budget's alpha_per_family = "
                      f"{alpha_family}. For an integer count that is exactly "
                      "max(0, seats_at_this_charge - charged_m), which is the identity to check "
                      "the artifact against -- charged_m is the family's EFFECTIVE m, so an "
                      "undeclared mechanism buys no more seats than a declared one. NEW "
                      "enrolments only; it never retires, resizes or "
                      "unseats a running clock, and an absent or stale artifact means UNCAPPED, "
                      "never zero"),
        "consumer": ("research/promoter.py and any enrolling engine, through "
                     "data/forward_reconcile.json only -- no import, no call"),
        "missed_growth_lines": _cap_missed_growth(caps, cap_detail, parts),
        "flat_cohort": {
            "max_forward_slots": MAX_FORWARD_SLOTS, "m_enrolled": m_flat,
            "holm_bar_rank1_at_cap": holm_bar(MAX_FORWARD_SLOTS, 1),
            "bh_bar_rank1_at_cap": fm.bh_bar(MAX_FORWARD_SLOTS, 1),
            "holm_bar_rank1_at_enrolled": holm_bar(m_flat, 1),
            "bh_bar_rank1_at_enrolled": fm.bh_bar(m_flat, 1),
        },
        "families": families,
        "clocks": clocks,
        "error_budget": budget,
        "orthogonality_floor": fm.ORTHOGONALITY_FLOOR,
        "basis": ("libs.validation.family_multiplicity (family_of / effective_m / bh_bar); "
                  "UNCLASSIFIED is floored at the largest declared family"),
    }


def _waiting_by_family() -> tuple[dict[str, list[dict]], str | None]:
    """The forward ranker's WAITING queue, grouped into census families -- what the desk would
    enrol next if a seat were free. `(rows_by_family, unmeasured_reason)`.

    This is the only thing that can price an enrolment cap honestly: a cap costs exactly the
    candidates it stops, and the ranker already measures each one's slot value in E[log W] per
    day. No ranker artifact is UNMEASURED, not zero -- and an empty queue is a measured zero.
    """
    try:
        from libs.validation import family_multiplicity as fm
    except Exception as exc:
        return {}, f"family_multiplicity unavailable: {type(exc).__name__}: {exc}"
    path = BASE / "reports" / RANKER
    doc = _read(path)
    if not doc:
        return {}, f"forward ranker unreadable or absent: {path}"
    waiting = doc.get("waiting")
    if not isinstance(waiting, list):
        return {}, f"{RANKER} carries no `waiting` list: the queue depth is unmeasured"
    out: dict[str, list[dict]] = {}
    for row in waiting:
        if not isinstance(row, dict):
            continue
        name = str(row.get("family") or row.get("cell") or "")
        out.setdefault(fm.family_of(name), []).append(row)
    return out, None


def _cap_missed_growth(caps: dict[str, int], detail: dict[str, dict],
                       parts: dict[str, list[str]]) -> list[dict]:
    """One missed-growth row per CAPPED family: what the cap forbids, in the ranker's own units.

    A cap with no ledger line is exactly what the growth governance forbids, so every family whose
    cap is zero gets a row whether or not anything is waiting -- NOT_BINDING is a measurement and
    silence is not. Published here rather than appended to data/missed_growth.jsonl: that ledger is
    keyed by `libs.portfolio.rails.RAILS` and this cap registers no rail, exactly as
    `forward_slot_ranker` publishes its slot-occupancy lines on its own artifact.
    """
    capped = [fam for fam, n in sorted(caps.items()) if n <= 0]
    if not capped:
        return []
    waiting, why_unmeasured = _waiting_by_family()
    now = datetime.now(tz=UTC)
    lines: list[dict] = []
    for fam in capped:
        rows = waiting.get(fam, [])
        values = [float(r["slot_value"]) for r in rows
                  if isinstance(r.get("slot_value"), (int, float))
                  and not isinstance(r.get("slot_value"), bool)]
        line = {
            "day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
            "rail": f"forward_enrolment_cap:{fam}", "kind": "opportunity_cost",
            "units": "E[log W] per day of book growth, per day of forward wait",
            "family": fam, "cap": int(caps.get(fam, 0)),
            "n_enrolled": int((detail.get(fam) or {}).get("n_enrolled", len(parts.get(fam, [])))),
            "n_blocked": len(rows),
            "why": ("what this family's exhausted error budget forbids the desk from testing this "
                    "pass, priced from FORWARD_SLOT_RANKER.json's waiting queue; PUBLISHED, never "
                    "appended to data/missed_growth.jsonl and never executed -- the cap registers "
                    "no rail and stops no running clock"),
        }
        if why_unmeasured is not None:
            line.update(value=None, verdict="UNMEASURED", unmeasured=why_unmeasured)
        elif not rows:
            line.update(value=0.0, verdict="NOT_BINDING",
                        note="no candidate of this family is waiting for a seat, so the cap "
                             "forbade nothing this pass -- a measured zero, not an absent number")
        elif not values:
            line.update(value=None, verdict="UNMEASURED",
                        unmeasured=f"{len(rows)} waiting candidate(s) carry no measured slot_value")
        else:
            line.update(value=round(-sum(values), 14), verdict="COSTS_GROWTH",
                        n_priced=len(values), best_blocked=round(max(values), 14))
        lines.append(line)
    return lines


# --------------------------------------------------------------- anytime-valid forward monitoring
#: Resolved once per process. `_rows_of` is called for every enrolled clock, so an unguarded
#: import failure would print its warning once per clock -- a hundred and fifty identical lines
#: in the leg's log, which is how a real warning becomes invisible.
_PA: list[object | None] = []


def _posterior() -> object | None:
    """`posterior_alpha`'s tolerant readers, or None. ONE implementation of "what counts as a
    forward trade" -- `phase == "forward"` rows only, an unreconstructed live R dropped rather
    than read as a zero. A second parser of these ledgers is how two organs come to disagree
    about how many trades a clock has."""
    if _PA:
        return _PA[0]
    try:
        import posterior_alpha as pa
        _PA.append(pa)
    except Exception as exc:
        print(f"  WARN: posterior_alpha readers unavailable ({exc}); anytime monitor reads raw")
        _PA.append(None)
    return _PA[0]


def _rows_of(path: Path) -> list[dict]:
    pa = _posterior()
    raw = pa._read_json(path, []) if pa is not None else None
    if raw is None:
        try:
            raw = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return []
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _fnum(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def live_series() -> dict[str, list[float]]:
    """{live sleeve name: its per-trade R}, from data/live_ledger.jsonl by posterior_alpha's own
    rule: a row stamped `r_multiple: 0.0` against non-zero P&L is an UNRECONSTRUCTED R, not an
    observation of no edge, and is dropped."""
    path = BASE / "data" / "live_ledger.jsonl"
    pa = _posterior()
    if pa is not None:
        rows = pa._read_jsonl(path)
    else:
        try:
            lines = path.read_text("utf-8-sig").splitlines()
        except OSError:
            return {}
        rows = []
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    out: dict[str, list[float]] = {}
    for row in rows:
        name = str(row.get("sleeve") or "").strip()
        if not name or name.startswith("["):
            continue                                   # a broker comment, not a sleeve
        value = _fnum(row.get("r_multiple"))
        pl = _fnum(row.get("pl_quote")) or 0.0
        if row.get("r_unreconstructible") or value is None or (value == 0.0 and pl != 0.0):
            continue
        out.setdefault(name, []).append(value)
    return out


def forward_series(key: str, row: dict | None,
                   live: dict[str, list[float]] | None = None) -> tuple[list[float], str]:
    """(forward per-trade R, where it came from) for one enrolled clock.

    The shadow ledger first (`ledger_<key with dots as underscores>.json`), then the same name
    with the parameter signature stripped, then the live ledger for a clock promoted to a sleeve,
    then the row's own moments -- which are NOT a series and are reported as such rather than
    silently imputed.

    THE STRIPPED NAME IS FLAGGED, NOT SILENTLY ACCEPTED. `shadow_forward` writes one ledger per
    (symbol, family, window) and appends no parameter signature, so EVERY parameterisation of one
    cell shares that file -- `XAUUSD.asia#rr=1.5` and `#rr=2.5` read the same trades. The row's own
    `forward_t` is per-parameterisation and this series is not, so the basis says
    `shadow_ledger_forward_shared` wherever that fallback fired and a reader can see which rows
    hold a series that is not exclusively their clock's.
    """
    base_key = key.split("#", 1)[0]
    exact = key.replace(".", "_")
    for stem in (exact, base_key.replace(".", "_")):
        path = SHADOW / f"ledger_{stem}.json"
        if not path.exists():
            continue
        r = [v for v in (_fnum(t.get("r_multiple")) for t in _rows_of(path)
                         if str(t.get("phase") or "") == "forward") if v is not None]
        if r:
            return r, ("shadow_ledger_forward" if stem == exact
                       else "shadow_ledger_forward_shared")
    names = live if live is not None else live_series()
    if names:
        stem = base_key.replace(".", "_")
        if stem in names:
            return list(names[stem]), "live_ledger"
        hits = [n for n in names if n.startswith(stem)]
        if len(hits) == 1:                             # an ambiguous prefix names nothing
            return list(names[hits[0]]), "live_ledger"
    n = _fnum((row or {}).get("n"))
    if n and n > 0:
        return [], "row_moments"
    return [], "none"


def fixed_sample_t(r: list[float], row: dict | None) -> tuple[float | None, str]:
    """THE EXISTING NUMBER, not a new one: `shadow_forward` publishes `forward_t` = mean /
    (sd / sqrt(n)) on every row it evaluates, and that is the statistic the desk re-reads every
    hour. It is preferred from the row and only recomputed -- by the identical formula -- for a
    lane that publishes none, so this organ can never disagree with the engine about it."""
    v = _fnum((row or {}).get("forward_t"))
    if v is not None:
        return round(v, 3), "row.forward_t (shadow_forward)"
    n = len(r)
    if n < 2:
        return None, f"{n} trade(s): a t-stat needs two"
    mean = sum(r) / n
    var = sum((x - mean) ** 2 for x in r) / (n - 1)
    if var <= 0:
        return None, "zero dispersion: the series never moved"
    return round(mean / ((var / n) ** 0.5), 3), "recomputed mean/(sd/sqrt(n)): row published none"


def bump_looks(keys: list[str], now: str, path: Path | None = None) -> tuple[dict[str, int], bool]:
    """Count this pass as a LOOK at every enrolled clock, persisted. (counts, persisted?).

    The number this file holds is the alpha the fixed-sample test has been spending without
    declaring it: a bar calibrated for one look, re-read `looks` times. Rows of clocks not
    enrolled this pass are left exactly as they are -- a clock that leaves and comes back keeps
    its count, because the looks it already cost were really taken.
    """
    p = path if path is not None else BASE / "data" / LOOKS_NAME
    doc = _read(p)
    clocks = doc.get("clocks") if isinstance(doc.get("clocks"), dict) else {}
    out: dict[str, int] = {}
    for key in keys:
        prev = clocks.get(key) if isinstance(clocks.get(key), dict) else {}
        n = int(_fnum(prev.get("looks")) or 0) + 1
        clocks[key] = {"looks": n, "first_look_at": prev.get("first_look_at") or now,
                       "last_look_at": now}
        out[key] = n
    persisted = _write_atomic(p, {
        "at": now, "n_clocks": len(clocks), "clocks": clocks,
        "rule": ("one row per forward clock, incremented every pass that READS it. A fixed-sample "
                 "bar is calibrated for one look; this is how many it has actually had")})
    return out, persisted


def anytime_monitor(enrolled: set[str] | None, rows: dict[str, dict], fam: dict | None,
                    now: str, looks_path: Path | None = None) -> dict:
    """PEEK-SAFE EVIDENCE BESIDE THE PEEK-UNSAFE BAR, per enrolled clock. Decides nothing.

    e_value  `anytime_valid.e_value` on the forward R series, H0: mean R <= 0. Ville's inequality
             bounds sup_t P(E_t >= 1/alpha) by alpha AT EVERY t, so this may be re-read hourly.
    lower_cb `forward_verdict.sequential_lower_bound` at alpha 0.05 -- the desk's one always-valid
             lower bound on mean R (Robbins mixture, variance proxy max(sample sd, range/2)).
    looks    how many passes have read this clock (data/forward_looks.json).
    disagreement  the fixed-sample verdict against the anytime one. A clock the t-stat passes and
             the e-process does not is NAMED, which is the entire point of publishing both.
    """
    if enrolled is None:
        return {"status": "UNMEASURED",
                "why": "enrolment unreadable this pass; no clock can be monitored"}
    try:
        root = str(BASE.parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        import forward_verdict as fv

        from libs.research import anytime_valid as av
    except Exception as exc:
        return {"status": "UNMEASURED",
                "why": f"anytime_valid unavailable: {type(exc).__name__}: {exc}"}

    keys = sorted(enrolled)
    looks, persisted = bump_looks(keys, now, looks_path)
    fam_clocks = (fam or {}).get("clocks") if isinstance(fam, dict) else None
    flat = (fam or {}).get("flat_cohort") if isinstance(fam, dict) else None
    flat_bar = _fnum((flat or {}).get("holm_bar_rank1_at_enrolled"))
    live = live_series()
    clocks: dict[str, dict] = {}
    n_any = n_fixed = n_dis = n_measured = 0
    for key in keys:
        row = rows.get(key)
        r, basis = forward_series(key, row, live)
        n = len(r)
        t, t_src = fixed_sample_t(r, row)
        bar = _fnum(((fam_clocks or {}).get(key) or {}).get("holm_bar"))
        if bar is None:
            bar = flat_bar
        fixed_reject = bool(t is not None and bar is not None and t >= bar)
        e = log_e = lcb = None
        if n < ANYTIME_MIN_TRADES:
            status = "UNMEASURED"
            why = f"{n}/{ANYTIME_MIN_TRADES} forward trades ({basis}): too few to monitor"
        elif n < av._MIN_OBS:
            status = "UNMEASURED"
            why = (f"{n}/{av._MIN_OBS} forward trades: below the e-process's own floor, where its "
                   "estimate of scale is not trustworthy")
        else:
            e = float(av.e_value(r))
            if e <= 0.0:
                status = "UNMEASURED"
                why = ("the e-process returned no capital: a degenerate series (no variation) or "
                       "a tail that excluded every mixture component")
                e = None
            else:
                status = "MEASURED"
                why = ("" if basis != "shadow_ledger_forward_shared" else
                       "series read from the cell's shared ledger: shadow_forward writes one "
                       "ledger per (symbol, family, window), so every parameterisation of this "
                       "cell reads the same trades")
                log_e = round(math.log(e), 6)
                e = round(e, 6)
                n_measured += 1
                b = fv.sequential_lower_bound(r, alpha=ANYTIME_ALPHA)
                lcb = round(b, 6) if math.isfinite(b) else None
        anytime_reject = bool(e is not None and e >= ANYTIME_THRESHOLD)
        n_any += int(anytime_reject)
        n_fixed += int(fixed_reject)
        n_dis += int(anytime_reject != fixed_reject)
        # THE ENGINE'S OWN COUNT, BESIDE THE ONE THIS ORGAN READ. They differ when the ledger is
        # missing or was written by another lane, and `n: 0` next to a row claiming nine trades is
        # a discrepancy a reader must be able to see rather than a number to be trusted.
        n_row = _fnum((row or {}).get("n"))
        clocks[key] = {"n": n, "n_row": int(n_row) if n_row is not None else None,
                       "looks": looks.get(key, 0), "basis": basis, "status": status,
                       "e_value": e, "log_e": log_e, "lower_cb": lcb,
                       "anytime_reject": anytime_reject, "fixed_sample_t": t,
                       "fixed_t_source": t_src, "holm_bar": bar, "fixed_reject": fixed_reject,
                       "disagreement": anytime_reject != fixed_reject, "why": why}
    disagreeing = sorted(k for k, v in clocks.items() if v["disagreement"])
    return {
        "status": "MEASURED",
        "summary": {
            "n_enrolled": len(keys), "n_anytime_reject": n_any, "n_fixed_reject": n_fixed,
            "n_disagree": n_dis,
            "rule": ("an e-process may be monitored continuously and stopped at any time and "
                     "remains valid; the t-stat re-read on every look is not"),
        },
        "alpha": ANYTIME_ALPHA, "e_threshold": ANYTIME_THRESHOLD,
        "min_trades": ANYTIME_MIN_TRADES,
        "n_measured": n_measured, "n_unmeasured": len(keys) - n_measured,
        "max_looks": max(looks.values(), default=0),
        "looks_state": str(looks_path if looks_path is not None else BASE / "data" / LOOKS_NAME),
        "looks_persisted": persisted,
        "fixed_passes_anytime_does_not": sorted(
            k for k, v in clocks.items() if v["fixed_reject"] and not v["anytime_reject"]),
        "disagreeing": disagreeing,
        "decides": ("NOTHING -- the promoter keeps its bar and no field here is read by any "
                    "promotion path. Both numbers are published so the disagreement is named"),
        "basis": ("libs.research.anytime_valid.e_value (H0: mean R <= 0, Ville) and "
                  "forward_verdict.sequential_lower_bound (Robbins mixture at alpha "
                  f"{ANYTIME_ALPHA}); the fixed-sample t is shadow_forward's own forward_t "
                  "against this clock's published Holm bar"),
        "clocks": clocks,
    }


def _invariance_rows() -> dict:
    """The causal organ's per-mechanism invariance verdicts, for publication beside the
    certificates. Never raises and never blocks: a missing organ is UNMEASURED with its reason.

    Kept to the counts plus the mechanisms that FAILED, because the whole table is the causal
    organ's own artifact and duplicating it here would create a second copy to drift."""
    try:
        import causal_invariance
        doc = json.loads(causal_invariance.OUT.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"status": "UNMEASURED",
                "why": f"reports/CAUSAL_INVARIANCE.json unreadable: {type(exc).__name__}"}
    pairs = doc.get("by_pair") if isinstance(doc.get("by_pair"), dict) else {}
    broken = {k: v for k, v in pairs.items()
              if isinstance(v, dict) and v.get("verdict") == "NON_INVARIANT"}
    return {"status": "OK", "at": doc.get("at"), "counts": doc.get("counts"),
            "n_pairs": len(pairs), "non_invariant": broken,
            "source": "desks/mt5/reports/CAUSAL_INVARIANCE.json",
            "note": ("a certificate is a claim that ten gates passed; this is a claim that the "
                     "effect did not change with session, year or volatility regime. It gates "
                     "nothing -- the sealed promoter does not read it."),
            }


def certified_clock_keys() -> set[str] | None:
    """The exact keys of clocks that are BOTH certified and runnable, or None if unreadable.

    `certified_sleeves()` is derived exclusively from `authorized_runs` -- the fail-closed
    admission door -- so membership here is proof of a ten-gate certificate that needs no string
    parsing at all. Every retirement branch below that guessed a certificate from the key's dots
    was guessing at something this set already knows exactly.
    """
    try:
        return _engine_clock_keys()
    except Exception as exc:
        print(f"  WARN: certified clock keys unreadable ({exc}); refusing to retire on cert")
        return None


def enrolled_keys() -> set[str] | None:
    """Exactly what the running engines will touch this cycle -- the only real clocks.

    Returns None for UNKNOWN (the enrolment source could not be read) and never conflates it with
    the empty set: absence is not a clean verdict, and an unreadable engine must not read as "no
    engine enrols anything", which is a licence to retire the entire forward book.
    """
    keys: set[str] = set()
    try:
        keys |= _engine_clock_keys()
    except Exception as exc:
        print(f"  WARN: shadow_forward enrolment unreadable ({exc}); treating its rows as enrolled")
        return None
    # qquant/scalp own their rows; this reconciler never calls another engine's rows orphaned.
    for f in ("qquant_shadow_state.json", "scalp_shadow_state.json"):
        d = _read(SHADOW / f)
        keys |= {k for k, v in d.items() if isinstance(v, dict)}
        keys |= set((d.get("sleeves") or {}).keys())
    return keys


def certified_pairs() -> set[tuple[str, str]]:
    try:
        from shadow_admission import authorized_specs
        return {(s[0], s[1]) for s in authorized_specs(BASE)}
    except Exception as exc:
        print(f"  WARN: admission unreadable ({exc}); refusing to retire anything this pass")
        return set()


def certified_ids() -> set[str]:
    """Exact certificate identities, including qquant's non-symbol display keys.

    A qquant state key starts ``qquant.<hunt>.<cell>``; splitting it at dots and
    treating the first two fields as ``symbol.selector`` turns a valid AUDNZD
    certificate into the fictitious pair ``qquant.hunt16``.  Prefer the frozen
    certificate id before falling back to the legacy pair-shaped identity.
    """
    try:
        from gate_policy import all_ten_pass, is_exact_policy
        doc = _read(CERTS)
        if not is_exact_policy(doc.get("gate_policy")):
            return set()
        return {
            str(key) for key, row in (doc.get("survivors") or {}).items()
            if isinstance(row, dict) and all_ten_pass(row.get("gates"))
        }
    except Exception as exc:
        print(f"  WARN: exact certificate ids unreadable ({exc}); using spec identity only")
        return set()


def gauntlet(cells: list[dict]) -> dict:
    """Run the canonical ten gates on reconstructed cells. Returns {key: verdict-row}."""
    if not cells:
        return {}
    sys.path.insert(0, str(BASE.parent.parent / "desks" / "mt5" / "scripts"))
    try:
        import external_gauntlet as eg
    except Exception as exc:
        print(f"  gauntlet unavailable ({exc}); no certification attempted this pass")
        return {}
    meta = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))
    built, keys = [], []
    for c in cells:
        obj = eg.build_cell(c["sym"], c["family"], c["params"], meta)
        if obj is None:
            print(f"  SKIP {c['key']}: cell would not build (missing bars or bad params)")
            continue
        built.append(obj)
        keys.append(c["key"])
    if not built:
        return {}
    res = eg.run_gauntlet(built, "forward_reconcile", meta)
    out = {}
    for key, v in zip(keys, res.get("verdicts", []), strict=False):
        out[key] = v
    return out


def _running_unfrozen(actions: list[dict]) -> int:
    """Keys flagged IDENTITY_UNFROZEN this pass that the same pass did not retire."""
    flagged = {str(a.get("key")) for a in actions if a.get("action") == "IDENTITY_UNFROZEN"}
    retired = {str(a.get("key")) for a in actions
               if str(a.get("action", "")).startswith("RETIRED")}
    return len(flagged - retired)


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    enrolled = enrolled_keys()
    cert_clock_keys = certified_clock_keys()
    certs = certified_pairs()
    cert_ids = certified_ids()
    # UNKNOWN IS NOT ZERO. If either the engine's enrolment or its certified-clock list is
    # unreadable, this pass has no basis on which to retire anything -- it can only report.
    unknown_enrolment = enrolled is None or cert_clock_keys is None
    if unknown_enrolment:
        print("forward reconcile: enrolment UNKNOWN -- retirement disabled for this pass")
    if not certs:
        print("forward reconcile: admission unreadable -- FAIL SOFT, nothing changed")
        return 0

    actions: list[dict] = []
    to_gauntlet: list[dict] = []
    # Every row seen this pass, by key, for the family census at the end. Read before any
    # mutation below; the family a row declares does not change with its status.
    all_rows: dict[str, dict] = {}
    # IDENTITY COVERAGE -- the property `sleeve_registry.json` actually guarantees. The registry is
    # IDEMPOTENT by construction (`freeze` returns early once a key is frozen), so its file age
    # says nothing at all: an unchanged registry is the HEALTHY state. The job manifest was
    # nonetheless gauging it by age with a 3h window, which is red whenever the desk is well --
    # exactly the fence that trains readers to skim. What matters is that no clock RUNS without a
    # frozen identity, because an unfrozen clock is one whose parameters can drift mid-window.
    try:
        from sleeve_registry import REGISTRY as _REG_PATH
        _frozen = set((_read(_REG_PATH).get("sleeves") or {}).keys())
    except Exception as exc:
        print(f"  WARN: sleeve registry unreadable ({exc}); identity coverage UNMEASURED")
        _frozen = None
    try:
        from shadow_forward import WINDOWS
    except Exception:
        WINDOWS = {}

    for fname in ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json"):
        path = SHADOW / fname
        data = _read(path)
        if not data:
            continue
        changed = False
        # BOTH LAYERS. scalp_shadow keeps its rows under a `sleeves` sub-dict; iterating only
        # data.items() left four live scalp clocks INVISIBLE to this reconciler while the
        # dashboard still counted them -- an organ that cannot see a lane cannot govern it.
        rows_here = [(k, v) for k, v in data.items() if isinstance(v, dict) and "status" in v]
        sub = data.get("sleeves")
        if isinstance(sub, dict):
            rows_here += [(k, v) for k, v in sub.items() if isinstance(v, dict) and "status" in v]
        for key, row in rows_here:
            if not isinstance(row, dict) or "status" not in row:
                continue
            all_rows.setdefault(key, row)
            _status = str(row.get("status") or "").upper()
            # REPAIR WHAT THIS ORGAN GOT WRONG. Only the two branches that INFER a verdict from
            # the key's shape are reversible here -- RETIRED_GATE_FAIL is a measured gauntlet
            # result and KILL/PROMOTED are decisions elsewhere, so none of them are touched. The
            # proof required to reverse is exact and needs no parsing: the engine itself names
            # this key from a live certificate (`cert_clock_keys`) AND will run it this cycle
            # (`enrolled`). Measured 2026-08-27: EURZAR and USDZAR overnight_gap_decay were
            # retired at 04:01 and the engine was still writing `last_attempt_at` to them at
            # 07:45 -- sleeves being traded while their evidence was discarded.
            # The revived clock is stamped FRESH, never inherited: the engine re-derives n,
            # n_historical and exp_r from `forward_start` on its next pass, so every trade before
            # this moment falls back to HISTORICAL exactly as the two-stage law requires.
            if (_status in {"RETIRED_ORPHAN", "RETIRED_UNRECONSTRUCTIBLE"}
                    and not unknown_enrolment and cert_clock_keys is not None
                    and key in cert_clock_keys and enrolled and key in enrolled):
                row["status"] = "ACTIVE"
                row["forward_start"] = datetime.now(tz=UTC).isoformat()
                row.pop("retired_at", None)
                row.pop("retire_reason", None)
                row.pop("promotion_authority", None)
                actions.append({"key": key, "action": "REVIVED_CERTIFIED", "why": (
                    "retired on a key-shape inference while holding a live ten-gate certificate "
                    "and an active enrolment; clock restamped FRESH so no pre-registration "
                    "boundary is inherited")})
                changed = True
                continue
            if _status in TERMINAL:
                continue
            # shadow_forward's lane is the one `freeze()` serves; qquant/scalp own their own rows.
            if _frozen is not None and fname == "shadow_state.json" and key not in _frozen:
                actions.append({"key": key, "action": "IDENTITY_UNFROZEN", "why": (
                    "running clock with no frozen identity in sleeve_registry.json; its "
                    "parameters can drift mid-window and nothing would notice. Reported, never "
                    "retired -- freezing is the engine's job, not the reconciler's.")})
            # STRIP THE PARAMETER SIGNATURE FIRST. Clock keys are `SYM.selector#p=v_p=v` since
            # each certified parameterization owns its own clock; splitting on "." alone made
            # `sel` come out as "asia#rr=1.5", which matched no window and no certificate, so
            # this reconciler retired 11 legitimately certified clocks as UNRECONSTRUCTIBLE.
            base_key = key.split("#", 1)[0]
            parts = base_key.split(".")
            sym, sel = parts[0], (parts[1] if len(parts) > 1 else "")
            # NOT EVERY LANE KEYS ROWS AS "SYMBOL.selector". qquant uses
            # "qquant.hunt16.json.<SYM> <family> <side> <window> <state>", so splitting on "."
            # produced sym="qquant" -- matching no certificate -- and this reconciler retired
            # AUDNZD, a genuinely certified sleeve, as UNRECONSTRUCTIBLE. The engine then reset
            # its status to ACTIVE on the next pass while the retire_* fields stayed behind,
            # leaving the contradictory row the principal found. When a row carries its own
            # descriptor, believe the row, not the key.
            _cell = str(row.get("cell") or row.get("certificate") or "")
            if not any(sym == a for a, _b in certs) and _cell:
                _tok = _cell.replace(".", " ").split()
                for _t in _tok:
                    if any(_t == a for a, _b in certs):
                        sym = _t
                        break
                for _t in _tok:
                    if any(_t == b for _a, b in certs):
                        sel = _t
                        break
            certificate_id = str(row.get("certificate") or key)
            # EXACT FIRST, PARSED SECOND. `cert_clock_keys` is named by the engine's own
            # `sleeve_key`, so a match is proof of certification with no dot-splitting involved.
            # The parsed fallbacks below only ever ADD matches; they can no longer be the reason a
            # family-shaped key like `EURZAR.overnight_gap_decay.asia` is judged uncertified.
            has_cert = (
                (cert_clock_keys is not None and key in cert_clock_keys)
                or certificate_id in cert_ids
                or any(sym == a and (sel == b or not sel) for a, b in certs)
            )

            if not unknown_enrolment and enrolled and key not in enrolled:
                row["status"] = "RETIRED_ORPHAN"
                row["promotion_authority"] = False
                row["retired_at"] = now
                row["retire_reason"] = (
                    "no engine enrols this row; its day count and trade count are FROZEN. A "
                    "stopped clock counted as forward evidence would take a day-14 verdict on "
                    "stale trades. Evidence preserved; revive only through a fresh certificate "
                    "and a new pre-registered window.")
                actions.append({"key": key, "action": "RETIRED_ORPHAN"})
                changed = True
                continue

            if has_cert:
                # CLEAR STALE RETIREMENT METADATA. A row that is certified and running must not
                # also carry retired_at/retire_reason from an earlier mistaken pass: a reader
                # cannot tell which field to believe, and the dashboard showed both.
                if row.pop("retired_at", None) or row.pop("retire_reason", None):
                    actions.append({"key": key, "action": "RETIREMENT_CLEARED",
                                    "why": "row is certified and running; stale retirement "
                                           "metadata removed so the state is unambiguous"})
                    changed = True
                continue

            # A FULLY-SPECIFIED SLEEVE THIS GAUNTLET CANNOT JUDGE keeps measuring but loses its
            # authority. The scalp lane carries complete params (family, session, stop/target
            # ATR, max_hold) on M5/M15 -- reconstructible in principle, but the canonical
            # gauntlet builds H1 session cells, so it cannot rule on them yet. Retiring them
            # would destroy a live research line for a tooling gap, and the principal's standing
            # rule is that caps never reduce discovery. Stripping PROMOTION AUTHORITY is the
            # exact, minimal correction: evidence keeps accruing (free, useful), but the lane
            # can no longer reach capital without passing the one door. Measured 2026-08-26:
            # four scalp sleeves held `promotion_authority: true` with no certificate at all.
            if row.get("choice") or row.get("timeframe"):
                if row.get("promotion_authority") is not False:
                    row["promotion_authority"] = False
                    row["gate_reason"] = (
                        "no canonical ten-gate certificate; promotion authority REVOKED until "
                        "certified. The sleeve keeps accruing forward evidence -- that costs "
                        "nothing and is never wasted -- but it cannot promote. Certifying it "
                        "needs a gauntlet on its own timeframe (register #134).")
                    actions.append({"key": key, "action": "AUTHORITY_REVOKED"})
                    changed = True
                continue

            # enrolled, running, no certificate -> it must face the gauntlet
            if sel in WINDOWS and len(parts) == 2:
                to_gauntlet.append({"key": key, "sym": sym, "family": "session_range_breakout",
                                    "params": dict(WINDOWS[sel]), "file": fname})
            elif unknown_enrolment:
                # cannot prove it is uncertified while the certificate list is unreadable
                continue
            else:
                row["status"] = "RETIRED_UNRECONSTRUCTIBLE"
                row["promotion_authority"] = False
                row["retired_at"] = now
                row["retire_reason"] = (
                    "running without a ten-gate certificate, and its exact parameters cannot be "
                    "reconstructed from the cell name. Guessing them is forbidden -- a gauntlet "
                    "run on guessed parameters certifies a strategy nobody is trading.")
                actions.append({"key": key, "action": "RETIRED_UNRECONSTRUCTIBLE"})
                changed = True
        if changed:
            path.write_text(json.dumps(data, indent=2), "utf-8")

    # --- certify or retire the reconstructible ones -------------------------------------------
    verdicts = gauntlet(to_gauntlet)
    if verdicts:
        doc = _read(CERTS)
        survivors = doc.get("survivors") or {}
        n_before = len(survivors)
        from gate_policy import ATTESTATION
        for spec in to_gauntlet:
            key = spec["key"]
            v = verdicts.get(key)
            path = SHADOW / spec["file"]
            data = _read(path)
            row = data.get(key)
            if v is None:
                continue
            if v.get("passed"):
                survivors[f"reconciled.{key}"] = {
                    "hunt": "forward_reconcile", "cell": key, "sym": spec["sym"],
                    "days": v.get("days"), "gates": v.get("stages"), "gated_at": now,
                    "shadow_spec": {"symbol": spec["sym"], "selector": key.split(".")[1],
                                    "family": "session_range_breakout", "is_universe": True,
                                    "hunt": "forward_reconcile", "condition": None},
                }
                actions.append({"key": key, "action": "CERTIFIED"})
                if isinstance(row, dict):
                    row.pop("gate_reason", None)
                    row["certified_at"] = now
            else:
                failed = [g for g, s in (v.get("stages") or {}).items()
                          if not (isinstance(s, dict) and s.get("passed") is True)]
                if isinstance(row, dict):
                    row["status"] = "RETIRED_GATE_FAIL"
                    row["retired_at"] = now
                    row["retire_reason"] = (
                        f"ran the canonical ten gates and failed: {', '.join(failed)}. Evidence "
                        f"preserved; a sleeve that cannot clear the one door does not hold a "
                        f"forward slot.")
                actions.append({"key": key, "action": "RETIRED_GATE_FAIL", "failed": failed})
            if isinstance(row, dict):
                path.write_text(json.dumps(data, indent=2), "utf-8")
        if len(survivors) > n_before:
            doc.update({"n": len(survivors), "gate_policy": ATTESTATION, "survivors": survivors,
                        "swept_at": now})
            CERTS.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
            CANON.write_text(json.dumps(doc, indent=2, default=str), "utf-8")

    # WHAT PASSED EVERY GATE AND STILL CANNOT RUN. Never allowed to break the reconcile:
    # this is a measurement attached to a health report, and a report that dies because
    # an enrichment threw is worse than one missing a field.
    try:
        from shadow_admission import unreachable_certificates
        _unreachable = unreachable_certificates()
    except Exception as exc:
        _unreachable = {"n": None, "error": f"{type(exc).__name__}: {exc}"}

    # THE PARTITIONED BUDGET, BESIDE THE FLAT COHORT. Same rule as the ceiling above: a
    # measurement attached to a health report, never allowed to break the reconcile.
    try:
        _families = family_budget(enrolled, all_rows, engine_clock_families())
    except Exception as exc:
        _families = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    _lines = _families.pop("missed_growth_lines", []) if isinstance(_families, dict) else []

    # ANYTIME-VALID MONITORING, beside the bars it is measured against. Same rule again: a
    # measurement attached to a health report never takes the reconcile down.
    try:
        _anytime = anytime_monitor(enrolled, all_rows, _families, now)
    except Exception as exc:
        _anytime = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}

    # REPORT UNKNOWN AS UNKNOWN. `"enrolled": 0` is what a reader saw for a full day while the
    # real cause was an unpack error -- indistinguishable from an engine that legitimately enrols
    # nothing, which is why nobody chased it. Null carries the distinction the count cannot.
    OUT.write_text(json.dumps(
        {"checked_at": now, "enrolled": None if enrolled is None else len(enrolled),
         "enrolment_readable": not unknown_enrolment,
         "certified_clocks": None if cert_clock_keys is None else len(cert_clock_keys),
         "certified_pairs": len(certs),
         # A CLOCK THIS PASS RETIRED IS NOT A RUNNING CLOCK. The unfrozen check runs before the
         # orphan retirement in the same loop, so eleven RETIRED_ORPHAN rows were also counted as
         # "running clock with no frozen identity" (2026-09-16) and the attestation read a
         # defect that no longer existed. Count only the keys still running after the pass.
         "identity_unfrozen": (None if _frozen is None else _running_unfrozen(actions)),
         # THE CEILING, AS A NUMBER. `certified_pairs` minus `certified_clocks` is a
         # discrepancy a reader has to notice and then investigate; this is the part of
         # that gap the desk can already explain -- certificates that passed all ten
         # gates and cannot enrol because the engine has no leg to run them on. It was
         # a bare `continue` in shadow_admission and left no trace anywhere.
         # Reported beside the counts it explains so the two are read together.
         "unreachable_certified": _unreachable,
         # PER-FAMILY MULTIPLICITY, AND THE ENROLMENT CAP IT NOW DECIDES. Each enrolled clock's
         # census family and that family's own BH bar, beside the flat 12-seat cohort's bar --
         # plus `caps`, the new enrolments each family's own error budget still affords. The
         # enrolment path reads that through THIS FILE and nothing else (see family_budget).
         "family_budget": _families,
         # WHAT THE CAPS FORBID, IN THE RANKER'S UNITS. A cap with no missed-growth line is what
         # the growth governance forbids; an empty list means no family is capped this pass.
         "missed_growth_lines": _lines,
         # THE PEEK-SAFE READING OF THE SAME COHORT. `looks` is how many times the fixed-sample
         # bar beside it has been re-read -- alpha it spends and does not price.
         "anytime_valid": _anytime,
         # THE INVARIANCE VERDICT, PUBLISHED BESIDE THE CERTIFICATE (Tier-1 B16). A certificate
         # says the cell cleared ten gates; this says whether its effect was the SAME number in
         # Asia and in London, in 2023 and in 2025, in a calm tape and a violent one. The two are
         # different claims and the second one was nowhere on the forward row. It gates nothing
         # here -- the promoter is sealed and reads none of this -- and an absent organ leaves
         # the field UNMEASURED rather than absent, so a reader can tell "stable" from "nobody
         # looked" (L1.28a).
         "causal_invariance": _invariance_rows(),
         "actions": actions}, indent=1), "utf-8")
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    print(f"forward reconcile: {len(actions)} action(s) {counts or '{}'}")
    _n_unreach = _unreachable.get("n")
    if _n_unreach:
        print(f"  CEILING: {_n_unreach} certificate(s) passed all ten gates and cannot "
              f"enrol -- {_unreachable.get('by_cause') or {}}")
    elif _n_unreach is None:
        print("  CEILING: UNMEASURED -- no certificate report was readable, which is "
              "not the same as nothing being blocked")
    if _families.get("decides") == "ENROLMENT_CAP_PER_FAMILY":
        print(f"  ENROLMENT CAPS: {_families.get('caps')} "
              f"({len(_lines)} missed-growth line(s))")
    _sum = _anytime.get("summary") if isinstance(_anytime.get("summary"), dict) else {}
    if _sum:
        print(f"  ANYTIME: {_sum['n_anytime_reject']}/{_sum['n_enrolled']} e-process reject, "
              f"{_sum['n_fixed_reject']} fixed-sample reject, {_sum['n_disagree']} disagree "
              f"(max looks {_anytime.get('max_looks')})")
        for key in _anytime.get("fixed_passes_anytime_does_not") or []:
            c = _anytime["clocks"][key]
            print(f"    DISAGREEMENT {key}: t={c['fixed_sample_t']} >= bar {c['holm_bar']} but "
                  f"e={c['e_value']} on n={c['n']} after {c['looks']} look(s) -- {c['status']}")
    else:
        print(f"  ANYTIME: UNMEASURED -- {_anytime.get('why')}")
    _forward_watermark(enrolled, _anytime)
    return 0


def _forward_watermark(enrolled: object, anytime: dict) -> None:
    """THE FORWARD LANE'S PROGRESS WATERMARK (LAWS.md 7): `forward_observations`.

    Not the number of clocks -- the number of OBSERVATIONS they have accrued. A forward lane with
    the same eighty-four clocks and no new observations is the exact shape that cost this desk
    those clocks in the first place: scheduled, running, reporting, and making no progress.
    """
    try:
        import sys as _sys
        root = str(BASE.parents[1])
        if root not in _sys.path:
            _sys.path.insert(0, root)
        from libs.ops.control_plane import watermarks as wm
        clocks = anytime.get("clocks") if isinstance(anytime, dict) else None
        total = sum(int(c.get("n") or 0) for c in clocks.values()
                    if isinstance(c, dict)) if isinstance(clocks, dict) else None
        if total is None:
            return
        wm.progress("leg:forward_reconcile", "forward_observations", total,
                    enrolled=None if enrolled is None else len(enrolled))
    except Exception as exc:
        print(f"  forward watermark not recorded: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
