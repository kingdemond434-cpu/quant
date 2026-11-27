"""COUNTERPARTY REGISTER -- each account's withdrawable profit valued as a risky claim on the firm
that holds it, not as cash (IDEA_QUEUE row 227).

INPUT. `desks/mt5/data/counterparty_register.json` (committed, seeded from public facts): per firm
the entity, regulator, payout caps and rules, last rule-change date and public trust events (each
with a URL and a date), a `p_default_prior` that is a stated ASSUMPTION, owner wealth outside the
accounts, and account LABELS. An operator file replaces the `owner` and `accounts` blocks:
`--accounts FILE`, or by default `desks/mt5/data/counterparty_accounts.local.json`
(`ACCOUNTS_LOCAL`, gitignored -- owner money never enters a tracked file).

THE TRACKED SEED CARRIES NO MONEY (Auditor MF4). Every `*_usd` field in it is null, and the firms'
public payout caps are `per_payout_cap` with `per_payout_cap_unit`. A seed (any `--register` file)
holding a non-null `*_usd` value anywhere is REFUSED: the whole report reads UNMEASURED and names
the offending fields, because money in a committed file would be published by git itself. Nothing here reads live sizing, the
allocator, the gateway or any broker state, and nothing here feeds them: REPORT ONLY.

HAIRCUT WITHDRAWABLE VALUE. p = the firm's annual default prior; per-day hazard
h = -ln(1 - p) / 365. Withdrawable profit P is paid on the firm's payout schedule: payout k
(k = 0, 1, ...) at t_k = k * interval_days, amount x_k = min(remaining, per_payout_cap), until P is
paid or the remaining payout count (max_payouts - payouts_taken) is spent. Then

    nominal  = sum_k x_k                       (profit the caps let out at all)
    forfeit  = P - nominal                     (beyond the cap schedule: worth 0 here)
    haircut  = sum_k x_k * exp(-h * t_k)       (each payout survives to its own date)

An uncapped firm (cap null) pays P at t = 0. A payout-count cap with `payouts_taken` unknown is
UNMEASURED (the remaining count is the unknown), never "assume none taken".

WITHDRAW NOW VERSUS HOLD, in owner-level E[log W] over a horizon H days (q = exp(-h * H) is the
chance the firm is still paying at H). W0 = owner wealth outside the accounts (must be > 0, or the
log is undefined and the row is UNMEASURED). x0 = the first payout available now, g = the
operator's expected extra profit from leaving the buffer in (`hold_gain_usd`, default 0):

    E_now  = q * ln(W0 + P)      + (1 - q) * ln(W0 + x0)
    E_hold = q * ln(W0 + P + g)  + (1 - q) * ln(W0)
    delta_elogw = E_now - E_hold   (> 0: log growth favours withdrawing now)

Where the firm caps the payout COUNT and x0 is below the per-payout cap, withdrawing now spends a
capped slot on a short payout; the row flags `spends_capped_slot` because this one-horizon model
does not price that.

AUDIT CLASSES. UNMEASURED is never 0 and always carries a reason. Inputs are size-bounded and the
pass is time-bounded (`budget`). Every key copied through is scrubbed with the repo's
`login_fence.is_login_key`, and an account label that is itself account-number shaped is withheld.

    python desks/mt5/research/counterparty_register.py [--accounts FILE] [--horizon-days 30]
        [--p-default "E8 Markets=0.2"]
Writes `desks/mt5/reports/counterparty_register.json` through `publishable`: every money amount
becomes a fraction of the account's own withdrawable profit, and no amount of money is published.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `counterparty_register` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import counterparty_register as M; M.main()"
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTER = DESK / "data" / "counterparty_register.json"
#: The operator's owner/accounts file. Gitignored (.gitignore, Auditor MF4); read when present.
ACCOUNTS_LOCAL = DESK / "data" / "counterparty_accounts.local.json"
OUT = DESK / "reports" / "counterparty_register.json"

SCHEMA = "counterparty-register-report/1"
UNMEASURED = "UNMEASURED"
#: Input files larger than this are not parsed (memory bound).
MAX_INPUT_BYTES = 1_000_000
#: At most this many accounts are valued; the rest are listed as over budget.
MAX_ACCOUNTS = 50
#: At most this many payouts are scheduled per account (an uncapped count with a tiny cap).
MAX_SCHEDULE = 500
DEFAULT_TIME_BUDGET_S = 10.0
_ACCOUNT_SHAPED = re.compile(r"\d{4,12}")
#: Money-valued keys that do not end in `_usd` (the firms' public caps); never published.
MONEY_KEYS = frozenset({"per_payout_cap"})


def seed_money(obj: Any, at: str = "") -> list[str]:
    """Dotted paths of every non-null `*_usd` value in a register document. Any hit is a
    refusal: the tracked seed never carries an amount of money."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{at}.{k}" if at else str(k)
            if str(k).endswith("_usd") and v is not None:
                out.append(here)
            else:
                out += seed_money(v, here)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += seed_money(v, f"{at}[{i}]")
    return out


