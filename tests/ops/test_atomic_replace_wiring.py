"""One atomic replace, retried while Windows refuses it, and the judge's writers all use it.

MergeDocket died on 10-27 on [WinError 5] replacing the 1.55M-row docket while a reader held it,
and the docket never shipped again. POSIX never refuses a rename, so these tests drive the
refusal by hand.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import atomic_replace as ar  # noqa: E402

#: The writers whose replaces died or would die the same way. A bare `os.replace(` in any of
#: them fails here: route it through `libs.ops.atomic_replace.replace_with_retry`.
WIRED = (
    "desks/mt5/research/merge_hypotheses.py",
    "desks/mt5/research/miner_candidate_compiler.py",
    "desks/mt5/research/judging_throughput.py",
)


def _refuse(n: int, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    real = ar.os.replace
    calls = {"n": 0}

    def fake(src, dst):
        calls["n"] += 1
        if calls["n"] <= n:
            raise PermissionError(13, "[WinError 5] Access is denied")
        return real(src, dst)

    monkeypatch.setattr(ar.os, "replace", fake)
    return calls


def test_a_refused_replace_is_retried_until_it_lands(tmp_path: Path, monkeypatch) -> None:
    calls = _refuse(4, monkeypatch)
    src, dst = tmp_path / "a.tmp", tmp_path / "a.json"
    src.write_text("new", "utf-8")
    dst.write_text("old", "utf-8")
    naps: list[float] = []
    assert ar.replace_with_retry(src, dst, sleep=naps.append) == 4
    assert dst.read_text("utf-8") == "new" and not src.exists() and calls["n"] == 5
    assert naps == sorted(naps) and max(naps) <= ar.MAX_STEP_S


def test_a_refusal_that_outlasts_the_budget_raises_and_keeps_the_old_file(
        tmp_path: Path, monkeypatch) -> None:
    _refuse(10**6, monkeypatch)
    src, dst = tmp_path / "a.tmp", tmp_path / "a.json"
    src.write_text("new", "utf-8")
    dst.write_text("old", "utf-8")
    naps: list[float] = []
    with pytest.raises(PermissionError):
        ar.replace_with_retry(src, dst, max_wait_s=20.0, sleep=naps.append)
    assert sum(naps) == pytest.approx(20.0)
    assert dst.read_text("utf-8") == "old"


def test_an_error_that_is_not_a_refusal_raises_at_once(tmp_path: Path) -> None:
    naps: list[float] = []
    with pytest.raises(FileNotFoundError):
        ar.replace_with_retry(tmp_path / "absent.tmp", tmp_path / "b.json", sleep=naps.append)
    assert naps == []


@pytest.mark.parametrize("rel", WIRED)
def test_no_wired_writer_calls_a_bare_os_replace(rel: str) -> None:
    src = (ROOT / rel).read_text("utf-8")
    bare = [i + 1 for i, line in enumerate(src.splitlines())
            if re.search(r"(?<![\w.])os\.replace\(", line) and not line.lstrip().startswith("#")]
    assert not bare, f"{rel} lines {bare}: use libs.ops.atomic_replace.replace_with_retry"
    assert "replace_with_retry" in src


def test_the_docket_writer_survives_a_reader_holding_the_docket(tmp_path: Path,
                                                                monkeypatch) -> None:
    """The 10-27 failure, replayed: the first replaces are refused, the docket still ships."""
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import merge_hypotheses as mh
    calls = _refuse(3, monkeypatch)
    monkeypatch.setattr(ar.time, "sleep", lambda s: None)
    target = tmp_path / "external_survivors.json"
    target.write_text("[]", "utf-8")
    mh._write_docket_atomically(target, [{"sym": "EURUSD", "family": "carry", "params": {}}])
    assert calls["n"] == 4
    assert json.loads(target.read_text("utf-8"))[0]["family"] == "carry"
    assert [p.name for p in tmp_path.iterdir()] == ["external_survivors.json"]
