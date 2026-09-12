"""THE SECOND VENUE THIS DESK HAS EVER HAD, and the first that is not MetaTrader.

E8 Pro account 2478877 is provisioned on **TradeLocker**. Every order this desk has ever sent
went through the `MetaTrader5` package into a local terminal on the Windows box; that account has
no terminal and never will. This module is the adapter, and it is deliberately nothing more than
one: it speaks TradeLocker and it speaks the desk's own vocabulary, and the DECISIONS stay where
they already are.

WHAT THIS FILE MAY AND MAY NOT DO -- the line is the whole point of having it.

    MAY   resolve a desk symbol to a venue instrument, read a quote, read account equity,
          place an order with a stop, list and close positions, and report what happened.
    MAY NOT decide a lot, a direction, an entry, a stop, or whether a sleeve trades at all.

Sizing belongs to `mt5desk.decision_core` and nothing here duplicates a line of it. The desk has
already paid for the other arrangement: `bracket_lane_lot` exists because two sites computed "the
lot" from two expressions and disagreed silently on the money path. A second venue is exactly how
that defect class comes back, so the adapter takes a lot as an ARGUMENT and has no opinion.

CREDENTIALS NEVER APPEAR HERE, IN A LOG, OR IN AN ARTIFACT. They are read from
`data/secrets/e8_tradelocker.json` (gitignored, never leaves the box) or from the environment,
and this module has no code path that prints, returns, or serialises one. The desk's standing
rule is that `data/secrets/**` never leaves the box and no tool ever prints a key; an adapter
that logs its own login is how that rule gets broken by accident.

THE ARENA IS NOT THE LIVE BOOK'S, AND THE GUARD IS SEPARATE. E8 Pro's rules -- 10% profit target,
10% STATIC drawdown, 2.5% daily drawdown, 2% daily profit cap with the excess stripped at
rollover -- live in `prop/e8_guard.py`, which is the only thing allowed to refuse an order for a
prop reason. Keeping the guard out of the adapter means the adapter can be tested against a fake
API and the guard against a fake account, instead of neither being testable.

Artifact: desks/mt5/reports/PROP_VENUE.json  (connection, instrument map, account state)
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "PROP_VENUE.json"

#: Gitignored, box-only. The loader also accepts the environment so a session can run without a
#: file existing; neither path is ever echoed.
SECRET = ROOT / "data" / "secrets" / "e8_tradelocker.json"

Side = Literal["buy", "sell"]


class VenueError(RuntimeError):
    """A venue refusal, with the secret-bearing detail already stripped by the raiser."""


@dataclass(frozen=True)
class Credentials:
    """Loaded, never logged. `__repr__` is overridden because a dataclass would print them."""
    environment: str
    username: str
    password: str
    server: str

    def __repr__(self) -> str:                      # pragma: no cover - trivial, but load-bearing
        return f"Credentials(environment={self.environment!r}, username=<redacted>, " \
               f"password=<redacted>, server={self.server!r})"

    __str__ = __repr__


def load_credentials(path: Path = SECRET) -> Credentials:
    """File first, environment second, and a refusal that names no value.

    The refusal deliberately reports WHICH field is missing and never what any field contains,
    because the most common way a credential reaches a log is a helpful error message.
    """
    raw: dict[str, Any] = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise VenueError(f"{path.name} is unreadable ({type(exc).__name__})") from None
    env = {
        "environment": os.environ.get("E8_TL_ENV"),
        "username": os.environ.get("E8_TL_USERNAME"),
        "password": os.environ.get("E8_TL_PASSWORD"),
        "server": os.environ.get("E8_TL_SERVER"),
    }
    got = {k: (raw.get(k) or env.get(k)) for k in ("environment", "username", "password", "server")}
    missing = sorted(k for k, v in got.items() if not v)
    if missing:
        raise VenueError(
            f"no E8 credentials: missing {missing}. Put them in data/secrets/e8_tradelocker.json "
            "(gitignored) or set E8_TL_ENV / E8_TL_USERNAME / E8_TL_PASSWORD / E8_TL_SERVER")
    return Credentials(environment=str(got["environment"]), username=str(got["username"]),
                       password=str(got["password"]), server=str(got["server"]))


#: The desk names instruments the way MetaTrader does. TradeLocker's names are close but not
#: identical and the differences are per-broker, so the map is BUILT from the venue's own
#: catalogue at connect time and never hard-coded -- a hard-coded table is how a rename becomes a
#: silently unhedged position. Only the normalisation rule lives here.
def _normalise(symbol: str) -> str:
    """Fold a symbol to a comparison key: upper case, no separators, no venue suffix.

    `XAUUSD`, `XAU/USD`, `XAUUSD.pro`, `XAUUSD+` and `xauusd` are one instrument; the desk's
    universe and the venue's catalogue disagree about which spelling is canonical, and neither is
    wrong.

    THE `+` IS NOT HYPOTHETICAL. Measured on the live E8 account 2026-09-12: every one of its 46
    instruments is suffixed -- `EURUSD+`, `XAUUSD+`, `AUDNZD+` -- and without folding it the
    adapter matched ZERO of the desk's 29 certified symbols while reporting a healthy connection
    and a full catalogue. That is the exact failure this function exists to prevent, and it got
    through because the suffix set was written from the venues the desk already knew.
    """
    s = symbol.upper()
    for sep in ("/", "-", "_", " "):
        s = s.replace(sep, "")
    if "." in s:
        s = s.split(".", 1)[0]
    # Trailing venue markers: `+` (E8/TradeLocker), and `m`/`c`/`pro` style suffixes are NOT
    # stripped -- `EURUSDm` on some brokers is a genuinely different contract size, and folding
    # those would map two instruments onto one key, which is worse than failing to match.
    return s.rstrip("+")


class TradeLockerVenue:
    """A thin, testable wrapper over the official `tradelocker` SDK.

    `api` is injected rather than constructed when given, so every test in
    `tests/test_tradelocker_venue.py` runs against a fake with no network and no credentials. An
    adapter that can only be exercised by connecting to a live funded account is an adapter whose
    first real test is a real order.
    """

    def __init__(self, api: Any | None = None, creds: Credentials | None = None) -> None:
        self._raw_api = api
        self._creds = creds
        self._by_key: dict[str, int] = {}
        self._details: dict[int, dict[str, Any]] = {}

    # ------------------------------------------------------------------ connection
    @property
    def _api(self) -> Any:
        """The live SDK handle, or a refusal NAMING the omission.

        Typed as a property rather than an optional attribute so every call site is statically
        known to have a handle: with `Any | None` the type checker flags each of the eight uses
        below, and the honest fix is one guarded accessor rather than eight `assert`s that would
        also be the only thing standing between an unconnected venue and a live order.
        """
        if self._raw_api is None:
            raise VenueError("venue not connected: call connect() first")
        return self._raw_api

    def connect(self) -> TradeLockerVenue:
        if self._raw_api is None:
            creds = self._creds or load_credentials()
            try:
                from tradelocker import TLAPI
            except ImportError as exc:                              # pragma: no cover - env
                raise VenueError(f"the tradelocker SDK is not installed ({exc})") from None
            try:
                self._raw_api = TLAPI(environment=creds.environment, username=creds.username,
                                      password=creds.password, server=creds.server,
                                      log_level="warning")
            except Exception as exc:
                # THE EXCEPTION IS NOT RE-RAISED. An SDK auth failure can carry the request body,
                # and the request body is the password.
                raise VenueError(f"TradeLocker login failed ({type(exc).__name__})") from None
        self._load_instruments()
        return self

    def _load_instruments(self) -> None:
        frame = self._api.get_all_instruments()
        rows = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame)
        self._by_key = {}
        for r in rows:
            name = r.get("name") or r.get("symbol") or r.get("tradableInstrumentId")
            iid = r.get("tradableInstrumentId") or r.get("id")
            if name is None or iid is None:
                continue
            self._by_key.setdefault(_normalise(str(name)), int(iid))
        if not self._by_key:
            raise VenueError("the venue returned no instruments; refusing to trade a blind map")

    # ------------------------------------------------------------------ reads
    def instrument_id(self, symbol: str) -> int:
        """Desk symbol -> venue id, or a refusal NAMING the symbol.

        A missing instrument is never a silent skip: the desk's whole point is that an absence is
        reported (L1.28a), and a sleeve that quietly stops trading because a symbol was renamed is
        the failure mode this raises to prevent.
        """
        key = _normalise(symbol)
        if key not in self._by_key:
            raise VenueError(f"{symbol} is not in this venue's catalogue "
                             f"({len(self._by_key)} instruments)")
        return self._by_key[key]

    def details(self, symbol: str) -> dict[str, Any]:
        iid = self.instrument_id(symbol)
        if iid not in self._details:
            self._details[iid] = dict(self._api.get_instrument_details(iid))
        return self._details[iid]

    def min_lot(self, symbol: str) -> float:
        """THE VENUE'S OWN MINIMUM, read the same way `decision_core.venue_min_lot` reads MT5's.

        The principal's 2026-09-12 order -- every sleeve trades at least the broker minimum -- is
        a rule about the VENUE, so on this venue it is this venue's number. A lot below it is
        REJECTED, not small.
        """
        d = self.details(symbol)
        for k in ("minLot", "min_lot", "lotSize", "minQuantity", "minVolume"):
            v = d.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
        return 0.01

    def quote(self, symbol: str) -> tuple[float, float]:
        """(bid, ask). Both, always -- the spread IS the cost on a commission-free account."""
        q = self._api.get_quotes(self.instrument_id(symbol))
        bid, ask = float(q["bp"]), float(q["ap"])
        if not (bid > 0 and ask > 0 and ask >= bid):
            raise VenueError(f"{symbol}: degenerate quote bid={bid} ask={ask}")
        return bid, ask

    def spread(self, symbol: str) -> float:
        bid, ask = self.quote(symbol)
        return ask - bid

    def account(self) -> dict[str, float]:
        """Balance and equity, normalised. The guard reads this and nothing else."""
        st = dict(self._api.get_account_state())
        out: dict[str, float] = {}
        for want, keys in (("balance", ("balance", "accountBalance")),
                           ("equity", ("projectedBalance", "equity", "accountEquity")),
                           ("open_pnl", ("openNetPnL", "openPnL", "unrealizedPnL"))):
            for k in keys:
                if isinstance(st.get(k), (int, float)):
                    out[want] = float(st[k])
                    break
        if "equity" not in out and "balance" in out:
            out["equity"] = out["balance"] + out.get("open_pnl", 0.0)
        if "equity" not in out:
            raise VenueError(f"account state carries no equity; keys were {sorted(st)}")
        return out

    def positions(self) -> list[dict[str, Any]]:
        frame = self._api.get_all_positions()
        return frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame)

    # ------------------------------------------------------------------ writes
    def place(self, symbol: str, side: Side, lot: float, *, stop: float | None = None,
              take_profit: float | None = None) -> int:
        """Send ONE market order with its stop attached, or refuse.

        THE STOP GOES WITH THE ORDER, NOT AFTER IT. On a 2.5% daily floor the window between an
        open position and its stop is the single most expensive thing that can go wrong, and
        "place then modify" leaves exactly that window open across a network call.

        The lot is the CALLER'S. This method floors it at the venue minimum -- per the principal's
        order, and because a sub-minimum order is rejected rather than small -- and otherwise does
        not touch it, because sizing is `decision_core`'s and duplicating it here is the
        charge-versus-send defect the desk has already paid for once.
        """
        if side not in ("buy", "sell"):
            raise VenueError(f"side must be buy or sell, got {side!r}")
        if not (lot > 0):
            raise VenueError(f"{symbol}: refusing a non-positive lot {lot}")
        iid = self.instrument_id(symbol)
        qty = max(float(lot), self.min_lot(symbol))
        oid = self._api.create_order(
            instrument_id=iid, quantity=qty, side=side, type_="market",
            stop_loss=stop, stop_loss_type="absolute" if stop is not None else None,
            take_profit=take_profit,
            take_profit_type="absolute" if take_profit is not None else None)
        if oid is None:
            raise VenueError(f"{symbol}: the venue rejected a {side} {qty} order")
        return int(oid)

    def close(self, position_id: int, quantity: float = 0) -> bool:
        return bool(self._api.close_position(position_id=int(position_id),
                                             close_quantity=float(quantity)))

    def close_all(self) -> bool:
        """Used by the guard at the daily stand-down and nowhere else."""
        return bool(self._api.close_all_positions())

    # ------------------------------------------------------------------ the artifact
    def report(self) -> dict[str, Any]:
        """What a session needs to know, with nothing in it that could identify the login."""
        acct = self.account()
        return {
            "generated_utc": datetime.now(UTC).isoformat(),
            "venue": "tradelocker",
            "instruments_in_catalogue": len(self._by_key),
            "balance": acct.get("balance"),
            "equity": acct.get("equity"),
            "open_positions": len(self.positions()),
            "rule": "the adapter resolves, quotes and sends; it decides nothing. Sizing is "
                    "mt5desk.decision_core and the prop rules are prop.e8_guard",
        }

    def write_report(self, path: Path = OUT) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.report(), indent=1), encoding="utf-8")
        return path
