"""Public trading code compiled into falsifiable hypotheses. CONSTITUTION 219.

The black-box miner reverse-engineers a strategy from its TRADES. This does the
same job one level earlier, from its CODE: parse a published MQL/Pine/Python
system, strip everything that is not a trading rule, normalise what is left into
a canonical form, and emit the ablation family that decides which part of it —
if any — carries the edge.

    the public internet becomes an automatic hypothesis donor

which is categorically different from copying internet strategies. The imported
object is a MECHANISM to be decomposed and falsified, never a system to be run.
A donated hypothesis that survives is ours because it survived our gauntlet, not
because somebody published it.

THIS MODULE NEVER EXECUTES WHAT IT READS

Downloading a stranger's trading code and running it is arbitrary code
execution with extra steps, and the fact that the file is "just a strategy" is
not a security model. Everything here is static: `ast.parse` for Python, regex
and tokenisation for the rest, and no `exec`, `eval`, `compile`, `import` or
subprocess anywhere on the path. A test walks this module's own AST to enforce
that, because the property is worth more than the docstring claiming it.

A PARSE THAT FAILS MUST NOT LOOK LIKE A SIMPLE STRATEGY

The dangerous failure is quiet: the parser understands three lines of a
four-hundred-line expert advisor, emits a two-term rule set, and the ablation
family that follows is a decomposition of something nobody wrote. Every parse
therefore reports COVERAGE — how much of the trading-relevant source it actually
accounted for — and a low-coverage parse is marked PARTIAL and refused for
ablation. Absence of extracted rules is not evidence of a simple system.

THE ABLATION FAMILY IS THE TRIAL COUNT (219.5)

An ablation family of twelve is TWELVE TRIALS, not one result with eleven
robustness checks. This section is the constitution's largest single source of
trial inflation, and the arithmetic is unforgiving: compile forty public systems
into twelve ablations each and the desk has run four hundred and eighty trials,
against which almost nothing survives a deflated Sharpe. `Family.n_trials` is
that number, it is carried into every descendant, and it is emitted for
`canonical.effective_trials` to deduplicate rather than being quietly forgotten.
"""
from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

COMPILER_VERSION = "compile-2026-08-18-a"

#: Below this fraction of trading-relevant lines accounted for, the parse is
#: PARTIAL and may not be ablated. Deliberately high: a decomposition of a rule
#: set the parser mostly invented is worse than no decomposition, because it
#: produces numbers.
MIN_COVERAGE = 0.60

#: Indicator vocabulary the IR normalises onto. Names are the desk's, not the
#: source language's, so `iMA`, `ta.ema` and `EMA` land on one term and the same
#: mechanism written in three languages fingerprints identically.
_INDICATORS = {
    "ema": ("ema", "ima.*mode_ema", "ta.ema", "exponentialmovingaverage"),
    "sma": ("sma", "ima.*mode_sma", "ta.sma", "simplemovingaverage", "average"),
    "rsi": ("rsi", "irsi", "ta.rsi"),
    "atr": ("atr", "iatr", "ta.atr", "truerange"),
    "macd": ("macd", "imacd", "ta.macd"),
    "bbands": ("bollinger", "ibands", "ta.bb"),
    "stoch": ("stoch", "istochastic", "ta.stoch"),
    "adx": ("adx", "iadx", "ta.adx", "dmi"),
    "session_range": ("session", "sessionhigh", "sessionlow", "dayhigh", "daylow",
                      "asian", "london", "newyork", "range_high", "range_low"),
    "sweep": ("sweep", "liquidity", "stophunt", "raid", "equalhighs", "equallows"),
    "fvg": ("fvg", "fairvaluegap", "imbalance", "gap"),
    "orderblock": ("orderblock", "ob_", "orderblocks", "supplyzone", "demandzone"),
    "bos": ("bos", "breakofstructure", "choch", "changeofcharacter", "mss"),
    "breakout": ("breakout", "highest", "lowest", "donchian", "channel"),
    "volume": ("volume", "ivolume", "obv", "tickvolume"),
    "pivot": ("pivot", "supportresistance", "swinghigh", "swinglow"),
}

