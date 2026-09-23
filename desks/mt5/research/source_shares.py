"""THE CRAWLERS' BUDGET IS THE SOURCE REGISTRY'S SHARES -- and a rising source gets its
neighbourhood expanded.

Tier-1 W17's measured gap was exact: "the source registry and the unseen-frontier estimator
exist; THE CRAWLER DOES NOT YET READ THE SHARES". `source_registry.shares()` has been computing a
softmax over measured intel ROI with a 20% exploration floor since 2026-09-16, publishing it to
reports/SOURCE_REGISTRY.json -- and both crawlers went on working their own hard-coded orders.
A budget nobody spends is a number, not an allocation (LAWS III.16).

This module is the one reader. It is deliberately tiny and deliberately guarded: every entry
point falls back to TODAY'S BEHAVIOUR when the artifact is absent, unreadable, stale or empty,
and says which of those it was. A crawler that cannot start because a report did not regenerate
is strictly worse than a crawler that crawls in the old order.

WHAT "FOLLOWS THE SHARES" MEANS IN EACH CRAWLER, because they spend different currency:

  deep_forest_miner  spends SECONDS. `run()` gives each ground `budget_s * weight / total_w`, so
                     multiplying a ground's weight by its registry share's ratio to the mean
                     moves seconds between grounds and changes the round-robin order inside each
                     cluster. The TOTAL is untouched: this redistributes, it never shrinks.
  world_crawler      spends FETCHES. The run stops on its clock, so the head of `wf.due()`'s list
                     is what actually gets fetched -- re-ranking that list IS the budget.

The ratio is clipped to [MIN_FACTOR, MAX_FACTOR]. That is a bound on a RATIO ESTIMATOR built
from small counts, not a cap on research: without it a single source holding 6% of a 639-source
registry would take 38x the mean and the rest of the forest would go unworked on one hour's
noise. Nothing here reduces the total crawl budget, refuses a ground, or vetoes a fetch.

SOURCE EXPANSION. When a source's share RISES, the pages it produced are evidence about its
NEIGHBOURHOOD, so the links that source actually served are classified (author pages, linked
forums, archives, citations, code repos, adjacent terminology) and appended to the REGISTERED
grounds file as candidate grounds -- `desks/mt5/data/deep_forest_sources.json`, the file the
principal's deep-forest order named, never a hard-coded list in a crawler. The next
`source_registry` pass prices them like any other ground, and the next crawl spends on them by
their own measured share.

EVERYTHING IS MINED (LAWS 5e, 2026-09-23). A row the registry marks `machine_use_allowed=false`,
`route=unreachable` or "snippets only" used to be DROPPED from the pass and from expansion. Those
were the desk's own discovery brakes, not legal requirements, and they are deleted: the registry's
note is now a ROUTING LABEL carried on the row (`terms_note`), never a skip. The ONLY refusal left
is one of the five acts of `libs.research.access_classifier.HARD_BOUNDARY` -- a credential dump, an
authenticated surface, MNPI, stolen data, personal-data harvesting -- and the registry declares
those with an access label, not with a licence note.
"""
from __future__ import annotations

import json
import os
import re
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
REPORT = DESK / "reports" / "SOURCE_REGISTRY.json"
REGISTRY = DESK / "data" / "source_registry.json"
GROUNDS = DESK / "data" / "deep_forest_sources.json"
STATE = DESK / "data" / "source_expansion.json"

#: Hours after which the published shares are not a budget any more. The registry is an hourly
#: leg, so a day and a half of silence means the organ is down and the old order is the honest
#: fallback -- not a frozen allocation nobody is still measuring.
STALE_H = 36.0
#: Bounds on the share/mean ratio. See the module docstring: a small-count ratio estimator, not
#: a cap on anything.
MIN_FACTOR, MAX_FACTOR = 0.25, 4.0
#: New candidate grounds a single expansion pass may append, in total and per rising source.
MAX_NEW_PER_PASS = 24
MAX_NEW_PER_SOURCE = 4
#: A share must rise by at least this to count as risen (float noise, not evidence).
RISE_EPS = 1e-9

