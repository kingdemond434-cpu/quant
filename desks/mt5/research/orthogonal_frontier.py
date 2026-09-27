#!/usr/bin/env python3
"""THE ORTHOGONAL FRONTIER, EMITTED: structured hypotheses for the cells the desk never asked.

    python desks/mt5/research/orthogonal_frontier.py            # report only, donates nothing
    python desks/mt5/research/orthogonal_frontier.py --apply    # donate through proposer_common

WHY (audit 2026-09-25). 20,900 judged cells, every certificate H1/asia. Judged outside the banned
family: FX majors 1,109, FX exotics 905, indices 423, crypto CFDs 252, gold 167, softs 97,
energy 93, base metals/PGM 70, silver 67, bonds 18. H4/D1/W1 effectively untested. And several
registered, price-only families that ARE the textbook orthogonal premia had no emitter at all:
nobody ever asked the gauntlet whether time-series momentum pays on a daily index, whether an FX
pair's rank against its peers predicts it, or whether the month-turn flow exists in softs.

A registered family with no row in the docket is a mechanism the judge can never reach -- the
same defect as having no family, one layer further out (III.16). This organ writes those rows.

WHAT IT EMITS -- one EXACT recipe per (family, instrument, chart), each on a chart it can mean:

  (a) time-series trend      multi_speed_trend, trend_ma_cross    D1, H4   index bond energy soft
                                                                           gold silver metal
  (b) cross-sectional rank   cross_sectional (momentum), a named  D1, H4   fx_major fx_cross
                             FX peer panel carried on the row
  (c) style premia           style_premia: trend momentum value   D1       fx_major fx_cross gold
                             carry defensive (D1), volatility (H1) / H1    silver index energy
                                                                           soft bond
  (d) index clock effects    overnight_drift; monday_gap momentum H1       index
                             and fade
  (e) relative value         relative_value on four economic pairs H4, D1  AUDUSD/NZDUSD,
                             (both legs as the traded instrument)          US500/NAS100,
                                                                           GER40/EUSTX50,
                                                                           XAUUSD/XAGUSD
  (f) calendar flow          turn_of_month                        H1, D1   soft bond index

`calendar_month` is DELIBERATELY NOT ENUMERATED: its own docstring says "the month and direction
are source evidence, not searched parameters", so a 12x2 grid here would be exactly the search it
refuses. It is fed by the seasonality source, which names both.

WHAT IT IS NOT. Not a screen and not a judge: every row goes to the ordinary ten gates through the
compiler (EXACT_RECIPE) and the docket, and pays its own trial there. Symbols come from
MetaTrader's registry through `universe_policy` and `sweep_breadth.research_bucket` -- never a
hand list -- except the four RV pairs, whose economics (a shared factor) is the hypothesis. A cell
whose chart is not on this box is NOT emitted and is named in the report, because a row the
gauntlet would refuse at gate 0 for a missing parquet is a data gap, not a hypothesis.

CADENCE. Rows are donated when the grid changes, and in full every `REDONATE_DAYS` so they stay
inside the compiler's seven-day window; an unchanged grid inside that window donates nothing,
because re-donating identical rows every hour is intake noise with a new timestamp.

Artifact: desks/mt5/reports/ORTHOGONAL_FRONTIER.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
INTEL = DESK / "data" / "intelligence"
REPORT = DESK / "reports" / "ORTHOGONAL_FRONTIER.json"
SOURCE = "orthogonal_frontier"
#: The compiler reads seven days of intake; a full re-donation every five keeps every row inside
#: that window with two days of slack for a missed pass.
REDONATE_DAYS = 5.0

TREND_BUCKETS = ("index", "bond", "energy", "soft", "gold", "silver", "metal")
XS_PANEL_BUCKETS = ("fx_major", "fx_cross")
STYLE_BUCKETS = ("fx_major", "fx_cross", "gold", "silver", "index", "energy", "soft", "bond")
CALENDAR_BUCKETS = ("soft", "bond", "index")

#: style -> the chart on which the family's inline bar counts ARE the published definition.
STYLE_CHART = {"trend": "D1", "momentum": "D1", "value": "D1", "carry": "D1",
               "defensive": "D1", "volatility": "H1"}

#: Cross-sectional horizon per chart, in that chart's bars: ~one month on D1, ~one week on H4.
XS_PARAMS = {"D1": {"horizon": 20, "ttl_bars": 20, "cooldown_bars": 5},
             "H4": {"horizon": 30, "ttl_bars": 30, "cooldown_bars": 6}}

#: Economic pairs: one shared factor, so the residual is the claim. Both legs are traded.
RV_PAIRS = (("AUDUSD", "NZDUSD"), ("US500", "NAS100"), ("GER40", "EUSTX50"),
            ("XAUUSD", "XAGUSD"))

MECHANISM = {
    "multi_speed_trend": ("time-series momentum: slow-moving capital and underreaction make a "
                          "vol-scaled multi-horizon trend persist; the payer is the late "
                          "rebalancer and the hedger who must transact against the move"),
    "trend_ma_cross": ("trend persistence on a slow chart: an EMA cross marks a regime the "
                       "underreacting holder has not yet repriced"),
    "cross_sectional": ("cross-sectional momentum: an FX pair displaced furthest against its "
                        "peers keeps outrunning them as the flow that displaced it continues; a "
                        "claim about dispersion, not direction, so it is short what trend "
                        "families are long on a dollar day"),
    "style_premia": ("an AQR style premium harvested on a CFD: compensation for a risk or a "
                     "constraint (carry, value, momentum, low-beta, trend, volatility) that "
                     "other participants cannot or will not bear"),
    "overnight_drift": ("index overnight vs intraday: the overnight return is earned by holders "
                        "who bear the close-to-open gap risk and is faded by the cash session"),
    "monday_gap": ("the weekend gap on an index: two days of information priced in one print, "
                   "followed or faded by the Monday cash session"),
    "relative_value": ("two instruments sharing one factor: the residual after differencing it "
                       "away mean-reverts when the shared factor reasserts itself"),
    "turn_of_month": ("month-end rebalancing and salary flow: a calendar-dated forced "
                      "participant, independent of what price did"),
}


def _bucket(sym: str) -> str:
    try:
        from research.sweep_breadth import research_bucket
    except ImportError:                                   # pragma: no cover - path-dependent
        from sweep_breadth import research_bucket  # type: ignore[no-redef]
    return research_bucket(sym)


def _registry() -> list[str]:
    try:
        doc = json.loads((UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(str(k) for k, v in doc.items() if isinstance(v, dict))


def _may_hypothesise(sym: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except ImportError:                                   # pragma: no cover - path-dependent
        from universe_policy import may_hypothesise  # type: ignore[no-redef]
    try:
        return bool(may_hypothesise(sym))
    except Exception:
        return False


def _has_chart(sym: str, tf: str) -> bool:
    return (UNI / f"{sym}_{tf}.parquet").exists()


def _overrides(family: str, tf: str) -> dict[str, int]:
    """The family's WALL-CLOCK defaults re-expressed on `tf` (`families_orthogonal`)."""
    try:
        from mt5desk import families_orthogonal as fo
        return dict(fo.timeframe_overrides(family, tf))
    except Exception:
        return {}


