"""ALT_DATA_YIELD.json -- what the alt-data miners actually reach, per platform, vector and leg.

A LIBRARY, NOT A LEG OF ITS OWN (no entry point, on purpose: a second clock would be a
shadow). The artifact is rewritten at the end of every pass of the organs that move
it -- `deep_forest_miner.run` (the hourly `deep_forest` leg and, through `forest_runner`'s
practitioner role, every `forest_*` leg) and `regional_survivor_hunters.run_and_save` (the
seed-miner clock). This file only COMPOSES what those organs already record:

* per PLATFORM (the regional copy/PAMM grounds): `data/intelligence/coverage_registry.json`
  -- attempts, successes, rows, last error;
* per VECTOR (the 502 deep-forest grounds): `data/deep_forest_frontier.json` (outcome,
  attempts, findings, blocker) joined with `data/deep_forest_vector_stats.json` (successes,
  rows, datasets, last error, counted per checkpoint since the counter landed);
* per LEG fetch rate: `data/alt_fetch_runs.jsonl` (one line per miner pass: fetches, ok,
  seconds) and, for the `forest_*` legs, the wall/CPU seconds `compute_ledger.jsonl` holds;
* the week: vectors attempted in the last seven days against vectors named.

THE YIELD LADDER (2026-10-13). Each vector also carries `conversion`, the deepest stage its
output reached: named -> attempted -> reached -> yielded -> collected (an endpoint it produced is
in `data/acquired/registry.json`) -> cell_generating (a compiled candidate in
`data/hypotheses/miner_candidates.json` names its ground or one of its own hosts). The summary
counts vectors per deepest stage. A stage whose source artifact is absent here is UNMEASURED with
the reason. `by_outcome` keeps HELD (a ground whose source policy is METHOD_BLOCKED -- the
only route would bypass a login, paywall, CAPTCHA, rate limit or region lock -- or NEEDS_KEY;
never a category ban, and `held_by` says which) apart from BLOCKED; `blocked_by_cause` counts
BLOCKED vectors by the closed `BLOCK_CAUSES` enum and
`yielded_by_rule` counts YIELDED vectors by the rule that fired (claims | endpoints | papers).

UNMEASURED IS NEVER ZERO (L1.28a). A counter that did not exist when a platform was last worked
reads "UNMEASURED" with the reason, never 0; a leg with no fetch-rate line reads UNMEASURED. A
vector that was never attempted has attempts 0 -- that zero IS measured, by the frontier.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ARTIFACT_NAME = "ALT_DATA_YIELD.json"
OUT = DESK / "reports" / ARTIFACT_NAME
COVERAGE = DESK / "data" / "intelligence" / "coverage_registry.json"
FRONTIER = DESK / "data" / "deep_forest_frontier.json"
VECTOR_STATS = DESK / "data" / "deep_forest_vector_stats.json"
RUNS = DESK / "data" / "alt_fetch_runs.jsonl"
COMPUTE_LEDGER = DESK / "data" / "compute_ledger.jsonl"
SOURCES = DESK / "data" / "deep_forest_sources.json"
DATASETS = DESK / "data" / "deep_forest_datasets.jsonl"
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
CANDIDATES = DESK / "data" / "hypotheses" / "miner_candidates.json"
#: A compiled-candidates file larger than this is not scanned here (the scan is text, not JSON,
#: and runs on every miner pass); the cell_generating stage then reads UNMEASURED with the size.
CANDIDATES_MAX_BYTES = 256 * 1024 * 1024
UNMEASURED = "UNMEASURED"
WEEK = timedelta(days=7)
DAY = timedelta(days=1)
#: The fetching legs this artifact accounts for. forest_* are added from the federation.
FETCH_LEGS: tuple[str, ...] = ("regional_survivor_hunters", "deep_forest_miner")


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl(p: Path, max_bytes: int = 32 * 1024 * 1024) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            for raw in fh:
                with contextlib.suppress(ValueError):
                    row = json.loads(raw.decode("utf-8", errors="replace"))
                    if isinstance(row, dict):
                        out.append(row)
    except OSError:
        return out
    return out


def _ts(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


# --------------------------------------------------------------------------- blocker causes
#: THE CLOSED CAUSE ENUM a BLOCKED (or HELD) ground's blocker is classified into. HTTP_4xx carries
#: its code beside it. UNCLASSIFIED is the honest residue for an error text none of these
#: patterns names; it is counted and its text kept, never folded into a neighbour.
BLOCK_CAUSES: tuple[str, ...] = (
    "HTTP_4xx", "HTTP_5xx", "HTTP_429", "TRANSPORT", "ANTI_BOT", "METHOD_BLOCKED", "NEEDS_KEY",
    "RENDER_FAILED", "NO_ADDRESS", "NO_NETWORK", "BUDGET")
UNCLASSIFIED = "UNCLASSIFIED"
#: Most decisive first: an anti-bot wall or a terms refusal explains a ground even when a later
#: fallback also failed for a duller reason. (A ground HELD by its source policy never gets
#: here: it is held before any fetch. A per-URL hold inside a ground ranks after anti-bot.)
_CAUSE_RANK: tuple[str, ...] = ("ANTI_BOT", "METHOD_BLOCKED", "NEEDS_KEY", "HTTP_429",
                                "HTTP_4xx", "HTTP_5xx",
                                "RENDER_FAILED", "TRANSPORT", "NO_ADDRESS", "NO_NETWORK", "BUDGET",
                                UNCLASSIFIED)
_STATUS_CAUSE: dict[str, str] = {"NO_ADDRESS": "NO_ADDRESS", "NO_NETWORK": "NO_NETWORK",
                                 "BUDGET_EXHAUSTED": "BUDGET"}
_RE_ANTI_BOT = re.compile(r"(?i)anti-bot|captcha|cf-chl|just a moment|attention required|"
                          r"are you a robot|ddos-guard|bot detection|"
                          r"(?:bing|duckduckgo) returned no parseable results")
_RE_METHOD = re.compile(r"(?i)METHOD_BLOCKED|robots(?:\.txt)? disallow")
_RE_NEEDS_KEY = re.compile(r"NEEDS_KEY")
_RE_HTTP = re.compile(r"(?i)\bHTTP(?:Error)?(?: Error)?[ :=]+(\d{3})\b")
_RE_RENDER = re.compile(r"(?i)\brender")
_RE_TRANSPORT = re.compile(r"(?i)URLError|timed? ?out|TimeoutError|ConnectionReset|"
                           r"ConnectionRefused|RemoteDisconnected|SSL|certificate|"
                           r"Name or service|getaddrinfo|No address associated|OSError|"
                           r"IncompleteRead|socket|deadline|fetch failed|no route")
_RE_BUDGET = re.compile(r"(?i)BUDGET")
_RE_NO_ADDRESS = re.compile(r"(?i)no site and no url|NO_ADDRESS")
_RE_NO_NETWORK = re.compile(r"(?i)NO_NETWORK|three straight transport failures")


def _one_cause(e: Any) -> tuple[str, int | None]:
    """The cause ONE fetch error names. A dict is a structured per-URL error from the miner
    (`http`, `error`, `render`, `terms`, `anti_bot`); a string is a route's own error text."""
    if isinstance(e, dict):
        if e.get("held") in ("METHOD_BLOCKED", "NEEDS_KEY"):
            return str(e["held"]), None
        if e.get("anti_bot"):
            return "ANTI_BOT", None
        if e.get("http") is not None:
            with contextlib.suppress(TypeError, ValueError):
                code = int(e["http"])
                if code == 429:
                    return "HTTP_429", 429
                return ("HTTP_5xx" if code >= 500 else "HTTP_4xx"), code
        if e.get("render"):
            return "RENDER_FAILED", None
        if e.get("error"):
            return _one_cause(str(e["error"]))
        return UNCLASSIFIED, None
    text = str(e or "")
    if _RE_METHOD.search(text):
        return "METHOD_BLOCKED", None
    if _RE_NEEDS_KEY.search(text):
        return "NEEDS_KEY", None
    if _RE_ANTI_BOT.search(text):
        return "ANTI_BOT", None
    m = _RE_HTTP.search(text)
    if m:
        code = int(m.group(1))
        if code == 429:
            return "HTTP_429", 429
        if code >= 500:
            return "HTTP_5xx", code
        if code >= 400:
            return "HTTP_4xx", code
    if _RE_RENDER.search(text):
        return "RENDER_FAILED", None
    if _RE_NO_ADDRESS.search(text):
        return "NO_ADDRESS", None
    if _RE_NO_NETWORK.search(text):
        return "NO_NETWORK", None
    if _RE_TRANSPORT.search(text):
        return "TRANSPORT", None
    if _RE_BUDGET.search(text):
        return "BUDGET", None
    return UNCLASSIFIED, None


