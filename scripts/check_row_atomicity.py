#!/usr/bin/env python3
"""R0345 FALSIFIER: do COMPOUND ledger rows actually age longer than ATOMIC ones?

R0345 (raised 2026-08-01, still open 10.9d later) proposed that the recommendation backlog --
the desk's #1 recurring defect, escalated to the principal page as `rec-ledger-backlog` and
RECURRED 3x over 11.9d -- is driven by COMPOUND rows: "do X AND Y AND Z" bundled behind one id.
Such a row cannot be marked implemented by any single action, so it can only ever be
re-scheduled, and it ages forever while atomic rows around it convert. The proposed build was
admission control in `scripts/recommendations.py add`.

R0345 PRE-REGISTERED ITS OWN FALSIFIER, and this runs it BEFORE that build:

    "measure disposition latency for compound versus atomic rows in the existing ledger --
     if compound rows do NOT age longer, this hypothesis is wrong and the backlog is
     explained by something else."

THREE METHOD CHOICES, each of which changes the answer, so each is stated rather than defaulted:

1. SURVIVAL, NOT MEAN-OF-COMPLETED. Latency over disposed rows only is survivorship-biased in
   the exact direction that would FAKE this hypothesis: a compound row that never converts is
   invisible to a completed-only mean, so the rows the hypothesis is ABOUT are the rows it drops.
   Open and scheduled rows are right-censored at (now - raised) and carried by Kaplan-Meier.
   The desk has already paid for this one (KM 5.27d vs naive 3.37d on the same ledger).

2. `scheduled` IS CENSORED, NOT AN EVENT. The ledger's own law admits it as a disposition, but
   conversion_status counts it in the backlog and R0345's claim is precisely that compound rows
   "can only ever be re-scheduled". Scoring `scheduled` as a conversion would assume the
   conclusion away; it is treated as still-at-risk.

3. SOURCE IS A CONFOUND AND IS STRATIFIED. R0345's own evidence is the 14-row SYNTH0731 batch,
   which is simultaneously compound AND from one neglected source raised in one burst. Without
   stratification "compound" and "that batch" are the same variable, and the test would confirm
   the hypothesis while measuring the confound.

The primary classifier is declared before the result and every alternative is reported, because
picking the definition that separates hardest after seeing the answer is the garden of forking
paths applied to our own governance.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs/research/recommendation_ledger.json"

#: A row is CONVERTED only at a terminal state. `scheduled` is deliberately excluded -- see (2).
_TERMINAL = ("implemented", "rejected", "done", "screened")
#: Still at risk: the row owes a decision nobody has made yet.
_CENSORED = ("open", "scheduled")

#: PRIMARY classifier, declared before the result: parenthesised enumeration, "(1) ... (2) ...".
#: This is how this desk writes multi-deliverable rows, and it is the structure R0345 describes.
_ENUM = re.compile(r"\((\d)\)")
#: Alternatives, reported for sensitivity -- never to be swapped in after seeing the answer.
_SEMI_REQ = re.compile(r"\bRequired\b.*;", re.IGNORECASE | re.DOTALL)
_PLUS_AND = re.compile(r"\b(?:plus|and then|as well as)\b", re.IGNORECASE)


def _enum_count(text: str) -> int:
    """Distinct parenthesised ordinals -- "(1)...(2)" is 2, "(1)...(1)" is 1."""
    return len(set(_ENUM.findall(text)))


def classify(summary: str, how: str = "enum") -> bool:
    """True when the row bundles independent deliverables under one id."""
    if how == "enum":
        return _enum_count(summary) >= 2
    if how == "enum3":
        return _enum_count(summary) >= 3
    if how == "semicolon":
        return bool(_SEMI_REQ.search(summary))
    if how == "conjunction":
        return _enum_count(summary) >= 2 or bool(_PLUS_AND.search(summary))
    if how == "length":
        return len(summary) >= 600
    raise ValueError(f"unknown classifier {how!r}")


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def observations(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """(duration_days, converted) per row, with censoring -- see method note (1)."""
    out = []
    for r in rows:
        raised = _parse(r.get("raised"))
        if raised is None:
            continue                       # cannot place it on a clock; excluded, and counted
        status = (r.get("status") or "").lower()
        disposed = _parse(r.get("disposed"))
        if status in _TERMINAL and disposed is not None:
            dur, converted = (disposed - raised).total_seconds() / 86400.0, True
        elif status in _CENSORED:
            dur, converted = (now - raised).total_seconds() / 86400.0, False
        else:
            continue                       # terminal but unstamped: no clock, excluded loudly
        out.append({"id": r.get("id"), "days": max(dur, 0.0), "converted": converted,
                    "source": r.get("source") or "?", "summary": r.get("summary") or ""})
    return out


def km_median(obs: list[dict[str, Any]]) -> tuple[float | None, float]:
    """Kaplan-Meier median time-to-conversion, and S(t) at the last event.

    Returns (median_days, tail_survival). A median of None means the curve never reached 0.5 --
    i.e. MOST ROWS IN THIS GROUP NEVER CONVERT, which is a real answer and not a missing number.
    """
    if not obs:
        return None, 1.0
    times = sorted({o["days"] for o in obs if o["converted"]})
    surv, median = 1.0, None
    for t in times:
        at_risk = sum(1 for o in obs if o["days"] >= t)
        events = sum(1 for o in obs if o["converted"] and o["days"] == t)
        if at_risk == 0:
            continue
        surv *= 1.0 - events / at_risk
        if median is None and surv <= 0.5:
            median = t
    return median, surv


def logrank(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> tuple[float, float]:
    """Two-group log-rank chi-square (1 df) and its p-value.

    The right test here: it compares whole curves under censoring rather than comparing two
    means that censoring has already biased.
    """
    times = sorted({o["days"] for o in (a + b) if o["converted"]})
    obs_a = exp_a = var = 0.0
    for t in times:
        n_a = sum(1 for o in a if o["days"] >= t)
        n_b = sum(1 for o in b if o["days"] >= t)
        n = n_a + n_b
        d_a = sum(1 for o in a if o["converted"] and o["days"] == t)
        d = d_a + sum(1 for o in b if o["converted"] and o["days"] == t)
        if n < 2 or d == 0:
            continue
        obs_a += d_a
        exp_a += d * n_a / n
        var += d * (n_a / n) * (n_b / n) * (n - d) / (n - 1)
    if var <= 0:
        return 0.0, 1.0
    chi2 = (obs_a - exp_a) ** 2 / var
    # Survival function of chi-square with 1 df = erfc(sqrt(chi2/2)).
    return chi2, math.erfc(math.sqrt(chi2 / 2.0))


def _group(obs: list[dict[str, Any]], how: str) -> tuple[list[Any], list[Any]]:
    comp = [o for o in obs if classify(o["summary"], how)]
    atom = [o for o in obs if not classify(o["summary"], how)]
    return comp, atom


def _line(name: str, g: list[dict[str, Any]]) -> str:
    med, tail = km_median(g)
    rate = sum(1 for o in g if o["converted"]) / len(g) if g else 0.0
    med_s = f"{med:.2f}d" if med is not None else "NEVER-REACHED"
    return (f"  {name:<10s} n={len(g):3d}  converted={rate:5.1%}  "
            f"KM-median={med_s:<14s} S(tail)={tail:.2f}")


def main() -> int:
    rows = json.loads(LEDGER.read_text("utf-8"))["recommendations"]
    now = datetime.now(tz=UTC)
    obs = observations(rows, now)
    dropped = len(rows) - len(obs)

    print("=" * 88)
    print("R0345 FALSIFIER -- compound vs atomic ledger rows, Kaplan-Meier with censoring")
    print("=" * 88)
    print(f"ledger rows={len(rows)}  usable={len(obs)}  dropped(no clock)={dropped}")
    print(f"converted={sum(1 for o in obs if o['converted'])}  "
          f"censored={sum(1 for o in obs if not o['converted'])}")

    print("\n-- PRIMARY (declared before the result): compound = >=2 parenthesised ordinals --")
    comp, atom = _group(obs, "enum")
    print(_line("COMPOUND", comp))
    print(_line("ATOMIC", atom))
    chi2, p = logrank(comp, atom)
    print(f"  log-rank chi2={chi2:.3f}  p={p:.4f}  "
          f"({'SEPARATES' if p < 0.05 else 'NO DIFFERENCE DETECTED'} at 0.05)")

    print("\n-- SENSITIVITY (every alternative reported, none swapped in after the fact) --")
    for how in ("enum3", "semicolon", "conjunction", "length"):
        c, a = _group(obs, how)
        if not c or not a:
            print(f"  {how:<12s} degenerate split (n_compound={len(c)}) -- no test")
            continue
        x, pv = logrank(c, a)
        mc, ma = km_median(c)[0], km_median(a)[0]
        mcs = f"{mc:.2f}" if mc is not None else "NEVER"
        mas = f"{ma:.2f}" if ma is not None else "NEVER"
        print(f"  {how:<12s} n_comp={len(c):3d} med_comp={mcs:>6s} med_atom={mas:>6s} "
              f"chi2={x:6.3f} p={pv:.4f}")

    print("\n-- CONFOUND: is 'compound' just the SYNTH0731/deep_sweep batch? (method note 3) --")
    src = Counter(o["source"] for o in comp)
    print(f"  compound rows by source: {dict(src.most_common(6))}")
    for source, n in src.most_common(3):
        if n < 8:
            continue
        sub = [o for o in obs if o["source"] == source]
        c2, a2 = _group(sub, "enum")
        if not c2 or not a2:
            print(f"  within {source:<14s} degenerate (n_comp={len(c2)}, n_atom={len(a2)})")
            continue
        x2, p2 = logrank(c2, a2)
        m2, m3 = km_median(c2)[0], km_median(a2)[0]
        print(f"  within {source:<14s} n_comp={len(c2):3d} n_atom={len(a2):3d} "
              f"med_comp={m2 if m2 is None else round(m2, 2)} "
              f"med_atom={m3 if m3 is None else round(m3, 2)} chi2={x2:.3f} p={p2:.4f}")

    print("\n-- WHAT ELSE EXPLAINS THE BACKLOG? age of the still-open rows by source --")
    open_rows = [o for o in obs if not o["converted"]]
    by_src: dict[str, list[float]] = {}
    for o in open_rows:
        by_src.setdefault(o["source"], []).append(o["days"])
    for source, ages in sorted(by_src.items(), key=lambda kv: -len(kv[1]))[:8]:
        ages.sort()
        print(f"  {source:<20s} open={len(ages):3d}  median_age={ages[len(ages)//2]:6.2f}d  "
              f"oldest={ages[-1]:6.2f}d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
