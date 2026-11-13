"""The Auditor's HOLD on the E8 recut v2 (dfcff6e4), pinned through the lane's own code.

MUST-FIX 1 -- no host identifier in a synced file. `e8_decision_ledger.jsonl` and
`e8_gold_heartbeat.json` are published by `sync_shadow_to_git.ps1`; they carried the hostname and
the raw MachineGuid / `/etc/machine-id`. They now carry the `host_identity` VERDICT and, when a
box-local key exists, a keyed HMAC `machine_ref`; no key, no field.

MUST-FIX 2 -- no free exception text in a synced field. A TradeLocker HTTP error can carry the
backend host, a URL with a token, an `Authorization: Bearer ...` header or a body. Every path that
reached `why` (the leg loop's refusal, the re-send's refusal, the guard, the position book, the
heartbeat's extra) now publishes the type name only, and the row/heartbeat writer runs every
string through `public_text`, so a forgotten call site is still caught.

SHOULD-FIX 1 -- slip charged once. SHOULD-FIX 2 -- a re-send is budgeted like a first send, and a
dropped leg still to be re-sent counts in the committed risk.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import e8_evidence as ev  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from prop import e8_guard  # noqa: E402
from test_e8_gold_guard_and_open_risk import _sandbox, _Venue  # noqa: E402
from test_e8_placement_evidence import (  # noqa: E402
    _LEG,
    _RETRY_HOUR,
    _declare_id_account,
    _FlatMT5,
    _fusion_kw,
    _IdVenue,
    _retry_state,
    _RetryVenue,
)

#: What a TradeLocker HTTP error can carry. None of it may reach a synced file.
SECRET = ("GET https://live.tradelocker.com/backend-api/trade/orders?access_token=tok_SECRET123 "
          "via api.internal.example.net (10.9.8.7:443) Authorization: Bearer "
          "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl body {\"error\": \"denied\"}")
NEEDLES = ("tradelocker.com", "tok_SECRET123", "example.net", "10.9.8.7", "Bearer",
           "eyJhbGci", "https://", "Authorization", "denied")
HOSTNAME = "secret-box-host-77"
MACHINE_ID = "deadbeefcafe0123456789abcdef0123"


def _synced_text() -> str:
    """Everything the box publishes from this lane: the ledger and the heartbeat."""
    out = []
    for p in (ev.decisions_path(), ev.heartbeat_path()):
        if p.exists():
            out.append(p.read_text("utf-8"))
    return "\n".join(out)


def _rows() -> list[dict[str, Any]]:
    p = ev.decisions_path()
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


def _no_needle(text: str) -> None:
    leaked = [n for n in NEEDLES if n in text]
    assert leaked == [], leaked


def _as_this_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import host_identity
    ident = host_identity.classify(MACHINE_ID, HOSTNAME,
                                   {"hostname": HOSTNAME, "machine_id": MACHINE_ID})
    monkeypatch.setattr(host_identity, "identify", lambda *a, **k: ident)


# ------------------------------------------------------------- MUST-FIX 1: host identifiers

def test_a_pass_publishes_the_verdict_and_a_keyed_machine_ref_only(monkeypatch, tmp_path) -> None:
    _as_this_host(monkeypatch)
    _sandbox(monkeypatch, tmp_path)
    doc = g.run(_Venue(), _FlatMT5(), armed=False)
    text = _synced_text()
    assert HOSTNAME not in text and MACHINE_ID not in text
    beat = json.loads(ev.heartbeat_path().read_text("utf-8"))
    ref = ev.machine_ref(MACHINE_ID)
    assert ref and ref.startswith("hmac:") and MACHINE_ID not in ref
    assert beat["host"] == {"verdict": "TRADING", "machine_ref": ref}
    [row] = _rows()
    assert row["host_verdict"] == "TRADING" and row["machine_ref"] == ref
    assert not {"host", "hostname", "machine_id", "recorded_machine_id"} & set(row)
    # The LOCAL report keeps the full identity, so the box can still say which machine it is.
    assert doc["host"]["hostname"] == HOSTNAME and doc["host"]["machine_id"] == MACHINE_ID
    # Stable on one box (rows still join), and a different machine reads differently.
    assert ev.machine_ref(MACHINE_ID) == ref != ev.machine_ref("0" * 32)


def test_no_host_key_omits_machine_ref_and_never_writes_the_raw_id(monkeypatch, tmp_path) -> None:
    _as_this_host(monkeypatch)
    monkeypatch.setenv(ev.HOST_KEY_ENV, "short")         # set but too short: NO key
    _sandbox(monkeypatch, tmp_path)
    g.run(_Venue(), _FlatMT5(), armed=False)
    text = _synced_text()
    assert HOSTNAME not in text and MACHINE_ID not in text and "machine_ref" not in text
    beat = json.loads(ev.heartbeat_path().read_text("utf-8"))
    assert beat["host"] == {"verdict": "TRADING"}


def test_the_host_key_is_never_created_in_the_repo() -> None:
    """The conftest redirects it; the default lives under the ignored secrets area."""
    assert "secrets" in ev.HOST_KEY_FILE.parts
    import subprocess
    rel = ev.HOST_KEY_FILE.relative_to(_ROOT).as_posix()
    assert subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=_ROOT).returncode == 0


def test_a_row_kept_by_an_older_build_loses_its_host_fields_and_free_text() -> None:
    st: dict[str, Any] = {"evidence_pending": [
        {"decided_at": "2026-10-19T14:00:00+00:00", "lane": "e8_gold", "window": "afternoon",
         "outcome": "DEFERRED", "reason": "venue_rejected", "host": HOSTNAME,
         "machine_id": MACHINE_ID, "host_verdict": "TRADING",
         "why": f"RuntimeError: {SECRET}"}]}
    written = ev.record_decisions([], st, now=datetime.now(UTC), server_date="2026-10-20",
                                  account=ev.UNMEASURED, armed=True, host={})
    assert len(written) == 1
    text = ev.decisions_path().read_text("utf-8")
    assert HOSTNAME not in text and MACHINE_ID not in text
    _no_needle(text)
    assert _rows()[0]["machine_ref"] == ev.machine_ref(MACHINE_ID)


# ------------------------------------------------------ MUST-FIX 2: no free exception text

class _SecretRefusingVenue(_IdVenue):
    def place_stop(self, symbol: str, side: str, lot: float, **kw: Any) -> int:
        raise RuntimeError(SECRET)


def test_a_refused_send_and_its_re_send_publish_the_type_name_only(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    _declare_id_account()
    venue = _SecretRefusingVenue()
    g.run(venue, _FlatMT5(), armed=True)          # the leg loop refuses; the retry refuses
    g.run(venue, _FlatMT5(), armed=True)          # a later pass re-sends and is refused again
    rows = _rows()
    refused = [r for r in rows if r["reason"] == ev.R_VENUE_REJECTED]
    assert refused and all("RuntimeError" in r["why"] for r in refused), rows
    _no_needle(_synced_text())
    # ...while the LOCAL log keeps the full text for whoever debugs it on the box.
    assert "tradelocker.com" in Path(g.LOG).read_text("utf-8")


def test_a_guard_that_raises_secret_text_publishes_the_type_name_only(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)

    def boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(e8_guard, "assess", boom)
    doc = g.run(_Venue(), _FlatMT5(), armed=True)
    assert doc["guard"] == "guard unreadable (RuntimeError)"
    rows = _rows()
    assert rows and all(r["reason"] == ev.R_GUARD_UNREADABLE for r in rows), rows
    assert json.loads(ev.heartbeat_path().read_text("utf-8"))["guard"] == doc["guard"]
    _no_needle(_synced_text())


def test_an_unreadable_position_book_publishes_the_type_name_only(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)

    class Leaky(_Venue):
        def positions(self) -> list[dict]:
            raise ConnectionError(SECRET)

    g.run(Leaky(), _FlatMT5(), armed=True)
    rows = _rows()
    assert any(r["reason"] == ev.R_POSITIONS_UNREADABLE and "ConnectionError" in r["why"]
               for r in rows), rows
    _no_needle(_synced_text())


def test_a_re_send_refused_with_secret_text_keeps_it_out_of_the_row_and_the_state(
        monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents.jsonl")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    (tmp_path / "intents.jsonl").write_text("", "utf-8")

    class Venue(_RetryVenue):
        def place_stop(self, sym: str, side: str, lot: float, **kw: Any) -> int:
            self.sent.append((side, lot))
            raise RuntimeError(SECRET)

    st, decided = _retry_state(), ev.Decisions()
    g._retry_failed_legs(Venue(), st, {"actions": []}, hour=_RETRY_HOUR, now=datetime.now(UTC),
                         open_orders=[], orders_ok=True, filled={}, xau_positions=[],
                         positions_ok=True, stood_down=False, armed=True, hist_rows=[],
                         history_ok=True, instrument_id=316, decided=decided,
                         budget=_AMPLE, **_fusion_kw())
    leg = st["windows"]["asia"]["failed"]["buy_stop"]
    assert leg["why"] == "venue refused (RuntimeError)"
    ev.record_decisions(decided, st, now=datetime.now(UTC), server_date="2026-09-28",
                        account=ev.UNMEASURED, armed=True, host={"verdict": "TRADING"})
    assert [r["reason"] for r in _rows()] == [ev.R_VENUE_REJECTED]
    _no_needle(_synced_text())
    # The local intents journal keeps the venue's text (it is never synced).
    assert "RuntimeError" in (tmp_path / "intents.jsonl").read_text("utf-8")


def test_the_writer_strips_free_text_a_call_site_forgot(monkeypatch) -> None:
    """The central guarantee: whatever a caller hands the writer, the published row and the
    heartbeat carry no URL, host, IP, token, header or body."""
    d = ev.Decisions()
    d.note("asia", ev.DEFERRED, ev.R_VENUE_REJECTED, f"refused ({type(KeyError()).__name__}: "
           f"{SECRET})")
    d.note("london_am", ev.DEFERRED, ev.R_GUARD_UNREADABLE, f"plain prose with {SECRET}")
    st: dict[str, Any] = {}
    ev.record_decisions(d, st, now=datetime.now(UTC), server_date="2026-10-20",
                        account=ev.UNMEASURED, armed=True, host={"verdict": "TRADING"})
    ev.write_heartbeat("OK", at=datetime.now(UTC), armed=True,
                       extra={"err": f"HTTPError: {SECRET}", "raw": SECRET,
                              "nested": {"e": RuntimeError(SECRET)}})
    _no_needle(_synced_text())
    assert _rows()[0]["why"].startswith("refused (KeyError <detail withheld>")


@pytest.mark.parametrize("text", [
    "sent buy_stop, sell_stop", "shadow: would send buy_stop",
    "one gold trade at risk at a time: bracket(s) 2026-10-15/asia still rest at the venue",
    "XAUUSD.asia 4320.30 at 2026-11-13T10:00:00+00:00 on e8_gold:afternoon",
])
def test_public_text_keeps_the_lanes_own_prose(text: str) -> None:
    assert ev.public_text(text) == text


def test_exc_name_is_the_type_name_only() -> None:
    assert ev.exc_name(RuntimeError(SECRET)) == "RuntimeError"
    assert g.published_failure(RuntimeError(SECRET)) == "RuntimeError"
    own = g.RiskUnbounded("position 9 has no readable stop: its adverse distance is the whole room")
    assert g.published_failure(own).startswith("RiskUnbounded: position 9")


# ------------------------------------------------------------ SHOULD-FIX 1: slip charged once

def test_committed_slip_is_not_grossed_up_again() -> None:
    # 1,349.2 committed already carries its 24.13 points of slip (committed_risk).
    assert not g.risk_budget_allows(1349.2, 600.0, 2500.0)[0]            # the old double charge
    ok, why = g.risk_budget_allows(1349.2, 600.0, 2500.0, committed_slip_counted=True)
    assert ok and "committed slip counted" in why                        # 1,349.2 + 750 = 2,099
    # An explicit new-leg slip replaces the buffer on the leg too.
    assert g.risk_budget_allows(1000.0, 1000.0, 2500.0, committed_slip_counted=True,
                                new_slip_usd=300.0)[0]                   # 2,300 <= 2,400
    assert not g.risk_budget_allows(1000.0, 1000.0, 2500.0, committed_slip_counted=True,
                                    new_slip_usd=401.0)[0]


def test_the_ceiling_fit_applies_the_buffer_only_without_explicit_slip() -> None:
    assert g.ceiling_budget_lot(0.0, 2500.0, 33.5, 10.0, 400.0) == pytest.approx(2400 / 4335)
    assert g.ceiling_budget_lot(0.0, 2500.0, 33.5, 10.0, 0.0) == pytest.approx(1920 / 335)


def test_a_window_the_double_charge_deferred_is_now_sent(monkeypatch, tmp_path) -> None:
    """The 0.4-lot locked short of test_an_unshrunk_window_over_the_budget_is_deferred_with_a_row:
    1,349.2 committed WITH its slip + 600 x 1.25 = 2,099.2 <= 2,400. Sent, no risk_budget row."""
    import test_e8_gold_bracket_guard as bg
    from test_e8_gold_bracket_guard_v5 import _locked_short

    bg._sandbox(monkeypatch, tmp_path, guard=bg._guard())
    bg._cert_book(tmp_path, 0.02)
    venue = bg._Venue()
    venue._positions = [_locked_short(0.4)]
    doc = g.run(venue, bg._FlatMT5(), armed=True)
    assert doc["committed_risk"]["total_usd"] == pytest.approx(1349.2)
    assert venue.sent
    assert not [d for d in doc["decisions"] if d["reason"] == ev.R_RISK_BUDGET]


# ------------------------------------------------------- SHOULD-FIX 2: budgeted re-sends

_AMPLE = {"committed": 0.0, "detail": {"slip_points": 0.0}, "contract": 100.0, "room": 1e9}


def _journal(tmp_path: Path) -> list[dict[str, Any]]:
    p = tmp_path / "intents.jsonl"
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


def _retry(monkeypatch, tmp_path, venue: _RetryVenue, st: dict,
           budget: dict | None) -> ev.Decisions:
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents.jsonl")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    if not (tmp_path / "intents.jsonl").exists():
        (tmp_path / "intents.jsonl").write_text("", "utf-8")
    decided = ev.Decisions()
    g._retry_failed_legs(venue, st, {"actions": []}, hour=_RETRY_HOUR, now=datetime.now(UTC),
                         open_orders=[], orders_ok=True, filled={}, xau_positions=[],
                         positions_ok=True, stood_down=False, armed=True, hist_rows=[],
                         history_ok=True, instrument_id=316, decided=decided, budget=budget,
                         **_fusion_kw())
    return decided


def test_a_dropped_leg_counts_in_the_committed_risk_once() -> None:
    st = _retry_state()
    total, detail = g.committed_risk([], [], [], st, bid=4320.0, ask=4320.3, contract_size=100.0)
    assert total == pytest.approx(20.0 * 0.5 * 100.0)
    assert detail["retrying_legs"] == {"2026-09-28/asia/buy_stop": pytest.approx(1000.0)}
    # The failed send in fact LANDED and rests with no id this lane knows: counted once, as it.
    landed = [{"id": 77, "side": "buy", "stopPrice": 4340.0, "qty": 0.5, "stopLoss": 4320.0,
               "tradableInstrumentId": 316}]
    total2, detail2 = g.committed_risk([], landed, [], st, bid=4320.0, ask=4320.3,
                                       contract_size=100.0, instrument_id=316)
    assert total2 == pytest.approx(total) and detail2["foreign"] == []


def test_a_dropped_leg_blocks_another_window_but_not_its_own_re_send() -> None:
    detail = {"retrying_legs": {"2026-09-28/asia/buy_stop": 1000.0},
              "pending_brackets": {"2026-09-28/asia": 900.0}}
    assert "dropped leg" in str(g.one_at_risk_blocker({"retrying_legs":
                                                       detail["retrying_legs"]}))
    assert g.one_at_risk_blocker(detail) is not None                    # london_am waits
    assert g.one_at_risk_blocker(detail, exclude_window="asia") is None  # asia completes itself


def test_a_re_send_waits_while_another_trade_is_at_risk_and_bills_once(
        monkeypatch, tmp_path) -> None:
    budget = {"committed": 2000.0, "contract": 100.0, "room": 1e9,
              "detail": {"slip_points": 24.13, "positions": [
                  {"position_id": 555, "at_risk": True, "risk_usd": 1000.0}],
                  "retrying_legs": {"2026-09-28/asia/buy_stop": 1000.0}}}
    v, st = _RetryVenue(), _retry_state()
    d = _retry(monkeypatch, tmp_path, v, st, budget)
    assert v.sent == []
    assert [(r["outcome"], r["reason"]) for r in d.rows] == [(ev.DEFERRED, ev.R_ONE_AT_RISK)]
    leg = st["windows"]["asia"]["failed"]["buy_stop"]
    assert leg["attempts"] == _LEG["attempts"]                          # not an attempt
    [bill] = [r for r in _journal(tmp_path) if r.get("status") == "RAIL_BLOCKED"]
    assert bill["rail"] == "one_gold_at_risk" and bill["reason"] == ev.R_ONE_AT_RISK
    assert bill["missed_growth_risk_usd"] == pytest.approx(1000.0)
    _retry(monkeypatch, tmp_path, _RetryVenue(), st, budget)              # held again
    assert len([r for r in _journal(tmp_path) if r.get("status") == "RAIL_BLOCKED"]) == 1


def test_a_re_send_over_the_budget_is_deferred_under_risk_budget(monkeypatch, tmp_path) -> None:
    # 2,500 committed includes this leg's own 1,000 (taken back out): 1,500 + 1,000 x 1.25 =
    # 2,750 > 2,500 - 100.
    budget = {"committed": 2500.0, "contract": 100.0, "room": 2500.0,
              "detail": {"slip_points": 24.13,
                         "retrying_legs": {"2026-09-28/asia/buy_stop": 1000.0}}}
    v = _RetryVenue()
    d = _retry(monkeypatch, tmp_path, v, _retry_state(), budget)
    assert v.sent == []
    assert [(r["outcome"], r["reason"]) for r in d.rows] == [(ev.DEFERRED, ev.R_RISK_BUDGET)]
    [bill] = [r for r in _journal(tmp_path) if r.get("status") == "RAIL_BLOCKED"]
    assert bill["rail"] == g.RISK_BUDGET_RAIL and bill["missed_growth_risk_usd"] == 1000.0
    # The same leg inside the budget (its own 1,000 is not charged twice) is sent.
    fits = {**budget, "committed": 2000.0}
    v2, other = _RetryVenue(), tmp_path / "fits"
    other.mkdir()
    d2 = _retry(monkeypatch, other, v2, _retry_state(), fits)
    assert v2.sent == [("buy", 0.5)] and d2.rows[0]["reason"] == ev.R_PLACED


def test_a_re_send_with_no_measured_budget_fails_closed(monkeypatch, tmp_path) -> None:
    for budget in (None, {"error": "ConnectionError", "code": ev.R_ORDERS_UNREADABLE}):
        v = _RetryVenue()
        d = _retry(monkeypatch, tmp_path, v, _retry_state(), budget)
        assert v.sent == []
        want = ev.R_RISK_UNMEASURABLE if budget is None else ev.R_ORDERS_UNREADABLE
        assert [(r["outcome"], r["reason"]) for r in d.rows] == [(ev.DEFERRED, want)]


def test_run_measures_and_passes_the_re_send_budget() -> None:
    src = (_DESK / "prop" / "e8_gold.py").read_text("utf-8")
    run_body = src[src.index("def run("):src.index("def _retry_failed_legs(")]
    assert "budget=retry_budget" in run_body and "measure_account_risk(" in run_body
    body = src[src.index("def _retry_failed_legs("):src.index("def connect_terminal(")]
    assert body.index("retry_budget_hold(") < body.index("fenced_send(")



def test_public_text_withholds_the_rails_usd_figures() -> None:
    """Audit HOLD on #1096: the rails' USD sentence publishes without its amounts."""
    out = ev.public_text("committed 1,349 + this window 600 USD, x1.25 slippage = 2,436, "
                         "against 2,500")
    assert out == ("committed <amount> + this window <amount>, x1.25 slippage = <amount>, "
                   "against <amount>")


@pytest.mark.parametrize("why, published", [
    ("daily loss -850 vs floor", "daily loss <n> vs floor"),
    ("pnl=-120.5", "pnl=<n>"),
    ("against -50 to today's floor", "against <n> to today's floor"),
    ("against 850 to today's floor.", "against <n> to today's floor."),
    ("850-900", "<n>-<n>"),
    ("850/1000", "<n>/<n>"),
    ("+75 above", "<n> above"),
    ("adopted order 42 on 2026-11-13 at 07:00", "adopted order 42 on 2026-11-13 at 07:00"),
    ("stop 20 points away, ticket 123456 #77 x1.5 lot 0.39",
     "stop 20 points away, ticket 123456 #77 x1.5 lot 0.39"),
    ("2026-11-13T07:00:05 placed", "2026-11-13T07:00:05 placed"),
])
def test_a_published_why_withholds_signed_and_joined_figures(why: str, published: str) -> None:
    """Audit HOLD on #1096 (MF1, SF1): a signed room or day P&L never publishes its figure."""
    assert ev._figures_withheld(why) == published
