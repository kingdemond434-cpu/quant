"""EDGAR FILING COMPILER -> CROSS-ASSET TRANSMISSION (event lane only).

Single-name equities are traded on news, reports and earnings reaction and never hunted for
statistical hypotheses (the two-lane order, 2026-09-06). This cell reads SEC filings as EVENTS
and asks only what a burst of disclosure does to the instruments it transmits into: the US
index CFDs, the dollar index and gold. The filer is metadata; no equity symbol ever leaves.

WHERE FILINGS COME FROM. The public EDGAR endpoints (full-text search `efts.sec.gov`, XBRL
frames `data.sec.gov`) are declared in `EDGAR_HOSTS`. They are fetched ONLY when the pass allows
network (`ctx.network_allowed`, i.e. the runner was told so explicitly), the federation policy
is `allowlist`, the access classifier confirms machine use is allowed for the endpoint, and a
User-Agent is configured (`QUANT_EDGAR_UA`, SEC fair-access policy). Otherwise the cell runs on
the cached filings under `data/edgar_cache/*.json`, and with no cache it is UNMEASURED with a
fetch task naming what would fill it. The network claim is DECLARED, NOT ENFORCED on this host
(the sandbox module says the same); saying otherwise would be the lie the law forbids.

WHAT LEAVES. A dataset row (the cache census), representations (daily filing bursts by form
and item), and event hypotheses on transmission instruments with the burst dates as evidence:
`overnight_drift` on the index after an earnings-filing (8-K item 2.02) burst day,
`volume_spike` on the index on 10-K/10-Q season peaks, `volatility_squeeze` on gold and the
dollar index into a burst. The gauntlet judges every one.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from libs.research import adapters as A
from libs.research import external_federation as fed
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "edgar_transmission"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "financial_nlp"
UPSTREAM = ()
FALLBACK = "cached EDGAR full-text hits and XBRL frames compiled into daily filing bursts"
EDGAR_HOSTS: tuple[str, ...] = ("efts.sec.gov", "data.sec.gov")
FULL_TEXT = "https://efts.sec.gov/LATEST/search-index"
CACHE_DIR = "edgar_cache"
#: Transmission instruments by mechanism; a symbol absent from the bundle is skipped.
INDEX_SYMBOLS = ("US500", "NAS100", "US30", "US2000")
MACRO_SYMBOLS = ("USDX", "XAUUSD")
FORMS = ("8-K", "10-K", "10-Q")
BURST_Z = 2.0
FETCH_TIMEOUT_S = 20


def _cache(ctx: CellContext) -> Path:
    return ctx.data / CACHE_DIR


def machine_use_allowed(url: str) -> tuple[bool, str]:
    """The access classifier's verdict for a public EDGAR endpoint; refused when it cannot be
    read (absence is not a permission)."""
    try:
        from libs.research import access_classifier as ac
        v = ac.classify({"url": url, "source_class": "official_statement", "licence": "public",
                         "is_open_data": True, "robots": "allowed",
                         "terms": "SEC fair access: 10 requests/second with a User-Agent"})
        return bool(v.machine_use_allowed and not v.refused), v.reason
    except Exception as exc:
        return False, f"classifier unavailable: {type(exc).__name__}"


def fetch_full_text(query: str, forms: tuple[str, ...], *, since: str, ua: str) -> dict[str, Any]:
    url = FULL_TEXT + "?" + urlencode({"q": query, "forms": ",".join(forms), "dateRange":
                                       "custom", "startdt": since})
    req = Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return dict(json.loads(resp.read(4_000_000).decode("utf-8")))


def _hits(doc: Any) -> list[dict[str, Any]]:
    """Filing rows from either a raw EDGAR full-text response or this cell's cache shape."""
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("hits"), dict):
        rows = doc["hits"].get("hits") or []
        out = []
        for r in rows:
            src = r.get("_source") or {}
            out.append({"form": str(src.get("form") or ""), "filed": str(src.get("file_date")
                                                                          or "")[:10],
                        "items": [str(i) for i in (src.get("items") or [])],
                        "sic": str(src.get("sics", [""])[0] if src.get("sics") else "")})
        return out
    if isinstance(doc.get("hits"), list):
        return [dict(h) for h in doc["hits"] if isinstance(h, dict)]
    return []