#: The neighbourhood classes, in priority order. First match wins.
NEIGHBOURHOODS: tuple[tuple[str, str], ...] = (
    ("code", r"(?:github\.com|gitee\.com|gitlab\.com|bitbucket\.org|codeberg\.org)/[^/]+/[^/]+"
             r"|/(?:repo|repository|blob|tree)/|\.ipynb(?:$|\?)"),
    ("citation", r"(?:doi\.org|arxiv\.org/abs|papers\.ssrn\.com|openreview\.net|scholar\.)"
                 r"|/(?:cite|citation|references|bibliograph)"),
    ("archive", r"(?:web\.archive\.org|archive\.(?:org|ph|today))|/(?:archive|archives|wayback)"
                r"|/(?:19|20)\d{2}/(?:0[1-9]|1[0-2])/"),
    ("author", r"/(?:author|authors|user|users|profile|member|members|people|u)/"),
    ("forum", r"/(?:forum|forums|thread|threads|topic|topics|board|boards|discussion|bbs)"
              r"|viewtopic|showthread"),
)
_NEIGH_RE: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (k, re.compile(v, re.IGNORECASE)) for k, v in NEIGHBOURHOODS)

#: Anchor vocabulary that makes an otherwise ordinary link an ADJACENT TOPIC rather than
#: navigation. Mechanism words in the languages the deep forest is worked in -- a link whose text
#: says "套利" or "seasonality" is about something, and a link that says "Next" is not.
_TOPIC_RE = re.compile(
    r"套利|价差|基差|回测|策略|实盘|量化|季节性|持仓|资金费|"
    r"アービトラージ|裁定|季節性|バックテスト|"
    r"арбитраж|сезонн|"
    r"arbitrage|spread|basis|carry|season|backtest|mean[- ]revers|momentum|overnight|"
    r"microstructure|order[- ]flow|cot\b|positioning|volatility|regime|gap\b|roll\b",
    re.IGNORECASE)

#: Hosts that are search or social plumbing rather than ground. A neighbour here is a query, not
#: a source, and minting it as a ground pollutes the registry with its own search engine.
_PLUMBING = ("google.", "bing.com", "duckduckgo.com", "sogou.com", "baidu.com", "youtube.com",
             "t.co", "facebook.com", "twitter.com", "x.com", "linkedin.com", "pinterest.")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)


