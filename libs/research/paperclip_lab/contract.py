"""THE NARROW DONATION GATEWAY: the only shape the Paperclip company may hand the desk.

The company is untrusted by construction. Its agents are free models on an isolated runner, and a
model can hallucinate, leak the future, repeat itself or be prompt-injected by what it reads. So
nothing it writes is executed, and nothing it writes is believed. This module is pure stdlib, runs
on BOTH sides (the runner screens before spending a bundle slot, the box re-screens before the
seat door) and answers one question per row: is this a well-formed, novel, non-leaky PROPOSAL?

    recipe      family + params + symbols    -> compiles as EXACT_RECIPE (an executable cell)
    hypothesis  family + symbols, no params  -> compiles as STRUCTURED_HYPOTHESIS (family defaults)
    revival     a dead/starved producer's diagnosis and the tweak proposed to revive it; routed
                to the producer's owner, never applied by the company
    triage      a prior on an UNJUDGED cell (mechanism plausibility, leak / duplicate flag);
                advisory until its measured precision on later verdicts earns it any weight

What it never does: grant a verdict, touch an order, read a secret. A row that fails any check is
REFUSED with the reasons named, and the refusal is counted -- a red-team that drops rows silently
is a second judge nobody can audit.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

KINDS = ("recipe", "hypothesis", "revival", "triage")
ORIGINS = ("dataset", "producer", "graveyard", "paper", "repo", "cross_asset", "unknown_unknown",
           "corpus", "queue")

#: Every key a row may carry. An extra key is refused, not ignored: the gateway is narrow on
#: purpose, and a field the desk does not read is a channel nobody is watching.
ALLOWED_KEYS = frozenset({
    "kind", "role", "family", "symbols", "params", "timeframe", "session", "mechanism",
    "testable_claim", "falsifier", "inputs", "origin", "origin_ref", "parent_cell",
    "producer", "diagnosis", "tweak", "expected_effect",
    "cell", "prior", "flag", "dup_of", "why",
})
TEXT_CAPS = {"mechanism": 700, "testable_claim": 400, "falsifier": 300, "diagnosis": 600,
             "tweak": 600, "expected_effect": 300, "why": 300, "origin_ref": 200,
             "parent_cell": 200, "cell": 200, "dup_of": 200, "producer": 80, "role": 60,
             "family": 60, "timeframe": 8, "session": 24}
MAX_SYMBOLS = 6
MAX_PARAMS = 12
MAX_INPUTS = 8
TIMEFRAMES = frozenset({"M1", "M5", "M15", "M30", "H1", "H4", "D1"})

#: MT5 universe mandate (CLAUDE.md): crypto-EXCHANGE ground is never hunted. Fusion crypto CFDs
#: are MT5 symbols and pass through the universe check like any other symbol.
_EXCHANGE_BAN = re.compile(
    r"\b(binance|bybit|okx|hyperliquid|coinbase|kraken|deribit|bitmex|bitfinex|kucoin|gate\.io|"
    r"perp(etual)?s? funding|funding[- ]rate arb)\b", re.I)

#: LOOK-AHEAD, in the forms a model actually writes it. A row that USES future information as an
#: input is refused; a row that merely enters "at the next bar's open" is fine and is not matched.
_LEAK = re.compile(
    r"(shift\(\s*-\s*\d|center\s*=\s*true|\bcentered (moving|rolling)|"
    r"\b(future|forward) (return|close|price|bar)s? (as|is used as|used as) (a |an )?"
    r"(feature|input|signal|filter)|"
    r"\btomorrow'?s (close|high|low|return)\b|\bnext (day|bar|session)'?s (close|high|low|range|"
    r"return) (as|to (define|set|compute|filter))|"
    r"\b(full|whole|entire)[- ]sample (mean|std|normali[sz]|z-?score|quantile|percentile)|"
    r"\bin hindsight\b|\blook[- ]?ahead\b(?! bias (is )?(avoided|excluded|prevented))|"
    r"\bpeek(s|ing)? (at|into) (the )?future|\bsurvivor(ship)? (list|universe) as of today)", re.I)

#: The gateway carries prose and numbers, never instructions or credentials.
_HOSTILE = re.compile(
    r"(-----BEGIN|\bsk-[A-Za-z0-9]{16,}|\bghp_[A-Za-z0-9]{20,}|\bgithub_pat_|\bAKIA[0-9A-Z]{12,}|"
    r"\$\(|`|\brm -rf\b|\bpowershell\b|\bInvoke-Expression\b|\biex\b|\bcurl\s+-|\bwget\s+|"
    r"<script|data/secrets|\bpassword\s*[:=])", re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,59}$")
_SYMBOL = re.compile(r"^[A-Za-z0-9._#-]{2,24}$")


@dataclass
class Verdict:
    ok: bool
    row: dict[str, Any] | None
    reasons: list[str] = field(default_factory=list)
    key: str | None = None


def _clean_text(v: Any, cap: int) -> str:
    s = _CTRL.sub(" ", str(v if v is not None else "")).strip()
    return s[:cap]


def _scalar(v: Any) -> bool:
    if isinstance(v, bool) or isinstance(v, str):
        return not isinstance(v, str) or len(v) <= 40
    if isinstance(v, int):
        return abs(v) <= 10**9
    if isinstance(v, float):
        return math.isfinite(v) and abs(v) <= 1e9
    return False


def dedup_key(row: Mapping[str, Any]) -> str:
    """One identity per BET, not per wording. Recipes key on the exact cell; hypotheses on family
    x instruments x the claim's word set; revivals on producer x tweak; triage on the cell."""
    kind = row.get("kind")
    if kind == "recipe":
        basis: Any = [row.get("family"), sorted(row.get("symbols") or []),
                      sorted((row.get("params") or {}).items()), row.get("timeframe"),
                      row.get("session")]
    elif kind == "hypothesis":
        words = sorted(set(re.findall(r"[a-z]{4,}", str(row.get("testable_claim") or
                                                         row.get("mechanism") or "").lower())))
        basis = [row.get("family"), sorted(row.get("symbols") or []), words[:40]]
    elif kind == "revival":
        words = sorted(set(re.findall(r"[a-z]{4,}", str(row.get("tweak") or "").lower())))
        basis = [row.get("producer"), words[:40]]
    else:
        basis = [row.get("cell")]
    raw = json.dumps([kind, basis], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def screen(row: Any, *, families: Mapping[str, Iterable[str]] | None = None,
           universe: Iterable[str] | None = None, producers: Iterable[str] | None = None,
           seen: set[str] | None = None) -> Verdict:
    """Validate ONE row. `families` maps registered family -> its parameter names (an empty
    iterable means the names are unknown and any scalar key is let through for the compiler to
    judge); `universe` is the MT5 symbol registry; `seen` is the dedup set (mutated on accept).
    A None catalogue is UNMEASURED and does not refuse -- the box re-screens with real ones."""
    reasons: list[str] = []
    if not isinstance(row, dict):
        return Verdict(False, None, ["not an object"])
    extra = sorted(set(row) - ALLOWED_KEYS)
    if extra:
        reasons.append(f"keys outside the contract: {extra[:5]}")
    kind = row.get("kind")
    if kind not in KINDS:
        return Verdict(False, None, reasons + [f"kind {kind!r} not in {KINDS}"])

    out: dict[str, Any] = {"kind": kind}
    for k, cap in TEXT_CAPS.items():
        if row.get(k) not in (None, ""):
            out[k] = _clean_text(row[k], cap)
    blob = " ".join(str(out.get(k) or "") for k in TEXT_CAPS)
    if _HOSTILE.search(blob) or _HOSTILE.search(json.dumps(row.get("params") or {}, default=str)):
        reasons.append("hostile content (credential, command or markup)")
    if _EXCHANGE_BAN.search(blob):
        reasons.append("crypto-exchange ground (MT5 universe mandate)")
    leak = _LEAK.search(blob)
    if leak:
        reasons.append(f"look-ahead: {leak.group(0)[:60]!r}")

    if kind in ("recipe", "hypothesis"):
        fam = out.get("family", "")
        if not _IDENT.match(fam):
            reasons.append("family missing or malformed")
        elif families is not None and fam not in families:
            reasons.append(f"family {fam!r} not registered")
        syms = row.get("symbols")
        if not isinstance(syms, list) or not syms:
            reasons.append("symbols missing")
            syms = []
        syms = [str(s).strip() for s in syms][:MAX_SYMBOLS + 1]
        if len(syms) > MAX_SYMBOLS:
            reasons.append(f"more than {MAX_SYMBOLS} symbols")
        bad = [s for s in syms if not _SYMBOL.match(s)]
        if bad:
            reasons.append(f"malformed symbols {bad[:3]}")
        if universe is not None:
            uni = set(universe)
            off = [s for s in syms if s not in uni]
            if off:
                reasons.append(f"symbols outside the MT5 registry {off[:3]}")
        out["symbols"] = sorted(set(syms))
        if not out.get("testable_claim"):
            reasons.append("no testable_claim")
        if not out.get("mechanism"):
            reasons.append("no economic mechanism")
        if out.get("timeframe") and out["timeframe"].upper() not in TIMEFRAMES:
            reasons.append(f"timeframe {out['timeframe']!r} unknown")
        elif out.get("timeframe"):
            out["timeframe"] = out["timeframe"].upper()
        inputs = row.get("inputs") or []
        if not isinstance(inputs, list) or len(inputs) > MAX_INPUTS:
            reasons.append("inputs must be a list of at most 8 dataset names")
        else:
            out["inputs"] = [_clean_text(i, 80) for i in inputs if str(i).strip()]
        origin = row.get("origin")
        if origin not in ORIGINS:
            reasons.append(f"origin {origin!r} not in {ORIGINS}")
        else:
            out["origin"] = origin
    if kind == "recipe":
        params = row.get("params")
        if not isinstance(params, dict) or not params:
            reasons.append("recipe without params (send it as a hypothesis)")
        elif len(params) > MAX_PARAMS:
            reasons.append(f"more than {MAX_PARAMS} params")
        else:
            badp = [k for k, v in params.items() if not _IDENT.match(str(k)) or not _scalar(v)]
            if badp:
                reasons.append(f"non-scalar or malformed params {badp[:3]}")
            names = set((families or {}).get(out.get("family", ""), ()) or ())
            unknown = sorted(set(map(str, params)) - names) if names else []
            if unknown:
                reasons.append(f"params the family does not take {unknown[:4]}")
            out["params"] = {str(k): v for k, v in params.items()}
    elif kind == "hypothesis" and row.get("params"):
        reasons.append("hypothesis carries params (send it as a recipe)")
    if kind == "revival":
        prod = out.get("producer", "")
        if not prod:
            reasons.append("revival names no producer")
        elif producers is not None and prod not in set(producers):
            reasons.append(f"producer {prod!r} unknown")
        if not out.get("diagnosis") or not out.get("tweak"):
            reasons.append("revival needs diagnosis and tweak")
    if kind == "triage":
        try:
            prior = float(row.get("prior"))
        except (TypeError, ValueError):
            prior = float("nan")
        if not (0.0 <= prior <= 1.0):
            reasons.append("prior must be in [0,1]")
        else:
            out["prior"] = round(prior, 3)
        flag = str(row.get("flag") or "none").lower()
        if flag not in ("none", "leak", "duplicate"):
            reasons.append(f"flag {flag!r} unknown")
        out["flag"] = flag
        if not out.get("cell"):
            reasons.append("triage names no cell")

    key = dedup_key(out)
    if not reasons and seen is not None:
        if key in seen:
            reasons.append("duplicate of an earlier donation")
        else:
            seen.add(key)
    return Verdict(not reasons, out if not reasons else None, reasons, key)


def screen_all(rows: Iterable[Any], **kw: Any) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """(accepted rows, refusal counts by first reason class). Every refusal is counted."""
    ok: list[dict[str, Any]] = []
    refused: dict[str, int] = {}
    for r in rows:
        v = screen(r, **kw)
        if v.ok and v.row is not None:
            v.row["dedup_key"] = v.key
            ok.append(v.row)
        else:
            cls = (v.reasons[0].split(":")[0].split(" ")[0] if v.reasons else "unknown").lower()
            refused[cls] = refused.get(cls, 0) + 1
    return ok, refused
