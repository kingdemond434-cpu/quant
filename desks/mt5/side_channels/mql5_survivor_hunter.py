"""MQL5 Signals survivor hunter -- the S++ direct max-growth engine (principal 2026-08-25).

THE RICHEST DIRECT GROUND: public MT5/MT4 signals expose growth, weeks, PF, drawdown, trades,
win rate and algo-trading share. This hunter enumerates list pages, screens MULTIPLE SURVIVOR
PHENOTYPES locally (never one leaderboard rank -- "best total return" alone selects
leverage/grid monsters), deep-fetches only the union of phenotype winners, and emits
survivor_candidate rows + a ranked shortlist for judgment. Cohort enrollment picks every row up
automatically (kind=track_record), so today's champions enter the mortality time-machine the
hour they are first seen.

RANKING LAW (principal): expected net log-growth per unit of hunting capacity -- the EV proxy
prefers one long-lived, reproducible survivor over 100 mediocre EAs:
    ev = growth% x sqrt(weeks/52) / max(dd%, 5), gated on trades >= 100.

Pipeline position: this feeds trade-DNA extraction -> source resolver -> reconstruction ->
frozen clone spec -> Fusion replay -> clone clock -> gauntlet. Enumeration only; zero LLM.
"""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
INTEL = BASE / "data" / "intelligence"
OUT = INTEL / "mql5_survivors"
SHORTLIST = INTEL / "survivor_shortlist.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.9"}

LIST_PAGES = [("mt5", 1), ("mt5", 2), ("mt5", 3), ("mt4", 1)]
DEEP_FETCH_CAP = 18
CARD_RE = re.compile(r'href="(/en/signals/(\d+)[^"]*)"[^>]*>([^<]{3,90})<')
#: A number as MQL5 prints it: thousands grouped by a space, a no-break space or a comma
#: ("2 281", "20,585.63"), or plain. The old `\d[\d\s,]*` let whitespace -- newlines included --
#: glue two separate numbers into one.
NUM = r"[-+]?(?:\d{1,3}(?:[ \u00a0,]\d{3})+|\d+)(?:\.\d+)?"
#: The page line is `Profit Trades: 2 281 (76.90%)` -- a COUNT, then the percent in parentheses.
#: Until 2026-09-30 `field` read the count into `win_pct`: 2,985 of 3,154 committed rows carried
#: a "win rate" above 100 (a 2,296% one reached the PR #160 committee), and all 3,042 rows with
#: both fields held a win count <= trades, i.e. every one was a count.
_MARKUP = r"\s*:?\s*(?:</[^>]+>\s*<[^>]+>\s*)*"
WIN_LABEL = r"Profit(?:able)?\s+Trades"
#: Total trades, never the `Profit Trades` / `Loss Trades` lines that also end in "Trades".
TRADES_LABEL = r"(?<!Profit )(?<!Profitable )(?<!Loss )(?<!Losing )\bTrades"


def fetch(url: str) -> str:
    time.sleep(1.2)
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text


def field(html: str, label: str) -> float | None:
    # Two passes: plain label:value, then markup-tolerant (MQL5 renders e.g.
    # `drawdown red">53%` -- label and value separated by class/markup fragments).
    for pat in (label + r"\s*:?\s*(?:</[^>]+>\s*<[^>]+>\s*)*(" + NUM + r")\s*%?",
                label + r"[^%<>]{0,40}?[\">]\s*(" + NUM + r")\s*%"):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "").replace("\u00a0", "")
                             .replace(" ", ""))
            except ValueError:
                continue
    return None


