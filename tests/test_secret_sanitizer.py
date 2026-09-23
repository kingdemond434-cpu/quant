"""The word "moat" killed the daily external audit for six days, and nothing said so.

MEASURED 2026-08-28. `run_micro_audit` refused to send on 08-23, 08-24, 08-25, 08-26 and 08-27 --
every run in the journal -- with the identical line "micro-audit brief failed sanitization --
refusing to send" and no indication anywhere of what tripped it. The cause was the prefixed-token
pattern `(?:sk|pk|oat|api|key|tok|ghp|xox|AKIA)[-_][A-Za-z0-9-]{16,}` matching UNANCHORED, so it
fired inside ordinary hyphenated words:

    m|oat-tape-decontamination-and-repair-window     <- "moat", the desk's own metaphor
    ri|sk-adjusted-return-over-the-window            <- "risk", on a quant desk
    mon|key-patched-resolver-under-test              <- "monkey"

The comment directly above the pattern already promised that hyphen-segmented ledger ids "stay
readable"; the pattern did the opposite. A fail-closed control is right, and one nobody can
diagnose is a scheduled organ that is dead while looking careful.

THIS FILE IS THE POSITIVE CONTROL. Anchoring a secret pattern narrows what it matches, so the
burden is to show every real key shape the desk handles is still redacted. A gate whose
rejections are observed but whose acceptances never are has not been validated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.generate_external_review_doc import (  # noqa: E402
    sanitize,
    sanitize_findings,
)

#: Real credential SHAPES (never real credentials). Each must survive anchoring.
REAL_KEY_SHAPES = [
    ("anthropic", "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"),
    ("openai", "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"),
    ("github-pat", "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123"),
    ("slack-bot", "xoxb-1234567890-1234567890-AbCdEfGhIjKlMnOpQrSt"),
    ("openrouter", "sk-or-v1-0123456789abcdef0123456789abcdef"),
    ("generic-api", "api_key_AbCdEfGhIjKlMnOpQrStUvWx"),
    ("aws-access-key-id", "AKIAIOSFODNN7EXAMPLE"),
]

#: Desk vocabulary that must NOT be redacted. Every one of these was a live false positive or is
#: one hyphen away from being one.
DESK_PROSE = [
    "2026-08-13-moat-tape-decontamination-and-repair-window",
    "the risk-adjusted-return-over-the-full-sample was negative",
    "monkey-patched-the-resolver-in-the-fixture",
    "2026-07-12-first-inversion-cap-nav-scaling-adopted",
    "session_range_breakout-asia-rr-2.0-wait-bars-12",
]


@pytest.mark.parametrize("name,secret", REAL_KEY_SHAPES, ids=[n for n, _ in REAL_KEY_SHAPES])
def test_a_real_key_shape_is_still_redacted(name: str, secret: str) -> None:
    """Anchoring must not cost one true positive."""
    for context in (secret, f"token={secret}", f'"{secret}"', f"use {secret} here",
                    f"Authorization: Bearer {secret}"):
        out = sanitize(context)
        assert secret not in out, f"{name} survived sanitization in context {context!r}"
        assert "[redacted]" in out


@pytest.mark.parametrize("prose", DESK_PROSE)
def test_desk_vocabulary_is_not_mistaken_for_a_credential(prose: str) -> None:
    """The bug: 'moat', 'risk' and 'monkey' each contain a token prefix mid-word."""
    assert sanitize(prose) == prose, (
        "ordinary hyphenated desk text was redacted, which is what silently stopped the daily "
        "external audit for six days")


def test_the_live_micro_audit_brief_now_passes() -> None:
    """The end-to-end reproduction: build the real brief and sanitize it."""
    try:
        from scripts.run_micro_audit import build_brief
    except Exception as exc:                                     # pragma: no cover
        pytest.skip(f"micro-audit unavailable in this tree: {exc!r}")
    brief = build_brief()
    assert sanitize(brief) == brief, (
        f"the brief still trips a control: {sanitize_findings(brief)}")


def test_a_refusal_names_the_control_and_never_the_match() -> None:
    """A five-day identical refusal with no cause is not a control, it is a silence."""
    secret = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    findings = sanitize_findings(f"header\n{secret}\nfooter")

    assert findings, "a text that fails sanitization must produce at least one finding"
    joined = " ".join(findings)
    assert "prefixed-token" in joined, "the finding must name WHICH control fired"
    assert "char" in joined, "and where, so a false positive can be located"
    assert secret not in joined, "printing the match would be the leak the control prevents"
    assert secret[:12] not in joined


def test_clean_text_produces_no_findings() -> None:
    assert sanitize_findings("a perfectly ordinary sentence about the moat tape") == []


def test_the_ip_rail_still_holds() -> None:
    """The VPS IP must never reach an external lab -- unchanged by this work, pinned anyway."""
    assert "95.216.191.70" not in sanitize("the box is at 95.216.191.70 in Helsinki")
