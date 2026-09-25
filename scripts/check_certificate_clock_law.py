#!/usr/bin/env python3
"""L1.102 -- A CERTIFICATE WITHOUT AN ACCUMULATING FORWARD CLOCK IS A BREACH.

THE ORDER (principal, 2026-09-24): "They must all automatically be on forward clocks live
immediate upon certification, in future all -- this not happening is a breach." That is the
standing AUTOMATIC PROMOTION rule of 2026-09-04 ("all promotion candidates get into the live
account immediately, no waiting, no permission, fully automatically, always") stated from the
other end: a certificate the desk cannot mature is a certificate the desk cannot promote, and an
unpromotable certificate breaches the rule exactly as completely as a refused promotion does.

WHY THIS FENCE EXISTS WHEN TWO CLOCK FENCES ALREADY DO, and the answer is one line of somebody
else's code. `research/forward_enrolment.census` decides whether a clock is accruing FROM THE
STATUS STRING ALONE:

    if state in ACCRUING_STATUSES:      # {"", "ACTIVE", "NONE", "UNMEASURED"}
        entry["accruing"] = True

Measured on the trading box 2026-09-24T23:25Z: 172 clocks, 171 of them `ACTIVE`, and 116 of
those had accumulated **zero forward observations**. The existing census called all 171
accruing. It was reading a label, not a ledger. That is this desk's signature deception in its
purest form -- the same shape as `fred.json` refreshing every thirty minutes onto 893 unchanged
bytes, and the same shape as a shadow ledger whose mtime moves while its row count is frozen.
`check_clock_liveness` is the nearest neighbour and asks a genuinely different question (has the
last ADVANCE fallen behind the venue's own bars), which a clock that has never advanced at all,
and so has no `last_entry` to be behind, answers vacuously.

SO THIS FENCE NEVER READS A STATUS TO DECIDE ACCUMULATION. It snapshots each clock's OBSERVATION
COUNT into `data/certificate_clock_history.json` on every pass and diffs successive samples. A
clock is accumulating if and only if its row count actually moved. No status string, no
`last_attempt_at`, no file mtime and no amount of re-running the engine can satisfy it; only real
forward observations can. That is the point: A FENCE THAT CAN BE SATISFIED BY FABRICATION IS
WORSE THAN NO FENCE.

THE DISTINCTION THAT IS THE WHOLE DESIGN, and getting it wrong in either direction ruins the law:

  * A clock that EXISTS and IS ACCUMULATING but is not yet mature is **COMPLIANT**. Forward time
    passing is the entire mechanism, not a delay. Never flag it, and nothing here may be read as
    licence to short-circuit it.
  * A clock that EXISTS and is still WARMING -- no observation yet, but younger than its own
    family's measured inter-observation gap -- is **COMPLIANT**. Measured tonight: 115 of the 116
    zero-observation clocks had been enrolled 2.3 hours earlier, because canon was republished at
    20:06Z. A fence that called those a breach would fire on every healthy new certificate the
    desk ever mints and would be switched off within a day.
  * A clock that DOES NOT EXIST, or exists and DOES NOT ACCUMULATE, is a **BREACH**, named with
    its certificate and its cause.

THE WARMING THRESHOLD IS DERIVED, NEVER DECLARED. Per family, from the desk's own forward
evidence: the median `(last_entry - first_entry) / (n - 1)` over that family's clocks that have
at least two observations, times `FROZEN_MULTIPLE`. The code path is identical for every family
-- there is no lookup table and no per-family branch, which is the point, because five of the
seven families have never had a live sleeve and a registry of known families would simply be the
next bug. A family with no two-observation clock yet reads UNMEASURED and is REPORTED, never
breached (L1.28a): absence is a real answer, not a clean bill and not a conviction.

THE LATENCY HALF, because "immediate" is the principal's word. `enrolled_at - gated_at` per
certificate, breached past `LATENCY_BREACH_H` -- one promoter cycle. A certificate that gets a
clock EVENTUALLY still fails the rule, and `forward_enrolment` already computes this number
against a `TARGET_LATENCY_H` of 0.0; what was missing was anything that treats exceeding it as a
breach rather than as a published statistic.

NOTHING HERE IS A CAP, A THROTTLE OR A STAGING GATE. This fence measures and names; it enrols
nothing, refuses nothing, sizes nothing and retires nothing. THE REMEDY FOR A BREACH IS ALWAYS
TO GIVE THE CERTIFICATE ITS CLOCK -- never to withdraw the certificate, never to shrink the book
(GROWTH GOVERNANCE Rule 1, and the standing order of 2026-09-08 that the desk never reduces its
aggressiveness).

HOST APPLICABILITY. A host with nothing scheduled to advance a clock cannot have a stalled one,
so on a build box this reads NOT_APPLICABLE rather than convicting `shadow_forward` of failing to
run where nothing was ever going to run it. That reuses `clock_liveness.mt5_installed` rather
than reinventing the judgement.

Artifact: `desks/mt5/reports/CERTIFICATE_CLOCK_LAW.json`
History:  `desks/mt5/data/certificate_clock_history.json`
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "CERTIFICATE_CLOCK_LAW.json"
HISTORY = DESK / "data" / "certificate_clock_history.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"

ALERT_ID = "certificate_clock_law"

#: One promoter cycle. A certificate certified at T must hold a ticking clock by T+1h; the
#: principal's word is "immediate" and `forward_enrolment.TARGET_LATENCY_H` is 0.0, so this is
#: the breach line, not the goal.
LATENCY_BREACH_H = 1.0

#: How many measured inter-observation gaps a clock may miss before its frozen row count is a
#: breach rather than a quiet market.
FROZEN_MULTIPLE = 3.0

#: The floor under the derived threshold, so an ordinary weekend can never manufacture a breach:
#: an M5 clock's measured gap can be minutes, and 3x minutes would convict every clock the desk
#: holds every Saturday. This makes the fence QUIETER and never makes the book smaller.
MIN_FROZEN_H = 72.0

#: Samples kept in the history file. At the hourly cadence this is two days of row counts, which
#: is what the frozen test needs to look back across `MIN_FROZEN_H`.
MAX_SAMPLES = 96

#: A row carrying one of these has no verdict yet and the next pass will replay it. The engine
#: writes `""` for an evaluated, unruled row; reading that as broken would fail on nearly every
#: healthy clock. Mirrors `forward_enrolment.ACCRUING_STATUSES` ON PURPOSE -- the two must agree
#: about what "working" means, and disagree only about whether a label is evidence of it.
WORKING_STATUSES = frozenset({"", "ACTIVE", "NONE", "UNMEASURED"})

#: A verdict, not a stall: the clock did its job and the desk decided.
DECIDED_STATUSES = frozenset({"KILL", "PROMOTED", "DEAD", "REJECTED", "RETIRED",
                              "PROMOTION CANDIDATE", "PROMOTION_CANDIDATE"})

#: The lane state files that hold forward clock rows, in the order the engine writes them.
LANES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
         "external_shadow_state.json", "FAMILY_shadow_state.json")

UNMEASURED = "UNMEASURED"


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(tz=UTC)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        t = datetime.fromisoformat(raw.strip().replace(" ", "T"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def host_runs_clocks(desk: Path | None = None) -> tuple[bool, str]:
    """Does anything on this host advance a forward clock?

    Reuses `clock_liveness.mt5_installed` rather than reinventing it: a host with no MetaTrader5
    package has no terminal, no bars, and nothing scheduled to move a clock, so its stale state
    copies are not evidence of a stall anywhere.
    """
    try:
        sys.path.insert(0, str(desk or DESK))
        from research import clock_liveness  # type: ignore[import-not-found]
        if clock_liveness.mt5_installed():
            return True, "MetaTrader5 is installed: this host advances forward clocks"
        return False, ("no MetaTrader5 package here: no terminal, no bars, nothing scheduled to "
                       "advance a forward clock, so a frozen row count is not this host's defect")
    except Exception as exc:
        return False, f"clock_liveness unavailable ({type(exc).__name__}: {exc}): host UNMEASURED"


def certificates(canon: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Every canon certificate as {name, symbol, family, selector, side, params, certified_at}.

    Reads the canon FILE rather than importing the gauntlet, so the fence means the same thing in
    CI, in a fresh clone and on the box, and can never be the organ that hangs the cycle.
    """
    notes: list[str] = []
    doc = _read_json(canon or CANON)
    if not isinstance(doc, dict):
        return [], [f"canon unreadable or absent at {canon or CANON}: certificates {UNMEASURED}"]
    surv = doc.get("survivors")
    if not isinstance(surv, dict):
        return [], [f"canon carries no `survivors` mapping: certificates {UNMEASURED}"]
    out: list[dict[str, Any]] = []
    for name, row in surv.items():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec")
        if not isinstance(spec, dict):
            notes.append(f"{name}: no shadow_spec, so no clock identity can be derived")
            continue
        out.append({
            "name": str(name),
            "symbol": str(spec.get("symbol") or row.get("sym") or ""),
            "family": str(spec.get("family") or ""),
            "selector": str(spec.get("selector") or ""),
            "side": str(spec.get("side") or "LONG").upper(),
            "params": spec.get("params") if isinstance(spec.get("params"), dict) else {},
            "certified_at": str(row.get("gated_at") or "") or UNMEASURED,
        })
    return out, notes


