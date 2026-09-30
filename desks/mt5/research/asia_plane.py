"""Every Asian ground, converted into gauntlet cells. A ground with no converter is a DEFECT.

THE RULE THIS FILE ENFORCES (principal, 2026-09-15): every ground the desk ever covers must have
machinery that turns it into cells for the gauntlet. Not a collector, not a dashboard tile, not a
document saying the source is interesting -- CELLS, in the docket, judged or explicitly blocked on
a named feed. A source that produces no cell is indistinguishable from a source nobody added, and
this desk has had both and could not tell them apart.

It is III.16 applied one layer out. "Unwired or idle is a defect" already says a built organ that
runs on no clock is not done; this says a ground that reaches no gauntlet is not covered. The
failure mode is specific and it is the one that makes source lists grow forever: adding a name to
a registry FEELS like progress, costs nothing, and is measured by nothing.

TWO TIERS, AND THE SECOND ONE IS NOT A STUB.

    MEASURABLE_NOW    the hypothesis is expressible in the bars already on disk. Chinese
                      information arrives during the Asia session, so its price EXPRESSION --
                      how the Asia session behaves, and what that says about London -- can be
                      tested today against the instruments the source names. These become real
                      docket cells on this pass.

    BLOCKED_ON_DATA   the hypothesis needs the external series itself (the SGE premium, the SHFE
                      member ranking, the fixing surprise). The cell is minted anyway, carrying
                      the exact source id it waits on, and it is COUNTED as blocked. That count
                      is the collector backlog, stated as a number instead of a feeling.

A BLOCKED CELL IS NOT A MEASURED ONE AND IS NEVER SCORED AS ONE. That is L1.28a and it is the
whole reason the tier is named in the row rather than inferred later.

WHAT THIS DOES NOT DO. It does not crawl, and it does not duplicate `deep_forest_miner` -- the
practitioner forest already works 502 grounds including 30 Chinese ones, and a second crawler over
the same ground would double the multiple-testing charge for the same information. This registry
is the HARD-DATA half: official, exchange, physical and flow, where the number itself is the
observation rather than somebody's opinion about it.

    python desks/mt5/research/asia_plane.py            # convert, publish, probe nothing
    python desks/mt5/research/asia_plane.py --probe    # add liveness/MOVED per route
    python desks/mt5/research/asia_plane.py --dry-run  # convert and print, donate nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = BASE / "data" / "asia_sources.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
#: The seat directory the compiler already reads. `miner_candidate_compiler` walks
#: `data/intelligence/**` and nothing else, so donating here is the whole of the wiring --
#: no new reader, no new schedule, no second pipeline that can drift from the first.
SEAT = BASE / "data" / "intelligence" / "asia"
OUT = BASE / "reports" / "ASIA_PLANE.json"

#: Mechanism kind -> the registered price-only families that EXPRESS it, and the session the
#: information arrives in. Keyed off the source's own declared mechanism text rather than a
#: per-source table, so adding a source to the registry converts without touching this file.
#:
#: THESE ARE EXPRESSIONS, NOT THE CHANNEL ITSELF, and the distinction is load-bearing. A cell
#: reading `mean_reversion_rsi on AUDUSD, asia` donated because SHFE copper inventory transmits
#: to AUD is NOT testing the copper channel -- it is testing whether the price expression the
#: channel would produce is there at all. If it is not, the channel is dead before a single byte
#: of SHFE data is collected, and that is worth knowing first because it is free.
_EXPRESSION = {
    "state": (("mean_reversion_rsi", "range_reversion", "spread_state"),
              "an inventory, premium or positioning STATE mean-reverts when it is extreme"),
    "flow": (("overnight_drift", "trend_ma_cross", "asia_momentum"),
             "a persistent settlement or portfolio flow drifts in one direction across sessions"),
    "event": (("session_range_breakout", "asia_momentum", "volatility_squeeze"),
              "a scheduled release resolves a coiled range in the session it lands in"),
    "crowd": (("retail_overlap_reversal", "failed_breakout", "pin_bar_reversal"),
              "a crowded book is a supply of stops, so the break that should run fails"),
    "handoff": (("overnight_gap_decay", "london_close_momentum", "asia_momentum"),
                "information priced in Asia is repriced, or given back, when London arrives"),
}

#: Keywords in a source's declared mechanism -> which expression it gets. First match wins and the
#: order is deliberate: positioning language is more specific than flow language, which is more
#: specific than the generic "demand".
_KIND_HINTS = (
    ("crowd", ("crowding", "retail", "stops", "crowded")),
    ("state", ("inventory", "premium", "basis", "receipt", "positioning", "concentration",
               "term structure", "curve", "stock")),
    ("event", ("surprise", "release", "print", "fixing", "operation", "announcement", "policy")),
    ("flow", ("flow", "settlement", "imbalance", "accumulation", "bid", "payment", "reserve",
              "northbound", "portfolio")),
    ("handoff", ("session", "close", "open", "overnight", "hours")),
)

#: Sources the desk HAS DATA FOR, read from the lake rather than declared in a tuple.
#:
#: THIS WAS A HARDCODED LIST AND THAT MADE THE TIER A CLAIM INSTEAD OF A MEASUREMENT. It named
#: one source and every other cell was BLOCKED_ON_DATA by assertion -- so a source the collector
#: had successfully fetched would have gone on reporting itself blocked until somebody remembered
#: to edit this line. That is the same shape as every other defect found tonight: a status
#: asserted where it could have been read.
#:
#: `asia_collector` vaults every fetch under the source id, so the presence of a vault directory
#: or a parsed series IS the answer, it updates itself, and a source added tomorrow is measured
#: the hour its first fetch lands.
_LAKE = BASE / "data" / "lake"


def _have_data(as_of: Any = None) -> set[str]:
    """Source ids with bytes on disk THE DESK COULD ALREADY HAVE KNOWN: a parsed series whose
    `available_time` has arrived, or vaulted raw content.

    THE JOIN ON available_time IS THE POINT (Tier-1 B2). This asked only whether a FILE existed,
    so a series stamped with an available_time in the future counted as data in hand -- the exact
    lookahead the five PIT stamps exist to refuse, in the one place a consumer actually decides
    something. `libs.data.lake_pit.usable_series` performs the join; a series with no sidecar or
    an unreadable stamp stays VISIBLE and is counted as unstamped, because withholding data on
    the strength of a missing file would be a reduction bought with no evidence.
    """
    out: set[str] = set()
    series = _LAKE / "series"
    if series.is_dir():
        try:
            from libs.data.lake_pit import usable_series
            out |= usable_series(series, as_of).visible
        except ImportError:
            out |= {f.stem for f in series.iterdir()
                    if f.is_file() and not f.name.endswith(".pit.json")}
    vault = _LAKE / "vault"
    if vault.is_dir():
        out |= {d.name for d in vault.iterdir()
                if d.is_dir() and any(d.glob("*.gz"))}
    # `fetch_sge_premium` writes its own history outside the generic collector's tree.
    if (_LAKE / "sge_daily.parquet").exists():
        out.add("sge_benchmark")
    return out


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _kind_of(mechanism: str) -> str:
    m = (mechanism or "").lower()
    for kind, words in _KIND_HINTS:
        if any(w in m for w in words):
            return kind
    return "handoff"


def _resolvable(symbols: list[str], universe: dict[str, Any]) -> list[str]:
    """Targets the account actually quotes. `*` means the source informs the whole book.

    A symbol absent from the registry is UNCLASSIFIED and hunted by nothing until it is
    classified -- absence is not a permission (LAWS, TWO LANES).
    """
    if "*" in symbols:
        return []
    return [s for s in symbols if s in universe]


def _cell_id(source_id: str, symbol: str, family: str, session: str) -> str:
    raw = f"asia|{source_id}|{symbol}|{family}|{session}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def convert(registry: dict[str, Any], universe: dict[str, Any]) -> list[dict[str, Any]]:
    """Every source -> its cells. The rule is total: a source that converts to nothing is named.

    THE SESSION IS ASIA AND THAT IS THE POINT. Chinese and Japanese information is released into
    Asian hours; an expression tested in the London session has already been through a liquidity
    regime the information did not arrive in. `_text_params` reads the session out of the prose,
    so saying it here is what sets it downstream.
    """
    rows: list[dict[str, Any]] = []
    have_data = _have_data()
    for src in registry.get("sources") or []:
        if not isinstance(src, dict):
            continue
        sid = str(src.get("id") or "")
        plane = str(src.get("plane") or "")
        mech = str(src.get("mechanism") or "")
        role = str(src.get("role") or "mechanism")
        declared = [str(t) for t in (src.get("targets") or [])]
        targets = _resolvable(declared, universe)
        # THE TARGETS THE ACCOUNT DOES NOT QUOTE ARE NAMED, NOT DROPPED. A source declaring
        # Copper, CN50 and USDCNH on an account that quotes none of them has converted to less
        # than it looks like it did, and a silent filter is how that becomes invisible.
        unquoted = [t for t in declared if t != "*" and t not in universe]

        if role == "transport":
            # A TRANSPORT IS NOT A MECHANISM and minting cells for it would double-count the
            # exchange it carries. It answers to the same rule in its own currency: every source
            # it serves must be named, and a transport serving nothing is the identical defect.
            serves = [str(s) for s in (src.get("serves") or [])]
            if not serves:
                rows.append({"kind": "unconverted", "source": f"asia:{sid}",
                             "asia_source_id": sid, "asia_plane": plane, "tier": "NO_CELLS",
                             "why": "declared a transport and serves no source: it carries "
                                    "nothing, so it converts to nothing"})
            else:
                rows.append({"kind": "transport", "source": f"asia:{sid}",
                             "asia_source_id": sid, "asia_plane": plane, "tier": "TRANSPORT",
                             "serves": serves,
                             "why": f"carries {len(serves)} source(s); their cells are minted "
                                    f"under their own ids so nothing is counted twice"})
            continue

        kind = _kind_of(mech)
        families, why_kind = _EXPRESSION[kind]
        blocked = sid not in have_data
        for sym in targets:
            for fam in families:
                rows.append({
                    "kind": "hypothesis",
                    "family": fam,
                    "symbols": [sym],
                    "source": f"asia:{sid}",
                    "cell_id": _cell_id(sid, sym, fam, "asia"),
                    "asia_source_id": sid,
                    "asia_plane": plane,
                    "expression_kind": kind,
                    "tier": "BLOCKED_ON_DATA" if blocked else "MEASURABLE_NOW",
                    "blocked_on": sid if blocked else None,
                    "mechanism_status": "NAMED",
                    "mechanism": mech,
                    # PROVENANCE IN THE KEYS THE COMPILER ACTUALLY READS. `_candidate` takes
                    # the url from `url`/`link` and the title from `title`/`description`; a
                    # `public_source` key it does not read is provenance that silently does not
                    # survive the compile, which is how a cell arrives in the docket with no way
                    # back to the ground that minted it.
                    "url": str(src.get("url") or ""),
                    "title": f"{src.get('name')} -- {plane}",
                    "public_source": str(src.get("url") or ""),
                    "pit": src.get("pit") or {},
                    # The prose the compiler reads. It must name the session in words, because
                    # `_text_params` takes the selector from the TEXT and a structured field it
                    # does not read is a field that silently does not exist.
                    "text": (f"{fam} on {sym} in the asia session. {mech}. Transmission declared "
                             f"by {src.get('name')} ({plane}); expression class {kind}: "
                             f"{why_kind}. This is a hypothesis for the ten gates, not a claim, "
                             f"and the conditioning series itself is "
                             + ("NOT yet collected -- the price expression is what is testable "
                                f"today and {sid} is the feed it waits on."
                                if blocked else "collected locally.")),
                })
        if unquoted:
            rows.append({
                "kind": "unquoted_targets",
                "source": f"asia:{sid}", "asia_source_id": sid, "asia_plane": plane,
                "tier": "TARGET_NOT_QUOTED", "symbols": unquoted,
                "why": (f"{len(unquoted)} declared target(s) are not in this account's universe "
                        f"registry, so the transmission has no instrument to land on here. "
                        f"Absence is not permission: they are hunted by nothing until the "
                        f"registry classifies them."),
            })
        if not targets:
            # NAMED, NOT SKIPPED. A source whose targets the account does not quote, or which
            # declares `*`, has converted to nothing and the register says so by name. This is
            # the row that makes the rule enforceable instead of aspirational.
            rows.append({
                "kind": "unconverted",
                "source": f"asia:{sid}",
                "asia_source_id": sid,
                "asia_plane": plane,
                "tier": "NO_CELLS",
                "why": ("declares no MT5-resolvable target: either `*` (informs the whole book "
                        "and needs a named instrument) or symbols this account does not quote"),
            })
    return rows


def _probe_routes(registry: dict[str, Any], timeout: float) -> list[dict[str, Any]]:
    """Liveness and SHAPE per route, reusing the NOAA rule: 200 with the wrong shape is MOVED."""
    try:
        from scripts.check_source_routes import probe  # type: ignore[import-not-found]
    except Exception:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from check_source_routes import probe  # type: ignore[no-redef]
        except Exception:
            return []
    out: list[dict[str, Any]] = []
    for src in registry.get("sources") or []:
        if not isinstance(src, dict):
            continue
        access = str(src.get("access") or "public")
        if access in ("key", "paid"):
            # A keyed route with no key is UNCONFIGURED, which is a different fact from a dead
            # one. Probing it would return 401 and pollute the census with an auth failure
            # dressed as a route change -- and this desk has read exactly that backwards before.
            out.append({"name": src.get("id"), "url": src.get("url"), "status": "UNCONFIGURED",
                        "access": access, "key_env": src.get("key_env"),
                        "why": f"needs {access} access; not probed so an auth failure cannot be "
                               f"misread as a moved route"})
            continue
        r = probe({"name": src.get("id"), "url": src.get("url"),
                   "expect": src.get("expect") or "any"}, timeout)
        r["plane"] = src.get("plane")
        out.append(r)
    return out


def build(probe_routes: bool = False, timeout: float = 15.0) -> dict[str, Any]:
    registry = _read(REGISTRY, {})
    universe = _read(UNIVERSE, {})
    rows = convert(registry, universe)
    cells = [r for r in rows if r.get("kind") == "hypothesis"]
    unconverted = [r for r in rows if r.get("kind") == "unconverted"]
    transports = [r for r in rows if r.get("kind") == "transport"]
    unquoted = [r for r in rows if r.get("kind") == "unquoted_targets"]

    by_plane: dict[str, Counter] = {}
    for c in cells:
        by_plane.setdefault(str(c["asia_plane"]), Counter())[str(c["tier"])] += 1
    per_source = Counter(str(c["asia_source_id"]) for c in cells)

    doc: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("EVERY GROUND CONVERTS TO CELLS. A source in this registry that reaches no "
                 "gauntlet cell is a defect and is listed by name, not omitted. A cell that "
                 "needs a feed the desk does not hold is BLOCKED_ON_DATA and carries the id of "
                 "the feed -- blocked is a verdict, never a pass."),
        "n_sources": len(registry.get("sources") or []),
        "n_cells": len(cells),
        "n_unconverted_sources": len(unconverted),
        "unconverted": unconverted,
        "n_transports": len(transports),
        "transports": transports,
        "unquoted_targets": unquoted,
        "n_targets_not_quoted": sum(len(u["symbols"]) for u in unquoted),
        "tiers": dict(Counter(str(c["tier"]) for c in cells)),
        "by_plane": {k: dict(v) for k, v in sorted(by_plane.items())},
        "cells_per_source": dict(per_source.most_common()),
        "expression_kinds": dict(Counter(str(c["expression_kind"]) for c in cells)),
        "families_used": dict(Counter(str(c["family"]) for c in cells)),
        "symbols_touched": sorted({str(c["symbols"][0]) for c in cells}),
    }
    if probe_routes:
        routes = _probe_routes(registry, timeout)
        doc["routes"] = routes
        doc["route_census"] = dict(Counter(str(r.get("status")) for r in routes))
        doc["moved"] = [r for r in routes if r.get("status") == "MOVED"]
    return doc, cells


def donate(cells: list[dict[str, Any]]) -> Path:
    """Write the cells where the compiler already looks. One file per pass, atomically.

    Not appended to a growing file: the compiler reads the directory, and a pass that re-donates
    the same deterministic cell ids is idempotent by construction rather than by a dedupe pass
    somebody has to remember to run.
    """
    SEAT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H")
    out = SEAT / f"asia_plane_{stamp}.json"
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(cells, indent=1), encoding="utf-8")
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--probe", action="store_true", help="also probe every public route")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--dry-run", action="store_true", help="convert and print, donate nothing")
    args = ap.parse_args(argv)

    doc, cells = build(probe_routes=args.probe, timeout=args.timeout)
    if not args.dry_run:
        doc["donated_to"] = str(donate(cells))
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print(f"asia plane: {doc['n_sources']} source(s) -> {doc['n_cells']} cell(s)  {doc['tiers']}")
    for plane, tiers in doc["by_plane"].items():
        print(f"  {plane:16} {dict(tiers)}")
    print(f"  expression kinds: {doc['expression_kinds']}")
    print(f"  {len(doc['symbols_touched'])} instrument(s) touched")
    if doc["unconverted"]:
        print(f"\n  UNCONVERTED {len(doc['unconverted'])} -- a ground that reaches no cell is a "
              f"defect:")
        for u in doc["unconverted"]:
            print(f"    {u['asia_source_id']!s:22} {str(u['why'])[:64]}")
    if doc.get("route_census"):
        print(f"\n  routes: {doc['route_census']}")
        for r in doc.get("moved") or []:
            print(f"    MOVED {r.get('name')}: {str(r.get('why'))[:70]}")
    if not args.dry_run:
        print(f"  donated -> {doc['donated_to']}")
        print(f"  -> {OUT}")
    # An unconverted ground is the fatal verdict: it is the thing the rule exists to forbid.
    return 1 if doc["unconverted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
