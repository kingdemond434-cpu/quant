"""THE CROSS-ACCOUNT GOLD DIRECTION LOCK (mt5desk.gold_oco), on stubbed venues and fake IDs.

E8 (TradeLocker), Fusion (the MT5 gateway) and later FTMO trade gold_asia. The first fill on any
account sets the day's direction; opposite resting legs are cancelled everywhere; nothing opens
against another account's open gold; everything fails closed; identity is the keyed account key.
No real login appears here: every login below is a made-up number.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cross_account as xa  # noqa: E402
from mt5desk import fusion_rails  # noqa: E402
from mt5desk import gold_oco as oco  # noqa: E402

# The REAL identity readers, captured before conftest wraps them with a fake-login fallback.
REAL_TL_KEY = oco.tradelocker_oco_key
REAL_MT5_KEY = oco.mt5_oco_key

_spec = importlib.util.spec_from_file_location("_gold_oco_adapter",
                                               _DESK / "tests" / "test_gateway_adapter.py")
assert _spec is not None and _spec.loader is not None
ga = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ga)

#: Fake logins (never a real account). Distinctive, so a leak is findable by substring.
#: E8 is the conftest's DECLARED E8 identity (conftest.CONFTEST_LOGINS/SERVERS["e8"]): r7.1
#: declares E8_ACCOUNT.json under it, and the OCO's key join refuses any other E8 key (v2s).
E8_LOGIN, E8_SERVER = 31337, "E8-Test"
FU_LOGIN, FU_SERVER = 72345678, "FusionMarkets-Test"
FT_LOGIN, FT_SERVER = 63456789, "FTMO-Test"
DAY = "2026-10-21"
MAGIC = 341953


def e8_key() -> str:
    return oco.oco_account_key(E8_LOGIN, E8_SERVER)


def fu_key() -> str:
    return oco.oco_account_key(FU_LOGIN, FU_SERVER)


def _mode(lanes: list[str] | None = None, **modes: str) -> None:
    doc: dict[str, Any] = {"modes": modes}
    if lanes is not None:
        doc["lanes"] = lanes
    oco.MODE_FILE.write_text(json.dumps(doc), encoding="utf-8")


def _flat(lane: str, key: str, *, positions: list | None = None, orders: list | None = None,
          now: datetime | None = None) -> None:
    oco.publish_lane(lane, key, positions=positions or [], orders=orders or [], date=DAY,
                     now=now)


def _world(mode_fusion: str = "fallback") -> None:
    _mode(["e8", "fusion"], fusion=mode_fusion)
    _flat("e8", e8_key())
    _flat("fusion", fu_key())


# ======================================================================== identity

def test_the_suite_e8_identity_is_the_declared_one_and_a_foreign_key_still_refuses() -> None:
    """v2s: the fixtures name E8 by the key E8_ACCOUNT.json declares (r7.1's conftest, as on the
    box), so the key join holds -- and is never loosened: an E8 state under ANY other key is
    still refused, fail closed."""
    assert xa.expected_key("e8") == e8_key()
    assert oco._key_join_refusal("e8", e8_key()) is None
    foreign = oco.oco_account_key(81234567, "E8-Live-Test")
    assert foreign != e8_key()
    assert "does not join" in (oco._key_join_refusal("e8", foreign) or "")


def test_the_identity_is_keyed_never_the_plain_sha256_of_login_at_server() -> None:
    key = oco.oco_account_key(FU_LOGIN, FU_SERVER)
    plain = "sha256:" + hashlib.sha256(f"{FU_LOGIN}@{FU_SERVER}".encode()).hexdigest()[:16]
    assert xa.valid_key(key) and key != plain
    assert key == xa.account_key(FU_LOGIN, FU_SERVER)            # ONE helper: the fence's key
    # One account, one key, however the venue spells its login.
    assert oco.oco_account_key(str(FU_LOGIN), FU_SERVER) == key
    assert oco.oco_account_key(float(FU_LOGIN), FU_SERVER) == key


def test_the_oco_key_joins_the_r6_norm_login_spellings() -> None:
    """Fusion r6's cross_account.norm_login: an int, an integral float and a padded digit string
    are one account, and the server is stripped -- the OCO key follows it, so the two fences
    name one account one way."""
    key = oco.oco_account_key(FU_LOGIN, FU_SERVER)
    for spelling in (FU_LOGIN, float(FU_LOGIN), f" {FU_LOGIN} ", str(FU_LOGIN)):
        assert xa.norm_login(spelling) == str(FU_LOGIN)
        assert oco.oco_account_key(spelling, f" {FU_SERVER} ") == key
    # A username is not a login (publish_sync v5d keys it None and alerts): it names nothing.
    for bad in (None, "", "  ", True, " trader01 "):
        with pytest.raises(oco.IdentityUnavailable):
            oco.oco_account_key(bad, FU_SERVER)


def test_the_oco_key_equals_the_bracket_guard_evidence_key_and_the_fence_key() -> None:
    """THE KEY JOIN (coordinator, OCO v2): bracket guard v5's evidence lane stamps
    `provenance.account_key(int(login), server, create=False)`; the OCO key, the existing
    fence's `cross_account.account_key` and the FTMO prop-ledger key are that same value."""
    from libs.ops import provenance as p
    for login, server in ((FU_LOGIN, FU_SERVER), (E8_LOGIN, E8_SERVER), (FT_LOGIN, FT_SERVER)):
        evidence = p.account_key(int(login), server, create=False)
        assert evidence is not None and xa.valid_key(evidence)
        assert oco.oco_account_key(login, server) == evidence
        assert oco.oco_account_key(str(login), server) == evidence
        assert xa.account_key(login, server) == evidence
        assert evidence != "sha256:" + hashlib.sha256(
            f"{login}@{server}".encode()).hexdigest()[:16]


