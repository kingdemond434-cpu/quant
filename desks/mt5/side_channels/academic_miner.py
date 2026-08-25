"""SSRN/arXiv academic papers miner.

Scrapes SSRN and arXiv for quantitative finance papers.
New alpha ideas often appear in academic papers before they become common knowledge.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "academic"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# arXiv API for quantitative finance
ARXIV_URL = "http://export.arxiv.org/api/query"
ARXIV_QUERIES = [
    "quantitative trading strategy",
    "forex prediction machine learning",
    "gold price prediction",
    "algorithmic trading alpha",
    "momentum strategy financial",
    "mean reversion trading",
]

# SSRN search
SSRN_URL = "https://papers.ssrn.com/sol3/results.cfm"


def mine_arxiv() -> list[dict]:
    """Search arXiv for quant finance papers."""
    discoveries = []
    for query in ARXIV_QUERIES:
        try:
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": 5,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            resp = requests.get(ARXIV_URL, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()

            # Parse XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", "", ns).replace("\n", " ").strip()
                summary = entry.findtext("atom:summary", "", ns).replace("\n", " ").strip()[:300]
                link = entry.findtext("atom:link[@type='text/html']", "", ns)
                if not link:
                    for l in entry.findall("atom:link", ns):
                        if l.get("type") == "text/html":
                            link = l.get("href", "")
                            break
                if not link:
                    link = entry.findtext("atom:id", "", ns)

                published = entry.findtext("atom:published", "", ns)

                combined = f"{title} {summary}"
                # Extract trading-related terms
                trading_terms = ["forex", "gold", "currency", "trading", "momentum",
                                 "mean reversion", "alpha", "risk", "portfolio", "strategy"]
                matches = [t for t in trading_terms if t.lower() in combined.lower()]

                if matches:
                    discoveries.append({
                        "source": "arxiv",
                        "type": "academic_paper",
                        "title": title,
                        "summary": summary[:200],
                        "url": link,
                        "published": published,
                        "trading_terms": matches,
                        "symbols": [],  # Will be mapped by converter
                        "confidence": min(0.5, len(matches) * 0.1),
                    })
        except Exception:
            continue
    return discoveries


def mine_ssrn() -> list[dict]:
    """Search SSRN for finance papers."""
    discoveries = []
    try:
        params = {"q": "forex trading strategy", "npage": 1}
        resp = requests.get(SSRN_URL, params=params, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            text = resp.text
            # Extract paper titles
            titles = re.findall(r'class="title.*?href="(/sol3/papers.cfm\?abstract_id=\d+)".*?>(.*?)</a>', text, re.DOTALL)
            for link, title in titles[:10]:
                clean_title = re.sub(r'<[^>]+>', '', title).strip()
                discoveries.append({
                    "source": "ssrn",
                    "type": "academic_paper",
                    "title": clean_title,
                    "url": f"https://papers.ssrn.com{link}",
                    "symbols": [],
                    "confidence": 0.3,
                })
    except Exception:
        pass
    return discoveries


def run_and_save() -> list[dict]:
    arxiv = mine_arxiv()
    ssrn = mine_ssrn()
    all_disc = arxiv + ssrn
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(all_disc, indent=2, default=str), encoding="utf-8")
    print(f"academic: {len(all_disc)} discoveries saved ({len(arxiv)} arxiv, {len(ssrn)} ssrn)")
    return all_disc


if __name__ == "__main__":
    run_and_save()
