"""Global regional survivor hunters -- the full world map, hourly (principal 2026-08-25/26).

Fourteen public copy/PAMM/leaderboard grounds across CN/JP/CIS/MENA/SEA/LATAM/EU/global,
config-driven and fail-soft: every source is enumerated with a ROTATING PAGE CURSOR persisted
across runs, so hourly sweeps accumulate unbounded breadth AND depth over time while staying
polite (a handful of requests per source per hour -- a banned scraper is a dead channel).
Every parsed account row is kind=track_record, so the forward-cohort time machine enrolls it
at first sight; unparseable pages degrade to raw_capture rows flagged needs_selector_work for
the wirer. FBS's published top-trades tape is captured as kind=trade_tape -- full open/close
timestamps, prices, SL/TP: direct Trade-DNA feedstock.

COVERAGE REGISTRY: every attempt updates data/intelligence/coverage_registry.json
(region x language x platform x evidence grade x last state). Empty regions (KR, TR) stay
OPEN cells, permanently searchable -- coverage is a ratchet, "done" is not a state.

Evidence grades: A = broker-native live account data; B = platform-verified aggregation;
C = self-reported/experimental. Grades flow into ranking, never into exclusion.
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
STATE = INTEL / "regional_hunters_state.json"
COVERAGE = INTEL / "coverage_registry.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.8,ru;q=0.6,zh;q=0.5,ja;q=0.5,ar;q=0.4,es;q=0.4"}
NUM = r"[-+]?\d[\d\s,]*\.?\d*"


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def fetch(url: str, timeout: int = 25) -> str:
    time.sleep(1.1)
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def row(source: str, kind: str, title: str, url: str = "", text: str = "",
        symbols: list | None = None, **extra) -> dict:
    return {"source": source, "kind": kind, "title": title[:300], "url": url,
            "text": text[:1200], "symbols": symbols or [],
            "found_at": datetime.now(tz=UTC).isoformat(timespec="seconds"), **extra}


def generic_cards(source: str, html: str, base_url: str, link_pat: str,
                  region: str) -> list[dict]:
    """Shared extractor: account/strategy links + nearby stats, LABELS READ IN ANY LANGUAGE
    (lang_intel: 収益率, просадка, 最大回撤, أقصى تراجع and drawdown are one concept)."""
    from lang_intel import STAT_CONCEPTS, detect_mechanisms, stat_near  # noqa: PLC0415
    out = []
    for m in re.finditer(link_pat, html):
        href, label = m.group(1), (m.group(2) if m.lastindex >= 2 else m.group(1)).strip()
        ctx = html[m.start():m.start() + 1200]
        pcts = [p.replace(" ", "").replace(",", "") for p in
                re.findall(r"(" + NUM + r")\s*%", ctx)][:6]
        stats = {c: stat_near(ctx, c) for c in STAT_CONCEPTS}
        url = href if href.startswith("http") else base_url.rstrip("/") + href
        out.append(row(source, "track_record", label or href, url,
                       region=region, nearby_pcts=pcts,
                       stats={k: v for k, v in stats.items() if v is not None},
                       mechanism_tags=detect_mechanisms(ctx)))
    return out


#: name -> (region, lang, evidence_grade, page_urls_fn(page:int), link_regex, base_url, npages)
SOURCES = {
    "equiti_copy": ("MENA/global", "en+ar", "A",
                    lambda p: f"https://copy-ratings.equiti.com/?page={p}",
                    r'href="(/(?:provider|strategy)[^"]*)"[^>]*>([^<]{3,80})<',
                    "https://copy-ratings.equiti.com", 5),
    "trading_latam": ("LATAM", "es", "B",
                      lambda p: "https://trading-latam.com/ranking-toptraders/",
                      r'href="(https://trading-latam\.com/[a-z0-9\-]{4,60}/)"[^>]*>([^<]{3,60})<',
                      "https://trading-latam.com", 1),
    "litefinance": ("CIS/SEA", "en+ru+vi", "A",
                    lambda p: f"https://my.litefinance.org/traders?page={p}",
                    r'href="(/traders/[^"]+)"[^>]*>([^<]{3,60})<',
                    "https://my.litefinance.org", 5),
    "duplitrade": ("EU/global", "en", "A",
                   lambda p: "https://duplitrade.com/strategy-providers",
                   r'href="(/strategy-provider[s]?/[^"]+)"[^>]*>([^<]{3,60})<',
                   "https://duplitrade.com", 1),
    "octa_masters": ("SEA", "en+id+vi", "A",
                     lambda p: f"https://my.octabroker.com/copy-trading/rating/?page={p}",
                     r'href="([^"]*master[^"]*)"[^>]*>([^<]{3,60})<',
                     "https://my.octabroker.com", 3),
    "share4you": ("CIS/Asia", "en+ru", "B",
                  lambda p: f"https://www.share4you.com/en/leaders?page={p}",
                  r'href="(/en/leaders/[^"]+)"[^>]*>([^<]{3,60})<',
                  "https://www.share4you.com", 4),
    "instaforex_copy": ("CIS", "en+ru", "A",
                        lambda p: f"https://www.instaforex.com/forexcopy_monitoring?page={p}",
                        r'href="([^"]*forexcopy[^"]*system[^"]*)"[^>]*>([^<]{3,60})<',
                        "https://www.instaforex.com", 3),
    "roboforex_copyfx": ("CIS/global", "en+ru", "A",
                         lambda p: f"https://copy.roboforex.pro/ratings/traders-all/?page={p}",
                         r'href="(/ratings/trader/[^"]+)"[^>]*>([^<]{3,60})<',
                         "https://copy.roboforex.pro", 4),
    "hfm_pamm": ("MENA/Africa", "en+ar", "A",
                 lambda p: f"https://pamm.hfm.com/int/en/performance?page={p}",
                 r'href="([^"]*/(?:pamm|manager|strategy)/[^"]+)"[^>]*>([^<]{3,60})<',
                 "https://pamm.hfm.com", 3),
    "amarkets": ("CIS", "en+ru", "A",
                 lambda p: f"https://www.amarkets.com/copy-trading-rating/?page={p}",
                 r'href="([^"]*strategy\d+[^"]*)"[^>]*>?([^<]{0,60})',
                 "https://www.amarkets.com", 3),
    "followme_cn": ("China", "zh", "B",
                    lambda p: f"https://cn.followme.com/trade/rank?page={p}",
                    r'href="(/(?:trader|user|account)/[^"]+)"[^>]*>([^<]{2,50})<',
                    "https://cn.followme.com", 3),
    "minfx_jp": ("Japan", "ja", "A",
                 lambda p: "https://min-fx.jp/systre/strategy/",
                 r'href="([^"]*strategy[^"]*)"[^>]*>([^<]{3,60})<',
                 "https://min-fx.jp", 1),
    "mylivefx_br": ("Brazil", "pt", "C",
                    lambda p: "https://mylivefx.com/",
                    r'href="(/[a-z0-9\-]*trader[^"]*)"[^>]*>([^<]{3,60})<',
                    "https://mylivefx.com", 1),
    "readitrades_africa": ("Africa", "en", "C",
                           lambda p: "https://www.ready-trade.com/",
                           r'href="(/[a-z0-9\-]*trader[^"]*)"[^>]*>([^<]{3,60})<',
                           "https://www.ready-trade.com", 1),
}

FBS_TRADE_RE = re.compile(
    r"(XAUUSD|XAGUSD|[A-Z]{6}|US\d{2,3}|USOIL)\D{0,60}(BUY|SELL)\D{0,400}?"
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)", re.IGNORECASE | re.DOTALL)


def mine_fbs_tape() -> list[dict]:
    """FBS publishes top closed trades with full geometry -- direct Trade-DNA feedstock."""
    html = fetch("https://fbs.com/top-trades")
    out = []
    for m in FBS_TRADE_RE.finditer(html):
        ctx = html[m.start():m.start() + 800]
        nums = re.findall(r"\b\d+\.\d{2,5}\b", ctx)[:6]
        out.append(row("fbs_tape", "trade_tape", f"{m.group(1)} {m.group(2)}",
                       "https://fbs.com/top-trades", symbols=[m.group(1).upper()],
                       side=m.group(2).upper(), ts=m.group(3), prices_seen=nums))
    if not out:
        out.append(row("fbs_tape", "raw_capture", "top-trades page shape drifted",
                       "https://fbs.com/top-trades", html[:1200],
                       needs_selector_work=True))
    return out[:80]


def update_coverage(name: str, region: str, lang: str, grade: str, state: str,
                    rows_n: int) -> None:
    cov = _read(COVERAGE, {"note": "region x language x platform coverage RATCHET; empty "
                                   "regions are OPEN cells, never 'done'",
                           "open_cells": {"KR": "no native MT5 survivor pool found yet -- "
                                                "canary searches standing",
                                          "TR": "same; OPEN"},
                           "platforms": {}})
    ent = cov["platforms"].setdefault(name, {"region": region, "lang": lang,
                                             "evidence_grade": grade,
                                             "best_rows": 0, "attempts": 0})
    ent["attempts"] += 1
    ent["last_state"] = state
    ent["last_attempt"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    ent["best_rows"] = max(ent["best_rows"], rows_n)     # coverage ratchets, never falls
    COVERAGE.write_text(json.dumps(cov, indent=1), "utf-8")


def run_and_save() -> dict:
    now = datetime.now(tz=UTC)
    st = _read(STATE, {})
    results = {}
    total_real = 0
    for name, (region, lang, grade, url_fn, link_pat, base_url, npages) in SOURCES.items():
        page = (int(st.get(name, 0)) % npages) + 1          # rotating cursor: depth over hours
        st[name] = page
        rows_: list[dict] = []
        state = "ok"
        try:
            html = fetch(url_fn(page))
            rows_ = generic_cards(name, html, base_url, link_pat, region)
            for r_ in rows_:
                r_["evidence_grade"] = grade
                r_["lang"] = lang
            if not rows_:
                state = "selector_work"
                rows_ = [row(name, "raw_capture", f"page {page} shape unknown",
                             url_fn(page), html[:1200], region=region,
                             needs_selector_work=True)]
        except Exception as exc:                                         # noqa: BLE001
            state = f"error:{type(exc).__name__}"
            rows_ = [row(name, "fetch_error", str(exc)[:180], url_fn(page),
                         region=region, needs_selector_work=True)]
        real = [r_ for r_ in rows_ if not r_.get("needs_selector_work")]
        total_real += len(real)
        d = INTEL / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"discoveries_{now:%Y%m%d_%H%M}.json").write_text(
            json.dumps(rows_, indent=1, default=str), "utf-8")
        results[name] = {"discoveries": rows_, "count": len(rows_)}
        update_coverage(name, region, lang, grade, state, len(real))
        print(f"  {name} p{page}: {len(real)} real / {len(rows_)} rows [{state}]")
    # FBS tape rides along
    try:
        tape = mine_fbs_tape()
        d = INTEL / "fbs_tape"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"discoveries_{now:%Y%m%d_%H%M}.json").write_text(
            json.dumps(tape, indent=1, default=str), "utf-8")
        results["fbs_tape"] = {"discoveries": tape, "count": len(tape)}
        print(f"  fbs_tape: {len(tape)} rows")
    except Exception as exc:                                             # noqa: BLE001
        print(f"  fbs_tape: {exc}")
    STATE.write_text(json.dumps(st, indent=0), "utf-8")
    latest_p = INTEL / "latest_discoveries.json"
    latest = _read(latest_p, {})
    latest.update(results)
    latest_p.write_text(json.dumps(latest, indent=1, default=str), "utf-8")
    print(f"regional hunters: {total_real} real account rows across {len(SOURCES)} grounds")
    return results


if __name__ == "__main__":
    run_and_save()
