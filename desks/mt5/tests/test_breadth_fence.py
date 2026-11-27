import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.breadth_fence import fence

CLASS = {"EURUSD": "fx", "GBPUSD": "fx", "USDJPY": "fx", "AUDUSD": "fx",
         "XAUUSD": "metal", "US500": "index", "GER40": "index", "XTIUSD": "energy"}


def cls(s):
    return CLASS.get(s, "?")


def _rows(spec):
    out = []
    for sym, n in spec:
        out += [{"symbol": sym, "family": f"f{i % 3}", "i": len(out) + k}
                for k, i in enumerate(range(n))]
    return out


def test_fx_pile_is_spread_on_every_prefix():
    rows = _rows([("EURUSD", 400), ("GBPUSD", 300), ("USDJPY", 200), ("XAUUSD", 30),
                  ("US500", 30), ("GER40", 30), ("XTIUSD", 30)])
    out, rep = fence(rows, window=len(rows), symbol_share=0.25, class_share=0.5,
                     class_of=cls)
    assert rep["status"] == "APPLIED"
    for n in (20, 50, 100):
        c = Counter(cls(r["symbol"]) for r in out[:n])
        assert c["fx"] <= 0.5 * n + 2
    assert rep["after"]["top_class_share"] <= rep["before"]["top_class_share"]


def test_never_drops_and_keeps_order_within_symbol():
    rows = _rows([("EURUSD", 50), ("XAUUSD", 5), ("US500", 5)])
    out, _rep = fence(rows, window=len(rows), symbol_share=0.2, class_share=0.5,
                     class_of=cls)
    assert sorted(r["i"] for r in out) == sorted(r["i"] for r in rows)
    eur = [r["i"] for r in out if r["symbol"] == "EURUSD"]
    assert eur == sorted(eur)


def test_only_window_reordered_and_tail_untouched():
    rows = _rows([("EURUSD", 30), ("XAUUSD", 30)])
    out, rep = fence(rows, window=10, symbol_share=0.5, class_share=0.6, class_of=cls)
    assert out[10:] == rows[10:]
    assert rep["window"] == 10


def test_low_variety_never_starves_the_judge():
    rows = _rows([("EURUSD", 20)])
    out, rep = fence(rows, window=20, symbol_share=0.05, class_share=0.4, class_of=cls)
    assert out == rows
    two = _rows([("EURUSD", 20), ("GBPUSD", 20)])
    out2, _ = fence(two, window=40, symbol_share=0.05, class_share=1.0, class_of=cls)
    assert sum(1 for r in out2[:10] if r["symbol"] == "EURUSD") == 5
    assert rep["steps_without_eligible_row"] > 0


def test_fault_returns_rows_unchanged():
    rows = _rows([("EURUSD", 5)])

    def boom(_s):
        raise RuntimeError("registry down")

    out, rep = fence(rows, window=5, class_of=boom)
    assert out == rows
    assert rep["status"].startswith("FAILED")


def test_non_dict_rows_ride_along():
    rows = [*_rows([("EURUSD", 3)]), "junk", *_rows([("XAUUSD", 3)])]
    out, _rep = fence(rows, window=len(rows), class_of=cls)
    assert len(out) == len(rows) and "junk" in out


def test_fx_dominant_window_still_caps_each_symbol_when_class_cap_binds():
    spec = [("EURUSD", 3000), ("GBPUSD", 3000), ("USDJPY", 2000), ("AUDUSD", 1500),
            ("EURJPY", 300), ("XAUUSD", 100), ("US500", 100)]
    rows = _rows(spec)
    cls_map = {**CLASS, "EURJPY": "fx"}
    out, rep = fence(rows, window=len(rows), symbol_share=0.05, class_share=0.40,
                     class_of=lambda s: cls_map.get(s, "?"))
    # five FX symbols x 5% = 25% FX cap can't fill the window, so the symbol cap is
    # waived only where every symbol is at its cap; it still bounds each FX symbol
    # until the non-FX supply runs out.
    first = out[:1000]
    eur = sum(1 for r in first if r["symbol"] == "EURUSD")
    assert eur <= 0.20 * 1000
    assert {"XAUUSD", "US500"} <= {r["symbol"] for r in out[:50]}
    assert rep["steps_class_cap_waived"] > 0
    assert sorted(r["i"] for r in out) == sorted(r["i"] for r in rows)


def test_class_of_unavailable_is_reported_and_symbol_cap_still_works():
    rows = _rows([("EURUSD", 100), ("GBPUSD", 100), ("XAUUSD", 100)])
    out, rep = fence(rows, window=300, symbol_share=0.34, class_share=0.4,
                     class_of=lambda _s: "?")
    assert rep["class_of_available"] is False
    assert sum(1 for r in out[:30] if r["symbol"] == "EURUSD") <= 0.34 * 30 + 2
