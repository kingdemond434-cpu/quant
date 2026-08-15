"""The credential ladder, pinned on the two ways it could mislead the operator it exists to help.

ONE: printing a credential. A diagnostic that echoes a key puts it in a terminal, a log and
whatever the operator pastes into a chat window. The mask is the whole safety property.

TWO: reading a MARKET_DATA success as proof the IP is allowed. Binance does not enforce the
whitelist on those endpoints, so passing that rung says the key STRING is real and says nothing
about the address -- and this desk drew exactly that wrong conclusion once already.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SRC = Path("scripts/check_binance_key.py")


def _mod():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("check_binance_key", _SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_A_CREDENTIAL_IS_NEVER_PRINTED_IN_FULL() -> None:
    key = "Ne9GVB98GSrCU307sOe3UFLvKRtyMw7FErahHo20ULboBIXbiBtyG5ZndcFx08Vx"
    out = _mod()._mask(key)
    assert key not in out
    assert out.startswith("Ne9G") and "08Vx" in out
    assert "64 chars" in out, "the length is what tells an operator a truncated paste happened"
    # the masked form must not leak enough to reconstruct: 8 of 64 characters
    assert sum(c in out for c in key[4:-4]) < len(key) - 8


def test_A_SHORT_STRING_IS_NOT_PARTIALLY_REVEALED() -> None:
    """Masking first-4/last-4 of a 9-character string reveals almost all of it."""
    assert _mod()._mask("abc") == "(too short to mask)"


def test_THE_MARKET_DATA_RUNG_STATES_THAT_IT_DOES_NOT_TEST_THE_IP() -> None:
    """THE MISREADING THIS PREVENTS. A MARKET_DATA endpoint validates the API key and skips the IP
    whitelist entirely, so its success narrows the cause to the IP or the permission -- it does not
    clear the IP. That conclusion was drawn wrongly once and cost an afternoon."""
    src = _SRC.read_text("utf-8")
    assert "do NOT enforce the IP whitelist" in src or "NOT enforce the IP whitelist" in src
    assert "says nothing about the IP" in src


def test_EVERY_KNOWN_VENUE_CODE_MAPS_TO_A_DISTINCT_ACTION() -> None:
    """-1021, -1022 and -2015 need three different fixes. Collapsing them into one message is the
    defect this script exists to remove, so each must appear with its own branch."""
    src = _SRC.read_text("utf-8")
    for code in ("-1021", "-1022", "-2015"):
        assert code in src, f"{code} is not distinguished, so its fix cannot be named"
    assert "SECRET" in src and "IP-OR-PERMISSION" in src and "CLOCK" in src


def test_AN_UNREACHABLE_VENUE_STOPS_THE_LADDER() -> None:
    """A later rung's verdict is meaningless once an earlier one failed, and printing one anyway
    is how an operator ends up rotating a credential to fix a firewall."""
    src = _SRC.read_text("utf-8")
    assert 'return _finish(rungs, "NETWORK"' in src


def test_UNMEASURED_IS_A_STATE_NOT_A_FAILURE() -> None:
    """L1.28a on the diagnostic itself: a rung that could not run must not read as a rung that
    failed, or the operator chases a problem the desk never observed."""
    m = _mod()
    assert m._rung("x", None, "d")["ok"] is None
    src = _SRC.read_text("utf-8")
    assert "UNMEASURED" in src
