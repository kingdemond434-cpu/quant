"""Boot r22: the packets-only inbox (coordinator 2026-11-27 12:44Z; zuck 12:33Z "Yes"). A folder
the box's own user can write, carrying AUTHOR packets only -- never a verdict, a boot packet, an
announcement or a manifest with a seat's line -- so builds reach the forge with no owner paste
while every approval keeps its admin-only path."""
from __future__ import annotations

from pathlib import Path

from ops.box_git import drop_pull as D


def _mk(root: Path, rel: str, data: bytes = b"x") -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_bytes(data)


def test_author_packets_are_staged_into_the_checkout_root(tmp_path) -> None:
    box, co = tmp_path / "packets", tmp_path / "co"
    co.mkdir()
    _mk(box, "fix-1_abc.bundle", b"PACK")
    _mk(box, "fix-1_abc.json", b'{"branch": "claude/fix-1", "head": "' + b"a" * 40 + b'"}')
    rows = D.stage_packets(box, co)
    assert (co / "fix-1_abc.bundle").read_bytes() == b"PACK" and (co / "fix-1_abc.json").is_file()
    assert rows[0].startswith("packets staged fix-1_abc.bundle")  # bundle before manifest


def test_verdicts_boot_packets_and_announcements_are_never_read(tmp_path) -> None:
    box, co = tmp_path / "packets", tmp_path / "co"
    co.mkdir()
    _mk(box, "verdicts/fix-1_abc.json", b'{"line": "AUDIT CLEAR ' + b"a" * 40 + b' merge"}')
    _mk(box, "forge_reboot/boot-r99-abc.bundle")
    _mk(box, "forge_reboot/boot-r99-abc.verdict.json")
    _mk(box, "announced/" + "a" * 40 + ".txt", b"cmsg_x")
    assert D.stage_packets(box, co) == []
    assert not any(co.rglob("*"))


def test_a_manifest_carrying_a_seat_line_is_refused(tmp_path) -> None:
    box, co = tmp_path / "packets", tmp_path / "co"
    co.mkdir()
    for i, line in enumerate((b"AUDIT CLEAR", b"AUDIT HOLD", b"AUTHORIZE TRUST", b"OWNER APPROVE",
                              b"silence_approved")):
        _mk(box, f"p{i}_abc.json", b'{"comments": ["' + line + b' x"]}')
    rows = D.stage_packets(box, co)
    assert len(rows) == 5 and all("refused" in r for r in rows)
    assert not any(co.iterdir())


def test_a_name_drop_local_holds_is_never_replaced_from_the_packets_inbox(tmp_path) -> None:
    box, co, local = tmp_path / "packets", tmp_path / "co", tmp_path / "local"
    co.mkdir()
    _mk(local, "fix-1_abc.bundle", b"ADMIN")
    _mk(box, "fix-1_abc.bundle", b"OTHER")
    rows = D.stage_packets(box, co, keep=local)
    assert rows == ["packets skipped fix-1_abc.bundle: drop_local holds that name"]
    assert not (co / "fix-1_abc.bundle").exists()


def test_symlinks_oversize_and_foreign_names_are_ignored(tmp_path) -> None:
    box, co = tmp_path / "packets", tmp_path / "co"
    co.mkdir()
    _mk(box, "notes.txt")
    _mk(box, "big_abc.json", b"x" * (D.MAX_JSON + 1))
    _mk(tmp_path, "outside_abc.json", b"{}")
    (box / "link_abc.json").symlink_to(tmp_path / "outside_abc.json")
    rows = D.stage_packets(box, co)
    assert rows == [f"packets refused big_abc.json: {D.MAX_JSON + 1} bytes over the "
                    f"{D.MAX_JSON} cap"]


def test_pull_stages_packets_after_drop_local(tmp_path) -> None:
    src = (Path(__file__).resolve().parents[2] / "ops" / "box_git" / "drop_pull.py").read_text(
        encoding="utf-8")
    i, j = src.index("stage_local(local, drop.checkout)"), src.index(
        "stage_packets(packets, drop.checkout, keep=local)")
    assert i < j
    assert D.PACKETS_LOCAL == Path(r"C:\opt\bridge\quant\packets_inbox")
