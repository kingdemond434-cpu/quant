# ruff: noqa: RUF001, E501  -- native-language lens briefs (CJK, Arabic, Thai ...) by design
"""THE SWARM LAYER OF THE CHINESE-MODEL ENSEMBLE: lenses, runnable recipes, critic, mutation,
and the per-model / per-lens scoreboard that steers it (principal, 2026-11-17: "swarms ... find
edges from everywhere using all sources individually, then amalgamate them into testable cells
and send them all to the gauntlet 24/7"; and "yes all" to the five extensions).

WHAT EACH PIECE IS FOR

* LENSES. One agent = one model looking through one lens: a named public source or region
  (PBOC fixing, SGE premium, BoJ operations, KRX flows, CFTC positioning, LBMA fix ...). Lenses
  for Chinese, Japanese and Korean official sources are WRITTEN IN THAT LANGUAGE, so the model
  reasons with what it learned from those documents in their own language rather than from
  English summaries of them. (Reading the live documents themselves is a fetch problem, and goes
  through `robots_gate` in its own organ; this layer sends no URL and fetches nothing.)

* RUNNABLE RECIPES. The prompt carries the desk's generic price-only family vocabulary (textbook
  rule templates such as `mean_reversion_rsi(rsi_n=14, oversold=30, ...)`: names and parameter
  defaults, never code, edges or results), so an idea comes back as `family + params + symbols`.
  `validate_recipe` admits it only when the family exists and every parameter is one that family
  takes, of the right type, inside a sane band around its default. Such a row compiles through the
  compiler's EXACT_RECIPE path straight into a cell; anything else is kept as prose and goes the
  slower deepening route, so nothing is lost.

* CRITIC. Judge-hours are the bottleneck, so a DIFFERENT model scores each recipe 0-10 for
  mechanism, cost survival and novelty before it is donated. Below the floor it is dropped (and
  counted); the rest carry `prior_score`. A critic that cannot be reached scores nothing and kills
  nothing: an unscored idea still reaches the judge.

* MUTATION. Cells the judge found real but under-powered (failing only the power gates) are the
  cheapest place to look next. A few calls an hour ask for variants of them. These calls carry the
  desk's own near-miss rules, so they go to OpenRouter only (the provider that already carries the
  desk's sanitised packets) and NEVER to a free-credit relay.

* SCOREBOARD AND STEERING. `data/cn_swarm_lineage.jsonl` records which model, provider, lens and
  task produced each recipe. `scoreboard` joins it to the hypothesis graph and the gate-verdict
  ledger and counts, per model and per lens, how many were judged, how many passed, how many were
  near misses. `weights` turns that into Thompson draws with an exploration floor, so the next
  hour leans toward what actually survives the judge without ever starving an arm.

AUTHORITY: NONE. Everything here proposes. Sizing, capital, promotion and live trading are not
reachable from this module.
"""
from __future__ import annotations

import inspect
import json
import random
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

LINEAGE = "data/cn_swarm_lineage.jsonl"
GRAPH = "desks/mt5/data/hypothesis_graph.jsonl"
GATE_LEDGER = "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"
DONOR_SOURCE = "miner:cn_ensemble"

#: Failures that mean UNDER-POWERED, not refuted (the judge's own set, external_gauntlet.py
#: POWER_ONLY_GATES; pinned equal by the test). A cell failing only these is a near miss.
POWER_ONLY_GATES = frozenset({"deflated_sharpe", "expected_value", "in_sample_screen"})

#: Exploration floor: no lens or model is weighted below this share of a uniform draw.
EXPLORE_FLOOR = 0.25

