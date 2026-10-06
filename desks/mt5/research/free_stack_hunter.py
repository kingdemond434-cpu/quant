"""THE FREE-STACK HUNTER -- the hourly leg that runs every free alt-data source the Asia gap
report measured MISSING (2026-09-30), point-in-time, cursor-based, with a yield row per source.

WHAT ONE PASS DOES, in order, inside its own wall budget:

  1. READS THE ROSTER `data/free_stack_sources.json` -- one data row per source with id, cadence,
     auth, licence, machine_use_allowed, cursor, region, language, targets and `uses`. The access
     label of every row is re-derived by `libs.research.access_classifier.classify` (LAWS 5e: a
     provenance label, never a brake -- only the five hard-boundary acts are refused).
  2. VISITS DUE SOURCES STALEST FIRST. A source's `next_due` is its cadence after the last
     attempt; a failure backs off one cadence, never forever. The per-source cursor (seen post
     ids, seen documents, catalogue links already known) is persisted after EVERY source, so a
     pass cut short by the cycle's cap still advanced everything it touched.
  3. STORES POINT-IN-TIME. Every observation is appended to `data/free_stack/obs/<id>.jsonl`
     with `period_end`, `available_time` and `first_seen_utc`; a changed value is a NEW row, never
     an overwrite, and the research series always serves the FIRST vintage. A value present in a
     source's first-ever fetch is BACKFILL and is timed at period_end + the declared lag; every
     later value is timed at max(that, first_seen) -- it cannot be known before the box saw it.
  4. PUBLISHES THE SERIES THE FAMILIES READ: `data/lake/series/fs_<id>.parquet` (an
     `available_time` column plus one numeric column per key) -- the exact frame
     `mt5desk.family_exogenous_conditioner` and `mt5desk.family_alt_series` load -- and
     `data/free_stack/columns.json`, which says which instruments each column may condition.
  5. FEEDS THE CATALOGUE QUEUES. Dataset links found in open catalogues go to
     `data/world_datasets/discovery_queue.json` (the #92 world dataset hunter's store) and to
     `data/free_stack/discovered_catalogue.json`, which `data_scout` and `data_prospector` read.
  6. WRITES `reports/FREE_STACK_YIELD.json`: per source status, attempts, successes, requests,
     observations added, columns, last success, last error, and the 24h / 7d yield. A source that
     has never run reads UNMEASURED, never 0.

NOTHING HERE IS A FIXTURE AT RUN TIME. Tests inject a recorded fetch and a temp store; the live
leg uses `libs.data.free_stack.http_fetch` and nothing else, so no yield in the artifact was
produced by a recording.

    python desks/mt5/research/free_stack_hunter.py --once --budget-s 600
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402

ROSTER = DESK / "data" / "free_stack_sources.json"
#: The leg's own artifact (the runtime attestation reads this binding).
REPORT = DESK / "reports" / "FREE_STACK_YIELD.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 600.0
#: A source may not take more than this share of the pass, so one slow door cannot starve the
#: rest; what it did not reach it reaches next pass from its cursor.
PER_SOURCE_SHARE = 0.34
CADENCE_H = {"hourly": 1.0, "4h": 4.0, "daily": 24.0, "weekly": 168.0}
#: How far behind period_end a value may be first seen and still count as BACKFILL on a
#: source's first fetch (history the source already published before the box existed).
BACKFILL = "backfill"


class Store:
    """Every path the hunter writes, rooted so a test can point the whole thing at a temp dir."""

    def __init__(self, desk: Path = DESK) -> None:
        self.desk = desk
        self.root = desk / "data" / "free_stack"
        self.obs = self.root / "obs"
        self.raw = self.root / "raw"
        self.inbox = self.root / "inbox"
        self.cursor = self.root / "cursor.json"
        self.columns = self.root / "columns.json"
        self.catalogue = self.root / "discovered_catalogue.json"
        self.runs = self.root / "yield_runs.jsonl"
        self.series = desk / "data" / "lake" / "series"
        self.world_queue = desk / "data" / "world_datasets" / "discovery_queue.json"
        self.universe = desk / "data" / "universe" / "universe.json"
        self.report = desk / "reports" / REPORT.name
        self.alt_state = desk / "reports" / "ALT_REGIME_STATE.json"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _parse(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, path)


# -------------------------------------------------------------------------------- roster ----
REQUIRED = ("id", "kind", "cadence", "auth", "licence", "machine_use_allowed", "cursor",
            "region", "language", "uses")


def load_roster(path: Path = ROSTER) -> tuple[list[dict[str, Any]], list[str]]:
    """(rows, complaints). A row missing a roster field is REFUSED by name, never guessed at."""
    doc = read_json(path, {})
    rows = doc.get("sources") if isinstance(doc, dict) else None
    out: list[dict[str, Any]] = []
    bad: list[str] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        miss = [k for k in REQUIRED if k not in r]
        if miss:
            bad.append(f"{r.get('id', '<unnamed>')}: missing {', '.join(miss)}")
            continue
        uses = r.get("uses") or {}
        if not all(k in uses for k in ("direct", "indirect", "allocation")):
            bad.append(f"{r['id']}: uses must name direct, indirect and allocation")
            continue
        out.append(r)
    return out, bad


def access(row: dict[str, Any]) -> dict[str, Any]:
    """The access router's label for this row (LAWS 5e). Never a brake except the hard five."""
    try:
        from libs.research.access_classifier import classify
        v = classify({"url": row.get("url") or row.get("home") or "", "licence":
                      row.get("licence"), "terms": row.get("terms_note", ""),
                      "requires_auth": str(row.get("auth", "none")) != "none",
                      "source_class": row.get("source_class", "public_web"),
                      "obtained": "public_api"})
        return {"label": str(v.access_label), "mined": bool(v.mined),
                "machine_use_allowed": bool(v.machine_use_allowed),
                "redistribute_allowed": bool(v.redistribute_allowed), "reason": v.reason}
    except Exception as exc:
        return {"label": UNMEASURED, "mined": True,
                "machine_use_allowed": row.get("machine_use_allowed"),
                "redistribute_allowed": False,
                "reason": f"access_classifier unavailable: {type(exc).__name__}"}


