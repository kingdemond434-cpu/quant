"""ops/release/auditor_sync.py: the box's copy of the Auditor's registry is only ever a valid,
append-only extension of the old copy, and a refusal leaves the old copy to age."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("auditor_sync", ROOT / "ops/release/auditor_sync.py")
assert _spec is not None and _spec.loader is not None
sy = importlib.util.module_from_spec(_spec)
sys.modules["auditor_sync"] = sy
_spec.loader.exec_module(sy)
H1, H2 = "1" * 40, "2" * 40


def _row(**kw: Any) -> str:
    row = {"pr": 41, "sha": H1, "verdict": "CLEAR", "at": "2026-11-10T16:00:00+00:00", **kw}
    return json.dumps(row)


def _text(*rows: str) -> str:
    return "".join(r + "\n" for r in rows)


def test_a_valid_registry_is_written_and_stamped_even_when_unchanged(tmp_path: Path) -> None:
    out = tmp_path / "box" / "rows.jsonl"
    assert "1 new" in sy.sync(_text(_row()), out, owner_registry="")
    assert out.read_text(encoding="utf-8") == _text(_row())
    os.utime(out, (1_000_000, 1_000_000))
    assert "0 new" in sy.sync(_text(_row()), out, owner_registry="")
    assert out.stat().st_mtime > 1_000_000  # the stamp is this run, which is what fresh means
    assert "1 new" in sy.sync(_text(_row(), _row(verdict="HOLD")), out, owner_registry="")


@pytest.mark.parametrize("bad", [
    "not json",
    "[1, 2]",
    _row(pr="41"),
    _row(pr=True),
    _row(pr=0),
    _row(sha="abc"),
    _row(sha=H1.upper().replace("1", "A")),
    _row(verdict="PASS"),
    _row(at="yesterday"),
    _row(at="2026-11-10T16:00:00"),
    _row(by="someone"),
    json.dumps({"pr": 41, "sha": H1, "verdict": "CLEAR"}),
])  # fmt: skip
def test_one_bad_line_refuses_the_whole_registry_and_keeps_the_old_copy(
    tmp_path: Path, bad: str
) -> None:
    out = tmp_path / "rows.jsonl"
    sy.sync(_text(_row()), out, owner_registry="")
    os.utime(out, (1_000_000, 1_000_000))
    with pytest.raises(sy.Refused):
        sy.sync(_text(_row(), bad), out, owner_registry="")
    assert out.read_text(encoding="utf-8") == _text(_row())
    assert out.stat().st_mtime == 1_000_000  # not re-stamped: it ages and the gate waits


def test_a_rewritten_history_is_refused_because_a_vanished_row_could_be_a_hold(
    tmp_path: Path,
) -> None:
    out = tmp_path / "rows.jsonl"
    held = _text(_row(), _row(verdict="HOLD"))
    sy.sync(held, out, owner_registry="")
    for rewritten in (_text(_row()), _text(_row(verdict="HOLD"), _row()), _text(_row(sha=H2)), ""):
        with pytest.raises(sy.Refused):
            sy.sync(rewritten, out, owner_registry="")
    assert out.read_text(encoding="utf-8") == held


def test_the_owners_registry_is_never_written(tmp_path: Path, monkeypatch: Any) -> None:
    owner = tmp_path / "registry.jsonl"
    owner.write_text("", encoding="utf-8")
    with pytest.raises(sy.Refused):
        sy.sync(_text(_row()), owner, owner_registry=str(owner))
    monkeypatch.setenv(sy.OWNER_REGISTRY_ENV, str(owner))
    with pytest.raises(sy.Refused):
        sy.sync(_text(_row()), owner)
    assert owner.read_text(encoding="utf-8") == ""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", "-c", f"core.hooksPath={os.devnull}", *args],
                   check=True, capture_output=True)  # fmt: skip


def test_main_copies_the_ref_from_origin_and_refuses_a_missing_one(
    tmp_path: Path, capsys: Any
) -> None:
    origin, box = tmp_path / "origin", tmp_path / "box"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "audit-registry")
    (origin / sy.FILE).write_text(_text(_row()), encoding="utf-8")
    _git(origin, "add", sy.FILE)
    _git(origin, "commit", "-q", "-m", "rows")
    subprocess.run(["git", "clone", "-q", str(origin), str(box)], check=True, capture_output=True)
    # the adopter's pre-fetched FETCH_HEAD and the checkout itself must not move (Auditor, #818)
    _git(box, "fetch", "-q", "origin", "audit-registry")
    fetch_head = (box / ".git" / "FETCH_HEAD").read_bytes()
    before = subprocess.run(["git", "-C", str(box), "rev-parse", "HEAD"], check=True,
                            capture_output=True).stdout  # fmt: skip
    (origin / sy.FILE).write_text(_text(_row(), _row(verdict="HOLD")), encoding="utf-8")
    _git(origin, "commit", "-q", "-am", "a hold")
    out = tmp_path / "rows.jsonl"
    assert sy.main(["--repo-dir", str(box), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == _text(_row(), _row(verdict="HOLD"))
    assert (box / ".git" / "FETCH_HEAD").read_bytes() == fetch_head
    after = subprocess.run(["git", "-C", str(box), "rev-parse", "HEAD"], check=True,
                           capture_output=True).stdout  # fmt: skip
    status = subprocess.run(["git", "-C", str(box), "status", "--porcelain"], check=True,
                            capture_output=True).stdout  # fmt: skip
    assert after == before and status == b""
    assert sy.main(["--repo-dir", str(box), "--out", str(out), "--ref", "refs/heads/nope"]) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == _text(_row(), _row(verdict="HOLD"))


def test_the_copy_it_writes_is_one_the_gate_accepts(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "audit_gate_for_sync", ROOT / ".github/scripts/audit_gate.py"
    )
    assert spec is not None and spec.loader is not None
    ag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ag)
    out = tmp_path / "rows.jsonl"
    sy.sync(_text(_row()), out, owner_registry="")
    rows, why = ag.registry_rows(str(out))
    assert why == "" and rows == [json.loads(_row())]


def test_the_fetch_never_writes_fetch_head() -> None:
    src = (ROOT / "ops/release/auditor_sync.py").read_text(encoding="utf-8")
    assert '"--no-write-fetch-head"' in src and '"FETCH_HEAD:' not in src
    assert sy.LOCAL_REF.startswith("refs/auditor-sync/")
