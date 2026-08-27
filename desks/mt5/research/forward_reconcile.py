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
"""
from __future__ import annotations

import json
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

TERMINAL = {"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED", "RETIRED",
            "RETIRED_ORPHAN", "RETIRED_GATE_FAIL", "RETIRED_UNRECONSTRUCTIBLE",
            "QUARANTINED_UNCERTIFIED"}


def _read(p: Path) -> dict:
    try:
        v = json.loads(p.read_text("utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _engine_clock_keys() -> set[str]:
    """Every clock key the engine will build from a certificate, named by the ENGINE.

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
    keys: set[str] = {sf.sleeve_key(s, w, dict(sf.WINDOWS.get(w, {}))) for s, w in sf.SLEEVES}
    for row in sf.certified_sleeves():
        sym, win, params = row[0], row[1], row[2]
        family = row[3] if len(row) > 3 else "session_range_breakout"
        keys.add(sf.sleeve_key(sym, win, params, family))
    return keys


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

    # REPORT UNKNOWN AS UNKNOWN. `"enrolled": 0` is what a reader saw for a full day while the
    # real cause was an unpack error -- indistinguishable from an engine that legitimately enrols
    # nothing, which is why nobody chased it. Null carries the distinction the count cannot.
    OUT.write_text(json.dumps(
        {"checked_at": now, "enrolled": None if enrolled is None else len(enrolled),
         "enrolment_readable": not unknown_enrolment,
         "certified_clocks": None if cert_clock_keys is None else len(cert_clock_keys),
         "certified_pairs": len(certs),
         "identity_unfrozen": (None if _frozen is None
                               else sum(a["action"] == "IDENTITY_UNFROZEN" for a in actions)),
         "actions": actions}, indent=1), "utf-8")
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    print(f"forward reconcile: {len(actions)} action(s) {counts or '{}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
