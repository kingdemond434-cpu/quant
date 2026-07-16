"""Concatenate EVERY Python module (libs + scripts + tests) into ONE file -> web/algo_complete.txt.

The entire platform in a single readable, shareable, downloadable artifact -- a table of contents
up top, then every file in full with a header. Excludes venv / data / secrets / caches. This is the
"give me all 300 files in one thing" bundle.

    python scripts/bundle_all.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

_ROOTS = ["libs", "scripts", "tests"]
_OUT = Path("web/algo_complete.txt")
_SKIP_PARTS = {"__pycache__", ".venv", ".git", "node_modules", ".mypy_cache", ".ruff_cache"}


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    files: list[Path] = []
    for r in _ROOTS:
        base = root / r
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if any(part in _SKIP_PARTS for part in p.parts):
                continue
            files.append(p)

    rels = [p.relative_to(root).as_posix() for p in files]
    header = [
        f"QUANT PLATFORM -- COMPLETE SOURCE BUNDLE ({len(files)} files)",
        f"Consolidated {datetime.now(tz=UTC).isoformat()} from C:/Users/dell/quant-platform",
        "Every Python module (libs + scripts + tests) in one file. Search '# FILE:' to jump.",
        "", "=" * 100, "TABLE OF CONTENTS", "=" * 100,
    ]
    header += [f"  {i + 1:3}. {rel}" for i, rel in enumerate(rels)]
    header += [""]

    parts = list(header)
    total_lines = 0
    for p, rel in zip(files, rels, strict=True):
        body = p.read_text("utf-8", errors="replace")
        total_lines += body.count("\n")
        parts += ["", "=" * 100, f"# FILE: {rel}", "=" * 100, "", body]

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(parts), "utf-8")
    size_kb = _OUT.stat().st_size / 1024
    print(f"bundled {len(files)} files (~{total_lines} lines, {size_kb:.0f} KB) -> {_OUT}")


if __name__ == "__main__":
    main()
