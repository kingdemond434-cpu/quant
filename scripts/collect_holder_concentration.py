#!/usr/bin/env python3
"""TOKEN-HOLDER CONCENTRATION (R0100 axis 4) -- Ethplorer free tier, wallet-resolution supply.

MECHANISM (stated before any screen): supply concentration marks accumulation/distribution
BEFORE exchange netflow prints -- wallet resolution is the layer the desk's flat-screened Coin
Metrics aggregates compress away. A single snapshot is nearly information-free; the axis is the
DELTA between successive snapshots (top-10/top-100 share drift, holder-count drift), which is
why this collector is strictly idempotent per (date, token): the archive of daily snapshots IS
the signal source, and a duplicated day would fabricate a zero-delta.

UNIVERSE (module constant, mapping stated): ~20 Ethereum-mainnet-primary ERC-20s the desk maps
1:1 to Binance USDT perps in its own lake (data/lake/bronze/futclose_daily/<perp>.jsonl holds
the matching target series; 1000x names map PEPE->1000PEPEUSDT, SHIB->1000SHIBUSDT). Tokens
whose primary supply lives on another chain (native L1s, migrated governance tokens like DYDX,
bridged NEAR/INJ) are deliberately EXCLUDED -- their mainnet ERC-20 holder set is not the asset.

SOURCE (§13): Ethplorer's documented free tier, apiKey=freekey. Their wiki states "The API
service is free, but you are required to place references to the Ethplorer API" and limits
freekey to "2 per second, 20/min, 100/hour, 1000/24hours, 3000/week" (fetched 2026-08-05).
This collector: 2 calls/token * 22 tokens = 44 calls/day at 3.2s spacing (~18.7/min) -- inside
every published bound. ATTRIBUTION (their stated condition): data source: Ethplorer.io API
(https://ethplorer.io) -- carried in every status artifact this organ writes.

MIS-CREDIT FENCE: getTokenInfo's on-chain symbol must equal the expected symbol or the token's
row is REFUSED for the run -- a wrong address must surface as an error, never as a plausible
concentration number credited to the wrong asset.

CLOCK PROVENANCE (L1.46, libs/research/clock_provenance.py convention): Ethplorer returns no
response stamp -> t = receipt ms, c = "recv_only". (Chain state has no single "venue instant"
for a holder table; the honest clock is when WE observed it.)

SCREEN-DEFERRAL (declared, computed from the harness's stated minimum): stage_a_screen needs
zwin(20)+30+1 = 51 aligned daily observations. Seeded 2026-08-05 at daily cadence -> the delta
series is screenable (not yet powered) from 2026-09-24. No screen before depth exists.

    .venv/bin/python scripts/collect_holder_concentration.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BASE = "https://api.ethplorer.io"
_KEY = "freekey"
_OUT = "data/holder_concentration.jsonl"
_STATUS = "data/holder_concentration_status.json"
_UA = "quant-desk-research/1.0 (public-endpoint reader)"
_TIMEOUT = 25
_SLEEP_S = 3.2          # 44 calls/run at ~18.7/min -- under freekey's 20/min and 2/sec bounds
_TOP_LIMIT = 100        # freekey maximum for getTopTokenHolders

#: (token symbol, ERC-20 mainnet address, Binance USDT perp it maps to). The mapping IS the
#: point: every row here joins the desk's own perp lake without a resolver.
UNIVERSE: tuple[tuple[str, str, str], ...] = (
    ("LINK", "0x514910771AF9Ca656af840dff83E8264EcF986CA", "LINKUSDT"),
    ("UNI", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "UNIUSDT"),
    ("AAVE", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", "AAVEUSDT"),
    ("PEPE", "0x6982508145454Ce325dDbE47a25d4ec3d2311933", "1000PEPEUSDT"),
    ("SHIB", "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE", "1000SHIBUSDT"),
    ("ENA", "0x57e114B691Db790C35207b2e685D4A43181e6061", "ENAUSDT"),
    ("ONDO", "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3", "ONDOUSDT"),
    ("WLD", "0x163f8C2467924be0ae7B5347228CABF260318753", "WLDUSDT"),
    ("CRV", "0xD533a949740bb3306d119CC777fa900bA034cd52", "CRVUSDT"),
    ("LDO", "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32", "LDOUSDT"),
    ("MKR", "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2", "MKRUSDT"),
    ("SNX", "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F", "SNXUSDT"),
    ("COMP", "0xc00e94Cb662C3520282E6f5717214004A7f26888", "COMPUSDT"),
    ("GRT", "0xc944E90C64B2c07662A292be6244BDf05Cda44a7", "GRTUSDT"),
    ("SAND", "0x3845badAde8e6dFF049820680d1F14bD3903a5d0", "SANDUSDT"),
    ("MANA", "0x0F5D2fB29fb7d3CFeE444a200298f468908cC942", "MANAUSDT"),
    ("APE", "0x4d224452801ACEd8B2F0aebE155379bb5D594381", "APEUSDT"),
    ("FET", "0xaea46A60368A7bD060eec7DF8CBa43b7EF41Ad85", "FETUSDT"),
    ("ENS", "0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72", "ENSUSDT"),
    ("PENDLE", "0x808507121B80c02388fAd14726482e061B8da827", "PENDLEUSDT"),
    ("SUSHI", "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2", "SUSHIUSDT"),
    ("1INCH", "0x111111111117dC0aa78b770fA6A738034120C302", "1INCHUSDT"),
)

SCREEN_DEFER = {"first_snapshot": "2026-08-05", "harness_min_daily_obs": 51,
                "screenable_from": "2026-09-24"}

_ATTRIBUTION = "data source: Ethplorer.io API (https://ethplorer.io) -- free-tier condition"


def _get(url: str) -> tuple[Any, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            doc = json.loads(r.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:140]}"
    if isinstance(doc, dict) and doc.get("error"):
        return None, f"api error: {json.dumps(doc['error'])[:140]}"
    return doc, ""


def concentration(holders: list[dict[str, Any]]) -> dict[str, float | int]:
    """Top-10/top-100 share from the holder table, sorted defensively by share desc."""
    shares = sorted((float(h.get("share", 0.0)) for h in holders
                     if isinstance(h, dict)), reverse=True)
    return {"top10_share": round(sum(shares[:10]), 4),
            "top100_share": round(sum(shares[:100]), 4),
            "n_top_returned": len(shares)}


def _today_tokens(path: Path, date: str) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                if d.get("date") == date:
                    done.add(str(d.get("token")))
            except ValueError:
                continue
    return done


def collect(root: Path, fetch=_get, sleep_s: float = _SLEEP_S) -> dict[str, Any]:
    """One row per (date, token), idempotent: tokens already recorded today are skipped, so a
    rerun costs zero API budget and can never fabricate a duplicate (= fake zero-delta) row."""
    date = datetime.now(tz=UTC).date().isoformat()
    out = root / _OUT
    done = _today_tokens(out, date)
    errors: dict[str, str] = {}
    fresh: list[dict[str, Any]] = []

    for token, addr, perp in UNIVERSE:
        if token in done:
            continue
        info, err = fetch(f"{_BASE}/getTokenInfo/{addr}?apiKey={_KEY}")
        time.sleep(sleep_s)
        if err:
            errors[token] = f"getTokenInfo: {err}"
            continue
        chain_symbol = str((info or {}).get("symbol", "")).upper()
        if chain_symbol != token:
            errors[token] = (f"REFUSED (mis-credit fence): on-chain symbol {chain_symbol!r} != "
                             f"expected {token!r} at {addr} -- no row written")
            continue
        top, err = fetch(f"{_BASE}/getTopTokenHolders/{addr}?apiKey={_KEY}&limit={_TOP_LIMIT}")
        time.sleep(sleep_s)
        holders = (top or {}).get("holders") if isinstance(top, dict) else None
        if err or not isinstance(holders, list) or not holders:
            errors[token] = f"getTopTokenHolders: {err or 'empty holder table'}"
            continue
        recv = int(datetime.now(tz=UTC).timestamp() * 1000)
        fresh.append({"t": recv, "c": "recv_only", "date": date, "token": token,
                      "perp_symbol": perp, "address": addr,
                      **concentration(holders),
                      "holders_count": (info or {}).get("holdersCount"),
                      "source": "ethplorer(freekey)"})

    if fresh:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row) + "\n")

    n_have = len(done) + len(fresh)
    # ERROR BRANCHES COME FIRST. This ladder tested the idempotent-rerun branch BEFORE any error
    # branch, so a catch-up run in which an earlier tick banked some tokens and EVERY remaining
    # token then failed reported "NO-NEW-ROWS (idempotent rerun)" -- a clean, expected-looking
    # status -- while carrying a non-empty token_errors, and main() exited 0. A failure that
    # renders as a success signal is the one defect a status field exists to prevent. The sibling
    # organ (collect_dexscreener) already orders DEGRADED ahead of NO-NEW-ROWS; this matches it.
    status = ("OK" if n_have == len(UNIVERSE) and not errors else
              "ALL-TOKENS-FAILED" if not fresh and not done else
              "DEGRADED" if errors else
              "NO-NEW-ROWS (idempotent rerun)" if not fresh and done else "DEGRADED")
    return {"generated": datetime.now(tz=UTC).isoformat(), "status": status,
            "date": date, "n_universe": len(UNIVERSE), "n_new": len(fresh),
            "n_already_today": len(done), "token_errors": errors,
            "screen_deferral": SCREEN_DEFER, "attribution": _ATTRIBUTION,
            "clock_provenance": "t=receipt ms, c=recv_only (Ethplorer returns no response "
                                "stamp) -- L1.46",
            "detail": (f"{len(fresh)} new rows, {len(done)} already recorded today, "
                       f"{len(errors)} token error(s) of {len(UNIVERSE)} universe")}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = collect(_ROOT)
    (_ROOT / _STATUS).write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"holder concentration (R0100 axis 4): {rep['status']} -- {rep['detail']}")
    if rep["status"] == "ALL-TOKENS-FAILED":
        print("REFUSED to report success: every token errored and none was recorded today -- "
              "NO-DATA must never read as a quiet day (L1.28a)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
