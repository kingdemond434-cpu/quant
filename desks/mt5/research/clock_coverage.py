"""CLOCK COVERAGE -- invariant I1: a certified survivor without a forward clock is impossible.

THE FAULT (measured on the trading box 2026-11-24, `reports/shadow/shadow_health.json`):
13,452 certified survivors against 627 forward clocks. Counted on the tree's own artifacts
(`reports/tier_s/ONLINE_FDR_ROWS.json` `certified`, 13,452 rows, against
`reports/shadow/shadow_state.json`, 1,018 clock rows of which 616 are not terminal):

    exotic FX                          7,325 certificates (banned; a named exclusion here)
    non-exotic                         6,127 certificates, at least 5,712 of them clockless
        formula                        4,859 (4,818 clockless)   clock_transition  640 (626)
        overnight_gap_decay              140 (80)                entry_conditioned  69 (69)
        mass_screen_clock                 69 (69)                session_range_br.  34 (16)

WHY, in three causes, and which one each piece below removes:

  1. CERTIFICATION AND ENROLMENT WERE TWO ACTS IN TWO PROCESSES. The gauntlet
     (`scripts/external_gauntlet.py`, sealed) writes UNIVERSAL_SURVIVORS.json; a clock appears
     only when `shadow_forward`'s next pass reaches `checkpoint_enrolments`. Anything that stops
     that pass first -- a tree that does not carry the enrolment (the box ran a release from
     before 2026-11-13, when the research-integrity door still WITHHELD clocks: 1,308 of 2,324
     certificates `held` on 2026-11-06, per FORWARD_ENROLMENT.json), a pass killed in its
     15-minute slot (2,849 s measured), or a raise inside `certified_sleeves` -- leaves a
     certificate with no clock and nothing tying the two together.
     -> `certify_with_clocks`: the canon and the clocks it owes are written in ONE transaction:
        a write-ahead journal under the state lock, clocks first, canon second, journal removed
        last; `recover` rolls a crashed transaction forward from any later reader. The sealed
        pen calls it through `.SEAL_CLEAR.patch`; until that patch is applied, the backfill
        below closes the same gap within the hour and the census reports it RED meanwhile.
  2. NOTHING RE-OPENED A CLOCK FOR AN EXISTING CERTIFICATE except a full engine pass, which
     `forward_enrolment`'s repair runs as a subprocess inside a 300 s budget the 2,849 s pass
     can never fit in.
     -> `backfill`: bounded per pass, with a cursor, opens the engine's own clock record for
        every certified non-exotic spec that has none. It writes records only -- the replay is
        done by `shadow_forward`'s rotation budget, which takes never-evaluated clocks early and
        stale clocks first of all.
  3. THE CENSUS COUNTED BANNED EXOTICS AS MISSING, so the deficit could never reach zero and
     a real gap was indistinguishable from the ban.
     -> `census`: certified non-exotic specs minus clocked specs, which must be 0; otherwise
        RED with the missing list, by family and reason. Exotics and banned families are named
        exclusions with their counts. Written to reports/shadow/CLOCK_COVERAGE.json by the
        hourly `forward_enrolment` leg.

WHAT THIS NEVER DOES. It never voids, restamps or cost-edits a certificate, never touches a
gate, DSR/FDR or a trial count, and never deletes evidence: a dead clock (its spec no longer
certified) is RETIRED_ORPHAN by `research/forward_reconcile.py` with its reason and evidence
kept; this organ names it. A forward clock deploys no capital, so opening one moves no risk.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

UNMEASURED = "UNMEASURED"
COVERAGE_NAME = "CLOCK_COVERAGE.json"
CURSOR_NAME = "clock_backfill_cursor.json"
JOURNAL_NAME = "certify_with_clocks.journal.json"
#: Clock records the backfill may open per pass. Opening a record is a dict insert and one state
#: write, so the bound is about the size of one write, not about compute: the box's ~6,100
#: non-exotic certificates clear in three hourly passes, the rotation replays them after.
BACKFILL_PER_PASS = int(os.environ.get("QUANT_CLOCK_BACKFILL_PER_PASS", "2500") or 2500)
#: Entries of the missing list carried in the artifact (the counts are always complete).
MISSING_LIST_CAP = 20_000
EXOTIC = "exotic"
BANNED = "banned_family"


def _sf():
    import shadow_forward
    return shadow_forward


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha(text: str | None) -> str | None:
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _state_path(state_path: Path | None) -> Path:
    return Path(state_path) if state_path else _sf().SHADOW_DIR / "shadow_state.json"


def _journal_path(state_path: Path) -> Path:
    return state_path.with_name(JOURNAL_NAME)


def _banned(family: object) -> bool:
    try:
        from family_policy import family_banned
        return bool(family_banned(family))
    except Exception:
        return False                        # an unreadable ban list excludes nothing


def exclusion(symbol: object, family: object) -> str | None:
    """'exotic' / 'banned_family' / None -- the two named exclusions, in that order.

    Exotic is `universe_policy.is_exotic_symbol`, the desk's one definition: any FX pair with a
    fiat leg outside USD, EUR, JPY, GBP, CHF, AUD, NZD and CAD, or a registry class naming one."""
    if symbol and _sf()._is_exotic(str(symbol)):
        return EXOTIC
    if family and _banned(family):
        return BANNED
    return None


def _row_parts(row: tuple) -> tuple[str, str]:
    return str(row[0]), str(row[3] if len(row) > 3 else "session_range_breakout")


def owed(rows: Iterable[tuple]) -> tuple[dict[str, tuple], dict[str, int]]:
    """({clock key: enrolment row} the desk owes a clock, {exclusion: n}) from engine rows."""
    sf = _sf()
    keyed: dict[str, tuple] = {}
    excluded: dict[str, int] = {}
    for row in rows:
        key = sf._row_key(row)
        if not key:
            continue
        why = exclusion(*_row_parts(row))
        if why:
            excluded[why] = excluded.get(why, 0) + 1
            continue
        keyed.setdefault(key, row)
    return keyed, excluded


def _open_unlocked(state_path: Path, add: dict[str, dict]) -> list[str]:
    """Merge `add` into the ledger on disk (never overwriting an existing row). Caller holds
    the state lock. Returns the keys actually opened. Raises if the ledger is unreadable."""
    sf = _sf()
    disk = sf._read_state(state_path)
    if disk is None:
        raise OSError(f"{state_path.name} exists and is unreadable; no clock opened over it")
    opened = [k for k in add if k not in disk]
    if not opened:
        return []
    for k in opened:
        disk[k] = add[k]
    disk["updated_at"] = _now()
    sf._atomic_write_text(state_path, json.dumps(disk, indent=2, default=str))
    return opened


def _records(rows: dict[str, tuple], stamp: str) -> dict[str, dict]:
    sf = _sf()
    return {k: sf.new_clock_record(stamp, sf._row_hold(r)) for k, r in rows.items()}


# ------------------------------------------------------------------ the certification transaction
def recover(state_path: Path | None = None) -> dict[str, Any] | None:
    """Roll a crashed certification transaction forward. Cheap when there is nothing to do.

    The journal is written atomically BEFORE either target, so it either names a whole
    transaction or does not exist. Clocks are re-applied (idempotent: an existing row is never
    overwritten). The canon is written only when the file still holds the bytes it held when
    the transaction began -- if another pen published since, that newer canon stands and the
    journal's copy is NOT rolled over it (it is kept beside the journal, never deleted)."""
    sp = _state_path(state_path)
    jp = _journal_path(sp)
    if not jp.exists():
        return None
    sf = _sf()
    try:
        j = json.loads(jp.read_text(encoding="utf-8"))
        if not isinstance(j, dict):
            raise ValueError("journal is not an object")
    except (OSError, ValueError) as exc:
        keep = jp.with_name(f"{jp.name}.unreadable-{datetime.now(UTC):%Y%m%dT%H%M%S}")
        with contextlib.suppress(OSError):
            os.replace(jp, keep)
        return {"status": "JOURNAL_UNREADABLE", "why": f"{type(exc).__name__}: {exc}",
                "kept_as": keep.name}
    out: dict[str, Any] = {"status": "RECOVERED", "at": _now(), "began_at": j.get("at")}
    with sf.state_lock(sp):
        try:
            out["clocks_opened"] = _open_unlocked(sp, dict(j.get("clocks") or {}))
        except OSError as exc:
            out["status"] = "PENDING"
            out["why"] = f"clocks not applied ({exc}); journal kept for the next reader"
            return out
        canon = Path(str(j.get("canon_path") or ""))
        text = j.get("canon_text")
        if canon.name and isinstance(text, str):
            cur = _sha(_read_text(canon))
            if cur == j.get("canon_sha_after"):
                out["canon"] = "ALREADY_WRITTEN"
            elif cur == j.get("canon_sha_before"):
                sf._atomic_write_text(canon, text)
                out["canon"] = "WRITTEN"
            else:
                keep = canon.with_name(f"{canon.name}.journal-superseded-"
                                       f"{datetime.now(UTC):%Y%m%dT%H%M%S}")
                sf._atomic_write_text(keep, text)
                out["canon"] = "SUPERSEDED"
                out["why"] = ("another pen published the canon after this transaction began; "
                              f"the newer canon stands, the journal's copy is kept as {keep.name}")
    with contextlib.suppress(OSError):
        jp.unlink()
    sf.slog(f"CLOCK-COVERAGE: recovered a certification transaction begun {j.get('at')}: "
            f"{len(out.get('clocks_opened') or [])} clock(s), canon {out.get('canon')}")
    return out


