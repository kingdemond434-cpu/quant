"""DELIVERY LEAD TIME: how long an Audit-CLEARed change takes to reach the box, by stage.

WHY (zuck 2026-11-25 17:33Z, PERMANENT; cio/LOOP_COVERAGE.md L16): delivery is maximised by a
standing loop, not fixed once. On 11-25, 75 forge PRs were open, 67 of them Audit CLEAR, and none
had ever merged. Nothing measured where the time went, so nothing could cut it. Lead time has no
good-enough level: each week's p90 is the bar to beat.

WHAT IT MEASURES, every loop pass, READ ONLY (forge GETs, git ancestry, the loop's own state):
  For each forge PR into LIVE, one row with a timestamp per stage:
    clear       the first AUDIT CLEAR <exact head> from the auditor or the owner
    forge_pr    the PR's creation (the packet reached the forge from the drop/inbox)
    ci_start    the first box-ci status on the head
    ci_end      the last finished box-ci status, with failure causes (env vs code)
    live        the merge into LIVE
    full_green  the first GREEN full run whose head contains the merge
    production  the first production commit that contains the merge
    adopted     the box running a release that contains it (release_identity.json, when given)
  Stages after `adopted` (gateway restart, first use) are named UNMEASURED, never guessed.

  Weekly (rolling 7 days): median and p90 lead time CLEAR -> production for the changes that got
  there, adoptions, green share of full runs, failed full runs by cause, the built-not-live
  backlog (count and age p50/p90), and THE STAGE HOLDING THE MOST LEAD TIME (open changes count
  their current stage up to now, so a stall shows as the bottleneck while it is stalling).

It changes nothing: no status, comment, merge, ref or file other than its own report.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

SCHEMA = "delivery_leadtime/1"
REPORT = "DELIVERY_LEADTIME.json"
WEEK = timedelta(days=7)
STAGES = ("clear", "forge_pr", "ci_start", "ci_end", "live", "full_green", "production",
          "adopted")
#: STUCK (zuck 11-26 15:47Z: memecoin #53 sat CLEAR with no box CI for ~40 h, unseen). An
#: open CLEAR change with no box-ci status, or not live, past these limits is listed in
#: summary.stuck on every pass.
STUCK_NO_CI_H = 2.0
STUCK_NOT_LIVE_H = 6.0
UNMEASURED_STAGES = {"gateway_restart": "no box artifact stamps a gateway restart per release yet",
                     "first_use": "no box artifact stamps the first use of a change yet"}
CLEARERS = frozenset({"auditor", "quant-admin"})
BOX_CI_USER = "box-ci"
_CLEAR = re.compile(r"^AUDIT CLEAR ([0-9a-f]{40})\b", re.M)
#: The pr stage's own verdict reading (box_loop._VERDICT over forge_api._comment): the LAST
#: verdict line on the PR decides, a HOLD from any account counts, a CLEAR only from a clearer.
_VERDICT = re.compile(r"^AUDIT (CLEAR|HOLD) ([0-9a-f]{40})(?: (merge|squash))?[ \t]*$", re.M)
#: Failure causes, first match wins. "env" mirrors box_loop._ENV_RED (a box defect, not the code).
CAUSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("env", re.compile(r"exit status 128|\+\+\+ Timeout \+\+\+|did not answer in time"
                       r"|Could not determine home directory|PermissionError", re.I)),
    ("law_gate", re.compile(r"law gate rc=(?!0\b)\d+", re.I)),
    ("timeout", re.compile(r"rc=124|timed? ?out", re.I)),
    ("collection", re.compile(r"error(s)? during collection|collection error", re.I)),
    ("tests", re.compile(r"\d+ failed|FAILED|failure", re.I)),
)

IsAncestor = Callable[[str, str], bool]


def _ts(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    try:
        t = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(t: datetime | None) -> str | None:
    return t.astimezone(UTC).isoformat(timespec="seconds") if t else None


def cause(text: str) -> str:
    for name, rx in CAUSES:
        if rx.search(text or ""):
            return name
    return "other"


def clear_at(comments: Iterable[Mapping[str, Any]], head: str) -> datetime | None:
    """The first CLEAR at the EXACT head from an account whose CLEAR counts (forge_api MF-1)."""
    out: datetime | None = None
    for c in comments:
        login = str((c.get("user") or {}).get("login") or "")
        if login not in CLEARERS:
            continue
        if head in _CLEAR.findall(str(c.get("body") or "")):
            t = _ts(c.get("created_at"))
            if t and (out is None or t < out):
                out = t
    return out


def ci_span(statuses: Iterable[Mapping[str, Any]]) -> tuple[datetime | None, datetime | None,
                                                            list[str]]:
    """First box-ci status, last finished one, and the causes of every failure."""
    rows = [s for s in statuses if str((s.get("creator") or {}).get("login") or "") == BOX_CI_USER]
    times = [t for s in rows if (t := _ts(s.get("created_at")))]
    done = [s for s in rows if str(s.get("status") or s.get("state") or "") != "pending"]
    ends = [t for s in done if (t := _ts(s.get("updated_at") or s.get("created_at")))]
    causes = sorted({cause(str(s.get("description") or "")) for s in done
                     if str(s.get("status") or s.get("state") or "") in ("failure", "error")})
    return (min(times) if times else None, max(ends) if ends else None, causes)


def first_containing(sha: str | None, rows: Sequence[tuple[datetime, str]],
                     is_ancestor: IsAncestor) -> datetime | None:
    """The earliest (time, head) whose head contains `sha`; rows need not be sorted."""
    if not sha:
        return None
    for t, h in sorted(rows):
        if h == sha or is_ancestor(sha, h):
            return t
    return None


def pr_view(comments: Sequence[Mapping[str, Any]], head: str) -> dict[str, Any]:
    """What the pr stage sees on this PR (11-26: CLEAR PRs #53/#147/#148 never got a box-ci
    status while later PRs did). Read only; mirrors box_loop.audited_clear exactly (tested)."""
    last: tuple[str, str, str, str | None] | None = None
    n = 0
    for c in comments:
        login = str((c.get("user") or {}).get("login") or "")
        for m in _VERDICT.finditer(str(c.get("body") or "")):
            if m.group(1) == "CLEAR" and login not in CLEARERS:
                continue  # forge_api._comment rewrites it to UNCOUNTED CLEAR
            n += 1
            last = (m.group(1), m.group(2), login, _iso(_ts(c.get("created_at"))))
    return {"verdict_lines": n,
            "last_verdict": None if last is None else
            {"kind": last[0], "sha": last[1][:12], "by": last[2], "at": last[3]},
            "clear_at_head": last is not None and last[:2] == ("CLEAR", head)}


def row(pr: Mapping[str, Any], comments: Sequence[Mapping[str, Any]],
        statuses: Sequence[Mapping[str, Any]], greens: Sequence[tuple[datetime, str]],
        production: Sequence[tuple[datetime, str]], adopted: Sequence[tuple[datetime, str]],
        is_ancestor: IsAncestor) -> dict[str, Any]:
    head = str((pr.get("head") or {}).get("sha") or "")
    merge = str(pr.get("merge_commit_sha") or "") or None
    live = _ts(pr.get("merged_at")) if pr.get("merged") or pr.get("merged_at") else None
    start, end, causes = ci_span(statuses)
    st: dict[str, datetime | None] = {
        "clear": clear_at(comments, head), "forge_pr": _ts(pr.get("created_at")),
        "ci_start": start, "ci_end": end, "live": live,
        "full_green": first_containing(merge, greens, is_ancestor) if live else None,
        "production": first_containing(merge, production, is_ancestor) if live else None,
        "adopted": first_containing(merge, adopted, is_ancestor) if live else None}
    return {"pr": pr.get("number"), "head": head, "title": str(pr.get("title") or "")[:120],
            "state": pr.get("state"), "ci_causes": causes,
            "stages": {k: _iso(st[k]) for k in STAGES},
            "pr_view": {**pr_view(comments, head), "box_ci_statuses": len(
                [s for s in statuses
                 if str((s.get("creator") or {}).get("login") or "") == BOX_CI_USER])}}


def _hours(a: datetime | None, b: datetime | None) -> float | None:
    return round((b - a).total_seconds() / 3600, 2) if a and b and b >= a else None


def _pct(xs: Sequence[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))], 2)


def bottleneck(rows: Sequence[Mapping[str, Any]], now: datetime) -> dict[str, float]:
    """Hours spent IN each stage (from reaching it to reaching the next), summed over changes.

    An open change counts its current stage up to now, so a stall is the bottleneck while it
    lasts. Hours are attributed to the stage being WAITED IN (e.g. 'live' = merged, waiting for
    a green full run)."""
    held: Counter[str] = Counter()
    for r in rows:
        st = {k: _ts(v) for k, v in (r.get("stages") or {}).items()}
        if not st.get("clear"):
            continue
        reached = [(k, st[k]) for k in STAGES if st.get(k)]
        reached.sort(key=lambda kv: kv[1])
        for (k, t), nxt in zip(reached, [*reached[1:], (None, None)], strict=True):
            end = nxt[1] if nxt[1] else (None if k == "adopted" else now)
            h = _hours(t, end)
            if h:
                held[k] += h
    return {k: round(v, 2) for k, v in held.most_common()}


def stuck(rows: Sequence[Mapping[str, Any]], now: datetime) -> dict[str, Any]:
    """Open CLEAR changes past their stage limit, oldest first. Read only: names them."""
    no_ci, not_live = [], []
    for r in rows:
        if r.get("state") not in (None, "open"):
            continue
        st = {k: _ts(v) for k, v in (r.get("stages") or {}).items()}
        c = st.get("clear")
        if not c or st.get("live"):
            continue
        age = _hours(c, now) or 0.0
        item = {"pr": r.get("pr"), "head": str(r.get("head") or "")[:12], "title": r.get("title"),
                "clear_age_h": age,
                "clear_at_head": (r.get("pr_view") or {}).get("clear_at_head")}
        if not st.get("ci_start") and age >= STUCK_NO_CI_H:
            no_ci.append(item)
        elif age >= STUCK_NOT_LIVE_H:
            not_live.append(item)
    key = lambda i: -i["clear_age_h"]  # noqa: E731
    return {"limits_h": {"no_ci": STUCK_NO_CI_H, "not_live": STUCK_NOT_LIVE_H},
            "no_ci": sorted(no_ci, key=key), "not_live": sorted(not_live, key=key),
            "n": len(no_ci) + len(not_live)}


#: (boot r20) PER-STAGE SLA (zuck 2026-11-27 01:18-01:21Z: every stage as fast as possible, 10
#: min a ceiling, not a target). Minutes a change may WAIT IN a stage (as bottleneck() counts
#: it) before it is a breach. The limits are what the r20 loop can hold today, not what is
#: wanted; each week's measured p90 is the bar. A breach is reported on every pass, never
#: hidden, and the CI zero-output alarm names a checker that has gone silent.
SLA_MIN: dict[str, float] = {
    "forge_pr": 10.0,     # the PR exists and is CLEAR: the first box check must start
    "clear": 10.0,
    "ci_start": 60.0,     # checks running: risk-invariants + replay-shadow must answer
    "ci_end": 10.0,       # checks green: the merge
    "live": 180.0,        # merged: the full suite on a head that contains it
    "full_green": 15.0,   # full green: seal and promote to production
    "production": 75.0,   # production: the box adopts it (MT5-AdoptRelease is hourly)
}
#: No box-ci status at all for this long while a CLEARed PR waits for its first check.
CI_SILENT_MIN = 30.0
#: (boot r21, direct live) no full run is waited for: a merged change is due in production
#: within minutes of landing on LIVE, and `full_green` is not a stage of its path.
DIRECT_SLA_MIN: dict[str, float] = {**SLA_MIN, "live": 10.0}


def sla(rows: Sequence[Mapping[str, Any]], now: datetime, *,
        direct: bool = False) -> dict[str, Any]:
    """Open changes past their current stage's SLA, and the CI zero-output alarm. Read only.
    A change held at 'ci_end' by a code red is the code's answer, not a breach of the loop."""
    breaches: dict[str, list[dict[str, Any]]] = {}
    last_ci: datetime | None = None
    waiting_first: list[Any] = []
    for r in rows:
        st = {k: _ts(v) for k, v in (r.get("stages") or {}).items()}
        for k in ("ci_start", "ci_end"):
            t = st.get(k)
            if t is not None and (last_ci is None or t > last_ci):
                last_ci = t
        if not st.get("clear") or st.get("adopted"):
            continue
        if r.get("state") not in (None, "open") and not st.get("live"):
            continue  # closed unmerged: nothing to deliver
        reached = sorted(((k, t) for k in STAGES if (t := st.get(k))
                          and not (direct and k == "full_green")), key=lambda kv: kv[1])
        stage, since = reached[-1]
        causes = [c for c in r.get("ci_causes") or [] if c != "env"]
        if stage == "ci_end" and causes:
            continue
        if stage in ("clear", "forge_pr"):
            waiting_first.append(r.get("pr"))
        mins = round((now - since).total_seconds() / 60, 1)
        limit = (DIRECT_SLA_MIN if direct else SLA_MIN).get(stage)
        if limit is not None and mins > limit:
            breaches.setdefault(stage, []).append({"pr": r.get("pr"), "waited_min": mins})
    alarms = []
    silent = round((now - last_ci).total_seconds() / 60, 1) if last_ci else None
    if waiting_first and (silent is None or silent > CI_SILENT_MIN):
        alarms.append({"alarm": "ci_zero_output", "silent_min": silent,
                       "waiting": len(waiting_first), "limit_min": CI_SILENT_MIN})
    out = {"targets_min": DIRECT_SLA_MIN if direct else SLA_MIN, "direct": direct,
           "ok": not breaches and not alarms, "alarms": alarms,
           "breaches": {k: {"n": len(v), "oldest_min": max(i["waited_min"] for i in v),
                            "prs": [i["pr"] for i in
                                    sorted(v, key=lambda i: -i["waited_min"])][:10]}
                        for k, v in breaches.items()}}
    return out


