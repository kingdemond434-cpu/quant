"""THE TIER S VERIFIERS' AUTHORITY AT THE PROMOTION DOOR (principal 2026-09-29: "no approvals
needed", every blueprint wired live).

`block(name)` is called by `research/promoter.py` beside `blind_review_veto`, with the same
consequence and the same limits: it WITHHOLDS A NEW LIVE ROW, it sizes nothing and it never
touches an open position or a row already holding capital. Seven verdicts can withhold, and a
check that raises withholds too (`DOOR_ERROR`, fail closed; every DOOR_ERROR row is billed to
the input it names and the window it was absent or stale, `record` -> `missed_growth`):

  RELEASE_REGRESSION_STOP  the running sealed release regressed forward against the previous
                         one (`libs/tiers/regression_stop.py`, data/tier_s/RELEASE_STOP.json):
                         nothing new is promoted under it until the running release changes;

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
withholds nothing until one of its layers is ADMITTED or UNMEASURED again. Its verdict is still
read, and what it would have withheld is recorded as DOOR_SUSPENDED in
`data/tier_s/door_suspended.jsonl`, never dropped silently. The constitution check is NEVER
suspended: law loosening binds whatever the truth kernel's contract reads.

READ-ONLY OF CERTIFICATES, BY THE FIREWALL: every file this module opens is checked with
`firewall.may("promoter", "read", ...)`, and the promoter role may not read raw hypotheses.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
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


SUSPENDED_LEDGER = DESK / "data" / "tier_s" / "door_suspended.jsonl"


def _suspended_note(organ: str, name: str, why: str) -> None:
    """A SUSPENDED ORGAN'S WITHHOLD IS RECORDED, NEVER DROPPED SILENTLY (audit I16, 2026-10-06).

    An organ whose every contract reads REJECTED has no authority over capital, so its verdict
    withholds nothing. But it used to return None before even reading its file, so nobody could
    see what it WOULD have withheld. The verdict is now still read; a would-be withhold goes to
    `data/tier_s/door_suspended.jsonl` as DOOR_SUSPENDED (a pass the door let through on a
    suspended organ's word, not a missed-growth row: nothing was withheld, so nothing is billed)."""
    row = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "name": name,
           "organ": organ, "reason": "DOOR_SUSPENDED",
           "why": f"DOOR_SUSPENDED: {organ} is suspended (every contract REJECTED); it would have "
                  f"withheld -- {why}"}
    _LAST_SUSPENDED[name] = row
    try:
        firewall.may("promoter", "write", str(SUSPENDED_LEDGER.relative_to(ROOT)))
        SUSPENDED_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with SUSPENDED_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:  # the note never costs the pass
        pass


#: {name: the last DOOR_SUSPENDED row}, for the caller and the tests
_LAST_SUSPENDED: dict[str, dict[str, Any]] = {}


def _suspendable(organ: str, name: str, verdict: Callable[[], str | None], *,
                 suspended: bool | None = None) -> str | None:
    """Run one suspendable organ's check. Not suspended: its verdict, fail closed as ever.
    Suspended: it withholds nothing, and what it would have said is recorded."""
    if not (authority.suspended(organ) if suspended is None else suspended):
        return verdict()
    try:
        why = verdict()
    except Exception as exc:  # a suspended organ's damaged file is not required either
        why = None
        _suspended_note(organ, name, f"(its input could not be read: {type(exc).__name__}: "
                                     f"{exc})")
    if why:
        _suspended_note(organ, name, why)
    return None


def _fdr(name: str) -> str | None:
    return _suspendable("online_fdr", name, partial(_fdr_verdict, name))


def _fdr_verdict(name: str) -> str | None:
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


def _freeze(name: str = "*") -> str | None:
    return _suspendable("immune", name, _freeze_verdict)


