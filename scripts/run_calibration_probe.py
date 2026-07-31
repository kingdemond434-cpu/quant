#!/usr/bin/env python3
"""CALIBRATION PROBE (R0142) -- does this model family's stated probability mean ANYTHING?

THE LOAD-BEARING ASSUMPTION NOBODY HAS TESTED. The whole discretionary sizing apparatus consumes
one number: the model's stated `probability`. Kelly is f* = (pb - q)/b -- if p is noise, the sizer
is not aggressive or conservative, it is arbitrary. Checked on 2026-07-31, the desk had logged
ZERO resolved forecasts. Not few. Zero. The most consequential input to the money path had never
been scored on anything, and the sleeve was built to consume it anyway.

WHY THIS IS ANSWERABLE TODAY, WITH NO CAPITAL. Waiting for the trading book to accumulate 50 marked
trades takes a week and needs venue keys. But calibration is a property of the FORECASTER, not of
the trading strategy -- so it can be measured directly with questions that resolve from public
price data in hours. This probe asks the same KIND of judgement the sleeve makes (directional, over
a horizon, on the same instruments) and scores it. 50 forecasts arrive in about two days and cost
nothing but quota.

WHAT IT WOULD TAKE TO MOVE ME:
  * Brier meaningfully below 0.25 (the score of always answering 50%),
  * a reliability curve that RISES -- when it says 70% it should be right more often than when it
    says 55%,
  * and a small |bias|, so the number is not systematically inflated.
A Brier at or above 0.25 means the probabilities carry no information, and then the correct move
is to strip the Kelly sizer out of the sleeve entirely and run flat size -- because sizing on a
meaningless number is strictly worse than not sizing on it.

DELIBERATELY NOT A TRADING SIGNAL. These questions are chosen to be SCORABLE, not tradeable, and
the probe places no orders and books nothing. Its output feeds only the calibration fence (L1.29),
which is what the conviction sleeve's sizer already reads -- so a proven-uncalibrated forecaster
automatically shrinks its own future size without anyone deciding to intervene.

    python scripts/run_calibration_probe.py [--resolve] [--n 6] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OPEN = "data/calibration_probe.jsonl"
_STATE = "data/calibration_probe.json"

#: Horizons chosen so a question resolves fast enough to accumulate a sample in days, and long
#: enough that the answer is not a coin flip on microstructure. 4h is the shortest horizon the
#: measured noise floors (PAXG 0.5%, SOL 0.73% at 8h) leave room to have a view over.
HORIZONS_H: tuple[int, ...] = (4, 12, 24)
#: 0.25 is the Brier score of a forecaster who always answers 50%. At or above it the stated
#: probabilities carry no information and the Kelly sizer should be removed, not tuned.
UNINFORMATIVE_BRIER = 0.25
#: 30 resolved forecasts before publishing a verdict: the binomial standard error on a hit rate is
#: ~9pp there, enough to separate a real signal from noise on the reliability curve.
MIN_FOR_VERDICT = 30

_BRIEF = """You are being SCORED on calibration, not on trading. These questions place no orders
and book nothing -- the only thing measured is whether your stated probabilities mean anything.

Answer each with an honest probability. Being right is worth nothing here; being CALIBRATED is
everything. If you say 70% you should be right about 70% of the time -- so a confident answer you
cannot back costs you exactly as much as a wrong one. Saying 50% when you do not know is the
correct answer and is not penalised.

{context}

QUESTIONS -- each resolves automatically from Binance/OKX price data at its stated horizon:
{questions}

OUTPUT EXACTLY ONE JSON OBJECT mapping each question id to your probability:
{{"q1": 0.55, "q2": 0.62, ...}}

