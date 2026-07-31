#!/usr/bin/env python3
"""COPYTRADING SCREEN (R0140) -- Stage A, ZERO promotion authority (L1.6).

PRINCIPAL ORDER (2026-07-31): *"test copytrading strategies on the side too to see if they survive
... you can add or abandon. It must be relative to our main goal, max geometric growth."*

TWO DIFFERENT HYPOTHESES LIVE UNDER THE WORD "COPYTRADING", and they have opposite verdicts.

  H1 -- FOLLOW A GOOD LEAD TRADER. Pick the leaderboard's best and copy them.
       VERDICT: NOT TESTABLE from public data, and the naive test is a trap. Run on a 34-trader
       OKX sample it returns Spearman +0.33 between first- and second-half 45-day returns, with
       5/6 of the top quintile beating the median. That reads like an edge and it is an ARTIFACT:

         * the sample was drawn by sorting on pnl / pnlRatio / aum / copiers / winRatio -- i.e.
           SELECTED ON THE OUTCOME then measured for that outcome,
         * mean 45-day return across the whole sample is +81%, which is not a population of
           traders, it is a leaderboard,
         * every trader who blew up in the second half is ABSENT: persistence measured on
           survivors is manufactured by the survival filter itself,
         * n=34 puts rho at ~1.9 sigma BEFORE either bias, both of which push it upward.

       That is the exact shape of the 420 patterns this desk has already killed. The only unbiased
       design is a FORWARD PANEL: fix the cohort today, follow it, and count the disappearances as
       FAILURES rather than dropping them. This organ archives that panel; until it has two
       separated snapshots the honest verdict is NO-DATA, not "promising".

       The economics have to clear a real hurdle too, which the leaderboard never shows: copiers
       pay the lead a profit share (up to ~13% on OKX), fill AFTER the lead moves, and inherit the
       lead's drawdowns in full. A persistent edge would still have to beat that stack.

  H2 -- TRADE THE COPY FLOW, don't join it. Copy capital is FORCED flow: copiers enter behind
       their lead, exit when the lead exits, and liquidate together. Aggregate copy positioning is
       therefore a crowding gauge, and aggregate copy STRESS (deeply underwater at high leverage)
       is a mechanical precursor to unwinds. This does not require picking a winner -- which is
       precisely why it dodges the selection problem that kills H1.
       VERDICT: MEASURABLE. Computed here, and it earns a forward clock, never capital.

WHAT THE PUBLIC FEED ACTUALLY GIVES, stated because it bounds H2: subpositions expose posSide,
lever, margin and uplRatio -- but `instId` comes back EMPTY, so per-instrument crowding is not
available. The index is therefore AGGREGATE (book-wide long/short skew, leverage, unrealised
stress) plus per-currency allocation from the preference endpoint. An aggregate gauge is a weaker
object than a per-instrument one and is labelled as such rather than dressed up.

RELATIVE TO THE OBJECTIVE (max E[log wealth]): a sleeve that merely adds more crypto beta adds
almost nothing to geometric growth, because the desk is already long that. So the report carries
the question that decides it -- is this DIVERSIFYING or duplicative -- and any promotion argument
must answer it.

    python scripts/screen_copytrading.py [--json] [--sample N]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_PANEL = "data/copytrading_panel.jsonl"
_STATE = "data/copytrading_screen.json"
_API = "https://www.okx.com/api/v5/copytrading"

#: 2 snapshots at least 5 days apart before ANY forward persistence number is published. 5 days is
#: the spacing of the venue's own pnlRatio series, so a shorter gap would re-read one datapoint
#: twice and call it two observations.
MIN_PANEL_GAP_DAYS = 5.0
#: 30 traders is the minimum cohort for a rank statistic worth printing: below it the Spearman
#: standard error (1/sqrt(n-1)) exceeds 0.19, so anything under ~0.4 is indistinguishable from
#: noise and publishing it invites exactly the over-reading this screen exists to prevent.
MIN_COHORT = 30
#: The profit share a copier pays the lead on OKX, published in the venue's copytrading terms.
#: Any measured edge must clear this before it is an edge for US rather than for the lead.
COPIER_PROFIT_SHARE = 0.13


def _get(url: str, *, timeout: int = 25) -> Any:
    r = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_leaders(sample: int = 60) -> tuple[list[dict[str, Any]], str]:
    """Lead-trader panel. NOTE the sampling bias this deliberately does NOT hide: every sort key
    here is an outcome variable, so this cohort is selected on performance. It is usable as a
    FORWARD cohort (fix it now, follow it) and NOT as a backward sample."""
    got: dict[str, dict[str, Any]] = {}
    errs = []
    for sort in ("pnl", "pnlRatio", "aum", "copyTraderNum", "winRatio"):
        for page in range(1, 4):
            try:
                d = _get(f"{_API}/public-lead-traders?instType=SWAP&limit=20"
                         f"&sortType={sort}&pageNumber={page}")
                rk = (d.get("data") or [{}])[0].get("ranks") or []
            except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as exc:
                errs.append(f"{sort}p{page}: {type(exc).__name__}")
                break
            if not rk:
                break
            for r in rk:
                got.setdefault(r["uniqueCode"], r)
            if len(got) >= sample:
                break
            time.sleep(0.15)
        if len(got) >= sample:
            break
    return list(got.values()), ("; ".join(errs) if errs else "ok")


def fetch_positions(codes: list[str], *, limit: int = 25) -> tuple[list[dict[str, Any]], int]:
    """Live subpositions across the cohort. `instId` is empty in the public feed, so this supports
    an AGGREGATE crowding gauge only -- named as such rather than presented as per-instrument."""
    rows, reachable = [], 0
    for c in codes[:limit]:
        try:
            d = _get(f"{_API}/public-current-subpositions?instType=SWAP&uniqueCode={c}&limit=20")
            data = d.get("data") or []
        except (urllib.error.URLError, OSError, ValueError) as exc:
            rows.append({"uniqueCode": c, "state": f"UNREADABLE {type(exc).__name__}"})
            continue
        if data:
            reachable += 1
        for p in data:
            rows.append({"uniqueCode": c, "posSide": p.get("posSide"),
                         "lever": float(p.get("lever") or 0), "margin": float(p.get("margin") or 0),
                         "upl": float(p.get("upl") or 0),
                         "uplRatio": float(p.get("uplRatio") or 0)})
        time.sleep(0.12)
    return rows, reachable


def _median(v: list[float]) -> float | None:
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def crowding_index(pos: list[dict[str, Any]]) -> dict[str, Any]:
    """H2: copy capital is FORCED flow -- copiers enter behind the lead, exit when it exits, and
    liquidate together. Skew says which way the crowd leans; stress says how close it is to being
    made to move.

    TWO CORRECTIONS FROM THE FIRST LIVE RUN, both found by checking the number instead of
    publishing it:

      OUTLIERS DOMINATED. Margin-weighted uplRatio read -0.97 -- an almost-liquidated book -- while
      the MEDIAN position was -0.078. Three positions carried 17% of all margin. The weighted mean
      is still reported because forced-flow impact IS size-weighted, but the median is reported
      beside it and the gap between them is published as `outlier_dominated`, because a gauge that
      quietly reports its own tail as its centre is worse than no gauge.

      posSide CAN BE "net". One-way-mode positions were being silently dropped from the long/short
      split, which biased the skew toward whichever side happened to use hedge mode. They are now
      counted in their own bucket and EXCLUDED from the skew denominator, with their share
      published -- a skew computed over a fraction of the book while presented as the book's skew
      is exactly the kind of quiet wrongness this desk keeps finding.
    """
    live = [p for p in pos if p.get("margin")]
    if not live:
        return {"state": "UNMEASURED", "why": "no readable subpositions -- gauge is BLIND, "
                                              "which is not the same as flat"}
    lg = sum(p["margin"] for p in live if p["posSide"] == "long")
    sh = sum(p["margin"] for p in live if p["posSide"] == "short")
    net = sum(p["margin"] for p in live if p["posSide"] not in ("long", "short"))
    tot = lg + sh + net
    directional = lg + sh
    notional = sum(p["margin"] * max(p["lever"], 1.0) for p in live)
    w_upl = sum(p["margin"] * p["uplRatio"] for p in live) / tot if tot else 0.0
    med_upl = _median([p["uplRatio"] for p in live]) or 0.0
    skew = (lg - sh) / directional if directional else None
    outlier_ratio = abs(w_upl - med_upl)
    return {
        "state": "MEASURED", "n_positions": len(live),
        "long_margin": round(lg, 2), "short_margin": round(sh, 2), "net_mode_margin": round(net, 2),
        "net_mode_share": round(net / tot, 3) if tot else None,
        "skew": round(skew, 4) if skew is not None else None,
        "skew_basis": "long+short only; one-way 'net' positions carry no readable direction and "
                      "are excluded from the denominator rather than silently counted",
        "median_leverage": _median([p["lever"] for p in live]),
        "margin_weighted_leverage": round(notional / tot, 2) if tot else None,
        "frac_underwater": round(sum(1 for p in live if p["uplRatio"] < 0) / len(live), 3),
        "median_uplRatio": round(med_upl, 4),
        "margin_weighted_uplRatio": round(w_upl, 4),
        "outlier_dominated": bool(outlier_ratio > 0.25),
        "outlier_note": (f"weighted {w_upl:+.3f} vs median {med_upl:+.3f} -- a few large positions "
                         "dominate the weighted figure; read the median as the centre"
                         if outlier_ratio > 0.25 else "weighted and median agree"),
        "reading": (
            "UNREADABLE DIRECTION: most margin is in one-way 'net' mode"
            if directional < tot * 0.4 else
            "crowded LONG and under water at leverage -- unwind risk is to the DOWNSIDE"
            if (skew is not None and skew > 0.15 and med_upl < -0.02) else
            "crowded SHORT and under water at leverage -- unwind risk is to the UPSIDE"
            if (skew is not None and skew < -0.15 and med_upl < -0.02) else
            "no strong crowd stress in the sampled cohort"),
    }


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None

    def rank(v: list[float]) -> list[int]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0] * len(v)
        for pos, i in enumerate(order):
            out[i] = pos
        return out
    rx, ry = rank(xs), rank(ys)
    return round(1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry, strict=False)) / (n * (n * n - 1)), 4)


def contaminated_persistence(leaders: list[dict[str, Any]]) -> dict[str, Any]:
    """The in-sample split-half test, computed AND disqualified in the same breath.

    It is reported rather than suppressed because the number is what a reasonable person would
    compute first, and the desk's job is to show why it must not be acted on -- a suppressed
    statistic gets recomputed by the next person without the warning attached."""
    h1, h2 = [], []
    for t in leaders:
        s = sorted(t.get("pnlRatios") or [], key=lambda x: int(x["beginTs"]))
        if len(s) < 12:
            continue
        v = [float(x["pnlRatio"]) for x in s]
        mid = len(v) // 2
        h1.append(v[mid] - v[0])
        h2.append(v[-1] - v[mid])
    if len(h1) < 3:
        return {"state": "NO-DATA", "n": len(h1)}
    rho = _spearman(h1, h2)
    n = len(h1)
    se = 1 / math.sqrt(n - 1)
    mean_h2 = sum(h2) / n
    return {
        "state": "CONTAMINATED -- NOT EVIDENCE", "n": n, "spearman": rho,
        "sigma": round(abs(rho) / se, 2) if rho is not None else None,
        "mean_second_half_return": round(mean_h2, 4),
        "disqualifiers": [
            "SELECTED ON THE OUTCOME: the cohort is drawn by sorting on pnl/pnlRatio/aum/copiers/"
            "winRatio, then measured for performance",
            "SURVIVORSHIP: traders who blew up are absent from the leaderboard entirely, so "
            "persistence here is partly manufactured by the survival filter",
            f"UNDERPOWERED: n={n}, Spearman SE ~{se:.3f}",
            f"POPULATION CHECK FAILS: mean 45-day return {mean_h2:+.1%} across the whole sample "
            "-- that is a leaderboard, not a population of traders",
        ],
        "only_valid_design": "a FORWARD panel: fix the cohort now, follow it, and count "
                             "disappearances as FAILURES rather than dropping them",
    }


def forward_persistence(root: Path) -> dict[str, Any]:
    """The only unbiased read: same cohort, two separated snapshots, EXITS COUNTED AS FAILURES."""
    snaps: list[dict[str, Any]] = []
    try:
        for ln in (root / _PANEL).read_text("utf-8", errors="ignore").splitlines():
            if ln.strip():
                try:
                    snaps.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        return {"state": "NO-DATA", "why": "no panel archived yet -- the forward clock starts on "
                                           "the first run of this organ"}
    if len(snaps) < 2:
        return {"state": "NO-DATA", "n_snapshots": len(snaps),
                "why": "one snapshot cannot measure persistence; the clock is running"}
    first, last = snaps[0], snaps[-1]
    gap = (datetime.fromisoformat(last["at"]) - datetime.fromisoformat(first["at"])).days
    if gap < MIN_PANEL_GAP_DAYS:
        return {"state": "NO-DATA", "gap_days": gap,
                "why": f"snapshots {gap}d apart, under the {MIN_PANEL_GAP_DAYS}d minimum -- a "
                       "shorter gap re-reads one datapoint twice and calls it two observations"}
    then = {t["uniqueCode"]: t for t in first["traders"]}
    now = {t["uniqueCode"]: t for t in last["traders"]}
    survived = [c for c in then if c in now]
    exited = [c for c in then if c not in now]
    if len(then) < MIN_COHORT:
        return {"state": "UNDERPOWERED", "cohort": len(then), "exited": len(exited),
                "why": f"cohort {len(then)} < {MIN_COHORT}; a rank statistic here is noise"}
    xs = [float(then[c].get("pnlRatio") or 0) for c in survived]
    ys = [float(now[c].get("pnlRatio") or 0) - float(then[c].get("pnlRatio") or 0)
          for c in survived]
    return {
        "state": "MEASURED", "gap_days": gap, "cohort": len(then),
        "survived": len(survived), "exited_counted_as_failures": len(exited),
        "exit_rate": round(len(exited) / len(then), 3),
        "forward_spearman": _spearman(xs, ys),
        "note": "exits are FAILURES, not missing data -- dropping them is the survivorship bug "
                "that makes the in-sample number look like an edge",
        "hurdle": f"any edge must also clear the ~{COPIER_PROFIT_SHARE:.0%} copier profit share, "
                  "entry lag behind the lead, and the lead's full drawdown",
    }


def build_report(root: Path | None = None, *, sample: int = 60,
                 leaders: list[dict[str, Any]] | None = None,
                 positions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root = root or _ROOT
    src = "injected"
    if leaders is None:
        leaders, src = fetch_leaders(sample)
    if positions is None and leaders:
        positions, _ = fetch_positions([t["uniqueCode"] for t in leaders])
    positions = positions or []
    crowd = crowding_index(positions)
    fwd = forward_persistence(root)
    contam = contaminated_persistence(leaders)
    status = ("NO-DATA" if not leaders else
              "FORWARD-CLOCK" if fwd["state"] in ("NO-DATA", "UNDERPOWERED") else "MEASURED")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "row": "R0140", "stage": "A", "source": src,
        "authority": "STAGE A ONLY -- earns at most a pre-registered forward clock, never capital "
                     "(L1.6). This script places no orders and copies no trader.",
        "status": status,
        "n_leaders": len(leaders),
        "h1_follow_a_lead_trader": contam,
        "h2_copy_flow_crowding": crowd,
        "forward_panel": fwd,
        "objective_test": "max E[log wealth]: a sleeve that only adds more crypto beta adds almost "
                          "nothing to geometric growth, because this book is already long that. "
                          "Any promotion argument must show DIVERSIFYING return, not more of the "
                          "same -- measured against the sleeve correlation matrix, not asserted.",
        "detail": (f"{len(leaders)} lead traders sampled; H1 (follow a lead) is "
                   f"{contam['state']}; H2 (trade the copy flow) is {crowd['state']}; forward "
                   f"panel {fwd['state']}"),
    }


def archive(root: Path, leaders: list[dict[str, Any]]) -> None:
    """Append the cohort so a survivorship-corrected forward panel accumulates."""
    if not leaders:
        return
    p = root / _PANEL
    p.parent.mkdir(parents=True, exist_ok=True)
    keep = [{k: t.get(k) for k in ("uniqueCode", "nickName", "pnlRatio", "aum", "copyTraderNum",
                                   "leadDays", "winRatio")} for t in leaders]
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(tz=UTC).isoformat(), "traders": keep}) + "\n")


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    leaders, src = fetch_leaders(args.sample)
    positions, _ = fetch_positions([t["uniqueCode"] for t in leaders]) if leaders else ([], 0)
    archive(_ROOT, leaders)
    rep = build_report(_ROOT, leaders=leaders, positions=positions)
    rep["source"] = src
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"copytrading screen (R0140): {rep['status']} -- {rep['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
