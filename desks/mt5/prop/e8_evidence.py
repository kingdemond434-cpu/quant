"""E8 GOLD PLACEMENT EVIDENCE -- which host ran the pass, and what each due window decided.

WHY THIS EXISTS (measured on the trading box 2026-10-20). `scripts/check_placement_interlock.py`
reads `desks/mt5/data/decision_ledger.jsonl`, and only the Fusion gateway writes that file (its
last row was 10-16). `prop/e8_gold.py` wrote its state and its pass report and nothing else, so
an E8 window that stopped placing was invisible to the one fence built to see a silent halt, and
no record anywhere said WHICH machine had sent the E8 gold orders -- the question CLAUDE.md's
two-box history keeps making expensive.

TWO FILES, BOTH OWNED BY THIS LANE AND NEVER BY THE GATEWAY:

  `data/e8_gold_heartbeat.json`   rewritten on EVERY pass, flat or not, failed or not: the
                                  `libs/ops/host_identity` verdict, hostname, machine id, the pass
                                  time, its status, `last_ok_at` / `failing_since` and the
                                  account's pseudonym. One small file, written via a temporary
                                  file and `os.replace`.
  `data/e8_decision_ledger.jsonl` one row per DECISION, never per pass: a due window's outcome
                                  (PLACED / WOULD_PLACE / DEFERRED / SKIPPED), a stable reason
                                  code, the prose why, its window, lot and risk_usd, attributed to
                                  `lane: e8_gold` and the account pseudonym so no reader can mix it
                                  with Fusion's rows. Separate from the gateway's ledger because
                                  two processes appending to one file is a second writer to a
                                  record the gateway owns.

WHY ROWS ONLY AT DECISION POINTS. The pass runs every five minutes, and the interlock's breach (a)
counts consecutive not-taken rows sharing one reason. A per-pass row would turn a legitimate
one-gold-at-a-time deferral -- which can hold a window for hours while an earlier trade's stop is
short of break-even -- into thirty identical rows, i.e. a false halt. So a row is written when a
window's (outcome, reason) for the server day CHANGES (`state["evidence"]`, emptied by the
rollover), and a pass with no window due writes nothing at all. The fence then judges this lane
in decisions per server day, not rows per minute (see `E8_*` in the fence).

FAIL SAFE. Nothing here may block or alter a placement: every public function returns None (or
an empty list) instead of raising, logs what it could not write, and the placement code calls it
only after the orders have been decided.

A FAILED LEDGER WRITE IS KEPT, NOT RE-DERIVED (v2, audit of 75004b6a). v1 left the dedupe mark
unset and relied on the next pass deciding the same thing again -- true of a deferral, false of a
placement: once a window is placed it is no longer due, so a lost PLACED row was lost for good,
and the audit's probe turned refusal / lost PLACED / refusal into a false two-day HALT. The rows
a write could not land now ride in `state["evidence_pending"]` (bounded, carried across the
rollover by `carry_pending`) and are written first on the next pass, with their own stamps.

A RE-SENT LEG IS A PLACEMENT (v2). `_retry_failed_legs` re-sends a leg the venue refused while
its window holds; v1 wrote no row for it, so the fence had to exempt `venue_rejected` outright and
five days of refusals with nothing placed read OK. Every successful re-send (or adoption of a send
that had landed) is now a PLACED row and every abandoned leg a row of its own, so `venue_rejected`
breaches like any desk-side refusal.

THE ACCOUNT IS PSEUDONYMISED BEFORE IT IS WRITTEN (v2). Both files are published to the public
branch by `desks/mt5/scripts/sync_shadow_to_git.ps1`, and no live account id may land in a tracked
file (tests/ops/test_live_infrastructure_is_not_published.py). A plain hash of a seven-digit id is
reversed by enumerating ten million ids, so the label is an HMAC-SHA256 under a box-local key
(`data/secrets/e8_evidence.key`, created on first use, never leaves the box): stable, so the fence
can still key runs by account, and meaningless off the box. An unreadable key writes `UNKEYED`,
never the raw id. The raw label stays on the unpublished pass report (reports/E8_GOLD.json).
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LANE = "e8_gold"
DECISIONS_NAME = "e8_decision_ledger.jsonl"
HEARTBEAT_NAME = "e8_gold_heartbeat.json"
#: Tests redirect both files here, exactly as MT5_ORDER_DOOR_DIR redirects the order door's.
DIR_ENV = "E8_EVIDENCE_DIR"
#: The pseudonym key: an explicit value, else a key file (tests redirect it).
KEY_ENV = "E8_EVIDENCE_KEY"
KEY_FILE_ENV = "E8_EVIDENCE_KEY_FILE"
KEY_FILE = DESK.parent.parent / "data" / "secrets" / "e8_evidence.key"
#: An explicit $E8_EVIDENCE_KEY shorter than this is no key (UNKEYED), never a weak one: the
#: file key is 64 hex characters, and a short secret is guessable alongside a 7-digit id.
KEY_MIN_CHARS = 32
UNMEASURED = "UNMEASURED"
UNKEYED = "UNKEYED"
#: What the scrub writes in place of an account id found in prose.
REDACTED = "<account>"
#: TradeLocker's own trade URLs and error texts carry the id: `/trade/accounts/<id>/orders`,
#: `accNum: 3`, `account 1234567`. Digits after an "account"-ish word are an id until proven
#: otherwise; prices, lots and order ids never follow that word in this lane's prose.
#: v5: the word may be followed by `_` or `-` (`acc_<id>`, `account-<id>`), which `\b` refused
#: because `_` is a word character -- the leak when the pass does not know its own id.
#: Bracket guard v5 (auditor's evidence v5 note): `subacc_<id>` (a `sub` prefix the `(?<![a-z])`
#: refused), `acc.<id>` (a dot separator) and `accountNumber=<id>` (a `number` suffix) leaked too.
_ACCOUNT_IN_TEXT = re.compile(
    r"(?i)((?<![a-z])(?:sub[_\-]?)?acc(?:ount)?(?:s|_?id|_?number|_?num|num)?(?![a-z])"
    r"[\s\\/:=#\"'_.\-]*)(\d{2,})")
#: The account this pass trades, bound by `e8_gold.run` (`bind_account`) so that text clipped
#: deep in the pass -- a retry's refusal, a position-book error -- is scrubbed of the id BEFORE it
#: is cut (v5: a bare id at the cut left a 2-6 digit prefix the later scrub could not match).
_PASS_ACCOUNT: list[str] = [UNMEASURED]
#: THE CROSS-LANE ACCOUNT STAMP (bracket guard v5, must-fix 7 and the evidence v5 note): the same
#: `account_key` the cross-account OCO books carry, so an E8 evidence row, a stop exit and an OCO
#: book join on one value. It is `libs.ops.provenance.account_key(login, server, create=False)`
#: -- "sha256:" + 16 hex of an HMAC under the box key -- and nothing else: when that helper is not
#: on this tree (it lands with publish_sync v5), or holds no key, or the login is not an integer,
#: there is NO stamp. Never the raw login, never a plain sha256 of it (reversed by enumerating
#: ten million ids). Bound per pass by `bind_account_key`, reset by `bind_account`.
_PASS_ACCOUNT_KEY: list[str | None] = [None]
ACCOUNT_KEY_SHAPE = re.compile(r"^sha256:[0-9a-f]{16}$")
#: Rows a failed write keeps for the next pass. A day writes a handful; this is weeks of them.
PENDING_MAX = 500
#: The ledger is bounded: past LEDGER_MAX_BYTES it is rewritten to its newest LEDGER_KEEP_LINES.
#: A row is ~500 bytes and a day writes a few, so 2,000 rows is over a year -- far past the
#: fence's longest look back (E8_RUN_MAX_AGE_HOURS) -- and 1 MB stays far under the publisher's
#: 4 MB per-file cap ($ReportCapBytes).
LEDGER_MAX_BYTES = 1_000_000
LEDGER_KEEP_LINES = 2000

# OUTCOMES. Only PLACED put an order at the venue; the fence reads `taken` from it.
PLACED = "PLACED"
WOULD_PLACE = "WOULD_PLACE"
DEFERRED = "DEFERRED"
SKIPPED = "SKIPPED"

# REASON CODES -- stable, short, never prose, because the fence's run is "consecutive rows sharing
# one reason" and a reason carrying position ids or dollar figures would never repeat. The prose
# rides beside it in `why`. `scripts/check_placement_interlock.py` classifies every code (pinned
# by tests/governance/test_placement_interlock_fence.py).
R_PLACED = "placed"
R_SHADOW = "shadow_unarmed"
R_VENUE_REJECTED = "venue_rejected"
R_LEGS_UNAVAILABLE = "legs_unavailable"
R_UNSIZEABLE = "unsizeable"
R_KELLY_ZERO = "kelly_zero"
R_ONE_AT_RISK = "one_at_risk"
R_RISK_BUDGET = "risk_budget"
R_SIDE_UNREADABLE = "side_unreadable"
R_RISK_UNMEASURABLE = "risk_unmeasurable"
R_EQUITY_UNREADABLE = "equity_unreadable"
R_GUARD_UNREADABLE = "guard_unreadable"
R_POSITIONS_UNREADABLE = "positions_unreadable"
#: A dropped leg given up after its window had already placed something of its own (the twin
#: leg rests or filled): the window traded, so this is not a refusal of the window.
R_LEG_ABANDONED = "leg_abandoned"
#: A dropped leg given up because a position on its side opened after the failed send and no
#: window owns it -- it may BE that send (UNOWNED_BLOCK_RAIL, billed as missed growth).
R_UNOWNED_POSITION = "unowned_position"
#: A send (first or re-send) the cross-account fence refused because the other account holds the
#: opposite gold position (`e8_gold.fenced_send`, Fusion r4; RAIL_BLOCKED / cross_account_opposite
#: in the intents journal). Declared here ahead of that merge so the fence already classifies it:
#: a policy answer like one_at_risk, exempt. The window is retried on a later pass.
R_CROSS_ACCOUNT_OPPOSITE = "cross_account_opposite"
#: The bracket lane's three sizing rails (`e8_gold`, bracket guard v4: LOT_CEILING_REASON,
#: DAILY_FLOOR_REASON, PROFIT_CAP_REASON). Each rail SHRINKS the lot to fit; a window it shrank is
#: PLACED (reason `placed`, the rail named in `why`). Only a lot that would fall under the venue
#: minimum is refused -- SKIPPED with one of these codes. They are NOT exempt: unlike
#: R_RISK_BUDGET (the lane's concurrent-risk policy answer) a run of them means the rail is taking
#: the book to zero day after day, which is exactly what the fence exists to see. Declared ahead
#: of that merge so the fence already classifies them.
R_LOT_CEILING = "lot_ceiling"
R_BRACKET_DAILY_FLOOR = "bracket_daily_floor"
R_DAILY_PROFIT_CAP = "daily_profit_cap"
#: The guard's own verdicts, as `guard_<verdict>` (e8_guard.Verdict, lower-cased).
GUARD_PREFIX = "guard_"


def _dir() -> Path:
    override = os.environ.get(DIR_ENV)
    return Path(override) if override else DESK / "data"


def decisions_path() -> Path:
    return _dir() / DECISIONS_NAME


def heartbeat_path() -> Path:
    return _dir() / HEARTBEAT_NAME


def _say(log: Callable[[str], None] | None, msg: str) -> None:
    if log is None:
        return
    with contextlib.suppress(Exception):
        log(msg)


def host_block() -> dict[str, Any]:
    """This machine through `libs/ops/host_identity`, the helper every fence shares. Never raises:
    an identity that cannot be read is recorded as UNMEASURED, never guessed from a label."""
    try:
        from libs.ops import host_identity
        ident = host_identity.identify()
        return {"verdict": ident.verdict, "hostname": ident.hostname,
                "machine_id": ident.machine_id,
                "recorded_machine_id": ident.recorded_machine_id,
                "may_be_trading": ident.may_be_trading, "why": ident.why}
    except Exception as exc:
        return {"verdict": UNMEASURED, "hostname": UNMEASURED, "machine_id": UNMEASURED,
                "why": f"host_identity unavailable ({type(exc).__name__})"}


def account_label(venue: Any) -> str:
    """The venue account this lane trades, as `tradelocker:<id>`, or UNMEASURED. Read from the SDK
    handle's own attributes; never a credential, never a call that could raise into the pass."""
    try:
        api = venue._api
    except Exception:
        return UNMEASURED
    for attr in ("account_id", "acc_num"):
        try:
            value = getattr(api, attr, None)
        except Exception:
            continue
        if isinstance(value, (int, str)) and str(value).strip() not in ("", "0"):
            return f"tradelocker:{str(value).strip()}"
    return UNMEASURED


