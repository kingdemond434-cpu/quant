"""Shared multilingual survivor-hunting intelligence (principal 2026-08-26: the frontier digs'
native-operator discipline applies to EVERY miner, Python included, all languages).

Three exports:
  LEXICON          concept -> native terms across en/ru/zh/ja/ko/ar/es/pt/vi/tr/de/fr/id --
                   stat labels AND mechanism slang, seeded from the operator library's verified
                   ground truth (автоследование, 反向跟单, поделка, 喊单 ...). A registry, never
                   a boundary: digs append what native ground teaches them.
  label_regex()    compiled alternation for a stat concept, so a parser reads 最大ドローダウン,
                   просадка, 最大回撤, أقصى تراجع and drawdown as ONE label.
  detect_mechanisms()  tag any text row in any language with normalized mechanism concepts
                   (martingale/grid/scalping/breakout/...) -- the converter maps tags to
                   families without an LLM touching the text.
"""
from __future__ import annotations

import re

LEXICON: dict[str, dict[str, list[str]]] = {
    # ---- stat labels -------------------------------------------------------------
    "return": {
        "en": ["growth", "return", "gain", "profit", "yield", "profitability"],
        "ru": ["доходность", "прибыль", "прирост"],
        "zh": ["收益率", "收益", "回报", "盈利"],
        "ja": ["収益率", "収益", "損益", "利益率", "リターン"],
        "ko": ["수익률", "수익"],
        "ar": ["العائد", "الربح", "الأرباح"],
        "es": ["rentabilidad", "retorno", "ganancia", "beneficio"],
        "pt": ["rentabilidade", "retorno", "lucro"],
        "vi": ["lợi nhuận", "tỷ suất"],
        "tr": ["getiri", "kazanç", "kâr"],
        "de": ["rendite", "gewinn"],
        "fr": ["rendement", "gain"],
        "id": ["keuntungan", "imbal hasil"],
    },
    "drawdown": {
        "en": ["drawdown", "max dd", "maximal drawdown"],
        "ru": ["просадка", "максимальная просадка"],
        "zh": ["回撤", "最大回撤"],
        "ja": ["ドローダウン", "最大ドローダウン", "最大損失率"],
        "ko": ["낙폭", "최대 낙폭"],
        "ar": ["التراجع", "أقصى تراجع", "الحد الأقصى للتراجع"],
        "es": ["drawdown", "retroceso máximo", "pérdida máxima"],
        "pt": ["rebaixamento", "drawdown máximo"],
        "vi": ["sụt giảm", "mức giảm tối đa"],
        "tr": ["düşüş", "maksimum düşüş"],
        "de": ["drawdown", "maximaler verlust"],
        "fr": ["drawdown", "perte maximale"],
        "id": ["penurunan maksimum"],
    },
    "win_rate": {
        "en": ["win rate", "profitable trades", "success rate"],
        "ru": ["процент прибыльных", "винрейт"],
        "zh": ["胜率", "盈利率"],
        "ja": ["勝率"],
        "ko": ["승률"],
        "ar": ["نسبة الربح", "معدل النجاح"],
        "es": ["tasa de acierto", "operaciones ganadoras"],
        "pt": ["taxa de acerto"],
        "vi": ["tỷ lệ thắng"],
        "tr": ["kazanma oranı"],
        "de": ["trefferquote"],
        "fr": ["taux de réussite"],
        "id": ["rasio menang"],
    },
    "trades": {
        "en": ["trades", "positions", "orders", "operations"],
        "ru": ["сделки", "сделок", "позиций"],
        "zh": ["交易次数", "订单", "笔数"],
        "ja": ["取引回数", "約定", "取引数"],
        "ko": ["거래 횟수"],
        "ar": ["الصفقات", "عدد الصفقات"],
        "es": ["operaciones", "órdenes"],
        "pt": ["operações", "negociações"],
        "vi": ["giao dịch", "lệnh"],
        "tr": ["işlemler", "işlem sayısı"],
        "de": ["trades", "positionen"],
        "fr": ["transactions", "ordres"],
        "id": ["transaksi"],
    },
    "followers": {
        "en": ["followers", "copiers", "subscribers", "investors"],
        "ru": ["подписчики", "инвесторы", "копировщики", "автоследование"],
        "zh": ["跟随者", "订阅者", "跟单人数", "投资者"],
        "ja": ["フォロワー", "セレクター数"],
        "ko": ["팔로워", "구독자"],
        "ar": ["المتابعون", "الناسخون", "المستثمرون"],
        "es": ["seguidores", "copiadores", "inversores"],
        "pt": ["seguidores", "copiadores"],
        "vi": ["người theo dõi", "người sao chép"],
        "tr": ["takipçiler", "kopyalayanlar"],
        "de": ["follower", "kopierer"],
        "fr": ["suiveurs", "copieurs"],
        "id": ["pengikut", "penyalin"],
    },
    "age": {
        "en": ["weeks", "days", "age", "since", "started"],
        "ru": ["дней", "недель", "возраст"],
        "zh": ["天数", "运行天数", "周"],
        "ja": ["運用日数", "週間", "日数"],
        "ko": ["운용 기간"],
        "ar": ["الأيام", "العمر", "منذ"],
        "es": ["días", "semanas", "antigüedad"],
        "pt": ["dias", "semanas"],
        "vi": ["ngày", "tuần"],
        "tr": ["gün", "hafta"],
        "de": ["tage", "wochen"],
        "fr": ["jours", "semaines"],
        "id": ["hari", "minggu"],
    },
    # ---- mechanism slang (verified ground truth where the digs measured it) -----
    "martingale": {
        "en": ["martingale", "recovery mode", "position averaging"],
        "ru": ["мартингейл", "мартин", "усреднение"],
        "zh": ["马丁", "马丁格尔", "加仓摊平", "低倍马丁"],
        "ja": ["マーチンゲール", "ナンピン"],
        "ko": ["마틴게일", "물타기"],
        "ar": ["مارتينجال", "مضاعفة الصفقات"],
        "es": ["martingala", "promediar"],
        "pt": ["martingale", "preço médio"],
        "vi": ["martingale", "nhồi lệnh"],
        "tr": ["martingale", "maliyet ortalama"],
        "de": ["martingale", "nachkaufen"],
        "fr": ["martingale", "moyenne à la baisse"],
        "id": ["martingale", "averaging"],
    },
    "grid": {
        "en": ["grid", "grid trading", "pending grid"],
        "ru": ["сетка", "сеточник", "сеточная"],
        "zh": ["网格", "网格交易"],
        "ja": ["リピート系", "グリッド", "トラリピ"],
        "ko": ["그리드"],
        "ar": ["الشبكة", "تداول الشبكة"],
        "es": ["rejilla", "grid"],
        "pt": ["grade", "grid"],
        "vi": ["lưới", "grid"],
        "tr": ["grid", "ızgara"],
        "de": ["grid", "raster"],
        "fr": ["grille"],
        "id": ["grid"],
    },
    "scalping": {
        "en": ["scalping", "scalper"],
        "ru": ["скальпинг", "скальпер", "пипсовка"],
        "zh": ["剥头皮", "超短线", "刷单"],
        "ja": ["スキャルピング", "スキャル", "秒スキャ"],
        "ko": ["스캘핑", "단타"],
        "ar": ["السكالبينج", "المضاربة اللحظية"],
        "es": ["scalping", "especulación rápida"],
        "pt": ["scalping", "escalpelamento"],
        "vi": ["scalping", "lướt sóng"],
        "tr": ["scalping", "kısa vadeli"],
        "de": ["scalping"],
        "fr": ["scalping"],
        "id": ["scalping"],
    },
    "breakout": {
        "en": ["breakout", "break of high", "range break"],
        "ru": ["пробой", "пробитие уровня"],
        "zh": ["突破", "破位"],
        "ja": ["ブレイクアウト", "ブレイク", "高値更新"],
        "ko": ["돌파"],
        "ar": ["الاختراق", "كسر المستوى"],
        "es": ["ruptura", "rompimiento"],
        "pt": ["rompimento"],
        "vi": ["phá vỡ", "breakout"],
        "tr": ["kırılım"],
        "de": ["ausbruch"],
        "fr": ["cassure"],
        "id": ["penembusan"],
    },
    "trend": {
        "en": ["trend following", "trend", "momentum"],
        "ru": ["трендовая", "по тренду", "моментум"],
        "zh": ["趋势", "顺势", "动量"],
        "ja": ["トレンドフォロー", "順張り"],
        "ko": ["추세", "모멘텀"],
        "ar": ["الاتجاه", "متابعة الاتجاه"],
        "es": ["tendencia", "seguimiento de tendencia"],
        "pt": ["tendência"],
        "vi": ["xu hướng"],
        "tr": ["trend takibi"],
        "de": ["trendfolge"],
        "fr": ["suivi de tendance"],
        "id": ["mengikuti tren"],
    },
    "mean_reversion": {
        "en": ["mean reversion", "counter trend", "reversal"],
        "ru": ["контртренд", "возврат к среднему", "разворот"],
        "zh": ["均值回归", "逆势", "反转"],
        "ja": ["逆張り", "リバーサル"],
        "ko": ["역추세", "평균회귀"],
        "ar": ["الارتداد", "العودة للمتوسط"],
        "es": ["reversión a la media", "contratendencia"],
        "pt": ["reversão à média"],
        "vi": ["đảo chiều"],
        "tr": ["ortalamaya dönüş"],
        "de": ["mean reversion", "umkehr"],
        "fr": ["retour à la moyenne"],
        "id": ["pembalikan"],
    },
    "news_trading": {
        "en": ["news trading", "nfp", "cpi", "fomc", "high impact news"],
        "ru": ["торговля на новостях", "новостник"],
        "zh": ["数据行情", "非农", "消息面"],
        "ja": ["指標トレード", "雇用統計", "経済指標"],
        "ko": ["뉴스 트레이딩", "지표 매매"],
        "ar": ["تداول الأخبار", "البيانات الاقتصادية"],
        "es": ["trading de noticias", "nóminas"],
        "pt": ["notícias", "payroll"],
        "vi": ["tin tức", "bảng lương phi nông nghiệp"],
        "tr": ["haber ticareti", "tarım dışı"],
        "de": ["newstrading"],
        "fr": ["trading de news"],
        "id": ["berita berdampak tinggi"],
    },
    "copy_trading": {
        "en": ["copy trading", "signal", "social trading"],
        "ru": ["копитрейдинг", "копирование сделок", "автоследование", "сигналы"],
        "zh": ["跟单", "复制交易", "喊单", "带单", "反向跟单"],
        "ja": ["コピートレード", "ミラートレード", "シストレ", "自動売買"],
        "ko": ["카피 트레이딩", "복사 매매"],
        "ar": ["نسخ الصفقات", "التداول الاجتماعي", "التداول الآلي"],
        "es": ["copytrading", "cuentas gestionadas", "señales"],
        "pt": ["copy trade", "sinais"],
        "vi": ["sao chép giao dịch", "copy trade"],
        "tr": ["kopya ticaret", "sinyal"],
        "de": ["copy trading", "signale"],
        "fr": ["copy trading", "signaux"],
        "id": ["salin perdagangan", "sinyal"],
    },
    "ea_robot": {
        "en": ["expert advisor", "ea", "trading robot", "algo"],
        "ru": ["советник", "робот", "алго", "торговый робот", "поделка"],
        "zh": ["智能交易", "ea", "程序化", "量化"],
        "ja": ["自動売買", "ea", "システムトレード"],
        "ko": ["자동매매", "이에이"],
        "ar": ["إكسبرت", "روبوت التداول", "التداول الآلي"],
        "es": ["robot de trading", "asesor experto"],
        "pt": ["robô de trading", "ea"],
        "vi": ["robot giao dịch", "ea"],
        "tr": ["uzman danışman", "robot"],
        "de": ["handelsroboter", "expert advisor"],
        "fr": ["robot de trading", "expert advisor"],
        "id": ["robot trading", "ea"],
    },
    "gold": {
        "en": ["gold", "xauusd", "xau"],
        "ru": ["золото"], "zh": ["黄金", "现货黄金"], "ja": ["ゴールド", "金"],
        "ko": ["금", "골드"], "ar": ["الذهب"], "es": ["oro"], "pt": ["ouro"],
        "vi": ["vàng"], "tr": ["altın"], "de": ["gold"], "fr": ["or"], "id": ["emas"],
    },
}

