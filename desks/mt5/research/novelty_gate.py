"""HOMOGENEITY IS PAID FOR OUT OF THE FAMILY-WISE ERROR BUDGET, SO IT IS CAUGHT BEFORE TESTING.

    EMA breakout on XAUUSD rr=1.5
    EMA breakout on XAUUSD rr=1.6      -- four docket rows
    EMA breakout on XAUUSD rr=1.7      -- ONE bet
    EMA breakout on XAUUSD rr=1.8      -- FOUR trials charged to every other hypothesis

THE COST IS NOT THE COMPUTE, IT IS THE BUDGET. `deflated_sharpe` and the program-level SPA/PBO
tests divide ONE family-wise error budget across every cell the desk tests, so a redundant cell
does not merely waste an hour: it raises the bar every genuinely different hypothesis has to
clear. CLAUDE.md records what that already cost once -- 10,575 of 23,627 docket cells were
single-name equities, about 61% of the multiple-testing charge spent on the asset class least
suited to the method, and on that campaign `deflated_sharpe` rejected 42 of 42 judged cells at
597 trials. Parameter clones are the same disease with no mandate to argue about: trials the desk
pays for and learns nothing from. `libs/research/novelty_v2` measures the same crime AFTER a
candidate has been tested (n_eff ~5.5 across 23 certificates); this runs BEFORE, on text, sets and
file names, so the trial is never spent.

WHAT IT MEASURES -- four similarities to the NEAREST library member:

    feature    which price/exogenous inputs the family+params actually consume. Derived from the
               family's own name tokens and its parameter keys, never a hard-coded whitelist: an
               unrecognised key rides as `param:<key>` rather than vanishing, because a key this
               vocabulary cannot name is an input it cannot name, not an input that is absent.
    semantic   the claim itself -- mechanism prose where both sides carry it, and the structural
               claim (family, instrument, chart, clock, parameter keys) always. The HIGHER of the
               two convicts: novelty cannot be bought by rewording a story, nor by reusing a
               coordinate under a new one.
    ast        node-type Jaccard of the expression, via `novelty_v2.ast_shape` /
               `program_similarity`. MEASURED 2026-09-16: not one of the 21,099 rows in
               `data/hypotheses/external_survivors.json` carries an expression, so today this
               reads UNMEASURED across the whole default docket. That is the measurement, not a
               defect of the gate.
    returns    |correlation| of realised R, read from `reports/shadow/ledger_*.json` when BOTH
               sides have one. A pre-test candidate has no forward record by construction, so this
               is usually UNMEASURED too -- it can convict a re-run, never a first run.

THE RULE, WHICH IS THE PAPER'S RULE CORRECTED FOR L1.28a. A candidate is NOVEL when it is DISTANT
(similarity < 0.90) in at least ONE economically meaningful dimension THAT WAS MEASURED, among
{feature, returns, semantic}. It is REDUNDANT only when every measurable dimension reads as a twin
AND THE TWIN IS NAMED. An unmeasurable dimension never convicts and never acquits: absence is not
evidence of difference (LAWS L1.28a), and it is not evidence of sameness either. `ast` is reported
and may corroborate, but can never establish novelty -- a clone rewritten in different syntax is
still a clone, and spelling is not an economic difference.

TWO CONVICTIONS THAT DO NOT NEED FOUR NUMBERS. An EXACT identity match (`frontier_identity.
cell_id`, the desk's own identity function) means this cell has already been judged. A PARAMETER
TWIN -- same family, instrument and chart, every parameter inside 10% -- is a sweep step, and is
REDUNDANT unless the returns distance says otherwise.

WHAT THIS IS NOT. It is not a kill: REDUNDANT names the twin and hands the decision back, as
`novelty_v2` does, because this desk's history contains a novelty rule that discarded the better
copy. It is not a risk reduction either -- refusing a clone does not shrink the book, it frees the
error budget for bets that are actually different, which is the Tier-1 definition of more
independent positive-Elog bets inside the same heat (GROWTH_GOVERNANCE Rule 1).

    python research/novelty_gate.py --dry-run     # screen the docket, write nothing
    python research/novelty_gate.py --limit 5000  # screen, write reports/NOVELTY_GATE.json
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Windows Python's OWN install dir ships a `libs\` folder that namespace-packages into
# `import libs` and can be cached BEFORE the repo root is reached -- `mt5desk/families.py`
# documents the same trap. Purge the cached wrong package so the repo-root one wins.
if "libs" in sys.modules and not getattr(sys.modules["libs"], "__file__", None):
    for _m in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
        del sys.modules[_m]

try:
    from libs.research.novelty_v2 import MIN_OVERLAP, ast_shape, program_similarity
except Exception:  # pragma: no cover - this gate must never be what breaks the funnel
    MIN_OVERLAP = 20

    def ast_shape(source: str) -> Any:  # type: ignore[misc]
        return {}

    def program_similarity(src_a: str, src_b: str) -> float | None:  # type: ignore[misc]
        return None

try:
    from libs.research import tri_alignment as _tri
except Exception:  # pragma: no cover
    _tri = None  # type: ignore[assignment]

try:
    from frontier_identity import cell_id, timeframe_of
except Exception:  # pragma: no cover
    def cell_id(cell: dict) -> str:  # type: ignore[misc]
        return f"{cell.get('sym')}.{cell.get('family')}"

    def timeframe_of(cell: dict) -> str:  # type: ignore[misc]
        return str((cell.get("params") or {}).get("timeframe") or cell.get("timeframe") or "H1")

SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = BASE / "data" / "sleeves.json"
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SHADOW_DIR = BASE / "reports" / "shadow"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
OUT = BASE / "reports" / "NOVELTY_GATE.json"

#: Similarity at or above this is a twin. 0.90 rather than novelty_v2's 0.85 because these are SET
#: similarities over small vocabularies, where one differing token already costs ~0.15.
TWIN_AT = 0.90

#: A parameter inside this relative band of an incumbent's is the same parameter region.
PARAM_BAND = 0.10

#: The dimensions that can ESTABLISH novelty. `ast` is deliberately absent: two spellings of one
#: computation are one bet, and letting syntax earn novelty is the cheapest possible way past the
#: only gate protecting the error budget.
ECONOMIC_DIMS = ("feature", "returns", "semantic")
DIMENSIONS = ("feature", "semantic", "ast", "returns")

#: Complexity above which a candidate is flagged OVERSIZED. MEASURED 2026-09-16 against the desk's
#: own library: every one of the 58 certified survivors carries 0, 1, 2 or 4 parameters (histogram
#: 18/1/15/24) and 65 of 66 live sleeves carry none. The docket's dominant generator (`discovered`,
#: 17,354 of 21,099 rows) carries exactly 4 by construction. 6 therefore sits above both the house
#: style and everything this desk has ever certified, so the flag marks real over-parameterisation
#: rather than the desk's own shape. It is a FLAG that rides on the verdict, never a veto.
OVERSIZED_AT = 6.0

#: Ten AST nodes count as one free parameter. Node count and parameter count are not the same
#: currency; the exchange rate is declared here rather than hidden inside a sum.
AST_NODES_PER_PARAM = 10.0

#: Cost bound per candidate. The compare set is blocked on symbol first, then family: because every
#: feature set contains `price:<SYMBOL>` and the sets run 4-10 tokens wide, a member on a different
#: instrument cannot reach 0.90 on `feature`, and `feature` must read as a twin for any REDUNDANT
#: verdict. So the block is EXACT for conviction, and can only cost a nearer-looking name on a
#: candidate that is novel either way.
MAX_COMPARISONS = 600
DEFAULT_LIMIT = 5000

RULE = ("NOVEL if distant (similarity < 0.90) in at least one MEASURED dimension among "
        "{feature, returns, semantic}; REDUNDANT only when every measurable dimension reads as a "
        "twin and the twin is named. An unmeasurable dimension never convicts and never acquits "
        "(LAWS L1.28a). AST similarity is reported and may corroborate but can never establish "
        "novelty. Exact cell identity, and a same-family/symbol/chart parameter region inside "
        "10%, convict directly -- the latter unless the returns distance says otherwise.")

_STOP = frozenset({"the", "and", "for", "with", "from", "that", "this", "are", "can", "has",
                   "its", "into", "when", "not", "but", "was", "were", "which", "their"})

#: family-name token -> the input it names. Unknown tokens are kept verbatim as `fam:<token>`.
#: `anti` is absent on purpose: `anti_donchian_breakout` consumes exactly what `donchian_breakout`
#: consumes -- the sign lives on the side, not in the inputs.
_FAMILY_FEATURES: dict[str, str] = {
    "range": "range_high_low", "breakout": "range_high_low", "donchian": "range_high_low",
    "channel": "range_high_low", "momentum": "return_momentum", "trend": "return_momentum",
    "speed": "return_momentum", "reversal": "return_momentum", "reversion": "return_momentum",
    "gap": "overnight_gap", "overnight": "overnight_gap", "vol": "realised_vol",
    "atr": "realised_vol", "variance": "realised_vol", "adx": "directional_index",
    "dmi": "directional_index", "rsi": "rsi", "carry": "swap_terms", "cot": "cot_positioning",
    "positioning": "cot_positioning", "macro": "macro_state", "event": "calendar_events",
    "news": "calendar_events", "liquidity": "tick_tape", "orderflow": "tick_tape",
    "spread": "tick_tape", "depth": "tick_tape", "residual": "peer_bars",
    "relative": "peer_bars", "correlation": "peer_bars", "pca": "peer_bars",
    "cross": "peer_bars", "lead": "peer_bars", "lag": "peer_bars", "triangle": "peer_bars",
    "basket": "peer_bars", "session": "clock_position", "asia": "clock_position",
    "london": "clock_position", "handoff": "clock_position", "fix": "clock_position",
    "clock": "clock_position", "turn": "calendar_date", "month": "calendar_date",
    "calendar": "calendar_date", "drawdown": "distance_from_peak",
}

#: param key -> the input it names. Keys naming a peer instrument expand to `peer:<VALUE>`.
_PARAM_FEATURES: dict[str, str] = {
    "stop_atr": "realised_vol", "target_atr": "realised_vol", "atr_n": "realised_vol",
    "entry_z": "zscore", "beta_win": "peer_bars", "band": "quantile_band",
    "horizon": "holding_clock", "max_hold": "holding_clock", "hold_bars": "holding_clock",
    "ttl_bars": "holding_clock", "wait_bars": "holding_clock", "range_start": "clock_position",
    "stamp_hour": "clock_position", "session": "clock_position", "selector": "clock_position",
}
_PEER_KEYS = ("input_symbol", "peer_symbol", "driver_symbol", "factor_symbols", "basket",
              "input_source", "peer", "factor")

#: Keys carrying a sign, a label or the chart -- never an input of their own.
_NON_FEATURE_KEYS = frozenset({"side", "direction", "side_mode", "label", "mode", "rr",
                               "timeframe", "name", "note"})
_HORIZON = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "4h",
            "D1": "1d", "W1": "1w"}


# --------------------------------------------------------------------------- tolerant readers

def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []
    return rows[-limit:] if limit else rows


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9_]{2,}", (text or "").lower()) if w not in _STOP}


def _tokens(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (name or "").lower())


def _jaccard(a: set[str], b: set[str]) -> float | None:
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < MIN_OVERLAP:
        return None
    xa, xb = a[:n], b[:n]
    ma, mb = sum(xa) / n, sum(xb) / n
    va = sum((x - ma) ** 2 for x in xa)
    vb = sum((x - mb) ** 2 for x in xb)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((xa[i] - ma) * (xb[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


# --------------------------------------------------------------------------- the cell in hand

@dataclass(frozen=True)
class Member:
    """One comparable cell: a candidate, a certified survivor, a sleeve or a judged docket row."""

    key: str
    symbol: str = ""
    family: str = ""
    timeframe: str = "H1"
    session: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    mechanism: str = ""
    source: str = ""
    origin: str = "candidate"
    ident: str = ""
    returns: list[float] = field(default_factory=list)


def _member(row: dict[str, Any], origin: str = "candidate", key: str = "") -> Member:
    """Read a cell out of whatever shape the desk wrote it in. Never raises."""
    row = row if isinstance(row, dict) else {}
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    src = {**row, **spec}
    params = src.get("params") if isinstance(src.get("params"), dict) else {}
    symbol = str(src.get("symbol") or src.get("sym") or "").strip()
    family = str(src.get("family") or "").strip()
    tf = timeframe_of({"timeframe": src.get("timeframe"), "params": params})
    session = str(src.get("session") or src.get("selector") or src.get("window") or "").strip()
    text = " ".join(str(src.get(k) or "") for k in
                    ("hypothesis", "mechanism_note", "rationale", "claim", "text",
                     "source_title")).strip()
    source = str(src.get("expression") or src.get("code") or src.get("source_code") or "")
    ident = str(src.get("cell") or "") or cell_id(
        {"sym": symbol, "family": family, "params": params, "timeframe": tf})
    name = key or str(src.get("name") or src.get("cell") or src.get("sleeve_id") or ident)
    raw = src.get("returns") or src.get("r_multiples") or []
    rets = [float(r) for r in raw if isinstance(r, (int, float))] if isinstance(raw, list) else []
    return Member(key=name, symbol=symbol, family=family, timeframe=tf, session=session,
                  params=dict(params), text=text, mechanism=str(src.get("mechanism") or ""),
                  source=source, origin=origin, ident=ident, returns=rets)


# --------------------------------------------------------------------------- the four readings

def features_of(m: Member) -> set[str]:
    """Which inputs this cell consumes, from the family's own name and its parameter keys."""
    feats: set[str] = set()
    if m.symbol:
        feats.add(f"price:{m.symbol.upper()}")
    feats.add(f"chart:{m.timeframe.upper()}")
    if m.session and m.session.lower() not in ("continuous", "any", "none"):
        feats.add("clock_position")
        feats.add(f"clock:{m.session.lower()}")
    for tok in _tokens(m.family):
        feats.add(_FAMILY_FEATURES.get(tok) or f"fam:{tok}")
    for k, v in (m.params or {}).items():
        key = str(k).lower()
        if key in _NON_FEATURE_KEYS:
            continue
        if key in _PEER_KEYS:
            vals = v if isinstance(v, (list, tuple)) else [v]
            feats.add("peer_bars")
            feats.update(f"peer:{str(x).upper()}" for x in vals if x)
            continue
        if key == "feature" and v:
            # THE `discovered` FAMILY CARRIES ITS PRIMITIVE HERE. Without this, 17,354 docket rows
            # on one instrument would share one identical feature set and read as one bet.
            feats.add(f"primitive:{str(v).lower()}")
            continue
        feats.add(_PARAM_FEATURES.get(key) or f"param:{key}")
    return feats


