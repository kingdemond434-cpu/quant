"""THE LEAN CORPUS MINER: classify every public LEAN file by what it teaches, then mine each.

    zuck, 2026-09-30: "classify every algorithm into: actual strategy idea, alpha model, portfolio
    method, risk method, execution method, universe-selection method, data-processing method,
    reality/fill model, pure regression test / no alpha value. This avoids wasting compute
    treating infrastructure examples as strategies."

MEASURED on QuantConnect/Lean@41c6e603 (2026-09-30, tree of 6,354 files): Algorithm.Python 476,
Algorithm.CSharp 892, Algorithm.Framework 86, Indicators 233, Tests 1,029, Optimizer 18. About half
of Algorithm.Python is `*RegressionAlgorithm.py` -- negative/engineering knowledge, not alpha --
and `Algorithm.Python/Alphas/` holds the 14 former Alpha Streams strategies, the densest alpha
content in the repo. So the path is the first classifier and content the second.

Four products, each a different consumer (see `ontology.CONSUMERS`):

  classify_path()       the LEAN class of a file, from path and name alone (no read needed)
  component_record()    Universe / Alpha / Portfolio / Risk / Execution framework components:
                        class name, the parameters it exposes, the indicators it builds
  lean_rule()           an alpha file's rule in the SAME shape `libs.mining.extractor.read_code`
                        returns, so the #133 compiler maps it onto a registered family
  regression_lessons()  a regression test -> failure mode -> market mechanism -> MT5/Fusion
                        analogue -> the deterministic test this desk should add
  classify_issue()      a LEAN issue/PR -> one of ten failure categories
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from libs.civilizations import ontology as O

# ------------------------------------------------------------------------------------ classes
STRATEGY = "strategy_idea"
ALPHA_MODEL = "alpha_model"
PORTFOLIO = "portfolio_method"
RISK = "risk_method"
EXECUTION = "execution_method"
UNIVERSE = "universe_selection_method"
DATA_PROCESSING = "data_processing_method"
REALITY = "reality_fill_model"
INDICATOR = "indicator"
OPTIMIZER = "optimizer_method"
RESEARCH = "research_notebook"
REGRESSION = "regression_test"
TEST = "unit_test"
INFRA = "infrastructure"
DEMO = "api_demo"

LEAN_CLASSES: tuple[str, ...] = (STRATEGY, ALPHA_MODEL, PORTFOLIO, RISK, EXECUTION, UNIVERSE,
                                 DATA_PROCESSING, REALITY, INDICATOR, OPTIMIZER, RESEARCH,
                                 REGRESSION, TEST, INFRA, DEMO)

#: class -> ontology outcomes it is forced into (structure, not keywords).
CLASS_OUTCOMES: dict[str, tuple[str, ...]] = {
    STRATEGY: (O.ALPHA_MECHANISM,),
    ALPHA_MODEL: (O.ALPHA_MECHANISM,),
    PORTFOLIO: (O.PORTFOLIO_IDEA,),
    RISK: (O.RISK_IDEA,),
    EXECUTION: (O.EXECUTION_IDEA,),
    UNIVERSE: (O.UNIVERSE_IDEA,),
    DATA_PROCESSING: (O.DATA_IDEA,),
    REALITY: (O.EXECUTION_IDEA, O.VALIDATION_IDEA),
    INDICATOR: (O.FEATURE_PRIMITIVE,),
    OPTIMIZER: (O.RESEARCH_METHOD,),
    RESEARCH: (O.RESEARCH_METHOD,),
    REGRESSION: (O.FAILURE_KNOWLEDGE, O.VALIDATION_IDEA),
    TEST: (O.FAILURE_KNOWLEDGE,),
    INFRA: (O.INFRASTRUCTURE_PATTERN,),
    DEMO: (),
}

_FRAMEWORK_DIRS = {"Alphas": ALPHA_MODEL, "Portfolio": PORTFOLIO, "Risk": RISK,
                   "Execution": EXECUTION, "Selection": UNIVERSE}
_REALITY_NAME = re.compile(r"(Fill|Slippage|Fee|BuyingPower|Margin|Settlement|Leverage|"
                           r"ShortableProvider|InterestRate|MarketHours|Brokerage)Model|"
                           r"PartialFill|ForwardDataOnlyFill|Latency", re.I)
_DATA_NAME = re.compile(r"Consolidat|CustomData|Dropbox|History|Warmup|WarmUp|Renko|"
                        r"FillForward|Resolution|Tick|Auxiliary|Universe(Data|Dataset)", re.I)
_STRATEGY_BODY = re.compile(
    r"(set_holdings|SetHoldings|market_order|MarketOrder|liquidate|Liquidate|emit_insights|"
    r"EmitInsights|Insight\.price|Insight\.Price)", re.I)
_SIGNAL_BODY = re.compile(r"\b(self\.)?(RSI|EMA|SMA|MACD|BB|MOMP|ROC|ATR|STD|MOM|ADX|"
                          r"rsi|ema|sma|macd|bb|momp|roc|atr|std|mom|adx)\s*\(")


def classify_path(path: str, body: str = "") -> str:
    """The LEAN class of one file. `body` sharpens the call for Algorithm.* demos."""
    p = path.replace("\\", "/")
    parts = p.split("/")
    top = parts[0]
    name = parts[-1]
    if top in ("Tests",) or "/Tests/" in p:
        return TEST
    if name.endswith(("RegressionAlgorithm.py", "RegressionAlgorithm.cs")) or \
            "IRegressionAlgorithmDefinition" in body:
        return REGRESSION
    if top == "Algorithm.Framework":
        for d, cls in _FRAMEWORK_DIRS.items():
            if f"/{d}/" in p:
                return cls
        return INFRA
    if top == "Indicators":
        return INDICATOR
    if top.startswith("Optimizer"):
        return OPTIMIZER
    if top == "Research" or name.endswith(".ipynb"):
        return RESEARCH
    if top.startswith("Algorithm."):
        if "/Alphas/" in p:
            return STRATEGY
        if "/Benchmarks/" in p:
            return INFRA
        if _REALITY_NAME.search(name):
            return REALITY
        if re.search(r"Alpha(Model)?(Framework)?Algorithm|AlphaModel", name):
            return ALPHA_MODEL
        if re.search(r"PortfolioConstruction|Portfolio(Optimi[sz]ation)?Framework|"
                     r"BlackLitterman|RiskParity|MeanVariance|ConfidenceWeighted|"
                     r"InsightWeighting|SectorWeighting", name):
            return PORTFOLIO
        if re.search(r"Risk(Management)?", name):
            return RISK
        if re.search(r"Execution|VWAP|TWAP|Spread", name):
            return EXECUTION
        if re.search(r"Universe|Selection|Coarse|Fine|Constituent", name):
            return UNIVERSE
        if _DATA_NAME.search(name):
            return DATA_PROCESSING
        if re.search(r"Template|Demo|Charting|Notification|Schedul|Logging|Debug|Api|Object"
                     r"Store|Signal Export|SignalExport", name):
            return DEMO
        if body and _STRATEGY_BODY.search(body) and _SIGNAL_BODY.search(body):
            return STRATEGY
        return DEMO
    if top in ("Common", "Engine", "Brokerages") and _REALITY_NAME.search(name):
        return REALITY
    return INFRA


def outcomes_for(path: str, body: str, *, hints: tuple[str, ...] = ()) -> tuple[str,
                                                                                 list[O.Outcome]]:
    """(LEAN class, ontology outcomes). Structure forces the class outcome; content may add
    others (a portfolio model that states a ranking rule is ALSO an alpha mechanism)."""
    cls = classify_path(path, body)
    forced = CLASS_OUTCOMES.get(cls, ())
    outs = O.classify(body, hints=hints, forced=forced)
    if cls in (REGRESSION, TEST, DEMO, INFRA):
        # A test that places orders is not a strategy: drop the alpha reading it triggered.
        outs = [o for o in outs if o.kind != O.ALPHA_MECHANISM] or [
            O.Outcome(O.NO_VALUE, 0.0, [f"lean class {cls}"])]
    return cls, outs


# ------------------------------------------------------------------------------ components
_CLASS_DEF = re.compile(r"class\s+(\w+)\s*[(:]\s*([\w.<>, ]+)?")
_PY_INIT = re.compile(r"def\s+__init__\s*\(\s*self\s*,([^)]*)\)", re.S)
_CS_CTOR = re.compile(r"public\s+(\w+)\s*\(([^)]*)\)", re.S)
_INDICATOR_CALL = re.compile(
    r"\b(RSI|RelativeStrengthIndex|EMA|ExponentialMovingAverage|SMA|SimpleMovingAverage|MACD|"
    r"MovingAverageConvergenceDivergence|BB|BollingerBands|MOMP|MomentumPercent|ROC|RateOfChange|"
    r"ATR|AverageTrueRange|STD|StandardDeviation|ADX|AverageDirectionalIndex|Momentum|"
    r"LogReturn|KAMA|HMA|WMA|DonchianChannel|KeltnerChannels|Stochastic|WilliamsPercentR|"
    r"IchimokuKinkoHyo|AROON|Beta|Correlation|ZScore)\s*\(([^()]*)\)", re.I)


def _params(sig: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in sig.split(","):
        a = a.strip()
        if not a:
            continue
        name, _, default = a.partition("=")
        name = name.strip().split(":")[0].split()[-1] if name.strip() else ""
        if name and name != "self":
            out[name] = default.strip()
    return out


def component_record(path: str, body: str) -> dict[str, Any]:
    """What a framework component IS: its class, what it extends, its constructor parameters
    (the knobs a challenger would mutate), and the indicators it builds."""
    m = _CLASS_DEF.search(body)
    ctor = _PY_INIT.search(body) if path.endswith(".py") else None
    params: dict[str, str] = _params(ctor.group(1)) if ctor else {}
    if not ctor and m:
        for c in _CS_CTOR.finditer(body):
            if c.group(1) == m.group(1):
                params = _params(re.sub(r"\b(int|double|decimal|bool|string|Resolution|"
                                        r"TimeSpan\??|PortfolioBias|Func<[^>]*>)\s+", "",
                                        c.group(2)))
                break
    inds = sorted({g.group(1).upper() for g in _INDICATOR_CALL.finditer(body)})
    return {"lean_class": classify_path(path, body), "class_name": m.group(1) if m else "",
            "extends": (m.group(2) or "").strip() if m else "", "parameters": params,
            "indicators": inds, "path": path}


# ---------------------------------------------------------------------------------- rules
_INT = re.compile(r"(?<![\w.])(\d{1,3})(?![\w.])")
_NUM = re.compile(r"(?<![\w])(\d+(?:\.\d+)?)(?![\w])")


def _ints(args: str) -> list[int]:
    return [int(x) for x in _INT.findall(args)]


def lean_rule(body: str) -> dict[str, Any]:
    """An alpha file's rule in `extractor.read_code`'s shape: indicators with the periods the
    code states, named patterns, and lookahead flags. Periods are published values, never
    defaults, so the compiler can mark the cell `directly_published_rules`."""
    ind: dict[str, dict[str, Any]] = {}
    pats: list[str] = []
    ma: list[int] = []
    for g in _INDICATOR_CALL.finditer(body):
        name, args = g.group(1).upper(), g.group(2)
        nums = _ints(args)
        if name in ("RSI", "RELATIVESTRENGTHINDEX") and "rsi" not in ind:
            ind["rsi"] = {"n": nums[0] if nums else None, "lo": None, "hi": None}
        elif name in ("EMA", "EXPONENTIALMOVINGAVERAGE", "SMA", "SIMPLEMOVINGAVERAGE", "KAMA",
                      "HMA", "WMA") and nums:
            ma.append(nums[0])
        elif name in ("MACD", "MOVINGAVERAGECONVERGENCEDIVERGENCE") and len(nums) >= 2:
            ma.extend(nums[:2])
        elif name in ("BB", "BOLLINGERBANDS"):
            fl = [float(x) for x in _NUM.findall(args)]
            ind["bb"] = {"n": int(fl[0]) if fl else None, "k": fl[1] if len(fl) > 1 else None}
        elif name in ("MOMP", "MOMENTUMPERCENT", "ROC", "RATEOFCHANGE", "MOMENTUM", "LOGRETURN"):
            pats.append("momentum")
        elif name in ("DONCHIANCHANNEL",):
            pats.append("prev_day_breakout")
    if "rsi" in ind:
        lo = re.search(r"(?:<|below|oversold\w*\s*=)\s*(\d{1,2})\b", body)
        hi = re.search(r"(?:>|above|overbought\w*\s*=)\s*([5-9]\d)\b", body)
        ind["rsi"]["lo"] = int(lo.group(1)) if lo else None
        ind["rsi"]["hi"] = int(hi.group(1)) if hi else None
    uniq = sorted(set(ma))
    if len(uniq) >= 2:
        ind["ma"] = {"fast": uniq[0], "slow": uniq[-1]}
    low = body.lower()
    if re.search(r"mean.?reversion|revert|reversal", low):
        pats.append("range_reversion")
    if re.search(r"\bgap\b", low):
        pats.append("monday_gap_fade" if "revers" in low or "fade" in low else "monday_gap")
    if "breakout" in low or "dual thrust" in low or "dualthrust" in low:
        pats.append("session_breakout")
    if "lunch" in low or "intraday reversal" in low:
        pats.append("range_reversion")
    tf = "H1"
    if re.search(r"Resolution\.(DAILY|Daily)", body):
        tf = "D1"
    elif re.search(r"Resolution\.(MINUTE|Minute)", body):
        tf = "M5"
    leaks = []
    if re.search(r"\.shift\(\s*-\d", body):
        leaks.append("negative shift reads a future bar")
    return {"indicators": ind, "patterns": list(dict.fromkeys(pats)), "regimes": [],
            "timeframe": tf, "hours": [], "lookahead": leaks}


# ------------------------------------------------------------------- regression archaeology
#: tag -> (name regex, market mechanism, MT5/Fusion analogue, deterministic test to add).
FAILURE_MODES: dict[str, tuple[re.Pattern[str], str, str, str]] = {
    "futures_rollover": (
        re.compile(r"Rollover|ContinuousFuture|FrontMonth|Mapping|MappedSymbol", re.I),
        "a continuous contract switches underlying and the price series jumps",
        "index/energy CFDs roll their underlying future; broker adjusts price or swap",
        "on every CFD roll date the cell's P&L must exclude the roll gap (roll-calendar fixture)"),
    "time_zone": (
        re.compile(r"TimeZone|Timezone|DaylightSaving|Dst|ExchangeTime", re.I),
        "bar timestamps in exchange vs UTC vs algorithm time disagree around DST",
        "MT5 server time is NY+7 (EET-ish) while research runs in UTC (#134)",
        "a session filter evaluated at 2 DST boundaries must select the same wall-clock bars"),
    "corporate_action": (
        re.compile(r"Split|Dividend|SymbolChanged|Delist|Merger|Spinoff|Rename", re.I),
        "price adjustments and ticker changes silently alter history",
        "share CFDs pay/charge dividend adjustments and delist; symbol map changes",
        "a cell on a share CFD must reproduce identical signals across a split-adjusted vintage"),
    "data_normalization": (
        re.compile(r"Normali[sz]|Adjusted|Raw(Price|Data)|ScaledRaw|BackwardsRatio", re.I),
        "raw vs adjusted prices change indicator values and fills",
        "broker history vs Dukascopy mid differ by spread and adjustment",
        "a family evaluated on bid vs mid bars must declare which, and its test pins it"),
    "warmup": (
        re.compile(r"WarmUp|Warmup|WarmingUp", re.I),
        "indicators emit before they have enough history",
        "cells that trade before `norm`/`atr_n` bars exist",
        "no signal may be emitted inside the first max(window) bars (warm-up fence test)"),
    "fill_model": (
        re.compile(r"Fill|Slippage|Latency|StalePrice|QuoteBar|Spread", re.I),
        "fills at prices the market never offered, or ignoring spread",
        "Fusion fills vs gauntlet cost model (zero-spread cost basis, #pass2)",
        "a gauntlet cost stress where every fill pays the recorded live spread percentile"),
    "margin_leverage": (
        re.compile(r"Margin|BuyingPower|Leverage|MarginCall|PatternDayTrading", re.I),
        "orders rejected or liquidated by margin rules the backtest ignored",
        "E8/prop daily-loss and broker margin-level stop-out",
        "sizing must be re-checked against broker margin at the stated leverage before donate"),
    "market_hours": (
        re.compile(r"MarketHours|ExtendedMarket|Holiday|EarlyClose|MarketOnOpen|MarketOnClose|"
                   r"Closed|AfterMarket|PreMarket", re.I),
        "orders at times the venue is closed or thin",
        "CFD session breaks (daily 1h break on indices/metals), holidays, Friday close",
        "no entry scheduled inside a symbol's session break or the last N minutes before close"),
    "option_expiry": (
        re.compile(r"Exercise|Expir|Assignment|Option", re.I),
        "expiry/assignment mechanics produce unmodelled P&L",
        "none for spot FX; relevant only to options-derived conditioners",
        "conditioner series built from options data must carry expiry-day masks"),
    "fill_forward": (
        re.compile(r"FillForward|Stale|MissingData|DataGap|Sparse", re.I),
        "stale bars re-used as if fresh",
        "weekend/holiday gaps in MT5 history; tick-volume zero bars",
        "a family fed a bar series with an injected 3-bar gap must not trade on the stale bars"),
    "order_semantics": (
        re.compile(r"Order(Ticket|Event|Update|Cancel)|StopLimit|Trailing|Combo|OCO|Bracket", re.I),
        "order lifecycle edge cases (partial, cancel/replace, stop triggers)",
        "MT5 order door (one door for money), pending order expiry, requotes",
        "order-door chaos test: every lifecycle transition has a ledger row"),
    "settlement_cash": (
        re.compile(r"Settlement|Cash|Currency|Conversion|AccountCurrency", re.I),
        "P&L in a currency the account does not hold, or unsettled cash reused",
        "EUR (Fusion) vs USD (E8) account currency; cross-rate conversion of P&L",
        "cell P&L must be converted at the bar's own cross rate, never a constant"),
    "universe_edge": (
        re.compile(r"Universe|Selection|Constituent|Coarse|Fine", re.I),
        "universe membership changes introduce survivorship or lookahead",
        "universe_policy admitting symbols after the fact",
        "a universe snapshot is PIT: membership at t reads only data available at t"),
    "history_consolidation": (
        re.compile(r"History|Consolidat|Resolution|Aggregat|Renko|RangeBar", re.I),
        "bar construction differs between history and live consolidation",
        "H1 bars from broker vs research resample; partial last bar",
        "live-consolidated bars and history bars must hash equal on a replay day"),
}


def regression_lessons(path: str, body: str = "") -> list[dict[str, str]]:
    """Each failure mode a regression/unit test covers, as the lesson this desk takes from it."""
    name = path.rsplit("/", 1)[-1]
    text = f"{name}\n{body[:4000]}"
    out = []
    for tag, (rx, mech, mt5, test) in FAILURE_MODES.items():
        if rx.search(name) or (body and len(rx.findall(text)) >= 3):
            out.append({"failure_mode": tag, "market_mechanism": mech, "mt5_analogue": mt5,
                        "test_to_add": test, "evidence_path": path})
    return out


# ---------------------------------------------------------------------------- issues / PRs
ISSUE_CATEGORIES: dict[str, re.Pattern[str]] = {
    "data_error": re.compile(r"\bdata (error|issue|missing|wrong|bad)|missing (bars|data)|"
                             r"incorrect (price|data)|bad tick|data gap", re.I),
    "backtest_live_divergence": re.compile(r"live (vs|versus|and) backtest|backtest (vs|versus) "
                                           r"live|differs? (in|from) live|paper trading", re.I),
    "fill_slippage": re.compile(r"\bfill|slippage|spread|partial fill|fee model", re.I),
    "broker_specific": re.compile(r"\b(interactive brokers|ib|oanda|fxcm|tradier|alpaca|"
                                  r"brokerage|tradestation|bybit|binance|kraken|coinbase)\b", re.I),
    "lookahead_timestamp": re.compile(r"look.?ahead|timestamp|time ?zone|end ?time|"
                                      r"future data|off by one", re.I),
    "corporate_action": re.compile(r"split|dividend|delist|symbol change|mapping|merger", re.I),
    "performance_scaling": re.compile(r"\bslow|performance|memory|timeout|out of memory|"
                                      r"speed up|leak", re.I),
    "strategy_implementation_error": re.compile(r"indicator (value|wrong|incorrect)|warm.?up|"
                                                r"wrong signal|insight", re.I),
    "portfolio_risk_behavior": re.compile(r"portfolio construction|risk management|margin|"
                                          r"buying power|leverage|liquidat", re.I),
    "api_change": re.compile(r"\bapi\b|deprecat|breaking change|pep8|rename|snake.?case", re.I),
}


def classify_issue(title: str, body: str = "") -> list[str]:
    text = f"{title}\n{body[:6000]}"
    hits = [c for c, rx in ISSUE_CATEGORIES.items() if rx.search(text)]
    return hits or ["uncategorised"]


def lean_record_kind(meta: Mapping[str, Any]) -> str:
    """'file' for a repo file record, 'commit' / 'issue' otherwise (from the fetcher's meta)."""
    return str(meta.get("item_kind") or "file")
