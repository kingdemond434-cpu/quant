#!/usr/bin/env python3
"""THE EVIDENCE WATCHTOWER -- a claim is not evidence until something independent agrees with it.

THE DEFECT THIS ENDS, and it is the oldest one on this desk. A source says a thing. The thing is
written into an artifact. The artifact is read by an organ. The organ writes a number. By the
fourth hop nobody can say whether the number was ever checked against the world, and the only
honest answer -- "we do not know" -- is the one answer the pipeline had no way to express. So
every claim resolved to TRUE or to nothing, and "nothing" silently became "not a problem".

THE CHAIN, and it runs in this order for every claim:

    claim -> DIRECT OBSERVABLE CHECK -> SECOND SOURCE -> STATE RECONCILIATION -> PROVENANCE
          -> UNRESOLVED if unknowable -> candidate only after agreement

UNRESOLVED IS A FIRST-CLASS VERDICT, not a failure and not a pass. A claim whose observable this
box cannot see is UNRESOLVED and stays in the record as UNRESOLVED for ever, with the checker that
could not resolve it named. The alternative -- collapsing "we could not check" into either
"verified" or "rejected" -- is exactly the WS-005 class the desk's own laws forbid: absence read
as a clean verdict.

THE WATCHTOWER HALF. Verification is a one-shot question; the watchtower is the standing one. It
re-scans objects the desk has ALREADY SEEN -- sources, claims, mechanisms, datasets, products,
leaderboard systems and live assumptions -- and records a transition when the EVIDENCE CHANGED.

    A MISSING FIELD IS NEVER A CHANGE.

That one line is the whole difference between a watchtower and an alarm that cries every time a
server is slow. A field that was MEASURED and is now UNRESOLVED is a gap in observation, not a
disappearance; a field that was UNRESOLVED and is now MEASURED is a first reading, not a change.
Only MEASURED -> DIFFERENT MEASURED is a transition. `false_transition_rate()` proves it on a
fixture where half the fields simply stop being readable, and the answer must be 0.

Transitions land in `data/watchtower.jsonl` (append-only, one JSON row per transition), become
registry discoveries with `source_type="watchtower"` so the compiler can turn a real change into
cells, and become a research-memory row so a later session reading the registry finds the same
history the file carries.

    python desks/mt5/research/evidence_watchtower.py --dry-run
    python desks/mt5/research/evidence_watchtower.py --budget-s 120
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

UNRESOLVED = "UNRESOLVED"
VERIFIED = "VERIFIED"
CONTRADICTED = "CONTRADICTED"
UNMEASURED = "UNMEASURED"
PASS, FAIL = "PASS", "FAIL"

WATCHTOWER = DESK / "data" / "watchtower.jsonl"
REPORT = DESK / "reports" / "EVIDENCE_WATCHTOWER.json"

#: The kinds of object the watchtower re-scans. Open: a kind nobody has registered is a kind
#: nobody can notice is missing, so new kinds are added here rather than special-cased downstream.
OBJECT_KINDS: tuple[str, ...] = ("source", "claim", "mechanism", "dataset", "product",
                                 "leaderboard_system", "live_assumption")

#: Default numeric agreement tolerance: two sources within 1% of each other agree. A tolerance is
#: a claim about measurement error and belongs on the claim, so this is only the fallback.
TOLERANCE = 0.01
#: A dataset older than this is STALE rather than missing -- a different verdict, and a real one.
DEFAULT_MAX_AGE_S = 86_400.0


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _agree(a: Any, b: Any, tol: float = TOLERANCE) -> bool:
    """Do two readings of the same thing agree? Numbers within a relative tolerance, everything
    else by exact equality after a string normalisation -- never by 'close enough' on prose."""
    x, y = _num(a), _num(b)
    if x is not None and y is not None:
        scale = max(abs(x), abs(y), 1e-12)
        return abs(x - y) / scale <= tol
    return str(a).strip().lower() == str(b).strip().lower()


# --------------------------------------------------------------------------- verdict objects
@dataclass(frozen=True)
class Check:
    """One checker's answer. PASS, FAIL or UNRESOLVED -- and UNRESOLVED carries the reason."""

    name: str
    verdict: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return {"check": self.name, "verdict": self.verdict, "detail": self.detail,
                "evidence": dict(self.evidence)}


