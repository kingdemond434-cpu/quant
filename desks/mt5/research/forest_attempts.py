"""FOREST ATTEMPTS: every deep-forest ground attempted on a daily cycle, or retired by name.

THE ORDER (principal, 2026-09-30 breadth review): "467 of 502 deep-forest vectors have never been
attempted, and only 10 have yielded." Fix the organ so every vector is attempted on a bounded
cycle -- every ground at least once a day -- or is EXPLICITLY retired as LOW_EV_RETIRED with its
recorded evidence and a named reopen condition. Publish attempted / never-attempted / yielded /
retired hourly, with a fence that turns red when never-attempted does not fall.

WHY THE VECTORS WERE NEVER ATTEMPTED (read from the code and the committed state, 2026-09-30):
  * THE LEG WAS KILLED BEFORE IT WROTE. `deep_forest_miner` ran a 900 s budget under a 720 s
    cycle cap and wrote every ledger only at the END, so a killed hour recorded nothing and the
    next hour restarted from the same cursor (fixed in 2c6059958: per-ground checkpoints, a leg
    cap above the budget, least-recently-attempted order, eight workers).
  * THE COMMITTED FRONTIER IS A PHOTOGRAPH OF 2026-09-12. `data/deep_forest_frontier.json` was
    last committed by the box that day (502 vectors, 467 NAMED_ONLY); box commits stopped on
    2026-09-25. The registry has since grown to 535 grounds, 35 of which the frontier file does
    not name at all. So "467" is a git-only number: the box's own count is UNMEASURED from here.
  * NOTHING HELD THE DAILY FLOOR. The scheduler put NAMED_ONLY first but then ordered covered
    ground by a 45-day cooldown, so a ground hunted once could wait six weeks; and nothing
    published how many grounds were overdue, so starvation read as silence.

WHAT THIS MODULE IS. A library the miner reads (retirement verdicts -> schedule order) and one
hourly core leg (`scripts/check_forest_attempts.py`) that publishes `reports/FOREST_ATTEMPTS.json`,
appends one line per pass to `data/forest_attempt_history.jsonl`, and fences the direction. The
per-ground state it composes is written by the miner at every ground's checkpoint:

    data/deep_forest_frontier.json      outcome, attempts, last_attempt, findings, blocker
    data/deep_forest_vector_stats.json  successes, rows, datasets, last_success (last yield),
                                        last_error (failure reason), last_status, and the DELTA
                                        CURSOR: urls_new / claims_new / claims_seen_before of the
                                        last attempt, last_new_content_at, empty_delta_streak

LOW_EV_RETIRED, AND WHAT IT IS NOT. A ground is retired only on measured evidence -- at least
RETIRE_MIN_ATTEMPTS counted attempts spread over at least RETIRE_MIN_SPAN_D days with ZERO claims
and ZERO datasets ever. Retirement changes ORDER, never membership: a retired ground is scheduled
after every other ground (so it is still worked whenever the pass has budget left), it is exempt
from the daily floor, and it REOPENS -- back into the daily set -- on any of three named
conditions: REOPEN_AFTER_D days since its last attempt (the re-probe), a sibling ground in the
same region and language yielding after its last attempt, or any yield of its own. No ground is
ever deleted from the registry by this module, and none is refused: licence and terms are routing
labels (LAWS 5e).

UNMEASURED IS NEVER ZERO (L1.28a). An absent sources file, frontier or stats file is named; a
count that cannot be derived reads UNMEASURED, never 0.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
SOURCES = DESK / "data" / "deep_forest_sources.json"
FRONTIER = DESK / "data" / "deep_forest_frontier.json"
VECTOR_STATS = DESK / "data" / "deep_forest_vector_stats.json"
ARTIFACT = DESK / "reports" / "FOREST_ATTEMPTS.json"
HISTORY = DESK / "data" / "forest_attempt_history.jsonl"
UNMEASURED = "UNMEASURED"

#: The daily floor: a ground not attempted inside this many hours is OVERDUE.
DAILY_H = 24.0
#: THE BLOCKED RETRY WINDOW, the frontier's own (`hunt_frontier.BLOCKED_RETRY_D`, 10 days): a
#: ground whose last attempt was BLOCKED is re-tried on that clock, not daily, so inside the
#: window it is not OVERDUE. Read from the frontier module; 10 if it cannot be imported.
try:
    from libs.research.hunt_frontier import BLOCKED_RETRY_D as _BLOCKED_RETRY_D
    BLOCKED_RETRY_D = float(_BLOCKED_RETRY_D)
except Exception:  # pragma: no cover - the frontier module is part of this tree
    BLOCKED_RETRY_D = 10.0
#: Retirement evidence: this many counted attempts, spread over this many days, zero yield.
RETIRE_MIN_ATTEMPTS = 6
RETIRE_MIN_SPAN_D = 7.0
#: The re-probe: a retired ground re-enters the daily set this many days after its last attempt.
REOPEN_AFTER_D = 30.0
LOW_EV_RETIRED = "LOW_EV_RETIRED"
#: State per ground, one of these.
STATES: tuple[str, ...] = ("NEVER_ATTEMPTED", "ATTEMPTED", "YIELDED", LOW_EV_RETIRED)
REOPEN_CONDITION = (f"reopens into the daily set on ANY of: {REOPEN_AFTER_D:g} days since its "
                    "last attempt (the re-probe); a sibling ground with the same region and "
                    "language yields after its last attempt; any claim or dataset of its own")
#: History lines kept (one per hourly pass: ~83 days).
MAX_HISTORY = 2000


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _ts(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _later(a: Any, b: Any) -> str:
    ta, tb = _ts(a), _ts(b)
    if ta is None:
        return str(b or "")
    if tb is None:
        return str(a or "")
    return str(a) if ta >= tb else str(b)


# --------------------------------------------------------------------------- retirement
def retirement(stat: dict[str, Any] | None, vec: dict[str, Any] | None,
               sibling_yield_at: datetime | None, now: datetime) -> dict[str, Any] | None:
    """LOW_EV_RETIRED with its evidence and reopen verdict, or None when the ground is live.

    Derived from the counters alone, every pass, so there is no retirement record that can go
    stale or be forgotten: the day the evidence stops holding, the retirement is gone.
    """
    if not isinstance(stat, dict):
        return None                    # no counted attempts: never evidence for retirement
    attempts = int(stat.get("attempts") or 0)
    successes = int(stat.get("successes") or 0)
    rows = int(stat.get("rows") or 0) + int(stat.get("datasets") or 0)
    findings = int((vec or {}).get("findings") or 0)
    if successes or rows or findings or attempts < RETIRE_MIN_ATTEMPTS:
        return None
    first = _ts(stat.get("counted_since"))
    last = _ts(stat.get("last_attempt"))
    if first is None or last is None:
        return None
    span_d = (last - first).total_seconds() / 86400.0
    if span_d < RETIRE_MIN_SPAN_D:
        return None
    since_d = (now - last).total_seconds() / 86400.0
    reopen_why = ""
    if since_d >= REOPEN_AFTER_D:
        reopen_why = f"re-probe due: last attempt {since_d:.1f}d ago >= {REOPEN_AFTER_D:g}d"
    elif sibling_yield_at is not None and sibling_yield_at > last:
        reopen_why = (f"a sibling ground (same region and language) yielded at "
                      f"{sibling_yield_at.isoformat(timespec='seconds')}, after this ground's "
                      "last attempt")
    return {"state": LOW_EV_RETIRED,
            "evidence": {"attempts": attempts, "successes": 0, "claims": 0, "datasets": 0,
                         "findings": 0, "counted_since": stat.get("counted_since"),
                         "last_attempt": stat.get("last_attempt"),
                         "span_d": round(span_d, 2),
                         "last_status": stat.get("last_status") or UNMEASURED,
                         "last_error": stat.get("last_error") or "",
                         "empty_delta_streak": stat.get("empty_delta_streak", UNMEASURED)},
            "rule": (f">= {RETIRE_MIN_ATTEMPTS} counted attempts over >= {RETIRE_MIN_SPAN_D:g} "
                     "days with zero claims and zero datasets"),
            "reopen_condition": REOPEN_CONDITION,
            "reopen_due": bool(reopen_why), "reopen_why": reopen_why}


def _sibling_yields(grounds: list[dict[str, Any]], stats: dict[str, Any],
                    frontier: dict[str, Any]) -> dict[tuple[str, str], datetime]:
    """(region, language) -> the latest yield of any ground in that pair."""
    out: dict[tuple[str, str], datetime] = {}
    for g in grounds:
        name = str(g.get("name") or "")
        s = stats.get(name) if isinstance(stats.get(name), dict) else {}
        v = frontier.get(name) if isinstance(frontier.get(name), dict) else {}
        at = _ts(s.get("last_success"))
        if at is None and str(v.get("outcome") or "") == "YIELDED":
            at = _ts(v.get("last_attempt"))
        if at is None:
            continue
        key = (str(g.get("region") or ""), str(g.get("language") or ""))
        if key not in out or at > out[key]:
            out[key] = at
    return out


def retired_names(grounds: list[dict[str, Any]], *, frontier: Path | None = None,
                  stats: Path | None = None, now: datetime | None = None) -> set[str]:
    """The grounds the miner schedules LAST this pass: retired and not reopen-due."""
    now = now or datetime.now(tz=UTC)
    fr = _vectors(_json(frontier or FRONTIER))
    st = _vectors(_json(stats or VECTOR_STATS))
    sib = _sibling_yields(grounds, st, fr)
    out: set[str] = set()
    for g in grounds:
        name = str(g.get("name") or "")
        r = retirement(st.get(name), fr.get(name),
                       sib.get((str(g.get("region") or ""), str(g.get("language") or ""))), now)
        if r is not None and not r["reopen_due"]:
            out.add(name)
    return out


def _vectors(doc: Any) -> dict[str, Any]:
    vec = doc.get("vectors") if isinstance(doc, dict) else None
    return vec if isinstance(vec, dict) else {}


# --------------------------------------------------------------------------- the state
def build(*, sources: Path | None = None, frontier: Path | None = None,
          stats: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Per-ground attempt state and the counts the fence reads."""
    now = now or datetime.now(tz=UTC)
    sources = sources or SOURCES
    frontier = frontier or FRONTIER
    stats = stats or VECTOR_STATS
    src = _json(sources)
    gaps: list[dict[str, str]] = []
    if not isinstance(src, dict) or not isinstance(src.get("grounds"), list):
        return {"generated_utc": now.isoformat(timespec="seconds"), "status": UNMEASURED,
                "why": f"{sources.name} absent or unreadable: no registered ground to count",
                "summary": dict.fromkeys(("named", "never_attempted", "attempted_ever",
                                          "attempted_24h", "overdue_24h", "yielded", "retired"),
                                         UNMEASURED)}
    grounds = [g for g in src["grounds"] if isinstance(g, dict) and g.get("name")]
    fr_doc, st_doc = _json(frontier), _json(stats)
    if fr_doc is None:
        gaps.append({"what": str(frontier), "why": "frontier absent: attempts read from the "
                                                   "stats counters alone"})
    if st_doc is None:
        gaps.append({"what": str(stats), "why": "vector stats absent: no yield counter, no "
                                                "failure reason, no delta cursor and no "
                                                "retirement evidence on this host"})
    fr, st = _vectors(fr_doc), _vectors(st_doc)
    sib = _sibling_yields(grounds, st, fr)
    rows: dict[str, dict[str, Any]] = {}
    counts = dict.fromkeys(STATES, 0)
    attempted_24h = overdue = reopen_due = 0
    by_region: dict[str, dict[str, int]] = {}
    day = timedelta(hours=DAILY_H)
    for g in grounds:
        name = str(g["name"])
        v = fr.get(name) if isinstance(fr.get(name), dict) else {}
        s = st.get(name) if isinstance(st.get(name), dict) else None
        attempts = max(int(v.get("attempts") or 0), int((s or {}).get("attempts") or 0))
        last_attempt = _later(v.get("last_attempt"), (s or {}).get("last_attempt"))
        la = _ts(last_attempt)
        yielded = bool(int((s or {}).get("successes") or 0) or int(v.get("findings") or 0)
                       or str(v.get("outcome") or "") == "YIELDED")
        last_yield = (s or {}).get("last_success") or (
            v.get("last_attempt") if str(v.get("outcome") or "") == "YIELDED" else "")
        region, lang = str(g.get("region") or ""), str(g.get("language") or "")
        ret = retirement(s, v, sib.get((region, lang)), now)
        if attempts == 0:
            state = "NEVER_ATTEMPTED"
        elif ret is not None:
            state = LOW_EV_RETIRED
        elif yielded:
            state = "YIELDED"
        else:
            state = "ATTEMPTED"
        counts[state] += 1
        recent = la is not None and now - la <= day
        attempted_24h += int(recent)
        exempt = ret is not None and not ret["reopen_due"]
        blocked_until = ""
        if str(v.get("outcome") or "") == "BLOCKED" and la is not None \
                and now - la < timedelta(days=BLOCKED_RETRY_D):
            exempt = True                   # inside the blocked retry window: not due daily
            blocked_until = (la + timedelta(days=BLOCKED_RETRY_D)).isoformat(timespec="seconds")
        is_overdue = not exempt and not recent
        overdue += int(is_overdue)
        reopen_due += int(bool(ret and ret["reopen_due"]))
        failure = ((s or {}).get("failure_reason") if (s or {}).get("failure_reason")
                   is not None else ((s or {}).get("last_error") or v.get("blocker") or ""))
        if not failure and attempts == 0:
            failure = "never attempted: no pass has reached this ground yet"
        b = by_region.setdefault(region or "?", dict.fromkeys((*STATES, "overdue_24h"), 0))
        b[state] += 1
        b["overdue_24h"] += int(is_overdue)
        rows[name] = {
            "state": state, "region": region, "language": lang,
            "route": g.get("route"), "weight": g.get("weight"),
            "attempts": attempts, "last_attempt": last_attempt or "",
            "last_yield": last_yield or "", "failure_reason": failure,
            "outcome": v.get("outcome") or "NAMED_ONLY",
            "successes": int((s or {}).get("successes") or 0) if s is not None else (
                0 if attempts == 0 else UNMEASURED),
            "delta_cursor": ({k: s.get(k) for k in ("last_delta", "last_new_content_at",
                                                     "empty_delta_streak") if k in s}
                             if s is not None else UNMEASURED),
            "overdue_24h": is_overdue,
            **({"blocked_retry_at": blocked_until} if blocked_until else {}),
            **({"retirement": ret} if ret is not None else {}),
        }
    registered = set(rows)
    orphans = sorted(set(fr) - registered)
    named = len(rows)
    summary = {
        "named": named,
        "never_attempted": counts["NEVER_ATTEMPTED"],
        "attempted_ever": named - counts["NEVER_ATTEMPTED"],
        "attempted_24h": attempted_24h,
        "overdue_24h": overdue,
        "yielded": counts["YIELDED"],
        "retired": counts[LOW_EV_RETIRED],
        "retired_reopen_due": reopen_due,
        "by_state": counts,
        "frontier_vectors_not_registered": len(orphans),
        "registered_not_in_frontier": len(registered - set(fr)),
    }
    return {"generated_utc": now.isoformat(timespec="seconds"), "status": "MEASURED",
            "summary": summary, "by_region": by_region, "grounds": rows,
            "orphan_frontier_vectors": orphans[:50], "unmeasured": gaps,
            "policy": {"daily_h": DAILY_H, "blocked_retry_d": BLOCKED_RETRY_D,
                       "retire_min_attempts": RETIRE_MIN_ATTEMPTS,
                       "retire_min_span_d": RETIRE_MIN_SPAN_D, "reopen_after_d": REOPEN_AFTER_D,
                       "reopen_condition": REOPEN_CONDITION,
                       "schedule": ("NAMED_ONLY -> retry-due BLOCKED -> cooldown-due covered -> "
                                    "any ground not attempted in 24h (the daily floor) -> "
                                    "attempted in 24h or BLOCKED inside its "
                                    f"{BLOCKED_RETRY_D:g}-day retry window (not overdue) -> "
                                    "LOW_EV_RETIRED not reopen-due; "
                                    "least-recently-attempted first inside each")},
            "sources": {"grounds": str(sources), "frontier": str(frontier),
                        "stats": str(stats)}}


