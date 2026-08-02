"""DAILY HYPOTHESIS FUNNEL -- generate at volume, screen hard, hand the gauntlet only survivors.

THE PRINCIPAL'S IDEA (2026-08-01), and it aims at the measured bottleneck exactly: have an AI
work through thousands of hypotheses a day against the desk's own standards, so the desk's real
gauntlet receives pre-screened candidates instead of raw volume -- WITHOUT the bar moving.

That last clause is the whole design constraint. The desk's own numbers say the bar is not the
problem: 420 candidates, zero survivors, and waiving the campaign veto was MEASURED to promote
nobody because every candidate also failed a gate that genuinely discriminates. The candidates
are the problem. So a pre-screen is worth building precisely because it improves candidate
quality, and worth building CAREFULLY because a pre-screen is the easiest place in the whole
pipeline to lower a bar by accident.

=============================================================================
THE TRAP, NAMED, BECAUSE IT WOULD BE FATAL AND IT LOOKS LIKE THE FEATURE
=============================================================================
AN LLM CANNOT TEST A HYPOTHESIS. It has no price data, runs no backtest, computes no
walk-forward, no CPCV, no PBO, no deflated Sharpe. Ask one to "apply our gate standards and
return the survivors" and it will return survivors -- fluently, confidently, with plausible
numbers attached, having computed nothing. That is not a screen. It is a random filter wearing
the language of rigour, and it is strictly WORSE than no screen at all, because its output
arrives carrying a false prior of quality that the real gauntlet then has to overcome.

So the split is hard and enforced in code:

  THE LLM JUDGES ONLY WHAT NEEDS NO DATA -- does the mechanism survive "why has nobody
  arbitraged this?"; is the named data source real, free and actually sufficient for the stated
  test; is the kill condition falsifiable; is this a renamed version of something already dead.
  Mechanism reasoning is the desk's CHEAPEST kill and its most historically productive one: the
  graveyard records four FAMILY KILLS reached that way, before any compute was spent.

  ARITHMETIC IS DONE BY ARITHMETIC -- the cost floor, degenerate turnover, the trivial-variation
  fingerprint and the graveyard match run in libs/hypmax/hypothesis_max, deterministically, with
  no model in the loop.

  STATISTICS ARE NEVER ASKED -- no seat is ever shown a significance question, and any answer
  claiming statistical validity is stripped. The gauntlet owns that and nothing else may.

=============================================================================
THE SECOND TRAP: A SCREEN THAT IS ALLOWED TO KILL
=============================================================================
The pre-filter's default is ESCALATE, not REJECT, and that inversion is deliberate and tested.
Everywhere else on this desk an ambiguous branch must block; here it must not. The failure being
guarded against is a silently killed alpha, not a bad trade -- the full gauntlet is unchanged
behind this. Wasted compute is recoverable; a discarded edge is not. So missing evidence can
never contribute to a rejection, and the panel needs a MAJORITY to kill rather than any single
seat's veto.

Reports and writes a candidate file. ZERO promotion authority: promotion still requires
pre-registered FORWARD evidence under the Two-Stage Discovery Law.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.hypmax.evig import p_validate_from_history, rank_by_evig  # noqa: E402
from libs.hypmax.hypothesis_max import (  # noqa: E402
    TrivialVariationBlocker,
    batch_diversity,
    fingerprint,
    horizon_bucket,
    prefilter,
)

QUEUE = ROOT / "data/hypothesis_queue.jsonl"
#: Data sources the desk RECORDS ITSELF. A candidate reading these cannot be replicated by a
#: competitor for a past date at any price, which is the only advantage that survives contact
#: with somebody else reading the same public feed.
_MOAT_TOKENS = ("moat", "order book", "orderbook", "depth", "l2", "withdrawal", "microprice",
                "resting", "book slope", "imbalance", "replenish", "our recorder", "recorded")

OUT = ROOT / "data/gauntlet_candidates.json"
FUNNEL = ROOT / "data/hypothesis_funnel.json"
GRAVE = ROOT / "docs/graveyard.md"

#: A mechanism must be killed by a MAJORITY of seats, never one. A single seat's veto would let
#: one model's blind spot silently define what the desk is allowed to investigate -- the exact
#: single-reviewer trap the multi-lab roster exists to break.
KILL_MAJORITY = 0.5

#: Phrases that mean a seat has strayed into statistics it cannot possibly have computed. Their
#: presence does not merely get ignored -- the whole verdict is discarded, because a seat willing
#: to fabricate a Sharpe is not a seat whose mechanism reasoning can be trusted in the same breath.
_FABRICATION = (
    "sharpe of", "sharpe ratio of", "t-stat", "t statistic", "p-value", "p value",
    "backtested", "back-tested", "i tested", "i ran", "returns of", "annualized return",
    "win rate of", "drawdown of", "ic of", "information coefficient of",
)

ADJUDICATION_SYSTEM = (
    "You are screening trading hypotheses for a crypto desk. You judge EXACTLY FOUR THINGS and "
    "nothing else:\n"
    "1. MECHANISM: does it survive 'why has nobody already arbitraged this?' Name the reason the "
    "edge persists -- a structural barrier, a forced flow, a measurement cost, a constraint. "
    "'It is a known anomaly' is NOT a mechanism.\n"
    "2. DATA: is the named source real, free, public, and actually SUFFICIENT for the stated "
    "test? A test needing tick data from a source that publishes daily bars is dead on arrival.\n"
    "3. FALSIFIABILITY: is the kill condition concrete enough that a specific measurement would "
    "end the hypothesis?\n"
    "4. NOVELTY: is this a renamed version of a mechanism already in the refuted list?\n\n"
    "YOU HAVE NO PRICE DATA AND YOU RUN NO TESTS. You must NEVER state or estimate a Sharpe "
    "ratio, t-statistic, p-value, IC, win rate, return or drawdown, and never claim anything was "
    "backtested. Any such claim is a fabrication and voids your entire verdict -- the desk's "
    "gauntlet owns statistics and you do not. Judging the mechanism is your job and it is the "
    "cheapest kill available; pretending to judge the statistics destroys your usefulness.\n\n"
    "BIAS TOWARD LETTING THINGS THROUGH. A wrongly-killed hypothesis is never recovered; a "
    "wrongly-passed one costs some compute and dies in the gauntlet. Kill ONLY on a clear, "
    "stateable defect. If unsure, PASS.\n\n"
    "Output ONE line per hypothesis, nothing else:\n"
    "NAME | PASS or KILL | the single clearest reason (<=20 words)"
)


def load_queue(path: Path = QUEUE, limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict) and d.get("name"):
                    rows.append(d)
    except OSError:
        return []
    return rows[-limit:] if limit else rows


def _horizon_of(row: dict) -> float:
    """Best-effort horizon in hours from free text. UNKNOWN maps to 0 -> bucket 'unknown', which
    is a distinct fingerprint bucket rather than a guess -- inventing a horizon would let two
    genuinely different mechanisms collide, and the blocker would then suppress a live one."""
    txt = f"{row.get('test', '')} {row.get('name', '')}".lower()
    m = re.search(r"(\d+)\s*(min|minute|hour|hr|h\b|day|d\b|week|w\b)", txt)
    if not m:
        return 0.0
    n, unit = float(m.group(1)), m.group(2)
    if unit.startswith("min"):
        return n / 60.0
    if unit.startswith(("hour", "hr", "h")):
        return n
    if unit.startswith(("day", "d")):
        return n * 24.0
    return n * 168.0


def _family_of(row: dict) -> str:
    """Feature family = the first substantive noun-ish token of the data source, falling back to
    the name. Crude by design: the fingerprint's job is to collapse PARAMETER variants, and a
    sophisticated extractor would create more distinct fingerprints, not fewer."""
    src = str(row.get("data", "")) or str(row.get("name", ""))
    toks = [t for t in re.split(r"[^A-Za-z]+", src) if len(t) > 3]
    return toks[0].lower() if toks else "unknown"


def _family_history() -> dict[str, tuple[int, int]]:
    """(survivors, attempts) per family, read from the desk's OWN graveyard.

    Real recorded outcomes rather than an asserted prior. Every entry there was tested and died,
    so the map is currently all-zero-survivors -- which is the honest input, and is precisely what
    keeps P(validate) near-flat until something actually validates.
    """
    hist: dict[str, list[int]] = {}
    grave = ROOT / "docs/graveyard.md"
    if not grave.exists():
        return {}
    for line in grave.read_text("utf-8", errors="ignore").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Hypothesis |" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0]:
            continue
        fam = _family_of({"name": cells[0]})
        row = hist.setdefault(fam, [0, 0])
        row[1] += 1                                  # attempted; survivors stay 0 by construction
    return {k: (v[0], v[1]) for k, v in hist.items()}


def _moat_advantage(row: dict) -> float:
    """Replication cost of this candidate's data, on the desk's own measured scale.

    The information-advantage ranking puts self-recorded order books at 1.03 and the next-best
    source at 0.37 -- so a candidate reading the moat is worth ~2.8x a public-data one at equal
    P(validate), and EVIG should say so. Anything unrecognised gets the PUBLIC value rather than
    a middle guess: an unknown source is one nobody has shown to be proprietary, and flattering it
    would let unlabelled candidates outrank measured moat ones.
    """
    blob = " ".join(str(row.get(k, "")) for k in
                    ("data_source", "data", "source", "mechanism", "name")).lower()
    return 1.03 if any(t in blob for t in _MOAT_TOKENS) else 0.37


def _test_cost(row: dict) -> float:
    """Relative L4 cost. 1.0 is a routine run; anything needing more history or more symbols
    costs more, and EVIG divides by it because compute is the resource actually being rationed."""
    cost = 1.0
    with contextlib.suppress(TypeError, ValueError):
        if float(row.get("turnover") or 0) > 10:
            cost *= 1.5              # high turnover: more fills to simulate, more cost sensitivity
    hz = _horizon_of(row)
    if hz and hz >= 168:
        cost *= 2.0                  # weekly+ horizons need years of history to say anything
    return round(cost, 3)


def score_evig(rows: list[dict], family_history: dict[str, tuple[int, int]] | None = None,
               ) -> list[dict]:
    """Order survivors by expected validated information gain per unit of compute (P1).

    THE FUNNEL RANKED BY NOTHING BEFORE THIS. Candidates came out of the arithmetic screen in
    whatever order the generator emitted them, so the scarcest resource on the desk -- L4 compute
    -- was allocated by accident of ordering. EVIG is the constitution's own answer: value is the
    expected SHIFT IN E[log W] from running the test, never the probability the answer is yes.

    P(validate) comes from the family's own recorded history, shrunk toward a failure-tilted
    prior, so it is measured rather than asserted; with 0 survivors so far it is near-flat and
    EVIG discriminates on MOAT and COST, which are the terms that actually vary today. It
    sharpens automatically the first time anything validates.

    NO PROMOTION AUTHORITY. This orders; it never rejects. A candidate at the bottom of the
    ranking is still a candidate.
    """
    hist = family_history or {}
    out = []
    for r in rows:
        d = dict(r)
        surv, att = hist.get(_family_of(r), (0, 0))
        d["p_validate"] = p_validate_from_history(surv, att)
        d["moat_advantage"] = _moat_advantage(r)
        d["cost"] = _test_cost(r)
        out.append(d)
    return rank_by_evig(out)


def deterministic_screen(rows: list[dict], blocker: TrivialVariationBlocker | None = None,
                         ) -> tuple[list[dict], Counter]:
    """STAGE 1 -- arithmetic only, no model in the loop.

    Cost floor, degenerate turnover, hopeless statistics WHEN PRESENT, and the trivial-variation
    fingerprint. Every field is optional and a missing one can never cause a rejection, so a
    hypothesis nobody has measured always survives to stage 2.
    """
    blocker = blocker or TrivialVariationBlocker()
    kept, why = [], Counter()
    for r in rows:
        fam = _family_of(r)
        hz = _horizon_of(r)
        v = prefilter(feature_family=fam, transform=str(r.get("lens", "raw")), horizon_h=hz,
                      gross_edge_bps=r.get("gross_edge_bps"),
                      round_trip_cost_bps=r.get("round_trip_cost_bps"),
                      turnover=r.get("turnover"), t_stat=r.get("t_stat"), ic=r.get("ic"),
                      blocker=blocker)
        r["fingerprint"] = v.fingerprint
        r["horizon_bucket"] = horizon_bucket(hz)
        if v.decision == "REJECT":
            why[v.reasons[0].split(":")[0][:40]] += 1
            continue
        r["prefilter"] = v.decision
        kept.append(r)
    return kept, why


def strip_fabrication(verdicts: list[dict]) -> tuple[list[dict], list[str]]:
    """Discard any verdict whose reason strays into statistics the seat cannot have computed.

    The whole verdict goes, not just the offending phrase. A seat willing to invent a t-stat has
    demonstrated it is answering from plausibility rather than from the four questions it was
    given, and its mechanism judgement in the same breath is worth nothing.
    """
    clean, dropped = [], []
    for v in verdicts:
        low = str(v.get("reason", "")).lower()
        if any(f in low for f in _FABRICATION):
            dropped.append(f"{v.get('seat', '?')}: {v.get('name', '?')[:40]}")
            continue
        clean.append(v)
    return clean, dropped


def adjudicate(verdicts: list[dict], n_seats: int,
               majority: float = KILL_MAJORITY) -> dict[str, dict]:
    """STAGE 2 -- multi-seat mechanism verdict. A MAJORITY kills; one seat never does.

    A single seat's veto would let one model's blind spot define what the desk may investigate,
    which is precisely the single-reviewer failure the multi-lab roster exists to break. Absent
    verdicts count as neither pass nor kill -- a seat that timed out has not voted.
    """
    by_name: dict[str, dict] = {}
    for v in verdicts:
        e = by_name.setdefault(str(v.get("name", ""))[:90],
                               {"pass": 0, "kill": 0, "reasons": []})
        if str(v.get("verdict", "")).upper().startswith("KILL"):
            e["kill"] += 1
            if v.get("reason"):
                e["reasons"].append(f"{v.get('seat', '?').split('/')[-1]}: {v['reason'][:90]}")
        else:
            e["pass"] += 1
    for e in by_name.values():
        voted = e["pass"] + e["kill"]
        e["voted"] = voted
        e["kill_share"] = round(e["kill"] / voted, 3) if voted else 0.0
        e["survived"] = not (voted and e["kill_share"] > majority)
        e["quorum"] = voted >= max(1, n_seats // 2)
    return by_name


def seat_yield(generated: list[dict], survived: list[dict]) -> list[dict]:
    """WHICH SEAT SHOULD GENERATE? Answered by measurement, never by reputation.

    hypothesis_generator has claimed "per-seat yield is tracked" since it was written, and
    nothing tracked it -- the same claim-without-an-artifact shape this desk keeps finding. So
    the question "which AI is the creative one?" had no data behind it and was going to be
    settled by whoever sounded most confident.

    THE DESK ALREADY HAS EVIDENCE THAT REPUTATION IS THE WRONG PRIOR, and it points the
    unintuitive way: its own measurement records gpt-5.6-terra-pro producing ZERO parseable rows
    on 5 of 6 breadth lenses while nemotron and grok produced 18 each. The model with the
    strongest creative reputation measured WORST on this desk's actual generation task. Seating
    by reputation would have been exactly wrong, and confidently so.

    FOUR COLUMNS, and `distinct` is the one that matters most. A seat emitting 200 near-identical
    hypotheses outranks everyone on raw count while contributing almost nothing -- volume without
    information, the same illusion batch_diversity() exists to strip out of a batch. Survival
    rate alone is also gameable: a seat proposing three safe restatements of the deployed edge
    scores 100% and discovers nothing. Read them together or not at all.
    """
    gen, surv, fps = Counter(), Counter(), {}
    for r in generated:
        seat = str(r.get("seat", "?"))
        gen[seat] += 1
        fps.setdefault(seat, set()).add(
            r.get("fingerprint") or fingerprint(_family_of(r), str(r.get("lens", "")),
                                                _horizon_of(r)))
    for r in survived:
        surv[str(r.get("seat", "?"))] += 1
    out = []
    for seat, n in gen.most_common():
        distinct = len(fps.get(seat, ()))
        out.append({
            "seat": seat, "generated": n, "survived": surv.get(seat, 0),
            "survival_rate": round(surv.get(seat, 0) / n, 3) if n else 0.0,
            "distinct_mechanisms": distinct,
            "duplicate_rate": round(1.0 - distinct / n, 3) if n else 0.0,
            # The honest headline: distinct mechanisms that cleared the arithmetic screen. Counts
            # neither raw volume nor safe restatement -- only NEW ideas that survived.
            "distinct_survivors": min(distinct, surv.get(seat, 0)),
        })
    return sorted(out, key=lambda d: -d["distinct_survivors"])


def _self_test() -> None:
    print("=== HYPOTHESIS FUNNEL (self-test) ===\n")
    rows = [
        {"name": "Depth replenishment after liquidity withdrawal", "data": "orderbook moat",
         "lens": "MEASUREMENT ADVANTAGE", "test": "4 hour horizon", "kill": "IC<0.02"},
        {"name": "RSI oversold bounce", "data": "price candles", "lens": "SECOND ORDER",
         "test": "12 hour", "kill": "none", "turnover": 0.0},
        {"name": "Funding persistence spread", "data": "funding endpoint", "lens": "PARTICIPANT",
         "test": "8 hour", "gross_edge_bps": 1.0, "round_trip_cost_bps": 2.0},
        {"name": "Validator exit queue congestion", "data": "beacon chain api",
         "lens": "PARTICIPANT CONSTRAINT", "test": "3 day", "kill": "spread<1bp"},
    ]
    kept, why = deterministic_screen(rows)
    print(f"STAGE 1 (arithmetic): {len(rows)} -> {len(kept)}")
    for k, n in why.items():
        print(f"    killed {n}: {k}")

    verdicts = [
        {"name": rows[0]["name"], "seat": "openai/x", "verdict": "PASS", "reason": "real barrier"},
        {"name": rows[0]["name"], "seat": "qwen/y", "verdict": "PASS", "reason": "observed only"},
        {"name": rows[3]["name"], "seat": "openai/x", "verdict": "KILL",
         "reason": "queue is public and already traded"},
        {"name": rows[3]["name"], "seat": "qwen/y", "verdict": "KILL", "reason": "no barrier"},
        {"name": rows[3]["name"], "seat": "google/z", "verdict": "PASS", "reason": "maybe"},
        {"name": rows[0]["name"], "seat": "bad/seat", "verdict": "KILL",
         "reason": "backtested Sharpe of 0.2"},
    ]
    clean, dropped = strip_fabrication(verdicts)
    print(f"\nFABRICATION GUARD: dropped {len(dropped)} verdict(s)")
    for d in dropped:
        print(f"    {d}")
    adj = adjudicate(clean, n_seats=3)
    print("\nSTAGE 2 (mechanism, majority kills):")
    for name, e in adj.items():
        print(f"    {name[:46]:<46} {'SURVIVED' if e['survived'] else 'KILLED':<9} "
              f"kill_share={e['kill_share']}")
    assert adj[rows[0]["name"]]["survived"] is True, "a fabricated kill must not count"
    assert adj[rows[3]["name"]]["survived"] is False, "a real majority must kill"
    print("\n  fabricated statistics did NOT kill a live hypothesis -- guard holds")
    d = batch_diversity([fingerprint(_family_of(r), r["lens"], _horizon_of(r)) for r in rows])
    print(f"  batch diversity: {d.distinct} distinct / {d.n}, collapsed={d.collapsed}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="screen only the newest N")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return

    rows = load_queue(limit=args.limit)
    print("=== DAILY HYPOTHESIS FUNNEL ===")
    if not rows:
        print(f"  {QUEUE.relative_to(ROOT)} empty -- run scripts/hypothesis_generator.py first.")
        print("  (Generation is unfunded today: OpenRouter 402.)")
        return

    kept, why = deterministic_screen(rows)
    fps = [r["fingerprint"] for r in kept]
    div = batch_diversity(fps)
    print(f"  generated              {len(rows)}")
    print(f"  survived arithmetic    {len(kept)}   ({len(rows) - len(kept)} killed)")
    for k, n in why.most_common(6):
        print(f"      {n:>5}  {k}")
    print(f"  distinct mechanisms    {div.distinct} of {div.n}  "
          f"(duplicate rate {div.duplicate_rate:.0%})")
    if div.collapsed:
        print("      COLLAPSE: volume held while information did not --")
        for r in div.reasons:
            print(f"      {r}")

    yields = seat_yield(rows, kept)
    if yields:
        print("\n  SEAT YIELD -- who actually generates, measured (not reputation):")
        print(f"    {'seat':<34}{'gen':>6}{'surv':>6}{'distinct':>10}{'dup':>7}{'NEW+SURV':>10}")
        for y in yields:
            print(f"    {y['seat'].split('/')[-1][:32]:<34}{y['generated']:>6}"
                  f"{y['survived']:>6}{y['distinct_mechanisms']:>10}"
                  f"{y['duplicate_rate']:>7.0%}{y['distinct_survivors']:>10}")
        print("    Ranked by DISTINCT SURVIVORS: raw count rewards a seat that repeats itself,")
        print("    and survival rate alone rewards one that restates the deployed edge safely.")

    # P1, INFORMATION VALUE CONDITION -- the funnel used to emit candidates in whatever order the
    # generator produced them, so L4 compute (the scarcest resource here) was allocated by
    # accident of ordering. Ranking only; nothing is rejected by EVIG.
    kept = score_evig(kept, _family_history())
    _scored = [c for c in kept if c.get("evig_scored")]
    _floor_dead = any(c.get("floor_not_discriminating") for c in _scored)
    print(f"  EVIG ranked           {len(_scored)} scored, {len(kept) - len(_scored)} unscored"
          + ("  [floor not discriminating -- base rate is 0 survivors; rank RELATIVELY]"
             if _floor_dead else ""))

    payload = {"ran": datetime.now(tz=UTC).isoformat(), "generated": len(rows),
               "seat_yield": yields,
               "survived_arithmetic": len(kept), "killed": dict(why),
               "distinct_mechanisms": div.distinct, "duplicate_rate": div.duplicate_rate,
               "candidates": kept}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    FUNNEL.write_text(json.dumps({k: v for k, v in payload.items() if k != "candidates"},
                                 indent=1), "utf-8")
    print(f"\n  -> {OUT.relative_to(ROOT)}")
    print("  Stage 2 (multi-seat MECHANISM adjudication) runs when the panel is funded.")
    print("  NO STATISTICS ARE EVER ASKED OF A SEAT: the gauntlet owns those, and a model")
    print("  claiming a Sharpe has fabricated it. ZERO promotion authority -- promotion still")
    print("  requires pre-registered FORWARD evidence under the Two-Stage Discovery Law.")


if __name__ == "__main__":
    main()
