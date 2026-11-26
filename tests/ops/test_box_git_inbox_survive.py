"""One bad file never stops the inbox or the drop delivery (2026-11-26 outage: 279 inbox copies
with a foreign ACL aborted every import pass). Failures are simulated by monkeypatching, so the
tests run the same on Linux CI and the box."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import drop_pull  # noqa: E402
from ops.box_git import inbox as I  # noqa: E402


def _two_packets(box: Path) -> None:
    box.mkdir()
    for n in ("a", "b"):
        (box / f"{n}.bundle").write_bytes(b"x")
        (box / f"{n}.json").write_text("{}")


def test_an_unmovable_packet_is_stuck_and_the_next_one_still_files(tmp_path, monkeypatch):
    box = tmp_path / "inbox"
    _two_packets(box)
    monkeypatch.setattr(I, "import_one", lambda b, m, **k: (False, "unreadable packet"))
    real = I._file_away

    def file_away(bundle: Path, *a: Any) -> None:
        if bundle.name == "a.bundle":
            raise PermissionError(13, "Access is denied")
        real(bundle, *a)

    monkeypatch.setattr(I, "_file_away", file_away)
    rows = I.drain(box, git=lambda *a, **k: (0, ""), api=lambda *a: None)
    assert rows[0].startswith("STUCK a.bundle") and rows[1].startswith("REFUSED b.bundle")
    assert (box / "refused" / "b.bundle").is_file() and (box / "a.bundle").is_file()
    stuck = json.loads((box / I.STUCK).read_text())["stuck"]
    assert [s["packet"] for s in stuck] == ["a.bundle"] and "PermissionError" in stuck[0][
        "file_away"]


def test_a_clean_pass_clears_the_stuck_list(tmp_path, monkeypatch):
    box = tmp_path / "inbox"
    _two_packets(box)
    (box / I.STUCK).write_text(json.dumps({"stuck": [{"packet": "old"}]}))
    monkeypatch.setattr(I, "import_one", lambda b, m, **k: (True, "ok"))
    I.drain(box, git=lambda *a, **k: (0, ""), api=lambda *a: None)
    assert json.loads((box / I.STUCK).read_text()) == {"stuck": []}


def _checkout(tmp: Path) -> Path:
    co = tmp / "drop"
    co.mkdir()
    (co / "p1.bundle").write_bytes(b"B1")
    (co / "p1.json").write_text("{}")
    (co / "p2.bundle").write_bytes(b"B2")
    (co / "p2.json").write_text("{}")
    return co


def test_an_unwritable_inbox_file_is_stuck_not_fatal_and_not_marked_seen(tmp_path, monkeypatch):
    co, box, ledger = _checkout(tmp_path), tmp_path / "inbox", tmp_path / "ledger.json"
    real = drop_pull.os.replace

    def replace(src: Any, dst: Any) -> None:
        if Path(dst).name == "p1.bundle":
            raise PermissionError(13, "Access is denied")
        real(src, dst)

    monkeypatch.setattr(drop_pull.os, "replace", replace)
    rows = drop_pull.deliver(co, box, ledger)
    assert any(r.startswith("stuck p1.bundle: PermissionError") for r in rows)
    assert (box / "p2.bundle").read_bytes() == b"B2"
    seen = json.loads(ledger.read_text())
    assert "p1.bundle" not in seen and "p2.bundle" in seen
    monkeypatch.setattr(drop_pull.os, "replace", real)
    rows = drop_pull.deliver(co, box, ledger)
    assert rows == [f"delivered p1.bundle {drop_pull.sha256(co / 'p1.bundle')[:12]}"]


def test_a_seen_but_unreadable_inbox_copy_is_delivered_again(tmp_path, monkeypatch):
    co, box, ledger = _checkout(tmp_path), tmp_path / "inbox", tmp_path / "ledger.json"
    drop_pull.deliver(co, box, ledger)
    assert drop_pull.deliver(co, box, ledger) == []
    monkeypatch.setattr(drop_pull, "_readable_or_gone", lambda p: p.name != "p1.json")
    rows = drop_pull.deliver(co, box, ledger)
    assert [r.split()[1] for r in rows] == ["p1.json"]


def test_a_filed_away_copy_is_not_delivered_again(tmp_path):
    co, box, ledger = _checkout(tmp_path), tmp_path / "inbox", tmp_path / "ledger.json"
    drop_pull.deliver(co, box, ledger)
    (box / "p1.bundle").unlink()
    assert drop_pull.deliver(co, box, ledger) == []
    assert drop_pull._readable_or_gone(box / "p2.bundle")


def test_the_gate_fetches_a_missing_boot_from_the_loop_source(tmp_path):
    """2026-11-26: boot 4acce0d9d was in loop-src but not in the forge repo, so every gate failed
    on "invalid reference". ensure_boot heals it with an objects-only fetch."""
    import subprocess

    from ops.box_git import box_loop as L

    def g(cwd: Path, *a: str) -> str:
        return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                              text=True).stdout.strip()

    src = tmp_path / "loop-src"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    g(src, "config", "user.email", "t@x")
    g(src, "config", "user.name", "t")
    (src / "a").write_text("a")
    g(src, "add", "a")
    g(src, "commit", "-q", "-m", "live")
    live = g(src, "rev-parse", "HEAD")
    bare = tmp_path / "forge.git"
    g(tmp_path, "clone", "-q", "--bare", str(src), str(bare))
    (src / "b").write_text("b")
    g(src, "add", "b")
    g(src, "commit", "-q", "-m", "boot")
    g(src, "checkout", "-q", "--detach")
    g(src, "branch", "-q", "-D", "main")       # the boot is reachable only from HEAD, as on the box
    boot = g(src, "rev-parse", "HEAD")
    refs = g(bare, "for-each-ref")
    cfg = L.Config(forge_url="https://127.0.0.1:443", bare=bare, work=tmp_path / "w",
                   tokens=tmp_path / "t", ca=tmp_path / "ca", state=tmp_path / "s", boot=boot)
    assert L.ensure_boot(cfg, src).startswith("fetched")
    assert L.ensure_boot(cfg, src) == "present"
    assert g(bare, "for-each-ref") == refs      # objects only: no forge ref created or moved
    assert L.gate_code(cfg, live) == boot
    nowhere = L.Config(**{**cfg.__dict__, "boot": "0" * 40})
    assert "MISSING" in L.ensure_boot(nowhere, src)
