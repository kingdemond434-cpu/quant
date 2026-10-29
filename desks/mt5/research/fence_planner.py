"""THE FENCE-AWARE PLANNER: one direction set per symbol and day across E8, FTMO and Fusion.

WHY (2026-10-29 04:24Z). `mt5desk.cross_account.opposite_block` refuses an order whose side is
opposite an OPEN or PENDING position of another account on the same symbol. It is right to refuse,
but it decides leg by leg, in whatever order the lanes' clocks happen to reach it. On 10-29 E8
held or rested a gold short, so Fusion's gold_asia buy_stop was refused while its sell_stop
placed: Fusion carried HALF a bracket that nothing had chosen. A bracket certificate measures the
two-sided entry; its lone short leg has no evidence of its own.

WHAT THIS DOES (REPORT-ONLY; it never sends, cancels or changes the fence). For every symbol and
day it gathers each account's intended orders and, over every assignment of {both, long, short,
none} per intent that the fence allows, picks the one that maximises combined
Delta E[log W] = sum_a ( f_a * mu_a - f_a^2 * E[R^2]_a / 2 ).

FEASIBILITY.
  * The cross-account fence (fusion <-> e8, `cross_account.ACCOUNTS`): no account carries a side
    opposite another account's side; a resting bracket counts as both sides.
  * FTMO is NOT a fence account. Its own rule (prop/ftmo_follower.py:1056-1060 and its docstring
    rule 3) is modelled instead: FTMO only FOLLOWS E8's single direction, never a bracket, and
    never opposite its own book. An FTMO choice is feasible only when E8's choice is exactly that
    one side.
  * BOOKS ARE ALWAYS FIXED. Each account's live book (`cross_account.read_book`, its MAX_AGE_S,
    key join and in-flight semantics; FTMO's via `gold_oco.read_lane`) is merged as an immovable
    `<acct>:book` intent EVEN when the account has intent rows today -- what rests or is held is
    already there. An absent, stale or unreadable book is a MISSING INPUT and makes every group
    UNMEASURED. A past day has no live book, so a past day is UNMEASURED too.

EVIDENCE (named). Edge per side comes from ONE source, EDGE_SOURCE: the realised R of the base
sleeve's closed trades in data/live_ledger.jsonl (gold_asia_v2/_v3/_v4 read gold_asia's), the
entry side read from the stop's side of the entry, R = pl_quote / |risk_quote|, at least
MIN_EDGE_N trades per side (the bracket's mu uses all of them). sleeves.json carries no edge
fields and no certificate artifact in this tree carries a per-side expectancy, so anything short of
MIN_EDGE_N is UNMEASURED. risk_frac comes from CERT_BOOK_LIVE[account][sleeve or base], else a
positive sleeves.json risk_frac; CERT_BOOK_LIVE.fusion has no gold_asia key, so Fusion's gold_asia
risk is UNMEASURED today.

VERDICTS. A group is PLANNED only when no input is missing and no alternative with any non-fixed
leg rests on an unmeasured input; otherwise UNMEASURED (its ranking is still shown, never counted).
Ties go to fewer half-brackets. `divergent_measured_symbol_days` counts PLANNED groups whose actual
differs from the plan -- an UNMEASURED plan is never a divergence.

Writes reports/FENCE_PLAN.json and upserts one row per day into reports/fence_plan_history.jsonl.
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Row = dict[str, Any]
DESK = Path(__file__).resolve().parent.parent
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))
OUT = DESK / "reports" / "FENCE_PLAN.json"
HISTORY = DESK / "reports" / "fence_plan_history.jsonl"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
E8_INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
FTMO_INTENTS = DESK / "data" / "ftmo_follower_intents.jsonl"
CERT_BOOK = DESK / "data" / "CERT_BOOK_LIVE.json"
SLEEVES = DESK / "data" / "sleeves.json"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
EDGE_SOURCE = ("data/live_ledger.jsonl realised R per base sleeve and entry side "
               "(side from stop vs entry; R = pl_quote/|risk_quote|)")
MIN_EDGE_N = 10
UNMEASURED = "UNMEASURED"
CHOICES = ("both", "long", "short", "none")
LONG_SIDES = {"buy_stop", "buy_limit", "buy", "long"}
SHORT_SIDES = {"sell_stop", "sell_limit", "sell", "short"}
FENCE_ACCOUNTS = ("fusion", "e8")
PLACED_STATUSES = ("PLACED", "SENT", "FILLED", "ADOPTED", "RESTING")


def side_dir(side: object) -> str | None:
    s = str(side or "").strip().lower()
    return "long" if s in LONG_SIDES else "short" if s in SHORT_SIDES else None


def base_sleeve(name: object) -> str:
    return re.sub(r"_v\d+$", "", str(name or ""))


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
    """Delta E[log W] of `choice` for one intent, with what it rests on. A fixed book is sunk."""
    if choice == "none" or intent.get("fixed"):
        return {"delta_elogw": 0.0, "half_bracket": False, "unmeasured": []}
    f = _num(intent.get("risk_frac"))
    edge = intent.get("edge") or {}
    rr = _num(intent.get("rr"))
    bracket = bool(intent.get("bracket"))
    half = bracket and choice != "both"
    key = "bracket" if choice == "both" else choice
    mu = _num(edge.get(key)) if (choice != "both" or bracket) else None
    missing = [n for n, v in (("risk_frac", f), (f"edge.{key}", mu)) if v is None]
    if missing or f is None or mu is None:
        return {"delta_elogw": 0.0, "half_bracket": half, "unmeasured": missing}
    return {"delta_elogw": elogw(f, mu, rr), "half_bracket": half, "unmeasured": []}


def allowed_choices(intent: Mapping[str, Any]) -> tuple[str, ...]:
    if intent.get("fixed"):
        return (str(intent.get("fixed_choice") or "none"),)
    if str(intent.get("account")) == "ftmo":
        d = side_dir(intent.get("direction"))
        return (d, "none") if d else ("long", "short", "none")
    if intent.get("bracket"):
        return CHOICES
    d = side_dir(intent.get("direction"))
    return (d, "none") if d else ("none",)


def feasible(acct: Mapping[str, set[str]], ftmo_new: set[str] | None = None) -> bool:
    """No account opposite another (the fusion<->e8 fence; FTMO's HELD book joins it through
    gold_oco's one-direction-a-day lock, so FTMO holding while E8 is flat is feasible), and
    FTMO's NEW legs follow E8's single direction only."""
    for a, b in itertools.combinations(list(acct), 2):
        sa, sb = acct[a], acct[b]
        if ("long" in sa and "short" in sb) or ("short" in sa and "long" in sb):
            return False
    ft = ftmo_new or set()
    return not (ft and (len(ft) != 1 or acct.get("e8") != ft))


def plan_group(intents: list[Row], missing: list[str] | None = None) -> Row:
    """Every feasible assignment, ranked; the first is the plan."""
    keys = [f"{i['account']}:{i.get('sleeve') or '-'}" for i in intents]
    alts: list[Row] = []
    for combo in itertools.product(*(allowed_choices(i) for i in intents)):
        by_acct: dict[str, set[str]] = {}
        legs: dict[str, int] = {}
        ftmo_new: set[str] = set()
        for i, c in zip(intents, combo, strict=True):
            a = str(i["account"])
            by_acct.setdefault(a, set()).update(sides_of(c))
            legs[a] = legs.get(a, 0) + (c != "none")
            if a == "ftmo" and not i.get("fixed"):
                ftmo_new |= sides_of(c)
        # One account never hedges itself across sleeves or against its own book.
        own_ok = all(not (s == {"long", "short"} and legs[a] > 1) for a, s in by_acct.items())
        if not (own_ok and feasible(by_acct, ftmo_new)):
            continue
        vals = [value(i, c) for i, c in zip(intents, combo, strict=True)]
        active = any(c != "none" and not i.get("fixed")
                     for i, c in zip(intents, combo, strict=True))
        alts.append({"assignment": dict(zip(keys, combo, strict=True)),
                     "delta_elogw": round(sum(v["delta_elogw"] for v in vals), 12),
                     "half_brackets": sum(1 for v in vals if v["half_bracket"]),
                     "active": active,
                     "unmeasured": sorted({f"{k}:{u}" for k, v in zip(keys, vals, strict=True)
                                           for u in v["unmeasured"]})})
    alts.sort(key=lambda a: (-a["delta_elogw"], a["half_brackets"], len(a["unmeasured"])))
    if not alts:
        return {"verdict": "NO_FEASIBLE_PLAN", "plan": None, "alternatives": [], "why": ""}
    best = alts[0]["delta_elogw"]
    for alt in alts:
        alt["delta_vs_plan"] = round(alt["delta_elogw"] - best, 12)
    why = ""
    if missing:
        why = "missing inputs: " + "; ".join(missing)
    elif any(a["active"] and a["unmeasured"] for a in alts):
        why = "an alternative with a live leg rests on an unmeasured input"
    return {"verdict": UNMEASURED if why else "PLANNED", "why": why, "plan": alts[0],
            "alternatives": alts[1:]}


def actual_vs_plan(intents: list[Row], plan: Mapping[str, Any] | None,
                   measured: bool) -> list[Row]:
    out = []
    for i in intents:
        k = f"{i['account']}:{i.get('sleeve') or '-'}"
        placed = sorted(set(i.get("placed") or []))
        actual = "both" if placed == ["long", "short"] else placed[0] if placed else "none"
        planned = (plan or {}).get("assignment", {}).get(k)
        out.append({"key": k, "actual": actual, "planned": planned,
                    "diverges": bool(measured and planned is not None and planned != actual),
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


def edges_from_ledger(rows: Iterable[Row]) -> dict[str, dict[str, Any]]:
    """Per base sleeve: {bracket, long, short} mean R (None below MIN_EDGE_N) and the n."""
    acc: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        e, sl = _num(r.get("entry_price")), _num(r.get("sl"))
        pl, rq = _num(r.get("pl_quote")), _num(r.get("risk_quote"))
        if None in (e, sl, pl, rq) or not rq or e == sl:
            continue
        assert e is not None and sl is not None and pl is not None and rq is not None
        d = "short" if sl > e else "long"
        b = acc.setdefault(base_sleeve(r.get("sleeve")), {"long": [], "short": []})
        b[d].append(pl / abs(rq))
    out: dict[str, dict[str, Any]] = {}
    for name, b in acc.items():
        allr = b["long"] + b["short"]
        out[name] = {"bracket": sum(allr) / len(allr) if len(allr) >= MIN_EDGE_N else None,
                     "long": sum(b["long"]) / len(b["long"]) if len(b["long"]) >= MIN_EDGE_N
                     else None,
                     "short": sum(b["short"]) / len(b["short"])
                     if len(b["short"]) >= MIN_EDGE_N else None,
                     "n": {"long": len(b["long"]), "short": len(b["short"])}}
    return out


def _same(a: str, b: str) -> bool:
    try:
        from mt5desk import cross_account as xa
        return bool(xa.same_instrument(a, b))
    except Exception:
        return a.upper()[:6] == b.upper()[:6]


def quiet_read_book(account: str, *, now: datetime | None = None) -> tuple[Row | None, str]:
    """`cross_account.read_book`'s semantics (full book of this account, MAX_AGE_S, the
    declared key, in-flight sends held both ways) WITHOUT its side effects: `read_book` calls
    `key_joins`, which pages and CLEARS the fence's key alert; a report must never do either."""
    from mt5desk import cross_account as xa
    try:
        doc = json.loads(xa.book_path(account).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"the {account} book is absent or unreadable ({type(exc).__name__})"
    try:
        at = datetime.fromisoformat(str(doc["at"]))
        if at.tzinfo is None:
            raise ValueError("naive timestamp")
        age = ((now or datetime.now(tz=UTC)) - at).total_seconds()
        symbols = doc["symbols"]
        if doc.get("account") != account or doc.get("covers") != "all" \
                or not isinstance(symbols, dict):
            raise ValueError("not a full book of this account")
        key = doc.get("account_key")
        if not xa.valid_key(key):
            raise ValueError("the book names no account")
        book = {xa.norm(k): {"long": bool(v.get("long")), "short": bool(v.get("short"))}
                for k, v in symbols.items()}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return None, f"the {account} book is malformed ({type(exc).__name__})"
    if not (-60.0 <= age <= xa.MAX_AGE_S):
        return None, f"the {account} book is {age:.0f}s old (limit {xa.MAX_AGE_S:.0f}s)"
    want = xa.expected_key(account)
    if want is not None and (str(want).startswith("invalid:") or key != want):
        return None, f"the {account} book is of another account than the one this box declares"
    try:
        held = xa.inflight(account, now=now)
    except (OSError, ValueError, TypeError) as exc:
        return None, f"the {account} in-flight file is unreadable ({type(exc).__name__})"
    for sym in held:
        book[sym] = {"long": True, "short": True}
    return book, f"{account} book {age:.0f}s old"


def live_books(now: datetime | None = None) -> dict[str, tuple[Row | None, str]]:
    """{acct: (exposure {SYM: {long, short}} or None, why)} with the fence's own semantics."""
    out: dict[str, tuple[Row | None, str]] = {}
    try:
        from mt5desk import cross_account as xa
        for a in xa.ACCOUNTS:
            book, why = quiet_read_book(a, now=now)
            out[a] = (dict(book) if book is not None else None, why)
    except Exception as exc:
        for a in FENCE_ACCOUNTS:
            out[a] = (None, f"cross_account unavailable ({type(exc).__name__})")
    try:
        from mt5desk import gold_oco as oco
        doc, why = oco.read_lane("ftmo", now=now)
        if doc is None:
            out["ftmo"] = (None, why)
        else:
            row = {"long": False, "short": False}
            for r in [*(doc.get("positions") or []), *(doc.get("orders") or [])]:
                s = oco.side_of((r or {}).get("side"))
                if s:
                    row[s] = True
            out["ftmo"] = ({"XAUUSD": row}, why)
    except Exception as exc:
        out["ftmo"] = (None, f"gold_oco unavailable ({type(exc).__name__})")
    return out


def gather(day: str, *, decisions: list[Row] | None = None, e8: list[Row] | None = None,
           ftmo: list[Row] | None = None, cert: Row | None = None,
           sleeves: list[Any] | None = None, ledger: list[Row] | None = None,
           books: Mapping[str, tuple[Row | None, str]] | None = None,
           today: str | None = None) -> Row:
    """Intents per (symbol, day). Every argument stands in for its file (tests)."""
    decisions = _jsonl(DECISIONS) if decisions is None else decisions
    e8 = _jsonl(E8_INTENTS) if e8 is None else e8
    ftmo = _jsonl(FTMO_INTENTS) if ftmo is None else ftmo
    cert = _json(CERT_BOOK) if cert is None else cert
    if sleeves is None:
        sl = _json(SLEEVES).get("sleeves")
        sleeves = sl if isinstance(sl, list) else []
    ledger = _jsonl(LIVE_LEDGER) if ledger is None else ledger
    today = today or datetime.now(tz=UTC).date().isoformat()
    missing: list[str] = []
    if books is None:
        if day == today:
            books = live_books()
        else:
            books = {}
            missing.append(f"books: {day} is past; no live book reads that day")
    for a in ("fusion", "e8", "ftmo"):
        b = books.get(a)
        if b is None:
            missing.append(f"book:{a}: not read")
        elif b[0] is None:
            missing.append(f"book:{a}: {b[1]}")
    edges = edges_from_ledger(ledger)
    srisk = {str(s.get("name")): _num(s.get("risk_frac")) for s in sleeves
             if isinstance(s, dict)}
    if not cert:
        missing.append("CERT_BOOK_LIVE")
    groups: dict[tuple[str, str], dict[str, Row]] = {}

    def risk_of(account: str, sleeve: str, row: Row) -> float | None:
        for v in (_num(row.get("risk_frac")),
                  _num((cert.get(account) or {}).get(sleeve)),
                  _num((cert.get(account) or {}).get(base_sleeve(sleeve)))):
            if v is not None:
                return v
        v = srisk.get(sleeve)
        return v if v else None

    def add(account: str, sleeve: str, symbol: str, side: object, row: Row,
            placed: bool) -> None:
        d = side_dir(side)
        if d is None:
            return
        g = groups.setdefault((symbol.upper(), day), {})
        e = edges.get(base_sleeve(sleeve)) or {}
        it = g.setdefault(f"{account}:{sleeve}", {
            "account": account, "sleeve": sleeve, "symbol": symbol.upper(), "sides": set(),
            "placed": set(), "risk_frac": risk_of(account, sleeve, row),
            "edge": {k: e.get(k) for k in ("bracket", "long", "short")},
            "edge_n": e.get("n"), "rr": None})
        it["sides"].add(d)
        if placed:
            it["placed"].add(d)
        p, s, t = _num(row.get("price")), _num(row.get("sl")), _num(row.get("tp"))
        if p is not None and s is not None and t is not None and abs(p - s) > 0:
            it["rr"] = abs(t - p) / abs(p - s)

    for r in decisions:
        if str(r.get("time") or r.get("decided_at") or "")[:10] != day:
            continue
        if not str(r.get("side") or "").endswith(("_stop", "_limit")):
            continue
        add("fusion", str(r.get("sleeve") or r.get("strategy_id") or "-"),
            str(r.get("symbol") or "XAUUSD"), r.get("side"), r,
            bool(r.get("taken")) or r.get("outcome") == "EXECUTED")
    for acct, rows in (("e8", e8), ("ftmo", ftmo)):
        for r in rows:
            if str(r.get("at") or "")[:10] != day or not r.get("window"):
                continue
            add(acct, str(r["window"]), str(r.get("symbol") or "XAUUSD"), r.get("side"), r,
                str(r.get("status") or "").upper() in PLACED_STATUSES)
    out: dict[str, list[Row]] = {}
    for (symbol, d), g in groups.items():
        intents = []
        for it in g.values():
            it["bracket"] = it["sides"] == {"long", "short"}
            it["direction"] = next(iter(it["sides"])) if len(it["sides"]) == 1 else None
            intents.append(it)
        # Every readable book is merged as FIXED, MINUS the sides the account's own placed
        # intents for this symbol/day explain (its own resting or filled bracket is the intent,
        # not a fixed position against it -- audit v2 must-fix 2). Every book symbol that is the
        # same instrument is merged (cross_account.same_instrument).
        for a, (book, _why) in (books or {}).items():
            own = set()
            for it in intents:
                if it["account"] == a:
                    own |= set(it.get("placed") or ())
            merged = {"long": False, "short": False}
            for bsym, brow in (book or {}).items():
                if isinstance(brow, dict) and _same(str(bsym), symbol):
                    merged["long"] |= bool(brow.get("long"))
                    merged["short"] |= bool(brow.get("short"))
            held = [s for s in ("long", "short") if merged[s] and s not in own]
            if held:
                intents.append({"account": a, "sleeve": "book", "symbol": symbol, "fixed": True,
                                "fixed_choice": "both" if len(held) == 2 else held[0],
                                "bracket": False, "placed": set(held),
                                "risk_frac": None, "edge": {}})
        out[f"{symbol}|{d}"] = intents
    return {"groups": out, "missing_inputs": missing, "edge_source": EDGE_SOURCE,
            "edges": edges}


def build(day: str | None = None, **kw: Any) -> Row:
    day = day or datetime.now(tz=UTC).date().isoformat()
    g = gather(day, **kw)
    plans = {}
    for key, intents in g["groups"].items():
        p = plan_group(intents, g["missing_inputs"])
        p["actual"] = actual_vs_plan(intents, p["plan"], p["verdict"] == "PLANNED")
        p["intents"] = [{k: (sorted(v) if isinstance(v, set) else v) for k, v in i.items()}
                        for i in intents]
        plans[key] = p
    divergent = sorted(k for k, p in plans.items() if any(a["diverges"] for a in p["actual"]))
    measured = [k for k, p in plans.items() if p["verdict"] == "PLANNED"]
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"), "day": day,
            "report_only": True,
            "verdict": "PLANNED" if plans and len(measured) == len(plans) else UNMEASURED,
            "missing_inputs": g["missing_inputs"], "edge_source": g["edge_source"],
            "min_edge_n": MIN_EDGE_N, "plans": plans,
            "measured_symbol_days": len(measured),
            "divergent_measured_symbol_days": len(divergent), "divergent": divergent,
            "half_brackets_actual": sorted(f"{k}:{a['key']}" for k, p in plans.items()
                                           for a in p["actual"] if a["actual_half_bracket"]),
            "rule": ("one direction set per symbol/day maximising sum f*mu - f^2 E[R^2]/2 "
                     "subject to the fusion<->e8 fence and FTMO's follow-E8 rule; books fixed; "
                     "a lone bracket leg needs its own measured edge; ties to fewer "
                     "half-brackets")}