_KEY_CACHE: dict[str, bytes] = {}


def _key() -> bytes | None:
    """The box-local pseudonym key: $E8_EVIDENCE_KEY, else the key file, created on first use.
    None when neither can be had -- the caller then writes UNKEYED, never the raw id."""
    explicit = os.environ.get(KEY_ENV)
    if explicit is not None and explicit != "":
        # Set but short is treated as NO key (UNKEYED), never silently swapped for the file key.
        return explicit.encode("utf-8") if len(explicit) >= KEY_MIN_CHARS else None
    path = Path(os.environ.get(KEY_FILE_ENV) or KEY_FILE)
    cached = _KEY_CACHE.get(str(path))
    if cached:
        return cached
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(FileExistsError), path.open("x", encoding="ascii") as fh:
                fh.write(os.urandom(32).hex())
        key = path.read_text("ascii").strip().encode("ascii")
    except Exception:
        return None
    if len(key) < KEY_MIN_CHARS:
        return None
    _KEY_CACHE[str(path)] = key
    return key


def account_ref(label: str) -> str:
    """The pseudonym written in place of the account: `<venue>:<16 hex of HMAC-SHA256>`. Stable
    on one box, so the fence can tell two accounts apart; never the id. Never raises."""
    try:
        text = str(label or "")
        if not text or text == UNMEASURED or ":" not in text:
            return UNMEASURED
        venue = text.split(":", 1)[0]
        key = _key()
        if key is None:
            return f"{venue}:{UNKEYED}"
        return f"{venue}:{hmac.new(key, text.encode('utf-8'), hashlib.sha256).hexdigest()[:16]}"
    except Exception:
        return UNMEASURED


