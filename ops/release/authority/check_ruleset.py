#!/usr/bin/env python3
"""Refuse to apply ruleset_live.json until it is safe to (ops/release/authority/LEVEL2.md step 5).

    python ops/release/authority/check_ruleset.py [ruleset.json]   # exit 0: safe to import

Safe means:
- the required check is pinned to the authority App;
- the admin bypass is pull-request-only;
- no bypass actor is a placeholder (actor_id 0);
- no bypass actor is GitHub Actions or any other identity whose credential a PR's own workflow
  can use (#650 audit MF: a same-repo pull_request run gets a write-scoped GITHUB_TOKEN, so an
  Actions bypass lets any branch push LIVE past the authority).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

AUTHORITY_APP_ID = 5601819
GITHUB_ACTIONS_APP_ID = 15368


def problems(rs: dict[str, Any]) -> list[str]:
    out: list[str] = []
    rules = {r.get("type"): r for r in rs.get("rules") or []}
    need = ((rules.get("required_status_checks") or {}).get("parameters") or {}).get(
        "required_status_checks"
    ) or []
    if need != [{"context": "release-authority", "integration_id": AUTHORITY_APP_ID}]:
        out.append("the required check must be exactly release-authority from the authority App")
    if rs.get("enforcement") != "active":
        out.append("enforcement must be active")
    for b in rs.get("bypass_actors") or []:
        kind, ident, mode = b.get("actor_type"), b.get("actor_id"), b.get("bypass_mode")
        if not ident:
            out.append(f"bypass actor {kind} has a placeholder id: fill in the state App's id")
        if kind == "Integration" and ident in (GITHUB_ACTIONS_APP_ID, AUTHORITY_APP_ID):
            out.append(f"Integration {ident} may not bypass (a PR's workflow or the signer)")
        if kind == "RepositoryRole" and mode != "pull_request":
            out.append("the admin bypass must be pull_request mode only (never direct pushes)")
        if kind not in ("Integration", "RepositoryRole"):
            out.append(f"bypass actor type {kind} is not allowed")
    integ = [b for b in rs.get("bypass_actors") or [] if b.get("actor_type") == "Integration"]
    if len(integ) != 1:
        out.append("exactly one App (the state publisher) may bypass")
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path(__file__).with_name("ruleset_live.json")
    got = problems(json.loads(path.read_text(encoding="utf-8")))
    for p in got:
        print(f"NOT SAFE: {p}")
    if not got:
        print("SAFE to import")
    return 1 if got else 0


if __name__ == "__main__":
    sys.exit(main())
