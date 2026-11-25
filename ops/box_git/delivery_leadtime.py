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
UNMEASURED_STAGES = {"gateway_restart": "no box artifact stamps a gateway restart per release yet",
                     "first_use": "no box artifact stamps the first use of a change yet"}
CLEARERS = frozenset({"auditor", "quant-admin"})
BOX_CI_USER = "box-ci"
_CLEAR = re.compile(r"^AUDIT CLEAR ([0-9a-f]{40})\b", re.M)
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
            "stages": {k: _iso(st[k]) for k in STAGES}}


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


def summary(rows: Sequence[Mapping[str, Any]], full_results: Sequence[Mapping[str, Any]],
            now: datetime) -> dict[str, Any]:
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
    }


def build(prs: Sequence[Mapping[str, Any]], comments: Mapping[int, Sequence[Mapping[str, Any]]],
          statuses: Mapping[str, Sequence[Mapping[str, Any]]], *,
          full_results: Sequence[Mapping[str, Any]],
          production: Sequence[tuple[datetime, str]],
          adopted: Sequence[tuple[datetime, str]] | None,
          is_ancestor: IsAncestor, now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(UTC)
    greens = [(at, str(f.get("head"))) for f in full_results
              if f.get("kind") == "full" and f.get("ok") is True and (at := _ts(f.get("at")))]
    rows = [row(p, comments.get(int(p.get("number") or 0), ()),
                statuses.get(str((p.get("head") or {}).get("sha") or ""), ()),
                greens, production, adopted or (), is_ancestor)
            for p in sorted(prs, key=lambda p: int(p.get("number") or 0))]
    doc = {"schema": SCHEMA, "at": _iso(t), "stages": list(STAGES),
           "summary": summary(rows, full_results, t), "changes": rows}
    if adopted is None:
        doc["summary"]["unmeasured_stages"] = {
            "adopted": "no adoption record was given to this pass", **UNMEASURED_STAGES}
    return doc