STAT_CONCEPTS = ("return", "drawdown", "win_rate", "trades", "followers", "age")
MECHANISM_CONCEPTS = ("martingale", "grid", "scalping", "breakout", "trend",
                      "mean_reversion", "news_trading", "copy_trading", "ea_robot", "gold")

_compiled: dict[str, re.Pattern] = {}


def all_terms(concept: str) -> list[str]:
    return [t for terms in LEXICON.get(concept, {}).values() for t in terms]


def label_regex(concept: str) -> re.Pattern:
    """Alternation over every language's labels for a stat concept, longest-first."""
    if concept not in _compiled:
        terms = sorted(all_terms(concept), key=len, reverse=True)
        _compiled[concept] = re.compile("(?:" + "|".join(re.escape(t) for t in terms) + ")",
                                        re.IGNORECASE)
    return _compiled[concept]


def stat_near(html: str, concept: str, window: int = 90) -> float | None:
    """First number within `window` chars after ANY language's label for `concept`."""
    m = label_regex(concept).search(html)
    if not m:
        return None
    seg = html[m.end():m.end() + window]
    n = re.search(r"[-+]?\d[\d\s, ]*\.?\d*", seg)
    if not n:
        return None
    try:
        return float(n.group(0).replace(",", "").replace(" ", "").replace(" ", ""))
    except ValueError:
        return None


def detect_mechanisms(text: str) -> list[str]:
    """Normalized mechanism tags for a text in ANY language."""
    if not text:
        return []
    low = text.lower()
    return [c for c in MECHANISM_CONCEPTS if label_regex(c).search(low)]


def native_queries(concept: str = "copy_trading", langs: tuple = ("ru", "zh", "ja", "ar",
                                                                 "es", "vi")) -> list[str]:
    """Seed search terms in native scripts for discovery layers (GitHub q=, site search)."""
    out = []
    for lg in langs:
        out.extend(LEXICON.get(concept, {}).get(lg, [])[:2])
    return out