def _freeze_verdict() -> str | None:
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
    A tightening, the sealed set itself or a ratified successor withholds nothing.

    NEVER SUSPENDABLE (audit I16, 2026-10-06). This used to return None whenever the truth
    kernel's contract read REJECTED, so a loosened rule set stopped being withheld exactly when
    the kernel was least trusted. Sealed-law loosening is a fact about two files and a
    ratification, not a steering opinion: it binds whatever the kernel's contract says."""
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
        return _suspendable("review+theory", name, partial(_panel_verdict, name, door_evidence),
                            suspended=True)
    doc = _required(DOOR_VERDICTS)
    rows = doc.get("rows") or {}
    if not isinstance(rows, dict):
        raise DoorReadError(f"{DOOR_VERDICTS.name} rows are a {type(rows).__name__}")
    for cert, row in rows.items():
        if not isinstance(row, dict) or not _match(str(cert), name):
            continue
        full = row
        if authority.suspended("review"):
            row = {**row, "review_failed": []}
        if authority.suspended("theory"):
            row = {**row, "theory": {}}
        why = door_evidence.door_reason(row)
        if why:
            return why
        if row is not full and (would := door_evidence.door_reason(full)):
            _suspended_note("review" if authority.suspended("review") else "theory", name,
                            would)
    return None


def _panel_verdict(name: str, door_evidence: Any) -> str | None:
    """The panel/theory verdict read whole, for the note when both organs are suspended."""
    doc = _required(DOOR_VERDICTS)
    rows = doc.get("rows") or {}
    if not isinstance(rows, dict):
        raise DoorReadError(f"{DOOR_VERDICTS.name} rows are a {type(rows).__name__}")
    for cert, row in rows.items():
        if isinstance(row, dict) and _match(str(cert), name):
            why = door_evidence.door_reason(row)
            if why:
                return str(why)
    return None


RELEASE_STOP_REL = Path("desks") / "mt5" / "data" / "tier_s" / "RELEASE_STOP.json"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _release_stop() -> str | None:
    """THE REGRESSION STOP (`libs/tiers/regression_stop.py`, written hourly by the twin organ):
    while the running release is one the forward-regression check STOPPED, no new LIVE row is
    promoted under it. Absent is no stop; a damaged stop file raises (fail closed)."""
    from libs.tiers import regression_stop
    firewall.may("promoter", "read", str(RELEASE_STOP_REL).replace("\\", "/"))
    try:
        return regression_stop.stop_reason(ROOT)
    except (OSError, ValueError) as exc:
        raise DoorReadError(f"RELEASE_STOP.json unreadable: {type(exc).__name__}: {exc}"
                            ) from exc


#: the last DOOR_ERROR per certificate name, as `record` bills it: which input, and the window
#: over which it was absent or stale (gap E, 2026-09-30)
_LAST_DOOR_ERROR: dict[str, dict[str, Any]] = {}
#: which REQUIRED input each labelled check reads
_CHECK_INPUT = {"replication": "replication", "fdr": "online_fdr", "freeze": "immune",
                "panel_and_theory": "door"}
#: the module attribute holding each labelled check's input file, and its stamp key -- read at
#: call time, so the bill names the file the check actually read
_CHECK_FILE = {"replication": ("REPLICATION", "at"), "fdr": ("FDR_ROWS", "generated_utc"),
               "freeze": ("FREEZE", "at"), "panel_and_theory": ("DOOR_VERDICTS", "generated_utc"),
               "constitution": ("CONSTITUTION", "")}


def _input_window(label: str, exc: BaseException) -> dict[str, Any]:
    """The input a DOOR_ERROR names and the window it was missing for: from its last stamp (or
    'never reported') to now, against the MAX_AGE_H freshness the door requires."""
    now = datetime.now(UTC)
    key = _CHECK_INPUT.get(label)
    out: dict[str, Any] = {"check": label, "input": key or label, "error": str(exc)[:300],
                           "max_age_h": MAX_AGE_H, "window_end": now.isoformat(timespec="seconds")}
    attr, stamp = _CHECK_FILE.get(label, ("", ""))
    path = getattr(sys.modules[__name__], attr) if attr else ROOT / RELEASE_STOP_REL
    out["input_file"] = _rel(path)
    if key is None:
        out.update(state="DAMAGED" if path.exists() else "ABSENT", window_start=None)
        return out
    out["writer"] = REQUIRED[key][2]
    try:
        doc = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        out.update(state="ABSENT", window_start=None, age_h=None)
        return out
    except (OSError, ValueError):
        out.update(state="DAMAGED", window_start=None, age_h=None)
        return out
    raw = (doc or {}).get(stamp) or (doc or {}).get("at") if isinstance(doc, dict) else None
    try:
        at = datetime.fromisoformat(str(raw))
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        out.update(state="UNDATED", window_start=None, age_h=None)
        return out
    age = (now - at).total_seconds() / 3600.0
    out.update(state="STALE" if age > MAX_AGE_H else "FRESH_BUT_UNREADABLE",
               last_stamp=at.isoformat(timespec="seconds"), age_h=round(age, 3),
               # the window the row was withheld over: from the moment the input went stale
               window_start=((at + timedelta(hours=MAX_AGE_H)).isoformat(timespec="seconds")
                             if age > MAX_AGE_H else None))
    return out


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
    checks.append(("release_stop", _release_stop))
    for label, check in checks:
        try:
            why = check()
        except Exception as exc:  # any failure must withhold, never pass
            try:
                _LAST_DOOR_ERROR[name] = _input_window(label, exc)
            except Exception as werr:      # the bill never costs the withhold
                _LAST_DOOR_ERROR[name] = {"check": label, "input": label,
                                          "error": f"{type(werr).__name__}: {werr}"}
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
#: `desks/mt5/research/research_live_identity.py`, hourly: per LIVE sleeve, whether the spec the
#: gateway trades is the spec research certified (family, symbol, selector, params, code hash)
IDENTITY = DESK / "reports" / "RESEARCH_LIVE_IDENTITY.json"


