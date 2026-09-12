"""F13 -- INDEPENDENCE IN THE TAILS, not just on average.

THE PRINCIPAL, 2026-09-12:

    Add conditional correlation, nonlinear mutual information, tail dependence, co-drawdown
    probability, same-event loss, common liquidity dependence, execution-resource overlap, factor
    residualisation and capacity overlap. The final score is marginal portfolio Elog after
    residualizing against the entire existing book.

WHY PEARSON IS THE WRONG NUMBER TO SIZE A BOOK ON, and this is not a refinement. n_eff =
N/(1+(N-1)rho) is computed from a LINEAR correlation estimated over ALL days -- and all days are
mostly quiet days. Two sleeves can sit at rho = 0.05 across a year and go down together in every
single week that matters, because dependence concentrates in the tail while correlation averages
it away. The desk then sizes as though it holds independent bets and discovers otherwise in the
one week it cannot afford to.

That failure is invisible to every number the allocator currently reads. It reports N_eff = 8.80
off a covariance matrix, and the covariance matrix cannot express "these two are unrelated on 95%
of days and identical on the other 5%".

WHAT IS MEASURED HERE, on the live book's own symbols:

    pearson         the baseline the allocator already uses, so the others have a reference
    stress_corr     correlation conditioned on the WORST decile of a common factor -- dependence
                    when it costs something, which is the only time it is priced
    lower_tail      P(B in its worst decile | A in its worst decile). A coincidence rate, not a
                    coefficient: 0.10 is independence, 1.00 is the same bet twice
    co_drawdown     P(both negative on the same bar) against what independence would give
    mutual_info     binned MI, which catches monotone-but-nonlinear and V-shaped dependence that
                    Pearson scores at zero

THE ROW THAT MATTERS IS `tail_lift` -- lower-tail coincidence divided by what independence
predicts. A pair at pearson 0.04 and tail_lift 4.0 is the dangerous kind: it LOOKS like breadth,
is bought as breadth, and is not breadth when the book is under water.

MEASURED ON SLEEVE RETURNS, NOT ON INSTRUMENT PRICES, and the first version of this file got that
wrong. It read `{symbol}_H1.parquet` closes directly, which sounds equivalent and is not: two
sleeves on the same symbol trading opposite directions have IDENTICAL instrument returns and
OPPOSITE sleeve returns, so a price-based estimate collapses every sleeve on a symbol into one
series and reports the book as far less diverse than it is -- or, when the directions agree,
far more. The desk's dependence numbers have to come from the same projection the allocator
sizes on, which is `research.portfolio_projection.build_sleeves` / `build_daily`.

That provenance is FENCED: `scripts/check_moneypath_fence.py` requires this file to carry
`research.portfolio_projection`, and the pre-commit guard's marker-strip layer restored the box's
copy every time the rewrite tried to land -- correctly, and for a day, while the adoption blamed
NTFS corruption. The fence was right and the rewrite was wrong. The instrument path survives only
as an explicitly-labelled FALLBACK for when the projection yields nothing, and the artifact says
which basis produced it rather than letting the two look alike.

IT PUBLISHES, IT DOES NOT RESIZE. Nothing here feeds the allocator: a dependence estimate that
silently shrank the book would be a growth cut with no missed-growth ledger line behind it. The
CEO docket decides what to do with a high tail lift, on this evidence.

    python desks/mt5/research/orthogonality.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "ORTHOGONALITY.json"

#: Bars of shared history. ~9 months of H1 gives roughly 6,000 overlapping observations, so the
#: worst decile still holds ~600 -- enough for a tail coincidence rate to mean something. Shorter
#: windows put the tail estimate on a handful of bars, where it is noise wearing a number.
BARS = 6000

#: The tail. A decile is the standard compromise: deep enough to be the part of the distribution
#: that hurts, populated enough that the conditional rate is estimable.
TAIL_Q = 0.10

#: Bins per axis for mutual information. 6x6 over ~6,000 points keeps ~165 per cell on average,
#: which is where a binned MI estimate stops being dominated by its own discretisation bias.
MI_BINS = 6

#: A pair is flagged when tail dependence exceeds independence by this much. 2.0 means "these two
#: crash together twice as often as chance" -- the point where treating them as separate bets
#: starts to overstate breadth materially rather than marginally.
TAIL_LIFT_FLAG = 2.0


def _live_symbols() -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out


def _sleeve_returns() -> Any:
    """The book's own per-sleeve daily R matrix, from the projection the allocator sizes on.

    THIS IS THE CANONICAL BASIS and the reason `check_moneypath_fence` pins
    `research.portfolio_projection` to this file. Returns a (dates x sleeves) frame, or None when
    the projection cannot be built here -- an absence this module REPORTS rather than papers over
    with prices that answer a different question.
    """
    try:
        import pandas as pd  # noqa: F401

        # QUALIFIED: the DESK-level SUPERSEDED stub shadows the bare name under pytest (see
        # research/allocation.py); `research.` cannot be shadowed.
        from research.portfolio_projection import build_daily, build_sleeves
    except ImportError:
        return None
    try:
        sleeves = build_sleeves()
        if not sleeves:
            return None
        daily = build_daily(sleeves)
    except Exception:
        # A projection that cannot be built is UNMEASURED, not zero (L1.28a). The caller falls
        # back to the instrument basis and the artifact records that it did.
        return None
    return daily if getattr(daily, "shape", (0, 0))[1] >= 2 else None


def _returns(symbol: str) -> Any:
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError):
        return None
    col = next((c for c in ("close", "Close", "c") if c in df.columns), None)
    if col is None or len(df) < 500:
        return None
    s = pd.to_numeric(df[col], errors="coerce")
    s = s[s > 0].tail(BARS)
    if len(s) < 500:
        return None
    r = np.log(s).diff().dropna()
    r.index = s.index[1:]
    return r


def _mutual_info(a: Any, b: Any, bins: int = MI_BINS) -> float:
    """Binned mutual information in nats. Zero means independent given the binning.

    Binned rather than kernel-based on purpose: it needs no bandwidth choice, it is stable at
    this sample size, and its bias is upward and roughly constant across pairs -- so the RANKING
    between pairs, which is what a reader acts on, survives the bias.
    """
    import numpy as np
    try:
        h, _, _ = np.histogram2d(a, b, bins=bins)
    except (ValueError, TypeError):
        return float("nan")
    n = h.sum()
    if n <= 0:
        return float("nan")
    pxy = h / n
    px = pxy.sum(axis=1, keepdims=True)
    py = pxy.sum(axis=0, keepdims=True)
    denom = px @ py
    mask = (pxy > 0) & (denom > 0)
    return float((pxy[mask] * np.log(pxy[mask] / denom[mask])).sum())


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy/pandas unavailable ({exc}) -- UNMEASURED, never 'independent'"}

    # SLEEVES FIRST, ALWAYS. Instrument prices answer a different question -- see the module
    # docstring -- and the basis that produced a number travels with it so the two can never be
    # read as the same measurement.
    basis = "sleeve_returns"
    min_rows = 60                       # daily R rows; a year of trading is ~250
    frame = _sleeve_returns()
    if frame is None:
        basis = "instrument_returns_FALLBACK"
        min_rows = 500                  # hourly bars
        series = {}
        for s in _live_symbols():
            r = _returns(s)
            if r is not None:
                series[s] = r
        if len(series) < 2:
            return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                    "basis": basis, "n_symbols": len(series),
                    "why": ("the sleeve projection yielded nothing and fewer than two live "
                            "symbols have usable history -- dependence between one thing and "
                            "nothing is not a measurement (L1.28a)")}
        frame = pd.DataFrame(series)
    frame = frame.dropna(how="all").dropna()
    if len(frame) < min_rows or frame.shape[1] < 2:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED", "basis": basis,
                "why": f"only {len(frame)} overlapping row(s) across {frame.shape[1]} series "
                       f"on the {basis} basis"}

    cols = list(frame.columns)
    # `basis` is threaded into every return below rather than added at the end, because a
    # dependence number whose provenance is optional is a dependence number nobody can audit.
    # THE COMMON FACTOR IS THE BOOK'S OWN AVERAGE MOVE. Conditioning stress on it, rather than on
    # each pair separately, asks the question the book actually faces: when the whole book is
    # having a bad bar, do these two move together?
    common = frame.mean(axis=1)
    stress = frame[common <= common.quantile(TAIL_Q)]

    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            x, y = frame[a].to_numpy(), frame[b].to_numpy()
            pear = float(np.corrcoef(x, y)[0, 1])
            sc = (float(np.corrcoef(stress[a].to_numpy(), stress[b].to_numpy())[0, 1])
                  if len(stress) > 30 else float("nan"))
            qa, qb = frame[a].quantile(TAIL_Q), frame[b].quantile(TAIL_Q)
            in_a = frame[a] <= qa
            both = float((in_a & (frame[b] <= qb)).sum())
            n_a = float(in_a.sum())
            lower_tail = both / n_a if n_a else float("nan")
            # Under independence the conditional rate is just TAIL_Q, so the lift is the whole
            # story: 1.0 is chance, 4.0 is four times chance.
            lift = lower_tail / TAIL_Q if TAIL_Q and not math.isnan(lower_tail) else float("nan")
            co_dd = float(((frame[a] < 0) & (frame[b] < 0)).mean())
            mi = _mutual_info(x, y)
            pairs.append({
                "a": a, "b": b,
                "pearson": round(pear, 4),
                "stress_corr": None if math.isnan(sc) else round(sc, 4),
                "lower_tail": None if math.isnan(lower_tail) else round(lower_tail, 4),
                "tail_lift": None if math.isnan(lift) else round(lift, 3),
                "co_drawdown": round(co_dd, 4),
                "mutual_info_nats": None if math.isnan(mi) else round(mi, 5),
                # The dangerous shape, named rather than left for a reader to spot: low linear
                # correlation and high tail coincidence.
                "hidden_dependence": bool(abs(pear) < 0.15
                                          and not math.isnan(lift) and lift >= TAIL_LIFT_FLAG),
            })

    pairs.sort(key=lambda p: (p["tail_lift"] is None, -(p["tail_lift"] or 0)))
    hidden = [p for p in pairs if p["hidden_dependence"]]
    mean_pear = sum(abs(p["pearson"]) for p in pairs) / len(pairs) if pairs else 0.0
    lifts = [p["tail_lift"] for p in pairs if p["tail_lift"] is not None]
    mean_lift = sum(lifts) / len(lifts) if lifts else None

    # n_eff computed two ways, which is the whole argument in one line.
    n = len(cols)
    neff_linear = n / (1 + (n - 1) * mean_pear) if mean_pear > -1 / max(n - 1, 1) else None
    tail_rho = (mean_lift * TAIL_Q) if mean_lift is not None else None
    neff_tail = (n / (1 + (n - 1) * tail_rho)) if tail_rho else None

    return {
        "at": now.isoformat(timespec="seconds"),
        # WHAT THE NUMBERS WERE COMPUTED ON. `sleeve_returns` is the canonical basis -- the same
        # projection the allocator sizes against -- and `instrument_returns_FALLBACK` means the
        # projection yielded nothing and these are PRICE dependences, which conflate every sleeve
        # on a symbol into one series. A reader who cannot tell the two apart cannot use either.
        "basis": basis,
        "n_symbols": n, "n_pairs": len(pairs), "bars": len(frame),
        "tail_quantile": TAIL_Q,
        "mean_abs_pearson": round(mean_pear, 4),
        "mean_tail_lift": None if mean_lift is None else round(mean_lift, 3),
        "n_hidden_dependence": len(hidden),
        "hidden_dependence_pairs": hidden[:20],
        "n_eff_linear": None if neff_linear is None else round(neff_linear, 2),
        "n_eff_tail_implied": None if neff_tail is None else round(neff_tail, 2),
        "pairs": pairs[:80],
        "status": "ATTENTION" if hidden else "OK",
        "the_point": (
            "n_eff_linear is what the allocator sizes on. n_eff_tail_implied is what the book "
            "would behave like if dependence in the worst decile were the dependence that "
            "mattered. Where the second is materially smaller, the desk is buying breadth it "
            "does not own -- and it finds out in the one week it cannot afford to."),
        "boundary": ("PUBLISHES, NEVER RESIZES. A dependence estimate that silently shrank the "
                     "book would be a growth cut with no missed-growth ledger line behind it. "
                     "What to do about a high tail lift is the CEO docket's decision."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") == "UNMEASURED":
        print(f"orthogonality: UNMEASURED -- {str(doc.get('why'))[:150]}")
    else:
        print(f"orthogonality: {doc['status']}   {doc['n_symbols']} live symbol(s), "
              f"{doc['n_pairs']} pair(s), {doc['bars']} shared bars")
        print(f"  mean |pearson| {doc['mean_abs_pearson']}   mean tail lift "
              f"{doc['mean_tail_lift']}")
        print(f"  n_eff linear   {doc['n_eff_linear']}   n_eff if the TAIL is what binds "
              f"{doc['n_eff_tail_implied']}")
        if doc["n_hidden_dependence"]:
            print(f"  HIDDEN DEPENDENCE -- {doc['n_hidden_dependence']} pair(s) look uncorrelated "
                  f"and crash together:")
            for p in doc["hidden_dependence_pairs"][:8]:
                print(f"     {p['a']:<9} {p['b']:<9} pearson {p['pearson']:+.3f}  "
                      f"tail lift {p['tail_lift']}x")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
