"""THE FENCE-AWARE PLANNER: one direction set per symbol and day across E8, FTMO and Fusion.

WHY (2026-10-29 04:24Z). `mt5desk.cross_account.opposite_block` refuses an order whose side is
opposite an OPEN or PENDING position of another account on the same symbol. It is right to refuse,
but it decides leg by leg, in whatever order the lanes' clocks happen to reach it. On 10-29 E8
held or rested a gold short, so Fusion's gold_asia buy_stop was refused while its sell_stop
placed: Fusion carried HALF a bracket that nothing had chosen. A bracket certificate measures the
two-sided entry; its lone short leg has no evidence of its own.

WHAT THIS DOES (REPORT-ONLY; it never sends, cancels or changes the fence). For every symbol and
day it gathers each account's intended orders and, over every assignment of {both, long, short,
none} per account that the fence allows, picks the one that maximises combined
Delta E[log W] = sum_a ( f_a * mu_a - f_a^2 * E[R^2]_a / 2 ). Feasible means no account carries a
side opposite another account's side (a resting bracket counts as both sides, so a whole bracket
is feasible only when no other account has any gold side). Positions that are already open or
resting on an account's book and cannot be withdrawn by a plan are FIXED.

EVIDENCE RULES. A bracket's edge is the bracket's measured mu (R per bracket). A lone leg of a
bracket counts only with its own measured per-side mu; without one it is UNMEASURED and contributes
0, flagged. Ties go to fewer half-brackets, then fewer unmeasured legs: so on 10-29 the plan is
Fusion short-only when a short edge is measured and positive, else skip -- never half by accident.
A missing input is UNMEASURED, never a zero that looks like a decision.

Writes reports/FENCE_PLAN.json.
"""
from __future__ import annotations

import itertools
import json
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Row = dict[str, Any]
DESK = Path(__file__).resolve().parent.parent
OUT = DESK / "reports" / "FENCE_PLAN.json"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
E8_INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
FTMO_INTENTS = DESK / "data" / "ftmo_follower_intents.jsonl"
CERT_BOOK = DESK / "data" / "CERT_BOOK_LIVE.json"
SLEEVES = DESK / "data" / "sleeves.json"
XACCT = DESK / "data" / "xacct"
UNMEASURED = "UNMEASURED"
CHOICES = ("both", "long", "short", "none")
LONG_SIDES = {"buy_stop", "buy_limit", "buy", "long"}
SHORT_SIDES = {"sell_stop", "sell_limit", "sell", "short"}
EDGE_KEYS = ("edge_r", "expectancy_r", "mean_r", "mu_r")


def side_dir(side: object) -> str | None:
    s = str(side or "").strip().lower()
    return "long" if s in LONG_SIDES else "short" if s in SHORT_SIDES else None


def _num(x: object) -> float | None:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def second_moment(mu: float, rr: float | None) -> float:
    """E[R^2] of a fixed-geometry leg (win +rr, loss -1) with mean mu; 1 + mu^2 without rr."""
    if rr is None or rr <= 0:
        return 1.0 + mu * mu
    p = min(max((mu + 1.0) / (rr + 1.0), 0.0), 1.0)
    return p * rr * rr + (1.0 - p)


def elogw(f: float, mu: float, rr: float | None) -> float:
    return f * mu - 0.5 * f * f * second_moment(mu, rr)


def sides_of(choice: str) -> set[str]:
    return {"long", "short"} if choice == "both" else set() if choice == "none" else {choice}


def value(intent: Mapping[str, Any], choice: str) -> Row:
    """Delta E[log W] of `choice` for one account's intent, with what it rests on."""
    if choice == "none":
        return {"delta_elogw": 0.0, "half_bracket": False, "unmeasured": []}
    f = _num(intent.get("risk_frac"))
    edge = intent.get("edge") or {}
    rr = _num(intent.get("rr"))
    bracket = bool(intent.get("bracket"))
    half = bracket and choice != "both"
    key = "bracket" if choice == "both" else choice
    mu = _num(edge.get(key))
    if choice == "both" and not bracket:
        mu = None
    missing = [n for n, v in (("risk_frac", f), (f"edge.{key}", mu)) if v is None]
    if missing:
        return {"delta_elogw": 0.0, "half_bracket": half, "unmeasured": missing}
    assert f is not None and mu is not None
    return {"delta_elogw": elogw(f, mu, rr), "half_bracket": half, "unmeasured": []}


def allowed_choices(intent: Mapping[str, Any]) -> tuple[str, ...]:
    """A FIXED book keeps what it holds; a bracket may be whole, either half, or none; a
    single-direction intent may be itself or none."""
    if intent.get("fixed"):
        return (str(intent.get("fixed_choice") or "none"),)
    if intent.get("bracket"):
        return CHOICES
    d = side_dir(intent.get("direction"))
    return (d, "none") if d else ("none",)


