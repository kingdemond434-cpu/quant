"""ONE ACCOUNT KEY, ONE SOURCE (auditor key-join ruling, 2026-10-21).

`libs.ops.provenance.account_key` is the only function that hashes an account. Every caller on
this base must answer the SAME key for one account however its login is spelt (int, digit
string, integral float) and whether or not its server is padded: the gold OCO
(`gold_oco.oco_account_key` and the venue readers), the existing two-account fence
(`cross_account.account_key`), the FTMO follower's bound key and the prop-fills-ledger rows its
adapter writes. The reference is the bracket guard v5 evidence lane's own call,
`provenance.account_key(int(login), server, create=False)`.

Fake logins only.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops import provenance  # noqa: E402
from mt5desk import cross_account as xa  # noqa: E402
from mt5desk import gold_oco as oco  # noqa: E402
from prop import ftmo_follower as ff  # noqa: E402

LOGIN, SERVER = 64567890, "FTMO-Server2"                 # fake
SPELLINGS = [LOGIN, str(LOGIN), float(LOGIN), f" {LOGIN} "]
SERVERS = [SERVER, f" {SERVER} "]

# The REAL identity readers (conftest wraps them with a fake-login fallback for venue stubs).
_REAL_TL = oco.tradelocker_oco_key
_REAL_MT5 = oco.mt5_oco_key


def _reference() -> str:
    ref = provenance.account_key(int(LOGIN), SERVER, create=False)
    assert ref is not None and xa.valid_key(ref)
    return ref


@pytest.mark.parametrize("server", SERVERS)
@pytest.mark.parametrize("login", SPELLINGS)
def test_provenance_itself(login: object, server: str) -> None:
    """publish_sync v5c's internal normalisation is on this base (v2r restack onto v5d): a str
    login, an integral float, a padded digit string and a padded server all key as the evidence
    lane's int login does. STRICT -- no xfail remains on the key path."""
    assert provenance.account_key(login, server, create=False) == _reference()


@pytest.mark.parametrize("server", SERVERS)
@pytest.mark.parametrize("login", SPELLINGS)
def test_the_oco_key_and_the_fence_key(login: object, server: str) -> None:
    ref = _reference()
    assert oco.oco_account_key(login, server) == ref
    assert xa.account_key(login, server) == ref


@pytest.mark.parametrize("server", SERVERS)
@pytest.mark.parametrize("login", SPELLINGS)
def test_the_venue_readers(login: object, server: str) -> None:
    ref = _reference()
    term = SimpleNamespace(account_info=lambda: SimpleNamespace(login=login, server=server))
    assert _REAL_MT5(term) == ref
    venue = SimpleNamespace(_raw_api=SimpleNamespace(acc_id=login, server=None,
                                                     _credentials={"server": server}),
                            _creds=None)
    # The E8 path is bracket guard v5.1's evidence rule EXACTLY: the TLAPI login as the SDK holds
    # it, handed to provenance (which normalises it, v5c) -- so every spelling is the reference.
    assert _REAL_TL(venue) == provenance.account_key(login, server.strip(), create=False) == ref


@pytest.mark.parametrize("server", SERVERS)
@pytest.mark.parametrize("login", SPELLINGS)
def test_the_ftmo_follower_and_its_prop_ledger_rows(login: object, server: str,
                                                    monkeypatch, tmp_path) -> None:
    ref = _reference()
    acct = tmp_path / "FTMO_LIVE_ACCOUNT.json"
    acct.write_text(json.dumps({"login": str(LOGIN), "server": SERVER, "trade_mode": 0,
                                "initial_balance": 100_000.0, "account_type": "2-step"}),
                    "utf-8")
    monkeypatch.setattr(ff, "ACCOUNT_FILE", acct)
    monkeypatch.setattr(ff, "PROP_LEDGER", tmp_path / "live_ledger_prop.jsonl")
    tick = 1_792_000_000
    deals = (SimpleNamespace(order=11, position_id=11, symbol="XAUUSD", magic=ff.MAGIC, entry=0,
                             type=0, volume=0.1, price=4000.0, time=tick, profit=0.0),
             SimpleNamespace(order=12, position_id=11, symbol="XAUUSD", magic=ff.MAGIC, entry=1,
                             type=1, volume=0.1, price=4010.0, time=tick + 60, profit=100.0,
                             reason=5))
    orders = (SimpleNamespace(ticket=11, sl=3990.0, tp=4010.0, price_open=4000.0),)
    mt5 = SimpleNamespace(
        account_info=lambda: SimpleNamespace(login=login, server=server, trade_mode=0),
        history_deals_get=lambda a, b: deals, history_orders_get=lambda a, b: orders,
        symbol_info=lambda s: SimpleNamespace(trade_contract_size=100.0))
    key, _decl, why = ff.bound_account(mt5)
    assert key == ref, why
    now = datetime.fromtimestamp(tick, tz=UTC) + timedelta(hours=1)
    assert ff.record_fills(mt5, key, set(), now)["written"] == 1
    (row,) = [json.loads(ln) for ln in (tmp_path / "live_ledger_prop.jsonl").read_text(
        "utf-8").splitlines()]
    assert row["account_key"] == ref and row["book"] == "ftmo"
    assert str(LOGIN) not in json.dumps(row)