def test_the_fence_has_no_plain_sha256_fallback(monkeypatch, tmp_path) -> None:
    """With no box key the fence's own key refuses (its readers fail closed): no plain sha256
    is ever computed in its place and written to a book."""
    from libs.ops import provenance as p
    monkeypatch.setenv(p.KEY_ENV, str(tmp_path / "absent.hmac"))
    assert xa.account_key(FU_LOGIN, FU_SERVER) is None          # r7: unresolvable is None
    term = SimpleNamespace(account_info=lambda: SimpleNamespace(login=FU_LOGIN, server=FU_SERVER),
                           positions_get=lambda symbol=None: [], orders_get=lambda symbol=None: [])
    with pytest.raises(ValueError):
        xa.publish_mt5(term, source="t")


def test_the_key_written_to_state_is_not_the_plain_sha256(monkeypatch) -> None:
    _world("oco")
    res = oco.claim_fill("fusion", fu_key(), "buy", date=DAY)
    assert res["won"]
    plain = "sha256:" + hashlib.sha256(f"{FU_LOGIN}@{FU_SERVER}".encode()).hexdigest()[:16]
    written = oco.direction_path().read_text("utf-8") + oco.lane_path("fusion").read_text("utf-8")
    assert fu_key() in written and plain not in written


def test_no_box_key_means_no_identity_and_no_gold_leg(monkeypatch, tmp_path) -> None:
    from libs.ops import provenance as p
    monkeypatch.setenv(p.KEY_ENV, str(tmp_path / "absent.hmac"))
    with pytest.raises(oco.IdentityUnavailable, match="absent"):
        oco.oco_account_key(FU_LOGIN, FU_SERVER)
    assert not (tmp_path / "absent.hmac").exists()        # a reader never creates the key
    v = oco.gate("fusion", "buy_stop", key=None, date=DAY)
    assert not v.allowed and "keyed" in v.why


def test_a_missing_provenance_helper_is_refused(monkeypatch) -> None:
    from libs.ops import provenance as p
    monkeypatch.delattr(p, "account_key")
    with pytest.raises(oco.IdentityUnavailable, match="not landed"):
        oco.oco_account_key(FU_LOGIN, FU_SERVER)


def test_venue_identities_go_through_the_one_helper() -> None:
    # TLAPI 0.56.2 keeps the server in `_credentials`; `api.server` is None and is never read.
    venue = SimpleNamespace(_raw_api=SimpleNamespace(acc_id=E8_LOGIN, server=None,
                                                     _credentials={"server": E8_SERVER}),
                            _creds=None)
    assert REAL_TL_KEY(venue) == oco.oco_account_key(E8_LOGIN, E8_SERVER)
    # No server anywhere fails closed (v1 fell back to a constant that joins nothing).
    with pytest.raises(oco.IdentityUnavailable, match="server"):
        REAL_TL_KEY(SimpleNamespace(_raw_api=SimpleNamespace(acc_id=E8_LOGIN, server=None,
                                                             _credentials={}), _creds=None))
    term = SimpleNamespace(account_info=lambda: SimpleNamespace(login=FU_LOGIN, server=FU_SERVER))
    assert REAL_MT5_KEY(term) == fu_key()
    with pytest.raises(oco.IdentityUnavailable):
        REAL_MT5_KEY(SimpleNamespace(account_info=lambda: None))
    with pytest.raises(oco.IdentityUnavailable):
        REAL_TL_KEY(SimpleNamespace())


# ======================================================================== E8 fills long first

class _GwTerminal(ga._Terminal):
    TRADE_ACTION_REMOVE = 8

    def order_send(self, req: dict) -> SimpleNamespace:
        if req.get("action") == self.TRADE_ACTION_REMOVE:
            self.sent.append(req)
            self.pending = [o for o in self.pending if int(o.ticket) != int(req["order"])]
            return SimpleNamespace(retcode=10009, order=req["order"], comment="removed")
        return super().order_send(req)


def _gw_order(ticket: int, typ: int) -> SimpleNamespace:
    return SimpleNamespace(ticket=ticket, symbol="XAUUSD", type=typ, magic=MAGIC,
                           price_open=2000.0, comment="DWgold_asia")


def test_e8_long_first_cancels_fusions_sell_stop_and_fusion_never_shorts(
        monkeypatch, tmp_path) -> None:
    _world("oco")
    _flat("e8", e8_key(), positions=[{"id": 1, "side": "long", "opened_date": DAY}])
    assert oco.claim_fill("e8", e8_key(), "buy", date=DAY)["won"]
    rows = ga._gold_rows()
    mt5 = _GwTerminal(rows, *ga._quote(rows))
    mt5.pending = [_gw_order(11, 4), _gw_order(12, 5)]          # Fusion's buy and sell stops
    ns = ga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    gone = ns["cancel_gold_against_direction"]({"armed": True}, "fusion", fu_key(), DAY)
    assert gone == 1 and [o.ticket for o in mt5.pending] == [11]
    entry, _ = oco.day_entry(DAY)
    assert entry is not None
    assert [(c["lane"], c["order_id"], c["side"]) for c in entry["legs_cancelled"]] == [
        ("fusion", "12", "short")]
    for mode in ("oco", "fallback"):
        _mode(["e8", "fusion"], fusion=mode)
        assert not oco.gate("fusion", "sell_stop", key=fu_key(), date=DAY).allowed
        assert oco.gate("fusion", "buy_stop", key=fu_key(), date=DAY).allowed