class Decisions:
    """What each due window decided on this pass, collected while the pass runs.

    `note` never raises: it is called from inside the placement block, and a bookkeeping error
    there must cost a row, never an order. `risk_of(window)` supplies the window's planned risk in
    USD for a row that never reached sizing (a deferral)."""

    def __init__(self, risk_of: Callable[[str], float | None] | None = None) -> None:
        self.rows: list[dict[str, Any]] = []
        self._risk_of = risk_of

    def note(self, window: str, outcome: str, reason: str, why: str = "", *,
             lot: float | None = None, risk_usd: float | None = None) -> None:
        try:
            risk = risk_usd
            if risk is None and self._risk_of is not None:
                risk = self._risk_of(window)
            self.rows.append({
                "window": str(window), "outcome": str(outcome), "reason": str(reason),
                "taken": outcome == PLACED, "why": scrub(str(why or ""))[:300],
                "lot": float(lot) if lot is not None else None,
                "risk_usd": round(float(risk), 2) if risk is not None else None,
            })
        except Exception:
            pass

    def windows(self) -> set[str]:
        return {r["window"] for r in self.rows}


def _raw_id(label: str) -> str | None:
    try:
        text = str(label or "")
        if ":" not in text or text == UNMEASURED:
            return None
        raw = text.split(":", 1)[1].strip()
        return raw if raw and raw not in (UNMEASURED, UNKEYED) else None
    except Exception:
        return None


def bind_account(label: str) -> None:
    """Bind the pass's raw account label for `clip` and an account-less `scrub`; the pass's
    account stamp is reset (`bind_account_key` sets it again). Never raises."""
    with contextlib.suppress(Exception):
        _PASS_ACCOUNT[0] = str(label or UNMEASURED)
        _PASS_ACCOUNT_KEY[0] = None
        _PASS_ACCOUNT_KEY_STATUS[0] = AK_HELPER_ABSENT


#: Why the pass carries no account stamp (v5.1, the auditor's key-join ruling), or OK.
AK_OK = "OK"
AK_HELPER_ABSENT = "HELPER_ABSENT"          # libs.ops.provenance not on this tree: dormant
AK_LOGIN_UNREADABLE = "LOGIN_UNREADABLE"    # the SDK handle names no account id
AK_SERVER_UNREADABLE = "SERVER_UNREADABLE"  # TLAPI `_credentials` carries no server
AK_KEY_UNAVAILABLE = "KEY_UNAVAILABLE"      # the helper answered no well-shaped key
#: EVERY missing stamp pages (v5.2, audit HOLD on 8fe4edce): an unreadable login or server, a
#: helper that answered no key (no box key, a login of -5), and a helper that is not on the tree
#: -- once OCO v2 reads the key, a silent None is a join that fails without anyone knowing.
#: Paged through the desk's alert ledger (`page_account_key`); only OK closes the page.
AK_PAGE = frozenset({AK_LOGIN_UNREADABLE, AK_SERVER_UNREADABLE, AK_KEY_UNAVAILABLE,
                     AK_HELPER_ABSENT})
#: The alert the page opens (libs/ops/alert_ledger.AlertLedger) and where the ledger lives.
AK_ALERT_ID = "e8_account_key_unstamped"
ALERT_LEDGER_ENV = "E8_ALERT_LEDGER"
ALERT_LEDGER = DESK.parent.parent / "data" / "alert_ledger.json"
_PASS_ACCOUNT_KEY_STATUS: list[str] = [AK_HELPER_ABSENT]


def _tl_api(venue: Any) -> Any:
    api = getattr(venue, "_raw_api", None)
    return api if api is not None else getattr(venue, "_api", None)


def tradelocker_login(venue: Any) -> Any:
    """The account id from the TLAPI handle (`account_id`, else `acc_id`), as the SDK holds it,
    or None. Not normalised here: `provenance.account_key` normalises the login itself. `acc_num`
    is the account's index on the user (1, 2, ...), never the id, so it is not read."""
    try:
        api = _tl_api(venue)
        for attr in ("account_id", "acc_id"):
            v = getattr(api, attr, None)
            if v is None or isinstance(v, bool) or str(v).strip() in ("", "0"):
                continue
            return v
    except Exception:
        return None
    return None


