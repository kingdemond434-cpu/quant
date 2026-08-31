"""SUB-ACCOUNTS -- automated when the venue permits it, honest about when it does not.

PRINCIPAL ORDER (2026-07-30): *"allow our system to create automated subaccounts when needed."*

WHY THE DESK WANTS THEM AT ALL: isolation. A sub-account per sleeve gives per-strategy margin
isolation (one sleeve's liquidation cannot cascade into another's collateral), clean per-edge
capacity accounting (the OUTGROWN lifecycle reads real per-sleeve equity instead of an
attribution), and a blast-radius boundary for a misbehaving executor. Those are the same
properties the desk currently approximates in software; sub-accounts make the venue enforce them.

=================================================================================================
THE CONSTRAINT THAT SHAPES EVERYTHING HERE, stated before any code pretends otherwise
=================================================================================================
Binance exposes sub-account creation (`POST /sapi/v1/sub-account/virtualSubAccount`) ONLY to
corporate/entity accounts (and broker-programme members). A personal account gets an error, full
stop -- no code changes that. So this module is built in the only honest shape available:

  PROBE     ask the venue what THIS account may do, and persist the answer where the boards read
            it (`data/subaccounts.json`). Capability is measured, never assumed -- the same rule
            as everything else on this desk (L2.4: artifact over claim).
  USE       where the probe says yes: create_virtual() under a bounded policy (name prefix,
            hard cap on count) with an append-only ledger row per creation.
  BLOCKED   where it says no: record the exact blocker and the upgrade path (corporate
            verification), so the max-push queue carries a real item instead of a wish.

CREATION is automated once permitted -- it moves no money and is the cheap, reversible act.
TRANSFERS between accounts are the money path, and they follow the house rule for money-path
acts: signed (`authorised_by`), reasoned, capped per-transfer, append-only ledgered
(`data/subaccount_ledger.jsonl`). The desk may open drawers on its own; moving cash between
drawers carries a name, every time. Same design as libs/risk/capital_events.py, and for the same
reason: an unattributed money movement is how a rail gets defeated by nobody in particular.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
STATE = _ROOT / "data/subaccounts.json"
LEDGER = _ROOT / "data/subaccount_ledger.jsonl"

#: Policy: every desk-created sub-account is recognisable, and there is a hard cap. The cap is a
#: runaway-loop backstop, not a plan -- one sleeve per live strategy family is the design point.
NAME_PREFIX = "qdesk"
MAX_SUBACCOUNTS = 12
#: Per-transfer ceiling. Deliberately equity-relative not absolute (the $100k-floor lesson):
#: a desk-initiated inter-account move may never exceed this fraction of the book in one call.
MAX_TRANSFER_FRACTION = 0.25


class SubAccountsUnavailable(RuntimeError):
    """This account tier cannot use the sub-account API. Carries the venue's own words."""


@dataclass(frozen=True)
class Capability:
    available: bool
    detail: str
    n_existing: int = 0
    checked: str = ""


def _signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    """Reuse the live connector's keyfile + signer -- one credential path, no second copy."""
    import libs.execution.binance_live as binance_live
    return binance_live._signed(path, params, method=method)


def probe(*, write_state: bool = True) -> Capability:
    """Measure what this account may do. Never raises on 'not permitted' -- that is a RESULT.

    The distinction it must not blur: NO-KEYS (cannot ask), BLOCKED-TIER (asked, venue said
    personal accounts may not), and AVAILABLE (asked, got a list). Collapsing the first two into
    one 'unavailable' would hide the difference between a launch-day gap and a Binance
    verification task -- different owners, different fixes.
    """
    import libs.execution.binance_live as binance_live
    now = datetime.now(tz=UTC).isoformat()
    if not binance_live.has_keys():
        cap = Capability(False, "NO-KEYS: no live credential on this box -- probe cannot run",
                         checked=now)
    else:
        try:
            resp = _signed("/sapi/v1/sub-account/list", {"limit": 200})
            subs = resp.get("subAccounts", []) if isinstance(resp, dict) else []
            cap = Capability(True, f"AVAILABLE: corporate-tier API confirmed, "
                                   f"{len(subs)} sub-account(s) exist", len(subs), now)
        except Exception as exc:
            cap = Capability(False, f"BLOCKED-TIER: venue refused the sub-account API "
                                    f"({str(exc)[:160]}). Upgrade path: Binance corporate/entity "
                                    "verification, or the broker programme. Until then this "
                                    "capability is externally gated, not missing.", checked=now)
    if write_state:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({
            "checked": cap.checked, "available": cap.available, "detail": cap.detail,
            "n_existing": cap.n_existing,
            "policy": {"name_prefix": NAME_PREFIX, "max_subaccounts": MAX_SUBACCOUNTS,
                       "max_transfer_fraction": MAX_TRANSFER_FRACTION},
        }, indent=2), "utf-8")
    return cap


