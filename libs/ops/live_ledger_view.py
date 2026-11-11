"""Audited metadata views over append-only broker records. Never places an order."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PosixPath, WindowsPath
from typing import Any, TypeVar, overload

FIELDS = frozenset({"time", "sleeve", "risk_quote", "r_multiple", "r_backfilled",
                    "entry_order", "entry_deal", "position_id", "close_order", "magic"})
SIDECAR = "live_ledger_corrections.jsonl"


class LedgerViewError(RuntimeError):
    """An invalid correction must not masquerade as an empty or valid ledger."""


def record_digest(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def effective_text(path: Path, raw: str) -> str:
    sidecar = Path(path).with_name(SIDECAR)
    if not sidecar.exists():
        manifest = Path(path).parent / "IMMUTABLE_MANIFEST.json"
        if manifest.exists():
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            if any(str(key).endswith("/" + SIDECAR) for key in doc.get("append_only", {})):
                raise LedgerViewError("Required audited corrections are missing")
        return raw
    try:
        event_lines = [line for line in sidecar.read_text(encoding="utf-8").splitlines()
                       if line.strip()]
        manifest = Path(path).parent / "IMMUTABLE_MANIFEST.json"
        if manifest.exists():
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            seals = doc.get("append_only", {})
            matches = [value for key, value in seals.items()
                       if str(key).endswith("/" + SIDECAR)]
            if len(matches) != 1 or not isinstance(matches[0], dict):
                raise LedgerViewError("Audited corrections have no unique seal")
            seal = matches[0]
            count = seal.get("records")
            if type(count) is not int or count < 1 or len(event_lines) < count:
                raise LedgerViewError("Sealed correction prefix is incomplete")
            prefix = "".join(line + "\n" for line in event_lines[:count]).encode()
            if hashlib.sha256(prefix).hexdigest()[:16] != seal.get("prefix_sha"):
                raise LedgerViewError("Sealed corrections changed")
        events = [json.loads(line) for line in event_lines]
        header = events[0]
        if header["schema_version"] != 1:
            raise LedgerViewError("Unsupported ledger-view schema")
        count = header["raw_prefix_records"]
        lines = raw.replace("\r\n", "\n").splitlines(keepends=True)
        if type(count) is not int or count < 1 or len(lines) < count:
            raise LedgerViewError("Raw sealed prefix is incomplete")
        prefix = "".join(lines[:count]).encode()
        if hashlib.sha256(prefix).hexdigest() != header["raw_prefix_sha256"]:
            raise LedgerViewError("Raw sealed prefix changed")
        rows = [json.loads(line) for line in lines if line.strip()]
        ids = [row["deal"] for row in rows]
        if any(type(key) is not int or key <= 0 for key in ids) or len(set(ids)) != len(ids):
            raise LedgerViewError("Raw trade identity is invalid or duplicated")
        by_id = {row["deal"]: dict(row) for row in rows}
        for correction in events[1:]:
            key = correction["deal"]
            if key not in by_id or record_digest(by_id[key]) != correction["before_sha256"]:
                raise LedgerViewError("Correction does not bind its preceding record")
            changes = correction["set"]
            if not isinstance(changes, dict) or set(changes) - FIELDS:
                raise LedgerViewError("Correction changes financial facts or account identity")
            updated = dict(by_id[key], **changes)
            if record_digest(updated) != correction["after_sha256"]:
                raise LedgerViewError("Correction result digest changed")
            by_id[key] = updated
        order = header["projection_order"]
        if (not isinstance(order, list) or len(set(order)) != len(order)
                or not set(order) <= set(ids)):
            raise LedgerViewError("Projection lost or invented a trade")
        order = order + [key for key in ids if key not in set(order)]
        return "".join(json.dumps(by_id[key], allow_nan=False) + "\n" for key in order)
    except LedgerViewError:
        raise
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise LedgerViewError("Malformed audited ledger view") from error


class _LedgerPath(Path):
    def read_text(self, *args: Any, **kwargs: Any) -> str:
        raw = Path(self).read_text(*args, **kwargs)
        if self.name != "live_ledger.jsonl":
            return raw
        return effective_text(Path(self), raw)

    def read_bytes(self) -> bytes:
        if self.name != "live_ledger.jsonl":
            return Path(self).read_bytes()
        return self.read_text(encoding="utf-8").encode()

    def open(self, *args: Any, **kwargs: Any) -> Any:
        if self.name != "live_ledger.jsonl":
            return Path(self).open(*args, **kwargs)
        mode = str(args[0] if args else kwargs.get("mode", "r"))
        if mode in {"r", "rt", "rb"}:
            body = self.read_text(encoding="utf-8")
            return io.BytesIO(body.encode()) if "b" in mode else io.StringIO(body)
        # The writer still appends real broker records to the raw file.
        if mode in {"a", "at", "ab"}:
            return Path(self).open(*args, **kwargs)
        raise LedgerViewError("A corrected view cannot rewrite raw broker history")


_T = TypeVar("_T")


class _WindowsLedgerPath(_LedgerPath, WindowsPath):
    """Concrete flavour also works with pathlib on Python 3.11."""


class _PosixLedgerPath(_LedgerPath, PosixPath):
    """Concrete flavour used by the canonical Linux CI host."""


@overload
def ledger_path(path: Path) -> Path: ...


@overload
def ledger_path(path: _T) -> _T: ...


def ledger_path(path: Any) -> Any:
    if type(path) is type(Path()) and path.name == "live_ledger.jsonl":
        return _WindowsLedgerPath(path) if isinstance(path, WindowsPath) else _PosixLedgerPath(path)
    return path
