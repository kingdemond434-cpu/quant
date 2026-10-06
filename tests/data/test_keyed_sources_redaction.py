"""keyed_sources: no credential leaves in an error, a stored body or a redirect (re-audit of
#201, 2026-10-06)."""

from __future__ import annotations

import io
import json
import urllib.request
from email.message import Message

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
    assert "ab" not in out.split("api_key=")[-1][:2] or "<redacted>" in out
    assert all(KEY[:i] not in out.split("?")[-1] for i in range(4, len(KEY)))


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
