"""SHA256 of a file's bytes with CRLF folded to LF. The desk's ONE parity digest.

WHY A FILE AND NOT A ONE-LINER. `check_desk_code_parity` used to hash locally with Python and
remotely with PowerShell's `Get-FileHash` -- two implementations that had to agree about encoding
and newlines, were never tested against each other, and did not agree. Replacing the remote half
with an inline `python -c` only moved the problem: the script crosses ssh, cmd.exe and PowerShell,
each with its own quoting, and `b'\r\n'` does not survive that trip -- it arrives as a literal
carriage return inside a string literal and the remote python dies on a SyntaxError that looks
nothing like a parity result.

So the algorithm lives in a file, in the repo, and BOTH boxes run this same file. It reaches the
trading box the way all code does -- push, then adopt -- which means it is also covered by the
signature and the gates, unlike a string assembled at call time.

    python scripts/fold_hash.py <path> [<path> ...]

One line of output per argument, positional: the hex digest, or MISSING. Positional matters --
skipping an absent file would shift every later verdict onto the wrong path, which is a worse
failure than the blank batch this replaced.

WHY FOLDING IS NOT A LOOSENING. CPython folds universal newlines in the tokenizer before the
parser sees them, so two files differing only in line terminators compile to the same code object
and place the same orders. The fold collapses CR-LF to LF and nothing else: any added, removed or
altered character still changes the digest. It removes exactly the one difference the two
checkouts are configured to create -- this box's git normalises line endings and the other's does
not -- and no difference an attacker or a bad sync could introduce.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def fold_hash(raw: bytes) -> str:
    """The digest. Fold CR-LF to LF, then SHA256."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main(argv: list[str]) -> int:
    for arg in argv:
        path = Path(arg)
        try:
            print(fold_hash(path.read_bytes()))
        except OSError:
            print("MISSING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