def tradelocker_server(venue: Any) -> str | None:
    """The E8 server from TLAPI 0.56.2's `_credentials` dict ({"username", "password",
    "server"}), or None. NEVER `api.server`: TLAPI has no such attribute, so a read of it is
    None and keyed every account to one server. Only the server is read. Never raises.

    v5.2: the server is passed RAW -- no strip, no case-folding. `provenance.account_key` (v5c)
    strips it itself, so the key is the HMAC of the normalised login, "@", and the stripped
    server, exactly as the auditor's reference derivation has it. A blank server is no server."""
    try:
        creds = getattr(_tl_api(venue), "_credentials", None)
        server = creds.get("server") if isinstance(creds, dict) else None
        return server if isinstance(server, str) and server.strip() else None
    except Exception:
        return None


def account_key_status(venue: Any) -> tuple[str | None, str]:
    """(the HMAC account stamp or None, why). Fails CLOSED: no helper, no login, no server or no
    well-shaped answer is no stamp. Never raises."""
    try:
        import importlib

        # libs/ops/provenance.py lands with publish_sync v5; absent -> ImportError -> no stamp.
        try:
            provenance = importlib.import_module("libs.ops.provenance")
        except ImportError:
            return None, AK_HELPER_ABSENT
        helper = getattr(provenance, "account_key", None)
        if not callable(helper):
            return None, AK_HELPER_ABSENT
        login = tradelocker_login(venue)
        if login is None:
            return None, AK_LOGIN_UNREADABLE
        server = tradelocker_server(venue)
        if server is None:
            return None, AK_SERVER_UNREADABLE
        key = helper(login, server, create=False)
        if isinstance(key, str) and ACCOUNT_KEY_SHAPE.match(key):
            return key, AK_OK
        return None, AK_KEY_UNAVAILABLE
    except Exception:
        return None, AK_KEY_UNAVAILABLE


def account_key(venue: Any) -> str | None:
    """The HMAC account stamp of `venue`'s account, or None (fail closed). Never raises."""
    return account_key_status(venue)[0]


def page_account_key(status: str, log: Callable[[str], None] | None = None) -> str | None:
    """Open (or, once stamped again, close) the `AK_ALERT_ID` alert in the desk's alert ledger.
    Every status in AK_PAGE opens it (v5.2: a dormant helper and a keyless answer too).
    Returns "OPEN", "FIXED" or None. Never raises, and never touches a placement.

    v5.6: the read-modify-save runs under ONE lock (`_ledger_txn`, the v5f AlertLedger
    semantics): an unreadable ledger is never saved over, and a busy lock gives up after
    AK_LOCK_WAIT_S instead of going on unlocked.

    On v5f each transition is also ENQUEUED (`_PAGE` = provenance._page): OPEN with the status
    as its sig, OK on the close. An append, never a send, so this stays off the network."""
    try:
        path = _ledger_path()
        if status in AK_PAGE:
            msg = (f"[e8_gold] account_key not stamped: {status}; "
                   "stop exits and evidence carry no cross-account key")
            with _ledger_txn(path, AK_LOCK_WAIT_S) as txn:
                txn.ledger.observe(AK_ALERT_ID, msg, scope="RUNTIME")
                txn.dirty = True
            if _enqueue_only():
                with contextlib.suppress(Exception):
                    _PAGE(AK_ALERT_ID, "OPEN", status, "E8 gold: account_key not stamped", msg)
            return "OPEN"
        if status == AK_OK and path.exists():
            with _ledger_txn(path, AK_LOCK_WAIT_S) as txn:
                alert = txn.ledger.alerts.get(AK_ALERT_ID)
                if alert is not None and alert.open:
                    txn.ledger.verify(AK_ALERT_ID, still_firing=False)
                    txn.dirty = True
            if txn.dirty and _enqueue_only():
                with contextlib.suppress(Exception):
                    _PAGE(AK_ALERT_ID, "OK", "recovered", "E8 gold: account_key stamped again",
                          "the E8 pass stamps account_key again")
            return "FIXED" if txn.dirty else None
    except Exception as exc:
        _say(log, f"account-key alert not recorded ({type(exc).__name__})")
    return None


# ------------------------------------------------------------------ the alert ledger and pager
#
# v5.6 (audit HOLD on 04e58c70, must-fix "page_alert is not a page"). v5.5's page_alert wrote
# alert_ledger.json and nothing else -- no organ forwards that ledger to a channel -- and did it
# synchronously on the order path. Now:
#
#   * page_alert QUEUES the work on a daemon thread and returns at once; `run()` never waits on it
#     (the pass's `main` drains it, bounded, after the pass, so a short-lived process still
#     delivers -- `drain_pages`).
#   * the ledger's read-modify-save runs under ONE OS lock (`_ledger_txn`), mirroring publish_sync
#     v5f's `AlertLedger.transaction`: the same `<ledger>.flock` sidecar, never deleted, never
#     broken as stale, a wait that expires gives up (no second holder), and a ledger that exists
#     but cannot be read is never saved over (an unparseable one is set aside, kept).
#   * the page is SENT only on the transition to open (absent, FIXED -> firing); a standing
#     alert re-observed is ledger dedup, not a new page. The send goes through `_PAGE`, which has
#     `libs.ops.provenance._page`'s signature (aid, status, sig, title, body) -> dict and never
#     raises; here it is `_page_direct`: alert_channels.send_all on its own daemon thread, joined
#     for at most PAGE_TIMEOUT_S, every exception swallowed and logged.
#
# THE ONE-LINE SWITCH once publish_sync v5e/v5f is merged (v5f's `_page` is enqueue-only, so the
# send leaves this process entirely):
#
#     _PAGE = provenance._page      # from libs.ops import provenance
#
# and `_ledger_txn` may then be replaced by `AlertLedger.transaction` (same lock file).

#: How long a page's send may run before the worker gives up waiting on it (it is never awaited
#: by `run`; this bounds the worker thread and `drain_pages`).
PAGE_TIMEOUT_S = 15.0
#: The ledger lock wait: the queued worker may wait this long; the synchronous account-key page
#: (pass start, before any order) waits less.
LOCK_WAIT_S = 10.0
AK_LOCK_WAIT_S = 2.0


class AlertLedgerBusy(TimeoutError):
    """The ledger lock was not obtained within the wait: nothing was written."""


class AlertLedgerUnreadable(OSError):
    """The ledger exists and could not be read: saving now would replace it with less."""


def _ledger_path() -> Path:
    return Path(os.environ.get(ALERT_LEDGER_ENV) or ALERT_LEDGER)


