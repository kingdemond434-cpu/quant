#!/usr/bin/env python3
"""LLM DISCRETIONARY SLEEVE (R0122) -- Claude as a human-style trader, 24/7, PAPER ONLY.

PRINCIPAL REQUEST (2026-07-31): *"a strategy where Claude acts like a human trader with a brain
and trades 24/7 at charts."*

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT. It is NOT an LLM staring at chart images calling
breakouts, and refusing that is not timidity -- it is the two measured facts. (1) Language models
reason poorly over precise numeric OHLC: the desk's own numeric pipelines already dominate on
anything expressible as arithmetic, so a model eyeballing candles is a worse version of a tool
that exists. (2) "It looked like a breakout" is a PATTERN WITH NO MECHANISM, which is precisely
the class the 420-tested/0-survived record refuted -- carding it would be breadth-mining with a
narrator attached (L1.16, L1.25).

WHERE AN LLM GENUINELY HAS AN EDGE, and this sleeve lives exactly there: UNSTRUCTURED
INFORMATION THAT NUMERIC MODELS CANNOT PARSE AT ALL. Exchange announcements, listing/delisting
notices, contract-spec changes, chain incidents, regulatory statements, unusual forum activity --
text a human trader reads and reacts to, arriving 24/7 while a human sleeps. The mechanism is
stated and falsifiable: *an event whose implication requires reading prose is priced more slowly
than one expressible as a number, and the desk can read it continuously.* That is a FORCED-
PARTICIPANT-adjacent claim (someone must reposition when a contract spec changes) and it is
testable.

THE HONEST HARNESS, which is what makes this worth running at all:
  * EVERY call is a PRE-REGISTERED FORECAST -- direction, horizon, and an explicit PROBABILITY --
    logged to libs.self_improvement.forecast_calibration. It is therefore SCORED automatically
    (Brier, bias, hit-rate) by the L1.29 calibration fence, and its measured over-confidence is
    fed back as a shrinkage. An LLM trader that cannot be scored is a story generator; this one
    grades itself whether it likes the answer or not.
  * EVERY call states a MECHANISM and a FALSIFIER, or it is refused at write time. No mechanism,
    no trade -- the same bar every axis on this desk faces.
  * PAPER ONLY, permanently, until it earns promotion the same way as everything else: a
    pre-registered forward clock, a Holm slot, and Stage-B evidence (L1.6). This file places no
    orders and imports no connector -- a test asserts it.
  * Its benchmark is not zero. A discretionary sleeve must beat BUY-AND-HOLD and the desk's own
    carry sleeve after costs, or it is an expensive way to be average.

    python scripts/run_llm_trader.py --brief        # build the market brief only
    python scripts/run_llm_trader.py                # brief -> call -> log forecast -> paper mark
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BOOK = "data/llm_trader_book.jsonl"
_STATE = "data/llm_trader.json"
MIN_PROB, MAX_PROB = 0.50, 0.95      # a call below 50% is a call the other way; 95%+ is a tell
#: 3 concurrent calls. DERIVED from the same simulation that set the conviction sleeve's heat cap:
#: at equal total risk, 1 bet has P(-90% drawdown)=100% while 4 bets have 1% and 8 have 0%. This
#: sleeve carries no stop, so its per-call loss is unbounded in a way the conviction sleeve's is
#: not -- 3 is the point where it stays a portfolio rather than a punt, without pretending the
#: no-stop payoff is safe to spread thinly.
MAX_OPEN = 3

#: CONTROLLED MECHANISM TAXONOMY (external critique, 2026-07-31). Free-text mechanisms cannot be
#: AGGREGATED, so "which mechanism families actually produce alpha" is unanswerable and every
#: thesis looks equally novel. Forcing each call into one of these makes mechanism survival
#: measurable exactly like an axis: after N calls the desk can retire the families that never
#: pay and concentrate on the ones that do. NEW families are added deliberately, never invented
#: per-call -- an unbounded vocabulary is the same as no vocabulary.
MECHANISMS = (
    "FORCED_LIQUIDATION",      # leveraged positions must close at any price
    "COLLATERAL_CHANGE",       # margin/leverage/haircut rules force repositioning
    "LIQUIDITY_MIGRATION",     # venue/pool listing or delisting moves where trading happens
    "INVENTORY_ADJUSTMENT",    # market makers rebalance inventory
    "ARBITRAGE_DISLOCATION",   # a link between venues/instruments breaks
    "SUPPLY_SHOCK",            # unlocks, emissions, burns, treasury movement
    "REGULATORY_CONSTRAINT",   # access/eligibility restricted or expanded
    "INFRASTRUCTURE_FAILURE",  # exploit, bridge/validator/RPC outage
    "GOVERNANCE_CHANGE",       # tokenomics, fees, emissions decided
)

#: WHO IS FORCED TO TRANSACT -- the external critique's sharpest structural suggestion. "LONG
#: because bullish" is untestable; "market makers must reduce inventory" names a participant
#: whose behaviour can be checked against OI, depth and flow. Forced flows persist; discretionary
#: ones do not, and this field is what lets the desk tell them apart afterwards.
PARTICIPANTS = ("LEVERAGED_LONGS", "LEVERAGED_SHORTS", "MARKET_MAKERS", "ARBITRAGEURS",
                "VALIDATORS_MINERS", "TREASURY_ISSUER", "ETF_AUTHORIZED_PARTICIPANTS",
                "LENDING_PROTOCOL_USERS", "NOBODY_FORCED")

_CALL_BRIEF = """You are the desk's DISCRETIONARY TRADER. You trade like a thoughtful human: you
read what happened, you form a view with a REASON, you state how confident you are, and you say
what would prove you wrong. You are PAPER-TRADING -- no capital moves on your word, and your only
route to real size is the same forward-evidence gate every other strategy faces.

