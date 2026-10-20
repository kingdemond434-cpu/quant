"""The complete adapter imports portably without contacting a broker."""
import pytest


def test_full_import_is_inert_and_uses_a_temporary_desk(portable_gateway, tmp_path):
    gw = portable_gateway
    assert gw.BASE == tmp_path
    assert gw.STATE == tmp_path / 'data' / 'gateway_state.json'
    assert gw.LEDGER == tmp_path / 'data' / 'live_ledger.jsonl'
    assert gw.TERMINAL == 'test-terminal-only'
    assert gw._test_sdk._test_calls == []
    assert list(tmp_path.iterdir()) == []


def test_sdk_contract_does_not_invent_constants(portable_gateway):
    sdk = portable_gateway._test_sdk
    assert sdk.TIMEFRAME_M15 == 15
    with pytest.raises(AttributeError):
        getattr(sdk, 'TIMEFRAME_INVENTED')


@pytest.mark.parametrize('name', ['initialize', 'login', 'order_send'])
def test_every_sdk_operation_requires_an_explicit_test_double(portable_gateway, name):
    sdk = portable_gateway._test_sdk
    with pytest.raises(AssertionError, match='Unmocked SDK operation'):
        getattr(sdk, name)()
    assert sdk._test_calls == [name]
