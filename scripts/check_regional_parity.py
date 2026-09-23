"""REGIONAL PARITY, MEASURED -- no region absent, every region at the same depth.

    python scripts/check_regional_parity.py             # measure, write the report, print
    python scripts/check_regional_parity.py --json      # the report on stdout
    python scripts/check_regional_parity.py --strict    # also fail on a flagged region

THE LAW (docs/LAWS.md 5n, principal 2026-09-19). Every world region receives the same depth of
civilization -- the ten source layers in the native language, its own mechanics, its own
calendars, its own rule states, its own transmission map -- and compute is NOT equal: it follows

    Priority = P(useful) x Orthogonality x InformationGain x CoverageDebt
               / (Compute + DataCost + TrialBurden)

so that the coverage-debt bonus keeps neglected regions discovering while the expected-value
terms keep low-information ground from eating the hour.

WHAT THIS FENCE ASSERTS, AND THE ONE THING IT REFUSES TO DO. It asserts exactly ONE condition:
**no region is absent.** A regional forest with no resolvable country pack and no dedicated
region package is a hole in the federation, and that is a hard failure. Everything else --
depth below the median, a dead resident, an empty trailing window, an empty lattice -- is
REPORTED with its number and never fails the commit gate, because those four are LIVE STATE and
a clean checkout has none of it: a gate that cries wolf on every pull request is a gate somebody
switches off, which is how enforcement dies (L1.43).

**IT NEVER CAPS COMPUTE.** The priority this script computes is published for the research-ROI
organ to fold into `forest_allocation.json` as a BONUS on the neglected; nothing here subtracts
a worker, a second or a trial from anybody. That is deliberate and it is the growth law (Rule 1,
`docs/GROWTH_GOVERNANCE.md`): a mechanism that reduces research is a mechanism that owes a proof
that it raises robust forward E[log W], and a parity fence has no such proof to offer. The
artifact therefore carries `caps_compute: false` as a machine-readable promise, and
`tests/research/test_regional_parity.py` pins it so a later session cannot quietly turn this
into a throttle.

UNMEASURED IS A VALUE (L1.28a). The registry may not open on this machine; the forest reports
directory may not exist in a fresh clone. Every such term reads UNMEASURED by name and holds the
MIDDLE of its factor, never zero and never the best, and the region is flagged only on a
MEASURED absence.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: The country packs import as `research.countries.<code>.pack`, which needs the desk on the
#: path -- the same three entries `country_lab._load_pack_file` inserts when it resolves one.
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "regional_parity.json"
#: The one flag that fails this fence. The other four in `RP.FLAGS` are live state and are
#: reported; `--strict` promotes them for the hourly box gate, where the state is real.
FATAL_FLAG = "NO_PACK"

#: PACK DIRECTORY -> ISO-2, where the two differ. This is not a guess: `libs/research/forests.py`
#: documents the convention in its own words ("`<code>` is the pack DIRECTORY name, which is not
#: always ISO-2 -- India is `ind`, Indonesia `idn`, the euro area `ea`"). A pack covering more
#: than one jurisdiction declares them itself in a module-level `JURISDICTIONS` tuple and is
#: credited with every one; nothing is inferred from a pack's prose.
PACK_ALIASES: dict[str, tuple[str, ...]] = {"ind": ("in",), "idn": ("id",), "uk": ("gb",)}
#: Where a multi-jurisdiction pack declares what it answers for.
JURISDICTIONS_ATTR = "JURISDICTIONS"


def jurisdictions_of(code: str) -> tuple[tuple[str, ...], str]:
    """Which ISO-2 countries a pack answers for, and HOW that was established.

    Read in one order and never guessed: the pack's own `JURISDICTIONS` tuple, then the documented
    directory aliases, then the directory code itself. A multi-country pack that declares nothing
    is credited with ONE country -- which is the honest reading, and the reason the coverage block
    below can name a real, closable gap ("the euro-area pack covers eleven members and declares
    none of them") instead of either crediting it with everything or calling it missing.
    """
    try:
        mod = importlib.import_module(f"research.countries.{code}.pack")
    except Exception:
        mod = None
    declared = getattr(mod, JURISDICTIONS_ATTR, None) if mod is not None else None
    if isinstance(declared, (list, tuple)) and declared:
        return tuple(str(c).lower() for c in declared), f"{code}/pack.py {JURISDICTIONS_ATTR}"
    if code in PACK_ALIASES:
        return PACK_ALIASES[code], f"pack-directory alias for {code!r}"
    return (code.lower(),), "the pack directory name"


def country_coverage() -> dict[str, Any]:
    """Every country the desk's own machinery NAMES, and which pack answers for it.

    THE PRINCIPAL'S ADDITION (2026-09-22): a pack for every ROI country and region the desk's own
    machinery names. `libs/research/forests.py` is that machinery's roster -- each forest lists the
    countries it covers -- so this reads the roster rather than a list somebody typed here, and a
    country added to a forest tomorrow shows up as UNANSWERED the same hour.

    IT REPORTS AND DOES NOT FAIL. An unanswered country is work, not a breach: the fence's single
    hard assertion stays "no region absent". Failing on this would turn every honest expansion of a
    forest's roster into a red gate, which is how a roster stops being expanded.
    """
    answered: dict[str, list[str]] = {}
    how: dict[str, str] = {}
    for code in sorted({p for f in F.FORESTS.values() for p in f.packs}):
        iso, why = jurisdictions_of(code)
        how[code] = why
        for c in iso:
            answered.setdefault(c, []).append(code)
    named = sorted({c.lower() for f in F.FORESTS.values() for c in f.countries})
    packaged = {c.lower() for f in F.FORESTS.values() if f.package for c in f.countries}
    rows: dict[str, Any] = {}
    for c in named:
        packs = answered.get(c, [])
        rows[c] = {"packs": packs,
                   "answered_by": ("pack" if packs else "package" if c in packaged else None)}
    unanswered = sorted(c for c, r in rows.items() if r["answered_by"] is None)
    undeclared = sorted(code for code, why in how.items() if why == "the pack directory name"
                        and len(jurisdictions_of(code)[0]) == 1
                        and code not in set(named))
    return {
        "order": ("principal 2026-09-22: a pack for every ROI country and region the desk's own "
                  "machinery names"),
        "roster": "libs/research/forests.py Forest.countries",
        "n_named": len(named), "n_answered": len(named) - len(unanswered),
        "unanswered": unanswered,
        "packs_declaring_jurisdictions": sorted(c for c, w in how.items()
                                                if w.endswith(JURISDICTIONS_ATTR)),
        "multi_country_packs_declaring_none": undeclared,
        "how": how, "by_country": rows,
        "why_not_fatal": ("an unanswered country is work, not a breach; the fence's one hard "
                          "assertion is NO REGION ABSENT. A multi-jurisdiction pack that covers a "
                          "country without declaring it reads as a gap here on purpose -- the fix "
                          f"is one {JURISDICTIONS_ATTR} tuple in that pack, and naming it is how "
                          "it gets written"),
    }


def _connect() -> sqlite3.Connection | None:
    """The moat registry, or None with the reason left to the caller. A machine with no
    registry measures depth and reports the live half UNMEASURED -- it does not fail."""
    try:
        from libs.moat import registry as R
    except Exception:
        return None
    try:
        return R.connect()
    except Exception:
        return None


#: The research-ROI organ's report and the block inside it that carries ROI_region. Read by
#: PATH AND KEY, because the two are the difference between a measured P(useful) and every
#: region silently holding the middle: an early draft of this fence read a file that does not
#: exist (`data/research_roi.json`) under a key that does not exist (`regions.by_region`), and
#: the fence still printed a complete-looking table -- with `p_useful` UNMEASURED on all
#: seventeen and the upstream measurement thrown away. A wrong path here does not error.
ROI_REPORT: Path = DESK / "reports" / "RESEARCH_ROI.json"
ROI_BLOCK = "region_roi"


def _roi_by_region() -> tuple[dict[str, float | None], str]:
    """P(useful) per forest from the research-ROI organ's own artifact, when it has run.

    A region whose `roi_status` is UNMEASURED reads None here and holds the middle by name in
    `parity_report`; a MEASURED zero is a zero. The two are not the same and the organ already
    tells them apart, so this reads its verdict rather than re-deriving one.
    """
    try:
        doc = json.loads(ROI_REPORT.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}, f"{RP.UNMEASURED}: {ROI_REPORT.name} is absent or unreadable"
    block = doc.get(ROI_BLOCK) if isinstance(doc, dict) else None
    per = (block or {}).get("by_region") or {} if isinstance(block, dict) else {}
    out: dict[str, float | None] = {}
    measured = 0
    for fid, row in per.items():
        if not isinstance(row, dict):
            continue
        val = row.get("roi")
        ok = (isinstance(val, (int, float))
              and str(row.get("roi_status") or "") != RP.UNMEASURED)
        out[str(fid)] = float(val) if isinstance(val, (int, float)) and ok else None
        measured += int(ok)
    if not per:
        return {}, (f"{RP.UNMEASURED}: {ROI_REPORT.name} carries no {ROI_BLOCK}.by_region -- "
                    f"every P(useful) holds the middle")
    return out, f"{ROI_REPORT.name} {ROI_BLOCK}.by_region: {measured} of {len(per)} MEASURED"


def measure(*, conn: sqlite3.Connection | None = None, now: datetime | None = None,
            reports_dir: Path | None = None) -> dict[str, Any]:
    """The parity report plus this fence's own verdict. Pure apart from the two reads."""
    roi, roi_why = _roi_by_region()
    doc = RP.parity_report(conn=conn, now=now, region_roi=roi or None,
                           reports_dir=reports_dir)
    rows = doc["regions"]
    declared = set(F.FORESTS)
    seen = set(rows)
    missing_from_report = sorted(declared - seen)
    absent = sorted(fid for fid, r in rows.items() if FATAL_FLAG in (r.get("flags") or ()))
    doc["country_coverage"] = country_coverage()
    doc["fence"] = {
        "law": "docs/LAWS.md 5n",
        "asserts": ("no region absent: every regional forest resolves a country pack or runs a "
                    "dedicated region package"),
        "caps_compute": False,
        "why_no_cap": ("the priority is published as a BONUS for research_roi.forest_allocation "
                       "to fold in; this fence subtracts no worker, second or trial from any "
                       "region (GROWTH_GOVERNANCE Rule 1)"),
        "regions_declared": len(declared),
        "regions_measured": len(seen),
        "missing_from_report": missing_from_report,
        "absent_regions": absent,
        "roi_source": roi_why or "desks/mt5/data/research_roi.json regions.by_region",
        "registry": "open" if conn is not None else
                    f"{RP.UNMEASURED}: no moat registry on this machine",
        "countries_named": doc["country_coverage"]["n_named"],
        "countries_unanswered": doc["country_coverage"]["unanswered"],
    }
    return doc


def _line(fid: str, row: dict[str, Any]) -> str:
    depth = row.get("depth_score")
    debt = (row.get("coverage_debt") or {}).get("debt")
    flags = ",".join(row.get("flags") or ()) or "-"
    return (f"  {fid:<22} {row.get('kind', '?'):<9} "
            f"depth={'UNMEASURED' if depth is None else f'{depth:.3f}'!s:>10} "
            f"debt={'?' if debt is None else f'{debt:.3f}'!s:>6} "
            f"prio={row.get('priority', 0.0):.4f} x{row.get('priority_factor', 1.0):.2f} "
            f"{flags}")


def render(doc: dict[str, Any]) -> str:
    fence = doc["fence"]
    out = [f"regional parity @ {doc['at']} -- {fence['regions_measured']} of "
           f"{fence['regions_declared']} forests measured, median depth "
           f"{doc.get('median_depth')}",
           f"  registry: {fence['registry']}; caps compute: {fence['caps_compute']}"]
    for fid, row in doc["regions"].items():
        out.append(_line(fid, row))
    counts = ", ".join(f"{k}={v}" for k, v in doc["flag_counts"].items())
    out.append(f"  flags: {counts}")
    cov = doc.get("country_coverage") or {}
    if cov:
        out.append(f"  countries: {cov['n_answered']}/{cov['n_named']} answered by a pack"
                   + (f"; UNANSWERED {cov['unanswered']}" if cov["unanswered"] else ""))
        if cov["multi_country_packs_declaring_none"]:
            out.append(f"  packs covering more than one jurisdiction and declaring none: "
                       f"{cov['multi_country_packs_declaring_none']}")
    if fence["absent_regions"]:
        out.append(f"  FAIL: region(s) absent from the federation: {fence['absent_regions']}")
    if fence["missing_from_report"]:
        out.append(f"  FAIL: forest(s) the report never reached: {fence['missing_from_report']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--strict", action="store_true",
                    help="also fail on a live-state flag (the hourly box gate, never CI)")
    ap.add_argument("--out", type=Path, default=REPORT)
    args = ap.parse_args(argv)

    conn = _connect()
    try:
        doc = measure(conn=conn, now=datetime.now(tz=UTC))
    finally:
        if conn is not None:
            conn.close()
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:                       # a read-only tree still gets a verdict
        doc["fence"]["report_write"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    fence = doc["fence"]
    if fence["absent_regions"] or fence["missing_from_report"]:
        return 1
    if args.strict and doc["flagged"]:
        print(f"  --strict: flagged regions {doc['flagged']}")
        return 1
    return 0


if __name__ == "__main__":                       # pragma: no cover
    raise SystemExit(main())
