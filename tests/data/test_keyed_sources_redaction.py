"""keyed_sources: no credential leaves in an error, a stored body or a redirect (re-audit of
#201, 2026-10-06)."""

from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request
from email.message import Message

import pytest

from libs.data import keyed_sources as ks

KEY = "ab+cd/ef==gh-0123456789"


def test_redact_scrubs_raw_and_encoded_forms() -> None:
    text = (f"raw {KEY} plus {urllib.parse.quote_plus(KEY)} "
            f"path {urllib.parse.quote(KEY, safe='')} {urllib.parse.quote(KEY)}")
    out = ks.redact(text, [KEY])
    assert "ab+cd" not in out and "ab%2Bcd" not in out and "ab%2Bcd%2F" not in out
    assert out.count("<redacted>") == 4


def test_redact_before_truncate_on_a_long_url() -> None:
    url = "https://api.eia.gov/v2/" + "p/" * 30 + "data/?" + urllib.parse.urlencode(
        {"api_key": KEY})
    out = ks.redact(f"URLError: {url}", [KEY])[:90]
    tail = out.split("api_key=")[-1]
    assert not tail.startswith(KEY[:4]) and not tail.startswith("ab%2B")


def test_eia_echo_is_stripped_from_the_body() -> None:
    body = json.dumps({"response": {"data": [{"period": "2026-09-26", "value": 1.0}]},
                       "request": {"command": "/v2/x/data/",
                                   "params": {"api_key": KEY, "frequency": "weekly"}}}).encode()
    out = ks.scrub_body(body, [KEY])
    doc = json.loads(out)
    assert "api_key" not in doc["request"]["params"]
    assert doc["response"]["data"][0]["value"] == 1.0
    assert KEY.encode() not in out


def test_scrub_body_catches_an_echo_anywhere_and_leaves_clean_bodies_alone() -> None:
    assert ks.scrub_body(f"<p>key={KEY}</p>".encode(), [KEY]) == b"<p>key=<redacted></p>"
    clean = b'{"response":{"data":[]}}'
    assert ks.scrub_body(clean, [KEY]) is clean


def _redirect(src: str, dst: str, headers: dict[str, str]) -> urllib.request.Request:
    req = urllib.request.Request(src, headers=headers)
    msg = Message()
    msg["Location"] = dst
    new = ks.SameHostAuthRedirect(["Bmx-Token"]).redirect_request(
        req, io.BytesIO(), 302, "Found", msg, dst)
    assert new is not None
    return new


def test_credentials_never_follow_a_cross_host_redirect() -> None:
    new = _redirect("https://www.banxico.org.mx/x", "https://cdn.elsewhere.net/x",
                    {"Bmx-Token": KEY, "Authorization": f"Bearer {KEY}", "Accept": "*/*"})
    names = {h.lower() for h in new.headers}
    assert "bmx-token" not in names and "authorization" not in names
    assert "accept" in names


def test_credentials_stay_on_a_same_host_redirect_but_not_on_a_downgrade() -> None:
    same = _redirect("https://api.darwinex.com/a", "https://api.darwinex.com/b",
                     {"Authorization": f"Bearer {KEY}"})
    assert "Authorization" in same.headers
    down = _redirect("https://api.darwinex.com/a", "http://api.darwinex.com/b",
                     {"Authorization": f"Bearer {KEY}"})
    assert "Authorization" not in down.headers


def test_lowercase_percent_escapes_are_scrubbed() -> None:
    echoed = urllib.parse.quote_plus(KEY).replace("%2B", "%2b").replace("%2F", "%2f")
    assert "ab%2bcd" not in ks.redact(f"Location: https://x/?k={echoed}", [KEY])


def test_a_gzip_body_is_scrubbed_inside() -> None:
    import gzip
    raw = gzip.compress(json.dumps({"request": {"params": {"api_key": KEY}}}).encode())
    out = ks.scrub_body(raw, [KEY])
    assert KEY.encode() not in gzip.decompress(out)
    clean = gzip.compress(b'{"response":{}}')
    assert ks.scrub_body(clean, [KEY]) is clean


