#!/usr/bin/env python3
"""LENDING RISK BASE RATES (R0375) -- the evidence under `DEFAULT_HAIRCUT_BPS`, which had none.

WHAT WAS WRONG. `screen_collateral_allocation.DEFAULT_HAIRCUT_BPS = 300.0` decided, single-handed,
whether the desk's idle dollars may earn a lending yield. Measured 2026-08-05 by check_idle_cost:
best stablecoin supply APY 3.78% against a risk-free 3.73%/yr, so the BREAKEVEN haircut is 5.5bps
and the assumed one is 300 -- the constant closes the band 55x over. It had no derivation anywhere
in the repo. That is L1.51's own defect class turned on the desk's only idle-capital decision: a
clamp whose price nobody could argue with, because nobody had computed it.

WHAT THIS COLLECTS, free and keyless (§13, free-first data protocol), from a source this desk
already reads in five other organs:
  1. EXPLOIT LOSSES     api.llama.fi/hacks -- every recorded DeFi loss event with date, amount,
                        technique and returnedFunds. NET of returned funds: a reimbursed exploit
                        is not a supplier loss, and counting it as one would inflate the haircut
                        in the direction that keeps the band shut.
  2. EXPOSURE           api.llama.fi/protocol/<slug> -- daily TVL history per protocol. The
                        DENOMINATOR (L1.57): a loss count with no exposure base is an anecdote.
                        Integrated by trapezoid into TVL-YEARS, so a $14B protocol-year and a
                        $10M one are not one "protocol-year" each.
  3. PEG               stablecoins.llama.fi/stablecoinprices -- daily price per stablecoin. The
                        depeg component measured, not assumed, including the 2023-03-12 USDC
                        trough this desk would otherwise be arguing about from memory.
  4. WITHDRAWAL QUEUE   our OWN data/defi_lending.jsonl utilisation tape. At 100% utilisation a
                        supplier CANNOT withdraw; that is the "correlated with exactly the moments
                        you need the collateral back" clause of the haircut's own docstring, and
                        it had never been measured on the desk's own data.

WHY THE DOWNLOAD PATH IS STREAMED AND NOT `json.loads`. The per-protocol histories are 3-29MB of
JSON each; parsing one whole builds a several-hundred-MB object, and this box OOM-killed
screen_orderbook_state four consecutive times at ~500MB free (R0378). `_top_level_array` walks the
file in fixed chunks tracking brace depth and string state, and parses ONLY the top-level `tvl`
array (~100KB). Peak RSS is O(chunk), not O(file). The naive scan for `"tvl":` is WRONG on this
schema and the test proves it: `chainTvls` comes first in the byte stream and carries one `"tvl":`
key per chain, so a first-match scan reads Base-borrowed and calls it the protocol.

WHAT THIS FILE DOES NOT DO. It collects; it decides nothing. `libs/research/lending_haircut.py`
derives the number and owns every judgement (reference set, confidence bound, which components are
priced at all). Stage A, zero promotion authority (L1.6): this moves no funds and lifts no clamp.

    .venv/bin/python scripts/collect_lending_risk_base_rates.py [--json] [--offline]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402

_UA = "quant-research/1.0 (lending risk base rates; contact via repo)"
_TIMEOUT = 90
_CHUNK = 1 << 20

_HACKS = "https://api.llama.fi/hacks"
_PROTOCOLS = "https://api.llama.fi/protocols"
_PRICES = "https://stablecoins.llama.fi/stablecoinprices"
_PROTOCOL = "https://api.llama.fi/protocol/{slug}"

#: The reference set: the lending protocols whose pools this desk would ACTUALLY supply into --
#: exactly the projects present in `data/defi_lending.jsonl`, plus the predecessor versions whose
#: TVL-years and losses belong to the same reference class. Chosen BEFORE the numbers were read
#: (the alternative -- picking the set after seeing which protocols were clean -- is the
#: garden-of-forking-paths on a risk estimate, and it fails in the direction that opens the band).
BLUE_CHIP_SLUGS: tuple[str, ...] = (
    "aave-v3", "aave-v2", "morpho-blue", "compound-v3", "compound-finance", "sparklend",
)
#: Hack rows whose `name` maps into the reference set. DefiLlama's hack names are protocol
#: display names and do not always equal the TVL slug, so the join is by an explicit table
#: rather than by a fuzzy match that would silently drop events (L1.60: a join that loses rows
#: in silence is a denominator claim the desk cannot cash).
BLUE_CHIP_HACK_NAMES: frozenset[str] = frozenset({
    "aave", "aave v1", "aave v2", "aave v3", "morpho blue", "morpho",
    "compound", "compound finance", "compound v1", "compound v2", "compound v3",
    "sparklend", "spark", "spark protocol",
})
#: Stablecoins priced for the depeg component, by DefiLlama/coingecko id.
PEG_ASSETS: dict[str, str] = {"usd-coin": "USDC", "tether": "USDT", "dai": "DAI"}
#: Prices outside this band are a feed error, not a depeg: a stablecoin at 0.0 or 12.0 is a bad
#: row, and averaging it into a shortfall would manufacture a haircut out of a parse failure.
_PRICE_SANE = (0.5, 1.5)
#: A supplier cannot withdraw at full utilisation. Measured at BOTH rungs so the reader sees the
#: shape rather than one threshold's answer.
_UTIL_RUNGS: tuple[float, ...] = (0.95, 0.99)

OUT = "data/lending_risk_base_rates.json"


def _fetch(url: str, dest: Path) -> tuple[int, str]:
    """Stream a URL to disk. Returns (bytes, error). Never raises: one dead source is not fatal."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        n = 0
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r, dest.open("wb") as fh:
            while chunk := r.read(_CHUNK):
                fh.write(chunk)
                n += len(chunk)
        return n, ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, f"{type(exc).__name__}: {str(exc)[:160]}"


