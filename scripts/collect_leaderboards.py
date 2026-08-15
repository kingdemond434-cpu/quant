#!/usr/bin/env python3
"""PUBLIC TRADER LEADERBOARDS -> A FORWARD PANEL. Binance and Hyperliquid, daily, append-only.

WHY THIS EXISTS. III.15 makes leaderboard forensics a standing mandate and `screen_copytrading`
implements it for ONE venue (OKX copytrading). Binance's futures leaderboard and Hyperliquid's
per-account feed -- which `FREE_DATA_ADDENDA` C3 #54 calls the most complete free positioning
dataset in crypto, public by design -- were in scope and collected by nothing.

**THE ONLY THING WORTH COLLECTING IS TIME.** A leaderboard read once is worthless: it is the
maximum of a very large number of draws, shown without its denominator, and every statistic
computed on it is computed on a sample selected for the outcome being measured. A leaderboard read
DAILY, with the same identifiers, becomes a forward panel in which disappearance is data. That is
the entire value proposition here and it is why this runs on a schedule or not at all.

**THE ENDPOINTS ARE UNOFFICIAL AND THIS FILE SAYS SO OUT LOUD.** Binance's leaderboard is a `bapi`
route behind its web front end, not a documented API: it can change shape or vanish without notice,
and it is rate-limited by an unpublished policy. So every venue carries a LIST of candidate
endpoints, each is probed in order, and the report names exactly which responded and how each
failure failed. A collector that returns nothing must be distinguishable from a venue that has
nothing, which is L1.28a on the collection layer.

**A FAILED FETCH IS NEVER ARCHIVED.** `append_snapshot` refuses an empty cohort, because writing
one would make every trader in the previous snapshot look like they exited -- turning a network
timeout into a 100% exit rate, which is a spectacular false finding rather than a missing one.

**NOTHING HERE IS EVIDENCE FOR CAPITAL.** It produces a panel. The panel earns a forward clock
under the ordinary funnel or it earns nothing, and no leaderboard entry, rank or return figure may
reach capital (III.15).

    python scripts/collect_leaderboards.py            # collect all venues
    python scripts/collect_leaderboards.py --probe    # report reachability, archive nothing
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

from libs.research.leaderboard_panel import TraderRow, append_snapshot, forward_persistence

_PANEL_DIR = Path("data/leaderboard_panel")
_OUT = Path("web/leaderboard_collector.json")
_TIMEOUT = 25

#: Binance's leaderboard lives behind its web front end. `periodType` values the route accepts are
#: EXACT_MONTHLY / EXACT_WEEKLY / EXACT_DAILY / ALL; ROI is requested rather than PNL because a
#: return is comparable across account sizes and a PnL is not.
_BINANCE_RANK = "https://www.binance.com/bapi/futures/v1/public/future/leaderboard/getLeaderboardRank"
_BINANCE_BODY = {"isShared": True, "isTrader": False, "periodType": "EXACT_MONTHLY",
                 "statisticsType": "ROI", "tradeType": "PERPETUAL"}

#: Hyperliquid publishes its leaderboard as a static stats blob. Every account's positions are
#: public by design on this venue, so this is the one place where a panel can eventually be joined
#: to actual holdings rather than to a published summary figure.
_HYPERLIQUID_URLS = ("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",)

_UA = {"User-Agent": "quant-platform/1.0", "Content-Type": "application/json"}


def _post(url: str, body: dict[str, Any]) -> Any:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=_UA, method="POST")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read())


def _get(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": _UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read())


def _why(exc: BaseException) -> str:
    """A failure named precisely enough to act on. `HTTPError` alone cannot distinguish a route
    that moved (404) from one that is rate-limiting us (429) from one that wants a browser (403),
    and those are three different responses."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return f"URLError {exc.reason}"
    return f"{type(exc).__name__}: {exc}"