def classify_cause(status: str = "", errors: Iterable[Any] = (), *,
                   over_budget: bool = False) -> tuple[str, int | None]:
    """(cause, http_code) for one ground's failed attempt, from its status and every fetch error
    the attempt collected. The most decisive cause wins (`_CAUSE_RANK`); among HTTP_4xx the
    first code seen is kept. A failed attempt with no error text at all is BUDGET when the
    ground's time ran out, else UNCLASSIFIED -- never a guessed cause."""
    st = str(status or "")
    if st == "HELD":
        for e in errors or ():
            c = _one_cause(e)[0]
            if c in ("METHOD_BLOCKED", "NEEDS_KEY"):
                return c, None
    if st in _STATUS_CAUSE:
        return _STATUS_CAUSE[st], None
    best: tuple[str, int | None] | None = None
    for e in errors or ():
        c = _one_cause(e)
        if best is None or _CAUSE_RANK.index(c[0]) < _CAUSE_RANK.index(best[0]):
            best = c
    if best is None or best[0] == UNCLASSIFIED:
        return ("BUDGET", None) if over_budget else (best or (UNCLASSIFIED, None))
    return best


def cause_label(cause: str, code: int | None = None) -> str:
    """`HTTP_4xx(403)` for a 4xx with its code, else the cause itself."""
    return f"{cause}({code})" if cause == "HTTP_4xx" and code else cause


