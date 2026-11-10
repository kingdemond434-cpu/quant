"""FENCE: every published handoff on the chain carries a consistent unit, currency, vintage,
horizon, instrument identity and gross/net basis (ARCH-11).

The chain is research -> forecast -> allocator input -> gateway intent, and its surfaces are
`libs.research.handoff_contract.SURFACES`: the forecast register, every allocator input that
`allocator_liveness.inputs()` names, sleeves.json and the allocation.

WHAT IT FAILS:
  1. WIRING (portable, needs no desk state): an allocator input `allocator_liveness` names that
     no surface covers; a non-money producer whose source no longer calls the contract; a
     PENDING_MONEY_PATH list that grew past its ceiling or names an unknown surface.
  2. A STAMPED SURFACE with a missing or malformed field, an instrument the universe registry
     does not quote, or a vintage from the future.
  3. A NON-MONEY SURFACE WITH NO BLOCK, written after its producer's stamping code landed on
     this machine (the artifact is newer than the producer source by more than GRACE_S). Older
     than that, the artifact predates the code and reads UNMEASURED, never PASS.
  4. A PENDING (money-path) surface that is now fully stamped: it healed, so remove it (ratchet).
     While pending, the identities it carries are still checked against the registry, and a
     sleeves.json `risk_frac` outside [0, 1] -- a percent written where a fraction belongs --
     fails as a unit error.
  5. CROSS-HOP: one instrument's currency differs between surfaces; a quantity NET upstream is
     republished GROSS downstream; one instrument and unit change horizon bucket across stages.

An absent artifact is UNMEASURED and named, never a pass. Exit 1 on any failure, else 0; the
verdict is PASS only when every surface was measured.

    python scripts/check_handoff_contract.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import handoff_contract as HC  # noqa: E402

#: How long after its producer's source changed an artifact may still predate the stamp. One
#: daily producer cadence plus the hourly adoption slot.
GRACE_S = 26 * 3600


def _read(path: Path, layout: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None]:
    if layout == "jsonl_rows":
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
        return None, rows
    doc = json.loads(path.read_text("utf-8"))
    return (doc if isinstance(doc, dict) else {}), None


def allocator_inputs() -> list[str] | None:
    """The input names `allocator_liveness` publishes, or None when it cannot be imported."""
    try:
        for p in (str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
            if p not in sys.path:
                sys.path.insert(0, p)
        import allocator_liveness  # type: ignore[import-not-found]
        return [i.key for i in allocator_liveness.inputs()]
    except Exception:                                            # pragma: no cover - import guard
        return None


def wiring(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    names = {s.name for s in HC.SURFACES}
    for key in allocator_inputs() or []:
        if key not in names:
            problems.append(f"allocator input {key!r} is on no handoff surface: add it to "
                            "handoff_contract.SURFACES")
    for name in HC.PENDING_MONEY_PATH:
        s = next((x for x in HC.SURFACES if x.name == name), None)
        if s is None or not s.money_path:
            problems.append(f"PENDING_MONEY_PATH names {name!r}, which is not a money-path "
                            "surface: only producers the cloud may not edit may wait")
    if len(HC.PENDING_MONEY_PATH) > HC.PENDING_CEILING:
        problems.append(f"PENDING_MONEY_PATH grew to {len(HC.PENDING_MONEY_PATH)} > "
                        f"{HC.PENDING_CEILING}: the list only shrinks")
    for s in HC.SURFACES:
        if s.money_path:
            continue                     # judged on its data: pending, or healed and stamped
        try:
            src = (root / s.producer).read_text("utf-8")
        except OSError:
            problems.append(f"{s.name}: producer {s.producer} is missing")
            continue
        if "handoff_contract" not in src or f'"{s.stage}"' not in src:
            problems.append(f"{s.name}: producer {s.producer} does not stamp the handoff "
                            f"contract at stage {s.stage!r}")
    return problems


def _inferred_pending(s: HC.Surface, doc: dict[str, Any] | None,
                      uni: dict[str, Any]) -> list[str]:
    """What a pending sleeves.json row can already be held to without a block."""
    if s.path.endswith("sleeves.json") and doc is not None:
        rows = [r for r in doc.get("sleeves") or [] if isinstance(r, dict)]
        out = HC.identity_defects([r.get("symbol") for r in rows], uni)
        for r in rows:
            rf = r.get("risk_frac")
            if isinstance(rf, (int, float)) and not 0.0 <= float(rf) <= 1.0:
                out.append(f"{r.get('name')}: risk_frac {rf} is outside [0, 1] -- a percent "
                           "where a heat fraction belongs")
        return [f"{s.name}: {p}" for p in out]
    return []


def measure(root: Path = ROOT, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    uni = HC.universe(root / "desks" / "mt5" / "data" / "universe" / "universe.json")
    problems = wiring(root)
    surfaces: dict[str, dict[str, Any]] = {}
    decls: list[HC.Declaration] = []
    for s in HC.SURFACES:
        path = root / s.path
        pending = s.name in HC.PENDING_MONEY_PATH
        row: dict[str, Any] = {"stage": s.stage, "producer": s.producer, "pending": pending}
        surfaces[s.name] = row
        if not path.exists():
            row.update(status="UNMEASURED", why=f"{s.path} absent")
            continue
        try:
            doc, rows = _read(path, s.layout)
        except (OSError, ValueError) as exc:
            row.update(status="FAIL", why=f"unreadable: {type(exc).__name__}: {exc}")
            problems.append(f"{s.name}: {row['why']}")
            continue
        if rows is not None:
            blocks = [r.get(HC.KEY) for r in rows]
            n_total = len(rows)
        else:
            blocks = [(doc or {}).get(HC.KEY)]
            n_total = 1
        stamped = [b for b in blocks if isinstance(b, dict)]
        if rows is not None and n_total == 0:
            row.update(status="UNMEASURED", why=f"{s.path} holds no rows")
            continue
        own: list[str] = []
        if pending:
            own += _inferred_pending(s, doc, uni)
            if stamped and len(stamped) == n_total:
                own.append(f"{s.name}: listed in PENDING_MONEY_PATH but fully stamped -- remove "
                           "it (ratchet)")
        if not stamped and not pending:
            try:
                src_m = (root / s.producer).stat().st_mtime
                age = path.stat().st_mtime - src_m
            except OSError:
                age = 0.0
            if age > GRACE_S:
                own.append(f"{s.name}: written {age / 3600:.1f}h after its producer's stamping "
                           f"code landed, with no handoff block")
            else:
                row.update(status="UNMEASURED",
                           why="artifact predates the producer's stamping code")
                continue
        for b in stamped:
            for d in HC.field_defects(b, now=now):
                own.append(f"{s.name}: {d}")
        if rows is not None and not pending and len(stamped) < n_total and stamped:
            own.append(f"{s.name}: {n_total - len(stamped)} of {n_total} row(s) carry no "
                       "handoff block")
        ids: list[Any] = []
        if rows is not None:
            for r in rows:
                if isinstance(r.get(HC.KEY), dict):
                    ids += HC.instruments(r, r[HC.KEY])
        elif stamped:
            ids += HC.instruments(doc or {}, stamped[0])
        own += [f"{s.name}: {p}" for p in HC.identity_defects(ids, uni)]
        decls += HC.declarations(s, doc, rows)
        row["status"] = "FAIL" if own else ("PENDING" if pending and not stamped else "PASS")
        row["n_rows"] = n_total
        row["n_stamped"] = len(stamped)
        if own:
            row["problems"] = own[:20]
        problems += own
    hop = HC.cross_hop(decls, uni)
    problems += [f"cross-hop: {p}" for p in hop]
    unmeasured = sorted(k for k, v in surfaces.items() if v.get("status") == "UNMEASURED")
    if not uni:
        unmeasured.append("universe registry (instrument identities)")
    verdict = "FAIL" if problems else ("UNMEASURED" if unmeasured else "PASS")
    return {"verdict": verdict, "measured_at": now.isoformat(timespec="seconds"),
            "contract": HC.CONTRACT, "problems": problems, "unmeasured": unmeasured,
            "pending_money_path": sorted(HC.PENDING_MONEY_PATH), "surfaces": surfaces,
            "declarations": len(decls)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = measure()
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
    else:
        print(f"HANDOFF CONTRACT ({HC.CONTRACT}): {doc['verdict']} -- "
              f"{len(doc['surfaces'])} surface(s), {doc['declarations']} declaration(s), "
              f"pending money path {doc['pending_money_path']}")
        for p in doc["problems"]:
            print(f"  FAIL {p}")
        for u in doc["unmeasured"]:
            print(f"  UNMEASURED {u}")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
