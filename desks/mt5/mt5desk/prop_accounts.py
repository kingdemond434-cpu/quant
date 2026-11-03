"""PROP ACCOUNTS: every prop-firm challenge account this box runs, and where each one's files live.

The principal, 2026-11-03: run the same strategies on several challenge accounts at once, across
two to four prop firms, each sized for its own firm's rules and its own phase, so every one of
them is funded as fast as it safely can be. One FTMO account existed before this module and keeps
every path it had (`LEGACY`, the implicit first row); every other account is a row of
`data/prop_accounts.json`, written on the box (the principal adds accounts; nothing here opens
one):

    {"accounts": [
      {"id": "ftmo2", "firm": "ftmo", "program": "ftmo_2step",
       "terminal_path": "C:\\\\MT5\\\\ftmo2\\\\terminal64.exe"},
      {"id": "fn1", "firm": "fundednext", "program": "fundednext_stellar_2step",
       "terminal_path": "C:\\\\MT5\\\\fn1\\\\terminal64.exe", "enabled": true}
    ]}

ONE ACCOUNT, ONE TERMINAL, ONE FOLDER. MetaTrader attaches one login per terminal process, so a row
names its own terminal; two rows on one terminal are refused (the second would trade the first's
account). Each non-legacy account's files live under data/prop/<id>/ and reports/prop/<id>/:
the declaration (`ACCOUNT.json`: login, server, initial_balance, daily_loss_frac -- gitignored,
the principal's, exactly as data/FTMO_LIVE_ACCOUNT.json), the venue reader's state, the
allocator's report and arm file, and the executor's state, report, intents and arm file. Its book
is the `prop_<id>` block of CERT_BOOK_LIVE.json and its cross-account book is
data/xacct/prop_<id>_book.json.

A firm's venue files (its symbol list, its cost surface, its bars) are shared by its accounts:
FTMO's are the files the FTMO reader always wrote; any other firm's live under
data/prop/firm_<firm>/.

FAIL CLOSED. An unreadable registry runs the legacy account alone and says why; a malformed row is
skipped and named. A disabled row stays REGISTERED: its last published book still fences the other
accounts (an account that stops trading may still hold positions).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
DATA = _DESK / "data"
REPORTS = _DESK / "reports"
LOGS = _DESK / "logs"
REGISTRY_NAME = "prop_accounts.json"
#: The FTMO account that existed before the registry: its id, files and book key never change.
LEGACY = "ftmo"
LEGACY_FIRM = "ftmo"
LEGACY_PROGRAM = "ftmo_2step"
#: prop/ftmo_follower.TERMINAL_PATH, the legacy account's terminal (restated: this module must not
#: import the follower; a test pins the two equal).
LEGACY_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,23}$")
FIRM_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,31}$")


#: A firm's challenge program: its rule text as fractions of the initial balance, its trading
#: day's time zone, and where the text was read. FTMO 2-Step is the one this desk has read; any
#: other program is a row of data/prop_programs.json carrying the same fields AND a `source`
#: (where its rule text was read) -- an unsourced program is refused, never guessed.
PROGRAMS_NAME = "prop_programs.json"
PROGRAM_FIELDS = ("daily_loss", "max_loss", "min_days", "targets", "next_phase", "day_tz",
                  "source", "max_loss_basis", "daily_loss_basis")
#: THE ONLY RULE SHAPES THE SOLVE AND THE EXECUTOR'S LOSS GUARD MODEL (audit of 580b6f99): a
#: maximum loss STATIC off the initial balance, and a daily loss measured from the day's starting
#: BALANCE. A firm whose rule is a trailing drawdown, or a day start taken from equity, or a
#: profit cap the executor would have to enforce, is REFUSED until that shape is modelled --
#: sizing it as if it were FTMO's would under-state the barrier. Each row must declare both
#: bases explicitly, so a trailing-drawdown firm can never enter by omission.
MODELLED_MAX_LOSS_BASIS = ("static_initial",)
MODELLED_DAILY_LOSS_BASIS = ("day_start_balance",)
BUILTIN_PROGRAMS: dict[str, dict[str, Any]] = {
    "ftmo_2step": {
        "daily_loss": 0.05, "max_loss": 0.10, "min_days": 4,
        "targets": {"phase1": 0.10, "phase2": 0.05},
        "next_phase": {"phase1": "phase2", "phase2": "funded"},
        "day_tz": "Europe/Prague", "profit_cap": None,
        "max_loss_basis": "static_initial", "daily_loss_basis": "day_start_balance",
        "source": "ftmo.com/en/trading-objectives + /en/2-step-challenge, read 2026-10-28"},
}


def programs(data: Path | None = None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """({program id: rule row}, [why each refused row was refused]). Built-ins first; a file row
    never overrides a built-in."""
    data = data or DATA
    out = {k: dict(v) for k, v in BUILTIN_PROGRAMS.items()}
    errors: list[str] = []
    try:
        doc = json.loads((data / PROGRAMS_NAME).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return out, errors
    except (OSError, ValueError) as exc:
        return out, [f"{PROGRAMS_NAME} unreadable ({type(exc).__name__})"]
    rows = doc.get("programs") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return out, [f"{PROGRAMS_NAME} has no 'programs' object"]
    for pid, row in rows.items():
        why = program_error(pid, row)
        if pid in out:
            why = why or "a built-in program is not overridden from a file"
        if why:
            errors.append(f"program {pid!r}: {why}")
            continue
        out[pid] = dict(row)
    return out, errors


def program_error(pid: object, row: object) -> str | None:
    """Why `row` is not a usable rule set, or None."""
    if not isinstance(pid, str) or not FIRM_RE.match(pid):
        return "id is not [a-z0-9_]"
    if not isinstance(row, dict):
        return "not an object"
    missing = [f for f in PROGRAM_FIELDS if f not in row]
    if missing:
        return f"missing {missing}"
    if not isinstance(row["source"], str) or len(row["source"].strip()) < 8:
        return "no source for the rule text"
    for f in ("daily_loss", "max_loss"):
        v = row[f]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= 0.5:
            return f"{f} {v!r} is not in (0, 0.5]"
    if isinstance(row["min_days"], bool) or not isinstance(row["min_days"], int) \
            or row["min_days"] < 0:
        return "min_days is not a non-negative int"
    tg, nx = row["targets"], row["next_phase"]
    if not isinstance(tg, dict) or not tg or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= 1
            for v in tg.values()):
        return "targets must map each challenge phase to a fraction in (0, 1]"
    if not isinstance(nx, dict) or set(nx) != set(tg) \
            or not all(v == "funded" or v in tg for v in nx.values()):
        return "next_phase must chain every challenge phase to another phase or 'funded'"
    if "phase1" not in tg:
        return "the chain must start at phase1"
    if row.get("profit_cap") is not None:
        return "profit_cap is not enforced by the prop executor yet; refused until it is"
    if row["max_loss_basis"] not in MODELLED_MAX_LOSS_BASIS:
        return (f"max_loss_basis {row['max_loss_basis']!r} is not modelled (only "
                f"{list(MODELLED_MAX_LOSS_BASIS)}); a trailing drawdown is refused")
    if row["daily_loss_basis"] not in MODELLED_DAILY_LOSS_BASIS:
        return (f"daily_loss_basis {row['daily_loss_basis']!r} is not modelled (only "
                f"{list(MODELLED_DAILY_LOSS_BASIS)})")
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(str(row["day_tz"]))
    except Exception:
        return f"day_tz {row['day_tz']!r} is not an IANA zone"
    return None


@dataclass(frozen=True)
class Account:
    id: str
    firm: str
    program: str
    terminal_path: str | None = None
    enabled: bool = True

    @property
    def legacy(self) -> bool:
        return self.id == LEGACY

    @property
    def xacct(self) -> str:
        """The account's name in data/xacct/ (cross_account books and in-flight holds)."""
        return LEGACY if self.legacy else f"prop_{self.id}"

    @property
    def book_key(self) -> str:
        """Its block in CERT_BOOK_LIVE.json."""
        return self.xacct