def _top_level_array(path: Path, key: str) -> list[dict[str, Any]] | None:
    """The value of a DEPTH-1 array key, parsed without loading the file.

    Walks bytes tracking `{}`/`[]` depth and string/escape state, so it finds the key at the
    top level of the object and NOT the same key nested inside `chainTvls`. Returns None when
    the key is absent or the slice does not parse -- never a silent empty list, which a caller
    would integrate to a zero denominator and publish as a real exposure (L1.28a).
    """
    want = f'"{key}"'.encode()
    depth, in_str, esc = 0, False, False
    cap: bytearray | None = None
    buf = b""
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(_CHUNK):
                buf += chunk
                i = 0
                while i < len(buf):
                    c = buf[i : i + 1]
                    if in_str:
                        if esc:
                            esc = False
                        elif c == b"\\":
                            esc = True
                        elif c == b'"':
                            in_str = False
                    elif c == b'"':
                        # Only a DEPTH-1 key can be the top-level array; deeper is a nested
                        # series (`chainTvls` carries one `"tvl"` per chain and comes FIRST in
                        # the byte stream, so a naive find() reads Base-borrowed instead).
                        if depth == 1 and cap is None:
                            if len(buf) - i < len(want) + 2:
                                break                      # undecidable: need more bytes
                            if buf[i : i + len(want)] == want:
                                j = i + len(want)
                                while j < len(buf) and buf[j : j + 1] in (b" ", b":", b"\n",
                                                                          b"\t", b"\r"):
                                    j += 1
                                if j >= len(buf):
                                    break                  # value not yet in the buffer
                                if buf[j : j + 1] != b"[":
                                    i = j                  # key present, value is not an array
                                    continue
                                cap, depth, i = bytearray(b"["), depth + 1, j + 1
                                continue
                        in_str = True
                    elif c in (b"{", b"["):
                        depth += 1
                    elif c in (b"}", b"]"):
                        depth -= 1
                        if cap is not None and depth == 1:
                            cap += c
                            try:
                                out = json.loads(bytes(cap))
                            except ValueError:
                                return None
                            return out if isinstance(out, list) else None
                    if cap is not None:
                        cap += c
                    i += 1
                buf = buf[i:]                              # keep ONLY unprocessed bytes
    except OSError:
        return None
    return None


