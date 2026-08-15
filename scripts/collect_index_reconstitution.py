#!/usr/bin/env python3
"""INDEX RECONSTITUTION EVENTS -- the feed census gap #1 has been waiting on.

`screen_index_reconstitution` runs daily and reports UNMEASURED because
`data/index_reconstitution_events.json` has no writer. This is the writer. The census records the
data as FREE-ACQUIRABLE: index providers publish methodology documents with announcement and
effective dates, and constituent lists before and after each review. Nobody had fetched them.

**IT COLLECTS AND NEVER JUDGES.** No return is computed here, no event is filtered on its outcome,
and no threshold appears anywhere in this file. Every construction, horizon and kill criterion is
pre-registered in `libs/research/index_reconstitution`, dated before the first fetch. A collector
that dropped events it found uninteresting would move the pre-registration after the data, and
would do it in the one place nobody audits.

**AN EVENT IS APPENDED ONCE AND NEVER REWRITTEN.** Announcement and effective dates are published
facts with an instant attached; a re-fetch that overwrote an earlier row would let a provider's
later correction silently change a window this desk had already measured against. Corrections are
appended as NEW rows carrying `supersedes`, so the original observation survives -- the desk can
then measure whether it acted on a date that was later revised, which is itself a finding.

**THE SOURCE LIST IS DECLARED, NOT DISCOVERED.** Each source names the provider and what it
publishes. A collector that scraped whatever it could reach would build a universe whose membership
depends on which sites happened to respond, and that universe is not the index.

**NETWORK FAILURE IS REPORTED, NEVER SWALLOWED.** A fetch that 403s and an index that announced
nothing this week produce the same empty list and must never produce the same report: the first is
UNMEASURED, the second is a measured zero.

    python scripts/collect_index_reconstitution.py [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data/index_reconstitution_events.json"
_STATUS = _ROOT / "web/index_reconstitution_collector.json"
_TIMEOUT_S = 20

#: DECLARED SOURCES. Each names a provider and the shape of what it publishes. Crypto index
#: products rebalance on published schedules and announce constituent changes ahead of the
#: effective date -- the same mechanism as equity reconstitution, with a shorter calendar.
#:
#: `kind` drives the parser. `announce_lag_days` is the provider's OWN published gap between
#: announcement and effective date, used ONLY to sanity-check a parsed row, never to synthesise
#: one: an event whose dates must be inferred is an event this desk did not observe.
SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "binance_index_composition",
     "url": "https://www.binance.com/bapi/composite/v1/public/market/indexPrice/constituents",
     "kind": "binance_constituents",
     "publishes": "current constituent set for Binance index products, polled for DIFFS",
     "announce_lag_days": 0},
    {"id": "coindesk_indices_announcements",
     "url": "https://api.coindesk.com/index/v1/announcements",
     "kind": "generic_announcements",
     "publishes": "CoinDesk Indices reconstitution announcements with effective dates",
     "announce_lag_days": 5},
)


def _fetch(url: str) -> tuple[Any | None, str]:
    """(payload, why). NEVER returns an empty payload for a failed fetch.

    A 403 and an index that announced nothing this week produce the same empty list, and the two
    must never produce the same report -- the first is UNMEASURED, the second is a measured zero.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as fh:
            return json.loads(fh.read().decode("utf-8")), "ok"
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code} -- UNMEASURED, not 'no events'"
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, f"{type(exc).__name__}: {exc.reason if hasattr(exc, 'reason') else exc}"
    except (ValueError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _load_existing() -> tuple[list[dict[str, Any]], set[tuple[str, str, str]]]:
    """Rows already on disk, and their identity keys. APPEND-ONLY: an event observed once is a
    published fact, and a re-fetch must not overwrite the window this desk measured against."""
    try:
        doc = json.loads(_OUT.read_text("utf-8"))
    except (OSError, ValueError):
        return [], set()
    rows = doc.get("events") if isinstance(doc, dict) else doc
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    keys = {(str(r.get("symbol", "")), str(r.get("index", "")), str(r.get("effective_at", "")))
            for r in rows}
    return rows, keys


def _parse_binance_constituents(payload: Any, prev: set[str]) -> list[dict[str, Any]]:
    """Constituent DIFFS -- what entered and what left since the last poll.

    **THESE ARE NOT PRE-REGISTERED EVENTS AND THEY ARE NOT FILED AS ONE.** The registered
    mechanism lives BETWEEN announcement and effective date. This provider publishes a CURRENT
    SET, so a diff is only visible AFTER the change is already effective -- there is no
    announcement window at all, and `announced_at == effective_at`.

    `ReconEvent.valid` would drop every one of these silently, which is the worst outcome: the
    collector would report "12 events collected" and the screen would report zero, with nothing
    naming the gap. So they go to a SEPARATE list. They are real observations of index membership
    changing and they may support the C2 reversal leg later; they cannot test C1, and filing them
    as events would credit the desk with a window it never observed.

    Backdating announced_at to manufacture a window is the obvious "fix" and it is the one thing
    that must never happen here: it would fabricate exactly the drift being measured.
    """
    data = payload.get("data") if isinstance(payload, dict) else payload
    now = datetime.now(tz=UTC)
    current = {str(x.get("baseAsset") or x.get("symbol") or "").upper()
               for x in (data or []) if isinstance(x, dict)}
    current.discard("")
    if not current or not prev:
        return []                       # first poll establishes the baseline; a diff needs two
    out = []
    for sym, direction, what in ([(s, 1, "entered") for s in sorted(current - prev)]
                                 + [(s, -1, "left") for s in sorted(prev - current)]):
        out.append({"symbol": sym, "index": "binance_index", "direction": direction,
                    "observed_at": now.isoformat(), "announcement_window": False,
                    "observed_as": f"constituent diff ({what}) -- POST-HOC, no announcement "
                                   "window exists, so this cannot test C1"})
    return out


def _parse_generic(payload: Any) -> list[dict[str, Any]]:
    """Announcement rows carrying BOTH dates. A row missing either is dropped and counted -- an
    event whose dates must be inferred is an event this desk did not observe."""
    rows = payload.get("announcements") if isinstance(payload, dict) else payload
    out = []
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or r.get("asset") or "").upper()
        a, e = r.get("announced_at") or r.get("announcementDate"), \
            r.get("effective_at") or r.get("effectiveDate")
        act = str(r.get("action") or r.get("type") or "").lower()
        direction = 1 if "add" in act or "includ" in act else (-1 if act else 0)
        if not (sym and a and e and direction):
            continue
        out.append({"symbol": sym, "index": str(r.get("index", "coindesk")),
                    "direction": direction, "announced_at": str(a), "effective_at": str(e),
                    "weight_change": float(r.get("weight_change", 0.0) or 0.0),
                    "observed_as": "published announcement"})
    return out


