"""Package the repository into a distributable ZIP (excludes venv/caches/db artifacts).

Usage: python scripts/make_archive.py [--out dist/quant-platform.zip]
Includes source, configs, tests, reports, requirements, MT5 integration, and dashboard code.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

_EXCLUDE_DIRS = {
    ".venv", ".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".hypothesis", "dist", "node_modules", ".idea", ".vscode",
}
_EXCLUDE_EXT = {".pyc", ".pyo", ".pyd"}
_EXCLUDE_SUFFIX = (".sqlite", ".sqlite-wal", ".sqlite-shm")
_EXCLUDE_NAMES = {".coverage"}


def _included(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in _EXCLUDE_DIRS for part in rel_parts):
        return False
    if path.suffix in _EXCLUDE_EXT or path.name in _EXCLUDE_NAMES:
        return False
    return not any(path.name.endswith(s) for s in _EXCLUDE_SUFFIX)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dist/quant-platform.zip")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    out = (root / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    n_files = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_dir() or path == out or not _included(path, root):
                continue
            zf.write(path, path.relative_to(root).as_posix())
            n_files += 1

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"wrote {out}")
    print(f"files: {n_files}, size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
