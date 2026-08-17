"""Move the desk between brokers with one command, safely, or refuse.

WHY THIS EXISTS

Switching the execution surface was six manual steps in a fixed order: pause the gateway, find
the terminal64.exe, write terminal_path.txt, verify the account, unpause, restart the loop. Every
one of them is easy, and getting them out of order is how a desk fires an order into the wrong
account. The dangerous ordering is not exotic -- writing the path before pausing leaves a window
where the gateway reads a new terminal with the old state.

So the order is encoded here rather than remembered, and the risky combinations are refused.

WHAT IT REFUSES TO DO

Switch to an account it cannot identify. `mt5.initialize(path=...)` is attempted against the
candidate terminal BEFORE the path is committed, and if the login, server and trade mode cannot
all be read the switch is abandoned with the old path intact. A desk pointed at an unverifiable
terminal is worse than a desk that did not switch: the second is visible, the first trades.

Switch to a LIVE account without --i-know-its-live. Demo and live differ by one line in a text
file, and that asymmetry deserves friction. Nothing here can be undone by the market.

    python -m mt5desk.broker_switch --list
    python -m mt5desk.broker_switch --to "C:\\...\\terminal64.exe"
    python -m mt5desk.broker_switch --to "C:\\...\\terminal64.exe" --i-know-its-live
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from mt5desk.config import DATA, desk_root
from mt5desk.provenance import DEMO, LIVE, UNKNOWN, current_account

PAUSE = DATA / "GATEWAY_PAUSED"
TERMINAL_FILE = DATA / "terminal_path.txt"

#: Where MT5 installs live on Windows. Searched in order; the first hit for a broker wins.
_ROOTS = (r"C:\Program Files", r"C:\Program Files (x86)",
          os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal"),
          os.path.expandvars(r"%LOCALAPPDATA%\Programs"))


def find_terminals(max_depth: int = 4) -> list[Path]:
    """Every terminal64.exe on this box. Cheap enough to run every time."""
    out: list[Path] = []
    for root in _ROOTS:
        p = Path(root)
        if not p.exists():
            continue
        for depth in range(1, max_depth + 1):
            out.extend(p.glob("/".join(["*"] * depth) + "/terminal64.exe"))
    return sorted({q.resolve() for q in out})


def identify(terminal: Path, timeout_s: int = 30) -> dict:
    """Log in to `terminal` in a SEPARATE process and report what account it holds.

    Separate process deliberately: MetaTrader5 keeps one global connection per process, so probing
    a candidate in-process would tear down the connection the caller may still be using. A crashed
    or hanging probe also cannot take the switch with it.
    """
    code = (
        "import json,sys\n"
        "import MetaTrader5 as mt5\n"
        f"ok = mt5.initialize(path=r'{terminal}')\n"
        "a = mt5.account_info() if ok else None\n"
        "print(json.dumps({'ok': bool(ok), 'login': getattr(a,'login',None),"
        " 'server': getattr(a,'server',None), 'mode': getattr(a,'trade_mode',None),"
        " 'company': getattr(a,'company',None), 'equity': getattr(a,'equity',None),"
        " 'currency': getattr(a,'currency',None)}))\n"
    )
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           timeout=timeout_s)
        import json
        return json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception as exc:                                        # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _kind(info: dict) -> str:
    from mt5desk.provenance import account_kind
    return account_kind(info.get("mode"))


def cmd_list() -> int:
    terms = find_terminals()
    if not terms:
        print("no terminal64.exe found under the usual install roots.")
        print("pass the full path directly: --to \"C:\\...\\terminal64.exe\"")
        return 1
    print(f"{len(terms)} terminal(s):\n")
    for t in terms:
        info = identify(t)
        if not info.get("ok"):
            print(f"  {t}\n      unreachable: {info.get('error', 'no account_info')}\n")
            continue
        kind = _kind(info)
        mark = "  <-- CURRENT" if _current() == str(t) else ""
        print(f"  {t}{mark}")
        print(f"      {info.get('company')} | {info.get('server')} | account "
              f"{info.get('login')} | {kind.upper()} | "
              f"{info.get('equity')} {info.get('currency')}\n")
    return 0


def _current() -> str | None:
    if TERMINAL_FILE.exists():
        return TERMINAL_FILE.read_text(encoding="utf-8").strip()
    return None


def switch(target: str, allow_live: bool = False) -> int:
    """Pause -> identify -> commit -> unpause. Aborts before committing on any doubt."""
    t = Path(target)
    if not t.exists():
        print(f"REFUSED: {t} does not exist.")
        return 2

    # PAUSE FIRST, ALWAYS. Writing the path before pausing leaves a window where the gateway
    # reads the new terminal against the old state -- brackets computed for one account placed
    # into another. The file is created before anything else is touched and removed only at the
    # end, so an abort anywhere in between leaves the desk SAFE rather than half-switched.
    was_paused = PAUSE.exists()
    PAUSE.parent.mkdir(parents=True, exist_ok=True)
    PAUSE.write_text(f"broker_switch: verifying {t}", encoding="utf-8")
    print("gateway paused for the switch")

    info = identify(t)
    if not info.get("ok") or info.get("login") is None:
        print(f"REFUSED: could not read an account from {t}")
        print(f"         {info.get('error', 'terminal did not return account_info')}")
        print("         Is the terminal installed and logged in? The old path is untouched.")
        if not was_paused:
            PAUSE.unlink(missing_ok=True)
            print("gateway unpaused (nothing changed)")
        return 3

    kind = _kind(info)
    print(f"identified: {info.get('company')} | {info.get('server')} | "
          f"account {info.get('login')} | {kind.upper()} | "
          f"{info.get('equity')} {info.get('currency')}")

    if kind == UNKNOWN:
        print("REFUSED: account trade mode is unrecognised, so this could be a live account.")
        print("         Absence of a classification is not permission. Old path untouched.")
        if not was_paused:
            PAUSE.unlink(missing_ok=True)
        return 4

    if kind == LIVE and not allow_live:
        print("REFUSED: that is a LIVE account and --i-know-its-live was not passed.")
        print("         Demo and live differ by one line in a text file; the friction is the point.")
        print(f"         Re-run: python -m mt5desk.broker_switch --to \"{t}\" --i-know-its-live")
        if not was_paused:
            PAUSE.unlink(missing_ok=True)
        return 5

    TERMINAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    TERMINAL_FILE.write_text(str(t), encoding="utf-8")
    print(f"terminal_path.txt -> {t}")

    PAUSE.unlink(missing_ok=True)
    print("gateway unpaused")
    print()
    print(f"NOW TRADING: {kind.upper()} account {info.get('login')} ({info.get('server')})")
    if kind == DEMO:
        print("Demo fills do not slip. markout will look clean and that means nothing --")
        print("what demo proves is contract sizes, stop/freeze levels, symbol suffixes,")
        print("session hours, and whether orders are accepted at all.")
    else:
        print("Forward evidence starts from ZERO on this account by design: the promoter counts")
        print("only trades from the account in hand, so nothing from demo can retire a live")
        print("sleeve or flatter one. See mt5desk.provenance.")
    print()
    print("Restart the gateway loop so it re-reads the path:")
    print("  Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | "
          "Where-Object { $_.CommandLine -like '*MT5Gateway*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    print(r"  Start-Process \"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\MT5Gateway.cmd\"")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    print(f"desk: {desk_root()}")
    print(f"current terminal: {_current() or '(unset)'}\n")
    if "--list" in argv or not argv:
        return cmd_list()
    if "--to" in argv:
        i = argv.index("--to")
        if i + 1 >= len(argv):
            print("--to needs a path")
            return 2
        return switch(argv[i + 1], allow_live="--i-know-its-live" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
