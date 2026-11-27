"""Provision audited ledger state only from the canonical released adoption target."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops.live_ledger_migration import authorized_handoff, migration_bytes  # noqa: E402
from libs.ops.release_promotion import Git, gate  # noqa: E402

BASELINE = "f707a5a534848601823feeedca431873053e1f97"
LEDGER = "desks/mt5/data/live_ledger.jsonl"
SIDECAR = "desks/mt5/data/live_ledger_corrections.jsonl"
MANIFEST = "desks/mt5/data/IMMUTABLE_MANIFEST.json"


def show(target: str, rel: str) -> bytes:
    return subprocess.run(["git", "show", f"{target}:{rel}"], cwd=ROOT,
                          check=True, capture_output=True, timeout=120).stdout


def atomic(path: Path, body: bytes) -> None:
    temporary = path.with_name(path.name + f".migration-{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    decision = gate(ROOT, fetch=False)
    if not authorized_handoff(decision, args.target, Git(ROOT)):
        raise RuntimeError("Migration target is not the canonical released adoption choice")
    exists = subprocess.run(["git", "cat-file", "-e", f"{args.target}:{SIDECAR}"],
                            cwd=ROOT, capture_output=True, timeout=120).returncode == 0
    if not exists:
        print(json.dumps({"state": "NOT_REQUIRED", "target": args.target}))
        return 0
    subprocess.run([sys.executable, "scripts/check_target_seal.py", args.target],
                   cwd=ROOT, check=True, capture_output=True, timeout=180)
    corrections = show(args.target, SIDECAR)
    manifest_bytes = show(args.target, MANIFEST)
    target_manifest = json.loads(manifest_bytes)
    previous = json.loads((ROOT / MANIFEST).read_bytes())
    for key, value in previous["append_only"].items():
        if target_manifest["append_only"].get(key) != value:
            raise RuntimeError("Adoption must preserve every existing record seal")
    if previous["vintage"] != target_manifest["vintage"]:
        raise RuntimeError("Adoption must preserve the existing vintage seal")
    sidecar = ROOT / SIDECAR
    if sidecar.exists() and sidecar.read_bytes().replace(b"\r\n", b"\n") != corrections:
        raise RuntimeError("Existing correction stream differs; refusing to overwrite it")
    baseline = show(BASELINE, LEDGER)
    path = ROOT / LEDGER
    current = path.read_bytes()
    planned = migration_bytes(baseline, current, corrections, target_manifest)
    if not args.apply:
        print(json.dumps({"state": "VERIFIED_PLAN", "rows": len(current.splitlines()),
                          "financial_facts_changed": False, "target": args.target}))
        return 0
    if os.name != "nt":
        raise RuntimeError("Automatic migration requires the Windows exclusive-file handoff")
    if planned == current and sidecar.exists() and previous == target_manifest:
        receipt = {"schema": "ledger_view_adoption/1", "state": "ALREADY_VERIFIED",
                   "target": args.target, "rows": len(current.splitlines()),
                   "verified_at": datetime.now(UTC).isoformat(),
                   "financial_facts_changed": False}
        atomic(ROOT / "desks/mt5/reports/LEDGER_VIEW_ADOPTION.json",
               (json.dumps(receipt, indent=2)+"\n").encode())
        print(json.dumps(receipt))
        return 0
    # Sharing mode zero blocks every concurrent ledger reader and append writer during handoff.
    import msvcrt
    from ctypes import wintypes

    windows_api = vars(ctypes)
    kernel = windows_api["WinDLL"]("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    native = create(str(path), 0xC0000000, 0, None, 3, 0x80, None)
    if native == wintypes.HANDLE(-1).value:
        raise windows_api["WinError"](windows_api["get_last_error"]())
    descriptor = vars(msvcrt)["open_osfhandle"](native, os.O_RDWR | getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "r+b") as handle:
        locked_current = handle.read()
        # A broker append between planning and the exclusive handle is retained and revalidated.
        planned = migration_bytes(baseline, locked_current, corrections, target_manifest)
        backup = ROOT / "data/secrets/ledger-migration-backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup.mkdir(parents=True, exist_ok=False)
        (backup / "live_ledger.jsonl").write_bytes(locked_current)
        (backup / "IMMUTABLE_MANIFEST.json").write_bytes((ROOT / MANIFEST).read_bytes())
        if sidecar.exists():
            (backup / sidecar.name).write_bytes(sidecar.read_bytes())
        atomic(sidecar, corrections)
        atomic(ROOT / MANIFEST, manifest_bytes)
        handle.seek(0)
        handle.write(planned)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
    receipt = {"schema": "ledger_view_adoption/1", "state": "MIGRATED",
               "target": args.target, "rows": len(planned.splitlines()),
               "verified_at": datetime.now(UTC).isoformat(),
               "raw_sha256": hashlib.sha256(planned).hexdigest(),
               "financial_facts_changed": False, "original_seals_preserved": len(previous["append_only"])}
    atomic(ROOT / "desks/mt5/reports/LEDGER_VIEW_ADOPTION.json", (json.dumps(receipt, indent=2)+"\n").encode())
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