def legacy_cause(text: str) -> tuple[str, int | None]:
    """The cause a blocker recorded BEFORE causes were kept reads as. The bare word "BLOCKED"
    (215 vectors on 2026-10-13) names nothing, so it is UNMEASURED, never a guessed cause."""
    t = str(text or "").strip()
    if not t or t.upper() in ("BLOCKED", "BLOCKED:", "UNREACHABLE"):
        return UNMEASURED, None
    head = t.split(":", 1)[0].split("(", 1)[0].strip()
    if head in BLOCK_CAUSES:
        m = re.match(r"HTTP_4xx\((\d{3})\)", t)
        return head, (int(m.group(1)) if m else None)
    return _one_cause(t)


def forest_legs() -> list[str]:
    try:
        from libs.research import forests as F
        return sorted(f"forest_{fid}" for fid in F.FORESTS)
    except Exception:
        return []


# --------------------------------------------------------------------------- platforms
def platforms(cov: Any) -> dict[str, Any]:
    if not isinstance(cov, dict) or not isinstance(cov.get("platforms"), dict):
        return {"status": UNMEASURED, "why": f"{COVERAGE.name} absent or unreadable here"}
    rows: dict[str, Any] = {}
    for name, e in sorted(cov["platforms"].items()):
        e = e if isinstance(e, dict) else {}
        counted = "successes" in e
        why_unm = "counter landed 2026-09-30; this platform has not been worked since"
        last_err = e.get("last_error")
        if last_err is None:
            st = str(e.get("last_state") or "")
            last_err = "" if st == "ok" else (st or UNMEASURED)
        rows[name] = {
            "region": e.get("region"), "lang": e.get("lang"),
            "attempts": int(e.get("attempts") or 0),
            "successes": int(e.get("successes") or 0) if counted else UNMEASURED,
            "rows": int(e.get("rows_total") or 0) if counted else UNMEASURED,
            "best_rows": int(e.get("best_rows") or 0),
            "last_rows": e.get("last_rows", UNMEASURED),
            "last_state": e.get("last_state") or UNMEASURED,
            "last_error": last_err,
            "last_attempt": e.get("last_attempt") or UNMEASURED,
            "last_success": e.get("last_success") or UNMEASURED,
            "last_via": e.get("last_via") or UNMEASURED,
            "counted_since": e.get("counted_since") or UNMEASURED,
            **({} if counted else {"why_unmeasured": why_unm}),
        }
    yielding = [n for n, r in rows.items()
                if r["best_rows"] > 0 or (isinstance(r["successes"], int) and r["successes"] > 0)]
    return {"n": len(rows), "yielding": len(yielding),
            "never_yielded": sorted(set(rows) - set(yielding)), "rows_by_platform": rows}


# --------------------------------------------------------------------------- vectors
#: The conversion ladder, shallowest first.
STAGES: tuple[str, ...] = ("named", "attempted", "reached", "yielded", "collected",
                           "cell_generating")
