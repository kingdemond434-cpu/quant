"""ONE ROBOTS GATE FOR EVERY FETCHER: read robots.txt, stop on a Disallow, and count what it cost.

THE RULE (ruling of 2026-11-10, journalled in PR #819). A robots.txt Disallow covering the exact
path a fetcher is about to request STOPS THAT FETCH. A site that publishes no robots.txt (404
and the other 4xx) has disallowed nothing and is fetched as before.

AN UNREADABLE robots.txt (a 5xx, a timeout, DNS, TLS) IS THE CALLER'S DECISION, AND IT IS COUNTED
EITHER WAY. The ruling names a Disallow only. The running collectors (`asia_collector`,
`data_acquisition_scientist`) therefore keep fetching on ACCESS_UNCLEAR, exactly as they did
before, and call `note_unread` so the day's count shows how often that happened -- slow regional
hosts time out on robots.txt routinely, and stopping on it would be a new brake of unmeasured
size. `shadow_institutional.Guard`, where no sensor consults robots today, refuses on it.

IT IS A BRAKE, SO IT IS BILLED (GROWTH_GOVERNANCE Rule 1). Every refusal is:
  * returned to the caller as a SET_ASIDE row -- the label, the reason and the named events that
    reopen it -- so a source is never lost silently the way `BLOCKED_BY_ROBOTS` once lost them;
  * appended to `data/robots_set_aside.jsonl`, one line per refused fetch;
  * summed per day and per organ in `reports/ROBOTS_SET_ASIDE.json`, which also carries the
    two-sided missed-growth line `missed_growth.run` picks up. Neither side is priced in
    E[log W] yet: both say UNMEASURED, never zero. The COUNT is measured.

WHAT THIS IS NOT. It is not a terms veto: licence and terms notes still route redistribution and
never stop mining. It is not a new access boundary either: logins, paywalls and hard statuses
are refused where they always were. This module only answers "does the site's robots.txt let
our agent read this exact path", and writes down every time the answer was no.

    python -m research.robots_gate            # print today's count from the ledger
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LEDGER = DESK / "data" / "robots_set_aside.jsonl"
REPORT = DESK / "reports" / "ROBOTS_SET_ASIDE.json"

PUBLIC = "PUBLIC"
DISALLOWED = "DISALLOWED"
ACCESS_UNCLEAR = "ACCESS_UNCLEAR"
#: Ledger statuses. SET_ASIDE = the fetch was NOT made. UNREAD_FETCHED = robots.txt could not be
#: read and the caller fetched anyway; counted beside the refusals, never among them.
SET_ASIDE = "SET_ASIDE"
UNREAD_FETCHED = "UNREAD_FETCHED"
RAIL = "robots_gate.set_aside"
#: Days of per-day counts kept on the report. The ledger itself is never trimmed.
REPORT_DAYS = 30

REOPEN = ("the next pass re-reads robots.txt and fetches as soon as it allows this path (or the "
          "site serves none); or a permitting clause from the publisher's terms is recorded on "
          "the source's registry row")

Opener = Callable[[str, str, float], str]
#: Collectors refuse from worker threads; one writer at a time keeps the report's tmp file whole.
_LOCK = threading.Lock()


def _open(url: str, agent: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return str(r.read(500_000).decode("utf-8", errors="replace"))


def read(url: str, agent: str, *, opener: Opener | None = None, timeout: float = 12.0,
         cache: dict[tuple[str, str], Any] | None = None) -> tuple[str, str]:
    """(label, why) for this exact URL and this agent.

    `cache` (a dict the caller owns for ONE pass) holds each host's parsed robots.txt, or the
    reason it could not be read, so a pass asks a host once however many of its paths it wants.

    PUBLIC          robots.txt allows the path, or the site serves none (a 4xx other than
                    401/403).
    DISALLOWED      robots.txt was READ and disallows this exact path for our agent. Nothing
                    else is a Disallow.
    ACCESS_UNCLEAR  the file could not be read: a 5xx, a timeout, DNS, TLS, a non-http URL --
                    and a 401/403 on robots.txt itself. A REFUSAL TO SERVE THE FILE IS NOT A
                    RULE IN THE FILE (measured on the box 2026-11-10: 9 of 13 non-allowing
                    Asia sources were a 403 on /robots.txt, among them keyed public APIs the
                    desk holds a key for -- api.eia.gov, data.api.abs.gov.au -- where the 403
                    is the host's answer to an unkeyed request, not a crawl policy). The
                    standard library reads 401/403 as "everything disallowed"; RFC 9309 reads
                    every 4xx as "no policy". This gate takes neither side: it says the policy
                    is UNREAD and lets the caller's own rule for unread decide.

    `cache` (a dict the caller owns for ONE pass) holds each host's parsed robots.txt, or the
    reason it could not be read, so a pass asks a host once however many of its paths it wants.

    PUBLIC          robots.txt allows the path, or the site serves none (any 4xx but 401/403).
    DISALLOWED      robots.txt disallows the path; or the file itself answers 401/403, which the
                    standard library also reads as "everything disallowed".
    ACCESS_UNCLEAR  the file could not be read (5xx, timeout, DNS, TLS, a non-http URL).
    """
    from urllib.robotparser import RobotFileParser
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ACCESS_UNCLEAR, "not an http(s) URL: no robots.txt to read"
    root = f"{parts.scheme}://{parts.netloc}"
    key = (root, agent)
    held = cache.get(key) if cache is not None else None
    if held is None:
        try:
            text = (opener or _open)(f"{root}/robots.txt", agent, timeout)
        except urllib.error.HTTPError as exc:
            code = int(getattr(exc, "code", 0) or 0)
            if code in (401, 403) or not 400 <= code < 500:
                held = (ACCESS_UNCLEAR, f"robots.txt unreadable (HTTP {code})")
            else:
                held = (PUBLIC, f"no robots.txt (HTTP {code})")
        except Exception as exc:
            held = (ACCESS_UNCLEAR, f"robots.txt unreadable ({type(exc).__name__})")
        else:
            held = RobotFileParser()
            held.parse(text.splitlines())
        if cache is not None:
            cache[key] = held
    if isinstance(held, tuple):
        return held
    if held.can_fetch(agent, url):
        return PUBLIC, "robots.txt allows this path for our agent"
    return DISALLOWED, "robots.txt disallows this exact path for our agent"


def set_aside_row(organ: str, source: str, url: str, label: str, why: str) -> dict[str, Any]:
    """The row a caller returns or publishes for a fetch it did not make."""
    return {"organ": organ, "source": source, "url": url, "status": SET_ASIDE,
            "access_label": label, "why": why, "redistribute_allowed": False,
            "reopen": REOPEN, "missed_growth": missed_growth_pair(1, organ=organ)}


def missed_growth_pair(n: int, *, organ: str = "", at: str | None = None,
                       by_label: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """The two-sided line. `n` (fetches refused) is MEASURED; the E[log W] of each side is not."""
    stamp = at or datetime.now(tz=UTC).isoformat(timespec="seconds")
    base = {"at": stamp, "day": stamp[:10], "rail": RAIL, "kind": "opportunity_cost",
            "value": None, "verdict": "UNMEASURED", "e_log_w": "UNMEASURED",
            "fetches_refused": int(n), **({"organ": organ} if organ else {}),
            **({"by_label": dict(by_label)} if by_label else {})}
    return [
        {**base, "side": "cost", "units": "fetches not made on a robots verdict",
         "why": ("each refused fetch is a source that added no observation this pass; the "
                 "growth forgone is the forward E[log W] of the cells that source would have "
                 "fed, unpriced until a refused source has a judged neighbour to price it by")},
        {**base, "side": "gain", "units": "fetches not made against a publisher's robots.txt",
         "why": ("the desk builds no evidence on a path its publisher asked agents not to "
                 "read; the avoided cost (a block, a terms dispute) is unpriced")},
    ]


def _append(path: Path, line: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")


def _write_atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                      # a read-only destination is WinError 5
        os.chmod(path, 0o666)
        os.replace(tmp, path)


def daily_counts(ledger: Path | None = None) -> dict[str, Any]:
    """Per day: `total` fetches REFUSED (by label, by organ, distinct sources) and, beside it,
    `unread_fetched` -- fetches made although robots.txt could not be read. Torn lines are
    COUNTED as torn, never dropped silently."""
    path = ledger or LEDGER
    days: dict[str, dict[str, Any]] = {}
    torn = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"status": "UNMEASURED", "why": f"no {path.name}: no fetch has been refused, "
                                               "or the gate has not run on this host",
                "days": {}, "torn_lines": 0}
    for raw in lines:
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
            day = str(row["at"])[:10]
        except (ValueError, KeyError, TypeError):
            torn += 1
            continue
        d = days.setdefault(day, {"total": 0, "by_label": Counter(), "by_organ": Counter(),
                                  "sources": set(), "unread_fetched": 0,
                                  "unread_by_organ": Counter()})
        if str(row.get("status") or SET_ASIDE) == UNREAD_FETCHED:
            d["unread_fetched"] += 1
            d["unread_by_organ"][str(row.get("organ"))] += 1
            continue
        d["total"] += 1
        d["by_label"][str(row.get("access_label"))] += 1
        d["by_organ"][str(row.get("organ"))] += 1
        d["sources"].add(str(row.get("source")))
    out = {day: {"total": d["total"], "by_label": dict(d["by_label"]),
                 "by_organ": dict(d["by_organ"]), "distinct_sources": len(d["sources"]),
                 "unread_fetched": d["unread_fetched"],
                 "unread_fetched_by_organ": dict(d["unread_by_organ"])}
           for day, d in sorted(days.items())}
    return {"status": "OK", "days": out, "torn_lines": torn}


def publish(ledger: Path | None = None, report: Path | None = None) -> dict[str, Any]:
    """Rewrite the report from the ledger: the daily count and today's two-sided line."""
    counts = daily_counts(ledger)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    days = counts.get("days") or {}
    today = days.get(now[:10])
    doc = {"generated_utc": now, "rule": "a robots.txt Disallow on the exact path, or an "
                                         "unreadable robots.txt, stops that fetch (PR #819)",
           "status": counts["status"], "torn_lines": counts.get("torn_lines", 0),
           "refused_today": int(today["total"]) if today else 0,
           "unread_fetched_today": int(today["unread_fetched"]) if today else 0,
           "daily": dict(list(days.items())[-REPORT_DAYS:]), "reopen": REOPEN,
           # No line on a day nothing was refused: missed_growth reads NOT_BINDING.
           "missed_growth": (missed_growth_pair(today["total"], at=now,
                                                by_label=today["by_label"])
                             if today and today["total"] else [])}
    if counts["status"] != "OK":
        doc["why"] = counts.get("why")
    _write_atomic(report or REPORT, doc)
    return doc


def record(row: dict[str, Any], *, ledger: Path | None = None,
           report: Path | None = None) -> bool:
    """Append one refused fetch and refresh the report; True when the ledger line was written.
    Never raises: a full disk must not turn a refused fetch into a crashed collector. A False
    is carried on the caller's row (`billed`), so an unbilled refusal is visible, not silent."""
    line = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            **{k: row.get(k) for k in ("organ", "source", "url", "status", "access_label",
                                       "why")}}
    with _LOCK:
        try:
            _append(ledger or LEDGER, line)
        except OSError:
            return False
        # A failed report write loses nothing: the ledger holds the line and the next call,
        # or `python -m research.robots_gate`, republishes from it.
        with contextlib.suppress(OSError):
            publish(ledger, report)
    return True