# ======================================================================== Fusion fills short first

class _E8Venue:
    def __init__(self) -> None:
        self.cancelled: list[int] = []

    def cancel(self, order_id: int) -> bool:
        self.cancelled.append(int(order_id))
        return True


def _e8_state(day: str = DAY) -> dict:
    return {"date": day, "carried": {}, "windows": {"asia": {
        "placed_hour": 7.0, "position_id": None, "shadow": False,
        "orders": {"buy_stop": {"id": 501, "price": 4340.0}, "sell_stop": {"id": 502,
                                                                          "price": 4300.0}}}}}


def test_fusion_short_first_cancels_e8s_buy_stop(monkeypatch) -> None:
    from prop import e8_gold as g
    _world("oco")
    assert oco.claim_fill("fusion", fu_key(), "sell", date=DAY)["won"]
    venue, state = _E8Venue(), _e8_state()
    doc: dict = {"gold_oco": {"date": DAY, "key": e8_key()}, "actions": []}
    gone = g.oco_cancel_opposite(venue, state, doc, {501, 502}, armed=True)
    assert gone == {501} and venue.cancelled == [501]
    assert [a["act"] for a in doc["actions"]] == ["oco_direction_cancel"]
    entry, _ = oco.day_entry(DAY)
    assert entry is not None and [c["order_id"] for c in entry["legs_cancelled"]] == ["501"]
    assert g.oco_block(doc, "buy_stop") is not None          # no new E8 long today
    assert g.oco_block(doc, "sell_stop") is None


def test_on_a_day_e8_set_its_own_twin_is_cancelled_and_never_re_placed() -> None:
    """v2 growth upgrade (supersedes v1's rule 8; audit must-fix 4): E8's first fill cancels
    E8's OWN twin through the direction lock -- the twin no longer waits on E8's history-driven
    twin cancel -- and the gate refuses an E8 leg against the day E8 itself set."""
    from prop import e8_gold as g
    _world("oco")
    assert oco.claim_fill("e8", e8_key(), "buy", date=DAY)["won"]
    venue, state = _E8Venue(), _e8_state()
    doc: dict = {"gold_oco": {"date": DAY, "key": e8_key()}, "actions": []}
    assert g.oco_cancel_opposite(venue, state, doc, {501, 502}, armed=True) == {502}
    assert venue.cancelled == [502]
    entry, _ = oco.day_entry(DAY)
    assert entry is not None and [c["order_id"] for c in entry["legs_cancelled"]] == ["502"]
    assert not oco.gate("e8", "sell_stop", key=e8_key(), date=DAY).allowed
    assert oco.gate("e8", "buy_stop", key=e8_key(), date=DAY).allowed
    assert oco.legs_to_cancel("e8", entry, [{"id": 1, "side": "long"},
                                            {"id": 2, "side": "short"}]) == [
        {"id": 2, "side": "short"}]


# ======================================================================== both fill in one pass

def test_two_claims_in_one_pass_exactly_one_wins() -> None:
    _world("oco")
    a = oco.claim_fill("e8", e8_key(), "buy", date=DAY)
    b = oco.claim_fill("fusion", fu_key(), "sell", date=DAY)
    assert (a["won"], b["won"]) == (True, False) and b["conflict"] and b["direction"] == "long"
    again = oco.claim_fill("fusion", fu_key(), "sell", date=DAY)
    entry, _ = oco.day_entry(DAY)
    assert entry is not None and entry["direction"] == "long" and len(entry["conflicts"]) == 1
    assert again["conflict"] and not again["won"]


def test_a_claim_without_the_lock_waits_and_claims_nothing() -> None:
    _world("oco")
    lock = xa.XACCT_DIR / "placement.lock"
    lock.write_text(json.dumps({"holder": "other-lane", "pid": os.getpid(), "host": "elsewhere",
                                "token": "t"}), encoding="utf-8")
    res = oco.claim_fill("fusion", fu_key(), "sell", date=DAY, wait_s=0.0)
    assert not res["ok"] and not res["won"] and oco.day_entry(DAY) == (None, None)


_RACER = textwrap.dedent("""
    import json, sys, time
    from pathlib import Path
    sys.path[:0] = [sys.argv[1], sys.argv[2]]
    from mt5desk import cross_account as xa
    from mt5desk import gold_oco as oco
    xa.XACCT_DIR = Path(sys.argv[3])
    go = Path(sys.argv[3]) / "go"
    while not go.exists():
        time.sleep(0.005)
    res = oco.claim_fill(sys.argv[4], sys.argv[5], sys.argv[6], date=sys.argv[7], wait_s=20.0)
    print(json.dumps(res))
""")