def xacct_name(account_id: str) -> str:
    return LEGACY if account_id == LEGACY else f"prop_{account_id}"


def paths(acct: Account, *, data: Path | None = None, reports: Path | None = None,
          logs: Path | None = None) -> dict[str, Path]:
    """Every per-account file. The legacy account's are the FTMO lane's original paths."""
    data, reports, logs = data or DATA, reports or REPORTS, logs or LOGS
    if acct.legacy:
        return {"declaration": data / "FTMO_LIVE_ACCOUNT.json",
                "venue_state": reports / "FTMO_ACCOUNT_STATE.json",
                "phase_state": data / "ftmo_phase_state.json",
                "alloc_report": reports / "FTMO_ALLOCATOR.json",
                "alloc_armed": data / "FTMO_ALLOCATOR_ARMED",
                "exec_armed": data / "FTMO_EXECUTOR_ARMED",
                "exec_state": data / "ftmo_executor_state.json",
                "exec_out": reports / "FTMO_EXEC.json",
                "exec_intents": data / "ftmo_exec_intents.jsonl",
                "exec_log": logs / "ftmo_executor.log",
                "reader_log": logs / "ftmo_venue_reader.log"}
    d, r = data / "prop" / acct.id, reports / "prop" / acct.id
    return {"declaration": d / "ACCOUNT.json",
            "venue_state": r / "ACCOUNT_STATE.json",
            "phase_state": d / "phase_state.json",
            "alloc_report": r / "ALLOCATOR.json",
            "alloc_armed": d / "ALLOCATOR_ARMED",
            "exec_armed": d / "EXECUTOR_ARMED",
            "exec_state": d / "executor_state.json",
            "exec_out": r / "EXEC.json",
            "exec_intents": d / "exec_intents.jsonl",
            "exec_log": logs / f"prop_{acct.id}_executor.log",
            "reader_log": logs / f"prop_{acct.id}_venue_reader.log"}


