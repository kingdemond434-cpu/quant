#!/usr/bin/env python3
"""WHY IS THE VENUE REFUSING THIS KEY? The ladder that separates causes -2015 cannot.

WHY THIS EXISTS. Binance answers `-2015 Invalid API-key, IP, or permissions for action` to at
least four unrelated problems, and it is the single most common wall between a correct desk and a
live one. This desk spent an afternoon on it: the key was right, the permissions were ticked, the
whitelist was set -- and the box was dual-stack, so every request left over IPv6 from an address
the venue had never been told about. Nothing in the error text could have told anyone that.

THE LADDER, EACH RUNG ISOLATING ONE VARIABLE:

  1. PUBLIC REACH      -- no key at all. Fails => network/proxy/DNS, and nothing below means anything.
  2. EGRESS ADDRESS    -- what the venue actually SEES. The whitelist is checked against this and
                          not against whatever `ip addr` prints on a dual-stack host.
  3. CLOCK SKEW        -- venue time vs local. A signed request outside recvWindow is rejected on
                          timing alone, and the desk would read it as a credential problem.
  4. KEY IDENTITY      -- a MARKET_DATA call, which requires a valid API key and NO signature and
                          NO permission flags. This rung answers "does this key exist" alone.
                          IMPORTANT AND EASY TO MISREAD: Binance does NOT enforce the IP whitelist
                          on MARKET_DATA. Passing here proves the key STRING is real and proves
                          NOTHING about the IP.
  5. SIGNATURE + PERMS -- the signed account read. Reaching here having passed 4 narrows the cause
                          to the whitelist, the Reading permission, or the secret.

A rung that cannot run is reported UNMEASURED and the ladder stops. A later rung's verdict is
meaningless once an earlier one has failed, and printing one anyway is how an operator ends up
fixing the wrong thing (L1.28a).

NO KEY, SECRET OR SIGNATURE IS EVER PRINTED. The key is shown as first-4/last-4 so an operator can
confirm WHICH credential is loaded without the value reaching a terminal, a log or a chat window.

    python scripts/check_binance_key.py
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/binance_key_check.json")

#: A signed request whose timestamp is further than this from the venue's clock is rejected on
#: timing, whatever the credential says. Binance's own recvWindow default is 5000ms; this warns
#: earlier because skew grows and a box that is 3s out today is 6s out next week.
_SKEW_WARN_MS = 2000


def _mask(s: str) -> str:
    return f"{s[:4]}...{s[-4:]} ({len(s)} chars)" if len(s) > 8 else "(too short to mask)"


def _rung(name: str, ok: bool | None, detail: str, action: str = "") -> dict[str, Any]:
    return {"check": name, "ok": ok, "detail": detail, "action": action}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keyfile", default="data/secrets/binance_live_spot.json")
    args = ap.parse_args()

    from libs.execution import binance_spot_live as live

    rungs: list[dict[str, Any]] = []
    verdict = "UNMEASURED"
    action = ""

    # 1. PUBLIC REACH -- no credential involved. Everything below is meaningless if this fails.
    try:
        live._get("/api/v3/ping")
        rungs.append(_rung("public reach", True, "api.binance.com answers unauthenticated calls"))
    except Exception as exc:
        rungs.append(_rung("public reach", False, f"{type(exc).__name__}: {exc}",
                           "the box cannot reach the venue at all -- DNS, egress firewall or "
                           "proxy. No credential change can fix this and none should be attempted "
                           "until it passes"))
        return _finish(rungs, "NETWORK", rungs[-1]["action"])

    # 2. EGRESS -- the address the whitelist is actually matched against.
    try:
        egress = live._urlopen(
            urllib.request.Request("https://api64.ipify.org")).read().decode().strip()
        v6 = ":" in egress
        rungs.append(_rung("egress address", not v6, egress,
                           "" if not v6 else
                           "requests are leaving over IPv6. A venue whitelist holding only the "
                           "IPv4 address will reject every signed call with -2015, and the error "
                           "text will not mention the address family"))
    except Exception as exc:
        rungs.append(_rung("egress address", None, f"UNMEASURED ({type(exc).__name__})",
                           "the echo service is unreachable; the egress address is unknown rather "
                           "than known-good"))

    # 3. CLOCK -- a timing rejection is not a credential problem, and reads like one.
    try:
        srv = int(live._get("/api/v3/time")["serverTime"])
        skew = srv - int(time.time() * 1000)
        rungs.append(_rung("clock skew", abs(skew) < _SKEW_WARN_MS, f"{skew:+d} ms vs venue",
                           "" if abs(skew) < _SKEW_WARN_MS else
                           "a signed request outside recvWindow is refused on timing alone: "
                           "`sudo timedatectl set-ntp true`, or widen recvWindow"))
    except Exception as exc:
        rungs.append(_rung("clock skew", None, f"UNMEASURED ({type(exc).__name__})"))

    # 4. KEY IDENTITY -- valid key, no signature, no permission flags, NO IP CHECK.
    try:
        d = json.loads(Path(args.keyfile).read_text("utf-8"))
        key, secret = d.get("key") or "", d.get("secret") or ""
    except (OSError, ValueError) as exc:
        rungs.append(_rung("keyfile", False, f"{type(exc).__name__}",
                           f"{args.keyfile} is missing or not valid JSON"))
        return _finish(rungs, "NO-CREDENTIAL", rungs[-1]["action"])
    rungs.append(_rung("keyfile", bool(key and secret),
                       f"key {_mask(key)}, secret {_mask(secret)}",
                       "" if key and secret else "one of the two fields is empty"))

    req = urllib.request.Request(
        "https://api.binance.com/api/v3/historicalTrades?symbol=BTCUSDT&limit=1",
        headers={"X-MBX-APIKEY": key})
    try:
        live._open(req)
        rungs.append(_rung("key identity", True,
                           "the venue recognises this key string. NOTE: MARKET_DATA endpoints do "
                           "NOT enforce the IP whitelist, so this says nothing about the IP"))
        key_ok = True
    except Exception as exc:
        rungs.append(_rung("key identity", False, str(exc)[:200],
                           "the key STRING is wrong, or it belongs to a different Binance site "
                           "(binance.us / testnet) or a sub-account"))
        key_ok = False

    # 5. SIGNED READ -- with 4 green, only three causes remain and they are named.
    try:
        live._signed("/api/v3/account", {})
        rungs.append(_rung("signed account read", True, "balances readable -- the path is LIVE"))
        verdict, action = "READY", ""
    except Exception as exc:
        msg = str(exc)
        rungs.append(_rung("signed account read", False, msg[:200]))
        if "-1021" in msg:
            verdict, action = "CLOCK", "the box clock is outside recvWindow -- see rung 3"
        elif "-1022" in msg:
            verdict, action = "SECRET", (
                "the KEY and PERMISSIONS are fine and the SECRET is wrong. Signature failures are "
                "-1022 and nothing else produces it. Rewrite the keyfile with the correct secret; "
                "if it was transcribed by eye, check O/0 and l/1/I")
        elif "-2015" in msg and key_ok:
            verdict, action = "IP-OR-PERMISSION", (
                "the key is REAL (rung 4 passed) so only two causes remain: the IP whitelist does "
                "not contain the egress address printed in rung 2, or Enable Reading is off. The "
                "fastest split is a NEW key set to Unrestricted -- if that works, it was the "
                "whitelist, and the address to enter is the one in rung 2")
        elif "-2015" in msg:
            verdict, action = "KEY", "the key string itself is not recognised -- see rung 4"
        else:
            verdict, action = "UNKNOWN", "the venue returned something not in the known set"

    return _finish(rungs, verdict, action)


def _finish(rungs: list[dict[str, Any]], verdict: str, action: str) -> int:
    rep = {"updated": datetime.now(tz=UTC).isoformat(), "verdict": verdict,
           "action": action, "rungs": rungs}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")
    print(f"=== BINANCE KEY CHECK === {verdict}")
    for r in rungs:
        mark = {True: "PASS", False: "FAIL", None: "????"}[r["ok"]]
        print(f"  [{mark}] {r['check']:<20} {r['detail'][:110]}")
        if r["action"]:
            print(f"         -> {r['action']}")
    if action:
        print(f"\n  WHAT TO DO: {action}")
    print(f"-> {_OUT}")
    return 0 if verdict == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
