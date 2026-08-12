#!/usr/bin/env python3
"""ARM THE PAGER — and prove delivery, because an unproven channel is a silent one.

WHY THIS EXISTS. `data/ALERT_CHANNELS_SILENT` has carried the same line since 2026-07-30:

    no alert delivery on ANY channel in 24h (armed: NONE -- arming owed)

Thirteen days. The desk's capability ratchet names it the DESK-WIDE BINDING CONSTRAINT at 0.0/10,
and it is the one defect that makes every other number less trustworthy: with no channel armed,
no failure since 30 July has woken anybody. Going live with real capital behind a dead pager
means the first thing you learn about a problem is the balance.

The delivery machinery was already built (libs/ops/alert_channels: registry, ledger, canary,
all_silent_since). What was missing was the CONFIG, and the reason it stayed missing is that
arming it by hand means writing JSON with the right shape into the right path with the right
permissions and then hoping. This makes it one command.

THE RULE THIS ENFORCES, and it is the whole point: ARMED IS NOT A CONFIG STATE, IT IS A DELIVERED
MESSAGE. Writing a channel file proves nothing -- a typo'd token, a revoked webhook, a chat the
bot was removed from all look identical to a correct config until something actually needs to
page. So this script writes the config, sends a REAL page through the real path, reads the
delivery ledger back, and REVERTS the config if nothing was delivered. You cannot end this
script believing you are armed when you are not.

    python scripts/arm_alert_channel.py --kind ntfy     --topic <your-topic>
    python scripts/arm_alert_channel.py --kind telegram --token <t> --chat-id <c>
    python scripts/arm_alert_channel.py --kind webhook  --url https://...
    python scripts/arm_alert_channel.py --verify        # re-test what is already armed

SECRETS NEVER REACH STDOUT OR THE LEDGER. The config is written 0600, values are masked in every
line this prints, and the delivery ledger already hashes titles rather than storing them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import alert_channels as AC  # noqa: E402

CONFIG = _ROOT / "data/secrets/alert_channels.json"
SILENT_FLAG = _ROOT / "data/ALERT_CHANNELS_SILENT"


def _mask(v: str) -> str:
    s = str(v or "")
    return f"{s[:3]}...{s[-2:]}" if len(s) > 7 else "***"


def _build(args) -> dict:
    kind = args.kind
    if kind == "ntfy":
        if not args.topic:
            raise SystemExit("--topic is required for ntfy")
        return {"kind": "ntfy", "topic": args.topic}
    if kind == "telegram":
        if not (args.token and args.chat_id):
            raise SystemExit("--token and --chat-id are required for telegram")
        return {"kind": "telegram", "token": args.token, "chat_id": args.chat_id}
    if kind == "webhook":
        if not args.url:
            raise SystemExit("--url is required for webhook")
        return {"kind": "webhook", "url": args.url}
    raise SystemExit(f"unknown --kind {kind!r}; valid: ntfy telegram webhook")


def _write(channels: list[dict]) -> None:
    """0600 in a gitignored directory. A pager token in a world-readable file is a credential
    leak that also happens to page you."""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps({"channels": channels}, indent=1), "utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(CONFIG)
    os.chmod(CONFIG, 0o600)


def _deliveries_since(mark: str) -> list[dict]:
    return [r for r in AC.ledger_tail(200) if str(r.get("ts", "")) > mark and r.get("ok")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["ntfy", "telegram", "webhook"])
    ap.add_argument("--topic"), ap.add_argument("--token"), ap.add_argument("--chat-id")
    ap.add_argument("--url")
    ap.add_argument("--verify", action="store_true",
                    help="send a test page through whatever is already armed and report")
    ap.add_argument("--keep-on-failure", action="store_true",
                    help="do NOT revert the config if delivery fails (default: revert, so the "
                         "desk never believes it is armed when it is not)")
    args = ap.parse_args(argv)

    prior = CONFIG.read_text("utf-8") if CONFIG.exists() else None

    if not args.verify:
        if not args.kind:
            ap.error("give --kind (or --verify to test what is already armed)")
        chan = _build(args)
        existing = AC.load_channels()
        # ADDITIVE. A second independent channel is the entire point of the 12/13 panel finding:
        # two channels on one provider is one channel wearing two hats.
        merged = [c for c in existing if c.get("kind") != chan["kind"]] + [chan]
        _write(merged)
        shown = {k: (_mask(v) if k in ("token", "url", "chat_id", "topic") else v)
                 for k, v in chan.items()}
        print(f"wrote {CONFIG} (0600) with {len(merged)} channel(s); new: {shown}")

    st = AC.status()
    if not int(st.get("armed") or 0):
        print("NOT ARMED: no channels configured. Nothing to verify.")
        return 2

    mark = datetime.now(tz=UTC).isoformat()
    title = "QUANT DESK — arming verification"
    body = (f"Pager arming test at {mark}. If you are reading this, the channel is LIVE and the "
            "desk can reach you. No action needed.")
    AC.send_all(title, body)

    delivered = _deliveries_since(mark)
    kinds = sorted({str(r.get("channel")) for r in delivered})
    if delivered:
        # The flag clears itself on the next successful delivery -- nothing else clears it.
        if SILENT_FLAG.exists():
            SILENT_FLAG.unlink()
            print(f"cleared {SILENT_FLAG.name} — the silence flag is cleared by DELIVERY, "
                  "never by editing it")
        print(f"ARMED AND VERIFIED: {len(delivered)} delivery(ies) on {kinds}")
        print("Check the device now. If no message arrived, the transport accepted it and did "
              "not deliver it — re-run with a different channel rather than trusting this line.")
        return 0

    print(f"DELIVERY FAILED on every armed channel ({int(st.get('armed') or 0)} tried).")
    for r in AC.ledger_tail(6):
        print(f"   {r.get('channel')}: ok={r.get('ok')} {str(r.get('detail'))[:110]}")
    if not args.keep_on_failure:
        if prior is None:
            CONFIG.unlink(missing_ok=True)
        else:
            CONFIG.write_text(prior, "utf-8")
            os.chmod(CONFIG, 0o600)
        print("REVERTED the config. A config that cannot deliver is worse than none: it reads as "
              "armed on every dashboard while the desk is silent. Fix the credential and re-run.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
