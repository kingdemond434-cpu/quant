"""BOOT r24, PHASE A: can a NON-ADMIN account drive an MT5 terminal? Measured, never assumed.

WHY. r23's guard is independent only once the live tree stops running as Administrator/SYSTEM
(Audit D1, measured 2026-11-27 13:20Z). Moving the gateway to `quantrun` is safe only if MT5's
python API works from that account, and the desk has evidence it may not: on 2026-10-02 a
windowless Session-0 Fusion terminal timed out every API call (ops/ensure_terminal.ps1).

WHAT IT DOES, run by the pinned migrator as a one-shot task under `quantrun`:
    python -I runas_probe.py --exe <terminal64.exe> --expect <login last 2 digits> --out <json>
  * initialize(path=exe, timeout) -- the ONLY MT5 call besides account_info, terminal_info and
    shutdown. No symbol, no order, no history: read-only on the account.
  * records connected, trade_allowed, the login's LAST TWO DIGITS (never the login), the session
    and the elapsed time; a pass needs connected and the expected suffix.
  * kills every terminal64 this account started during the probe (an attach that fails makes
    initialize autostart one), and only those: its own processes, never another account's.
The answer goes to --out (the migrator writes it into guard\\RUN_AS_PROBE.json); the probe never
writes anywhere else and prints nothing secret.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterable
from typing import Any


def _own_terminals(procs: Iterable[Any], me: str) -> set[int]:
    out = set()
    for p in procs:
        try:
            if p.name().lower() == "terminal64.exe" and p.username().split("\\")[-1].lower() == me:
                out.add(int(p.pid))
        except Exception:  # another account's process: not ours, never touched
            continue
    return out


def probe(mt5: Any, exe: str, expect: str, *, timeout_ms: int = 15000,
          clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    t0 = clock()
    row: dict[str, Any] = {"exe": exe, "expect_suffix": expect, "ok": False}
    try:
        if not mt5.initialize(path=exe, timeout=timeout_ms):
            row["why"] = f"initialize failed: {mt5.last_error()}"
            return row
        acc, term = mt5.account_info(), mt5.terminal_info()
        suffix = str(getattr(acc, "login", "") or "")[-2:]
        row.update({"connected": bool(getattr(term, "connected", False)),
                    "trade_allowed": bool(getattr(term, "trade_allowed", False)),
                    "login_suffix": suffix})
        row["ok"] = row["connected"] and bool(expect) and suffix == expect
        if not row["ok"]:
            row["why"] = "not connected" if not row["connected"] else "login suffix differs"
        return row
    except Exception as exc:
        row["why"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return row
    finally:
        with contextlib.suppress(Exception):
            mt5.shutdown()
        row["elapsed_s"] = round(clock() - t0, 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--expect", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    import psutil
    me = os.environ.get("USERNAME", "").lower()
    before = _own_terminals(psutil.process_iter(), me)
    try:
        import MetaTrader5 as mt5
        row = probe(mt5, a.exe, a.expect)
    except ImportError as exc:
        row = {"exe": a.exe, "ok": False, "why": f"MetaTrader5 not importable: {exc}"}
    spawned = _own_terminals(psutil.process_iter(), me) - before
    for pid in spawned:
        with contextlib.suppress(Exception):
            psutil.Process(pid).kill()
    row.update({"account": me, "session": _session(), "killed_spawned": sorted(spawned),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    tmp = a.out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(row, fh, sort_keys=True)
    os.replace(tmp, a.out)
    return 0 if row["ok"] else 1


def _session() -> int | None:
    try:
        import psutil
        return int(getattr(psutil.Process(), "session_id", lambda: None)() or 0)
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
