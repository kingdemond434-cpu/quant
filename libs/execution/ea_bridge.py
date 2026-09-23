"""File-queue bridge to the MT5 Execution EA — Python stays the brain, the EA only executes.

Transport is a directory of atomic ``key=value`` files in the MT5 *common files* folder (no DLLs,
no sockets): Python writes ``commands/<id>.cmd``; the EA writes ``responses/<id>.resp`` and
refreshes ``state/*``. This implements the existing :class:`BrokerGateway` protocol, so the
unchanged :class:`ExecutionEngine` drives the EA like any other venue — no trading logic lives here
or in the EA. Idempotent by command id; fails closed (ambiguous timeout -> ``BrokerTimeout`` ->
reconcile, never an assumed fill).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from libs.core.ids import generate_id
from libs.core.time import to_iso8601, utcnow
from libs.execution.broker import BrokerOrderResult, BrokerPosition, OrderRequest
from libs.execution.errors import BrokerError, BrokerTimeout

_FILLED = {"filled"}
_DEAD = {"rejected", "error", "blocked"}
_HB_FMT = "%Y.%m.%d %H:%M:%S"  # MT5 datetime format (GMT); both sides agree on this


def dump_record(record: Mapping[str, object]) -> str:
    """Serialize a flat record to ``key=value`` lines (MQL-friendly; no nesting)."""
    return "".join(f"{k}={v}\n" for k, v in record.items())


def load_record(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)  # atomic on the same filesystem; EA never reads a partial file


class EABridge:
    """Drives the MT5 Execution EA over the atomic file queue (a ``BrokerGateway``)."""

    def __init__(
        self,
        comm_dir: Path,
        *,
        magic: int = 990001,
        timeout_s: float = 5.0,
        poll_s: float = 0.05,
        on_poll: Callable[[], None] | None = None,
    ) -> None:
        self.root = Path(comm_dir)
        self.commands = self.root / "commands"
        self.responses = self.root / "responses"
        self.state = self.root / "state"
        for d in (self.commands, self.responses, self.state):
            d.mkdir(parents=True, exist_ok=True)
        self.magic = magic
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self._on_poll = on_poll  # test/advance hook; None in production (EA writes async)

    # ----------------------------------------------------------------- commands
    def _send(self, command: Mapping[str, object]) -> dict[str, str]:
        cid = str(command["id"])
        resp_path = self.responses / f"{cid}.resp"
        if resp_path.exists():
            return load_record(resp_path.read_text("utf-8"))  # idempotent: already answered
        cmd_path = self.commands / f"{cid}.cmd"
        if not cmd_path.exists():
            _atomic_write(cmd_path, dump_record({**command, "magic": self.magic,
                                                 "ts": to_iso8601(utcnow())}))
        deadline = time.monotonic() + self.timeout_s
        while True:
            if self._on_poll is not None:
                self._on_poll()
            if resp_path.exists():
                return load_record(resp_path.read_text("utf-8"))
            if time.monotonic() >= deadline:
                raise BrokerTimeout(f"no EA response for command {cid} within {self.timeout_s}s")
            time.sleep(self.poll_s)

    def place_order(self, request: OrderRequest) -> BrokerOrderResult:
        if not request.risk_approval_id:
            raise BrokerError("fail-closed: order requires a risk_approval_id")
        resp = self._send({
            "id": request.idempotency_key,
            "type": "PENDING" if request.order_type != "market" else "MARKET",
            "symbol": request.instrument, "side": request.side, "volume": request.qty,
            "order_type": request.order_type, "price": request.price or 0.0,
        })
        return self._to_result(request.idempotency_key, resp)

    def cancel_order(self, broker_order_id: int) -> bool:
        resp = self._send({"id": f"cancel-{broker_order_id}", "type": "CLOSE",
                           "ticket": broker_order_id})
        return resp.get("status", "") in (_FILLED | {"ack", "closed"})

    def modify_sltp(self, ticket: int, *, sl: float, tp: float) -> bool:
        resp = self._send({"id": f"modify-{ticket}", "type": "MODIFY", "ticket": ticket,
                           "sl": sl, "tp": tp})
        return resp.get("status", "") in {"ack", "modified", "filled"}

    def flatten_all(self) -> bool:
        """Emergency flatten — also drops the EA-side EMERGENCY_STOP flag file."""
        _atomic_write(self.root / "EMERGENCY_STOP", to_iso8601(utcnow()))
        resp = self._send({"id": generate_id("flatten"), "type": "FLATTEN_ALL"})
        return resp.get("status", "") in {"ack", "filled", "flat"}

    # ----------------------------------------------------------------- reads
    def get_positions(self) -> list[BrokerPosition]:
        path = self.state / "positions.state"
        if not path.exists():
            return []
        positions: list[BrokerPosition] = []
        for line in path.read_text("utf-8").splitlines():
            parts = line.split("|")
            if len(parts) not in (3, 4) or float(parts[1]) == 0.0:
                continue
            # v1.10 EA writes SYMBOL|qty|avg|magic; scope to our magic when present
            if len(parts) == 4 and int(parts[3]) != self.magic:
                continue
            positions.append(
                BrokerPosition(instrument=parts[0], qty=float(parts[1]), avg_price=float(parts[2]))
            )
        return positions

    def get_order(self, client_order_id: str) -> BrokerOrderResult | None:
        path = self.responses / f"{client_order_id}.resp"
        if not path.exists():
            return None
        return self._to_result(client_order_id, load_record(path.read_text("utf-8")))

    def account_state(self) -> dict[str, str]:
        path = self.state / "account.state"
        return load_record(path.read_text("utf-8")) if path.exists() else {}

    # ----------------------------------------------------------------- heartbeat
    def write_heartbeat(self) -> None:
        """Write the Python liveness beat in the MT5 datetime format the EA parses."""
        _atomic_write(self.state / "py_heartbeat", datetime.now(UTC).strftime(_HB_FMT))

    def read_ea_heartbeat_epoch(self) -> float | None:
        path = self.state / "ea_heartbeat"
        if not path.exists():
            return None
        try:
            stamp = path.read_text("utf-8").strip()
            return datetime.strptime(stamp, _HB_FMT).replace(tzinfo=UTC).timestamp()
        except ValueError:
            return None

    def ea_alive(self, *, max_silence_s: float) -> bool:
        """Whether the EA heartbeat is fresh (fail-closed: missing/unparseable -> not alive)."""
        beat = self.read_ea_heartbeat_epoch()
        return beat is not None and (time.time() - beat) <= max_silence_s

    @staticmethod
    def _to_result(cid: str, resp: Mapping[str, str]) -> BrokerOrderResult:
        status = resp.get("status", "error")
        normalized = "filled" if status in _FILLED else ("rejected" if status in _DEAD else status)
        return BrokerOrderResult(
            client_order_id=cid,
            broker_order_id=int(float(resp.get("ticket", "0") or "0")),
            status=normalized,
            filled_qty=float(resp.get("fill_volume", "0") or "0"),
            fill_price=float(resp["fill_price"]) if resp.get("fill_price") else None,
            deal_id=int(float(resp.get("ticket", "0") or "0")) or None,
            message=resp.get("message", ""),
        )
