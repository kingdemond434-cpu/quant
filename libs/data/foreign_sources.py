"""NON-CHINESE FOREIGN FORESTS -- Japanese, Korean and Russian practitioner writing.

WHY THESE AND NOT "MORE SOURCES". The desk's Chinese lane exists because Chinese quant writing is
substantial, practitioner-authored, and INVISIBLE to English search -- not because Chinese is
special. That argument is language-agnostic, and it was being made for exactly one language while
three other large crypto-native communities went unindexed:

  JAPANESE   the largest retail derivatives market outside the US by turnover, with a domestic
             engineering-blog culture (Qiita, Zenn) where implementations are posted with code.
  KOREAN     the venue whose price gap has its own name on this desk -- capital_control_barrier_rent
             is measured against Upbit/Bithumb. The desk screens the KR premium and has never read
             a word written by the people creating it.
  RUSSIAN    a deep quantitative-engineering tradition on Habr, and a crypto community that
             discusses OTC, settlement and sanctions-adjacent flow that surfaces nowhere else.

EVERY ROUTE HERE WAS PROBED LIVE ON 2026-08-05, not assumed. What answered, what did not, and the
route that worked when the obvious one failed:

  Qiita (JP)      api.qiita.com items?query=   -> clean JSON, keyless, ~300KB/query.  USED
  Zenn (JP)       zenn.dev/api/articles        -> clean JSON, keyless.                USED
  Hatena (JP)     b.hatena.ne.jp .../?mode=rss -> RDF/RSS, keyless, 32 items/query.   USED
  Habr (RU)       habr.com/ru/search/          -> JS SHELL, 0 parseable results.      route failed
  Habr (RU)       habr.com/ru/rss/search/      -> RSS, 20 items/query.                USED
  DCInside (KR)   search.dcinside.com/post/q/  -> server-rendered HTML, 25 rows.      USED
  Naver (KR)      openapi.naver.com            -> HTTP 401, needs an API key.         out of scope
  note.com (JP)   /api/v3/searches             -> HTTP 403 {"error":"Access denied"}.  BLOCKED
                  (the old `/searchs` spelling 404s; corrected + re-probed 2026-08-12.
                   403 with a STRUCTURED json error is the endpoint refusing us, not a
                   missing route -- a different problem needing a different fix)

THE HABR LINE IS THE POINT OF L1.54 CLAUSE 6. The search PAGE is a JS shell and a desk that
stopped there would have recorded "Habr: blocked, client-rendered" and lost a Russian corpus
permanently. The same site serves the same query as RSS, keylessly, in one request. A shut door
was a routing problem, and the cost of finding that out was one more probe.

ENTITY DECODING IS NOT OPTIONAL HERE, and Hatena proves it: its RSS returns titles as numeric
character references (`&#x306B;` for に). Undecoded, the triage ranker sees no Japanese at all and
scores every row zero -- a real edge made invisible to the gate rather than rejected by it, which
is the identical failure fixed in the CN parsers earlier the same day. Every parser below decodes,
and every one strips tags BEFORE decoding so an encoded `&lt;b&gt;` cannot become a tag the
stripper then eats.

ONLY TITLES AND SNIPPETS ARE KEPT, exactly as for the Chinese sources. These are indexed to decide
what a human should go and READ. Nothing archives article bodies.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import quote

#: Minimum seconds between requests to one source. NOT one global number: Hatena answered 429 to
#: EVERY query in the first live sweep at 1.2s spacing while Qiita and Habr were untroubled by it,
#: so a single pace either wastes time on the tolerant sources or keeps losing the strict one.
#: Measured, not guessed -- these are the values that produced a clean sweep.
_MIN_INTERVAL_S: Final[dict[str, float]] = {
    "hatena": 6.0,     # 429s the whole sweep at 1.2s; the strictest source here by a distance
    "dcinside": 2.0,
    "qiita": 1.0,
    "zenn": 1.0,
    "habr": 1.5,
    "note": 1.5,
    "velog": 1.5,
    "vcru": 1.5,
    "smartlab": 2.5,
    "coinpan": 2.5,
    "tinhte": 2.5,
    "eksisozluk": 3.0,
}

#: Sources that answered 429 THIS PROCESS. A source that has asked for a pause gets one for the
#: rest of the run rather than another seventeen requests -- continuing to hammer it is how a
#: temporary rate-limit becomes a durable block, which would cost the lane rather than the query.
_BACKED_OFF: set[str] = set()

_UA: Final[dict[str, str]] = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/html, application/rss+xml, */*",
}


@dataclass(frozen=True)
class Article:
    """Deliberately the SAME shape as cn_sources.Article.

    Not a coincidence and not laziness: the triage ranker, the miner's queue writer and the
    dedupe key all already speak this shape, so a new language costs a parser rather than a
    pipeline. A second, parallel article type would have forced every downstream consumer to grow
    a branch per language -- which is how a desk ends up indexing four languages and ranking one.
    """

    source: str
    ident: str
    title: str
    url: str
    author: str = ""
    snippet: str = ""

    @property
    def searchable(self) -> str:
        return f"{self.title} {self.snippet}"


# --------------------------------------------------------------------------- query territories
# ONE TERRITORY PER LINE, never a synonym of the line above. The Chinese set learned this the
# expensive way: four rephrasings of "quant backtest" return one forest four times. Each list
# below walks the same axes as CN_ARTICLE_QUERIES -- validation, factors, the MT5 universe
# (gold/FX/metals/indices/energy), MT5-native mechanisms (carry/swap, futures basis, COT
# positioning, session structure), microstructure and cost, and the failure literature -- in the
# vocabulary the local community actually uses, because a translated English phrase finds
# translated English content and that is the one corpus already covered.
#
# MT5 UNIVERSE MANDATE (2026-08-18). Every crypto-exchange-native query (crypto assets, funding
# rate, perpetual mechanics, cross-exchange/kimchi/on-chain/miner-flow, whale wallets) was removed
# from all five language sets on that date and replaced with the desk's real market and its
# analogues. No crypto-exchange universe is hunted in any language any longer. What stayed is
# universe-neutral (validation, microstructure, factor work transfer to any market).

QUERIES_JA: Final[tuple[str, ...]] = (
    "バックテスト 過学習 検証",              # overfitting in backtests
    "アウトオブサンプル 検証 失敗",           # out-of-sample validation
    "先読みバイアス バックテスト",            # lookahead bias
    "生存者バイアス 検証",                    # survivorship bias
    "ファクター 有効性 検証",                 # factor validity
    "ゴールド XAUUSD トレード 戦略",          # gold / XAUUSD
    "為替 FX アルゴリズム 戦略 検証",         # forex algorithmic strategy
    "MT5 EA 自動売買 開発",                   # MT5 expert advisors
    "スワップ キャリー 金利差 取引",          # carry / swap -- the funding-rate analogue
    "先物 現物 ベーシス 収束",                # futures-cash basis convergence (index/gold)
    "COT 建玉 ポジション 分析",               # COT positioning -- the whale-tracking analogue
    "株価指数 先物 戦略",                     # equity-index futures
    "原油 コモディティ トレード 戦略",        # energy / commodities
    "マーケットメイク 在庫リスク",            # market-making inventory risk
    "板 スリッページ 執行コスト",             # book slippage / execution cost
    "高頻度取引 約定 メカニズム",             # HFT matching mechanics
    "ロンドン ニューヨーク 時間帯 為替",      # session structure -- first-class off 24/7
    "経済指標 雇用統計 為替 反応",            # NFP / macro-event reaction
    "実運用 バックテスト 乖離",               # live-vs-backtest divergence
    # -- breadth parity with the CN lane (2026-08-18): same territory, native vocabulary
    "順張り トレンドフォロー 戦略",           # trend following
    "逆張り 平均回帰 戦略",                   # mean reversion
    "ブレイクアウト 戦略 検証",               # breakout
    "ボラティリティ ブレイクアウト 戦略",     # volatility breakout
    "グリッドトレード リスク 破綻",           # grid trading risk
    "統計的裁定 ペアトレード",                # statistical arbitrage / pairs
    "CTA トレンド 戦略 検証",                 # CTA
    "オプション ボラティリティ 戦略",         # options vol
    "マルチファクター モデル 検証",           # multi-factor
    "クロスセクション ファクター アルファ",   # cross-sectional factor
    "オーダーブロック 手法 検証",             # SMC order block
    "フェアバリューギャップ FVG 手法",        # SMC / ICT FVG
    "流動性 スイープ 相場構造",               # liquidity sweep / market structure
    "銀 XAGUSD 取引 戦略",                    # silver
    "ドル円 ユーロドル トレード 戦略",        # USDJPY / EURUSD
    "日経225 ダウ ナスダック 戦略",           # equity indices
    "ロンドンフィックス 実需 フロー",         # London WMR fix flow
    "先物 ロールオーバー 期日 取引",          # futures roll
    "中央銀行 政策金利 発表 反応",            # central-bank event
    "週末 窓開け ギャップ リスク",            # weekend gap risk
    "生産者 ヘッジ COT 商業筋",               # producer hedging (COT commercial)
    "破産 ロスカット 反省 実弾",              # blow-up / ruin post-mortem
    "プロップファーム 手法 検証",             # prop-firm methods
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "EA パラメータ 設定 詳解",                # EA parameter settings, explained in detail
    "戦略 ソースコード 公開",                 # strategy source code, made public
    "トレードシステム 完全 ルール",           # complete trading system rules
    "コピートレード 手法 分解",               # copy-trading method, broken down
    "トップトレーダー 戦略 暴露",             # top trader's strategy, revealed
    "EA バックテスト パラメータ 最適化",      # EA backtest, parameter optimisation
    "ゴールド EA パラメータ 公開",            # gold EA, parameters disclosed
    "MQL5 シグナル 戦略 分析",                # MQL5 Signals -- a public copy-trading leaderboard
)

QUERIES_KO: Final[tuple[str, ...]] = (
    "퀀트 백테스트 과최적화",                 # overfitting
    "표본외 검증 실패",                       # out-of-sample failure
    "미래참조 편향 백테스트",                 # lookahead bias
    "생존편향 검증",                          # survivorship bias
    "팩터 유효성 소멸",                       # factor decay
    "금 XAUUSD 트레이딩 전략",                # gold / XAUUSD
    "외환 FX 알고리즘 전략 검증",             # forex algorithmic strategy
    "MT5 EA 자동매매 개발",                   # MT5 expert advisors
    "캐리 트레이드 스왑 금리차",              # carry / swap -- the funding analogue
    "선물 현물 베이시스 수렴",                # futures-cash basis convergence (index/gold)
    "COT 미결제약정 포지션 분석",             # COT positioning -- the whale-tracking analogue
    "주가지수 선물 전략",                     # equity-index futures
    "원유 상품 트레이딩 전략",                # energy / commodities
    "마켓메이킹 재고 리스크",                 # market-making inventory
    "호가창 슬리피지 체결",                   # book slippage / fills
    "런던 뉴욕 세션 외환 변동성",             # session structure
    "고용지표 비농업 외환 반응",              # NFP / macro-event reaction
    "실전 백테스트 괴리",                     # live-vs-backtest divergence
    # -- breadth parity with the CN lane (2026-08-18)
    "추세추종 트렌드 전략",                   # trend following
    "역추세 평균회귀 전략",                   # mean reversion
    "돌파 브레이크아웃 전략 검증",            # breakout
    "변동성 돌파 전략",                       # volatility breakout
    "그리드 매매 리스크 청산",                # grid trading risk
    "통계적 차익거래 페어트레이딩",           # statistical arbitrage / pairs
    "CTA 추세 전략 검증",                     # CTA
    "옵션 변동성 전략",                       # options vol
    "멀티팩터 모델 검증",                     # multi-factor
    "횡단면 팩터 알파",                       # cross-sectional factor
    "오더블록 기법 검증",                     # SMC order block
    "공정가치갭 FVG 기법",                    # SMC / ICT FVG
    "유동성 스윕 시장구조",                   # liquidity sweep / market structure
    "은 XAGUSD 트레이딩 전략",                # silver
    "달러엔 유로달러 트레이딩 전략",          # USDJPY / EURUSD
    "코스피200 나스닥 지수 전략",             # equity indices
    "런던 픽싱 실수요 플로우",                # London WMR fix flow
    "선물 롤오버 만기 거래",                  # futures roll
    "중앙은행 금리 결정 반응",                # central-bank event
    "주말 갭 리스크",                         # weekend gap risk
    "생산자 헤지 COT 상업",                   # producer hedging (COT commercial)
    "깡통 손절 복기 실전",                    # blow-up / ruin post-mortem
    "프랍 펌 기법 검증",                      # prop-firm methods
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "EA 파라미터 설정 상세",                  # EA parameter settings, explained in detail
    "전략 소스코드 공개",                     # strategy source code, made public
    "매매 시스템 완전한 규칙",                # complete trading system rules
    "카피 트레이딩 기법 분석",                # copy-trading method, broken down
    "탑 트레이더 전략 공개",                  # top trader's strategy, revealed
    "EA 백테스트 파라미터 최적화",            # EA backtest, parameter optimisation
    "골드 EA 파라미터 공개",                  # gold EA, parameters disclosed
    "MQL5 시그널 전략 분석",                  # MQL5 Signals -- a public copy-trading leaderboard
)

QUERIES_RU: Final[tuple[str, ...]] = (
    "бэктест переобучение проверка",          # overfitting
    "проверка вне выборки стратегия",         # out-of-sample validation
    "заглядывание в будущее бэктест",         # lookahead bias
    "ошибка выжившего тестирование",          # survivorship bias
    "фактор затухание доходности",            # factor decay
    "золото XAUUSD торговая стратегия",       # gold / XAUUSD
    "форекс алгоритмическая стратегия тест",  # forex algorithmic strategy
    "MT5 советник эксперт разработка",        # MT5 expert advisors
    "кэрри трейд своп разница ставок",        # carry / swap -- the funding analogue
    "базис фьючерс спот сходимость",          # futures-cash basis convergence (index/gold)
    "COT отчёт позиции анализ",               # COT positioning -- the whale-tracking analogue
    "индекс фьючерс торговая стратегия",      # equity-index futures
    "нефть сырьевые товары стратегия",        # energy / commodities
    "маркетмейкинг риск запасов",             # market-making inventory risk
    "проскальзывание стакан исполнение",      # slippage / book / execution
    "лондон нью-йорк сессия волатильность",   # session structure
    "макроэкономика ставка ЦБ реакция",       # central-bank macro reaction
    "реальная торговля отличие бэктеста",     # live-vs-backtest divergence
    # -- breadth parity with the CN lane (2026-08-18)
    "следование тренду стратегия",            # trend following
    "возврат к среднему стратегия",           # mean reversion
    "пробой уровня стратегия",                # breakout
    "волатильный пробой стратегия",           # volatility breakout
    "сеточная торговля риск слив",            # grid trading risk
    "статистический арбитраж пары",           # statistical arbitrage / pairs
    "CTA трендовая стратегия",                # CTA
    "опционы волатильность стратегия",        # options vol
    "мультифакторная модель проверка",        # multi-factor
    "кросс-секционный фактор альфа",          # cross-sectional factor
    "ордер блок метод проверка",              # SMC order block
    "гэп справедливой цены FVG",              # SMC / ICT FVG
    "снятие ликвидности структура рынка",     # liquidity sweep / market structure
    "серебро XAGUSD торговая стратегия",      # silver  # noqa: RUF001
    "доллар йена евродоллар стратегия",       # USDJPY / EURUSD
    "индекс насдак торговая стратегия",       # equity indices
    "лондонский фиксинг реальный поток",      # London WMR fix flow
    "ролловер фьючерс экспирация",            # futures roll
    "центробанк ставка решение реакция",      # central-bank event
    "выходной гэп риск",                      # weekend gap risk
    "хеджирование производителей COT",        # producer hedging (COT commercial)
    "слив депозита разбор стоп",              # blow-up / ruin post-mortem
    "проп фирма метод проверка",              # prop-firm methods
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "EA параметры настройка подробно",        # EA parameter settings, explained in detail
    "исходный код стратегии публикация",      # strategy source code, made public
    "торговая система полные правила",        # complete trading system rules
    "копитрейдинг метод разбор",              # copy-trading method, broken down
    "топ трейдер стратегия раскрыта",         # top trader's strategy, revealed
    "EA бэктест параметры оптимизация",       # EA backtest, parameter optimisation
    "золото EA параметры публикация",         # gold EA, parameters disclosed
    "MQL5 сигналы стратегия анализ",          # MQL5 Signals -- a public copy-trading leaderboard
)

#: language -> (queries, the source functions that speak it). Consulted by the miner so adding a
#: language is a table entry rather than a code path.
#: VIETNAMESE -- a lane the desk did not have at all. Vietnam has a large and vocal retail
#: forex/gold trading community that argues MT5/EA mechanics in Vietnamese only.
QUERIES_VI: Final[tuple[str, ...]] = (
    "backtest quá khớp tối ưu",              # overfitting a backtest
    "kiểm định ngoài mẫu chiến lược",        # out-of-sample validation
    "thiên lệch nhìn trước dữ liệu",         # look-ahead bias
    "thiên lệch kẻ sống sót kiểm định",      # survivorship bias
    "vàng XAUUSD chiến lược giao dịch",      # gold / XAUUSD
    "forex ngoại hối chiến lược thuật toán",  # forex algorithmic strategy
    "MT5 EA robot giao dịch phát triển",     # MT5 expert advisors
    "carry trade lãi suất swap qua đêm",     # carry / swap -- the funding analogue
    "basis hợp đồng tương lai giao ngay",    # futures/spot basis (index/gold)
    "COT báo cáo vị thế phân tích",          # COT positioning -- the whale-tracking analogue
    "chỉ số chứng khoán tương lai chiến lược",  # equity-index futures
    "dầu thô hàng hóa chiến lược giao dịch",  # energy / commodities
    "tạo lập thị trường rủi ro tồn kho",     # market-making inventory risk
    "trượt giá sổ lệnh khớp lệnh",           # slippage and order-book fills
    "phiên luân đôn new york biến động",     # session structure
    "chỉ báo quá khớp dữ liệu lịch sử",      # indicator overfit to history
    "quản lý vốn kelly rủi ro phá sản",      # Kelly sizing / ruin risk
    # -- breadth parity with the CN lane (2026-08-18)
    "theo xu hướng trend following",          # trend following
    "hồi quy trung bình chiến lược",          # mean reversion
    "phá vỡ breakout chiến lược",             # breakout
    "phá vỡ biến động chiến lược",            # volatility breakout
    "giao dịch lưới rủi ro cháy",             # grid trading risk
    "kinh doanh chênh lệch thống kê cặp",     # statistical arbitrage / pairs
    "CTA chiến lược xu hướng",                # CTA
    "quyền chọn biến động chiến lược",        # options vol
    "mô hình đa nhân tố kiểm định",           # multi-factor
    "nhân tố cắt ngang alpha",                # cross-sectional factor
    "order block phương pháp",                # SMC order block
    "khoảng trống giá trị hợp lý FVG",        # SMC / ICT FVG
    "quét thanh khoản cấu trúc thị trường",   # liquidity sweep / market structure
    "bạc XAGUSD chiến lược giao dịch",        # silver
    "đô la yên euro đô la chiến lược",        # USDJPY / EURUSD
    "chỉ số nasdaq chiến lược giao dịch",     # equity indices
    "phiên định giá luân đôn dòng tiền",      # London WMR fix flow
    "đáo hạn hợp đồng tương lai giao dịch",   # futures roll
    "ngân hàng trung ương lãi suất phản ứng",  # central-bank event
    "khoảng trống cuối tuần rủi ro",          # weekend gap risk
    "phòng hộ nhà sản xuất COT",              # producer hedging (COT commercial)
    "cháy tài khoản dừng lỗ rút kinh nghiệm",  # blow-up / ruin post-mortem
    "prop firm phương pháp kiểm định",        # prop-firm methods
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "EA cài đặt tham số chi tiết",            # EA parameter settings, explained in detail
    "mã nguồn chiến lược công khai",          # strategy source code, made public
    "hệ thống giao dịch quy tắc đầy đủ",      # complete trading system rules
    "copy trade phương pháp phân tích",       # copy-trading method, broken down
    "chiến lược trader hàng đầu tiết lộ",     # top trader's strategy, revealed
    "EA backtest tối ưu tham số",             # EA backtest, parameter optimisation
    "vàng EA tham số công khai",              # gold EA, parameters disclosed
    "MQL5 tín hiệu chiến lược phân tích",     # MQL5 Signals -- a public copy-trading leaderboard
)

#: TURKISH -- Turkey has a large retail trading community, and lira-pair microstructure (a
#: currency under sustained pressure: USDTRY, EURTRY) is exactly the MT5/FX universe and a
#: mechanism family the English-language forests barely discuss.
QUERIES_TR: Final[tuple[str, ...]] = (
    "backtest aşırı optimizasyon",           # overfitting  # noqa: RUF001
    "örneklem dışı test strateji",           # out-of-sample testing  # noqa: RUF001
    "ileriye bakma yanlılığı",               # look-ahead bias  # noqa: RUF001
    "hayatta kalma yanlılığı test",          # survivorship bias  # noqa: RUF001
    "altın XAUUSD işlem stratejisi",         # gold / XAUUSD  # noqa: RUF001
    "forex döviz algoritmik strateji",       # forex algorithmic strategy
    "MT5 uzman danışman geliştirme",         # MT5 expert advisors  # noqa: RUF001
    "carry trade swap faiz farkı",           # carry / swap -- the funding analogue  # noqa: RUF001
    "vadeli spot baz farkı yakınsama",       # futures/spot basis (index/gold)  # noqa: RUF001
    "COT raporu pozisyon analizi",           # COT positioning -- the whale-tracking analogue
    "endeks vadeli işlem stratejisi",        # equity-index futures
    "petrol emtia işlem stratejisi",         # energy / commodities
    "emir defteri kayma slipaj",             # order-book slippage
    "piyasa yapıcılığı envanter riski",      # market-making inventory risk  # noqa: RUF001
    "londra new york seans volatilite",      # session structure
    "lira paritesi döviz volatilite",        # lira-pair FX -- kept: it IS the MT5 universe
    "kelly kriteri pozisyon büyüklüğü",      # Kelly sizing
    "gerçek işlem backtest sapması",         # live-vs-backtest divergence  # noqa: RUF001
    # -- breadth parity with the CN lane (2026-08-18)
    "trend takip stratejisi",                # trend following
    "ortalamaya dönüş stratejisi",           # mean reversion
    "kırılım breakout stratejisi",           # breakout  # noqa: RUF001
    "volatilite kırılımı stratejisi",        # volatility breakout  # noqa: RUF001
    "grid işlem riski patlama",              # grid trading risk
    "istatistiksel arbitraj çift işlem",     # statistical arbitrage / pairs
    "CTA trend stratejisi testi",            # CTA
    "opsiyon volatilite stratejisi",         # options vol
    "çok faktörlü model testi",              # multi-factor
    "kesitsel faktör alfa",                  # cross-sectional factor
    "order block yöntemi testi",             # SMC order block
    "adil değer boşluğu FVG yöntemi",        # SMC / ICT FVG
    "likidite süpürme piyasa yapısı",        # liquidity sweep / market structure  # noqa: RUF001
    "gümüş XAGUSD işlem stratejisi",         # silver
    "dolar yen euro dolar stratejisi",       # USDJPY / EURUSD
    "endeks nasdaq işlem stratejisi",        # equity indices
    "londra fixing gerçek akışı",            # London WMR fix flow  # noqa: RUF001
    "vadeli sözleşme rollover vade",         # futures roll
    "merkez bankası faiz kararı tepki",      # central-bank event  # noqa: RUF001
    "hafta sonu boşluk riski",               # weekend gap risk
    "üretici hedge COT ticari",              # producer hedging (COT commercial)
    "hesap patlatma stop loss ders",         # blow-up / ruin post-mortem
    "prop firma yöntem testi",               # prop-firm methods
    # -- SECRET-SAUCE REVEALS (2026-08-20): named, reproducible systems, not validation commentary
    "EA parametre ayarları detaylı",          # EA parameter settings, explained in detail  # noqa: RUF001, E501
    "strateji kaynak kodu paylaşım",          # strategy source code, made public  # noqa: RUF001
    "işlem sistemi tam kurallar",             # complete trading system rules
    "kopya işlem yöntemi analiz",             # copy-trading method, broken down
    "üst düzey trader stratejisi ifşa",       # top trader's strategy, revealed
    "EA backtest parametre optimizasyonu",    # EA backtest, parameter optimisation
    "altın EA parametreleri paylaşım",        # gold EA, parameters disclosed  # noqa: RUF001
    "MQL5 sinyal strateji analizi",           # MQL5 Signals -- a public copy-trading leaderboard
)


LANGUAGES: Final[dict[str, tuple[str, ...]]] = {
    "ja": QUERIES_JA,
    "ko": QUERIES_KO,
    "ru": QUERIES_RU,
    "vi": QUERIES_VI,
    "tr": QUERIES_TR,
}


# ------------------------------------------------------------------------------------ helpers

_LAST_CALL: dict[str, float] = {}


def _pace(source: str) -> None:
    """Sleep just long enough that this source's minimum interval is respected."""
    gap = _MIN_INTERVAL_S.get(source, 1.0)
    last = _LAST_CALL.get(source)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _LAST_CALL[source] = time.monotonic()