def _pct(s: str) -> float | None:
    """A percent as printed: "76.90", or with a decimal comma "76,90" (a non-English locale)."""
    s = s.strip().replace("\u00a0", "").replace(" ", "")
    if re.fullmatch(r"\d+,\d{1,2}", s):
        s = s.replace(",", ".")
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def win_rate(html: str, trades: float | None) -> tuple[float | None, str]:
    """(win rate in percent, how it was read) -- never the win COUNT.

    1. the percent MQL5 prints in parentheses after the count;
    2. else the count over total trades, when both were read and count <= trades;
    3. else a bare percent (a value followed by `%`) inside [0, 100];
    4. else UNMEASURED (None). A number that cannot be a rate is never written as one."""
    m = re.search(WIN_LABEL + _MARKUP + "(" + NUM + r")\s*\(\s*([\d.,\s]+?)\s*%\s*\)", html,
                  re.IGNORECASE)
    if m:
        p = _pct(m.group(2))
        if p is not None and 0.0 <= p <= 100.0:
            return p, "percent_in_parentheses"
    m = re.search(WIN_LABEL + _MARKUP + "(" + NUM + r")(\s*%)?", html, re.IGNORECASE)
    if m:
        try:
            v = float(re.sub(r"[ \u00a0,]", "", m.group(1)))
        except ValueError:
            return None, "unparsed"
        if m.group(2):
            return (v, "bare_percent") if 0.0 <= v <= 100.0 else (None, "percent_out_of_bounds")
        if trades and trades > 0 and 0.0 <= v <= trades:
            return round(100.0 * v / trades, 2), "count_over_trades"
        return None, "count_without_trades"
    return None, "absent"


def deep_stats(sid: str) -> dict:
    html = fetch(f"https://www.mql5.com/en/signals/{sid}")
    trades = field(html, TRADES_LABEL)
    win, win_basis = win_rate(html, trades)
    stats = {
        "growth_pct": field(html, "Growth"),
        "weeks": field(html, "Weeks"),
        "pf": field(html, "Profit Factor"),
        "max_dd_pct": field(html, r"Maximal?\s+drawdown"),
        "trades": trades,
        "win_pct": win,
        "win_pct_basis": win_basis,
        "algo_pct": field(html, r"Algo\s*trading"),
        "subscribers": field(html, "Subscribers"),
    }
    syms = sorted(set(re.findall(r'\b([A-Z]{6}|XAUUSD|XAGUSD|XAUEUR|US500|NAS100|USOIL)\b',
                                 html)))[:12]
    stats["symbols_seen"] = syms
    # FREE CURVE GEOMETRY + AUTHOR GENEALOGY: the page inlines the author's OTHER signals with
    # their growth% and full sparkline equity values -- blowup morphology and author track
    # record without a single extra fetch.
    author = re.search(r'href="(/en/users/[A-Za-z0-9_\-.]+)"', html)
    stats["author"] = author.group(1) if author else None
    others = []
    for m in re.finditer(r'href="https://www\.mql5\.com(/en/signals/(\d+))\?[^"]*"[^>]*'
                         r'title="([^"]{3,80})".*?name="growth"[^>]*value="([^"]+)"'
                         r'.*?name="value"[^>]*value="([^"]+)"', html, re.DOTALL):
        curve = [float(x) for x in m.group(5).split(",")[:200] if
                 x.strip().lstrip("-").replace(".", "").isdigit()]
        dd_curve = 0.0
        peak = 0.0
        for v in curve:
            peak = max(peak, v)
            dd_curve = min(dd_curve, v - peak)
        others.append({"sid": m.group(2), "title": m.group(3),
                       "growth": m.group(4).replace(" ", ""),
                       "curve_points": len(curve), "curve_dd": round(dd_curve, 2)})
    stats["author_other_signals"] = others[:10]
    # session DNA seed: hour histogram of any trade timestamps present on the page
    hours = re.findall(r"\b\d{4}\.\d{2}\.\d{2}\s+(\d{2}):\d{2}", html)
    if hours:
        hist: dict[str, int] = {}
        for h in hours:
            hist[h] = hist.get(h, 0) + 1
        stats["hour_histogram"] = hist
    return stats


def phenotypes(s: dict) -> list[str]:
    g = s.get("growth_pct") or 0
    dd = s.get("max_dd_pct") or 100
    wk = s.get("weeks") or 0
    pf = s.get("pf") or 0
    tr = s.get("trades") or 0
    algo = s.get("algo_pct") or 0
    tags = []
    if tr < 100:
        return tags                                  # sub-viable evidence, no phenotype
    if g >= 200:
        tags.append("max_growth")
    if dd > 0 and g / dd >= 8 and g >= 60:
        tags.append("low_dd_high_return")
    if wk >= 104 and g > 50:
        tags.append("long_lived")
    if wk <= 26 and g >= 80:
        tags.append("new_fast_growth")
    if pf >= 2.0 and tr >= 200:
        tags.append("high_pf")
    if algo >= 80:
        tags.append("algo_survivor")
    if any(x in (s.get("symbols_seen") or []) for x in ("XAUUSD", "XAGUSD", "XAUEUR")):
        tags.append("gold")
    if len([x for x in (s.get("symbols_seen") or []) if len(x) == 6]) >= 4:
        tags.append("multi_fx")
    return tags