@dataclass(frozen=True)
class Verdict:
    """The claim's standing, and every check that produced it.

    `checks` is kept whole rather than summarised: a VERIFIED claim whose second source was
    UNRESOLVED is a different object from one where two sources agreed, and a caller that can only
    see the headline cannot tell them apart.
    """

    verdict: str
    checks: tuple[Check, ...]
    claim_id: str = ""
    at: str = field(default_factory=_now)

    @property
    def verified(self) -> bool:
        return self.verdict == VERIFIED

    def by_name(self) -> dict[str, str]:
        return {c.name: c.verdict for c in self.checks}

    def as_row(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "verdict": self.verdict, "at": self.at,
                "checks": [c.as_row() for c in self.checks]}


# --------------------------------------------------------------------------- the checkers
def check_artifact(claim: Mapping[str, Any], ctx: Mapping[str, Any]) -> Check:
    """Does the artifact this claim rests on EXIST, and is it FRESH?

    Three outcomes and they are all real: the file is there and recent (PASS), it is there and
    older than the claim's own freshness requirement (FAIL -- a stale artifact is a claim about
    yesterday presented as one about today), or the claim names no artifact at all (UNRESOLVED,
    because a claim with no observable behind it has not been refuted, it has been un-asked).
    """
    raw = claim.get("artifact") or claim.get("path")
    if not raw:
        return Check("artifact_fresh", UNRESOLVED, "the claim names no artifact to check")
    p = Path(str(raw))
    if not p.is_absolute():
        p = Path(str(ctx.get("root") or ROOT)) / p
    if not p.exists():
        return Check("artifact_fresh", FAIL, f"named artifact does not exist: {p}",
                     {"path": str(p)})
    age = time.time() - p.stat().st_mtime
    max_age = float(claim.get("max_age_s") or ctx.get("max_age_s") or DEFAULT_MAX_AGE_S)
    if age > max_age:
        return Check("artifact_fresh", FAIL,
                     f"artifact is {age / 3600:.1f}h old against a {max_age / 3600:.1f}h "
                     "requirement: this is a claim about yesterday",
                     {"path": str(p), "age_s": age, "max_age_s": max_age})
    return Check("artifact_fresh", PASS, f"artifact exists and is {age / 3600:.1f}h old",
                 {"path": str(p), "age_s": age})


def check_series(claim: Mapping[str, Any], ctx: Mapping[str, Any]) -> Check:
    """Does the series actually carry the claimed value AT THE CLAIMED TIME?

    The time half is the point. A series that contains the value somewhere is not evidence for a
    claim about Tuesday, and the commonest way a bad number survives review is that somebody
    checked the value and not the stamp.
    """
    series = claim.get("series") or ctx.get("series")
    want = claim.get("value")
    when = str(claim.get("at") or claim.get("knowable_at") or "")
    if not isinstance(series, Sequence) or isinstance(series, (str, bytes)) or not series:
        return Check("series_carries_value", UNRESOLVED, "no series supplied for this claim")
    if want is None:
        return Check("series_carries_value", UNRESOLVED, "the claim states no value to look for")
    tol = float(claim.get("tolerance") or TOLERANCE)
    stamped = [p for p in series if isinstance(p, Mapping)]
    if not stamped:
        return Check("series_carries_value", UNRESOLVED,
                     "the series carries no stamped points; a value with no time cannot support "
                     "a claim about a time")
    if when:
        hit = [p for p in stamped if str(p.get("at") or p.get("time") or "") == when]
        if not hit:
            return Check("series_carries_value", UNRESOLVED,
                         f"the series has no point stamped {when!r}", {"claimed_at": when})
        ok = any(_agree(p.get("value"), want, tol) for p in hit)
        return Check("series_carries_value", PASS if ok else FAIL,
                     f"series at {when} is {[p.get('value') for p in hit]} against a claimed "
                     f"{want}", {"claimed_at": when, "claimed_value": want,
                                 "observed": [p.get("value") for p in hit]})
    ok = any(_agree(p.get("value"), want, tol) for p in stamped)
    return Check("series_carries_value", PASS if ok else FAIL,
                 f"claimed {want} {'found' if ok else 'absent'} in an unstamped comparison",
                 {"claimed_value": want, "n_points": len(stamped)})


