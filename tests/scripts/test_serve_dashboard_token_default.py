"""The dashboard server demands its token from loopback too, unless the exemption is named.

A tunnel delivers every public request to its origin as 127.0.0.1, so a server that trusts
loopback by default publishes equity to whoever holds the tunnel hostname. The safe shape is the
default; --trust-loopback and --no-auth are the only ways out and both have to be spelled.
"""
from __future__ import annotations

from types import SimpleNamespace

import scripts.serve_dashboard as sd


def _req(require_token: bool, *, client: str = "127.0.0.1", path: str = "/desk.html",
         headers: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(token="tok-fixture", require_token=require_token,
                           client_address=(client, 1234), path=path, headers=headers or {})


def test_the_class_default_requires_the_token_from_loopback() -> None:
    assert sd._Handler.require_token is True
    assert not sd._Handler._authorised(_req(sd._Handler.require_token))


def test_the_token_still_opens_it() -> None:
    assert sd._Handler._authorised(_req(True, path="/desk.html?k=tok-fixture"))
    assert sd._Handler._authorised(_req(True, headers={"Authorization": "Bearer tok-fixture"}))
    assert not sd._Handler._authorised(_req(True, path="/desk.html?k=wrong"))


def test_only_a_named_exemption_trusts_loopback() -> None:
    assert sd._Handler._authorised(_req(False))
    assert not sd._Handler._authorised(_req(False, client="203.0.113.9"))


def test_the_banner_says_which_gate_is_on() -> None:
    assert "every request" in sd._auth_banner(False, True)
    assert "--trust-loopback" in sd._auth_banner(False, False)
    assert "DISABLED" in sd._auth_banner(True, False)