def _claim_tokens(m: Member) -> set[str]:
    toks: set[str] = set(_tokens(m.family))
    if m.family:
        toks.add(f"fam:{m.family.lower()}")
    if m.symbol:
        toks.add(f"sym:{m.symbol.upper()}")
    toks.add(f"tf:{m.timeframe.upper()}")
    if m.session:
        toks.add(f"sess:{m.session.lower()}")
    toks.update(f"p:{str(k).lower()}" for k in (m.params or {}))
    return toks


def semantic_similarity(a: Member, b: Member) -> float | None:
    """The claim: prose where both sides carry it, structure always. The higher reading convicts."""
    struct = _jaccard(_claim_tokens(a), _claim_tokens(b))
    prose = _jaccard(_words(a.text), _words(b.text)) if (a.text and b.text) else None
    scores = [s for s in (struct, prose) if s is not None]
    return max(scores) if scores else None


def ast_similarity(a: Member, b: Member) -> float | None:
    """AST node-type Jaccard. Reported only -- syntax is not an economic difference."""
    if not (a.source and b.source):
        return None
    return program_similarity(a.source, b.source)


_SERIES_CACHE: dict[tuple[str, str, str, str], Any] = {}


def _series_for(m: Member) -> tuple[str, dict[str, float] | list[float]] | None:
    """Realised R for this cell, WITH the source it came from: inline, else the shadow ledger.

    The source is returned because a pre-test candidate has no ledger of its own and resolves to
    its INCUMBENT'S: correlating that with the incumbent is a series against itself, and it read
    1.00 on three of the first three hundred docket rows -- a conviction manufactured out of one
    file. `returns_similarity` refuses a comparison whose two sides share a source.
    """
    if m.returns:
        return (f"inline:{id(m)}", list(m.returns))
    if not m.symbol:
        return None
    sym, fam = m.symbol.upper(), m.family.lower()
    sess = m.session.lower() or "continuous"
    cache_key = (str(SHADOW_DIR), sym, fam, sess)
    if cache_key in _SERIES_CACHE:
        return _SERIES_CACHE[cache_key]
    paths = [SHADOW_DIR / n for n in (f"ledger_{sym}_{fam}_{sess}.json",
                                      f"ledger_{sym}_{fam}_continuous.json",
                                      f"ledger_{sym}_{sess}.json")]
    if fam:
        with contextlib.suppress(OSError):
            paths.extend(sorted(SHADOW_DIR.glob(f"ledger_{sym}_{fam}_*.json")))
    out: tuple[str, dict[str, float]] | None = None
    for path in paths:
        rows = _json(path)
        if not isinstance(rows, list) or not rows:
            continue
        keyed: dict[str, float] = {}
        for trade in rows:
            if not isinstance(trade, dict):
                continue
            r = trade.get("r_multiple")
            stamp = str(trade.get("entry_time") or trade.get("at") or "")[:16]
            if isinstance(r, (int, float)) and stamp:
                keyed[stamp] = keyed.get(stamp, 0.0) + float(r)
        if len(keyed) >= MIN_OVERLAP:
            out = (str(path), keyed)
            break
    _SERIES_CACHE[cache_key] = out
    return out