def _identity_mismatches() -> dict[str, str]:
    """{LIVE sleeve: reason} for every row the identity join names MISMATCH.

    ABSENT OR STALE LISTS NOTHING: the join is a live-book check, not one of the door's required
    verdict files, and a missing report is the absence of a finding. A report that EXISTS but is
    damaged raises `DoorReadError` from `_read` -- damage is not silence -- and `review_live`
    turns that into a named row per live sleeve, the door's fail-closed rule."""
    from libs.tiers import research_live_identity
    doc = _read(IDENTITY)
    if doc is None or not _fresh(doc):
        return {}
    rows = doc.get("rows")
    if rows is not None and not isinstance(rows, list):
        raise DoorReadError(f"{IDENTITY.name} rows are a {type(rows).__name__}")
    return research_live_identity.mismatch_reasons(doc)


def review_live(live_names: list[str]) -> dict[str, str]:
    """{LIVE row name: the reason the door would withhold it if it were promoted now}.

    The door must also act on rows ALREADY LIVE (verifier, 2026-09-30): a certificate whose
    replication failed, whose FDR budget was spent or whose own forward clock turned against it
    after it went live is no better for having gone live first. This is the same `block`, fail
    closed, run over the live book; the `door` organ publishes it as `data/tier_s/live_door.json`
    for the promoter's automatic retirement to read, billed like every door verdict.

    PLUS ONE CHECK ONLY A LIVE ROW CAN FAIL: the research-live identity join. A LIVE sleeve whose
    traded spec differs from the certified one (`IDENTITY_MISMATCH`) is trading a strategy no
    certificate covers, so it is listed here beside the six door verdicts."""
    out: dict[str, str] = {}
    try:
        ident = _identity_mismatches()
        ident_err = None
    except Exception as exc:
        ident, ident_err = {}, (f"DOOR_ERROR: the identity check raised {type(exc).__name__}: "
                                f"{exc}; withheld until it runs clean")
    for name in live_names:
        why = block(name) or ident_err or ident.get(name)
        if why:
            out[name] = why
    return out


def _door_error_from_why(why: str) -> dict[str, Any]:
    """The input a DOOR_ERROR names, parsed from its reason when `block` left no detail."""
    import re
    m = re.search(r"the (\w+) check raised", why)
    label = m.group(1) if m else "unknown"
    return {"check": label, "input": _CHECK_INPUT.get(label, label), "error": why[:300],
            "max_age_h": MAX_AGE_H, "window_start": None,
            "window_end": datetime.now(UTC).isoformat(timespec="seconds")}


def record(name: str, why: str, *, lane: str, exp_r: Any = None, n: Any = None) -> None:
    """Append one withheld promotion to the ledger `missed_growth` bills.

    A DOOR_ERROR row (an input absent, stale or damaged -- fail closed) also carries `door_error`:
    WHICH input withheld it and the WINDOW it was missing over, so `missed_growth.
    measure_tier_s_block` bills the cost of failing closed per input (gap E, 2026-09-30)."""
    firewall.may("promoter", "write", str(LEDGER.relative_to(ROOT)))
    row: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "name": name,
                           "lane": lane, "why": why, "reason": why.split(":", 1)[0],
                           "exp_r": exp_r, "n": n}
    if row["reason"] == "DOOR_ERROR":
        row["door_error"] = _LAST_DOOR_ERROR.pop(name, None) or _door_error_from_why(why)
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass
