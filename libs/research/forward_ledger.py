"""ONE FORWARD LEDGER PER CLOCK KEY, and a named gap where the past shared one.

THE DEFECT (measured 2026-10-14 on the tracked `reports/shadow/shadow_state.json` at 5cc427f82).
`shadow_forward` names a clock's trade ledger `ledger_<sym>_<window>.json` (breakout) or
`ledger_<sym>_<family>_<window>.json`, from symbol, family and window ONLY. Every other part of
the clock key -- the parameter signature `#...`, the chart `@TF`, the side `.SHORT` -- is dropped,
so every parameterisation of a cell writes ONE file and the last clock replayed in a pass owns
it. Of 845 clock rows, 796 sat in 102 shared files (88 files with more than one non-KILL clock),
including both LIVE gap-decay sleeves' certified base clocks (AUDCHF, EURZAR) and the four
certified XAUUSD.asia clocks behind six STANDBY gold rows. Every reader that globbed or resolved
a ledger got one clock's trades under another clock's name. The state rows were never mixed (the
engine computes n / exp_r / forward_t from its in-memory trades), so the promoter's own numbers
stand; the FILES were mixed, and every file reader inherited it.

THE RULE FROM HERE ON.

  * `per_key_name(key)` is `ledger_<key with dots as underscores>.json` -- the convention
    `forward_reconcile` and `decay_monitor` already resolve by. For a key with no variant tail
    it is byte-identical to the legacy name, so a clock that never collided keeps its file.
  * A legacy file that more than one clock key ever mapped to is FROZEN in the shadow
    directory's `shared_ledgers.json`, append-only: nothing ever writes it again, nothing deletes
    it, and no reader treats it as any clock's series. A clock whose per-key name IS a frozen
    legacy file (the base key of a colliding group) writes `ledger_<...>#own.json` instead.
  * `resolve` gives a reader the clock's own file, or UNMEASURED_SHARED_LEDGER (a named gap) when
    the only file on disk is a shared legacy one, or NO_LEDGER. It never falls back to a sibling.

WHY NOTHING IS SPLIT OUT OF THE LEGACY FILES. A legacy row carries entry/exit, side, R, phase and
the bar stamp -- no clock key -- so no row can be attributed to one clock unambiguously, and a
guess would mint exactly the mixed series this module exists to end. Nothing is lost by refusing:
`shadow_forward` replays every clock from SHADOW_START on each pass, so a clock's own file holds
its whole record from the first pass after the fix.

NAMES ARE BOUNDED. The longest key on the box made a 208-character file name; Windows refuses a
path past 260 and the shadow directory costs ~37. A name past NAME_MAX keeps a readable prefix and
ends in a 16-hex digest of the full key, so two keys can never meet on a truncation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REGISTRY_NAME = "shared_ledgers.json"
OWN_SUFFIX = "#own"
NAME_MAX = 200

OWN = "OWN"
UNMEASURED_SHARED_LEDGER = "UNMEASURED_SHARED_LEDGER"
NO_LEDGER = "NO_LEDGER"


@dataclass(frozen=True)
class KeyParts:
    symbol: str
    family: str
    window: str
    timeframe: str
    signature: str
    side: str

    @property
    def is_variant(self) -> bool:
        return bool(self.timeframe or self.signature or self.side)


def parse_key(key: str) -> KeyParts | None:
    """`shadow_forward.sleeve_key`'s grammar read back: `SYM.window` (breakout) or
    `SYM.family.window`, then `@TF`, then `#signature`, then `.SHORT`. None if it is not one."""
    k = str(key)
    side = ""
    if k.endswith(".SHORT"):
        k, side = k[: -len(".SHORT")], "SHORT"
    head, _, sig = k.partition("#")
    stem, _, tf = head.partition("@")
    parts = stem.split(".")
    if len(parts) == 2 and all(parts):
        return KeyParts(parts[0], "session_range_breakout", parts[1], tf, sig, side)
    if len(parts) == 3 and all(parts):
        return KeyParts(parts[0], parts[1], parts[2], tf, sig, side)
    return None


def legacy_name_for(symbol: str, family: str, window: str) -> str:
    """Exactly the name `shadow_forward` wrote before 2026-10-14 (and still writes for a clock
    whose key has no variant tail)."""
    return (f"ledger_{symbol}_{window}.json" if family == "session_range_breakout"
            else f"ledger_{symbol}_{family}_{window}.json")


def legacy_name(key: str) -> str | None:
    p = parse_key(key)
    return legacy_name_for(p.symbol, p.family, p.window) if p else None


def _bounded(stem: str, key: str) -> str:
    name = f"ledger_{stem}.json"
    if len(name) <= NAME_MAX:
        return name
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:16]
    keep = NAME_MAX - len("ledger_") - len(".json") - len("#h") - len(digest)
    return f"ledger_{stem[:keep]}#h{digest}.json"


def per_key_name(key: str) -> str:
    """`ledger_<key with dots as underscores>.json`; the legacy name for a non-variant key."""
    p = parse_key(key)
    if p is not None and not p.is_variant:
        return legacy_name_for(p.symbol, p.family, p.window)
    return _bounded(str(key).replace(".", "_"), key)


def own_name(key: str) -> str:
    """The name a base key writes once its legacy file is frozen as shared."""
    base = per_key_name(key)
    return _bounded(base[len("ledger_"):-len(".json")] + OWN_SUFFIX, f"{key}{OWN_SUFFIX}")


def collisions(keys: Iterable[str]) -> dict[str, list[str]]:
    """legacy file -> the distinct clock keys that map to it, for every file with more than one."""
    groups: dict[str, set[str]] = {}
    for k in keys:
        name = legacy_name(str(k))
        if name:
            groups.setdefault(name, set()).add(str(k))
    return {n: sorted(m) for n, m in sorted(groups.items()) if len(m) > 1}


def load_shared(shadow_dir: Path) -> dict[str, Any]:
    """The frozen legacy files: {name: {members, frozen_at, why}}. Absent or unreadable is {}."""
    try:
        doc = json.loads((Path(shadow_dir) / REGISTRY_NAME).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    files = doc.get("files") if isinstance(doc, dict) else None
    return dict(files) if isinstance(files, dict) else {}


def freeze_collisions(keys: Iterable[str], shadow_dir: Path, *,
                      now: datetime | None = None) -> dict[str, Any]:
    """Add every legacy file more than one key maps to into the registry. APPEND-ONLY: a frozen
    file is never unfrozen and its member list only grows. Returns the merged registry files."""
    d = Path(shadow_dir)
    files = load_shared(d)
    stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    changed = False
    for name, members in collisions(keys).items():
        row = files.get(name) if isinstance(files.get(name), dict) else None
        if row is None:
            files[name] = {"members": members, "frozen_at": stamp,
                           "legacy_file_present": (d / name).exists(),
                           "why": ("written under symbol/family/window only by more than one "
                                   "clock key; its rows carry no key, so it is no clock's series")}
            changed = True
        else:
            merged = sorted(set(row.get("members") or []) | set(members))
            if merged != row.get("members"):
                row["members"] = merged
                changed = True
    if changed:
        d.mkdir(parents=True, exist_ok=True)
        body = {"schema": 1, "rule": ("append-only: a frozen legacy ledger is never written, "
                                      "deleted or read as any clock's series; each member clock "
                                      "writes and reads its own per-key ledger"),
                "updated_at": stamp, "files": dict(sorted(files.items()))}
        tmp = d / (REGISTRY_NAME + ".tmp")
        tmp.write_text(json.dumps(body, indent=1), "utf-8")
        os.replace(tmp, d / REGISTRY_NAME)
    return files


def writer_name(key: str, shared: Mapping[str, Any]) -> str:
    name = per_key_name(key)
    return own_name(key) if name in shared else name


def writer_path(key: str, shadow_dir: Path, shared: Mapping[str, Any] | None = None) -> Path:
    """Where `shadow_forward` writes clock `key`'s ledger. Never a frozen shared legacy file."""
    d = Path(shadow_dir)
    return d / writer_name(key, load_shared(d) if shared is None else shared)