YOUR EDGE IS NOT CHARTS. The desk's numeric pipelines beat you at anything arithmetic: momentum,
carry, z-scores, cross-sectional ranks. Do not compete there -- you will lose and you will waste
the slot. YOUR EDGE IS PROSE: exchange announcements, contract-spec changes, listing/delisting
notices, chain incidents, regulatory statements, unusual community activity -- information whose
IMPLICATION requires reading, arriving at 3am while humans sleep. Trade the implication of an
EVENT, not the shape of a line.

TODAY'S BRIEF:
{brief}

OUTPUT EXACTLY ONE JSON OBJECT, no prose around it:
{{"action": "CALL" | "PASS",
  "symbol": "BTCUSDT",
  "direction": "LONG" | "SHORT",
  "horizon_hours": 8,
  "probability": 0.62,            // YOUR honest P(this call is right). It WILL be scored.
  "mechanism": "who is forced to do what, and why that moves price",
  "falsifier": "the observation that would prove this wrong",
  "reasoning": "2-4 sentences"}}

PASS IS A FIRST-CLASS ANSWER and most windows deserve it: if nothing happened that requires
reading prose to understand, there is no edge here and a call would be noise. A desk that trades
every window is a desk with no filter. REFUSED AT WRITE TIME: any call without a real mechanism
(not a pattern), without a falsifier, or with a probability outside {lo}-{hi}.

BUT A PASS IS ALSO SCORED, and you must justify it. A model that passes on everything gets a
beautiful calibration score and contributes nothing -- so a PASS carries
`passed_on` (the most material event you declined) and `pass_reason` (already priced / no
mechanism / not tradeable / unclear direction). Those declines are marked against the same
horizon as a real call, so the desk can measure whether your filter ADDS value or merely avoids
deciding. Passing is allowed; passing without saying what you passed on is not.