def clock_keys(certs: list[dict[str, Any]],
               desk: Path | None = None) -> tuple[dict[str, str], list[str]]:
    """certificate name -> the engine's own `sleeve_key`, plus notes.

    THE KEY MUST BE THE ENGINE'S, NOT A RECONSTRUCTION. `shadow_forward.sleeve_key` carries
    hard-won rules (a long key is byte-identical to what it has always been so no running clock
    is renamed; the chart suffix appears only off H1) and a fence that guessed the shape would
    convict healthy clocks of not existing. If the engine cannot be imported the keys are
    UNMEASURED and this fence says so rather than inventing them.
    """
    base = desk or DESK
    try:
        sys.path.insert(0, str(base))
        sys.path.insert(0, str(base / "research"))
        import shadow_forward as sf  # type: ignore[import-not-found]
    except Exception as exc:
        return {}, [f"shadow_forward unavailable ({type(exc).__name__}: {exc}): "
                    f"clock keys {UNMEASURED}"]
    keys: dict[str, str] = {}
    notes: list[str] = []
    for c in certs:
        try:
            keys[c["name"]] = sf.sleeve_key(c["symbol"], c["selector"], dict(c["params"]),
                                            c["family"], c["side"])
        except Exception as exc:
            notes.append(f"{c['name']}: sleeve_key refused ({type(exc).__name__}: {exc})")
    return keys, notes


