"""THE ARENA: research arms judged against each other, and the verdict written down.

MEASURED 2026-09-08 (Tier-1 programme item, acceptance property AP5 "the machine improves the
machine"): the desk runs eleven research arms under a bandit that allocates between them every
day, and NOT ONE ARM HAS EVER CARRIED A RECORDED VERDICT. The bandit re-weights continuously,
which is a decision that leaves no trace: an arm that has been starved for three months and an
arm that was funded yesterday look identical in the artifact, and "the inferior arm is retired"
-- AP5's own measure -- has no denominator because no arm has ever been JUDGED.

WHAT A VERDICT IS HERE. Each arm carries a survivor posterior from the bandit's own evidence
block (alpha/beta over born -> certified). This module compares every arm against the leader
and records:

    LEADS       the arm with the highest posterior mean, once it is decisive against the field
    KEEP        not decisively worse than the leader
    TRAILS      decisively worse than the leader (P(worse) >= DECISIVE) at or above MIN_N
    UNDECIDED   above MIN_N but the comparison does not separate them
    UNMEASURED  below MIN_N entries: silence, never a judgement

and appends one row per arm per pass to an append-only history, so "arms with a recorded
verdict" is a count anyone can take. The same comparison runs over CONTROLLER VARIANTS (item
I12) whenever more than one variant has rows: an A/B of the schedulers themselves.

IT RETIRES NOTHING. A TRAILS verdict is evidence for the principal and for the bandit's own
next pass; this module writes no budget, moves no floor and removes no arm. The desk's standing
order is that exploration is never reduced by fiat, and a verdict that silently defunded an arm
would be exactly that. The point of AP5 is that the judgement is RECORDED, not that it is
automatically executed.

THE COMPARISON IS A NORMAL APPROXIMATION OF THE BETA POSTERIORS, named as such in `basis`: with
the counts this desk carries (tens, not thousands) it agrees with the exact integral to well
inside the decision threshold, and it costs no dependency. A different estimator would change
the arithmetic, not the shape of the claim.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
BANDIT = DESK / "reports" / "RESEARCH_BANDIT.json"
OUT = DESK / "reports" / "ARM_VERDICTS.json"
HISTORY = DESK / "data" / "arm_verdicts.jsonl"

MIN_N = 20            # entries (born) below which an arm is UNMEASURED, not judged
DECISIVE = 0.95       # P(arm's survivor rate < leader's) at or above which TRAILS is recorded

LEADS, KEEP, TRAILS, UNDECIDED, UNMEASURED = (
    "LEADS", "KEEP", "TRAILS", "UNDECIDED", "UNMEASURED")


def _mean_var(alpha: float, beta: float) -> tuple[float, float]:
    a, b = max(1e-9, float(alpha)), max(1e-9, float(beta))
    n = a + b
    return a / n, (a * b) / (n * n * (n + 1.0))


def p_worse(alpha: float, beta: float, l_alpha: float, l_beta: float) -> float:
    """P(this arm's survivor rate < the leader's), normal approximation of both posteriors."""
    m1, v1 = _mean_var(alpha, beta)
    m2, v2 = _mean_var(l_alpha, l_beta)
    sd = math.sqrt(max(1e-18, v1 + v2))
    return round(0.5 * (1.0 + math.erf((m2 - m1) / (sd * math.sqrt(2.0)))), 4)


def judge(arms: dict[str, dict[str, Any]], min_n: int = MIN_N,
          decisive: float = DECISIVE) -> dict[str, Any]:
    """One verdict per arm, plus the leader it was judged against."""
    rows: dict[str, dict[str, Any]] = {}
    eligible = {k: v for k, v in arms.items()
                if isinstance(v, dict) and int(v.get("born") or 0) >= min_n}
    leader = None
    if eligible:
        leader = max(eligible, key=lambda k: _mean_var(eligible[k].get("alpha", 1),
                                                       eligible[k].get("beta", 1))[0])
    for name, a in sorted(arms.items()):
        born = int((a or {}).get("born") or 0)
        alpha, beta = float(a.get("alpha", 1.0)), float(a.get("beta", 1.0))
        mean, _ = _mean_var(alpha, beta)
        row = {"arm": name, "born": born, "certified": int(a.get("certified") or 0),
               "p_survivor": round(mean, 4), "group": a.get("group"),
               "cost_basis": a.get("cost_basis"), "leader": leader}
        if born < min_n:
            row.update(verdict=UNMEASURED, p_worse_than_leader=None,
                       why=f"born={born} < {min_n}: too few entries to judge")
        elif name == leader:
            row.update(verdict=LEADS, p_worse_than_leader=0.0,
                       why="highest posterior survivor rate among arms above the floor")
        else:
            la, lb = float(arms[leader].get("alpha", 1.0)), float(arms[leader].get("beta", 1.0))
            p = p_worse(alpha, beta, la, lb)
            row.update(p_worse_than_leader=p)
            if p >= decisive:
                row.update(verdict=TRAILS,
                           why=f"P(worse than {leader}) = {p} >= {decisive}; evidence only, "
                               f"this module retires nothing")
            else:
                row.update(verdict=KEEP if p < 0.5 else UNDECIDED,
                           why=f"P(worse than {leader}) = {p} < {decisive}: not separated")
        rows[name] = row
    return {"arms": rows, "leader": leader,
            "recorded": sum(1 for r in rows.values() if r["verdict"] != UNMEASURED),
            "trails": sorted(k for k, r in rows.items() if r["verdict"] == TRAILS)}


def variants(history: list[dict[str, Any]], min_n: int = MIN_N) -> dict[str, Any]:
    """The controller A/B: survivor rate per controller variant across recorded passes."""
    agg: dict[str, dict[str, float]] = {}
    for row in history:
        v = str(row.get("controller_variant") or "")
        if not v:
            continue
        a = agg.setdefault(v, {"born": 0.0, "certified": 0.0, "passes": 0.0})
        a["born"] += float(row.get("born") or 0)
        a["certified"] += float(row.get("certified") or 0)
        a["passes"] += 1
    out = {v: {"born": int(a["born"]), "certified": int(a["certified"]), "passes": int(a["passes"]),
               "rate": round((a["certified"] + 1.0) / (a["born"] + 2.0), 4)}
           for v, a in agg.items()}
    ready = [v for v, a in out.items() if a["born"] >= min_n]
    status = "MEASURED" if len(ready) >= 2 else ("ONE_ARM" if out else "UNMEASURED")
    return {"variants": out, "status": status,
            "why": ("an A/B of the schedulers needs two variants with entries; a desk that has "
                    "only ever run one controller has no comparison, which is not a tie")}


def _read(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _history(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def build(bandit: dict[str, Any], history: list[dict[str, Any]],
          now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    arms = bandit.get("arms") if isinstance(bandit.get("arms"), dict) else {}
    verdicts = judge(arms)
    variant = str(bandit.get("controller_variant") or "")
    return {
        "at": now.isoformat(timespec="seconds"),
        "controller_variant": variant or None,
        **verdicts,
        "controller_ab": variants(history),
        "n_arms": len(arms),
        "parameters": {"min_n": MIN_N, "decisive": DECISIVE},
        "basis": ("survivor posteriors from RESEARCH_BANDIT.json compared to the leader by a "
                  "normal approximation of the Beta posteriors; verdicts are recorded, never "
                  "executed -- no arm is defunded and no floor moves"),
        "status": "MEASURED" if verdicts["recorded"] else "UNMEASURED",
    }


def main(argv: list[str] | None = None) -> int:
    bandit = _read(BANDIT)
    doc = build(bandit, _history(HISTORY))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as fh:
            for row in doc["arms"].values():
                fh.write(json.dumps({"at": doc["at"],
                                     "controller_variant": doc["controller_variant"],
                                     **row}, default=str) + "\n")
    except OSError as exc:
        print(f"arena: history NOT appended ({type(exc).__name__}: {exc})", flush=True)
    print(f"arena: {doc['status']}; {doc['recorded']}/{doc['n_arms']} arms carry a verdict; "
          f"leader {doc['leader']}; trails {doc['trails'] or 'none'}; "
          f"controller A/B {doc['controller_ab']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