def feasible(assign: Mapping[str, str]) -> bool:
    """The fence: no account's side opposite ANOTHER account's side (own bracket is fine)."""
    accts = list(assign)
    for a, b in itertools.combinations(accts, 2):
        sa, sb = sides_of(assign[a]), sides_of(assign[b])
        if ("long" in sa and "short" in sb) or ("short" in sa and "long" in sb):
            return False
    return True


def plan_group(intents: list[Row]) -> Row:
    """Every feasible assignment, ranked; the first is the plan."""
    keys = [f"{i['account']}:{i.get('sleeve') or '-'}" for i in intents]
    alts: list[Row] = []
    for combo in itertools.product(*(allowed_choices(i) for i in intents)):
        # Feasibility is per ACCOUNT: two sleeves on one account may not hedge either (the lanes'
        # own self-hedge rule), so they are merged under the account for the fence check.
        by_acct: dict[str, set[str]] = {}
        for i, c in zip(intents, combo, strict=True):
            by_acct.setdefault(str(i["account"]), set()).update(sides_of(c))
        acct_choice = {a: ("both" if s == {"long", "short"} else next(iter(s)) if s else "none")
                       for a, s in by_acct.items()}
        own_ok = all(not (s == {"long", "short"} and
                          sum(1 for i, c in zip(intents, combo, strict=True)
                              if str(i["account"]) == a and c != "none") > 1)
                     for a, s in by_acct.items())
        if not (own_ok and feasible(acct_choice)):
            continue
        vals = [value(i, c) for i, c in zip(intents, combo, strict=True)]
        alts.append({"assignment": dict(zip(keys, combo, strict=True)),
                     "delta_elogw": round(sum(v["delta_elogw"] for v in vals), 12),
                     "half_brackets": sum(1 for v in vals if v["half_bracket"]),
                     "unmeasured": sorted({f"{k}:{u}" for k, v in zip(keys, vals, strict=True)
                                           for u in v["unmeasured"]})})
    alts.sort(key=lambda a: (-a["delta_elogw"], a["half_brackets"], len(a["unmeasured"])))
    if not alts:
        return {"verdict": "NO_FEASIBLE_PLAN", "plan": None, "alternatives": []}
    best = alts[0]["delta_elogw"]
    for a in alts:
        a["delta_vs_plan"] = round(a["delta_elogw"] - best, 12)
    plan = alts[0]
    verdict = UNMEASURED if plan["unmeasured"] and all(a["delta_elogw"] == 0 for a in alts) \
        else "PLANNED"
    return {"verdict": verdict, "plan": plan, "alternatives": alts[1:]}


def actual_vs_plan(intents: list[Row], plan: Mapping[str, Any] | None) -> list[Row]:
    """What each account actually ended with (`placed` sides) beside the plan's choice."""
    out = []
    for i in intents:
        k = f"{i['account']}:{i.get('sleeve') or '-'}"
        placed = sorted(set(i.get("placed") or []))
        actual = "both" if placed == ["long", "short"] else placed[0] if placed else "none"
        out.append({"key": k, "actual": actual,
                    "planned": (plan or {}).get("assignment", {}).get(k),
                    "actual_half_bracket": bool(i.get("bracket")) and actual in ("long", "short")
                    and not i.get("fixed")})
    return out


# ------------------------------------------------------------------------ loading the inputs
def _jsonl(path: Path, tail: int = 20000) -> list[Row]:
    try:
        lines = path.read_text("utf-8").splitlines()[-tail:]
    except OSError:
        return []
    rows = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _json(path: Path) -> Row:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _edges(sleeves: Iterable[Any]) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for s in sleeves:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        e: dict[str, float | None] = {"bracket": None, "long": None, "short": None}
        for k in EDGE_KEYS:
            if _num(s.get(k)) is not None:
                e["bracket"] = _num(s.get(k))
                break
        for d in ("long", "short"):
            e[d] = _num(s.get(f"edge_r_{d}"))
        out[str(s["name"])] = e
    return out