def _backed_off(source: str) -> tuple[list[Article], str] | None:
    """A short-circuit for a source that already answered 429 in this process."""
    if source in _BACKED_OFF:
        return [], (f"{source} returned HTTP 429 earlier in this run -- backed off for the rest "
                    "of it rather than hammering a source that asked for a pause")
    return None


def _note_429(source: str, exc: Exception) -> None:
    if getattr(exc, "code", None) == 429:
        _BACKED_OFF.add(source)


def _get(url: str, *, referer: str = "", timeout: float = 25.0) -> str:
    hdr = dict(_UA)
    if referer:
        hdr["Referer"] = referer
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def _post(url: str, payload: bytes, *, timeout: float = 20.0) -> str:
    """POST for the GraphQL-only sources. Same UA and timeout discipline as _get.

    Velog exposes search ONLY over GraphQL, and refusing to speak POST would have meant recording
    Korea's largest engineering-writeup platform as unreachable when it answers fine -- a routing
    problem misfiled as an absent forest (L1.54).
    """
    req = urllib.request.Request(
        url, data=payload, headers={**_UA, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(resp.read().decode("utf-8", errors="replace"))



def _text(raw: str) -> str:
    """Strip tags, drop CDATA wrappers, decode entities, collapse whitespace -- IN THAT ORDER.

    The order is load-bearing and Hatena is the proof: its RSS titles arrive as numeric character
    references (`&#x306B;`), so an undecoded title contains no Japanese at all as far as the
    triage ranker is concerned and scores zero. Decoding BEFORE stripping would be the opposite
    error -- an encoded `&lt;b&gt;` would become a real tag that the stripper then eats, deleting
    text that was never markup.
    """
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _rss_items(body: str) -> list[str]:
    """Item blocks from RSS 2.0 or RDF/RSS 1.0. Hatena serves the latter, Habr the former."""
    return re.findall(r"<item[^>]*>(.*?)</item>", body, flags=re.S)


def _tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", block, flags=re.S)
    return _text(m.group(1)) if m else ""


def _err(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:140]}"


# ------------------------------------------------------------------------------- JAPANESE (ja)

def qiita(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """Qiita -- Japan's largest engineering-writeup community. Keyless JSON API.

    Only rows carrying both a title and an id are kept, so an API shape change degrades to fewer
    results rather than to rows with empty titles that the ranker would score as zero and the
    desk would read as "nothing found in Japanese".
    """
    hit = _backed_off("qiita")
    if hit is not None:
        return hit
    _pace("qiita")
    url = f"https://qiita.com/api/v2/items?query={quote(keyword)}&per_page={int(limit)}"
    try:
        rows = json.loads(_get(url))
    except Exception as exc:
        _note_429("qiita", exc)
        return [], _err(exc)
    if not isinstance(rows, list):
        return [], "qiita returned a non-list payload -- API shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title, ident = _text(str(r.get("title") or "")), str(r.get("id") or "")
        if not title or not ident:
            continue
        tags = " ".join(str(t.get("name", "")) for t in (r.get("tags") or [])
                        if isinstance(t, dict))
        out.append(Article(source="qiita", ident=ident, title=title,
                           url=str(r.get("url") or f"https://qiita.com/items/{ident}"),
                           author=str((r.get("user") or {}).get("id") or ""),
                           snippet=f"{tags} {_text(str(r.get('body') or ''))[:360]}".strip()))
    return out, None


def zenn(keyword: str) -> tuple[list[Article], str | None]:
    """Zenn -- the newer Japanese engineering publication platform. Keyless JSON."""
    hit = _backed_off("zenn")
    if hit is not None:
        return hit
    _pace("zenn")
    url = f"https://zenn.dev/api/articles?keyword={quote(keyword)}&order=latest"
    try:
        doc = json.loads(_get(url))
    except Exception as exc:
        _note_429("zenn", exc)
        return [], _err(exc)
    out: list[Article] = []
    for r in (doc.get("articles") or []) if isinstance(doc, dict) else []:
        if not isinstance(r, dict):
            continue
        title, path = _text(str(r.get("title") or "")), str(r.get("path") or "")
        if not title or not path:
            continue
        out.append(Article(source="zenn", ident=str(r.get("id") or path), title=title,
                           url=f"https://zenn.dev{path}",
                           author=str((r.get("user") or {}).get("username") or ""),
                           snippet=str(r.get("article_type") or "")))
    return out, None


def hatena(keyword: str) -> tuple[list[Article], str | None]:
    """Hatena Bookmark search as RSS -- what Japanese engineers SAVE, not merely what they wrote.

    A bookmark count is a weak crowd filter the other sources do not carry, and it is orthogonal
    to the triage ranker's vocabulary scoring: one measures what practitioners thought worth
    keeping, the other measures what the text says.
    """
    hit = _backed_off("hatena")
    if hit is not None:
        return hit
    _pace("hatena")
    url = f"https://b.hatena.ne.jp/search/text?q={quote(keyword)}&mode=rss"
    try:
        body = _get(url)
    except Exception as exc:
        _note_429("hatena", exc)
        return [], _err(exc)
    out: list[Article] = []
    for block in _rss_items(body):
        title = _tag(block, "title")
        link = _tag(block, "link")
        if not title or not link:
            continue
        out.append(Article(source="hatena", ident=link[-40:], title=title, url=link,
                           snippet=_tag(block, "description")[:360]))
    if not out:
        return [], "hatena RSS fetched but no <item> blocks parsed -- feed shape changed"
    return out, None


# --------------------------------------------------------------------------------- KOREAN (ko)

def dcinside(keyword: str) -> tuple[list[Article], str | None]:
    """DCInside post search -- Korea's largest forum, and where the KR premium is discussed.

    Server-rendered HTML, so the parse is deliberately shallow (link + title text) and degrades to
    zero results rather than to wrong ones when the markup shifts. This desk MEASURES the Korean
    venue premium as a mechanism class and had never read a word written by the participants
    creating it, which is a strange asymmetry for a lane it already screens.
    """
    hit = _backed_off("dcinside")
    if hit is not None:
        return hit
    _pace("dcinside")
    url = f"https://search.dcinside.com/post/q/{quote(keyword)}"
    try:
        body = _get(url, referer="https://search.dcinside.com/")
    except Exception as exc:
        _note_429("dcinside", exc)
        return [], _err(exc)
    out: list[Article] = []
    seen: set[str] = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*class="tit_txt"[^>]*>(.*?)</a>',
                         body, flags=re.S):
        href, title = m.group(1), _text(m.group(2))
        if not title or href in seen:
            continue
        seen.add(href)
        out.append(Article(source="dcinside", ident=href[-40:], title=title,
                           url=href if href.startswith("http") else f"https:{href}"))
    if not out:
        # The class attribute may precede href; try the other order before reporting empty. A
        # regex that demanded one attribute order is exactly how the Sogou parser lost a working
        # source for a week, and that lesson is cheaper to reuse than to relearn.
        for m in re.finditer(r'<a[^>]+class="tit_txt"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                             body, flags=re.S):
            href, title = m.group(1), _text(m.group(2))
            if title and href not in seen:
                seen.add(href)
                out.append(Article(source="dcinside", ident=href[-40:], title=title,
                                   url=href if href.startswith("http") else f"https:{href}"))
    if not out:
        # AN EMPTY RESULT IS NOT A BROKEN PARSER, and conflating them sends the next reader to
        # the wrong place entirely: "markup changed" says go rewrite the regex, "no results" says
        # the query found nothing and the source is fine. DCInside says so on the page itself.
        # Found by running it -- 4 of 17 Korean queries reported "markup changed" while the same
        # parser worked on the other 13, which is the signature of a false diagnosis rather than
        # a real break.
        if "결과가 없" in body or "검색결과가 없" in body:
            return [], None
        return [], "dcinside page fetched but no result links parsed -- markup changed"
    return out, None


# -------------------------------------------------------------------------------- RUSSIAN (ru)

def habr(keyword: str) -> tuple[list[Article], str | None]:
    """Habr search via RSS.

    THE HTML SEARCH PAGE IS A JS SHELL -- probed 2026-08-05: 39KB with zero parseable result
    links. A desk that stopped there records "Habr: client-rendered, blocked" and loses a Russian
    corpus permanently. The SAME query served as RSS returns 20 items in one keyless request.
    L1.54 clause 6: a shut door named a ROUTE, not the source, and finding that out cost one probe.
    """
    hit = _backed_off("habr")
    if hit is not None:
        return hit
    _pace("habr")
    url = f"https://habr.com/ru/rss/search/?q={quote(keyword)}&target_type=posts&order=relevance"
    try:
        body = _get(url)
    except Exception as exc:
        _note_429("habr", exc)
        return [], _err(exc)
    out: list[Article] = []
    for block in _rss_items(body):
        title, link = _tag(block, "title"), _tag(block, "link")
        if not title or not link:
            continue
        out.append(Article(source="habr", ident=link[-40:], title=title, url=link,
                           author=_tag(block, "dc:creator"),
                           snippet=_tag(block, "description")[:360]))
    if not out:
        return [], "habr RSS fetched but no <item> blocks parsed -- feed shape changed"
    return out, None


#: source name -> (callable, language). The miner iterates this rather than a hardcoded list, so a
#: new forest is one entry and its queries, never a new branch in the mining loop.


# ======================================================================= THE DEEP LOCAL FORESTS
# WHY THESE AND NOT MORE BLOG PLATFORMS. Qiita, Zenn, Habr and the rest above are POLISHED
# publication venues: people write there to be seen being competent, so the failure literature --
# the part that is actually worth mining -- is systematically under-represented. The candid
# material lives on FORUMS, where practitioners complain, post their losses, argue about fills and
# name the venue that front-ran them. That is the register the Chinese lane already reaches through
# Bilibili comment culture, and every non-Chinese lane was missing it entirely.
#
# EACH SOURCE IS A LOCAL FOREST, not a translation of an English one. A Russian algo trader posts
# on smart-lab, not on Reddit; a Korean crypto trader posts on Coinpan, not on Bitcointalk. The
# whole point of a foreign lane is the material that never crosses into English, and it is exactly
# that material which sits behind a forum login-wall culture rather than an API.
#
# A BLOCKED SOURCE IS RECORDED, NEVER DROPPED. Several of these sit behind anti-bot layers that
# may answer 403 or serve a challenge page. `probe_all` marks such a lane BLOCKED with the reason,
# and it stays in the roster: a lane nobody can reach today is a routing problem to solve, not a
# verdict that the forest is empty (L1.54). Dropping it from SOURCES would erase the evidence that
# it was ever wanted.


def note(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """note.com -- where Japan's `botter` community actually publishes.

    The single highest-value Japanese venue for this desk: Japanese crypto bot operators write
    post-mortems here, including the losses, in a way they do not on Qiita. Keyless JSON search.
    """
    hit = _backed_off("note")
    if hit is not None:
        return hit
    _pace("note")
    # `searches`, NOT `searchs` -- corrected 2026-08-12. The misspelling 404s, and an 18-query
    # sweep recording "404 Not Found" every run reads as a DEAD ENDPOINT when the endpoint is
    # alive and REFUSING us: the correct path answers 403 with a structured
    # {"error":{"message":"Access denied","type":"forbidden"}}. Those are different problems with
    # different fixes -- a 404 says stop looking, a 403 says find credentials or another route --
    # and the desk was recording the one that closes the investigation.
    #
    # This is the eksisozluk defect in a second source, found the same day by the same question:
    # does a UNIFORM failure across every query really describe the site, or does it describe our
    # URL? Fixing it does not unblock note.com; it makes the recorded blocker TRUE, which is what
    # decides whether the next reader hunts a route or writes the source off.
    url = ("https://note.com/api/v3/searches?context=note&mode=search&size="
           f"{int(limit)}&q={quote(keyword)}")
    try:
        doc = json.loads(_get(url))
    except Exception as exc:
        _note_429("note", exc)
        return [], _err(exc)
    data = doc.get("data") if isinstance(doc, dict) else None
    notes = (data or {}).get("notes") if isinstance(data, dict) else None
    rows = notes.get("contents") if isinstance(notes, dict) else notes
    if not isinstance(rows, list):
        return [], "note.com returned no `data.notes.contents` list -- API shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title, key = _text(str(r.get("name") or "")), str(r.get("key") or r.get("id") or "")
        if not title or not key:
            continue
        _u = r.get("user")
        user: dict[str, Any] = _u if isinstance(_u, dict) else {}
        urlname = str(user.get("urlname") or "")
        out.append(Article(source="note", ident=key, title=title,
                           url=str(r.get("noteUrl") or f"https://note.com/{urlname}/n/{key}"),
                           author=urlname,
                           snippet=_text(str(r.get("body") or r.get("description") or ""))[:360]))
    return out, None


def velog(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """Velog -- the Korean engineering-writeup platform. GraphQL, keyless.

    Korea's Qiita. Paired with Coinpan below it covers both registers: the polished writeup and
    the trading-floor argument.
    """
    hit = _backed_off("velog")
    if hit is not None:
        return hit
    _pace("velog")
    # DIRECT ARGUMENTS, not an input object. The input-object form is what the schema browser
    # suggests and it answers HTTP 400; measured against the live endpoint, `searchPosts` takes
    # keyword/offset/limit at the top level. Recorded because a 400 here is indistinguishable from
    # a dead source unless somebody has checked.
    query = ("query($keyword:String!,$offset:Int,$limit:Int){"
             "searchPosts(keyword:$keyword,offset:$offset,limit:$limit){"
             "posts{id title short_description url_slug user{username}}}}")
    payload = json.dumps({
        "query": query,
        "variables": {"keyword": keyword, "offset": 0, "limit": int(limit)}}).encode()
    try:
        raw = _post("https://v2cdn.velog.io/graphql", payload)
        doc = json.loads(raw)
    except Exception as exc:
        _note_429("velog", exc)
        return [], _err(exc)
    if isinstance(doc, dict) and doc.get("errors"):
        return [], f"velog GraphQL errors: {str(doc['errors'])[:140]}"
    node = ((doc.get("data") or {}).get("searchPosts") or {}) if isinstance(doc, dict) else {}
    rows = node.get("posts")
    if not isinstance(rows, list):
        return [], "velog returned no data.searchPosts.posts list -- GraphQL shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = _text(str(r.get("title") or ""))
        slug, ident = str(r.get("url_slug") or ""), str(r.get("id") or "")
        if not title or not ident:
            continue
        _u = r.get("user")
        user: dict[str, Any] = _u if isinstance(_u, dict) else {}
        who = str(user.get("username") or "")
        out.append(Article(source="velog", ident=ident, title=title,
                           url=f"https://velog.io/@{who}/{slug}" if who and slug
                               else f"https://velog.io/search?q={quote(keyword)}",
                           author=who,
                           snippet=_text(str(r.get("short_description") or ""))[:360]))
    return out, None


def coinpan(keyword: str) -> tuple[list[Article], str | None]:
    """Coinpan (코인판) -- Korea's crypto forum, and a genuine dark forest.

    The kimchi-premium trade, Upbit/Bithumb listing mechanics and the domestic arbitrage routes are
    discussed here in a detail that never reaches English. HTML search, so the parser is deliberate
    about distinguishing "no results" from "markup changed" -- collapsing those is how a live
    source gets recorded as dead.
    """
    hit = _backed_off("coinpan")
    if hit is not None:
        return hit
    _pace("coinpan")
    url = ("https://coinpan.com/index.php?mid=free&search_target=title"
           f"&search_keyword={quote(keyword)}")
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("coinpan", exc)
        return [], _err(exc)
    rows = re.findall(
        r'<a href="(/(?:free|index\.php)[^"]*document_srl=(\d+)[^"]*)"[^>]*>(.*?)</a>',
        page, flags=re.S)
    if not rows:
        if re.search(r"검색결과|내용이 없|게시물이 없", page):
            return [], None                    # a MEASURED empty result, not a parser failure
        return [], "coinpan fetched but no document links parsed -- markup changed or challenged"
    out: list[Article] = []
    seen: set[str] = set()
    for href, srl, raw_title in rows:
        title = _text(raw_title)
        if not title or srl in seen:
            continue
        seen.add(srl)
        out.append(Article(source="coinpan", ident=srl, title=title,
                           url=f"https://coinpan.com{href}" if href.startswith("/") else href))
    return out, None


def vcru(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """vc.ru -- Russian tech/finance long-form with an open JSON search."""
    hit = _backed_off("vcru")
    if hit is not None:
        return hit
    _pace("vcru")
    url = f"https://api.vc.ru/v2.1/search?q={quote(keyword)}&sorting=date&count={int(limit)}"
    try:
        doc = json.loads(_get(url))
    except Exception as exc:
        _note_429("vcru", exc)
        return [], _err(exc)
    # `items` AT THE TOP LEVEL. The documented envelope is `result`, and the live endpoint does not
    # use it -- measured 2026-08-05, both v2.1 and v2.5 answer `{"items": [...]}`. Both spellings
    # are accepted so a rollback of theirs is not an outage of ours.
    rows = None
    if isinstance(doc, dict):
        rows = doc.get("items")
        if rows is None:
            res = doc.get("result")
            rows = res.get("items") if isinstance(res, dict) else res
    if not isinstance(rows, list):
        keys = sorted(doc)[:6] if isinstance(doc, dict) else "?"
        return [], f"vc.ru returned no item list (top keys: {keys})"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        _d = r.get("data")
        data: dict[str, Any] = _d if isinstance(_d, dict) else r
        title = _text(str(data.get("title") or ""))
        ident = str(data.get("id") or "")
        if not title or not ident:
            continue
        out.append(Article(source="vcru", ident=ident, title=title,
                           url=str(data.get("url") or f"https://vc.ru/{ident}"),
                           snippet=_text(str(data.get("intro") or ""))[:360]))
    return out, None


def smartlab(keyword: str) -> tuple[list[Article], str | None]:
    """smart-lab.ru -- the Russian retail-algo trading forum.

    Russia's densest concentration of people who actually run systematic strategies and post the
    equity curves when they break. HTML search.
    """
    hit = _backed_off("smartlab")
    if hit is not None:
        return hit
    _pace("smartlab")
    url = f"https://smart-lab.ru/search/?q={quote(keyword)}"
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("smartlab", exc)
        return [], _err(exc)
    # PROMOTED COMPANY BLOGS ARE NOT SEARCH RESULTS, and a parser that cannot tell the difference
    # is worse than one that returns nothing. Measured 2026-08-05: smart-lab's search page ships
    # NO results in its HTML -- they are fetched by script -- while the sidebar carries five
    # /company/<name>/blog/<id>.php promos on every page regardless of query. A naive link regex
    # returned those five as "results", so a query about backtesting produced Russian corporate
    # news and the lane looked healthy while indexing noise. That is a fail-OPEN in the one
    # direction a miner must never fail: fabricated yield hides a dead source forever.
    rows = re.findall(
        r'<a[^>]+href="(https?://smart-lab\.ru/(?!company/)[^"]+/(\d+)\.php)"[^>]*>(.*?)</a>',
        page, flags=re.S)
    if not rows:
        if re.search(r"ничего не найден|нет результат", page, flags=re.I):
            return [], None                    # a MEASURED empty result
        return [], ("smart-lab search results are rendered by script, not served in HTML -- the "
                    "page carries only sidebar company-blog promos, which are NOT results. Needs "
                    "a render path (Chromium is present) or the forum's own RSS per section; "
                    "recorded as a ROUTING problem, never as an empty forest")
    out: list[Article] = []
    seen: set[str] = set()
    for href, ident, raw_title in rows:
        title = _text(raw_title)
        if not title or ident in seen:
            continue
        seen.add(ident)
        out.append(Article(source="smartlab", ident=ident, title=title, url=href))
    return out, None


def tinhte(keyword: str) -> tuple[list[Article], str | None]:
    """Tinh te -- Vietnam's largest tech community. Vietnamese is a real crypto-retail forest and
    the desk had NO Vietnamese lane at all.

    BLOCKED, DIAGNOSED PRECISELY 2026-08-19 (was previously mislabelled "markup changed or
    challenged", which is wrong on both counts -- verified live from this box). `GET
    /search/?q=X` returns a normal 52KB XenForo page with NO challenge markers and NO auth wall,
    but the query is never echoed anywhere in the response -- the GET does not execute a search
    at all; it silently returns the generic empty search-landing page. This is standard XenForo
    2.x behaviour: a real search needs a CSRF token pulled from an initial page load, then a POST
    to /search/search carrying that token and a session cookie. Same class of blocker as Bilibili
    WBI signing (libs/data/bilibili.wbi_keys) -- a request-signature/token gate, not a markup
    problem and not an anti-bot challenge. Fixing this needs the two-step token+POST flow, not a
    regex change; recorded here rather than left as a vague "challenged" guess.
    """
    hit = _backed_off("tinhte")
    if hit is not None:
        return hit
    _pace("tinhte")
    url = f"https://tinhte.vn/search/?q={quote(keyword)}"
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("tinhte", exc)
        return [], _err(exc)
    # XenForo migrated /thread/N/ (singular) -> /threads/slug.N/ (plural) at some point; matched
    # here for when the CSRF+POST flow above is built, though today's GET-only fetch never
    # populates real results so this rarely has anything to match against either way.
    rows = re.findall(r'<a[^>]+href="(/threads?/[^"]+\.(\d+)/?)"[^>]*>(.*?)</a>', page, flags=re.S)
    if not rows:
        if re.search(r"không tìm thấy|không có kết quả", page, flags=re.I):
            return [], None
        return [], ("tinhte GET search does not execute (query never echoed in the response) -- "
                    "needs a CSRF-token POST flow, same class as Bilibili WBI signing; not a "
                    "markup change and not a challenge page")
    out: list[Article] = []
    seen: set[str] = set()
    for href, ident, raw_title in rows:
        title = _text(raw_title)
        if not title or ident in seen:
            continue
        seen.add(ident)
        out.append(Article(source="tinhte", ident=ident, title=title,
                           url=f"https://tinhte.vn{href}"))
    return out, None


def eksisozluk(keyword: str) -> tuple[list[Article], str | None]:
    """Eksi Sozluk -- Turkey's collaborative dictionary, and the country's real public square.

    Turkish crypto retail is enormous relative to the economy and argues here rather than on a
    forum. Heavy anti-bot; a challenge page is reported as a BLOCKER, never as an empty forest.
    """
    hit = _backed_off("eksisozluk")
    if hit is not None:
        return hit
    _pace("eksisozluk")
    # SEARCH PATH, MEASURED 2026-08-12 -- not the site root. `/?q=` answered 404 on all 17 queries
    # of the 2026-08-12 sweep and 403 on a direct probe, which had been read as "Turkey blocks us".
    # It is neither: the root simply is not the search route. `/basliklar/ara?SearchForm.Keywords=`
    # answers 200 with 60KB of real threads. A uniform 404 across every query of a live site is the
    # signature of a URL bug, never of a hostile source -- the same class as the CJK \b bug and the
    # Sogou attribute-order bug, and the third time this desk has mistaken its own construction
    # error for a blocked forest.
    url = f"https://eksisozluk.com/basliklar/ara?SearchForm.Keywords={quote(keyword)}"
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("eksisozluk", exc)
        return [], _err(exc)
    # SCOPED TO THE RESULTS LIST, not the whole page. Matching every `--<id>` link site-wide
    # also collects the footer's "sozluk kurallari" and "kariyer" -- permanent chrome that would
    # be re-surfaced as a fresh candidate on every query of every run, quietly poisoning the seen
    # ledger and the yield ratio with two rows that are never research.
    #
    # THE SOURCE DECLARES ITS OWN RESULT COUNT in its results heading, and that count is the
    # arbiter of the three states L1.41 insists on separating. A zero-result query renders NO
    # topic-list at all (just a short "nothing here" line), so "no container" cannot by itself
    # tell a genuine empty result from a markup change. Reading the declared count settles it:
    #   N == 0 and no rows  -> RAN AND FOUND NOTHING (empty, no error)
    #   N  > 0 and no rows  -> PARSER DEFECT (loud), because the source says it has threads
    declared = re.search(r'<h2 title="(\d+)\s+başlık"', page)  # noqa: RUF001
    n_declared = int(declared.group(1)) if declared else None
    block = re.search(r'<ul class="topic-list[^"]*"[^>]*>(.*?)</ul>', page, flags=re.S)
    rows = (re.findall(r'<a[^>]+href="(/[^"?]+--(\d+))"[^>]*>(.*?)</a>', block.group(1), flags=re.S)
            if block else [])
    if not rows:
        if n_declared == 0:
            return [], None
        if n_declared is None:
            return [], ("eksisozluk fetched but neither a result count nor a topic-list parsed -- "
                        "markup changed or challenged")
        return [], (f"eksisozluk declares {n_declared} thread(s) but none parsed -- PARSER DEFECT, "
                    "not an empty source")
    out: list[Article] = []
    seen: set[str] = set()
    for href, ident, raw_title in rows:
        title = _text(raw_title)
        if not title or ident in seen:
            continue
        seen.add(ident)
        out.append(Article(source="eksisozluk", ident=ident, title=title,
                           url=f"https://eksisozluk.com{href}"))
    return out, None


SOURCES: Final[dict[str, tuple[Any, str]]] = {
    # POLISHED PUBLICATION VENUES -- competence on display, failure under-represented.
    "qiita": (qiita, "ja"),
    "zenn": (zenn, "ja"),
    "hatena": (hatena, "ja"),
    "habr": (habr, "ru"),
    "velog": (velog, "ko"),
    "vcru": (vcru, "ru"),
    # THE DEEP LOCAL FORESTS -- where practitioners are candid, which is the material worth mining.
    "note": (note, "ja"),
    "dcinside": (dcinside, "ko"),
    "coinpan": (coinpan, "ko"),
    "smartlab": (smartlab, "ru"),
    "tinhte": (tinhte, "vi"),
    "eksisozluk": (eksisozluk, "tr"),
}


def probe_all() -> list[dict[str, Any]]:
    """One cheap query per source, for the health ledger. Same contract as cn_sources.probe_all.

    `ok` means the source returned USABLE ROWS, never merely that it answered with HTTP 200 -- a
    200 carrying an anti-bot page is not a working source, and recording it as one is how a dead
    lane stays green on a dashboard.

    THREE STATES, NOT TWO -- and the third was invisible until 2026-08-12. `ok` alone collapses
    "answered cleanly, has nothing for THIS probe keyword" into the same cell as "returned
    nothing and did not say why", so the report showed `ok:false, error:null` for eksisozluk
    (healthy, genuinely no thread for the probe term) and for velog and vcru alike. That is the
    L1.41 failure inside the health layer itself.

    It is not cosmetic: source_health reads these rows and hunt_source_alternatives goes shopping
    for replacements for whatever has been dead N runs running. A working-but-narrow source that
    reads as indistinguishable-from-blocked sends the alternatives hunter after a source that
    needs nothing, while a genuinely dead one looks identical to it. `state` separates them:

        OK       usable rows returned
        EMPTY    answered cleanly, no rows for this probe keyword -- NOT a fault
        BLOCKED  refused, errored, or returned an unparseable body

    `ok` keeps its old meaning for existing consumers; `state` is what a reader should trust.
    """
    out: list[dict[str, Any]] = []
    for name, (fn, lang) in SOURCES.items():
        probe_kw = LANGUAGES[lang][0]
        try:
            arts, err = fn(probe_kw)
        except Exception as exc:
            out.append({"source": name, "lang": lang, "ok": False, "n": 0,
                        "state": "BLOCKED", "error": _err(exc)})
            continue
        state = "BLOCKED" if err else ("OK" if arts else "EMPTY")
        row: dict[str, Any] = {"source": name, "lang": lang,
                               "ok": bool(arts) and err is None,
                               "n": len(arts), "state": state, "error": err}
        if state == "EMPTY":
            row["why"] = (f"answered cleanly with no rows for the probe keyword {probe_kw!r}. "
                          "That is a fact about the KEYWORD, not a fault in the source -- do not "
                          "hunt a replacement for it on this evidence")
        out.append(row)
    return out
