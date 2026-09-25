"""RETIRED 2026-09-25 -- this script refuses to run.

It started a cloudflared QUICK tunnel to http://127.0.0.1:8899, the listener registered by
install_local_dashboard.ps1, which was then a bare ``python -m http.server`` with no
authentication. That published live equity, positions and sleeve names to anyone holding the
random trycloudflare.com hostname -- and the loopback bind was no protection, because a tunnel
delivers every public request to its origin as 127.0.0.1.

It was already recorded retired on 2026-09-23 (docs/research/retirements.jsonl) but the live path
was copied, not moved, so anything scheduled against it could still start the tunnel. This stub
closes that: it exits non-zero with a message and starts nothing.

If remote access to the dashboard is wanted, the supported path is scripts/serve_dashboard.py
(token required on every request by default) behind scripts/run_tunnel.py, which fronts the
token-gated server and never an ungated one. The original source is in git history
(6d5bd697e) and archived at desks/mt5/scripts/_retired/dashboard_tunnel.py.
"""
from __future__ import annotations

import sys

MESSAGE = (
    "dashboard_tunnel.py is RETIRED: it tunnelled an unauthenticated dashboard to the internet. "
    "Use scripts/serve_dashboard.py (token-gated) behind scripts/run_tunnel.py instead."
)


def main() -> int:
    print(f"REFUSING: {MESSAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