def refuse(organ: str, source: str, url: str, label: str, why: str, *,
           ledger: Path | None = None, report: Path | None = None) -> dict[str, Any]:
    """Build the SET_ASIDE row AND bill it. The one call a fetcher makes when it does not fetch."""
    row = set_aside_row(organ, source, url, label, why)
    row["billed"] = record(row, ledger=ledger, report=report)
    return row


def note_unread(organ: str, source: str, url: str, why: str, *,
                ledger: Path | None = None, report: Path | None = None) -> bool:
    """Count a fetch that WAS made although robots.txt could not be read. Not a refusal and
    never billed as one: it is the measurement that says how large a stop-on-unreadable rule
    would be, should anyone propose it."""
    return record({"organ": organ, "source": source, "url": url, "status": UNREAD_FETCHED,
                   "access_label": ACCESS_UNCLEAR, "why": why}, ledger=ledger, report=report)


def main() -> int:
    doc = publish()
    print(f"robots gate: {doc['refused_today']} fetch(es) refused today, "
          f"{doc['unread_fetched_today']} fetched with robots.txt unread ({doc['status']})")
    for day, d in list((doc.get("daily") or {}).items())[-7:]:
        print(f"  {day}  refused={d['total']}  {d['by_label']}  {d['by_organ']}  "
              f"unread_fetched={d['unread_fetched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
