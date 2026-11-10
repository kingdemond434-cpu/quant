"""The last N lines of a file, read from its end. Memory bounded by the tail, never the file.

`fh.readlines()[-n:]` and `read_text().splitlines()[-n:]` hold the WHOLE file to keep its end.
Measured 2026-11-04 18:21Z on the trading box: merge_hypotheses held 13.7 GB of commit keeping
the last 200,000 rows of a ~1.4M-row gate ledger, the box's commit went past its limit, and about
one Fusion gateway pass in four died at numpy import with "paging file is too small".

`tail_lines(path, n)` returns exactly what `path.open(...).readlines()[-n:]` returned for a
newline-delimited file, each line with its trailing "\n" (the last one without it when the file
has no final newline), decoded with `errors`. Lines split on b"\n" only; a "\r\n" ending is kept
as text, which every caller strips (a text-mode read would also have split on a lone "\r", which
JSON Lines never carries raw). An OSError propagates, exactly as the open it replaces.
"""
from __future__ import annotations

import os
from pathlib import Path

BLOCK = 1 << 20


def tail_lines(path: Path | str, n: int, *, encoding: str = "utf-8",
               errors: str = "replace", block: int = BLOCK) -> list[str]:
    if n <= 0:
        return []
    with open(path, "rb") as fh:
        end = fh.seek(0, os.SEEK_END)
        pos, chunks, newlines = end, [], 0
        # n lines need n newlines before them, plus the file's own final one when present.
        while pos > 0 and newlines <= n:
            step = min(block, pos)
            pos -= step
            fh.seek(pos)
            chunk = fh.read(step)
            chunks.append(chunk)
            newlines += chunk.count(b"\n")
    data = b"".join(reversed(chunks))
    lines = _split(data)
    if pos > 0:
        lines = lines[1:]                      # the first is a fragment of an earlier line
    return [ln.decode(encoding, errors) for ln in lines[-n:]]


def _split(data: bytes) -> list[bytes]:
    parts = data.split(b"\n")
    out = [p + b"\n" for p in parts[:-1]]
    if parts[-1]:
        out.append(parts[-1])
    return out