# ------------------------------------------------------------------------------- login scrub


def _fallback_is_login_key(key: str) -> bool:
    """Used only when `libs.ops.login_fence` is not on this tree; mirrors its key rule."""
    n = re.sub(r"[^a-z0-9]", "", str(key).lower())
    if not n or n.startswith(("requires", "require", "needs", "last", "failed", "allow", "auto",
                              "sso", "first", "prev", "next")):
        return False
    return n in {"account", "accountnumber", "accountno", "accountnum", "accountid",
                 "accountlogin", "login", "loginid", "loginno", "loginnumber"} or n.endswith(
        ("login", "loginid"))


try:  # the repo's fence, when this tree carries it
    from libs.ops.login_fence import is_login_key  # type: ignore[import-not-found]

    LOGIN_FENCE_SOURCE = "libs.ops.login_fence.is_login_key"
except ImportError:  # pragma: no cover - depends on the tree
    is_login_key = _fallback_is_login_key
    LOGIN_FENCE_SOURCE = "fallback (libs.ops.login_fence absent on this tree)"


def scrub(obj: Any) -> Any:
    """A copy with every login-shaped key dropped, at any depth."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not is_login_key(str(k))}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def safe_label(label: Any, i: int) -> str:
    s = str(label or "").strip()
    if not s or _ACCOUNT_SHAPED.fullmatch(s):
        return f"account_{i}"
    return s[:64]


# ----------------------------------------------------------------------------------- loading


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """(doc, None) or (None, reason)."""
    try:
        size = path.stat().st_size
    except OSError:
        return None, f"{path.name} absent"
    if size > MAX_INPUT_BYTES:
        return None, f"{path.name} is {size} bytes, over the {MAX_INPUT_BYTES} byte budget"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{path.name} unreadable: {type(exc).__name__}"
    if not isinstance(doc, dict):
        return None, f"{path.name} is not a JSON object"
    return doc, None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# -------------------------------------------------------------------------------------- math


def daily_hazard(p_annual: float) -> float:
    if not 0.0 <= p_annual < 1.0:
        raise ValueError("p_default must be in [0, 1)")
    return -math.log1p(-p_annual) / 365.0


def payout_schedule(profit: float, cap: float | None, remaining_count: int | None,
                    interval_days: float) -> list[tuple[float, float]]:
    """[(t_days, amount)] under the caps. Uncapped: one payout of everything at t = 0."""
    if profit <= 0:
        return []
    if cap is None:
        return [(0.0, profit)] if (remaining_count is None or remaining_count > 0) else []
    out: list[tuple[float, float]] = []
    left, k = profit, 0
    while left > 1e-9 and len(out) < MAX_SCHEDULE:
        if remaining_count is not None and k >= remaining_count:
            break
        x = min(left, cap)
        out.append((k * interval_days, x))
        left -= x
        k += 1
    return out


def haircut_value(schedule: list[tuple[float, float]], h: float) -> float:
    return sum(x * math.exp(-h * t) for t, x in schedule)


def delta_elogw(w0: float, profit: float, x0: float, q: float, gain: float) -> float:
    e_now = q * math.log(w0 + profit) + (1 - q) * math.log(w0 + x0)
    e_hold = q * math.log(w0 + profit + gain) + (1 - q) * math.log(w0)
    return e_now - e_hold


# ------------------------------------------------------------------------------------- rows


def _unmeasured(base: dict[str, Any], *reasons: str) -> dict[str, Any]:
    base.update({"status": UNMEASURED, "haircut_withdrawable_usd": UNMEASURED,
                 "delta_elogw_withdraw_now_vs_hold": UNMEASURED,
                 "reasons": [r for r in reasons if r]})
    return base


def value_account(i: int, acct: dict[str, Any], firms: dict[str, Any],
                  priors: dict[str, float], w0: float | None,
                  horizon_days: float) -> dict[str, Any]:
    firm_name = str(acct.get("firm") or "")
    row: dict[str, Any] = {"label": safe_label(acct.get("label"), i), "firm": firm_name}
    firm = firms.get(firm_name)
    if not isinstance(firm, dict):
        return _unmeasured(row, f"firm {firm_name!r} not in the register")
    p = priors.get(firm_name)
    if p is None:
        return _unmeasured(row, f"no p_default prior for {firm_name}")
    row["p_default_annual"] = p
    row["p_default_is_assumption"] = True
    payout = firm.get("payout") if isinstance(firm.get("payout"), dict) else {}
    cap = _num(payout.get("per_payout_cap"))
    max_n = payout.get("max_payouts_per_account")
    interval = _num(payout.get("payout_interval_days"))
    profit = _num(acct.get("withdrawable_usd"))
    reasons: list[str] = []
    if profit is None:
        reasons.append("withdrawable_usd not supplied")
    elif profit < 0:
        reasons.append("withdrawable_usd is negative")
    if interval is None or interval < 0:
        reasons.append("payout_interval_days missing for the firm")
    remaining: int | None = None
    if max_n is not None:
        taken = acct.get("payouts_taken")
        if not isinstance(max_n, int) or isinstance(max_n, bool):
            reasons.append("max_payouts_per_account is not an integer")
        elif not isinstance(taken, int) or isinstance(taken, bool) or taken < 0:
            reasons.append("payouts_taken unknown under a payout-count cap")
        else:
            remaining = max(0, max_n - taken)
    if reasons:
        return _unmeasured(row, *reasons)
    assert profit is not None and interval is not None
    h = daily_hazard(p)
    sched = payout_schedule(profit, cap, remaining, interval)
    nominal = sum(x for _, x in sched)
    row.update({
        "status": "MEASURED",
        "withdrawable_usd": round(profit, 2),
        "per_payout_cap_usd": cap,
        "payouts_remaining": remaining,
        "payout_interval_days": interval,
        "n_payouts_scheduled": len(sched),
        "schedule_truncated": len(sched) >= MAX_SCHEDULE,
        "nominal_withdrawable_usd": round(nominal, 2),
        "forfeit_beyond_caps_usd": round(profit - nominal, 2),
        "haircut_withdrawable_usd": round(haircut_value(sched, h), 2),
    })
    x0 = sched[0][1] if sched and sched[0][0] == 0.0 else 0.0
    row["withdraw_now_usd"] = round(x0, 2)
    row["spends_capped_slot"] = bool(remaining is not None and cap is not None and x0 < cap)
    gain = _num(acct.get("hold_gain_usd")) or 0.0
    row["hold_gain_usd"] = gain
    q = math.exp(-h * horizon_days)
    row["survival_to_horizon"] = round(q, 6)
    if w0 is None:
        row["delta_elogw_withdraw_now_vs_hold"] = UNMEASURED
        row["reasons"] = ["owner other_wealth_usd not supplied (must be > 0)"]
        return row
    d = delta_elogw(w0, profit, x0, q, gain)
    row["delta_elogw_withdraw_now_vs_hold"] = d
    row["log_growth_favours"] = "WITHDRAW_NOW" if d > 0 else ("HOLD" if d < 0 else "INDIFFERENT")
    return row


def build(register: dict[str, Any] | None, register_reason: str | None,
          accounts_doc: dict[str, Any] | None, *, horizon_days: float,
          p_override: dict[str, float], time_budget_s: float,
          now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "idea_row": 227,
        "report_only": True,
        "feeds_allocator": False,
        "login_fence": LOGIN_FENCE_SOURCE,
        "horizon_days": horizon_days,
        "budget": {"max_input_bytes": MAX_INPUT_BYTES, "max_accounts": MAX_ACCOUNTS,
                   "time_budget_s": time_budget_s, "exceeded": False},
    }
    if register is None:
        doc.update({"status": UNMEASURED, "reasons": [register_reason or "register absent"],
                    "accounts": []})
        return doc
    money = seed_money(register)
    if money:
        shown = ", ".join(money[:5]) + (f" (+{len(money) - 5} more)" if len(money) > 5 else "")
        doc.update({"status": UNMEASURED, "accounts": [],
                    "reasons": [f"refused: the tracked register carries money in {shown}; "
                                "every *_usd field in it must be null and owner money belongs "
                                "only in the gitignored operator file (--accounts, default "
                                "data/counterparty_accounts.local.json)"]})
        return doc
    firms = register.get("firms") if isinstance(register.get("firms"), dict) else {}
    prior_block = register.get("p_default_prior")
    prior_block = prior_block if isinstance(prior_block, dict) else {}
    priors: dict[str, float] = {}
    for k, v in (prior_block.get("values") or {}).items():
        f = _num(v)
        if f is not None and 0.0 <= f < 1.0:
            priors[str(k)] = f
    for k, v in p_override.items():
        priors[k] = v
    doc["p_default_prior"] = {"values": priors, "assumption": True,
                              "overridden": sorted(p_override),
                              "basis": prior_block.get("basis", UNMEASURED)}
    doc["firms"] = scrub(firms)
    source = accounts_doc if accounts_doc is not None else register
    owner = source.get("owner") if isinstance(source.get("owner"), dict) else {}
    w0 = _num(owner.get("other_wealth_usd"))
    if w0 is not None and w0 <= 0:
        w0 = None
    doc["owner_other_wealth_usd"] = w0 if w0 is not None else UNMEASURED
    accts = source.get("accounts") if isinstance(source.get("accounts"), list) else []
    rows: list[dict[str, Any]] = []
    for i, acct in enumerate(accts):
        if i >= MAX_ACCOUNTS or time.monotonic() - t0 > time_budget_s:
            doc["budget"]["exceeded"] = True
            rows.append({"label": f"account_{i}+", "status": UNMEASURED,
                         "haircut_withdrawable_usd": UNMEASURED,
                         "delta_elogw_withdraw_now_vs_hold": UNMEASURED,
                         "reasons": [f"{len(accts) - i} account(s) over the budget"]})
            break
        if not isinstance(acct, dict):
            rows.append({"label": f"account_{i}", "status": UNMEASURED,
                         "reasons": ["account entry is not an object"]})
            continue
        rows.append(value_account(i, scrub(acct), firms, priors, w0, horizon_days))
    doc["accounts"] = scrub(rows)
    measured = [r for r in rows if r.get("status") == "MEASURED"]
    doc["n_accounts"] = len(rows)
    doc["n_measured"] = len(measured)
    doc["status"] = ("MEASURED" if rows and len(measured) == len(rows)
                     else "PARTIAL" if measured else UNMEASURED)
    if not rows:
        doc["reasons"] = ["no accounts listed"]
    doc["total_haircut_withdrawable_usd"] = (
        round(sum(r["haircut_withdrawable_usd"] for r in measured), 2)
        if measured and len(measured) == len(rows) else UNMEASURED)
    doc["elapsed_s"] = round(time.monotonic() - t0, 4)
    return scrub(doc)


def _ratio(num: Any, den: Any) -> Any:
    n, d = _num(num), _num(den)
    if n is None or d is None or d <= 0:
        return UNMEASURED
    return round(n / d, 6)


def _money_free(obj: Any) -> Any:
    """Every `*_usd` value replaced by whether it was recorded: a published report names no
    amount of money, the firm's public caps included."""
    if isinstance(obj, dict):
        return {k: (("recorded" if v is not None else None)
                    if (str(k).endswith("_usd") or k in MONEY_KEYS)
                    and not isinstance(v, (dict, list)) else _money_free(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_money_free(v) for v in obj]
    return obj


def publishable(doc: dict[str, Any]) -> dict[str, Any]:
    """The report as it is WRITTEN: each account's money as fractions of its own withdrawable
    profit (the E[log W] delta is already a pure number), owner wealth as supplied or not, and no
    amount of money anywhere. `build` keeps the amounts for the in-process caller only."""
    out = dict(doc)
    rows = []
    for r in doc.get("accounts") or []:
        if not isinstance(r, dict):
            rows.append(r)
            continue
        row = dict(r)
        if row.get("status") == "MEASURED":
            p = row.get("withdrawable_usd")
            row.update({
                "basis": "fractions of this account's withdrawable profit",
                "nominal_frac": _ratio(row.get("nominal_withdrawable_usd"), p),
                "forfeit_beyond_caps_frac": _ratio(row.get("forfeit_beyond_caps_usd"), p),
                "haircut_frac": _ratio(row.get("haircut_withdrawable_usd"), p),
                "withdraw_now_frac": _ratio(row.get("withdraw_now_usd"), p),
                "per_payout_cap_frac": (_ratio(row.get("per_payout_cap_usd"), p)
                                        if row.get("per_payout_cap_usd") is not None
                                        else "uncapped"),
                "hold_gain_frac": _ratio(row.get("hold_gain_usd"), p),
            })
        rows.append({k: v for k, v in row.items() if not str(k).endswith("_usd")})
    out["accounts"] = rows
    w0 = doc.get("owner_other_wealth_usd")
    out.pop("owner_other_wealth_usd", None)
    out["owner_other_wealth"] = UNMEASURED if w0 in (None, UNMEASURED) else "supplied"
    total = doc.get("total_haircut_withdrawable_usd")
    out.pop("total_haircut_withdrawable_usd", None)
    measured = [r for r in doc.get("accounts") or []
                if isinstance(r, dict) and r.get("status") == "MEASURED"]
    out["total_haircut_frac_of_withdrawable"] = (
        _ratio(total, sum(float(r["withdrawable_usd"]) for r in measured))
        if total != UNMEASURED and measured else UNMEASURED)
    out["money"] = "no amount of money is published; every figure is a ratio"
    return _money_free(out)


def _parse_override(items: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for it in items:
        name, _, val = it.partition("=")
        f = _num(val)
        if not name.strip() or f is None or not 0.0 <= f < 1.0:
            raise SystemExit(f"--p-default wants FIRM=P with P in [0, 1): {it!r}")
        out[name.strip()] = f
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--register", type=Path, default=REGISTER)
    ap.add_argument("--accounts", type=Path, default=None,
                    help="operator JSON with `owner` and `accounts` (labels only, no logins); "
                    "default: data/counterparty_accounts.local.json when it exists (gitignored)")
    ap.add_argument("--horizon-days", type=float, default=30.0)
    ap.add_argument("--p-default", action="append", default=[], metavar="FIRM=P")
    ap.add_argument("--time-budget-s", type=float, default=DEFAULT_TIME_BUDGET_S)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.horizon_days <= 0:
        raise SystemExit("--horizon-days must be > 0")
    register, reason = load_json(a.register)
    accounts_doc = None
    accounts = a.accounts
    if accounts is None and ACCOUNTS_LOCAL.is_file():
        accounts = ACCOUNTS_LOCAL
    if accounts is not None:
        accounts_doc, acc_reason = load_json(accounts)
        if accounts_doc is None:
            register, reason = None, f"--accounts: {acc_reason}"
    doc = build(register, reason, accounts_doc, horizon_days=a.horizon_days,
                p_override=_parse_override(a.p_default), time_budget_s=a.time_budget_s)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(publishable(doc), indent=1, default=str), encoding="utf-8")
    tmp.replace(a.out)
    print(f"counterparty_register: {doc['status']} "
          f"({doc.get('n_measured', 0)}/{doc.get('n_accounts', 0)} accounts)")
    return 0