def resolve(key: str, dirs: Iterable[Path], shared: Mapping[str, Any] | None = None
            ) -> tuple[Path | None, str, str]:
    """(path, status, why) for a READER of clock `key`.

    OWN with the clock's own file; UNMEASURED_SHARED_LEDGER when the only file is a legacy one the
    key does not own alone (a variant reading its cell's file, or a base key whose legacy file is
    frozen); NO_LEDGER otherwise. `shared` defaults to the registry in each directory; a caller
    holding every clock key should pass `collisions(keys)` merged in, so a box that has not yet
    written its registry still refuses a shared file.
    """
    dirs = [Path(d) for d in dirs]
    legacy = legacy_name(key)
    p = parse_key(key)
    for d in dirs:
        frozen = dict(load_shared(d))
        frozen.update(shared or {})
        mine = d / writer_name(key, frozen)
        if mine.exists() and mine.name not in frozen:
            return mine, OWN, str(mine)
    for d in dirs:
        frozen = dict(load_shared(d))
        frozen.update(shared or {})
        if legacy and (d / legacy).exists() and (legacy in frozen or (p and p.is_variant)):
            return None, UNMEASURED_SHARED_LEDGER, (
                f"{d / legacy} is shared by several clock keys (written under symbol/family/"
                f"window only); its rows carry no key, so it is not {key}'s series")
    return None, NO_LEDGER, f"no ledger for {key} in {[str(d) for d in dirs]}"