@contextlib.contextmanager
def _os_lock(lock: Path, timeout_s: float) -> Any:
    """An exclusive OS lock on a sidecar that is never deleted (v5f's `os_lock`): msvcrt on
    Windows, flock elsewhere. Released when the handle closes, including on a crash, so there is
    no stale lock to break and never a second holder. A wait that expires RAISES."""
    import sys
    import time

    lock.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock, "a+b")  # noqa: SIM115 -- held for the whole body, closed below
    try:
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, ImportError) as exc:
                if time.monotonic() >= deadline:
                    raise AlertLedgerBusy(f"{lock.name} held for {timeout_s:g}s") from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            with contextlib.suppress(OSError, ImportError):
                if sys.platform == "win32":
                    import msvcrt
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


class _Txn:
    def __init__(self, ledger: Any) -> None:
        self.ledger = ledger
        self.dirty = False


@contextlib.contextmanager
def _ledger_txn(path: Path, timeout_s: float = LOCK_WAIT_S) -> Any:
    """Lock, read, yield, and (only when the body set `dirty`) write atomically -- one critical
    section. A ledger that exists and cannot be read raises AlertLedgerUnreadable and writes
    nothing; one that reads but does not parse is moved aside (kept) and started afresh. The
    write is temp file + fsync + os.replace, never `AlertLedger.save` (whose v5f form takes this
    same lock, which would deadlock here)."""
    import time
    from dataclasses import asdict

    from libs.ops.alert_ledger import AlertLedger

    with _os_lock(path.with_name(path.name + ".flock"), timeout_s):
        try:
            text: str | None = path.read_text("utf-8")
        except FileNotFoundError:
            text = None
        except OSError as exc:
            raise AlertLedgerUnreadable(f"{path.name}: {type(exc).__name__}; not saved over") \
                from exc
        if text is not None:
            try:
                raw = json.loads(text)
                if not isinstance(raw, dict) or not isinstance(raw.get("alerts") or {}, dict):
                    raise ValueError("not a ledger")
            except ValueError:
                with contextlib.suppress(OSError):
                    os.replace(path, path.with_name(f"{path.name}.unparseable-{time.time_ns()}"))
        led = AlertLedger(path)
        txn = _Txn(led)
        yield txn
        if not txn.dirty:
            return
        body = json.dumps({
            "updated": datetime.now(UTC).isoformat(),
            "alerts": {a.id: asdict(a) for a in led.alerts.values()},
            "note": ("`last_seen` is dedup state and `state` is truth -- they are never the same "
                     "field. Suppressing a repeat makes the pager quieter and does nothing about "
                     "the condition."),
        }, indent=1)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)


#: Tests (and only tests) replace this; None means alert_channels.send_all, against the channels
#: config beside the alert ledger when $E8_ALERT_LEDGER overrides it (so a test's temp ledger can
#: never reach the real channels), else the box's data/secrets/alert_channels.json.
SENDER: Callable[[str, str], Any] | None = None


def _default_send(title: str, body: str) -> Any:
    from libs.ops import alert_channels

    override = os.environ.get(ALERT_LEDGER_ENV)
    if override:
        base = Path(override).parent
        return alert_channels.send_all(title, body, config=base / "secrets" / "alert_channels.json",
                                       ledger=base / "alert_delivery.jsonl")
    return alert_channels.send_all(title, body)


def _page_direct(aid: str, status: str, sig: str, title: str, body: str) -> dict[str, Any]:
    """`provenance._page`'s signature and contract (never raises, a dict back): the send runs on
    its own daemon thread, joined for at most PAGE_TIMEOUT_S, every exception swallowed."""
    import threading

    out: dict[str, Any] = {"sent": False, "reason": "timed out"}

    def _go() -> None:
        try:
            res = (SENDER or _default_send)(title, body[:1500])
            res = res if isinstance(res, dict) else {}
            out.update(sent=bool(res.get("delivered")), reason="sent" if res.get("delivered")
                       else "undelivered", delivered=res.get("delivered"), armed=res.get("armed"))
        except Exception as exc:
            out.update(sent=False, reason=f"sender raised {type(exc).__name__}")

    try:
        t = threading.Thread(target=_go, daemon=True, name=f"e8-send-{aid}")
        t.start()
        t.join(PAGE_TIMEOUT_S)
    except Exception as exc:
        out.update(sent=False, reason=f"not started ({type(exc).__name__})")
    return out


#: THE PAGER: publish_sync v5f's enqueue-only `provenance._page` (the one-line switch, made on
#: claude/e8-bracket-v5_6-on-v5f). It appends one outbox row and returns; v5f's
#: `deliver_pending` (MT5-BoxHeartbeat every 5 min, MT5-ProcessHealth hourly) sends it, under its
#: own lock, with v5f's dedupe and 6 h repage. `_page_direct` stays as the fallback for a tree
#: without the helper.
try:
    from libs.ops import provenance as _provenance
except Exception:  # pragma: no cover - a tree without publish_sync v5f
    _provenance = None  # type: ignore[assignment]
_PAGE: Callable[[str, str, str, str, str], dict[str, Any]] = (
    _provenance._page if _provenance is not None else _page_direct)


def _enqueue_only() -> bool:
    """True when `_PAGE` is v5f's outbox (never a send), so every ledger write may call it."""
    return _PAGE is not _page_direct
_PENDING: list[Any] = []


def _alert_worker(aid: str, message: str, firing: bool,
                  log: Callable[[str], None] | None) -> None:
    """Off the order path: the ledger transition under the lock, then a page on OPEN only."""
    try:
        path = _ledger_path()
        opened = False
        with _ledger_txn(path) as txn:
            alert = txn.ledger.alerts.get(aid)
            was_open = alert is not None and alert.open
            if firing:
                txn.ledger.observe(aid, message, scope="RUNTIME")
                txn.dirty, opened = True, not was_open
            elif was_open:
                txn.ledger.verify(aid, still_firing=False)
                txn.dirty = True
        # v5f's deliverer reads only its outbox, so EVERY ledger write is mirrored there: OPEN on
        # each firing write (v5f dedupes in-process and repages a standing incident every 6 h),
        # OK on the close. With the direct fallback, only an opening sends.
        if firing and (opened or _enqueue_only()):
            res = _PAGE(aid, "OPEN", aid, f"E8 gold: {aid}", message)
            _say(log, f"alert {aid} {'opened' if opened else 'firing'}; page {res.get('reason')}")
        elif txn.dirty and not firing and _enqueue_only():
            res = _PAGE(aid, "OK", aid, f"E8 gold: {aid} cleared", f"{aid} no longer firing")
            _say(log, f"alert {aid} closed; page {res.get('reason')}")
    except Exception as exc:
        _say(log, f"alert {aid} not recorded ({type(exc).__name__}: {exc})"[:200])


