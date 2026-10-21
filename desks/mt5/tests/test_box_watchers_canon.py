"""The two box watchers ported from C:\\opt\\quant-ops compile, and stay the box's bytes.

Neither script is imported: both run on import (read box paths, page, exit), so they are only
compiled. Below each file's leading `#` comment block the body must hash, with CRLF line endings,
to the sha256 the trading box reported for its original -- the port's promise of identical
behaviour, pinned rather than asserted in a comment.
"""
from __future__ import annotations

import hashlib
import py_compile
from pathlib import Path

import pytest

WATCHERS = Path(__file__).resolve().parents[1] / "scripts" / "watchers"
BOX_SHA256 = {
    "ftmo_follow.py": "b657dfac2975b456493787b56b1bcb8d619e40d8165759d5e0aa0ec78072c0af",
    "e8_window_guard.py": "c72dcb882fa0639f7b2776df800239f9daac1133d9da7f99459f25a4c8aff6e8",
}


@pytest.mark.parametrize("name", sorted(BOX_SHA256))
def test_watcher_compiles(name: str, tmp_path: Path) -> None:
    py_compile.compile(str(WATCHERS / name), cfile=str(tmp_path / (name + "c")), doraise=True)


@pytest.mark.parametrize("name", sorted(BOX_SHA256))
def test_watcher_body_is_the_box_original(name: str) -> None:
    lines = (WATCHERS / name).read_bytes().replace(b"\r\n", b"\n").split(b"\n")
    start = next(i for i, line in enumerate(lines) if not line.startswith(b"#"))
    body = b"\n".join(lines[start:]).replace(b"\n", b"\r\n")
    assert hashlib.sha256(body).hexdigest() == BOX_SHA256[name]
