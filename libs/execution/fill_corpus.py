"""The fill corpus: one durable, append-only record per execution, carrying everything.

THE PRINCIPAL'S ORDER. "Turn every live fill into proprietary data. This is your small solo
firm's equivalent of building a RenTech historical corpus. For every execution retain: full
market state, reason for entry, strategy DNA, posterior edge estimate, predicted distribution,
spread, slippage, regime, cross-asset state, MAE, MFE, path after entry, exit reason, alternative
exits, counterfactual entries, realized R, prediction error."

WHY A THIRD FILE, WHEN THE DESK ALREADY HAS ELEVEN LEDGERS. It does not add a twelfth capture
point; it adds the JOIN, and the join is the asset. The gateway's ledgers each hold one moment
(what was asked, what the plan expected, what the deal did). `decision_dataset` holds the
decision minute and its priced alternatives. `execution_twin_cases` holds intent-versus-fill.
Every one of those is a projection, and a model of adverse selection needs the whole row: the
world at the decision, the quote at the send, the fill, the path AFTER the fill, the exit and
what the alternatives would have paid. Assembling that at query time from five files with five
different keys is how an analysis gets written once and never re-run. Assembling it once, on the
desk's own clock, into an append-only file with a schema version, is a corpus.

WHAT MAKES IT TRAINABLE RATHER THAN DESCRIPTIVE. The counterfactual fields. A record that says
"entered at market, made +0.4R" teaches nothing about execution; a record that also says what a
limit would have paid, what waiting five seconds would have paid, and what the trade would have
returned under the three exits the desk did not choose, is a labelled training row for exactly
the two models the principal asked for. Those fields come from the desk's own counterfactual
machinery (`libs.research.counterfactual_world`, priced by `counterfactual_replay`); this module
carries them onto the fill row and never invents one.

THE CAPTURE RULE, AND WHY IT IS THE WHOLE POINT. An unrecorded fill cannot be recovered later.
A field this corpus does not carry today is not a gap that can be backfilled next quarter -- the
tick that would have priced it is gone. So `completeness()` is a first-class output, not a
diagnostic: it names, field by field, what fraction of rows carry it and which ledger has to
start writing it. A corpus that is 40% populated and SAYS SO is worth more than one that looks
full because absent fields were defaulted to zero.

NOTHING HERE MAY STALL AN ORDER. `CorpusWriter` exists for the one case where a record is
produced on the money path: it is a bounded queue and a daemon thread, `submit()` is a
non-blocking enqueue that never raises and never waits on a disk, and a full queue DROPS the row
and counts the drop rather than blocking the caller. A recorder that can stall an order loses
more money than the row was worth. The research-side assembly (`build_records` + `append_rows`)
does the ordinary work and runs on an hourly organ, far from any socket.

UNITS. Every R figure is in units of the trade's own initial stop distance. Slippage is a signed
fraction of price against the reference quote (ask for a buy, bid for a sell), positive = worse
than asked -- the axis `digital_twin`, `execution_registry` and `markout` already share. Times
are ISO-8601 UTC strings, verbatim from the ledger that wrote them.
"""
from __future__ import annotations

import atexit
import contextlib
import json
import math
import queue
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

__all__ = [
    "CAPTURE_HANDOFFS",
    "MARKOUT_HORIZONS_S",
    "SCHEMA_VERSION",
    "CorpusWriter",
    "FillRecord",
    "append_rows",
    "build_records",
    "completeness",
    "excursions_from_ticks",
    "markouts_from_ticks",
    "read_rows",
    "record_from_row",
]

#: Bumped whenever a field is ADDED. Fields are never removed or repurposed: a reader of an old
#: row must keep reading it, which is why every field below has a default.
SCHEMA_VERSION = 1

#: The markout clock the principal named. Seconds after the fill.
MARKOUT_HORIZONS_S: tuple[float, ...] = (1.0, 5.0, 30.0, 300.0)

#: Field -> (the ledger or recorder that has to write it, what to do about it). Read by
#: `completeness` so an empty column reports the HANDOFF rather than merely reporting emptiness.
#: A field absent from this map is one the join can always fill from what already exists.
CAPTURE_HANDOFFS: dict[str, tuple[str, str]] = {
    "quote_bid": ("gateway order_intents", "record decision_bid/decision_ask on every intent "
                  "row, not only the bracket path"),
    "quote_ask": ("gateway order_intents", "as quote_bid"),
    "spread_frac_at_fill": ("tick tape / broker deal row", "the spread at the moment of the "
                            "fill; the tape can supply it once the fill timestamp is on the row"),
    "latency_send_to_ack_ms": ("gateway", "time order_send and write the ack delta on the "
                               "intent row"),
    "latency_ack_to_fill_ms": ("gateway + deal row", "needs the broker's fill timestamp in ms"),
    "markout_1s_r": ("tick tape", "needs data/tape ticks covering the fill minute"),
    "markout_5s_r": ("tick tape", "as markout_1s_r"),
    "markout_30s_r": ("tick tape", "as markout_1s_r"),
    "markout_5m_r": ("tick tape", "as markout_1s_r"),
    "mae_r": ("excursions.jsonl or the tape", "bar-derived until the tape covers the hold"),
    "mfe_r": ("excursions.jsonl or the tape", "as mae_r"),
    "path_r": ("tick tape", "the sampled post-fill path; tape only"),
    "predicted_r_sd": ("decision ledger", "the posterior's dispersion, not only its mean"),
    "alt_styles": ("counterfactual_replay", "prices market/limit/delayed per decision"),
    "alt_exits": ("counterfactual_replay", "prices fixed TP / trail / hold / partial"),
    "alt_entries": ("counterfactual_replay", "prices entered / skipped / 0.5x / 1x / 1.5x"),
    "cross_asset": ("state vector", "the cross-asset block of the world state at the decision"),
    "strategy_dna": ("decision ledger", "family, parameters and genome id of the signal"),
}


