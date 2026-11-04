"""independent-review reads a PR diff as bytes it does not control (#674, run 41742215537): a
Shift-JIS fixture crashed it with UnicodeDecodeError, so the PR got no review at all."""

from __future__ import annotations

import os
import runpy
import stat
import sys
from pathlib import Path

import pytest

IR = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "ops" / "release" / "independent_review.py")
)


@pytest.mark.skipif(sys.platform == "win32", reason="the fake gh is a POSIX shell script")
def test_a_non_utf8_diff_is_read_not_crashed_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sjis = "価格".encode("shift_jis")  # not valid UTF-8
    gh = tmp_path / "gh"
    gh.write_bytes(
        b"#!/bin/sh\nprintf '+ price: " + b"".join(b"\\%03o" % c for c in sjis) + b"\\n'\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    out = IR["_gh"]("repos/o/r/pulls/1")
    assert out.startswith("+ price: ") and "\ufffd" in out
