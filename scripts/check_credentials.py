#!/usr/bin/env python3
"""EVERY CREDENTIAL THIS DESK CAN USE -- what needs it, what breaks without it, how to get it.

THE PROBLEM THIS ANSWERS. Credential files are read from fifteen different places, each with its
own graceful-degradation path, and every one of those paths is silent by design -- a missing key
must never crash an organ. The sum of fifteen silent degradations is a desk that appears healthy
while most of it is switched off, and nothing anywhere states which of them are currently dark.

THIS IS AN INVENTORY, NOT A GATE. It reads presence and shape only. It NEVER prints a key, never
validates one against a venue (that would spend a rate limit to answer a question about a file),
and never writes anything. Every field it reports about a present file is a length or a boolean.

WHAT "BLOCKS" MEANS in the output: the capability is dark right now. What "degrades" means: the
capability runs with a documented fallback. The distinction matters because a dark organ produces
nothing and a degraded one produces something worse, and only the second is dangerous to trust.

    python scripts/check_credentials.py            # human table
    python scripts/check_credentials.py --json     # machine-readable
    python scripts/check_credentials.py --missing  # only what is absent, for a setup checklist
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "data/secrets"


@dataclass(frozen=True)
class Credential:
    """One credential file: who reads it, what goes dark without it, and how to obtain it."""

    name: str
    shape: tuple[str, ...]          #: required top-level keys
    unlocks: str                    #: what having it turns ON
    without: str                    #: what happens when it is absent
    how: str                        #: how to obtain it
    tier: str                       #: "money" | "research" | "ops"
    cost: str = "free"
    optional_keys: tuple[str, ...] = field(default=())


#: Ordered by consequence, not alphabetically: the money path first, then what unblocks the most
#: dark capability, then the rest. `unlocks`/`without` are the two columns worth reading.
CREDENTIALS: tuple[Credential, ...] = (
    # RETIRED 2026-09-05 (universe mandate): `binance_live.json` and `binance_live_spot.json`
    # unlocked LIVE futures placement and the cash-and-carry spot leg. Both executors are deleted
    # and no organ on this desk may place an order on a crypto exchange, so a row telling a reader
    # how to mint those keys is an instruction to rebuild the desk that was just retired.
    #
    # The two TESTNET rows below stay, and only for one reason, stated so nobody prunes them as
    # leftovers: they are the Tier-3 DEAD-MAN RAIL's keys. run_deadman_switch.py (never-touch),
    # run_deadman_reconciliation.py and run_deadman_stranded_sweep.py read these exact filenames
    # to reconcile and close positions the retired venue may still hold. Losing them does not
    # retire a strategy, it strands real money with nothing watching it.
    #
    # Their `how` fields no longer carry the venue's signup URLs. This desk is not opening new
    # accounts on a universe it may not hunt; the keys either already exist on the box or the rail
    # is honestly BLOCKED, and an inventory that reads like an onboarding guide is exactly the
    # second-desk signal check_mt5_purity exists to catch.
    Credential(
        name="binance_testnet.json",
        shape=("api_key", "api_secret"),
        unlocks="the Tier-3 dead-man rail's futures leg: reconciliation and stranded-position "
                "close-out on the retired venue",
        without="stranded futures positions from the retired era cannot be seen or closed -- the "
                "one remaining path by which this desk can still lose real money goes dark",
        how="already provisioned on the trading box; not re-issued. If absent, the rail reports "
            "BLOCKED and an operator restores it from the existing account -- no new key is minted",
        tier="money"),
    Credential(
        name="binance_spot_testnet.json",
        shape=("api_key", "api_secret"),
        unlocks="the Tier-3 dead-man rail's spot leg -- same rail, other half of the book",
        without="the spot half of the stranded sweep is blind, so a residual balance is invisible",
        how="already provisioned on the trading box; not re-issued. Same restore path as the "
            "futures leg above",
        tier="money"),
    Credential(
        name="llm_panel.json",
        shape=("providers",),
        unlocks="EVERY reasoning organ: external panel, code auditor, strategic director, "
                "kimi hunter, blind rediscovery, hypothesis generator, breadth expander",
        without="all of them return 402 and produce nothing. This is the single largest block of "
                "dark capability on the desk -- one payment turns on more than any other file.",
        how='OpenRouter -> add credit -> create key. Shape: {"providers": [{"base_url": '
            '"https://openrouter.ai/api/v1", "key": "sk-or-..."}]}',
        tier="research", cost="PAID -- the only credential here that costs money"),
    Credential(
        name="llm_panel_free.json",
        shape=("providers",),
        unlocks="the free-tier fallback roster for the external panel",
        without="the panel has no fallback when the paid roster is exhausted or rate-limited",
        how="same shape as llm_panel.json, pointed at free-tier model ids",
        tier="research"),
    Credential(
        name="ntfy.json",
        shape=("topic",),
        unlocks="the pager -- every alert, the dead-man's fire, the daily brief",
        without="ALERTS ARE COMPUTED AND DELIVERED NOWHERE. The desk pages into the void, which is "
                "indistinguishable from having nothing to say. This is the cheapest file here and "
                "the most consequential to omit.",
        how='pick an unguessable topic name, then subscribe to it in the ntfy app or at '
            'https://ntfy.sh/<topic>. Shape: {"topic": "quant-<something-random>"}',
        tier="ops"),
    Credential(
        name="heartbeat_url.json",
        shape=("url",),
        unlocks="box-liveness heartbeat AND the second alert channel (a different provider on a "
                "different network path)",
        without="a dead box is silent, and silence is what a healthy box also looks like. One "
                "provider means one outage takes the whole pager down.",
        how='healthchecks.io -> create a check -> copy its ping URL. Shape: {"url": "https://'
            'hc-ping.com/<uuid>"}',
        tier="ops"),
    Credential(
        name="alert_channels.json",
        shape=("channels",),
        unlocks="additional independent pager routes (telegram / webhook / email / hc)",
        without="the registry records NOT-ARMED as a state; ntfy and the heartbeat still work",
        how='see libs/ops/alert_channels.py. Shape: {"channels": [{"kind": "telegram", "token": '
            '"...", "chat_id": "..."}]}',
        tier="ops"),
    Credential(
        name="databento.json",
        shape=("api_key",),
        unlocks="CME futures history -- the cross-asset axis",
        without="cross-asset studies have no CME leg and report NO-INPUT rather than a result",
        how="https://databento.com -> API keys. Has a free tier with a monthly allowance.",
        tier="research"),
    Credential(
        name="fred.json",
        shape=("key",),
        unlocks="FRED macro series (rates, liquidity, the macro regime axis)",
        without="the macro collector skips gracefully and the regime axis is price-only",
        how="https://fredaccount.stlouisfed.org/apikeys -- free, instant",
        tier="research"),
    Credential(
        name="naver.json",
        shape=("client_id", "client_secret"),
        unlocks="NAVER search volume -- the Korean retail-attention axis",
        without="the KR attention axis is unmeasured; the kimchi-premium work loses its "
                "attention leg",
        how="https://developers.naver.com -> register an application -> Search API. Free.",
        tier="research"),
    Credential(
        name="netlify.json",
        shape=("token", "site_id"),
        unlocks="publishing the dashboard to a URL the principal can open from a phone",
        without="the dashboard exists only on the box, so reviewing it requires SSH",
        how="Netlify -> user settings -> applications -> personal access token; site_id from the "
            "site's settings. Free tier is sufficient.",
        tier="ops"),
    Credential(
        name="ngrok.json",
        shape=("authtoken",),
        unlocks="a temporary tunnel to the local ops server",
        without="the ops server is reachable only from the box itself",
        how="https://dashboard.ngrok.com/get-started/your-authtoken -- free tier",
        tier="ops"),
)


def _inspect(cred: Credential) -> dict[str, Any]:
    """Presence and SHAPE only. Never the value -- this output is meant to be pasteable."""
    p = SECRETS / cred.name
    row: dict[str, Any] = {
        "file": f"data/secrets/{cred.name}", "tier": cred.tier, "cost": cred.cost,
        "unlocks": cred.unlocks, "without": cred.without, "how": cred.how,
        "present": p.exists(), "status": "MISSING", "detail": "",
    }
    if not p.exists():
        return row
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as e:
        row["status"] = "UNREADABLE"
        row["detail"] = f"{type(e).__name__} -- present but not valid JSON, which every reader "\
                        "treats as absent while it LOOKS configured"
        return row
    if not isinstance(doc, dict):
        row["status"] = "MALFORMED"
        row["detail"] = f"top level is {type(doc).__name__}, expected an object"
        return row
    missing = [k for k in cred.shape if not doc.get(k)]
    if missing:
        row["status"] = "INCOMPLETE"
        row["detail"] = f"missing or empty: {', '.join(missing)}"
        return row
    row["status"] = "OK"
    # Lengths, never values. Enough to catch a truncated paste, useless to an attacker.
    def _size(v: Any) -> str:
        return (f"<{len(v)} entries>" if isinstance(v, (list, dict))
                else f"<{len(str(v))} chars>")

    row["detail"] = ", ".join(f"{k}={_size(doc[k])}" for k in cred.shape)
    return row


def build() -> dict[str, Any]:
    rows = [_inspect(c) for c in CREDENTIALS]
    ok = [r for r in rows if r["status"] == "OK"]
    broken = [r for r in rows if r["status"] in {"UNREADABLE", "MALFORMED", "INCOMPLETE"}]
    # `relative_to` RAISES when the directory is not under ROOT, which is exactly the case on a
    # box where secrets live on a separate mount or an encrypted volume -- a perfectly ordinary
    # arrangement that would have made this tool crash instead of reporting. Report the absolute
    # path when it is outside the repo; a longer string is not a reason to lose the answer.
    try:
        shown = str(SECRETS.relative_to(ROOT))
    except ValueError:
        shown = str(SECRETS)
    return {
        "secrets_dir": shown,
        "secrets_dir_exists": SECRETS.is_dir(),
        "n_declared": len(rows), "n_present": len(ok), "n_broken": len(broken),
        "n_missing": len(rows) - len(ok) - len(broken),
        "by_tier": {t: sum(1 for r in rows if r["tier"] == t and r["status"] == "OK")
                    for t in ("money", "research", "ops")},
        # A file that is present-but-broken is worse than an absent one: it LOOKS configured, so
        # nobody looks again, while every reader treats it as absent.
        "worst_first": [r["file"] for r in broken] + [r["file"] for r in rows
                                                      if r["status"] == "MISSING"],
        "credentials": rows,
        "note": "presence and shape only -- no key is printed, and none is validated against a "
                "venue. This output is safe to paste.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--missing", action="store_true", help="only what is absent or broken")
    a = ap.parse_args()

    rep = build()
    if a.json:
        print(json.dumps(rep, indent=1))
        return 0

    rows = rep["credentials"]
    if a.missing:
        rows = [r for r in rows if r["status"] != "OK"]

    print(f"CREDENTIALS -- {rep['n_present']}/{rep['n_declared']} present"
          f"  ({rep['n_broken']} present-but-broken, {rep['n_missing']} absent)")
    print(f"  dir: {rep['secrets_dir']}"
          f"{'' if rep['secrets_dir_exists'] else '  [DOES NOT EXIST -- mkdir -p it first]'}")
    print()
    mark = {"OK": "[ok]", "MISSING": "[--]", "UNREADABLE": "[!!]", "MALFORMED": "[!!]",
            "INCOMPLETE": "[!?]"}
    for r in rows:
        print(f"{mark[r['status']]} {r['file']:<38} {r['tier']:<9} {r['cost']}")
        if r["status"] == "OK":
            print(f"       {r['detail']}")
        else:
            if r["detail"]:
                print(f"       {r['detail']}")
            print(f"       WITHOUT IT: {r['without']}")
            print(f"       HOW:        {r['how']}")
        print()

    if not a.missing:
        print("UNLOCKS, for the ones that are absent:")
        for r in rep["credentials"]:
            if r["status"] != "OK":
                print(f"  - {r['file']:<38} {r['unlocks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
