#!/usr/bin/env python3
"""Stamp `data/.desk_host.json` -- this box owns the desk's runtime state.

Run by the research cycle, ONCE per run, before any organ reads the cohort. It is deliberately a
separate entry point rather than a library call on first read: a marker written by whoever asks
the question answers "did someone ask?" instead of "did a desk run here?", which is the exact
substitution GAP 111 and GAP 113 were made of.

Idempotent and safe to run every cycle -- it re-stamps the time, which is the only thing that
should change.
"""
from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

from libs.ops.desk_host import MARKER, stamp


def main() -> None:
    when = stamp()
    print(f"desk-host: stamped {MARKER} at {when}")
    print("  absent artifacts on THIS box are now readable as measured zeros; on any other host "
          "they stay UNKNOWN, which floors the Holm cohort at the cap rather than loosening it")


if __name__ == "__main__":
    main()
