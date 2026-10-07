"""Strip credential-shaped strings out of anything a miner is about to write to disk.

Scraped pages and LLM answers carry other people's leaked keys, and the intelligence
producers wrote them verbatim into tracked artifacts (a Google API key sat in
daily_alpha_frontier.json, external_frontier.json and gpt_practitioner_corpus.jsonl on a
public repository). Every producer of a tracked intelligence artifact passes its payload
through `scrub` (or writes through `write_json` / `write_text` / `append_jsonl` here, or a
helper that calls them) before writing, and the commit boundary scrubs again:

    python -m libs.ops.secret_scrub --staged          # pre-commit: staged intelligence blobs
    python -m libs.ops.secret_scrub --tree DIR ...    # before a push script stages DIR

WHAT COUNTS AS A KEY. Vendor shapes only (Google, GitHub, OpenRouter in either case, OpenAI
`sk-`, Anthropic `sk-ant-`, AWS `AKIA`, Slack `xox?-`), each ANCHORED so it never fires inside
an ordinary hyphenated word (tests/test_secret_sanitizer.py: "risk-adjusted" and "moat-tape"
killed an audit for six days under an unanchored pattern). The generic `sk-` shapes also need
a digit, which every random key of that length carries and English prose does not.

WHAT COUNTS AS HIDING ONE. A key split by whitespace or zero-width characters, %-encoded,
\\u/\\x-escaped, or base64-encoded is still a key: each run is decoded, checked, and the WHOLE
encoded run is replaced, so the output carries neither the key nor an encoding of it.

Pattern literals are built by concatenation so this module never matches the repository-wide
key scan (tests/governance/test_no_google_api_key_in_repo.py) itself.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import unquote

REDACTED = "[REDACTED_KEY]"

_B = "(?<![A-Za-z0-9])"  # anchor: a key starts a token, never the middle of a word
_PATTERNS = (
    "AI" + "za[0-9A-Za-z_-]{35}",                                  # Google API key
    "gh" + "[pousr]_[0-9A-Za-z]{36,}",                             # GitHub token
    "github" + "_pat_[0-9A-Za-z_]{40,}",                           # GitHub fine-grained token
    "(?i:s" + "k-or-v1-)[0-9a-fA-F]{40,}",                         # OpenRouter, any case
    "s" + "k-ant-(?=[A-Za-z0-9_-]*[0-9])[A-Za-z0-9_-]{20,}",       # Anthropic
    "s" + "k-(?=[A-Za-z0-9_-]*[0-9])[A-Za-z0-9_-]{20,}",           # OpenAI style, generic
    "AK" + "IA[0-9A-Z]{16}(?![0-9A-Z])",                           # AWS access key id
    "xo" + "x[baprs]-[0-9A-Za-z-]{10,}",                           # Slack token
)
# One anchor outside the alternation: eight times faster than one per branch (10 MB: 1.3s->0.16s).
KEY_RE = re.compile(_B + "(?:" + "|".join(f"(?:{p})" for p in _PATTERNS) + ")")

#: Zero-width space / non-joiner / joiner and the BOM: invisible, so they split a key silently.
_ZERO_WIDTH = "​‌‍﻿"
_ZW_RE = re.compile(f"[{_ZERO_WIDTH}]")
#: Separators a key may be split by: whitespace and the zero-width characters.
_SEP = re.compile(rf"[\s{_ZERO_WIDTH}]")
_PCT_RUN = re.compile(r"(?:[A-Za-z0-9_.~+-]|%[0-9A-Fa-f]{2})*%[0-9A-Fa-f]{2}"
                      r"(?:[A-Za-z0-9_.~+-]|%[0-9A-Fa-f]{2})*")
_ESC_RUN = re.compile(r"(?:[A-Za-z0-9_-]|\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2})*"
                      r"(?:\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2})"
                      r"(?:[A-Za-z0-9_-]|\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2})*")
_ESC_ONE = re.compile(r"\\u([0-9A-Fa-f]{4})|\\x([0-9A-Fa-f]{2})")
_B64_RUN = re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}")
_MAX_DEPTH = 3

#: Trees whose files the commit boundary scrubs (both intelligence roots).
INTEL_PREFIXES = ("data/intelligence/", "desks/mt5/data/intelligence/")
_TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".md", ".csv", ".tsv", ".yaml", ".yml", ".html",
                  ".xml", ".log", ".ndjson"}


def _strip_zero_width(text: str) -> str:
    return _ZW_RE.sub("", text)


def _unescape(run: str) -> str:
    return _ESC_ONE.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)), run)


def _b64_decode(run: str) -> str | None:
    body = run.rstrip("=")
    for alt in (None, b"-_"):
        try:
            raw = base64.b64decode(body + "=" * (-len(body) % 4), altchars=alt, validate=True)
        except (binascii.Error, ValueError):
            continue
        text = raw.decode("utf-8", errors="ignore")
        if text:
            return text
    return None


def _split_matches(text: str) -> list[tuple[int, int]]:
    """Spans of `text` that form a key once whitespace / zero-width separators are removed."""
    if not _SEP.search(text) or not KEY_RE.search(_SEP.sub("", text)):
        return []  # the common case stays in C: no key even after joining
    kept: list[int] = []
    chars: list[str] = []
    for i, ch in enumerate(text):
        if not _SEP.match(ch):
            kept.append(i)
            chars.append(ch)
    joined = "".join(chars)
    spans: list[tuple[int, int]] = []
    for m in KEY_RE.finditer(joined):
        tok = m.group(0)
        # Joining words can manufacture a shape out of prose; a real key carries a digit.
        if not any(c.isdigit() for c in tok):
            continue
        spans.append((kept[m.start()], kept[m.end() - 1] + 1))
    return spans


def contains_key(text: str, _depth: int = 0) -> bool:
    """True when `text` carries a key, directly or hidden by any encoding scrub_text undoes."""
    if not text:
        return False
    if KEY_RE.search(text) or _split_matches(text):
        return True
    if _ZW_RE.search(text) and KEY_RE.search(_strip_zero_width(text)):
        return True
    if _depth >= _MAX_DEPTH:
        return False
    if "%" in text:
        for m in _PCT_RUN.finditer(text):
            dec = unquote(m.group(0))
            if dec != m.group(0) and contains_key(dec, _depth + 1):
                return True
    if "\\" in text:
        for m in _ESC_RUN.finditer(text):
            if contains_key(_unescape(m.group(0)), _depth + 1):
                return True
    for m in _B64_RUN.finditer(text):
        decoded = _b64_decode(m.group(0))
        if decoded and contains_key(decoded, _depth + 1):
            return True
    return False


def _replace_spans(text: str, spans: Iterable[tuple[int, int]]) -> str:
    merged: list[list[int]] = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out, pos = [], 0
    for a, b in merged:
        out.append(text[pos:a])
        out.append(REDACTED)
        pos = b
    out.append(text[pos:])
    return "".join(out)


def _pct(m: re.Match[str]) -> str:
    run = m.group(0)
    dec = unquote(run)
    return REDACTED if dec != run and contains_key(dec, 1) else run


def _esc(m: re.Match[str]) -> str:
    return REDACTED if contains_key(_unescape(m.group(0)), 1) else m.group(0)


def _b64(m: re.Match[str]) -> str:
    dec = _b64_decode(m.group(0))
    return REDACTED if dec and contains_key(dec, 1) else m.group(0)


def _scrub_once(text: str) -> str:
    text = KEY_RE.sub(REDACTED, text)
    if _SEP.search(text):
        text = _replace_spans(text, _split_matches(text))
    if "%" in text:
        text = _PCT_RUN.sub(_pct, text)
    if "\\" in text:
        text = _ESC_RUN.sub(_esc, text)
    return _B64_RUN.sub(_b64, text)


def scrub_text(text: str) -> str:
    """Return `text` with every credential-shaped run, or encoded run hiding one, redacted."""
    if not text or not contains_key(text):
        return text  # the common case: one read-only pass, nothing rebuilt
    for _ in range(4):
        new = _scrub_once(text)
        if new == text:
            break
        text = new
    if contains_key(text):  # whatever survived every pass is cut wholesale, never published
        text = REDACTED
    return text


def _scrub_exception(exc: BaseException) -> Any:
    args = tuple(scrub(a) for a in exc.args)
    try:
        clone = type(exc)(*args)
    except Exception:
        return scrub_text(str(exc))
    if contains_key(str(clone)):
        return scrub_text(str(exc))
    return clone


def scrub(value: Any) -> Any:
    """Recursively scrub strings, bytes and keys inside containers, dataclasses and exceptions.

    Returns a scrubbed COPY; the input is never mutated."""
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, (bytes, bytearray)):
        text = bytes(value).decode("utf-8", errors="surrogateescape")
        clean = scrub_text(text)
        if clean == text:
            return value
        return type(value)(clean.encode("utf-8", errors="surrogateescape"))
    if isinstance(value, dict):
        return {scrub(k): scrub(v) for k, v in value.items()}
    if isinstance(value, tuple) and hasattr(value, "_fields"):  # namedtuple
        return type(value)(*(scrub(v) for v in value))
    if isinstance(value, (list, tuple, set, frozenset)):
        return type(value)(scrub(v) for v in value)
    if isinstance(value, BaseException):
        return _scrub_exception(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = [f for f in dataclasses.fields(value) if f.init]
        try:
            return dataclasses.replace(
                value, **{f.name: scrub(getattr(value, f.name)) for f in fields})
        except Exception:
            return scrub(dataclasses.asdict(value))
    return value


# ---- scrubbing write helpers: producers write through these -------------------------------

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        try:
            os.replace(tmp, path)
        except PermissionError:  # Windows: a held / read-only destination refuses the rename
            path.write_bytes(data)
    finally:
        Path(tmp).unlink(missing_ok=True)


def write_text(path: Path | str, text: str, encoding: str = "utf-8") -> Path:
    """Scrub `text` and write it atomically to `path`."""
    target = Path(path)
    _atomic_write_bytes(target, scrub_text(text).encode(encoding))
    return target


def write_json(path: Path | str, doc: Any, *, indent: int | None = 1, default: Any = str,
               sort_keys: bool = False, ensure_ascii: bool = False,
               trailing_newline: bool = False) -> Path:
    """Scrub `doc` and write it as JSON atomically to `path`."""
    body = json.dumps(scrub(doc), indent=indent, default=default, sort_keys=sort_keys,
                      ensure_ascii=ensure_ascii)
    # A custom `default` can surface text the walk never saw; write_text scrubs the result.
    return write_text(path, body + ("\n" if trailing_newline else ""))


def append_jsonl(path: Path | str, rows: Iterable[Any], *, default: Any = str,
                 ensure_ascii: bool = False) -> Path:
    """Scrub each row and append it to a JSONL file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for row in rows:
            line = json.dumps(scrub(row), default=default, ensure_ascii=ensure_ascii)
            fh.write(scrub_text(line) + "\n")
    return target


