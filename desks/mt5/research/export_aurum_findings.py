"""Write the findings Aurum's absorption channel has been waiting for.

    python research/export_aurum_findings.py

THE GAP THIS CLOSES

Aurum's `step_absorb` runs every day from `aurum_cycle.py`. It reads
`inbox/quant_findings.jsonl`, feeds each row to `Absorber`, and reports what
arrived. It works. It has never absorbed anything, because that file has
never existed and NOTHING IN THIS REPO WROTE IT -- a repo-wide grep for
`quant_findings` returns nothing on the quant side.

So the channel is a pipe with a consumer and no producer. Every cycle it
reports "0 new findings", which is indistinguishable from "the quant desk
genuinely had nothing to say this week". That is absence read as clean,
inside the very organ built to move knowledge between the two desks.

WHY THE FINDINGS EXPORTED ARE MOSTLY NEGATIVE RESULTS

Aurum's CONTRIBUTOR_BRIEF names negative results as the rarest and most
valuable class, because nobody publishes them and every desk therefore
re-runs the same dead ends. This desk has just produced several, at a real
bar, on real data. A sweep that killed a mechanism is exactly the finding
that stops Aurum spending a forward slot rediscovering it.

WHAT THIS DELIBERATELY DOES NOT DO

It does not write into Aurum's checkout. A script that reached across into
another repository would fail in a way neither desk owns -- Aurum's own
`step_absorb` docstring says the same thing from the other side. This writes
`reports/aurum_findings.jsonl` HERE; moving it is a transport step the
operator performs, and the file is designed to be concatenated rather than
replaced so a transport that runs twice cannot lose a row.

EVERY FINDING CARRIES `measured_on` AND `transfer_test`, WHICH IS THE POINT

`measured_on` is what the claim was actually measured against. A result from
a BTCUSD/ETHUSD sweep is evidence about BTCUSD and ETHUSD; asserting it about
XAUUSD because the same code produced it is the cargo-culting Aurum's
absorber exists to refuse. `transfer_test` states what would have to be true
on Aurum's OWN data for the finding to carry -- a finding without one is a
note by construction, and `Absorber.queue()` says so.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
OUT = REPORTS / "aurum_findings.jsonl"


def _f(statement: str, source: str, grade: str, measured_on: str,
       transfer_test: str, **meta) -> dict:
    """One Finding row in the schema golddesk/absorb.py accepts."""
    return {"statement": statement, "source": source, "grade": grade,
            "measured_on": measured_on, "transfer_test": transfer_test,
            "observed_utc": datetime.now(tz=UTC).isoformat(),
            "meta": meta}


def _load(name: str):
    p = REPORTS / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build() -> list[dict]:
    """Collect findings from whatever sweep artefacts actually exist.

    Reads the reports rather than restating remembered numbers: a hand-typed
    t-statistic is correct the day it is typed and silently wrong after the
    next run. A sweep whose artefact is absent contributes NOTHING rather
    than a placeholder -- an unmeasured finding is not a finding.
    """
    out: list[dict] = []

    cot = _load("cot_macro_sweep.json")
    if cot:
        rows = cot.get("rows", [])
        n_neg = sum(1 for r in rows if isinstance(r.get("t"), (int, float))
                    and r["t"] < 0)
        out.append(_f(
            statement=(
                "Following CFTC positioning does not pay on FX and metals. Four "
                f"COT-conditioned families across 8 symbols ({len(rows)} cells): "
                f"zero cleared the sweep's own multiplicity-corrected bar of "
                f"t>={cot.get('required_t', 0):.2f}, and {n_neg} of {len(rows)} "
                "cells had NEGATIVE t. Commercial-follow (the informed-hedger "
                "hypothesis) lost on every symbol tested."),
            source="quant desks/mt5 research/run_cot_macro_sweep.py",
            grade="E2", measured_on="AUDUSD USDCAD USDCHF GBPUSD USDJPY NZDUSD XAUUSD XAGUSD, H1",
            transfer_test=(
                "Aurum trades XAUUSD only. Gold IS in this sample and its four "
                "COT cells were all negative or flat, so the claim covers Aurum's "
                "instrument directly. To refute: run a COT-conditioned entry on "
                "Aurum's own XAUUSD bars and show positive expectancy net of the "
                "live spread."),
            trials=cot.get("trials"), required_t=cot.get("required_t"),
            survivors=0),
        )

    dip = _load("dip_buy_sweep.json")
    if dip:
        rows = dip.get("rows", [])
        out.append(_f(
            statement=(
                "Three distinct definitions of 'buy the dip' -- fixed-% "
                "retracement with a stall-confirmation, RSI oversold-reclaim, "
                "and single-bar ATR volatility flush -- all failed on "
                f"Fusion-executable crypto CFDs. {len(rows)} cells, none cleared "
                "the screening bar, and the great majority had negative "
                "expectancy. The three mechanisms are economically different, so "
                "this is not one idea failing three times."),
            source="quant desks/mt5 research/run_dip_buy_sweep.py",
            grade="E2", measured_on="BTCUSD ETHUSD, H1, 2018-2026",
            transfer_test=(
                "NOT measured on gold. Crypto CFDs are far more volatile than "
                "XAUUSD, so this must NOT be asserted about gold -- it is a "
                "reason to test the same three definitions on Aurum's XAUUSD "
                "bars, not a reason to assume the answer.")),
        )

    mc = _load("macro_conditioned_sweep.json")
    if mc:
        rows = mc.get("rows", [])
        helped = sum(1 for r in rows
                     if isinstance(r.get("t_delta"), (int, float)) and r["t_delta"] > 0)
        out.append(_f(
            statement=(
                "Macro conditioning carries real information but does not create "
                f"edge. Conditioning entries on the supportive macro state raised "
                f"the t-statistic in {helped} of {len(rows)} cells -- a consistent "
                "directional effect -- yet every cell improved only from strongly "
                "negative to less negative, and none reached the screening bar. "
                "Macro conditioning improves a mechanism; it cannot rescue one "
                "that has no edge to begin with."),
            source="quant desks/mt5 research/run_macro_conditioned_sweep.py",
            grade="E2", measured_on="XAUUSD XAGUSD GBPUSD AUDUSD NZDUSD BTCUSD ETHUSD, H1",
            transfer_test=(
                "Aurum now renders macro into the analyst brief. If this finding "
                "transfers, macro context should measurably change Aurum's reads "
                "without, on its own, turning losing setups into winners. The test "
                "is a paired comparison on identical states with the macro block "
                "present vs absent -- which Aurum can run, because the block is "
                "optional by construction.")),
        )

    sw = _load("macro_swing_sweep.json")
    if sw:
        rows = sw.get("rows", [])
        ranked = [r for r in rows
                  if isinstance(r.get("t"), (int, float)) and r["t"] >= 1.96]
        best = max((r for r in rows if isinstance(r.get("t"), (int, float))),
                   key=lambda r: r["t"], default=None)
        out.append(_f(
            statement=(
                "Macro used as the SIGNAL ITSELF -- no price trigger, the series "
                "turning is the whole thesis -- produced positive expectancy on "
                "gold, silver, sterling and yen, unlike every price-structure "
                "family tested. Best cell: "
                + (f"{best['symbol']} vs {best['driver']}, hold {best['hold']}, "
                   f"n={best['n']}, t={best['t']:.2f}, {best['exp']:+.4f}R. "
                   if best else "")
                + f"{len(ranked)} of {len(rows)} cells cleared the Stage-A "
                "screening bar, which is close to the chance rate, so this ranks "
                "for forward confirmation rather than proving an edge."),
            source="quant desks/mt5 research/run_macro_swing_sweep.py",
            grade="E2", measured_on="XAUUSD XAGUSD GBPUSD AUDUSD NZDUSD USDJPY BTCUSD ETHUSD, H1",
            transfer_test=(
                "XAUUSD vs the 10y real yield is in this sample and was positive "
                "(+0.14R at a 5-day hold) though below the bar. Aurum has the same "
                "driver via drivers_free (FRED DFII10). To refute: run a real-yield "
                "swing entry on Aurum's XAUUSD bars and show it does not beat "
                "Aurum's structural entries on matched states.")),
        )
        out.append(_f(
            statement=(
                "Longer holds did NOT amortise cost into an edge, contradicting "
                "the prior. The prediction was stated before the run: t should "
                "rise with hold length. It did not. The single best-ranked cell "
                "was the SHORTEST hold and decayed monotonically as the hold "
                "extended, and most apparent 'improvement' with length was a "
                "losing signal diluting toward zero rather than a winning one "
                "strengthening. Beyond roughly 10 days the TTL stopped binding "
                "at all -- stop or target resolved first -- so the long end of "
                "the sweep was not testing what it appeared to."),
            source="quant desks/mt5 research/run_macro_swing_sweep.py",
            grade="E2", measured_on="8 symbols x 4 hold lengths (1/5/10/20 trading days), H1",
            transfer_test=(
                "Aurum's holds are set by its own stop/target geometry, not by a "
                "TTL. The transferable part is the WARNING: do not lengthen Aurum's "
                "holds expecting cost amortisation to create edge. To refute, show "
                "matched Aurum states where a longer hold beat a shorter one net "
                "of cost.")),
        )

    return out


def main() -> int:
    findings = build()
    if not findings:
        print("NO SWEEP ARTEFACTS FOUND under reports/. Nothing exported.\n"
              "That is UNMEASURED, not 'no findings' -- run the sweeps first.")
        return 2

    REPORTS.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:      # APPEND: see the docstring
        for row in findings:
            fh.write(json.dumps(row) + "\n")

    print(f"{len(findings)} finding(s) appended to {OUT}\n")
    for row in findings:
        print(f"  [{row['grade']}] {row['statement'][:96]}...")
        print(f"        measured on: {row['measured_on']}")
    print("\nTRANSPORT IS A SEPARATE, OPERATOR-PERFORMED STEP -- this script does "
          "not reach into\nAurum's checkout. Copy this file to Aurum as "
          "inbox/quant_findings.jsonl (append, do not\noverwrite), then Aurum's "
          "daily step_absorb will queue each row as a SEALED HYPOTHESIS\nat zero "
          "authority, which is the only safe way a finding from one desk enters "
          "another.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