# ---------------------------------------------------------------------------------- lenses
#: (lens id, language, brief). Public briefs only: a source or a region, never the desk.
LENSES: tuple[tuple[str, str, str], ...] = (
    ("pboc_fixing_cnh", "zh", "人民银行中间价、逆周期因子、离岸人民币（CNH"
                              "）流动性与CFETS篮子：这些机制在亚洲时段对"
     "USDCNH、AUDUSD、XAUUSD以及亚洲股指CFD造成的可预测价格行为"),
    ("sge_shfe_gold_metals", "zh", "上海黄金交易所溢价、上期所黄金白银"
                                   "铜夜盘、进口配额与实物需求：它们如何"
     "领先或扰动伦敦与纽约的XAUUSD、XAGUSD和铜价"),
    ("china_retail_forums", "zh", "雪球、知乎、期货日报实盘大赛与私募访"
                                  "谈中反复出现的交易规律，以及散户情绪"
     "在这些市场留下的可交易痕迹"),
    ("china_data_calendar", "zh", "国家统计局、海关总署、财新PMI与政"
                                  "治局会议等官方发布的时间规律，以及发布"
     "前后外汇、商品和股指CFD的系统性价格反应"),
    ("boj_mof_jgb", "ja", "日本銀行のオペ、国債入札、財務省の為替介入パターン、GPIFのリバランスが"
     "USDJPY・クロス円・JPN225に生む予測可能な値動き"),
    ("tse_japan_flows", "ja", "東証の投資主体別売買動向、五十日（ごとうび）の実需フロー、期末の"
     "レパトリエーションと配当再投資がもたらす為替・株価指数の季節性"),
    ("bok_krx_nps", "ko", "한국은행 정책, 국민연금 환헤지 비율 조정"
                          ", KRX 외국인 수급, 수출입 통계 발표가"
     "USDKRW 연동 통화와 아시아 지수 CFD에 남기는 예측 가능한 패턴"),
    ("cftc_positioning", "en", "public CFTC Commitments of Traders positioning in FX, metals and "
     "energy futures: extremes, changes and who is forced to unwind"),
    ("fixings_and_auctions", "en", "the WM/Reuters 4pm fix, LBMA gold and silver auctions, COMEX "
     "settlement and government bond auctions: the forced flows around each"),
    ("central_bank_ops", "en", "Fed, ECB, BoE, SNB, RBA, RBNZ and Norges Bank operations, "
     "statements and blackout periods, and the price behaviour around each"),
    ("energy_reports", "en", "EIA inventory reports, OPEC meetings, refinery seasonality and "
     "pipeline maintenance as drivers of crude and related currencies (CAD, NOK)"),
    ("index_rebalances_expiry", "en", "index rebalances, option expiries, quarter-end window "
     "dressing and pension rebalancing in equity indices and the currencies that fund them"),
    ("em_fx_carry", "en", "emerging-market central banks (Banxico, BCB, SARB, CBRT), carry "
     "unwinds and risk-off episodes in USDMXN, USDZAR, USDTRY and friends"),
    ("gulf_india_gold", "en", "Dubai and Mumbai physical gold demand, Indian import duty changes "
     "and festival seasons (Diwali, Akshaya Tritiya) as gold drivers"),
    # WORLDWIDE, OBSCURE FIRST (principal, 2026-11-17: "the swarm should do worldwide all unknown
    # sources"). Each brief is in the region's own language and asks for the LITTLE-KNOWN local
    # publishers -- regional central-bank bulletins, provincial statistics, local exchanges and
    # trader communities -- that English-language quants rarely read.
    ("latam_es", "es", "boletines poco conocidos de bancos centrales y oficinas de estadistica de "
     "Mexico, Chile, Colombia, Peru y Argentina, flujos de AFORE y AFP, subastas locales de bonos "
     "y foros de traders hispanohablantes: efectos predecibles en USDMXN, USDCLP, cobre y oro"),
    ("brazil_pt", "pt", "publicacoes pouco conhecidas do Banco Central do Brasil, Tesouro, B3, "
     "CONAB e IBGE, fluxos de exportadores e foros de traders brasileiros: padroes previsiveis "
     "em USDBRL, soja, cafe, acucar e no indice brasileiro"),
    ("mena_ar", "ar", "النشرات غير المعروفة للبنوك المركزية والهيئات الاحصائية في السعودية والامارات "
     "ومصر وتركيا، وتدفقات الذهب في دبي، وقرارات اوبك+ ومواسم رمضان والحج: انماط تداول قابلة "
     "للاختبار في الذهب والنفط والعملات"),
    ("russia_cis_ru", "ru", "малоизвестные публикации Банка России, Минфина, Мосбиржи, Росстата и "
     "центробанков Казахстана и Узбекистана, а также форумы русскоязычных трейдеров: проверяемые "
     "закономерности в золоте, нефти, металлах и валютах"),
    ("eastern_europe", "pl", "malo znane publikacje NBP, CNB, MNB i banku centralnego Rumunii, "
     "aukcje obligacji, przeplywy funduszy emerytalnych i fora inwestorow: przewidywalne wzorce w "
     "EURPLN, EURCZK, EURHUF i indeksach regionu"),
    ("turkey_tr", "tr", "TCMB, TUIK ve Borsa Istanbul'un az bilinen yayinlari, ihracatci doviz "
     "akislari, altin ithalati ve yerel yatirimci forumlari: USDTRY, altin ve endeksler icin "
     "test edilebilir oruntuler"),
    ("india_hi", "hi", "भारतीय रिज़र्व बैंक, MCX, SEBI और राज्य स्तरीय आंकड़ों के कम ज्ञात प्रकाशन, "
     "सोने का आयात, त्योहारों का मौसम और भारतीय ट्रेडर समुदाय: USDINR, सोना और सूचकांकों में "
     "परीक्षण योग्य पैटर्न"),
    ("indonesia_malaysia", "id", "publikasi yang kurang dikenal dari Bank Indonesia, BPS, Bank "
     "Negara Malaysia, Bursa Malaysia dan forum trader lokal, ekspor batu bara, CPO dan nikel: pola "
     "yang dapat diuji pada USDIDR, USDMYR, emas dan komoditas"),
    ("thailand_vietnam", "th", "สิ่งพิมพ์ที่ไม่ค่อยมีคนรู้จักของธนาคารแห่งประเทศไทย สมาคมค้าทองคำ "
     "ตลาดหลักทรัพย์ และธนาคารแห่งรัฐเวียดนาม รวมถึงชุมชนเทรดเดอร์ท้องถิ่น: รูปแบบที่ทดสอบได้ในทองคำ "
     "USDTHB และดัชนีในภูมิภาค"),
    ("africa_anglophone", "en", "little-known publications of the South African Reserve Bank, "
     "Central Bank of Nigeria, Central Bank of Kenya, Bank of Ghana, JSE and Zambian and Chilean "
     "copper-belt statistics, plus African trader communities: testable patterns in USDZAR, gold, "
     "platinum and copper"),
    ("africa_francophone", "fr", "publications peu connues de la BCEAO, de la BEAC, de Bank "
     "Al-Maghrib, de la BRVM et des offices statistiques d'Afrique francophone, et forums de "
     "traders: regularites testables sur l'or, le cacao, le cafe et l'EUR"),
    ("europe_regional", "de", "wenig beachtete Veroeffentlichungen von Landeszentralbanken, "
     "Bundesbank-Regionalumfragen, Ifo-Branchendaten, SNB- und OeNB-Statistiken sowie "
     "deutschsprachige Traderforen: testbare Muster in EUR, CHF, DAX und Metallen"),
    ("nordics_oceania", "en", "little-known Norges Bank, Riksbank, Danmarks Nationalbank, ABS, "
     "Stats NZ, RBA regional liaison and dairy-auction publications: testable patterns in NOK, "
     "SEK, AUD, NZD and their commodity drivers"),
    ("source_scout", "en", "PUBLIC SOURCES nobody in Western quant finance reads: name obscure "
     "official, exchange, industry or community publishers in any country and language whose "
     "releases could move FX, gold, metals, energy or index CFDs"),
    ("academic_literature", "en", "published papers and working papers (SSRN, arXiv q-fin, BIS, "
     "central-bank research) whose effect is still plausible in FX, metals, energy and indices"),
    ("microstructure_sessions", "en", "session opens and closes, liquidity gaps, spread changes "
     "and stop clustering in FX, gold and index CFDs, stated as rules"),
    ("regime_conditioning", "en", "volatility, trend, rates and risk-on/off regimes under which "
     "a simple price rule flips from losing to winning"),
    ("contrarian_retail", "en", "popular retail trading beliefs in these markets that are probably "
     "wrong, and the rule that profits from the crowd acting on them"),
)
LENS_BRIEF = {lid: brief for lid, _lang, brief in LENSES}  # science lenses join below

