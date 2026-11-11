"""FEED SCHEMA WATCH -- our own feeds' fetch health and schema drift, with repair tickets.

THE FAILURE IT EXISTS FOR. A scraper rarely dies loudly. The site changes a class name or a JSON
key, the request still returns 200, the parser finds nothing, and the harvest reads "no chart
parsed" with zero transport failures: indistinguishable on every dashboard from a quiet day. The
lake has the sister case: a producer renames a column or changes its dtype, the file is still
fresh, and every cell that reads the old column goes silently UNMEASURED. `scripts/data_vitals.py`
scores key-set conformance on the legacy `data/*.jsonl` files on the VPS's daily cycle, and
`libs/data/pit_certificate.py` checks a certified dataset's schema hash. Neither watches the
MT5 desk's own live feeds, and neither says what to do next.

WHAT ONE PASS MEASURES

  lake schema     every `data/lake/series/*.parquet|csv`: column names and dtypes, row count and
                  whether it still carries `available_time`, against the baseline recorded the
                  first time the file was seen. COLUMN_REMOVED, DTYPE_CHANGED, STAMP_LOST and
                  ROWS_SHRANK (below half the baseline) are BREAKING; COLUMN_ADDED is noted and
                  the baseline extended.
  parser drift    every free-stack source in `data/free_stack/yield_runs.jsonl`: the newest live
                  run made requests, had NO transport failure, and parsed nothing (no obs, no
                  raw rows, no datasets) -- while an earlier live run of the same source did
                  yield. That is the shape of a page that changed under its parser. A transport
                  failure (timeout, DNS, TLS, proxy, HTTP status) is TRANSPORT, never drift.

WHAT IT DOES ABOUT IT. One REPAIR TICKET per drifting feed in `data/feed_schema_watch/tickets/`,
first_seen kept across passes. For parser drift the ticket names the fetcher and its source
file, and -- when an LLM seat is configured -- carries a PROPOSED parser change. LLMs PROPOSE
ONLY: nothing here edits, applies or merges code. A proposal is text on a ticket for a builder to
read and test; the fetcher is changed only through a reviewed PR. A breaking lake schema keeps its
old baseline until the same new schema has held `ACCEPT_AFTER_PASSES` passes, then the ticket is
closed ACCEPTED_AS_NEW_SCHEMA, so a deliberate change stops alarming without anyone editing state.

READ-ONLY OVER THE FEEDS. No feed is fetched, restarted or paused: drift is routed to a ticket,
never turned into a veto (GROWTH_GOVERNANCE Rule 1 -- nothing here sizes or blocks).

    python desks/mt5/research/feed_schema_watch.py --once [--no-llm]
"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import re
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SERIES = DESK / "data" / "lake" / "series"
RUNS = DESK / "data" / "free_stack" / "yield_runs.jsonl"
ROSTER = DESK / "data" / "free_stack_sources.json"
STATE = DESK / "data" / "feed_schema_watch"
BASELINE = STATE / "baseline.json"
TICKETS = STATE / "tickets"
REPORT = DESK / "reports" / "FEED_SCHEMA_WATCH.json"

UNMEASURED = "UNMEASURED"
BREAKING = ("COLUMN_REMOVED", "DTYPE_CHANGED", "STAMP_LOST", "ROWS_SHRANK")
ACCEPT_AFTER_PASSES = 24
SHRINK_RATIO = 0.5
#: Live runs read per source, newest last.
RUN_WINDOW = 40
#: The failure classes `free_stack.classify` gives a request that never got a parsable answer.
TRANSPORT = re.compile(r"^(timeout|dns|tls|refused|reset|proxy|http_\d+|URLError|"
                       r"ConnectionError|OSError|BLOCKED_BY_ROBOTS|RATE_LIMITED)$")
#: LLM proposals per pass, and per ticket lifetime one. A proposal is text; it is never applied.
MAX_PROPOSALS_PER_PASS = 2

#: propose(prompt) -> (text, error)
Propose = Callable[[str], tuple[str, str | None]]


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


# ------------------------------------------------------------------------------ lake schema

def fingerprint(path: Path) -> dict[str, Any] | None:
    """Columns -> dtype, row count, stamp presence. Parquet from its footer; CSV from its head."""
    try:
        if path.suffix == ".parquet":
            import pyarrow.parquet as pq
            f = pq.ParquetFile(path)
            cols = {fld.name: str(fld.type) for fld in f.schema_arrow}
            rows = int(f.metadata.num_rows)
        else:
            import pandas as pd
            head = pd.read_csv(path, nrows=200)
            cols = {c: str(t) for c, t in head.dtypes.items()}
            with path.open("rb") as fh:
                rows = max(0, sum(1 for _ in fh) - 1)
    except Exception as exc:
        return {"unreadable": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return {"columns": cols, "rows": rows, "stamped": "available_time" in cols}


def compare(base: Mapping[str, Any], now: Mapping[str, Any]) -> list[dict[str, Any]]:
    """What changed between a baseline fingerprint and this pass's."""
    out: list[dict[str, Any]] = []
    bc, nc = dict(base.get("columns") or {}), dict(now.get("columns") or {})
    for c in sorted(set(bc) - set(nc)):
        out.append({"kind": "COLUMN_REMOVED", "column": c, "was": bc[c]})
    for c in sorted(set(bc) & set(nc)):
        if bc[c] != nc[c]:
            out.append({"kind": "DTYPE_CHANGED", "column": c, "was": bc[c], "now": nc[c]})
    for c in sorted(set(nc) - set(bc)):
        out.append({"kind": "COLUMN_ADDED", "column": c, "now": nc[c]})
    if base.get("stamped") and not now.get("stamped"):
        out.append({"kind": "STAMP_LOST", "column": "available_time"})
    br, nr = int(base.get("rows") or 0), int(now.get("rows") or 0)
    if br >= 10 and nr < br * SHRINK_RATIO:
        out.append({"kind": "ROWS_SHRANK", "was": br, "now": nr})
    return out