# --------------------------------------------------------------------------- history + fence
def history(path: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = (path or HISTORY).read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines[-MAX_HISTORY:]:
        with contextlib.suppress(ValueError):
            row = json.loads(ln)
            if isinstance(row, dict):
                out.append(row)
    return out


#: The window over which never-attempted must fall, and the youngest reading that may anchor it.
FALL_WINDOW_H = 24.0
FALL_MIN_AGE_H = 20.0
#: The daily floor's own window: overdue grounds must fall over this long, or be zero.
OVERDUE_WINDOW_H = 48.0
OVERDUE_MIN_AGE_H = 40.0
#: The miner's counters older than this, while grounds are still never-attempted: the miner is
#: not running, and the fence says so rather than judging a frozen file.
STATS_SILENT_H = 6.0


def _anchor(hist: list[dict[str, Any]], now: datetime, window_h: float, min_age_h: float,
            key: str) -> dict[str, Any] | None:
    """The reading closest to `window_h` ago that is at least `min_age_h` old."""
    best: dict[str, Any] | None = None
    best_gap = None
    for h in hist:
        at = _ts(h.get("at"))
        val = (h.get("summary") or {}).get(key)
        if at is None or not isinstance(val, int):
            continue
        age_h = (now - at).total_seconds() / 3600.0
        if age_h < min_age_h:
            continue
        gap = abs(age_h - window_h)
        if best_gap is None or gap < best_gap:
            best, best_gap = h, gap
    return best


def judge(doc: dict[str, Any], hist: list[dict[str, Any]], now: datetime,
          stats_updated: Any = None) -> dict[str, Any]:
    """GREEN / RED / UNMEASURED. Red when never-attempted is positive and did not fall over the
    last day, when the overdue count is positive and did not fall over two days, or when the
    miner's counters have gone silent while grounds are still unattempted."""
    s = doc.get("summary") or {}
    never, overdue = s.get("never_attempted"), s.get("overdue_24h")
    if not isinstance(never, int) or not isinstance(overdue, int):
        return {"status": UNMEASURED, "exit": 0, "reasons": [],
                "why": doc.get("why") or "the counts could not be derived on this host"}
    reasons: list[str] = []
    notes: list[str] = []
    upd = _ts(stats_updated)
    if never > 0:
        if upd is None:
            notes.append("the miner's vector stats carry no update stamp here: its liveness is "
                         "UNMEASURED")
        elif (now - upd).total_seconds() / 3600.0 > STATS_SILENT_H:
            reasons.append(f"MINER SILENT: {never} ground(s) never attempted and the per-ground "
                           f"counters were last written {upd.isoformat(timespec='seconds')} "
                           f"(> {STATS_SILENT_H:g}h ago)")
        a = _anchor(hist, now, FALL_WINDOW_H, FALL_MIN_AGE_H, "never_attempted")
        if a is None:
            notes.append(f"never-attempted {never}: no reading >= {FALL_MIN_AGE_H:g}h old yet, "
                         "so its direction is UNMEASURED (not falling is not yet provable)")
        elif never >= int(a["summary"]["never_attempted"]):
            reasons.append(f"NEVER-ATTEMPTED DID NOT FALL: {a['summary']['never_attempted']} at "
                           f"{a.get('at')} -> {never} now")
    if overdue > 0:
        a = _anchor(hist, now, OVERDUE_WINDOW_H, OVERDUE_MIN_AGE_H, "overdue_24h")
        if a is None:
            notes.append(f"overdue {overdue}: no reading >= {OVERDUE_MIN_AGE_H:g}h old yet")
        elif overdue >= int(a["summary"]["overdue_24h"]):
            reasons.append(f"DAILY FLOOR NOT CLOSING: {a['summary']['overdue_24h']} ground(s) "
                           f"overdue at {a.get('at')} -> {overdue} now (target 0: every live "
                           "ground attempted at least once a day)")
    # GREEN ONLY ON EVIDENCE: nothing left to attempt, or both counts measured as falling. A
    # direction that cannot be judged yet is UNMEASURED, which is a verdict and not a pass.
    status = "RED" if reasons else ("UNMEASURED" if notes else "GREEN")
    return {"status": status, "exit": 1 if reasons else 0, "reasons": reasons, "notes": notes,
            "why": "; ".join(reasons) if reasons else (
                f"never-attempted {never}, overdue {overdue}"
                + (f" ({'; '.join(notes)})" if notes else ""))}


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:            # Windows: a reader holds the file; retry, then write
            time.sleep(0.2 * (i + 1))
    try:
        path.write_text(text, "utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def publish(*, out: Path | None = None, history_path: Path | None = None,
            now: datetime | None = None, write: bool = True, **paths: Any) -> dict[str, Any]:
    """Build, judge against the history, write the artifact, append the history line."""
    now = now or datetime.now(tz=UTC)
    doc = build(now=now, **{k: Path(v) for k, v in paths.items() if v is not None})
    hpath = history_path or HISTORY
    hist = history(hpath)
    st_doc = _json(Path(paths.get("stats") or VECTOR_STATS))
    verdict = judge(doc, hist, now,
                    stats_updated=(st_doc or {}).get("updated") if isinstance(st_doc, dict)
                    else None)
    doc["fence"] = verdict
    if write:
        _atomic(out or ARTIFACT, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
        if doc.get("status") == "MEASURED":
            line = json.dumps({"at": doc["generated_utc"], "summary": {
                k: v for k, v in doc["summary"].items() if not isinstance(v, dict)},
                "fence": verdict["status"]}, ensure_ascii=False)
            hpath.parent.mkdir(parents=True, exist_ok=True)
            keep = [json.dumps(h, ensure_ascii=False) for h in hist[-(MAX_HISTORY - 1):]]
            if len(hist) >= MAX_HISTORY:
                _atomic(hpath, "\n".join([*keep, line]) + "\n")
            else:
                with hpath.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
    return doc