def check_second_source(claim: Mapping[str, Any], ctx: Mapping[str, Any]) -> Check:
    """Does an INDEPENDENT second source say the same thing?

    Independence is counted by source id, not by document: the same wire republished under two
    names is one source, and a desk that counts it twice has invented a confirmation. Fewer than
    two independent sources is UNRESOLVED -- never a pass, and never a rejection either.
    """
    sources = claim.get("sources") or ctx.get("sources") or []
    rows = [s for s in sources if isinstance(s, Mapping)]
    by_id: dict[str, Any] = {}
    for s in rows:
        sid = str(s.get("source_id") or s.get("source") or s.get("url") or "")
        if sid and sid not in by_id:
            by_id[sid] = s.get("value")
    if len(by_id) < 2:
        return Check("second_source", UNRESOLVED,
                     f"{len(by_id)} independent source(s): a single source is a claim, not a "
                     "corroboration", {"n_independent": len(by_id)})
    tol = float(claim.get("tolerance") or TOLERANCE)
    values = list(by_id.values())
    anchor = claim.get("value") if claim.get("value") is not None else values[0]
    agreeing = [v for v in values if _agree(v, anchor, tol)]
    if len(agreeing) >= 2:
        return Check("second_source", PASS,
                     f"{len(agreeing)} of {len(values)} independent sources agree on {anchor!r}",
                     {"n_independent": len(by_id), "n_agreeing": len(agreeing),
                      "values": values})
    return Check("second_source", FAIL,
                 f"independent sources disagree: {values} against a claimed {anchor!r}",
                 {"n_independent": len(by_id), "values": values})


def check_state(claim: Mapping[str, Any], ctx: Mapping[str, Any]) -> Check:
    """Does the claim reconcile with the state the DESK itself holds?

    A source saying a sleeve is live and `sleeves.json` saying it is standby is a contradiction
    worth catching immediately, because everything downstream will otherwise average the two.
    """
    want = claim.get("state")
    have = ctx.get("desk_state")
    if want is None or have is None:
        return Check("state_reconciliation", UNRESOLVED,
                     "no desk-side state to reconcile against" if want is not None
                     else "the claim asserts no state")
    if isinstance(have, Mapping):
        key = str(claim.get("state_key") or "")
        if key not in have:
            return Check("state_reconciliation", UNRESOLVED,
                         f"the desk holds no {key!r} to reconcile against")
        have = have[key]
    ok = _agree(have, want, float(claim.get("tolerance") or TOLERANCE))
    return Check("state_reconciliation", PASS if ok else FAIL,
                 f"claim says {want!r}; the desk holds {have!r}",
                 {"claimed": want, "desk": have})


def check_provenance(claim: Mapping[str, Any], ctx: Mapping[str, Any]) -> Check:
    """Was this KNOWABLE when the claim says it was, and does it name where it came from?

    `knowable_at` is the publisher's own stamp and `observed_at` is when the desk read it. A claim
    whose knowable time is AFTER the moment it was acted on is look-ahead, and it is a FAIL rather
    than a warning, because a look-ahead claim that enters the record poisons every backtest that
    touches it.
    """
    src = str(claim.get("source_id") or claim.get("source") or "")
    knowable = str(claim.get("knowable_at") or "")
    if not src and not knowable:
        return Check("provenance", UNRESOLVED, "no source and no knowable_at on this claim")
    if not knowable or knowable == UNMEASURED:
        return Check("provenance", UNRESOLVED,
                     f"source {src!r} states no publish time; PIT status is UNMEASURED",
                     {"source_id": src})
    used_at = str(claim.get("used_at") or ctx.get("used_at") or "")
    if used_at:
        try:
            k = datetime.fromisoformat(knowable)
            u = datetime.fromisoformat(used_at)
            k = k if k.tzinfo else k.replace(tzinfo=UTC)
            u = u if u.tzinfo else u.replace(tzinfo=UTC)
            if k > u:
                return Check("provenance", FAIL,
                             f"knowable_at {knowable} is AFTER used_at {used_at}: look-ahead",
                             {"knowable_at": knowable, "used_at": used_at})
        except ValueError:
            return Check("provenance", UNRESOLVED, "unparseable timestamps on this claim")
    return Check("provenance", PASS, f"source {src!r}, knowable at {knowable}",
                 {"source_id": src, "knowable_at": knowable})