def test_a_query_key_never_follows_a_cross_host_redirect() -> None:
    src = "https://api.eia.gov/v2/x/?" + urllib.parse.urlencode({"api_key": KEY, "f": "w"})
    dst = "https://mirror.elsewhere.net/x/?" + urllib.parse.urlencode(
        {"api_key": KEY, "page": "2"})
    req = urllib.request.Request(src)
    msg = Message()
    msg["Location"] = dst
    new = ks.SameHostAuthRedirect((), [KEY]).redirect_request(
        req, io.BytesIO(), 302, "Found", msg, dst)
    assert new is not None
    assert "api_key" not in new.full_url and "page=2" in new.full_url
    assert urllib.parse.quote_plus(KEY) not in new.full_url


def test_a_same_host_redirect_keeps_its_query() -> None:
    src = "https://api.eia.gov/v2/x/?api_key=k1"
    dst = "https://api.eia.gov/v2/y/?api_key=k1"
    req = urllib.request.Request(src)
    msg = Message()
    msg["Location"] = dst
    new = ks.SameHostAuthRedirect((), ["k1"]).redirect_request(
        req, io.BytesIO(), 302, "Found", msg, dst)
    assert new is not None and new.full_url == dst


def test_a_truncated_gzip_body_is_scrubbed_on_what_decodes() -> None:
    import gzip
    raw = gzip.compress((f"key={KEY} " * 50).encode())
    out = ks.scrub_body(raw[: len(raw) // 2], [KEY])
    assert KEY.encode() not in gzip.decompress(out)


def test_deflate_bodies_are_scrubbed() -> None:
    import zlib
    for packed, enc in ((zlib.compress(f"k={KEY}".encode()), ""),
                        (zlib.compress(f"k={KEY}".encode())[2:-4], "deflate")):
        out = ks.scrub_body(packed, [KEY], enc)
        try:
            plain = zlib.decompress(out)
        except zlib.error:
            plain = zlib.decompress(out, -15)
        assert KEY.encode() not in plain


def test_inflation_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    import gzip
    monkeypatch.setattr(ks, "MAX_INFLATE", 1024)
    out = ks.scrub_body(gzip.compress(b"a" * 100_000 + KEY.encode()), [KEY])
    assert len(gzip.decompress(out)) <= 1024


def _follow(src: str, dst: str, secrets: list[str]) -> urllib.request.Request | None:
    req = urllib.request.Request(src)
    msg = Message()
    msg["Location"] = dst
    return ks.SameHostAuthRedirect((), secrets).redirect_request(
        req, io.BytesIO(), 302, "Found", msg, dst)


def test_a_key_in_a_redirect_path_or_nested_value_is_refused() -> None:
    src = "https://api.eia.gov/v2/x/?" + urllib.parse.urlencode({"api_key": KEY})
    assert _follow(src, f"https://evil.example/{urllib.parse.quote(KEY, safe='')}/x", []) is None
    nested = "https://evil.example/?" + urllib.parse.urlencode(
        {"next": "/x?" + urllib.parse.urlencode({"api_key": KEY})})
    assert _follow(src, nested, []) is None
    assert _follow("https://api.darwinex.com/a", f"https://evil.example/?t={KEY}", [KEY]) is None


def test_every_gzip_member_and_trailing_bytes_are_scrubbed() -> None:
    import gzip
    raw = gzip.compress(b'{"ok":1}') + gzip.compress(f'{{"echo":"{KEY}"}}'.encode())
    out = ks.scrub_body(raw, [KEY])
    assert KEY.encode() not in gzip.decompress(out)
    trailing = gzip.compress(b'{"ok":1}') + f"tail {KEY}".encode()
    out = ks.scrub_body(trailing, [KEY])
    assert KEY.encode() not in out and KEY.encode() not in gzip.decompress(out)
