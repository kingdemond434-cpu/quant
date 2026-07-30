"""Sub-accounts: automated where permitted, refused where the guard says so, honest when blocked.

The module's whole design is the three-way distinction NO-KEYS / BLOCKED-TIER / AVAILABLE and the
money-path guards on transfer. These tests pin both without ever touching the network: the venue
call is monkeypatched at the single `_signed` seam.
"""

from __future__ import annotations

import json

import pytest

from libs.execution import sub_accounts as SA


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(SA, "STATE", tmp_path / "subaccounts.json")
    monkeypatch.setattr(SA, "LEDGER", tmp_path / "ledger.jsonl")


def _keys(monkeypatch, present=True):
    from libs.execution import binance_live
    monkeypatch.setattr(binance_live, "has_keys", lambda: present)


class TestProbeDistinguishesThreeStates:
    def test_no_keys_is_not_blocked_tier(self, monkeypatch):
        """Different owners, different fixes: NO-KEYS is a launch-day gap (paste keys);
        BLOCKED-TIER is a Binance verification task. Collapsing them hides which one you have."""
        _keys(monkeypatch, present=False)
        cap = SA.probe()
        assert not cap.available
        assert "NO-KEYS" in cap.detail

    def test_venue_refusal_reads_blocked_tier_with_upgrade_path(self, monkeypatch):
        _keys(monkeypatch)
        def refuse(path, params, method="GET"):
            raise RuntimeError("This endpoint is only available for corporate accounts")
        monkeypatch.setattr(SA, "_signed", refuse)
        cap = SA.probe()
        assert not cap.available
        assert "BLOCKED-TIER" in cap.detail and "corporate" in cap.detail

    def test_success_counts_existing_subaccounts(self, monkeypatch):
        _keys(monkeypatch)
        monkeypatch.setattr(SA, "_signed",
                            lambda *a, **k: {"subAccounts": [{"email": "a"}, {"email": "b"}]})
        cap = SA.probe()
        assert cap.available and cap.n_existing == 2
        assert json.loads(SA.STATE.read_text())["available"] is True

    def test_probe_never_raises_on_refusal(self, monkeypatch):
        """'Not permitted' is a RESULT the boards consume, not an exception that kills an organ."""
        _keys(monkeypatch)
        monkeypatch.setattr(SA, "_signed",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope")))
        assert SA.probe().available is False


class TestCreationIsBoundedAutomation:
    def _available(self, monkeypatch, n=1):
        _keys(monkeypatch)
        calls = []
        def fake(path, params, method="GET"):
            calls.append((path, method))
            if "list" in path:
                return {"subAccounts": [{"email": f"s{i}"} for i in range(n)]}
            return {"email": params.get("subAccountString", "x") + "@virtual"}
        monkeypatch.setattr(SA, "_signed", fake)
        return calls

    def test_create_writes_a_ledger_row_with_the_purpose(self, monkeypatch):
        self._available(monkeypatch)
        row = SA.create_virtual("isolate the funding-carry sleeve margin")
        assert row["action"] == "CREATE"
        assert "funding-carry" in row["purpose"]
        assert SA.LEDGER.exists()

    def test_the_count_cap_is_hard(self, monkeypatch):
        self._available(monkeypatch, n=SA.MAX_SUBACCOUNTS)
        with pytest.raises(SA.SubAccountsUnavailable, match="cap"):
            SA.create_virtual("one drawer too many for the policy")

    def test_a_purposeless_drawer_is_refused(self, monkeypatch):
        self._available(monkeypatch)
        with pytest.raises(SA.SubAccountsUnavailable, match="purpose"):
            SA.create_virtual("x")

    def test_blocked_tier_creation_raises_with_the_venue_reason(self, monkeypatch):
        _keys(monkeypatch)
        monkeypatch.setattr(SA, "_signed",
                            lambda *a, **k: (_ for _ in ()).throw(
                                RuntimeError("corporate accounts only")))
        with pytest.raises(SA.SubAccountsUnavailable, match="BLOCKED-TIER"):
            SA.create_virtual("isolate the carry sleeve")


class TestTransfersAreMoneyPath:
    def _ready(self, monkeypatch, book=1000.0):
        _keys(monkeypatch)
        monkeypatch.setattr(SA, "_signed", lambda *a, **k: {"subAccounts": [], "tranId": 1})
        import libs.autodiscovery.validation as V
        monkeypatch.setattr(V, "_desk_equity_usd", lambda: book)

    def test_unsigned_transfer_refused(self, monkeypatch):
        self._ready(monkeypatch)
        with pytest.raises(SA.SubAccountsUnavailable, match="unsigned"):
            SA.transfer(to_email="a@b", asset="USDT", amount=10,
                        authorised_by="  ", reason="fund the carry sleeve drawer")

    def test_reasonless_transfer_refused(self, monkeypatch):
        self._ready(monkeypatch)
        with pytest.raises(SA.SubAccountsUnavailable, match="reason"):
            SA.transfer(to_email="a@b", asset="USDT", amount=10,
                        authorised_by="principal", reason="fund")

    def test_the_cap_is_equity_relative_not_absolute(self, monkeypatch):
        """The $100k-floor lesson, applied forward: an absolute cap is correct at one book size
        and wrong at every other. 25% of a $1k book refuses $260 and allows $250."""
        self._ready(monkeypatch, book=1000.0)
        with pytest.raises(SA.SubAccountsUnavailable, match="exceeds"):
            SA.transfer(to_email="a@b", asset="USDT", amount=260,
                        authorised_by="principal", reason="fund the carry sleeve drawer")
        row = SA.transfer(to_email="a@b", asset="USDT", amount=250,
                          authorised_by="principal", reason="fund the carry sleeve drawer")
        assert row["action"] == "TRANSFER" and row["amount"] == 250

    def test_unreadable_book_fails_closed(self, monkeypatch):
        self._ready(monkeypatch)
        import libs.autodiscovery.validation as V
        monkeypatch.setattr(V, "_desk_equity_usd",
                            lambda: (_ for _ in ()).throw(OSError("no state")))
        with pytest.raises(SA.SubAccountsUnavailable, match="fail-closed"):
            SA.transfer(to_email="a@b", asset="USDT", amount=1,
                        authorised_by="principal", reason="fund the carry sleeve drawer")

    def test_every_transfer_lands_in_the_ledger_with_a_name(self, monkeypatch):
        self._ready(monkeypatch)
        SA.transfer(to_email="a@b", asset="USDT", amount=50,
                    authorised_by="principal", reason="fund the carry sleeve drawer")
        rows = [json.loads(x) for x in SA.LEDGER.read_text().splitlines()]
        assert rows[-1]["authorised_by"] == "principal"