_HOST_TOKEN = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+[a-z]{2,24}\b")
_JSON_STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_TOKEN_CACHE: dict[tuple[str, int, int], tuple[set[str], set[str]]] = {}


def _host(u: Any) -> str:
    s = str(u or "").strip().lower()
    if not s:
        return ""
    if "://" not in s:
        s = "https://" + s
    from urllib.parse import urlparse
    h = (urlparse(s).hostname or "").strip(".")
    return h[4:] if h.startswith("www.") else h


def own_hosts(g: dict[str, Any]) -> set[str]:
    """The hosts a ground itself names (url, alt, site, feeds) -- never the hosts a search
    result happened to point at, which would credit a ground for someone else's page."""
    out = {_host(g.get("url")), _host(g.get("site"))}
    for k in ("alt", "feeds"):
        for u in g.get(k) or []:
            out.add(_host(u))
    out.discard("")
    return out


def _held(g: dict[str, Any] | None) -> str | None:
    """METHOD_BLOCKED or NEEDS_KEY when the ground's source policy holds it, else None."""
    if not g:
        return None
    try:
        from research.deep_forest_miner import held_ground
    except Exception:
        return None
    p = held_ground(g)
    return str(p["status"]) if p else None


def _endpoints_by_ground(rows: Iterable[dict[str, Any]] | None) -> dict[str, set[str]] | None:
    """Endpoints each ground produced, from the datasets ledger. A dataset row with 0 endpoints
    adds nothing -- a dataset PAGE is not a yield."""
    if rows is None:
        return None
    out: dict[str, set[str]] = {}
    for r in rows:
        eps = [str(e) for e in (r.get("endpoints") or []) if e]
        if eps:
            out.setdefault(str(r.get("ground") or ""), set()).update(eps)
    return out


def _acquired_urls(reg: Any) -> set[str] | None:
    if not isinstance(reg, dict) or not isinstance(reg.get("by_url"), dict):
        return None
    return {str(u) for u in reg["by_url"]}


def candidate_tokens(path: Path) -> tuple[tuple[set[str], set[str]] | None, str]:
    """(JSON string values, host tokens) in the compiled-candidates file, or None and why.
    A TEXT scan, bounded and cached per file version: the file is tens of MB and this runs on
    every miner pass, so it is never parsed as one JSON tree here."""
    try:
        st = path.stat()
    except OSError:
        return None, f"{path.name} absent here"
    if st.st_size > CANDIDATES_MAX_BYTES:
        return None, f"{path.name} is {st.st_size} bytes, above the {CANDIDATES_MAX_BYTES} scan cap"
    key = (str(path), int(st.st_size), int(st.st_mtime))
    if key in _TOKEN_CACHE:
        return _TOKEN_CACHE[key], ""
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError as exc:
        return None, f"{path.name} unreadable: {type(exc).__name__}"
    strings: set[str] = set()
    for m in _JSON_STR.finditer(text):
        v = m.group(1)
        if len(v) > 300:               # a ground name is short; prose is not a match target
            continue
        if "\\" in v:
            with contextlib.suppress(ValueError):
                v = json.loads(f'"{v}"')
        strings.add(v)
    hosts = {h.lower()[4:] if h.lower().startswith("www.") else h.lower()
             for h in _HOST_TOKEN.findall(text)}
    del text
    _TOKEN_CACHE.clear()
    _TOKEN_CACHE[key] = (strings, hosts)
    return (strings, hosts), ""


def _ladder(*, attempts: int, outcome: str, findings: int, endpoints: Any,
            collected: Any, cells: Any) -> dict[str, Any]:
    eps_n = len(endpoints) if isinstance(endpoints, set) else endpoints
    reached = outcome in ("EMPTY", "YIELDED") or findings > 0 or (
        isinstance(eps_n, int) and eps_n > 0)
    yielded = outcome == "YIELDED" or findings > 0 or (isinstance(eps_n, int) and eps_n > 0)
    stages: dict[str, Any] = {"named": True, "attempted": attempts > 0, "reached": reached,
                              "yielded": yielded, "collected": collected,
                              "cell_generating": cells}
    deepest = "named"
    for k in STAGES:
        if stages[k] is True:
            deepest = k
    return {**stages, "deepest": deepest,
            "unmeasured": [k for k in STAGES if stages[k] == UNMEASURED]}


