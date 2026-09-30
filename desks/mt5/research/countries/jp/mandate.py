"""THE JAPAN MANDATE, REBUILT IN GIT: who moves Japan's instruments, and which ones the broker quotes.

WHY THIS FILE EXISTS HERE AND NOT AT `research/japan/mandate.py`. `countries/jp/pack.py` imports
`research.japan.mandate`, and that package was never committed: `tests/test_region_department.py`
records that it "lives only on the box", and the one recovered artefact that names the department
(`recovered_box_lanes/05-*.patch`, 2026-09-24) carries only ledger rows for `japan/dashboard.py`
and `japan/miners.py`, not their source. So the box may STILL hold the originals, untracked.
`Adopt-Release.ps1` writes every path origin adds IN PLACE over whatever the box has there, so a
rebuild committed at `research/japan/mandate.py` would silently overwrite the box's own copy on
the next hourly adoption. This rebuild therefore lives beside the pack that reads it, and the pack
asks for the box's department FIRST and falls back to this one. Committing the originals from the
box is the box's job (it holds the only copy).

WHAT IT DECLARES. Actors and the instruments each one moves, as the DEPARTMENT'S CLAIM; the pack
intersects every name with the broker's registry, so a symbol Fusion does not quote (a JGB future,
a Japanese share the account cannot trade) drops out rather than being argued about. The single
names are DERIVED: every share CFD the registry quotes whose name matches a Japanese issuer the
disclosure lane knows (`research/corporate_disclosure.ISSUERS`, with its TDnet/EDINET code). Those
are the EVENT LANE for Japan: traded on their own TDnet/EDINET filings through `event_reaction`
and `news_reaction`, never hunted with statistical families (the two-lane order).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]          # countries/jp/mandate.py -> desks/mt5
UNIVERSE = BASE / "data" / "universe" / "universe.json"

REGION = "japan"
CODE = "JP"
CURRENCY = "JPY"

#: The yen crosses the department trades the funding-currency story on. The pack keeps only the
#: ones the broker quotes, and adds every other six-letter JPY pair the registry lists.
JPY_CROSSES: tuple[str, ...] = ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY",
                                "CHFJPY", "SGDJPY", "HKDJPY", "ZARJPY", "MXNJPY", "NOKJPY",
                                "SEKJPY")

#: Who moves Japan's instruments, and what each one moves. The instruments are the department's
#: claim; `pack._department_instruments` keeps only what the broker quotes.
ACTORS: tuple[dict[str, Any], ...] = (
    {"actor": "Bank of Japan", "kind": "central_bank", "participant_structure": "policy_driven",
     "instruments": ["USDJPY", "EURJPY", "JPN225", "JP225", "XAUUSD"],
     "channel": "policy rate, yield-curve operations and JGB purchase amounts; the meeting is "
                "the event, the Summary of Opinions and the Outlook Report the follow-ups"},
    {"actor": "Ministry of Finance (FX intervention)", "kind": "treasury",
     "participant_structure": "policy_driven", "instruments": ["USDJPY", "EURJPY", "GBPJPY"],
     "channel": "intervention, confirmed monthly in arrears; verbal escalation first"},
    {"actor": "GPIF", "kind": "pension", "participant_structure": "institutional",
     "instruments": ["USDJPY", "JPN225", "JP225"],
     "channel": "policy-portfolio rebalancing between domestic and foreign assets"},
    {"actor": "Life insurers", "kind": "insurer", "participant_structure": "institutional",
     "instruments": ["USDJPY", "EURJPY", "AUDJPY"],
     "channel": "hedged and unhedged foreign bond buying, announced in April and October plans"},
    {"actor": "Retail margin FX (Mrs Watanabe)", "kind": "retail",
     "participant_structure": "retail_heavy",
     "instruments": ["USDJPY", "AUDJPY", "MXNJPY", "ZARJPY", "TRYJPY", "NZDJPY", "GBPJPY"],
     "channel": "carry build and forced unwind on margin; contrarian intraday against the move"},
    {"actor": "Toshin (investment trusts)", "kind": "retail_fund",
     "participant_structure": "retail_heavy", "instruments": ["USDJPY", "AUDJPY", "US500"],
     "channel": "monthly-distribution funds buying foreign assets; NISA flows from January"},
    {"actor": "Japanese exporters", "kind": "corporate", "participant_structure": "mixed",
     "instruments": ["USDJPY", "EURJPY", "JPN225"],
     "channel": "gotobi (5th/10th) settlement demand at the 09:55 JST Tokyo fix; half-year-end "
                "repatriation in March and September"},
    {"actor": "Foreign equity investors", "kind": "foreign_flow",
     "participant_structure": "institutional", "instruments": ["JPN225", "JP225", "USDJPY"],
     "channel": "weekly investor-type flow (JPX), hedged or not"},
    {"actor": "TSE-listed issuers (TDnet/EDINET)", "kind": "issuer",
     "participant_structure": "mixed", "instruments": ["JPN225", "JP225", "USDJPY"],
     "channel": "timely disclosure, 15:00 JST after the close; guidance revisions and buybacks"},
)

#: Instruments the forest runner reads when it asks this module directly.
INSTRUMENTS: tuple[str, ...] = tuple(dict.fromkeys(
    [*JPY_CROSSES, "JPN225", "JP225"]))


def _registry() -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)} if isinstance(doc, dict) \
        else {}


def single_names() -> list[dict[str, Any]]:
    """Every Japanese issuer the broker quotes as a share CFD, derived, with its native code.

    The event lane for Japan: each row names the symbol, the TSE code TDnet and EDINET file under,
    and the stream spec its own disclosures are read through. Empty when the registry is
    unreadable, which the caller reports as UNMEASURED.
    """
    try:
        from research.corporate_disclosure import ISSUERS, Resolver
        from mt5desk.disclosure_events import make_spec
    except Exception:
        return []
    res = Resolver(_registry())
    out: list[dict[str, Any]] = []
    for iss in ISSUERS:
        if not iss.get("jp"):
            continue
        sym = res._registry_symbol(iss.get("short") or (), iss.get("names") or ())
        if not sym:
            continue
        out.append({"symbol": sym, "tse_code": iss["jp"], "names": list(iss["names"]),
                    "lane": "event",
                    "streams": [make_spec("jp", "self", "*", "any", 1)],
                    "families": ["event_reaction", "news_reaction"]})
    return out


def executable(quoted: set[str] | None = None) -> list[str]:
    """Every instrument this mandate names that the broker quotes, crosses first."""
    q = quoted if quoted is not None else set(_registry())
    names: list[str] = []
    for sym in [*JPY_CROSSES, *(s for a in ACTORS for s in a["instruments"])]:
        if sym in q and sym not in names:
            names.append(sym)
    names.extend(r["symbol"] for r in single_names() if r["symbol"] not in names)
    return names
