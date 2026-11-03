"""Send one alert on every armed channel; exit 0 only if at least one channel delivered it.

The box gate's registry path (QUANT_REGISTRY_NOTIFY, .github/scripts/audit_gate.py) runs this to
send its veto notice, and starts the 24 h veto window only on exit 0, so an unarmed pager or a
failed send can never start a window that nobody was told about. Run it from the live tree, where
data/secrets/alert_channels.json is:

    python scripts/send_alert.py "<title>" "<body>"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.ops.alert_channels import send_all


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: send_alert.py TITLE BODY", file=sys.stderr)
        return 2
    got = send_all(argv[0], argv[1])
    print(f"armed {got.get('armed', 0)}, delivered {got.get('delivered', 0)}")
    return 0 if int(got.get("delivered") or 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
