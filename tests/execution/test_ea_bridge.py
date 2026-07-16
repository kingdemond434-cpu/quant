"""Integration tests for the MT5 EA file-queue bridge, against a simulated EA.

The real ``.mq5`` cannot run under pytest, so ``FakeEA`` reproduces the EA's file protocol exactly
(read commands/<id>.cmd -> write responses/<id>.resp + state/*). This verifies the Python side and
the wire contract end-to-end, including idempotency, fail-closed timeout, and ExecutionEngine drive.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from migrations import MIGRATIONS

from libs.execution.broker import OrderRequest
from libs.execution.ea_bridge import EABridge, dump_record, load_record
from libs.execution.engine import ExecStatus, ExecutionEngine
from libs.execution.errors import BrokerTimeout
from libs.execution.journal import TradeJournal
from libs.store.connection import Database
from libs.store.migrations import run_migrations
from libs.store.registries import RiskRegistry
from libs.store.trading import OrderStore


class FakeEA:
    """A faithful in-process stand-in for QuantPlatformExecutor.mq5's file protocol."""

    def __init__(self, comm_dir: Path, *, fill_price: float = 1.10) -> None:
        self.root = comm_dir
        self.fill_price = fill_price
        self._ticket = 1000
        self._pos: dict[str, float] = {}

    def step(self) -> None:
        cmd_dir = self.root / "commands"
        resp_dir = self.root / "responses"
        for cmd in sorted(cmd_dir.glob("*.cmd")):
            cid = cmd.stem
            resp = resp_dir / f"{cid}.resp"
            if resp.exists():
                cmd.unlink(missing_ok=True)
                continue
            rec = load_record(cmd.read_text("utf-8"))
            self._handle(rec, resp)
            cmd.unlink(missing_ok=True)
        self._write_state()

    def _handle(self, rec: dict[str, str], resp: Path) -> None:
        kind = rec.get("type", "")
        out: dict[str, object] = {"id": rec.get("id", ""), "ticket": 0, "fill_price": 0.0,
                                  "fill_volume": 0.0, "message": ""}
        if kind == "MARKET":
            self._ticket += 1
            qty = float(rec.get("volume", "0"))
            signed = qty if rec.get("side") == "buy" else -qty
            self._pos[rec["symbol"]] = self._pos.get(rec["symbol"], 0.0) + signed
            out |= {"status": "filled", "ticket": self._ticket, "fill_price": self.fill_price,
                    "fill_volume": qty, "message": "market filled"}
        elif kind == "PING":
            out["status"] = "ack"
        elif kind == "FLATTEN_ALL":
            self._pos.clear()
            out["status"] = "flat"
        elif kind == "CLOSE":
            out["status"] = "closed"
        elif kind == "MODIFY":
            out["status"] = "modified"
        else:
            out["status"] = "error"
        resp.write_text(dump_record(out), "utf-8")

    def _write_state(self) -> None:
        state = self.root / "state"
        lines = [f"{s}|{q}|{self.fill_price}" for s, q in self._pos.items() if q != 0.0]
        (state / "positions.state").write_text("\n".join(lines), "utf-8")
        beat = datetime.now(UTC).strftime("%Y.%m.%d %H:%M:%S")
        (state / "ea_heartbeat").write_text(beat, "utf-8")


@pytest.fixture
def comm(tmp_path: Path) -> Path:
    return tmp_path / "quant_ea"


def _req(key: str = "idem-1", **over: object) -> OrderRequest:
    base: dict[str, object] = {
        "idempotency_key": key, "instrument": "EURUSD", "side": "buy", "qty": 0.1,
        "order_type": "market", "risk_approval_id": "appr-1",
    }
    base.update(over)
    return OrderRequest(**base)  # type: ignore[arg-type]


def test_market_order_round_trips(comm: Path) -> None:
    ea = FakeEA(comm, fill_price=1.2345)
    bridge = EABridge(comm, on_poll=ea.step)
    result = bridge.place_order(_req())
    assert result.status == "filled"
    assert result.fill_price == 1.2345
    assert result.broker_order_id > 0
    assert bridge.get_positions()[0].instrument == "EURUSD"


def test_idempotent_no_double_fill(comm: Path) -> None:
    ea = FakeEA(comm)
    bridge = EABridge(comm, on_poll=ea.step)
    first = bridge.place_order(_req("dup"))
    second = bridge.place_order(_req("dup"))  # same id -> existing response reused
    assert first.broker_order_id == second.broker_order_id
    assert bridge.get_positions()[0].qty == 0.1  # filled once


def test_timeout_fails_closed(comm: Path) -> None:
    bridge = EABridge(comm, timeout_s=0.05, poll_s=0.01)  # no EA responding
    with pytest.raises(BrokerTimeout):
        bridge.place_order(_req("lonely"))


def test_requires_risk_approval(comm: Path) -> None:
    bridge = EABridge(comm, on_poll=FakeEA(comm).step)
    with pytest.raises(Exception, match="risk_approval_id"):
        bridge.place_order(_req(risk_approval_id=""))


def test_flatten_all_and_emergency_flag(comm: Path) -> None:
    ea = FakeEA(comm)
    bridge = EABridge(comm, on_poll=ea.step)
    bridge.place_order(_req("o1"))
    assert bridge.flatten_all() is True
    assert (comm / "EMERGENCY_STOP").exists()
    assert bridge.get_positions() == []


def test_heartbeat_liveness(comm: Path) -> None:
    ea = FakeEA(comm)
    bridge = EABridge(comm, on_poll=ea.step)
    bridge.write_heartbeat()
    assert (comm / "state" / "py_heartbeat").exists()
    ea.step()  # EA writes its heartbeat
    assert bridge.ea_alive(max_silence_s=60.0) is True
    assert bridge.ea_alive(max_silence_s=-1.0) is False  # nothing is fresh enough


def test_cancel_and_modify(comm: Path) -> None:
    bridge = EABridge(comm, on_poll=FakeEA(comm).step)
    assert bridge.cancel_order(12345) is True
    assert bridge.modify_sltp(12345, sl=1.0, tp=1.2) is True


def test_execution_engine_drives_ea_bridge(comm: Path) -> None:
    # The unchanged ExecutionEngine treats the EA bridge as just another BrokerGateway.
    db = Database(comm.parent / "sor.sqlite")
    run_migrations(db, MIGRATIONS)
    try:
        approval = RiskRegistry(db).create_approval(target_ref="intent_ea").id
        engine = ExecutionEngine(OrderStore(db), EABridge(comm, on_poll=FakeEA(comm).step),
                                 TradeJournal(db))
        result = engine.submit_order(_req("eng-1", risk_approval_id=approval))
        assert result.status is ExecStatus.FILLED
        assert OrderStore(db).get_position("EURUSD") is not None
    finally:
        db.close()
