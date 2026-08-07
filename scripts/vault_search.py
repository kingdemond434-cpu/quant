#!/usr/bin/env python3
"""Search the vault from a shell -- the entry point for CYCLES, AUDITS and SWEEPS.

The MCP server (scripts/vault_mcp_server.py) gives Claude the same index. This gives it to every
NON-INTERACTIVE organ, and that half matters more: an audit that cannot ask "has this been decided
before" re-decides it, and a sweep that cannot find the graveyard re-proposes a corpse. Both share
one index (libs/research/vault_index) so an organ and a session can never disagree about what the
vault says.

  scripts/vault_search.py "reduce_only close leg"
  scripts/vault_search.py --path CONSTITUTION "exhausted"      # one document
  scripts/vault_search.py --limit 20 --json "liquidation"      # machine-readable, for an organ
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.vault_index import build, format_hits  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="+")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--path", default="", help="substring filter on the file path")
    ap.add_argument("--json", action="store_true", help="machine-readable, for an organ")
    a = ap.parse_args()

    idx = build()
    hits = idx.search(" ".join(a.query), limit=a.limit, path_filter=a.path)
    if a.json:
        # `lexical: true` travels with EVERY machine result on purpose: a consumer that treats an
        # empty list as "the desk never considered this" would be wrong, and the flag is the only
        # thing standing between that inference and a re-decided question.
        print(json.dumps({
            "query": " ".join(a.query), "n_chunks_indexed": len(idx), "lexical": True,
            "empty_means": "these tokens are absent -- NOT that the decision was never made",
            "hits": [{"score": round(s, 3), "path": c.path, "line": c.line,
                      "heading": c.heading, "text": c.text[:1200]} for s, c in hits],
        }, indent=1))
    else:
        print(f"vault: {len(idx)} chunks indexed (LEXICAL/BM25, not semantic)\n")
        print(format_hits(hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