def gather(day: str, *, decisions: list[Row] | None = None, e8: list[Row] | None = None,
           ftmo: list[Row] | None = None, cert: Row | None = None,
           sleeves: list[Any] | None = None, books: Row | None = None) -> Row:
    """Intents per (symbol, day) from the ledgers, the cert book, sleeves.json and the
    cross-account books. Every argument stands in for its file (tests)."""
    decisions = _jsonl(DECISIONS) if decisions is None else decisions
    e8 = _jsonl(E8_INTENTS) if e8 is None else e8
    ftmo = _jsonl(FTMO_INTENTS) if ftmo is None else ftmo
    cert = _json(CERT_BOOK) if cert is None else cert
    if sleeves is None:
        sl = _json(SLEEVES).get("sleeves")
        sleeves = sl if isinstance(sl, list) else []
    if books is None:
        books = {a: _json(XACCT / f"{a}_book.json") for a in ("e8", "fusion", "ftmo")}
    edges = _edges(sleeves)
    missing: list[str] = []
    for name, rows in (("decision_ledger", decisions), ("e8_gold_intents", e8),
                       ("ftmo_follower_intents", ftmo)):
        if not rows:
            missing.append(name)
    if not cert:
        missing.append("CERT_BOOK_LIVE")
    groups: dict[tuple[str, str], dict[str, Row]] = {}

    def add(account: str, sleeve: str, symbol: str, side: object, row: Row, placed: bool) -> None:
        d = side_dir(side)
        if d is None:
            return
        g = groups.setdefault((symbol.upper(), day), {})
        it = g.setdefault(f"{account}:{sleeve}", {
            "account": account, "sleeve": sleeve, "symbol": symbol.upper(), "sides": set(),
            "placed": set(), "risk_frac": _num(row.get("risk_frac")) if row.get("risk_frac")
            is not None else _num((cert.get(account) or {}).get(sleeve)),
            "edge": dict(edges.get(sleeve) or {"bracket": None, "long": None, "short": None}),
            "rr": None})
        it["sides"].add(d)
        if placed:
            it["placed"].add(d)
        p, s, t = _num(row.get("price")), _num(row.get("sl")), _num(row.get("tp"))
        if p is not None and s is not None and t is not None and abs(p - s) > 0:
            it["rr"] = abs(t - p) / abs(p - s)

    for r in decisions:
        if str(r.get("time") or r.get("decided_at") or "")[:10] != day:
            continue
        if r.get("execution") not in ("pending_stop", "pending_limit") and \
                not str(r.get("side") or "").endswith(("_stop", "_limit")):
            continue
        add("fusion", str(r.get("sleeve") or r.get("strategy_id") or "-"),
            str(r.get("symbol") or "XAUUSD"), r.get("side"), r,
            bool(r.get("taken")) or r.get("outcome") == "EXECUTED")
    for acct, rows in (("e8", e8), ("ftmo", ftmo)):
        for r in rows:
            if str(r.get("at") or "")[:10] != day or not r.get("window"):
                continue
            st = str(r.get("status") or "").upper()
            add(acct, str(r["window"]), str(r.get("symbol") or "XAUUSD"), r.get("side"), r,
                st in ("PLACED", "SENT", "FILLED", "ADOPTED", "RESTING"))
    out: Row = {}
    for (symbol, d), g in groups.items():
        intents = []
        for it in g.values():
            it["bracket"] = it["sides"] == {"long", "short"}
            it["direction"] = next(iter(it["sides"])) if len(it["sides"]) == 1 else None
            intents.append(it)
        # A book side on an account with no intent row today is a FIXED exposure (it is held
        # or resting already; no plan for today withdraws it).
        accts = {i["account"] for i in intents}
        for a, b in (books or {}).items():
            row = ((b or {}).get("symbols") or {}).get(symbol) if isinstance(b, dict) else None
            if not isinstance(row, dict) or a in accts:
                continue
            held = [s for s in ("long", "short") if row.get(s)]
            if held:
                intents.append({"account": a, "sleeve": "book", "symbol": symbol, "fixed": True,
                                "fixed_choice": "both" if len(held) == 2 else held[0],
                                "bracket": len(held) == 2, "placed": set(held),
                                "risk_frac": None, "edge": {}})
        out[f"{symbol}|{d}"] = intents
    return {"groups": out, "missing_inputs": missing}


def build(day: str | None = None, **kw: Any) -> Row:
    day = day or datetime.now(tz=UTC).date().isoformat()
    g = gather(day, **kw)
    plans = {}
    for key, intents in g["groups"].items():
        p = plan_group(intents)
        p["actual"] = actual_vs_plan(intents, p["plan"])
        p["intents"] = [{k: (sorted(v) if isinstance(v, set) else v) for k, v in i.items()}
                        for i in intents]
        plans[key] = p
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"), "day": day,
            "report_only": True, "verdict": (UNMEASURED if not plans else "PLANNED"),
            "missing_inputs": g["missing_inputs"], "plans": plans,
            "half_brackets_actual": sorted(f"{k}:{a['key']}" for k, p in plans.items()
                                           for a in p["actual"] if a["actual_half_bracket"]),
            "rule": ("one direction set per symbol/day maximising sum f*mu - f^2 E[R^2]/2 "
                     "subject to the cross-account fence; a lone bracket leg needs its own "
                     "measured edge; ties to fewer half-brackets")}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    day = args[args.index("--day") + 1] if "--day" in args else None
    doc = build(day)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"fence_planner: {len(doc['plans'])} group(s), half-brackets actual "
          f"{len(doc['half_brackets_actual'])}, missing {doc['missing_inputs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