def compile_bursts(hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Daily counts per form (and 8-K item 2.02) and the days that are bursts (z >= BURST_Z)."""
    import numpy as np
    daily: dict[str, Counter[str]] = {f: Counter() for f in (*FORMS, "8-K:2.02")}
    for h in hits:
        form, day = str(h.get("form") or ""), str(h.get("filed") or "")[:10]
        if not day or form not in FORMS:
            continue
        daily[form][day] += 1
        if form == "8-K" and any(str(i).startswith("2.02") for i in h.get("items") or []):
            daily["8-K:2.02"][day] += 1
    out: dict[str, Any] = {}
    for key, counter in daily.items():
        if not counter:
            continue
        days = sorted(counter)
        counts = np.asarray([counter[d] for d in days], dtype=float)
        z = (counts - counts.mean()) / max(counts.std(), 1e-12) if counts.shape[0] > 3 \
            else np.zeros_like(counts)
        out[key] = {"days": len(days), "total": int(counts.sum()), "mean": float(counts.mean()),
                    "bursts": [days[i] for i in np.flatnonzero(z >= BURST_Z)][-12:],
                    "last_day": days[-1], "last_count": int(counts[-1])}
    return out


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    cache = _cache(ctx)
    files = sorted(cache.glob("*.json")) if cache.exists() else []
    fetched: dict[str, Any] = {"attempted": False, "why": ""}
    network_ok = ctx.network_allowed and fed.POLICY.network == "allowlist"
    if network_ok and not ctx.dry_run:
        ua = os.environ.get("QUANT_EDGAR_UA", "")
        allowed, why = machine_use_allowed(FULL_TEXT)
        if not ua:
            fetched = {"attempted": False, "why": "no User-Agent configured (QUANT_EDGAR_UA); SEC "
                                                 "fair-access policy requires one"}
        elif not allowed:
            fetched = {"attempted": False, "why": f"machine use not allowed: {why}"}
        else:
            since = (datetime.now(tz=UTC) - timedelta(days=30)).date().isoformat()
            try:
                doc = fetch_full_text('"results of operations"', FORMS, since=since, ua=ua)
                rows = _hits(doc)
                cache.mkdir(parents=True, exist_ok=True)
                out = cache / f"fulltext_{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
                out.write_text(json.dumps({"fetched_at": datetime.now(tz=UTC).isoformat(),
                                           "endpoint": FULL_TEXT, "hosts": EDGAR_HOSTS,
                                           "hits": rows}, indent=1), encoding="utf-8")
                files.append(out)
                fetched = {"attempted": True, "why": "fetched", "rows": len(rows)}
            except Exception as exc:
                fetched = {"attempted": True, "why": f"{type(exc).__name__}: {exc}"[:200]}
    hits: list[dict[str, Any]] = []
    for p in files[-40:]:
        try:
            hits.extend(_hits(json.loads(p.read_text(encoding="utf-8-sig"))))
        except (OSError, ValueError):
            continue
    network_note = ("network: allowlist DECLARED for " + ", ".join(EDGAR_HOSTS)
                    + " (UNENFORCED_ON_THIS_HOST; fetch only with --allow-network)")
    if not hits:
        return A.packet(SYSTEM, bundle, trials=0, research_methods=[
            {"kind": "UNMEASURED", "system": SYSTEM,
             "why": f"no cached filings under {cache} and no fetch this pass "
                    f"({fetched['why'] or 'network not allowed for this pass'})",
             "task": {"kind": "fetch", "what": "EDGAR full-text hits (8-K/10-K/10-Q, last 30 "
                                                "days) into data/edgar_cache/*.json",
                      "how": "sandbox_runner --allow-network with QUANT_EDGAR_UA set, or drop "
                             "a cached response file", "hosts": list(EDGAR_HOSTS)},
             "network": network_note, "fetch": fetched}])
    bursts = compile_bursts(hits)
    reps = [{"kind": "filing_bursts", "form": k, **v, "lane": "EVENT",
             "representation": "a burst day is an information shock; what it transmits into is "
                               "the hypothesis"} for k, v in bursts.items()]
    present = set(bundle.universe)
    cands: list[dict[str, Any]] = []
    trials = len(bursts)
    e202 = bursts.get("8-K:2.02") or bursts.get("8-K")
    if e202 and e202["bursts"]:
        for sym in INDEX_SYMBOLS:
            if sym in present:
                cands.append(A.candidate(
                    "overnight_drift", [sym],
                    f"{sym}: on the {len(e202['bursts'])} days when 8-K earnings filings burst "
                    f"(z>={BURST_Z}; last {e202['bursts'][-1]}) the index carries a disclosure "
                    f"shock overnight -- an event-lane drift hypothesis on the index, never on "
                    f"the filer", horizon="24h", source=SYSTEM,
                    evidence={"burst_days": e202["bursts"], "form": "8-K item 2.02",
                              "filings_seen": e202["total"], "lane": "EVENT"}))
    season = bursts.get("10-Q") or bursts.get("10-K")
    if season and season["bursts"]:
        for sym in INDEX_SYMBOLS[:2]:
            if sym in present:
                cands.append(A.candidate(
                    "volume_spike", [sym],
                    f"{sym}: periodic-report season peaks ({len(season['bursts'])} burst days, "
                    f"last {season['bursts'][-1]}) concentrate index flow -- a volume-spike "
                    f"hypothesis on the index", horizon="24h", source=SYSTEM,
                    evidence={"burst_days": season["bursts"], "form": "10-Q/10-K",
                              "lane": "EVENT"}))
        for sym in MACRO_SYMBOLS:
            if sym in present:
                cands.append(A.candidate(
                    "volatility_squeeze", [sym],
                    f"{sym}: into a periodic-report burst the macro complex waits for the "
                    f"disclosure to clear -- a squeeze hypothesis on {sym} dated by the bursts",
                    horizon="24h", source=SYSTEM,
                    evidence={"burst_days": season["bursts"], "transmission": "equity "
                              "disclosure -> dollar/gold", "lane": "EVENT"}))
    dataset = {"kind": "edgar_cache_census", "files": len(files), "hits": len(hits),
               "forms": dict(Counter(str(h.get("form") or "") for h in hits)),
               "hosts": list(EDGAR_HOSTS), "network": network_note, "fetch": fetched,
               "single_names": "metadata only; no equity symbol leaves this cell"}
    return A.packet(SYSTEM, bundle, trials=trials, datasets=[dataset], representations=reps,
                    candidates=cands, note=f"{len(hits)} filings from {len(files)} cache files")