# ---- the commit boundary ------------------------------------------------------------------

def _is_text_artifact(path: str) -> bool:
    return Path(path).suffix.lower() in _TEXT_SUFFIXES


def scrub_file(path: Path | str) -> bool:
    """Rewrite one text file in place if it carries a key. True when it was changed."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError:
        return False
    text = raw.decode("utf-8", errors="surrogateescape")
    if not contains_key(text):
        return False
    # surrogateescape round-trips undecodable bytes, so nothing but the key changes
    _atomic_write_bytes(p, scrub_text(text).encode("utf-8", errors="surrogateescape"))
    return True


def scrub_tree(*roots: Path | str) -> list[Path]:
    """Scrub every text artifact under `roots` in place; the files it changed."""
    changed: list[Path] = []
    for root in roots:
        base = Path(root)
        if base.is_file():
            if scrub_file(base):
                changed.append(base)
            continue
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and _is_text_artifact(p.name) and scrub_file(p):
                changed.append(p)
    return changed


def _git(*args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], input=input_bytes, capture_output=True,
                          check=True).stdout


def scrub_staged(prefixes: tuple[str, ...] = INTEL_PREFIXES) -> list[str]:
    """Scrub the STAGED blobs of intelligence paths (pre-commit). Paths whose blob changed.

    The index entry is rewritten with the scrubbed blob, and the working copy too when it
    carries a key, so neither this commit nor the next `git add` restores the literal."""
    names = _git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split(b"\0")
    paths = [n.decode("utf-8", "surrogateescape") for n in names if n]
    paths = [p for p in paths if p.startswith(prefixes) and _is_text_artifact(p)]
    changed: list[str] = []
    for rel in paths:
        entry = _git("ls-files", "-s", "--", rel).decode("utf-8", "surrogateescape").split()
        if len(entry) < 2:
            continue
        mode, sha = entry[0], entry[1]
        text = _git("cat-file", "blob", sha).decode("utf-8", errors="surrogateescape")
        if not contains_key(text):
            continue
        clean = scrub_text(text).encode("utf-8", errors="surrogateescape")
        new_sha = _git("hash-object", "-w", "--stdin", input_bytes=clean).decode().strip()
        _git("update-index", "--cacheinfo", f"{mode},{new_sha},{rel}")
        scrub_file(rel)
        changed.append(rel)
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Redact credential-shaped strings at the "
                                             "commit boundary.")
    ap.add_argument("--staged", action="store_true",
                    help="scrub staged intelligence blobs (pre-commit hook)")
    ap.add_argument("--tree", nargs="*", default=[],
                    help="scrub every text artifact under these files/directories")
    args = ap.parse_args(argv)
    try:
        if args.staged:
            for rel in scrub_staged():
                print(f"secret_scrub: redacted a key in staged {rel}", file=sys.stderr)
        for p in scrub_tree(*args.tree):
            print(f"secret_scrub: redacted a key in {p}", file=sys.stderr)
    except (OSError, subprocess.CalledProcessError) as exc:
        # Loud, but never a wedge on the box's state pipeline: the producers scrub at write
        # time and the next pass retries the boundary.
        print(f"secret_scrub: boundary scrub could not run: {scrub_text(str(exc))}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
