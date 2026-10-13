"""Final family volume obeys the existing account-currency risk envelope."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _path in (str(_DESK), str(_DESK.parent.parent)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import mt5desk  # noqa: E402
import test_gateway_adapter as adapter  # noqa: E402


def resolve(tmp_path, monkeypatch, *, multiplier=1.4, fraction=0.10,
            equity=1000.0, step=0.01, minimum=0.01, maximum=100.0, sovereign=True):
    rows = adapter._rows()
    venue = adapter._fake_mt5(rows)
    info = SimpleNamespace(volume_min=minimum, volume_step=step, volume_max=maximum,
                           trade_tick_size=0.00001, trade_tick_value=1.0)
    venue.symbol_info = lambda symbol: info
    namespace = adapter._family_ns(tmp_path, venue, monkeypatch, armed_file=False,
                                   sig_hour=adapter._sig_hour(rows))
    namespace["promoted_lot"] = adapter.dc.promoted_lot
    monkeypatch.setattr(adapter.dc, "allocator_sovereign", lambda: sovereign)
    fake_leg = SimpleNamespace(multiplier=lambda *a, **k: (1.0, "neutral"),
                               already_held=lambda *a, **k: 0)
    fake_macro = SimpleNamespace(multiplier=lambda *a, **k: (multiplier, "synthetic"))
    for name, module in (("leg_balance", fake_leg), ("macro_view", fake_macro)):
        monkeypatch.setitem(sys.modules, f"mt5desk.{name}", module)
        monkeypatch.setattr(mt5desk, name, module, raising=False)
    sleeve = adapter._sleeve(risk_frac=fraction, sized_by="allocator_book")
    result = namespace["resolve_family_order"]({"armed": False}, sleeve, equity)
    assert venue.sent == [], "source replay must never reach an order API"
    return result, info


@pytest.mark.parametrize("multiplier,fraction,capped", [
    (1.4, 0.10, True), (1.0, 0.10, False), (0.6, 0.10, False), (1.4, 0.03, False),
])
def test_final_stop_risk_never_exceeds_the_existing_cap(
        tmp_path, monkeypatch, multiplier, fraction, capped):
    result, info = resolve(tmp_path, monkeypatch, multiplier=multiplier, fraction=fraction)
    assert result["ok"]
    risk = result["lot"] * result["dist"] * info.trade_tick_value / info.trade_tick_size
    assert risk <= adapter.dc.MAX_RISK_FRAC * 1000.0 + 1e-9
    assert result["risk_envelope_capped"] is capped
    if fraction == 0.03:
        assert result["lot"] > 0.05, "a boost below the envelope must remain effective"


def test_final_volume_respects_coarse_venue_step(tmp_path, monkeypatch):
    result, _ = resolve(tmp_path, monkeypatch, step=0.1, minimum=0.1)
    assert result["ok"] and result["lot"] == pytest.approx(0.1)


def test_final_volume_respects_venue_maximum(tmp_path, monkeypatch):
    result, _ = resolve(tmp_path, monkeypatch, maximum=0.1)
    assert result["ok"] and result["lot"] == pytest.approx(0.1)


def test_modifier_does_not_bypass_existing_five_lot_ceiling(tmp_path, monkeypatch):
    result, _ = resolve(tmp_path, monkeypatch, equity=1_000_000.0)
    assert result["ok"] and result["lot"] == pytest.approx(5.0)


def test_minimum_lot_is_refused_if_it_cannot_fit_the_envelope(tmp_path, monkeypatch):
    result, _ = resolve(tmp_path, monkeypatch, equity=1.0, sovereign=False)
    assert not result["ok"] and result["stage"] == "risk_envelope"
    assert result["mark"] is False


@pytest.mark.parametrize("maximum", [0.0, float("nan"), float("inf")])
def test_invalid_final_volume_metadata_is_a_refusal(tmp_path, monkeypatch, maximum):
    result, _ = resolve(tmp_path, monkeypatch, maximum=maximum)
    assert not result["ok"] and result["stage"] == "risk_envelope"


def test_unmeasured_final_risk_never_falls_back_to_uncapped_volume(tmp_path, monkeypatch):
    original = adapter.dc._eur_per_price_unit
    calls = 0

    def measured_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ValueError("final risk source unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter.dc, "_eur_per_price_unit", measured_once)
    result, _ = resolve(tmp_path, monkeypatch)
    assert not result["ok"] and result["stage"] == "risk_envelope"