def firm_paths(firm: str, *, data: Path | None = None) -> dict[str, Path]:
    """A firm's venue files, shared by its accounts."""
    data = data or DATA
    if firm == LEGACY_FIRM:
        return {"registry": data / "ftmo_registry.json",
                "surface": data / "cost_surface_ftmo.json",
                "bars": data / "universe_ftmo"}
    d = data / "prop" / f"firm_{firm}"
    return {"registry": d / "registry.json", "surface": d / "cost_surface.json", "bars": d / "bars"}


def _legacy_row(raw: dict[str, Any] | None) -> Account:
    enabled = True if raw is None else raw.get("enabled", True) is not False
    return Account(id=LEGACY, firm=LEGACY_FIRM, program=LEGACY_PROGRAM, terminal_path=None,
                   enabled=enabled)


def load(data: Path | None = None) -> tuple[list[Account], list[str]]:
    """([every registered account, the legacy one first], [why each refused row was refused])."""
    data = data or DATA
    errors: list[str] = []
    path = data / REGISTRY_NAME
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return [_legacy_row(None)], []
    except (OSError, ValueError) as exc:
        return [_legacy_row(None)], [f"{REGISTRY_NAME} unreadable ({type(exc).__name__}); "
                                     f"the legacy account runs alone"]
    rows = doc.get("accounts") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return [_legacy_row(None)], [f"{REGISTRY_NAME} has no 'accounts' list; the legacy "
                                     f"account runs alone"]
    progs, _ = programs(data)
    legacy_raw = next((r for r in rows if isinstance(r, dict) and r.get("id") == LEGACY), None)
    out = [_legacy_row(legacy_raw)]
    # the legacy account's terminal is FTMO's default install; no other account may claim it
    seen_ids, seen_terms = {LEGACY}, {LEGACY_TERMINAL.lower()}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {i}: not an object")
            continue
        aid = row.get("id")
        if aid == LEGACY:
            continue
        firm, program, term = row.get("firm"), row.get("program"), row.get("terminal_path")
        if not isinstance(aid, str) or not ID_RE.match(aid):
            errors.append(f"row {i}: id {aid!r} is not [a-z0-9_], 1-24 chars")
            continue
        if aid in seen_ids:
            errors.append(f"row {i}: id {aid!r} is registered twice")
            continue
        if not isinstance(firm, str) or not FIRM_RE.match(firm):
            errors.append(f"{aid}: firm {firm!r} is not [a-z0-9_]")
            continue
        if not isinstance(program, str) or program not in progs:
            errors.append(f"{aid}: program {program!r} is not a known, sourced rule set "
                          f"({PROGRAMS_NAME})")
            continue
        if not isinstance(term, str) or not term.strip():
            errors.append(f"{aid}: no terminal_path (one terminal per account)")
            continue
        norm_term = term.strip().lower().replace("/", "\\")
        if norm_term in seen_terms:
            errors.append(f"{aid}: terminal {term!r} is another account's; refused")
            continue
        seen_ids.add(aid)
        seen_terms.add(norm_term)
        out.append(Account(id=aid, firm=firm, program=program, terminal_path=term.strip(),
                           enabled=row.get("enabled", True) is not False))
    return out, errors