def _host(url: str) -> str:
    try:
        host = (urlsplit(str(url)).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def _age_h(stamp: Any, now: datetime | None = None) -> float | None:
    try:
        at = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0


# ------------------------------------------------------------------------------ reading
def load(report: Path | None = None, registry: Path | None = None,
         now: datetime | None = None, stale_h: float = STALE_H) -> dict[str, Any]:
    """The published shares, or a stated reason there are none.

    Returns `{"status", "why", "at", "age_h", "shares", "rows", "index"}`. `status` is
    `present` / `absent` / `stale` / `empty`; ONLY `present` may change a crawler's behaviour.
    """
    rpt_path, reg_path = report or REPORT, registry or REGISTRY
    doc = _read_json(rpt_path, None)
    blank: dict[str, Any] = {"at": None, "age_h": None, "shares": {}, "rows": {}, "index": {}}
    if not isinstance(doc, dict):
        return {**blank, "status": "absent",
                "why": f"{rpt_path.name} absent or unreadable; crawl order unchanged"}
    shares = doc.get("shares")
    if not isinstance(shares, dict) or not shares:
        return {**blank, "status": "empty", "at": doc.get("at"),
                "why": f"{rpt_path.name} carries no shares block; crawl order unchanged"}
    age = _age_h(doc.get("at"), now)
    if age is None:
        return {**blank, "status": "absent", "at": doc.get("at"),
                "why": f"{rpt_path.name} has no readable `at`; crawl order unchanged"}
    if age > stale_h:
        return {**blank, "status": "stale", "at": doc.get("at"), "age_h": round(age, 2),
                "why": (f"{rpt_path.name} is {age:.1f}h old (> {stale_h:.0f}h): the registry leg "
                        "is not running, so its shares are not a budget; crawl order unchanged")}
    reg = _read_json(reg_path, None)
    rows = reg.get("sources") if isinstance(reg, dict) else None
    rows = rows if isinstance(rows, dict) else {}
    clean = {str(k): float(v) for k, v in shares.items()
             if isinstance(v, (int, float)) and float(v) > 0.0}
    state = {"status": "present", "why": f"{len(clean)} share(s) at {doc.get('at')}",
             "at": doc.get("at"), "age_h": round(age, 2), "shares": clean, "rows": rows,
             "index": {}}
    state["index"] = _index(state)
    return state


def _index(state: dict[str, Any]) -> dict[str, str]:
    """Every string that can name a source -> its source_id. Hosts, aliases, ground names."""
    idx: dict[str, str] = {}
    rows: dict[str, Any] = state.get("rows") or {}
    for sid in state.get("shares") or {}:
        idx.setdefault(sid.lower(), sid)
        row = rows.get(sid)
        if not isinstance(row, dict):
            continue
        for key in ("name", "ground", "url"):
            val = row.get(key)
            if val:
                idx.setdefault(str(val).lower(), sid)
        for alias in row.get("aliases") or []:
            idx.setdefault(str(alias).lower(), sid)
        host = _host(row.get("url") or "")
        if host:
            idx.setdefault(host, sid)
    return idx


#: Access labels that carry the five refused ACTS of `HARD_BOUNDARY`. Kept as a literal tuple so
#: this module stays importable with no dependency on `libs/` from inside a crawler subprocess;
#: `_refused_label()` prefers the classifier's own list when it can be imported.
_REFUSED_LABELS: tuple[str, ...] = ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")


def _refused_labels() -> tuple[str, ...]:
    """The classifier's refused-label list when reachable, else the literal copy above."""
    try:
        from libs.research.access_classifier import REFUSED_LABELS
        return tuple(str(x) for x in REFUSED_LABELS)
    except Exception:
        return _REFUSED_LABELS


def machine_use_allowed(row: Any) -> tuple[bool, str]:
    """IS THIS ROW MINED? Yes, unless it carries one of the five refused acts.

    LAWS 5e (2026-09-23): licence, terms, robots, `machine_use_allowed=false`, `route=unreachable`
    and "snippets only" are ROUTING AND PROVENANCE LABELS -- they say what the desk may
    REDISTRIBUTE and how the row is provenanced, never whether it may be read, extracted or
    tested. The four refusals this function used to return were discovery brakes the desk imposed
    on itself; they are deleted and the note travels with the row instead.

    The name and the `(bool, str)` signature are unchanged because other organs import this
    (`coverage_drain.machine_use_allowed(reg_row)` among them); what changed is that the bool is
    True for everything off the hard boundary, and the string is the LABEL rather than an excuse.
    """
    if not isinstance(row, dict):
        return True, "no registry row: mined, with no terms label to carry"
    label = str(row.get("access_label") or row.get("access") or "").strip().upper()
    if label in _refused_labels():
        return False, f"hard boundary: access_label={label}"
    if row.get("requires_auth") is True or row.get("is_mnpi") is True:
        return False, "hard boundary: authenticated surface or declared MNPI"
    notes: list[str] = []
    if row.get("machine_use_allowed") is False:
        notes.append("registry declares machine_use_allowed=false")
    if str(row.get("route") or "") == "unreachable":
        notes.append("registry route=unreachable")
    if row.get("snippets_only"):
        notes.append("registry: search-index snippets only")
    note = str(row.get("licence_note") or "")
    if "NOT FETCHABLE" in note.upper() or "SNIPPETS ONLY" in note.upper():
        notes.append(f"registry licence note: {note}")
    if notes:
        return True, ("mined with its label attached [" + "; ".join(notes)
                      + "]; redistribution withheld by its terms")
    return True, "mined"


def resolve(state: dict[str, Any], *keys: Any) -> str | None:
    """The source_id for any of these names, or None."""
    idx: dict[str, str] = state.get("index") or {}
    for key in keys:
        if not key:
            continue
        text = str(key).strip().lower()
        hit = idx.get(text)
        if hit:
            return hit
        host = _host(text if "://" in text else f"http://{text}")
        if host and host in idx:
            return idx[host]
    return None


def share_for(state: dict[str, Any], *keys: Any) -> float | None:
    """This source's published crawl share, or None when the registry does not know it."""
    sid = resolve(state, *keys)
    if sid is None:
        return None
    return float((state.get("shares") or {}).get(sid) or 0.0) or None


def factor_for(state: dict[str, Any], *keys: Any) -> tuple[float, str | None]:
    """The multiplier this source's share earns against the mean share, clipped. 1.0 = unknown,
    which leaves today's behaviour exactly as it was."""
    shares: dict[str, float] = state.get("shares") or {}
    if not shares:
        return 1.0, None
    sid = resolve(state, *keys)
    if sid is None:
        return 1.0, None
    mean = statistics.fmean(shares.values()) or 0.0
    if mean <= 0.0:
        return 1.0, sid
    ratio = float(shares.get(sid) or 0.0) / mean
    return max(MIN_FACTOR, min(MAX_FACTOR, ratio)), sid


# ------------------------------------------------------- deep_forest: seconds follow the shares
def weight_grounds(grounds: list[dict[str, Any]], state: dict[str, Any] | None = None
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """COPIES of `grounds` whose `weight` is the registered weight times the registry's share
    factor. Order and per-ground seconds both follow, because `schedule()` sorts on weight and
    `run()` divides the budget by it. Returns the copies and a meta row for the report.

    The file on disk is NOT touched: the registered weight is the human's declaration and the
    share is this hour's evidence about it. Multiplying them in memory keeps both readable.
    """
    st = state if state is not None else load()
    meta: dict[str, Any] = {"status": st.get("status"), "why": st.get("why"),
                            "at": st.get("at"), "age_h": st.get("age_h"),
                            "n_reweighted": 0, "n_unknown": 0, "n_refused": 0, "n_labelled": 0,
                            "clip": [MIN_FACTOR, MAX_FACTOR]}
    if st.get("status") != "present":
        return list(grounds), meta
    rows: dict[str, Any] = st.get("rows") or {}
    out: list[dict[str, Any]] = []
    for g in grounds:
        if not isinstance(g, dict):
            continue
        factor, sid = factor_for(st, g.get("name"), g.get("url"), g.get("site"))
        row = rows.get(sid) if sid else None
        allowed, why = machine_use_allowed(row)
        if not allowed:
            # THE ONLY DROP LEFT: one of the five refused acts. A licence, robots or
            # "snippets only" note is a label on the ground below, never a skip (LAWS 5e).
            meta["n_refused"] += 1
            meta.setdefault("refused", []).append({"ground": g.get("name"), "why": why})
            continue
        copy = dict(g)
        if why != "mined":
            copy["_terms_note"] = why
            meta["n_labelled"] += 1
            meta.setdefault("labelled", []).append({"ground": g.get("name"), "terms_note": why})
        if sid is None:
            meta["n_unknown"] += 1
        else:
            copy["weight"] = round(float(g.get("weight") or 1.0) * factor, 6)
            copy["_share_factor"], copy["_source_id"] = round(factor, 4), sid
            meta["n_reweighted"] += 1
        out.append(copy)
    meta["top"] = [{"ground": g.get("name"), "weight": g.get("weight"),
                    "factor": g.get("_share_factor")}
                   for g in sorted(out, key=lambda g: -float(g.get("weight") or 1.0))[:8]]
    return out, meta


# ------------------------------------------------------- world_crawler: fetches follow the shares
def order_picked(picked: list[Any], state: dict[str, Any] | None = None
                 ) -> tuple[list[Any], dict[str, Any]]:
    """Re-rank `wf.due()`'s pick so the registry's high-share hosts are fetched FIRST.

    The run stops on its clock, so the head of this list is the budget. A source the registry
    does not know keeps the mean factor of 1.0 and therefore keeps its original position among
    its equals -- python's sort is stable, so an unknown source is never pushed to the back and
    never dropped. A source carrying a licence, robots or "snippets only" note is CRAWLED with
    that note recorded as its label (LAWS 5e); the only removal left is one of the five refused
    acts of the hard boundary.
    """
    st = state if state is not None else load()
    meta: dict[str, Any] = {"status": st.get("status"), "why": st.get("why"),
                            "at": st.get("at"), "age_h": st.get("age_h"),
                            "n_ranked": 0, "n_unknown": 0, "n_refused": 0, "n_labelled": 0}
    if st.get("status") != "present" or not picked:
        return list(picked), meta
    rows: dict[str, Any] = st.get("rows") or {}
    scored: list[tuple[float, Any]] = []
    for src in picked:
        url = getattr(src, "url", None) or (src.get("url") if isinstance(src, dict) else None)
        host = getattr(src, "host", None) or (src.get("host") if isinstance(src, dict) else None)
        factor, sid = factor_for(st, url, host)
        allowed, why = machine_use_allowed(rows.get(sid) if sid else None)
        if not allowed:
            meta["n_refused"] += 1
            meta.setdefault("refused", []).append({"url": url, "why": why})
            continue
        if why != "mined":
            meta["n_labelled"] += 1
            meta.setdefault("labelled", []).append({"url": url, "terms_note": why})
        if sid is None:
            meta["n_unknown"] += 1
        else:
            meta["n_ranked"] += 1
        scored.append((factor, src))
    scored.sort(key=lambda t: -t[0])
    meta["top_factors"] = [round(f, 3) for f, _ in scored[:8]]
    return [s for _, s in scored], meta


# ------------------------------------------------------------------------ source expansion
def classify(url: str, anchor: str = "") -> str | None:
    """Which neighbourhood a link belongs to, or None when it is navigation."""
    text = str(url or "")
    if not text.startswith(("http://", "https://")):
        return None
    host = _host(text)
    if not host or any(p in host for p in _PLUMBING):
        return None
    for kind, rx in _NEIGH_RE:
        if rx.search(text):
            return kind
    if _TOPIC_RE.search(str(anchor or "")) or _TOPIC_RE.search(text):
        return "adjacent_topic"
    return None


def risen(state: dict[str, Any], prior: dict[str, float] | None = None
          ) -> dict[str, float]:
    """Sources whose published share is HIGHER than the last pass recorded.

    A source the desk has never recorded has a prior of 0.0, so its first positive share counts
    as a rise -- which is the honest reading: it went from nothing to something, and that is
    exactly the moment its neighbourhood is worth looking at.
    """
    was = prior if prior is not None else (_read_json(STATE, {}) or {}).get("shares") or {}
    out: dict[str, float] = {}
    for sid, cur in (state.get("shares") or {}).items():
        before = float(was.get(sid) or 0.0)
        if float(cur) > before + RISE_EPS:
            out[sid] = round(float(cur) - before, 10)
    return out


def expand(observations: dict[str, list[tuple[str, str]]], state: dict[str, Any] | None = None,
           grounds_path: Path | None = None, state_path: Path | None = None,
           apply: bool = True) -> dict[str, Any]:
    """Append candidate grounds for the neighbourhoods of sources whose share rose.

    `observations` maps a source key (its id, name, url or host -- whatever the crawler had in
    hand) to the `(url, anchor)` links that source actually served this pass. Nothing is invented:
    a neighbour must have been SEEN on a page the desk fetched, and its parent must be a source
    the registry prices. A parent carrying a terms/robots label mints its neighbours WITH that
    label copied onto them (LAWS 5e); only a parent on the hard boundary mints none.
    """
    gpath, spath = grounds_path or GROUNDS, state_path or STATE
    st = state if state is not None else load()
    meta: dict[str, Any] = {"status": st.get("status"), "why": st.get("why"),
                            "n_risen": 0, "n_candidates": 0, "n_appended": 0,
                            "n_refused": 0, "n_labelled": 0, "added": []}
    if st.get("status") != "present":
        return meta
    prior_doc = _read_json(spath, {}) or {}
    rose = risen(st, (prior_doc.get("shares") if isinstance(prior_doc, dict) else None))
    meta["n_risen"] = len(rose)

    cfg = _read_json(gpath, None)
    if not isinstance(cfg, dict) or not isinstance(cfg.get("grounds"), list):
        meta["why"] = f"{gpath.name} unreadable or carries no grounds list; nothing appended"
        return meta
    grounds: list[dict[str, Any]] = [g for g in cfg["grounds"] if isinstance(g, dict)]
    known = {str(g.get("url") or "").rstrip("/").lower() for g in grounds}
    known |= {str(a).rstrip("/").lower() for g in grounds for a in (g.get("alt") or [])}
    rows: dict[str, Any] = st.get("rows") or {}

    fresh: list[dict[str, Any]] = []
    for key, links in (observations or {}).items():
        sid = resolve(st, key)
        if sid is None or sid not in rose:
            continue
        raw = rows.get(sid)
        parent: dict[str, Any] = raw if isinstance(raw, dict) else {}
        allowed, why = machine_use_allowed(parent)
        if not allowed:
            meta["n_refused"] += 1
            meta.setdefault("refused", []).append({"source_id": sid, "why": why})
            continue
        if why != "mined":
            meta["n_labelled"] += 1
            meta.setdefault("labelled", []).append({"source_id": sid, "terms_note": why})
        taken = 0
        for url, anchor in links or ():
            if len(fresh) >= MAX_NEW_PER_PASS or taken >= MAX_NEW_PER_SOURCE:
                break
            kind = classify(url, anchor)
            meta["n_candidates"] += int(kind is not None)
            flat = str(url).rstrip("/").lower()
            if kind is None or flat in known:
                continue
            known.add(flat)
            taken += 1
            fresh.append({
                "name": f"{parent.get('name') or sid} :: {kind} :: {_host(url) or 'link'}",
                "region": parent.get("region") or "world",
                "language": parent.get("language") or "en",
                "route": "http", "kind": "code" if kind == "code" else "community",
                "weight": 1.0,
                "why": (f"SOURCE EXPANSION: {sid}'s ROI share rose by {rose[sid]:.6f}; this "
                        f"{kind} link was served by it. Candidate ground -- priced by "
                        f"source_registry like any other, never privileged for its parent."),
                "url": str(url),
                "neighbourhood": kind, "discovered_from": sid,
                "terms_note": "" if why == "mined" else why,
                "candidate": True,
                "added_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            })
    meta["n_appended"] = len(fresh)
    meta["added"] = [{"url": g["url"], "neighbourhood": g["neighbourhood"],
                      "from": g["discovered_from"]} for g in fresh]
    if not apply:
        meta["applied"] = False
        return meta
    if fresh:
        cfg["grounds"] = grounds + fresh
        _atomic(gpath, cfg)
    _atomic(spath, {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                    "shares": st.get("shares") or {},
                    "runs": int((prior_doc or {}).get("runs") or 0) + 1,
                    "appended_this_pass": len(fresh),
                    "rule": ("a source whose ROI share rises has its observed neighbourhood "
                             "registered as candidate grounds; the registry prices them next")})
    meta["applied"] = True
    return meta