def summary(rows: Sequence[Mapping[str, Any]], full_results: Sequence[Mapping[str, Any]],
            now: datetime, *, direct: bool = False) -> dict[str, Any]:
    since = now - WEEK
    lead, adopt_n = [], 0
    backlog: list[float] = []
    for r in rows:
        st = {k: _ts(v) for k, v in (r.get("stages") or {}).items()}
        c = st.get("clear")
        if not c:
            continue
        done = st.get("production")
        if done and done >= since:
            lead.append(_hours(c, done) or 0.0)
        if st.get("adopted") and st["adopted"] >= since:
            adopt_n += 1
        if not done:
            backlog.append(_hours(c, now) or 0.0)
    week = [f for f in full_results if f.get("kind") == "full"
            and (t := _ts(f.get("at"))) and t >= since]
    greens = sum(1 for f in week if f.get("ok") is True)
    held = bottleneck(rows, now)
    return {
        "window_days": 7, "lead_time_h": {"n": len(lead),
                                          "median": round(statistics.median(lead), 2)
                                          if lead else None, "p90": _pct(lead, 0.9)},
        "bar_to_beat": "this week's p90 (no good-enough level)",
        "adoptions": adopt_n,
        "full_runs": {"n": len(week), "green": greens,
                      "green_share": round(greens / len(week), 3) if week else None,
                      "failed_by_cause": dict(Counter(cause(str(f.get("why") or ""))
                                                      for f in week if f.get("ok") is not True))},
        "built_not_live": {"n": len(backlog), "age_h_p50": _pct(backlog, 0.5),
                           "age_h_p90": _pct(backlog, 0.9),
                           "oldest_h": round(max(backlog), 2) if backlog else None},
        "hours_held_by_stage": held,
        "bottleneck": next(iter(held), None),
        "unmeasured_stages": UNMEASURED_STAGES,
        "stuck": stuck(rows, now),
        "sla": sla(rows, now, direct=direct),
    }