def _ledger_append(row: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def create_virtual(purpose: str) -> dict[str, Any]:
    """Create one virtual sub-account for a named purpose. Automated by design -- creation moves
    no money -- but bounded: recognisable name, hard count cap, ledger row per creation."""
    cap = probe()
    if not cap.available:
        raise SubAccountsUnavailable(cap.detail)
    if cap.n_existing >= MAX_SUBACCOUNTS:
        raise SubAccountsUnavailable(
            f"policy cap reached ({cap.n_existing}/{MAX_SUBACCOUNTS}) -- a runaway creation loop "
            "is indistinguishable from intent at the venue's end, so the cap is hard")
    if not purpose.strip() or len(purpose.strip()) < 8:
        raise SubAccountsUnavailable("a sub-account without a stated purpose is a drawer nobody "
                                     "can audit -- name what it isolates")
    tag = f"{NAME_PREFIX}{datetime.now(tz=UTC).strftime('%m%d%H%M')}"
    resp = _signed("/sapi/v1/sub-account/virtualSubAccount",
                   {"subAccountString": tag}, method="POST")
    row = {"at": datetime.now(tz=UTC).isoformat(), "action": "CREATE",
           "email": (resp or {}).get("email", tag), "purpose": purpose.strip()}
    _ledger_append(row)
    probe()                                             # refresh the persisted count
    return row


def transfer(*, to_email: str, asset: str, amount: float,
             authorised_by: str, reason: str) -> dict[str, Any]:
    """Move funds master->sub. MONEY PATH: signed, reasoned, capped, ledgered -- every time.

    The cap is equity-relative (MAX_TRANSFER_FRACTION of the live book per call). An absolute
    dollar cap would rot exactly the way the $100k capacity floor did -- correct at one book size,
    wrong at every other.
    """
    if not authorised_by.strip():
        raise SubAccountsUnavailable("unsigned transfer refused -- money moving between drawers "
                                     "carries a name, every time (same rule as capital_events)")
    if len(reason.strip()) < 12:
        raise SubAccountsUnavailable("a transfer reason is the record; state what it funds")
    try:
        from libs.autodiscovery.validation import _desk_equity_usd
        book = float(_desk_equity_usd())
    except Exception:
        book = 0.0
    if book <= 0:
        raise SubAccountsUnavailable("live book unreadable -- an uncapped transfer is refused, "
                                     "never waved through (fail-closed)")
    if amount > book * MAX_TRANSFER_FRACTION:
        raise SubAccountsUnavailable(
            f"transfer ${amount:,.2f} exceeds {MAX_TRANSFER_FRACTION:.0%} of the "
            f"${book:,.2f} book -- split it, or the principal moves it at the venue")
    cap = probe(write_state=False)
    if not cap.available:
        raise SubAccountsUnavailable(cap.detail)
    resp = _signed("/sapi/v1/sub-account/universalTransfer",
                   {"toEmail": to_email, "fromAccountType": "SPOT", "toAccountType": "SPOT",
                    "asset": asset, "amount": amount}, method="POST")
    row = {"at": datetime.now(tz=UTC).isoformat(), "action": "TRANSFER", "to": to_email,
           "asset": asset, "amount": amount, "authorised_by": authorised_by.strip(),
           "reason": reason.strip(), "venue_response": str(resp)[:120]}
    _ledger_append(row)
    return row
