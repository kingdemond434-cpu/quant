#!/usr/bin/env python3
"""MINER CONVERSION AND BREADTH -- what each miner actually converts, and what the book still lacks.

TWO QUESTIONS, ONE ANSWER (principal 2026-08-26, items 5 and 6). "Which miners earn their compute"
and "what independent breadth is missing" are the same question asked from opposite ends, because
a miner whose discoveries all become another session-range breakout has converted nothing: the
book already holds that bet, and N_eff does not move when you add a fifteenth copy of it.

WHAT IS MEASURED PER MINER, in the order a decision actually needs it:

  DISCOVERIES  raw rows produced -- the only number miners currently report, and the least useful
  NOVEL        rows whose MECHANISM is not already held. Deduplicated by economic exposure, not
               by title: two writeups calling the same asia-range breakout different names are
               one discovery, and counting them twice is how a desk mistakes volume for breadth
  TESTED       novel rows that actually reached a backtest -- the step where most corpora die
  SURVIVORS    tested rows that cleared the ten gates
  CONVERSION   survivors / discoveries; the only ratio that says whether the miner is earning
  ZERO-YIELD   a miner with discoveries but no survivor across the whole window: it is producing
               noise at cost, and under III.16 that is a defect to fix or retire, not a neutral

WHAT IS MEASURED FOR THE BOOK:

  FAMILY CONCENTRATION -- the share of certificates held by the single largest family. This desk
  is currently ~95% session_range_breakout, which is why N_eff collapses. The gap list is ordered
  by what would add the most INDEPENDENT bet, not by what is easiest to mine: carry, relative
  value, cross-asset residuals, volatility/liquidity transitions, event reactions, COT
  positioning, macro conditionality, execution-derived effects.

This file MEASURES and REPORTS. It does not retire miners on its own: killing a research line is
a decision with a cost, and the register plus the gap-wirer are where that decision belongs.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.repair_invoke import request_repair

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
INTEL = [DESK / "data" / "intelligence", ROOT / "data" / "intelligence"]
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
HYP = DESK / "data" / "hypotheses" / "external_backtest_results.json"
OUT = ROOT / "data" / "miner_conversion.json"
ALARM = ROOT / "data" / "MINER_YIELD_ALARM.txt"

WINDOW_DAYS = 14
#: Families that would each add a genuinely different bet, ordered by independence from a
#: session-range book rather than by how easy they are to mine.
#: Names must match the generator registry EXACTLY -- `volatility_transition` here versus
#: `vol_transition` there reported a family as having no generator when one existed, which turns a
#: naming slip into a fabricated acquisition task.
BREADTH_TARGETS = (
    ("carry", "swap/rollover differentials -- a return stream with no directional overlap"),
    ("relative_value", "cross-pair and triangle residuals -- profits when direction does not"),
    ("cross_asset_residual", "metals vs FX vs index residuals after the common factor"),
    ("vol_transition", "regime changes in realised vol -- fires when breakouts stall"),
    ("liquidity_regime", "spread/depth regime shifts -- an execution-derived edge"),
    ("event_reaction", "scheduled macro releases -- a different clock entirely"),
    ("cot_positioning", "COT/positioning extremes -- weekly, uncorrelated to intraday ranges"),
    ("macro_conditional", "rates/DXY conditionality -- changes WHEN other sleeves should fire"),
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _mechanism_key(row: dict) -> str:
    """Dedup key by ECONOMIC EXPOSURE, never by title.

    Two rows are the same discovery if they trade the same family on the same instrument in the
    same session, however differently they are described. Titles are the worst possible key: the
    corpus is full of the same mechanism renamed by each source that found it.
    """
    fam = str(row.get("family") or row.get("mechanism") or "unknown").casefold()
    sym = str(row.get("symbol") or row.get("sym") or "*").upper()
    ses = str(row.get("session") or row.get("window") or row.get("selector") or "*").casefold()
    return f"{fam}|{sym}|{ses}"


def miner_rows(cutoff: datetime) -> dict[str, list[dict]]:
    """Recent discovery rows per miner directory."""
    out: dict[str, list[dict]] = {}
    for base in INTEL:
        if not base.exists():
            continue
        for src in sorted(d for d in base.iterdir() if d.is_dir()):
            rows: list[dict] = []
            for f in list(src.glob("discoveries_*.json")) + list(src.glob("*.json")):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
                        continue
                except OSError:
                    continue
                data = _read(f)
                if isinstance(data, list):
                    rows.extend(r for r in data if isinstance(r, dict))
                elif isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            rows.extend(r for r in v if isinstance(r, dict))
            if rows:
                out.setdefault(src.name, []).extend(rows)
    return out


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=WINDOW_DAYS)

    certs = (_read(CERTS) or {}).get("survivors") or {}
    held = {_mechanism_key({"family": (c.get("shadow_spec") or {}).get("family"),
                            "symbol": (c.get("shadow_spec") or {}).get("symbol"),
                            "session": (c.get("shadow_spec") or {}).get("selector")})
            for c in certs.values()}
    fam_counts = Counter(str((c.get("shadow_spec") or {}).get("family") or "unknown")
                         for c in certs.values())

    tested = {_mechanism_key(r) for r in (_read(HYP) or []) if isinstance(r, dict)}
    survivor_keys = held

    per_miner: dict[str, dict] = {}
    zero_yield: list[str] = []
    for miner, rows in sorted(miner_rows(cutoff).items()):
        keys = [_mechanism_key(r) for r in rows]
        uniq = set(keys)
        novel = uniq - held
        per_miner[miner] = {
            "discoveries": len(rows),
            "distinct_mechanisms": len(uniq),
            "novel_mechanisms": len(novel),
            "reached_backtest": len(novel & tested),
            "survivors": len(uniq & survivor_keys),
            "conversion": round(len(uniq & survivor_keys) / len(rows), 4) if rows else None,
            "duplicate_rate": round(1 - len(uniq) / len(rows), 3) if rows else None,
        }
        if len(rows) >= 20 and not (uniq & survivor_keys):
            zero_yield.append(miner)

    total_certs = sum(fam_counts.values())
    top_family, top_n = (fam_counts.most_common(1) or [("none", 0)])[0]
    concentration = round(top_n / total_certs, 3) if total_certs else None
    # A family is now three states, not two, and the difference is what to DO about it:
    #   held        -- a certificate exists
    #   reachable   -- a generator exists and its input is present; it just has not certified yet
    #   unreachable -- no generator, or its input is not recorded (an ACQUISITION task, which is a
    #                  completely different piece of work from "nobody mined it")
    try:
        import sys as _sys
        _sys.path.insert(0, str(DESK))
        from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
    except Exception:
        ORTHOGONAL_FAMILIES, FAMILY_INPUTS = {}, {}
    missing = []
    for f, why in BREADTH_TARGETS:
        if any(f in k for k in held):
            continue
        needs = FAMILY_INPUTS.get(f, ("unknown", None))[0]
        missing.append({
            "family": f, "why": why,
            "state": "REACHABLE" if f in ORTHOGONAL_FAMILIES else "NO_GENERATOR",
            "needs": needs,
        })

    report = {
        "measured_at": now.isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "miners": per_miner,
        "zero_yield_miners": zero_yield,
        "book_breadth": {
            "certificates": total_certs,
            "families": dict(fam_counts),
            "largest_family": top_family,
            "family_concentration": concentration,
            "missing_families": missing,
            "why": ("concentration is the share of certificates in the single largest family. "
                    "Near 1.0 means every certificate is the same bet, and no amount of mining "
                    "inside that family raises the book's effective independent bets."),
        },
        "note": ("Deduplication is by economic exposure (family|symbol|session), never by title: "
                 "the corpus renames the same mechanism per source, and counting those as "
                 "separate discoveries mistakes volume for breadth."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")

    print(f"miner conversion: {len(per_miner)} miner(s) with rows in {WINDOW_DAYS}d; "
          f"{len(zero_yield)} zero-yield")
    print(f"book breadth: {total_certs} certificate(s), largest family '{top_family}' "
          f"= {concentration} of the book; {len(missing)} target family(ies) absent")
    for row in missing[:8]:
        print(f"   {row['state']:12} {row['family']:22} needs: {row['needs']}")

    findings = []
    if concentration is not None and concentration > 0.8:
        findings.append(f"BREADTH: {concentration:.0%} of certificates are '{top_family}' -- the "
                        f"book is close to one bet; mining more of it cannot raise N_eff")
    if zero_yield:
        findings.append(f"ZERO-YIELD: {', '.join(zero_yield[:6])} produced 20+ rows and no "
                        f"survivor in {WINDOW_DAYS}d -- noise at cost (III.16)")
    if findings:
        ALARM.write_text("MINER/BREADTH " + now.isoformat(timespec="seconds") + "\n\n"
                         + "\n".join(f"  - {f}" for f in findings) + "\n", "utf-8")
        print("\n" + "\n".join(f"  - {f}" for f in findings))
        request_repair("miner-conversion breach")
        return 1
    if ALARM.exists():
        ALARM.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
