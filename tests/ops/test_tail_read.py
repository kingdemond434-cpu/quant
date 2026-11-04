"""`tail_lines` returns what `readlines()[-n:]` returned, reading only the file's end."""
from __future__ import annotations

import io
import random
from pathlib import Path

import pytest

from libs.ops.tail_read import tail_lines


def test_tail_lines_matches_readlines_on_every_shape(tmp_path: Path) -> None:
    rng = random.Random(7)
    f = tmp_path / "ledger.jsonl"
    for _ in range(150):
        rows = ["x" * rng.randint(0, 30) + "é" * rng.randint(0, 2)
                for _ in range(rng.randint(0, 50))]
        f.write_bytes(("\n".join(rows) + ("\n" if rng.random() < 0.7 else "")).encode())
        for n in (0, 1, 2, 7, 40, 100):
            for block in (1, 5, 64, 1 << 20):
                with f.open(encoding="utf-8", errors="replace", newline="") as fh:
                    want = fh.readlines()[-n:] if n else []
                assert tail_lines(f, n, block=block) == want


def test_tail_lines_reads_only_the_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "big.jsonl"
    f.write_bytes(b'{"family":"a"}\n' * 200_000)
    reads: list[int] = []

    class Spy(io.BufferedReader):
        def read(self, size: int | None = -1) -> bytes:
            data = super().read(size)
            reads.append(len(data))
            return data

    import libs.ops.tail_read as tr
    monkeypatch.setattr(tr, "open", lambda p, mode="rb": Spy(io.FileIO(p, "r")), raising=False)
    assert len(tail_lines(f, 10, block=4096)) == 10
    assert sum(reads) <= 4096 < f.stat().st_size


def test_a_missing_file_raises_oserror_like_the_open_it_replaces(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        tail_lines(tmp_path / "absent.jsonl", 5)


def test_judged_by_family_counts_the_tail_only(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5"))
    from research.merge_hypotheses import judged_by_family
    f = tmp_path / "gate.jsonl"
    f.write_text('{"family":"old"}\n' * 5 + '{"family":"new"}\n' * 3 + "not json\n", "utf-8")
    assert judged_by_family(f, tail=4) == {"new": 3}
    assert judged_by_family(tmp_path / "absent.jsonl") == {}
