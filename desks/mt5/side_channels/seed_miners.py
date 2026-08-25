"""Seed Drop 2 miner suite (S9-S24) -- principal order 2026-08-25: build ALL proposed miners.

Sixteen token-free enumeration miners in one fail-soft module. Same contract as the Drop-1
miners (per-source data/intelligence/<name>/discoveries_<ts>.json + merge into
latest_discoveries.json so convert_to_hypotheses feeds them to the gauntlet queue). Each miner
is best-effort: a source whose page shape drifts degrades to raw-capture rows flagged
needs_selector_work -- corpus either way, and the gap-wirer iterates selectors from evidence.

Politeness: sequential, one UA, 20s timeouts, per-source request caps, 1s spacing. A banned
scraper is a dead discovery channel; breadth never buys a ban.
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
STATE = INTEL / "seed_miners_state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
LINK_RE = re.compile(r"https?://[^\s)\"'<>]+")


def fetch(url: str, as_json: bool = False, timeout: int = 20):
    time.sleep(1.0)
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json() if as_json else r.text


def row(source: str, kind: str, title: str, url: str = "", text: str = "",
        symbols: list | None = None, **extra) -> dict:
    return {"source": source, "kind": kind, "title": title[:300], "url": url,
            "text": text[:1500], "symbols": symbols or [],
            "found_at": datetime.now(tz=UTC).isoformat(timespec="seconds"), **extra}


def _state() -> dict:
    try:
        return json.loads(STATE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- S9 MQL5 Signals
def mine_mql5_signals() -> list[dict]:
    out = []
    for platform in ("mt5", "mt4"):
        html = fetch(f"https://www.mql5.com/en/signals/{platform}")
        for m in re.finditer(r'href="(/en/signals/(\d+))"[^>]*>([^<]{3,80})<', html):
            out.append(row("mql5_signals", "track_record", m.group(3).strip(),
                           "https://www.mql5.com" + m.group(1), platform=platform))
        if not out:
            out.append(row("mql5_signals", "raw_capture", f"signals/{platform} page shape "
                           "drifted", f"https://www.mql5.com/en/signals/{platform}",
                           html[:1200], needs_selector_work=True))
    return out[:80]


# ---------------------------------------------------------------- S10 Myfxbook outlook
def mine_myfxbook_outlook() -> list[dict]:
    html = fetch("https://www.myfxbook.com/community/outlook")
    out = []
    for m in re.finditer(r'symbolOutlook[^>]*?>([A-Z]{6})</a>.*?(\d{1,2})%.*?(\d{1,2})%',
                         html, re.DOTALL):
        sym, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        out.append(row("myfxbook_outlook", "positioning", f"{sym} retail positioning",
                       "https://www.myfxbook.com/community/outlook", symbols=[sym],
                       pct_a=a, pct_b=b))
    if not out:
        pairs = sorted(set(re.findall(r'\b([A-Z]{6})\b', html)))[:30]
        out.append(row("myfxbook_outlook", "raw_capture", "outlook page shape drifted",
                       "https://www.myfxbook.com/community/outlook",
                       " ".join(pairs), needs_selector_work=True))
    return out[:60]


# ---------------------------------------------------------------- S11 Darwinex
def mine_darwinex() -> list[dict]:
    html = fetch("https://www.darwinex.com/darwins")
    codes = sorted(set(re.findall(r'\b([A-Z]{3,4})\.(?:\d+\.)?\d+\b', html)))[:40]
    if codes:
        return [row("darwinex", "track_record", f"DARWIN {c}",
                    f"https://www.darwinex.com/darwin/{c}") for c in codes]
    return [row("darwinex", "raw_capture", "darwins page shape drifted",
                "https://www.darwinex.com/darwins", html[:1200],
                needs_selector_work=True)]


# ---------------------------------------------------------------- S12 TradingView scripts
def mine_tradingview_scripts() -> list[dict]:
    out = []
    html = fetch("https://www.tradingview.com/scripts/?script_access=open&script_type=strategies")
    for m in re.finditer(r'href="(/script/[^"]+/)"[^>]*>([^<]{3,120})<', html):
        out.append(row("tradingview_scripts", "strategy_source", m.group(2).strip(),
                       "https://www.tradingview.com" + m.group(1)))
    if not out:
        ids = re.findall(r'"scriptIdPart":"([^"]+)"', html)[:40]
        out = [row("tradingview_scripts", "strategy_source", i,
                   f"https://www.tradingview.com/script/{i}/") for i in ids] or \
              [row("tradingview_scripts", "raw_capture", "scripts page shape drifted",
                   "https://www.tradingview.com/scripts/", html[:1200],
                   needs_selector_work=True)]
    return out[:60]


# ---------------------------------------------------------------- S13 FX Blue
def mine_fxblue() -> list[dict]:
    html = fetch("https://www.fxblue.com/users")
    users = sorted(set(re.findall(r'href="/users/([A-Za-z0-9_\-]{3,30})"', html)))[:40]
    if users:
        return [row("fxblue", "track_record", f"FX Blue user {u}",
                    f"https://www.fxblue.com/users/{u}") for u in users]
    return [row("fxblue", "raw_capture", "users page shape drifted",
                "https://www.fxblue.com/users", html[:1200], needs_selector_work=True)]


# ---------------------------------------------------------------- S14 Collective2
def mine_collective2() -> list[dict]:
    html = fetch("https://collective2.com/leaderboard")
    out = []
    for m in re.finditer(r'href="(/details/\d+)"[^>]*>([^<]{3,80})<', html):
        out.append(row("collective2", "track_record", m.group(2).strip(),
                       "https://collective2.com" + m.group(1)))
    return out[:40] or [row("collective2", "raw_capture", "leaderboard shape drifted",
                            "https://collective2.com/leaderboard", html[:1200],
                            needs_selector_work=True)]


# ---------------------------------------------------------------- S15 QuantConnect
def mine_quantconnect() -> list[dict]:
    html = fetch("https://www.quantconnect.com/forum/discussions/1/newest")
    out = []
    for m in re.finditer(r'href="(/forum/discussion/\d+/[^"]+)"[^>]*>([^<]{3,120})<', html):
        out.append(row("quantconnect", "strategy_thread", m.group(2).strip(),
                       "https://www.quantconnect.com" + m.group(1)))
    return out[:40] or [row("quantconnect", "raw_capture", "forum shape drifted",
                            "https://www.quantconnect.com/forum", html[:1200],
                            needs_selector_work=True)]


# ---------------------------------------------------------------- S16 ForexPeaceArmy
def mine_forexpeacearmy() -> list[dict]:
    html = fetch("https://www.forexpeacearmy.com/forex-reviews")
    out = []
    for m in re.finditer(r'href="(/forex-reviews/[^"]+)"[^>]*>([^<]{4,100})<', html):
        out.append(row("forexpeacearmy", "refutation_review", m.group(2).strip(),
                       "https://www.forexpeacearmy.com" + m.group(1)))
    return out[:40] or [row("forexpeacearmy", "raw_capture", "reviews shape drifted",
                            "https://www.forexpeacearmy.com/forex-reviews", html[:1200],
                            needs_selector_work=True)]


# ---------------------------------------------------------------- S17 FF calendar VINTAGES
def mine_ff_calendar_vintage() -> list[dict]:
    data = fetch("https://nfs.faireconomy.media/ff_calendar_thisweek.json", as_json=True)
    cap = datetime.now(tz=UTC).isoformat(timespec="seconds")
    out = []
    for ev in data[:120]:
        out.append(row("ff_calendar_vintage", "calendar_vintage",
                       f"{ev.get('country', '')} {ev.get('title', '')}",
                       "", symbols=[str(ev.get('country', ''))],
                       event_date=ev.get("date"), impact=ev.get("impact"),
                       forecast=ev.get("forecast"), previous=ev.get("previous"),
                       captured_at=cap))
    return out


# ---------------------------------------------------------------- S18 Forex-TSD CDX
def mine_forextsd_cdx() -> list[dict]:
    st = _state()
    offset = int(st.get("forextsd_offset", 0))
    txt = fetch("http://web.archive.org/cdx/search/cdx?url=forex-tsd.com*&output=json"
                f"&limit=300&offset={offset}&collapse=urlkey", timeout=40)
    rows_ = json.loads(txt)
    out = []
    for r_ in rows_[1:]:
        try:
            ts, orig = r_[1], r_[2]
        except (IndexError, TypeError):
            continue
        out.append(row("forextsd_cdx", "era_archive", orig[:120],
                       f"https://web.archive.org/web/{ts}/{orig}"))
    st["forextsd_offset"] = offset + max(len(rows_) - 1, 0)
    STATE.write_text(json.dumps(st, indent=0), "utf-8")
    return out[:120]


# ---------------------------------------------------------------- S19 quant.SE
def mine_quant_se() -> list[dict]:
    data = fetch("https://api.stackexchange.com/2.3/questions?order=desc&sort=activity"
                 "&site=quant&pagesize=30", as_json=True)
    return [row("quant_se", "qa", it.get("title", ""), it.get("link", ""),
                symbols=[], score=it.get("score"), tags=it.get("tags", []))
            for it in data.get("items", [])]


# ---------------------------------------------------------------- S20 arXiv q-fin
def mine_arxiv_qfin() -> list[dict]:
    xml = fetch("http://export.arxiv.org/api/query?search_query=cat:q-fin.TR+OR+cat:q-fin.PM"
                "+OR+cat:q-fin.ST&sortBy=submittedDate&sortOrder=descending&max_results=25",
                timeout=40)
    out = []
    for m in re.finditer(r"<entry>.*?<id>([^<]+)</id>.*?<title>([^<]+)</title>.*?"
                         r"<summary>([^<]{0,800})", xml, re.DOTALL):
        out.append(row("arxiv_qfin", "paper", m.group(2).strip().replace("\n", " "),
                       m.group(1).strip(), m.group(3).strip()))
    return out


# ---------------------------------------------------------------- S21 BIS speeches
def mine_bis_speeches() -> list[dict]:
    xml = fetch("https://www.bis.org/doclist/cbspeeches.rss", timeout=30)
    out = []
    for m in re.finditer(r"<item>.*?<title>([^<]+)</title>.*?<link>([^<]+)</link>.*?"
                         r"<description>([^<]{0,600})", xml, re.DOTALL):
        out.append(row("bis_speeches", "cb_speech", m.group(1).strip(), m.group(2).strip(),
                       m.group(3).strip()))
    return out[:40]


# ---------------------------------------------------------------- S22 broker swaps
def mine_broker_swaps() -> list[dict]:
    out = []
    for broker, url in [("fusionmarkets", "https://fusionmarkets.com/en/pricing/swap-rates")]:
        try:
            html = fetch(url)
            hits = re.findall(r'([A-Z]{6})\D{0,40}(-?\d+\.?\d*)\D{1,20}(-?\d+\.?\d*)',
                              html)[:60]
            for sym, lng, sht in hits:
                out.append(row("broker_swaps", "swap_table", f"{broker} {sym} swap",
                               url, symbols=[sym], swap_long=lng, swap_short=sht,
                               broker=broker))
            if not hits:
                out.append(row("broker_swaps", "raw_capture", f"{broker} swap page shape",
                               url, html[:1200], needs_selector_work=True))
        except Exception as exc:                                         # noqa: BLE001
            out.append(row("broker_swaps", "fetch_error", f"{broker}: {exc}", url,
                           needs_selector_work=True))
    return out


# ---------------------------------------------------------------- S23 GitHub topic deltas
def mine_github_topics() -> list[dict]:
    st = _state()
    stars = st.setdefault("gh_stars", {})
    out = []
    for topic in ("mql5", "metatrader5", "forex-trading"):
        data = fetch(f"https://api.github.com/search/repositories?q=topic:{topic}"
                     "&sort=updated&per_page=15", as_json=True)
        for it in data.get("items", []):
            full, s = it.get("full_name", ""), int(it.get("stargazers_count", 0))
            delta = s - int(stars.get(full, s))
            stars[full] = s
            out.append(row("github_topics", "repo", full, it.get("html_url", ""),
                           (it.get("description") or "")[:400], topic=topic,
                           stars=s, star_delta=delta, pushed=it.get("pushed_at")))
    STATE.write_text(json.dumps(st, indent=0), "utf-8")
    return out


# ---------------------------------------------------------------- S24 prop-firm boards
def mine_propfirm_boards() -> list[dict]:
    html = fetch("https://ftmo.com/en/leaderboards/")
    hits = re.findall(r'>([A-Za-z .\-]{3,30})</td>\s*<td[^>]*>\s*\$?([\d,]+)', html)[:30]
    if hits:
        return [row("propfirm_boards", "leaderboard", f"FTMO {name.strip()}",
                    "https://ftmo.com/en/leaderboards/", gain=g) for name, g in hits]
    return [row("propfirm_boards", "raw_capture", "ftmo leaderboard shape drifted",
                "https://ftmo.com/en/leaderboards/", html[:1200],
                needs_selector_work=True)]


def mine_mql5_survivors() -> list[dict]:
    """S++ flagship: phenotype-screened MQL5 survivor hunt (own module, richest ground)."""
    from mql5_survivor_hunter import run_and_save as _hunt  # noqa: PLC0415
    return _hunt()


def mine_regional_survivors() -> list[dict]:
    """Global regional family (14 grounds + FBS tape), rotating-cursor hourly depth."""
    from regional_survivor_hunters import run_and_save as _hunt  # noqa: PLC0415
    res = _hunt()
    return [r for v in res.values() for r in v.get("discoveries", [])]


def mine_global_frontier() -> list[dict]:
    """Adaptive per-locale discovery cell: native queries -> new populations -> graduation."""
    from global_survivor_frontier import run_and_save as _frontier  # noqa: PLC0415
    return _frontier().get("discoveries", [])


MINERS = {
    "global_frontier": mine_global_frontier,
    "regional_survivors": mine_regional_survivors,
    "mql5_survivors": mine_mql5_survivors,
    "mql5_signals": mine_mql5_signals, "myfxbook_outlook": mine_myfxbook_outlook,
    "darwinex": mine_darwinex, "tradingview_scripts": mine_tradingview_scripts,
    "fxblue": mine_fxblue, "collective2": mine_collective2,
    "quantconnect": mine_quantconnect, "forexpeacearmy": mine_forexpeacearmy,
    "ff_calendar_vintage": mine_ff_calendar_vintage, "forextsd_cdx": mine_forextsd_cdx,
    "quant_se": mine_quant_se, "arxiv_qfin": mine_arxiv_qfin,
    "bis_speeches": mine_bis_speeches, "broker_swaps": mine_broker_swaps,
    "github_topics": mine_github_topics, "propfirm_boards": mine_propfirm_boards,
}


def run_and_save() -> dict:
    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
    results, summary = {}, {"total": 0, "ok": 0, "raw_only": 0, "failed": 0}
    for name, fn in MINERS.items():
        try:
            rows_ = fn()
        except Exception as exc:                                         # noqa: BLE001
            rows_ = [row(name, "fetch_error", str(exc)[:200], needs_selector_work=True)]
            summary["failed"] += 1
        d = INTEL / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"discoveries_{ts}.json").write_text(
            json.dumps(rows_, indent=1, default=str), "utf-8")
        real = [r_ for r_ in rows_ if not r_.get("needs_selector_work")]
        results[name] = {"discoveries": rows_, "count": len(rows_)}
        summary["total"] += len(rows_)
        summary["ok"] += 1 if real else 0
        summary["raw_only"] += 0 if real else 1
        print(f"  {name}: {len(rows_)} rows ({'real' if real else 'RAW/selector-work'})")
    # merge into latest_discoveries.json so convert_to_hypotheses feeds the gauntlet queue
    latest_p = INTEL / "latest_discoveries.json"
    try:
        latest = json.loads(latest_p.read_text("utf-8"))
    except (OSError, ValueError):
        latest = {}
    latest.update(results)
    latest_p.write_text(json.dumps(latest, indent=1, default=str), "utf-8")
    print(f"seed miners: {summary['total']} rows across {len(MINERS)} sources "
          f"(ok={summary['ok']} raw={summary['raw_only']} failed={summary['failed']})")
    # JOIN STAGE (Drop 3): forward-cohort enrollment/mortality + identity graph run on every
    # sweep's output -- relationships and TIME are the corpus the sites cannot sell us.
    try:
        from cohort_and_identity import run_and_save as _cohorts  # noqa: PLC0415
        _cohorts()
    except Exception as exc:                                             # noqa: BLE001
        print(f"cohort/identity join failed (non-fatal): {exc}")
    return results


if __name__ == "__main__":
    run_and_save()