Probabilities strictly between 0.02 and 0.98. Nothing else in the output."""


def build_questions(root: Path, n: int = 6) -> list[dict[str, Any]]:
    """Directional questions on the sleeve's own instruments -- the same KIND of judgement it
    makes when it trades, so the measured calibration transfers."""
    try:
        charts = json.loads((root / "data/chart_context.json").read_text("utf-8"))["charts"]
    except (OSError, ValueError, KeyError):
        return []
    qs: list[dict[str, Any]] = []
    syms = [s for s, c in charts.items() if c.get("state") == "OK"]
    for i, sym in enumerate(syms):
        tf = charts[sym]["timeframes"].get("15m", {})
        px = tf.get("price")
        if not px:
            continue
        h = HORIZONS_H[i % len(HORIZONS_H)]
        qs.append({"id": f"q{len(qs)+1}", "symbol": sym, "horizon_h": h,
                   "ref_price": px, "kind": "above_ref",
                   "text": f"Will {sym} trade ABOVE {px} in {h} hours' time?"})
        if len(qs) >= n:
            break
    return qs


def _ask(prompt: str, timeout: int = 600) -> str:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def parse(raw: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def pose(root: Path, *, n: int = 6, ask=_ask) -> dict[str, Any]:
    qs = build_questions(root, n)
    if not qs:
        return {"status": "NO-QUESTIONS",
                "why": "no chart context on this host -- the probe cannot pose a question it "
                       "cannot later resolve, and a question it cannot resolve is not a test"}
    ctx = json.dumps([{k: q[k] for k in ("id", "symbol", "ref_price", "horizon_h")} for q in qs])
    raw = ask(_BRIEF.format(context=f"Current reference prices: {ctx}",
                            questions="\n".join(f"  {q['id']}: {q['text']}" for q in qs)))
    ans = parse(raw)
    if not ans:
        return {"status": "NO-ANSWER", "why": "no parseable JSON (auth/quota/refusal)"}
    now = datetime.now(tz=UTC)
    posed = []
    for q in qs:
        p = ans.get(q["id"])
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if not 0.0 < p < 1.0:
            continue
        row = {**q, "p": p, "asked_at": now.isoformat(),
               "resolve_at": (now + timedelta(hours=q["horizon_h"])).isoformat(),
               "key": f"probe:{now.isoformat()}:{q['id']}"}
        posed.append(row)
    path = root / _OPEN
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in posed:
            fh.write(json.dumps(row) + "\n")
    try:
        from libs.self_improvement import forecast_calibration as fc
        for row in posed:
            fc.log_forecast(row["key"], row["p"], "calibration_probe",
                            resolve_by=row["resolve_at"], claim=row["text"])
    except Exception as exc:                              # broad by design -- never lose the probe
        return {"status": "POSED", "n": len(posed), "calibration_log_error": str(exc)}
    return {"status": "POSED", "n": len(posed),
            "questions": [{"id": r["id"], "symbol": r["symbol"], "p": r["p"]} for r in posed]}


def resolve_due(root: Path, *, now: datetime | None = None, fetch=None) -> dict[str, Any]:
    """Score every question whose horizon has passed, from real bars. Unresolvable stays open."""
    now = now or datetime.now(tz=UTC)
    if fetch is None:
        from scripts.resolve_paper_book import fetch_bars as fetch
    try:
        lines = (root / _OPEN).read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return {"status": "NOTHING-POSED", "n_resolved": 0}
    rows, keep, resolved = [], [], 0
    for ln in lines:
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except ValueError:
            continue
    try:
        from libs.self_improvement import forecast_calibration as fc
    except ImportError as exc:
        return {"status": "UNSCORABLE", "why": f"calibration module unavailable ({exc})"}
    for r in rows:
        try:
            due = datetime.fromisoformat(r["resolve_at"])
        except (KeyError, ValueError):
            continue
        if due > now:
            keep.append(r)
            continue
        end = int(due.timestamp() * 1000)
        bars, _src = fetch(r["symbol"], end - 3 * 3600 * 1000, end, "15m")
        if not bars:
            keep.append(r)                     # UNRESOLVABLE stays open, never guessed
            continue
        outcome = bars[-1][4] > float(r["ref_price"])
        try:
            fc.resolve(r["key"], bool(outcome))
            resolved += 1
        except (KeyError, ValueError, OSError):
            keep.append(r)
    with (root / _OPEN).open("w", encoding="utf-8") as fh:
        for r in keep:
            fh.write(json.dumps(r) + "\n")
    return {"status": "RESOLVED", "n_resolved": resolved, "still_open": len(keep)}


def verdict() -> dict[str, Any]:
    """The answer to the question this organ exists for -- and what to DO about each outcome."""
    try:
        from libs.self_improvement.forecast_calibration import report
        rep = report()
    except Exception as exc:                              # broad by design
        return {"state": "UNMEASURED", "why": f"calibration unavailable ({exc})"}
    n, brier = rep.get("n_resolved") or 0, rep.get("brier")
    if n < MIN_FOR_VERDICT or brier is None:
        return {"state": "ACCUMULATING", "n_resolved": n, "need": MIN_FOR_VERDICT,
                "why": f"{n}/{MIN_FOR_VERDICT} resolved -- no verdict is available yet, and a "
                       "partial record must not read as one"}
    if brier >= UNINFORMATIVE_BRIER:
        return {"state": "UNINFORMATIVE", "n_resolved": n, "brier": brier,
                "why": f"Brier {brier:.4f} >= {UNINFORMATIVE_BRIER} -- the stated probabilities "
                       "carry no more information than always answering 50%. The correct response "
                       "is to REMOVE the Kelly sizer from the sleeve and run flat size: sizing on "
                       "a meaningless number is strictly worse than not sizing on it."}
    return {"state": "INFORMATIVE", "n_resolved": n, "brier": brier, "bias": rep.get("bias"),
            "why": f"Brier {brier:.4f} beats the {UNINFORMATIVE_BRIER} uninformative benchmark -- "
                   "the probabilities carry signal, so Kelly sizing on them is justified and the "
                   "measured bias is worth applying as shrinkage."}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat()}
    out["resolve"] = resolve_due(_ROOT)
    if not args.resolve:
        out["pose"] = pose(_ROOT, n=args.n)
    out["verdict"] = verdict()
    (_ROOT / _STATE).write_text(json.dumps(out, indent=2), "utf-8")
    print(json.dumps(out, indent=2) if args.json else
          f"calibration probe (R0142): {out['verdict']['state']} -- {out['verdict']['why'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