def _crash_point(name: str, at: str | None) -> None:
    if at == name:
        raise SystemExit(f"simulated crash after {name}")


def certify_with_clocks(surv_path: Path, doc: dict, *, fresh: Iterable[str] | None = None,
                        state_path: Path | None = None, text: str | None = None,
                        _crash_after: str | None = None) -> dict[str, Any]:
    """Write a canon document AND the forward clocks its new certificates owe, atomically.

    `fresh`: the certificate names minted by this publish (the gauntlet's `_remint_fresh`);
    None means every certificate absent from the canon on disk. Their clocks are derived by the
    ENGINE'S OWN DOOR (`shadow_admission.runs_from_canon` -> `shadow_forward.certified_sleeves`),
    so a clock opened here is exactly the clock the next pass would open: same key, same
    integrity hold, same record. Exotic and banned-family certificates get no clock (named
    exclusions). The canon is written whatever the derivation says: a certificate is never
    withheld because a clock could not be derived -- that is the census's RED, not a refusal.

    ORDER: derive (no lock) -> lock -> journal -> clocks -> canon -> unlink journal. A crash at
    any point leaves either nothing changed, or a journal that `recover` completes."""
    sf = _sf()
    surv_path = Path(surv_path)
    sp = _state_path(state_path)
    fresh = None if fresh is None else [str(n) for n in fresh]
    recover(sp)
    text = text if text is not None else json.dumps(doc, indent=2, default=str)
    before = _read_text(surv_path)
    result: dict[str, Any] = {"at": _now(), "canon": str(surv_path.name)}
    rows: dict[str, tuple] = {}
    try:
        from shadow_admission import _evicted_keys, runs_from_canon
        engine_rows = sf.certified_sleeves(
            runs=runs_from_canon(doc, evicted=_evicted_keys(sf.BASE)))
        disp = dict(sf.CERT_DISPOSITION)
        if fresh is None:
            try:
                prior = set(json.loads(before or "{}").get("survivors") or {})
            except ValueError:
                prior = set()
            fresh = [n for n in (doc.get("survivors") or {}) if n not in prior]
        fresh_keys = {disp[n]["key"] for n in fresh if "key" in disp.get(n, {})}
        keyed, excluded = owed(engine_rows)
        rows = {k: r for k, r in keyed.items() if k in fresh_keys}
        result.update({"fresh": len(fresh), "owed": len(rows), "excluded": excluded,
                       "unclocked_fresh": sorted(n for n in fresh
                                                 if "key" not in disp.get(n, {}))[:200]})
    except Exception as exc:              # the certificate is written regardless
        result["derive"] = f"UNMEASURED: {type(exc).__name__}: {exc}"
    stamp = _now()
    add = _records(rows, stamp)
    jp = _journal_path(sp)
    with sf.state_lock(sp):
        journal = {"at": stamp, "canon_path": str(surv_path), "canon_text": text,
                   "canon_sha_before": _sha(before), "canon_sha_after": _sha(text),
                   "state_path": str(sp), "clocks": add}
        sf._atomic_write_text(jp, json.dumps(journal, default=str))
        _crash_point("journal", _crash_after)
        try:
            result["clocks_opened"] = _open_unlocked(sp, add)
        except OSError as exc:
            result["clocks_opened"] = []
            result["clocks_pending"] = f"{exc}; journal kept, `recover` applies them"
        _crash_point("clocks", _crash_after)
        sf._atomic_write_text(surv_path, text)
        _crash_point("canon", _crash_after)
        if "clocks_pending" not in result:
            with contextlib.suppress(OSError):
                jp.unlink()
    sf.slog(f"CLOCK-COVERAGE: canon written with {len(result['clocks_opened'])} new forward "
            f"clock(s) in the same transaction")
    return result