def test_two_processes_racing_opposite_claims_exactly_one_wins(tmp_path) -> None:
    _world("oco")
    script = tmp_path / "racer.py"
    script.write_text(_RACER, encoding="utf-8")
    env = dict(os.environ)
    procs = [subprocess.Popen([sys.executable, str(script), str(_DESK), str(_ROOT),
                               str(xa.XACCT_DIR), lane, key, side, DAY],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
             for lane, key, side in (("e8", e8_key(), "buy"), ("fusion", fu_key(), "sell"))]
    (xa.XACCT_DIR / "go").write_text("go", encoding="utf-8")
    outs = []
    for p in procs:
        out, err = p.communicate(timeout=60)
        assert p.returncode == 0, err
        outs.append(json.loads(out.strip().splitlines()[-1]))
    assert sum(1 for o in outs if o["won"]) == 1 and all(o["ok"] for o in outs)
    winner = next(o for o in outs if o["won"])
    entry, _ = oco.day_entry(DAY)
    assert entry is not None and entry["direction"] == winner["direction"]
    assert len(entry["conflicts"]) == 1


# ======================================================================== fail closed

def _tear(path: Path) -> None:
    """A body change the digest does not cover: what a half-written or hand-edited file reads as."""
    doc = json.loads(path.read_text("utf-8"))
    doc["tampered"] = True
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.mark.parametrize("damage", ["absent", "stale", "torn", "unreadable", "unreadable_side",
                                    "direction_torn", "undeclared_lane_state"])
def test_an_unreadable_stale_or_torn_state_places_nothing(damage: str) -> None:
    _world("oco")
    p = oco.lane_path("e8")
    if damage == "absent":
        p.unlink()
    elif damage == "stale":
        _flat("e8", e8_key(), now=datetime.now(tz=UTC) - timedelta(
            seconds=oco.MAX_STATE_AGE_S + 60))
    elif damage == "torn":
        _tear(p)
    elif damage == "unreadable":
        p.write_bytes(b"\xff\xfe{not json")
    elif damage == "unreadable_side":
        _flat("e8", e8_key(), positions=[{"id": 9, "side": "sideways"}])
    elif damage == "direction_torn":
        oco.claim_fill("e8", e8_key(), "buy", date=DAY)
        _tear(oco.direction_path())
    elif damage == "undeclared_lane_state":
        _mode(["e8", "fusion", "ftmo"], fusion="oco")         # FTMO declared, never published
    for side in ("buy_stop", "sell_stop"):
        v = oco.gate("fusion", side, key=fu_key(), date=DAY)
        assert not v.allowed and "fail closed" in v.why, (damage, v.why)


def test_the_staleness_bound_is_two_e8_passes() -> None:
    assert oco.MAX_STATE_AGE_S == 600.0 < xa.MAX_AGE_S
    _world("oco")
    _flat("e8", e8_key(), now=datetime.now(tz=UTC) - timedelta(seconds=540))
    assert oco.gate("fusion", "buy_stop", key=fu_key(), date=DAY).allowed


def _e8_harness(monkeypatch, tmp_path, *, fusion_positions=(), fusion_orders=()):
    import test_e8_gold_guard_and_open_risk as h

    class _V(h._Venue):
        _by_key: ClassVar[dict[str, int]] = {"XAUUSD": 6102}

        def __init__(self) -> None:
            super().__init__()
            self.placed: list[tuple] = []
            self._raw_api = SimpleNamespace(acc_id=E8_LOGIN,
                                            _credentials={"server": E8_SERVER})

        def place_stop(self, symbol, side, lot, *, price, stop, take_profit):
            self.placed.append((side, lot))
            return 500 + len(self.placed)

    class _M(h._MT5):
        def account_info(self):
            return SimpleNamespace(login=FU_LOGIN, server=FU_SERVER, trade_mode=2)

        def positions_get(self, symbol=None):
            return fusion_positions

        def orders_get(self, symbol=None):
            return fusion_orders

    h._sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(oco, "tradelocker_oco_key", REAL_TL_KEY)
    monkeypatch.setattr(oco, "mt5_oco_key", REAL_MT5_KEY)
    venue = _V()
    doc = h.g.run(venue, _M(), armed=True)
    ip = tmp_path / "intents.json"
    intents = [json.loads(ln) for ln in ip.read_text().splitlines() if ln.strip()] \
        if ip.exists() else []
    return doc, venue, intents, h


def test_e8_with_a_torn_direction_state_places_nothing_and_bills_it(monkeypatch, tmp_path):
    from research import missed_growth as mg
    _world("oco")
    oco.claim_fill("fusion", fu_key(), "sell", date="2026-10-15")
    _tear(oco.direction_path())
    doc, venue, intents, _h = _e8_harness(monkeypatch, tmp_path)
    assert venue.placed == []
    blocked = [r for r in intents if r.get("status") == "RAIL_BLOCKED"]
    assert {r["side"] for r in blocked} == {"buy_stop", "sell_stop"}
    assert all(r["rail"] == oco.RAIL and r["missed_growth_risk_usd"] > 0
               and "fail closed" in r["why"] for r in blocked)
    assert not doc["placed"]                                  # the window waits, unplaced
    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "intents.json")
    monkeypatch.setattr(mg, "E8_EXEC_INTENTS", tmp_path / "absent.jsonl")
    monkeypatch.setattr(mg, "FUSION_RAILS", tmp_path / "rails.jsonl")
    (tmp_path / "rails.jsonl").write_text("", "utf-8")
    line = mg.published_fusion_book_lines()["rails"][oco.RAIL]
    assert line["n_e8"] == 2 and line["e8_undeployed_risk_usd"] > 0


