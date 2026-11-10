"""ONE ROBOTS GATE FOR EVERY FETCHER: read robots.txt, stop when it says no, and count the cost.

THE RULE (Governance rulings of 2026-11-10, journalled in PR #819; RFC 9309, stricter on 401/403):

  robots.txt answer                           label               the fetch
  ------------------------------------------  ------------------  -----------------------------
  read, no rule covers the path               PUBLIC              made
  404, 410 or any other 4xx but those below   ROBOTS_ABSENT       made, and COUNTED
  read, a Disallow covers the exact path      DISALLOWED          STOPPED
  401, 403, 429 or 451 on robots.txt itself   ROBOTS_REFUSED      STOPPED (a refusal or a rate
                                                                  limit aimed at us; never
                                                                  worked around)
  5xx, timeout, DNS, TLS, not http(s)         ROBOTS_UNREACHABLE  STOPPED this pass; the next
                                                                  scheduled pass asks again --
                                                                  never a retry loop

A PUBLISHER'S PERMIT REOPENS A REFUSAL, AND ONLY A REFUSAL (Governance ruling 2026-11-10 20:24Z).
A source whose robots.txt answers 401/403 (never 429 or 451) and whose
`research/robots_permits.json` row quotes the publisher's own clause permitting machine reading
is PERMITTED: fetched on the documented endpoint with the honest agent and its own key, counted
as PERMIT_FETCHED. If the data endpoint itself answers 401/403/429/451, that pass stops as
ROBOTS_REFUSED (`data_refused`), with no retry.

The rule matching itself (`*`, `$`, longest match wins, Allow wins a tie, our agent's group else
`*`) and the status table above (`classify_robots_status`) are `libs/data/robots_gate.py`, the
desk's one reader; this module adds the desk's labels for fetchers and the bill. Every caller
stops on `stops(label)` and on nothing else.

IT IS A BRAKE, SO IT IS BILLED (GROWTH_GOVERNANCE Rule 1). Every stopped fetch is:
  * returned to the caller as a SET_ASIDE row -- the label, the reason and the named events that
    reopen it -- so a source is never lost silently;
  * appended to `data/robots_set_aside.jsonl`, one line per stopped fetch;
  * summed per day, per label and per organ in `reports/ROBOTS_SET_ASIDE.json`, which also
    carries the two-sided missed-growth line `missed_growth.run` picks up. Neither side is
    priced in E[log W] yet: both say UNMEASURED, never zero. The COUNT is measured.
A ROBOTS_ABSENT fetch is counted beside the refusals (`absent_fetched`), never among them.

WHAT THIS IS NOT. It is not a terms veto: licence and terms notes still route redistribution and
never stop mining. Logins, paywalls and hard statuses on the DATA URL are refused where they
always were. This module answers one question -- may our agent read this exact path, by the
site's robots.txt -- and writes down every time the answer was no.

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
ROBOTS_ABSENT = "ROBOTS_ABSENT"
DISALLOWED = "DISALLOWED"
ROBOTS_REFUSED = "ROBOTS_REFUSED"
ROBOTS_UNREACHABLE = "ROBOTS_UNREACHABLE"
#: A ROBOTS_REFUSED source reopened by a publisher's documented permit (robots_permits.json).
PERMITTED = "PERMITTED"
#: The labels that stop a fetch. Every caller asks `stops(label)`; none keeps its own list.
STOP_LABELS = frozenset({DISALLOWED, ROBOTS_REFUSED, ROBOTS_UNREACHABLE})
#: Ledger statuses. SET_ASIDE = the fetch was NOT made. ABSENT_FETCHED = the site serves no
#: robots.txt and the fetch was made; counted beside the refusals, never among them.
SET_ASIDE = "SET_ASIDE"
ABSENT_FETCHED = "ABSENT_FETCHED"
PERMIT_FETCHED = "PERMIT_FETCHED"
#: Statuses on the DATA endpoint that end a permitted fetch for the pass (Governance condition 4):
#: the permit covers a refusal of robots.txt, never a refusal of the data itself.
DATA_REFUSAL = frozenset({401, 403, 429, 451})
PERMITS = Path(__file__).resolve().with_name("robots_permits.json")
#: The robots.txt statuses a permit may reopen. Never 429 (a rate limit) or 451 (a legal bar).
PERMIT_REOPENS = frozenset({401, 403})
#: Every field a permit row must fill before it counts.
PERMIT_FIELDS = ("host", "doc_url", "clause", "licence", "endpoint_doc", "key", "rate_limit",
                 "recorded_at")
RAIL = "robots_gate.set_aside"
#: Days of per-day counts kept on the report. The ledger itself is never trimmed.
REPORT_DAYS = 30

REOPEN = ("the next scheduled pass re-reads robots.txt and fetches as soon as it is readable and "
          "allows this path (or the site serves none); or a documented API or licence that "
          "permits machine reading is recorded on the source's registry row")

Opener = Callable[[str, str, float], str]
#: Collectors refuse from worker threads; one writer at a time keeps the report's tmp file whole.
_LOCK = threading.Lock()


def _open(url: str, agent: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return str(r.read(500_000).decode("utf-8", errors="replace"))


def stops(label: str) -> bool:
    """True when this label stops the fetch. The one test every caller makes."""
    return label in STOP_LABELS


def permit_for(source: str, url: str, path: Path | None = None) -> dict[str, Any] | None:
    """The ACTIVE machine_read_permit for this source (or its parent, for a derived
    `<id>__ep<hash>` source) whose host is this URL's host, else None. A permit that is
    inactive, incomplete or for another host is no permit: the source stays stopped."""
    try:
        rows = json.loads((path or PERMITS).read_text("utf-8")).get("permits") or {}
    except (OSError, ValueError, AttributeError):
        return None
    row = rows.get(source) or rows.get(str(source).split("__ep", 1)[0])
    if not isinstance(row, dict) or row.get("active") is not True:
        return None
    if not all(str(row.get(k) or "").strip() for k in PERMIT_FIELDS):
        return None
    if urllib.parse.urlsplit(url).netloc.lower() != str(row["host"]).lower():
        return None
    return row


def read(url: str, agent: str, *, opener: Opener | None = None, timeout: float = 12.0,
         cache: dict[tuple[str, str], Any] | None = None,
         source: str | None = None) -> tuple[str, str]:
    """(label, why) for this exact URL and this agent; see the table in the module docstring.

    `source` names the registry source. When robots.txt REFUSES (401/403/429/451) and that
    source holds an active `machine_read_permit` for this host, the label is PERMITTED: the
    publisher's own written terms reopen it (Governance ruling 2026-11-10 20:24Z). A permit
    never reopens DISALLOWED or ROBOTS_UNREACHABLE.

    `cache` (a dict the caller owns for ONE pass) holds each host's parsed rules, or the label
    it earned instead, so a pass asks a host once however many of its paths it wants. An
    unreachable host is therefore asked once a pass and stopped for the rest of it: the retry
    is the next scheduled pass, never a loop.
    """
    from libs.data.robots_gate import classify_robots_status, robots_allows, robots_rules
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ROBOTS_UNREACHABLE, "not an http(s) URL: no robots.txt can be read"
    root = f"{parts.scheme}://{parts.netloc}"
    key = (root, agent)
    held = cache.get(key) if cache is not None else None
    if held is None:
        try:
            text = (opener or _open)(f"{root}/robots.txt", agent, timeout)
        except urllib.error.HTTPError as exc:
            code = int(getattr(exc, "code", 0) or 0)
            kind = classify_robots_status(code)          # the desk's one meaning, libs/data
            if kind == ROBOTS_REFUSED:
                held = (ROBOTS_REFUSED, f"robots.txt answers HTTP {code}: a refusal aimed at "
                                        f"our agent, not fetched and never worked around", code)
            elif kind == ROBOTS_ABSENT:
                held = (ROBOTS_ABSENT, f"no robots.txt (HTTP {code}): no rules, fetched", code)
            else:
                held = (ROBOTS_UNREACHABLE, f"robots.txt unreadable (HTTP {code}): not "
                                            f"fetched this pass, asked again next pass", code)
        except Exception as exc:
            held = (ROBOTS_UNREACHABLE, f"robots.txt unreadable ({type(exc).__name__}): not "
                                        f"fetched this pass, asked again next pass", None)
        else:
            held = robots_rules(text, agent)
        if cache is not None:
            cache[key] = held
    if isinstance(held, tuple):
        # A permit reopens a 401/403 ONLY. A 429 is the host rate-limiting us and a 451 is a
        # legal refusal: fetching through either is never a permit's to allow (Auditor, 20:29Z).
        if held[0] == ROBOTS_REFUSED and held[2] in PERMIT_REOPENS and source:
            permit = permit_for(source, url)
            if permit is not None:
                return PERMITTED, (f"{held[1]}; reopened by the publisher's terms "
                                   f"({permit['doc_url']}): fetched on the documented endpoint, "
                                   f"counted as {PERMIT_FETCHED}")
        return str(held[0]), str(held[1])
    if robots_allows(held, url):
        return PUBLIC, "robots.txt allows this path for our agent"
    return DISALLOWED, "robots.txt disallows this exact path for our agent: not fetched"


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
    `absent_fetched` -- fetches made because the site serves no robots.txt. Torn lines are
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
                                  "sources": set(), "absent_fetched": 0,
                                  "absent_by_organ": Counter(), "permit_fetched": 0,
                                  "permit_by_source": Counter()})
        if str(row.get("status") or SET_ASIDE) == PERMIT_FETCHED:
            d["permit_fetched"] += 1
            d["permit_by_source"][str(row.get("source"))] += 1
            continue
        if str(row.get("status") or SET_ASIDE) == ABSENT_FETCHED:
            d["absent_fetched"] += 1
            d["absent_by_organ"][str(row.get("organ"))] += 1
            continue
        d["total"] += 1
        d["by_label"][str(row.get("access_label"))] += 1
        d["by_organ"][str(row.get("organ"))] += 1
        d["sources"].add(str(row.get("source")))
    out = {day: {"total": d["total"], "by_label": dict(d["by_label"]),
                 "by_organ": dict(d["by_organ"]), "distinct_sources": len(d["sources"]),
                 "absent_fetched": d["absent_fetched"],
                 "absent_fetched_by_organ": dict(d["absent_by_organ"]),
                 "permit_fetched": d["permit_fetched"],
                 "permit_fetched_by_source": dict(d["permit_by_source"])}
           for day, d in sorted(days.items())}
    return {"status": "OK", "days": out, "torn_lines": torn}


def publish(ledger: Path | None = None, report: Path | None = None) -> dict[str, Any]:
    """Rewrite the report from the ledger: the daily count and today's two-sided line."""
    counts = daily_counts(ledger)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    days = counts.get("days") or {}
    today = days.get(now[:10])
    doc = {"generated_utc": now, "rule": ("a Disallow on the exact path, a 401/403 on robots.txt "
                                          "or an unreachable robots.txt stops that fetch; a "
                                          "missing robots.txt (other 4xx) is fetched (PR #819)"),
           "status": counts["status"], "torn_lines": counts.get("torn_lines", 0),
           "refused_today": int(today["total"]) if today else 0,
           "absent_fetched_today": int(today["absent_fetched"]) if today else 0,
           "permit_fetched_today": int(today["permit_fetched"]) if today else 0,
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


def note_absent(organ: str, source: str, url: str, why: str, *,
                ledger: Path | None = None, report: Path | None = None) -> bool:
    """Count a fetch that WAS made because the site serves no robots.txt. Not a refusal and
    never billed as one: it says how often the desk reads a site that states no rules."""
    return record({"organ": organ, "source": source, "url": url, "status": ABSENT_FETCHED,
                   "access_label": ROBOTS_ABSENT, "why": why}, ledger=ledger, report=report)


def note_permit(organ: str, source: str, url: str, why: str, *,
                ledger: Path | None = None, report: Path | None = None) -> bool:
    """Count a fetch made on a machine_read_permit. Beside the refusals, never among them."""
    return record({"organ": organ, "source": source, "url": url, "status": PERMIT_FETCHED,
                   "access_label": PERMITTED, "why": why}, ledger=ledger, report=report)


def data_refused(organ: str, source: str, url: str, code: int, *,
                 ledger: Path | None = None, report: Path | None = None) -> dict[str, Any]:
    """A permitted source whose DATA endpoint refused or rate-limited: the pass falls back to
    ROBOTS_REFUSED, billed, with no retry (Governance condition 4)."""
    return refuse(organ, source, url, ROBOTS_REFUSED,
                  f"the data endpoint answered HTTP {code} on a permitted fetch: the permit "
                  f"covers a refusal of robots.txt only, so this pass stops (no retry)",
                  ledger=ledger, report=report)


def main() -> int:
    doc = publish()
    print(f"robots gate: {doc['refused_today']} fetch(es) refused today, "
          f"{doc['absent_fetched_today']} fetched with no robots.txt ({doc['status']})")
    for day, d in list((doc.get("daily") or {}).items())[-7:]:
        print(f"  {day}  refused={d['total']}  {d['by_label']}  {d['by_organ']}  "
              f"absent_fetched={d['absent_fetched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
