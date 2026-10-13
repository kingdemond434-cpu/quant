"""WHICH MACHINE IS THIS? ONE ANSWER FOR EVERY FENCE (PR #130 audit follow-up, 2026-09-30).

Before this module three organs asked "am I on the trading box?" three different ways:
`libs/tiers/box_evidence.py` and `scripts/check_placement_interlock.py` by a hostname PREFIX
(`vmi3571445`), and `scripts/check_birth_obligations.py` by the age of `gateway_state.json` -- a
file that is tracked in git and therefore sits on every checkout. A hostname is a label anyone can
set and a prefix match is a guess; CLAUDE.md carries three wrong memory figures that were each a
reading from one box written down as a fact about the other. So the identity is now keyed on the
machine's own STABLE id:

  * Linux    -- `/etc/machine-id`
  * Windows  -- `HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid` via `winreg`

and compared with the trading box's id RECORDED in the committed `config/trading_host.json`.

THREE VERDICTS, NEVER TWO:

  TRADING     this machine's id was measured and equals the recorded one.
  OFF_BOX     this machine's id was measured, an id is recorded, and they differ.
  UNMEASURED  the id could not be read, or no id is recorded yet. The hostname is then read as a
              FALLBACK and reported (`hostname_match`), but it never turns into TRADING: a label
              is not an identity (L1.28a -- UNMEASURED is a real answer).

HOW A CONSUMER SPENDS AN UNMEASURED ANSWER depends on which side is safe for it, so the helper
exposes both and each caller names the one it uses:

  `confirmed_trading`  -- TRADING only. For anything that GRANTS credit (a Tier S layer counting
                          toward DONE): unproven identity earns nothing.
  `may_be_trading`     -- TRADING, or UNMEASURED with a matching hostname. For a fence that must
                          FAIL LOUD on the box (a silent halt, a stale birth axis): an unrecorded
                          id must never make the trading box read green.

RECORDING THE ID. Run once ON the trading box (the hostname must match, so the id of the other
box is never written down as this one's -- the exact trap CLAUDE.md warns about):

    python -m libs.ops.host_identity --record
    python -m libs.ops.host_identity          # print this machine's verdict
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_REL = "config/trading_host.json"
CONFIG = ROOT / CONFIG_REL
UNMEASURED = "UNMEASURED"
TRADING = "TRADING"
OFF_BOX = "OFF_BOX"
#: Only the fallback for a checkout whose config cannot be read (the Contabo trading box).
DEFAULT_TRADING_HOSTNAME = "vmi3571445"
_WIN_KEY = r"SOFTWARE\Microsoft\Cryptography"
#: DNS domains under which a fully-qualified name may still name a declared host. EMPTY ON PURPOSE.
#: Every hostname the trading box has ever recorded -- `config/trading_host.json`, the committed
#: attestation and placement-interlock stamps -- is the bare label, `vmi3571445` or `VMI3571445`
#: (Windows reports it upper-case); no stamp written on the box carries a domain. Dropping ANY
#: suffix let `vmi3571445.evil.com` read as the box (audit of #267, 2026-10-07). Add a domain here
#: only after a stamp written ON the box records it.
TRUSTED_DOMAINS: tuple[str, ...] = ()


def read_machine_id() -> str | None:
    """This machine's persistent id, or None when it cannot be read. Never raises."""
    if sys.platform.startswith("win"):
        try:
            import winreg
            flags = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _WIN_KEY, 0, flags) as k:
                value = str(winreg.QueryValueEx(k, "MachineGuid")[0]).strip()
            return value.lower() or None
        except Exception:
            return None
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(path).read_text("utf-8").strip()
        except OSError:
            continue
        if value:
            return value.lower()
    return None


def read_hostname() -> str:
    try:
        return socket.gethostname() or ""
    except Exception:
        return ""


def host_key(name: object) -> str:
    """A hostname as an identity compares it -- THE one normalisation every hostname check shares
    (`classify` here, `runtime_attestation.is_desk_host` and the drift / on-host checks in
    `scripts/check_runtime_attestation.py`).

    Stripped, casefolded and without a trailing root dot, because Windows reports the box as
    `VMI3571445` while every config and stamp holds `vmi3571445`. A domain suffix is dropped ONLY
    when it is in `TRUSTED_DOMAINS`; any other fully-qualified name keeps its whole spelling, so
    `vmi3571445.evil.com` keys as itself, never as the box, and a stamp claiming it while measured
    on `vmi3571445` reads as host drift rather than as the same machine.
    """
    full = str(name or "").strip().casefold().rstrip(".")
    label, _, domain = full.partition(".")
    return label if not domain or domain in TRUSTED_DOMAINS else full


