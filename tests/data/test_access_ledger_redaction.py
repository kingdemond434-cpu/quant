"""A credential never reaches the shared access ledger (audit HOLD on 4ac92d8316).

A 401/403 hold stores the refused URL in `world_crawler_access.json`. A key riding in the query
(`?api_key=`) or in the path (BPS's `/key/<key>/`) must be blanked before that row is written, on
every route that writes one: `get()`, `_post()` and `refuse_status()`.
"""
from __future__ import annotations

import io
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data import polite_fetch as pf  # noqa: E402

SECRET = "S3CRETKEYVALUE0123456789"
_ALLOW = b"User-agent: *\nDisallow:\n"


class _Resp(io.BytesIO):
    def __init__(self, body: bytes) -> None:
        super().__init__(body)
        self.status = 200
        self.url = ""
        self.headers = {"Content-Type": "text/plain"}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def _web(status: int) -> Any:
    def opener(req: Any, timeout: float, context: Any = None) -> _Resp:
        if req.full_url.endswith("/robots.txt"):
            return _Resp(_ALLOW)
        raise urllib.error.HTTPError(req.full_url, status, "x", Message(), io.BytesIO(b""))
    return opener


URLS = [f"https://a.test/v1/key/{SECRET}/data",
        f"https://a.test/v1/data?api_key={SECRET}&q=1",
        f"https://a.test/v1/APIKEY/{SECRET}"]


def test_redact_url_blanks_path_and_query_keys() -> None:
    for u in URLS:
        out = pf.redact_url(u)
        assert SECRET not in out and "REDACTED" in out, out
    assert pf.redact_url("https://a.test/v1/keyboard/data") == "https://a.test/v1/keyboard/data"


def test_a_registered_secret_is_blanked_in_any_path_segment() -> None:
    other = "ZZ9PLURALZALPHA42"
    pf.register_secret(other)
    try:
        assert other not in pf.redact_url(f"https://b.test/{other}/series.json")
        assert other not in pf.redact_url(f"https://b.test/s?k={other}")
    finally:
        pf._REGISTERED_SECRETS.discard(other)
    pf.register_secret("short")
    assert pf.redact_url("https://b.test/short/x") == "https://b.test/short/x"


@pytest.mark.parametrize("url", URLS)
@pytest.mark.parametrize("status", [401, 403])
def test_get_never_writes_the_key_into_the_ledger(tmp_path: Path, url: str, status: int) -> None:
    state = tmp_path / "world_crawler_access.json"
    acc = pf.HostAccess.load(state)
    r = pf.get(url, opener=_web(status), gate=None, sleep=lambda s: None, access=acc)
    assert not r.ok and r.verdict
    text = state.read_text("utf-8")
    assert "a.test" in text and SECRET not in text


@pytest.mark.parametrize("url", URLS)
def test_post_never_writes_the_key_into_the_ledger(tmp_path: Path, url: str) -> None:
    state = tmp_path / "world_crawler_access.json"
    acc = pf.HostAccess.load(state)
    with pytest.raises(pf.FetchRefused) as exc:
        pf._post(url, b"{}", opener=_web(403), access=acc)
    assert SECRET not in str(exc.value) and SECRET not in exc.value.url
    text = state.read_text("utf-8")
    assert "a.test" in text and SECRET not in text


def test_refuse_status_and_a_direct_block_never_store_the_key(tmp_path: Path) -> None:
    state = tmp_path / "world_crawler_access.json"
    acc = pf.HostAccess.load(state)
    pf.refuse_status(URLS[0], 403, access=acc)
    acc.block(URLS[1].replace("a.test", "c.test"), 401)   # a caller that forgot to redact
    text = state.read_text("utf-8")
    assert "c.test" in text and SECRET not in text
