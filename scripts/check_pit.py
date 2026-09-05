#!/usr/bin/env python3
"""Generated truth about point-in-time provenance: what fraction of ingested rows carry it.

    python scripts/check_pit.py                 # the gate: census, write reports/PIT_CENSUS.json
    python scripts/check_pit.py --init          # seal the first baseline from this census, once
    python scripts/check_pit.py --floor 0.10    # ALSO exit 1 below 0.10 (never lowers the mark)

The doctrine names the fields; this measures them. Per source, so the sources whose ingestor
has not been moved onto `libs.data.pit.stamp` are listed by name rather than averaged away.
The floor RATCHETS: the high-water mark is stored and the check refuses a regression, exactly as
the bar-history floor does.

THE MARK IS COMMITTED, OR THERE IS NO RATCHET (audit 2026-09-05). The high-water file was never
committed and a missing one was read as 0.0, so every fresh CI runner measured against zero, wrote
a mark that died with the runner, and passed. A ratchet whose memory lives on a disposable host
starts from nothing every time. Now an absent or unreadable baseline FAILS the run naming the file
and the one command that creates it; `--init` seals the baseline from a real census, refuses to
overwrite, and records the population it was measured over -- because a stamped fraction is only
comparable against the rows that produced it.

A CENSUS OVER NOTHING IS NOT A READING. Zero rows used to fold into `stamped_frac or 0.0` and
be compared like a measurement. It is neither a pass nor a zero (L1.28a): it fails by name, and
`--init` will not seal from it.

MEASURED AT SEALING, 2026-09-05: 4,768 rows across 43 sources, 0 stamped. The mark starts at
0.0 because that is what the tree holds -- `proposer_common.donate` stamps rows at the proposer,
and none of the discovery files under `desks/mt5/data/intelligence` have been written through it
yet. The number is real and dated, which is the whole difference from the absent file it
replaces: the first stamped row will raise it, and nothing can lower it back.

WHY IT WAS ZERO, AND WHAT CHANGED (2026-09-05). `donate` applied the stamp inside a bare
`try/except: pass`, so a donation that could not be stamped was written anyway and read
downstream as if it had been. The stamp is now REQUIRED: an unstampable candidate is refused at
the door and counted (`counts.refused_unstamped` on the contract file). Every discovery file
written from here carries stamps, so the fraction rises as the intelligence tree turns over --
by the ratchet's own arithmetic, never by an edit to the mark.

THE SECOND CENSUS: CERTIFICATES. Rows carry stamps; DATASETS carry certificates
(`libs.data.pit_certificate`), and "no certificate -> no promotion authority" needs a published
count of who has one. This check now also reports, per dataset, whether all seven adversarial
checks passed, and names the ones that did not. It is a CENSUS, not a second gate: the exit code
still belongs to the stamped-fraction ratchet alone, so this cannot loosen -- or tighten by
accident -- the mark that already exists.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.data.pit import census  # noqa: E402
from libs.data.pit_certificate import CERT_DIR  # noqa: E402
from libs.data.pit_certificate import census as cert_census  # noqa: E402

INTEL = ROOT / "desks" / "mt5" / "data" / "intelligence"
OUT = ROOT / "desks" / "mt5" / "reports" / "PIT_CENSUS.json"
HIGH_WATER = ROOT / "desks" / "mt5" / "data" / "pit_high_water.json"
CERTIFICATES = CERT_DIR
INIT_COMMAND = "python scripts/check_pit.py --init"


def _rows(path: Path) -> list[Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        rows = d.get("discoveries") or d.get("rows") or []
        return rows if isinstance(rows, list) else []
    return []


def run() -> dict[str, Any]:
    """The census: newest three discovery files per source, stamped fraction per source and in
    total. Written to OUT (gitignored: a generated report, not a record)."""
    per_source: dict[str, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []
    for src_dir in sorted(p for p in INTEL.iterdir() if p.is_dir()) if INTEL.exists() else []:
        files = sorted(glob.glob(str(src_dir / "discoveries_*.json")))[-3:]
        rows = [r for f in files for r in _rows(Path(f)) if isinstance(r, dict)]
        if not rows:
            continue
        per_source[src_dir.name] = census(rows)
        all_rows.extend(rows)
    total = census(all_rows)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "total": total,
           "per_source": per_source,
           "unstamped_sources": sorted(s for s, c in per_source.items()
                                       if (c["stamped_frac"] or 0.0) < 0.5),
           # THE DATASET HALF. A stamped row says when the desk could have known it; a certificate
           # says whether the DATASET it came from survived the seven adversarial questions. Both
           # are published here because a pipeline can be perfect at one and empty at the other.
           "certificates": cert_census(CERTIFICATES)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def read_baseline(path: Path) -> dict[str, Any]:
    """The committed mark. Raises rather than defaulting -- FileNotFoundError when absent,
    ValueError when it is not a record carrying `stamped_frac` -- because 0.0-by-default was
    the defect."""
    doc = json.loads(path.read_text("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("stamped_frac"), int | float):
        raise ValueError(f"{path} is not a PIT high-water record (no numeric `stamped_frac`)")
    return doc


def _record(doc: dict[str, Any], *, sealed_at: str, when: str) -> dict[str, Any]:
    """The baseline shape: the fraction, the population it was measured over, and where the
    census that produced it was written. `stamped_frac` keeps its name so the record stays
    readable by anything that read the old file."""
    total = doc["total"]
    return {
        "_": (
            "HIGH-WATER MARK for the point-in-time stamped fraction of ingested discovery rows. "
            "Sealed once by --init, raised by the gate whenever a census measures higher, NEVER "
            "lowered by code. A missing file is a CI failure, not a zero."
        ),
        "sealed_at": sealed_at,
        "measured_at": when,
        "stamped_frac": float(total["stamped_frac"]),
        "rows": int(total["rows"]),
        "stamped": int(total["stamped"]),
        "sources": len(doc["per_source"]),
        "field_frac": total.get("field_frac", {}),
        "report": str(OUT.relative_to(ROOT)) if OUT.is_relative_to(ROOT) else str(OUT),
        "census_generated_utc": doc["generated_utc"],
        "command": "python scripts/check_pit.py",
    }


def _write(path: Path, rec: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1) + "\n", "utf-8")


def print_certificates(doc: dict[str, Any]) -> None:
    """The dataset census, named rather than averaged. NOT part of the exit code: this reports
    what has been certified, and the ratchet that can fail the run is the stamped fraction."""
    c = doc.get("certificates") or {}
    n = int(c.get("certificates") or 0)
    if not n:
        print(f"PIT certificates: NONE under {c.get('dir')}. Every dataset therefore has no "
              "promotion authority -- that is the rule, not a gap in the count.")
        return
    frac = c.get("authority_frac")
    print(f"PIT certificates: {c.get('with_authority')} of {n} carry authority"
          + (f" ({frac:.0%})" if isinstance(frac, float) else "")
          + f"; {c.get('without_authority')} do not")
    for ds in list(c.get("datasets_without_authority") or [])[:20]:
        blocking = ", ".join((c.get("blocking_check") or {}).get(ds) or []) or "?"
        print(f"  no authority: {ds}  (blocked on {blocking})")
    for name in list(c.get("unreadable") or [])[:10]:
        print(f"  UNREADABLE certificate: {name} -- an unreadable certificate is not a "
              "certificate")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--floor", type=float, default=None,
                    help="an explicit minimum on top of the high-water mark; the effective floor "
                         "is the HIGHER of the two, so this can tighten but never loosen")
    ap.add_argument("--baseline", default=None,
                    help=f"high-water record (default {HIGH_WATER.relative_to(ROOT)})")
    ap.add_argument("--init", action="store_true",
                    help="SEAL the baseline from this census. Refuses if one exists.")
    a = ap.parse_args(argv)
    baseline_path = Path(a.baseline) if a.baseline else HIGH_WATER

    doc = run()
    rows = int(doc["total"]["rows"])
    if rows == 0:
        print(f"PIT census UNMEASURED: no discovery rows under {INTEL}. That is not a pass and "
              "not a zero -- nothing was counted, so nothing can be compared or sealed.")
        print_certificates(doc)
        return 1
    frac = float(doc["total"]["stamped_frac"])

    if a.init:
        if baseline_path.exists():
            print(f"REFUSING --init: {baseline_path} already exists. The gate raises it by itself "
                  "on every higher census; the only way down is a human editing the file with a "
                  "reason, never a re-seal.")
            return 1
        when = datetime.now(tz=UTC).isoformat()
        rec = _record(doc, sealed_at=when, when=when)
        _write(baseline_path, rec)
        print(f"sealed {baseline_path}: stamped {frac:.1%} of {rows} rows across "
              f"{rec['sources']} sources (census {doc['generated_utc']}). Commit it.")
        return 0

    try:
        baseline = read_baseline(baseline_path)
    except FileNotFoundError:
        print(f"NO BASELINE: {baseline_path} is absent. A ratchet with nothing to ratchet against "
              "is not a ratchet, and a zero floor is not a floor -- this used to pass silently. "
              f"Seal one deliberately from a real census and commit it:\n  {INIT_COMMAND}")
        return 1
    except (OSError, ValueError) as exc:
        print(f"BASELINE UNREADABLE: {baseline_path} ({exc}). Not defaulting to zero; repair the "
              "file by hand from git history rather than re-sealing.")
        return 1

    hw = float(baseline["stamped_frac"])
    floor = max(hw, a.floor) if a.floor is not None else hw
    print(f"PIT census: {rows} rows across {len(doc['per_source'])} sources; "
          f"stamped {frac:.1%} (high-water {hw:.1%} sealed {baseline.get('sealed_at', '?')}, "
          f"floor {floor:.1%})")
    for s in doc["unstamped_sources"][:20]:
        print(f"  unstamped: {s}  ({doc['per_source'][s]['stamped_frac']:.0%})")
    print_certificates(doc)
    if frac > hw:
        # THE MARK ONLY RISES; the provenance moves with it so the file always names the census
        # that earned its number, and `sealed_at` stays the day the ratchet was first armed.
        rec = _record(doc, sealed_at=str(baseline.get("sealed_at", "")),
                      when=datetime.now(tz=UTC).isoformat())
        _write(baseline_path, rec)
        print(f"  high-water raised {hw:.1%} -> {frac:.1%} in {baseline_path} (commit it)")
    if frac + 1e-9 < floor:
        print(f"PIT REGRESSION: stamped fraction {frac:.1%} below floor {floor:.1%}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
