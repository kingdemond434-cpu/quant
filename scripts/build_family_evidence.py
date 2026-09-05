"""Pool each mechanism's forward panel, so twelve instruments stop being counted as one.

WHY THIS EXISTS (principal, 2026-08-29: "n >= 50 is throughput-bound, not calendar-bound")

Measured the same day: forward sleeves accrue about 8 trades per 12 days. Against a 20-trade
floor that is a month per sleeve and against 50 it is three months -- while the 14-day calendar
floor was already nearly satisfied. The desk was not waiting for time. It was waiting for ONE
instrument to produce evidence that TWELVE instruments were producing in parallel and discarding,
because every sleeve counted only its own fills.

`overnight_gap_decay` runs on 12 distinct symbols. Pooled, its panel reaches 20 observations in
under two days rather than a month. That is the whole speedup and it costs nothing in rigour --
provided the pooled count is honest about what is actually independent, which is the hard part.

WHY NAIVE POOLING WOULD BE FRAUD. `session_range_breakout` also shows 15 sleeves -- across 5
symbols. Most are rr-variants of the same symbol and session: the same trade exited at three
targets. Summing them claims 15x the evidence for something nearer 5x, and would certify a
mechanism on its own reflections. Two families identical in a sleeve count, completely different
as panels. The cluster is therefore (symbol, date): a fresh observation needs a different
instrument OR a different day, so three rr-variants of EURUSD on one day collapse to one.

THE BAR DOES NOT MOVE. Pooled evidence faces the identical thresholds a single sleeve faces --
14 days, 50 trades or 20 with an always-valid significant bound, and 20 EFFECTIVE observations,
all from `forward_verdict`. Nothing here is a lower standard; it is the same standard applied to
evidence the desk already had and was throwing away.

IT PUBLISHES, IT DOES NOT PROMOTE. A family verdict is written to an artifact and never to a
sleeve's status. Opening a new promotion path is a money-path decision with the same standing as
a gate threshold, and a script that quietly granted one every twenty minutes would make the
book's composition unauditable. `member_inherits` records WHICH members would qualify and why;
acting on that is the promoter's job, under the principal's rules.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
SHADOW = DESK / "reports" / "shadow"
OUT = SHADOW / "FAMILY_EVIDENCE.json"

sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))

#: Ledger rows carry `phase`; only forward observations count. A selection-era fill pooled into a
#: forward panel is exactly the contamination the two-stage law exists to prevent, and it is
#: easier to make this mistake at the family level because no single sleeve looks wrong.
_FORWARD_PHASES = ("forward", None)


def _registry_identities() -> dict[str, dict]:
    """Authoritative (symbol, family, selector) per sleeve, from the frozen identity registry.

    NEVER PARSE THE LEDGER FILENAME. A first version derived the family from
    `ledger_<sym>_<fam>_<win>.json` by splitting on '_' and taking the middle, which turned
    `ledger_CADJPY_fair_value_gap.json` into a family called `fair_value` and produced a census of
    mechanisms named `asia_FAILED`, `london`, `level` and `session_range`. Family names contain
    underscores and the two-branch filename convention has no delimiter that survives them.

    `sleeve_registry.json` records `identity.family` because identity ambiguity is the exact
    disease it was built to cure. Reading it is both correct and the point of its existing.
    """
    try:
        reg = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict] = {}
    for key, row in (reg.get("sleeves") or {}).items():
        ident = (row or {}).get("identity") or {}
        fam, sym = ident.get("family"), ident.get("symbol")
        if fam and sym:
            out[key] = {"family": str(fam), "symbol": str(sym),
                        "selector": str(ident.get("selector") or "")}
    return out


def _ledger_for(sym: str, fam: str, selector: str) -> Path | None:
    """The engine's own two-branch ledger path for this identity.

    `shadow_forward` writes `ledger_<sym>_<win>.json` for session_range_breakout and
    `ledger_<sym>_<fam>_<win>.json` for everything else. Reproducing that rule FORWARD from a
    recorded identity is safe; inferring it backward from a filename is not.
    """
    cand = [SHADOW / (f"ledger_{sym}_{selector}.json" if fam == "session_range_breakout"
                      else f"ledger_{sym}_{fam}_{selector}.json")]
    # Older rows were written before the family was carried in the name.
    cand.append(SHADOW / f"ledger_{sym}_{fam}.json")
    cand.append(SHADOW / f"ledger_{sym}_{selector}.json")
    return next((c for c in cand if c.exists()), None)


def _forward_trades(path: Path) -> list[tuple[str, float]]:
    """Forward-phase (entry_time, r_multiple) rows only.

    A selection-era fill pooled into a forward panel is exactly the contamination the two-stage
    law prevents, and it is EASIER to make that mistake at family level because no single sleeve
    looks wrong afterwards.
    """
    try:
        rows = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(rows, dict):
        rows = rows.get("trades") or []
    if not isinstance(rows, list):
        return []
    out: list[tuple[str, float]] = []
    for r in rows:
        if not isinstance(r, dict) or r.get("phase") not in _FORWARD_PHASES:
            continue
        t, rm = r.get("entry_time"), r.get("r_multiple")
        if t is None or rm is None:
            continue
        try:
            out.append((str(t), float(rm)))
        except (TypeError, ValueError):
            continue
    return out


def main() -> int:
    import family_evidence as fe
    import forward_verdict as fv

    now = datetime.now(tz=UTC)
    identities = _registry_identities()
    if not identities:
        print("  sleeve_registry.json unreadable or empty -- refusing to guess families from "
              "filenames (that produced mechanisms called 'asia_FAILED' and 'level'). No panel.")
        return 1

    fams: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(dict)
    unmatched = 0
    for key, ident in identities.items():
        path = _ledger_for(ident["symbol"], ident["family"], ident["selector"])
        if path is None:
            unmatched += 1
            continue
        trades = _forward_trades(path)
        if not trades:
            continue
        # `pool` reads the instrument off the leading component of the member key, so the key
        # must start with the symbol -- see family_evidence.pool.
        fams[ident["family"]][f"{ident['symbol']}.{key}"] = trades
    if unmatched:
        print(f"  {unmatched} registered sleeve(s) have no ledger on this box -- counted as "
              f"absent, never as zero trades")

    report: dict = {"built_at": now.isoformat(timespec="seconds"),
                    "rule": "family_evidence/2026-08-29", "families": {}}

    print(f"FAMILY EVIDENCE {now.isoformat(timespec='seconds')}")
    print(f"  {'family':26s} {'memb':>5s} {'syms':>5s} {'pooled_n':>9s} {'n_eff':>7s}  verdict")

    for fam, members in sorted(fams.items()):
        # The panel has been observed as long as its LONGEST-running member; taking the newest
        # would restart the family clock every time an instrument joined.
        days = 0
        for trades in members.values():
            if trades:
                try:
                    first = datetime.fromisoformat(trades[0][0].replace("Z", "+00:00"))
                    if not first.tzinfo:
                        first = first.replace(tzinfo=UTC)
                    days = max(days, (now - first).days)
                except ValueError:
                    continue

        v = fe.family_verdict(members, days)
        pooled = fe.pool(members)
        inherits: dict[str, str] = {}
        for key, own in pooled["per_member"].items():
            ok, why = fe.member_inherits(own, v, pooled["rs"])
            if ok:
                inherits[key] = why

        report["families"][fam] = {**v, "days_active": days,
                                   "members_qualifying": inherits,
                                   "n_members_qualifying": len(inherits)}
        mark = "PROMOTE-ELIGIBLE" if v["promote"] else v["reason"][:58]
        print(f"  {fam:26s} {v['n_members']:5d} {v['n_symbols']:5d} {v['n']:9d} "
              f"{v['n_eff']:7.1f}  {mark}")
        if v["promote"]:
            print(f"      {len(inherits)}/{v['n_members']} member(s) would inherit this verdict; "
                  f"promotion remains the promoter's decision, not this script's")

    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    ready = [f for f, r in report["families"].items() if r.get("promote")]
    print(f"\n  families with a pooled verdict: {len(ready)} of {len(report['families'])}")
    print(f"  bar applied: {fv.VERDICT_MIN_DAYS}d AND ({fv.VERDICT_MIN_TRADES} trades OR "
          f"{fv.SEQ_MIN_TRADES} significant), n_eff >= {fv.MIN_EFFECTIVE_N} -- identical to the "
          f"per-sleeve bar")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
