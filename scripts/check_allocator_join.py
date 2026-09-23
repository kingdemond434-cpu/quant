"""FENCE: the allocator's book must actually join the sleeve registry.

WHY THIS EXISTS. On 2026-09-15 the desk discovered that `pf_allocation.json`'s book and
`sleeves.json` spell the same sleeve two different ways:

    allocator book   CHFNOK_carry_asia          SYMBOL_family_selector, symbol upper-cased
    sleeve registry  chfnok_carry_asia_p_98d7   symbol lower-cased, parameter hash appended

The gateway looked a sleeve up as `s["name"] in book`. Across 40 LIVE rows the exact intersection
was 1 with the dynamic book and 0 with the fallback. So `from_book` was False for essentially
every sleeve on every pass, each fell through to `promoted_lot`'s ramp and
`sizing.clamp_risk_frac` -- which FLOORS at BASE_RISK_FRAC -- and the optimiser, the baseline
contest, the proof certificate and the heat budget all resolved to one flat base fraction at the
venue. A sleeve forward-measuring +1.77R and one measuring -0.574R were sized identically.

THE FAILURE WAS SILENT AND EVERY ARTIFACT LOOKED RIGHT. `pf_allocation.json` held a well-formed
book. `sleeves.json` held well-formed rows. The gateway logged a sizing line every pass. Nothing
anywhere said "these two files do not refer to the same sleeves", because nothing checked.

So this checks. It is cheap, it reads two artifacts, and it fails when the desk's capital
allocation stops reaching the desk's positions. A join that silently empties is exactly the class
of defect the desk cannot detect by reading logs, which is what makes it worth a fence.

    python scripts/check_allocator_join.py            # exits 1 on a broken join
    python scripts/check_allocator_join.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
ALLOC = DESK / "reports" / "pf_allocation.json"
SLEEVES = DESK / "data" / "sleeves.json"

#: A book that funds sleeves and joins NONE of them is broken by definition. Stated as a floor on
#: the join rather than on a ratio: the allocator legitimately prices sleeves that are not live
#: (they were live when it solved) and legitimately leaves new sleeves unpriced, so the honest
#: invariant is that SOME funded name reaches SOME live row.
MIN_JOINED = 1


def _book_key(row: dict[str, object], book: dict[str, object]) -> str | None:
    """Mirror of `mt5desk.gateway._book_key`, kept here so the fence needs no MT5 import.

    Deliberately a copy and not an import: this fence must run on a box with no MetaTrader5
    package (the VPS, CI) and its whole job is to catch the two spellings drifting apart.
    `test_allocator_join_fence` pins the two implementations to the same answers.
    """
    if not book:
        return None
    name = str(row.get("name") or "")
    if name in book:
        return name
    # THE VERSION SUFFIX (2026-09-23): the live rows are `gold_afternoon_v2/_v3/_v4` and the
    # allocator prices `gold_afternoon`. Same sleeve, same window, re-versioned row -- so the
    # join emptied on a suffix and this fence measured 0/7. Mirrors `gateway._book_key` exactly.
    base = re.sub(r"_v\d+$", "", name)
    if base != name:
        if base in book:
            return base
        folded_base = {k.lower(): k for k in book}
        if base.lower() in folded_base:
            return str(folded_base[base.lower()])
    sym = str(row.get("symbol") or "").upper()
    fam = str(row.get("family") or "")
    sel = str(row.get("selector") or "")
    if not (sym and fam):
        return None
    derived = f"{sym}_{fam}_{sel}" if sel else f"{sym}_{fam}"
    if derived in book:
        return derived
    folded = {k.lower(): k for k in book}
    return folded.get(derived.lower())


def measure() -> dict[str, Any]:
    try:
        art = json.loads(ALLOC.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED",
                "why": f"pf_allocation.json unreadable ({type(exc).__name__})"}
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
        rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED",
                "why": f"sleeves.json unreadable ({type(exc).__name__})"}

    live = [r for r in (rows or [])
            if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"]
    books = {"dynamic": art.get("book") or {},
             "fallback": (art.get("book_fallback") or {}).get("book") or {}}

    out: dict[str, Any] = {"n_live": len(live), "books": {}, "status": "OK",
                           "why": ""}
    broken = []
    for label, bk in books.items():
        bk = {str(k): v for k, v in bk.items()}
        joined = [r for r in live if _book_key(r, bk) is not None]
        raw = [r for r in live if str(r.get("name") or "") in bk]
        out["books"][label] = {"entries": len(bk), "joined": len(joined),
                               "joined_by_raw_name": len(raw)}
        # An EMPTY book is not a broken join -- it is the allocator declining to allocate, which
        # `book_from_allocation` already reports as its own refusal. Only a book that funds
        # something and reaches nothing is a defect.
        if bk and not joined:
            broken.append(f"{label} book funds {len(bk)} sleeve(s) and joins NONE of the "
                          f"{len(live)} live rows")
    if broken:
        out["status"] = "BROKEN"
        out["why"] = ("; ".join(broken)
                      + " -- every sleeve then reads from_book=False and is sized at the "
                        "BASE_RISK_FRAC floor, so the allocator sizes nothing")
    elif not live:
        out["status"] = "UNMEASURED"
        out["why"] = "no LIVE sleeve in the registry; the join cannot be measured"
    else:
        out["why"] = "; ".join(f"{k}: {v['joined']}/{len(live)} live rows joined"
                               for k, v in out["books"].items())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the measurement as JSON")
    a = ap.parse_args(argv)
    m = measure()
    if a.json:
        print(json.dumps(m, indent=1))
    else:
        print(f"allocator join: {m['status']} -- {m['why']}")
        for label, d in (m.get("books") or {}).items():
            print(f"   {label:9} entries={d['entries']:3} joined={d['joined']:3} "
                  f"(by raw name alone: {d['joined_by_raw_name']})")
    return 1 if m["status"] == "BROKEN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