def vectors(frontier: Any, stats: Any, now: datetime, *, grounds: Any = None,
            datasets: list[dict[str, Any]] | None = None, acquired: Any = None,
            candidates: tuple[tuple[set[str], set[str]] | None, str] | None = None,
            ) -> dict[str, Any]:
    vec = frontier.get("vectors") if isinstance(frontier, dict) else None
    if not isinstance(vec, dict):
        return {"status": UNMEASURED, "why": f"{FRONTIER.name} absent or unreadable here"}
    st = (stats or {}).get("vectors") if isinstance(stats, dict) else None
    st = st if isinstance(st, dict) else {}
    gidx: dict[str, dict[str, Any]] = {}
    if isinstance(grounds, dict):
        gidx = {str(g.get("name")): g for g in grounds.get("grounds") or []
                if isinstance(g, dict) and g.get("name")}
    eps_by = _endpoints_by_ground(datasets)
    acq = _acquired_urls(acquired)
    cand, cand_why = candidates if candidates is not None else (None, "not scanned")
    rows: dict[str, Any] = {}
    outcomes: dict[str, int] = {}
    by_cause: dict[str, int] = {}
    by_code: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    held_by: dict[str, int] = {}
    deepest: dict[str, int] = dict.fromkeys(STAGES, 0)
    week = never = 0
    landed_pages = landed_vectors = landed_unmeasured = 0
    for name, v in sorted(vec.items()):
        v = v if isinstance(v, dict) else {}
        s = st.get(name) if isinstance(st.get(name), dict) else None
        g = gidx.get(name)
        attempts = int(v.get("attempts") or 0)
        recorded = str(v.get("outcome") or "NAMED_ONLY")
        outcome = recorded
        # A ground its source policy HOLDS reads HELD whatever an older pass recorded: it is not
        # fetched again, so its last BLOCKED/EMPTY is history, not a standing outcome.
        held = _held(g)
        if held and outcome != "HELD":
            outcome = "HELD"
        elif not held and outcome == "HELD" and g is not None:
            outcome = "NAMED_ONLY"          # re-admitted: its policy no longer holds it
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        la = _ts(v.get("last_attempt"))
        if attempts == 0:
            never += 1
        if la is not None and now - la <= WEEK:
            week += 1
        if s is not None:
            successes: Any = int(s.get("successes") or 0)
            rows_n: Any = int(s.get("rows") or 0)
            landed: Any = int(s.get("landed_raw") or 0)
        elif attempts == 0:
            successes, rows_n, landed = 0, 0, 0      # never attempted: a MEASURED zero
        else:
            successes, rows_n, landed = UNMEASURED, UNMEASURED, UNMEASURED
        last_error = (s or {}).get("last_error") or v.get("blocker") or ""
        row: dict[str, Any] = {
            "outcome": outcome, "attempts": attempts, "successes": successes,
            "rows": rows_n, "findings_total": int(v.get("findings") or 0),
            "datasets": int(s.get("datasets") or 0) if s is not None else (
                0 if attempts == 0 else UNMEASURED),
            "last_error": last_error,
            "last_attempt": v.get("last_attempt") or "",
            "language": v.get("language") or "", "region": v.get("region") or "",
        }
        if outcome != recorded:
            row["outcome_recorded"] = recorded
        if held:
            row["held_by"] = held
            held_by[held] = held_by.get(held, 0) + 1
        if outcome == "BLOCKED":
            if s is not None and s.get("last_cause"):
                cause, code = str(s["last_cause"]), s.get("last_http_code")
            else:
                cause, code = legacy_cause(str(v.get("blocker") or ""))
                if cause == UNMEASURED and s is not None:
                    cause, code = legacy_cause(str(s.get("last_error") or ""))
            row["cause"] = cause
            if cause == UNMEASURED:
                row["cause_why"] = ("blocker recorded before causes were kept (the bare word "
                                    "BLOCKED); the next attempt records it")
            if code:
                row["http_code"] = code
                by_code[str(code)] = by_code.get(str(code), 0) + 1
            by_cause[cause] = by_cause.get(cause, 0) + 1
        if outcome == "YIELDED":
            rule = str((s or {}).get("last_yield_rule") or "")
            if not rule:
                rule = "claims"
                row["yield_rule_source"] = ("legacy: claims was the only yield rule before "
                                            "2026-10-13")
            row["yield_rule"] = rule
            by_rule[rule] = by_rule.get(rule, 0) + 1
        eps: Any = UNMEASURED if eps_by is None else eps_by.get(name, set())
        row["endpoints"] = len(eps) if isinstance(eps, set) else UNMEASURED
        if not isinstance(eps, set) or acq is None:
            collected: Any = UNMEASURED
        else:
            collected = bool(eps & acq)
        if cand is None:
            cells: Any = UNMEASURED
        else:
            strings, hosts = cand
            cells = name in strings or bool(own_hosts(g or {}) & hosts)
        row["conversion"] = _ladder(attempts=attempts, outcome=outcome,
                                    findings=row["findings_total"], endpoints=eps,
                                    collected=collected, cells=cells)
        # RAW PAGES LANDED for the parser (deep_forest_miner.land_raw): counted beside the
        # ladder, never a rung of it -- a landing is not a yield.
        row["conversion"]["landed_raw"] = landed
        if isinstance(landed, int):
            landed_pages += landed
            landed_vectors += int(landed > 0)
        else:
            landed_unmeasured += 1
        deepest[row["conversion"]["deepest"]] += 1
        rows[name] = row
    named = len(rows)
    why_unm = {}
    if eps_by is None:
        why_unm["yielded_endpoints"] = f"{DATASETS.name} absent or unreadable here"
    if acq is None:
        why_unm["collected"] = f"{ACQUIRED.name} absent or unreadable here"
    if cand is None:
        why_unm["cell_generating"] = cand_why
    reached_at_least: dict[str, Any] = {}
    for i, k in enumerate(STAGES):
        reached_at_least[k] = (UNMEASURED if k in why_unm else
                               sum(deepest[x] for x in STAGES[i:]))
    return {"named": named, "by_outcome": outcomes, "never_attempted": never,
            "attempted_this_week": week,
            "attempted_this_week_share": round(week / named, 4) if named else UNMEASURED,
            "blocked_by_cause": by_cause, "blocked_http_codes": by_code, "held_by": held_by,
            "yielded_by_rule": by_rule,
            "conversion": {"deepest_stage": deepest, "reached_at_least": reached_at_least,
                           "landed_raw": ({"pages": landed_pages, "vectors": landed_vectors,
                                           "vectors_unmeasured": landed_unmeasured}
                                          if st else {"status": UNMEASURED,
                                                      "why": "vector stats absent here"}),
                           "unmeasured": why_unm,
                           "note": ("collected = an endpoint the ground produced is in the "
                                    "acquisition registry (exact URL); cell_generating = a "
                                    "compiled candidate names the ground or one of its own "
                                    "hosts (text match; the compiler carries no per-ground "
                                    "lineage field, so this is a lower bound)")},
            "rows_by_vector": rows}