def fetch_binance() -> tuple[list[TraderRow], str]:
    """Normalised cohort from the Binance futures leaderboard.

    `encryptedUid` is the identifier that must be stable across snapshots -- nickName is not, since
    a trader can rename and would then read as one exit plus one new entrant.
    """
    try:
        d = _post(_BINANCE_RANK, _BINANCE_BODY)
    except Exception as exc:
        return [], f"UNREACHABLE ({_why(exc)})"
    rows = (d or {}).get("data") or []
    if not isinstance(rows, list) or not rows:
        return [], f"RESPONDED BUT EMPTY (success={(d or {}).get('success')!r}) -- shape may have changed"
    out: list[TraderRow] = []
    for r in rows:
        uid = r.get("encryptedUid")
        if not uid:
            continue
        out.append({"trader_id": str(uid), "nick": r.get("nickName"),
                    "roi": float(r.get("value") or 0.0),
                    "position_shared": bool(r.get("positionShared")),
                    "window": _BINANCE_BODY["periodType"]})
    return out, "ok" if out else "RESPONDED BUT NO USABLE IDENTIFIERS"


def _hl_roi(row: dict[str, Any], window: str = "month") -> float:
    """Hyperliquid publishes performance as [[window, {pnl, roi, vlm}], ...]. Absent window -> 0.0
    only because a rank statistic needs a number; the collector records the window it used so a
    reader can see which figure is being ranked."""
    for w in row.get("windowPerformances") or []:
        if isinstance(w, list) and len(w) == 2 and w[0] == window:
            return float((w[1] or {}).get("roi") or 0.0)
    return 0.0


def fetch_hyperliquid() -> tuple[list[TraderRow], str]:
    errs = []
    for url in _HYPERLIQUID_URLS:
        try:
            d = _get(url)
        except Exception as exc:
            errs.append(f"{url}: {_why(exc)}")
            continue
        rows = (d or {}).get("leaderboardRows") or []
        out: list[TraderRow] = [
            {"trader_id": str(r.get("ethAddress")), "roi": _hl_roi(r),
             "account_value": float(r.get("accountValue") or 0.0), "window": "month"}
            for r in rows if r.get("ethAddress")
        ]
        if out:
            return out, "ok"
        errs.append(f"{url}: RESPONDED BUT EMPTY")
    return [], "UNREACHABLE (" + "; ".join(errs) + ")"


VENUES = {"binance": fetch_binance, "hyperliquid": fetch_hyperliquid}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true",
                    help="report reachability and archive NOTHING -- for checking an endpoint "
                         "without putting a possibly-malformed row into an append-only panel")
    ap.add_argument("--venue", default=None, choices=sorted(VENUES))
    args = ap.parse_args()

    venues = {args.venue: VENUES[args.venue]} if args.venue else VENUES
    rep: dict[str, Any] = {"updated": datetime.now(tz=UTC).isoformat(),
                           "probe_only": bool(args.probe), "venues": {}}
    for name, fetch in venues.items():
        traders, why = fetch()
        panel = _PANEL_DIR / f"{name}.jsonl"
        archived = (not args.probe) and append_snapshot(panel, name, traders, source=why)
        rep["venues"][name] = {
            "n_traders": len(traders), "fetch": why, "archived": archived,
            "panel": str(panel),
            # THE PANEL'S VERDICT, READ EVERY RUN. A collector that never reports what its own
            # archive says is how a panel accumulates for weeks with nobody noticing it is ready.
            "persistence": forward_persistence(panel),
        }

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    print(f"=== LEADERBOARD PANEL {'[PROBE]' if args.probe else ''} ===")
    for name, v in rep["venues"].items():
        p = v["persistence"]
        print(f"  {name:<12} {v['n_traders']:>4} traders  fetch={v['fetch'][:60]}")
        if p.get("state") == "MEASURED":
            # BOTH RHOs OR NEITHER. The survivors-only figure alone is the survivorship bug with a
            # number attached, and it is the one a reader will quote if it is printed alone.
            print(f"               panel: MEASURED over {p['gap_days']}d, cohort {p['cohort']}, "
                  f"exit_rate={p['exit_rate']}")
            print(f"               rho survivors-only {p['spearman_survivors_only']} (BIASED UP) "
                  f"vs exits-ranked-last {p['spearman_exits_ranked_last']}")
        else:
            print(f"               panel: {p.get('state')} -- {p.get('why') or ''}")
    print(f"-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
