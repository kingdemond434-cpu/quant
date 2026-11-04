"""independent-review reads a PR diff as bytes it does not control (#674, run 41742215537): a
Shift-JIS fixture crashed it with UnicodeDecodeError, so the PR got no review at all."""

from __future__ import annotations

import json
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


def _diff(path: str, body: bytes) -> str:
    raw = (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n".encode()
        + b"+"
        + body
        + b"\n"
    )
    return raw.decode("utf-8", errors="replace")


SJIS_CODE = "# -*- coding: shift_jis -*-\nlimit = 3  # 上限".encode("shift_jis")


def test_undecodable_bytes_in_code_fail_and_in_fixtures_are_only_counted() -> None:
    """#681 audit MF1: a Shift-JIS .py RUNS as text the model saw only as U+FFFD."""
    d = _diff("desks/mt5/prop/sizing.py", SJIS_CODE) + _diff(
        "tests/research/fixtures/jp_quotes.csv", "価格".encode("shift_jis")
    )
    code, data = IR["undecodable"](d)
    assert set(code) == {"desks/mt5/prop/sizing.py"} and code["desks/mt5/prop/sizing.py"] > 0
    assert set(data) == {"tests/research/fixtures/jp_quotes.csv"}
    for p in (
        "ops/x.csv",
        ".github/fixtures/a.txt",
        "tests/fixtures/run.py",
        "tests/fixtures/c.json",
    ):
        assert not IR["_is_data"](p), p  # never data, whatever its directory


def test_main_fails_a_shift_jis_code_hunk_before_any_model_and_reviews_a_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g = IR["main"].__globals__
    asked: list[str] = []
    notes: list[str] = []
    monkeypatch.setitem(g, "_annotate", notes.append)

    def run(diff: str) -> int:
        def gh(*args: str) -> str:
            if "compare/" in args[0]:
                return diff
            return json.dumps({"head": {"sha": "h" * 40}, "changed_files": 1})

        monkeypatch.setitem(g, "_gh", gh)
        monkeypatch.setitem(g, "rungs", lambda n: (asked.append("asked") or [], []))
        monkeypatch.setitem(g, "read_closure", lambda *a: (set(), "closure"))
        return int(IR["main"](["--repo", "o/r", "--pr", "1", "--head", "h" * 40,
                               "--base-sha", "b" * 40]))  # fmt: skip

    assert run(_diff("scripts/run_box.py", SJIS_CODE)) == 1
    assert not asked and "undecodable bytes" in notes[-1]  # no model ever saw it
    run(_diff("tests/research/fixtures/jp.csv", "価格".encode("shift_jis")))
    assert asked  # a data fixture still goes to review