def window_metric(path: Path, day: str, days: int = 14) -> int | None:
    """Divergent MEASURED symbol-days over the `days` days ending `day` (the falsifier's
    window), or None when the history holds none of them."""
    from datetime import date, timedelta
    try:
        end = date.fromisoformat(day)
    except ValueError:
        return None
    lo = (end - timedelta(days=days - 1)).isoformat()
    rows = [r for r in _jsonl(path, tail=100000) if lo <= str(r.get("day") or "") <= day]
    if not rows:
        return None
    return sum(int(r.get("divergent_measured_symbol_days") or 0) for r in rows)


def upsert_history(doc: Row, path: Path = HISTORY) -> None:
    """One row per day: today's row is replaced each pass, other days are kept."""
    rows = [r for r in _jsonl(path, tail=100000) if r.get("day") != doc["day"]]
    rows.append({k: doc[k] for k in ("day", "generated_utc", "verdict", "missing_inputs",
                                     "measured_symbol_days", "divergent_measured_symbol_days",
                                     "divergent", "half_brackets_actual")}
                | {"plans": {k: {"verdict": p["verdict"],
                                 "plan": (p["plan"] or {}).get("assignment"),
                                 "delta_elogw": (p["plan"] or {}).get("delta_elogw")}
                             for k, p in doc["plans"].items()}})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), "utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    day = args[args.index("--day") + 1] if "--day" in args else None
    doc = build(day)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    upsert_history(doc)
    doc["divergent_measured_symbol_days_14d"] = window_metric(HISTORY, doc["day"])
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"fence_planner: {len(doc['plans'])} group(s) {doc['verdict']}, divergent "
          f"{doc['divergent_measured_symbol_days']}, missing {doc['missing_inputs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
