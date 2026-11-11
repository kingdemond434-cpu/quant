r"""Send one alert on every armed channel; exit 0 only if at least one channel delivered it.

The box gate's registry path (QUANT_REGISTRY_NOTIFY, .github/scripts/audit_gate.py) runs this to
send its veto notice, and starts the 24 h veto window only on exit 0, so an unarmed pager or a
failed send can never start a window that nobody was told about. It runs from ITS OWN tree's root
whatever the caller's directory (the gate calls it from its own clone), so the live tree's
data/secrets/alert_channels.json resolves:

    python C:\opt\quant\libs\ops\send_alert.py "<title>" "<body>"

A helper the gate invokes, not a clocked job: it lives in libs/ops, outside the birth fence's
executable areas (scripts/check_birth_obligations.py EXEC_AREAS).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.ops.alert_channels import send_all  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: send_alert.py TITLE BODY", file=sys.stderr)
        return 2
    os.chdir(ROOT)  # the channel config and the delivery ledger are relative to the tree root
    got = send_all(argv[0], argv[1])
    print(f"armed {got.get('armed', 0)}, delivered {got.get('delivered', 0)}")
    return 0 if int(got.get("delivered") or 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
