"""Strip credential-shaped strings out of anything a miner is about to write to disk.

Scraped pages and LLM answers carry other people's leaked keys, and the intelligence
producers wrote them verbatim into tracked artifacts (a Google API key sat in
daily_alpha_frontier.json, external_frontier.json and gpt_practitioner_corpus.jsonl on a
public repository). Every producer of a tracked intelligence artifact passes its payload
through `scrub` before writing.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED_KEY]"

# Shapes only: these are vendor key formats, never values. Patterns are built by
# concatenation so this module never matches the repository-wide key scan itself.
_PATTERNS = (
    "AI" + "za[0-9A-Za-z_-]{35}",                 # Google API key
    "gh[pousr]_" + "[0-9A-Za-z]{36,}",             # GitHub token
    "github_pat_" + "[0-9A-Za-z_]{40,}",           # GitHub fine-grained token
    "sk-or-v1-" + "[0-9a-f]{40,}",                 # OpenRouter key
)
KEY_RE = re.compile("|".join(f"(?:{p})" for p in _PATTERNS))


def scrub_text(text: str) -> str:
    """Return `text` with every credential-shaped run replaced by REDACTED."""
    return KEY_RE.sub(REDACTED, text)


def scrub(value: Any) -> Any:
    """Recursively scrub strings (and string keys) inside dicts, lists and tuples."""
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {scrub(k) if isinstance(k, str) else k: scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(scrub(v) for v in value)
    return value