def ev_score(s: dict) -> float:
    g = s.get("growth_pct") or 0
    dd = max(s.get("max_dd_pct") or 100, 5)
    wk = max(s.get("weeks") or 0, 1)
    if (s.get("trades") or 0) < 100 or g <= 0:
        return 0.0
    return round(g * (wk / 52) ** 0.5 / dd, 3)


def run_and_save() -> list[dict]:
    now = datetime.now(tz=UTC)
    cards: dict[str, dict] = {}
    for platform, page in LIST_PAGES:
        try:
            html = fetch(f"https://www.mql5.com/en/signals/{platform}/page{page}")
            for m in CARD_RE.finditer(html):
                sid = m.group(2)
                cards.setdefault(sid, {"sid": sid, "name": m.group(3).strip(),
                                       "platform": platform,
                                       "url": f"https://www.mql5.com/en/signals/{sid}"})
        except Exception as exc:                                         # noqa: BLE001
            print(f"  list {platform} p{page}: {exc}")
    print(f"  enumerated {len(cards)} signals")
    rows = []
    for sid, c in list(cards.items())[:DEEP_FETCH_CAP]:
        try:
            s = deep_stats(sid)
        except Exception as exc:                                         # noqa: BLE001
            print(f"  deep {sid}: {exc}")
            continue
        tags = phenotypes(s)
        ev = ev_score(s)
        rows.append({"source": "mql5_survivors", "kind": "track_record",
                     "title": c["name"], "url": c["url"], "symbols": s.get("symbols_seen", []),
                     "found_at": now.isoformat(timespec="seconds"),
                     "platform": c["platform"], "phenotypes": tags, "ev_score": ev,
                     **{k: v for k, v in s.items() if k != "symbols_seen"}})
    # THE SHARED METRIC FENCE, AT THE SCRAPER TOO (libs/research/metric_fence.py). The compiler
    # refuses these rows before any cell exists; here they are marked and kept off the ranked
    # shortlist, so an impossible record is never what "judgment" reads first.
    refused = 0
    fence = None
    try:
        import sys
        root = str(BASE.parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs.research.metric_fence import fence_row
        fence = fence_row
        for r in rows:
            bad = fence_row(r)
            if bad:
                r["metric_refused"] = bad
                refused += 1
    except ImportError as exc:
        print(f"  metric fence unavailable here ({exc}); the compiler still applies it")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"discoveries_{now:%Y%m%d_%H%M}.json").write_text(
        json.dumps(rows, indent=1, default=str), "utf-8")
    # ranked shortlist: the ONLY thing judgment needs to read
    short = sorted((r for r in rows if r["ev_score"] > 0 and r["phenotypes"]
                    and not r.get("metric_refused")),
                   key=lambda r: -r["ev_score"])[:25]
    try:
        prev = json.loads(SHORTLIST.read_text("utf-8")).get("shortlist", [])
    except (OSError, ValueError):
        prev = []
    seen = {r["url"] for r in short}
    merged = short + [p for p in prev if p.get("url") not in seen
                      and not (fence is not None and fence(p))]
    SHORTLIST.write_text(json.dumps(
        {"updated_at": now.isoformat(timespec="seconds"),
         "ranking_law": "growth x sqrt(weeks/52) / dd, trades>=100; EV per hunting capacity",
         "shortlist": merged[:50]}, indent=1), "utf-8")
    tagged = sum(1 for r in rows if r["phenotypes"])
    print(f"mql5 survivor hunter: {len(rows)} deep-fetched, {tagged} phenotype-tagged, "
          f"shortlist {len(merged[:50])}, impossible-metric rows refused {refused}")
    return rows


if __name__ == "__main__":
    run_and_save()