def read_rows(key: str, dirs: Iterable[Path], shared: Mapping[str, Any] | None = None
              ) -> tuple[list[dict[str, Any]] | None, str, str]:
    """(rows | None, status, why): `resolve` plus the read. Unreadable is NO_LEDGER with why."""
    path, status, why = resolve(key, dirs, shared)
    if path is None:
        return None, status, why
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return None, NO_LEDGER, f"{path} unreadable: {type(exc).__name__}"
    if not isinstance(doc, list):
        return None, NO_LEDGER, f"{path} is not a list of trades"
    return [r for r in doc if isinstance(r, dict)], OWN, str(path)


_REPO = Path(__file__).resolve().parents[2]
# A drive-anchored (`C:\\...`, `C:/...`) or root-anchored (`/home/...`) path token. The lookbehind
# keeps prose like `symbol/family/window` and relative paths like `reports/x.json` untouched.
_ABS = re.compile(r"(?<![\w.:/\\])(?:[A-Za-z]:[\\/]|/)[^\s'\",;)\]}]+")


def public_path(p: str | Path) -> str:
    """A path fit for a PUBLISHED artifact: repo-relative when it sits in the repository, else its
    basename. The repo is public, so a box's absolute layout never leaves the box."""
    raw = str(p)
    try:
        if not Path(raw).is_absolute():
            raise ValueError(raw)          # a Windows path read on POSIX, or a relative one
        return Path(raw).relative_to(_REPO).as_posix()
    except ValueError:
        return re.split(r"[\\/]", raw.rstrip("\\/"))[-1] or raw


def public_text(text: str) -> str:
    """`text` with every absolute path token replaced by `public_path` of it."""
    return _ABS.sub(lambda m: public_path(m.group(0)), text)


def public_doc(obj: Any) -> Any:
    """`obj` (a JSON-shaped document) with `public_text` applied to every string, keys included."""
    if isinstance(obj, str):
        return public_text(obj)
    if isinstance(obj, Mapping):
        return {public_text(str(k)): public_doc(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [public_doc(v) for v in obj]
    return obj


__all__ = ["NAME_MAX", "NO_LEDGER", "OWN", "OWN_SUFFIX", "REGISTRY_NAME",
           "UNMEASURED_SHARED_LEDGER", "KeyParts", "collisions", "freeze_collisions",
           "legacy_name", "legacy_name_for", "load_shared", "own_name", "parse_key",
           "per_key_name", "public_doc", "public_path", "public_text", "read_rows", "resolve", "writer_name", "writer_path"]