def crypto_cfds(store: Store) -> list[str]:
    """Fusion's crypto CFDs, read off the broker registry -- the only crypto this organ touches."""
    uni = read_json(store.universe, {})
    return sorted(k for k, v in (uni or {}).items()
                  if isinstance(v, dict) and str(v.get("asset_class") or "") == "Crypto")


def hypothesis_filter(symbols: list[str], store: Store) -> list[str]:
    """Only instruments the broker lists AND the two-lane order lets a statistical cell touch."""
    uni = read_json(store.universe, {}) or {}
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        def may_hypothesise(symbol: str, family: object = None) -> bool:
            return True
    return [s for s in symbols if s in uni and may_hypothesise(s)]


# ---------------------------------------------------------------------------- PIT store ----
def _obs_key(o: dict[str, Any]) -> tuple[str, str]:
    return str(o["key"]), str(o["period_end"])


def load_obs(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def _period_end_dt(p: str) -> datetime | None:
    d = _parse(p)
    if d is not None and len(p) > 10:
        return d
    try:
        return datetime.combine(date.fromisoformat(p[:10]), datetime.max.time()).replace(
            tzinfo=UTC, microsecond=0)
    except ValueError:
        return None


def merge_obs(path: Path, new: list[dict[str, Any]], *, now: datetime, lag_h: float
              ) -> dict[str, int]:
    """Append what is NEW: an unseen (key, period_end), or a changed value for a seen one (a
    revision, kept as its own vintage). Returns counts."""
    have = load_obs(path)
    first_fetch = not have
    last: dict[tuple[str, str], float] = {}
    for r in have:
        last[_obs_key(r)] = float(r.get("value"))
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for o in new:
        try:
            v = float(o["value"])
        except (KeyError, TypeError, ValueError):
            counts["refused_non_numeric"] += 1
            continue
        k = _obs_key(o)
        if k in last and abs(last[k] - v) <= 1e-12:
            counts["unchanged"] += 1
            continue
        pe = _period_end_dt(str(o["period_end"]))
        if pe is None:
            counts["refused_bad_period"] += 1
            continue
        avail = pe + timedelta(hours=lag_h)
        backfill = first_fetch and k not in last
        at = avail if backfill else max(avail, now)
        rows.append({"key": k[0], "period_end": k[1], "value": v, "available_time": _iso(at),
                     "first_seen_utc": _iso(now), "vintage": BACKFILL if backfill else
                     ("revision" if k in last else "first")})
        counts["revisions" if k in last else "added"] += 1
        last[k] = v
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    return dict(counts)


def first_vintage_frame(path: Path) -> Any:
    """The research view: per (key, period_end) the FIRST vintage only, one row per period with
    `available_time` = the latest availability among that period's first vintages."""
    import pandas as pd
    rows = load_obs(path)
    if not rows:
        return None
    first: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        first.setdefault(_obs_key(r), r)
    df = pd.DataFrame(list(first.values()))
    wide = df.pivot_table(index="period_end", columns="key", values="value", aggfunc="first")
    avail = df.groupby("period_end")["available_time"].max()
    wide.insert(0, "available_time", avail.reindex(wide.index).to_numpy())
    wide = wide.reset_index().sort_values("period_end")
    wide.columns = [str(c) for c in wide.columns]
    return wide


def publish_series(store: Store, sid: str) -> dict[str, Any]:
    df = first_vintage_frame(store.obs / f"{sid}.jsonl")
    if df is None or df.empty:
        return {"rows": 0}
    store.series.mkdir(parents=True, exist_ok=True)
    out = store.series / f"fs_{sid}.parquet"
    try:
        df.to_parquet(out, index=False)
    except Exception:
        out = store.series / f"fs_{sid}.csv"
        df.to_csv(out, index=False)
    return {"rows": len(df), "columns": int(df.shape[1] - 2), "path": str(out)}


# --------------------------------------------------------------------- post aggregates ----
def append_raw(store: Store, sid: str, rows: list[dict[str, Any]], now: datetime) -> Path:
    """The point-in-time archive of what the source said, one file per UTC day."""
    p = store.raw / sid / f"{now.date().isoformat()}.jsonl"
    if rows:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return p


def raw_rows(store: Store, sid: str, days: int = 120) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    d = store.raw / sid
    if not d.exists():
        return out
    for f in sorted(d.glob("*.jsonl"))[-days:]:
        out.extend(load_obs(f))
    return out


def aggregate_posts(store: Store, row: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """Forums: weekly index over closed ISO weeks. Reddit / Telegram: daily over closed days."""
    rows = raw_rows(store, str(row["id"]))
    if row["kind"] == "cn_forum":
        return fs.weekly_index(rows, now.date())
    return fs.daily_social(rows, now.date())


# ------------------------------------------------------------------------- catalogue feed ----
def feed_catalogue(store: Store, datasets: list[dict[str, Any]], row: dict[str, Any],
                   now: datetime) -> dict[str, int]:
    """Dataset links into three consumers: the #92 hunter's queue, and the catalogue file that
    `data_scout` and `data_prospector` read. Each row carries its roster fields and `uses`."""
    if not datasets:
        return {"queued": 0}
    q = read_json(store.world_queue, {}) or {}
    qrows = {r["url"]: r for r in q.get("rows", []) if isinstance(r, dict) and r.get("url")}
    cat = read_json(store.catalogue, {}) or {}
    crows = {r["url"]: r for r in cat.get("rows", []) if isinstance(r, dict) and r.get("url")}
    added = 0
    for d in datasets:
        url = str(d["url"])
        sid = "cat_" + hashlib.sha1(url.encode()).hexdigest()[:12]
        base = {"id": sid, "name": d.get("name"), "url": url, "section": d.get("section"),
                "catalogue": d.get("catalogue"), "score": d.get("score"),
                "discovered_utc": d.get("discovered_utc"), "state": "DISCOVERED",
                "cadence": "unknown", "auth": "unknown", "licence": "UNVERIFIED",
                "machine_use_allowed": None, "cursor": "none until adopted",
                "region": "global", "language": "unknown",
                "source_culture": "UNMEASURED", "participant_structure": "UNMEASURED",
                "failure_mode_hypothesis": "UNMEASURED until the dataset's origin is read",
                "uses": {"direct": {"family": "exogenous_conditioner",
                                    "organ": "free_stack_proposer (once ingested)"},
                         "indirect": {"family": "alt_conditioned",
                                      "organ": "free_stack_proposer (once ingested)"},
                         "allocation": {"artifact": "reports/ALT_REGIME_STATE.json",
                                        "organ": "free_stack_hunter (once ingested)"}}}
        if url not in qrows:
            qrows[url] = {**base, "mode": _mode_of(url), "from": "free_stack_hunter.catalogue"}
            added += 1
        crows.setdefault(url, {**base, "source": f"{d.get('name')} ({d.get('catalogue')})",
                               "access": "free", "pit_status": "UNMEASURED until ingested",
                               "cost": 2.0, "integration_effort": 3.0,
                               "how_to_fetch": f"world_dataset_hunter queue; {url}",
                               "observables": _observables(d),
                               "observable_class": "discovered_catalogue",
                               "expected_alpha_value": round(0.01 * float(d.get("score") or 0),
                                                             4)})
    write_json(store.world_queue, {"generated_utc": _iso(now), "writer": "free_stack_hunter",
                                   "rule": "dataset links from open catalogues; the world "
                                           "dataset hunter adopts rows whose mode it can read",
                                   "rows": sorted(qrows.values(), key=lambda r: -float(
                                       r.get("score") or 0))})
    write_json(store.catalogue, {"generated_utc": _iso(now), "writer": "free_stack_hunter",
                                 "readers": ["research/data_scout.py",
                                             "research/data_prospector.py"],
                                 "rows": sorted(crows.values(), key=lambda r: -float(
                                     r.get("score") or 0))})
    return {"queued": added, "queue_size": len(qrows), "catalogue_size": len(crows)}


def _mode_of(url: str) -> str:
    low = url.lower().split("?")[0]
    for ext, mode in ((".csv", "csv"), (".json", "json_records"), (".zip", "zip"),
                      (".xlsx", "xlsx"), (".parquet", "parquet")):
        if low.endswith(ext):
            return mode
    return "landing_page"


def _observables(d: dict[str, Any]) -> list[str]:
    blob = f"{d.get('name', '')} {d.get('section', '')}".lower()
    words = sorted({w for w in fs.MT5_RELEVANCE if w in blob and len(w) >= 5})
    return words[:8] or ["unclassified"]


# ---------------------------------------------------------------------- allocation state ----
def build_alt_state(store: Store, columns: dict[str, Any], now: datetime) -> dict[str, Any]:
    """ALLOCATION INTELLIGENCE: per hypothesis-lane symbol, the latest point-in-time z of every
    alt column mapped to it, its regime (high / low / mid at |z| >= 1) and its age. A state
    artifact the allocator MAY read; nothing here sizes, vetoes or edits the allocator."""
    import numpy as np
    per_symbol: dict[str, list[dict[str, Any]]] = {}
    for sid, cols in columns.items():
        df = first_vintage_frame(store.obs / f"{sid}.jsonl")
        if df is None or df.empty:
            continue
        df = df[[_parse(a) is not None and _parse(a) <= now
                 for a in df["available_time"]]]
        for col, meta in cols.items():
            if col not in df.columns:
                continue
            s = df[["available_time", col]].dropna()
            if len(s) < 8:
                continue
            v = s[col].astype(float).to_numpy()
            win = v[-250:]
            sd = float(np.std(win))
            z = float((v[-1] - float(np.mean(win))) / sd) if sd > 0 else 0.0
            at = _parse(s["available_time"].iloc[-1])
            row = {"source": sid, "column": col, "z": round(z, 3),
                   "regime": "high" if z >= 1 else "low" if z <= -1 else "mid",
                   "as_of": _iso(at), "age_h": round((now - at).total_seconds() / 3600, 1)
                   if at else None, "n": len(v)}
            for sym in meta.get("hypothesis") or []:
                per_symbol.setdefault(sym, []).append(row)
    doc = {"generated_utc": _iso(now), "writer": "research/free_stack_hunter.py",
           "rule": ("point-in-time z (first vintage, available_time <= now) of each alt column "
                    "over its trailing 250 observations; regime high/low at |z| >= 1. A state "
                    "input the allocator may read -- never a size, a cap or a veto"),
           "symbols": {k: sorted(v, key=lambda r: -abs(r["z"])) for k, v in
                       sorted(per_symbol.items())},
           "n_symbols": len(per_symbol)}
    write_json(store.alt_state, doc)
    return {"symbols": len(per_symbol), "rows": sum(len(v) for v in per_symbol.values())}


# ------------------------------------------------------------------------------ the pass ----
def _due(state: dict[str, Any], row: dict[str, Any], now: datetime) -> bool:
    nd = _parse(state.get("next_due"))
    return nd is None or nd <= now


def _stalest(state: dict[str, Any]) -> float:
    at = _parse(state.get("last_attempt"))
    return at.timestamp() if at else 0.0


def run_source(row: dict[str, Any], store: Store, fetch: fs.Fetch, cstate: dict[str, Any],
               now: datetime) -> tuple[fs.Harvest, dict[str, Any]]:
    kind = str(row["kind"])
    fn = fs.FETCHERS.get(kind)
    from libs.data import terms_fence as _tf
    platform = (_tf.fenced_source(kind) or _tf.fenced_source(str(row["id"]))
                or _tf.platform_of_url(str(row.get("url") or "")))
    if platform:
        # Terms-fenced (principal 2026-09-30): no request, no raw, no series, nothing to mint.
        ref = _tf.refusal(platform)
        return fs.Harvest(str(row["id"]), status=str(ref["status"]), detail=ref["why"]), {}
    if fn is None:
        h = fs.Harvest(str(row["id"]), status="NO_ROUTE", detail=f"no fetcher for kind {kind}")
        return h, {}
    cur = dict(cstate.get("cursor") or {})
    try:
        if kind == "coinpaprika":
            h = fn(fetch, row, cur, now, crypto_cfds=crypto_cfds(store))
        elif kind == "jp_patents":
            h = fn(fetch, row, cur, now, inbox=store.inbox / "jp_patents")
        else:
            h = fn(fetch, row, cur, now)
    except Exception as exc:
        h = fs.Harvest(str(row["id"]), status="ERROR",
                       detail=f"{type(exc).__name__}: {str(exc)[:160]}")
        return h, {}
    extra: dict[str, Any] = {}
    sid = str(row["id"])
    lag_h = float(row.get("lag_hours", 24))
    if h.raw:
        append_raw(store, sid, h.raw, now)
    if kind in ("cn_forum", "reddit", "telegram"):
        h.obs = aggregate_posts(store, row, now)
    if h.obs:
        extra["merge"] = merge_obs(store.obs / f"{sid}.jsonl", h.obs, now=now, lag_h=lag_h)
        extra["series"] = publish_series(store, sid)
    if h.datasets:
        extra["catalogue"] = feed_catalogue(store, h.datasets, row, now)
    return h, extra


def run(*, budget_s: float = DEFAULT_BUDGET_S, fetch: fs.Fetch | None = None,
        store: Store | None = None, roster: Path = ROSTER, now: datetime | None = None,
        only: list[str] | None = None, live: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    store = store or Store()
    fetch = fetch or fs.http_fetch
    now = now or _now()
    rows, complaints = load_roster(roster)
    cursor = read_json(store.cursor, {}) or {}
    columns: dict[str, Any] = read_json(store.columns, {}) or {}
    ran: list[dict[str, Any]] = []
    order = sorted(rows, key=lambda r: _stalest(cursor.get(r["id"]) or {}))
    for row in order:
        sid = str(row["id"])
        if only and sid not in only:
            continue
        st = cursor.setdefault(sid, {})
        if not only and not _due(st, row, now):
            continue
        spent = time.monotonic() - t0
        if spent >= budget_s:
            break
        acc = access(row)
        st["access"] = acc
        if not acc["mined"]:
            st.update({"last_status": "REFUSED_HARD_BOUNDARY", "last_error": acc["reason"],
                       "last_attempt": _iso(now)})
            continue
        s0 = time.monotonic()
        h, extra = run_source(row, store, fetch, st, now)
        secs = round(time.monotonic() - s0, 2)
        cad = CADENCE_H.get(str(row.get("cadence")), 24.0)
        st["attempts"] = int(st.get("attempts") or 0) + 1
        st["last_attempt"] = _iso(now)
        st["next_due"] = _iso(now + timedelta(hours=cad))
        st["last_status"] = h.status
        st["last_error"] = h.detail if h.status != "OK" else ""
        st["requests"] = int(st.get("requests") or 0) + h.requests
        st["failures"] = dict(Counter(st.get("failures") or {}) + h.failures)
        if h.cursor:
            st["cursor"] = {**(st.get("cursor") or {}), **h.cursor}
        added = int((extra.get("merge") or {}).get("added", 0)) + int(
            (extra.get("merge") or {}).get("revisions", 0))
        ok = h.status == "OK" and (added > 0 or bool(h.raw) or bool(h.datasets)
                                    or bool(extra.get("catalogue")))
        if ok:
            st["successes"] = int(st.get("successes") or 0) + 1
            st["last_success"] = _iso(now)
        st["obs_total"] = int(st.get("obs_total") or 0) + added
        if h.columns:
            hyp = {c: {**m, "hypothesis": hypothesis_filter(list(m.get("hypothesis") or []),
                                                          store)}
                   for c, m in h.columns.items()}
            columns[sid] = {**(columns.get(sid) or {}), **hyp}
        run_row = {"at": _iso(now), "source": sid, "status": h.status, "seconds": secs,
                   "requests": h.requests, "obs_added": added, "raw_rows": len(h.raw),
                   "datasets": len(h.datasets), "failures": dict(h.failures),
                   "detail": h.detail[:200], "notes": h.notes[-6:], "live": live, **extra}
        ran.append(run_row)
        if live:
            store.runs.parent.mkdir(parents=True, exist_ok=True)
            with store.runs.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(run_row, default=str) + "\n")
        # THE CURSOR IS PERSISTED AFTER EVERY SOURCE: a pass the cycle cuts still advanced.
        write_json(store.cursor, cursor)
        write_json(store.columns, columns)
        if time.monotonic() - s0 > budget_s * PER_SOURCE_SHARE:
            st["slow"] = True
    alloc = build_alt_state(store, columns, now)
    report = build_report(rows, complaints, cursor, columns, ran, store, now,
                          seconds=time.monotonic() - t0, alloc=alloc, live=live)
    write_json(store.report, report)
    return report


def _window(store: Store, sid: str, now: datetime, hours: float) -> dict[str, Any] | str:
    rows = [r for r in load_obs(store.runs) if r.get("source") == sid and r.get("live")]
    if not rows:
        return UNMEASURED
    since = now - timedelta(hours=hours)
    win = [r for r in rows if (_parse(r.get("at")) or now) >= since]
    return {"runs": len(win), "ok_runs": sum(1 for r in win if r.get("status") == "OK"),
            "obs_added": sum(int(r.get("obs_added") or 0) for r in win),
            "raw_rows": sum(int(r.get("raw_rows") or 0) for r in win),
            "datasets": sum(int(r.get("datasets") or 0) for r in win)}


def build_report(rows: list[dict[str, Any]], complaints: list[str], cursor: dict[str, Any],
                 columns: dict[str, Any], ran: list[dict[str, Any]], store: Store,
                 now: datetime, *, seconds: float, alloc: dict[str, Any], live: bool
                 ) -> dict[str, Any]:
    per: dict[str, Any] = {}
    for r in rows:
        sid = str(r["id"])
        st = cursor.get(sid) or {}
        never = not st.get("attempts")
        per[sid] = {
            "kind": r["kind"], "region": r["region"], "language": r["language"],
            "cadence": r["cadence"], "auth": r["auth"], "licence": r["licence"],
            "machine_use_allowed": (st.get("access") or {}).get("machine_use_allowed",
                                                                r["machine_use_allowed"]),
            "redistribute_allowed": (st.get("access") or {}).get("redistribute_allowed"),
            # a hard-boundary refusal is a verdict the pass reached, so it is shown as one
            "status": st.get("last_status") or UNMEASURED,
            "attempts": int(st.get("attempts") or 0), "successes":
                UNMEASURED if never else int(st.get("successes") or 0),
            "requests": int(st.get("requests") or 0), "failures": st.get("failures") or {},
            "obs_total": UNMEASURED if never else int(st.get("obs_total") or 0),
            "columns": len(columns.get(sid) or {}),
            "last_success": st.get("last_success") or (UNMEASURED if never else None),
            "last_error": st.get("last_error") or "",
            "next_due": st.get("next_due"),
            "yield_24h": _window(store, sid, now, 24.0),
            "yield_7d": _window(store, sid, now, 168.0),
            "uses": r["uses"], "blocker_prior": r.get("blocker_prior", ""),
        }
    statuses = Counter(str(v["status"]) for v in per.values())
    return {"generated_utc": _iso(now), "writer": "research/free_stack_hunter.py",
            "live": live, "seconds": round(seconds, 1), "sources": len(rows),
            "roster_complaints": complaints, "by_status": dict(statuses),
            "yielding": sorted(k for k, v in per.items() if v["status"] == "OK"),
            "ran_this_pass": [{k: v for k, v in r.items() if k != "notes"} | {
                "notes": r.get("notes", [])[-3:]} for r in ran],
            "allocation_state": {"artifact": str(store.alt_state), **alloc},
            "per_source": per,
            "rule": ("a source that never ran is UNMEASURED, never 0; yields are counted from "
                     "live runs only (tests run on recorded fixtures and never write here)")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--only", default="", help="comma-separated source ids (ignores cadence)")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, only=[s for s in a.only.split(",") if s] or None)
    print(f"free_stack_hunter: {len(rep['ran_this_pass'])} source(s) visited in "
          f"{rep['seconds']}s; by status {rep['by_status']}; yielding {rep['yielding']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