# --------------------------------------------------------------------------- legs
def legs(runs: Iterable[dict[str, Any]], ledger: Iterable[dict[str, Any]],
         now: datetime) -> dict[str, Any]:
    agg: dict[str, dict[str, Any]] = {}
    for r in runs:
        at = _ts(r.get("at"))
        if at is None or now - at > WEEK:
            continue
        leg = str(r.get("leg") or "?")
        a = agg.setdefault(leg, {"runs": 0, "fetches": 0, "ok": 0, "http_errors": 0,
                                 "transport_errors": 0, "seconds": 0.0, "rows": 0,
                                 "last_run": ""})
        a["runs"] += 1
        for k in ("fetches", "ok", "http_errors", "transport_errors"):
            a[k] += int(r.get(k) or 0)
        a["seconds"] += float(r.get("seconds") or 0.0)
        a["rows"] += int(r.get("rows") or r.get("claims_new") or 0) + int(
            r.get("datasets_new") or 0)
        a["last_run"] = max(a["last_run"], str(r.get("at") or ""))
    wall: dict[str, dict[str, float]] = {}
    for row in ledger:
        name = str(row.get("run") or "")
        at = _ts(row.get("at"))
        if at is None or now - at > DAY:
            continue
        w = wall.setdefault(name, {"wall_s": 0.0, "cpu_s": 0.0, "runs": 0})
        w["wall_s"] += float(row.get("wall_s") or 0.0)
        w["cpu_s"] += float(row.get("cpu_s") or 0.0)
        w["runs"] += 1
    out: dict[str, Any] = {}
    for leg in (*FETCH_LEGS, *forest_legs(), *sorted(set(agg) - set(FETCH_LEGS))):
        if leg in out:
            continue
        a = agg.get(leg)
        w = wall.get(leg) or wall.get(leg.replace("_miner", ""))
        row: dict[str, Any] = {}
        if a:
            row.update({k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items()})
            row["fetches_per_s"] = (round(a["fetches"] / a["seconds"], 4)
                                    if a["seconds"] > 0 else UNMEASURED)
            row["success_rate"] = (round(a["ok"] / a["fetches"], 4)
                                   if a["fetches"] else UNMEASURED)
        else:
            row.update({"runs": UNMEASURED, "fetches": UNMEASURED,
                        "fetches_per_s": UNMEASURED,
                        "why": "no fetch-rate line in the last 7 days for this leg"})
        if w:
            row["wall_s_24h"] = round(w["wall_s"], 1)
            row["cpu_s_24h"] = (round(w["cpu_s"], 1) if w["cpu_s"] > 0 else UNMEASURED)
            if w["cpu_s"] <= 0:
                row["cpu_why"] = ("child CPU was not counted on Windows before 2026-09-30 "
                                  "(os.times() reports children as 0 there); a zero here was "
                                  "never a measurement of idleness")
        else:
            row["wall_s_24h"] = UNMEASURED
        out[leg] = row
    return out


