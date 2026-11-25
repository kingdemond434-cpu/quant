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
  EXPIRED  nothing sent by the deadline -> keep the hold and page. Never a lift on silence.

After the lift, `watch` compares the new release's rejects and bound failures with the previous
window for canary_watch_h hours: rejects >= 3 and above 2x the baseline, or ANY bound failure ->
rollback-with-hold.
"""
from __future__ import annotations

import json
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


def problems(r: Mapping[str, Any], symbol: str = SYMBOL) -> list[str]:
    """Why a SENT canary row is not a clean send; empty when it is."""
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
    if room is None:
        bad.append("no room to today's floor on the send: cannot bound it")
    elif at_stop > room + 1e-9:
        bad.append(f"risk at stop {at_stop:.2f} > room to today's floor {room:.2f}")
    return bad


def judge(hold: Mapping[str, Any] | None, journal: Iterable[Mapping[str, Any]],
          now: datetime) -> dict[str, Any]:
    """The canary verdict for the standing hold (None: no canary is up)."""
    if hold is None:
        return {"verdict": NONE}
    since = _ts(hold.get("at"))
    deadline = _ts(hold.get("deadline"))
    allow = {str(a) for a in (hold.get("allow") or [])}
    if since is None or deadline is None or not allow:
        return {"verdict": FAIL, "why": "the canary hold is unreadable or names no window"}
    clean, failed = [], []
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
            bad = problems(r)
            (failed if bad else clean).append({"at": r.get("at"), "window": r.get("window"),
                                               **({"why": bad} if bad else {})})
    if failed:
        return {"verdict": FAIL, "failed": failed, "clean": len(clean)}
    if clean:
        return {"verdict": PASS, "clean": clean}
    if now >= deadline:
        return {"verdict": EXPIRED, "why": f"no canary send by {deadline.isoformat()}"}
    return {"verdict": WAIT, "until": deadline.isoformat()}


def watch(lifted_at: datetime, journal: Iterable[Mapping[str, Any]], now: datetime,
          hours: float = DEFAULT_WATCH_H) -> dict[str, Any]:
    """After the lift: spike in rejects against the same span before the adoption, or any bound
    failure on any window -> SPIKE. Outside the watch span -> DONE."""
    if now > lifted_at + timedelta(hours=hours):
        return {"verdict": "DONE"}
    span = now - lifted_at
    before_from = lifted_at - span
    rej_now = rej_before = 0
    bound: list[dict[str, Any]] = []
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
            elif st == "SENT" and (bad := problems(r)):
                bound.append({"at": r.get("at"), "window": r.get("window"), "why": bad})
        elif t >= before_from and st == "REJECTED":
            rej_before += 1
    if bound or (rej_now >= SPIKE_MIN_REJECTS and rej_now > 2 * rej_before):
        return {"verdict": "SPIKE", "rejects": rej_now, "baseline": rej_before, "bound": bound}
    return {"verdict": "OK", "rejects": rej_now, "baseline": rej_before}
