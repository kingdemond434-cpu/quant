"""`polite_fetch.redact_text` blanks a key in a URL PATH and any registered secret, not only a
`name=value` pair (audit HOLD on 4ac92d8316): it is what fetch_alfred and the hunters print."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data import polite_fetch as pf  # noqa: E402

SECRET = "S3CRETKEYVALUE0123456789"


def test_redact_text_blanks_path_keys_and_registered_secrets() -> None:
    other = "TEXTSECRETVALUE77"
    pf.register_secret(other)
    try:
        line = (f"HTTP 403 on https://a.test/v1/key/{SECRET}/x and /APIKEY/{SECRET} "
                f"token {other} api_key={SECRET}")
        out = pf.redact_text(line)
        assert SECRET not in out and other not in out and "REDACTED" in out
    finally:
        pf._REGISTERED_SECRETS.discard(other)
    assert pf.redact_text("see /keyboard/layout") == "see /keyboard/layout"