# --------------------------------------------------------------------------- the artifact
def build(*, coverage: Path | None = None, frontier: Path | None = None,
          vector_stats: Path | None = None, runs: Path | None = None,
          compute_ledger: Path | None = None, sources: Path | None = None,
          datasets: Path | None = None, acquired: Path | None = None,
          candidates: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    coverage = coverage or COVERAGE
    frontier = frontier or FRONTIER
    vector_stats = vector_stats or VECTOR_STATS
    runs = runs or RUNS
    compute_ledger = compute_ledger or COMPUTE_LEDGER
    sources = sources or SOURCES
    datasets = datasets or DATASETS
    acquired = acquired or ACQUIRED
    candidates = candidates or CANDIDATES
    plat = platforms(_json(coverage))
    ds_rows = _jsonl(datasets) if datasets.exists() else None
    vec = vectors(_json(frontier), _json(vector_stats), now, grounds=_json(sources),
                  datasets=ds_rows, acquired=_json(acquired),
                  candidates=candidate_tokens(candidates))
    leg = legs(_jsonl(runs), _jsonl(compute_ledger, max_bytes=8 * 1024 * 1024), now)
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "summary": {
            "platforms": plat.get("n", UNMEASURED),
            "platforms_yielding": plat.get("yielding", UNMEASURED),
            "vectors_named": vec.get("named", UNMEASURED),
            "vectors_attempted_this_week": vec.get("attempted_this_week", UNMEASURED),
            "vectors_never_attempted": vec.get("never_attempted", UNMEASURED),
            "vectors_by_outcome": vec.get("by_outcome", UNMEASURED),
            "blocked_by_cause": vec.get("blocked_by_cause", UNMEASURED),
            "yielded_by_rule": vec.get("yielded_by_rule", UNMEASURED),
            "conversion": (vec.get("conversion") or {}).get("reached_at_least", UNMEASURED),
            "landed_raw": (vec.get("conversion") or {}).get("landed_raw", UNMEASURED),
        },
        "platforms": plat, "vectors": vec, "legs": leg,
        "sources": {"platforms": str(coverage), "vectors": [str(frontier), str(vector_stats)],
                    "conversion": [str(sources), str(datasets), str(acquired), str(candidates)],
                    "legs": [str(runs), str(compute_ledger)]},
        "rule": ("UNMEASURED is never written as 0; a vector never attempted has attempts 0, "
                 "which the frontier measures. Rewritten by every pass of deep_forest_miner "
                 "(deep_forest and forest_* legs) and regional_survivor_hunters."),
    }


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            with contextlib.suppress(OSError):
                os.chmod(path, 0o666)
            time.sleep(0.2 * (i + 1))
    try:
        path.write_text(text, "utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def write(out: Path | None = None, **paths: Any) -> dict[str, Any]:
    """Build and write the artifact. `paths` overrides any input (tests point them at tmp)."""
    doc = build(**{k: Path(v) for k, v in paths.items() if v is not None})
    _atomic(out or OUT, json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    return doc