def check_url(claim: Mapping[str, Any], ctx: Mapping[str, Any]) -> Check:
    """OPTIONAL and OFF BY DEFAULT: does the claim's url still resolve?

    Uses the desk's ONE http client (`deep_forest_miner._http`) rather than opening a second one,
    and only when the caller passes `fetch=True`. A url that cannot be fetched is UNRESOLVED,
    never CONTRADICTED -- a network failure is a fact about this box, not about the claim.

    LAWS 5e (2026-09-23): `machine_use_allowed is False` used to leave this check permanently
    UNRESOLVED "by design", which meant the desk could never verify a claim from a source with a
    terms note. That was a discovery brake; it is deleted. The claim's terms label travels into
    the check's detail instead, and the url is checked like any other.
    """
    url = str(claim.get("url") or "")
    label = str(claim.get("terms_note") or "")
    if claim.get("machine_use_allowed") is False:
        label = (label + "; source declares machine_use_allowed=false: checked anyway, "
                         "redistribution withheld").strip("; ")
    if not url:
        return Check("url_resolves", UNRESOLVED, "the claim names no url")
    if not ctx.get("fetch"):
        return Check("url_resolves", UNRESOLVED,
                     "network checks are off for this pass; nothing was fetched")
    try:
        import deep_forest_miner as dfm
        page = dfm._http(url, timeout=float(ctx.get("timeout_s") or 10.0))
    except Exception as exc:
        return Check("url_resolves", UNRESOLVED, f"fetch failed: {type(exc).__name__}: {exc}",
                     {"url": url, "terms_note": label})
    return Check("url_resolves", PASS if page else UNRESOLVED,
                 f"url returned {len(page or '')} characters",
                 {"url": url, "terms_note": label})


#: The chain, IN ORDER. A caller may pass a subset; the order is what the docstring's chain says.
CHECKERS: dict[str, Callable[[Mapping[str, Any], Mapping[str, Any]], Check]] = {
    "artifact_fresh": check_artifact,
    "series_carries_value": check_series,
    "second_source": check_second_source,
    "state_reconciliation": check_state,
    "provenance": check_provenance,
    "url_resolves": check_url,
}
#: The checks whose PASS is required before a claim may become a CANDIDATE. Agreement is the bar:
#: a direct observable AND an independent second source. Everything else informs, none of it
#: promotes on its own.
REQUIRED_FOR_CANDIDATE: tuple[str, ...] = ("second_source",)
DIRECT_OBSERVABLE: tuple[str, ...] = ("artifact_fresh", "series_carries_value")


