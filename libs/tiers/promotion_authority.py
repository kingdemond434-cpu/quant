"""THE TIER S VERIFIERS' AUTHORITY AT THE PROMOTION DOOR (principal 2026-09-29: "no approvals
needed", every blueprint wired live).

`block(name)` is called by `research/promoter.py` beside `blind_review_veto`, with the same
consequence and the same limits: it WITHHOLDS A NEW LIVE ROW, it sizes nothing and it never
touches an open position or a row already holding capital. Six verdicts can withhold, and a
check that raises withholds too (`DOOR_ERROR`, fail closed):

  CONSTITUTION_VIOLATED  the truth kernel's rule set in force loosens the sealed constitution
                         without a principal ratification of its exact hash;
  REPLICATION_MISMATCH   an independent re-execution of the certificate disagreed with it
                         (`reports/REPLICATION.json`, verdict MISMATCH / DISAGREE / FAIL);
  ONLINE_FDR_OVER_BUDGET the certificate was admitted after the desk's lifetime online-FDR
                         budget was spent (`reports/tier_s/ONLINE_FDR_ROWS.json`, certified row
                         with `over_budget`);
  REVIEW_PANEL_FAILED    the review panel resolved a HIGH challenge against the candidate on
                         its own evidence (forward clock or x5-cost world), and
  THEORY_REFUTED         its mechanism is refuted on forward/live/replication evidence alone
                         (`libs/tiers/door_evidence`, `data/tier_s/door_verdicts.json`);
  IMMUNE_FREEZE          the production certifier got EASIER TO FOOL on the sealed suite -- a
                         freeze judged by the real certifier (`judge` production:*) whose reason
                         is a DROP. A freeze from the reference validator or from an absolute
                         floor withholds nothing: a toy's verdict gets no authority over capital.

FAIL CLOSED (audit 2026-09-30). The door's four hourly verdict files (replication, online FDR,
the immune verdict, the panel/theory verdicts) must be PRESENT and FRESH (<= MAX_AGE_H): absent,
stale, torn or malformed withholds as `DOOR_ERROR`, as does any check that raises. Silence from
a verifier is never read as its approval. An organ whose contracts are all REJECTED is suspended
and is not required.

BILLED LIKE EVERY RAIL (growth governance Rule 1): the rail `tier_s_evidence_block` in
`libs/portfolio/rails.py` is measured by `missed_growth.measure_tier_s_block` from the ledger
this module appends (`data/tier_s/promotion_blocks.jsonl`): every withheld row, with the forward
expectancy its clock carried when it was withheld, so what the door refused is a number.

AUTHORITY IS EARNED: an organ whose every contracted layer reads REJECTED
(`libs/tiers/authority.py`) loses its verdict here -- a suspended `online_fdr` or `immune` organ
withholds nothing until one of its layers is ADMITTED or UNMEASURED again.

READ-ONLY OF CERTIFICATES, BY THE FIREWALL: every file this module opens is checked with
`firewall.may("promoter", "read", ...)`, and the promoter role may not read raw hypotheses.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from libs.tiers import authority, firewall

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPLICATION = DESK / "reports" / "REPLICATION.json"
FDR_ROWS = DESK / "reports" / "tier_s" / "ONLINE_FDR_ROWS.json"
FREEZE = DESK / "data" / "tier_s" / "PROMOTION_FREEZE.json"
LEDGER = DESK / "data" / "tier_s" / "promotion_blocks.jsonl"
DOOR_VERDICTS = DESK / "data" / "tier_s" / "door_verdicts.json"
MAX_AGE_H = 6.0
MISMATCH = frozenset({"MISMATCH", "DISAGREE", "FAIL", "FAILED", "NOT_REPLICATED"})


class DoorReadError(RuntimeError):
    """A door input that EXISTS but cannot be read, parsed or understood. `block` turns it into
    a `DOOR_ERROR` withhold: absence is a verdict (nothing to withhold on), damage is not."""


def _read(p: Path) -> Any:
    """The parsed file, or None when it does not exist. Anything else -- a permission error, a
    torn write, invalid JSON, a document that is not a JSON object -- raises DoorReadError, so
    the door fails CLOSED on a damaged input instead of reading it as 'nothing to withhold'."""
    firewall.may("promoter", "read", str(p.relative_to(ROOT)).replace("\\", "/"))
    try:
        doc = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise DoorReadError(f"{p.name} unreadable: {type(exc).__name__}: {exc}") from exc
    if not isinstance(doc, dict):
        raise DoorReadError(f"{p.name} is a {type(doc).__name__}, not a JSON object")
    return doc


def _required(p: Path, key: str = "generated_utc") -> dict[str, Any]:
    """A verdict file the door NEEDS: present, readable and fresh (<= MAX_AGE_H). Absent or stale
    raises DoorReadError -- a verifier that stopped reporting cannot vouch for a certificate, so
    the door withholds (billed, like every door verdict) instead of reading silence as a pass
    (audit 2026-09-30). Suspended organs are exempt: their checks return before reading."""
    doc = _read(p)
    if doc is None:
        raise DoorReadError(f"{p.name} absent: its hourly verifier has not reported")
    if not _fresh(doc, key):
        raise DoorReadError(f"{p.name} stale or undated (> {MAX_AGE_H:g}h): its hourly "
                            "verifier has stopped reporting")
    return dict(doc)


def _fresh(doc: Any, key: str = "generated_utc") -> bool:
    try:
        at = datetime.fromisoformat(str((doc or {}).get(key) or (doc or {}).get("at")))
    except (TypeError, ValueError):
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return (datetime.now(UTC) - at).total_seconds() <= MAX_AGE_H * 3600


def _match(cert: str, name: str) -> bool:
    return bool(cert) and (cert == name or cert.endswith("." + name) or name.endswith("." + cert))


def _replication(name: str) -> str | None:
    doc = _required(REPLICATION, "at")
    rows = (doc.get("verdicts") or doc.get("rows") or []) if isinstance(doc, dict) else []
    if not isinstance(rows, list):
        raise DoorReadError(f"{REPLICATION.name} verdicts are a {type(rows).__name__}")
    for r in rows:
        if not isinstance(r, dict):
            continue
        cert = str(r.get("cell") or r.get("key") or "")
        v = str(r.get("verdict") or r.get("status") or "").upper()
        if v in MISMATCH and _match(cert, name):
            return f"REPLICATION_MISMATCH: re-execution of {cert} returned {v}"
    return None


def _fdr(name: str) -> str | None:
    if authority.suspended("online_fdr"):      # its contract is REJECTED: no authority here
        return None
    doc = _required(FDR_ROWS)
    certified = doc.get("certified") or []
    if not isinstance(certified, list):
        raise DoorReadError(f"{FDR_ROWS.name} certified rows are a {type(certified).__name__}")
    for r in certified:
        if isinstance(r, dict) and r.get("over_budget") and _match(str(r.get("test_id")), name):
            return (f"ONLINE_FDR_OVER_BUDGET: {r.get('test_id')} was admitted after the lifetime "
                    f"online-FDR budget was spent (p={r.get('p')}, "
                    f"LORD level={r.get('lord_level')})")
    return None


def _freeze() -> str | None:
    if authority.suspended("immune"):
        return None
    doc = _required(FREEZE, "at")
    if str(doc.get("verdict")) != "FREEZE" or not str(doc.get("judge") or "").startswith(
            "production:"):
        return None
    why = str(doc.get("why") or "")
    if "fell" not in why:           # only a DROP freezes; an absolute floor is a report
        return None
    return f"IMMUNE_FREEZE: the production certifier got easier to fool -- {why}"


CONSTITUTION = ROOT / "docs" / "research" / "tier_s_constitution.json"
RATIFICATIONS = ROOT / "docs" / "research" / "tier_s_ratifications.jsonl"


def _constitution(name: str) -> str | None:
    """THE TRUTH KERNEL'S CONSTITUTION BINDS THE DOOR. A rule set in force that LOOSENS the
    sealed one (a DSR bar lowered, a gate count cut, cost fail-closed switched off) without a
    principal ratification of its exact hash is a VIOLATION, and while it stands no new LIVE row
    is written: a certificate minted under loosened law is not the certificate the law promised.
    A tightening, the sealed set itself or a ratified successor withholds nothing."""
    if authority.suspended("truth_kernel"):
        return None
    from libs.tiers import truth_kernel
    live = _read(CONSTITUTION)
    if live is None:
        return None                     # no live file: the sealed default is in force
    if not isinstance(live.get("rules"), dict):
        raise DoorReadError(f"{CONSTITUTION.name} carries no rules object")
    firewall.may("promoter", "read", str(RATIFICATIONS.relative_to(ROOT)))
    ratifs: list[dict[str, Any]] = []
    try:
        for line in RATIFICATIONS.read_text("utf-8").splitlines():
            if line.strip():
                ratifs.append(json.loads(line))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        raise DoorReadError(f"{RATIFICATIONS.name} unreadable: {type(exc).__name__}: {exc}"
                            ) from exc
    st = truth_kernel.constitution_status(truth_kernel.constitution_doc(), live, ratifs)
    if st.get("status") != "VIOLATION":
        return None
    loosened = ", ".join((st.get("diff") or {}).get("loosen") or []) or "rules removed"
    return (f"CONSTITUTION_VIOLATED: the rule set in force loosens the sealed constitution "
            f"({loosened}) without a principal ratification; {name} waits for the law")


def _panel_and_theory(name: str) -> str | None:
    """The review panel's candidate-specific HIGH failure, or the mechanism REFUTED out of
    sample (`libs/tiers/door_evidence`). A stale verdict file withholds nothing, and each half
    loses its authority while its organ is suspended."""
    from libs.tiers import door_evidence
    if authority.suspended("review") and authority.suspended("theory"):
        return None
    doc = _required(DOOR_VERDICTS)
    rows = doc.get("rows") or {}
    if not isinstance(rows, dict):
        raise DoorReadError(f"{DOOR_VERDICTS.name} rows are a {type(rows).__name__}")
    for cert, row in rows.items():
        if not isinstance(row, dict) or not _match(str(cert), name):
            continue
        if authority.suspended("review"):
            row = {**row, "review_failed": []}
        if authority.suspended("theory"):
            row = {**row, "theory": {}}
        why = door_evidence.door_reason(row)
        if why:
            return why
    return None


def block(name: str) -> str | None:
    """The first reason this certificate may not be written LIVE now, or None.

    FAILS CLOSED (verifier, 2026-09-30): a check that raises WITHHOLDS with `DOOR_ERROR`, it is
    never skipped. Before this, one exception anywhere in here reached the promoter's wrapper
    and dropped all six checks at once. The withheld row is billed by `tier_s_evidence_block`
    like every other door verdict, so a broken check costs a measured amount of growth rather
    than silently waving certificates through."""
    per_cert: list[tuple[str, Callable[[str], str | None]]] = [
        ("constitution", _constitution), ("replication", _replication), ("fdr", _fdr),
        ("panel_and_theory", _panel_and_theory)]
    checks: list[tuple[str, Callable[[], str | None]]] = [
        (label, partial(fn, name)) for label, fn in per_cert]
    checks.append(("freeze", _freeze))
    for label, check in checks:
        try:
            why = check()
        except Exception as exc:  # any failure must withhold, never pass
            return (f"DOOR_ERROR: the {label} check raised "
                    f"{type(exc).__name__}: {exc}; withheld until it runs clean")
        if why:
            return why
    return None


#: the four hourly verdict files the door REQUIRES present and fresh (fail closed), with their
#: stamp key and the leg that writes each
REQUIRED: dict[str, tuple[Path, str, str]] = {
    "replication": (REPLICATION, "at", "hourly leg replication_civilization"),
    "online_fdr": (FDR_ROWS, "generated_utc", "tier_s organ online_fdr"),
    "immune": (FREEZE, "at", "tier_s organ immune"),
    "door": (DOOR_VERDICTS, "generated_utc", "tier_s organ door"),
}


def door_inputs() -> dict[str, dict[str, Any]]:
    """{input: {ok, why, writer}} for the door's four required verdict files, read exactly as
    `block` reads them. A missing or stale one withholds EVERY promotion, so its health is
    published every hour (the `tier_s` summary's `door_inputs`)."""
    out: dict[str, dict[str, Any]] = {}
    for key, (path, stamp, writer) in REQUIRED.items():
        try:
            _required(path, stamp)
            out[key] = {"ok": True, "why": "present and fresh", "writer": writer}
        except Exception as exc:
            out[key] = {"ok": False, "why": str(exc), "writer": writer}
    return out


LIVE_DOOR = DESK / "data" / "tier_s" / "live_door.json"


def review_live(live_names: list[str]) -> dict[str, str]:
    """{LIVE row name: the reason the door would withhold it if it were promoted now}.

    The door must also act on rows ALREADY LIVE (verifier, 2026-09-30): a certificate whose
    replication failed, whose FDR budget was spent or whose own forward clock turned against it
    after it went live is no better for having gone live first. This is the same `block`, fail
    closed, run over the live book; the `door` organ publishes it as `data/tier_s/live_door.json`
    for the promoter's automatic retirement to read, billed like every door verdict."""
    out: dict[str, str] = {}
    for name in live_names:
        why = block(name)
        if why:
            out[name] = why
    return out


def record(name: str, why: str, *, lane: str, exp_r: Any = None, n: Any = None) -> None:
    """Append one withheld promotion to the ledger `missed_growth` bills."""
    firewall.may("promoter", "write", str(LEDGER.relative_to(ROOT)))
    row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "name": name, "lane": lane,
           "why": why, "reason": why.split(":", 1)[0], "exp_r": exp_r, "n": n}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass
