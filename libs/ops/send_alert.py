r"""Send one alert on every armed channel; exit 0 only if at least one channel delivered it.

The box gate's registry path (QUANT_REGISTRY_NOTIFY, .github/scripts/audit_gate.py) runs this to
send its veto notice, and starts the 24 h veto window only on exit 0, so an unarmed pager or a
failed send can never start a window that nobody was told about. It runs from ITS OWN tree's root
whatever the caller's directory (the gate calls it from its own clone), so the live tree's
data/secrets/alert_channels.json resolves:

    python C:\opt\quant\libs\ops\send_alert.py "<title>" "<body>"

A helper the gate invokes, not a clocked job: it lives in libs/ops, outside the birth fence's
executable areas (scripts/check_birth_obligations.py EXEC_AREAS).

THE PAGER TOPIC (2026-11-17). With data/secrets/alert_channels.json absent nothing is armed, every
veto notice failed and the registry merged nothing. The box pager (scripts/run_alerts.py) has
paged the phone through its own ntfy topic (data/secrets/ntfy.json) since July. When no armed
channel delivered and none of them is ntfy, the notice goes to that EXISTING topic too: no new
credential and no human step. It is read here, never printed, and never minted. It lives in this
helper, not in alert_channels.load_channels, so the pager's own pages are not doubled (run_alerts
pushes ntfy itself and also calls send_all) and the money path's import closure is unchanged.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.ops import alert_channels  # noqa: E402
from libs.ops.alert_channels import send_all  # noqa: E402

#: the pager's topic files, as scripts/run_alerts.py `_BOX_SECRETS` reads them (tree-relative)
PAGER_TOPICS = (Path("data/secrets/ntfy.json"), Path("desks/mt5/data/secrets/ntfy.json"))


def pager_topic(paths: tuple[Path, ...] = PAGER_TOPICS) -> str | None:
    """The EXISTING pager topic, or None. A PS 5.1 copy may be UTF-16; never minted or printed."""
    for p in paths:
        try:
            raw = p.read_bytes()
            if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = raw.decode("utf-16")
            elif raw[1:2] == b"\x00":
                text = raw.decode("utf-16-le")
            else:
                text = raw.decode("utf-8-sig")
            topic = json.loads(text).get("topic")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
    return None


def via_pager(title: str, body: str) -> bool:
    """One send to the pager's topic, ledgered like every other channel; True if it delivered."""
    topic = pager_topic()
    if not topic:
        return False
    try:
        detail, ok = alert_channels._send_ntfy({"topic": topic}, title, body), True
    except Exception as exc:  # one channel's failure is a ledger row, never a crash
        detail, ok = f"{type(exc).__name__}: {exc}"[:200], False
    alert_channels._log("ntfy-pager", ok, detail, title)
    return ok


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: send_alert.py TITLE BODY", file=sys.stderr)
        return 2
    os.chdir(ROOT)  # the channel config and the delivery ledger are relative to the tree root
    got: dict[str, Any] = send_all(argv[0], argv[1])
    delivered = int(got.get("delivered") or 0)
    kinds = {str(r.get("channel")) for r in got.get("results") or [] if isinstance(r, dict)}
    pager = False
    if not delivered and "ntfy" not in kinds:
        pager = via_pager(argv[0], argv[1])
    print(f"armed {got.get('armed', 0)}, delivered {delivered}, pager {'yes' if pager else 'no'}")
    return 0 if delivered > 0 or pager else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
