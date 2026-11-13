"""Fold an append-only JSONL ledger incrementally: re-read only what was appended since last time.

WHY (2026-11-13). The judge publishes verdicts in `merge_and_publish`, a phase that keeps the
judge's tree at ~0.4 busy cores for ~1h a sweep. Its wall profile on the box (JUDGE_RESIDENT.json
`sweep_phase.wall_profile`, sweep pid 25964) puts 27% of the phase's samples in
`preregistration.spec_index` and another ~12% in `hypothesis_graph._fate_index`. Both re-parse a
whole append-only ledger from byte 0 on every sweep, and together they read ~15 GB. Both are folds
that respect append order (earliest-wins / latest-wins per key), so the answer for
`prefix + appended` is the answer for `prefix`, folded forward over `appended`.

THE CONTRACT: the same answer as the full read, or no answer.
  * The cache records the byte offset it folded through and the SHA-256 of every byte before it.
    The prefix is re-hashed on every call (a raw read, ~1 GB/s, versus a JSON parse of the same
    bytes), so a ledger that was rewritten, truncated, merged by git or edited in the middle
    fails the hash and is folded again from byte 0. Nothing is trusted on size or mtime.
  * Only lines ending in a newline are committed to the cache. A trailing partial line (a writer
    mid-append) is folded into the returned answer but never into the cache.
  * Anything the fast path cannot reproduce exactly returns None, and the caller runs its own
    original full read: a fold that refuses a row (the graph raises on a non-object row), a line
    that does not parse where the original would give up, or a bare carriage return inside a line
    (text-mode reading splits there, a byte reader would not).
  * Every cache read or write failure is swallowed: the cache is an accelerator, never an input.
    `APPEND_FOLD_CACHE=0` turns it off.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

S = TypeVar("S")

VERSION = 1
CHUNK = 8 << 20
CACHE_DIR = ".fold_cache"


def enabled() -> bool:
    return os.environ.get("APPEND_FOLD_CACHE", "1").strip().lower() not in ("0", "off", "false",
                                                                              "no")


def cache_path(path: Path, kind: str) -> Path:
    return path.parent / CACHE_DIR / f"{path.name}.{kind}.json"


def _load(cp: Path, ledger: Path, kind: str) -> dict[str, Any] | None:
    try:
        doc = json.loads(cp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(doc, dict) or doc.get("v") != VERSION or doc.get("kind") != kind
            or doc.get("ledger") != str(ledger) or not isinstance(doc.get("offset"), int)
            or not isinstance(doc.get("sha256"), str) or "state" not in doc):
        return None
    return doc


def _save(cp: Path, ledger: Path, kind: str, offset: int, digest: str, state: Any) -> None:
    tmp = cp.with_name(f"{cp.name}.{os.getpid()}.tmp")
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"v": VERSION, "kind": kind, "ledger": str(ledger), "offset": offset,
                       "sha256": digest, "state": state}, fh, separators=(",", ":"))
        os.replace(tmp, cp)
    except (OSError, TypeError, ValueError):
        with contextlib.suppress(OSError):
            tmp.unlink()


def _line(raw: bytes, errors: str, strict_json: bool) -> tuple[bool, Any]:
    """(ok, obj). obj is None for a blank line. ok False means the fast path must give up."""
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    if b"\r" in raw:
        return False, None
    try:
        text = raw.decode("utf-8", errors=errors)
    except UnicodeDecodeError:
        return False, None
    if not text.strip():
        return True, None
    try:
        return True, json.loads(text)
    except ValueError:
        return (not strict_json), _SKIP


_SKIP: Any = object()


def fold_appended(path: Path, *, kind: str, empty: Callable[[], S],
                  fold: Callable[[S, Any], bool], encode: Callable[[S], Any],
                  decode: Callable[[Any], S], errors: str = "strict",
                  strict_json: bool = True) -> S | None:
    """The fold of every row of `path`, reusing the cached fold of an unchanged prefix.

    `fold(state, row)` folds one parsed row in place and returns False to refuse it (the caller's
    full read must then decide). `strict_json`: a line that fails to parse aborts the fast path
    (True) or is skipped (False), whichever the caller's own reader does. Returns None whenever
    the answer is not provably the full read's, and the caller falls back to that read.
    """
    if not enabled():
        return None
    try:
        ledger = path.resolve()
    except OSError:
        return None
    cp = cache_path(path, kind)
    doc = _load(cp, ledger, kind)
    try:
        fh = path.open("rb")
    except OSError:
        return None
    with fh:
        try:
            size = os.fstat(fh.fileno()).st_size
        except OSError:
            return None
        h = hashlib.sha256()
        state: S | None = None
        offset = 0
        if doc is not None and 0 < doc["offset"] <= size:
            left = doc["offset"]
            while left:
                b = fh.read(min(CHUNK, left))
                if not b:
                    break
                h.update(b)
                left -= len(b)
            if left == 0 and h.hexdigest() == doc["sha256"]:
                try:
                    state = decode(doc["state"])
                    offset = doc["offset"]
                except (TypeError, ValueError, KeyError, AttributeError):
                    state = None
        if state is None:
            fh.seek(0)
            h = hashlib.sha256()
            state = empty()
            offset = 0
        start = offset
        carry = b""
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            buf = carry + b
            cut = buf.rfind(b"\n")
            if cut < 0:
                carry = buf
                continue
            body, carry = buf[:cut + 1], buf[cut + 1:]
            h.update(body)
            offset += len(body)
            for raw in body.split(b"\n")[:-1]:
                ok, obj = _line(raw, errors, strict_json)
                if not ok:
                    return None
                if obj is None or obj is _SKIP:
                    continue
                if not fold(state, obj):
                    return None
    if offset != start or doc is None or doc.get("offset") != offset:
        _save(cp, ledger, kind, offset, h.hexdigest(), encode(state))
    if carry:
        ok, obj = _line(carry, errors, strict_json)
        if not ok:
            return None
        if obj is not None and obj is not _SKIP and not fold(state, obj):
            return None
    return state
