"""THE EXPRESSION ARCHAEOLOGIST: public WorldQuant-style formulas -> AST -> genome -> MT5.

Reads the notation of the 101-formulaic-alphas paper (Kakushadze 2016, arXiv:1601.00991) and of
public BRAIN documentation / community posts: function calls, `+ - * / ^`, comparisons, `&& ||`,
the C ternary `c ? a : b`, unary minus, dotted names (`IndClass.industry`) and keyword arguments
(`ts_decay_linear(x, 10, dense=false)`). Deterministic: the same text always gives the same tree.

Three identities, because "100 variants must not become 100 discoveries":

    exact_hash     the canonical tree with every constant (windows included)
    genome_hash    constants bucketed (windows to the desk's WINDOWS grid, scalars to sign) and
                   commutative arguments sorted -- two implementations that differ by a window of
                   9 vs 10 are ONE mechanism
    skeleton_hash  every constant erased: the operator/field topology only

`to_mt5()` rewrites a tree into `libs.research.alpha_grammar`'s prefix-list form so the desk's own
`formula` family (desks/mt5/mt5desk/family_formula.py) can execute it on one MT5 instrument. The
translation is the one the grammar already documents: a cross-sectional `rank(x)` becomes
`ts_rank(x, w)` (the same question asked of time), `volume` becomes `activity`, `returns` becomes
`ret`. Every approximation is NAMED on the result; anything that needs data the bars do not carry
(`cap`, fundamentals, `IndClass`, analyst fields) is refused with the field named, and that
refusal is a DATA_IDEA, not a loss.

AFFINE INVARIANCE. `family_formula` z-scores the expression over `norm` bars before thresholding,
so `c*x` (c>0) and `x + c` are the same signal as `x`; `-x` is kept as `neg`. The translator uses
that to drop the paper's scale constants honestly rather than approximating them.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

Node = tuple[Any, ...]  # ("num", v) ("var", name) ("call", name, args, kwargs) ("bin", op, a, b)
#               ("un", op, a) ("tern", c, a, b)

# ------------------------------------------------------------------------------ vocabulary
#: surface name (lower-case) -> canonical operator. Paper names, BRAIN names and common
#: community spellings fold to one vocabulary.
ALIASES: dict[str, str] = {
    "ts_argmax": "ts_argmax", "ts_argmin": "ts_argmin", "ts_rank": "ts_rank",
    "ts_min": "ts_min", "ts_max": "ts_max", "min": "min", "max": "max",
    "delta": "ts_delta", "ts_delta": "ts_delta", "delay": "ts_delay", "ts_delay": "ts_delay",
    "correlation": "ts_corr", "corr": "ts_corr", "ts_corr": "ts_corr", "ts_correlation": "ts_corr",
    "covariance": "ts_cov", "ts_covariance": "ts_cov", "cov": "ts_cov",
    "stddev": "ts_std", "ts_std_dev": "ts_std", "ts_std": "ts_std", "ts_stddev": "ts_std",
    "sum": "ts_sum", "ts_sum": "ts_sum", "product": "ts_product", "ts_product": "ts_product",
    "decay_linear": "ts_decay_linear", "ts_decay_linear": "ts_decay_linear",
    "decay_exp": "ts_decay_exp", "ts_decay_exp_window": "ts_decay_exp",
    "ts_mean": "ts_mean", "mean": "ts_mean", "sma": "ts_mean", "ts_av_diff": "ts_av_diff",
    "ts_zscore": "ts_zscore", "zscore": "zscore", "ts_scale": "ts_scale",
    "ts_backfill": "ts_backfill", "ts_regression": "ts_regression", "ts_skewness": "ts_skew",
    "ts_kurtosis": "ts_kurt", "ts_entropy": "ts_entropy", "ts_count_nans": "ts_count_nans",
    "ts_step": "ts_step", "ts_quantile": "ts_quantile", "hump": "hump",
    "rank": "rank", "scale": "scale", "normalize": "normalize", "quantile": "quantile",
    "winsorize": "winsorize", "truncate": "truncate",
    "signedpower": "signed_power", "signed_power": "signed_power", "power": "power",
    "abs": "abs", "log": "log", "sign": "sign", "sqrt": "sqrt", "exp": "exp",
    "inverse": "inverse", "reverse": "reverse", "s_log_1p": "s_log_1p",
    "indneutralize": "group_neutralize", "group_neutralize": "group_neutralize",
    "group_rank": "group_rank", "group_zscore": "group_zscore", "group_mean": "group_mean",
    "group_scale": "group_scale", "group_backfill": "group_backfill",
    "vector_neut": "vector_neut", "regression_neut": "regression_neut",
    "trade_when": "trade_when", "if_else": "if_else", "bucket": "bucket", "densify": "densify",
    "kth_element": "kth_element", "last_diff_value": "last_diff_value",
    "days_from_last_change": "days_from_last_change", "add": "add", "subtract": "subtract",
    "multiply": "multiply", "divide": "divide",
}
#: canonical operator -> class (the coverage tensor's operator axis).
OPERATOR_CLASS: dict[str, str] = {
    **dict.fromkeys((
        "ts_argmax", "ts_argmin", "ts_rank", "ts_min", "ts_max", "ts_delta",
        "ts_delay", "ts_corr", "ts_cov", "ts_std", "ts_sum", "ts_product",
        "ts_decay_linear", "ts_decay_exp", "ts_mean", "ts_av_diff",
        "ts_zscore", "ts_scale", "ts_backfill", "ts_regression", "ts_skew",
        "ts_kurt", "ts_entropy", "ts_count_nans", "ts_step", "ts_quantile",
        "hump", "days_from_last_change", "last_diff_value", "kth_element"),
        "time_series"),
    **dict.fromkeys((
        "rank", "scale", "normalize", "quantile", "winsorize", "truncate",
        "zscore"),
        "cross_sectional"),
    **dict.fromkeys((
        "group_neutralize", "group_rank", "group_zscore", "group_mean",
        "group_scale", "group_backfill", "bucket", "densify"),
        "group"),
    **dict.fromkeys((
        "vector_neut", "regression_neut"),
        "vector"),
    **dict.fromkeys((
        "signed_power", "power", "abs", "log", "sign", "sqrt", "exp",
        "inverse", "reverse", "s_log_1p", "min", "max", "add", "subtract",
        "multiply", "divide"),
        "arithmetic"),
    **dict.fromkeys((
        "trade_when", "if_else"),
        "logical"),
}
#: public data-field vocabulary -> category (the coverage tensor's data axis). Unknown
#: identifiers are mined into the taxonomy by `worldquant.FieldTaxonomy`, never dropped.
FIELD_CATEGORY: dict[str, str] = {
    **dict.fromkeys((
        "open", "high", "low", "close", "volume", "vwap", "returns", "adv5",
        "adv10", "adv15", "adv20", "adv30", "adv40", "adv50", "adv60",
        "adv81", "adv120", "adv150", "adv180", "cap", "sharesout", "split",
        "dividend"),
        "price_volume"),
    **dict.fromkeys((
        "indclass.sector", "indclass.industry", "indclass.subindustry",
        "sector", "industry", "subindustry", "market", "country", "exchange"),
        "group"),
}
FIELD_PREFIX_CATEGORY: tuple[tuple[str, str], ...] = (
    ("fnd", "fundamental"), ("fn_", "fundamental"), ("fundamental", "fundamental"),
    ("assets", "fundamental"), ("liabilities", "fundamental"), ("sales", "fundamental"),
    ("revenue", "fundamental"), ("ebit", "fundamental"), ("eps", "fundamental"),
    ("debt", "fundamental"), ("cash", "fundamental"), ("equity", "fundamental"),
    ("operating_", "fundamental"), ("book", "fundamental"), ("income", "fundamental"),
    ("anl", "analyst"), ("est_", "analyst"), ("analyst", "analyst"), ("mdl", "model"),
    ("model", "model"), ("nws", "news"), ("news", "news"), ("snt", "sentiment"),
    ("sentiment", "sentiment"), ("scl", "social"), ("social", "social"), ("opt", "option"),
    ("implied_vol", "option"), ("iv", "option"), ("pcr", "option"), ("rsk", "risk"),
    ("beta", "risk"), ("shrt", "short_interest"), ("short", "short_interest"),
    ("insider", "insider"), ("inst", "institutional"), ("oth", "other"),
)

WINDOWS = (2, 3, 5, 8, 12, 24, 48, 120, 240)       # libs.research.alpha_grammar.WINDOWS
COMMUTATIVE_BIN = frozenset({"+", "*", "==", "!=", "&&", "||"})
COMMUTATIVE_CALL = frozenset({"ts_corr", "ts_cov", "min", "max", "add", "multiply"})


def field_category(name: str) -> str:
    n = name.lower()
    if n in FIELD_CATEGORY:
        return FIELD_CATEGORY[n]
    if re.fullmatch(r"adv\d+", n):
        return "price_volume"
    for pre, cat in FIELD_PREFIX_CATEGORY:
        if n.startswith(pre):
            return cat
    return "unknown"


# ---------------------------------------------------------------------------------- lexer
_TOK = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+(?:[eE][-+]?\d+)?)|([A-Za-z_][\w.]*)|"
                  r"(\|\||&&|==|!=|<=|>=|[-+*/^<>?:(),=!]))")


class ParseError(ValueError):
    pass


def tokens(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    s = text.strip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m or m.end() == pos:
            if s[pos:].strip() == "":
                break
            raise ParseError(f"bad character {s[pos]!r} at {pos}")
        pos = m.end()
        if m.group(1):
            out.append(("num", m.group(1)))
        elif m.group(2):
            out.append(("id", m.group(2)))
        elif m.group(3):
            out.append(("op", m.group(3)))
    return out


_BP = {"?": 1, "||": 2, "&&": 3, "==": 4, "!=": 4, "<": 5, ">": 5, "<=": 5, ">=": 5,
       "+": 6, "-": 6, "*": 7, "/": 7, "^": 9}


def _fold(op: str, a: Node, b: Node) -> Node:
    """Constant folding: `(1 - 0.728317)` is a number, not an expression."""
    if a[0] == "num" and b[0] == "num":
        x, y = float(a[1]), float(b[1])
        try:
            v = {"+": x + y, "-": x - y, "*": x * y, "/": x / y if y else math.nan,
                 "^": x ** y if x >= 0 else math.nan}.get(op)
        except (OverflowError, ZeroDivisionError):
            v = None
        if v is not None and math.isfinite(v):
            return ("num", v)
    return ("bin", op, a, b)


class _Parser:
    def __init__(self, toks: list[tuple[str, str]]) -> None:
        self.t = toks
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self, val: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok is None or (val is not None and tok[1] != val):
            raise ParseError(f"expected {val!r} at token {self.i}, got {tok}")
        self.i += 1
        return tok

    def expr(self, rbp: int = 0) -> Node:
        left = self.prefix()
        while True:
            tok = self.peek()
            if tok is None or tok[0] != "op" or tok[1] not in _BP or _BP[tok[1]] <= rbp:
                return left
            op = tok[1]
            self.i += 1
            if op == "?":
                a = self.expr(0)
                self.take(":")
                b = self.expr(0)
                left = ("tern", left, a, b)
            else:
                # ^ is right-associative; everything else left-associative
                right = self.expr(_BP[op] - 1 if op == "^" else _BP[op])
                left = _fold(op, left, right)

    def prefix(self) -> Node:
        tok = self.take()
        kind, val = tok
        if kind == "num":
            return ("num", float(val))
        if kind == "op" and val == "(":
            e = self.expr(0)
            self.take(")")
            return e
        if kind == "op" and val in ("-", "+", "!"):
            a = self.expr(8)
            if val == "+":
                return a
            if val == "-" and a[0] == "num":
                return ("num", -a[1])
            return ("un", val, a)
        if kind == "id":
            low = val.lower()
            if low in ("true", "false"):
                return ("num", 1.0 if low == "true" else 0.0)
            nxt = self.peek()
            if nxt is not None and nxt == ("op", "("):
                self.i += 1
                args: list[Node] = []
                kwargs: dict[str, Node] = {}
                if self.peek() != ("op", ")"):
                    while True:
                        t0, t1 = self.peek(), (self.t[self.i + 1] if self.i + 1 < len(self.t)
                                               else None)
                        if t0 and t0[0] == "id" and t1 == ("op", "="):
                            self.i += 2
                            kwargs[t0[1].lower()] = self.expr(0)
                        else:
                            args.append(self.expr(0))
                        if self.peek() == ("op", ","):
                            self.i += 1
                            continue
                        break
                self.take(")")
                return ("call", ALIASES.get(low, low), tuple(args),
                        tuple(sorted(kwargs.items())))
            return ("var", low)
        raise ParseError(f"unexpected {tok}")


def parse(text: str) -> Node:
    toks = tokens(text)
    if not toks:
        raise ParseError("empty expression")
    p = _Parser(toks)
    node = p.expr(0)
    if p.i != len(toks):
        raise ParseError(f"trailing tokens from {p.i}: {toks[p.i:p.i + 3]}")
    return node


# ------------------------------------------------------------------------------ inspection
def walk(node: Node) -> Iterator[Node]:
    yield node
    kind = node[0]
    if kind == "call":
        for a in node[2]:
            yield from walk(a)
        for _, v in node[3]:
            yield from walk(v)
    elif kind == "bin":
        yield from walk(node[2])
        yield from walk(node[3])
    elif kind == "un":
        yield from walk(node[2])
    elif kind == "tern":
        for a in node[1:]:
            yield from walk(a)


def operators_in(node: Node) -> list[str]:
    return sorted({n[1] for n in walk(node) if n[0] == "call"})


def fields_in(node: Node) -> list[str]:
    return sorted({n[1] for n in walk(node) if n[0] == "var"})


def windows_in(node: Node) -> list[int]:
    out = []
    for n in walk(node):
        if n[0] == "call" and OPERATOR_CLASS.get(n[1]) == "time_series":
            for a in n[2][1:]:
                if a[0] == "num" and a[1] >= 1:
                    out.append(round(a[1]))
    return sorted(set(out))


def depth(node: Node) -> int:
    kind = node[0]
    if kind == "call":
        kids = list(node[2]) + [v for _, v in node[3]]
    elif kind == "bin":
        kids = [node[2], node[3]]
    elif kind == "un":
        kids = [node[2]]
    elif kind == "tern":
        kids = list(node[1:])
    else:
        return 1
    return 1 + max((depth(k) for k in kids), default=0)


def render(node: Node) -> str:
    kind = node[0]
    if kind == "num":
        v = node[1]
        return str(int(v)) if float(v).is_integer() else repr(v)
    if kind == "var":
        return str(node[1])
    if kind == "call":
        parts = [render(a) for a in node[2]] + [f"{k}={render(v)}" for k, v in node[3]]
        return f"{node[1]}({', '.join(parts)})"
    if kind == "bin":
        return f"({render(node[2])} {node[1]} {render(node[3])})"
    if kind == "un":
        return f"{node[1]}{render(node[2])}"
    return f"({render(node[1])} ? {render(node[2])} : {render(node[3])})"


# ----------------------------------------------------------------------------- identities
def _bucket(v: float, *, window: bool) -> str:
    if window:
        w = max(1, round(v))
        return f"w{min(WINDOWS, key=lambda x: abs(math.log(x) - math.log(w)))}"
    return "c+" if v > 0 else "c-" if v < 0 else "c0"


def _canon(node: Node, mode: str, window: bool = False) -> Any:
    kind = node[0]
    if kind == "num":
        if mode == "exact":
            return ["num", round(node[1], 6)]
        if mode == "skeleton":
            return ["num"]
        return ["num", _bucket(node[1], window=window)]
    if kind == "var":
        return ["var", node[1]]
    if kind == "call":
        ts = OPERATOR_CLASS.get(node[1]) == "time_series"
        args = [_canon(a, mode, window=ts and i > 0) for i, a in enumerate(node[2])]
        if node[1] in COMMUTATIVE_CALL and mode != "exact":
            head = sorted(args[:2], key=json.dumps)
            args = head + args[2:]
        kw = [[k, _canon(v, mode)] for k, v in node[3]]
        return ["call", node[1], args, kw]
    if kind == "bin":
        a, b = _canon(node[2], mode), _canon(node[3], mode)
        if node[1] in COMMUTATIVE_BIN and mode != "exact":
            a, b = sorted([a, b], key=json.dumps)
        return ["bin", node[1], a, b]
    if kind == "un":
        return ["un", node[1], _canon(node[2], mode)]
    return ["tern", *(_canon(x, mode) for x in node[1:])]


def _h(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, separators=(",", ":")).encode()).hexdigest()[:20]


def exact_hash(node: Node) -> str:
    return _h(_canon(node, "exact"))


def genome_hash(node: Node) -> str:
    return _h(_canon(node, "genome"))


def skeleton_hash(node: Node) -> str:
    return _h(_canon(node, "skeleton"))


@dataclass
class Genome:
    text: str
    canonical: str
    exact: str
    genome: str
    skeleton: str
    operators: list[str]
    operator_classes: list[str]
    fields: list[str]
    field_categories: list[str]
    windows: list[int]
    depth: int

    def as_row(self) -> dict[str, Any]:
        return dict(self.__dict__)


def genome_of(text: str) -> Genome:
    node = parse(text)
    ops = operators_in(node)
    flds = fields_in(node)
    return Genome(text=text.strip(), canonical=render(node), exact=exact_hash(node),
                  genome=genome_hash(node), skeleton=skeleton_hash(node), operators=ops,
                  operator_classes=sorted({OPERATOR_CLASS.get(o, "unknown") for o in ops}),
                  fields=flds, field_categories=sorted({field_category(f) for f in flds}),
                  windows=windows_in(node), depth=depth(node))


# ------------------------------------------------------------------------ text -> formulas
_ALPHA_LINE = re.compile(r"Alpha\s*#\s*(\d{1,3})\s*[:\t ]\s*(.+)$", re.I)
_QUOTED = re.compile(r"""["'`]([^"'`\n]{8,600})["'`]""")
_KNOWN_CALL = re.compile(r"\b(" + "|".join(sorted({re.escape(k) for k in ALIASES}, key=len,
                                                     reverse=True)) + r")\s*\(", re.I)


def _balanced_from(s: str, start: int) -> str:
    """The shortest prefix of s[start:] that closes every paren it opens, extended across
    binary operators so `rank(a) * rank(b)` is taken whole."""
    depth_ = 0
    end = start
    i = start
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth_ += 1
        elif ch == ")":
            depth_ -= 1
            if depth_ < 0:
                break
            if depth_ == 0:
                end = i + 1
                j = i + 1
                while j < len(s) and s[j] == " ":
                    j += 1
                if j >= len(s) or s[j] not in "+-*/^<>=!&|?:":
                    break                         # the expression ends here
        elif depth_ == 0 and ch in ";#\n,]}\"'`":
            break
        i += 1
    return s[start:end]


def plausible(node: Node) -> bool:
    """A formula, not a line of host-language code: every variable is a known data field (no
    `self.x`, `insight.price`, `df`), every call carries an argument, and a field is read."""
    vars_ = fields_in(node)
    if not vars_:
        return False
    for v in vars_:
        if field_category(v) == "unknown" or ("." in v and not v.lower().startswith("indclass")):
            return False
    return all(len(n[2]) + len(n[3]) > 0 for n in walk(node) if n[0] == "call")


def extract_formulas(text: str, *, max_n: int = 200) -> list[tuple[str, str]]:
    """(label, formula) pairs a document states. Labels are 'alpha#N', 'quoted' or 'inline'.
    Only strings that PARSE and call at least one known operator are returned."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: str, f: str) -> None:
        f = f.strip().rstrip(";,")
        if len(found) >= max_n or not f or f in seen or not _KNOWN_CALL.search(f):
            return
        try:
            node = parse(f)
        except (ParseError, RecursionError):
            return
        if not label.startswith("alpha#") and not plausible(node):
            return
        seen.add(f)
        found.append((label, f))

    for line in str(text).splitlines():
        m = _ALPHA_LINE.search(line)
        if m:
            add(f"alpha#{int(m.group(1))}", m.group(2))
            continue
        for q in _QUOTED.finditer(line):
            add("quoted", q.group(1))
        pos = 0
        for k in _KNOWN_CALL.finditer(line):
            if k.start() < pos:
                continue                      # inside an expression already taken
            # widen left to an opening paren / unary minus that belongs to the expression
            start = k.start()
            while start > 0 and line[start - 1] in "(-":
                start -= 1
            cand = _balanced_from(line, start) or _balanced_from(line, k.start())
            add("inline", cand)
            pos = start + max(1, len(cand))
    return found


# ---------------------------------------------------------------------------- MT5 rewrite
BAR_FIELDS: dict[str, str] = {"close": "close", "open": "open", "high": "high", "low": "low",
                              "volume": "activity", "returns": "ret"}
APPROX_FIELDS: dict[str, tuple[str, str]] = {
    "vwap": ("close", "vwap approximated by close (no traded volume at price in MT5 bars)")}
RANK_WINDOW = 120


class Untranslatable(ValueError):
    def __init__(self, reason: str, needs: Iterable[str] = ()) -> None:
        super().__init__(reason)
        self.reason = reason
        self.needs = list(needs)


@dataclass
class Translation:
    expr: Any
    approximations: list[str] = field(default_factory=list)


def _snap(v: float) -> int:
    w = max(2, round(abs(v)))
    return min(WINDOWS, key=lambda x: abs(math.log(x) - math.log(w)))


def _num(node: Node) -> float | None:
    return float(node[1]) if node[0] == "num" else None


def to_mt5(node: Node) -> Translation:
    """Rewrite onto alpha_grammar terminals/operators; raise Untranslatable with the reason
    (and the data it would need) otherwise."""
    notes: list[str] = []

    def tr(n: Node) -> Any:
        kind = n[0]
        if kind == "num":
            raise Untranslatable("bare constant as a signal operand")
        if kind == "var":
            name = n[1]
            if re.fullmatch(r"adv\d+", name):
                return ["mean", "activity", _snap(float(name[3:]))]
            if name in BAR_FIELDS:
                return BAR_FIELDS[name]
            if name in APPROX_FIELDS:
                notes.append(APPROX_FIELDS[name][1])
                return APPROX_FIELDS[name][0]
            raise Untranslatable(f"field {name!r} is not on MT5 bars", [name])
        if kind == "un":
            if n[1] == "-":
                return ["neg", tr(n[2])]
            raise Untranslatable("logical not")
        if kind == "tern":
            raise Untranslatable("conditional (?:) needs a regime gate the grammar lacks")
        if kind == "bin":
            op, a, b = n[1], n[2], n[3]
            ca, cb = _num(a), _num(b)
            if op in ("*", "/") and (ca is not None or cb is not None):
                c = float(ca if ca is not None else cb or 0.0)
                other = b if ca is not None else a
                if op == "/" and ca is not None:
                    raise Untranslatable("constant divided by a series")
                if c == 0:
                    raise Untranslatable("multiplication by zero")
                inner = tr(other)
                if c < 0:
                    return ["neg", inner]
                notes.append("positive scale dropped (formula family z-scores)")
                return inner
            if op in ("+", "-") and (ca is not None or cb is not None):
                if cb is not None:
                    notes.append("additive constant dropped (formula family z-scores)")
                    return tr(a)
                inner = tr(b)
                notes.append("additive constant dropped (formula family z-scores)")
                return ["neg", inner] if op == "-" else inner
            if op in ("<", ">", "<=", ">=") and (ca is not None or cb is not None):
                notes.append(f"comparison {op} with a constant read as the signed series")
                if cb is not None:
                    return tr(a) if op in (">", ">=") else ["neg", tr(a)]
                return tr(b) if op in ("<", "<=") else ["neg", tr(b)]
            if op in ("<", ">", "<=", ">="):
                notes.append(f"comparison {op} read as a signed difference")
                x, y = tr(a), tr(b)
                return ["sub", y, x] if op in ("<", "<=") else ["sub", x, y]
            table = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
            if op == "^":
                if cb is not None and cb > 0:
                    notes.append("power with positive exponent kept monotone (base only)")
                    return tr(a)
                notes.append("series exponent dropped (base kept; sign-preserving proxy)")
                return tr(a)
            if op in table:
                return [table[op], tr(a), tr(b)]
            raise Untranslatable(f"operator {op}")
        # call
        name, args = n[1], n[2]

        def win(i: int, default: int = 24) -> int:
            if len(args) > i and args[i][0] == "num":
                return _snap(args[i][1])
            return default
        if name == "rank":
            notes.append("cross-sectional rank -> ts_rank over the series' own history")
            return ["ts_rank", tr(args[0]), RANK_WINDOW]
        if name in ("zscore", "normalize", "scale"):
            notes.append(f"cross-sectional {name} -> time-series zscore")
            return ["zscore", tr(args[0]), 240]
        simple = {"ts_delta": "delta", "ts_delay": "delay", "ts_std": "std", "ts_sum": "sum",
                  "ts_min": "min", "ts_max": "max", "ts_rank": "ts_rank", "ts_mean": "mean",
                  "ts_zscore": "zscore", "ts_decay_linear": "decay",
                  "ts_argmax": "bars_since_max", "ts_argmin": "bars_since_min",
                  "ts_backfill": "ts_backfill", "ts_scale": "scale"}
        if name in ("min", "max") and len(args) == 2 and args[1][0] != "num":
            return ["min2" if name == "min" else "max2", tr(args[0]), tr(args[1])]
        if name in ("min", "max"):
            return ["min" if name == "min" else "max", tr(args[0]), win(1)]
        if name in simple:
            return [simple[name], tr(args[0]), win(1)]
        if name in ("ts_corr", "ts_cov"):
            return ["corr" if name == "ts_corr" else "cov", tr(args[0]), tr(args[1]), win(2)]
        if name == "abs":
            return ["abs", tr(args[0])]
        if name == "sign":
            return ["sign", tr(args[0])]
        if name in ("log", "sqrt", "s_log_1p"):
            notes.append(f"{name} dropped (monotone; z-scoring keeps the order)")
            return tr(args[0])
        if name in ("signed_power", "power"):
            notes.append(f"{name} kept monotone (base only)")
            return tr(args[0])
        if name == "trade_when":
            return ["trade_when", tr(args[1]), tr(args[0])] if len(args) >= 2 else tr(args[0])
        if name in ("group_neutralize", "group_rank", "group_zscore", "group_mean"):
            notes.append(f"{name} over a peer group -> single series (the peer axis is lost)")
            return tr(args[0])
        if name in ("add", "subtract", "multiply", "divide"):
            op = {"add": "add", "subtract": "sub", "multiply": "mul", "divide": "div"}[name]
            return [op, tr(args[0]), tr(args[1])]
        if name == "ts_product":
            notes.append("ts_product read as ts_sum of the series (log-sum proxy)")
            return ["sum", tr(args[0]), win(1)]
        raise Untranslatable(f"operator {name!r} has no MT5 grammar form")

    try:
        out = tr(node)
    except IndexError as e:
        raise Untranslatable("operator called with fewer arguments than its form needs") from e
    if isinstance(out, str):
        raise Untranslatable("a bare field is not a signal")
    return Translation(out, list(dict.fromkeys(notes)))


def grammar_valid(expr: Any) -> tuple[bool, str]:
    """The desk grammar's own verdict, when importable (numpy/pandas present)."""
    try:
        from libs.research import alpha_grammar as g
    except Exception as exc:                                   # pragma: no cover - env
        return True, f"grammar not importable ({type(exc).__name__}); structural only"
    try:
        return bool(g.is_valid(expr)), ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:200]
