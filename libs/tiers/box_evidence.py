"""A TIER S LAYER IS DONE ONLY ON THE TRADING BOX'S OWN EVIDENCE (verifier, 2026-09-30).

Until this module, `docs/research/tier_s_program.json` marked a layer DONE on the author's word:
code on a branch, tests green, the hourly organ timed in a cloud container. None of that is the
desk. The verifier re-scored the programme 0/46 and was right to: no Tier S artifact existed on
any branch or on the box.

`attest()` runs at the end of every `tier_s` pass, on whichever host runs it, and writes
`data/tier_s/box_evidence.json`: for each layer, whether its artifact is on THIS host's disk,
how old it is, and its contract's latest verdict from `reports/tier_s/CONTRACTS.json`. The
file lives under `data/`, so it is box state and reaches git through the box's own sync.

`scripts/check_tier_s_program.py` then accepts `status: DONE` only for a layer the committed
file attests from TRADING_HOST, with a fresh artifact and a contract verdict other than
REJECTED. A layer whose code is complete but which the box has not yet attested is `BUILT`.
Evidence written on any other host (a cloud container, the VPS, the desktop) is recorded and
never counts.
"""
from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
LEDGER = ROOT / "docs" / "research" / "tier_s_program.json"
CONTRACTS = DESK / "reports" / "tier_s" / "CONTRACTS.json"
OUT = DESK / "data" / "tier_s" / "box_evidence.json"
#: the Contabo trading box (CLAUDE.md, measured 2026-09-24): the only host whose word counts
TRADING_HOST = "vmi3571445"
MAX_AGE_H = 6.0


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _stamp(doc: Any, p: Path) -> datetime | None:
    raw = doc.get("generated_utc") or doc.get("generated_at") if isinstance(doc, dict) else None
    if raw:
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, UTC)
    except OSError:
        return None


def layer_evidence(layer: dict[str, Any], verdicts: dict[str, Any], root: Path,
                   now: datetime) -> dict[str, Any]:
    lid = str(layer.get("id"))
    art = root / str(layer.get("artifact") or "")
    verdict = str(((verdicts.get(lid) or {}).get("verdict")) or "UNMEASURED")
    if not layer.get("artifact") or not art.is_file():
        return {"ok": False, "artifact": layer.get("artifact"), "verdict": verdict,
                "why": "artifact absent on this host"}
    ts = _stamp(_json(art), art)
    age_h = None if ts is None else round((now - ts).total_seconds() / 3600, 2)
    ok = age_h is not None and 0 <= age_h <= MAX_AGE_H and verdict != "REJECTED"
    why = ("fresh artifact, contract not rejected" if ok else
           "contract REJECTED" if verdict == "REJECTED" else
           f"artifact {age_h}h old (limit {MAX_AGE_H}h)")
    return {"ok": ok, "artifact": layer.get("artifact"), "age_h": age_h, "verdict": verdict,
            "why": why}


def attest(*, root: Path = ROOT, out: Path | None = None, host: str | None = None,
           now: datetime | None = None) -> dict[str, Any]:
    """Measure every layer on this host and write the evidence file."""
    now = now or datetime.now(UTC)
    ledger = _json(root / LEDGER.relative_to(ROOT)) or {}
    verdicts = (_json(root / CONTRACTS.relative_to(ROOT)) or {}).get("layers") or {}
    rows = {str(r.get("id")): layer_evidence(r, verdicts, root, now)
            for r in ledger.get("layers") or []}
    doc = {"generated_utc": now.isoformat(timespec="seconds"),
           "host": host or socket.gethostname(), "trading_host": TRADING_HOST,
           "counts_toward_done": (host or socket.gethostname()).lower().startswith(TRADING_HOST),
           "n_ok": sum(1 for v in rows.values() if v["ok"]), "layers": rows}
    dest = out or (root / OUT.relative_to(ROOT))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    tmp.replace(dest)
    return doc


def attested(doc: Any) -> set[str]:
    """The layer ids a committed evidence file attests from the trading box."""
    if not isinstance(doc, dict):
        return set()
    if not str(doc.get("host") or "").lower().startswith(TRADING_HOST):
        return set()
    return {lid for lid, v in (doc.get("layers") or {}).items()
            if isinstance(v, dict) and v.get("ok") is True}