def lake_pass(series_dir: Path, baseline: dict[str, Any], now: datetime
              ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    files = sorted([*series_dir.glob("*.parquet"), *series_dir.glob("*.csv")]) \
        if series_dir.exists() else []
    rows: dict[str, Any] = {}
    drift: list[dict[str, Any]] = []
    for p in files:
        name = p.name
        fp = fingerprint(p)
        if fp is None or "unreadable" in fp:
            rows[name] = {"status": "UNREADABLE", "why": (fp or {}).get("unreadable")}
            drift.append({"feed": f"lake:{name}", "kind": "UNREADABLE",
                          "detail": rows[name]["why"], "breaking": True})
            continue
        b = baseline.get(name)
        if b is None:
            baseline[name] = {**fp, "since": now.isoformat(timespec="seconds")}
            rows[name] = {"status": "BASELINED", "columns": len(fp["columns"]), "rows": fp["rows"]}
            continue
        changes = compare(b, fp)
        breaking = [c for c in changes if c["kind"] in BREAKING]
        if not breaking:
            # additions extend the baseline; row growth moves it forward
            baseline[name] = {**fp, "since": b.get("since")}
            rows[name] = {"status": "OK", "added": [c["column"] for c in changes
                                                    if c["kind"] == "COLUMN_ADDED"]}
            continue
        sig = json.dumps(fp["columns"], sort_keys=True)
        pend = b.get("pending") or {}
        streak = int(pend.get("passes") or 0) + 1 if pend.get("sig") == sig else 1
        if streak >= ACCEPT_AFTER_PASSES:
            baseline[name] = {**fp, "since": now.isoformat(timespec="seconds"),
                              "accepted_from": b.get("columns")}
            rows[name] = {"status": "ACCEPTED_AS_NEW_SCHEMA", "changes": changes}
            drift.append({"feed": f"lake:{name}", "kind": "ACCEPTED_AS_NEW_SCHEMA",
                          "changes": changes, "breaking": False})
            continue
        b["pending"] = {"sig": sig, "passes": streak}
        rows[name] = {"status": "DRIFT", "changes": changes, "passes": streak}
        drift.append({"feed": f"lake:{name}", "kind": "SCHEMA_DRIFT", "changes": changes,
                      "passes_with_new_schema": streak, "breaking": True})
    return rows, drift


# ----------------------------------------------------------------------------- parser drift

def _runs(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                with contextlib.suppress(ValueError):
                    r = json.loads(line)
                    if isinstance(r, dict) and r.get("live"):
                        out.append(r)
    except OSError:
        pass
    return out


def _yielded(r: Mapping[str, Any]) -> bool:
    return bool(int(r.get("obs_added") or 0) or int(r.get("raw_rows") or 0)
                or int(r.get("datasets") or 0))


def classify_run(r: Mapping[str, Any]) -> str:
    """YIELD, TRANSPORT, PARSED_NOTHING or NO_REQUEST for one live run."""
    if _yielded(r):
        return "YIELD"
    if not int(r.get("requests") or 0):
        return "NO_REQUEST"
    fails = dict(r.get("failures") or {})
    if any(TRANSPORT.match(str(k)) for k, v in fails.items() if v):
        return "TRANSPORT"
    return "PARSED_NOTHING"


def parser_pass(runs_path: Path, roster: Mapping[str, Mapping[str, Any]]
                ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for r in _runs(runs_path):
        by.setdefault(str(r.get("source")), []).append(r)
    rows: dict[str, Any] = {}
    drift: list[dict[str, Any]] = []
    for sid, rs in sorted(by.items()):
        rs = rs[-RUN_WINDOW:]
        last = rs[-1]
        kind = classify_run(last)
        ever = next((r for r in reversed(rs[:-1]) if _yielded(r)), None)
        row = {"last": kind, "last_at": last.get("at"), "runs": len(rs),
               "last_yield_at": ever.get("at") if ever else None}
        if kind == "PARSED_NOTHING" and ever is not None:
            row["status"] = "PARSER_DRIFT"
            kind_name = str((roster.get(sid) or {}).get("kind") or "")
            drift.append({"feed": f"free_stack:{sid}", "kind": "PARSER_DRIFT",
                          "fetcher_kind": kind_name, "breaking": True,
                          "detail": str(last.get("detail") or "")[:200],
                          "status": last.get("status"), "requests": last.get("requests"),
                          "notes": last.get("notes") or [],
                          "last_yield_at": ever.get("at")})
        else:
            row["status"] = {"YIELD": "OK", "TRANSPORT": "TRANSPORT",
                             "NO_REQUEST": "IDLE"}.get(kind, UNMEASURED if ever is None
                                                       else "PARSER_DRIFT")
        rows[sid] = row
    return rows, drift


# ---------------------------------------------------------------------------------- tickets

def fetcher_source(kind: str) -> tuple[str, str]:
    """(qualified name, source text) of the free-stack fetcher for this kind, or ("", "")."""
    try:
        from libs.data import free_stack as fs
        fn = fs.FETCHERS.get(kind)
        if fn is None:
            return "", ""
        return f"libs/data/free_stack.py:{fn.__name__}", inspect.getsource(fn)
    except Exception:
        return "", ""


#: The only fields of a drift record that may leave the box in a prompt. Counts, classes and
#: dates -- never a row, a page body, a URL's query, a run note or a `detail` string, any of
#: which can carry licensed feed content. A third-party LLM sees the SHAPE of the breakage and
#: the desk's own parser code, nothing the feed published.
PROMPT_FIELDS: tuple[str, ...] = ("kind", "fetcher_kind", "status", "requests",
                                  "last_yield_at", "passes_with_new_schema")


def schema_diff(d: Mapping[str, Any]) -> dict[str, Any]:
    """The drift as a schema diff: whitelisted scalars plus column-level changes (names and
    dtypes only, never values)."""
    out: dict[str, Any] = {k: d.get(k) for k in PROMPT_FIELDS if d.get(k) is not None}
    if d.get("kind") == "PARSER_DRIFT":
        out["parsed_rows"] = 0
    changes = []
    for c in d.get("changes") or []:
        changes.append({k: c.get(k) for k in ("kind", "column", "was", "now")
                        if c.get(k) is not None and not (c.get("kind") == "ROWS_SHRANK"
                                                         and k == "column")})
    if changes:
        out["changes"] = changes
    return out


def prompt_for(d: Mapping[str, Any], name: str, src: str) -> str:
    """The source NAME, the schema diff and the desk's own parser code. Never sample rows."""
    return ("A data parser stopped producing rows. Requests succeeded (no transport failure) "
            "but nothing was parsed, while earlier runs yielded. Propose the smallest change to "
            "the parser below that would read the likely new page/JSON shape, as a unified diff, "
            "and list what a builder must verify on a recorded fixture before merging. Do not "
            "change what is fetched or the robots/UA handling.\n\n"
            f"Source: {d.get('feed')}\nFetcher: {name}\n"
            f"Schema diff: {json.dumps(schema_diff(d), sort_keys=True, default=str)}\n\n"
            f"```python\n{src[:6000]}\n```")


def default_proposer() -> tuple[Propose | None, str]:
    try:
        from libs.ops import openrouter_free as orf
        key, source = orf.resolve_key()
        if not key:
            return None, "no LLM seat configured (OPENROUTER_API_KEY / llm_panel)"
        models, _basis = orf.free_models(key)
        state = orf.load_state()

        def propose(prompt: str) -> tuple[str, str | None]:
            text, _model, err = orf.complete([{"role": "user", "content": prompt}], key=key,
                                             models=models, state=state, max_tokens=2000)
            return text, err
        return propose, source
    except Exception as exc:
        return None, f"LLM seat unavailable ({type(exc).__name__})"


def _slug(feed: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", feed)[:120]


def write_tickets(drift: list[dict[str, Any]], now: datetime, *, tickets: Path,
                  propose: Propose | None, seat: str) -> dict[str, Any]:
    tickets.mkdir(parents=True, exist_ok=True)
    open_now = {_slug(d["feed"]) for d in drift if d.get("breaking")}
    proposals = 0
    rep: dict[str, Any] = {"open": 0, "closed": 0, "proposed": 0, "llm_seat": seat}
    for d in drift:
        path = tickets / f"{_slug(d['feed'])}.json"
        prior = _read(path, {}) or {}
        t = {**d, "first_seen": prior.get("first_seen") or now.isoformat(timespec="seconds"),
             "last_seen": now.isoformat(timespec="seconds"),
             "state": "OPEN" if d.get("breaking") else "CLOSED",
             "rule": "LLMs propose only: nothing on this ticket is applied by any organ"}
        if d["kind"] == "PARSER_DRIFT":
            name, src = fetcher_source(str(d.get("fetcher_kind") or ""))
            t["fetcher"] = name or UNMEASURED
            t["proposal"] = prior.get("proposal") or {"status": "NOT_REQUESTED"}
            if (t["proposal"].get("status") != "PROPOSED_NOT_APPLIED" and src
                    and propose is not None and proposals < MAX_PROPOSALS_PER_PASS):
                proposals += 1
                text, err = propose(prompt_for(d, name, src))
                t["proposal"] = ({"status": "PROPOSED_NOT_APPLIED", "text": text[:12000],
                                  "at": now.isoformat(timespec="seconds"), "seat": seat}
                                 if text and not err else
                                 {"status": "LLM_FAILED", "why": str(err)[:200]})
            elif propose is None and t["proposal"].get("status") == "NOT_REQUESTED":
                t["proposal"] = {"status": "NO_LLM_SEAT", "why": seat}
        _write_json(path, t)
        rep["open" if t["state"] == "OPEN" else "closed"] += 1
    # a ticket whose feed no longer drifts is closed, not deleted: the history is the record
    for p in tickets.glob("*.json"):
        if p.stem in open_now:
            continue
        t = _read(p, {}) or {}
        if t.get("state") == "OPEN":
            t.update({"state": "RESOLVED", "resolved_at": now.isoformat(timespec="seconds")})
            _write_json(p, t)
            rep["closed"] += 1
    rep["proposed"] = proposals
    return rep


# ------------------------------------------------------------------------------------- main

def run(*, now: datetime | None = None, llm: bool = True, series_dir: Path = SERIES,
        runs_path: Path = RUNS, state: Path = STATE, report: Path = REPORT,
        propose: Propose | None = None) -> dict[str, Any]:
    now = now or _now()
    baseline_path = state / "baseline.json"
    baseline = _read(baseline_path, {}) or {}
    roster = {str(r.get("id")): r for r in ((_read(ROSTER, {}) or {}).get("sources") or [])
              if isinstance(r, dict)}
    lake_rows, lake_drift = lake_pass(series_dir, baseline, now)
    parser_rows, parser_drift = parser_pass(runs_path, roster)
    _write_json(baseline_path, baseline)
    seat = "disabled (--no-llm)"
    if llm and propose is None:
        propose, seat = default_proposer()
    elif propose is not None:
        seat = "injected"
    tickets = write_tickets(lake_drift + parser_drift, now, tickets=state / "tickets",
                            propose=propose if llm else None, seat=seat)
    breaking = [d for d in lake_drift + parser_drift if d.get("breaking")]
    measured = bool(lake_rows) or bool(parser_rows)
    doc = {"generated_utc": now.isoformat(timespec="seconds"),
           "writer": "research/feed_schema_watch.py",
           "status": (UNMEASURED if not measured else "DRIFT" if breaking else "OK"),
           "lake": {"files": len(lake_rows), "rows": lake_rows},
           "free_stack": {"sources": len(parser_rows), "rows": parser_rows},
           "drift": breaking, "tickets": tickets,
           "rule": ("read-only over the feeds; drift opens a ticket, an LLM may PROPOSE a "
                    "parser change on it, and only a reviewed PR changes a fetcher")}
    if not measured:
        doc["why"] = "no lake series and no free-stack live runs on this host"
    _write_json(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args(argv)
    doc = run(llm=not a.no_llm)
    print(f"feed_schema_watch: {doc['status']}; lake {doc['lake']['files']} file(s), "
          f"free stack {doc['free_stack']['sources']} source(s), {len(doc['drift'])} drifting; "
          f"tickets open {doc['tickets']['open']}, proposals {doc['tickets']['proposed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