_LANG_ASK = {
    "zh": "请用你从中文原始资料中学到的知识来思考。JSON字段值可以用英文写。",
    "ja": "日本語の一次資料から学んだ知識で考えてください。JSONの値は英語で構いません。",
    "ko": "한국어 1차 자료에서 배운 지식으로 생각하세요. JSON 값은 영어로 써도 됩니다.",
    "en": "",
    "es": "Piensa con lo que aprendiste de las fuentes originales en espanol. Los valores JSON pueden ir en ingles.",
    "pt": "Pense com o que aprendeu das fontes originais em portugues. Os valores JSON podem ser em ingles.",
    "ar": "فكر بما تعلمته من المصادر الاصلية باللغة العربية. يمكن كتابة قيم JSON بالانجليزية.",
    "ru": "Опирайся на знания из первоисточников на русском языке. Значения JSON можно писать по-английски.",
    "pl": "Korzystaj z wiedzy ze zrodel w jezyku polskim i regionalnych. Wartosci JSON moga byc po angielsku.",
    "tr": "Turkce birincil kaynaklardan ogrendiklerinle dusun. JSON degerleri Ingilizce olabilir.",
    "hi": "हिंदी और भारतीय मूल स्रोतों से सीखे ज्ञान से सोचें। JSON मान अंग्रेज़ी में हो सकते हैं।",
    "id": "Berpikirlah dengan pengetahuan dari sumber asli berbahasa Indonesia dan Melayu. Nilai JSON boleh dalam bahasa Inggris.",
    "th": "คิดจากความรู้ที่ได้จากแหล่งข้อมูลต้นฉบับภาษาไทยและเวียดนาม ค่า JSON เขียนเป็นภาษาอังกฤษได้",
    "fr": "Raisonne avec ce que tu as appris des sources originales en francais. Les valeurs JSON peuvent etre en anglais.",
    "de": "Denke mit dem Wissen aus deutschsprachigen Originalquellen. JSON-Werte duerfen englisch sein.",
}


DISCOVERED_LENS = "discovered_sources"


def lens_prompt(lens: str, extra: Mapping[str, str] | None = None) -> str:
    lang = next((lg for lid, lg, _b in LENSES if lid == lens), "en")
    ask = _LANG_ASK.get(lang, "")
    brief = (extra or {}).get(lens) or LENS_BRIEF[lens]
    return f"RESEARCH LENS ({lens}): {brief}." + (f"\n{ask}" if ask else "")


