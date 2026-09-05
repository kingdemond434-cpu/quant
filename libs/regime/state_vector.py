"""One addressable description of the world, assembled from every state engine the desk runs.

    GLOBAL      regime probabilities, entropy, age, P(exit) at each horizon
    ASSETS      the same, per instrument the book actually holds, per clock
    FACTORS     the same, for the instruments that DEFINE the dollar, rates, risk, metals,
                energy and growth -- `economic_drivers.ROLES` says which
    SESSION     broker-stamp phase and the offset it was derived with
    EVENT       where in a scheduled release's life the market is
    LIQUIDITY   what execution costs right now, and whether it is normal

WHY ONE OBJECT. These states already existed in pieces -- a session phase in `session_phase`, a
regime in `pf_allocator`, spreads in the tape -- and each was consumed by whoever happened to
compute it. That is how a desk ends up with two vocabularies for the same thing. One object, one
producer, one id, and every consumer reads the same description of the same moment.

THE ID IS THE POINT. `sv.id` is a hash of the rounded contents, so it can be stamped on an order,
carried through the ledger to the fill, and used later to ask what the world looked like when a
decision was made. Execution cost, slippage and fill probability become learnable functions of a
state the desk can actually reconstruct, rather than of a timestamp somebody has to re-derive.

WHAT THIS DELIBERATELY DOES NOT DO. It grants nothing authority. A state variable here is
INFORMATION, and information becomes capital authority only by improving forecast calibration or
marginal E[log W] against the desk's existing gates -- otherwise it stays a recorded field and
eventually goes to the graveyard. `bucket()` exists so evidence can be conditioned on a chosen
subset of dimensions, and the caller still faces `robust_elog`'s state shrinkage (k_state = 40),
which is what stops a six-observation bucket from capturing the book.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from libs.regime.asset_state import AssetState, _from_dict


@dataclass(frozen=True)
class StateVector:
    """The desk's description of one moment, addressable by `id`."""

    at: str
    #: The book-wide regime, kept separate because it is the one that draws scenario worlds.
    global_state: AssetState | None = None
    #: "SYMBOL@clock" -> state, for instruments the book holds.
    assets: dict[str, AssetState] = field(default_factory=dict)
    #: ROLE ("USD", "RATES", "RISK", "GOLD", "OIL", "GROWTH") -> state of the instrument that
    #: defines it, with the symbol recorded on the state itself.
    factors: dict[str, AssetState] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    event: dict[str, Any] = field(default_factory=dict)
    liquidity: dict[str, Any] = field(default_factory=dict)
    #: Everything that could NOT be built, by name and reason. A hole recorded is a fact about
    #: what the desk knows; a hole filled in is a lie about it.
    gaps: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return hashlib.sha256(
            json.dumps(self._identity(), sort_keys=True, default=str).encode()).hexdigest()[:16]

    def _identity(self) -> dict[str, Any]:
        """The content the id is over: labels and rounded probabilities, never timestamps.

        Rounded to two places on purpose. An id that changes on the fourth decimal of a posterior
        changes every pass and identifies nothing; at two places, two moments share an id exactly
        when the desk would describe them the same way.
        """
        def _st(s: AssetState | None) -> Any:
            if s is None:
                return None
            return {"top": s.top, "probs": {k: round(v, 2) for k, v in sorted(s.probs.items())},
                    "age": s.age_bars}

        return {
            "global": _st(self.global_state),
            "assets": {k: _st(v) for k, v in sorted(self.assets.items())},
            "factors": {k: _st(v) for k, v in sorted(self.factors.items())},
            "session": self.session.get("phase"),
            "event": self.event.get("phase"),
            "liquidity": self.liquidity.get("state"),
        }

    def bucket(self, *dims: str) -> str:
        """A compact conditioning key over chosen dimensions, e.g. bucket("global", "session").

        Names a BUCKET, never a belief: the top label per dimension, joined. Conditioning evidence
        on this is only honest because `robust_elog` shrinks a state's mean toward its parent by
        how many observations the bucket has.
        """
        parts: list[str] = []
        for d in dims:
            if d == "global":
                parts.append(self.global_state.top if self.global_state else "?")
            elif d == "session":
                parts.append(str(self.session.get("phase") or "?"))
            elif d == "event":
                parts.append(str(self.event.get("phase") or "?"))
            elif d == "liquidity":
                parts.append(str(self.liquidity.get("state") or "?"))
            elif d in self.factors:
                parts.append(f"{d}:{self.factors[d].top}")
            elif d in self.assets:
                parts.append(f"{d}:{self.assets[d].top}")
            else:
                parts.append("?")
        return "|".join(parts)

    def asset(self, symbol: str, clock: str = "daily") -> AssetState | None:
        """This symbol's own state, falling back to the global one so a caller always has A state.

        The fallback is EXPLICIT rather than silent: `gaps` records that the symbol had no fit of
        its own, so nobody can later mistake gold's regime for GBPUSD's.
        """
        return self.assets.get(f"{symbol}@{clock}") or self.global_state

    def entropy(self, horizon: int | None = None) -> float:
        """The global state's normalised entropy -- how uncertain the desk is about where it is."""
        if not self.global_state or not self.global_state.entropy:
            return float("nan")
        if horizon is not None and horizon in self.global_state.entropy:
            return self.global_state.entropy[horizon]
        return self.global_state.entropy[min(self.global_state.entropy)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at, "id": self.id,
            "global": self.global_state.to_dict() if self.global_state else None,
            "assets": {k: v.to_dict() for k, v in sorted(self.assets.items())},
            "factors": {k: v.to_dict() for k, v in sorted(self.factors.items())},
            "session": self.session, "event": self.event, "liquidity": self.liquidity,
            "gaps": self.gaps,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StateVector:
        return cls(
            at=str(d.get("at") or ""),
            global_state=_from_dict(d["global"]) if d.get("global") else None,
            assets={str(k): _from_dict(v) for k, v in (d.get("assets") or {}).items()},
            factors={str(k): _from_dict(v) for k, v in (d.get("factors") or {}).items()},
            session=dict(d.get("session") or {}), event=dict(d.get("event") or {}),
            liquidity=dict(d.get("liquidity") or {}), gaps=dict(d.get("gaps") or {}),
        )

    def age_seconds(self, now: datetime | None = None) -> float:
        try:
            built = datetime.fromisoformat(self.at)
        except (TypeError, ValueError):
            return float("inf")
        if built.tzinfo is None:
            built = built.replace(tzinfo=UTC)
        return (now or datetime.now(tz=UTC)).timestamp() - built.timestamp()