# --------------------------------------------------------------------------- small helpers
def _f(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _i(x: Any) -> int | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _s(x: Any) -> str:
    return "" if x is None else str(x)


def _d(x: Any) -> dict[str, Any]:
    return dict(x) if isinstance(x, Mapping) else {}


def _l(x: Any) -> list[Any]:
    return list(x) if isinstance(x, (list, tuple)) else []


def _minute(x: Any) -> str:
    """`YYYY-MM-DDTHH:MM` from any of the timestamp spellings this desk's ledgers use.

    THE FALLBACK JOIN DEPENDS ENTIRELY ON THIS. `decision_dataset` writes the minute as a full
    offset-aware ISO string (`2026-09-05T09:00:00+00:00`), `excursions.jsonl` writes it with a
    space separator, and the twin's case time is an `isoformat()`. Truncating each to sixteen
    characters WITHOUT normalising the separator silently produces two keys that never meet, and
    the visible symptom is a corpus whose counterfactual columns are all empty for no reason.
    """
    s = _s(x).strip().replace(" ", "T")
    return s[:16] if len(s) >= 16 else s


def _first(*vals: float | None) -> float | None:
    """The first value that is not None. NOT `a or b`.

    Every quantity on a corpus row can legitimately be exactly 0.0 -- a momentum z-score sitting
    on its mean, a trade exited at break-even, a signal with no edge left. `a or b` silently
    discards those and reaches for the fallback, which is how a column of real zeros becomes a
    column of somebody else's numbers.
    """
    for v in vals:
        if v is not None:
            return v
    return None


def _modal_regime(block: Any) -> str:
    """The regime the desk was in, from the allocator's own forecast.

    `pf_forecast_log` writes `regime` as a PROBABILITY MIXTURE over labels
    (`{"bull/low_vol": 0.41, "bull/mid_vol": 0.39, ...}`), not as a label -- so the modal label is
    the honest single-valued reading of it, and an empty or non-numeric block yields "" rather
    than a guess. A conditioning column filled with the wrong key is worse than an empty one: the
    empty one shows up in `completeness`.
    """
    d = _d(block)
    best, best_p = "", float("-inf")
    for k, v in d.items():
        p = _f(v)
        if p is not None and p > best_p:
            best, best_p = str(k), p
    return best


def _dir(x: Any) -> str:
    """"buy" / "sell" / "" -- the same rule `digital_twin._side` uses, so a case's normalised
    side and a ledger's raw `buy_stop` land on one key."""
    s = _s(x).lower()
    return "buy" if "buy" in s else ("sell" if "sell" in s else "")


# --------------------------------------------------------------------------- the record
@dataclass(frozen=True)
class FillRecord:
    """One execution, whole. Every field defaults, so a row written today reads back on a
    reader that predates half of it and a row written last month reads back here."""

    # ---- identity and provenance ------------------------------------------------------
    record_id: str = ""                       #: (intent_id or decision_id) + fill time
    intent_id: str = ""
    decision_id: str = ""
    dataset_row_id: str = ""                  #: the decision_dataset row this joined to
    ticket: int | None = None
    deal: int | None = None
    release_id: str = ""
    state_vector_id: str = ""
    account_kind: str = "unknown"             #: live / demo / unknown -- never blended
    join_keys: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    # ---- when and where ---------------------------------------------------------------
    symbol: str = ""
    sleeve: str = ""
    session: str = ""
    hour: int | None = None
    decided_at: str = ""
    sent_at: str = ""
    ack_at: str = ""
    filled_at: str = ""
    exit_at: str = ""

    # ---- why: reason for entry and strategy DNA ---------------------------------------
    entry_reason: str = ""                    #: the decision row's own `reason`
    veto_reason: str = ""                     #: empty for a taken trade; kept so the row is
                                              #: comparable with the vetoed rows beside it
    strategy_id: str = ""
    strategy_dna: dict[str, Any] = field(default_factory=dict)

    # ---- what the desk believed -------------------------------------------------------
    posterior_edge_r: float | None = None     #: the edge estimate that authorised the size
    posterior_edge_ci: list[float] | None = None
    signal_bps: float | None = None
    predicted_r_mean: float | None = None
    predicted_r_sd: float | None = None
    predicted_r_quantiles: dict[str, float] = field(default_factory=dict)
    predicted_p_fill: float | None = None
    predicted_slip_frac: float | None = None
    modelled_cost_bps: float | None = None

    # ---- the order --------------------------------------------------------------------
    side: str = ""
    direction: int = 0                        #: +1 long, -1 short
    order_type: str = ""                      #: market / limit / stop
    algo: str = ""                            #: the registry's algorithm name
    execution_style: str = ""                 #: the principal's vocabulary (see STYLE_ALIASES)
    lots: float | None = None
    requested_price: float | None = None      #: the reference quote the intent recorded
    quote_bid: float | None = None
    quote_ask: float | None = None
    fill_price: float | None = None
    filled_frac: float | None = None
    retcode: int | None = None
    rejected: bool = False
    reject_reason: str = ""

    # ---- the friction -----------------------------------------------------------------
    slip_frac: float | None = None            #: signed fraction of price, worse-than-asked > 0
    slip_r: float | None = None
    spread_frac_at_decision: float | None = None
    spread_frac_at_fill: float | None = None
    commission_r: float | None = None
    latency_decision_to_send_ms: float | None = None
    latency_send_to_ack_ms: float | None = None
    latency_ack_to_fill_ms: float | None = None

    # ---- the world --------------------------------------------------------------------
    regime: str = ""
    vol_frac: float | None = None             #: the intent's own volatility fraction of price
    momentum_z: float | None = None
    stop_frac: float | None = None            #: initial stop as a fraction of price
    market_state: dict[str, Any] = field(default_factory=dict)
    cross_asset: dict[str, Any] = field(default_factory=dict)
    portfolio_context: dict[str, Any] = field(default_factory=dict)

    # ---- the path after entry ---------------------------------------------------------
    markout_1s_r: float | None = None
    markout_5s_r: float | None = None
    markout_30s_r: float | None = None
    markout_5m_r: float | None = None
    markout_source: str = ""                  #: which tape or ledger produced them
    mae_r: float | None = None
    mfe_r: float | None = None
    path_r: list[list[float]] = field(default_factory=list)   #: [[seconds, R], ...] sampled

    # ---- the exit ---------------------------------------------------------------------
    exit_reason: str = ""
    realized_r: float | None = None
    holding_s: float | None = None

    # ---- the roads not taken ----------------------------------------------------------
    alt_styles: list[dict[str, Any]] = field(default_factory=list)   #: {style, r, basis}
    alt_exits: list[dict[str, Any]] = field(default_factory=list)    #: {exit, r, basis}
    alt_entries: list[dict[str, Any]] = field(default_factory=list)  #: {action, r, basis}

    # ---- the score --------------------------------------------------------------------
    prediction_error_r: float | None = None   #: realized_r - predicted_r_mean
    status: str = ""                          #: FILLED / REJECTED / UNRESOLVED

    def to_row(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def key(self) -> str:
        """The corpus key. Last row per key is the truth, so a record can be re-appended when a
        later pass resolves its exit or its markouts."""
        return self.record_id or f"{self.intent_id}|{self.filled_at}"

    @property
    def resolution(self) -> str:
        """The mutable half. A re-append is warranted only when this string changes."""
        return (f"{self.status}|{self.realized_r}|{self.exit_reason}|{self.mae_r}|{self.mfe_r}|"
                f"{self.markout_5m_r}|{len(self.alt_exits)}|{len(self.alt_entries)}|"
                f"{len(self.alt_styles)}")


_FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in fields(FillRecord))


def record_from_row(row: Mapping[str, Any]) -> FillRecord:
    """A record back from `to_row()`. Unknown keys are ignored (a newer writer's field) and
    missing ones take their default (an older writer's row): the corpus stays readable in both
    directions, which is what makes an append-only file survive its own schema."""
    kw: dict[str, Any] = {k: row[k] for k in _FIELD_NAMES if k in row}
    return FillRecord(**kw)


# --------------------------------------------------------------------------- durable writing
def append_rows(path: Path | str, rows: Iterable[Mapping[str, Any] | FillRecord]) -> int:
    """Append rows to the corpus, one JSON object per line. Returns how many landed.

    Synchronous and ordinary: this is the research-side path, called by an hourly organ that is
    nowhere near a socket. The money path uses `CorpusWriter`.
    """
    out = [r.to_row() if isinstance(r, FillRecord) else dict(r) for r in rows]
    if not out:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    return len(out)


def read_rows(path: Path | str) -> list[dict[str, Any]]:
    """Every JSON row in the corpus; a torn final line is skipped, never fatal."""
    try:
        text = Path(path).read_text("utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


class CorpusWriter:
    """A bounded queue and a daemon thread. `submit()` never blocks and never raises.

    THE RULE THIS CLASS EXISTS TO KEEP. The gateway must never wait on a disk write. An fsync on
    a busy box can take tens of milliseconds and a stalled `order_send` is a worse outcome than
    any record is worth, so the enqueue is `put_nowait` and a FULL QUEUE DROPS THE ROW AND COUNTS
    IT. Drops are surfaced in `stats` and are meant to be alarming: a non-zero drop count means
    the corpus is lossy and the queue or the drain needs to be bigger, not that the number should
    be ignored.

    `maxsize` is deliberately generous. At the desk's order rate the queue can hold hours of
    records in a few megabytes of process memory, so a drop means the writer thread died or the
    disk is gone -- both worth knowing about.
    """

    def __init__(self, path: Path | str, *, maxsize: int = 65536,
                 batch: int = 64, poll_s: float = 0.25) -> None:
        self.path = Path(path)
        self._q: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=max(1, int(maxsize)))
        self._batch = max(1, int(batch))
        self._poll_s = max(0.01, float(poll_s))
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._closed = False
        self._n_submitted = 0
        self._n_written = 0
        self._n_dropped = 0
        self._n_errors = 0
        self._last_error = ""

    # -- the money path -----------------------------------------------------------------
    def submit(self, record: FillRecord | Mapping[str, Any]) -> bool:
        """Enqueue one record. Returns False when it was dropped. NEVER blocks, NEVER raises."""
        try:
            row = record.to_row() if isinstance(record, FillRecord) else dict(record)
        except Exception:
            with self._lock:
                self._n_errors += 1
                self._last_error = "record did not serialise"
            return False
        try:
            self._ensure_thread()
            self._q.put_nowait(row)
        except queue.Full:
            with self._lock:
                self._n_submitted += 1
                self._n_dropped += 1
            return False
        except Exception as exc:
            with self._lock:
                self._n_submitted += 1
                self._n_dropped += 1
                self._n_errors += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
            return False
        with self._lock:
            self._n_submitted += 1
        return True

    # -- the drain ----------------------------------------------------------------------
    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            if self._closed:
                return
            if self._thread is not None and self._thread.is_alive():
                return
            t = threading.Thread(target=self._run, name="fill-corpus-writer", daemon=True)
            self._thread = t
            t.start()
        atexit.register(self._atexit)

    def _run(self) -> None:
        while True:
            try:
                item = self._q.get(timeout=self._poll_s)
            except queue.Empty:
                continue
            if item is None:
                self._q.task_done()
                return
            batch = [item]
            while len(batch) < self._batch:
                try:
                    nxt = self._q.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    self._write(batch)
                    for _ in batch:
                        self._q.task_done()
                    self._q.task_done()
                    return
                batch.append(nxt)
            self._write(batch)
            for _ in batch:
                self._q.task_done()

    def _write(self, batch: list[dict[str, Any]]) -> None:
        try:
            n = append_rows(self.path, batch)
        except Exception as exc:
            with self._lock:
                self._n_errors += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
            return
        with self._lock:
            self._n_written += n

    def _atexit(self) -> None:
        with contextlib.suppress(Exception):
            self.close(timeout_s=2.0)

    # -- operations ---------------------------------------------------------------------
    def _settled(self) -> bool:
        """Every submitted row has either landed or been counted as dropped. Stronger than an
        empty queue: a row popped for writing is out of the queue and not yet on disk."""
        with self._lock:
            return self._n_written + self._n_dropped >= self._n_submitted

    def flush(self, timeout_s: float = 5.0) -> bool:
        """Wait until every accepted row has landed (or been counted lost). For tests and for
        shutdown -- NEVER call from the money path, which is the entire reason `submit` exists."""
        if self._thread is None:
            return self._settled()
        deadline = threading.Event()
        t = threading.Timer(max(0.0, timeout_s), deadline.set)
        t.daemon = True
        t.start()
        try:
            while not self._settled() and not deadline.is_set():
                deadline.wait(0.01)
            return self._settled()
        finally:
            t.cancel()

    def close(self, timeout_s: float = 5.0) -> dict[str, Any]:
        with self._lock:
            already, self._closed = self._closed, True
        t = self._thread
        if t is not None and t.is_alive() and not already:
            with_sentinel = True
            try:
                self._q.put_nowait(None)
            except queue.Full:
                with_sentinel = False
            if with_sentinel:
                t.join(timeout=max(0.0, timeout_s))
        return self.stats

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {"path": str(self.path), "submitted": self._n_submitted,
                    "written": self._n_written, "dropped": self._n_dropped,
                    "errors": self._n_errors, "last_error": self._last_error,
                    "queued": self._q.qsize(), "lossy": self._n_dropped > 0}


# --------------------------------------------------------------------------- tape arithmetic
def _mid_at(times_ms: Sequence[float], bid: Sequence[float], ask: Sequence[float],
            at_ms: float) -> float | None:
    """The last mid at or before `at_ms`. LAST-AT-OR-BEFORE, never interpolated: a mid between
    two ticks is a price nobody could have traded, and a markout is supposed to be a price."""
    n = len(times_ms)
    if n == 0 or n != len(bid) or n != len(ask):
        return None
    lo, hi = 0, n - 1
    if times_ms[0] > at_ms:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if times_ms[mid] <= at_ms:
            lo = mid
        else:
            hi = mid - 1
    b, a = _f(bid[lo]), _f(ask[lo])
    if b is None or a is None or b <= 0 or a <= 0:
        return None
    return 0.5 * (b + a)


def markouts_from_ticks(times_ms: Sequence[float], bid: Sequence[float], ask: Sequence[float],
                        *, fill_ms: float, fill_price: float, direction: int,
                        stop_distance: float,
                        horizons_s: Sequence[float] = MARKOUT_HORIZONS_S,
                        ) -> dict[str, float | None]:
    """Post-fill markout in R at each horizon: (mid(t+h) - fill) * direction / stop_distance.

    Signed in the TRADE's direction, so a positive markout means the market moved the desk's way
    after the fill and a negative one is adverse selection -- the fill arrived exactly as the
    price was leaving. A horizon past the end of the tape returns None rather than the last tick:
    the last tick of a segment is a boundary artefact, not a 5-minute markout.
    """
    out: dict[str, float | None] = {}
    d = 1 if int(direction) > 0 else (-1 if int(direction) < 0 else 0)
    ok = (d != 0 and stop_distance > 0 and math.isfinite(stop_distance)
          and math.isfinite(fill_price) and len(times_ms) > 0)
    last_ms = float(times_ms[-1]) if len(times_ms) else float("-inf")
    for h in horizons_s:
        key = _horizon_key(h)
        if not ok or fill_ms + h * 1000.0 > last_ms:
            out[key] = None
            continue
        mid = _mid_at(times_ms, bid, ask, fill_ms + h * 1000.0)
        out[key] = None if mid is None else (mid - fill_price) * d / stop_distance
    return out


def _horizon_key(h: float) -> str:
    if h >= 60 and float(h).is_integer() and h % 60 == 0:
        return f"markout_{int(h // 60)}m_r"
    return f"markout_{int(h)}s_r" if float(h).is_integer() else f"markout_{h:g}s_r"


def excursions_from_ticks(times_ms: Sequence[float], bid: Sequence[float], ask: Sequence[float],
                          *, fill_ms: float, exit_ms: float | None, fill_price: float,
                          direction: int, stop_distance: float,
                          path_points: int = 24) -> dict[str, Any]:
    """MFE, MAE and a sampled path in R over the holding window, from the tape.

    MAE is reported POSITIVE-IS-WORSE (the desk's `excursions.jsonl` convention), MFE
    positive-is-better, both in R. `path_r` is `path_points` evenly spaced [seconds, R] pairs so
    a model can see the SHAPE of the excursion without the corpus carrying every tick -- the
    shape is what separates "went straight to target" from "sat under water for an hour first",
    and those two are different trades with the same realised R.
    """
    d = 1 if int(direction) > 0 else (-1 if int(direction) < 0 else 0)
    if d == 0 or not (stop_distance > 0) or not len(times_ms):
        return {"mfe_r": None, "mae_r": None, "path_r": []}
    t_end = float(exit_ms) if exit_ms is not None else float(times_ms[-1])
    rs: list[tuple[float, float]] = []
    for i, t in enumerate(times_ms):
        tf = float(t)
        if tf < fill_ms:
            continue
        if tf > t_end:
            break
        b, a = _f(bid[i]), _f(ask[i])
        if b is None or a is None:
            continue
        rs.append(((tf - fill_ms) / 1000.0,
                   (0.5 * (b + a) - fill_price) * d / stop_distance))
    if not rs:
        return {"mfe_r": None, "mae_r": None, "path_r": []}
    vals = [r for _, r in rs]
    step = max(1, len(rs) // max(1, int(path_points)))
    path = [[round(s, 3), round(r, 6)] for s, r in rs[::step]][:max(1, int(path_points))]
    #: `-min(vals)` yields -0.0 when the trade never traded against the fill; `+ 0.0` normalises
    #: it, because a report that prints "MAE -0.0" reads as a defect to whoever opens it.
    return {"mfe_r": max(vals), "mae_r": -min(vals) + 0.0, "path_r": path}


# --------------------------------------------------------------------------- the join
#: The alpha classes `libs.research.counterfactual_world` prices, mapped to the three
#: counterfactual columns of a fill row. VETO and MISSED_TRADE are both "would this trade have
#: been better not taken / taken", so they land beside the sizing arms as ENTRY alternatives.
_ALT_CLASSES: dict[str, str] = {
    "SIZING_ALPHA": "action", "VETO_ALPHA": "action", "MISSED_TRADE_ALPHA": "action",
    "EXECUTION_ALPHA": "style", "EXIT_ALPHA": "exit",
}


def _alt_rows(cf: Mapping[str, Any], kind: str) -> list[dict[str, Any]]:
    """Counterfactual arms off a `decision_dataset` row's `counterfactual_outcomes`, normalised
    to {<kind>, r, d_r, d_elog, status}.

    THE SHAPE IS THE ONE THE DESK ACTUALLY WRITES: `counterfactual_world.price_row` returns an
    `alternatives` LIST of `{class, arm, status, r, d_r, d_elog, ...}`, and this splits it by
    `class` into the entry, style and exit columns. A flat `{arm: r}` mapping under `entry` /
    `exit` / `execution` is accepted too, because a hand-built fixture and an older row both take
    that form and a corpus reader that only understands today's writer is a corpus reader that
    breaks on its own history.

    An arm with no R is DROPPED rather than written with a null: a null in a training column is a
    value a model will learn from.
    """
    out: list[dict[str, Any]] = []
    for e in _l(cf.get("alternatives")):
        if not isinstance(e, Mapping):
            continue
        if _ALT_CLASSES.get(_s(e.get("class"))) != kind:
            continue
        r = _f(e.get("r"))
        if r is None:
            continue
        out.append({kind: _s(e.get("arm")), "r": r, "d_r": _f(e.get("d_r")),
                    "d_elog": _f(e.get("d_elog")), "status": _s(e.get("status"))})
    if out:
        return out
    legacy = {"action": ("entry", "sizing", "entries"), "style": ("execution", "styles"),
              "exit": ("exit", "exits")}[kind]
    block: Any = next((cf[k] for k in legacy if isinstance(cf.get(k), Mapping)), None)
    if not isinstance(block, Mapping):
        return out
    for name, v in block.items():
        if not name or str(name).startswith("_") or name in {"status", "why", "basis", "n"}:
            continue
        r = _f(v.get("r")) if isinstance(v, Mapping) else _f(v)
        if r is None:
            continue
        out.append({kind: str(name), "r": r,
                    "d_r": _f(v.get("d_r")) if isinstance(v, Mapping) else None,
                    "d_elog": _f(v.get("d_elog")) if isinstance(v, Mapping) else None,
                    "status": _s(v.get("status")) if isinstance(v, Mapping) else ""})
    return out


def _dataset_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """decision_dataset rows by every key a fill might carry: row_id, the chosen action's
    intent_id, and (sleeve, symbol, minute). Later rows win -- the dataset is versioned and its
    last row per key is the resolved one."""
    ix: dict[str, Mapping[str, Any]] = {}
    for r in rows:
        rid = _s(r.get("row_id"))
        if rid:
            ix[f"row:{rid}"] = r
        chosen = _d(r.get("chosen_action"))
        for k in ("intent_id", "decision_id"):
            v = _s(chosen.get(k)) or _s(r.get(k))
            if v:
                ix[f"{k}:{v}"] = r
        prov = _d(r.get("provenance"))
        for k in ("intent_id", "decision_id"):
            v = _s(prov.get(k))
            if v:
                ix[f"{k}:{v}"] = r
        sl, sym, m = _s(r.get("sleeve")), _s(r.get("symbol")), _minute(r.get("minute"))
        if sl and sym and m:
            # THE SIDE IS IN THE KEY when the row carries one: a sleeve can place a buy_stop and a
            # sell_stop in the SAME minute (every bracket does), and a key without the side hands
            # the buy leg's counterfactuals to the sell leg.
            d = _dir(r.get("side"))
            if d:
                ix[f"min:{sl}|{sym}|{d}|{m}"] = r
            ix.setdefault(f"min:{sl}|{sym}|{m}", r)
    return ix


def _decision_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    ix: dict[str, Mapping[str, Any]] = {}
    for r in rows:
        for k in ("intent_id", "decision_id"):
            v = _s(r.get(k))
            if v:
                ix[f"{k}:{v}"] = r
        m = _minute(r.get("time"))
        sl, sym = _s(r.get("sleeve")), _s(r.get("symbol"))
        if sl and sym and m:
            d = _dir(r.get("side"))
            if d:
                ix[f"min:{sl}|{sym}|{d}|{m}"] = r
            ix.setdefault(f"min:{sl}|{sym}|{m}", r)
        tk = _i(r.get("ticket"))
        if tk is not None:
            ix[f"ticket:{tk}"] = r
    return ix


def _excursion_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    ix: dict[str, Mapping[str, Any]] = {}
    for r in rows:
        sl, m = _s(r.get("sleeve")), _minute(r.get("entry_time"))
        if sl and m:
            ix[f"{sl}|{m}"] = r
    return ix


def _deal_index(rows: Iterable[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    ix: dict[int, Mapping[str, Any]] = {}
    for r in rows:
        tk = _i(r.get("order"))
        if tk is not None:
            ix[tk] = r
    return ix


def build_records(cases: Sequence[Any], *,
                  decisions: Iterable[Mapping[str, Any]] = (),
                  deals: Iterable[Mapping[str, Any]] = (),
                  dataset_rows: Iterable[Mapping[str, Any]] = (),
                  excursions: Iterable[Mapping[str, Any]] = (),
                  markouts: Mapping[str, Mapping[str, Any]] | None = None,
                  tickets: Mapping[str, int] | None = None,
                  release_id: str = "") -> list[FillRecord]:
    """One `FillRecord` per twin case, enriched from every ledger that has something to add.

    `cases` are `digital_twin.TwinCase` objects (duck-typed, so a test can pass a stand-in): they
    already carry the intent-versus-fill truth and the join key that produced it, which is why
    this extends them rather than re-joining the gateway's ledgers a second time.

    `markouts` is an optional {intent_id: {...}} map the ORGAN supplies from the tick tape --
    this module does the arithmetic (`markouts_from_ticks`) but reads no files, so it stays
    importable on a container with no tape and no MetaTrader5.

    `tickets` is an optional {intent_id: broker ticket} map. A `TwinCase` does not carry the
    ticket, and the ticket is the only key a DEAL joins on, so without it the exit half of every
    row would be empty on a desk whose decision ledger does not stamp one.

    NOTHING IS INVENTED. A field no ledger carries stays None and `completeness` reports it.
    """
    dec = _decision_index(decisions)
    dset = _dataset_index(dataset_rows)
    exc = _excursion_index(excursions)
    dl = _deal_index(deals)
    mk = dict(markouts or {})
    tk = dict(tickets or {})
    out: list[FillRecord] = []
    for c in cases:
        out.append(_one(c, dec, dset, exc, dl, mk, tk, release_id))
    return out


def _one(c: Any, dec: Mapping[str, Mapping[str, Any]], dset: Mapping[str, Mapping[str, Any]],
         exc: Mapping[str, Mapping[str, Any]], dl: Mapping[int, Mapping[str, Any]],
         mk: Mapping[str, Mapping[str, Any]], tickets: Mapping[str, int],
         release_id: str) -> FillRecord:
    iid = _s(getattr(c, "intent_id", ""))
    sleeve, symbol = _s(getattr(c, "sleeve", "")), _s(getattr(c, "symbol", ""))
    t = _s(getattr(c, "time", ""))
    minute = _minute(t)
    side_d = _dir(getattr(c, "side", ""))
    mkey, mkey_loose = f"min:{sleeve}|{symbol}|{side_d}|{minute}", f"min:{sleeve}|{symbol}|{minute}"
    sources: list[str] = ["execution_twin_cases"]
    joins: dict[str, str] = {"intent_outcome": _s(getattr(c, "join_key", ""))}

    d_row = dec.get(f"intent_id:{iid}") or dec.get(mkey) or dec.get(mkey_loose) or {}
    if d_row:
        sources.append("decision_ledger")
        joins["decision"] = ("intent_id" if dec.get(f"intent_id:{iid}") else
                             "sleeve_symbol_side_min" if dec.get(mkey) else "sleeve_symbol_min")
    ds_row = (dset.get(f"intent_id:{iid}")
              or dset.get(f"decision_id:{_s(d_row.get('decision_id'))}" if d_row else "")
              or dset.get(mkey) or dset.get(mkey_loose) or {})
    if ds_row:
        sources.append("decision_dataset")
        joins["dataset"] = ("intent_id" if dset.get(f"intent_id:{iid}") else
                            "sleeve_symbol_side_min" if dset.get(mkey) else "sleeve_symbol_min")
    ex_row = exc.get(f"{sleeve}|{minute}") or {}
    if ex_row:
        sources.append("excursions")
        joins["excursions"] = "sleeve_entry_minute"

    tk = _i(getattr(c, "ticket", None)) or _i(tickets.get(iid)) or _i(d_row.get("ticket"))
    deal_row = dl.get(tk) if tk is not None else None
    if deal_row:
        sources.append("live_ledger")
        joins["deal"] = "ticket"

    price_ref = _f(getattr(c, "price_ref", None))
    stop_frac = _f(getattr(c, "stop_frac", None))
    direction = _i(getattr(c, "direction", 0)) or 0
    slip_frac = _f(getattr(c, "actual_slip_frac", None))
    slip_r = (slip_frac / stop_frac) if (slip_frac is not None and stop_frac) else None

    filled = getattr(c, "filled", None)
    rejected = bool(getattr(c, "rejected", False))
    status = ("REJECTED" if rejected else
              "FILLED" if filled else
              "UNFILLED" if filled is False else "UNRESOLVED")

    m = dict(mk.get(iid) or {})
    if m:
        sources.append(_s(m.get("source")) or "tape")

    ws = _d(ds_row.get("world_state"))
    cf = _d(ds_row.get("counterfactual_outcomes"))
    outcome = _d(ds_row.get("outcome"))
    quote = _d(ws.get("quote"))

    realized_r = _first(_f(outcome.get("r_multiple")),
                        _f((deal_row or {}).get("r_multiple")),
                        _f(ex_row.get("r_multiple")))
    pred_mean = _first(_f(d_row.get("predicted_r_mean")), _f(d_row.get("posterior_edge_r")),
                       _f(_d(d_row.get("chosen_action")).get("edge_r")))
    fill_price = _f((deal_row or {}).get("fill_price"))
    if fill_price is None and price_ref is not None and slip_frac is not None:
        fill_price = price_ref * (1.0 + slip_frac * (direction or 1))

    rec = FillRecord(
        record_id=f"{iid or minute}|{_s((deal_row or {}).get('deal')) or status}",
        intent_id=iid, decision_id=_s(d_row.get("decision_id")),
        dataset_row_id=_s(ds_row.get("row_id")), ticket=tk,
        deal=_i((deal_row or {}).get("deal")),
        release_id=release_id or _s(d_row.get("release_id")) or _s(ws.get("release_id")),
        state_vector_id=_s(d_row.get("state_vector_id")) or _s(ds_row.get("world_state_id")),
        account_kind=_s(getattr(c, "account_kind", "")) or "unknown",
        join_keys=joins, sources=sorted(set(sources)),
        symbol=symbol, sleeve=sleeve, session=_s(getattr(c, "session", "")),
        hour=_i(getattr(c, "hour", None)),
        decided_at=t, sent_at=_s(d_row.get("sent_at")), ack_at=_s(d_row.get("ack_at")),
        filled_at=_s((deal_row or {}).get("entry_time")) or _s(m.get("fill_time")),
        exit_at=_s((deal_row or {}).get("exit_time")) or _s(ex_row.get("exit_time")),
        entry_reason=_s(d_row.get("reason")), veto_reason=_s(d_row.get("veto_reason")),
        strategy_id=_s(d_row.get("strategy_id")) or sleeve,
        strategy_dna=_d(d_row.get("strategy_dna")) or _d(d_row.get("features")),
        posterior_edge_r=_f(d_row.get("posterior_edge_r")),
        posterior_edge_ci=(_l(d_row.get("posterior_edge_ci")) or None),
        signal_bps=_f(d_row.get("signal_bps")),
        predicted_r_mean=pred_mean, predicted_r_sd=_f(d_row.get("predicted_r_sd")),
        predicted_r_quantiles=_d(d_row.get("predicted_r_quantiles")),
        predicted_p_fill=_f(getattr(c, "predicted_p_fill", None)),
        predicted_slip_frac=_f(getattr(c, "predicted_slip_frac", None)),
        modelled_cost_bps=_f(d_row.get("modelled_cost_bps")),
        side=_s(getattr(c, "side", "")), direction=direction,
        order_type=_s(getattr(c, "order_type", "")), algo=_s(getattr(c, "algo", "")),
        execution_style=_s(d_row.get("execution")) or _s(getattr(c, "algo", "")),
        lots=_f(getattr(c, "lots", None)), requested_price=price_ref,
        quote_bid=_f(quote.get("bid")), quote_ask=_f(quote.get("ask")),
        fill_price=fill_price, filled_frac=_f(getattr(c, "filled_frac", None)),
        retcode=_i(getattr(c, "retcode", None)), rejected=rejected,
        reject_reason=_s(getattr(c, "reject_reason", "")),
        slip_frac=slip_frac, slip_r=slip_r,
        spread_frac_at_decision=_f(getattr(c, "spread_frac", None)),
        spread_frac_at_fill=_f(getattr(c, "spread_at_fill_frac", None)),
        commission_r=_f((deal_row or {}).get("commission_r")),
        latency_decision_to_send_ms=_f(getattr(c, "latency_ms", None)),
        latency_send_to_ack_ms=_f(d_row.get("latency_send_to_ack_ms")),
        latency_ack_to_fill_ms=_f(d_row.get("latency_ack_to_fill_ms")),
        regime=_s(d_row.get("regime")) or _modal_regime(_d(ws.get("allocator")).get("regime")),
        vol_frac=_f(getattr(c, "vol_frac", None)),
        momentum_z=_first(_f(d_row.get("momentum_z")),
                          _f(_d(d_row.get("features")).get("momentum_z"))),
        stop_frac=stop_frac, market_state=ws,
        cross_asset=_d(ws.get("cross_asset")),
        portfolio_context=_d(d_row.get("portfolio_context")) or _d(ws.get("allocator")),
        markout_1s_r=_f(m.get("markout_1s_r")), markout_5s_r=_f(m.get("markout_5s_r")),
        markout_30s_r=_f(m.get("markout_30s_r")), markout_5m_r=_f(m.get("markout_5m_r")),
        markout_source=_s(m.get("source")),
        mae_r=_first(_f(m.get("mae_r")), _f(ex_row.get("mae_r"))),
        mfe_r=_first(_f(m.get("mfe_r")), _f(ex_row.get("mfe_r"))),
        path_r=[list(p) for p in _l(m.get("path_r"))],
        exit_reason=_s((deal_row or {}).get("exit_reason")) or _s(outcome.get("exit_reason")),
        realized_r=realized_r,
        holding_s=_first(_f(outcome.get("holding_s")), _f((deal_row or {}).get("holding_s"))),
        alt_styles=_alt_rows(cf, "style"),
        alt_exits=_alt_rows(cf, "exit"),
        alt_entries=_alt_rows(cf, "action"),
        prediction_error_r=((realized_r - pred_mean)
                            if realized_r is not None and pred_mean is not None else None),
        status=status)
    return rec


# --------------------------------------------------------------------------- completeness
#: Fields whose absence is expected and carries no handoff: they are empty by construction on a
#: row of that kind (a rejected order has no fill price) rather than by a capture gap.
_CONDITIONAL: dict[str, str] = {
    "fill_price": "only a filled row has one",
    "filled_frac": "only a filled row has one",
    "exit_at": "only a closed trade has one",
    "exit_reason": "only a closed trade has one",
    "realized_r": "only a closed trade has one",
    "holding_s": "only a closed trade has one",
    "reject_reason": "only a rejected row has one",
    "veto_reason": "empty on a TAKEN decision, by construction",
}


def _populated(v: Any) -> bool:
    if v is None or v == "":
        return False
    if isinstance(v, (list, dict, tuple)):
        return len(v) > 0
    if isinstance(v, float):
        return math.isfinite(v)
    return True


def completeness(records: Sequence[FillRecord | Mapping[str, Any]]) -> dict[str, Any]:
    """Field-by-field coverage, and the handoff for every column that is empty.

    THE MOST IMPORTANT OUTPUT IN THIS MODULE. Completeness of capture matters more than
    sophistication of analysis, because an unrecorded fill cannot be recovered later: the tick
    that would have priced its 5-second markout is gone. A report that says "the corpus holds
    1,200 fills" and nothing else hides the fact that four of the principal's named fields are
    empty on every one of them. This says which, how empty, and who has to start writing it.
    """
    rows = [r.to_row() if isinstance(r, FillRecord) else dict(r) for r in records]
    n = len(rows)
    per: dict[str, dict[str, Any]] = {}
    for name in _FIELD_NAMES:
        k = sum(1 for r in rows if _populated(r.get(name)))
        cell: dict[str, Any] = {"n": k, "share": (round(k / n, 6) if n else None)}
        if k == 0 and n:
            if name in _CONDITIONAL:
                cell["why"] = _CONDITIONAL[name]
            elif name in CAPTURE_HANDOFFS:
                who, what = CAPTURE_HANDOFFS[name]
                cell["handoff"] = f"{who}: {what}"
        per[name] = cell
    empty = sorted(f for f in _FIELD_NAMES
                   if per[f]["n"] == 0 and f not in _CONDITIONAL)
    gaps = [f"{f} -- {CAPTURE_HANDOFFS[f][0]}: {CAPTURE_HANDOFFS[f][1]}"
            for f in empty if f in CAPTURE_HANDOFFS]
    counterfactual_n = sum(1 for r in rows
                           if _populated(r.get("alt_entries")) or _populated(r.get("alt_exits"))
                           or _populated(r.get("alt_styles")))
    #: A row is TRAINABLE when it carries both an outcome and something the outcome can be scored
    #: against. The predicted edge reaches the row under either name -- `posterior_edge_r` is what
    #: authorised the size, `predicted_r_mean` is the distribution's mean -- and counting only one
    #: of them reported zero trainable rows on a corpus that was fully trainable.
    trainable = sum(1 for r in rows
                    if _populated(r.get("realized_r"))
                    and (_populated(r.get("predicted_r_mean"))
                         or _populated(r.get("posterior_edge_r"))))
    return {
        "n_records": n, "schema_version": SCHEMA_VERSION,
        "fields": per,
        "empty_fields": empty,
        "gaps": gaps,
        "n_with_counterfactuals": counterfactual_n,
        "n_trainable": trainable,
        "why": ("a field at 0 with a handoff is a CAPTURE GAP -- the observation it needed is "
                "gone for every row already written and can only be fixed forward" if gaps
                else "every named field is carried by at least one row"),
    }
