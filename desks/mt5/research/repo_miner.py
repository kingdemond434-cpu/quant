"""The public-system miner: a new repository is fuel, not a competitor.

    Discover -> Extract -> Reimplement -> Mutate -> Falsify -> Validate -> Measure -> Allocate

This is the DISCOVER and EXTRACT stages for public code. A watchlist (`data/repo_watchlist.json`)
names repositories and search queries; each run fetches what it can reach (README, tree, the
files the watchlist points at, licence) through the GitHub API with the host's own credentials
if any, caches the text under `data/repo_cache/`, and extracts MECHANISM CLAIMS by a declared
vocabulary -- a sentence that names a market quantity, a direction and a horizon becomes a
hypothesis card. Every claim is written to the deepening queue as `repo_mechanism` with the
provenance line `libs.data.datahub.record_mined_source` requires: repo, URL, commit, licence,
file, and the policy (concept reimplemented; code copied only under a copy-permitted licence,
which by default nothing is).

OFF THE BOX the network is usually absent; the miner then works the cache and says so. The
worker seat (an LLM, on the box) is the one that turns a claim into an exact recipe through
the compiler's existing contract -- this module never invents a rule.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

WATCHLIST = _DESK / "data" / "repo_watchlist.json"
CACHE = _DESK / "data" / "repo_cache"
REPORT = _DESK / "reports" / "REPO_MINER.json"
API = "https://api.github.com"

#: Mechanism vocabulary: a claim must name a quantity, a direction word and a horizon word.
QUANTITY = ("momentum", "reversal", "mean reversion", "carry", "swap", "breakout", "range",
            "volatility", "spread", "order flow", "imbalance", "positioning", "cot", "seasonal",
            "session", "open", "close", "fix", "rollover", "gap", "correlation", "cointegration",
            "pairs", "lead", "lag", "surprise", "cpi", "nfp", "rate", "yield", "factor",
            "residual", "skew", "kurtosis", "liquidity", "flow", "inventory", "basis")
DIRECTION = ("long", "short", "buy", "sell", "fade", "follow", "revert", "continue", "increase",
             "decrease", "predict", "forecast", "outperform", "underperform", "positive",
             "negative")
HORIZON = ("minute", "hour", "hourly", "daily", "day", "week", "weekly", "month", "monthly",
           "intraday", "overnight", "bar", "bars", "h1", "h4", "d1")


def _watchlist() -> dict[str, Any]:
    try:
        return json.loads(WATCHLIST.read_text("utf-8"))
    except (OSError, ValueError):
        return {"repos": [], "queries": []}


def _get(url: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "quant-repo-miner"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


GITEE_API = "https://gitee.com/api/v5"


def _fetch_repo(full: str, host: str = "github") -> dict[str, Any] | None:
    """Metadata + README text + licence, via the host's API. None when unreachable.

    GITEE IS A HOST, NOT A SPECIAL CASE (2026-09-04). The Chinese code host carries the vn.py
    lineage, factor libraries and competition strategies that never reach GitHub; its v5 API has
    the same shape (repo metadata, base64 README) so one reader serves both.
    """
    try:
        import base64
        if host == "gitee":
            meta = _get(f"{GITEE_API}/repos/{full}")
            readme = _get(f"{GITEE_API}/repos/{full}/readme")
            lic = meta.get("license") or "NONE"
        else:
            meta = _get(f"{API}/repos/{full}")
            readme = _get(f"{API}/repos/{full}/readme")
            lic = (meta.get("license") or {}).get("spdx_id") or "NONE"
        text = base64.b64decode(readme.get("content", "")).decode("utf-8", errors="replace")
        return {"repo": full, "host": host, "url": meta.get("html_url"),
                "commit": meta.get("pushed_at"), "license": str(lic),
                "stars": meta.get("stargazers_count"), "description": meta.get("description"),
                "readme": text, "fetched_utc": datetime.now(tz=UTC).isoformat()}
    except Exception:
        return None


def _cached(full: str) -> dict[str, Any] | None:
    p = CACHE / (full.replace("/", "__") + ".json")
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _cache(doc: dict[str, Any]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / (str(doc["repo"]).replace("/", "__") + ".json")).write_text(
        json.dumps(doc, indent=1), "utf-8")


def extract_claims(text: str, *, max_claims: int = 40) -> list[dict[str, Any]]:
    """Sentences that name a quantity, a direction and a horizon. Verbatim, never paraphrased.

    BILINGUAL since 2026-09-04: `libs.research.mechanism_claims` speaks the Chinese practitioner
    register too, maps instruments to MT5 analogues and drops crypto-exchange venues, so a Gitee
    README and a GitHub one are read by the same grammar. The English vocabulary above stays as
    the documented seed of that grammar.
    """
    from libs.research.mechanism_claims import extract_claims as _bilingual
    return _bilingual(text, max_claims=max_claims)


def run(fetch: bool = True, write: bool = True) -> dict[str, Any]:
    wl = _watchlist()
    mined: list[dict[str, Any]] = []
    unreachable: list[str] = []
    tasks: list[dict[str, Any]] = []
    try:
        from libs.data.datahub import copy_allowed, record_mined_source
    except Exception:
        record_mined_source = None                               # type: ignore[assignment]
        copy_allowed = lambda lic: False                         # noqa: E731
    for entry in wl.get("repos", []):
        full = str(entry.get("repo") if isinstance(entry, dict) else entry)
        host = str(entry.get("host", "github")) if isinstance(entry, dict) else "github"
        doc = (_fetch_repo(full, host) if fetch else None) or _cached(full)
        if doc is None:
            unreachable.append(full)
            continue
        if fetch and "fetched_utc" in doc:
            _cache(doc)
        claims = extract_claims(f"{doc.get('description') or ''}\n{doc.get('readme', '')}")
        for c in claims:
            if record_mined_source is not None:
                with contextlib.suppress(Exception):
                    record_mined_source(repo=full, url=str(doc.get("url")),
                                        commit=str(doc.get("commit")),
                                        license_=str(doc.get("license")), file="README",
                                        mechanism=c["claim"][:200], code_copied=False,
                                        commercial_restriction=(not copy_allowed(
                                            str(doc.get("license")))))
            tasks.append({"source": "repo_miner", "kind": "repo_mechanism",
                          "title": f"{full}: {c['claim'][:90]}",
                          "description": (f"Public claim in {full} (licence {doc.get('license')}, "
                                          f"{doc.get('stars')} stars): \"{c['claim']}\". "
                                          "Extract the exact mechanism as an MT5 family and "
                                          "parameters if the text states one; otherwise reject "
                                          "with why. Concept only -- never copy code."),
                          "url": str(doc.get("url")), "license": doc.get("license"),
                          "symbols": list((c.get("instruments") or {}).get("analogues") or []),
                          "lang": c.get("lang"), "claim_hash": c["claim_hash"], "status": None,
                          "consumer": "deepening_worker (repo_mechanism)",
                          "quantities": c["quantities"], "horizon": c["horizon"]})
        mined.append({"repo": full, "license": doc.get("license"), "stars": doc.get("stars"),
                      "claims": len(claims), "cached": "fetched_utc" in doc,
                      "copy_allowed": copy_allowed(str(doc.get("license")))})
    doc_out = {"generated_utc": datetime.now(tz=UTC).isoformat(),
               "watchlist": len(wl.get("repos", [])),
               "mined": mined, "unreachable": unreachable, "tasks": len(tasks),
               "network": fetch and not (unreachable and not mined),
               "loop": "Discover -> Extract -> (deepening_worker) Reimplement -> proposers Mutate "
                       "-> falsifiers -> gauntlet Validate -> allocator Measure dElogW -> Allocate "
                       "-> hypothesis graph Learn -> Repeat"}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc_out, indent=1), "utf-8")
        if tasks:
            try:
                from research.regime_coverage import _merge_into_queue
                _merge_into_queue(tasks, source="repo_miner")
            except Exception:
                pass
    return doc_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="work the cache only")
    a = ap.parse_args()
    d = run(fetch=not a.no_fetch)
    print(f"REPO MINER  {d['watchlist']} watched, {len(d['mined'])} mined, "
          f"{len(d['unreachable'])} unreachable, {d['tasks']} mechanism tasks")
    for m in d["mined"]:
        print(f"  {m['repo']:40s} {m['license']!s:12s} claims={m['claims']} "
              f"copy_allowed={m['copy_allowed']}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
