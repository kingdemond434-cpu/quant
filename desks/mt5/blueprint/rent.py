"""What each capability costs and what it returns -- mandate §135, §136, §158.

THE RULE THE MANDATE SETS AND THIS ENFORCES: every module eventually pays rent in
E[log W]. Below zero after enough evidence, it is hibernated or removed, and DELETION IS AN
OPTIMIZATION ACTION (§158). The desk is not trying to maximise lines of code.

WHY UPSTREAM MODULES ARE NOT CHARGED IN E[log W] YET, AND WHY THAT IS NOT A LOOPHOLE. A research
organ three steps from a trade cannot have its growth contribution measured until something it
produced reaches capital. Charging it in E[log W] today would price it at zero and retire the
whole research layer -- the mandate says so itself (§135), and allows the proxies:

    delta research velocity     idea -> result latency
    delta survivor yield        survivors per 10k tests
    delta false discovery       how many survivors die in forward
    delta live retention        how much certified edge survives contact

So a capability is UNPRICED, PROXY_PRICED or ELOG_PRICED, and the three are never summed. A
proxy is a promissory note, not a payment, and adding it to an E[log W] figure would let a module
that has produced no money claim it had.

REFUSES TO INVENT A NUMBER. Where `libs.ops.module_rent` carries no line for a module, the rent
is UNPRICED and says so. An estimated rent is worse than none: it would be the input to a
retire/keep decision, and a made-up input to a deletion decision deletes the wrong things.

    python blueprint/rent.py
    python blueprint/rent.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
# THIS PACKAGE'S DIRECTORY GOES FIRST, and that is not cosmetic: `scripts/dependency_graph.py`
# already exists and shadowed `blueprint/dependency_graph.py` when scripts/ sorted earlier --
# closure_report imported the wrong module and died on a missing name. Two files with one module
# name is a fact of this tree; the fix is to be explicit about which one this package means.
_HERE = str(Path(__file__).resolve().parent)
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.append(_p)
if _HERE in sys.path:
    sys.path.remove(_HERE)
sys.path.insert(0, _HERE)

OUT = Path(__file__).resolve().parent / "RENT.json"

#: Rungs at which a capability is claimed to touch a decision. At or above these the mandate
#: requires a measurement protocol; below, rent is legitimately not yet answerable.
DECIDING = ("DECISION_AFFECTING", "MEASURED", "PROVEN")


def _rent_lines() -> list[dict[str, Any]]:
    """Every MODULE_RENT line, with the fields it actually has.

    KEYED BY FILE STEM WAS WRONG AND SILENTLY WRONG. `MODULES` names its entries by LOGICAL
    module -- rail names, proposer arms, `state_posterior`, `state_dimension:<d>` -- not by
    filename; the file lives in `where`. Looking up `Path(name).stem` therefore matched almost
    nothing, and every capability came back PROTOCOL_ONLY. 79 of 94 "unpriced" was mostly my
    lookup missing, not the desk failing to price its organs, and a rent report that
    under-reports pricing is one that would retire modules for not paying when they do
    (§158 makes deletion an action, so a wrong input here deletes working code).

    The real fields are `rule` (the with/without statement) and `measure` (the function that
    computes it); there is no `metric`/`basis`, so reading those returned empty strings that
    then looked like a missing protocol.
    """
    try:
        from libs.ops import module_rent as mr
    except Exception:                             # noqa: BLE001 - absence is reported, not raised
        return []
    out: list[dict[str, Any]] = []
    for m in getattr(mr, "MODULES", ()):
        out.append({
            "name": str(getattr(m, "name", "") or ""),
            "kind": str(getattr(m, "kind", "") or ""),
            "rule": str(getattr(m, "rule", "") or ""),
            "measure": str(getattr(m, "measure", "") or ""),
            "where": str(getattr(m, "where", "") or ""),
            "ledger": str(getattr(m, "ledger", "") or ""),
        })
    return out


def _line_for(producer: str, lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The rent line that prices this producer, matched on `where` then on name.

    `where` is the field that names the code, so it is tried first and on the PATH rather than
    the stem: `pf_allocator` appears in several rules as prose, and a stem match would price a
    capability by a sentence that merely mentions it.
    """
    if not producer:
        return None
    stem = Path(producer).stem
    for line in lines:
        where = line["where"]
        if where and (producer in where or f"{stem}." in where or f"/{stem}" in where):
            return line
    for line in lines:
        if stem and stem == line["name"]:
            return line
    return None


def rent() -> dict[str, Any]:
    from coverage import registry
    reg = registry()
    lines = _rent_lines()
    rows: list[dict[str, Any]] = []
    for cap in reg["capabilities"]:
        line = _line_for(cap.get("producer") or "", lines)
        declared = cap.get("measurements") or ""
        if line:
            # ELOG when the RULE states a with/without in log-wealth -- the mandate's own
            # currency. Anything else MODULE_RENT prices is a real measurement in another unit
            # (out-of-sample MSE gain, survivor growth), which is a proxy and is never summed
            # with a growth figure.
            rule = (line.get("rule") or "").lower()
            kind = "ELOG_PRICED" if ("log w" in rule or "log-wealth" in rule) else "PROXY_PRICED"
        elif declared:
            # The registry declares WHAT would price it; that is a protocol, not a payment.
            kind = "PROTOCOL_ONLY"
        else:
            kind = "UNPRICED"
        rows.append({
            "id": cap["id"], "producer": cap.get("producer"), "status": cap["status"],
            "rent_kind": kind,
            "metric": (line or {}).get("rule") or declared,
            "basis": (line or {}).get("where") or "",
            "measure_fn": (line or {}).get("measure") or "",
            "ledger": (line or {}).get("ledger") or "",
            # §136: a capability that DECIDES and is not priced is the one the mandate says must
            # not keep its authority. Named so the governor can act rather than inferring it.
            "owes_rent": cap["status"] in DECIDING and kind in ("UNPRICED", "PROTOCOL_ONLY"),
        })
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["rent_kind"]] = kinds.get(r["rent_kind"], 0) + 1
    return {
        "generated_at": reg["generated_at"], "git_sha": reg["git_sha"],
        "total": len(rows), "by_kind": kinds,
        "owing": [r["id"] for r in rows if r["owes_rent"]],
        "capabilities": rows,
        "law": ("E[log W] rent and proxy rent are NEVER summed. A proxy is a promissory note; "
                "adding it to a growth figure lets a module that has produced no money claim it "
                "had. An unpriced module is reported UNPRICED and never estimated -- rent is the "
                "input to a retire/keep decision, and a made-up input deletes the wrong things."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    r = rent()
    if args.write:
        OUT.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
        print(f"{r['total']} capabilities -> {OUT}")
    if args.json:
        print(json.dumps(r, indent=2, default=str))
        return 0
    if not args.write:
        print(f"rent across {r['total']} capabilities @ {r['git_sha'] or 'no sha'}")
        for k, n in sorted(r["by_kind"].items(), key=lambda kv: -kv[1]):
            print(f"  {k:16s} {n:4d}")
        print(f"\n  decision-affecting and owing rent: {len(r['owing'])}"
              + (f" -> {', '.join(r['owing'][:12])}" if r["owing"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
