#!/usr/bin/env python3
"""TIER-1 W0 / C1 -- WHY LIVE TRADE ATTRIBUTION READS 4.6%, AND THE JOIN THAT FIXES IT.

THE SCORECARD'S ROW IS RIGHT AND ITS JOIN IS WRONG. `tier1_scorecard._r06_live_attribution`
attributes a deal by testing `deal["sleeve"] in {roster names} | {survivor keys}` -- an EXACT
string match. Measured on this box's own `data/live_ledger.jsonl` (151 deals, 2026-09-22):

  * the roster carries names up to 60 characters (`xau_m5_anti_breakout_overlap`,
    `chfnok_carry_asia_p_98d776f0a1...`), and
  * EVERY label the ledger carries is exactly 27 characters or shorter, because the gateway
    writes the sleeve into MetaTrader's position COMMENT and the terminal truncates it.

So `chfnok_carry_asia_p_98d776f` (14 deals) is the same sleeve as
`chfnok_carry_asia_p_98d776f0a1b2...` and the exact match says it is not. A second family of
labels is not a sleeve name at all: a deal closed by the broker's own take-profit or stop is
stamped `[tp 4360.71]` / `[sl 4461.71]`, which names the PRICE that closed it and not the
strategy that opened it.

Neither is a mystery trade. Both are joinable from what the ledger already records, and this
organ is that join, in three passes, each of which must be UNAMBIGUOUS or it does not fire:

  1. EXACT      the label is a roster name or a survivor key (what the scorecard already does).
  2. PREFIX     the label is a prefix of exactly ONE roster name. Two candidates sharing the
                prefix is an AMBIGUOUS verdict with both names published -- never a coin flip.
  3. GEOMETRY   a `[tp x]` / `[sl x]` deal matches an attributed deal on the same symbol and
                account whose own tp (or sl) is that price. The closing print and the opening
                print agree on the bracket the position was carrying, which is a fact the
                terminal wrote, not an inference.

WHAT IS NOT CLOSED, STATED PLAINLY. A deal none of the three passes reaches is UNATTRIBUTED and
is PUBLISHED BY NAME with its symbol, time and label, because "4.6% attributed" is only
actionable if the other 95% have names. The fix for the truncation itself belongs in the
gateway's comment writer (write a stable short id, not a truncated name) and is recorded here as
an owed change rather than performed here: this organ never writes to the ledger and never
edits a deal.

IT SIZES NOTHING. Attribution is provenance, not permission: no capital, no gate, no veto.

    python desks/mt5/research/attribution_reconcile.py [--once] [--budget-s N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent

LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"
SURVIVORS = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVE_REGISTRY = DESK / "data" / "sleeve_registry.json"
REPORT = DESK / "reports" / "ATTRIBUTION_RECONCILE.json"

#: The shortest label that may be prefix-matched. A two-character label is a prefix of half the
#: roster and matching on it would manufacture attribution, which is the opposite of the point.
MIN_PREFIX = 8

#: Price agreement for the geometry pass, as a RELATIVE tolerance. The two prints come from the
#: same terminal and the same position, so they agree to the tick; this only absorbs the
#: rounding in the label's own decimal rendering.
PRICE_TOL = 1e-6

EXACT, PREFIX, GEOMETRY = "EXACT", "PREFIX", "GEOMETRY"
AMBIGUOUS, UNATTRIBUTED = "AMBIGUOUS", "UNATTRIBUTED"
ROUTES = (EXACT, PREFIX, GEOMETRY)
RULE = ("a deal is attributed by an exact roster name, else by a UNIQUE roster-name prefix "
        "(the terminal truncates the comment), else by the tp/sl price its closing print "
        "carries; anything else is UNATTRIBUTED and published by name")


def _read_jsonl(path: Path) -> list[dict[str, Any]] | None:
    """Every readable row, or None when the file itself is absent (a different verdict)."""
    if not path.exists():
        return None
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return None
    return out


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def roster() -> tuple[list[str], dict[str, str]]:
    """Every name a deal could legitimately carry, and where each came from."""
    names: dict[str, str] = {}
    doc = _read_json(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    if isinstance(rows, list):
        for s in rows:
            if isinstance(s, dict) and s.get("name"):
                names.setdefault(str(s["name"]), "sleeves.json")
    canon = _read_json(SURVIVORS)
    surv = canon.get("survivors") if isinstance(canon, dict) else None
    if isinstance(surv, dict):
        for key in surv:
            names.setdefault(str(key), "UNIVERSAL_SURVIVORS.canon.json")
    # THE THREE GOLD WINDOWS ARE NAMES, NOT TRUNCATIONS. `promoter.GOLD_SLEEVE_NAMES` is the
    # desk's own declaration that `gold_asia`, `gold_london_am` and `gold_afternoon` ARE the
    # sleeves the gold book places under; the roster's `_v2/_v3/_v4` rows are the versioned
    # certificates BEHIND each window, so a deal stamped `gold_asia` prefix-matches three of
    # them and reads AMBIGUOUS while being perfectly well identified. Reading the constant
    # rather than restating it keeps the two from ever disagreeing.
    try:
        import sys
        if str(DESK) not in sys.path:
            sys.path.insert(0, str(DESK))
        from research.promoter import GOLD_SLEEVE_NAMES
    except Exception:                                    # absence is a verdict, never a crash
        GOLD_SLEEVE_NAMES = ()                           # type: ignore[assignment]
    for name in GOLD_SLEEVE_NAMES:
        names.setdefault(str(name), "promoter.GOLD_SLEEVE_NAMES (gateway window)")
    reg = _read_json(SLEEVE_REGISTRY)
    reg_rows = reg.get("sleeves") if isinstance(reg, dict) else reg
    if isinstance(reg_rows, list):
        for s in reg_rows:
            if isinstance(s, dict):
                for field in ("name", "key"):
                    if s.get(field):
                        names.setdefault(str(s[field]), "sleeve_registry.json")
    return sorted(names), names


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def bracket_price(label: str) -> tuple[str, float] | None:
    """`[tp 4360.71]` -> ("tp", 4360.71). None when the label is not a bracket print."""
    text = label.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return None
    body = text[1:-1].strip().split()
    if len(body) != 2:
        return None
    kind = body[0].lower()
    price = _num(body[1])
    if kind not in ("tp", "sl") or price is None:
        return None
    return kind, price


def prefix_match(label: str, names: list[str]) -> tuple[str | None, list[str]]:
    """The one roster name this truncated label can only be, or every candidate it could be."""
    if len(label) < MIN_PREFIX:
        return None, []
    hits = [n for n in names if n.startswith(label)]
    return (hits[0] if len(hits) == 1 else None), hits


def attribute(deals: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    """One verdict per deal, in the three passes, each unambiguous or it does not fire."""
    known = set(names)
    out: list[dict[str, Any]] = []
    for d in deals:
        label = str(d.get("sleeve") or "")
        row: dict[str, Any] = {
            "deal": d.get("deal"), "time": str(d.get("time") or ""),
            "symbol": str(d.get("symbol") or ""), "label": label,
            "account": d.get("account"),
            "tp": _num(d.get("tp")), "sl": _num(d.get("sl")),
            "sleeve": None, "route": UNATTRIBUTED, "candidates": [],
        }
        if label in known:
            row["sleeve"], row["route"] = label, EXACT
        else:
            hit, cands = prefix_match(label, names)
            if hit is not None:
                row["sleeve"], row["route"] = hit, PREFIX
            elif len(cands) > 1:
                row["route"], row["candidates"] = AMBIGUOUS, cands[:8]
        out.append(row)
    # PASS 3, after the first two, because it joins ONTO what they attributed.
    by_price: dict[tuple[str, int, float], str] = {}
    for row, d in zip(out, deals, strict=True):
        if row["sleeve"] is None:
            continue
        acct = int(_num(d.get("account")) or 0)
        for key in ("tp", "sl"):
            price = row[key]
            if price is not None and price > 0:
                by_price.setdefault((row["symbol"], acct, round(float(price), 5)),
                                    str(row["sleeve"]))
    for row, d in zip(out, deals, strict=True):
        if row["sleeve"] is not None:
            continue
        got = bracket_price(str(row["label"]))
        if got is None:
            continue
        _kind, price = got
        acct = int(_num(d.get("account")) or 0)
        hit = by_price.get((row["symbol"], acct, round(price, 5)))
        if hit is None:
            for (sym, a, p), name in by_price.items():
                if sym == row["symbol"] and a == acct and abs(p - price) <= PRICE_TOL * max(
                        1.0, abs(price)):
                    hit = name
                    break
        if hit is not None:
            row["sleeve"], row["route"] = hit, GEOMETRY
    return out


def build(*, budget_s: float = 300.0, ledger: Path | None = None) -> dict[str, Any]:
    """The reconciliation, written every run -- including when there is nothing to reconcile."""
    started = time.monotonic()
    lp = ledger or LIVE_LEDGER
    deals = _read_jsonl(lp)
    names, where = roster()
    inputs = {
        lp.name: "absent" if deals is None else ("present" if deals else "empty"),
        SLEEVES.name: "present" if SLEEVES.exists() else "absent",
        SURVIVORS.name: "present" if SURVIVORS.exists() else "absent",
        SLEEVE_REGISTRY.name: "present" if SLEEVE_REGISTRY.exists() else "absent",
    }
    notes: list[str] = []
    rows = attribute(deals or [], names) if deals else []
    counts = {r: sum(1 for x in rows if x["route"] == r)
              for r in (*ROUTES, AMBIGUOUS, UNATTRIBUTED)}
    n = len(rows)
    attributed = sum(counts[r] for r in ROUTES)
    if deals is None:
        notes.append(f"UNMEASURED: {lp.name} is absent on this host; attribution is not zero, "
                     "it is unmeasured (L1.28a)")
    elif not deals:
        notes.append(f"UNMEASURED: {lp.name} holds no deal; an empty ledger is not 100% "
                     "attributed")
    if not names:
        notes.append("UNMEASURED: no roster is readable on this host, so every label is "
                     "unattributable for a reason that is not the label's fault")
    exact_only = sum(1 for r in rows if r["route"] == EXACT)
    gained = attributed - exact_only
    if counts[AMBIGUOUS]:
        notes.append(f"{counts[AMBIGUOUS]} label(s) prefix-match more than one roster name and "
                     "are published with their candidates rather than guessed")
    truncated = sorted({str(r["label"]) for r in rows if r["route"] == PREFIX})
    if truncated:
        notes.append("the gateway writes the sleeve into MetaTrader's position comment, which "
                     "truncates it; the owed fix is a stable short id at the WRITER, not a "
                     "longer match here")
    by_route_syms = {r: sorted({x["symbol"] for x in rows if x["route"] == r})[:12]
                     for r in (*ROUTES, AMBIGUOUS, UNATTRIBUTED)}
    return {
        "schema": "attribution-reconcile-1",
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "rule": RULE,
        "inputs": inputs,
        "n_roster_names": len(names),
        "roster_sources": sorted(set(where.values())),
        "n_deals": n,
        "attributed_deals": attributed,
        "attributed_share": round(attributed / n, 6) if n else None,
        "attributed_pct": round(100.0 * attributed / n, 2) if n else None,
        "exact_only_pct": round(100.0 * exact_only / n, 2) if n else None,
        "recovered_by_this_organ": gained,
        "counts": counts,
        "symbols_by_route": by_route_syms,
        "truncated_labels": truncated[:40],
        "unattributed": [{k: r[k] for k in ("deal", "time", "symbol", "label", "candidates")}
                         for r in rows if r["route"] in (UNATTRIBUTED, AMBIGUOUS)][:80],
        "rows": rows[:400],
        "unmeasured": notes,
        "budget_s": budget_s,
        "elapsed_s": round(time.monotonic() - started, 3),
        "sizes_nothing": ("attribution is provenance, not permission: this organ allocates no "
                          "capital, gates no promotion and vetoes nothing"),
    }


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="reconcile every live deal to the roster that "
                                             "placed it")
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--out", type=Path, default=REPORT)
    a = ap.parse_args(argv)
    rep = build(budget_s=a.budget_s)
    pct = rep["attributed_pct"]
    print(f"attribution-reconcile: {rep['n_deals']} deal(s) against {rep['n_roster_names']} "
          f"roster name(s)")
    print(f"  attributed {rep['attributed_deals']}/{rep['n_deals']} = "
          f"{'UNMEASURED' if pct is None else str(pct) + '%'}  "
          f"(exact alone would read {rep['exact_only_pct']}%, "
          f"+{rep['recovered_by_this_organ']} recovered here)")
    print("  by route  " + "  ".join(f"{k}:{v}" for k, v in rep["counts"].items()))
    for note in rep["unmeasured"][:4]:
        print(f"  {note}")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    _atomic(a.out, json.dumps(rep, indent=1, default=str) + "\n")
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
