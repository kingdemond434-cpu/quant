"""ops/box_git/drop_pull.py: the box pulls packets from the drop with no Claude session."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ops.box_git import drop_pull


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def _drop_repo(tmp: Path, files: dict[str, bytes]) -> Path:
    src = tmp / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    for rel, data in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(data)
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "drop")
    return src


def _drop(tmp: Path, src: Path) -> drop_pull.Drop:
    return drop_pull.Drop(url=src.resolve().as_uri(), key=tmp / "keys" / "drop_ed25519",
                          checkout=tmp / "checkout")


def test_wanted_only_packet_paths():
    assert drop_pull.wanted("q-x.bundle") == drop_pull.MAX_BUNDLE
    assert drop_pull.wanted("q-x.json") == drop_pull.MAX_JSON
    assert drop_pull.wanted("verdicts/q-x.json") == drop_pull.MAX_JSON
    for bad in ("README.md", "verdicts/q-x.bundle", "a/b/c.json", ".hidden.json",
                "x/q.json", "verdicts/../q.json", "run.ps1"):
        assert drop_pull.wanted(bad) is None, bad


def test_order_bundles_then_manifests_then_verdicts():
    rels = ["verdicts/a.json", "a.json", "a.bundle"]
    assert sorted(rels, key=drop_pull.order) == ["a.bundle", "a.json", "verdicts/a.json"]


def test_pull_delivers_once_and_redelivers_on_change(tmp_path):
    (tmp_path / "keys").mkdir()
    src = _drop_repo(tmp_path, {"q-a.bundle": b"B1", "q-a.json": b"{}",
                                "verdicts/q-a.json": b'{"v":1}', "notes.txt": b"x"})
    drop, inbox, state = _drop(tmp_path, src), tmp_path / "inbox", tmp_path / "state"
    state.mkdir()
    out = drop_pull.pull(drop, inbox, state)
    assert "delivered q-a.bundle" in out and "delivered verdicts/q-a.json" in out
    assert (inbox / "q-a.bundle").read_bytes() == b"B1"
    assert not (inbox / "notes.txt").exists()
    assert drop.known_hosts().read_text(encoding="utf-8").strip() == drop_pull.GITLAB_HOST_KEY
    # the inbox consumed the packet (moved to done/): nothing is delivered again
    (inbox / "q-a.bundle").unlink()
    assert drop_pull.pull(drop, inbox, state).endswith("nothing new")
    assert not (inbox / "q-a.bundle").exists()
    # a new head for the same packet id is delivered again
    (src / "q-a.bundle").write_bytes(b"B2")
    _git(src, "commit", "-q", "-am", "new head")
    out = drop_pull.pull(drop, inbox, state)
    assert "delivered q-a.bundle" in out and "q-a.json" not in out
    assert (inbox / "q-a.bundle").read_bytes() == b"B2"
    ledger = json.loads((state / drop_pull.LEDGER).read_text(encoding="utf-8"))
    assert set(ledger) == {"q-a.bundle", "q-a.json", "verdicts/q-a.json"}


def test_failed_fetch_leaves_inbox_unchanged(tmp_path):
    (tmp_path / "keys").mkdir()
    drop = drop_pull.Drop(url=(tmp_path / "missing").as_uri(), key=tmp_path / "keys" / "k",
                          checkout=tmp_path / "checkout")
    out = drop_pull.pull(drop, tmp_path / "inbox", tmp_path)
    assert out.startswith("drop not pulled") and not (tmp_path / "inbox").exists()


def test_oversize_file_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(drop_pull, "MAX_JSON", 4)
    (tmp_path / "keys").mkdir()
    src = _drop_repo(tmp_path, {"q-a.json": b"0123456789"})
    out = drop_pull.pull(_drop(tmp_path, src), tmp_path / "inbox", tmp_path)
    assert "refused q-a.json" in out and not (tmp_path / "inbox" / "q-a.json").exists()


def test_ssh_command_pins_host_key(tmp_path):
    d = drop_pull.Drop(url="git@gitlab.com:o/quant-drop.git", key=tmp_path / "k",
                       checkout=tmp_path / "c")
    cmd = d.ssh()
    assert "StrictHostKeyChecking=yes" in cmd and "BatchMode=yes" in cmd
    assert "IdentitiesOnly=yes" in cmd and "drop_known_hosts" in cmd