FIELDS REQUIRED ON EVERY CALL, in addition to the above:
  "mechanism_class": one of {mechs}
  "forced_participant": one of {parts} -- who MUST transact, not who might want to
  "compressible": true if a simple IF-THEN rule on the event text would produce this same call.
    ANSWER HONESTLY: if most of your calls are compressible, the desk should replace you with
    ten lines of code, and finding that out is a win, not a loss."""


def build_brief(root: Path) -> dict[str, Any]:
    """Market state + the unstructured feeds this sleeve actually trades on."""
    brief: dict[str, Any] = {"generated": datetime.now(tz=UTC).isoformat(), "sources": {}}
    for label, rel, n in (("funding", "data/bitmex_funding.jsonl", 5),
                          ("defi_lending", "data/defi_lending.jsonl", 2),
                          ("liquidations", "data/liquidations.jsonl", 8),
                          ("announcements", "data/exchange_announcements.jsonl", 10),
                          ("news", "data/news_feed.jsonl", 10)):
        try:
            lines = (root / rel).read_text("utf-8", errors="ignore").splitlines()
            if label == "announcements":
                # ONLY TRADEABLE ITEMS reach the trader (R0122b): fresh enough to still be
                # unpriced AND material enough to force repositioning. Handing it the archive
                # is how a sleeve "trades" a three-year-old exploit.
                import json as _j
                rows = []
                for ln in reversed(lines):
                    try:
                        r = _j.loads(ln)
                    except ValueError:
                        continue
                    if r.get("tradeable"):
                        rows.append({k: r[k] for k in
                                     ("source", "title", "symbols", "latency_minutes", "tier")
                                     if k in r})
                    if len(rows) >= n:
                        break
                brief["sources"][label] = rows or "no TRADEABLE events this window"
                continue
            brief["sources"][label] = [ln[:400] for ln in lines[-n:] if ln.strip()]
        except OSError:
            # ABSENT, never silently empty: a brief that hides its missing feeds invites a call
            # made on nothing (L1.28a).
            brief["sources"][label] = "ABSENT on this host"
    return brief


#: BLINDING EXPERIMENT (R0124 item b, 2026-08-05) -- "hide asset/exchange names behind
#: placeholders: if performance collapses it was brand recognition, not reasoning. Cheapest
#: decisive test of whether the edge is real."
#:
#: WHY IT IS NOT BLOCKED, since the ledger recorded that it was. R0124 was disposed SCHEDULED on
#: the grounds that this item is "OpenRouter-blocked (-0.59 USD, no seats can respond)". That
#: balance blocks the EXTERNAL PANEL. This sleeve never touches OpenRouter -- _ask_claude below
#: shells out to the Claude CLI through ops/brain_env.sh. Two different backends were conflated.
#:
#: THE DESIGN IS FROZEN HERE, BEFORE THE DATA, and it deliberately mirrors the excitation design
#: of L1.45: the arm is assigned by a pre-registered deterministic rule over a knob the desk
#: already owns, it varies HOW the sleeve is asked and never HOW MUCH it may risk, and there is no
#: vocabulary for size anywhere in it. Arm = BLIND on odd 4-hour windows, CLEAR on even ones, keyed
#: off the UTC window index so the assignment is reproducible from the row's own timestamp and
#: cannot be chosen after seeing the brief. ~50/50 by construction on the 4-hourly cadence.
#:
#: WHAT IT CAN MEASURE TODAY, WITH ZERO CALLS ON THE BOOK. The sleeve is 9/9 PASS, so the
#: performance comparison the critique wants genuinely has nothing to compare yet -- but the
#: PASS RATE ITSELF is an observable that needs no call: if the model passes at a different rate
#: when it cannot see WHICH asset an event names, that is brand recognition operating on the
#: filter, and it is visible from the first pair of windows. Recording the arm from the start is
#: what makes the eventual comparison possible at all; an arm cannot be assigned retroactively.
_BLIND_TOKEN = "ASSET_{}"    # noqa: S105 -- a placeholder format string, not a credential
_VENUE_TOKEN = "VENUE_{}"    # noqa: S105 -- ditto ("TOKEN" is the crypto sense, not the auth one)
#: Venue names the feeds actually carry (collect_announcements's sources + the desk's venues).
#: Held separately from tickers because a venue leak and an asset leak are different confounds.
_VENUES = ("binance", "okx", "bybit", "coinbase", "kraken", "upbit", "bithumb", "bitmex",
           "kucoin", "gate.io", "huobi", "mexc", "deribit", "bitflyer", "gmo", "hyperliquid",
           "coindesk", "cointelegraph", "defillama", "bitfinex", "gemini", "crypto.com")

#: PROSE NAMES -> ticker. THE FIRST DRAFT OF THIS BLINDER LEAKED, and the leak is worth recording
#: because it is the failure mode that makes a blinding experiment produce a confidently WRONG
#: answer rather than no answer. Masking `_KNOWN` tickers alone left "Bitcoin ETFs log inflows",
#: "Bitcoin's memory pool" and "XBTUSD" fully legible in the first real brief -- the model would
#: have read the brand in plain English, scored the same in both arms, and the experiment would
#: have reported "blinding changes nothing, so the edge is real reasoning". A leaky blind is worse
#: than no blind: it manufactures evidence for the conclusion the desk would prefer.
#: Aliases resolve to the SAME placeholder as their ticker, or "Bitcoin" and "BTC" would appear as
#: two unrelated assets and the brief would be incoherent rather than merely anonymous.
_ALIASES: dict[str, str] = {
    "bitcoin": "BTC", "xbt": "BTC", "ethereum": "ETH", "ether": "ETH", "solana": "SOL",
    "ripple": "XRP", "dogecoin": "DOGE", "cardano": "ADA", "avalanche": "AVAX",
    "chainlink": "LINK", "polkadot": "DOT", "litecoin": "LTC", "polygon": "POL",
    "tether": "USDT", "binance coin": "BNB", "tron": "TRX", "uniswap": "UNI",
    "cosmos": "ATOM", "stellar": "XLM", "filecoin": "FIL", "aptos": "APT", "arbitrum": "ARB",
    "optimism": "OP", "near protocol": "NEAR", "hedera": "HBAR", "algorand": "ALGO",
    "shiba inu": "SHIB", "bitcoin cash": "BCH", "ethereum classic": "ETC", "toncoin": "TON",
}
#: Quote/suffix forms that glue a ticker to another token and defeat a bare \b match: XBTUSD,
#: BTCUSDT, ETH-PERP. Matched as part of the ticker pattern and re-emitted after the placeholder
#: so the brief still reads as an instrument rather than a bare noun.
_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "PERP", "-PERP", "-USD", "/USD", "/USDT")


def _blind_brief(brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Replace every asset and venue name with a stable placeholder. Returns (brief, unmask).

    Stable WITHIN a window and meaningless ACROSS windows: ASSET_1 is whichever asset appeared
    first in this brief and carries no identity the model could learn. The map is returned rather
    than stored globally so the caller can turn a blinded answer back into a real symbol -- the
    experiment hides the name from the REASONING, it does not hide it from the book.

    Ticker matching reuses the collector's `_KNOWN` whitelist rather than a fresh regex. That set
    exists because a naive uppercase-word pattern extracted ACROSS, BANKS and LED as tickers, and
    a blinder with that bug would mask ordinary English into gibberish -- which is the same defect
    as leaking, pointed the other way.
    """
    from scripts.collect_announcements import _KNOWN

    text = json.dumps(brief)
    suffix = "|".join(re.escape(s) for s in sorted(_QUOTE_SUFFIXES, key=len, reverse=True))
    # ticker -> every string that names it, longest first so a longer alias is consumed before a
    # shorter one it contains ("bitcoin cash" before "bitcoin", "ethereum classic" before "ether")
    by_ticker: dict[str, list[str]] = {}
    for alias, ticker in _ALIASES.items():
        by_ticker.setdefault(ticker, []).append(alias)
    for tok in _KNOWN:
        # `_KNOWN` carries XBT as a ticker in its own right while _ALIASES maps xbt -> BTC. Adding
        # it again as its own key would hand XBTUSD and BTCUSDT DIFFERENT placeholders, so the
        # blinded brief would describe one asset as two -- anonymised into incoherence, which
        # degrades the CLEAR-vs-BLIND comparison for a reason that has nothing to do with brand.
        if _ALIASES.get(tok.lower(), tok) == tok:
            by_ticker.setdefault(tok, []).append(tok)

    def _pattern(alias: str) -> str:
        esc = re.escape(alias)
        # A single-token name may be glued to a quote currency (XBTUSD, BTCUSDT); a multi-word
        # prose name never is. This keyed on `alias.isupper()` until a test caught it: aliases are
        # stored LOWERCASE, so `xbt` fell to the no-suffix branch and XBTUSD stayed legible while
        # BTCUSDT was masked -- the same leak the alias table was added to close, one layer in.
        return rf"\b{esc}({suffix})?\b" if " " not in alias else rf"\b{esc}\b"

    # order tickers by their longest alias so multi-word names are masked before their heads
    order = sorted(by_ticker, key=lambda t: -max(len(a) for a in by_ticker[t]))
    unmask: dict[str, str] = {}
    n = 0
    for ticker in order:
        aliases = sorted(by_ticker[ticker], key=len, reverse=True)
        if not any(re.search(_pattern(a), text, flags=re.IGNORECASE) for a in aliases):
            continue
        n += 1
        ph = _BLIND_TOKEN.format(n)
        for alias in aliases:
            # keep the quote suffix so ASSET_1USDT still reads as an instrument, not a bare noun.
            # `ph` is bound as a default argument rather than captured: the closure outlives this
            # loop iteration inside re.sub, and a late-bound ph would stamp every alias with the
            # LAST placeholder assigned.
            text = re.sub(_pattern(alias),
                          lambda m, _ph=ph: _ph + ((m.group(1) or "") if m.groups() else ""),
                          text, flags=re.IGNORECASE)
        unmask[ph] = ticker
    for i, venue in enumerate(sorted(_VENUES, key=len, reverse=True), 1):
        ph = _VENUE_TOKEN.format(i)
        new = re.sub(rf"\b{re.escape(venue)}\b", ph, text, flags=re.IGNORECASE)
        if new != text:
            unmask[ph] = venue
            text = new
    return json.loads(text), unmask