def verify(claim: Mapping[str, Any], *, checkers: Iterable[str] | None = None,
           ctx: Mapping[str, Any] | None = None) -> Verdict:
    """Run the chain and aggregate. ANY FAIL CONTRADICTS; agreement VERIFIES; the rest is
    UNRESOLVED.

    The aggregation is deliberately asymmetric. One checker saying the artifact is missing is
    enough to contradict, because a claim resting on a file that is not there is already wrong.
    But no single PASS verifies: a direct observable must hold AND an independent second source
    must agree, which is the "candidate only after agreement" half of the chain.
    """
    context = dict(ctx or {})
    names = list(checkers) if checkers is not None else list(CHECKERS)
    checks: list[Check] = []
    for name in names:
        fn = CHECKERS.get(name)
        if fn is None:
            checks.append(Check(name, UNRESOLVED, f"no checker named {name!r} is registered"))
            continue
        try:
            checks.append(fn(claim, context))
        except Exception as exc:
            checks.append(Check(name, UNRESOLVED,
                                f"checker raised {type(exc).__name__}: {exc}; counted, never "
                                "swallowed"))
    by = {c.name: c.verdict for c in checks}
    if any(v == FAIL for v in by.values()):
        verdict = CONTRADICTED
    elif (any(by.get(n) == PASS for n in DIRECT_OBSERVABLE)
          and all(by.get(n) == PASS for n in REQUIRED_FOR_CANDIDATE)):
        verdict = VERIFIED
    else:
        verdict = UNRESOLVED
    return Verdict(verdict, tuple(checks), str(claim.get("claim_id") or claim.get("id") or ""))


def may_become_candidate(v: Verdict) -> tuple[bool, str]:
    """The one door out of this module: VERIFIED only, and the reason is always given."""
    if v.verdict == VERIFIED:
        return True, "a direct observable holds and an independent second source agrees"
    if v.verdict == CONTRADICTED:
        failed = [c.name for c in v.checks if c.verdict == FAIL]
        return False, f"contradicted by {failed}"
    missing = [c.name for c in v.checks if c.verdict == UNRESOLVED]
    return False, (f"UNRESOLVED on {missing}: unknowable from this box, which is a verdict and "
                   "not a rejection -- the claim stays in the record")


# --------------------------------------------------------------------------- the watchtower
def observe(obj: Mapping[str, Any]) -> dict[str, Any]:
    """The current fingerprint of one watched object: every tracked field MEASURED or UNRESOLVED.

    Two sources of fields, and neither may invent one. A `path` yields file facts (existence,
    size, modification time and, for a JSON document, its top-level row count). A `fields` mapping
    is what the caller already measured. A field the caller names in `track` but supplies no value
    for is UNRESOLVED -- present in the fingerprint, with no value -- because a field that is
    absent from the fingerprint entirely cannot later be seen to have gone missing.
    """
    out: dict[str, Any] = {}
    raw = obj.get("path")
    if raw:
        p = Path(str(raw))
        if p.exists():
            st = p.stat()
            out["exists"] = True
            out["size"] = int(st.st_size)
            out["mtime"] = round(float(st.st_mtime), 3)
            if p.suffix.lower() == ".json":
                try:
                    doc = json.loads(p.read_text(encoding="utf-8-sig"))
                    out["n_rows"] = len(doc) if isinstance(doc, (list, dict)) else None
                except (OSError, ValueError):
                    out["n_rows"] = None
        else:
            out["exists"] = False
    fields = obj.get("fields")
    if isinstance(fields, Mapping):
        for k, v in fields.items():
            out[str(k)] = v
    for k in (obj.get("track") or ()):
        out.setdefault(str(k), None)
    return out


