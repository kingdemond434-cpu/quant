#!/usr/bin/env python3
"""DECAY-TRIGGERED RE-SEARCH FOR HAND-SPECIFIED FAMILIES: the refit a rule-based cell never had.

    python desks/mt5/research/hand_refit.py [--dry-run] [--family carry ...]

WHY. `decay_refit_trigger` (#1149) refits the LEARNED families when a cell decays and counts every
other family under `no_refit_schedule`. Measured 2026-11-13 on the forward clocks: 441 cells read
as decayed and none were learned -- cross_asset_residual 201, macro_conditional 135, carry 87.
For a hand-specified rule, "continuous retraining" (the CN shops' answer to alpha decay) is a
PARAMETER RE-SEARCH around the decayed spec, and that is a new set of hypotheses, so it is done
the honest way: pre-registered, charged, judged from scratch.

TRIGGER, per forward clock of a covered family, read point-in-time from the clock's own state and
ledger (an absent artifact is UNMEASURED, never "nothing decayed"):

    kill       the clock reached KILL
    flat       n >= DECAY_FWD_N with forward t <= 0 (promotion's arithmetic, sign flipped)
    cusum      a one-sided CUSUM on the clock's standardised forward R crossed CUSUM_H
               (reference k = CUSUM_K; ARL0 ~ 170 trades under no change for h=4, k=0.5). The
               change-point estimate is reported, so the re-search knows where the old regime
               ended

DECAYED, NOT NEVER-WORKED. A parameter re-search around a rule that never earned forward is the
overfitting machine, and its trials are paid by every other cell on the desk (CLAUDE.md, "trial
count is a shared cost"). So a triggered clock is re-searched only when its own forward ledger
shows an edge that LIVED and then broke: the CUSUM change point sits after at least
DECAYED_MIN_N forward trades and the trades before it averaged above zero. A clock whose CUSUM
fires from the start is NEVER_WORKED and is counted, not re-searched; a clock whose ledger cannot
be read is UNMEASURED and is counted, not guessed.

RE-SEARCH. The decayed spec is parsed from its clock key (`SYM.family.selector@TF#k=v_...`, the
same parse the allocator uses) and moved ONE AXIS AT A TIME along the family's declared refit
axes (REFIT_AXES). One-axis moves, not a grid: at most MAX_VARIANTS per cell, so the multiple-
testing bill stays proportional. A variant that already has a forward clock is not re-proposed
(it is already being measured).

PRE-REGISTRATION AND CHARGE. Every variant is written to data/hand_refit_preregistration.jsonl
BEFORE it is donated, with the trigger, the parent and the full variant set for the cell, and
the donation's `tests_run` is the number of variants, so the judge's deflation counts them. The
intake door (`proposer_common.donate`, seat `hand_refit`) is the only exit; nothing here arms,
sizes, promotes, retires or edits a certificate. One proposal per (parent, variant) per
REPROPOSE_DAYS.

Writes reports/HAND_REFIT.json.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "hand_refit"
OUT = DESK / "reports" / "HAND_REFIT.json"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
PREREG = DESK / "data" / "hand_refit_preregistration.jsonl"
DECAY_FWD_N = 20
CUSUM_K = 0.5
CUSUM_H = 4.0
CUSUM_MIN_N = 10
REPROPOSE_DAYS = 30
MAX_VARIANTS = 8
MAX_PARENTS_PER_PASS = 150
DECAYED_MIN_N = 20

#: Per family: param -> the moves tried from the parent's value. A number moves by the listed
#: multipliers (int params rounded, never to the same value); a choice param moves to the listed
#: alternatives. Missing in the parent = the family default, which the variant then states.
REFIT_AXES: dict[str, dict[str, Any]] = {
    "cross_asset_residual": {
        "lookback": ("mul", (0.5, 2.0), 240), "entry_z": ("set", (1.5, 2.0, 2.5, 3.0), 2.0),
        "ttl_bars": ("mul", (0.5, 2.0), 72), "beta_win": ("mul", (0.5, 2.0), 240)},
    "macro_conditional": {
        "regime_high": ("set", (0.3, 0.5, 0.7), 0.5), "ttl_bars": ("mul", (0.5, 2.0), 96),
        "rr": ("set", (1.5, 2.0, 3.0), 2.0)},
    "carry": {
        "min_edge_bp_per_day": ("set", (0.25, 0.5, 1.0), 0.5),
        "hold_bars": ("mul", (0.5, 2.0), 120), "require_quiet": ("set", (True, False), True)},
}
_CLOCK_PARAM = re.compile(r"(?:^|_)([a-z][a-z0-9_]*?)=(\[[^\]]*\]|[^_]+)")


# ----------------------------------------------------------------------------- the clock key
def parse_key(key: str) -> dict[str, Any] | None:
    """`SYM.family.selector@TF#k=v_k=v` -> {symbol, family, selector, timeframe, params}."""
    head, _, tail = str(key).partition("#")
    parts = head.split(".")
    if len(parts) < 3:
        return None
    sel, _, tf = parts[2].partition("@")
    params: dict[str, Any] = {}
    for k, raw in _CLOCK_PARAM.findall(tail):
        try:
            params[k] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            params[k] = raw
    return {"symbol": parts[0], "family": parts[1], "selector": sel, "timeframe": tf,
            "params": params}


def spec_key(spec: Mapping[str, Any]) -> str:
    """The canonical key of a spec, so a variant can be compared to existing clocks."""
    p = spec["params"]
    tail = "_".join(f"{k}={p[k]}" for k in sorted(p))
    tf = f"@{spec['timeframe']}" if spec.get("timeframe") else ""
    return f"{spec['symbol']}.{spec['family']}.{spec['selector']}{tf}" + (f"#{tail}" if tail
                                                                          else "")


# ----------------------------------------------------------------------------- triggers
def cusum(rs: Sequence[float]) -> dict[str, Any]:
    """One-sided CUSUM for a DOWNWARD shift of standardised R below zero. Standardised by the
    series' own dispersion; reports the alarm index and the change-point estimate (the last
    index the statistic was zero before the alarm)."""
    x = [float(r) for r in rs if isinstance(r, (int, float)) and math.isfinite(float(r))]
    if len(x) < CUSUM_MIN_N:
        return {"status": "UNMEASURED", "n": len(x)}
    m = sum(x) / len(x)
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1)) or 1.0
    s, last_zero = 0.0, 0
    for i, v in enumerate(x):
        s = max(0.0, s + (-v / sd) - CUSUM_K)
        if s == 0.0:
            last_zero = i + 1
        if s > CUSUM_H:
            return {"status": "ALARM", "n": len(x), "alarm_at": i, "change_at": last_zero}
    return {"status": "QUIET", "n": len(x), "stat": round(s, 3)}


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _forward_rs(key: str) -> list[float]:
    try:
        import decay_monitor as dm
    except ImportError:                                       # pragma: no cover
        from research import decay_monitor as dm
    out: list[float] = []
    try:
        for row in dm._shadow_ledger_rows(key):
            r = dm._row_r(row)
            if r is not None:
                out.append(float(r))
    except Exception:
        return []
    return out


def trigger(key: str, st: Mapping[str, Any], rs: Sequence[float] | None = None
            ) -> tuple[str | None, str, dict[str, Any] | None]:
    """(kill | flat | cusum | None, why, cusum reading)."""
    status = str(st.get("status") or "")
    n, t = _num(st.get("n")), _num(st.get("forward_t"))
    if status == "KILL":
        return "kill", f"forward clock KILL (n={st.get('n')}, t={st.get('forward_t')})", None
    if n is not None and t is not None and n >= DECAY_FWD_N and t <= 0:
        return "flat", f"forward edge absent: n={int(n)}, t={t:+.2f} <= 0", None
    cs = cusum(rs if rs is not None else _forward_rs(key))
    if cs.get("status") == "ALARM":
        return "cusum", (f"CUSUM alarm at forward trade {cs['alarm_at']} (change point "
                         f"~{cs['change_at']}, h={CUSUM_H}, k={CUSUM_K})"), cs
    return None, "", cs


def history(rs: Sequence[float]) -> tuple[str, str]:
    """DECAYED | NEVER_WORKED | UNMEASURED, and why, from the clock's forward R in order."""
    x = [float(r) for r in rs if isinstance(r, (int, float)) and math.isfinite(float(r))]
    if len(x) < CUSUM_MIN_N:
        return "UNMEASURED", f"{len(x)} forward trade(s) readable in the ledger"
    cs = cusum(x)
    cp = int(cs.get("change_at") or 0) if cs.get("status") == "ALARM" else len(x)
    pre = x[:cp]
    if cp >= DECAYED_MIN_N and pre and sum(pre) / len(pre) > 0:
        return "DECAYED", (f"{cp} forward trades averaged {sum(pre) / len(pre):+.3f}R before the "
                           f"change point, then broke")
    return "NEVER_WORKED", (f"change point at trade {cp} of {len(x)}"
                            + (f", pre-change mean {sum(pre) / len(pre):+.3f}R" if pre else ""))