def _tvl_years(series: list[dict[str, Any]]) -> tuple[float, int, int, str, str]:
    """Trapezoid-integrate a daily TVL series into TVL-YEARS.

    Gaps longer than a week are NOT bridged: a protocol DefiLlama stopped tracking did not hold
    that TVL through the hole, and bridging would inflate the exposure denominator -- the
    direction that shrinks the haircut and opens the band.
    """
    pts = []
    skipped = 0
    for row in series:
        try:
            pts.append((int(row["date"]), float(row["totalLiquidityUSD"])))
        except (KeyError, TypeError, ValueError):
            skipped += 1                                   # attrition-counted, never silent
    pts.sort()
    years = 0.0
    for (t0, v0), (t1, v1) in itertools.pairwise(pts):
        days = (t1 - t0) / 86400.0
        if 0.0 < days <= 7.0:
            years += 0.5 * (v0 + v1) * days / 365.0
    first = datetime.fromtimestamp(pts[0][0], UTC).date().isoformat() if pts else ""
    last = datetime.fromtimestamp(pts[-1][0], UTC).date().isoformat() if pts else ""
    return years, len(pts), skipped, first, last


def collect_exposure(tmp: Path, *, offline: bool = False) -> dict[str, Any]:
    """TVL-years per reference protocol. Every slug reports READ or its failure, never absence."""
    per: dict[str, Any] = {}
    for slug in BLUE_CHIP_SLUGS:
        dest = tmp / f"llama_{slug}.json"
        if offline and not dest.exists():
            per[slug] = {"status": "OFFLINE", "tvl_years_usd": None}
            continue
        if not offline:
            n, err = _fetch(_PROTOCOL.format(slug=slug), dest)
            if err:
                per[slug] = {"status": "UNREADABLE", "error": err, "tvl_years_usd": None}
                continue
            if n == 0:
                per[slug] = {"status": "EMPTY", "tvl_years_usd": None}
                continue
        series = _top_level_array(dest, "tvl")
        if series is None:
            per[slug] = {"status": "UNPARSEABLE", "tvl_years_usd": None}
            continue
        years, n_pts, skipped, first, last = _tvl_years(series)
        per[slug] = {"status": "READ", "tvl_years_usd": round(years, 2), "n_points": n_pts,
                     "n_rows_unusable": skipped, "first": first, "last": last}
        if not offline:
            # Only delete what THIS run downloaded: these payloads are 3-29MB each and there is
            # no reason to leave ~100MB on a 3.8GB box. A pre-existing cache is left alone, or
            # --offline would work exactly once and report OFFLINE forever after.
            dest.unlink(missing_ok=True)
    total = sum(float(v["tvl_years_usd"] or 0.0) for v in per.values() if v.get("status") == "READ")
    ok = [s for s, v in per.items() if v.get("status") == "READ"]
    return {"per_protocol": per, "total_tvl_years_usd": round(total, 2),
            "n_protocols_declared": len(BLUE_CHIP_SLUGS), "n_protocols_read": len(ok),
            "complete": len(ok) == len(BLUE_CHIP_SLUGS)}