def build(prs: Sequence[Mapping[str, Any]], comments: Mapping[int, Sequence[Mapping[str, Any]]],
          statuses: Mapping[str, Sequence[Mapping[str, Any]]], *,
          full_results: Sequence[Mapping[str, Any]],
          production: Sequence[tuple[datetime, str]],
          adopted: Sequence[tuple[datetime, str]] | None,
          is_ancestor: IsAncestor, now: datetime | None = None,
          direct: bool = False) -> dict[str, Any]:
    t = now or datetime.now(UTC)
    greens = [(at, str(f.get("head"))) for f in full_results
              if f.get("kind") == "full" and f.get("ok") is True and (at := _ts(f.get("at")))]
    rows = [row(p, comments.get(int(p.get("number") or 0), ()),
                statuses.get(str((p.get("head") or {}).get("sha") or ""), ()),
                greens, production, adopted or (), is_ancestor)
            for p in sorted(prs, key=lambda p: int(p.get("number") or 0))]
    doc = {"schema": SCHEMA, "at": _iso(t), "stages": list(STAGES),
           "summary": summary(rows, full_results, t, direct=direct), "changes": rows}
    if adopted is None:
        doc["summary"]["unmeasured_stages"] = {
            "adopted": "no adoption record was given to this pass", **UNMEASURED_STAGES}
    return doc
