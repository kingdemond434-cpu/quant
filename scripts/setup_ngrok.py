"""Set up ngrok: save authtoken (+ optional static domain), configure the agent.

    python scripts/setup_ngrok.py <AUTHTOKEN> [your-domain.ngrok-free.app]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_NGROK = Path("tools/ngrok.exe")
_SECRETS = Path("data/secrets/ngrok.json")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/setup_ngrok.py <AUTHTOKEN> [domain.ngrok-free.app]")
        raise SystemExit(2)
    token = sys.argv[1].strip()
    domain = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    _SECRETS.parent.mkdir(parents=True, exist_ok=True)
    _SECRETS.write_text(json.dumps({"authtoken": token, "domain": domain}, indent=2), "utf-8")
    subprocess.run([str(_NGROK), "config", "add-authtoken", token], check=False,
                   capture_output=True, text=True)
    print(f"ngrok configured (token saved). domain = {domain or '(ephemeral -- rotates)'}")


if __name__ == "__main__":
    main()
