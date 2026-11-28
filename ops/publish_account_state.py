"""Publish the live account to `desks/mt5/data/account_state.json`, on a clock.

WHY THIS EXISTS. `build_zentech_state` reads the account two ways: `_mt5_snapshot()` straight
from the terminal, and `desks/mt5/data/account_state.json` as the fallback. On 2026-09-11 the
dashboard published

    account: {'venue': 'UNMEASURED', 'currency': 'UNMEASURED',
              'balance': None, 'equity': None}

on a box whose terminal was connected and answering -- `_mt5_snapshot()` returns the right
numbers when called by hand (equity 607.81 EUR, today_pnl -144.70), but the builder runs on a
schedule alongside the gateway, which holds its own terminal connection every minute, and a
snapshot that loses that race falls through to the file. The file is then consulted and

    NOTHING IN THIS REPOSITORY WRITES IT.

Every reference to account_state.json is a reader or a path list -- `release_identity`'s state
prefixes, `libs.ops.release`, the dashboard builder, a test. The fallback for the desk's most
-read number was a path nobody produced, so the panel read UNMEASURED whenever the live read
missed. That is III.16 exactly: a consumer wired to a producer that does not exist.

WHY A SEPARATE ORGAN AND NOT A LINE IN THE GATEWAY. The gateway is the money path; every edit
there costs a re-seal and a restart of the thing that trades. This needs none of that -- it
reads and writes one small artifact, holds no order authority, and a failed pass leaves the
previous file in place with its own timestamp so staleness stays visible rather than being
papered over with a stale number presented as current.

    python ops/publish_account_state.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desks" / "mt5" / "data" / "account_state.json"
#: The open book, per position. UNTRACKED (.gitignore): the repository is public, and tickets,
#: sizes and stops are the live account's own. It stays on the box for restore and reconcile.
POSITIONS_REL = "desks/mt5/data/account_positions.json"
POSITIONS = ROOT / POSITIONS_REL
#: The one line that names the desk's execution terminal (mt5desk/config.py TERMINAL_FILE;
#: broker_switch writes it). Read here directly so this organ imports nothing from the gateway.
TERMINAL_FILE = ROOT / "desks" / "mt5" / "data" / "terminal_path.txt"
#: The live account is Fusion. Any other server on the attached terminal (FTMO, E8, a demo) is
#: the WRONG account, and its balance must never be published as this desk's.
EXPECTED_SERVER_PREFIX = "FusionMarkets-"
PAGE_MARKER = "ACCOUNT STATE REFUSED:"
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
sys.path.insert(0, str(ROOT))
from research.mt5_session import attach_or_initialize  # noqa: E402


def _position(p: object) -> dict[str, object]:
    """One open position as the ledger row; a field the terminal did not supply reads None."""
    def f(name: str) -> float | None:
        v = getattr(p, name, None)
        return round(float(v), 5) if v is not None else None
    opened = getattr(p, "time", None)
    kind = getattr(p, "type", None)
    return {"ticket": getattr(p, "ticket", None), "symbol": getattr(p, "symbol", None),
            "side": None if kind is None else ("buy" if int(kind) == 0 else "sell"),
            "volume": f("volume"), "price_open": f("price_open"),
            "sl": f("sl") or None, "tp": f("tp") or None,
            "swap": f("swap"), "profit": f("profit"), "magic": getattr(p, "magic", None),
            "opened_at": (datetime.fromtimestamp(int(opened), tz=UTC).isoformat()
                          if opened else None)}


def _terminal_path() -> str | None:
    """The configured terminal64.exe, or None when the file is missing or empty."""
    try:
        p = TERMINAL_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return p or None


def _same_terminal(configured: str, attached_dir: str | None) -> bool:
    """`terminal_info().path` is the terminal's DIRECTORY; the file names its executable."""
    if not attached_dir:
        return False
    def norm(x: str) -> str:
        return x.replace("/", "\\").rstrip("\\").lower()
    conf = norm(configured)
    if conf.endswith("\\terminal64.exe"):
        conf = conf[: -len("\\terminal64.exe")]
    return conf == norm(attached_dir)


def _refuse(reason: str) -> int:
    """FAIL CLOSED: leave the previous file in place and page the principal.

    2026-11-11 (Desk health AS1). `attach_or_initialize` is called with no path and attaches to
    whatever terminal the bridge already sees. The box runs TWO logged-in terminals in session 2,
    Fusion and FTMO. If restart order ever made FTMO the bridge's default, this organ would publish
    FTMO's ~$99.7k as the desk's balance -- the sizing input -- with nothing in the record noticing.
    A stale file with its own timestamp is visible; a wrong account presented as current is not.
    """
    msg = f"{PAGE_MARKER} {reason}; previous account_state.json left in place"
    print(msg)
    try:
        from libs.ops.principal_page import page
        page(msg, marker=PAGE_MARKER, path=ROOT / "data" / "PRINCIPAL_ACTION.md")
    except Exception as exc:  # the page is best-effort; the refusal itself never depends on it
        print(f"page failed: {type(exc).__name__}: {exc}")
    return 1


