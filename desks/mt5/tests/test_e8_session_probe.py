"""E8 gold session probe and speed lift (zuck 2026-11-26 22:34Z; risk-autonomy ruling 2026-11-14).

london_am and afternoon go live on E8 at a fill-proven shrink of the code ceiling, latch back to the
principal's pin after SESSION_PROBE_DEMOTE_STOPS stop exits, and never open on a void cert book.
gold_asia is lifted to E8_SPEED_RISK while the other windows carry at most probe-scale risk.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from test_fusion_book_r6 import AFTERNOON_H, ASIA_H, LONDON_H, VALID, _e8, _placed  # noqa: E402

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


def _probe(tmp_path, *, cert=None, void=False, pinned=("london_am", "afternoon"), stops=(),
           now=NOW):
    sp = tmp_path / "stops.jsonl"
    if stops:
        sp.write_text("".join(json.dumps(r) + "\n" for r in stops), encoding="utf-8")
    return g.session_probe(now=now, cert_void=void, cert=cert or {"asia": 0.006},
                           pinned=set(pinned), ceiling=dc.E8_CERT_CEILING,
                           off=tmp_path / "off", state_path=tmp_path / "state.json",
                           stops_path=sp)


def test_the_probe_size_is_the_fill_proven_shrink_of_the_ceiling() -> None:
    assert g.session_probe_frac(7, 0.006) == round(0.006 * 7 / 57, 6)
    assert g.session_probe_frac(5, 0.006) == round(0.006 * 5 / 55, 6)
    assert g.session_probe_frac(0, 0.006) == 0.0
    assert g.session_probe_frac(7, 0.0) == 0.0


def test_the_probe_opens_both_pinned_windows_on_their_own_n(tmp_path) -> None:
    out, doc = _probe(tmp_path)
    assert out == {"london_am": g.session_probe_frac(7, dc.E8_CERT_CEILING),
                   "afternoon": g.session_probe_frac(5, dc.E8_CERT_CEILING)}
    assert {w: r["status"] for w, r in doc["windows"].items()} == dict.fromkeys(
        ("london_am", "afternoon"), "LIVE")
    st = json.loads((tmp_path / "state.json").read_text("utf-8"))
    assert set(st["windows"]) == {"london_am", "afternoon"}


def test_a_void_book_or_the_revert_marker_opens_nothing(tmp_path) -> None:
    assert _probe(tmp_path, void=True)[0] == {}
    (tmp_path / "off").write_text("", encoding="utf-8")
    out, doc = _probe(tmp_path)
    assert out == {} and doc["enabled"] is False


def test_a_certified_number_beats_the_probe_and_an_unpinned_window_is_untouched(tmp_path) -> None:
    out, doc = _probe(tmp_path, cert={"asia": 0.006, "london_am": 0.004}, pinned=("afternoon",))
    assert set(out) == {"afternoon"}
    assert doc["windows"]["london_am"]["status"] == "NOT_PINNED"
    (tmp_path / "b").mkdir()
    out, doc = _probe(tmp_path / "b", cert={"asia": 0.006, "london_am": 0.004})
    assert set(out) == {"afternoon"} and doc["windows"]["london_am"]["status"] == "CERTIFIED"


def test_five_stop_exits_since_the_start_demote_and_the_demotion_latches(tmp_path) -> None:
    _probe(tmp_path)                                    # starts the clock at NOW
    later = (NOW + timedelta(hours=1)).isoformat()
    rows = [{"at": later, "window": "london_am"}] * g.SESSION_PROBE_DEMOTE_STOPS
    rows += [{"at": later, "window": "afternoon"}] * (g.SESSION_PROBE_DEMOTE_STOPS - 1)
    day2 = NOW + timedelta(days=1)
    out, doc = _probe(tmp_path, stops=rows, now=day2)
    assert "london_am" not in out and doc["windows"]["london_am"]["status"] == "DEMOTED"
    assert "afternoon" in out
    (tmp_path / "stops.jsonl").unlink()                 # the latch holds with no journal at all
    out, doc = _probe(tmp_path, now=day2)
    assert "london_am" not in out and doc["windows"]["london_am"]["status"] == "DEMOTED"


def test_stops_before_the_probe_started_do_not_count(tmp_path) -> None:
    old = (NOW - timedelta(days=3)).isoformat()
    out, _ = _probe(tmp_path, stops=[{"at": old, "window": "london_am"}] * 9)
    assert "london_am" in out


def test_an_unreadable_state_opens_nothing(tmp_path) -> None:
    (tmp_path / "state.json").write_text("{torn", encoding="utf-8")
    out, doc = _probe(tmp_path)
    assert out == {} and doc["enabled"] is False


def test_the_lane_places_london_am_at_the_probe_size_and_bills_the_shrink(
        monkeypatch, tmp_path) -> None:
    doc, intents = _e8(monkeypatch, tmp_path, hour=LONDON_H, kelly=None, cert=VALID, probe=True)
    frac = g.session_probe_frac(7, dc.E8_CERT_CEILING)
    assert doc["sizing_source"]["london_am"] == "session_probe"
    assert _placed(doc, intents)["london_am"] == {(frac, "session_probe")}
    (row,) = [r for r in intents if r.get("rail") == "session_probe_shrink"]
    assert row["window"] == "london_am" and row["missed_growth_risk_usd"] > 0


def test_the_lane_places_afternoon_at_its_own_n(monkeypatch, tmp_path) -> None:
    doc, intents = _e8(monkeypatch, tmp_path, hour=AFTERNOON_H, kelly=None, cert=VALID,
                       probe=True)
    assert _placed(doc, intents)["afternoon"] == {
        (g.session_probe_frac(5, dc.E8_CERT_CEILING), "session_probe")}


def test_a_void_book_still_sends_nothing_with_the_probe_on(monkeypatch, tmp_path) -> None:
    doc, _ = _e8(monkeypatch, tmp_path, hour=LONDON_H, kelly=None, cert=None, probe=True)
    assert doc["placed"] == [] and doc["sizing_source"]["london_am"] == "pinned_zero"


# ------------------------------------------------------------------------------ the speed lift

def test_asia_is_lifted_while_the_other_windows_are_probe_scale(monkeypatch, tmp_path) -> None:
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=None, cert=VALID, probe=True,
                       lift=True)
    assert doc["e8_speed_lift"]["status"] == "LIFTED"
    assert _placed(doc, intents)["asia"] == {(g.E8_SPEED_RISK, "e8_speed_lift")}


def test_the_lift_drops_when_the_other_windows_carry_real_size(tmp_path) -> None:
    kelly = {"asia": 0.006, "london_am": 0.004, "afternoon": 0.0}
    lift, doc = g.e8_speed_lift(kelly, {"asia": "cert_book"}, ceiling=0.006,
                                off=tmp_path / "off")
    assert lift is None and doc["status"] == "DROPPED"
    lift, doc = g.e8_speed_lift({**kelly, "london_am": 0.0007}, {"asia": "cert_book"},
                                ceiling=0.006, off=tmp_path / "off")
    assert lift == g.E8_SPEED_RISK and doc["status"] == "LIFTED"


def test_the_lift_never_revives_a_zero_or_lifts_an_unbooked_window(tmp_path) -> None:
    off = tmp_path / "off"
    assert g.e8_speed_lift({"asia": 0.0}, {"asia": "cert_book"}, ceiling=0.006, off=off)[0] is None
    assert g.e8_speed_lift({"asia": 0.005}, {"asia": "kelly_survival"}, ceiling=0.006,
                           off=off)[0] is None
    off.write_text("", encoding="utf-8")
    assert g.e8_speed_lift({"asia": 0.006}, {"asia": "cert_book"}, ceiling=0.006,
                           off=off)[0] is None


def test_the_lift_is_off_with_its_marker_and_asia_is_the_cert(monkeypatch, tmp_path) -> None:
    doc, intents = _e8(monkeypatch, tmp_path, hour=ASIA_H, kelly=None, cert=VALID, probe=True)
    assert _placed(doc, intents)["asia"] == {(0.006, "cert_book")}


def test_the_summed_gold_risk_with_the_lift_is_capped_in_code(tmp_path) -> None:
    """Audit condition (c): asia + both probes never exceed E8_GOLD_SUM_MAX with the lift on."""
    off = tmp_path / "off"
    probes = {w: g.session_probe_frac(n, dc.E8_CERT_CEILING)
              for w, n in g.SESSION_PROBE_PRIOR_N.items()}
    lift, _ = g.e8_speed_lift({"asia": 0.006, **probes}, {"asia": "cert_book"}, ceiling=0.006,
                              off=off)
    assert lift is not None and lift + sum(probes.values()) <= g.E8_GOLD_SUM_MAX
    assert g.E8_GOLD_SUM_MAX < 0.025              # E8 Pro's daily limit
    for others in (0.0015, 0.0016, 0.003):
        lift, _ = g.e8_speed_lift({"asia": 0.006, "london_am": others}, {"asia": "cert_book"},
                                  ceiling=0.006, off=off)
        total = (lift if lift is not None else 0.006) + others
        assert lift is None or total <= g.E8_GOLD_SUM_MAX


def test_the_exception_is_scoped_to_exactly_two_e8_windows() -> None:
    """Audit condition (a): the n<10 exception names london_am and afternoon only, on E8 only."""
    assert set(g.SESSION_PROBE_PRIOR_N) == {"london_am", "afternoon"}
    assert dc.PRINCIPAL_ZERO["fusion"] >= dc.GOLD_ASIA_ONLY_ZERO     # Fusion keeps its pin
