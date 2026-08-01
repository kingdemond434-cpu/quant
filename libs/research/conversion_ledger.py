"""Did the thing we queued actually produce anything? The feedback loop the ranker never had.

THE DEFECT THIS CLOSES. `libs/research/video_triage` ranks candidates by weights I read off the
2026-08-01 batch, whose outcomes I already knew. That is fitting on the training set and then
reporting the training score -- the exact defect this desk exists to catch, committed in the tool
built to feed it. Worse, nothing recorded what happened to a queued item afterwards, so the
weights could never become measured. The ranker would have been exactly as good in a year as on
its first day.

WHAT A CONVERSION IS, and the definition is deliberately strict. An item CONVERTED if it produced
shipped, tested code or a measurement that changed a constant. Not "was interesting". Not
"confirmed something". The desk has a measured record precisely because that line was held: of
roughly thirty transcripts mined, the ones that converted produced bar_permutation,
lookahead_audit, intermarket, overlays, random_baseline, drawdown_metrics -- and the ones that did
not produced hours of reading and nothing else.

WHY THE LEDGER IS APPEND-ONLY AND SEPARATE FROM THE RANKER. If the same pass could both score an
item and record its outcome, the outcome would drift toward the score. Keeping them apart means
`calibration()` is a genuine out-of-sample check on the weights: it asks whether items the ranker
scored HIGH actually converted more often than items it scored LOW, on data recorded after the
scoring. That number is the only honest evidence the ranking works, and until it exists the
weights are an assertion.

THE FIRST ENTRIES ARE THE 2026-08-01 BATCH, seeded from what is known to have shipped. That is
in-sample by construction and it is labelled as such -- `calibration()` reports the in-sample and
out-of-sample cohorts separately, because a calibration number computed on the fitting set is the
same mistake one level up.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = _ROOT / "docs" / "research_conversions.jsonl"

#: The only outcomes worth distinguishing. "read" is deliberately separate from "rejected": an
#: item read and found empty is evidence about the RANKER, while an item never read is evidence
#: about nothing and must not be scored either way.
OUTCOMES = ("converted", "read_no_value", "queued_unread")


@dataclass(frozen=True)
class Entry:
    ident: str
    title: str
    source: str
    score: float
    outcome: str
    produced: str = ""
    cohort: str = "out_of_sample"
    recorded_utc: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")


def record(entry: Entry, *, path: Path | None = None) -> None:
    """Append one outcome. APPEND-ONLY: an outcome that can be edited is an outcome that will be
    edited to match whatever the ranker later says."""
    p = path or LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(entry)
    row["recorded_utc"] = entry.recorded_utc or datetime.now(UTC).isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load(path: Path | None = None) -> list[Entry]:
    p = path or LEDGER
    if not p.exists():
        return []
    out: list[Entry] = []
    for line in p.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(Entry(**json.loads(line)))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue          # a malformed row must not take down the audit
    return out


def calibration(path: Path | None = None, *, threshold: float = 6.0) -> dict[str, Any]:
    """Do high-scored items convert more often than low-scored ones?

    THE ONLY HONEST EVIDENCE THE RANKING WORKS. Items never read are excluded entirely: they carry
    no information about the ranker, and counting them as failures would punish exactly the
    high-scored backlog the ranker is trying to build.

    In-sample and out-of-sample cohorts are reported SEPARATELY. The seeded 2026-08-01 rows are
    the set the weights were read off, so their calibration is guaranteed good and means nothing;
    only the out-of-sample lift is evidence.
    """
    rows = [e for e in load(path) if e.outcome in ("converted", "read_no_value")]
    out: dict[str, Any] = {"n_ledger": len(load(path)), "n_scored": len(rows),
                           "threshold": threshold}
    for cohort in ("in_sample", "out_of_sample"):
        sub = [e for e in rows if e.cohort == cohort]
        hi = [e for e in sub if e.score >= threshold]
        lo = [e for e in sub if e.score < threshold]
        hi_rate = _rate(hi)
        lo_rate = _rate(lo)
        out[cohort] = {
            "n": len(sub), "n_high": len(hi), "n_low": len(lo),
            "convert_rate_high": hi_rate, "convert_rate_low": lo_rate,
            "lift": (None if hi_rate is None or lo_rate in (None, 0.0)
                     else round(hi_rate / lo_rate, 2)),
        }
    oos = out["out_of_sample"]
    if oos["n"] < 10:
        out["verdict"] = (f"UNMEASURED: only {oos['n']} out-of-sample outcomes recorded. The "
                          "ranker's weights remain an assertion until this reaches a usable "
                          "count -- read items and record what they produced.")
    elif oos["lift"] is None:
        out["verdict"] = "UNMEASURABLE: no low-scored items were read, so there is no baseline."
    elif oos["lift"] >= 1.5:
        out["verdict"] = (f"CALIBRATED: high-scored items convert {oos['lift']}x more often "
                          "out-of-sample. The ranking carries real information.")
    else:
        out["verdict"] = (f"NOT CALIBRATED: lift is {oos['lift']}x out-of-sample. The weights "
                          "were fitted on the 2026-08-01 batch and do not generalise; re-derive "
                          "them from this ledger rather than from memory.")
    return out


def _rate(entries: list[Entry]) -> float | None:
    if not entries:
        return None
    return round(sum(1 for e in entries if e.outcome == "converted") / len(entries), 3)


#: The 2026-08-01 batch, seeded from what actually shipped. IN-SAMPLE BY CONSTRUCTION and labelled
#: so, because these are the outcomes the ranker's weights were read off.
SEED: tuple[tuple[str, str, float, str, str], ...] = (
    ("neurotrader:permutation_tests", "Monte Carlo Permutation Tests", 8.0, "converted",
     "libs/validation/bar_permutation + the coupled-shuffle correction"),
    ("neurotrader:develop_strategies", "How I Develop Trading Strategies", 6.0, "converted",
     "confirmed the construction defect against the reference implementation"),
    ("neurotrader:intramarket", "Intramarket Indicator Differences", 5.0, "converted",
     "libs/research/intermarket"),
    ("neurotrader:trade_dependence", "Trade Dependence / Donchian", 5.0, "converted",
     "overlays.trade_dependence_filter; conditional adoption via runs test, corr 0.898"),
    ("algovibes:regime", "Everyone Says Market Regimes Fix Strategies", 5.0, "converted",
     "libs/validation/lookahead_audit"),
    ("algovibes:vol_target", "Volatility Targeting vs Buy & Hold", 3.0, "converted",
     "overlays.volatility_target -- drawdown 0.64 -> 0.20 on 12/12"),
    ("algovibes:350k_btc", "I Tested 350,000 Bitcoin Strategies", 8.0, "converted",
     "monte_carlo_survival dd_limit calibration landmine"),
    ("algovibes:combined51", "I Combined 51 Trading Strategies", 5.0, "converted",
     "correlation-of-winners: 0.08 population vs 0.85 among winners"),
    ("davey:book_summary", "Building Winning Algorithmic Trading Systems", 4.0, "converted",
     "libs/validation/random_baseline + drawdown_metrics"),
    ("iqcapital:trader_x", "I Reverse-Engineered a $102,000/Month Trader", -4.0, "read_no_value",
     ""),
    ("iqcapital:hedge_fund", "Ex-Hedge Fund Manager Reveals $150M Scalping", -4.0,
     "read_no_value", ""),
    ("iqcapital:10k_traders", "I Analyzed 10,000 Traders", 3.0, "read_no_value",
     "one corroboration of the family ranking, no code"),
    ("deltatrend:ivy_league", "Build Your Own Trading Strategy", 2.0, "read_no_value",
     "one number (25% post-publication decay), never built"),
    ("neurotrader:books", "Books for Algorithmic Trading", 1.0, "read_no_value",
     "two pointers, no direct conversion"),
)


def seed(path: Path | None = None) -> int:
    """Write the known 2026-08-01 outcomes. Idempotent by ident."""
    have = {e.ident for e in load(path)}
    n = 0
    for ident, title, score, outcome, produced in SEED:
        if ident in have:
            continue
        record(Entry(ident=ident, title=title, source=ident.split(":")[0], score=score,
                     outcome=outcome, produced=produced, cohort="in_sample"), path=path)
        n += 1
    return n