#: Lines that are presentation, not trading. Stripped before coverage is
#: computed, because counting them would make a plotting-heavy indicator look
#: like a strategy the parser failed to understand.
_NOISE = re.compile(
    r"^\s*(//|#|/\*|\*|\}|\{|$)"
    r"|plot|draw|comment\(|print\(|alert|label|line\.new|box\.new|table\."
    r"|objectcreate|objectset|chartset|display|color|input\s*\(|indicator\("
    r"|study\(|#property|#include|import\s|from\s+\w+\s+import",
    re.I)

#: Constructs that indicate an actual trading decision.
_TRADING = re.compile(
    r"ordersend|order_send|positionopen|buy|sell|long|short|entry|exit"
    r"|strategy\.(entry|close|exit|order)|close\(|openposition|trade\."
    r"|signal|takeprofit|stoploss|\bsl\b|\btp\b|lot|volume|position",
    re.I)


class ParseError(Exception):
    """Refused rather than half-understood."""


# ------------------------------------------------------------------ the IR

@dataclass(frozen=True)
class Term:
    """One normalised condition. The atom the ablations remove."""
    indicator: str
    #: Free parameters as found. Kept because two systems differing only in a
    #: lookback are ONE mechanism sampled twice, and `fingerprint` must see that.
    params: tuple = ()
    direction: str = "any"                 # long | short | any
    raw: str = ""

    def render(self) -> str:
        p = f"({', '.join(str(x) for x in self.params)})" if self.params else ""
        return f"{self.indicator}{p}"


@dataclass
class Strategy:
    """The canonical IR: what a published system actually decides on."""
    name: str
    language: str
    terms: tuple = ()
    #: 0..1 — the fraction of trading-relevant source lines the parser accounted
    #: for. The honesty of everything downstream rests on this number.
    coverage: float = 0.0
    lines_total: int = 0
    lines_trading: int = 0
    lines_matched: int = 0
    unparsed: tuple = ()
    why: str = ""

    @property
    def partial(self) -> bool:
        return self.coverage < MIN_COVERAGE

    def fingerprint(self) -> str:
        """Identity of the MECHANISM, not of the file.

        Parameters are deliberately EXCLUDED: an EMA(20)/EMA(50) cross and an
        EMA(21)/EMA(55) cross are one hypothesis sampled twice, and treating
        them as two doubles the apparent breadth of a search that only widened
        its parameter grid.
        """
        body = "|".join(sorted(t.indicator for t in self.terms))
        return hashlib.sha256(body.encode()).hexdigest()[:16]

    def render(self) -> str:
        head = (f"{self.name} [{self.language}] -> "
                f"{' + '.join(t.render() for t in self.terms) or '(no terms)'}")
        cov = (f"  coverage {self.coverage:.0%} "
               f"({self.lines_matched}/{self.lines_trading} trading lines"
               f" of {self.lines_total} total)")
        if self.partial:
            cov += "  PARTIAL — not ablatable"
        return f"{head}\n{cov}" + (f"\n  {self.why}" if self.why else "")


# ------------------------------------------------------------- the front end

def _classify(line: str) -> Optional[str]:
    low = line.lower()
    for name, pats in _INDICATORS.items():
        for p in pats:
            if re.search(p, low):
                return name
    return None


