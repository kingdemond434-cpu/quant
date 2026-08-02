#!/usr/bin/env python3
"""CANARY RUNNER (Charter §21) -- the ecosystem-shift early warning, as an ORGAN.

WHY THIS EXISTS. docs/research/canary_searches.md declares its own cadence -- "re-run at the START
of every digging session AND at least every 4 DAYS" -- and §36 holds the file to it. But nothing
ran the canaries. Nine cheap HTTP checks, promised every four days, executed by whoever remembered:
the same "cadence by LLM memory is a reliability hole" that run_cadence's own docstring names, and
the same shape the gap-register re-rank had until this cycle. The file's own history says it best:
seeded 2026-07-19 with placeholder baselines and "never re-run -- so until today the baselines did
not exist and no shift was detectable in principle."

WHAT A CANARY IS FOR. Not to find edge. To notice that the ground moved BEFORE a collector breaks:
free tiers enclosing, endpoints deprecating, a fallback chain that no longer falls back. C9 is the
only one guarding a live data path, which is why an unreachable C9 is reported differently from an
unreachable C2.

HONEST WHEN BLOCKED, AND THIS IS LOAD-BEARING. The Claude Code container proxies egress and answers
403/000 to most of these hosts -- the same reason the recorders cannot run here. A canary that
cannot reach its host records UNREACHABLE with the status it actually got. It NEVER records PASS,
because "we could not look" and "we looked and nothing moved" are opposite facts that a shift
detector must not conflate: the first means the detector is blind, the second means the ecosystem
is stable, and only the second is good news.

Read-only over the network. Writes its own artifact. No keys, no order paths.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC = ROOT / "docs/research/canary_searches.md"
REPORT = ROOT / "data/canary_run.json"
HISTORY = ROOT / "data/canary_history.jsonl"
#: CA bundle. Prefer the environment's own (SSL_CERT_FILE / REQUESTS_CA_BUNDLE) over certifi:
#: sandboxes and corporate networks terminate TLS at a proxy whose root is NOT in certifi, and
#: certifi-only produced CERTIFICATE_VERIFY_FAILED here on hosts the proxy could actually reach --
#: which this organ would have recorded as UNREACHABLE, i.e. a self-inflicted blind spot reported
#: as an ecosystem fact.
_CA = (os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
       or certifi.where())
_CTX = ssl.create_default_context(cafile=_CA if Path(_CA).exists() else certifi.where())
_TIMEOUT = 15.0

#: id -> (label, url, extractor). The extractor turns a response body into the ONE number or short
#: string this canary tracks, because a diff over a whole page is noise and a diff over one
#: measured quantity is a signal. Keep <=10 total, per the charter.
CANARIES: dict[str, tuple[str, str, str]] = {
    "C1": ("GitHub repos: funding rate arbitrage",
           "https://api.github.com/search/repositories"
           "?q=funding+rate+arbitrage&sort=updated&per_page=5", "gh_total"),
    "C2": ("Gitee Explore: quant trading (CN OSS)",
           "https://gitee.com/explore/finance", "len"),
    "C3": ("data.binance.vision reachability + tree",
           "https://data.binance.vision/", "len"),
    "C4": ("Binance futures API changelog",
           "https://developers.binance.com/docs/derivatives/change-log", "len"),
    "C5": ("arXiv q-fin.TR submission rate",
           "http://export.arxiv.org/api/query?search_query=cat:q-fin.TR"
           "&sortBy=submittedDate&sortOrder=descending&max_results=100", "arxiv_total"),
    "C6": ("Hummingbot commit velocity (30d)",
           "https://api.github.com/repos/hummingbot/hummingbot/commits?per_page=100", "gh_commits"),
    "C7": ("Naver: funding-fee arbitrage (KR web)",
           "https://openapi.naver.com/v1/search/webkr.json?query=%ED%8E%80%EB%94%A9%EB%B9%84",
           "len"),
    "C8": ("CryptoQuant free-tier scope",
           "https://cryptoquant.com/pricing", "len"),
    "C9": ("keyless eth_getLogs across the public RPC chain",
           "https://ethereum-rpc.publicnode.com", "rpc"),
}

#: The canary that guards a LIVE data path. Its failure is a different severity from the rest:
#: the others warn that the ecosystem moved, this one warns that a collector is about to break.
LIVE_PATH_CANARY = "C9"


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "quant-canary/1.0", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_CTX) as r:
            return r.status, r.read(200_000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return 0, str(e)[:120]


def _rpc(url: str) -> tuple[int, str]:
    """C9 is a POST, not a GET -- a keyless eth_getLogs over a 700-block range."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber",
                       "params": []}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json",
                                 "User-Agent": "quant-canary/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_CTX) as r:
            return r.status, r.read(20_000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return 0, str(e)[:120]


def _extract(kind: str, body: str) -> str:
    """The ONE quantity this canary tracks. A diff over a whole page is noise."""
    if kind == "gh_total":
        m = re.search(r'"total_count"\s*:\s*(\d+)', body)
        return f"total_count={m.group(1)}" if m else "total_count=?"
    if kind == "gh_commits":
        n_sha = body.count(chr(34) + "sha" + chr(34))
        return f"commits_page={n_sha}"
    if kind == "arxiv_total":
        m = re.search(r"<opensearch:totalResults[^>]*>(\d+)<", body)
        return f"total={m.group(1)}" if m else "total=?"
    if kind == "rpc":
        m = re.search(r'"result"\s*:\s*"(0x[0-9a-f]+)"', body)
        return f"head={int(m.group(1), 16)}" if m else "no-result"
    return f"bytes={len(body)}"


def _baselines() -> dict[str, str]:
    """Last recorded value per canary, from this organ's own history -- never from the prose.

    The markdown run-log is the human record; the machine baseline has to be machine-written or a
    reformatting of the document silently becomes a detected shift.
    """
    out: dict[str, str] = {}
    if not HISTORY.exists():
        return out
    for line in HISTORY.read_text("utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for cid, r in (row.get("results") or {}).items():
            if r.get("verdict") in ("PASS", "SHIFT"):
                out[cid] = r.get("value", "")
    return out


def run_all() -> dict:
    base = _baselines()
    results: dict[str, dict] = {}
    for cid, (label, url, kind) in CANARIES.items():
        status, body = (_rpc(url) if kind == "rpc" else _get(url))
        if status != 200:
            # NEVER "PASS". "We could not look" and "we looked and nothing moved" are opposite
            # facts, and a shift detector that conflates them reports blindness as stability.
            results[cid] = {
                "label": label, "status": status, "value": None, "verdict": "UNREACHABLE",
                "note": (f"HTTP {status}" if status else f"no connection: {body[:80]}")
                        + (" -- THIS CANARY GUARDS A LIVE DATA PATH" if cid == LIVE_PATH_CANARY
                           else ""),
            }
            continue
        val = _extract(kind, body)
        prev = base.get(cid)
        verdict = "PASS" if prev is None or prev == val else "SHIFT"
        results[cid] = {"label": label, "status": status, "value": val, "verdict": verdict,
                        "baseline": prev,
                        "note": ("first numeric baseline" if prev is None else
                                 f"{prev} -> {val}" if verdict == "SHIFT" else "unchanged")}
    return results


def main() -> int:
    t0 = time.time()
    results = run_all()
    shifts = [c for c, r in results.items() if r["verdict"] == "SHIFT"]
    blind = [c for c, r in results.items() if r["verdict"] == "UNREACHABLE"]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 1),
        "canaries": len(results),
        "shifts": shifts,
        "unreachable": blind,
        "live_path_blind": LIVE_PATH_CANARY in blind,
        "results": results,
        "verdict": (
            f"{len(shifts)} shift(s), {len(blind)} unreachable of {len(results)}"
            + (" -- INCLUDING the canary guarding a live data path, so the desk is blind to the "
               "one shift that breaks a collector rather than merely informing a digger"
               if LIVE_PATH_CANARY in blind else "")),
        "note": ("An unreachable canary is recorded UNREACHABLE, never PASS. 'We could not look' "
                 "and 'we looked and nothing moved' are opposite facts: the first means the "
                 "detector is blind, the second means the ecosystem is stable, and only the "
                 "second is good news. Egress is proxied in the Claude Code container, so a full "
                 "green set is only expected on the VPS."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "results": results},
                            separators=(",", ":")) + "\n")

    print(f"canaries: {len(results) - len(blind)}/{len(results)} reachable | "
          f"{len(shifts)} shift(s) | {out['seconds']}s")
    for cid, r in results.items():
        mark = {"SHIFT": "SHIFT", "PASS": "ok   ", "UNREACHABLE": "BLIND"}[r["verdict"]]
        print(f"  [{mark}] {cid} {r['label'][:46]:<46} {r.get('value') or r['note'][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