def test_e8_with_no_box_key_places_nothing_and_says_why(monkeypatch, tmp_path) -> None:
    from libs.ops import provenance as p
    _world("oco")
    monkeypatch.setenv(p.KEY_ENV, str(tmp_path / "absent.hmac"))
    doc, venue, intents, _h = _e8_harness(monkeypatch, tmp_path)
    assert venue.placed == [] and doc["gold_oco"]["key"] is None
    blocked = [r for r in intents if r.get("status") == "RAIL_BLOCKED"]
    # Both fences now name accounts by the one keyed helper, so with no box key the existing
    # two-account fence refuses first (its book cannot be named) and the OCO behind it too. On
    # r7.1+ the account rail refuses before either: the venue's own key is unresolvable, so the
    # declaration cannot be joined (`e8_account_undeclared`, billed). Every refusal names why.
    assert blocked and all(
        (r["rail"] in (oco.RAIL, "cross_account_opposite")
         and ("HMAC" in r["why"] or "no box key" in r["why"]) and "fail closed" in r["why"])
        or (r["rail"] == "e8_account_undeclared" and "unresolvable" in r["why"])
        for r in blocked)


def test_e8_in_a_readable_world_places_both_legs_and_publishes_keyed_states(
        monkeypatch, tmp_path) -> None:
    _world("oco")
    _doc, venue, _intents, h = _e8_harness(monkeypatch, tmp_path)
    assert sorted(s for s, _ in venue.placed) == ["buy", "sell"]
    st, _ = oco.read_lane("e8")
    assert st is not None and st["account_key"] == oco.oco_account_key(E8_LOGIN, E8_SERVER)
    # NO RAW LOGIN ANYWHERE THE PASS WROTE: the xacct states, the report, the state, the journal.
    texts = [f.read_text("utf-8", errors="replace") for f in xa.XACCT_DIR.iterdir()
             if f.is_file()]
    texts += [Path(p).read_text("utf-8") for p in (h.g.OUT, h.g.STATE, h.g.INTENTS)
              if Path(p).exists()]
    for login in (E8_LOGIN, FU_LOGIN):
        assert not any(str(login) in t for t in texts)


def test_the_gateway_with_a_torn_direction_state_sends_no_gold(monkeypatch, tmp_path) -> None:
    _world("oco")
    oco.claim_fill("e8", e8_key(), "buy", date=ga._DAY)
    _tear(oco.direction_path())
    rows = ga._gold_rows()
    mt5 = _GwTerminal(rows, *ga._quote(rows))
    ns = ga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    ns["main"]()
    assert mt5.sent == []
    lines = [json.loads(ln) for ln in fusion_rails.LEDGER.read_text("utf-8").splitlines()
             if ln.strip()]
    mine = [r for r in lines if r["rail"] == oco.RAIL]
    assert {r["side"] for r in mine} == {"buy_stop", "sell_stop"}
    assert all(r["risk_frac"] > 0 and "fail closed" in r["why"] for r in mine)


# ======================================================================== across the date boundary

def test_an_open_long_on_one_account_blocks_a_short_on_another_across_days() -> None:
    _world("oco")
    _flat("e8", e8_key(), positions=[{"id": 1, "side": "long", "opened_date": DAY}])
    tomorrow = (datetime.fromisoformat(DAY) + timedelta(days=1)).date().isoformat()
    assert oco.day_entry(tomorrow) == (None, None)            # no direction set tomorrow
    v = oco.gate("fusion", "sell_stop", key=fu_key(), date=tomorrow)
    assert not v.allowed and "open gold long" in v.why
    assert oco.gate("fusion", "buy_stop", key=fu_key(), date=tomorrow).allowed
    # And the reverse: Fusion's open short blocks E8's long.
    _flat("e8", e8_key())
    _flat("fusion", fu_key(), positions=[{"id": 2, "side": "short", "opened_date": DAY}])
    assert not oco.gate("e8", "buy_stop", key=e8_key(), date=tomorrow).allowed
    assert oco.gate("e8", "sell_stop", key=e8_key(), date=tomorrow).allowed


def test_a_resting_opposite_entry_on_another_account_blocks_too() -> None:
    _world("oco")
    _flat("e8", e8_key(), orders=[{"id": 5, "side": "sell"}])
    assert not oco.gate("fusion", "buy_stop", key=fu_key(), date=DAY).allowed


# ======================================================================== fallback mode

def test_fallback_fusion_waits_for_e8s_fill_then_copies_its_direction(
        monkeypatch, tmp_path) -> None:
    oco.MODE_FILE.unlink()                                    # no mode file = the default
    _flat("e8", e8_key())
    _flat("fusion", fu_key())
    assert oco.configured_mode("fusion") == "fallback"
    v = oco.gate("fusion", "buy_stop", key=fu_key(), date=ga._DAY)
    assert not v.allowed and "no E8 fill yet" in v.why
    rows = ga._gold_rows()
    mt5 = _GwTerminal(rows, *ga._quote(rows))
    ns = ga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    ns["main"]()
    assert mt5.sent == []                                     # waits: nothing placed
    # E8 fills short; its sibling is gone; Fusion now places only the short.
    _flat("e8", e8_key(), positions=[{"id": 3, "side": "short", "opened_date": ga._DAY}])
    assert oco.claim_fill("e8", e8_key(), "sell", date=ga._DAY)["won"]
    ns["_state_file"].write_text(json.dumps({"armed": True, "brackets": {}, "position": None,
                                             "last_bracket_date": None}), "utf-8")
    ns["main"]()
    assert [r["type"] for r in mt5.sent] == [mt5.ORDER_TYPE_SELL_STOP]