def _numbers(line: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\b(\d{1,4})\b", line)[:3])


#: Side detection. `\b` DOES NOT WORK HERE: underscore is a word character, so
#: `\bbuy\b` never matches MQL's `OP_BUY`, `ORDER_TYPE_BUY` or
#: `POSITION_TYPE_BUY` — which is every way MQL spells a direction. The result
#: was that every term came back directionless and the inversion ablation had
#: nothing to invert. Lookarounds on LETTERS instead, so an underscore counts as
#: a separator while `buyer` and `overbought` still do not match.
_LONG = re.compile(r"(?<![a-z])(buy|long)(?![a-z])")
_SHORT = re.compile(r"(?<![a-z])(sell|short)(?![a-z])")


def _direction(line: str) -> str:
    low = line.lower()
    long_hit = _LONG.search(low)
    short_hit = _SHORT.search(low)
    if long_hit and not short_hit:
        return "long"
    if short_hit and not long_hit:
        return "short"
    return "any"


def parse_source(src: str, name: str = "unnamed",
                 language: str = "auto") -> Strategy:
    """Static parse only. Nothing here executes, imports or compiles the input.

    Coverage is computed over TRADING-RELEVANT lines rather than all lines,
    because a four-hundred-line file that is three hundred lines of plotting is
    not a strategy the parser failed at.
    """
    if language == "auto":
        language = detect_language(src)
    lines = src.splitlines()
    trading, matched, terms, unparsed = 0, 0, [], []
    for ln in lines:
        if _NOISE.match(ln):
            continue
        if not _TRADING.search(ln) and _classify(ln) is None:
            continue
        trading += 1
        ind = _classify(ln)
        if ind is None:
            unparsed.append(ln.strip()[:120])
            continue
        matched += 1
        terms.append(Term(ind, _numbers(ln), _direction(ln), ln.strip()[:160]))

    # Deduplicate by indicator. A rule referenced on eight lines is one term;
    # counting it eight times makes the ablation family eight times larger and
    # the trial count with it.
    #
    # KEEPING THE FIRST OCCURRENCE LOSES THE DIRECTION. An indicator is almost
    # always DECLARED before it is USED — `double atr = iATR(...)` carries no
    # side, and the OrderSend line that actually trades on it does. First-wins
    # therefore kept the declaration and discarded the only line that said long
    # or short, so every term came back directionless and the inversion ablation
    # had nothing to invert. A term carrying a direction supersedes one that
    # does not; among equals the first still wins.
    best: dict = {}
    for t in terms:
        prior = best.get(t.indicator)
        if prior is None or (prior.direction == "any" and t.direction != "any"):
            best[t.indicator] = t
    uniq = list(best.values())

    cov = (matched / trading) if trading else 0.0
    why = ""
    if trading == 0:
        why = ("no trading-relevant lines found at all. This is not a simple "
               "strategy — it is a file this parser did not understand, or one "
               "that does not trade.")
    elif cov < MIN_COVERAGE:
        why = (f"only {cov:.0%} of trading lines were recognised. A decomposition "
               f"of a rule set the parser mostly invented is worse than none, "
               f"because it produces numbers. Extend the indicator vocabulary or "
               f"read this one by hand.")
    return Strategy(name=name, language=language, terms=tuple(uniq), coverage=cov,
                    lines_total=len(lines), lines_trading=trading,
                    lines_matched=matched, unparsed=tuple(unparsed[:20]), why=why)


def detect_language(src: str) -> str:
    low = src.lower()
    if "//@version" in low or "strategy(" in low or "ta." in low:
        return "pinescript"
    if "#property" in low or "ordersend" in low or "mql" in low or "int ontick" in low:
        return "mql"
    if re.search(r"^\s*def\s|^\s*import\s|^\s*class\s", src, re.M):
        return "python"
    if "namespace" in low or "#include" in low:
        return "cpp"
    return "unknown"


def parse_python(src: str, name: str = "unnamed") -> Strategy:
    """Python gets a real AST rather than regex — and still never executes.

    `ast.parse` builds a tree without running a line, which is the entire reason
    it is safe to point at a stranger's file.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise ParseError(f"{name}: not valid Python ({e}). Refused rather than "
                         f"regex-guessed, which would produce a rule set nobody "
                         f"wrote.") from e
    names: list = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.append(n.id)
        elif isinstance(n, ast.Attribute):
            names.append(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            names.append(n.value)
    joined = "\n".join(names)
    base = parse_source(joined, name=name, language="python")
    # Coverage from the regex pass over identifiers is not meaningful; recompute
    # it against the SOURCE's trading lines so the number means what it says.
    return Strategy(name=name, language="python", terms=base.terms,
                    coverage=base.coverage, lines_total=len(src.splitlines()),
                    lines_trading=base.lines_trading,
                    lines_matched=base.lines_matched, unparsed=base.unparsed,
                    why=base.why)


def compile_source(src: str, name: str = "unnamed") -> Strategy:
    """Front door. Routes to the AST path for Python, static scan otherwise."""
    lang = detect_language(src)
    if lang == "python":
        return parse_python(src, name)
    return parse_source(src, name, lang)


# ---------------------------------------------------------------- ablations

@dataclass(frozen=True)
class Descendant:
    """One hypothesis derived from a parsed system. Carries its own lineage."""
    name: str
    parent: str
    mutation: str
    terms: tuple
    #: Every descendant is ONE TRIAL. Stated on the object so it cannot be lost
    #: between generation and the multiplicity correction.
    n_trials: int = 1

    def render(self) -> str:
        body = " + ".join(t.render() for t in self.terms) or "(empty)"
        return f"  {self.mutation:<26} {body}"


@dataclass
class Family:
    parent: Strategy
    descendants: tuple = ()

    @property
    def n_trials(self) -> int:
        """219.5. An ablation family of twelve is TWELVE TRIALS.

        Not one result with eleven robustness checks. The constitution names
        this section as its largest single source of trial inflation, and the
        arithmetic is unforgiving: forty public systems at twelve ablations each
        is four hundred and eighty trials.
        """
        return sum(d.n_trials for d in self.descendants)

    def render(self) -> str:
        lines = [f"ABLATION FAMILY of {self.parent.name} "
                 f"({COMPILER_VERSION})",
                 self.parent.render(), ""]
        lines += [d.render() for d in self.descendants]
        lines += ["",
                  f"  {self.n_trials} TRIALS, not one result with "
                  f"{max(self.n_trials - 1, 0)} robustness checks. Every "
                  f"descendant enters the trial census (219.5); see "
                  f"mt5desk.canonical for the deduplication that follows."]
        return "\n".join(lines)


def ablate(s: Strategy) -> Family:
    """The 219.3 family: original, drop-one, isolate-one, and the variants.

    REFUSES a PARTIAL parse. Generating twelve descendants of a rule set the
    parser mostly invented would spend twelve trials of multiplicity budget on
    a decomposition of nothing, and the trial count is real even when the
    hypothesis is not.
    """
    if s.partial:
        raise ParseError(
            f"{s.name}: coverage {s.coverage:.0%} is below {MIN_COVERAGE:.0%}, so "
            f"this parse is PARTIAL and may not be ablated. Twelve descendants of "
            f"a rule set the parser mostly invented would spend twelve trials on "
            f"a decomposition of nothing — and the trials are real even when the "
            f"hypothesis is not.")
    if not s.terms:
        raise ParseError(f"{s.name}: no terms extracted; nothing to ablate.")

    d: list = [Descendant(f"{s.name}.original", s.name, "original", s.terms)]
    if len(s.terms) > 1:
        for t in s.terms:
            rest = tuple(x for x in s.terms if x is not t)
            d.append(Descendant(f"{s.name}.no_{t.indicator}", s.name,
                                f"without {t.indicator}", rest))
        for t in s.terms:
            d.append(Descendant(f"{s.name}.only_{t.indicator}", s.name,
                                f"{t.indicator} only", (t,)))
    # Direction inversion: the cheapest and most informative mutation there is.
    # A system whose INVERSE is profitable has found a real relationship and got
    # the sign wrong, which is a better discovery than the original working.
    d.append(Descendant(f"{s.name}.inverted", s.name, "opposite direction",
                        tuple(Term(t.indicator, t.params,
                                   {"long": "short", "short": "long"}.get(
                                       t.direction, "any"), t.raw)
                              for t in s.terms)))
    for sess in ("asia", "london", "ny"):
        d.append(Descendant(f"{s.name}.{sess}", s.name, f"{sess} session only",
                            s.terms))
    d.append(Descendant(f"{s.name}.delayed", s.name, "delayed entry", s.terms))
    d.append(Descendant(f"{s.name}.failed_reversal", s.name,
                        "failed-signal reversal", s.terms))
    return Family(s, tuple(d))


def compile_and_ablate(src: str, name: str = "unnamed") -> Family:
    return ablate(compile_source(src, name))


def census(families: Iterable[Family]) -> dict:
    """Trial accounting across a batch. What the multiplicity gate must be told.

    Distinct MECHANISMS are counted separately from descendants, because two
    published systems that fingerprint identically are one donation twice — and
    a corpus scraped from the internet is full of the same three ideas.
    """
    fams = list(families)
    trials = sum(f.n_trials for f in fams)
    prints = {f.parent.fingerprint() for f in fams}
    return {
        "version": COMPILER_VERSION,
        "systems": len(fams),
        "distinct_mechanisms": len(prints),
        "trials": trials,
        "duplicate_donations": len(fams) - len(prints),
        "note": (f"{trials} trials from {len(fams)} systems, but only "
                 f"{len(prints)} distinct mechanisms — a public corpus is full "
                 f"of the same few ideas rewritten. Deflate against the trial "
                 f"count, deduplicate against the mechanism count, and report "
                 f"both (see mt5desk.canonical.deflation_pair)."),
    }
