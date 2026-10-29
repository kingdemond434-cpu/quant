"""Bounded-memory readers for campaign-sized JSON arrays."""

from __future__ import annotations

from pathlib import Path


def count_object_array(path: Path, *, chunk_size: int = 1024 * 1024) -> int | None:
    """Count objects in a top-level JSON array without materialising its rows.

    The reader retains only nesting and string state.  It fails closed on truncated,
    malformed, non-array, or non-object-row input instead of publishing a partial count.
    """
    count = 0
    stack: list[str] = []
    in_string = False
    escaped = False
    started = False
    finished = False
    expect_value = True
    try:
        with path.open(encoding="utf-8") as handle:
            while chunk := handle.read(chunk_size):
                for char in chunk:
                    if finished:
                        if not char.isspace():
                            return None
                        continue
                    if in_string:
                        if escaped:
                            escaped = False
                        elif char == "\\":
                            escaped = True
                        elif char == '"':
                            in_string = False
                        continue
                    if char == '"':
                        if len(stack) == 1 and expect_value:
                            return None
                        in_string = True
                        continue
                    if not started:
                        if char.isspace():
                            continue
                        if char != "[":
                            return None
                        started = True
                        stack.append("[")
                        continue
                    if len(stack) == 1:
                        if char.isspace():
                            continue
                        if char == "]":
                            if expect_value and count:
                                return None
                            stack.pop()
                            finished = True
                            continue
                        if char == ",":
                            if expect_value:
                                return None
                            expect_value = True
                            continue
                        if expect_value:
                            if char != "{":
                                return None
                            count += 1
                            expect_value = False
                    if char in "[{":
                        stack.append(char)
                    elif char in "]}":
                        expected = "[" if char == "]" else "{"
                        if not stack or stack[-1] != expected:
                            return None
                        stack.pop()
        if not started or not finished or in_string or stack:
            return None
        return count
    except (OSError, UnicodeError):
        return None