def page_alert(aid: str, message: str, *, firing: bool,
               log: Callable[[str], None] | None = None) -> str | None:
    """QUEUE an alert transition and return at once: "QUEUED", "NOTHING" (a close with no ledger
    on disk) or None. The worker opens (firing) or closes the alert in the desk's alert ledger
    under one lock and PAGES only when it opens. Never raises, never blocks the caller."""
    try:
        if not firing and not _ledger_path().exists():
            return "NOTHING"
        import threading

        msg = str(clip(scrub(message), 300)) if message else ""
        t = threading.Thread(target=_alert_worker, args=(aid, msg, firing, log), daemon=True,
                             name=f"e8-alert-{aid}")
        t.start()
        _PENDING[:] = [x for x in _PENDING if x.is_alive()] + [t]
        return "QUEUED"
    except Exception as exc:
        _say(log, f"alert {aid} not queued ({type(exc).__name__})")
        return None


def drain_pages(timeout_s: float = PAGE_TIMEOUT_S + LOCK_WAIT_S) -> int:
    """Wait (bounded) for queued alert work; returns how many are still running. Called by the
    pass's `main` AFTER `run` returns -- never from the order path -- and by tests."""
    import time

    deadline = time.monotonic() + max(0.0, timeout_s)
    for t in list(_PENDING):
        t.join(max(0.0, deadline - time.monotonic()))
    _PENDING[:] = [x for x in _PENDING if x.is_alive()]
    return len(_PENDING)


def bind_pass_account_key(venue: Any, doc: dict[str, Any] | None = None,
                          log: Callable[[str], None] | None = None) -> str:
    """Derive, bind and report this pass's account stamp: the key (or None), its status on the
    pass report, an alert line in `doc["alerts"]` and a page when the venue could not be read.
    Returns the status. Never raises."""
    key, status = account_key_status(venue)
    bind_account_key(key)
    with contextlib.suppress(Exception):
        _PASS_ACCOUNT_KEY_STATUS[0] = status
        if doc is not None:
            doc["account_key_status"] = status
            if status in AK_PAGE:
                doc.setdefault("alerts", []).append(
                    f"account_key not stamped ({status}): failing closed, no key written")
    if status in AK_PAGE:
        _say(log, f"ACCOUNT KEY NOT STAMPED ({status}); failing closed, paging")
    page_account_key(status, log)
    return status


def bound_account_key_status() -> str:
    try:
        return str(_PASS_ACCOUNT_KEY_STATUS[0])
    except Exception:
        return AK_KEY_UNAVAILABLE


def bind_account_key(key: str | None) -> None:
    """Bind the pass's account stamp (only a well-shaped one; anything else binds None)."""
    with contextlib.suppress(Exception):
        _PASS_ACCOUNT_KEY[0] = key if isinstance(key, str) and ACCOUNT_KEY_SHAPE.match(key) \
            else None


def bound_account_key() -> str | None:
    """The account stamp bound for this pass, or None."""
    try:
        key = _PASS_ACCOUNT_KEY[0]
        return key if isinstance(key, str) and ACCOUNT_KEY_SHAPE.match(key) else None
    except Exception:
        return None


def clip(text: Any, limit: int, account: str | None = None) -> str:
    """`str(text)` scrubbed of the account id and THEN cut to `limit` (v5). Never raises."""
    try:
        return str(scrub(str(text), account or UNMEASURED))[:limit]
    except Exception:
        return "<unscrubbed text withheld>"[:limit]


