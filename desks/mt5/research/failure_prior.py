"""B10 -- THE FAILURE PRIOR THAT CAN CHANGE ITS MIND: P(failure | structure), by era and state.

THE BLUEPRINT ITEM: "learned negative knowledge as a search prior". THE GAP, in the ledger's
words: "failure reasons are logged and generator weights move on fate; no learned
P(failure|structure,data,state) prior that can REOPEN an old failure under new conditions".

Half of it was already built and is not rebuilt here. `libs/research/graveyard_model.py` fits
P(failure class | hypothesis) and P(survivor | hypothesis) by naive Bayes over declared features,
the compiler stamps the pre-mortem, and the deepening queue's VOI order uses P(survivor). What
none of that can do is CHANGE ITS MIND. A region buried in March under a regime that ended in
May is buried forever, because a model fitted on the whole graph averages the two eras together
and reports the pooled failure rate as a fact about the structure. That is how a desk's own
history becomes a cage: every generator learns not to propose what used to fail, and nothing
ever measures whether it still does.

WHAT THIS ADDS, and it is one idea: FIT THE SAME MODEL TWICE.

    lifetime   every judged row in the hypothesis graph
    recent     the rows judged inside RECENT_DAYS

A structure whose survival probability is materially HIGHER in the recent fit than in the
lifetime fit is a REOPEN candidate: the desk's negative knowledge about it was earned under
conditions that have since changed. The state dimension enters by name where it can -- the
instrument's CURRENT regime from `REGIME_HIERARCHY.json` against the era it was buried in -- and
is reported UNMEASURED where it cannot, never guessed.

IT IS A PRIOR AND NEVER A BLACKLIST. Nothing here rejects a candidate, removes a region or
narrows a search. It publishes a multiplier in [MIN_MULT, MAX_MULT] on a candidate's priority
and a list of regions to RE-OPEN, which is the only direction a negative prior may act in on
this desk: failure to discover is never evidence there is nothing to discover (L1.25), and a
search that stopped proposing what it once buried is a cap on discovery wearing the word
"learning".

    python desks/mt5/research/failure_prior.py [--once] [--budget-s N]
        -> desks/mt5/reports/FAILURE_PRIOR.json (+ data/failure_prior.json)
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "FAILURE_PRIOR.json"
TABLE = DESK / "data" / "failure_prior.json"
REGIMES = DESK / "reports" / "REGIME_HIERARCHY.json"

#: The window that counts as "now". Thirty days of judging on this desk is thousands of rows --
#: enough for a family-level rate, never enough for a single region, which is why the prior is
#: built on FEATURES and not on regions.
RECENT_DAYS = 30.0
#: Rows a feature level needs in the recent window before its rate is allowed to differ from the
#: lifetime rate. Below it the level reports UNMEASURED and keeps the lifetime prior.
MIN_RECENT = 20
#: A level is a REOPEN candidate when its recent survival odds are this many times its lifetime
#: odds. Two is deliberately loud: the point is to re-ask, and re-asking is cheap.
REOPEN_ODDS = 2.0
#: The multiplier's range. Symmetric in log space, so the prior can promote exactly as hard as
#: it demotes -- a one-sided prior is a brake with a learning-shaped label on it.
MIN_MULT, MAX_MULT = 0.5, 2.0
#: The features the prior is built on. Every one is DECLARED by the hypothesis row itself; none
#: is inferred from performance, because a feature learned from the outcome would make the prior
#: a restatement of the fate it is supposed to predict.
FEATURES = ("family", "asset_class", "source", "mechanism", "session", "chart", "n_params")


def _parse_at(v: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _odds(p: float) -> float:
    p = min(max(float(p), 1e-6), 1.0 - 1e-6)
    return p / (1.0 - p)


def build(recent_days: float = RECENT_DAYS) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        from libs.research.graveyard_model import GraveyardModel
        from libs.research.hypothesis_graph import Graph
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"graveyard model / hypothesis graph unavailable ({exc})"}
    rows = Graph().rows()
    if not rows:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "the hypothesis graph holds no rows on this box"}
    # THE WINDOW ADAPTS TO THE LEDGER IT HAS (measured 2026-09-23: all 35,209 graph rows on this
    # box are stamped inside the last 30 days, so a fixed 30-day window makes "recent" and
    # "lifetime" the same set and the reopen test can never fire). When the fixed window would
    # swallow most of the ledger, "recent" becomes the most recent TERCILE by timestamp and the
    # comparison is against everything before it. The rule that applied is published.
    stamps = sorted(t for t in ((_parse_at(r.get("at"))) for r in rows) if t is not None)
    cutoff = now - timedelta(days=float(recent_days))
    split_rule = f"fixed window: rows judged since {cutoff.isoformat(timespec='seconds')}"
    if stamps and sum(1 for t in stamps if t >= cutoff) > 0.8 * len(stamps):
        cutoff = stamps[int(len(stamps) * 2 / 3)]
        split_rule = (f"most recent tercile: the fixed {recent_days:.0f}-day window held over "
                      f"80% of the ledger, so 'recent' is everything judged since "
                      f"{cutoff.isoformat(timespec='seconds')} and 'lifetime' is all of it")
    recent_rows = [r for r in rows if (_parse_at(r.get("at")) or now) >= cutoff]

    life = GraveyardModel().fit(rows)
    fresh = GraveyardModel().fit(recent_rows) if recent_rows else None

    by_feature: dict[str, dict[str, Any]] = {}
    reopen: list[dict[str, Any]] = []
    for feat in FEATURES:
        lv = life.survival_by(feat)
        rv = fresh.survival_by(feat) if fresh is not None else {}
        levels: dict[str, Any] = {}
        for level, l_row in lv.items():
            r_row = rv.get(level) or {}
            n_recent = int(r_row.get("certified", 0)) + int(r_row.get("failed", 0))
            p_life = float(l_row["p_survival"])
            p_recent = float(r_row["p_survival"]) if n_recent >= MIN_RECENT else None
            ratio = (_odds(p_recent) / _odds(p_life)) if p_recent is not None else None
            levels[level] = {
                "p_survival_lifetime": round(p_life, 6),
                "p_survival_recent": (round(p_recent, 6) if p_recent is not None else None),
                "n_lifetime": int(l_row["certified"]) + int(l_row["failed"]),
                "n_recent": n_recent,
                "odds_ratio": (round(ratio, 4) if ratio is not None else None),
                "status": "MEASURED" if p_recent is not None else "UNMEASURED_RECENT",
            }
            if ratio is not None and ratio >= REOPEN_ODDS:
                reopen.append({"feature": feat, "level": level, "odds_ratio": round(ratio, 4),
                               "p_survival_lifetime": round(p_life, 6),
                               "p_survival_recent": round(p_recent, 6), "n_recent": n_recent,
                               "why": (f"{feat}={level} now survives at {p_recent:.4f} against "
                                       f"a lifetime {p_life:.4f}; whatever buried it is no "
                                       f"longer what is happening")})
        by_feature[feat] = levels
    reopen.sort(key=lambda r: -float(r["odds_ratio"]))

    pooled = life.summary()
    doc = {
        "at": now.isoformat(timespec="seconds"), "status": "OK",
        "n_rows": len(rows), "n_recent_rows": len(recent_rows), "recent_days": recent_days,
        "split_rule": split_rule,
        "pooled": pooled,
        "by_feature": by_feature,
        "n_reopen": len(reopen), "reopen": reopen[:40],
        "state": _state_note(),
        "multiplier": {"min": MIN_MULT, "max": MAX_MULT,
                       "rule": ("exp of the mean log odds-ratio across a candidate's measured "
                                "features, clipped. A structure the desk has recently begun to "
                                "certify is promoted exactly as hard as one it has recently "
                                "begun to bury is demoted")},
        "boundary": ("a PRIOR, never a blacklist. Nothing here rejects a candidate, removes a "
                     "region or narrows any search: it multiplies a priority and publishes a "
                     "reopen list. A search that stopped proposing what it once buried would be "
                     "a cap on discovery calling itself learning (L1.25)."),
        "consumers": ["desks/mt5/research/miner_candidate_compiler.py (stamps failure_prior and "
                      "reopen on every compiled candidate, beside prior_failures_in_region)"],
    }
    return doc


def _state_note() -> dict[str, Any]:
    """The state half of P(failure | structure, data, state), as far as it is measurable here."""
    rh = _read(REGIMES)
    assets = rh.get("assets") if isinstance(rh.get("assets"), dict) else {}
    if not assets:
        return {"status": "UNMEASURED",
                "why": ("no REGIME_HIERARCHY.json: the era a region was buried in can be read "
                        "from its timestamps, but the STATE it was buried in cannot")}
    return {"status": "MEASURED", "at": rh.get("at"), "n_assets": len(assets),
            "state_now": {k: (v or {}).get("state_now") for k, v in list(assets.items())[:30]},
            "why": ("the recent window is the desk's proxy for 'new conditions'; where the "
                    "per-asset regime is known it names WHICH conditions those are")}


def multiplier_for(row: dict[str, Any], table: dict[str, Any] | None = None
                   ) -> tuple[float, str]:
    """The prior multiplier for one candidate, and the reason. 1.0 when nothing is measured."""
    doc = table if table is not None else _read(TABLE)
    by_feature = doc.get("by_feature") if isinstance(doc.get("by_feature"), dict) else {}
    if not by_feature:
        return 1.0, "no failure prior on disk"
    try:
        from libs.research.graveyard_model import features_of
    except ImportError:
        return 1.0, "graveyard model unavailable"
    feats = features_of(row)
    logs, used = [], []
    for feat, level in feats.items():
        cell = (by_feature.get(feat) or {}).get(str(level))
        if not isinstance(cell, dict) or cell.get("odds_ratio") is None:
            continue
        logs.append(math.log(max(1e-6, float(cell["odds_ratio"]))))
        used.append(f"{feat}={level}:{cell['odds_ratio']}")
    if not logs:
        return 1.0, "no measured feature level for this candidate"
    mult = math.exp(sum(logs) / len(logs))
    mult = min(MAX_MULT, max(MIN_MULT, mult))
    return round(mult, 4), "recent-vs-lifetime survival odds on " + ", ".join(used[:4])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--recent-days", type=float, default=RECENT_DAYS)
    a = ap.parse_args(argv)
    doc = build(recent_days=a.recent_days)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(json.dumps({"at": doc.get("at"),
                                 "by_feature": doc.get("by_feature") or {},
                                 "reopen": doc.get("reopen") or [],
                                 "multiplier": doc.get("multiplier") or {}}, indent=1),
                     encoding="utf-8")
    print(f"failure prior: {doc.get('status')}  {doc.get('n_rows')} judged row(s), "
          f"{doc.get('n_recent_rows')} in the last {doc.get('recent_days')}d; "
          f"{doc.get('n_reopen', 0)} reopen candidate(s)")
    for r in (doc.get("reopen") or [])[:8]:
        print(f"  reopen {r['feature']}={str(r['level'])[:26]:<26} odds x{r['odds_ratio']} "
              f"(n_recent={r['n_recent']})")
    print(f"-> {OUT}; table -> {TABLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