def blind_audit(blinded: dict[str, Any], unmask: dict[str, str] | None = None) -> dict[str, Any]:
    """Grade the blind itself. Runs at CALL time, not only in tests.

    A blind that leaks does not fail loudly -- it quietly answers the research question wrong, in
    the direction the desk would prefer ("blinding changed nothing, so the edge is real"). So the
    experiment carries its own falsifier and the verdict rides on the row.

    TWO CLASSES, kept apart because only one is fixable by widening a list:
      `leaks`    a name still legible as a WHOLE WORD. This is a defect; it must be empty.
      `residual` a masked ticker surviving INSIDE a longer token -- CBBTC (Coinbase Wrapped BTC)
                 is the measured real case. Not whole-word, so no vocabulary addition removes it,
                 and a reader fluent in wrapped-token tickers can still infer the asset. Recorded
                 rather than suppressed: an experiment that hides its own imperfect treatment is
                 the thing this whole item exists to test for.
    """
    from scripts.collect_announcements import _KNOWN

    text = json.dumps(blinded)
    names = {*_ALIASES, *_VENUES, *(t.lower() for t in _KNOWN)}
    leaks = sorted(nm for nm in names
                   if re.search(rf"\b{re.escape(nm)}\b", text, re.IGNORECASE))
    residual = sorted({tok for tok in (unmask or {}).values()
                       if re.search(re.escape(tok), text, re.IGNORECASE)})
    return {"leaks": leaks, "residual": residual, "clean": not leaks}