def scrub(value: Any, account: str = UNMEASURED) -> Any:
    """`value` with every account id taken out (recursively through dicts, lists and tuples, dict
    KEYS included): the raw id of `account` -- or, when none is given, of the account the pass
    bound (`bind_account`) -- wherever it stands between non-digits, and any digits that follow an
    account-ish word (a TradeLocker URL or error). A non-string leaf (an int or float id) whose
    text carries the id is replaced by the marker (v5). Never raises: on an internal error a
    string is replaced whole, never kept raw."""
    try:
        if (not account or account == UNMEASURED) and _PASS_ACCOUNT[0] != UNMEASURED:
            account = _PASS_ACCOUNT[0]
        if isinstance(value, dict):
            return {scrub(k, account) if isinstance(k, str) else _scrub_leaf(k, account):
                    scrub(v, account) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [scrub(v, account) for v in value]
        if not isinstance(value, str):
            return _scrub_leaf(value, account)
        out = _ACCOUNT_IN_TEXT.sub(lambda m: m.group(1) + REDACTED, value)
        raw = _raw_id(account)
        if raw:
            # DIGIT boundaries, not word boundaries (v4): `acc_<id>`, `x<id>` and a sentence-final
            # `<id>.` all carry the id touching a letter, `_` or `.`, and `\w`/`.` lookarounds let
            # every one of them through. Only an adjacent DIGIT means it is part of another number.
            out = re.sub(r"(?<!\d)" + re.escape(raw) + r"(?!\d)", REDACTED, out)
        return out
    except Exception:
        return "<unscrubbed text withheld>" if isinstance(value, str) else value


def _scrub_leaf(value: Any, account: str) -> Any:
    """A non-string leaf: kept as it is unless its text carries the account id."""
    if value is None or isinstance(value, bool):
        return value
    raw = _raw_id(account)
    if not raw:
        return value
    text = str(value)
    return REDACTED if scrub(text, account) != text else value


def publishable(value: Any, account: str = UNMEASURED) -> Any:
    """`value` exactly as it will be written -- through `json.dumps(default=str)` and back, so a
    non-str leaf (an exception, a Path, a custom object) is the text it will become -- and then
    scrubbed (v4: a non-str `extra` value used to reach the file raw). Never raises."""
    try:
        return scrub(json.loads(json.dumps(value, default=str)), account)
    except Exception:
        return scrub(value, account)


def key_id() -> str | None:
    """A short public fingerprint of the pseudonym key (a hash of it, never the key), written
    beside every `account_ref` so the fence can tell a NEW KEY for the same account from a
    different account (v4). None when there is no key."""
    try:
        key = _key()
        if key is None:
            return None
        return hashlib.sha256(b"e8-evidence-key-id:" + key).hexdigest()[:12]
    except Exception:
        return None


def stand_down_reason(equity: float, guard_decision: Any, doc: dict[str, Any]) -> str:
    """Why `run` placed nothing this pass, as a reason code, derived after the fact from what the
    pass already recorded -- the guard block itself is not touched. First cause wins: an equity
    the venue would not state, a guard that raised, the guard's verdict, the position book."""
    try:
        if not equity > 0:
            return R_EQUITY_UNREADABLE
        if guard_decision is None:
            return R_GUARD_UNREADABLE
        if not guard_decision.may_open:
            return GUARD_PREFIX + str(guard_decision.verdict.value).lower()
        if doc.get("positions_unreadable"):
            return R_POSITIONS_UNREADABLE
    except Exception:
        pass
    return R_GUARD_UNREADABLE


def window_outcome(legs: dict[str, dict[str, Any]], failed: dict[str, dict[str, Any]], *,
                   armed: bool, unsizeable: bool) -> tuple[str, str, str, float | None]:
    """(outcome, reason, why, lot) for a window that reached the leg loop. Pure.

    PLACED when an armed pass sent at least one leg; WOULD_PLACE for the same in shadow; DEFERRED
    when every leg the venue was sent failed (`_retry_failed_legs` re-sends it while the window
    holds); otherwise SKIPPED -- a leg the sizer could not size, or no leg available at all (the
    level is already through the price, or the one legal leg would trade against the book).
    Called inside the placement loop, so a malformed leg reads as an unknown lot, never a raise."""
    try:
        return _window_outcome(legs, failed, armed=armed, unsizeable=unsizeable)
    except Exception as exc:
        # Unreachable on any input the leg loop builds; if it ever is reached, the window still
        # leaves a row -- one the fence does not exempt, so it is seen.
        return SKIPPED, R_LEGS_UNAVAILABLE, f"outcome not derived ({type(exc).__name__})", None


def _window_outcome(legs: dict[str, dict[str, Any]], failed: dict[str, dict[str, Any]], *,
                    armed: bool, unsizeable: bool) -> tuple[str, str, str, float | None]:
    try:
        lots = [float(v.get("lot") or 0.0) for v in (*legs.values(), *failed.values())]
        lot: float | None = max(lots) if lots else None
    except Exception:
        lot = None
    if legs and armed:
        return PLACED, R_PLACED, f"sent {', '.join(sorted(legs))}", lot
    if legs:
        return WOULD_PLACE, R_SHADOW, f"shadow: would send {', '.join(sorted(legs))}", lot
    if failed:
        first = next(iter(failed.values()), {})
        why = first.get("why") if isinstance(first, dict) else None
        return DEFERRED, R_VENUE_REJECTED, str(why or "venue refused"), lot
    if unsizeable:
        return SKIPPED, R_UNSIZEABLE, "the sizer returned no lot for this window's risk", 0.0
    return SKIPPED, R_LEGS_UNAVAILABLE, "no leg of the bracket was available to send", None


def abandon_reason(why: str, window: dict[str, Any]) -> str:
    """The reason code for a dropped leg `_retry_failed_legs` gave up on. Pure, never raises.

    The other leg filled, or the window holds an order of its own: the window traded, so the
    abandon is not a refusal (R_LEG_ABANDONED, exempt). An unowned position on the leg's side:
    R_UNOWNED_POSITION (exempt; it may be the send). Otherwise nothing of the window ever reached
    the venue and the last word was the venue's refusal, so the row CONTINUES the window's
    `venue_rejected` run -- which is what lets that run breach after E8_TRAILING_DAYS_MAX days."""
    try:
        if "other leg filled" in str(why):
            return R_LEG_ABANDONED
        if any(isinstance(v, dict) and v.get("id") is not None
               for v in (window.get("orders") or {}).values()):
            return R_LEG_ABANDONED
    except Exception:
        pass
    return R_VENUE_REJECTED


def pending_rows(decided: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    """The decisions that are NEW for today: a window's (outcome, reason) that differs from the
    last one recorded for it on this server day. Pure. `state["evidence"]` is window ->
    "OUTCOME:reason"; the rollover builds a fresh state, so a new day starts with none."""
    raw = state.get("evidence")
    seen: dict[str, Any] = raw if isinstance(raw, dict) else {}
    out: list[dict[str, Any]] = []
    for row in decided:
        key = f"{row.get('outcome')}:{row.get('reason')}"
        if seen.get(str(row.get("window"))) == key:
            continue
        out.append(row)
    return out


def carry_pending(old: dict[str, Any], new: dict[str, Any]) -> None:
    """Carry rows a failed write kept across the rollover, which builds a fresh state. Never
    raises; touches nothing a placement reads."""
    try:
        if new is old:
            return
        pending = old.get("evidence_pending")
        if isinstance(pending, list) and pending:
            new["evidence_pending"] = list(pending)[-PENDING_MAX:]
    except Exception:
        pass


def _bound_ledger(path: Path, log: Callable[[str], None] | None) -> None:
    """Rewrite the ledger to its newest LEDGER_KEEP_LINES once it passes LEDGER_MAX_BYTES, via a
    temporary file and `os.replace`. A failure leaves the file as it was. Never raises."""
    try:
        if path.stat().st_size <= LEDGER_MAX_BYTES:
            return
        lines = path.read_text("utf-8", errors="replace").splitlines(keepends=True)
        kept = "".join(lines[-LEDGER_KEEP_LINES:])
        if _atomic_write(path, kept, log=log, in_place_fallback=False):
            _say(log, f"E8 decision ledger rotated: kept the newest {LEDGER_KEEP_LINES} rows")
    except Exception as exc:
        _say(log, f"E8 decision ledger not rotated ({type(exc).__name__}: {exc})")


def record_decisions(decided: Decisions | list[dict[str, Any]], state: dict[str, Any], *,
                     now: datetime, server_date: str, account: str, armed: bool,
                     host: dict[str, Any], symbol: str = "XAUUSD",
                     log: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
    """Append this pass's NEW decisions -- after any rows an earlier failed write kept -- to the
    lane's ledger and mark them in `state`. Returns the rows written ([] when there were none or
    the write failed, in which case they are kept in `state["evidence_pending"]`). `account` is
    the raw label; only its pseudonym (`account_ref`) is written. Never raises."""
    new: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    try:
        rows = decided.rows if isinstance(decided, Decisions) else list(decided)
        new = pending_rows(rows, state)
        raw_pending = state.get("evidence_pending")
        pending = [r for r in raw_pending if isinstance(r, dict)] \
            if isinstance(raw_pending, list) else []
        if not new and not pending:
            return []
        stamp = now.isoformat(timespec="seconds")
        ref = account_ref(account)
        kid = key_id() if not ref.endswith(":" + UNKEYED) else None
        akey = bound_account_key()
        for row in new:
            sleeve = f"{LANE}:{row['window']}"
            line = publishable({
                "decided_at": stamp, "lane": LANE, "account_ref": ref, "key_id": kid,
                "sleeve": sleeve, "strategy_id": sleeve, "symbol": symbol,
                "server_date": server_date, "armed": bool(armed),
                "host": host.get("hostname"), "machine_id": host.get("machine_id"),
                "host_verdict": host.get("verdict"), **row,
            }, account)
            # The stamp goes on AFTER the scrub: it is an HMAC, never the id, and a hex run that
            # happened to contain the id's digits must not be mangled into a key nothing joins.
            if isinstance(line, dict):
                line["account_key"] = akey
            lines.append(line)
        # Rows kept by a failed write are scrubbed again on the way out: an OLDER build kept them
        # (v4), and this build's scrub is the one that publishes them.
        out = [*(publishable(r, account) for r in pending), *lines]
    except Exception as exc:
        _say(log, f"E8 decision evidence not built ({type(exc).__name__}: {exc}); "
                  "placement unaffected")
        return []
    # The marks are set whether or not the write lands: a row that fails is KEPT below, so
    # re-deriving it next pass would only duplicate it.
    try:
        marks = state.setdefault("evidence", {})
        for row in new:
            marks[row["window"]] = f"{row['outcome']}:{row['reason']}"
    except Exception:
        pass
    try:
        path = decisions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r, default=str) + "\n" for r in out))
    except Exception as exc:
        with contextlib.suppress(Exception):
            state["evidence_pending"] = out[-PENDING_MAX:]
        _say(log, f"E8 DECISION EVIDENCE WRITE FAILED ({type(exc).__name__}: {exc}); "
                  f"placement unaffected, {min(len(out), PENDING_MAX)} row(s) kept in the state "
                  "for the next pass")
        return []
    with contextlib.suppress(Exception):
        state.pop("evidence_pending", None)
    _bound_ledger(path, log)
    return out


