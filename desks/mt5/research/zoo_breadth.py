#!/usr/bin/env python3
"""JUDGE THE ALPHA ZOO ON EVERY PEER CLASS, AND DONATE THE LEGS OF THE BOOKS THAT SURVIVE.

    python desks/mt5/research/zoo_breadth.py --once [--budget-s 600]
    python desks/mt5/research/zoo_breadth.py --once --dry-run

WHY A CLASS SCREEN FIRST. `mt5desk/family_zoo_alpha.py` makes 317 published alphas (GTJA 191,
Qlib 158, Alpha101, academic) runnable as MT5 class books. Donating every alpha x member leg
would put ~317 x 250 cells on the shared deflation, and each cell raises the bar for every FX
and metals cell. So the unit of trial here is the BOOK: (class, alpha, horizon).
  1. For each peer class and each zoo alpha, compute the alpha on the class's daily panel and
     measure its daily rank IC against the next `h` days' return (open of day t+1 to close of day
     t+h) across members, on non-overlapping days. A day with fewer than MIN_MEMBERS members
     scored is skipped.
  2. The IC's t is deflated by the expected maximum of |t| over every book this organ has ever
     measured, counting both signs (`multiplicity.deflate_t`).
  3. A book whose deflated t is > 0 has its members' legs screened on cost
     (`proposer_common.screen`) and the ones that pay are donated as `zoo_alpha_class` cells, with
     `direction` set to the IC's sign, through the one proposer door into
     `data/intelligence/zoo_breadth/`. Each cell carries its zoo's culture.
Writes `reports/ZOO_BREADTH.json`: books measured, the |t| tail against the null's, survivors,
donations, and per-zoo counts. That is the measured contract the subsystem answers to.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_zoo_alpha as zoo  # noqa: E402

SOURCE = "zoo_breadth"
OUT = BASE / "reports" / "ZOO_BREADTH.json"
STATE = BASE / "data" / "zoo_breadth_state.json"
UNMEASURED = "UNMEASURED"
HORIZONS = (1, 5)
MIN_DAYS_IC = 120
MIN_TRADES = 30
ORIGIN = "github.com/HKUDS/Vibe-Trading agent/src/factors (MIT; Qlib158 Apache-2.0)"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    tmp.replace(path)


def classes() -> dict[str, list[str]]:
    """Peer class -> the members the class book may trade (hypothesis lane, or equity)."""
    from research import proposer_common as pc
    from research import universe_policy as up
    out: dict[str, list[str]] = {}
    for s in pc.universe_meta():
        k = up.peer_class(s)
        if k and up.may_hypothesise(s, "zoo_alpha_class"):
            out.setdefault(k, []).append(s)
    return out


def book_ic(score: pd.DataFrame, panel: dict[str, pd.DataFrame], h: int
            ) -> tuple[float, int] | None:
    """(t of the mean daily rank IC, days used) on non-overlapping days."""
    op, cl = panel["open"], panel["close"]
    fwd = np.log(cl.shift(-h) / op.shift(-1))
    ics = []
    for t in range(0, len(score) - h - 1, h):
        a, b = score.iloc[t], fwd.iloc[t]
        m = a.notna() & b.notna() & np.isfinite(b)
        if int(m.sum()) < zoo.MIN_MEMBERS:
            continue
        ra, rb = a[m].rank(), b[m].rank()
        if ra.std() > 0 and rb.std() > 0:
            ics.append(float(np.corrcoef(ra, rb)[0, 1]))
    if len(ics) < MIN_DAYS_IC:
        return None
    v = np.asarray(ics)
    sd = float(v.std(ddof=1))
    return (float(v.mean() / sd * math.sqrt(len(v))) if sd > 0 else 0.0), len(v)


def seed(*, budget_s: float = 600.0, dry_run: bool = False) -> dict[str, Any]:
    from research import proposer_common as pc
    from research.multiplicity import deflate_t

    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    state = _read(STATE) if isinstance(_read(STATE), dict) else {}
    books: dict[str, Any] = state.setdefault("books", {})
    donated: dict[str, Any] = state.setdefault("donated", {})
    # EACH LOOK IS CHARGED ONCE, BY IDENTITY (audit PR166_v2, 2026-10-06). A book (both signs)
    # and a leg screen are trials the first time they are measured, on the pass that measures
    # them, whether or not it donates; re-measuring the same identity is not a new trial. Every
    # pass that donated before this rule charged every book it had, so a legacy book on a desk
    # that has donated counts as charged.
    screened: dict[str, Any] = state.setdefault("legs_screened", {})
    legacy_charged = bool(donated)
    new_looks: Counter[str] = Counter()
    try:
        cls = classes()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"universe unreadable: {type(exc).__name__}"}
    cat = zoo.catalogue()
    errors: Counter[str] = Counter()
    stopped = "every book measured today"
    measured = 0
    for klass, members in sorted(cls.items()):
        if len(members) < zoo.MIN_MEMBERS:
            continue
        got = zoo.class_panel(members[0])
        if got is None:
            continue
        panel = got[0]
        for aid in cat:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                break
            if all((books.get(f"{klass}|{aid}|{h}") or {}).get("day") == today for h in HORIZONS):
                continue
            try:
                score = zoo.compute(aid, panel)
            except Exception as exc:
                errors[f"{aid}: {type(exc).__name__}"] += 1
                continue
            for h in HORIZONS:
                ic = None if score is None else book_ic(score, panel, h)
                key = f"{klass}|{aid}|{h}"
                prior = books.get(key) or {}
                charged_at = prior.get("charged_at") or (
                    "legacy" if prior and legacy_charged else None)
                if charged_at is None and ic is not None:
                    new_looks["zoo_alpha_class"] += 2            # both signs are a test
                    charged_at = today
                books[key] = {"day": today, "klass": klass, "alpha": aid,
                              "h": h, "t": None if ic is None else round(ic[0], 3),
                              "days": None if ic is None else ic[1], "charged_at": charged_at}
                measured += 1
        else:
            continue
        break

    ts = [(k, v) for k, v in books.items() if isinstance(v.get("t"), (int, float))]
    n_tests = max(1, 2 * len(ts))                        # both signs are a test
    survivors = [(k, v) for k, v in ts if deflate_t(abs(float(v["t"])), n_tests) > 0]
    cands: list[dict[str, Any]] = []
    for key, v in survivors:
        if time.monotonic() - started > budget_s + 120:
            break
        direction = 1 if float(v["t"]) > 0 else -1
        for sym in cls.get(v["klass"], []):
            if time.monotonic() - started > budget_s + 120:
                break
            params = {"symbol": sym, "alpha_id": v["alpha"], "direction": direction,
                      "hold_d": int(v["h"])}
            ident = json.dumps(params, sort_keys=True)
            if ident in donated:
                continue
            d = pc.bars(sym)
            if d is None or len(d) < 2_000:
                continue
            cost = pc.cost_frac(sym, pc.universe_meta(), d["close"])
            if cost is None:
                continue
            try:
                r = pc.screen(d, zoo.family_zoo_alpha_class(d, **params), cost) or {}
            except Exception as exc:
                errors[f"leg {sym}: {type(exc).__name__}"] += 1
                continue
            if ident not in screened:                    # a leg screen is a look too
                new_looks["zoo_alpha_class"] += 1
                screened[ident] = today
            if int(r.get("n_independent") or 0) >= MIN_TRADES and r.get("clears_cost"):
                cands.append({"ident": ident, "params": params, "book": key, "book_t": v["t"],
                              "t_gross": r.get("t_gross"), "n": r.get("n_independent")})
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        rows = []
        for c in cands:
            p = c["params"]
            z = zoo.catalogue()[p["alpha_id"]]["zoo"]
            row = pc.candidate(
                SOURCE, p["symbol"], "zoo_alpha_class", dict(p),
                (f"{p['alpha_id']} ranked within {c['book'].split('|')[0]}: the class book's "
                 f"daily rank IC t={c['book_t']} survives deflation over {n_tests} book tests; "
                 f"this is {p['symbol']}'s leg, direction {p['direction']:+d}. "
                 f"Fails when {zoo.ZOO_CULTURE[z]['failure_mode_hypothesis']}"),
                f"{p['symbol']} zoo {p['alpha_id']}",
                {"screen_t_gross": c["t_gross"], "n_independent": c["n"], "book": c["book"],
                 "book_t": c["book_t"], "book_tests": n_tests, "origin": ORIGIN})
            row.update(zoo.ZOO_CULTURE[z])
            row["origin_source_id"] = "github:HKUDS/Vibe-Trading"     # the federation seed row
            row.setdefault("provenance", {})["source_id"] = row["origin_source_id"]
            row["culture_derivation"] = dict.fromkeys(zoo.ZOO_CULTURE[z], "declared")
            rows.append(row)
        path = pc.donate_or_charge(SOURCE, rows, sum(new_looks.values()),
                                   dict(new_looks))["path"]
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None, "n": int(counts.get("donated") or 0),
                    "refused_wrong_lane": counts.get("refused_wrong_lane")}
        if path:
            for c in cands:
                donated[c["ident"]] = _now()
    elif new_looks and not dry_run:
        donation["charged_on"] = pc.donate_or_charge(
            SOURCE, [], sum(new_looks.values()), dict(new_looks))["charged_on"]
    if not dry_run:
        _atomic(STATE, state)
    tv = [abs(float(v["t"])) for _, v in ts]
    by_zoo: Counter[str] = Counter(v["alpha"].split(".")[0] for _, v in survivors)
    return {
        "status": "OK", "dry_run": dry_run, "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 1), "classes": {k: len(v) for k, v in
                                                                        cls.items()},
        "alphas_offered": len(cat), "books_measured_this_pass": measured,
        "books_measured_total": len(ts), "book_tests_deflated_over": n_tests,
        "new_looks_charged": 0 if dry_run else int(sum(new_looks.values())),
        "abs_t_tail": {"gt_2": sum(t > 2 for t in tv), "gt_3": sum(t > 3 for t in tv),
                       "null_expected_gt_2": round(0.0455 * len(tv), 1),
                       "null_expected_gt_3": round(0.0027 * len(tv), 1)},
        "survivors": [{"book": k, "t": v["t"], "days": v["days"]} for k, v in
                      sorted(survivors, key=lambda kv: -abs(float(kv[1]["t"])))[:50]],
        "survivors_by_zoo": dict(by_zoo), "legs_clearing_cost_this_pass": len(cands),
        "donation": donation, "errors": dict(errors.most_common(10)),
        "contract": ("the zoo earns its place by the ten gates' verdicts on the legs of books "
                     "whose class IC survives deflation over every book it measured; the |t| "
                     "tail says whether the zoo prints more than a null of its size"),
        "origin": ORIGIN,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = {"generated_at": _now(), "source": SOURCE,
           **seed(budget_s=a.budget_s, dry_run=a.dry_run)}
    if not a.dry_run:
        _atomic(OUT, rep)
    print(f"zoo_breadth: {rep.get('status')} books={rep.get('books_measured_total')} "
          f"survivors={len(rep.get('survivors') or [])} "
          f"donation={(rep.get('donation') or {}).get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