def _fingerprint(state: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()[:16]


def diff_state(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    """MEANINGFUL transitions only, and the rule is one sentence long.

    A transition exists when a field was MEASURED (a non-None value) before, is MEASURED now, and
    the two readings DISAGREE. Everything else is observation noise with a name:

      * measured -> missing        an observation gap. The thing may be fine; the reader is blind.
      * missing  -> measured       a first reading. Nothing changed; the desk started looking.
      * missing  -> missing        nothing happened, loudly.
      * a field present on one side only   the schema moved, not the world.

    This is the entire difference between a watchtower and a pager that goes off whenever a
    scraper times out -- and a pager that cries wolf is turned off within the week, which is how
    a desk ends up with no monitoring at all.
    """
    out: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if key not in before or key not in after:
            continue
        if old is None or new is None:
            continue
        if _agree(old, new, TOLERANCE):
            continue
        out.append({"field": key, "from": old, "to": new,
                    "kind": "value_change",
                    "why": "both readings are measured and they disagree"})
    return out


def _load_history(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The last recorded state per object. The file is append-only, so the last row wins."""
    p = path or WATCHTOWER
    out: dict[str, dict[str, Any]] = {}
    if not p.exists():
        return out
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("object_id"):
                    out[str(row["object_id"])] = row
    except OSError:
        return out
    return out


def _append(path: Path, rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    return len(rows)


def watch(objects: Sequence[Mapping[str, Any]], *, path: Path | None = None,
          dry_run: bool = False, conn: Any = None,
          record: bool = True) -> list[dict[str, Any]]:
    """Re-scan the objects the desk has already seen; record what genuinely CHANGED.

    Every scanned object gets a row in the ledger (so the next pass has a `before` for it) and
    only the objects with a real transition get a registry discovery and a memory row. A pass that
    records a hundred observations and zero discoveries is a healthy pass, not a wasted one.
    """
    p = path or WATCHTOWER
    history = _load_history(p)
    rows: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    at = _now()
    for obj in objects:
        oid = str(obj.get("object_id") or obj.get("id") or obj.get("path") or "")
        if not oid:
            continue
        kind = str(obj.get("kind") or "dataset")
        state = observe(obj)
        prev = history.get(oid, {})
        before = prev.get("state") if isinstance(prev.get("state"), Mapping) else {}
        changes = diff_state(before or {}, state)
        row = {"object_id": oid, "kind": kind, "at": at, "state": state,
               "fingerprint": _fingerprint(state), "n_changes": len(changes),
               "changes": changes, "first_seen": bool(not prev)}
        rows.append(row)
        for ch in changes:
            transitions.append({**ch, "object_id": oid, "kind": kind, "at": at})
    if dry_run:
        return transitions
    _append(p, rows)
    if record and transitions:
        _record_transitions(transitions, conn=conn)
    return transitions


def _record_transitions(transitions: Sequence[Mapping[str, Any]], *, conn: Any = None) -> int:
    """A real transition becomes a registry DISCOVERY (source_type `watchtower`) and a memory row.

    The discovery is what lets the compiler turn "this dataset's row count fell by 40%" into
    testable cells; the memory row is what lets a session six weeks later find the same history
    without knowing the file exists.
    """
    own = conn is None
    c = conn or R.connect()
    n = 0
    try:
        for t in transitions:
            oid = str(t.get("object_id") or "")
            R.record_discovery(
                source_id=f"watchtower:{oid}", source_type="watchtower",
                mechanism=(f"{t.get('field')} on {oid} moved {t.get('from')!r} -> "
                           f"{t.get('to')!r}")[:400],
                origin="DESK", generator="evidence_watchtower",
                assets=[], sessions=["all"], horizons=["D1"],
                economic_rationale=("a watched object's evidence changed; the change is the "
                                    "hypothesis, and nothing about it is verified yet"),
                falsifier="the change does not recur and does not separate anything downstream",
                payload=dict(t), conn=c)
            R.remember("watchtower", f"{oid}: {t.get('field')} {t.get('from')!r} -> "
                                     f"{t.get('to')!r}",
                       kind="transition", memory_key=f"watchtower:{oid}:{t.get('field')}",
                       result="pending", payload=dict(t), conn=c)
            n += 1
    finally:
        if own:
            c.close()
    return n


# --------------------------------------------------------------------------- the fixture
#: THE MISSING-DATA FIXTURE. Ten objects observed twice; on the second pass every second object
#: loses half its fields and two vanish entirely. A correct watchtower reports ZERO transitions,
#: because nothing about the WORLD changed -- only the desk's ability to see it did.
def missing_data_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    first: list[dict[str, Any]] = []
    second: list[dict[str, Any]] = []
    for i in range(10):
        oid = f"fixture:{i}"
        fields = {"growth": 10.0 + i, "drawdown": 3.0 + i, "status": "active",
                  "subscribers": 100 + i}
        first.append({"object_id": oid, "kind": "leaderboard_system", "fields": dict(fields),
                      "track": list(fields)})
        if i % 2 == 0:
            gone = {k: (None if k in ("growth", "drawdown") else v) for k, v in fields.items()}
            second.append({"object_id": oid, "kind": "leaderboard_system", "fields": gone,
                           "track": list(fields)})
        elif i >= 8:
            second.append({"object_id": oid, "kind": "leaderboard_system", "fields": {},
                           "track": list(fields)})
        else:
            second.append({"object_id": oid, "kind": "leaderboard_system", "fields": dict(fields),
                           "track": list(fields)})
    return first, second


def false_transition_rate() -> dict[str, Any]:
    """Measure the watchtower's own false-positive rate on the missing-data fixture. MUST BE 0.

    Run in memory against a throwaway ledger: the first pass establishes the baseline, the second
    removes readings without changing a single underlying value, and every transition reported is
    by construction FALSE. This number is published in the report on every pass, because a
    watchtower's credibility is exactly its false-transition rate and a desk that does not measure
    it will believe the alarm the day it should not.
    """
    import tempfile
    first, second = missing_data_fixture()
    with tempfile.TemporaryDirectory(prefix="watchtower_fixture_") as d:
        tmp = Path(d) / "ledger.jsonl"
        watch(first, path=tmp, record=False)
        transitions = watch(second, path=tmp, record=False)
    n_fields = sum(len(o.get("track") or ()) for o in second)
    return {"false_transitions": len(transitions), "observations": n_fields,
            "false_transition_rate": (len(transitions) / n_fields) if n_fields else 0.0,
            "must_be": 0.0, "detail": list(transitions)[:5],
            "rule": "a missing field is an observation gap, never a change"}


# --------------------------------------------------------------------------- the organ
def default_objects() -> list[dict[str, Any]]:
    """What this box actually has to watch: the artifacts the desk's own decisions rest on."""
    watched = [
        ("live_assumption", DESK / "data" / "sleeves.json"),
        ("live_assumption", DESK / "data" / "forward_reconcile.json"),
        ("dataset", DESK / "reports" / "UNIVERSAL_SURVIVORS.json"),
        ("dataset", DESK / "data" / "universe" / "universe.json"),
        ("dataset", DESK / "data" / "forced_flow_calendar.json"),
        ("product", DESK / "reports" / "SOURCE_REGISTRY.json"),
        ("mechanism", DESK / "data" / "graveyard.json"),
    ]
    return [{"object_id": f"{kind}:{p.name}", "kind": kind, "path": str(p),
             "track": ["exists", "size", "n_rows"]} for kind, p in watched]


def run_pass(*, dry_run: bool = False, budget_s: float = 120.0,
             objects: Sequence[Mapping[str, Any]] | None = None,
             claims: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    objs = list(objects) if objects is not None else default_objects()
    transitions = watch(objs, dry_run=dry_run)
    verdicts = [verify(c).as_row() for c in (claims or [])
                if (time.monotonic() - started) < budget_s]
    rate = false_transition_rate()
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[str(v["verdict"])] = counts.get(str(v["verdict"]), 0) + 1
    report = {
        "generated_at": _now(), "dry_run": dry_run,
        "elapsed_s": round(time.monotonic() - started, 2),
        "chain": ["direct_observable", "second_source", "state_reconciliation", "provenance",
                  "UNRESOLVED if unknowable", "candidate only after agreement"],
        "checkers": list(CHECKERS), "required_for_candidate": list(REQUIRED_FOR_CANDIDATE),
        "direct_observable_checks": list(DIRECT_OBSERVABLE),
        "object_kinds": list(OBJECT_KINDS),
        "objects_watched": len(objs), "transitions": transitions,
        "n_transitions": len(transitions),
        "claims_verified": counts, "verdicts": verdicts[:50],
        "false_transition": rate,
        "ledger": str(WATCHTOWER),
        "rule": "a missing field is UNRESOLVED, never a change; a claim becomes a candidate only "
                "after an independent second source agrees with a direct observable",
    }
    if not dry_run:
        _atomic(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the evidence watchtower")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    rep = run_pass(dry_run=bool(a.dry_run), budget_s=float(a.budget_s))
    print(json.dumps({k: rep[k] for k in ("generated_at", "dry_run", "objects_watched",
                                          "n_transitions", "false_transition",
                                          "claims_verified")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