def _atomic_write(path: Path, text: str, *, log: Callable[[str], None] | None = None,
                  in_place_fallback: bool = True) -> bool:
    """Write `text` to `path` through a temporary sibling and `os.replace`. Never raises.

    ON WINDOWS `os.replace` RAISES WinError 5 (PermissionError) onto a read-only destination, or
    onto one another process holds open without FILE_SHARE_DELETE -- which is how Python itself
    opens a file a reader is reading. POSIX allows both, so a test passing on Linux proves
    nothing here. When the replace is refused, the text is written in place instead
    (`in_place_fallback`): Python readers share write access, so this lands for the reader-holds-
    it case, and a reader catching it half-written reads a torn heartbeat, which the fence reads
    as UNMEASURED. A read-only file refuses both; that is logged and False returned. The
    temporary file is always removed."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        try:
            os.replace(tmp, path)
            return True
        except OSError as exc:
            if not in_place_fallback:
                raise
            _say(log, f"{path.name}: replace refused ({type(exc).__name__}: {exc}); "
                      "writing in place")
            path.write_text(text, encoding="utf-8")
            return True
    except Exception as exc:
        _say(log, f"{path.name} not written ({type(exc).__name__}: {exc})")
        return False
    finally:
        with contextlib.suppress(Exception):
            if tmp.exists():
                tmp.unlink()


def _previous_heartbeat() -> dict[str, Any]:
    try:
        prev = json.loads(heartbeat_path().read_text("utf-8"))
        return prev if isinstance(prev, dict) else {}
    except Exception:
        return {}


def write_heartbeat(status: str, *, at: datetime, armed: bool, account: str = UNMEASURED,
                    host: dict[str, Any] | None = None, extra: dict[str, Any] | None = None,
                    log: Callable[[str], None] | None = None) -> dict[str, Any] | None:
    """Rewrite the lane's heartbeat: this pass happened, on this host, with this result. Written
    on every pass, including a flat one and one whose connection failed. Never raises.

    `last_ok_at` (the last pass whose status was OK) and `failing_since` (the first pass of the
    current run of non-OK passes; None while OK) are carried from the previous heartbeat, so the
    fence can tell a pass that just failed from a lane that has failed for hours (v2, audit of
    75004b6a: a heartbeat from a failed pass was read as live and the lane as OK). A previous
    heartbeat that cannot be read starts the run afresh at this pass."""
    try:
        stamp = at.isoformat(timespec="seconds")
        ok = str(status) == "OK"
        prev = _previous_heartbeat()
        prev_failing = prev.get("failing_since") if str(prev.get("status")) != "OK" else None
        doc: dict[str, Any] = {
            "at": stamp, "lane": LANE, "status": str(status), "armed": bool(armed),
            "account_ref": account_ref(account),
            "last_ok_at": stamp if ok else prev.get("last_ok_at"),
            "failing_since": None if ok else (prev_failing or stamp),
            "host": host if host is not None else host_block(),
        }
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in doc:
                    doc[str(k)] = v
        if not str(doc["account_ref"]).endswith(":" + UNKEYED):
            doc["key_id"] = key_id()
        doc = publishable(doc, account)
        doc["account_key"] = bound_account_key()
        doc["account_key_status"] = bound_account_key_status()
        text = json.dumps(doc, indent=1, default=str) + "\n"
    except Exception as exc:
        _say(log, f"E8 heartbeat not built ({type(exc).__name__}: {exc}); pass unaffected")
        return None
    if not _atomic_write(heartbeat_path(), text, log=log):
        _say(log, "E8 heartbeat write failed; pass unaffected")
        return None
    return doc
