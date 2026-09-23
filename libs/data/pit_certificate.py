"""Adversarial dataset acquisition: seven questions asked as CODE, and a certificate that says so.

    NO CERTIFICATE -> NO PROMOTION AUTHORITY (principal's order, 2026-09-05)

The desk's acquisition doctrine already refuses an undated series and a revised-without-vintage
one (`research/acquire_datasets.py`). That is two of the seven questions a hostile reader would
ask, asked at intake, and the other five were asked nowhere -- so a dataset could reach a
gauntlet having never been interrogated about survivorship, truncation or schema drift, and
nothing on disk recorded which questions had been put to it at all.

THE SEVEN, each a function with a verdict of its own:

  leak          can it leak future information -- rows dated after now, or an available_time
                EARLIER than the event it describes (knowable before it happened)
  revision      does its historical API show revised values, and if it restates, is there a
                vintage column to read the old one back from
  timestamps    can timestamps be reconstructed -- every row parseable, ordered, tz-aware
  availability  was it ACTUALLY available then -- a declared publication lag the stamps honour,
                and no row claiming availability in the future
  survivorship  does source selection use future survival -- "currently listed", "still active",
                "top N by today's size" are all future information about the past
  truncation    is history truncated -- a head cut off relative to the declared start, or an
                interior gap far larger than the series' own cadence
  schema        was the schema changed -- the column set and dtypes against the last certified
                schema hash, so a silent rename does not read as a new dataset

A VERDICT IS PASS, FAIL, or UNMEASURED, never a default. UNMEASURED is the honest answer when the
dataset does not carry what the question needs (L1.28a: an unasked question is not a pass), and
it is NOT authority: `authority` is true only when all seven PASS. That asymmetry is the point --
a source that cannot say whether it restates history is exactly as unusable as one that admits it
does.

WHERE THEY LIVE. `desks/mt5/data/pit_certificates/<dataset>.json`, one per dataset, written by
the acquirer and read by `scripts/check_pit.py`'s census and by any promotion gate that wants to
know whether a dataset may carry authority. The certificate id is a hash of WHAT WAS CERTIFIED --
dataset, schema, span, rows, checker version -- and not of when, so re-certifying an unchanged
dataset produces the same id and a diff shows only real change.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CERT_DIR = ROOT / "desks" / "mt5" / "data" / "pit_certificates"

#: Bumped when a check changes what it asks. Part of the certificate id, so an old certificate
#: cannot silently claim to have passed a question that did not exist when it was written.
CHECKER_VERSION = "2026-09-05.1"

#: The three verdicts. Prefixed so a reader importing one cannot mistake it for a boolean.
#: The bandit-rule suppression is a NAME collision, not a suppressed finding: S105 fires on any
#: constant whose identifier contains "pass", and this one holds a gate verdict, not a secret.
VERDICT_PASS = "PASS"          # noqa: S105  -- a gate verdict, not a credential
VERDICT_FAIL = "FAIL"
VERDICT_UNMEASURED = "UNMEASURED"

CHECK_NAMES: tuple[str, ...] = ("leak", "revision", "timestamps", "availability",
                                "survivorship", "truncation", "schema")

#: An interior gap this many times the series' own median cadence is a hole, not a weekend.
#: Chosen against the desk's actual cadences: a daily series skips two days over a weekend and
#: four over a long holiday, so anything under ~5x is normal calendar behaviour.
TRUNCATION_GAP_MULT = 8.0
#: A parseable-timestamp fraction below this is not a dated series at all.
MIN_TIMESTAMP_FRAC = 0.99
#: Rows below which the span checks cannot say anything: a series this short has no cadence.
MIN_ROWS_FOR_CADENCE = 20

#: Selection rules that are point-in-time by construction, and ones that are survivorship by
#: construction. Anything else is UNMEASURED: the acquirer must declare, never the checker guess.
PIT_SELECTIONS: frozenset[str] = frozenset({
    "all_rows_as_published", "full_history_no_filter", "listed_at_t", "as_of_vintage",
    "complete_universe",
})
SURVIVORSHIP_SELECTIONS: frozenset[str] = frozenset({
    "currently_listed", "currently_active", "still_trading", "survivors_only",
    "top_by_current_size", "top_by_current_volume", "current_constituents", "delisted_dropped",
})
#: Words that make a free-text selection rule survivorship even when it is not on the list.
_SURVIVOR_WORDS = re.compile(r"\b(current(ly)?|today|still|surviv\w*|active now|as of now)\b",
                             re.I)


@dataclass(frozen=True)
class Check:
    """One adversarial question, its verdict, and WHY -- the why is the deliverable."""

    name: str
    verdict: str
    why: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verdict == VERDICT_PASS


@dataclass(frozen=True)
class PITCertificate:
    """What was asked of a dataset, what it answered, and whether it may carry authority."""

    dataset: str
    certificate_id: str
    checker_version: str
    certified_at: str
    authority: bool
    checks: tuple[Check, ...]
    span: dict[str, Any]
    source: dict[str, Any]

    # ------------------------------------------------------------------ reading
    def failures(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.checks if c.verdict == VERDICT_FAIL)

    def unmeasured(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.checks if c.verdict == VERDICT_UNMEASURED)

    def why(self, name: str) -> str:
        for c in self.checks:
            if c.name == name:
                return c.why
        return f"no check named {name!r}"

    # ------------------------------------------------------------------ persistence
    def to_json(self) -> str:
        return json.dumps({
            "_": ("PIT CERTIFICATE. `authority` is true only when all seven adversarial checks "
                  "PASS; UNMEASURED is not a pass. No certificate -> no promotion authority."),
            "dataset": self.dataset, "certificate_id": self.certificate_id,
            "checker_version": self.checker_version, "certified_at": self.certified_at,
            "authority": self.authority,
            "failures": list(self.failures()), "unmeasured": list(self.unmeasured()),
            "checks": [asdict(c) for c in self.checks],
            "span": self.span, "source": self.source,
        }, indent=1, default=str)

    @classmethod
    def from_json(cls, text: str) -> PITCertificate:
        doc = json.loads(text)
        if not isinstance(doc, dict) or "checks" not in doc:
            raise ValueError("not a PIT certificate document (no `checks`)")
        checks = tuple(Check(name=str(c.get("name")), verdict=str(c.get("verdict")),
                             why=str(c.get("why")), detail=dict(c.get("detail") or {}))
                       for c in doc["checks"])
        return cls(dataset=str(doc.get("dataset")),
                   certificate_id=str(doc.get("certificate_id")),
                   checker_version=str(doc.get("checker_version")),
                   certified_at=str(doc.get("certified_at")),
                   authority=bool(doc.get("authority")),
                   checks=checks, span=dict(doc.get("span") or {}),
                   source=dict(doc.get("source") or {}))


# --------------------------------------------------------------------------- helpers
def _aware(t: datetime) -> datetime:
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _index(series: pd.DataFrame | pd.Series) -> pd.DatetimeIndex:
    """The series' own clock as UTC. A naive index is read as UTC, matching the lake convention."""
    return pd.DatetimeIndex(pd.to_datetime(series.index, utc=True, errors="coerce"))


