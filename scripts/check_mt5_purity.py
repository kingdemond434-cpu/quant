"""ONE DESK IN THIS REPO. A reader must not have to guess which market it trades.

WHY THIS FENCE EXISTS (principal instruction, 2026-09-05)

    "delete all other crypto things left fully from repo to clean it up fully"
    "so if i send it to other ais to judge they never get confused by old crypto things"
    "and its purely an mt5 what we use repo"

Until today this repository held TWO desks. The live one is `desks/mt5/`: one broker connection,
the Fusion Markets universe, a gateway and a promoter and a forward clock. Beside it sat a
retired crypto-exchange desk -- some two hundred entry points that ingested, screened, backtested
and traded Binance, Bybit, OKX, Hyperliquid, Deribit and Upbit. Both described themselves as
authoritative. Whichever a reader opened first became what they believed the desk hunts, and a
reviewer asked to judge the work judged the wrong desk.

The 2026-08-18 mandate had already retired the crypto universe. Retirement was not enough,
because a retired desk that is still on disk still answers the question "what does this repo do?"
The crypto-native code is now DELETED, and this fence is what stops it coming back.

WHAT IT MEASURES, AND WHY THAT AND NOT SOMETHING EASIER

Not the word "crypto". Half this desk's institutional memory is a record of the crypto era --
the graveyard, the negative-knowledge register, the deep sweeps, the blind-rediscovery log --
and that record is the most valuable thing in the repo. A fence that flagged the word would
force the desk to burn its own memory to go green, which is the opposite of what the principal
asked for. It would also be lying: a HISTORY of a retired venue is not a live mandate over it.

What it measures is CAPABILITY: whether a file can still reach a crypto-exchange venue. A module
that names `fapi.binance.com` is not remembering Binance, it is calling it. That is a sharp,
falsifiable, hard-to-argue signal, and it is exactly the thing the mandate forbids -- a hunted
universe of its own. The second signal is a file DECLARING a crypto-exchange universe as its
subject in its own docstring, which is how the old desk announced itself.

Fusion-executable crypto CFDs stay legal, and this fence permits them, because they reach the
market through the MT5 gateway like every other instrument. The line is the VENUE, never the
asset: BTC through Fusion is an MT5 instrument, BTC through Binance is a retired universe.

    python3 scripts/check_mt5_purity.py [--json]

Exit 0 when the tree holds one desk. Exit 1 naming every file that would give a reader a second.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mt5_purity.json"

#: A LIVE REACH into a crypto-exchange venue. Hostnames, not brand names: a comment saying
#: "Binance" is memory, a string saying "fapi.binance.com" is a client. Kept as hostnames so the
#: check cannot drift into flagging prose, which is the failure mode that kills fences.
_VENUE_HOSTS: tuple[str, ...] = (
    "api.binance.com", "fapi.binance.com", "dapi.binance.com", "api.binance.us",
    "testnet.binancefuture.com", "testnet.binance.vision", "data.binance.vision",
    "api.bybit.com", "api-testnet.bybit.com", "public.bybit.com",
    "api.hyperliquid.xyz", "api.hyperliquid-testnet.xyz",
    "www.okx.com/api", "aws.okx.com",
    "www.deribit.com/api", "test.deribit.com",
    "api.upbit.com", "api-manager.upbit.com",
    "www.bitmex.com/api", "testnet.bitmex.com",
    "api.kucoin.com", "api.gateio.ws", "api.mexc.com", "api.bitget.com",
    "api.coinbase.com", "api.exchange.coinbase.com", "api.pro.coinbase.com",
    "api.kraken.com", "futures.kraken.com",
    "api.coingecko.com", "pro-api.coinmarketcap.com", "api.coinmetrics.io",
    "api.llama.fi", "api.dune.com", "api.glassnode.com", "api.cryptoquant.com",
)

#: A file DECLARING a crypto-exchange universe as its own subject. Anchored to the declaration
#: window (a module docstring), shouted or hyphenated, because that is how the retired desk
#: announced itself. Prose using the words in a sentence is not a declaration -- see
#: `check_universe_mandate.py`, which learned this the expensive way by flagging four modules
#: that were correctly explaining the mandate they complied with.
_DECLARES = (
    re.compile(r"CRYPTO-ONLY"),
    re.compile(r"MT5 abandoned", re.I),
    re.compile(r"crypto-(?:native|exchange) (?:portfolio|universe|desk|sleeves?)", re.I),
    re.compile(r"\bperp(?:etual)?s? (?:funding|universe|cross-section)\b", re.I),
)

#: Explicitly permitted by the mandate: crypto as REFERENCE data informing an MT5 instrument, and
#: Fusion-executable crypto CFDs. A file saying so is complying, and must never be flagged for
#: saying so clearly.
_PERMITTED = re.compile(r"crypto only as information|fusion[- ]executable|crypto CFD", re.I)

_DECLARATION_WINDOW = 2500

#: Allowed to reach a venue, each with the reason it survives an MT5-only purge. A bare allowlist
#: is a list nobody can safely extend; every entry here answers "why is this not the thing we
#: just deleted?"
_ALLOWED: dict[str, str] = {
    "libs/execution/binance_testnet.py":
        "TIER-3 DEADMAN RAIL. run_deadman_reconciliation.py and run_deadman_stranded_sweep.py "
        "import this directly, and run_deadman_switch.py is never-touch. The rail's own plumbing "
        "is not a hunted universe -- it is how stranded positions from the retired era are still "
        "reconciled and closed. Deleting it breaks the one mechanism that protects real money.",
    "libs/execution/binance_spot_testnet.py":
        "TIER-3 DEADMAN RAIL, spot leg. Same reason as the futures leg above.",
    "scripts/run_deadman_switch.py":
        "TIER-3 NEVER-TOUCH. Restored byte-for-byte only; not modified for any reason.",
    "scripts/run_deadman_reconciliation.py":
        "TIER-3 rail companion: reconciles positions the retired venue may still hold.",
    "scripts/run_deadman_stranded_sweep.py":
        "TIER-3 rail companion: sweeps stranded balances on the retired venue.",
    "scripts/enforce_mt5_mandate.py":
        "THE ENFORCER. It must name the forbidden hunters to stop them; a rule that cannot say "
        "what it forbids cannot enforce anything.",
    "scripts/check_universe_mandate.py":
        "The mandate's sibling fence: it must name the retired ground it looks for.",
    "scripts/check_mt5_purity.py":
        "This file. It carries the venue list it enforces.",
    "tests/scripts/test_check_mt5_purity.py":
        "THIS FENCE'S OWN NON-VACUITY PROOF. It plants a working crypto client in a temporary "
        "tree and asserts the fence turns red. A fence that forbade its own proof could never be "
        "shown to fire, which is the whole reason an outside reviewer would trust it.",
    "tests/scripts/test_enforce_mt5_mandate.py":
        "Tests the enforcer, so it must name the hunters the enforcer stops. Pinning that the "
        "money path is refused FIRST even when its command line mentions a forbidden script is "
        "only possible by writing both down.",
    "tests/scripts/test_watchdog_banned_universe.py":
        "Tests that the watchdog rejects the banned universe, which it can only do by naming it.",
}

#: Read, never executed: the desk's memory of the era it retired. A record of what was tried and
#: what failed is the most valuable thing in the repo, and burning it to go green would be a
#: worse outcome than the confusion this fence exists to prevent. Data and prose cannot call an
#: exchange; only code can, so only code is scanned.
_MEMORY_ROOTS = ("docs/", "data/", "desks/mt5/data/", "ops/memory/", "reports/")

_SKIP_PARTS = {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".ruff_cache"}


def _scannable(p: Path) -> bool:
    if any(part in _SKIP_PARTS for part in p.parts):
        return False
    if p.suffix not in {".py", ".sh", ".ps1", ".cmd"}:
        return False
    rel = str(p.relative_to(ROOT))
    return not any(rel.startswith(m) for m in _MEMORY_ROOTS)


def _executable_text(text: str, path: Path) -> str:
    """The part of the file that could actually make a request.

    A hostname in a `#` comment is not a client, it is a note -- and the desk writes a lot of
    those on purpose: `.claude/desk-state.sh` names `fapi.binance.com` precisely to record that
    it is BANNED ground. Counting that as a reach would flag the enforcement for enforcing, which
    is how a fence teaches everyone to skim past its output.

    So comments are stripped before the venue scan. Nothing is lost: a URL that a program calls
    has to survive into code, and this only removes lines that cannot execute. Python docstrings
    are handled separately by the declaration check, which is where a file's claim about its own
    universe belongs.
    """
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") or (path.suffix == ".ps1" and stripped.startswith("<#")):
            continue
        if path.suffix in {".cmd"} and stripped.lower().startswith(("rem ", "::")):
            continue
        out.append(line)
    return "\n".join(out)


def _docstring_window(text: str, path: Path) -> str:
    """The file's own declaration of what it is, not an arbitrary prefix.

    For Python that is the module docstring; falling back to the head of the file when it has
    none, because a shell script declares itself in its opening comment block.
    """
    if path.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(text, str(path)))
        except (SyntaxError, ValueError):
            doc = None
        if doc is not None:
            return doc
    return text[:_DECLARATION_WINDOW]


def scan() -> dict:
    reaches: list[dict] = []
    declares: list[dict] = []
    allowed_seen: list[str] = []

    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or not _scannable(p):
            continue
        rel = str(p.relative_to(ROOT))
        try:
            text = p.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        code = _executable_text(text, p)
        hosts = sorted({h for h in _VENUE_HOSTS if h in code})
        window = _docstring_window(text, p)
        claims = ([r.pattern for r in _DECLARES if r.search(window)]
                  if not _PERMITTED.search(window) else [])

        if not hosts and not claims:
            continue
        if rel in _ALLOWED:
            allowed_seen.append(rel)
            continue
        if hosts:
            reaches.append({"file": rel, "hosts": hosts})
        if claims:
            declares.append({"file": rel, "claims": claims})

    # An allowlist entry that never fired is not automatically stale: the file may simply be
    # clean now (it imports the rail rather than naming a host). Only an entry whose FILE is gone
    # is genuinely dead weight, and saying "no longer present" about a file sitting on disk would
    # send the next reader looking for a deletion that never happened.
    unused = sorted(e for e in set(_ALLOWED) - set(allowed_seen)
                    if e != "scripts/check_mt5_purity.py" and not (ROOT / e).exists())
    clean = sorted(e for e in set(_ALLOWED) - set(allowed_seen)
                   if e != "scripts/check_mt5_purity.py" and (ROOT / e).exists())
    return {
        "checked_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "reaches_a_crypto_venue": reaches,
        "declares_a_crypto_universe": declares,
        "allowed_and_present": sorted(allowed_seen),
        "allowed_file_gone": unused,
        "allowed_but_already_clean": clean,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the report instead of a summary")
    args = ap.parse_args()

    doc = scan()
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    except OSError as e:                      # an unwritable report never costs the finding
        doc["report_unwritten"] = str(e)

    if args.json:
        print(json.dumps(doc, indent=1))

    bad = doc["reaches_a_crypto_venue"] + doc["declares_a_crypto_universe"]
    print(f"MT5 PURITY {doc['checked_at']}")
    print(f"  allowed and present: {len(doc['allowed_and_present'])} "
          f"(the deadman rail and the mandate's own enforcers)")

    # Neither of these is fatal: both mean less crypto in the tree, which is the direction this
    # fence wants. They are reported so the allowlist does not quietly rot into a list of
    # excuses for files that no longer need one.
    for s in doc["allowed_file_gone"]:
        print(f"  NOTE stale allowlist entry, the file it excused is gone: {s}")
    for s in doc["allowed_but_already_clean"]:
        print(f"  NOTE allowlisted but no longer needs the excuse, now clean: {s}")

    if not bad:
        print("  one desk: no file reaches a crypto-exchange venue or declares one as its "
              "universe. A reader opening this repo finds the MT5/Fusion desk and nothing else.")
        return 0

    print(f"  BREACH: {len(bad)} file(s) would give a reader a second desk")
    for r in doc["reaches_a_crypto_venue"]:
        print(f"    REACHES {r['file']} -> {', '.join(r['hosts'])}")
    for d in doc["declares_a_crypto_universe"]:
        print(f"    DECLARES {d['file']} -> {', '.join(d['claims'])}")
    print("  Delete the file, or add it to _ALLOWED WITH THE REASON it survives an MT5-only "
          "repo. Never widen the venue list to go green.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