# ----------------------------------------------------------------------------- variants
def variants(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One-axis moves of the parent along its family's REFIT_AXES, at most MAX_VARIANTS."""
    axes = REFIT_AXES.get(str(spec["family"]), {})
    base = dict(spec["params"])
    out: list[dict[str, Any]] = []
    seen = {json.dumps(base, sort_keys=True, default=str)}
    for k, (kind, moves, default) in axes.items():
        cur = base.get(k, default)
        cands: list[Any] = []
        if kind == "mul" and isinstance(cur, (int, float)) and not isinstance(cur, bool):
            for m in moves:
                v = cur * m
                v = max(1, round(v)) if isinstance(cur, int) else round(v, 4)
                cands.append(v)
        elif kind == "set":
            cands = [v for v in moves if v != cur]
        for v in cands:
            p = {**base, k: v}
            sig = json.dumps(p, sort_keys=True, default=str)
            if sig in seen:
                continue
            seen.add(sig)
            out.append({**spec, "params": p, "moved": {k: [cur, v]}})
            if len(out) >= MAX_VARIANTS:
                return out
    return out


# ----------------------------------------------------------------------------- ledger
def _prior(now: datetime) -> set[str]:
    cut = now - timedelta(days=REPROPOSE_DAYS)
    done: set[str] = set()
    try:
        lines = PREREG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return done
    for line in lines[-50_000:]:
        try:
            r = json.loads(line)
            at = datetime.fromisoformat(str(r.get("at")))
        except (ValueError, TypeError):
            continue
        if at.tzinfo and at >= cut:
            done.add(str(r.get("variant_key")))
    return done


def plan(state: Mapping[str, Any], now: datetime, *, families: Sequence[str] | None = None,
         forward_rs: Mapping[str, Sequence[float]] | None = None,
         include_never_worked: bool = False) -> dict[str, Any]:
    fams = set(families or REFIT_AXES)
    existing = {str(k) for k in state}
    prior = _prior(now)
    triggered: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_history: Counter[str] = Counter()
    unparsed: list[str] = []
    parents: list[dict[str, Any]] = []
    for key, st in state.items():
        if not isinstance(st, Mapping):
            continue
        spec = parse_key(str(key))
        if spec is None:
            unparsed.append(str(key))
            continue
        if spec["family"] not in fams:
            continue
        rs = (list((forward_rs or {}).get(str(key)) or []) if forward_rs is not None
              else _forward_rs(str(key)))
        kind, why, cs = trigger(str(key), st, rs)
        if kind is None:
            continue
        triggered[spec["family"]] += 1
        by_kind[kind] += 1
        hist, hwhy = history(rs)
        by_history[hist] += 1
        if hist != "DECAYED" and not (include_never_worked and hist == "NEVER_WORKED"):
            continue
        parents.append({"key": str(key), "spec": spec, "trigger": kind,
                        "why": f"{why}; {hwhy}", "cusum": cs, "n": st.get("n"),
                        "forward_t": st.get("forward_t")})
    # the worst evidence first: most forward trades with the most negative t
    parents.sort(key=lambda p: (-(_num(p.get("n")) or 0), _num(p.get("forward_t")) or 0.0))
    proposals: list[dict[str, Any]] = []
    already_clocked = already_proposed = 0
    for p in parents[:MAX_PARENTS_PER_PASS]:
        for v in variants(p["spec"]):
            vk = spec_key(v)
            if vk in existing:
                already_clocked += 1
                continue
            if vk in prior:
                already_proposed += 1
                continue
            proposals.append({"parent": p["key"], "trigger": p["trigger"], "why": p["why"],
                              "variant_key": vk, "symbol": v["symbol"], "family": v["family"],
                              "selector": v["selector"], "timeframe": v["timeframe"],
                              "params": v["params"], "moved": v["moved"]})
    return {"triggered_by_family": dict(triggered), "triggered_by_kind": dict(by_kind),
            "triggered_by_history": dict(by_history),
            "parents": len(parents), "parents_this_pass": min(len(parents),
                                                              MAX_PARENTS_PER_PASS),
            "variants_already_clocked": already_clocked,
            "variants_proposed_within_window": already_proposed,
            "unparsed_keys": len(unparsed), "proposals": proposals,
            "parent_sample": [{k: p[k] for k in ("key", "trigger", "why")} for p in parents[:20]]}


def to_candidate(p: Mapping[str, Any]) -> dict[str, Any]:
    from research import proposer_common as pc
    moved = ", ".join(f"{k} {a}->{b}" for k, (a, b) in p["moved"].items())
    c = pc.candidate(
        SEAT, str(p["symbol"]), str(p["family"]), dict(p["params"]),
        mechanism=(f"decay re-search of {p['parent']}: the parent's forward clock decayed "
                   f"({p['why']}); one pre-registered move ({moved}) re-tests the same mechanism "
                   "at a neighbouring setting, judged from scratch"),
        title=str(p["variant_key"]),
        evidence={"parent": p["parent"], "trigger": p["trigger"], "moved": p["moved"],
                  "preregistered_in": f"data/{PREREG.name}"})
    c.update({"chart": p.get("timeframe") or "", "timeframe": p.get("timeframe") or "",
              "selector": p.get("selector"), "trial_family": f"{SEAT}:{p['family']}"})
    return c


def run(now: datetime | None = None, *, donate: bool = True,
        families: Sequence[str] | None = None, include_never_worked: bool = False
        ) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    try:
        state = json.loads(SHADOW.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = None
    doc: dict[str, Any] = {"schema": "hand-refit/1", "at": now.isoformat(timespec="seconds"),
                           "families": sorted(families or REFIT_AXES),
                           "rule": {"kill": "clock KILL", "flat": f"n>={DECAY_FWD_N}, t<=0",
                                    "cusum": f"one-sided, h={CUSUM_H}, k={CUSUM_K}",
                                    "moves": "one axis at a time, <= "
                                             f"{MAX_VARIANTS} per parent",
                                    "repropose_days": REPROPOSE_DAYS,
                                    "re_searched": f"DECAYED only (change point after >= "
                                                   f"{DECAYED_MIN_N} trades with a positive "
                                                   "pre-change mean)"}}
    if not isinstance(state, dict):
        doc.update({"status": "UNMEASURED", "why": f"{SHADOW.name} absent or unreadable"})
    else:
        doc.update({"status": "MEASURED", **plan(state, now, families=families,
                                                    include_never_worked=include_never_worked)})
        props = doc["proposals"]
        if donate and props:
            PREREG.parent.mkdir(parents=True, exist_ok=True)
            batch = hashlib.sha256(json.dumps([p["variant_key"] for p in props]).encode()
                                   ).hexdigest()[:12]
            with PREREG.open("a", encoding="utf-8") as fh:
                for p in props:
                    fh.write(json.dumps({"at": now.isoformat(timespec="seconds"), "batch": batch,
                                         **p}, default=str) + "\n")
            from research import proposer_common as pc
            path = pc.donate(SEAT, [to_candidate(p) for p in props], len(props))
            doc["donated"] = {"file": path.name if path else None, "batch": batch,
                              **pc.donation_counts()}
        doc["proposals_n"] = len(props)
        doc["proposals"] = props[:200]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(OUT)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--family", action="append", default=None)
    a = ap.parse_args(argv)
    doc = run(donate=not a.dry_run, families=a.family)
    print(json.dumps({k: doc.get(k) for k in ("status", "why", "triggered_by_family",
                                               "triggered_by_kind", "triggered_by_history",
                                               "parents",
                                               "variants_already_clocked", "proposals_n",
                                               "donated")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
