#!/usr/bin/env python3
"""MCP stdio server exposing the vault to Claude -- layer 3 of the memory stack.

  layer 1  CLAUDE.md              the map        (always loaded, never changes)
  layer 2  .claude/desk-state.sh  the odometer   (live numbers, read at session start)
  layer 3  THIS                   the library    (208k lines, searched on demand)

WHY HAND-ROLLED JSON-RPC AND NOT THE MCP SDK. The SDK is not installed and cannot be: this clone is
network-policy-denied at the gateway (GAP row 91), so `pip install mcp` fails. The protocol needed
here is three methods over stdio, and implementing them in stdlib is smaller than the dependency
would be -- the same argument libs/execution/idempotency.py makes for staying stdlib on the order
path. It also means this server starts with no venv and no install step, which is what makes it
usable from a fresh clone.

PROTOCOL DISCIPLINE THAT IS EASY TO GET WRONG AND BREAKS THE TRANSPORT SILENTLY:
  * stdout carries JSON-RPC and NOTHING ELSE. One stray print corrupts the stream and the client
    reports a mysterious parse error rather than pointing at the print. All diagnostics go to
    stderr, which the client shows as server logs.
  * a NOTIFICATION (no `id`) MUST NOT get a response. Replying to `notifications/initialized` is
    the classic way to hang a handshake.
  * an unknown method returns a JSON-RPC error, never a crash -- a server that dies on an
    unrecognised method takes the whole connection with it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.vault_index import build, format_hits  # noqa: E402

PROTOCOL = "2024-11-05"
_INDEX: Any = None


def _index() -> Any:
    """Built once, lazily -- ~1,200 chunks parse in well under a second, but paying it on import
    would delay the handshake and a client that times out looks like a broken server."""
    global _INDEX
    if _INDEX is None:
        _INDEX = build()
        print(f"vault index: {len(_INDEX)} chunks", file=sys.stderr)
    return _INDEX


_TOOL = {
    "name": "vault_search",
    "description": (
        "Search this desk's institutional vault (docs/, ops/memory/ -- 208k lines of standing law, "
        "pre-registrations, gap register, playbooks, graveyard, deep sweeps). Use it BEFORE "
        "deciding anything the desk may already have decided, and before proposing research that "
        "may already be in the graveyard. LEXICAL (BM25), not semantic: an empty result means "
        "these TOKENS are absent, NOT that the question was never settled -- re-query with the "
        "vocabulary the document itself would use."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "terms to search for"},
            "limit": {"type": "integer", "default": 8},
            "path": {"type": "string",
                     "description": "optional path substring filter, e.g. CONSTITUTION"},
        },
        "required": ["query"],
    },
}


def _handle(req: dict[str, Any]) -> dict[str, Any] | None:
    method, rid = req.get("method"), req.get("id")
    if rid is None:                      # notification -- answering one hangs the handshake
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "quant-vault", "version": "1.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [_TOOL]}}
    if method == "tools/call":
        args = (req.get("params") or {}).get("arguments") or {}
        try:
            hits = _index().search(str(args.get("query", "")),
                                   limit=int(args.get("limit", 8)),
                                   path_filter=str(args.get("path", "")))
            body = format_hits(hits)
        except Exception as exc:         # a tool error is reported IN BAND, never as a crash
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"vault_search failed: {exc!r}"}],
                "isError": True}}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": body}]}}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue                     # never die on one malformed frame
        resp = _handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