def names_host(name: object, declared: Any) -> bool:
    """Does `name` name one of the `declared` hosts? Case-insensitive; a domain counts only when
    trusted (`host_key`). An empty name names nothing."""
    key = host_key(name)
    hosts = (declared,) if isinstance(declared, str) else tuple(declared)
    return bool(key) and key in {host_key(h) for h in hosts}


def load_config(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path or CONFIG).read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def recorded_machine_id(config: dict[str, Any] | None = None) -> str | None:
    cfg = load_config() if config is None else config
    raw = str(cfg.get("machine_id") or "").strip().lower()
    return raw or None


def trading_hostname(config: dict[str, Any] | None = None) -> str:
    cfg = load_config() if config is None else config
    return str(cfg.get("hostname") or DEFAULT_TRADING_HOSTNAME)


@dataclass(frozen=True)
class HostIdentity:
    verdict: str
    hostname: str
    machine_id: str
    recorded_machine_id: str
    trading_hostname: str
    hostname_match: bool
    why: str

    @property
    def confirmed_trading(self) -> bool:
        return self.verdict == TRADING

    @property
    def may_be_trading(self) -> bool:
        return self.verdict == TRADING or (self.verdict == UNMEASURED and self.hostname_match)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["confirmed_trading"] = self.confirmed_trading
        d["may_be_trading"] = self.may_be_trading
        return d


def classify(machine_id: str | None, hostname: str,
             config: dict[str, Any] | None = None) -> HostIdentity:
    """The pure decision, so every branch is testable without touching the machine."""
    cfg = load_config() if config is None else config
    recorded = recorded_machine_id(cfg)
    thost = trading_hostname(cfg)
    mid = (machine_id or "").strip().lower() or None
    host_match = names_host(hostname, thost)
    if mid and recorded:
        verdict = TRADING if mid == recorded else OFF_BOX
        why = ("machine id equals the recorded trading-box id" if verdict == TRADING
               else "machine id differs from the recorded trading-box id")
        if verdict == OFF_BOX and host_match:
            why += f" (the hostname says {thost}; the id wins, a label is not an identity)"
    else:
        verdict = UNMEASURED
        missing = [] if mid else ["this machine's id is unreadable"]
        if not recorded:
            missing.append(f"no trading-box id is recorded in {CONFIG_REL}")
        why = ("; ".join(missing) + f" -- hostname fallback: {hostname or '?'} "
               + ("matches" if host_match else "does not match") + f" {thost}, "
               "reported, never taken as the identity")
    return HostIdentity(verdict=verdict, hostname=hostname, machine_id=mid or UNMEASURED,
                        recorded_machine_id=recorded or UNMEASURED, trading_hostname=thost,
                        hostname_match=host_match, why=why)


def identify(config_path: Path | None = None) -> HostIdentity:
    return classify(read_machine_id(), read_hostname(), load_config(config_path))


def is_recorded_trading_id(machine_id: Any, config: dict[str, Any] | None = None) -> bool | None:
    """For a COMMITTED document that names the machine it was written on: True/False against the
    recorded id, None (UNMEASURED) when either side is absent."""
    recorded = recorded_machine_id(config)
    mid = str(machine_id or "").strip().lower()
    if not recorded or not mid or mid == UNMEASURED.lower():
        return None
    return mid == recorded


def record(config_path: Path | None = None, *,
           identity: HostIdentity | None = None) -> dict[str, Any]:
    """Write THIS machine's id into the config -- refused unless the hostname names the trading
    box and the id is readable, so the other box's id is never recorded as this one's."""
    path = Path(config_path or CONFIG)
    cfg = load_config(path)
    ident = identity or classify(read_machine_id(), read_hostname(), cfg)
    if not ident.hostname_match:
        raise SystemExit(f"refused: hostname {ident.hostname!r} is not {ident.trading_hostname}; "
                         "record the id on the trading box itself")
    if ident.machine_id == UNMEASURED:
        raise SystemExit("refused: this machine's id is unreadable")
    cfg.update(hostname=ident.trading_hostname, machine_id=ident.machine_id,
               recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
               recorded_on=ident.hostname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return cfg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Which machine is this? (TRADING / OFF_BOX / UNMEASURED)")
    ap.add_argument("--record", action="store_true",
                    help="record this machine's id as the trading box's (trading box only)")
    args = ap.parse_args(argv)
    if args.record:
        print(json.dumps(record(), indent=2))
        return 0
    print(json.dumps(identify().as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
