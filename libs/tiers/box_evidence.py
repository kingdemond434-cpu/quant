"""A TIER S LAYER IS DONE ONLY ON THE TRADING BOX'S OWN EVIDENCE (verifier, 2026-09-30).

Until this module, `docs/research/tier_s_program.json` marked a layer DONE on the author's word:
code on a branch, tests green, the hourly organ timed in a cloud container. None of that is the
desk. The verifier re-scored the programme 0/46 and was right to: no Tier S artifact existed on
any branch or on the box.

`attest()` runs at the end of every `tier_s` pass, on whichever host runs it, and writes
`data/tier_s/box_evidence.json`: for each layer, whether its artifact is on THIS host's disk,
how old it is, and its contract's latest verdict from `reports/tier_s/CONTRACTS.json`. The
file lives under `data/`, so it is box state and reaches git through the box's own sync. It
also carries a digest of each output the verifier named (TIER_S, ALPHA_RANK, ONLINE_FDR_ROWS,
IMMUNE, allocator_tilts, research_budget with its `authoritative` flag, the door verdicts and the
contracts), because those are written under gitignored `reports/` or box-local `data/` and were
otherwise readable nowhere off the box.

`scripts/check_tier_s_program.py` then accepts `status: DONE` only for a layer the committed
file attests from TRADING_HOST, with a fresh artifact and a contract verdict other than
REJECTED. A layer whose code is complete but which the box has not yet attested is `BUILT`.
Evidence written on any other host (a cloud container, the VPS, the desktop) is recorded and
never counts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import host_identity

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
LEDGER = ROOT / "docs" / "research" / "tier_s_program.json"
CONTRACTS = DESK / "reports" / "tier_s" / "CONTRACTS.json"
OUT = DESK / "data" / "tier_s" / "box_evidence.json"
#: the Contabo trading box (CLAUDE.md, measured 2026-09-24): the only host whose word counts.
#: Kept as the display name; the IDENTITY is the machine id in config/trading_host.json, read by
#: `libs/ops/host_identity` -- one helper for every fence, never a hostname prefix.
TRADING_HOST = host_identity.trading_hostname()
MAX_AGE_H = 6.0
#: the verifier's named outputs (2026-09-30): each is gitignored or box-local where it is
#: written, so the box's evidence file carries a digest of each -- stamp, hash and headline
#: fields -- into git through the box's own sync
PUBLISHED: dict[str, str] = {
    "TIER_S": "desks/mt5/reports/TIER_S.json",
    "ALPHA_RANK": "desks/mt5/reports/ALPHA_RANK.json",
    "ONLINE_FDR_ROWS": "desks/mt5/reports/tier_s/ONLINE_FDR_ROWS.json",
    "IMMUNE": "desks/mt5/reports/tier_s/IMMUNE.json",
    "allocator_tilts": "desks/mt5/data/tier_s/allocator_tilts.json",
    "research_budget": "desks/mt5/data/research_budget.json",
    "door_verdicts": "desks/mt5/data/tier_s/door_verdicts.json",
    "CONTRACTS": "desks/mt5/reports/tier_s/CONTRACTS.json",
}
#: whole documents small enough, and consequential enough, to carry verbatim
VERBATIM = frozenset({"allocator_tilts"})


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


def digest(p: Path, *, verbatim: bool = False) -> dict[str, Any]:
    """Stamp, hash and headline of one output: every top-level scalar, and the size of every
    top-level list or mapping (one level into `rows`)."""
    if not p.is_file():
        return {"exists": False}
    raw = p.read_bytes()
    doc = _json(p)
    ts = _stamp(doc, p)
    out: dict[str, Any] = {"exists": True, "bytes": len(raw),
                           "sha256": hashlib.sha256(raw).hexdigest(),
                           "stamp": ts.isoformat(timespec="seconds") if ts else None}
    if isinstance(doc, dict):
        head: dict[str, Any] = {}
        for k, v in doc.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                head[k] = v if not isinstance(v, str) else v[:200]
            elif isinstance(v, (list, dict)):
                head[f"n_{k}"] = len(v)
        rows = doc.get("rows")
        if isinstance(rows, list):
            for flag in ("over_budget", "certified"):
                head[f"n_rows_{flag}"] = sum(1 for r in rows
                                             if isinstance(r, dict) and r.get(flag))
        out["head"] = head
        if verbatim:
            out["doc"] = doc
    return out


def layer_evidence(layer: dict[str, Any], verdicts: dict[str, Any], root: Path,
                   now: datetime) -> dict[str, Any]:
    lid = str(layer.get("id"))
    art = root / str(layer.get("artifact") or "")
    verdict = str(((verdicts.get(lid) or {}).get("verdict")) or "UNMEASURED")
    if not layer.get("artifact") or not art.is_file():
        return {"ok": False, "artifact": layer.get("artifact"), "verdict": verdict,
                "why": "artifact absent on this host"}
    doc = _json(art)
    ts = _stamp(doc, art)
    age_h = None if ts is None else round((now - ts).total_seconds() / 3600, 2)
    errored = isinstance(doc, dict) and str(doc.get("status")) == "ERROR"
    ok = (age_h is not None and 0 <= age_h <= MAX_AGE_H and verdict != "REJECTED"
          and not errored)
    why = ("fresh artifact, contract not rejected" if ok else
           "the organ raised: its artifact is an ERROR record" if errored else
           "contract REJECTED" if verdict == "REJECTED" else
           f"artifact {age_h}h old (limit {MAX_AGE_H}h)")
    return {"ok": ok, "artifact": layer.get("artifact"), "age_h": age_h, "verdict": verdict,
            "why": why}


def attest(*, root: Path = ROOT, out: Path | None = None, host: str | None = None,
           machine_id: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Measure every layer on this host and write the evidence file."""
    now = now or datetime.now(UTC)
    ledger = _json(root / LEDGER.relative_to(ROOT)) or {}
    verdicts = (_json(root / CONTRACTS.relative_to(ROOT)) or {}).get("layers") or {}
    rows = {str(r.get("id")): layer_evidence(r, verdicts, root, now)
            for r in ledger.get("layers") or []}
    ident = (host_identity.identify() if host is None
             else host_identity.classify(machine_id, host))
    doc = {"generated_utc": now.isoformat(timespec="seconds"),
           "host": ident.hostname, "trading_host": TRADING_HOST,
           "machine_id": ident.machine_id, "host_identity": ident.as_dict(),
           # Evidence GRANTS credit, so only a confirmed identity counts: an unrecorded or
           # unreadable id is UNMEASURED and earns nothing (libs/ops/host_identity).
           "counts_toward_done": ident.confirmed_trading,
           "n_ok": sum(1 for v in rows.values() if v["ok"]), "layers": rows,
           "published": {k: digest(root / rel, verbatim=k in VERBATIM)
                         for k, rel in PUBLISHED.items()}}
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
    # Keyed on the machine id the box wrote, checked against the committed record. A doc with no
    # id, or a checkout with none recorded, is UNMEASURED and attests nothing -- never a hostname.
    if host_identity.is_recorded_trading_id(doc.get("machine_id")) is not True:
        return set()
    return {lid for lid, v in (doc.get("layers") or {}).items()
            if isinstance(v, dict) and v.get("ok") is True}