def test_fallback_copies_only_e8_and_oco_is_not_taken_unproven() -> None:
    _world("fallback")
    oco.claim_fill("fusion", fu_key(), "buy", date=DAY)
    v = oco.gate("fusion", "buy_stop", key=fu_key(), date=DAY)
    assert not v.allowed and "copies only E8" in v.why
    # Full OCO asked for, but a lane runs older code (no protocol): fallback stands.
    _mode(["e8", "fusion"], fusion="oco")
    body = json.loads(oco.lane_path("e8").read_text("utf-8"))
    body.pop("digest")
    body["protocol"] = 0
    oco._write(oco.lane_path("e8"), body)
    v = oco.gate("fusion", "buy_stop", key=fu_key(), date=DAY)
    assert v.mode == "fallback" and not v.allowed


def test_an_undeclared_lane_and_an_unknown_gateway_lane_place_nothing(monkeypatch) -> None:
    _world("oco")
    assert not oco.gate("ftmo", "buy_stop", key=fu_key(), date=DAY).allowed
    monkeypatch.setenv(oco.LANE_ENV, "e8")
    assert oco.gateway_lane() is None
    monkeypatch.setenv(oco.LANE_ENV, "ftmo")
    assert oco.gateway_lane() == "ftmo"
    monkeypatch.delenv(oco.LANE_ENV)
    assert oco.gateway_lane() == "fusion"


# ======================================================================== the day boundary

def test_the_trading_day_rolls_over_on_the_server_clock() -> None:
    eod = datetime(2026, 10, 21, 23, 59, 59, tzinfo=UTC).timestamp()
    assert oco.trading_date(eod) == "2026-10-21" and oco.trading_date(eod + 1) == "2026-10-22"
    assert oco.ms_trading_date(int((eod + 1) * 1000)) == "2026-10-22"
    assert oco.ms_trading_date(None) is None and oco.ms_trading_date(0) is None
    _world("oco")
    oco.claim_fill("e8", e8_key(), "buy", date="2026-10-21")
    assert not oco.gate("fusion", "sell_stop", key=fu_key(), date="2026-10-21").allowed
    assert oco.gate("fusion", "sell_stop", key=fu_key(), date="2026-10-22").allowed
    # Yesterday's position claims nothing today; today's does.
    res = oco.observe_fills("fusion", fu_key(), [
        {"id": 1, "side": "short", "opened_date": "2026-10-21"}], date="2026-10-22")
    assert res == [] and oco.day_entry("2026-10-22") == (None, None)
    # Days older than KEEP_DAYS leave the file at the next write.
    oco.claim_fill("e8", e8_key(), "buy", date="2026-11-05")
    days, _ = oco.read_directions()
    assert days is not None and set(days) == {"2026-11-05"}


def test_mt5_and_tradelocker_rows_date_their_positions_on_the_broker_clock() -> None:
    t = int(datetime(2026, 10, 21, 7, 5, tzinfo=UTC).timestamp())
    term = SimpleNamespace(
        positions_get=lambda: (SimpleNamespace(symbol="XAUUSD+", type=0, ticket=1, time=t),
                               SimpleNamespace(symbol="EURUSD", type=1, ticket=2, time=t)),
        orders_get=lambda: (SimpleNamespace(symbol="XAUUSD", type=5, ticket=3),))
    pos, ords = oco.mt5_gold_rows(term)
    assert pos == [{"id": 1, "side": "long", "opened_date": "2026-10-21"}]
    assert ords == [{"id": 3, "side": "short"}]
    tl_pos = [{"id": 9, "tradableInstrumentId": 6102, "side": "buy", "stopLossId": 90,
               "openDate": t * 1000}]
    tl_ord = [{"id": 90, "tradableInstrumentId": 6102, "side": "sell"},     # its protective stop
              {"id": 91, "tradableInstrumentId": 6102, "side": "sell"},     # a resting entry
              {"id": 92, "tradableInstrumentId": 7000, "side": "sell"}]     # another instrument
    pos, ords = oco.tradelocker_gold_rows(tl_pos, tl_ord, 6102)
    assert pos == [{"id": 9, "side": "buy", "opened_date": "2026-10-21"}]
    assert ords == [{"id": 91, "side": "sell"}]


def test_no_raw_login_in_any_written_state() -> None:
    _mode(["e8", "fusion", "ftmo"], fusion="oco", ftmo="fallback")
    ft_key = oco.oco_account_key(FT_LOGIN, FT_SERVER)
    for lane, key in (("e8", e8_key()), ("fusion", fu_key()), ("ftmo", ft_key)):
        _flat(lane, key, positions=[{"id": 1, "side": "long", "opened_date": DAY}])
        oco.claim_fill(lane, key, "buy", date=DAY)
        oco.note_cancelled(DAY, lane, key, 77, "sell")
    blob = "".join(f.read_text("utf-8") for f in xa.XACCT_DIR.iterdir()
                   if f.is_file() and f.name.startswith("gold_"))
    assert blob
    for login in (E8_LOGIN, FU_LOGIN, FT_LOGIN):
        assert str(login) not in blob


# ======================================================================== v2: blind cancels all

