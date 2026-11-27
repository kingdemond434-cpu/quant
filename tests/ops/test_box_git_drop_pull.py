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
    out = drop_pull.pull(drop, inbox, state, local=None)
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


def test_wanted_local_adds_only_boot_packets_under_forge_reboot():
    b = "forge_reboot/boot-r12-baa818189"
    for ok in (f"{b}.bundle", f"{b}.bundle.sha256", f"{b}.verdict.json", "q-a.bundle",
               "verdicts/q-a.json"):
        assert drop_pull.wanted_local(ok) is not None, ok
    for bad in ("forge_reboot/auto_boot_move.ps1", "forge_reboot/announced/x.txt",
                "forge_reboot/install_auto_boot_move.ps1", "forge_reboot/boot-..x.bundle",
                "forge_reboot/x/boot-a.bundle", "run.ps1"):
        assert drop_pull.wanted_local(bad) is None, bad


def test_local_drop_is_staged_into_the_checkout_and_delivered(tmp_path):
    (tmp_path / "keys").mkdir()
    src = _drop_repo(tmp_path, {"q-g.json": b"{}"})
    drop, inbox, state = _drop(tmp_path, src), tmp_path / "inbox", tmp_path / "state"
    state.mkdir()
    local = tmp_path / "local"
    (local / "verdicts").mkdir(parents=True)
    (local / "forge_reboot").mkdir()
    (local / "q-l.bundle").write_bytes(b"L1")
    (local / "verdicts" / "q-l.json").write_bytes(b'{"v":1}')
    (local / "forge_reboot" / "boot-r9-abc.bundle").write_bytes(b"BB")
    (local / "forge_reboot" / "auto_boot_move.ps1").write_bytes(b"never")
    (local / "notes.txt").write_bytes(b"x")
    out = drop_pull.pull(drop, inbox, state, local=local)
    assert "local staged forge_reboot/boot-r9-abc.bundle" in out
    assert (drop.checkout / "forge_reboot" / "boot-r9-abc.bundle").read_bytes() == b"BB"
    assert not (drop.checkout / "forge_reboot" / "auto_boot_move.ps1").exists()
    assert not (drop.checkout / "notes.txt").exists()
    assert (inbox / "q-l.bundle").read_bytes() == b"L1"        # through the normal deliver()
    assert (inbox / "q-g.json").exists()                       # the GitLab drop still works
    assert not (inbox / "forge_reboot").exists()               # boot packets are the mover's
    # a second pass with nothing changed stages and delivers nothing
    assert drop_pull.pull(drop, inbox, state, local=local).endswith("nothing new")


def test_local_drop_works_when_the_gitlab_fetch_fails(tmp_path):
    (tmp_path / "keys").mkdir()
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    drop = drop_pull.Drop(url=(tmp_path / "missing").as_uri(), key=tmp_path / "keys" / "k",
                          checkout=checkout)
    local = tmp_path / "local"
    local.mkdir()
    (local / "q-l.json").write_bytes(b"{}")
    out = drop_pull.pull(drop, tmp_path / "inbox", tmp_path, local=local)
    assert out.startswith("drop not pulled") and "local drop only" in out
    assert (tmp_path / "inbox" / "q-l.json").exists()


def test_local_symlink_and_oversize_are_never_staged(tmp_path, monkeypatch):
    monkeypatch.setattr(drop_pull, "MAX_JSON", 4)
    local, checkout = tmp_path / "local", tmp_path / "checkout"
    local.mkdir()
    checkout.mkdir()
    (local / "q-big.json").write_bytes(b"0123456789")
    (tmp_path / "secret.json").write_bytes(b"{}")
    (local / "q-link.json").symlink_to(tmp_path / "secret.json")
    rows = drop_pull.stage_local(local, checkout)
    assert any(r.startswith("local refused q-big.json") for r in rows)
    assert not (checkout / "q-big.json").exists() and not (checkout / "q-link.json").exists()