def clock_rows(desk: Path | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Every forward clock row on this host, keyed as the engine keys it."""
    base = (desk or DESK) / "reports" / "shadow"
    rows: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    for lane in LANES:
        doc = _read_json(base / lane)
        if not isinstance(doc, dict):
            continue
        for key, row in doc.items():
            if isinstance(row, dict) and "n" in row:
                rows.setdefault(str(key), {**row, "lane": lane})
    if not rows:
        notes.append(f"no lane state file under {base} carries a clock row: clocks {UNMEASURED}")
    return rows, notes


def family_gap_hours(rows: dict[str, dict[str, Any]],
                     key_family: dict[str, str]) -> dict[str, float]:
    """family -> its MEASURED median hours between forward observations.

    Derived from this desk's own forward evidence and nothing else: no constant, no lookup table,
    no per-family branch. A family whose clocks have never produced two observations is absent
    from the mapping, which the caller reads as UNMEASURED rather than as a pass or a conviction.
    """
    per: dict[str, list[float]] = {}
    for key, row in rows.items():
        fam = key_family.get(key)
        if not fam:
            continue
        n = row.get("n")
        if not isinstance(n, int) or n < 2:
            continue
        first, last = _parse_ts(row.get("first_entry")), _parse_ts(row.get("last_entry"))
        if first is None or last is None or last <= first:
            continue
        per.setdefault(fam, []).append((last - first).total_seconds() / 3600.0 / (n - 1))
    return {fam: statistics.median(gaps) for fam, gaps in per.items() if gaps}


def _threshold_h(family: str, gaps: dict[str, float]) -> tuple[float | None, str]:
    gap = gaps.get(family)
    if gap is None:
        return None, (f"no clock in `{family}` has two forward observations yet, so its "
                      f"inter-observation gap is {UNMEASURED}")
    thr = max(MIN_FROZEN_H, gap * FROZEN_MULTIPLE)
    return thr, (f"measured gap {gap:.2f}h x{FROZEN_MULTIPLE:g}, floored at {MIN_FROZEN_H:g}h "
                 f"so a weekend cannot manufacture a breach -> {thr:.1f}h")


def load_history(path: Path | None = None) -> list[dict[str, Any]]:
    doc = _read_json(path or HISTORY)
    if isinstance(doc, dict) and isinstance(doc.get("samples"), list):
        return [s for s in doc["samples"] if isinstance(s, dict)]
    return []


def save_history(samples: list[dict[str, Any]], path: Path | None = None) -> Path:
    p = Path(path or HISTORY)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "samples": samples[-MAX_SAMPLES:],
        "rule": ("one sample per pass of the observation COUNT of every forward clock. The law's "
                 "accumulation test diffs these; a status string, a fresh mtime or a re-run of "
                 "the engine cannot move them, which is the whole defence"),
    }, indent=1, default=str) + "\n", encoding="utf-8")
    return p


def _prior_sample(samples: list[dict[str, Any]], key: str,
                  now: datetime, threshold_h: float) -> tuple[int | None, datetime | None]:
    """The oldest recorded count for `key` that is at least `threshold_h` old.

    Oldest-within-window rather than most-recent: the question is whether the clock moved across
    the whole window, and the most recent sample is minutes old on an hourly cadence.
    """
    best: tuple[int, datetime] | None = None
    for s in samples:
        t = _parse_ts(s.get("at"))
        if t is None or (now - t).total_seconds() / 3600.0 < threshold_h:
            continue
        counts = s.get("counts")
        if not isinstance(counts, dict) or key not in counts:
            continue
        n = counts.get(key)
        if not isinstance(n, int):
            continue
        if best is None or t < best[1]:
            best = (n, t)
    return best if best is not None else (None, None)


def _seal(entry: dict[str, Any]) -> dict[str, Any]:
    """Fold the latency condition into the verdict WITHOUT overwriting it.

    The accumulation verdict is the answer to the law's main question and always survives; a late
    clock adds a breach alongside it rather than replacing it. `breach` is the OR, so the fence
    fails on either, and the report still says which.
    """
    if entry.get("late"):
        entry["breach"] = True
    return entry


def judge(cert: dict[str, Any], key: str | None, row: dict[str, Any] | None,
          samples: list[dict[str, Any]], threshold_h: float | None, why_thr: str,
          now: datetime) -> dict[str, Any]:
    """One certificate's verdict. The ONLY place a breach is decided."""
    entry: dict[str, Any] = {
        "certificate": cert["name"], "symbol": cert["symbol"], "family": cert["family"],
        "selector": cert["selector"], "side": cert["side"],
        "key": key or UNMEASURED, "certified_at": cert["certified_at"],
        "n": (row or {}).get("n", UNMEASURED),
        "status": (row or {}).get("status", UNMEASURED),
        "lane": (row or {}).get("lane", UNMEASURED),
        "threshold_h": round(threshold_h, 2) if threshold_h is not None else UNMEASURED,
        "threshold_why": why_thr,
        "latency_h": UNMEASURED,
    }

    if key is None:
        entry.update(verdict="UNMEASURED_KEY", breach=False,
                     why="the engine could not be imported, so this certificate's clock key is "
                         "UNMEASURED -- a real answer, never a pass and never a conviction")
        return entry

    # ---- 1. does a clock exist at all?
    if row is None:
        gated = _parse_ts(cert["certified_at"])
        entry["clockless_h"] = (round((now - gated).total_seconds() / 3600.0, 2)
                                if gated else UNMEASURED)
        entry.update(verdict="NO_CLOCK", breach=True,
                     why="BREACH: certified and holds no forward clock at all, so it can never "
                         "mature and can never be promoted. Remedy: enrol it -- never withdraw "
                         "the certificate")
        return entry

    # ---- 2. did it get that clock IMMEDIATELY? ("immediate" is the principal's word)
    #
    # MEASURED FROM THE EARLIEST EVIDENCE THAT A CLOCK EXISTED, not from `enrolled_at` alone, and
    # the difference is the difference between a measurement and a libel. `enrolled_at` is
    # REWRITTEN every time the enrolment leg touches a row, so on 2026-09-24 -- when canon was
    # republished at 20:06Z and enrolment ran at 21:00Z -- every one of the 174 certificates
    # carried an `enrolled_at` of 21:00 whatever its clock had been doing. Reading latency off
    # that field alone charged `external.XAUUSD.session_range_breakout` 679 hours for a clock
    # whose `forward_start` proves it has been running since 2026-08-27. `forward_start` is the
    # honest stamp: it is when THIS clock began accruing and the engine does not refresh it.
    #
    # AND LATENCY NEVER SHORT-CIRCUITS THE ACCUMULATION VERDICT. A certificate can be both late
    # and now accruing perfectly well; returning here would report 174 LATE_CLOCKs and say
    # nothing whatever about whether a single clock is ticking, which is the question the law
    # exists to answer. The two conditions are independent and both are published.
    gated = _parse_ts(cert["certified_at"])
    stamps = [t for t in (_parse_ts(row.get("forward_start")),
                          _parse_ts(row.get("enrolled_at"))) if t is not None]
    late = False
    if gated is not None and stamps:
        began = min(stamps)
        lat = max(0.0, (began - gated).total_seconds() / 3600.0)
        entry["latency_h"] = round(lat, 3)
        entry["clock_began_at"] = began.isoformat()
        late = lat > LATENCY_BREACH_H
        if late:
            entry["latency_breach"] = (
                f"BREACH: {lat:.2f}h from certification to a ticking clock, past the "
                f"{LATENCY_BREACH_H:g}h promoter cycle. A certificate that gets a clock "
                f"EVENTUALLY still fails 'immediately, no waiting, fully automatically, always'")
    entry["late"] = late

    status = str(row.get("status") or "").strip().upper()

    # ---- 3. a decided clock did its job; it is not a stall
    if (status in DECIDED_STATUSES
            or status.startswith("QUARANTINED")
            or any(status.startswith(d + "_") for d in DECIDED_STATUSES)):
        entry.update(verdict="DECIDED", breach=False,
                     why=f"`{status}` is a verdict the clock reached, not a wiring defect")
        return _seal(entry)

    # ---- 4. a clock the engine refuses to advance is a breach whatever its row count says
    if status not in WORKING_STATUSES:
        entry.update(verdict="BLOCKED", breach=True,
                     blocker=str(row.get("last_error") or "")[:400] or status,
                     why=f"BREACH: the engine will not advance this clock (`{status}`), so the "
                         f"certificate can never mature. Fix the blocker, never the certificate")
        return _seal(entry)

    # ---- 5. THE ROW COUNT ITSELF. Never the status, never the mtime.
    n = row.get("n")
    n = n if isinstance(n, int) else 0
    entry["n"] = n
    if threshold_h is None:
        entry.update(verdict="UNMEASURED_THRESHOLD", breach=False,
                     why=f"the clock is running and this family's inter-observation gap is "
                         f"{UNMEASURED}, so whether {n} observation(s) is a stall cannot yet be "
                         f"decided. Reported, never breached (L1.28a)")
        return _seal(entry)

    prior_n, prior_at = _prior_sample(samples, key, now, threshold_h)
    if prior_n is not None and n > prior_n:
        entry.update(verdict="ACCUMULATING", breach=False, prior_n=prior_n,
                     prior_at=prior_at.isoformat() if prior_at else UNMEASURED,
                     why=f"row count moved {prior_n} -> {n} since "
                         f"{prior_at.isoformat() if prior_at else UNMEASURED}: real forward "
                         f"evidence, measured from the rows")
        return _seal(entry)

    started = _parse_ts(row.get("forward_start")) or _parse_ts(row.get("enrolled_at"))
    age_h = (now - started).total_seconds() / 3600.0 if started else None
    entry["clock_age_h"] = round(age_h, 2) if age_h is not None else UNMEASURED

    if prior_n is None:
        # No sample old enough to diff against. If the clock is itself younger than the window it
        # is WARMING; otherwise the history simply has not run long enough yet to rule.
        if age_h is not None and age_h < threshold_h:
            entry.update(verdict="WARMING", breach=False,
                         why=f"enrolled {age_h:.1f}h ago with {n} observation(s), inside this "
                             f"family's own {threshold_h:.1f}h gap. Forward time passing is the "
                             f"mechanism, not a delay")
        else:
            entry.update(verdict="UNMEASURED_HISTORY", breach=False,
                         why=f"no row-count sample yet reaches back {threshold_h:.1f}h, so "
                             f"accumulation is {UNMEASURED} on this pass. It becomes measurable "
                             f"once the leg has run that long")
        return _seal(entry)

    if n > 0 and age_h is not None and age_h < threshold_h:
        entry.update(verdict="WARMING", breach=False, prior_n=prior_n,
                     why=f"{n} observation(s) and only {age_h:.1f}h old, inside the "
                         f"{threshold_h:.1f}h gap: still accruing")
        return _seal(entry)

    entry.update(verdict="FROZEN_ROWS", breach=True, prior_n=prior_n,
                 prior_at=prior_at.isoformat() if prior_at else UNMEASURED,
                 why=f"BREACH: the row count has not moved off {n} since "
                     f"{prior_at.isoformat() if prior_at else UNMEASURED} "
                     f"(>{threshold_h:.1f}h, this family's own measured gap). The clock's status "
                     f"reads `{status or 'ACTIVE'}` and its file is being rewritten -- a fresh "
                     f"timestamp over frozen content is not evidence")
    return _seal(entry)


def scan(root: Path | None = None, *, now: datetime | None = None,
         record: bool = True) -> dict[str, Any]:
    base = Path(root or ROOT)
    desk = base / "desks" / "mt5"
    t = _now(now)
    notes: list[str] = []
    problems: list[str] = []

    runs, why_host = host_runs_clocks(desk)
    if not runs:
        return {"at": t.isoformat(), "ok": True, "verdict": "NOT_APPLICABLE",
                "host_why": why_host, "certificates": [], "problems": [],
                "notes": [f"NOT_APPLICABLE: {why_host}"], "counts": {},
                "law": "L1.102", "alert_id": ALERT_ID}

    certs, cnotes = certificates(desk / "data" / "UNIVERSAL_SURVIVORS.canon.json")
    notes.extend(cnotes)
    keys, knotes = clock_keys(certs, desk)
    notes.extend(knotes)
    rows, rnotes = clock_rows(desk)
    notes.extend(rnotes)

    if not certs:
        return {"at": t.isoformat(), "ok": True, "verdict": UNMEASURED, "host_why": why_host,
                "certificates": [], "problems": [], "notes": notes or ["canon UNMEASURED"],
                "counts": {}, "law": "L1.102", "alert_id": ALERT_ID}

    key_family = {keys[c["name"]]: c["family"] for c in certs if c["name"] in keys}
    gaps = family_gap_hours(rows, key_family)
    samples = load_history(desk / "data" / "certificate_clock_history.json")

    judged: list[dict[str, Any]] = []
    for c in certs:
        key = keys.get(c["name"])
        thr, why_thr = _threshold_h(c["family"], gaps)
        judged.append(judge(c, key, rows.get(key) if key else None,
                            samples, thr, why_thr, t))

    counts: dict[str, int] = {}
    for e in judged:
        counts[str(e["verdict"])] = counts.get(str(e["verdict"]), 0) + 1

    # THE DUPLICATE READING, published rather than hidden. Two canon rows that differ only by an
    # explicitly-written default collapse onto one `sleeve_key`; that is a canon defect, and it
    # BREAKS the clock they share (the identity guard sees params change under a frozen clock).
    seen: dict[str, list[str]] = {}
    for c in certs:
        k = keys.get(c["name"])
        if k:
            seen.setdefault(k, []).append(c["name"])
    collisions = {k: names for k, names in seen.items() if len(names) > 1}

    # TWO INDEPENDENT BREACH CONDITIONS, REPORTED SEPARATELY. A clock can be late AND ticking,
    # or punctual AND frozen; collapsing them would hide whichever came second.
    for e in judged:
        if e.get("verdict") not in ("ACCUMULATING", "WARMING", "DECIDED", "UNMEASURED_KEY",
                                    "UNMEASURED_THRESHOLD", "UNMEASURED_HISTORY"):
            problems.append(f"{e['verdict']} {e['certificate']} ({e['family']}): {e['why']}")
    late = [e for e in judged if e.get("late")]
    for e in late:
        problems.append(f"LATE_CLOCK {e['certificate']} ({e['family']}): {e['latency_breach']}")

    latencies = [e["latency_h"] for e in judged if isinstance(e.get("latency_h"), (int, float))]
    notes.append(f"{len(certs)} certificate(s), {len(set(keys.values()))} distinct clock key(s), "
                 f"{len(rows)} clock row(s) on this host")
    notes.append("verdicts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if latencies:
        notes.append(f"certification->clock latency hours: median "
                     f"{statistics.median(latencies):.3f}, max {max(latencies):.3f} "
                     f"(breach past {LATENCY_BREACH_H:g})")
    for fam in sorted({c["family"] for c in certs}):
        g = gaps.get(fam)
        notes.append(f"family `{fam}`: measured inter-observation gap "
                     + (f"{g:.2f}h" if g is not None else UNMEASURED))
    if collisions:
        for k, names in sorted(collisions.items()):
            problems.append(
                f"CANON_DUPLICATE {k}: {len(names)} certificates share one clock key "
                f"({', '.join(sorted(names))}). They differ only by a default written out "
                f"explicitly; they alternately rewrite one row, which the identity guard reads "
                f"as `params changed after the clock froze`. Remedy: collapse the duplicate in "
                f"the organ that mints canon -- never retire the clock")

    doc = {
        "at": t.isoformat(), "law": "L1.102", "alert_id": ALERT_ID,
        "host_why": why_host,
        "ok": not problems,
        "verdict": "BREACH" if problems else "COMPLIANT",
        "n_certificates": len(certs),
        "n_clock_keys": len(set(keys.values())),
        "n_clock_rows": len(rows),
        "counts": counts,
        "n_late": len(late),
        "latency_breach_h": LATENCY_BREACH_H,
        "family_gap_hours": {k: round(v, 3) for k, v in sorted(gaps.items())},
        "collisions": collisions,
        "certificates": judged,
        "problems": problems,
        "notes": notes,
        "rule": ("a certificate holds a clock that is ACCUMULATING, measured from its observation "
                 "COUNT across passes and never from a status, an mtime or a re-run. Warming is "
                 "compliant; absent, blocked, late or frozen is a breach. The remedy is always to "
                 "give the certificate its clock -- never to withdraw it and never to cap it"),
    }
    if record:
        samples.append({"at": t.isoformat(),
                        "counts": {k: (r.get("n") if isinstance(r.get("n"), int) else 0)
                                   for k, r in rows.items()}})
        save_history(samples, desk / "data" / "certificate_clock_history.json")
    return doc


def record_alert(doc: dict[str, Any], root: Path | None = None) -> str | None:
    base = Path(root or ROOT) / "desks" / "mt5"
    try:
        from libs.ops.alert_ledger import AlertLedger
    except Exception:
        return None
    try:
        ledger = AlertLedger(base / "data" / "alert_ledger.json")
        if doc.get("ok") or doc.get("verdict") in ("NOT_APPLICABLE", UNMEASURED):
            alert = ledger.alerts.get(ALERT_ID)
            if alert is not None and alert.open:
                ledger.verify(ALERT_ID, still_firing=False)
                ledger.save()
                return "FIXED"
            return None
        ledger.observe(ALERT_ID, "; ".join(str(p) for p in doc.get("problems", []))[:600],
                       scope="RUNTIME")
        ledger.save()
        return "OPEN"
    except Exception:
        return None


def write_artifact(doc: dict[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact as JSON")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    ap.add_argument("--no-record", action="store_true",
                    help="do not append a row-count sample to the history")
    args = ap.parse_args(argv)

    doc = scan(record=not args.no_record)
    if not args.no_write:
        write_artifact(doc)
        doc["alert"] = record_alert(doc)
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 0 if doc["ok"] else 2

    print(f"certificate clock law (L1.102): {doc.get('verdict')}; "
          f"{doc.get('n_certificates', 0)} certificate(s), "
          f"{doc.get('n_clock_keys', 0)} clock key(s)")
    for k, v in sorted((doc.get("counts") or {}).items()):
        print(f"    {k:24s} {v}")
    for note in doc["notes"]:
        print(f"  note: {note}")
    for problem in doc["problems"][:40]:
        print(f"  FAIL: {problem}")
    extra = len(doc["problems"]) - 40
    if extra > 0:
        print(f"  FAIL: ... and {extra} more")
    if doc["ok"]:
        print("check_certificate_clock_law: OK -- every certificate holds an accumulating clock")
        return 0
    print("check_certificate_clock_law: FAILED -- a certificate cannot mature, so it cannot be "
          "promoted. Give it its clock; never withdraw the certificate")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