# ---------------------------------------------------------------------------------- the backfill
def _cursor_path(state_path: Path) -> Path:
    return state_path.with_name(CURSOR_NAME)


def _all_clock_keys(shadow_dir: Path) -> set[str]:
    try:
        from forward_enrolment import clock_rows
    except ImportError:
        from research.forward_enrolment import clock_rows  # type: ignore[no-redef]
    return set(clock_rows(shadow_dir))


def backfill(max_new: int | None = None, *, rows: list[tuple] | None = None,
             state_path: Path | None = None) -> dict[str, Any]:
    """Open the clock record for every certified non-exotic spec that has none, `max_new` per
    pass, resuming after the cursor (sorted clock keys, wrapping), so successive passes cover
    every spec in a fixed order. Records only; `shadow_forward`'s rotation replays them."""
    sf = _sf()
    sp = _state_path(state_path)
    limit = BACKFILL_PER_PASS if max_new is None else int(max_new)
    rec = recover(sp)
    if rows is None:
        rows = sf.certified_sleeves()
    keyed, excluded = owed(rows)
    have = _all_clock_keys(sp.parent)
    missing = sorted(k for k in keyed if k not in have)
    cp = _cursor_path(sp)
    try:
        cursor = str(json.loads(cp.read_text(encoding="utf-8")).get("cursor") or "")
    except (OSError, ValueError, AttributeError):
        cursor = ""
    ordered = [k for k in missing if k > cursor] + [k for k in missing if k <= cursor]
    take = ordered[:max(0, limit)]
    opened: list[str] = []
    why = ""
    if take:
        with sf.state_lock(sp):
            try:
                opened = _open_unlocked(sp, _records({k: keyed[k] for k in take}, _now()))
            except OSError as exc:
                why = str(exc)
    remaining = len(missing) - len(opened)
    new_cursor = take[-1] if (take and remaining > 0) else ""
    out = {"at": _now(), "cursor_in": cursor, "cursor": new_cursor, "per_pass": limit,
           "owed": len(keyed), "missing_before": len(missing), "opened": len(opened),
           "remaining": remaining,
           "passes_to_clear": (-(-remaining // limit) if limit > 0 else None),
           "excluded": excluded, **({"why": why} if why else {}),
           **({"recovered": rec} if rec else {})}
    with contextlib.suppress(OSError):
        sf._atomic_write_text(cp, json.dumps(out, indent=1, default=str))
    if opened:
        sf.slog(f"CLOCK-COVERAGE backfill: opened {len(opened)} clock(s), {remaining} still "
                f"owed; the rotation replays them")
    return out


# ------------------------------------------------------------------------- the invariant (census)
def derive(base: Path | None = None) -> dict[str, Any]:
    """The canon, its certified rows and the ENGINE'S derivation of their clocks, read once.

    {"status": UNMEASURED, "why"} when no canon carries the exact ten-gate policy."""
    sf = _sf()
    base = Path(base or sf.BASE)
    try:
        import shadow_admission as sa
        from gate_policy import all_ten_pass, is_exact_policy
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    universal, src = sa._canon(base)
    if not is_exact_policy(universal.get("gate_policy")):
        return {"status": UNMEASURED,
                "why": f"no canon under the exact ten-gate policy ({src}); nothing can be "
                       "counted, and absence is not a clean verdict"}
    survivors = universal.get("survivors") or {}
    certified = {str(n): r for n, r in survivors.items()
                 if isinstance(r, dict) and all_ten_pass(r.get("gates"))}
    sa.DROPPED_CERTIFICATES.clear()
    runs = sa.runs_from_canon(universal, evicted=sa._evicted_keys(base))
    dropped = {str(d.get("certificate") or ""): d
               for d in list(sa.DROPPED_CERTIFICATES) if isinstance(d, dict)}
    rows = sf.certified_sleeves(runs=runs)
    return {"status": "MEASURED", "canon": src, "certified": certified, "runs": runs,
            "dropped": dropped, "rows": rows, "disposition": dict(sf.CERT_DISPOSITION)}


def census(*, base: Path | None = None, state_path: Path | None = None,
           now: datetime | None = None, derived: dict[str, Any] | None = None) -> dict[str, Any]:
    """Certified non-exotic specs minus clocked specs. 0 is GREEN; anything else is RED with
    the missing list. UNMEASURED when the canon cannot be read under the exact policy."""
    sf = _sf()
    sp = _state_path(state_path)
    t = now or datetime.now(UTC)
    rec = recover(sp)
    d0 = derived if derived is not None else derive(base)
    if d0.get("status") != "MEASURED":
        return {"at": t.isoformat(timespec="seconds"), "status": UNMEASURED,
                "why": d0.get("why")}
    src, certified, dropped = d0["canon"], d0["certified"], d0["dropped"]
    run_of = {str(r.get("certificate") or ""): r for r in d0["runs"]}
    disp = d0["disposition"]
    try:
        from forward_enrolment import _run_key, clock_rows
    except ImportError:
        from research.forward_enrolment import _run_key, clock_rows  # type: ignore[no-redef]
    clocks = clock_rows(sp.parent)
    excluded: dict[str, int] = {}
    missing: list[dict[str, Any]] = []
    owed_keys: set[str] = set()
    by_family: dict[str, dict[str, int]] = {}
    for name, row in sorted(certified.items()):
        spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
        sym = str(spec.get("symbol") or row.get("sym") or "")
        fam = str(spec.get("family") or row.get("family") or "")
        fb = by_family.setdefault(fam or UNMEASURED, {"certified": 0, "excluded": 0,
                                                      "clocked": 0, "missing": 0})
        fb["certified"] += 1
        why = exclusion(sym, fam)
        if why:
            excluded[why] = excluded.get(why, 0) + 1
            fb["excluded"] += 1
            continue
        if name.startswith(("scalp.", "qquant.")) and name in run_of:
            key: str | None = _run_key(run_of[name])
            reason = "lane resolver gave no clock address"
        else:
            d = disp.get(name) or {}
            key = d.get("key")
            reason = d.get("why") or (
                f"DROPPED_AT_ADMISSION: {dropped[name].get('why') or dropped[name]}"
                if name in dropped else "not returned by the admission door")
        if key:
            owed_keys.add(key)
        if key and key in clocks:
            fb["clocked"] += 1
            continue
        fb["missing"] += 1
        missing.append({"certificate": name, "symbol": sym, "family": fam,
                        "key": key or UNMEASURED,
                        "why": "NO CLOCK" if key else reason})
    # DEAD AND STALE, on the engine's own lane.
    state = sf._read_state(sp) or {}
    dead, stale = [], []
    for key, st in state.items():
        if not isinstance(st, dict) or not ("status" in st or "n" in st):
            continue
        if sf._is_terminal(st.get("status")):
            continue
        parts = key.split("#", 1)[0].split("@", 1)[0].split(".")
        fam = parts[1] if len(parts) > 2 else "session_range_breakout"
        if exclusion(parts[0], fam):
            continue
        if key not in owed_keys:
            dead.append(key)
        elif sf._clock_is_stale(st, t):
            stale.append({"key": key, "last_attempt_at": st.get("last_attempt_at"),
                          "enrolled_at": st.get("enrolled_at")})
    n_owed = len(certified) - sum(excluded.values())
    status = "GREEN" if not missing else "RED"
    return {
        "at": t.isoformat(timespec="seconds"), "status": status,
        "invariant": "certified non-exotic specs minus clocked specs == 0",
        "canon": src, "n_certified": len(certified), "n_owed": n_owed,
        "n_clocked": n_owed - len(missing), "n_missing": len(missing),
        "excluded": {k: {"n": v, "why": (sf.EXOTIC_EXCLUSION_WHY if k == EXOTIC else
                                         "family banned by the principal "
                                         "(data/banned_families.json); no clock is owed")}
                     for k, v in sorted(excluded.items())},
        "missing_by_reason": _count(missing, "why"),
        "by_family": dict(sorted(by_family.items(), key=lambda kv: -kv[1]["certified"])),
        "missing": missing[:MISSING_LIST_CAP],
        "dead_clocks": {"n": len(dead), "keys": sorted(dead)[:2000],
                        "repair": ("RETIRED_ORPHAN by research/forward_reconcile.py (hourly) with "
                                   "its reason; evidence is never deleted")},
        "stale_clocks": {"n": len(stale), "stale_after_h": sf.CLOCK_STALE_H,
                         "clocks": stale[:2000],
                         "repair": ("first in the next shadow_forward rotation "
                                    "(_stalest_symbols_first tier 0)")},
        **({"recovered": rec} if rec else {}),
        "rule": ("every certified survivor is on a forward clock; certification writes the clock "
                 "in the same transaction (certify_with_clocks), the hourly backfill re-opens any "
                 "that are missing, and no certificate, gate, DSR/FDR or trial count is touched"),
    }


def _count(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        head = str(r.get(field) or "").split(":", 1)[0]
        out[head] = out.get(head, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def run(write: bool = True, *, do_backfill: bool = True,
        state_path: Path | None = None) -> dict[str, Any]:
    """One hourly pass: backfill (bounded), then the census; writes CLOCK_COVERAGE.json."""
    sp = _state_path(state_path)
    bf: dict[str, Any] | None = None
    try:
        derived = derive()
    except Exception as exc:
        derived = {"status": UNMEASURED, "why": f"derive failed: {type(exc).__name__}: {exc}"}
    if do_backfill and derived.get("status") == "MEASURED":
        try:
            bf = backfill(rows=list(derived["rows"]), state_path=sp)
        except Exception as exc:
            bf = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    try:
        doc = census(state_path=sp, derived=derived)
    except Exception as exc:
        doc = {"status": UNMEASURED, "why": f"census failed: {type(exc).__name__}: {exc}"}
    doc["backfill"] = bf
    if write:
        try:
            _sf()._atomic_write_text(sp.parent / COVERAGE_NAME,
                                     json.dumps(doc, indent=1, default=str))
        except OSError as exc:
            doc["write"] = f"UNMEASURED: {type(exc).__name__}: {exc}"
    return doc


def summary(doc: dict[str, Any]) -> dict[str, Any]:
    """The few fields a health board carries."""
    return {k: doc.get(k) for k in ("at", "status", "n_certified", "n_owed", "n_clocked",
                                    "n_missing", "missing_by_reason")} | {
        "excluded": {k: (v or {}).get("n") for k, v in (doc.get("excluded") or {}).items()},
        "dead_clocks": (doc.get("dead_clocks") or {}).get("n"),
        "stale_clocks": (doc.get("stale_clocks") or {}).get("n"),
        "backfill_remaining": (doc.get("backfill") or {}).get("remaining")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Invariant I1: every certified survivor on a clock.")
    ap.add_argument("--no-backfill", action="store_true", help="census only")
    ap.add_argument("--dry-run", action="store_true", help="write no artifact")
    args = ap.parse_args(argv)
    doc = run(write=not args.dry_run, do_backfill=not args.no_backfill)
    print(json.dumps(summary(doc), indent=1, default=str))
    return 1 if doc.get("status") == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