def test_an_unresolvable_or_non_joining_key_never_reads_as_an_empty_book(tmp_path) -> None:
    """A lane state whose key does not join the box's declared key for that account is not
    "that account holds nothing": the OCO gate fails closed."""
    day = "2026-10-21"
    e8 = oco.oco_account_key(81234567, "E8-Live-Test")
    xa.E8_ACCOUNT_FILE.write_text(json.dumps({"account_key": e8}), "utf-8")
    oco.MODE_FILE.write_text(json.dumps({"lanes": ["e8", "fusion"], "modes": {"fusion": "oco"}}))
    fu = oco.oco_account_key(72345678, "FusionMarkets-Test")
    oco.publish_lane("fusion", fu, positions=[], orders=[], date=day)
    oco.publish_lane("e8", e8, positions=[], orders=[], date=day)
    assert oco.gate("fusion", "buy_stop", key=fu, date=day).allowed
    # E8's state under ANOTHER key (r5's plain pin, a second box key, a mis-spelt login).
    oco.publish_lane("e8", oco.oco_account_key(81234567, "tradelocker"), positions=[],
                     orders=[], date=day)
    v = oco.gate("fusion", "buy_stop", key=fu, date=day)
    assert not v.allowed and "does not join" in v.why
    # This lane's own key not joining its declaration refuses too.
    oco.publish_lane("e8", e8, positions=[], orders=[], date=day)
    assert not oco.gate("e8", "buy_stop", key=fu, date=day).allowed


def _evidence_key(api: object) -> str | None:
    """bracket guard v5.1's `prop/e8_evidence.account_key_status`, restated (e8_evidence is not
    on this base): login = TLAPI `account_id`, else `acc_id` (never `acc_num`); server =
    `api._credentials["server"]` stripped (never `api.server`, never the venue Credentials,
    never a default); key = provenance.account_key(login, server, create=False).

    TODO (bracket v5 lands): replace this restatement with `prop.e8_evidence` itself, so the
    test pins the evidence lane's own code rather than a copy of its rule."""
    login = None
    for attr in ("account_id", "acc_id"):
        v = getattr(api, attr, None)
        if v is None or isinstance(v, bool) or str(v).strip() in ("", "0"):
            continue
        login = v
        break
    creds = getattr(api, "_credentials", None)
    server = creds.get("server") if isinstance(creds, dict) else None
    if login is None or not isinstance(server, str) or not server.strip():
        return None
    return provenance.account_key(login, server.strip(), create=False)


def test_the_e8_oco_key_equals_the_bracket_guard_evidence_key_for_one_tlapi_object() -> None:
    """One fake TLAPI handle, decoys on every attribute the evidence lane refuses to read."""
    api = SimpleNamespace(account_id=81234567, acc_id=99999999, acc_num=1,
                          server="decoy-api-server",
                          _credentials={"username": "u", "password": "p",
                                        "server": " E8-Live-Test "})
    venue = SimpleNamespace(_raw_api=api, _creds=SimpleNamespace(server="decoy-creds-server",
                                                                 username="u"))
    ev = _evidence_key(api)
    assert ev is not None and xa.valid_key(ev)
    assert _REAL_TL(venue) == ev == xa.tradelocker_account_key(venue)
    assert ev == oco.oco_account_key(81234567, "E8-Live-Test")
    # acc_id only (no account_id): still the evidence rule.
    api2 = SimpleNamespace(acc_id=81234567, acc_num=2, _credentials={"server": "E8-Live-Test"})
    assert _REAL_TL(SimpleNamespace(_raw_api=api2)) == _evidence_key(api2) == ev
    # acc_num alone names nothing; no _credentials server fails closed (no default).
    with pytest.raises(oco.IdentityUnavailable):
        _REAL_TL(SimpleNamespace(_raw_api=SimpleNamespace(acc_num=1, _credentials={
            "server": "E8-Live-Test"})))
    with pytest.raises(oco.IdentityUnavailable, match="server"):
        _REAL_TL(SimpleNamespace(_raw_api=SimpleNamespace(account_id=81234567,
                                                          server="E8-Live-Test"),
                                 _creds=SimpleNamespace(server="E8-Live-Test")))


#: FIXED TEST VECTORS (the suite's throwaway key, b"0123456789abcdef" * 4, conftest
#: `_account_key_file`): "sha256:" + HMAC-SHA256(key, "<login>@<server>")[:16] with the server
#: passed as given -- case preserved, never lowercased. Bracket guard v5.1's e8_evidence key for
#: the same TLAPI handle is this value byte for byte (its rule is restated in `_evidence_key`).
VECTOR_E8 = ("sha256:ccd25414061507fe", 81234567, "E8-Live-Test")
VECTOR_FTMO = ("sha256:9e6e987a65c2762b", 64567890, "FTMO-Server2")


def test_the_keys_match_the_fixed_vectors_byte_for_byte(monkeypatch, tmp_path) -> None:
    want, login, server = VECTOR_E8
    api = SimpleNamespace(account_id=login, _credentials={"server": server})
    assert _evidence_key(api) == want
    assert _REAL_TL(SimpleNamespace(_raw_api=api)) == want
    assert oco.oco_account_key(login, server) == want
    assert xa.account_key(login, server) == want
    # The server's case is the account's: a case-folded server is another key, never this one.
    assert oco.oco_account_key(login, server.lower()) != want
    want, login, server = VECTOR_FTMO
    assert oco.oco_account_key(login, server) == want
    term = SimpleNamespace(account_info=lambda: SimpleNamespace(login=login, server=server,
                                                                trade_mode=0))
    acct = tmp_path / "FTMO_LIVE_ACCOUNT.json"
    acct.write_text(json.dumps({"login": login, "server": server, "trade_mode": 0,
                                "initial_balance": 100_000.0, "account_type": "2-step"}),
                    "utf-8")
    monkeypatch.setattr(ff, "ACCOUNT_FILE", acct)
    assert ff.bound_account(term)[0] == want                 # the follower and its ledger rows