def test_cancel_plan_cancels_every_leg_when_the_direction_state_is_unreadable() -> None:
    legs = [{"id": 1, "side": "long"}, {"id": 2, "side": "short"}]
    plan, why = oco.cancel_plan("fusion", None, "the gold direction state is torn", legs)
    assert plan == legs and "unreadable" in why
    plan, _ = oco.cancel_plan("fusion", None, None, legs)
    assert plan == []                                         # readable, no direction yet


def test_the_gateway_with_a_torn_direction_state_cancels_every_resting_gold_leg(
        monkeypatch, tmp_path) -> None:
    _world("oco")
    oco.claim_fill("e8", e8_key(), "buy", date=DAY)
    _tear(oco.direction_path())
    rows = ga._gold_rows()
    mt5 = _GwTerminal(rows, *ga._quote(rows))
    mt5.pending = [_gw_order(11, 4), _gw_order(12, 5),
                   SimpleNamespace(ticket=13, symbol="XAUUSD", type=4, magic=0,
                                   price_open=2000.0, comment="manual")]
    ns = ga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    gone = ns["cancel_gold_against_direction"]({"armed": True}, "fusion", fu_key(), DAY)
    assert gone == 2 and [o.ticket for o in mt5.pending] == [13]     # manual never touched


def test_e8_with_a_torn_direction_state_cancels_its_resting_legs() -> None:
    from prop import e8_gold as g
    _world("oco")
    oco.claim_fill("fusion", fu_key(), "sell", date=DAY)
    _tear(oco.direction_path())
    venue, state = _E8Venue(), _e8_state()
    doc: dict = {"gold_oco": {"date": DAY, "key": e8_key()}, "actions": []}
    assert g.oco_cancel_opposite(venue, state, doc, {501, 502}, armed=True) == {501, 502}
    assert sorted(venue.cancelled) == [501, 502] and doc["gold_oco_unreadable"]
    assert any("blind" in a for a in doc["alerts"])


def test_a_leg_that_filled_before_its_cancel_is_not_noted_as_cancelled(
        monkeypatch, tmp_path) -> None:
    _world("oco")
    assert oco.claim_fill("e8", e8_key(), "buy", date=DAY)["won"]
    rows = ga._gold_rows()

    class _Filling(_GwTerminal):
        def order_send(self, req: dict) -> SimpleNamespace:
            if req.get("action") == self.TRADE_ACTION_REMOVE:
                # The sell stop filled between the read and the remove.
                self.pending = [o for o in self.pending if int(o.ticket) != int(req["order"])]
                self.positions = [SimpleNamespace(ticket=12, identifier=12, symbol="XAUUSD",
                                                  type=1, magic=MAGIC, volume=0.05,
                                                  comment="DWgold_asia", time=0)]
                return SimpleNamespace(retcode=10013, order=req["order"], comment="filled")
            return super().order_send(req)

        def positions_get(self, symbol=None):
            return list(getattr(self, "positions", []))
    mt5 = _Filling(rows, *ga._quote(rows))
    mt5.pending = [_gw_order(12, 5)]
    ns = ga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    assert ns["cancel_gold_against_direction"]({"armed": True}, "fusion", fu_key(), DAY) == 0
    entry, _ = oco.day_entry(DAY)
    assert entry is not None and entry["legs_cancelled"] == []


# ======================================================================== v2: flatten

def test_positions_to_flatten_takes_only_todays_wrong_side_fills() -> None:
    entry = {"direction": "long"}
    pos = [{"id": 1, "side": "short", "opened_date": DAY},
           {"id": 2, "side": "long", "opened_date": DAY},
           {"id": 3, "side": "short", "opened_date": "2026-10-20"},     # carried: not touched
           {"id": 4, "side": "sell", "opened_date": None}]              # undated: today's
    assert [p["id"] for p in oco.positions_to_flatten(entry, pos, date=DAY)] == [1, 4]
    assert oco.positions_to_flatten(None, pos, date=DAY) == []


def test_the_gateway_flattens_its_own_wrong_side_gold_fill_and_alerts_a_manual_one(
        monkeypatch, tmp_path) -> None:
    _world("oco")
    assert oco.claim_fill("e8", e8_key(), "buy", date=DAY)["won"]
    rows = ga._gold_rows()
    epoch = int(datetime.fromisoformat(DAY + "T08:00:00+00:00").timestamp())

    class _Pos(_GwTerminal):
        def positions_get(self, symbol=None):
            return [SimpleNamespace(ticket=21, symbol="XAUUSD", type=1, magic=MAGIC,
                                    volume=0.05, comment="DWgold_asia", time=epoch),
                    SimpleNamespace(ticket=22, symbol="XAUUSD", type=1, magic=0,
                                    volume=0.10, comment="", time=epoch),
                    SimpleNamespace(ticket=23, symbol="XAUUSD", type=0, magic=MAGIC,
                                    volume=0.05, comment="DWgold_asia", time=epoch)]
    mt5 = _Pos(rows, *ga._quote(rows))
    ns = ga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    assert ns["flatten_gold_against_direction"]({"armed": True}, "fusion", DAY) == 1
    deals = [r for r in mt5.sent if r.get("action") == mt5.TRADE_ACTION_DEAL]
    assert [(d["position"], d["type"]) for d in deals] == [(21, mt5.ORDER_TYPE_BUY)]
    assert any("MANUAL" in ln for ln in ns["log"].__self__)