def collect_losses(tmp: Path, *, offline: bool = False) -> dict[str, Any]:
    """Exploit losses, NET of returned funds, split into the reference set and the wide category."""
    dest = tmp / "llama_hacks.json"
    if not offline:
        _n, err = _fetch(_HACKS, dest)
        if err:
            return {"status": "UNREADABLE", "error": err}
    try:
        rows = json.loads(dest.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    if not isinstance(rows, list):
        return {"status": "UNPARSEABLE", "error": "hacks payload is not a list"}

    seen, unusable, blue, category = 0, 0, [], []
    for h in rows:
        if not isinstance(h, dict):
            unusable += 1
            continue
        seen += 1
        try:
            gross = float(h.get("amount") or 0.0)
            returned = float(h.get("returnedFunds") or 0.0)
            when = datetime.fromtimestamp(int(h["date"]), UTC).date().isoformat()
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            unusable += 1
            continue
        rec = {"date": when, "name": str(h.get("name") or ""), "gross_usd": gross,
               "returned_usd": returned, "net_usd": max(gross - returned, 0.0),
               "technique": str(h.get("technique") or "")}
        if rec["name"].lower() in BLUE_CHIP_HACK_NAMES:
            blue.append(rec)
        if str(h.get("targetType") or "") == "DeFi Protocol":
            category.append(rec)
    blue.sort(key=lambda r: r["date"])
    return {
        "status": "READ", "n_rows_seen": seen, "n_rows_unusable": unusable,
        "n_rows_attempted": len(rows),
        "blue_chip_events": blue,
        "blue_chip_net_usd": round(sum(r["net_usd"] for r in blue), 2),
        "defi_wide_n": len(category),
        "defi_wide_net_usd": round(sum(r["net_usd"] for r in category), 2),
    }


def collect_peg(tmp: Path, *, offline: bool = False) -> dict[str, Any]:
    """Daily shortfall below $1 per stablecoin -- the depeg component, measured not assumed."""
    dest = tmp / "llama_prices.json"
    if not offline:
        _n, err = _fetch(_PRICES, dest)
        if err:
            return {"status": "UNREADABLE", "error": err}
    try:
        rows = json.loads(dest.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    if not isinstance(rows, list):
        return {"status": "UNPARSEABLE", "error": "price payload is not a list"}

    out: dict[str, Any] = {}
    for cid, sym in PEG_ASSETS.items():
        prices: list[tuple[int, float]] = []
        attempted, rejected = 0, 0
        for r in rows:
            if not isinstance(r, dict) or cid not in (r.get("prices") or {}):
                continue
            attempted += 1
            try:
                p, when = float(r["prices"][cid]), int(r["date"])
            except (KeyError, TypeError, ValueError):
                rejected += 1
                continue
            if when <= 0:
                # The feed's first row carries date=0. Kept out of the sample rather than
                # silently averaged in: it would date the window to 1970-01-01 and add a
                # phantom observation to the denominator the shortfall is divided by.
                rejected += 1
                continue
            if not (_PRICE_SANE[0] < p < _PRICE_SANE[1]):
                rejected += 1                              # feed error, not a depeg
                continue
            prices.append((when, p))
        if not prices:
            out[sym] = {"status": "NO-DATA", "n_days": 0, "n_rows_attempted": attempted}
            continue
        prices.sort()
        ps = [p for _, p in prices]
        n = len(ps)
        worst_t, worst_p = min(prices, key=lambda x: x[1])
        out[sym] = {
            "status": "READ", "n_days": n,
            "n_rows_attempted": attempted, "n_rows_rejected": rejected,
            "mean_shortfall_bps": round(sum(max(0.0, 1.0 - p) for p in ps) / n * 10_000.0, 4),
            "pct_days_below_0995": round(100.0 * sum(1 for p in ps if p < 0.995) / n, 4),
            "pct_days_below_099": round(100.0 * sum(1 for p in ps if p < 0.99) / n, 4),
            "worst_price": round(worst_p, 6),
            "worst_date": datetime.fromtimestamp(worst_t, UTC).date().isoformat(),
            "first": datetime.fromtimestamp(prices[0][0], UTC).date().isoformat(),
            "last": datetime.fromtimestamp(prices[-1][0], UTC).date().isoformat(),
        }
    return {"status": "READ", "per_asset": out}


def collect_withdrawal_queue(root: Path) -> dict[str, Any]:
    """Utilisation on OUR OWN lending tape -- at 100% a supplier cannot withdraw at all.

    This is the one component measured from desk data rather than a vendor. It is reported as a
    FREQUENCY and is deliberately not converted into bps: the severity of being locked out
    (what a day of unavailable collateral costs this desk) is not measured anywhere, and
    inventing it would rebuild the exact defect this row exists to remove.
    """
    path = root / "data/defi_lending.jsonl"
    per: dict[str, dict[str, Any]] = {}
    attempted, unusable = 0, 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.strip():
                    continue
                attempted += 1
                try:
                    r = json.loads(line)
                except ValueError:
                    unusable += 1
                    continue
                if not isinstance(r, dict):
                    unusable += 1
                    continue
                u, pool = r.get("utilisation"), r.get("pool")
                if not isinstance(u, (int, float)) or not pool:
                    continue
                key = f"{r.get('project')}/{str(r.get('symbol') or '').upper()}/{str(pool)[:8]}"
                slot = per.setdefault(key, {"n": 0, "max": 0.0, "tvl_usd": 0.0,
                                            **{f"n_ge_{int(x * 100)}": 0 for x in _UTIL_RUNGS}})
                slot["n"] += 1
                slot["max"] = max(float(slot["max"]), float(u))
                tvl = r.get("tvl_usd")
                if isinstance(tvl, (int, float)):
                    slot["tvl_usd"] = float(tvl)
                elif tvl is not None:
                    slot["n_tvl_unusable"] = int(slot.get("n_tvl_unusable", 0)) + 1
                for rung in _UTIL_RUNGS:
                    if float(u) >= rung:
                        slot[f"n_ge_{int(rung * 100)}"] += 1
    except OSError:
        return {"status": "NO-DATA", "why": f"{path} absent or unreadable"}
    if not per:
        return {"status": "NO-DATA", "why": f"{path} holds no utilisation rows",
                "n_rows_attempted": attempted, "n_rows_unusable": unusable}
    for slot in per.values():
        for rung in _UTIL_RUNGS:
            k = f"n_ge_{int(rung * 100)}"
            slot[f"pct_ge_{int(rung * 100)}"] = round(100.0 * slot[k] / slot["n"], 3)
    return {"status": "READ", "n_rows_attempted": attempted, "n_rows_unusable": unusable,
            "n_pools": len(per), "per_pool": per}


def build(root: Path | None = None, *, offline: bool = False) -> dict[str, Any]:
    root = root or _ROOT
    tmp = root / "data/.llama_cache"
    tmp.mkdir(parents=True, exist_ok=True)
    losses = collect_losses(tmp, offline=offline)
    exposure = collect_exposure(tmp, offline=offline)
    peg = collect_peg(tmp, offline=offline)
    queue = collect_withdrawal_queue(root)
    measured = (losses.get("status") == "READ" and exposure.get("complete")
                and peg.get("status") == "READ")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "row": "R0375", "law": "L1.51", "stage": "A",
        "status": "READ" if measured else "PARTIAL",
        "measured": measured,
        "sources": {"hacks": _HACKS, "protocols": _PROTOCOL, "prices": _PRICES,
                    "withdrawal_queue": "data/defi_lending.jsonl (desk-collected)"},
        "licence": "DefiLlama public API -- free, keyless, no licence bar on research reads (§13)",
        "losses": losses, "exposure": exposure, "peg": peg, "withdrawal_queue": queue,
        "authority": "STAGE A evidence. Derives nothing and moves no funds -- "
                     "libs/research/lending_haircut.py owns every judgement made from this.",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--offline", action="store_true",
                    help="reuse any cached payloads; report OFFLINE rather than fetching")
    args = ap.parse_args()
    rep = build(offline=args.offline)
    out = _ROOT / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        exp, los = rep["exposure"], rep["losses"]
        print(f"lending risk base rates: {rep['status']} -- "
              f"{exp['n_protocols_read']}/{exp['n_protocols_declared']} protocols, "
              f"${exp['total_tvl_years_usd'] / 1e9:.1f}B TVL-years, "
              f"{len(los.get('blue_chip_events', []))} attributable events, "
              f"${float(los.get('blue_chip_net_usd') or 0) / 1e6:.2f}M net loss\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