# ----------------------------------------------------------------------- recipe catalogue
_SIMPLE = (int, float, str, bool)


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict[str, Any]]:
    """Price-only families -> {param: default}: every registered family whose only positional
    input is the bar frame and whose parameters all have simple defaults. Empty when the family
    registry cannot be imported (the swarm then donates prose, as before)."""
    import sys
    root = Path(__file__).resolve().parents[2]
    mt5 = str(root / "desks" / "mt5")
    if mt5 not in sys.path:
        sys.path.insert(0, mt5)
    try:
        from mt5desk import families, families_orthogonal
    except Exception:
        return {}
    fns: dict[str, Any] = {k[7:]: getattr(families, k) for k in dir(families)
                           if k.startswith("family_") and callable(getattr(families, k))}
    for k, fn in getattr(families_orthogonal, "ORTHOGONAL_FAMILIES", {}).items():
        if callable(fn):
            fns.setdefault(str(k), fn)
    out: dict[str, dict[str, Any]] = {}
    for name, fn in sorted(fns.items()):
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        ps = list(sig.parameters.values())
        positional = [p for p in ps if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(positional) != 1:
            continue                                    # needs a second input (cot, macro, fx)
        kw = [p for p in ps if p.kind == p.KEYWORD_ONLY]
        if not kw:
            continue
        if any(re.search(r"DataFrame|Series|ndarray", str(p.annotation)) for p in kw):
            continue                                    # an optional data input: not price-only
        params: dict[str, Any] = {}
        for p in kw:
            d = p.default
            if d is inspect.Parameter.empty:
                params = {}
                break
            if isinstance(d, tuple) and all(isinstance(x, int) for x in d):
                params[p.name] = list(d)
            elif d is None or isinstance(d, _SIMPLE):
                params[p.name] = d
        if params:
            out[name] = params
    return out


def catalog_text(cat: Mapping[str, Mapping[str, Any]], limit: int = 70) -> str:
    lines = []
    for name, ps in list(cat.items())[:limit]:
        args = ", ".join(f"{k}={json.dumps(v)}" for k, v in ps.items())
        lines.append(f"- {name}({args})")
    return "\n".join(lines)


def _coerce(value: Any, default: Any) -> Any:
    """The value in the default's type, inside a sane band, or a ValueError."""
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        raise ValueError("bool")
    if isinstance(default, int) and not isinstance(default, bool):
        v = round(float(value))
        if default > 0 and not (max(0, default // 10) <= v <= max(default * 10, default + 24)):
            raise ValueError("band")
        return v
    if isinstance(default, float):
        v = float(value)
        if v != v or abs(v) > 1e6:
            raise ValueError("nan")
        if default > 0 and not (default / 20 <= v <= default * 20):
            raise ValueError("band")
        return v
    if isinstance(default, str):
        s = str(value).strip()
        if not s or len(s) > 24 or not re.fullmatch(r"[A-Za-z0-9_.\-]+", s):
            raise ValueError("str")
        return s
    if isinstance(default, list):
        if not isinstance(value, list) or not value or len(value) > 8:
            raise ValueError("list")
        return [int(x) for x in value]
    if default is None:
        if value is None:
            return None
        return round(float(value))
    raise ValueError("type")


_SYM = re.compile(r"^[A-Z0-9.]{3,12}$")


def validate_recipe(f: Mapping[str, Any], cat: Mapping[str, Mapping[str, Any]]
                    ) -> dict[str, Any] | None:
    """{family, params, symbols} when the finding is a runnable recipe, else None."""
    fam = str(f.get("family") or "").strip()
    if fam not in cat:
        return None
    raw = f.get("params")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return None
    defaults = cat[fam]
    params: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in defaults:
            return None                     # a parameter the family does not take: not runnable
        try:
            c = _coerce(v, defaults[k])
        except (TypeError, ValueError):
            return None
        if c != defaults[k]:
            params[k] = c                   # only what differs from the default, so ids agree
    syms = []
    for s in f.get("symbols") or []:
        u = str(s).upper().replace("/", "").strip()
        if _SYM.match(u) and u not in syms:
            syms.append(u)
    if not syms:
        return None
    return {"family": fam, "params": params, "symbols": syms[:6]}


def genome_id(symbol: str, family: str, params: Mapping[str, Any]) -> str:
    """The hypothesis graph's own node id (`hypothesis_graph.node_id`), so lineage joins."""
    import hashlib
    payload = json.dumps({"s": str(symbol).upper(), "f": family, "p": dict(params)},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ------------------------------------------------------------------------------ prompts
#: WHAT ACTUALLY PASSES (Hourly evolve pass, 2026-11-17, from the judge's realised pass rates):
#: structural clock and flow mechanisms carry the passes; retail chart patterns sit at zero
#: after thousands of judgings each. Qualitative on purpose: no desk number goes in a prompt.
MECHANISM_STEER = (
    "What tends to survive testing: effects tied to the CLOCK and to FORCED FLOWS -- session "
    "and time-of-day transitions, overnight gaps and their decay, settlement, fixing and "
    "auction timing, month- and quarter-end rebalancing, rules whose ENTRY is conditioned on a "
    "state (volatility, trend, carry, risk-on/off), and carry with conditioning. What almost "
    "never survives: retail chart patterns and indicator crosses (RSI or Bollinger reversion, "
    "engulfing and pin bars, moving-average crosses, fair-value gaps, opening-range breakouts). "
    "Do not propose those unless a specific forced participant explains them.\n\n")

COVERAGE = "desks/mt5/reports/JUDGE_COVERAGE.json"
#: A family judged at least this often whose pass-rate upper bound is below DEAD_HI is pruned
#: from the prompt and its recipes are not donated: it has had its chance.
DEAD_MIN_JUDGED = 1000
DEAD_HI = 0.003
#: Used only where the judge's coverage report is absent (any host but the box): the families
#: the 2026-11-17 yield table showed at zero after thousands of judgings each.
DEAD_FALLBACK = frozenset({"ict_fvg", "mean_reversion_rsi", "mean_reversion_bollinger",
                           "engulfing_reversal", "pin_bar_reversal", "trend_ma_cross",
                           "opening_range", "volatility_squeeze", "asia_momentum",
                           "london_close_momentum", "level_breakout", "failed_breakout"})


def family_yield(root: Path) -> dict[str, dict[str, float]]:
    """The judge's realised pass rate per family (`JUDGE_COVERAGE.json`), or {} off the box."""
    try:
        doc = json.loads((root / COVERAGE).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, float]] = {}
    for r in doc.get("realised_pass_rate") or [] if isinstance(doc, dict) else []:
        if isinstance(r, dict) and r.get("family"):
            out[str(r["family"])] = {"judged": float(r.get("judged") or 0),
                                     "passed": float(r.get("passed") or 0),
                                     "mean": float(r.get("posterior_mean") or 0),
                                     "hi": float(r.get("posterior_hi") or 0)}
    return out


def steer_catalog(cat: Mapping[str, Mapping[str, Any]], yld: Mapping[str, Mapping[str, float]]
                  ) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """(catalogue with dead families removed, best realised yield first, unjudged families kept
    in the middle for exploration; the pruned names)."""
    if yld:
        dead = sorted(f for f in cat if f in yld and yld[f]["judged"] >= DEAD_MIN_JUDGED
                      and yld[f]["hi"] < DEAD_HI)
    else:
        dead = sorted(f for f in cat if f in DEAD_FALLBACK)
    live = [f for f in cat if f not in dead]
    explore = 0.01                                    # unjudged: between the winners and the rest
    live.sort(key=lambda f: -(yld[f]["mean"] if f in yld else explore))
    return {f: dict(cat[f]) for f in live}, dead


def propose_system(cat: Mapping[str, Mapping[str, Any]]) -> str:
    recipe = (
        "Where the idea fits one of these rule templates, ALSO give it as a runnable recipe: "
        '"family" (one name from the list) and "params" (only parameters that template takes; '
        "omit any you would leave at the default). Templates (name(parameter=default)):\n"
        f"{catalog_text(cat)}\n\n") if cat else ""
    return (
        "You are one agent in a research swarm. You propose testable trading hypotheses for "
        "liquid FX, gold, silver, metals, energy and equity-index CFDs; you decide nothing. "
        "Every idea will be tested by an independent statistical judge on historical data with "
        "costs, and most will fail, which is expected. Prefer unusual, specific ideas from your "
        "lens over ones every trader already knows.\n\n" + MECHANISM_STEER + recipe +
        "Return ONLY valid JSON, no prose outside it:\n"
        '{"findings": [{"title": "short label", '
        '"mechanism": "the economic reason the effect exists: who pays, and why they cannot stop", '
        '"testable_claim": "one falsifiable rule with entry, exit and holding time", '
        '"symbols": ["instruments, e.g. EURUSD, XAUUSD, USDCNH, US500, USOIL"], '
        '"family": "template name or null", "params": {}, '
        '"horizon": "intraday | days | weeks", '
        '"source": "a named public paper, report or practitioner source, or null"}]}\n'
        "Give up to 8 findings. An empty list is an honest answer.")


CRITIC_SYSTEM = (
    "You are a sceptical research critic. For each numbered trading rule, score 0-10 how likely "
    "it is to show a real, cost-surviving effect out of sample: is the mechanism real and still "
    "present, is the edge large enough to pay spread and slippage, is it more than a restatement "
    "of a common indicator, are the parameters sensible. Be harsh: most ideas deserve under 5.\n"
    'Return ONLY JSON: {"scores": [{"i": 0, "score": 0-10, "why": "one short reason"}]}')

MUTATE_SYSTEM = (
    "You improve trading rules. Each rule below showed a real but statistically under-powered "
    "effect in a historical test: the direction looked right, the sample was too thin to be "
    "sure. Propose variants that could make the same mechanism stronger or more frequent: "
    "other parameters, a related template, a tighter session, a sibling instrument with the same "
    "driver. Use only the templates and parameters listed.\n"
    "Return ONLY JSON in the same findings format as the input contract.")


def critic_user(batch: list[dict[str, Any]]) -> str:
    rows = []
    for i, r in enumerate(batch):
        rows.append(json.dumps({"i": i, "title": str(r.get("title", ""))[:120],
                                "family": r.get("family"), "params": r.get("params"),
                                "symbols": r.get("symbols"),
                                "mechanism": str(r.get("mechanism", ""))[:300]}))
    return "RULES:\n" + "\n".join(rows)


def parse_scores(text: str, n: int) -> dict[int, tuple[float, str]]:
    t = text.strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return {}
    try:
        doc = json.loads(t[a:b + 1])
    except ValueError:
        return {}
    out: dict[int, tuple[float, str]] = {}
    for r in doc.get("scores") or [] if isinstance(doc, dict) else []:
        try:
            i = int(r.get("i"))
            s = max(0.0, min(10.0, float(r.get("score"))))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= i < n:
            out[i] = (s, str(r.get("why") or "")[:160])
    return out


def mutate_user(near: list[dict[str, Any]], cat: Mapping[str, Mapping[str, Any]]) -> str:
    near = [r for r in near if r["family"] in cat]
    fams = {r["family"] for r in near}
    related = {k: v for k, v in cat.items() if k in fams} | dict(list(cat.items())[:24])
    # Only the template's own parameters: the judge's chart and session axes are not the
    # model's to vary, and a variant that copied them would fail `validate_recipe`.
    rows = "\n".join(json.dumps({"symbol": r["symbol"], "family": r["family"],
                                 "params": {k: v for k, v in r["params"].items()
                                            if k in cat[r["family"]]}}) for r in near)
    return (f"RULES:\n{rows}\n\nTEMPLATES:\n{catalog_text(related, limit=40)}\n\n"
            'Return {"findings": [{"title", "mechanism", "testable_claim", "symbols", '
            '"family", "params", "horizon", "source"}]} with up to 8 variants.')


# ------------------------------------------------------------------------- the scoreboard
def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        fh = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                yield r


def lineage(root: Path, since: datetime | None = None) -> list[dict[str, Any]]:
    out = []
    stamp = since.isoformat(timespec="seconds") if since else ""
    for r in _jsonl(root / LINEAGE):
        if str(r.get("at", "")) >= stamp:
            out.append(r)
    return out


def _subset(base: Mapping[str, Any], full: Mapping[str, Any]) -> bool:
    return all(full.get(k) == v for k, v in base.items())


def scoreboard(root: Path) -> dict[str, Any]:
    """Per model and per lens: recipes donated, judged, passed, near misses. UNMEASURED when the
    judge's ledger is not on this host (it lives on the box), never zero."""
    lin = lineage(root)
    ledger = root / GATE_LEDGER
    if not ledger.exists():
        return {"status": "UNMEASURED", "why": f"{GATE_LEDGER} absent on this host",
                "donated": len(lin), "by_model": {}, "by_lens": {}}
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in lin:
        by_key.setdefault((str(r.get("symbol", "")).upper(), str(r.get("family", ""))), []
                          ).append(r)
    # The graph rows the compiler wrote for this donor: graph id -> (sym, family, params).
    ids: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for g in _jsonl(root / GRAPH):
        if str(g.get("source", "")) == DONOR_SOURCE and g.get("id"):
            ids[str(g["id"])] = (str(g.get("symbol", "")).upper(), str(g.get("family", "")),
                                 g.get("params") if isinstance(g.get("params"), dict) else {})
    verdict: dict[str, tuple[bool, str]] = {}
    for v in _jsonl(ledger):
        gid = str(v.get("graph_id") or "")
        if gid in ids:
            verdict[gid] = (bool(v.get("passed")), str(v.get("terminal_gate") or ""))
    tally: dict[str, dict[str, dict[str, int]]] = {"by_model": {}, "by_lens": {}}
    for r in lin:
        for axis, key in (("by_model", f"{r.get('provider')}:{r.get('model')}"),
                          ("by_lens", str(r.get("lens")))):
            t = tally[axis].setdefault(key, {"donated": 0, "judged": 0, "passed": 0, "near": 0})
            t["donated"] += 1
    for gid, (passed, gate) in verdict.items():
        sym, fam, params = ids[gid]
        for r in by_key.get((sym, fam), []):
            if not _subset(r.get("params") or {}, params):
                continue
            for axis, key in (("by_model", f"{r.get('provider')}:{r.get('model')}"),
                              ("by_lens", str(r.get("lens")))):
                t = tally[axis][key]
                t["judged"] += 1
                t["passed"] += int(passed)
                t["near"] += int((not passed) and gate in POWER_ONLY_GATES)
    return {"status": "MEASURED", "donated": len(lin), "judged_cells": len(verdict), **tally}


def weights(arms: list[str], board: Mapping[str, Mapping[str, int]], rng: random.Random
            ) -> dict[str, float]:
    """Thompson draws on 'progressed' (passed, or a near miss) per judged recipe, floored so no
    arm drops below EXPLORE_FLOOR of a uniform share. Unjudged arms draw from the prior."""
    if not arms:
        return {}
    draws = {}
    for a in arms:
        t = board.get(a) or {}
        good = int(t.get("passed", 0)) + int(t.get("near", 0))
        bad = max(0, int(t.get("judged", 0)) - good)
        draws[a] = rng.betavariate(1 + good, 1 + bad)
    tot = sum(draws.values()) or 1.0
    floor = EXPLORE_FLOOR / len(arms)
    w = {a: max(floor, d / tot) for a, d in draws.items()}
    s = sum(w.values())
    return {a: v / s for a, v in w.items()}


def ordered(arms: list[str], w: Mapping[str, float], rng: random.Random) -> list[str]:
    """Arms in a weighted random order (sampling without replacement)."""
    left = list(arms)
    out = []
    while left:
        tot = sum(w.get(a, 0.0) for a in left) or 1.0
        x = rng.random() * tot
        acc = 0.0
        for a in left:
            acc += w.get(a, 0.0)
            if acc >= x:
                break
        out.append(a)
        left.remove(a)
    return out


def near_misses(root: Path, limit: int = 30, max_rows: int = 400_000) -> list[dict[str, Any]]:
    """The latest under-powered cells (any producer), newest first, with their parameters."""
    latest: dict[str, tuple[str, bool, str]] = {}
    for n, v in enumerate(_jsonl(root / GATE_LEDGER), 1):
        gid = str(v.get("graph_id") or "")
        if gid:
            latest[gid] = (str(v.get("at", "")), bool(v.get("passed")),
                           str(v.get("terminal_gate") or ""))
        if n >= max_rows:
            break
    near = sorted(((at, gid) for gid, (at, ok, gate) in latest.items()
                   if not ok and gate in POWER_ONLY_GATES), reverse=True)[: limit * 3]
    want = {gid for _at, gid in near}
    if not want:
        return []
    found: dict[str, dict[str, Any]] = {}
    for g in _jsonl(root / GRAPH):
        gid = str(g.get("id") or "")
        if gid in want and isinstance(g.get("params"), dict) and g.get("symbol"):
            found[gid] = {"symbol": str(g["symbol"]).upper(), "family": str(g.get("family")),
                          "params": g["params"]}
    return [found[g] for _at, g in near if g in found][:limit]


def recent_ids(root: Path, days: int, now: datetime) -> set[str]:
    since = now - timedelta(days=days)
    return {str(r.get("gid")) for r in lineage(root, since) if r.get("gid")}


# ---------------------------------------------------------------------- source discovery
#: The `source_scout` lens asks for SOURCES, not trades. Each answer is registered as a CANDIDATE
#: source in the moat registry through `scout_swarm.register_expansions` (parent
#: `seat:cn_swarm`): registration is not permission to fetch. A candidate is crawled only by the
#: desk's collectors, only once the parent's ROI gate opens, and every fetch still passes
#: `robots_gate` and the terms checks. Nothing here fetches anything.
SCOUT_LENS = "source_scout"
SOURCES_LEDGER = "data/cn_swarm_sources.jsonl"
SCOUT_PARENT = "seat:cn_swarm"

SCOUT_SYSTEM = (
    "You are a source scout for a research team. Name PUBLIC, FREE, little-known publishers "
    "(official statistics offices, regional central-bank bulletins, exchanges, industry "
    "associations, port and customs data, commodity boards, local trader communities) in any "
    "country and language whose releases could predict moves in FX, gold, metals, energy or "
    "equity-index CFDs. Prefer the obscure over the famous; never name a paywalled, "
    "members-only source, or a crypto exchange.\n"
    'Return ONLY JSON: {"sources": [{"name": "publisher", "url": "https://...", '
    '"country": "ISO code", "language": "ISO code", "publishes": "what and how often", '
    '"why": "the market it could move and how"}]}\nGive up to 10.')

_CRYPTO = ("binance", "bybit", "okx", "hyperliquid", "deribit", "kraken", "coinbase", "bitmex",
           "kucoin", "huobi", "gate.io", "bitfinex")


def parse_sources(text: str) -> list[dict[str, str]]:
    t = text.strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return []
    try:
        doc = json.loads(t[a:b + 1])
    except ValueError:
        return []
    out = []
    for r in doc.get("sources") or [] if isinstance(doc, dict) else []:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "").strip()
        name = str(r.get("name") or "").strip()
        if not (url.startswith("https://") and name) or len(url) > 300 or " " in url:
            continue
        if any(c in url.lower() for c in _CRYPTO):
            continue
        out.append({"name": name[:120], "url": url,
                    "country": str(r.get("country") or "")[:8],
                    "language": str(r.get("language") or "")[:8],
                    "publishes": str(r.get("publishes") or "")[:300],
                    "why": str(r.get("why") or "")[:300]})
    return out


def _host_path(url: str) -> str:
    from urllib.parse import urlparse
    u = urlparse(url)
    return f"{(u.netloc or '').lower()}{u.path.rstrip('/')}"


def known_sources(root: Path) -> set[str]:
    return {_host_path(str(r.get("url", ""))) for r in _jsonl(root / SOURCES_LEDGER)}


def register_sources(urls: list[str], dry: bool = False) -> dict[str, Any]:
    """Candidates into the moat registry, or UNMEASURED saying why they could not be."""
    import sys
    root = Path(__file__).resolve().parents[2]
    for p in (root / "desks" / "mt5" / "research", root / "desks" / "mt5", root):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import scout_swarm

        from libs.moat import registry
        conn = registry.connect()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registry unavailable: {type(exc).__name__}"}
    try:
        got = scout_swarm.register_expansions(SCOUT_PARENT, {"datasets": urls}, conn, dry=dry)
        conn.commit()
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"registration failed: {type(exc).__name__}"}
    finally:
        conn.close()
    return {"status": "REGISTERED", **{k: v for k, v in got.items() if k != "ids"}}


def discovered_brief(root: Path, rng: random.Random, n: int = 4) -> str | None:
    """A lens built from sources the scouts found earlier: the swarm then mines them for ideas
    from what the model knows of them (still nothing is fetched here)."""
    rows = list(_jsonl(root / SOURCES_LEDGER))[-200:]
    if not rows:
        return None
    pick = rng.sample(rows, min(n, len(rows)))
    names = "; ".join(f"{r.get('name')} ({r.get('country')}, {r.get('publishes', '')[:80]})"
                      for r in pick)
    return ("what these little-known public publishers release, and which predictable price "
            f"behaviour in FX, gold, metals, energy or index CFDs it could drive: {names}")


# ------------------------------------------------------------- cross-science analog families
#: Models borrowed from other sciences (Hourly pass ideas duty, 2026-11-17). Each lens asks for
#: the analog as a FORMULA in the desk's causal alpha grammar (`libs.research.alpha_grammar`),
#: built from the instrument's own bars only, so it compiles straight into the `formula` family.
#: `population` in its params names the analog (provenance, never a tuned parameter), which makes
#: each analog its own never-judged cell population for the breadth floor.
SCIENCE_PREFIX = "science_"
SCIENCE_LENSES: tuple[tuple[str, str], ...] = (
    ("science_predator_prey", "ecology's predator-prey (Lotka-Volterra) cycles between two "
     "populations, e.g. momentum traders feeding on trend while mean-reverters feed on them"),
    ("science_sir_contagion", "epidemiology's SIR contagion: a move that infects activity and "
     "volatility, spreads, peaks and burns out as the susceptible pool is exhausted"),
    ("science_queueing_refill", "queueing theory: liquidity consumed by aggressive flow and "
     "refilled at a finite rate, so price impact decays as the queue rebuilds"),
    ("science_critical_slowing", "physics' critical slowing down before a phase transition: "
     "rising autocorrelation and variance that warn of a regime break"),
    ("science_hawkes_excitation", "self-exciting point processes (earthquake aftershocks): "
     "bursts of activity that raise the odds of further bursts, then decay"),
    ("science_diffusion_barrier", "diffusion against a reflecting or absorbing barrier: price "
     "near a recent extreme behaves differently from price in open space"),
    ("science_oscillator_damping", "damped and driven oscillators: an overshoot that rings back "
     "with a characteristic period and decay set by the session clock"),
    ("science_entropy_order", "information entropy: low-entropy, orderly flow that precedes a "
     "directional move versus high-entropy noise"),
)
SCIENCE_BRIEF = dict(SCIENCE_LENSES)


def formula_system() -> str:
    from libs.research import alpha_grammar as g
    return (
        "You are one agent in a research swarm that borrows models from other sciences. Turn "
        "the science model you are given into a TRADING SIGNAL written as a formula over one "
        "instrument's own bars, in this exact grammar (prefix calls, nothing else):\n"
        f"- terminals: {', '.join(g.BAR_TERMINALS)} (ret = return, range = high-low, "
        "activity = tick count, flow = signed tick flow, vol = realised volatility)\n"
        f"- one-argument: {', '.join(g.UNARY)}\n"
        f"- windowed (child, window): {', '.join(g.WINDOWED)}\n"
        f"- two-argument: {', '.join(g.BINARY)}\n"
        f"- two-argument windowed (a, b, window): {', '.join(x for x in g.BINARY_WINDOWED if 'group' not in x)}\n"
        f"- windows: {', '.join(str(w) for w in g.WINDOWS)}; at most {g.MAX_DEPTH} levels deep\n"
        "Never add a price to a count or a return: combine like with like, or z-score first.\n"
        "The signal is z-scored and traded when extreme: side_mode 'follow' trades with its "
        "sign, 'fade' against it.\n"
        "Return ONLY JSON: "
        '{"findings": [{"title": "short label", "analog": "the science model", '
        '"mechanism": "why markets should behave like this model", '
        '"testable_claim": "what the signal predicts", '
        '"expr": "zscore(sub(mean(flow, 12), mean(flow, 48)), 120)", '
        '"side_mode": "follow | fade", "hold_bars": 8, "entry_z": 1.5, '
        '"symbols": ["EURUSD", "XAUUSD"]}]}\nGive up to 6 findings.')


def validate_formula(f: Mapping[str, Any], analog: str) -> dict[str, Any] | None:
    """A `formula` recipe when the expression parses and is valid on bar terminals only."""
    try:
        from libs.research import alpha_grammar as g
        expr = g.from_str(str(f.get("expr") or ""))
    except Exception:
        return None
    if not g.is_valid(expr, terminals=g.BAR_TERMINALS) or g.complexity(expr) > 24:
        return None
    params: dict[str, Any] = {"expr": expr, "population": f"llm_{analog}"}
    side = str(f.get("side_mode") or "follow")
    if side not in ("follow", "fade"):
        return None
    if side != "follow":
        params["side_mode"] = side
    try:
        hb = round(float(f.get("hold_bars", 8)))
        ez = float(f.get("entry_z", 1.5))
    except (TypeError, ValueError):
        return None
    if not (1 <= hb <= 240 and 0.5 <= ez <= 4.0):
        return None
    if hb != 8:
        params["hold_bars"] = hb
    if ez != 1.5:
        params["entry_z"] = ez
    syms = []
    for s in f.get("symbols") or []:
        u = str(s).upper().replace("/", "").strip()
        if _SYM.match(u) and u not in syms:
            syms.append(u)
    if not syms:
        return None
    return {"family": "formula", "params": params, "symbols": syms[:6]}


LENSES = LENSES + tuple((lid, "en", brief) for lid, brief in SCIENCE_LENSES)
LENS_BRIEF.update(SCIENCE_BRIEF)
