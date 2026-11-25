"""THE ADOPT CANARY: what releases new risk after an adoption (pre-mortem #1; Audit 2026-11-25
19:48Z, sizing bound 19:49Z). Pure: reads journals, returns a verdict; the CLI and Adopt-And-Seal
act on it.

After an adoption lands new code, `arm` puts up the `adopt_canary` hold (libs/ops/new_risk_hold):
every lane stays held except the canary window(s) on its allow-list (ADOPT_POLICY canary_allow,
default the E8 gold Asia window, `asia`).
`judge` then reads the E8 gold intents journal for sends since the
hold went up:

  FAIL   any REJECTED send of a canary window, or a SENT one that fails a check:
           - lot > 0 and sl/tp present on the correct side of the entry for the side
           - the lane's own logged sizing agrees with what it sent: lot x |entry-sl| x contract is
             within 10% of the row's risk_usd
           - INDEPENDENT BOUND (does not re-derive sizing): lot x |entry-sl| x contract size (this
             module's table, not the lane's) <= risk_frac x equity x 1.10 AND <= room_to_floor
         -> rollback-with-hold to the pre-adoption head, and a page.
  PASS   at least one SENT canary row that passes every check and no failure -> lift the hold.
  WAIT   nothing sent yet, before the deadline -> keep the hold.
  EXPIRED  nothing sent by the deadline -> page, and lift INTO THE POST-LIFT WATCH (Audit should-fix
         1: a hold on silence kept every lane shut indefinitely; a rollback on silence would undo
         an audited delivery for want of a setup). The watch still rolls back on any bound
         failure or reject spike. A canary window that has sent nothing ARMED in 7 days is not
         armed at all: the adoption goes straight to the watch, and pages.
  Every check also runs per WINDOW: all legs of one placement summed must fit the room to the
  floor (an OCO whose cancel fails fills both), and each leg's risk_frac must not exceed the
  allocator's published budget (cert book, capped by the E8 code ceiling; read from the files).

After the lift, `watch` compares the new release's rejects and bound failures with the previous
window for canary_watch_h hours: rejects >= 3 and above 2x the baseline, or ANY bound failure ->
rollback-with-hold.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

INTENTS_REL = "desks/mt5/data/e8_gold_intents.jsonl"
#: Contract size per lot by symbol, held here so the bound never trusts the lane's own figure.
#: A symbol not in this table cannot be bounded, so it can never PASS (doubt keeps the hold).
CONTRACT = {"XAUUSD": 100.0}
SYMBOL = "XAUUSD"
BUDGET_SLACK = 1.10
LANE_AGREE = 0.10
#: e8_gold names its windows bare ("asia"), not by the book's gold keys ("gold_asia").
DEFAULT_ALLOW = ("asia",)
DEFAULT_DEADLINE_H = 24.0
DEFAULT_WATCH_H = 24.0
SPIKE_MIN_REJECTS = 3

PASS, FAIL, WAIT, EXPIRED, NONE = "PASS", "FAIL", "WAIT", "EXPIRED", "NONE"
#: The lift record the post-lift watch reads (release, the head to go back to, when it lifted).
STATE_REL = "desks/mt5/reports/ADOPT_CANARY.json"


def load_state(root: Path) -> dict[str, Any]:
    try:
        doc = json.loads((root / STATE_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def save_state(root: Path, doc: Mapping[str, Any]) -> bool:
    f = root / STATE_REL
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(doc), indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(f)
    except OSError:
        return False
    return True


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


#: THE ALLOCATOR'S PUBLISHED BUDGET (Audit should-fix 3): the certified book's window value when
#: an enabled book names it, never above the principal's code ceiling. Read from the files, not
#: from the lane, so a lane that logs an inflated risk_frac cannot vouch for itself.
CERT_BOOK_REL = "desks/mt5/data/CERT_BOOK_LIVE.json"
CEILING_SRC_REL = "desks/mt5/mt5desk/decision_core.py"
_CEILING = re.compile(r"(?m)^E8_CERT_CEILING\s*=\s*([0-9.]+)\s*$")
RECENT_DAYS = 7


def published_frac(root: Path, window: str) -> tuple[float | None, str]:
    """(the window's published risk fraction cap, where it came from); None when unreadable."""
    try:
        m = _CEILING.search((root / CEILING_SRC_REL).read_text(encoding="utf-8"))
        ceiling = float(m.group(1)) if m else None
    except (OSError, ValueError):
        ceiling = None
    if ceiling is None or not ceiling > 0:
        return None, "the E8 code ceiling could not be read"
    try:
        book = json.loads((root / CERT_BOOK_REL).read_text(encoding="utf-8"))
        v = book["e8"][f"gold_{window}"] if book.get("enabled") is True else None
        v = None if isinstance(v, bool) else float(v) if v is not None else None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        v = None
    if v is not None and 0 <= v <= ceiling:
        return v, "cert_book"
    return ceiling, "e8_code_ceiling"


def recently_armed(journal: Iterable[Mapping[str, Any]], allow: Iterable[str], now: datetime,
                   days: float = RECENT_DAYS) -> bool:
    """Has a canary window sent an ARMED order lately? If not, a canary would wait forever."""
    want = {str(a) for a in allow}
    since = now - timedelta(days=days)
    for r in journal:
        t = _ts(r.get("at"))
        if (t is not None and t >= since and str(r.get("window")) in want
                and r.get("armed") is True and r.get("status") == "SENT"):
            return True
    return False


def rows(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = (root / INTENTS_REL).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def problems(r: Mapping[str, Any], symbol: str = SYMBOL,
             cap: float | bool | None = False) -> list[str]:
    """Why a SENT canary row is not a clean send; empty when it is.

    `cap`: the window's published risk fraction (published_frac). None = unreadable (a problem);
    False = not checked (pure callers and tests of the other checks)."""
    bad: list[str] = []
    lot, px, sl, tp = (_f(r.get(k)) for k in ("lot", "price", "sl", "tp"))
    side = str(r.get("side") or "")
    if not lot or lot <= 0:
        return [f"lot {r.get('lot')!r} is not positive"]
    if px is None or sl is None or tp is None:
        return ["entry, sl or tp missing"]
    long = side.startswith("buy")
    if not (side.startswith(("buy", "sell"))):
        return [f"side {side!r} unknown"]
    if (long and not sl < px < tp) or (not long and not tp < px < sl):
        bad.append(f"bracket on the wrong side for {side}: sl {sl} entry {px} tp {tp}")
    contract = CONTRACT.get(symbol)
    if contract is None:
        return [*bad, f"no contract size for {symbol}: cannot bound the risk"]
    if _f(r.get("contract_size")) not in (None, contract):
        bad.append(f"lane contract {r.get('contract_size')} != {contract}")
    at_stop = lot * abs(px - sl) * contract
    logged = _f(r.get("risk_usd"))
    if logged is None or logged <= 0:
        bad.append("the lane logged no sized risk for this send")
    elif abs(at_stop - logged) > LANE_AGREE * logged:
        bad.append(f"sent risk {at_stop:.2f} disagrees with the lane's sized risk {logged:.2f}")
    frac, equity, room = (_f(r.get(k)) for k in ("risk_frac", "equity", "room_to_floor"))
    if frac is None or equity is None or equity <= 0:
        bad.append("no published risk budget or equity on the send: cannot bound it")
    elif at_stop > frac * equity * BUDGET_SLACK + 1e-9:
        bad.append(f"risk at stop {at_stop:.2f} > budget {frac} x {equity:.2f} x {BUDGET_SLACK}")
    if cap is None:
        bad.append("the allocator's published budget could not be read: cannot bound it")
    elif cap is not False:
        if frac is not None and frac > float(cap) + 1e-12:
            bad.append(f"the lane's risk_frac {frac} > the published budget {cap}")
        if equity and equity > 0 and at_stop > float(cap) * equity * BUDGET_SLACK + 1e-9:
            bad.append(f"risk at stop {at_stop:.2f} > published {cap} x {equity:.2f} x "
                       f"{BUDGET_SLACK}")
    if room is None:
        bad.append("no room to today's floor on the send: cannot bound it")
    elif at_stop > room + 1e-9:
        bad.append(f"risk at stop {at_stop:.2f} > room to today's floor {room:.2f}")
    return bad


def _at_stop(r: Mapping[str, Any], symbol: str = SYMBOL) -> float:
    lot, px, sl = (_f(r.get(k)) for k in ("lot", "price", "sl"))
    return (lot or 0.0) * abs((px or 0.0) - (sl or 0.0)) * CONTRACT.get(symbol, 0.0)


def window_sums(sent: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Every leg of one window placement (same window, same `at`) summed against the room to the
    floor: an OCO whose cancel fails can fill both legs (Audit should-fix 4). Pure."""
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for r in sent:
        groups.setdefault((str(r.get("window")), str(r.get("at"))), []).append(r)
    out = []
    for (w, at), legs in groups.items():
        total = sum(_at_stop(r) for r in legs)
        rooms = [x for x in (_f(r.get("room_to_floor")) for r in legs) if x is not None]
        if not rooms:
            out.append({"at": at, "window": w, "why": ["no room to the floor on the window"]})
        elif total > min(rooms) + 1e-9:
            out.append({"at": at, "window": w,
                        "why": [f"window risk at stop {total:.2f} (all legs) > room "
                                f"{min(rooms):.2f}"]})
    return out


def judge(hold: Mapping[str, Any] | None, journal: Iterable[Mapping[str, Any]],
          now: datetime, caps: Mapping[str, float | None] | None = None) -> dict[str, Any]:
    """The canary verdict for the standing hold (None: no canary is up)."""
    if hold is None:
        return {"verdict": NONE}
    since = _ts(hold.get("at"))
    deadline = _ts(hold.get("deadline"))
    allow = {str(a) for a in (hold.get("allow") or [])}
    if since is None or deadline is None or not allow:
        return {"verdict": FAIL, "why": "the canary hold is unreadable or names no window"}
    clean, failed, sent = [], [], []
    for r in journal:
        t = _ts(r.get("at"))
        if t is None or t < since or str(r.get("window")) not in allow:
            continue
        if r.get("armed") is False:  # a paper pass proves nothing about live sends
            continue
        st = str(r.get("status") or "")
        if st == "REJECTED":
            failed.append({"at": r.get("at"), "window": r.get("window"), "why": "REJECTED"})
        elif st == "SENT":
            sent.append(r)
            cap = caps.get(str(r.get("window"))) if caps is not None else False
            bad = problems(r, cap=cap)
            (failed if bad else clean).append({"at": r.get("at"), "window": r.get("window"),
                                               **({"why": bad} if bad else {})})
    failed += window_sums(sent)
    if failed:
        return {"verdict": FAIL, "failed": failed, "clean": len(clean)}
    if clean:
        return {"verdict": PASS, "clean": clean}
    if now >= deadline:
        return {"verdict": EXPIRED, "why": f"no canary send by {deadline.isoformat()}"}
    return {"verdict": WAIT, "until": deadline.isoformat()}


def watch(lifted_at: datetime, journal: Iterable[Mapping[str, Any]], now: datetime,
          hours: float = DEFAULT_WATCH_H,
          caps: Mapping[str, float | None] | None = None) -> dict[str, Any]:
    """After the lift: spike in rejects against the same span before the adoption, or any bound
    failure on any window -> SPIKE. Outside the watch span -> DONE."""
    if now > lifted_at + timedelta(hours=hours):
        return {"verdict": "DONE"}
    span = now - lifted_at
    before_from = lifted_at - span
    rej_now = rej_before = 0
    bound: list[dict[str, Any]] = []
    sent: list[Mapping[str, Any]] = []
    for r in journal:
        t = _ts(r.get("at"))
        if t is None:
            continue
        st = str(r.get("status") or "")
        if r.get("armed") is False:
            continue
        if t >= lifted_at:
            if st == "REJECTED":
                rej_now += 1
            elif st == "SENT":
                sent.append(r)
                cap = caps.get(str(r.get("window"))) if caps is not None else False
                if bad := problems(r, cap=cap):
                    bound.append({"at": r.get("at"), "window": r.get("window"), "why": bad})
        elif t >= before_from and st == "REJECTED":
            rej_before += 1
    bound += window_sums(sent)
    if bound or (rej_now >= SPIKE_MIN_REJECTS and rej_now > 2 * rej_before):
        return {"verdict": "SPIKE", "rejects": rej_now, "baseline": rej_before, "bound": bound}
    return {"verdict": "OK", "rejects": rej_now, "baseline": rej_before}