def _column(series: pd.DataFrame | pd.Series, name: str) -> pd.Series | None:
    if isinstance(series, pd.DataFrame) and name in series.columns:
        return pd.to_datetime(series[name], utc=True, errors="coerce")
    return None


def schema_hash(series: pd.DataFrame | pd.Series) -> str:
    """Column names and dtypes, in order. A rename or a retype moves it; a new row does not."""
    if isinstance(series, pd.Series):
        cols = [(str(series.name), str(series.dtype))]
    else:
        cols = [(str(c), str(series[c].dtype)) for c in series.columns]
    payload = json.dumps(cols, sort_keys=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- the seven checks
def check_leak(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
               now: datetime) -> Check:
    """Can it leak future information? Two ways it can, both counted rather than argued about."""
    idx = _index(series)
    if idx.isna().all():
        return Check("leak", VERDICT_UNMEASURED, "no parseable index: nothing to place in time, so "
                                         "whether it leaks cannot be asked yet")
    future = int((idx > pd.Timestamp(_aware(now))).sum())
    avail = _column(series, "available_time")
    early = 0
    if avail is not None:
        early = int((avail.to_numpy() < idx.to_numpy()).sum())
    detail = {"rows": len(idx), "rows_dated_after_now": future,
              "rows_available_before_event": early,
              "now": _aware(now).isoformat()}
    if future:
        return Check("leak", VERDICT_FAIL,
                     f"{future} of {len(idx)} rows are dated AFTER now ({_aware(now).isoformat()}"
                     f"); a value the desk holds before its own event time is future information "
                     f"however it got here", detail)
    if early:
        return Check("leak", VERDICT_FAIL,
                     f"{early} of {len(idx)} rows declare an available_time EARLIER than the "
                     "event they describe -- knowable before it happened, which is the canonical "
                     "point-in-time leak", detail)
    if avail is None:
        return Check("leak", VERDICT_PASS,
                     "no row is dated after now; the series carries no available_time column, so "
                     "the availability check -- not this one -- is where its stamps are judged",
                     detail)
    return Check("leak", VERDICT_PASS,
                 f"no row dated after now and no row knowable before its event across "
                 f"{len(idx)} rows", detail)


def check_revision(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                   now: datetime) -> Check:
    """Does its historical API show revised values, and can the old vintage be read back?"""
    vintage_cols = [c for c in ("vintage", "available_time", "revision_time", "as_of")
                    if isinstance(series, pd.DataFrame) and c in series.columns]
    idx = _index(series)
    dup = int(idx.duplicated().sum()) if not idx.isna().all() else 0
    declared = meta.get("revised")
    detail = {"declared_revised": declared, "vintage_columns": vintage_cols,
              "duplicate_event_times": dup}
    restates = bool(declared) or dup > 0
    if restates and not vintage_cols:
        why = ("the source restates history" if declared else
               f"{dup} rows repeat an event time, which is a restatement by another name")
        return Check("revision", VERDICT_FAIL,
                     f"{why} and the series carries no vintage column "
                     "(vintage/available_time/revision_time/as_of), so the value the desk "
                     "decided on cannot be read back -- revision leakage with no way to detect "
                     "it", detail)
    if restates:
        return Check("revision", VERDICT_PASS,
                     f"the source restates history and the vintage is on the row "
                     f"({', '.join(vintage_cols)}), so a backtest can read the value that "
                     "existed at its decision time", detail)
    if declared is None:
        return Check("revision", VERDICT_UNMEASURED,
                     "the acquirer did not declare whether this source restates history, and no "
                     "repeated event time proves it does. Declare `revised: true/false` in the "
                     "dataset meta; absence is not permission", detail)
    return Check("revision", VERDICT_PASS,
                 "declared final-at-publication and no event time repeats, so there is no vintage "
                 "to lose", detail)


def check_timestamps(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                     now: datetime) -> Check:
    """Can timestamps be reconstructed -- parseable, ordered, and on a stated clock?"""
    idx = _index(series)
    n = len(idx)
    if not n:
        return Check("timestamps", VERDICT_UNMEASURED, "the series is empty", {"rows": 0})
    ok = int(idx.notna().sum())
    frac = ok / n
    monotonic = bool(pd.Series(idx.dropna().astype("int64")).is_monotonic_increasing)
    detail = {"rows": n, "parseable": ok, "parseable_frac": round(frac, 6),
              "monotonic": monotonic, "timezone": "UTC"}
    if frac < MIN_TIMESTAMP_FRAC:
        return Check("timestamps", VERDICT_FAIL,
                     f"only {frac:.1%} of {n} rows carry a parseable timestamp (need "
                     f"{MIN_TIMESTAMP_FRAC:.0%}); a row the desk cannot place in time is not a "
                     "weaker observation, it is not an observation", detail)
    if not monotonic:
        return Check("timestamps", VERDICT_FAIL,
                     "timestamps are not monotonically increasing after parsing: the file's row "
                     "order and its clock disagree, so `as-of` joins on it are undefined", detail)
    return Check("timestamps", VERDICT_PASS,
                 f"{ok} of {n} rows parse to an ordered, timezone-aware UTC clock", detail)


def check_availability(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                       now: datetime) -> Check:
    """Was it actually available then? The declared publication lag, checked against the stamps."""
    idx = _index(series)
    avail = _column(series, "available_time")
    lag_s = meta.get("publication_lag_s")
    detail: dict[str, Any] = {"declared_publication_lag_s": lag_s,
                              "has_available_time": avail is not None}
    if avail is None:
        if lag_s is None:
            return Check("availability", VERDICT_UNMEASURED,
                         "no available_time column and no declared publication_lag_s: when the "
                         "desk could have known each row is unknown, so it cannot be asserted",
                         detail)
        return Check("availability", VERDICT_PASS,
                     f"no per-row stamp, but the acquirer declares a publication lag of {lag_s}s "
                     "that a joiner applies uniformly to the event time", detail)
    future = int((avail > pd.Timestamp(_aware(now))).sum())
    detail["rows_available_after_now"] = future
    if future:
        return Check("availability", VERDICT_FAIL,
                     f"{future} rows claim an available_time in the future; a stamp the clock "
                     "cannot have reached is a manufactured availability", detail)
    lags = (avail.to_numpy() - idx.to_numpy()) / pd.Timedelta(seconds=1)
    finite = [float(x) for x in lags if isinstance(x, float) and math.isfinite(x)]
    if finite:
        detail["median_lag_s"] = round(sorted(finite)[len(finite) // 2], 3)
        detail["min_lag_s"] = round(min(finite), 3)
    if lag_s is not None and finite and detail["min_lag_s"] < float(lag_s):
        return Check("availability", VERDICT_FAIL,
                     f"the acquirer declares a publication lag of {lag_s}s but the shortest lag "
                     f"on the rows is {detail['min_lag_s']}s: some rows are stamped as knowable "
                     "sooner than the source publishes", detail)
    return Check("availability", VERDICT_PASS,
                 f"every row carries an available_time at or after its event and at or before "
                 f"now (median lag {detail.get('median_lag_s')}s)", detail)


def check_survivorship(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                       now: datetime) -> Check:
    """Does source selection use future survival? Declared, never inferred."""
    sel = meta.get("selection")
    detail = {"selection": sel, "pit_selections": sorted(PIT_SELECTIONS)}
    if not isinstance(sel, str) or not sel.strip():
        return Check("survivorship", VERDICT_UNMEASURED,
                     "the acquirer did not declare HOW the rows were selected. A universe picked "
                     f"by who survived is invisible in the data itself; declare `selection` as "
                     f"one of {sorted(PIT_SELECTIONS)} or say what it is", detail)
    low = sel.strip().lower()
    if low in SURVIVORSHIP_SELECTIONS or _SURVIVOR_WORDS.search(low):
        return Check("survivorship", VERDICT_FAIL,
                     f"the declared selection {sel!r} conditions on the present -- who is listed, "
                     "active or largest TODAY -- which is future information about every past "
                     "row in the file", detail)
    if low in PIT_SELECTIONS:
        return Check("survivorship", VERDICT_PASS,
                     f"selection {sel!r} is point-in-time by construction: no row's presence "
                     "depends on anything after its own timestamp", detail)
    return Check("survivorship", VERDICT_UNMEASURED,
                 f"selection {sel!r} is declared but is not one the checker knows to be "
                 f"point-in-time. Add it to PIT_SELECTIONS with the reason, or restate it as one "
                 f"of {sorted(PIT_SELECTIONS)}", detail)


def check_truncation(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                     now: datetime) -> Check:
    """Is history truncated -- at the head against the declared start, or by an interior hole?"""
    idx = _index(series).dropna().sort_values()
    n = len(idx)
    detail: dict[str, Any] = {"rows": n,
                              "first": str(idx[0]) if n else None,
                              "last": str(idx[-1]) if n else None,
                              "declared_history_starts": meta.get("history_starts")}
    if n < MIN_ROWS_FOR_CADENCE:
        return Check("truncation", VERDICT_UNMEASURED,
                     f"{n} rows is below {MIN_ROWS_FOR_CADENCE}: the series has no cadence to "
                     "measure a hole against", detail)
    declared = meta.get("history_starts")
    if declared:
        want = pd.to_datetime(declared, utc=True, errors="coerce")
        if pd.notna(want) and idx[0] > want + pd.Timedelta(days=1):
            missing = idx[0] - want
            detail["missing_head"] = str(missing)
            return Check("truncation", VERDICT_FAIL,
                         f"history is truncated at the head: the source declares it starts "
                         f"{want.isoformat()} and the file starts {idx[0].isoformat()} -- "
                         f"{missing} missing. A backtest over what is here silently begins after "
                         "whatever the missing span contained", detail)
    steps = idx.to_series().diff().dropna()
    med = steps.median()
    biggest = steps.max()
    detail["median_step"] = str(med)
    detail["largest_gap"] = str(biggest)
    if pd.isna(med) or med <= pd.Timedelta(0):
        return Check("truncation", VERDICT_UNMEASURED,
                     "the median step between rows is zero or undefined, so a gap cannot be "
                     "measured against the cadence", detail)
    if biggest > med * TRUNCATION_GAP_MULT:
        at = idx[int(steps.to_numpy().argmax()) + 1]
        gap_from = at - biggest
        detail["gap_from"] = str(gap_from)
        detail["gap_to"] = str(at)
        return Check("truncation", VERDICT_FAIL,
                     f"history is truncated in the middle: nothing between {gap_from.isoformat()}"
                     f" and {at.isoformat()} ({biggest} against a {med} cadence, "
                     f"{TRUNCATION_GAP_MULT}x the bound). Name the span or repair it -- a hole "
                     "the desk cannot see is a regime it never tested in", detail)
    return Check("truncation", VERDICT_PASS,
                 f"{n} rows from {idx[0].isoformat()} to {idx[-1].isoformat()} with no gap over "
                 f"{TRUNCATION_GAP_MULT}x the {med} cadence", detail)


def check_schema(meta: dict[str, Any], series: pd.DataFrame | pd.Series,
                 now: datetime) -> Check:
    """Was the schema changed? Against the hash the last certificate recorded, not against hope."""
    got = schema_hash(series)
    prior = meta.get("schema_hash")
    detail = {"schema_hash": got, "prior_schema_hash": prior,
              "columns": ([str(c) for c in series.columns] if isinstance(series, pd.DataFrame)
                          else [str(series.name)])}
    if not prior:
        return Check("schema", VERDICT_UNMEASURED,
                     f"no prior schema hash to compare against; this run's is {got}. Record it "
                     "on the dataset so the NEXT acquisition can tell a rename from a new "
                     "dataset", detail)
    if str(prior) != got:
        return Check("schema", VERDICT_FAIL,
                     f"the schema changed: {prior} -> {got}. A renamed or retyped column reads "
                     "downstream as a new series with a new history, which is how a break becomes "
                     "an edge. Re-certify deliberately with a migration note", detail)
    return Check("schema", VERDICT_PASS,
                 f"schema hash {got} matches the one last certified", detail)


CHECKS = (check_leak, check_revision, check_timestamps, check_availability,
          check_survivorship, check_truncation, check_schema)


# --------------------------------------------------------------------------- the certificate
def certificate_id(dataset: str, series: pd.DataFrame | pd.Series,
                   span: dict[str, Any]) -> str:
    """A hash of WHAT was certified, never of when. Re-certifying an unchanged dataset returns
    the same id, so a changed id is always a changed dataset."""
    body = json.dumps({"dataset": dataset, "schema": schema_hash(series),
                       "rows": span.get("rows"), "first": span.get("first"),
                       "last": span.get("last"), "v": CHECKER_VERSION},
                      sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:20]


def certify(dataset_meta: dict[str, Any], series: pd.DataFrame | pd.Series, *,
            now: datetime | None = None) -> PITCertificate:
    """Put all seven questions to a dataset and mint the certificate that records the answers.

    `dataset_meta` is what the ACQUIRER declares -- name, url, selection rule, whether the source
    restates, its publication lag, when its history starts, the schema hash last certified. The
    checker never guesses any of it: an undeclared question reads UNMEASURED, and UNMEASURED
    carries no authority.
    """
    when = _aware(now or datetime.now(tz=UTC))
    name = str(dataset_meta.get("dataset") or dataset_meta.get("name") or "unnamed")
    idx = _index(series).dropna().sort_values()
    span = {"rows": len(series),
            "first": str(idx[0]) if len(idx) else None,
            "last": str(idx[-1]) if len(idx) else None,
            "schema_hash": schema_hash(series)}
    checks = tuple(fn(dataset_meta, series, when) for fn in CHECKS)
    return PITCertificate(
        dataset=name,
        certificate_id=certificate_id(name, series, span),
        checker_version=CHECKER_VERSION,
        certified_at=when.isoformat(),
        authority=all(c.passed for c in checks),
        checks=checks,
        span=span,
        source={k: dataset_meta.get(k) for k in
                ("url", "host", "provider", "selection", "revised", "publication_lag_s",
                 "history_starts", "license")},
    )


def _slug(dataset: str) -> str:
    """A filesystem-safe stem. Datasets are named by host and file, which carry dots and slashes."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", dataset).strip("_")[:120] or "unnamed"


def path_for(dataset: str, root: Path = CERT_DIR) -> Path:
    return root / f"{_slug(dataset)}.json"


def write(cert: PITCertificate, root: Path = CERT_DIR) -> Path:
    p = path_for(cert.dataset, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cert.to_json() + "\n", "utf-8")
    return p


def load(dataset: str, root: Path = CERT_DIR) -> PITCertificate | None:
    """The certificate on disk, or None. A corrupt one is None too: an unreadable certificate is
    not a certificate, and reading it as one would be the absent-file defect all over again."""
    p = path_for(dataset, root)
    try:
        return PITCertificate.from_json(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def has_authority(dataset: str, root: Path = CERT_DIR) -> bool:
    """THE GATE. No certificate, an unreadable one, or one with any check not PASSing -> False."""
    cert = load(dataset, root)
    return bool(cert and cert.authority)


def census(root: Path = CERT_DIR) -> dict[str, Any]:
    """Every certificate on disk: who has authority, who does not, and which check stopped them.

    Read by `scripts/check_pit.py`. Reports the count of datasets with NO certificate as unknown
    rather than zero -- this function can only see the certificates that exist, and saying
    otherwise would turn an unasked question into a pass.
    """
    certs: list[PITCertificate] = []
    unreadable: list[str] = []
    for p in sorted(root.glob("*.json")) if root.exists() else []:
        try:
            certs.append(PITCertificate.from_json(p.read_text("utf-8")))
        except (OSError, ValueError):
            unreadable.append(p.name)
    def _tally() -> dict[str, int]:
        return {VERDICT_PASS: 0, VERDICT_FAIL: 0, VERDICT_UNMEASURED: 0}

    by_check: dict[str, dict[str, int]] = {n: _tally() for n in CHECK_NAMES}
    for c in certs:
        for chk in c.checks:
            row = by_check.setdefault(chk.name, _tally())
            row[chk.verdict] = row.get(chk.verdict, 0) + 1
    with_auth = sorted(c.dataset for c in certs if c.authority)
    without = sorted(c.dataset for c in certs if not c.authority)
    return {
        "dir": str(root),
        "certificates": len(certs),
        "with_authority": len(with_auth),
        "without_authority": len(without),
        "authority_frac": (round(len(with_auth) / len(certs), 4) if certs else None),
        "datasets_with_authority": with_auth,
        "datasets_without_authority": without,
        "blocking_check": {c.dataset: sorted(set(c.failures()) | set(c.unmeasured()))
                           for c in certs if not c.authority},
        "by_check": by_check,
        "unreadable": unreadable,
        "rule": ("authority requires all seven adversarial checks to PASS; UNMEASURED is not a "
                 "pass, and a dataset with no certificate at all has no promotion authority "
                 "whatever this census counts"),
    }


def stale(cert: PITCertificate, *, now: datetime | None = None,
          max_age: timedelta = timedelta(days=90)) -> bool:
    """Has the certificate aged past the point where its answers still describe the live feed?
    A source re-fetched daily can change its schema, its selection or its lag at any time."""
    when = _aware(now or datetime.now(tz=UTC))
    try:
        at = _aware(datetime.fromisoformat(cert.certified_at))
    except (TypeError, ValueError):
        return True
    return (when - at) > max_age
