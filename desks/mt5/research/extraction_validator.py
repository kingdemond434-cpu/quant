"""EXTRACTION VALIDATOR -- every row a model extracted is checked against the bytes it came from.

WHY IT IS A SEPARATE MODULE. `llm_extractor` asks a language model to turn a vaulted page the
shape parsers could not read into rows (period, variable, value, unit, quote). A model can and
will write a plausible number that is not on the page. So no extracted row is trusted: this
module scores each one against the SOURCE TEXT with deterministic checks and rejects it with a
reason code. It holds no model and no network, which is what makes its verdict worth reading;
it is also what the tests pin.

THE CHECKS, each a reason code when it fails:

    MISSING_FIELD          period, variable, value or quote absent
    NON_NUMERIC_VALUE      the value is not a finite number
    QUOTE_NOT_IN_SOURCE    the quoted evidence is not a substring of the source (whitespace-
                           and width-normalised, so a full-width CJK digit still matches)
    VALUE_NOT_IN_QUOTE     no rendering of the value (1234.5 / 1,234.5 / 1 234,5 / 12.3%) is in
                           the quote -- the number was not read off the evidence it cites
    PERIOD_UNPARSEABLE     the period is not a date, month, quarter or year
    PERIOD_NOT_IN_SOURCE   the period's year appears nowhere in the source
    FUTURE_PERIOD          the period starts after the page was fetched: a forecast or a
                           hallucination, and either way not an observation
    DUPLICATE_ROW          the same (period, variable) was already accepted with another value

A row is ACCEPTED only with no reason code. `score` is the fraction of checks passed, reported
so a source whose rows fail one check can be told from one whose rows fail all of them.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

REASONS: tuple[str, ...] = (
    "MISSING_FIELD", "NON_NUMERIC_VALUE", "QUOTE_NOT_IN_SOURCE", "VALUE_NOT_IN_QUOTE",
    "PERIOD_UNPARSEABLE", "PERIOD_NOT_IN_SOURCE", "FUTURE_PERIOD", "DUPLICATE_ROW")
N_CHECKS = len(REASONS)
REQUIRED = ("period", "variable", "value", "quote")


def normalise(text: str) -> str:
    """NFKC (full-width digits and punctuation to ASCII), lower case, whitespace collapsed."""
    t = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"\s+", " ", t).strip().lower()


def _digits(text: str) -> str:
    """The quote with every separator a locale may put inside a number removed."""
    return re.sub(r"(?<=\d)[,  ' ](?=\d)", "", normalise(text))


def value_renderings(value: float) -> set[str]:
    """The strings a page may print `value` as, after `_digits` has removed group separators."""
    out: set[str] = set()
    for nd in range(0, 5):
        s = f"{value:.{nd}f}"
        out.add(s)
        out.add(s.replace(".", ","))            # decimal comma
        if "." in s:
            out.add(s.rstrip("0").rstrip("."))
    if float(value).is_integer():
        out.add(str(int(value)))
    return {s for s in out if s and s not in ("-0", "0.")}


def _num_tokens(text: str) -> list[str]:
    """Numbers in the text read both ways: with group separators removed ("1,234" -> 1234) and
    as written (so a decimal comma "3,5" is still found as 3,5)."""
    pat = r"-?\d+(?:[.,]\d+)?"
    return re.findall(pat, _digits(text)) + re.findall(pat, normalise(text))


def parse_period(period: Any) -> datetime | None:
    """A date, a month (2026-08, 2026年8月), a quarter (2026Q2, 2026-Q2) or a year."""
    s = normalise(str(period or ""))
    if not s:
        return None
    m = re.match(r"^(\d{4})\s*[-/ ]?\s*q([1-4])$", s)
    if m:
        return datetime(int(m.group(1)), 3 * int(m.group(2)) - 2, 1, tzinfo=UTC)
    m = re.match(r"^(\d{4})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?$", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1), tzinfo=UTC)
    m = re.match(r"^(\d{4})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?$", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1), tzinfo=UTC)
        except ValueError:
            return None
    m = re.match(r"^(\d{4})年?$", s)
    if m:
        return datetime(int(m.group(1)), 1, 1, tzinfo=UTC)
    return None


def check_row(row: Mapping[str, Any], source_text: str, *, fetched_at: datetime | None,
              seen: dict[tuple[str, str], float] | None = None,
              _norm_source: str | None = None) -> dict[str, Any]:
    """{accepted, reasons, score} for one extracted row against its source text."""
    reasons: list[str] = []
    src = _norm_source if _norm_source is not None else normalise(source_text)
    missing = [k for k in REQUIRED if row.get(k) in (None, "")]
    if missing:
        reasons.append("MISSING_FIELD")
    value: float | None
    try:
        value = float(str(row.get("value")).replace(",", "")) \
            if not isinstance(row.get("value"), (int, float)) else float(row["value"])
        if not math.isfinite(value):
            value = None
    except (TypeError, ValueError):
        value = None
    if value is None:
        reasons.append("NON_NUMERIC_VALUE")
    quote = normalise(str(row.get("quote") or ""))
    if not quote or quote not in src:
        reasons.append("QUOTE_NOT_IN_SOURCE")
    if value is not None and quote:
        toks = set(_num_tokens(quote))
        rend = value_renderings(value) | value_renderings(abs(value))
        pct = value_renderings(value * 100.0) if abs(value) < 1.0 else set()
        if not (toks & (rend | pct)):
            reasons.append("VALUE_NOT_IN_QUOTE")
    per = parse_period(row.get("period"))
    if per is None:
        reasons.append("PERIOD_UNPARSEABLE")
    else:
        if str(per.year) not in src:
            reasons.append("PERIOD_NOT_IN_SOURCE")
        if fetched_at is not None and per > fetched_at:
            reasons.append("FUTURE_PERIOD")
    if seen is not None and per is not None and value is not None and not reasons:
        key = (per.date().isoformat(), normalise(str(row.get("variable") or "")))
        if key in seen and seen[key] != value:
            reasons.append("DUPLICATE_ROW")
        else:
            seen[key] = value
    return {"accepted": not reasons, "reasons": reasons,
            "score": round(1.0 - len(set(reasons)) / N_CHECKS, 3),
            "period": per.date().isoformat() if per is not None else None, "value": value}


def validate(rows: Iterable[Mapping[str, Any]], source_text: str, *,
             fetched_at: datetime | None = None) -> dict[str, Any]:
    """Score every row; return the accepted rows and a reason-code census of the rejected."""
    src = normalise(source_text)
    seen: dict[tuple[str, str], float] = {}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    census: Counter[str] = Counter()
    scores: list[float] = []
    for r in rows:
        if not isinstance(r, Mapping):
            rejected.append({"row": str(r)[:120], "reasons": ["MISSING_FIELD"]})
            census["MISSING_FIELD"] += 1
            continue
        v = check_row(r, source_text, fetched_at=fetched_at, seen=seen, _norm_source=src)
        scores.append(v["score"])
        if v["accepted"]:
            accepted.append({"period": v["period"], "variable": str(r.get("variable")),
                             "value": v["value"], "unit": str(r.get("unit") or ""),
                             "quote": str(r.get("quote"))[:200]})
        else:
            census.update(v["reasons"])
            rejected.append({"row": {k: r.get(k) for k in (*REQUIRED, "unit")},
                             "reasons": v["reasons"]})
    n = len(accepted) + len(rejected)
    return {"n": n, "accepted": accepted, "n_accepted": len(accepted),
            "rejected": rejected, "n_rejected": len(rejected),
            "acceptance_rate": round(len(accepted) / n, 4) if n else None,
            "mean_score": round(sum(scores) / len(scores), 4) if scores else None,
            "reason_codes": dict(census)}
