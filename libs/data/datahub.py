"""The DataHub: one typed, point-in-time, provider-swappable door for every observation.

OpenBB's provider-extension idea (one standard interface, many vendors underneath) and the
desk's own point-in-time doctrine (`libs.data.pit`) meet here. A CONTRACT names a dataset the
research code may ask for; PROVIDERS are the concrete loaders, tried in declared order; every
row that leaves carries the PIT stamp, and every physical measurement leaves as a typed
`Quantity`. No strategy scrapes the web; no research module opens a vendor file by name.

    hub.get("bars.h1", symbol="XAUUSD")          -> bars with provenance
    hub.get("terms.swap", symbol="AUDCAD")       -> Quantity(points, source=...)
    hub.get("calendar.events")                   -> stamped rows
    hub.reconcile("terms.spread", symbol=...)    -> agreement between providers

PROVENANCE OF MINED IDEAS lives here too (`record_mined_source`): every public repository or
paper the desk extracts a mechanism from is logged with URL, commit, licence, file, whether any
code was copied (default: no -- concepts are reimplemented) and whether attribution or
commercial restrictions apply. A licence the desk cannot honour is a source the desk cites and
does not copy.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.data.pit import stamp
from libs.data.units import Quantity, reconcile

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
MINED_SOURCES = DESK / "data" / "mined_sources.jsonl"

Loader = Callable[..., Any]


@dataclass(frozen=True)
class Provider:
    name: str
    load: Loader
    #: "primary" | "backup" | "historical" | "free" | "paid"
    role: str = "primary"
    version: str = ""


@dataclass
class Contract:
    name: str
    #: what the payload is: "frame" (bars, tables), "rows" (stamped dict rows), "quantity"
    kind: str
    unit: str | None = None
    providers: list[Provider] = field(default_factory=list)
    description: str = ""


class DataHub:
    def __init__(self) -> None:
        self._contracts: dict[str, Contract] = {}

    def register(self, contract: Contract) -> None:
        if contract.name in self._contracts:
            raise ValueError(f"contract {contract.name} already registered")
        self._contracts[contract.name] = contract

    def add_provider(self, contract: str, provider: Provider) -> None:
        self._contracts[contract].providers.append(provider)

    def contracts(self) -> list[str]:
        return sorted(self._contracts)

    def get(self, contract: str, **kw: Any) -> dict[str, Any]:
        """The first provider that answers, with provenance. Raises when none does."""
        c = self._contracts[contract]
        errors: dict[str, str] = {}
        for p in c.providers:
            try:
                payload = p.load(**kw)
            except Exception as exc:
                errors[p.name] = f"{type(exc).__name__}: {exc}"
                continue
            if payload is None:
                errors[p.name] = "no data"
                continue
            return {"contract": c.name, "provider": p.name, "role": p.role,
                    "version": p.version, "kind": c.kind, "unit": c.unit,
                    "payload": self._typed(c, payload, p),
                    "loaded_at": datetime.now(tz=UTC).isoformat(), "tried": errors}
        raise LookupError(f"{contract}: no provider answered ({errors})")

    @staticmethod
    def _typed(c: Contract, payload: Any, p: Provider) -> Any:
        if c.kind == "quantity":
            if isinstance(payload, Quantity):
                return payload
            return Quantity(float(payload), c.unit or "count", source=p.name)
        if c.kind == "rows":
            return [stamp(dict(r), p.name, source_version=p.version or None)
                    for r in payload if isinstance(r, dict)]
        return payload

    def reconcile(self, contract: str, **kw: Any) -> dict[str, Any]:
        """Ask every provider and compare: the cross-source check on overlapping feeds."""
        c = self._contracts[contract]
        if c.kind != "quantity":
            raise ValueError("reconcile is defined for quantity contracts")
        got: list[Quantity] = []
        for p in c.providers:
            try:
                v = p.load(**kw)
            except Exception:
                continue
            if v is not None:
                got.append(v if isinstance(v, Quantity) else
                           Quantity(float(v), c.unit or "count", source=p.name))
        if len(got) < 2:
            return {"agree": None, "why": f"{len(got)} provider(s) answered; need 2"}
        verdicts = [reconcile(got[0], g) for g in got[1:]]
        return {"agree": all(bool(v.get("agree")) for v in verdicts), "n": len(got),
                "verdicts": verdicts}


# --------------------------------------------------------------------------- mined sources
def record_mined_source(*, repo: str, url: str, commit: str, license_: str, file: str,
                        mechanism: str, code_copied: bool = False,
                        attribution_required: bool | None = None,
                        commercial_restriction: bool | None = None,
                        path: Path = MINED_SOURCES) -> dict[str, Any]:
    """The provenance line every extracted public mechanism must carry. Append-only."""
    row = {"at": datetime.now(tz=UTC).isoformat(), "repo": repo, "url": url, "commit": commit,
           "license": license_, "file": file, "mechanism": mechanism,
           "code_copied": bool(code_copied),
           "attribution_required": attribution_required,
           "commercial_restriction": commercial_restriction,
           "policy": "concept reimplemented independently; provenance cited"
                     if not code_copied else "code copied under its licence"}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


#: Licences under which COPYING code into this tree is permitted. Anything else: concept only.
COPY_PERMITTED: frozenset[str] = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
                                           "ISC", "Unlicense", "CC0-1.0"})


def copy_allowed(license_: str) -> bool:
    return license_ in COPY_PERMITTED


# --------------------------------------------------------------------------- the desk's hub
def desk_hub() -> DataHub:
    """The contracts the MT5 desk actually serves, bound to its existing loaders."""
    hub = DataHub()

    def _bars(symbol: str, tf: str = "H1") -> Any:
        import pandas as pd
        p = DESK / "data" / "universe" / f"{symbol}_{tf}.parquet"
        return pd.read_parquet(p) if p.exists() else None

    def _swap(symbol: str) -> Quantity | None:
        import glob
        files = sorted(glob.glob(str(DESK / "data" / "intelligence" / "broker_swaps"
                                     / "discoveries_*.json")))
        for f in reversed(files):
            try:
                doc = json.loads(Path(f).read_text("utf-8"))
            except (OSError, ValueError):
                continue
            rows = doc if isinstance(doc, list) else (doc.get("discoveries") or [])
            for r in rows:
                if isinstance(r, dict) and (r.get("symbols") or [None])[0] == symbol:
                    return Quantity(float(r.get("swap_diff", 0.0)), "points",
                                    source="broker_swaps")
        return None

    def _calendar() -> list[dict[str, Any]]:
        import glob
        out: list[dict[str, Any]] = []
        for f in sorted(glob.glob(str(DESK / "data" / "intelligence" / "ff_calendar_vintage"
                                      / "discoveries_*.json")))[-30:]:
            try:
                doc = json.loads(Path(f).read_text("utf-8"))
            except (OSError, ValueError):
                continue
            out.extend(doc if isinstance(doc, list) else (doc.get("discoveries") or []))
        return out

    hub.register(Contract("bars.h1", "frame", description="H1 OHLC + spread + tick_volume",
                          providers=[Provider("universe_parquet", _bars, "primary")]))
    hub.register(Contract("terms.swap_diff", "quantity", unit="points",
                          description="Fusion long-minus-short rollover, points",
                          providers=[Provider("broker_swaps", _swap, "primary")]))
    hub.register(Contract("calendar.events", "rows", description="ForexFactory vintage rows",
                          providers=[Provider("ff_calendar_vintage", _calendar, "primary")]))
    return hub