def _unmask_symbol(symbol: str, unmask: dict[str, str]) -> str:
    """Turn a blinded answer back into a real ticker. A placeholder the map does not know is
    returned UNCHANGED so validate_call refuses it -- inventing a symbol to rescue a malformed
    answer is how a paper sleeve books a trade on an asset nobody named."""
    base = unmask.get(symbol.upper())
    if base:
        return f"{base}USDT" if not base.endswith(("USDT", "USD")) else base
    for ph, tok in unmask.items():
        if symbol.upper().startswith(ph):
            return f"{tok}USDT"
    return symbol


def blind_arm(now: datetime) -> str:
    """Pre-registered arm assignment: deterministic in the UTC 4-hour window index.

    Not random at call time on purpose. A seed drawn when the brief is already in hand is a knob
    someone can turn after seeing the data; an index derived from the clock is reproducible by any
    later reader from the row's own timestamp, which is what makes the two arms comparable.
    """
    return "BLIND" if (now.timetuple().tm_yday * 6 + now.hour // 4) % 2 else "CLEAR"


def validate_call(call: dict[str, Any]) -> tuple[bool, str]:
    """The write-time bar. A call that cannot state WHY is not a call (L1.16)."""
    if call.get("action") == "PASS":
        # A PASS IS A DECISION AND IS SCORED. Without this the model optimises toward passing:
        # perfect calibration, zero economic value (external critique, 2026-07-31).
        if not call.get("pass_reason"):
            return False, ("REFUSED: a PASS must say WHY -- an unjustified pass is how a model "
                           "farms a clean Brier score while contributing nothing")
        return True, f"PASS recorded and scored: {str(call.get('pass_reason'))[:80]}"
    for field in ("symbol", "direction", "horizon_hours", "probability", "mechanism",
                  "falsifier", "mechanism_class", "forced_participant"):
        if not call.get(field):
            return False, f"REFUSED: missing {field}"
    if call["direction"] not in ("LONG", "SHORT"):
        return False, "REFUSED: direction must be LONG or SHORT"
    try:
        p = float(call["probability"])
    except (TypeError, ValueError):
        return False, "REFUSED: probability not numeric"
    if not MIN_PROB <= p <= MAX_PROB:
        return False, (f"REFUSED: probability {p} outside {MIN_PROB}-{MAX_PROB} -- below 50% is "
                       "a call the other way, above 95% is a tell that the model is not scoring "
                       "itself honestly")
    mech = str(call["mechanism"])
    if len(mech) < 25:
        return False, "REFUSED: mechanism too thin to be a mechanism"
    # A PATTERN is not a MECHANISM -- this is the 420/0 lesson enforced at write time.
    pattern_words = ("breakout", "support", "resistance", "trend line", "trendline",
                     "head and shoulders", "golden cross", "oversold", "overbought")
    if any(w in mech.lower() for w in pattern_words) and "because" not in mech.lower():
        return False, ("REFUSED: mechanism reads as a chart PATTERN, not a mechanism -- name who "
                       "is forced to do what and why (L1.16). Patterns are the class the desk's "
                       "420-tested/0-survived record already refuted")
    if len(str(call["falsifier"])) < 15:
        return False, "REFUSED: no real falsifier"
    if call["mechanism_class"] not in MECHANISMS:
        return False, (f"REFUSED: mechanism_class must be one of {MECHANISMS} -- free-text "
                       "mechanisms cannot be aggregated, so mechanism survival becomes "
                       "unmeasurable and weak families never get retired")
    if call["forced_participant"] not in PARTICIPANTS:
        return False, f"REFUSED: forced_participant must be one of {PARTICIPANTS}"
    if call["forced_participant"] == "NOBODY_FORCED":
        return False, ("REFUSED: no forced participant means no forced flow -- that is a VIEW, "
                       "not a mechanism, and views are what the 420/0 record already refuted")
    return True, "accepted"


def record_call(root: Path, call: dict[str, Any]) -> dict[str, Any]:
    """Append to the paper book AND log the forecast so L1.29 scores it automatically.

    A PASS IS LOGGED TOO, which is the whole of R0123's remaining scope. The brief promises the
    model that "a PASS is also scored ... marked against the same horizon as a real call", and
    until now the code kept that promise only for CALLs -- so the sleeve wrote nine consecutive
    PASSes and logged zero scoreable forecasts. A filter nobody grades is a filter that maximises
    its record by never deciding.

    A decline is logged under its OWN kind, never `discretionary`. forecast_calibration.report()
    excludes those kinds by default, so the bias that shrinks live Kelly sizing keeps meaning what
    it meant; the declines are scored in libs.research.decline_value, where the question is whether
    the FILTER adds value. Mixing the two pools would move position size on trades never taken.

    A decline the model left ungradeable -- no symbol, or no LONG/SHORT -- is stamped as such on
    the row and NOT logged. Logging one would create a forecast nothing can ever resolve, and an
    unresolved forecast past its deadline is a hard FAILURE of check_calibration (exit 2): the fix
    for an ungradeable decline is a better decline, never a fence that stops looking.
    """
    now = datetime.now(tz=UTC)
    row = {**call, "at": now.isoformat(),
           "resolve_by": (now + timedelta(hours=float(call.get("horizon_hours", 8)))).isoformat(),
           "paper": True}
    is_pass = call.get("action") == "PASS"
    key = f"llm_trader:{now.isoformat()}"
    try:
        from libs.research.decline_value import scoreable
        ok, why = scoreable(row) if is_pass else (True, "call")
    except Exception as exc:                                # never lose the row to a grader import
        ok, why = False, f"scoreability check failed: {exc}"
    if is_pass:
        row["decline_scoreable"], row["decline_scoreable_why"] = ok, why
    if ok:
        row["forecast_key"] = key

    # THE BOOK IS WRITTEN FIRST, AND THE ORDER IS THE RECOVERY STORY. If the forecast log fails
    # after the row lands, resolve_llm_trader_book.py re-registers it from the row itself and
    # nothing is lost. The reverse order loses the opposite way and it is the expensive one: a
    # forecast whose book row never landed can never be graded, and an ungradeable forecast past
    # its deadline fails check_calibration permanently.
    p = root / _BOOK
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")

    if ok:
        try:
            from libs.self_improvement import forecast_calibration as fc
            if is_pass:
                fc.log_forecast(
                    key, float(row["probability"]), "discretionary_pass",
                    resolve_by=row["resolve_by"],
                    claim=(f"DECLINED {row['direction']} {row['symbol']} over "
                           f"{row.get('horizon_hours', 8)}h "
                           f"({str(row.get('pass_reason'))[:40]}) @ {now.isoformat()}"))
            else:
                fc.log_forecast(key, float(call["probability"]), "discretionary",
                                resolve_by=row["resolve_by"],
                                claim=f"{call['direction']} {call['symbol']}: "
                                      f"{call['mechanism'][:120]}")
        except Exception as exc:                            # never lose the call
            row["calibration_log_error"] = str(exc)
    return row


#: Set by _ask_claude to whatever the shell actually reported. Read when the call yields no
#: parseable JSON, so the recorded status names the REAL cause instead of guessing at three.
_LAST_CALL_FAILURE = ""


def _ask_claude(prompt: str, timeout: int = 600) -> str:
    """Ask the brain, and KEEP the evidence when it refuses.

    THE BUG THIS FIXES: this returned `r.stdout or ""` and dropped stderr and the return code on
    the floor, so a failed call was indistinguishable from a model that simply answered nothing.
    The caller then recorded the hardcoded string "(auth, quota, or a refusal)" -- a three-way
    guess that was never once checked against the actual error. It also made data/cro_ai_logs/
    llm_trader.log match the stub-death fence's bare "auth" marker, so a pure QUOTA outage was
    reported to the desk as an auth failure and would have sent anyone debugging it at the
    credentials rather than the credit balance. A flag computed and dropped is evidence destroyed
    at zero saving.
    """
    global _LAST_CALL_FAILURE
    _LAST_CALL_FAILURE = ""
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || exit 90 && '
         'claude --effort xhigh --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip().replace("\n", " ")[:300]
        # 90 is brain_auth_check's own exit code -- the ONE case where "auth" is established
        # rather than assumed. Everything else reports the code and the venue's own words.
        _LAST_CALL_FAILURE = (
            f"brain_auth_check refused before the model was reached (exit 90): {err}"
            if r.returncode == 90 else f"claude exited {r.returncode}: {err}")
    return r.stdout or ""


def parse_call(raw: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", action="store_true", help="build the brief and stop")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--arm", choices=("BLIND", "CLEAR"), default=None,
                    help="override the pre-registered arm (testing/inspection only; "
                         "the scheduled run must let blind_arm() assign it)")
    args = ap.parse_args()
    brief = build_brief(_ROOT)
    now = datetime.now(tz=UTC)
    arm = args.arm or blind_arm(now)
    unmask: dict[str, str] = {}
    audit: dict[str, Any] = {}
    if arm == "BLIND":
        brief, unmask = _blind_brief(brief)
        audit = blind_audit(brief, unmask)
    if args.brief:
        print(json.dumps({"arm": arm, "brief": brief, "unmask": unmask, "blind_audit": audit}
                         if arm == "BLIND" else brief, indent=2))
        return 0

    raw = _ask_claude(_CALL_BRIEF.format(brief=json.dumps(brief, indent=1)[:6000],
                                         lo=MIN_PROB, hi=MAX_PROB,
                                         mechs=" | ".join(MECHANISMS),
                                         parts=" | ".join(PARTICIPANTS)))
    call = parse_call(raw)
    if call is not None:
        # The arm rides on the row so the eventual comparison is possible; it CANNOT be assigned
        # retroactively, which is why it is recorded from the first window rather than from the
        # first call. Unmasking happens BEFORE validate_call, so a blinded answer faces exactly
        # the same write-time bar as a clear one -- the experiment must not change the gate.
        call["blind_arm"] = arm
        if arm == "BLIND":
            # the blind's own grade rides on the row: a window whose treatment leaked must be
            # excludable from the comparison later, and that is only possible if it was recorded
            # at the time. `clean` is the field the analysis filters on.
            call["blind_audit"] = audit
            if call.get("symbol"):
                call["symbol_as_answered"] = call["symbol"]
                call["symbol"] = _unmask_symbol(str(call["symbol"]), unmask)
    if call is None:
        why = (f"call FAILED -- {_LAST_CALL_FAILURE}" if _LAST_CALL_FAILURE else
               "model ran but returned no parseable JSON (a refusal or a malformed answer)")
        state = {"status": "NO-CALL", "why": f"{why} -- recorded, never treated as a PASS",
                 "at": datetime.now(tz=UTC).isoformat()}
    else:
        ok, why = validate_call(call)
        if not ok:
            state = {"status": "REFUSED", "why": why, "call": call,
                     "at": datetime.now(tz=UTC).isoformat()}
        else:
            row = record_call(_ROOT, call)
            state = {"status": call.get("action", "CALL"), "why": why, "call": row,
                     "at": row["at"]}
    (_ROOT / _STATE).write_text(json.dumps(state, indent=2), "utf-8")
    print(json.dumps(state, indent=2) if args.json else
          f"llm trader (R0122): {state['status']} -- {state['why']}")
    return 0                          # a refused call is a working filter, never a build failure


if __name__ == "__main__":
    sys.exit(main())