def returns_similarity(a: Member, b: Member) -> float | None:
    """|correlation| of realised R on the overlapping stamps. UNMEASURED below 20 pairs, and
    UNMEASURED when both sides resolve to the SAME ledger -- a series against itself is 1.00 and
    says nothing about the candidate."""
    ra, rb = _series_for(a), _series_for(b)
    if ra is None or rb is None:
        return None
    (src_a, sa), (src_b, sb) = ra, rb
    if src_a == src_b:
        return None
    if isinstance(sa, dict) and isinstance(sb, dict):
        keys = sorted(set(sa) & set(sb))
        if len(keys) < MIN_OVERLAP:
            return None
        xa, xb = [sa[k] for k in keys], [sb[k] for k in keys]
    else:
        xa = list(sa.values()) if isinstance(sa, dict) else list(sa)
        xb = list(sb.values()) if isinstance(sb, dict) else list(sb)
    c = _pearson(xa, xb)
    return None if c is None else abs(c)


def param_region(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Same parameter region: the same keys, every numeric inside 10%, everything else equal."""
    a, b = a or {}, b or {}
    if set(a) != set(b):
        return False
    for k, x in a.items():
        y = b[k]
        if isinstance(x, bool) or isinstance(y, bool):
            if x != y:
                return False
        elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
            scale = max(abs(float(x)), abs(float(y)))
            if scale and abs(float(x) - float(y)) > PARAM_BAND * scale:
                return False
        elif str(x) != str(y):
            return False
    return True


def complexity_of(m: Member) -> float:
    """Free parameters plus expression size, in parameter-equivalents. Regularisation, measured."""
    size = 0.0
    if m.source:
        nodes = sum(dict(ast_shape(m.source)).values())
        if not nodes:
            nodes = len(re.findall(r"[A-Za-z_0-9.]+|[^\sA-Za-z_0-9]", m.source))
        size = nodes / AST_NODES_PER_PARAM
    return round(len(m.params or {}) + size, 3)


def alignment_of(m: Member) -> bool | None:
    """tri_alignment's verdict, when this cell carries BOTH a story and an implementation."""
    if _tri is None or not (m.text and m.source):
        return None
    # An unrecognised mechanism name is passed as empty: tri_alignment rejects a mechanism it does
    # not know BY DESIGN, and that is a fact about its vocabulary, not about this candidate. The
    # clock and lookahead checks still run.
    vocab = getattr(_tri, "_MECHANISM_TOKENS", {})
    mech = m.mechanism if m.mechanism in vocab else ""
    try:
        res = _tri.check(hypothesis=m.text, mechanism=mech, code=m.source,
                         horizon=_HORIZON.get(m.timeframe.upper(), ""),
                         coordinate_context=f"{m.symbol} {m.session}")
    except Exception:  # pragma: no cover - a flag must never break the funnel
        return None
    return bool(res.ok)


# --------------------------------------------------------------------------- the library

@dataclass
class Library:
    """Certified survivors, live sleeves and recently judged cells -- read tolerantly, or empty."""

    members: list[Member] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    by_symbol: dict[str, list[Member]] = field(default_factory=dict)
    by_family: dict[str, list[Member]] = field(default_factory=dict)
    by_ident: dict[str, Member] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for m in self.members:
            self.by_symbol.setdefault(m.symbol.upper(), []).append(m)
            self.by_family.setdefault(m.family.lower(), []).append(m)
            if m.ident:
                self.by_ident.setdefault(m.ident, m)

    @classmethod
    def load(cls) -> Library:
        """Three files, read tolerantly. An absent or unreadable one contributes nothing."""
        members: list[Member] = []
        counts = {"survivors": 0, "sleeves": 0, "judged": 0}

        surv = _json(SURVIVORS) or {}
        rows = surv.get("survivors") if isinstance(surv, dict) else surv
        pairs = (list(rows.items()) if isinstance(rows, dict)
                 else [("", r) for r in (rows or []) if isinstance(r, dict)])
        for key, row in pairs:
            if isinstance(row, dict):
                members.append(_member(row, "survivor", key=str(key)))
                counts["survivors"] += 1

        sl = _json(SLEEVES) or {}
        for row in (sl.get("sleeves") if isinstance(sl, dict) else sl) or []:
            if isinstance(row, dict) and (row.get("symbol") or row.get("sym")):
                members.append(_member(row, "sleeve"))
                counts["sleeves"] += 1

        seen: set[str] = set()
        for row in _jsonl(VERDICTS):
            ident = str(row.get("cell") or "")
            if not ident or ident in seen:
                continue
            seen.add(ident)
            members.append(_member(row, "judged", key=ident))
            counts["judged"] += 1

        return cls(members=members, counts=counts)

    def compare_set(self, cand: Member) -> list[Member]:
        """Members worth comparing: same instrument first, then same family, bounded."""
        out: list[Member] = []
        seen: set[int] = set()
        for bucket in (self.by_symbol.get(cand.symbol.upper(), []),
                       self.by_family.get(cand.family.lower(), [])):
            for m in bucket:
                if id(m) in seen:
                    continue
                seen.add(id(m))
                out.append(m)
                if len(out) >= MAX_COMPARISONS:
                    return out
        return out


# --------------------------------------------------------------------------- the verdict

@dataclass(frozen=True)
class Verdict:
    """`twin` is the NEAREST library member compared: the duplicate when REDUNDANT, the closest
    thing the library holds when NOVEL -- and `why` says which, and on what evidence."""

    novel: bool
    dims: dict[str, float | None]
    twin: str | None
    why: str
    complexity: float
    oversized: bool
    aligned: bool | None
    cell: str = ""
    verdict: str = "NOVEL"

    def __bool__(self) -> bool:
        return self.novel

    def as_dict(self) -> dict[str, Any]:
        return {"cell": self.cell, "verdict": self.verdict, "novel": self.novel,
                "dims": self.dims, "twin": self.twin, "why": self.why,
                "complexity": self.complexity, "oversized": self.oversized,
                "aligned": self.aligned}


def _blank_dims() -> dict[str, float | None]:
    return dict.fromkeys(DIMENSIONS)


def admit(candidate: dict[str, Any], library: Library | None = None) -> Verdict:
    """Screen ONE candidate against the desk's library, before a trial is spent on it.

    `library` is optional; pass one (or call `screen`) for a batch, because loading it per call
    re-reads three files. Absent inputs make an EMPTY library, never an exception.
    """
    lib = library if library is not None else Library.load()
    cand = _member(candidate, "candidate")
    comp = complexity_of(cand)
    over = comp > OVERSIZED_AT
    aligned = alignment_of(cand)
    dims = _blank_dims()

    def out(novel: bool, verdict: str, twin: str | None, why: str,
            scored: dict[str, float | None] | None = None) -> Verdict:
        return Verdict(novel, dims if scored is None else scored, twin, why, comp, over, aligned,
                       cell=cand.ident or cand.key, verdict=verdict)

    if not lib.members:
        return out(True, "NOVEL", None,
                   "the library is empty -- there is nothing here to be a clone of, and an "
                   "unreadable library is reported as empty rather than as agreement")

    exact = lib.by_ident.get(cand.ident)
    if exact is not None:
        # Scored anyway, so `by_dimension` counts a short-circuit as MEASURED rather than as a
        # dimension that could not be read -- those are different facts about the gate.
        dims["feature"] = _jaccard(features_of(cand), features_of(exact))
        dims["semantic"] = semantic_similarity(cand, exact)
        dims["ast"] = ast_similarity(cand, exact)
        dims["returns"] = returns_similarity(cand, exact)
        clock = ""
        if cand.session and exact.session and cand.session.lower() != exact.session.lower():
            clock = (f". The clocks differ ({cand.session} vs {exact.session}) but "
                     f"`frontier_identity.cell_id` does not carry the clock, so testing this "
                     f"would write its verdict under the incumbent's key")
        return out(False, "REDUNDANT", exact.key,
                   f"exact cell identity: this IS {exact.key} ({exact.origin}), already in the "
                   f"library. Re-testing it spends a trial on an answered question{clock}")

    best: Member | None = None
    best_score = -1.0
    best_dims = _blank_dims()
    region: Member | None = None
    region_score = -1.0
    cand_feats = features_of(cand)

    for m in lib.compare_set(cand):
        scored = _blank_dims()
        scored["feature"] = _jaccard(cand_feats, features_of(m))
        scored["semantic"] = semantic_similarity(cand, m)
        scored["ast"] = ast_similarity(cand, m)
        cheap = [v for k, v in scored.items() if k in ECONOMIC_DIMS and v is not None]
        score = sum(cheap) / len(cheap) if cheap else -1.0
        if (score > region_score and m.family.lower() == cand.family.lower()
                and m.symbol.upper() == cand.symbol.upper()
                and m.timeframe.upper() == cand.timeframe.upper()
                and param_region(cand.params, m.params)):
            region, region_score = m, score
        if score > best_score:
            best, best_score, best_dims = m, score, scored

    # THE PARAMETER REGION CONVICTS ON ITS OWN, and only realised returns can overturn it. Returns
    # are measured HERE and for the nearest member only: reading a ledger costs file IO, and those
    # are the two comparisons where the number can change a verdict.
    if region is not None:
        scored = best_dims if best is region else _blank_dims()
        scored["feature"] = _jaccard(cand_feats, features_of(region))
        scored["semantic"] = semantic_similarity(cand, region)
        scored["ast"] = ast_similarity(cand, region)
        scored["returns"] = returns_similarity(cand, region)
        r = scored["returns"]
        if r is not None and r < TWIN_AT:
            return out(True, "NOVEL", region.key,
                       f"a parameter step on {region.key}, but the realised returns disagree "
                       f"({r:.2f} < {TWIN_AT}) -- the measurement outranks the parameter rule",
                       scored)
        tail = ("" if r is not None else
                "; realised returns are UNMEASURED on both sides, which is why the parameter "
                "region is what decides")
        return out(False, "REDUNDANT", region.key,
                   f"same family, instrument and chart as {region.key}, every parameter inside "
                   f"{PARAM_BAND:.0%}: a sweep step, not a hypothesis{tail}", scored)

    if best is None:
        return out(False, "UNMEASURED", None,
                   "no library member shares this instrument or family, so nothing was compared. "
                   "UNMEASURED is a real answer (L1.28a); it is not a novelty claim")

    best_dims["returns"] = returns_similarity(cand, best)
    measured = {k: v for k, v in best_dims.items() if k in ECONOMIC_DIMS and v is not None}
    if not measured:
        return out(False, "UNMEASURED", best.key,
                   f"nearest member is {best.key}, but no economically meaningful dimension could "
                   f"be compared. Absence is not difference (L1.28a)", best_dims)

    distant = sorted((k for k, v in measured.items() if v < TWIN_AT), key=lambda k: measured[k])
    if distant:
        detail = ", ".join(f"{k} {measured[k]:.2f}" for k in distant)
        return out(True, "NOVEL", best.key,
                   f"distant from its nearest member {best.key} on {detail} (< {TWIN_AT}); one "
                   f"economically meaningful difference is enough", best_dims)
    twins = ", ".join(f"{k} {v:.2f}" for k, v in sorted(measured.items()))
    return out(False, "REDUNDANT", best.key,
               f"every measurable dimension reads as a twin of {best.key} ({twins}); the twin is "
               f"NAMED rather than the candidate rejected -- which of the pair survives is the "
               f"caller's decision", best_dims)


def screen(rows: list[dict[str, Any]], library: Library | None = None) -> list[Verdict]:
    """Batch: the library is read ONCE, then every row is judged against it."""
    lib = library if library is not None else Library.load()
    return [admit(r if isinstance(r, dict) else {}, lib) for r in rows]


# --------------------------------------------------------------------------- the artifact

def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomic where the filesystem allows it.

    `os.replace` onto a read-only destination is legal on POSIX and raises WinError 5 here -- the
    exact way a VPS-tested fix broke the box that trades -- so the flag is cleared and a direct
    write is the last resort, rather than a lost artifact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, sort_keys=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")
    with contextlib.suppress(OSError):
        tmp.unlink()


def _summarise(verdicts: list[Verdict], lib: Library, docket: Path) -> dict[str, Any]:
    by_dim: dict[str, Any] = {}
    for dim in DIMENSIONS:
        vals = [v.dims.get(dim) for v in verdicts]
        seen = [x for x in vals if x is not None]
        by_dim[dim] = {
            "measured": len(seen),
            "unmeasured": len(vals) - len(seen),
            "mean": round(sum(seen) / len(seen), 4) if seen else None,
            "twin_at_threshold": sum(1 for x in seen if x >= TWIN_AT),
            "establishes_novelty": dim in ECONOMIC_DIMS,
        }
    twins: dict[str, int] = {}
    for v in verdicts:
        if v.verdict == "REDUNDANT" and v.twin:
            twins[v.twin] = twins.get(v.twin, 0) + 1
    over = [v for v in verdicts if v.oversized]
    return {
        "at": datetime.now(UTC).isoformat(),
        "docket": str(docket),
        "n_screened": len(verdicts),
        "n_novel": sum(1 for v in verdicts if v.verdict == "NOVEL"),
        "n_redundant": sum(1 for v in verdicts if v.verdict == "REDUNDANT"),
        "n_unmeasured": sum(1 for v in verdicts if v.verdict == "UNMEASURED"),
        "threshold": TWIN_AT,
        "library": {"members": len(lib.members), **lib.counts},
        "by_dimension": by_dim,
        "twins_named": dict(sorted(twins.items(), key=lambda kv: -kv[1])[:20]),
        "n_twins_named": len(twins),
        "oversized": {"n": len(over), "threshold": OVERSIZED_AT,
                      "worst": sorted(v.cell for v in over)[:10]},
        "alignment": {"aligned": sum(1 for v in verdicts if v.aligned is True),
                      "misaligned": sum(1 for v in verdicts if v.aligned is False),
                      "unmeasurable": sum(1 for v in verdicts if v.aligned is None)},
        "sample": [v.as_dict() for v in verdicts if v.verdict == "REDUNDANT"][:20],
        "rule": RULE,
    }


def _rows_of(payload: Any) -> list[dict[str, Any]]:
    """The docket's rows, whichever of the desk's shapes it was written in."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "candidates", "survivors", "cells", "docket", "hypotheses"):
            got = payload.get(key)
            if isinstance(got, list):
                return [r for r in got if isinstance(r, dict)]
            if isinstance(got, dict):
                return [r for r in got.values() if isinstance(r, dict)]
    return []


def _dim_line(payload: dict[str, Any], n: int) -> str:
    parts = []
    for dim in DIMENSIONS:
        block = payload["by_dimension"][dim]
        mean = "" if block["mean"] is None else f" mean {block['mean']:.2f}"
        parts.append(f"{dim} {block['measured']}/{n}{mean}")
    return "dimension    | " + " | ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Novelty gate: screen a docket before it is tested.")
    ap.add_argument("--docket", default=str(DOCKET))
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    docket = Path(args.docket)
    rows = _rows_of(_json(docket))
    lib = Library.load()
    verdicts = screen(rows[: max(0, args.limit)], lib)
    payload = _summarise(verdicts, lib, docket)
    denom = len(verdicts) or 1

    print(f"novelty gate | docket {docket} | {len(verdicts)} of {len(rows)} rows screened")
    print(f"library      | {len(lib.members)} members "
          f"({lib.counts.get('survivors', 0)} certified, {lib.counts.get('sleeves', 0)} sleeves, "
          f"{lib.counts.get('judged', 0)} judged cells)")
    print(f"verdict      | NOVEL {payload['n_novel']} ({payload['n_novel'] / denom:.1%}) | "
          f"REDUNDANT {payload['n_redundant']} | UNMEASURED {payload['n_unmeasured']} | "
          f"{payload['n_twins_named']} twins named")
    print(_dim_line(payload, len(verdicts)))
    print(f"regularise   | oversized {payload['oversized']['n']} (> {OVERSIZED_AT} units) | "
          f"aligned {payload['alignment']['aligned']} | "
          f"misaligned {payload['alignment']['misaligned']} | "
          f"unmeasurable {payload['alignment']['unmeasurable']}")
    if args.dry_run:
        print("dry run      | nothing written")
    else:
        _write_atomic(Path(args.out), payload)
        print(f"wrote        | {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