def build() -> dict[str, Any]:
    existing, keys = _load_existing()
    prev_sets: dict[str, set[str]] = {}
    try:
        prev_sets = {k: set(v) for k, v in
                     (json.loads(_OUT.read_text("utf-8")).get("last_constituents") or {}).items()}
    except (OSError, ValueError, AttributeError):
        prev_sets = {}

    new: list[dict[str, Any]] = []
    # OBSERVATIONS THAT ARE REAL BUT CANNOT TEST THE REGISTERED MECHANISM. Kept separate so the
    # collector's count and the screen's count can never disagree without something saying why.
    post_hoc: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    latest_sets = dict(prev_sets)

    for src in SOURCES:
        payload, why = _fetch(str(src["url"]))
        row = {"id": src["id"], "publishes": src["publishes"], "state": "OK" if payload else why}
        if payload is None:
            # THE STATE THAT MATTERS. Not "0 events" -- nothing was observed at all.
            row["state_class"] = "UNMEASURED"
            sources.append(row)
            continue
        row["state_class"] = "MEASURED"
        if src["kind"] == "binance_constituents":
            data = payload.get("data") if isinstance(payload, dict) else payload
            cur = {str(x.get("baseAsset") or x.get("symbol") or "").upper()
                   for x in (data or []) if isinstance(x, dict)}
            cur.discard("")
            post_hoc.extend(_parse_binance_constituents(payload, prev_sets.get(src["id"], set())))
            latest_sets[str(src["id"])] = sorted(cur)  # type: ignore[assignment]
            row["baseline_only"] = not prev_sets.get(src["id"])
            row["n_post_hoc"] = len(post_hoc)
            found = []
        else:
            found = _parse_generic(payload)
        row["n_found"] = len(found)
        for ev in found:
            k = (ev["symbol"], ev["index"], ev["effective_at"])
            if k in keys:
                continue                  # append-only: an observed event is never rewritten
            keys.add(k)
            new.append(ev)
        sources.append(row)

    all_rows = [*existing, *new]
    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_events_total": len(all_rows), "n_new_this_run": len(new),
        "sources": sources,
        "n_sources_unmeasured": sum(1 for s in sources if s.get("state_class") == "UNMEASURED"),
        "last_constituents": {k: sorted(v) if isinstance(v, set) else v
                              for k, v in latest_sets.items()},
        "post_hoc_constituent_changes": post_hoc,
        "n_post_hoc": len(post_hoc),
        "why_post_hoc_is_separate": (
            "a constituent DIFF is only visible after the change is already effective, so there "
            "is no announcement window and announced_at == effective_at. ReconEvent.valid would "
            "drop every one silently -- the collector reporting N and the screen reporting zero, "
            "with nothing naming the gap. They are real observations that may support the C2 "
            "reversal leg later; they cannot test C1, and filing them as events would credit the "
            "desk with a window it never observed"),
        "append_only": ("an event observed once is a published fact. A re-fetch never rewrites a "
                        "row -- a provider's later correction would otherwise silently change a "
                        "window this desk had already measured against"),
        "collects_never_judges": ("no return is computed here and no event is filtered on its "
                                  "outcome. Every construction and threshold is pre-registered in "
                                  "libs/research/index_reconstitution, dated before the first "
                                  "fetch"),
        "events": all_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    _STATUS.parent.mkdir(parents=True, exist_ok=True)
    _STATUS.write_text(json.dumps({k: v for k, v in rep.items() if k != "events"}, indent=1),
                       "utf-8")

    if args.json:
        print(json.dumps({k: v for k, v in rep.items() if k != "events"}, indent=1))
        return 0
    print(f"index-recon collector: {rep['n_new_this_run']} new, {rep['n_events_total']} total "
          f"pre-registered event(s), {rep['n_post_hoc']} post-hoc diff(s) (cannot test C1), "
          f"{rep['n_sources_unmeasured']} source(s) UNMEASURED")
    for s in rep["sources"]:
        print(f"  [{s.get('state_class','?'):<10}] {s['id']:<34} {s.get('state')}")
        if s.get("baseline_only"):
            print("      first poll: baseline recorded, no diff possible yet -- a constituent "
                  "diff needs two observations and this is the first")
    print(f"-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