def get(account_id: str, data: Path | None = None) -> Account:
    """The registered account `account_id`, or ValueError naming why not."""
    accounts, errors = load(data)
    for a in accounts:
        if a.id == account_id:
            return a
    tail = f" ({'; '.join(errors)})" if errors else ""
    raise ValueError(f"prop account {account_id!r} is not registered in {REGISTRY_NAME}{tail}")


def xacct_names(data: Path | None = None) -> tuple[str, ...]:
    """Every registered account's data/xacct name, the legacy one first."""
    return tuple(a.xacct for a in load(data)[0])


def account_of_xacct(name: str, data: Path | None = None) -> Account | None:
    for a in load(data)[0]:
        if a.xacct == name:
            return a
    return None


#: WHICH ACCOUNT A PROP PROCESS SERVES (2026-11-03, replacing the per-process rebinding of
#: module globals, which the release gate cannot bound): read ONCE, at import, from this
#: variable. Unset is the legacy FTMO account, so every existing task is unchanged; the fleet
#: runner (prop/prop_fleet.py) sets it per child. A process's account never changes after import.
PROCESS_ENV = "QUANT_PROP_ACCOUNT"
#: The account a process is given when its variable names no usable account: its files live
#: under data/prop/refused/, where nothing is ever armed, and the process refuses to run.
REFUSED = Account(id="refused", firm="refused", program="refused", terminal_path=None,
                  enabled=False)


def for_process(environ: Any = None, data: Path | None = None) -> tuple[Account, str | None]:
    """(the account this process serves, why it may not run or None). Never raises: an
    unregistered id or an unknown program is REFUSED with its reason."""
    import os
    raw = str((os.environ if environ is None else environ).get(PROCESS_ENV) or "").strip()
    try:
        acct = get(raw or LEGACY, data)
    except ValueError as exc:
        return REFUSED, str(exc)
    if acct.program not in programs(data)[0]:
        return REFUSED, f"prop account {acct.id}: program {acct.program!r} is unknown"
    return acct, None


def venue(acct: Account, data: Path | None = None) -> dict[str, Any]:
    """What a non-legacy account changes in the follower's shared helpers, passed to them as
    arguments: its terminal, its declaration, its program's loss limits and trading day. The
    legacy account (and REFUSED) is {}: every helper's own default, byte-identical."""
    prog = programs(data)[0].get(acct.program)
    if acct.legacy or acct is REFUSED or prog is None:
        return {}
    return {"terminal_path": str(acct.terminal_path),
            "terminal_env": f"QUANT_PROP_{acct.id.upper()}_TERMINAL",
            "account_file": paths(acct, data=data)["declaration"],
            "account_types": {acct.program: float(prog["daily_loss"])},
            "daily_loss": float(prog["daily_loss"]), "max_loss": float(prog["max_loss"]),
            "day_tz": str(prog["day_tz"]), "program": acct.program}