def main() -> int:
    try:
        import MetaTrader5 as mt5
    except Exception as exc:  # the research box has no terminal; absence is not an error
        print(f"MetaTrader5 unavailable: {type(exc).__name__}: {exc}")
        return 0

    terminal = _terminal_path()
    if not attach_or_initialize(mt5, path=terminal, timeout=15000):
        # LEAVE THE OLD FILE ALONE. Writing a null-filled record here would turn "I could not
        # reach the terminal this minute" into a published verdict that the account is empty --
        # the same confusion the dashboard already shipped once.
        print(f"terminal unreachable: {mt5.last_error()}; previous file left in place")
        return 1

    info = mt5.account_info()
    if info is None:
        print("account_info() returned None; previous file left in place")
        return 1
    server = str(getattr(info, "server", "") or "")
    if not server.startswith(EXPECTED_SERVER_PREFIX):
        return _refuse(f"attached terminal is on server {server or '(none)'!r}, "
                       f"not {EXPECTED_SERVER_PREFIX}*")
    if terminal is not None:
        tinfo = mt5.terminal_info()
        attached = str(getattr(tinfo, "path", "") or "") if tinfo is not None else ""
        if not _same_terminal(terminal, attached):
            return _refuse(f"attached terminal {attached or '(unknown)'!r} is not "
                           f"terminal_path.txt's {terminal!r}")

    now = datetime.now(UTC)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(day0, now)
    positions = mt5.positions_get()
    if deals is None or positions is None:
        print("broker history or positions unavailable; previous file left in place")
        return 1
    closed = 0.0
    for d in deals:
        closed += float(getattr(d, "profit", 0.0) or 0.0)
        closed += float(getattr(d, "commission", 0.0) or 0.0)
        closed += float(getattr(d, "swap", 0.0) or 0.0)
    floating = sum(float(getattr(p, "profit", 0.0) or 0.0) for p in positions)

    rec = {
        "updated_at": now.isoformat(timespec="seconds"),
        "source": "ops/publish_account_state.py",
        "venue": str(getattr(info, "company", "") or "") or None,
        "server": str(getattr(info, "server", "") or "") or None,
        # The login is WITHHELD: this file is committed by the box, and a tracked file must never
        # name the live account (tests/ops/test_live_infrastructure_is_not_published.py). No
        # reader takes it from here; provenance reads mt5.account_info().login from the terminal.
        "login_withheld": info.login is not None,
        "currency": str(info.currency),
        "balance": round(float(info.balance), 2),
        "equity": round(float(info.equity), 2),
        "margin_free": round(float(info.margin_free), 2),
        "today_pnl": round(closed + floating, 2),
        "today_closed_pnl": round(closed, 2),
        "today_floating_pnl": round(floating, 2),
        "open_positions": len(positions),
        # ONE AUTHORITATIVE LEDGER (recovery drills, account_ledger row, 2026-10-07): used margin
        # and the financing carried, as AGGREGATES. The positions themselves (tickets, sizes,
        # stops) go to POSITIONS, which is gitignored: this file is committed by the box and the
        # repository is public, so nothing that identifies a live position may land here.
        "margin": round(float(getattr(info, "margin", 0.0) or 0.0), 2),
        "margin_level": (round(float(info.margin_level), 2)
                         if getattr(info, "margin_level", None) else None),
        "swap": round(sum(float(getattr(p, "swap", 0.0) or 0.0) for p in positions), 2),
        "today_swap": round(sum(float(getattr(d, "swap", 0.0) or 0.0) for d in deals), 2),
        "positions_file": POSITIONS_REL,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    tmp.replace(OUT)          # atomic, so a reader never sees a half-written record
    book = {"updated_at": rec["updated_at"], "open_positions": len(positions),
            "positions": [_position(p) for p in positions]}
    ptmp = POSITIONS.with_suffix(".json.tmp")
    ptmp.write_text(json.dumps(book, indent=1), encoding="utf-8")
    ptmp.replace(POSITIONS)
    print(f"wrote {OUT.name}: equity {rec['equity']} {rec['currency']} "
          f"today_pnl {rec['today_pnl']} positions {rec['open_positions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