def test_e8_flattens_its_own_twin_fill_against_the_direction() -> None:
    from prop import e8_gold as g
    _world("oco")
    assert oco.claim_fill("e8", e8_key(), "buy", date=DAY)["won"]
    ms = int(datetime.fromisoformat(DAY + "T08:00:00+00:00").timestamp() * 1000)

    class _V(_E8Venue):
        closed: ClassVar[list[int]] = []

        def close(self, position_id: int) -> bool:
            self.closed.append(int(position_id))
            return True
    venue, state = _V(), _e8_state()
    state["windows"]["asia"]["position_id"] = 9001                    # the buy stop's position
    doc: dict = {"gold_oco": {"date": DAY, "key": e8_key()}, "actions": []}
    xau = [{"id": 9001, "side": "buy", "openDate": ms},
           {"id": 9002, "side": "sell", "openDate": ms},             # the twin, filled
           {"id": 9003, "side": "sell", "openDate": ms}]             # not this lane's
    out = g.oco_flatten_opposite(venue, state, doc, xau, {502: 9002}, armed=True)
    assert out == {9002} and venue.closed == [9002]
    assert [a["act"] for a in doc["actions"]] == ["oco_direction_flatten"]
    assert len([a for a in doc["alerts"] if "against" in a]) == 2


# ======================================================================== v2: the identity page

def test_a_missing_key_pages_once_dedupes_and_pages_the_recovery(monkeypatch) -> None:
    t0 = datetime(2026, 10, 21, 6, 0, tzinfo=UTC)
    oco.PAGES.clear()
    assert oco.page_identity("fusion", "the box-held HMAC account key is absent", now=t0)["sent"]
    assert oco.page_identity("fusion", "the box-held HMAC account key is absent",
                             now=t0 + timedelta(hours=1))["reason"] == "deduplicated"
    assert oco.page_identity("fusion", "the box-held HMAC account key is absent",
                             now=t0 + timedelta(hours=7))["sent"]
    assert oco.page_identity("fusion", None, now=t0 + timedelta(hours=8))["reason"] == "recovered"
    assert oco.page_identity("fusion", None, now=t0 + timedelta(hours=9))["sent"] is False
    assert len(oco.PAGES) == 3 and "fusion" in oco.PAGES[0][0]
    from libs.ops.alert_ledger import AlertLedger
    led = AlertLedger(Path(oco.ALERT_ROOT) / "data" / "alert_ledger.json")
    assert not led.alerts[f"{oco.ALERT_ID}:fusion"].open
    monkeypatch.setattr(oco, "PAGER", lambda t, b: 1 / 0)
    assert "error" in oco.page_identity("e8", "boom", now=t0)       # never raises


def test_e8_with_no_box_key_pages(monkeypatch, tmp_path) -> None:
    from libs.ops import provenance as p
    _world("oco")
    oco.PAGES.clear()
    monkeypatch.setenv(p.KEY_ENV, str(tmp_path / "absent.hmac"))
    doc, venue, _intents, _h = _e8_harness(monkeypatch, tmp_path)
    assert venue.placed == [] and any("e8" in t for t, _b in oco.PAGES)
    assert any("identity" in a for a in doc.get("alerts") or [])
    assert str(E8_LOGIN) not in str(oco.PAGES)


# ======================================================================== v2: every refusal bills

def test_a_retry_refusal_bills_dollars_never_none() -> None:
    from prop import e8_gold as g
    assert g.leg_missed_usd({"risk_usd": 412.5}) == 412.5
    assert g.leg_missed_usd({"lot": 0.3, "price": 4340.0, "sl": 4320.0}) == pytest.approx(600.0)
    assert g.leg_missed_usd({}) == 0.0


def test_the_gateways_gold_lines_carry_their_dollars_into_missed_growth(
        monkeypatch, tmp_path) -> None:
    from research import missed_growth as mg
    ns: dict[str, Any] = {}
    exec(compile(ga.ast.Module(body=[n for n in ga._GW_TREE.body
                                     if getattr(n, "name", None) == "_missed_usd"],
                               type_ignores=[]), "gateway", "exec"), ns)
    assert ns["_missed_usd"](100_000.0, 0.0075) == 750.0 and ns["_missed_usd"](None, 0.1) is None
    rails = tmp_path / "rails.jsonl"
    rails.write_text("\n".join(json.dumps(r) for r in (
        {"rail": oco.RAIL, "lot": 0.05, "risk_frac": 0.0075, "missed_growth_risk_usd": 750.0},
        {"rail": oco.RAIL, "lot": 0.05, "risk_frac": 0.0075, "missed_growth_risk_usd": None},
        {"rail": "cross_account_opposite", "lot": 0.05, "risk_frac": 0.0075,
         "missed_growth_risk_usd": 750.0})) + "\n", "utf-8")
    monkeypatch.setattr(mg, "FUSION_RAILS", rails)
    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "absent1.jsonl")
    monkeypatch.setattr(mg, "E8_EXEC_INTENTS", tmp_path / "absent2.jsonl")
    (tmp_path / "absent1.jsonl").write_text("", "utf-8")
    (tmp_path / "absent2.jsonl").write_text("", "utf-8")
    out = mg.published_fusion_book_lines()["rails"]
    assert out[oco.RAIL]["fusion_undeployed_risk_usd"] == 750.0
    assert out[oco.RAIL]["n_unpriced"] == 1
    assert out["cross_account_opposite"]["fusion_undeployed_risk_usd"] == 750.0
