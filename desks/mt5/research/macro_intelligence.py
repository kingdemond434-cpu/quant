"""Fuse PIT-safe macro inputs into transparent, two-sided MT5 research suggestions.

This organ is an information consumer, not a trader. Missing/ambiguous inputs remain UNMEASURED;
it never substitutes zero for absence, grants authority, sizes capital, or places an order.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORT = DESK / "reports" / "MACRO_INTELLIGENCE.json"
STATE = DESK / "data" / "macro_intelligence.json"
INPUTS = {
    "macro_state": DESK / "data" / "macro_state.json",
    "fred": DESK / "data" / "axes" / "fred.json",
    "event_surprise": DESK / "reports" / "EVENT_SURPRISE.json",
    "event_atlas": DESK / "reports" / "EVENT_RESPONSE_ATLAS.json",
    "transmission": DESK / "reports" / "TRANSMISSION_GRAPH.json",
    "world_model": DESK / "reports" / "WORLD_MODEL.json",
}
REFUSED_ACCESS = {"REFUSED", "ILLEGAL", "AUTH_REQUIRED", "PAYWALL_BYPASS"}


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def _stamp(doc: Any) -> datetime | None:
    if not isinstance(doc, Mapping):
        return None
    for key in ("available_time", "at", "generated_utc", "generated_at", "updated_at"):
        raw = doc.get(key)
        if not raw:
            continue
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)
        except ValueError:
            continue
    return None


def _numbers(node: Any, prefix: str = "", depth: int = 0) -> Iterable[tuple[str, float]]:
    if depth > 6:
        return
    if isinstance(node, Mapping):
        for key, value in node.items():
            name = f"{prefix}.{key}".strip(".")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                yield name, float(value)
            else:
                yield from _numbers(value, name, depth + 1)
    elif isinstance(node, list):
        for i, value in enumerate(node[-100:]):
            yield from _numbers(value, f"{prefix}[{i}]", depth + 1)


def _bounded_signal(doc: Any, words: tuple[str, ...]) -> tuple[float | None, list[str]]:
    vals = [(name, value) for name, value in _numbers(doc)
            if any(word in name.lower() for word in words) and math.isfinite(value)]
    if not vals:
        return None, []
    # Inputs already expressed as z/probability/change are comparable after tanh. Raw levels are
    # not; exclude them rather than invent a scale that creates a macro opinion from units.
    usable = [(name, value) for name, value in vals
              if any(tok in name.lower() for tok in ("z", "surprise", "change", "delta",
                                                     "prob", "score", "state"))]
    if not usable:
        return None, []
    score = sum(math.tanh(value) for _, value in usable) / len(usable)
    return max(-1.0, min(1.0, score)), [name for name, _ in usable[:20]]


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    docs: dict[str, Any] = {}
    inputs: dict[str, Any] = {}
    consumed: list[str] = []
    for name, path in INPUTS.items():
        doc = _read(path)
        stamp = _stamp(doc)
        future = stamp is not None and stamp > now
        status = "MISSING" if doc is None else "WITHHELD_FUTURE" if future else "MEASURED"
        inputs[name] = {"path": str(path), "status": status,
                        "available_time": stamp.isoformat() if stamp else "UNMEASURED"}
        if status == "MEASURED":
            docs[name] = doc
            try:
                identity = path.relative_to(DESK).as_posix()
            except ValueError:
                # Tests and external read-only mounts may deliberately supply an artifact outside
                # the desk root.  Provenance must still be recorded; location is not permission to
                # discard an otherwise valid point-in-time input.
                identity = path.as_posix()
            consumed.append(f"artifact:{identity}")

    risk, risk_keys = _bounded_signal(docs, ("vix", "move", "risk", "stress", "volatility"))
    growth, growth_keys = _bounded_signal(docs, ("growth", "pmi", "employment", "gdp"))
    inflation, inflation_keys = _bounded_signal(docs, ("inflation", "cpi", "ppi", "price"))
    usd, usd_keys = _bounded_signal(docs, ("usd", "dollar", "dxy", "rate_diff"))
    # Every tilt is explicitly two-sided and exactly zero at a neutral posterior. Missing state
    # emits no tilt key at all, so the consumer cannot confuse UNMEASURED with neutral.
    tilts: dict[str, float] = {}
    if risk is not None:
        tilts.update({"indices": round(-risk, 5), "metals": round(risk * 0.5, 5),
                      "bonds": round(risk * 0.5, 5)})
    if growth is not None:
        tilts["indices"] = round(max(-1.0, min(1.0, tilts.get("indices", 0.0) + growth * 0.5)), 5)
        tilts["energy"] = round(growth * 0.5, 5)
    if inflation is not None:
        tilts["bonds"] = round(max(-1.0, min(1.0, tilts.get("bonds", 0.0) - inflation * 0.5)), 5)
        tilts["commodities"] = round(inflation * 0.5, 5)
    if usd is not None:
        tilts["forex"] = round(usd, 5)

    return {"at": now.isoformat(timespec="seconds"),
            "status": "MEASURED" if docs else "UNMEASURED",
            "inputs": inputs, "consumed_units": sorted(consumed),
            "states": {"risk": risk, "growth": growth, "inflation": inflation, "usd": usd},
            "state_features": {"risk": risk_keys, "growth": growth_keys,
                               "inflation": inflation_keys, "usd": usd_keys},
            "suggestions": {"asset_classes": tilts,
                            "contract": "two-sided [-1,1], neutral=0; missing key=UNMEASURED"},
            "unmeasured": [name for name, value in (("risk", risk), ("growth", growth),
                                                      ("inflation", inflation), ("usd", usd))
                           if value is None],
            "boundary": "research suggestion only; no allocation, sizing, promotion or orders"}


def run(*, out: Path = REPORT, state: Path = STATE) -> dict[str, Any]:
    doc = build()
    _atomic(out, doc)
    _atomic(state, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-s", type=float, default=240.0,
                        help="compatibility with the bounded hourly producer")
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--state", type=Path, default=STATE)
    args = parser.parse_args(argv)
    doc = run(out=args.out, state=args.state)
    measured = sum(v["status"] == "MEASURED" for v in doc["inputs"].values())
    print(f"macro intelligence: {doc['status']} inputs={measured} "
          f"tilts={len(doc['suggestions']['asset_classes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