def _domain_ok(family: str, tf: str) -> bool:
    try:
        from mt5desk import families_orthogonal as fo
        return fo.timeframe_refusal(family, tf) is None
    except Exception:
        return True


def grid(symbols: list[str] | None = None,
         has_chart=_has_chart) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every row this organ would emit, and what it could not (chart absent, off-domain)."""
    syms = [s for s in (symbols if symbols is not None else _registry()) if _may_hypothesise(s)]
    by_bucket: dict[str, list[str]] = {}
    for s in syms:
        by_bucket.setdefault(_bucket(s), []).append(s)
    rows: list[dict[str, Any]] = []
    gaps: dict[str, int] = {}

    def emit(sym: str, family: str, tf: str, params: dict[str, Any], why: str) -> None:
        if not _domain_ok(family, tf):
            gaps[f"off_domain:{family}@{tf}"] = gaps.get(f"off_domain:{family}@{tf}", 0) + 1
            return
        if not has_chart(sym, tf):
            gaps[f"chart_absent:{tf}"] = gaps.get(f"chart_absent:{tf}", 0) + 1
            return
        p = {**_overrides(family, tf), **params, "timeframe": tf}
        rows.append({"symbol": sym, "family": family, "params": p,
                     "mechanism": MECHANISM.get(family, family),
                     "title": f"{family} on {sym} {tf} -- {why}",
                     "bucket": _bucket(sym), "chart": tf})

    def members(buckets: tuple[str, ...]) -> list[str]:
        return sorted(s for b in buckets for s in by_bucket.get(b, []))

    for sym in members(TREND_BUCKETS):
        for tf in ("D1", "H4"):
            emit(sym, "multi_speed_trend", tf, {}, "time-series trend on a slow chart")
            emit(sym, "trend_ma_cross", tf, {}, "time-series trend on a slow chart")

    panel = members(XS_PANEL_BUCKETS)
    for tf, xp in XS_PARAMS.items():
        peers = [s for s in panel if has_chart(s, tf)]
        if len(peers) < 10:
            gaps[f"panel_too_small:{tf}"] = len(peers)
            continue
        for sym in peers:
            emit(sym, "cross_sectional", tf,
                 {**xp, "mode": "momentum", "peer_symbols": peers},
                 f"rank against a {len(peers)}-pair FX panel")

    for sym in members(STYLE_BUCKETS):
        for style, tf in STYLE_CHART.items():
            emit(sym, "style_premia", tf, {"style": style}, f"{style} premium")

    for sym in members(("index",)):
        emit(sym, "overnight_drift", "H1", {}, "index overnight vs intraday")
        emit(sym, "monday_gap", "H1", {"mode": "momentum"}, "weekend gap followed")
        emit(sym, "monday_gap", "H1", {"mode": "fade"}, "weekend gap faded")

    known = set(syms)
    for a, b in RV_PAIRS:
        if a not in known or b not in known:
            gaps[f"rv_pair_absent:{a}/{b}"] = 1
            continue
        for sym, peer in ((a, b), (b, a)):
            for tf in ("H4", "D1"):
                if not has_chart(peer, tf):
                    gaps[f"chart_absent:{tf}"] = gaps.get(f"chart_absent:{tf}", 0) + 1
                    continue
                emit(sym, "relative_value", tf, {"peer_symbol": peer},
                     f"residual against {peer}")

    for sym in members(CALENDAR_BUCKETS):
        for tf in ("H1", "D1"):
            emit(sym, "turn_of_month", tf, {}, "month-turn flow")

    return rows, gaps


def _cell_key(r: dict[str, Any]) -> str:
    return json.dumps({"s": r["symbol"], "f": r["family"], "p": r["params"]},
                      sort_keys=True, default=str)


def _grid_digest(rows: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for k in sorted(_cell_key(r) for r in rows):
        h.update(k.encode())
    return h.hexdigest()[:16]


def _last_donation(intel: Path = INTEL) -> tuple[float | None, str | None]:
    """(age in days, grid digest) of this organ's newest donation, or (None, None)."""
    files = sorted((intel / SOURCE).glob("discoveries_*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, None
    newest = files[0]
    age = (time.time() - newest.stat().st_mtime) / 86400.0
    try:
        doc = json.loads(newest.read_text("utf-8"))
        return age, str(doc.get("grid_digest") or "") or None
    except (OSError, ValueError):
        return age, None


def run(apply: bool, now: datetime | None = None) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    rows, gaps = grid()
    digest = _grid_digest(rows)
    age, last_digest = _last_donation()
    due = age is None or age >= REDONATE_DAYS or last_digest != digest
    by: dict[str, int] = {}
    for r in rows:
        k = f"{r['family']}|{r['bucket']}|{r['chart']}"
        by[k] = by.get(k, 0) + 1
    doc: dict[str, Any] = {
        "at": at, "status": "OK", "n_rows": len(rows), "grid_digest": digest,
        "by_family_bucket_chart": dict(sorted(by.items())), "not_emitted": gaps,
        "last_donation_age_days": None if age is None else round(age, 2),
        "donation_due": due, "donated": 0, "path": None,
        "rule": ("one EXACT recipe per (family, instrument, chart) for the orthogonal cells the "
                 "desk never asked; each pays its own trial at the ten gates. Donated when the "
                 "grid changes and in full every REDONATE_DAYS, never hourly."),
    }
    if apply and due and rows:
        from research import proposer_common
        payload = [{k: v for k, v in r.items() if k not in ("bucket", "chart")} for r in rows]
        path = proposer_common.donate(SOURCE, payload, tests_run=len(payload))
        if path is not None:
            try:
                d = json.loads(path.read_text("utf-8"))
                d["grid_digest"] = digest
                path.write_text(json.dumps(d, indent=1, default=str), "utf-8")
            except (OSError, ValueError):
                pass
        doc["donated"] = int((proposer_common.LAST_DONATION or {}).get("donated") or 0)
        doc["refused_wrong_lane"] = int(
            (proposer_common.LAST_DONATION or {}).get("refused_wrong_lane") or 0)
        doc["path"] = str(path) if path else None
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="donate the rows")
    a = ap.parse_args(argv)
    doc = run(a.apply)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"orthogonal frontier: {doc['n_rows']} row(s) across "
          f"{len(doc['by_family_bucket_chart'])} family x bucket x chart cell(s); "
          f"not emitted {doc['not_emitted']}; due={doc['donation_due']} "
          f"donated={doc['donated']} -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
