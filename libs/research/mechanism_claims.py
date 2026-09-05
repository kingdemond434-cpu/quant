"""Mechanism claims out of text in every language the desk mines -- the whole world, one grammar.

    a CLAIM  =  a sentence that names a market QUANTITY, a DIRECTION and a HORIZON

That is the whole grammar, and it is deliberately shallow. A trader's interview, a competition
write-up, a forum reply or a README does not state a family and parameters; it states that
"gold usually reverses after the night-session open when the day range is already wide", and
the value of the sentence is that it is FALSIFIABLE on bars the desk already holds. Everything
richer than this -- the exact rule, the parameters, the instrument mapping -- is the deepening
worker's job, through the compiler's existing contract, so nothing here can invent a family.

WHY EVERY LANGUAGE IS FIRST-CLASS (principal, 2026-09-05: "deep forests in ALL major languages
... widen deep-forest to full global, 100 percent"). The Chinese forest was the proof: a large
practitioner literature the English-speaking crowd never reads, and even a dubious trading story
names a testable mechanism. The same argument holds for Japanese botters, Korean futures boards,
Taiwanese option writers, Vietnamese derivatives forums, Brazilian B3 traders, Polish GPW boards,
Turkish lira desks and Russian smart-lab -- and a claim extractor that speaks only English and
Chinese reports every other forest as empty, which is the L1.28a failure: absence
indistinguishable from emptiness. Vocabulary here is per language, SEEDS NEVER BOUNDARIES; a
region's frontier seat extends its own list (docs/research/search_operator_library.md OP-041).

INSTRUMENTS ARE MAPPED, NEVER INVENTED. A story about 沪金 is a story about gold; the desk trades
XAUUSD. Every candidate symbol in `INSTRUMENT_ALIASES` is a name Fusion actually quotes
(desks/mt5/data/universe/universe.json, first candidate first); instruments with no Fusion
analogue (螺纹钢, KOSPI, Nifty, IHSG, WIG20 ...) are kept as MECHANISM-CLASS transfers -- the
mechanism is the fuel, the instrument is whatever the desk can actually quote -- and the row says
so. A claim with NO analogue AND no transfer note is dropped and COUNTED (`dropped_unmappable`):
a summary nobody can test is not a hypothesis.

INDIRECT EDGES ARE THE POINT. "Brazilian soy exports" is a claim about USDBRL, "the CBRT hiked"
is a claim about USDTRY, "the Shanghai gold premium" is a claim about XAUUSD -- a foreign dataset
or event, an information shock, an MT5 instrument. `INDIRECT_CHANNELS` maps such triggers to the
pair they move, and every claim records its `channel` ("direct" when the source names the MT5
instrument, "indirect" otherwise) so the funnel can measure whether indirect channels convert.

DEDUPLICATE FIRST. The same story told on ten sites is ONE mechanism: `mechanism_key` folds
instrument, mechanism class, direction bucket and horizon bucket into a stable key, so the miner
queues one deepening task with ten provenance rows rather than ten tasks.

Crypto-EXCHANGE claims are dropped at the door (standing order 2026-08-18); Fusion's crypto CFDs
remain reachable through their own aliases.
"""
# ruff: noqa: RUF001 -- a lexicon in twenty-six scripts is made of the
# "ambiguous" characters this rule guards against; here they are the data, not typos.
from __future__ import annotations

import hashlib
import re
from typing import Any

# ============================================================================== vocabulary
# One (QUANTITY, DIRECTION, HORIZON) triple per language. Chinese and English first because they
# were first; the rest at the same depth, in the vocabulary each community actually uses (a
# translated English phrase finds translated English content, which is the corpus already read).
# Non-ASCII words are written as literals on purpose: they are data, and an escape would hide
# what the lexicon says from the next reader.

QUANTITY_EN: tuple[str, ...] = (
    "momentum", "reversal", "mean reversion", "carry", "swap", "breakout", "range",
    "volatility", "spread", "order flow", "imbalance", "positioning", "cot", "seasonal",
    "session", "open", "close", "fix", "rollover", "gap", "correlation", "cointegration",
    "pairs", "lead", "lag", "surprise", "cpi", "nfp", "rate", "yield", "factor", "residual",
    "skew", "kurtosis", "liquidity", "flow", "inventory", "basis", "term structure", "premium",
    "drawdown", "trend", "pullback", "stop hunt", "sweep", "vwap", "volume", "open interest",
    "expiry", "auction", "intervention", "rate decision", "hike", "cut", "curve", "spot",
    "futures", "stocks", "inventories", "exports", "imports", "shipping", "freight", "harvest",
    "weather", "etf flows", "fund flows", "options", "gamma", "vix", "risk reversal", "fixing",
)
QUANTITY_ZH: tuple[str, ...] = (
    "动量", "反转", "均值回归", "均值回复", "趋势", "突破", "假突破", "套利", "基差", "价差",
    "持仓",
    "成交量", "量能", "波动率", "跳空", "缺口", "隔夜", "夜盘", "开盘", "收盘", "换月", "展期",
    "升水", "贴水", "利差", "掉期", "隔夜利息", "季节性", "时段", "资金流", "主力", "库存",
    "期限结构", "相关性", "协整", "领先", "滞后", "非农", "通胀", "加息", "降息", "利率",
    "美元指数", "流动性", "订单流", "盘口", "委托", "止损", "日内", "波段", "高频", "做市",
    "滑点", "冲击成本", "量价", "放量", "缩量", "振幅", "均线", "布林", "回撤", "回调", "反弹",
    "跨期", "跨品种", "跨市", "内外盘", "沪伦比", "金银比", "金油比", "持仓量", "多空比",
    "黄金", "白银", "原油", "铜", "股指", "外汇", "美元", "欧元", "英镑", "日元", "澳元", "恒指",
    "纳指", "标普", "道指", "德指", "日经", "汇率", "点差", "atr", "rsi", "macd", "kdj",
    "溢价", "央行", "干预", "结算", "交割", "到期", "出口", "进口", "运费", "天气", "产量",
)
DIRECTION_EN: tuple[str, ...] = (
    "long", "short", "buy", "sell", "fade", "follow", "revert", "continue", "increase",
    "decrease", "predict", "forecast", "outperform", "underperform", "positive", "negative",
    "rally", "sell-off", "selloff", "bounce", "reverse", "expand", "contract", "widen", "narrow",
    "rise", "rises", "fall", "falls", "drop", "drops", "strengthen", "weaken", "appreciate",
    "depreciate", "bullish", "bearish", "higher", "lower", "steepen", "flatten", "rebound",
    "rebounds", "fell", "rose", "dropped", "rallied", "gained", "gains", "weakened",
    "strengthened", "bounced", "reversed", "fade", "fades", "bounces", "reverts", "continues",
    "rallies", "widens", "narrows", "steepens", "flattens", "strengthens", "weakens",
    "appreciates", "depreciates", "reverses", "expands", "contracts", "climbs", "climb", "slides",
    "slide", "sinks", "surges", "surge", "tumbles", "jumps", "dips", "dip",
)
DIRECTION_ZH: tuple[str, ...] = (
    "做多", "做空", "买入", "卖出", "反向", "顺势", "逆势", "回归", "延续", "上涨", "下跌", "预测",
    "跑赢", "跑输", "正相关", "负相关", "追涨", "杀跌", "抄底", "摸顶", "止盈", "加仓", "减仓",
    "多头", "空头", "看多", "看空", "走强", "走弱", "收敛", "扩大", "反弹", "回落", "冲高", "跳水",
    "涨", "跌", "收窄", "拉升", "砸盘", "平仓", "开仓", "入场", "出场", "升值", "贬值",
)
HORIZON_EN: tuple[str, ...] = (
    "minute", "minutes", "hour", "hours", "hourly", "daily", "day", "days", "week", "weekly",
    "month", "monthly", "intraday", "overnight", "bar", "bars", "h1", "h4", "d1", "m5", "m15",
    "session", "open", "close", "tick", "quarter", "quarterly", "expiry", "next day",
)
HORIZON_ZH: tuple[str, ...] = (
    "分钟", "小时", "日内", "隔夜", "当日", "次日", "每日", "日线", "周线", "月线", "开盘后",
    "收盘前", "夜盘", "早盘", "尾盘", "根k线", "交易日", "一周", "一个月", "tick", "秒级",
    "分钟级", "小时级", "日级", "周", "月", "季度",
)

# ---- Traditional Chinese (Taiwan / Hong Kong): the same grammar in the other script. Shared
# characters (突破, 原油) are covered by the simplified table, which is searched as well.
QUANTITY_ZHT: tuple[str, ...] = (
    "動量", "反轉", "均值回歸", "趨勢", "假突破", "套利", "基差", "價差", "持倉", "成交量",
    "量能", "波動率", "跳空", "缺口", "隔夜", "夜盤", "開盤", "收盤", "換月", "轉倉", "升水",
    "貼水", "利差", "掉期", "隔夜利息", "季節性", "時段", "資金流", "主力", "庫存", "期限結構",
    "相關性", "協整", "領先", "滯後", "非農", "通膨", "升息", "降息", "利率", "美元指數",
    "流動性", "訂單流", "盤口", "委託", "停損", "日內", "波段", "高頻", "造市", "滑價", "量價",
    "爆量", "縮量", "振幅", "均線", "布林", "回撤", "回檔", "反彈", "跨期", "跨市", "內外盤",
    "金銀比", "金油比", "未平倉", "多空比", "黃金", "白銀", "銅", "股指", "外匯", "歐元",
    "英鎊", "日圓", "澳幣", "恆指", "恆生", "那斯達克", "納斯達克", "標普", "道瓊", "德指",
    "日經", "匯率", "點差", "台指", "加權", "選擇權", "期貨", "法人", "外資", "投信", "自營商",
    "融資", "融券", "借券", "籌碼", "當沖", "報酬", "乖離", "支撐", "壓力", "前高", "前低",
    "台股", "港股", "美股", "台幣", "港幣", "國企", "北水", "港股通", "南下資金", "牛熊證",
    "窩輪", "權證", "溢價", "結算", "央行", "干預", "運費", "產量", "出口",
)
DIRECTION_ZHT: tuple[str, ...] = (
    "做多", "做空", "買入", "賣出", "反向", "順勢", "逆勢", "回歸", "延續", "上漲", "下跌", "預測",
    "跑贏", "跑輸", "正相關", "負相關", "追漲", "殺跌", "抄底", "摸頭", "停利", "加碼", "減碼",
    "多頭", "空頭", "看多", "看空", "走強", "走弱", "收斂", "擴大", "反彈", "回落", "衝高",
    "跳水", "漲", "跌", "收窄", "拉抬", "殺盤", "平倉", "開倉", "進場", "出場", "多單", "空單",
    "站上", "跌破", "拉回", "上攻", "翻多", "翻空", "升值", "貶值",
)
HORIZON_ZHT: tuple[str, ...] = (
    "分鐘", "小時", "日內", "隔夜", "當日", "次日", "每日", "日線", "週線", "月線", "開盤後",
    "收盤前", "夜盤", "早盤", "尾盤", "根k線", "交易日", "一週", "一個月", "秒級", "分鐘級",
    "小時級", "日級", "週", "月", "盤中", "盤後", "盤前", "當沖", "隔日沖", "結算日", "週選",
    "月選", "除息", "季底", "年底",
)

# ---- Japanese: the botter / FX-blog register (note.com, Qiita, みんかぶ, 株探, 5ch 株板).
QUANTITY_JA: tuple[str, ...] = (
    "モメンタム", "逆張り", "順張り", "トレンド", "トレンドフォロー", "ブレイク", "ブレイクアウト",
    "裁定", "スプレッド", "ボラティリティ", "窓", "ギャップ", "スワップ", "キャリー", "出来高",
    "建玉", "季節", "季節性", "アノマリー", "時間帯", "仲値", "ゴールド", "金", "原油", "ドル円",
    "ユーロドル", "日経", "ロンドン", "ニューヨーク", "東京時間", "指標", "雇用統計", "平均回帰",
    "押し目", "戻り", "レンジ", "板", "歩み値", "気配", "スリッページ", "移動平均", "ボリンジャー",
    "一目", "サポート", "レジスタンス", "高値", "安値", "前日高値", "前日安値", "窓埋め",
    "ゴトー日",
    "五十日", "月末", "期末", "実需", "輸出企業", "リバランス", "決算", "配当", "先物",
    "オプション",
    "ベーシス", "限月", "ロールオーバー", "スワップポイント", "金利差", "政策金利", "日銀",
    "fomc", "cpi", "指標発表", "相関", "逆相関", "乖離", "乖離率", "atr", "rsi", "macd",
    "騰落", "空売り", "信用", "貸借", "需給", "買い戻し", "踏み上げ", "投げ", "介入", "為替介入",
    "国債", "利回り", "銀", "プラチナ", "銅", "天然ガス", "ダウ", "ナスダック", "s&p", "dax",
    "ポンド円", "ユーロ円", "豪ドル", "ドルインデックス", "在庫", "出荷", "天候", "運賃",
)
DIRECTION_JA: tuple[str, ...] = (
    "買い", "売り", "ロング", "ショート", "上昇", "下落", "反発", "反落", "続伸", "続落", "戻る",
    "上抜け", "下抜け", "利確", "損切り", "上がる", "下がる", "上がりやすい", "下がりやすい",
    "押し目買い", "戻り売り", "買い増し", "手仕舞い", "エントリー", "イグジット", "決済", "強含",
    "弱含", "円高", "円安", "ドル高", "ドル安", "上振れ", "下振れ", "急騰", "急落", "反転",
)
HORIZON_JA: tuple[str, ...] = (
    "分", "時間", "日", "週", "月", "デイトレ", "スイング", "足", "寄り", "引け", "オーバーナイト",
    "日中", "翌日", "当日", "前場", "後場", "大引け", "寄り付き", "分足", "時間足", "日足",
    "週足", "月足", "秒", "ザラ場", "夜間", "ナイトセッション", "週末", "月初", "年末", "四半期",
)

# ---- Korean: 해외선물 / 주식 boards (Naver, 팍스넷, DC, tistory).
QUANTITY_KO: tuple[str, ...] = (
    "모멘텀", "추세", "돌파", "역추세", "평균회귀", "차익", "스프레드", "변동성", "갭", "스왑",
    "캐리", "거래량", "포지션", "계절", "계절성", "세션", "금", "골드", "원유", "달러", "엔",
    "지수", "고용", "이동평균", "볼린저", "지지", "저항", "고점", "저점", "전일", "눌림목",
    "되돌림", "박스권", "횡보", "거래대금", "미결제약정", "호가", "체결", "슬리피지", "베이시스",
    "만기", "롤오버", "금리차", "기준금리", "한은", "연준", "고용지표", "물가", "지표발표",
    "아시아장", "런던장", "뉴욕장", "시간대", "상관관계", "이격도", "공매도", "수급", "외국인",
    "기관", "개인", "프로그램매매", "선물", "옵션", "차익거래", "괴리율", "환율", "달러원",
    "원달러", "엔화", "유가", "금값", "은", "구리", "나스닥", "다우", "s&p", "코스피", "코스닥",
    "국채", "재고", "수출", "운임", "개입", "외환당국", "atr", "rsi", "macd",
)
DIRECTION_KO: tuple[str, ...] = (
    "매수", "매도", "롱", "숏", "상승", "하락", "반등", "급락", "급등", "돌파", "이탈", "익절",
    "손절", "오른다", "내린다", "오르는", "내리는", "강세", "약세", "추격매수", "저점매수",
    "고점매도", "진입", "청산", "절상", "절하", "강해", "약해",
)
HORIZON_KO: tuple[str, ...] = (
    "분", "시간", "일", "주", "월", "데이", "스윙", "봉", "장초", "장마감", "오버나잇", "장중",
    "분봉", "시간봉", "일봉", "주봉", "월봉", "당일", "익일", "전일", "장초반", "장후반", "종가",
    "시가", "야간", "주말", "월말", "월초", "초", "틱", "단타", "스캘핑", "분기",
)

# ---- Russian and Ukrainian (stems: Cyrillic inflects, a stem catches every case).
QUANTITY_RU: tuple[str, ...] = (
    "моментум", "импульс", "разворот", "возврат к среднему", "тренд", "пробой", "арбитраж",
    "спред", "волатильност", "гэп", "своп", "кэрри", "объем", "объём", "позици", "сезонн",
    "сесси", "золот", "нефт", "доллар", "евро", "индекс", "фиксинг", "ставк", "нонфарм",
    "скользящ", "боллиндж", "поддержк", "сопротивлен", "максимум", "минимум", "откат", "флэт",
    "боковик", "открыт интерес", "стакан", "проскальзыван", "базис", "экспирац", "ролл",
    "инфляц", "корреляц", "дивергенц", "шорт-сквиз", "ликвидн", "азиатск", "лондон", "нью-йорк",
    "паттерн", "уровен", "rsi", "macd", "atr", "серебр", "медь", "газ", "рубл", "насдак", "dax",
    "ртс", "ммвб", "мосбирж", "фьючерс", "опцион", "цб", "фрс", "интервенц", "офз", "доходност",
    "запас", "экспорт", "фрахт", "урожа",
)
DIRECTION_RU: tuple[str, ...] = (
    "лонг", "шорт", "покуп", "прода", "рост", "падени", "отскок", "продолж", "пробит", "фиксац",
    "стоп", "растет", "растёт", "падает", "снижен", "вход", "выход", "откуп", "слив", "усилен",
    "ослаблен", "бычий", "медвеж", "вверх", "вниз", "укреплен", "девальвац",
)
HORIZON_RU: tuple[str, ...] = (
    "минут", "час", "дне", "день", "недел", "месяц", "интрадей", "свинг", "свеч", "открыти",
    "закрыти", "овернайт", "таймфрейм", "тик", "скальп", "дневн", "недельн", "месячн", "утр",
    "вечер", "ночн", "внутри дня", "квартал",
)
QUANTITY_UK: tuple[str, ...] = (
    "моментум", "імпульс", "розворот", "повернення до середнього", "тренд", "пробій", "арбітраж",
    "спред", "волатильн", "геп", "своп", "керрі", "обсяг", "позиці", "сезонн", "сесі", "золот",
    "нафт", "долар", "євро", "індекс", "фіксинг", "ставк", "ковзн", "підтримк", "опір",
    "максимум", "мінімум", "відкат", "бічн", "ліквідн", "кореляц", "гривн", "нбу", "інтервенц",
    "запас", "експорт", "фрахт", "урожа", "ф'ючерс", "опціон", "дохідн", "інфляц",
)
DIRECTION_UK: tuple[str, ...] = (
    "лонг", "шорт", "купівл", "купу", "прода", "зростан", "зроста", "падінн", "падає", "відскок",
    "продовж", "пробит", "фіксац", "стоп", "вхід", "вихід", "зниж", "посилен", "послаблен",
    "бичач", "ведмеж", "вгору", "вниз", "зміцн", "девальвац",
)
HORIZON_UK: tuple[str, ...] = (
    "хвилин", "годин", "дня", "день", "тижн", "місяц", "інтрадей", "свінг", "свічк", "відкритт",
    "закритт", "овернайт", "таймфрейм", "тік", "скальп", "денн", "тижнев", "місячн", "ранк",
    "вечір", "нічн", "квартал",
)

# ---- Vietnamese: F319 / CafeF / VnDirect derivatives forums.
QUANTITY_VI: tuple[str, ...] = (
    "xu hướng", "động lượng", "đảo chiều", "hồi quy", "phá vỡ", "breakout", "biên độ",
    "biến động", "khối lượng", "thanh khoản", "dòng tiền", "khối ngoại", "tự doanh", "chênh lệch",
    "spread", "cơ sở", "phái sinh", "hợp đồng tương lai", "đáo hạn", "kỳ hạn", "lãi suất",
    "tỷ giá", "mùa vụ", "tính mùa vụ", "tương quan", "hỗ trợ", "kháng cự", "đỉnh", "đáy",
    "đường trung bình", "rsi", "macd", "bollinger", "nến", "gap", "khoảng trống", "vàng", "dầu",
    "bạc", "chỉ số", "vn-index", "vn30", "chứng khoán", "cổ phiếu", "ato", "atc", "giá đóng cửa",
    "giá mở cửa", "margin", "ký quỹ", "call margin", "giải chấp", "bán tháo", "sóng", "nhịp",
    "tồn kho", "xuất khẩu", "nhập khẩu", "cước", "thời tiết", "ngân hàng nhà nước", "can thiệp",
    "trái phiếu", "lợi suất", "usd", "đô la",
)
DIRECTION_VI: tuple[str, ...] = (
    "mua", "bán", "long", "short", "tăng", "giảm", "bật tăng", "hồi phục", "điều chỉnh",
    "phá đỉnh", "thủng đáy", "đảo chiều", "tiếp diễn", "chốt lời", "cắt lỗ", "bắt đáy", "đu đỉnh",
    "tăng giá", "giảm giá", "đi lên", "đi xuống", "vượt", "xuyên thủng", "gom", "xả", "vào lệnh",
    "thoát lệnh", "mở vị thế", "đóng vị thế", "mất giá", "lên giá",
)
HORIZON_VI: tuple[str, ...] = (
    "phút", "giờ", "ngày", "tuần", "tháng", "phiên", "trong phiên", "cuối phiên", "đầu phiên",
    "qua đêm", "phiên sau", "hôm sau", "ngắn hạn", "trung hạn", "dài hạn", "khung", "nến ngày",
    "nến tuần", "nến giờ", "intraday", "t+2", "t+3", "lướt sóng", "scalp", "quý",
)

# ---- Thai: Pantip Sinthorn / stock2morrow / SET research.
QUANTITY_TH: tuple[str, ...] = (
    "โมเมนตัม", "แนวโน้ม", "กลับตัว", "ทะลุ", "เบรคเอาท์", "กรอบ", "ไซด์เวย์", "ความผันผวน",
    "วอลุ่ม", "ปริมาณการซื้อขาย", "สภาพคล่อง", "ฟันด์โฟลว์", "ต่างชาติ", "สเปรด", "เบสิส",
    "ฟิวเจอร์ส", "ออปชั่น", "หมดอายุ", "ดอกเบี้ย", "ค่าเงิน", "บาท", "ฤดูกาล", "ความสัมพันธ์",
    "แนวรับ", "แนวต้าน", "จุดสูงสุด", "จุดต่ำสุด", "เส้นค่าเฉลี่ย", "ema", "rsi", "macd",
    "แท่งเทียน", "แก๊ป", "ทองคำ", "ทอง", "น้ำมัน", "ดัชนี", "set50", "หุ้น", "ราคาปิด",
    "ราคาเปิด", "มาร์จิ้น", "ฟอร์ซเซล", "เทขาย", "สต็อก", "ส่งออก", "ค่าระวาง", "แบงก์ชาติ",
    "ธปท", "แทรกแซง", "พันธบัตร", "ผลตอบแทน", "ดอลลาร์",
)
DIRECTION_TH: tuple[str, ...] = (
    "ซื้อ", "ขาย", "ลอง", "ชอร์ต", "ขึ้น", "ลง", "เด้ง", "รีบาวด์", "ปรับฐาน", "ย่อ", "ทะลุ",
    "หลุด", "กลับตัว", "ต่อเนื่อง", "ทำกำไร", "ตัดขาดทุน", "คัทลอส", "ช้อน", "ดอย", "บวก",
    "ลบ", "แรง", "อ่อน", "เข้า", "ออก", "เปิดสถานะ", "ปิดสถานะ", "ไล่ราคา", "แข็งค่า", "อ่อนค่า",
)
HORIZON_TH: tuple[str, ...] = (
    "นาที", "ชั่วโมง", "วัน", "สัปดาห์", "เดือน", "รายวัน", "รายสัปดาห์", "ระหว่างวัน", "ข้ามคืน",
    "ปิดตลาด", "เปิดตลาด", "ช่วงเช้า", "ช่วงบ่าย", "ท้ายตลาด", "เดย์เทรด", "สวิง", "ไทม์เฟรม",
    "แท่ง", "ไตรมาส",
)

# ---- Indonesian / Malay: Stockbit, Kaskus, i3investor, Lowyat (one lexicon, shared roots).
QUANTITY_ID: tuple[str, ...] = (
    "momentum", "tren", "trend", "pembalikan", "reversal", "breakout", "penembusan", "sideways",
    "volatilitas", "volume", "likuiditas", "aliran dana", "asing", "spread", "basis", "berjangka",
    "futures", "kedaluwarsa", "suku bunga", "bunga", "kurs", "rupiah", "ringgit", "musiman",
    "korelasi", "support", "resistance", "resisten", "puncak", "dasar", "moving average",
    "rata-rata bergerak", "rsi", "macd", "candle", "gap", "emas", "minyak", "perak", "tembaga",
    "indeks", "ihsg", "klci", "saham", "harga penutupan", "harga pembukaan", "margin", "bandar",
    "akumulasi", "distribusi", "stok", "persediaan", "ekspor", "impor", "ongkos kirim", "cuaca",
    "bank indonesia", "bank negara", "intervensi", "obligasi", "imbal hasil", "dolar",
)
DIRECTION_ID: tuple[str, ...] = (
    "beli", "jual", "long", "short", "naik", "turun", "rebound", "pantul", "koreksi", "menembus",
    "jebol", "berbalik", "berlanjut", "ambil untung", "taking profit", "cut loss", "potong rugi",
    "serok", "nyangkut", "menguat", "melemah", "masuk", "keluar", "buka posisi", "tutup posisi",
    "bullish", "bearish", "terdepresiasi", "terapresiasi",
)
HORIZON_ID: tuple[str, ...] = (
    "menit", "jam", "hari", "minggu", "pekan", "bulan", "harian", "mingguan", "intraday",
    "semalam", "penutupan", "pembukaan", "sesi", "sesi pagi", "sesi siang", "akhir sesi",
    "scalping", "swing", "jangka pendek", "jangka panjang", "time frame", "kuartal",
)

# ---- Hindi: Moneycontrol boards, Hindi finance YouTube descriptions, Hindi blogs.
QUANTITY_HI: tuple[str, ...] = (
    "मोमेंटम", "ट्रेंड", "रुझान", "रिवर्सल", "पलटाव", "ब्रेकआउट", "रेंज", "वोलैटिलिटी",
    "उतार-चढ़ाव", "वॉल्यूम", "लिक्विडिटी", "तरलता", "स्प्रेड", "बेसिस", "फ्यूचर्स", "वायदा",
    "ऑप्शन", "एक्सपायरी", "ब्याज दर", "रुपया", "डॉलर", "सीज़नल", "मौसमी", "सहसंबंध", "सपोर्ट",
    "रेजिस्टेंस", "प्रतिरोध", "समर्थन", "मूविंग एवरेज", "rsi", "macd", "कैंडल", "गैप", "सोना",
    "चांदी", "कच्चा तेल", "तांबा", "इंडेक्स", "निफ्टी", "बैंक निफ्टी", "सेंसेक्स", "शेयर",
    "बंद भाव", "खुला भाव", "fii", "dii", "ओपन इंटरेस्ट", "pcr", "vix", "आरबीआई", "रिज़र्व बैंक",
    "हस्तक्षेप", "बॉन्ड", "यील्ड", "निर्यात", "आयात", "भंडार", "मानसून", "एमसीएक्स",
)
DIRECTION_HI: tuple[str, ...] = (
    "खरीद", "बेच", "लॉन्ग", "शॉर्ट", "तेजी", "मंदी", "बढ़", "गिर", "उछाल", "रिकवरी", "करेक्शन",
    "गिरावट", "तोड़", "टूट", "पलट", "जारी", "मुनाफा", "प्रॉफिट बुक", "स्टॉप लॉस", "मजबूत",
    "कमजोर", "एंट्री", "एग्जिट", "ऊपर", "नीचे", "चढ़",
)
HORIZON_HI: tuple[str, ...] = (
    "मिनट", "घंटा", "घंटे", "दिन", "हफ्ता", "सप्ताह", "महीना", "महीने", "इंट्राडे", "ओवरनाइट",
    "बंद", "खुलने", "सुबह", "दोपहर", "शाम", "स्कैल्पिंग", "स्विंग", "शॉर्ट टर्म", "लॉन्ग टर्म",
    "टाइमफ्रेम", "साप्ताहिक", "मासिक", "दैनिक", "एक्सपायरी", "तिमाही",
)

# ---- German: wallstreet-online, finanzen.net, stock3, Bundesbank.
QUANTITY_DE: tuple[str, ...] = (
    "momentum", "trend", "umkehr", "rückkehr zum mittelwert", "mean reversion", "ausbruch",
    "seitwärts", "range", "volatilität", "volumen", "umsatz", "liquidität", "orderfluss", "spread",
    "basis", "terminkurs", "futures", "verfall", "verfallstag", "hexensabbat", "zins", "zinsen",
    "zinsdifferenz", "wechselkurs", "saison", "korrelation", "unterstützung", "widerstand",
    "gleitend", "durchschnitt", "rsi", "macd", "kerze", "gap", "kurslücke", "gold", "silber",
    "rohöl", "kupfer", "index", "dax", "mdax", "euro stoxx", "aktie", "schlusskurs",
    "eröffnungskurs", "positionierung", "cot", "stimmung", "sentiment", "überkauft", "überverkauft",
    "dollar", "euro", "lagerbestand", "lagerbestände", "export", "fracht", "ernte", "ezb",
    "bundesbank", "intervention", "anleihe", "rendite", "bund",
)
DIRECTION_DE: tuple[str, ...] = (
    "kaufen", "kauf", "verkaufen", "verkauf", "long", "short", "steig", "fall", "fällt", "erhol",
    "korrektur", "durchbr", "bricht", "dreht", "umkehr", "fortsetz", "gewinnmitnahme", "stopp",
    "stärk", "schwäch", "einstieg", "ausstieg", "aufwärts", "abwärts", "hausse", "baisse",
    "bullisch", "bärisch", "nachkauf", "glattstell", "aufwert", "abwert",
)
HORIZON_DE: tuple[str, ...] = (
    "minute", "stunde", "stündlich", "tag", "täglich", "woche", "wöchentlich", "monat",
    "monatlich", "intraday", "übernacht", "schluss", "handelsschluss", "tagesschluss", "eröffnung",
    "handelstag", "sitzung",
    "session", "vormittag", "nachmittag", "scalp", "swing", "kurzfristig", "langfristig",
    "zeitebene", "tageskerze", "wochenkerze", "quartal",
)

# ---- French: Boursorama, ABC Bourse, Banque de France.
QUANTITY_FR: tuple[str, ...] = (
    "momentum", "tendance", "retournement", "retour à la moyenne", "cassure", "breakout", "range",
    "latéral", "volatilité", "volume", "liquidité", "flux", "spread", "contango", "backwardation",
    "échéance", "taux", "différentiel", "change", "saisonnalité", "saisonnier", "corrélation",
    "support", "résistance", "plus haut", "plus bas", "moyenne mobile", "rsi", "macd", "bougie",
    "gap", "l'or", "once", "pétrole", "brut", "cuivre", "indice", "cac", "dax", "action", "clôture",
    "ouverture", "positionnement", "cot", "sentiment", "suracheté", "survendu", "dollar", "euro",
    "carry", "stocks", "exportations", "fret", "récolte", "bce", "intervention", "obligation",
    "rendement", "oat",
)
DIRECTION_FR: tuple[str, ...] = (
    "achat", "achet", "vente", "vend", "long", "short", "hausse", "baisse", "monte", "rebond",
    "correction", "casse", "franchit", "retourne", "continue", "prise de bénéfice", "stop",
    "renforce", "faiblit", "entrée", "sortie", "haussier", "baissier", "repli", "décroch",
    "s'envole", "s'apprécie", "se déprécie", "grimpe", "chute",
)
HORIZON_FR: tuple[str, ...] = (
    "minute", "heure", "horaire", "jour", "journalier", "quotidien", "semaine", "hebdomadaire",
    "mois", "mensuel", "intraday", "overnight", "clôture", "ouverture", "séance", "session",
    "matin", "après-midi", "scalping", "swing", "court terme", "long terme", "unité de temps",
    "bougie", "trimestre",
)

# ---- Italian: FinanzaOnline, Banca d'Italia.
QUANTITY_IT: tuple[str, ...] = (
    "momentum", "trend", "tendenza", "inversione", "ritorno alla media", "rottura", "breakout",
    "laterale", "range", "volatilità", "volume", "liquidità", "flusso", "spread", "base",
    "scadenza", "tasso", "tassi", "differenziale", "cambio", "stagionalità", "stagionale",
    "correlazione", "supporto", "resistenza", "massimo", "minimo", "media mobile", "rsi", "macd",
    "candela", "gap", "oro", "argento", "petrolio", "greggio", "rame", "indice", "ftse mib", "dax",
    "azione", "chiusura", "apertura", "posizionamento", "cot", "sentiment", "ipercomprato",
    "ipervenduto", "dollaro", "euro", "carry", "scorte", "export", "noli", "raccolto", "bce",
    "intervento", "btp", "rendimento",
)
DIRECTION_IT: tuple[str, ...] = (
    "compra", "acquist", "vend", "long", "short", "rialzo", "ribasso", "sale", "scende", "rimbalz",
    "correzione", "rompe", "supera", "inverte", "prosegue", "presa di profitto", "stop", "rafforz",
    "indebol", "ingresso", "uscita", "rialzista", "ribassista", "storno", "si apprezza",
    "si deprezza", "crolla",
)
HORIZON_IT: tuple[str, ...] = (
    "minut", "ora", "orari", "giorn", "settiman", "mese", "mensil", "intraday", "overnight",
    "chiusura", "apertura", "seduta", "sessione", "mattina", "pomeriggio", "scalping", "swing",
    "breve termine", "lungo termine", "time frame", "candela", "trimestre",
)

# ---- Spanish (Spain and Latin America): Rankia, X-Trader, Rava, El Economista.
QUANTITY_ES: tuple[str, ...] = (
    "momentum", "impulso", "tendencia", "reversión", "retorno a la media", "ruptura", "breakout",
    "rango", "lateral", "volatilidad", "volumen", "liquidez", "flujo", "spread", "diferencial",
    "base", "vencimiento", "tasa", "tipos", "tipo de interés", "cambio", "estacionalidad",
    "estacional", "correlación", "soporte", "resistencia", "máximo", "mínimo", "media móvil", "rsi",
    "macd", "vela", "gap", "hueco", "oro", "plata", "petróleo", "crudo", "cobre", "índice", "ibex",
    "dax", "sp500", "acción", "cierre", "apertura", "posicionamiento", "cot", "sentimiento",
    "sobrecompra", "sobreventa", "dólar", "euro", "peso", "carry", "inventario", "existencias",
    "exportaciones", "flete", "cosecha", "banxico", "banco central", "intervención", "bono",
    "rendimiento", "cepo", "merval", "brecha",
)
DIRECTION_ES: tuple[str, ...] = (
    "compra", "compr", "vend", "venta", "largo", "corto", "long", "short", "alza", "sube", "baja",
    "cae", "rebote", "rebota", "corrección", "rompe", "supera", "gira", "revierte", "continúa",
    "toma de beneficios", "stop", "fortalece", "debilita", "entrada", "salida", "alcista",
    "bajista", "retroceso", "desplome", "se aprecia", "se deprecia", "devalúa",
)
HORIZON_ES: tuple[str, ...] = (
    "minuto", "hora", "horario", "día", "diario", "semana", "semanal", "mes", "mensual",
    "intradía", "intradia", "overnight", "cierre", "apertura", "sesión", "sesion", "mañana",
    "tarde", "scalping", "swing", "corto plazo", "largo plazo", "marco temporal", "temporalidad",
    "vela diaria", "trimestre",
)

# ---- Portuguese (Brazil): InfoMoney, Clube do Valor, Suno, Quantbrasil, Bastter.
QUANTITY_PT: tuple[str, ...] = (
    "momentum", "tendência", "reversão", "retorno à média", "rompimento", "breakout", "lateral",
    "range", "volatilidade", "volume", "liquidez", "fluxo", "estrangeiro", "spread", "base",
    "vencimento", "taxa", "juros", "selic", "diferencial", "câmbio", "sazonalidade", "sazonal",
    "correlação", "suporte", "resistência", "topo", "fundo", "máxima", "mínima", "média móvel",
    "rsi", "macd", "candle", "gap", "ouro", "prata", "petróleo", "cobre", "índice", "ibovespa",
    "ibov", "ação", "fechamento", "abertura", "posicionamento", "cot", "sentimento",
    "sobrecomprado", "sobrevendido", "dólar", "real", "carry", "ajuste", "leilão", "estoque",
    "safra", "exportação", "exportações", "frete", "copom", "bacen", "banco central", "intervenção",
    "swap cambial", "tesouro", "cupom cambial",
)
DIRECTION_PT: tuple[str, ...] = (
    "compra", "compr", "vend", "venda", "comprado", "vendido", "long", "short", "alta", "sobe",
    "baixa", "cai", "queda", "repique", "correção", "rompe", "supera", "vira", "reverte",
    "continua", "realização", "stop", "fortalece", "enfraquece", "entrada", "saída", "altista",
    "baixista", "pullback", "tombo", "dispara", "desvaloriza", "valoriza",
)
HORIZON_PT: tuple[str, ...] = (
    "minuto", "hora", "dia", "diário", "semana", "semanal", "mês", "mensal", "intraday",
    "intradiário", "overnight", "fechamento", "abertura", "pregão", "sessão", "manhã", "tarde",
    "scalping", "swing", "curto prazo", "longo prazo", "tempo gráfico", "candle diário", "after",
    "trimestre",
)

# ---- Arabic: Argaam, Mubasher, ArabicTrader, Gulf exchange research.
QUANTITY_AR: tuple[str, ...] = (
    "زخم", "اتجاه", "انعكاس", "اختراق", "نطاق", "تذبذب", "تقلب", "حجم", "سيولة", "فارق",
    "أساس", "عقود آجلة", "فائدة", "سعر الصرف", "موسمي", "ارتباط", "دعم", "مقاومة", "قمة", "قاع",
    "متوسط متحرك", "شمعة", "فجوة", "ذهب", "فضة", "نفط", "نحاس", "مؤشر", "تاسي", "دولار", "ريال",
    "درهم", "جنيه", "مخزون", "صادرات", "شحن", "البنك المركزي", "ساما", "تدخل", "سندات", "عائد",
    "أوبك", "خام",
)
DIRECTION_AR: tuple[str, ...] = (
    "شراء", "بيع", "صعود", "هبوط", "ارتفاع", "انخفاض", "ارتداد", "تصحيح", "كسر", "اختراق",
    "انعكاس", "استمرار", "جني أرباح", "وقف خسارة", "دخول", "خروج", "يرتفع", "ينخفض", "تراجع",
)
HORIZON_AR: tuple[str, ...] = (
    "دقيقة", "ساعة", "يوم", "يومي", "أسبوع", "أسبوعي", "شهر", "شهري", "خلال اليوم", "ليلي",
    "إغلاق", "افتتاح", "جلسة", "صباح", "مساء", "مضاربة", "إطار زمني", "ربع",
)

# ---- Turkish: Borsa Istanbul boards, Bloomberg HT, KAP.
QUANTITY_TR: tuple[str, ...] = (
    "momentum", "trend", "dönüş", "kırılım", "yatay", "volatilite", "oynaklık", "hacim",
    "likidite", "spread", "baz", "vade", "faiz", "kur", "mevsimsel", "korelasyon", "destek",
    "direnç", "zirve", "dip", "hareketli ortalama", "rsi", "macd", "mum", "gap", "boşluk", "altın",
    "ons", "gümüş", "petrol", "bakır", "endeks", "bist", "dolar", "euro", "lira", "swap", "taşıma",
    "stok", "ihracat", "navlun", "hasat", "merkez bankası", "tcmb", "müdahale", "tahvil", "getiri",
    "enflasyon", "rezerv", "kkm",
)
DIRECTION_TR: tuple[str, ...] = (
    "alım", "satış", "long", "short", "yüksel", "düş", "toparlan", "tepki", "düzeltme", "kır",
    "aş", "dön", "devam", "kâr al", "stop", "güçlen", "zayıfla", "giriş", "çıkış", "yukarı",
    "aşağı", "boğa", "ayı", "değer kazan", "değer kaybet", "al ", "sat ",
)
HORIZON_TR: tuple[str, ...] = (
    "dakika", "saat", "gün", "günlük", "hafta", "haftalık", "ay", "aylık", "gün içi", "gece",
    "kapanış", "açılış", "seans", "sabah", "öğleden", "scalp", "swing", "kısa vade", "uzun vade",
    "zaman dilimi", "mum", "çeyrek",
)

# ---- Hebrew: Globes, TASE research, Bizportal boards.
QUANTITY_HE: tuple[str, ...] = (
    "מומנטום", "מגמה", "היפוך", "פריצה", "טווח", "תנודתיות", "מחזור", "נזילות", "מרווח",
    "בסיס", "חוזים", "ריבית", "שער חליפין", "עונתי", "מתאם", "תמיכה", "התנגדות", "שיא", "שפל",
    "ממוצע נע", "נר", "פער", "זהב", "כסף", "נפט", "נחושת", "מדד", "דולר", "שקל", "מלאי",
    "יצוא", "בנק ישראל", "התערבות", "אג\"ח", "תשואה", "אינפלציה",
)
DIRECTION_HE: tuple[str, ...] = (
    "קנייה", "מכירה", "לונג", "שורט", "עלייה", "ירידה", "עולה", "יורד", "תיקון", "שובר", "פורץ",
    "היפוך", "המשך", "מימוש", "סטופ", "כניסה", "יציאה", "מתחזק", "נחלש", "ייסוף", "פיחות",
)
HORIZON_HE: tuple[str, ...] = (
    "דקה", "דקות", "שעה", "שעות", "יום", "יומי", "שבוע", "שבועי", "חודש", "חודשי", "תוך יומי",
    "לילה", "סגירה", "פתיחה", "מסחר", "בוקר", "ערב", "סווינג", "רבעון",
)

# ---- Polish: Bankier, StockWatch, GPW.
QUANTITY_PL: tuple[str, ...] = (
    "momentum", "trend", "odwrócen", "powrót do średniej", "wybicie", "konsolidac", "zmienność",
    "wolumen", "obrót", "płynność", "spread", "baza", "kontrakt", "wygaśnięci", "stopa", "stóp",
    "kurs", "sezonow", "korelac", "wsparci", "opór", "szczyt", "dołek", "średnia krocząc", "rsi",
    "macd", "świec", "luka", "złoto", "srebro", "ropa", "miedź", "indeks", "wig20", "wig",
    "akcje", "zamknięci", "otwarci", "pozycjonowan", "cot", "nastroj", "dolar", "euro", "złoty",
    "zapas", "eksport", "fracht", "zbior", "nbp", "rpp", "interwenc", "obligac", "rentowność",
    "inflacj",
)
DIRECTION_PL: tuple[str, ...] = (
    "kupn", "kupuj", "sprzeda", "long", "short", "wzrost", "rośnie", "spadek", "spada", "odbici",
    "korekt", "przebij", "przełam", "odwrac", "kontynu", "realizac", "stop", "umacnia", "słabnie",
    "wejści", "wyjści", "byczy", "niedźwiedz", "w górę", "w dół", "aprecjac", "deprecjac",
)
HORIZON_PL: tuple[str, ...] = (
    "minut", "godzin", "dzień", "dni", "dzienn", "tydzień", "tygodni", "miesiąc", "miesięczn",
    "intraday", "overnight", "zamknięci", "otwarci", "sesj", "rano", "popołudni", "scalp",
    "swing", "krótkoterminow", "długoterminow", "interwał", "świec", "kwartał",
)

# ---- Dutch: IEX.nl, Belegger.nl, DNB.
QUANTITY_NL: tuple[str, ...] = (
    "momentum", "trend", "omkeer", "terugkeer naar het gemiddelde", "uitbraak", "zijwaarts",
    "volatiliteit", "volume", "liquiditeit", "spread", "basis", "termijn", "expiratie", "rente",
    "wisselkoers", "seizoen", "correlatie", "steun", "weerstand", "hoogtepunt", "dieptepunt",
    "voortschrijdend gemiddelde", "rsi", "macd", "candle", "gap", "goud", "zilver", "olie",
    "koper", "index", "aex", "aandeel", "slotkoers", "openingskoers", "positionering", "cot",
    "sentiment", "dollar", "euro", "voorraad", "voorraden", "export", "vracht", "oogst", "ecb",
    "dnb", "interventie", "obligatie", "rendement", "inflatie",
)
DIRECTION_NL: tuple[str, ...] = (
    "koop", "kopen", "verkoop", "verkopen", "long", "short", "stijg", "daal", "herstel",
    "correctie",
    "doorbr", "breekt", "draait", "omkeer", "vervolg", "winst nemen", "stop", "sterker", "zwakker",
    "instap", "uitstap", "opwaarts", "neerwaarts", "bullish", "bearish", "apprecieer", "deprecieer",
)
HORIZON_NL: tuple[str, ...] = (
    "minuut", "minuten", "uur", "dag", "dagelijks", "week", "wekelijks", "maand", "maandelijks",
    "intraday", "overnight", "slot", "opening", "handelsdag", "sessie", "ochtend", "middag",
    "scalp", "swing", "korte termijn", "lange termijn", "tijdframe", "kwartaal",
)

# ---- Swedish, Danish, Norwegian, Finnish: Avanza, Nordnet, Shareville, Kauppalehti.
QUANTITY_SV: tuple[str, ...] = (
    "momentum", "trend", "vändning", "återgång till medelvärdet", "utbrott", "sidledes",
    "volatilitet", "volym", "likviditet", "spread", "bas", "termin", "förfall", "ränta",
    "räntor", "växelkurs", "säsong", "korrelation", "stöd", "motstånd", "topp", "botten",
    "glidande medelvärde", "rsi", "macd", "candle", "gap", "guld", "silver", "olja", "koppar",
    "index", "omx", "aktie", "stängningskurs", "öppningskurs", "positionering", "cot",
    "sentiment", "dollar", "euro", "krona", "kronan", "lager", "export", "frakt", "skörd",
    "riksbanken", "intervention", "obligation", "avkastning", "inflation",
)
DIRECTION_SV: tuple[str, ...] = (
    "köp", "sälj", "long", "short", "stig", "steg", "fall", "föll", "sjunk", "rekyl", "studs",
    "korrigering", "bryter", "vänder", "fortsätter", "vinsthemtagning", "stopp", "stärk",
    "försvag", "ingång", "utgång", "uppåt", "nedåt", "bullish", "bearish",
)
HORIZON_SV: tuple[str, ...] = (
    "minut", "timme", "timmar", "dag", "daglig", "vecka", "veckovis", "månad", "månatlig",
    "intradag", "intraday", "övernatt", "stängning", "öppning", "handelsdag", "session",
    "morgon", "eftermiddag", "scalp", "swing", "kort sikt", "lång sikt", "tidsram", "kvartal",
)
QUANTITY_DA: tuple[str, ...] = (
    "momentum", "trend", "vending", "tilbagevenden til gennemsnittet", "udbrud", "sidelæns",
    "volatilitet", "volumen", "likviditet", "spread", "basis", "termin", "udløb", "rente",
    "renter", "valutakurs", "sæson", "korrelation", "støtte", "modstand", "top", "bund",
    "glidende gennemsnit", "rsi", "macd", "candle", "gap", "guld", "sølv", "olie", "kobber",
    "indeks", "omxc", "aktie", "lukkekurs", "åbningskurs", "positionering", "cot", "stemning",
    "dollar", "euro", "krone", "kronen", "lager", "eksport", "fragt", "høst", "nationalbanken",
    "intervention", "obligation", "afkast", "inflation",
)
DIRECTION_DA: tuple[str, ...] = (
    "køb", "sælg", "long", "short", "stig", "steg", "fald", "faldt", "rekyl", "korrektion",
    "bryder", "vender", "fortsætter", "gevinsthjemtagning", "stop", "styrk", "svæk", "indgang",
    "udgang", "opad", "nedad", "bullish", "bearish",
)
HORIZON_DA: tuple[str, ...] = (
    "minut", "time", "timer", "dag", "daglig", "uge", "ugentlig", "måned", "månedlig",
    "intradag", "intraday", "overnight", "lukning", "åbning", "handelsdag", "session", "morgen",
    "eftermiddag", "scalp", "swing", "kort sigt", "lang sigt", "tidsramme", "kvartal",
)
QUANTITY_NO: tuple[str, ...] = (
    "momentum", "trend", "vending", "tilbake til gjennomsnittet", "utbrudd", "sidelengs",
    "volatilitet", "volum", "likviditet", "spread", "basis", "termin", "forfall", "rente",
    "renter", "valutakurs", "sesong", "korrelasjon", "støtte", "motstand", "topp", "bunn",
    "glidende gjennomsnitt", "rsi", "macd", "candle", "gap", "gull", "sølv", "olje", "kobber",
    "indeks", "obx", "aksje", "sluttkurs", "åpningskurs", "posisjonering", "cot", "stemning",
    "dollar", "euro", "krone", "kronen", "lager", "eksport", "frakt", "avling", "norges bank",
    "intervensjon", "obligasjon", "avkastning", "inflasjon", "oljefondet",
)
DIRECTION_NO: tuple[str, ...] = (
    "kjøp", "selg", "long", "short", "stig", "steg", "fall", "falt", "rekyl", "korreksjon",
    "bryter", "snur", "fortsetter", "gevinstsikring", "stopp", "styrk", "svekk", "inngang",
    "utgang", "oppover", "nedover", "bullish", "bearish",
)
HORIZON_NO: tuple[str, ...] = (
    "minutt", "time", "timer", "dag", "daglig", "uke", "ukentlig", "måned", "månedlig",
    "intradag", "intraday", "overnight", "stenging", "åpning", "handelsdag", "sesjon", "morgen",
    "ettermiddag", "scalp", "swing", "kort sikt", "lang sikt", "tidsramme", "kvartal",
)
QUANTITY_FI: tuple[str, ...] = (
    "momentum", "trendi", "käänne", "paluu keskiarvoon", "läpimurto", "sivuttais", "volatiliteetti",
    "volyymi", "vaihto", "likviditeetti", "spread", "basis", "futuuri", "erääntymi", "korko",
    "korot", "valuuttakurssi", "kausi", "korrelaatio", "tuki", "vastus", "huippu", "pohja",
    "liukuva keskiarvo", "rsi", "macd", "kynttilä", "gap", "kulta", "hopea", "öljy", "kupari",
    "indeksi", "omxh", "osake", "päätöskurssi", "avauskurssi", "positiointi", "cot", "sentimentti",
    "dollari", "euro", "varasto", "vienti", "rahti", "sato", "ekp", "interventio",
    "joukkovelkakirja",
    "tuotto", "inflaatio",
)
DIRECTION_FI: tuple[str, ...] = (
    "osta", "osto", "myy", "myynti", "long", "short", "nous", "lask", "elpy", "korjaus", "rikko",
    "kääntyy", "jatkuu", "voittojen kotiutus", "stop", "vahvist", "heikke", "sisään", "ulos",
    "ylös", "alas", "bullish", "bearish",
)
HORIZON_FI: tuple[str, ...] = (
    "minuutti", "tunti", "tuntia", "päivä", "päivittäin", "viikko", "viikoittain", "kuukausi",
    "kuukausittain", "intraday", "yön yli", "päätös", "avaus", "kaupankäyntipäivä", "sessio",
    "aamu", "iltapäivä", "scalp", "swing", "lyhyellä", "pitkällä", "aikaväli", "kynttilä",
    "vuosineljännes",
)

# ---- Swahili: East African markets press (NSE Kenya, DSE Tanzania).
QUANTITY_SW: tuple[str, ...] = (
    "mwelekeo", "kasi", "mabadiliko", "kuvunja", "kiwango", "mtetemo", "kiasi", "ukwasi",
    "tofauti", "riba", "kiwango cha ubadilishaji", "msimu", "uhusiano", "msaada", "upinzani",
    "kilele", "chini", "wastani", "dhahabu", "fedha", "mafuta", "shaba", "faharasa", "hisa", "bei",
    "dola", "shilingi", "hifadhi", "mauzo ya nje", "usafirishaji", "mavuno", "benki kuu",
    "uingiliaji", "hati fungani", "mapato", "mfumuko wa bei", "soko",
)
DIRECTION_SW: tuple[str, ...] = (
    "nunua", "uza", "kununua", "kuuza", "kupanda", "kushuka", "panda", "shuka", "inapanda",
    "inashuka", "kurudi", "kuendelea", "imara", "dhaifu", "kuingia", "kutoka", "juu", "chini",
    "kuimarika", "kudhoofika",
)
HORIZON_SW: tuple[str, ...] = (
    "dakika", "saa", "siku", "kila siku", "wiki", "kila wiki", "mwezi", "kila mwezi", "usiku",
    "kufunga", "kufungua", "kikao", "asubuhi", "mchana", "muda mfupi", "muda mrefu", "robo",
)

#: Per-language (quantity, direction, horizon) seeds; English is always searched as well.
_VOCAB: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "zh": (QUANTITY_ZH, DIRECTION_ZH, HORIZON_ZH),
    "zh-Hant": (QUANTITY_ZHT + QUANTITY_ZH, DIRECTION_ZHT + DIRECTION_ZH,
                HORIZON_ZHT + HORIZON_ZH),
    "ja": (QUANTITY_JA + QUANTITY_ZH, DIRECTION_JA + DIRECTION_ZH, HORIZON_JA + HORIZON_ZH),
    "ko": (QUANTITY_KO, DIRECTION_KO, HORIZON_KO),
    "ru": (QUANTITY_RU, DIRECTION_RU, HORIZON_RU),
    "uk": (QUANTITY_UK + QUANTITY_RU, DIRECTION_UK + DIRECTION_RU, HORIZON_UK + HORIZON_RU),
    "vi": (QUANTITY_VI, DIRECTION_VI, HORIZON_VI),
    "th": (QUANTITY_TH, DIRECTION_TH, HORIZON_TH),
    "id": (QUANTITY_ID, DIRECTION_ID, HORIZON_ID),
    "hi": (QUANTITY_HI, DIRECTION_HI, HORIZON_HI),
    "de": (QUANTITY_DE, DIRECTION_DE, HORIZON_DE),
    "fr": (QUANTITY_FR, DIRECTION_FR, HORIZON_FR),
    "it": (QUANTITY_IT, DIRECTION_IT, HORIZON_IT),
    "es": (QUANTITY_ES, DIRECTION_ES, HORIZON_ES),
    "pt": (QUANTITY_PT, DIRECTION_PT, HORIZON_PT),
    "ar": (QUANTITY_AR, DIRECTION_AR, HORIZON_AR),
    "tr": (QUANTITY_TR, DIRECTION_TR, HORIZON_TR),
    "he": (QUANTITY_HE, DIRECTION_HE, HORIZON_HE),
    "pl": (QUANTITY_PL, DIRECTION_PL, HORIZON_PL),
    "nl": (QUANTITY_NL, DIRECTION_NL, HORIZON_NL),
    "sv": (QUANTITY_SV, DIRECTION_SV, HORIZON_SV),
    "da": (QUANTITY_DA, DIRECTION_DA, HORIZON_DA),
    "no": (QUANTITY_NO, DIRECTION_NO, HORIZON_NO),
    "fi": (QUANTITY_FI, DIRECTION_FI, HORIZON_FI),
    "sw": (QUANTITY_SW, DIRECTION_SW, HORIZON_SW),
    "en": (QUANTITY_EN, DIRECTION_EN, HORIZON_EN),
}
LANGUAGES: tuple[str, ...] = tuple(_VOCAB)

#: How a language's vocabulary is matched. "sub": plain substring (scripts without spaces);
#: "stem": the word must START at a word boundary and may continue (inflecting languages).
_SUBSTRING_LANGS: frozenset[str] = frozenset({"zh", "zh-Hant", "ja", "ko", "th"})

# ============================================================================== detection
_CJK = re.compile(r"[一-鿿]")
_KANA = re.compile(r"[぀-ヿ]")
_HANGUL = re.compile(r"[가-힯]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_UKR_ONLY = re.compile(r"[іїєґІЇЄҐ]")
_THAI = re.compile(r"[฀-๿]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_HEBREW = re.compile(r"[֐-׿]")
_ARABIC = re.compile(r"[؀-ۿ]")
#: Vietnamese-only letters: the horn/breve vowels and every dotted-below tone vowel. Portuguese
#: and French share the circumflex and tilde, so those are deliberately NOT in this class.
_VIET = re.compile(r"[ăđơưĂĐƠƯạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")

# Traditional-vs-simplified: characters that exist in only ONE script, paired so a reader can
# check them. The count decides, so a Hong Kong post quoting one simplified word stays zh-Hant.
_TRAD_SIMP_PAIRS = (
    "漲涨", "報报", "週周", "價价", "買买", "賣卖", "點点", "幣币", "匯汇", "證证", "現现", "貨货",
    "選选", "權权", "開开", "關关", "時时", "間间", "動动", "轉转", "趨趋", "勢势", "頭头", "態态",
    "線线", "續续", "隨随", "場场", "盤盘", "億亿", "萬万", "數数", "據据", "個个", "們们", "這这",
    "說说", "會会", "來来", "對对", "後后", "過过", "還还", "從从", "電电", "機机", "議议", "業业",
    "產产", "運运", "經经", "濟济", "資资", "訊讯", "網网", "際际", "國国", "學学", "讀读", "寫写",
    "聽听", "問问", "題题", "幾几", "發发", "變变", "麼么", "樣样", "強强", "預预", "測测", "隻只",
    "兩两", "極极", "舉举", "黃黄", "銀银", "銅铜", "歐欧", "鎊镑", "圓圆", "恆恒", "達达", "標标",
    "瓊琼", "壓压", "撐撑", "檔档", "彈弹", "單单", "進进", "當当", "沖冲", "結结", "擇择", "籌筹",
    "碼码", "勝胜", "離离", "內内", "戶户", "賺赚", "虧亏", "損损", "險险", "風风", "獲获", "調调",
    "節节", "與与", "於于", "為为", "無无", "沒没", "長长", "較较", "給给", "讓让", "見见", "觀观",
    "顯显", "響响", "觸触", "擊击", "縮缩", "擴扩",
)
_TRAD_CHARS = frozenset(p[0] for p in _TRAD_SIMP_PAIRS)
_SIMP_CHARS = frozenset(p[1] for p in _TRAD_SIMP_PAIRS)

#: Function words that separate the Latin-script languages. Word-bounded on lowercased text;
#: the language with the most hits wins when it beats English and has at least two. Words that
#: three languages share ("de", "en", "a") are left out on purpose -- they separate nothing.
_STOPWORDS: dict[str, tuple[str, ...]] = {
    "de": ("und", "der", "die", "das", "nicht", "ist", "wird", "wenn", "nach", "bei", "mit",
           "auf", "eine", "einer", "dem", "den", "sich", "auch", "oder", "aber", "über", "für",
           "meist", "oft", "dann", "steigt", "fällt"),
    "fr": ("le", "la", "les", "des", "est", "une", "dans", "après", "pour", "sur", "avec", "pas",
           "sont", "qui", "du", "au", "aux", "cette", "ce", "souvent", "généralement", "quand"),
    "it": ("il", "lo", "della", "del", "che", "non", "gli", "sono", "dopo", "una", "per", "nel",
           "nella", "degli", "delle", "alla", "questo", "spesso", "solitamente", "quando"),
    "es": ("el", "los", "las", "es", "una", "después", "para", "con", "que", "del", "se", "por",
           "al", "cuando", "suele", "también", "suelen", "hacia", "desde"),
    "pt": ("os", "não", "uma", "após", "para", "com", "que", "do", "da", "dos", "das", "na",
           "quando", "costuma", "também", "é", "são", "no", "mais", "pelo", "pela"),
    "id": ("yang", "dan", "dengan", "untuk", "akan", "tidak", "ini", "itu", "dari", "pada", "ke",
           "di", "adalah", "saat", "setelah", "biasanya", "harga", "cenderung", "sering"),
    "tr": ("ve", "bir", "için", "ile", "bu", "sonra", "genellikle", "olarak", "kadar", "ise",
           "gibi", "daha", "çok", "ama", "değil", "zaman", "sonrasında"),
    "pl": ("nie", "się", "jest", "na", "w", "z", "do", "że", "po", "przy", "oraz", "zwykle",
           "często", "ale", "lub", "od", "gdy", "kiedy"),
    "nl": ("het", "een", "niet", "wordt", "zijn", "ook", "als", "vaak", "meestal", "naar", "dan",
           "bij", "van", "voor", "na", "op", "dat", "wanneer"),
    "sv": ("och", "att", "är", "inte", "som", "för", "på", "med", "det", "ett", "efter", "när",
           "brukar", "ofta", "av", "till", "från", "sedan"),
    "da": ("og", "at", "er", "ikke", "som", "for", "på", "med", "det", "et", "efter", "når",
           "plejer", "ofte", "af", "til", "fra", "hvad", "meget", "kun"),
    "no": ("og", "at", "er", "ikke", "som", "for", "på", "med", "det", "et", "etter", "når",
           "pleier", "ofte", "av", "til", "fra", "hva", "mye", "bare"),
    "fi": ("ja", "on", "ei", "että", "kun", "jälkeen", "yleensä", "usein", "mutta", "myös", "tai",
           "kanssa", "ovat", "tämä", "jos", "niin", "sitten"),
    "sw": ("na", "ya", "wa", "kwa", "ni", "za", "la", "katika", "baada", "kawaida", "bei", "soko",
           "hisa", "huwa", "mara", "nyingi", "ambayo", "wakati"),
    "en": ("the", "and", "is", "of", "to", "in", "when", "after", "usually", "tends", "with",
           "that", "this", "for", "on", "are", "it", "be", "than", "into"),
}
#: Letters that belong to one Latin-script language alone; each counts as two function words.
_LETTER_HINTS: tuple[tuple[str, str], ...] = (
    ("ß", "de"), ("ł", "pl"), ("ż", "pl"), ("ę", "pl"), ("ą", "pl"), ("ś", "pl"), ("ź", "pl"),
    ("ã", "pt"), ("õ", "pt"), ("ñ", "es"), ("¿", "es"), ("ı", "tr"), ("ğ", "tr"), ("ş", "tr"),
)
_STOP_RE: dict[str, re.Pattern[str]] = {
    lang: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)")
    for lang, words in _STOPWORDS.items()
}


def language_of(text: str) -> str:
    """Language code by script, then by function words for the Latin-script languages.

    Script decides where it can (kana -> ja, hangul -> ko, Thai, Devanagari, Hebrew, Arabic;
    Cyrillic -> uk when a Ukrainian-only letter is present, else ru; CJK -> zh-Hant when
    traditional-only characters outnumber simplified-only ones). The Latin languages are scored
    on function words and one-language letters; English is the fallback, never a winner by
    default, so a Spanish sentence with two Spanish function words is Spanish.
    """
    t = text or ""
    if _KANA.search(t):
        return "ja"
    if _HANGUL.search(t):
        return "ko"
    if _CJK.search(t):
        trad = sum(1 for ch in t if ch in _TRAD_CHARS)
        simp = sum(1 for ch in t if ch in _SIMP_CHARS)
        return "zh-Hant" if trad > simp else "zh"
    if _THAI.search(t):
        return "th"
    if _DEVANAGARI.search(t):
        return "hi"
    if _HEBREW.search(t):
        return "he"
    if _ARABIC.search(t):
        return "ar"
    if _CYRILLIC.search(t):
        return "uk" if _UKR_ONLY.search(t) else "ru"
    if len(_VIET.findall(t)) >= 2:
        return "vi"
    low = t.lower()
    score: dict[str, int] = {lang: len(rx.findall(low)) for lang, rx in _STOP_RE.items()}
    for ch, lang in _LETTER_HINTS:
        if ch in low:
            score[lang] = score.get(lang, 0) + 2
    en = score.pop("en", 0)
    best = max(score, key=lambda k: score[k]) if score else "en"
    return best if score.get(best, 0) >= 2 and score[best] > en else "en"


def is_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


# ============================================================================== the fence
#: Crypto-exchange-native ground is never hunted (principal, 2026-08-18). Any claim naming one of
#: these is dropped and COUNTED; the count is on the report so the fence is visible, not silent.
#: Widened 2026-09-05 with every region's exchanges and the funding/perpetual vocabulary in each
#: script, because a world forest has a crypto-exchange corner in every language.
FORBIDDEN_VENUES: tuple[str, ...] = (
    "binance", "bybit", "okx", "okex", "huobi", "htx", "hyperliquid", "bitget", "gate.io",
    "kucoin", "deribit", "coinbase", "kraken", "币安", "欧易", "火币", "抹茶", "资金费率",
    "funding rate", "永续合约", "perpetual", "perp ", "合约爆仓", "现货杠杆", "u本位", "币本位",
    # regional exchanges and forums
    "upbit", "bithumb", "coinone", "업비트", "빗썸", "코인원", "코인판", "coinpan", "bitflyer",
    "coincheck", "ビットフライヤー", "コインチェック", "gmoコイン", "wazirx", "coindcx",
    "coinswitch", "zebpay", "indodax", "tokocrypto", "bitkub", "luno", "bitso", "mercado bitcoin",
    "mexc", "bitmex", "bitfinex", "bitstamp", "dydx", "phemex", "crypto.com", "paribu", "btcturk",
    "exmo", "garantex", "whitebit", "zonda", "bitpanda",
    # funding / perpetual vocabulary in the other scripts
    "永續合約", "資金費率", "無期限先物", "資金調達率", "무기한 선물", "펀딩비", "펀딩 수수료",
    "фандинг", "бессрочн", "hợp đồng vĩnh cửu", "phí funding", "ฟันดิ้ง", "สัญญาถาวร",
    "funding-rate", "taxa de funding", "tasa de funding", "funding fee",
)


def forbidden_venue(text: str) -> str | None:
    """The first crypto-exchange token the text names, or None."""
    low = (text or "").lower()
    for v in FORBIDDEN_VENUES:
        if v in low:
            return v
    return None


# ============================================================================== instruments
#: Aliases -> Fusion symbols, most likely broker name FIRST. Every first candidate is a symbol in
#: desks/mt5/data/universe/universe.json (a test pins this); later candidates are other brokers'
#: names for the same contract, kept so the resolver still lands when the universe is unknown.
#: An empty tuple means "no MT5 analogue -- mechanism-class transfer only", and the third field
#: says which class the mechanism transfers to.
INSTRUMENT_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    # ---- metals
    (("黄金", "沪金", "au9999", "au(t+d)", "伦敦金", "金价", "gold", "xauusd", "comex黄金", "黃金",
      "ゴールド", "金相場", "골드", "금값", "золот", "vàng", "ทองคำ", "ทอง", "emas", "सोना",
      "गोल्ड", "ذهب", "الذهب", "altın", "ons altın", "זהב", "złoto", "goud", "guld", "gull",
      "kulta", "dhahabu", "oro", "ouro", "l'or", "once d'or", "xau", "gc="), ("XAUUSD",), "metals"),
    (("白银", "沪银", "伦敦银", "银价", "silver", "xagusd", "白銀", "シルバー", "은값", "серебр",
      "bạc", "โลหะเงิน", "perak", "चांदी", "فضة", "الفضة", "gümüş", "srebro", "zilver", "silber",
      "sølv", "hopea", "plata", "prata", "argento", "xag"), ("XAGUSD",), "metals"),
    (("铂金", "platinum", "xptusd", "白金", "プラチナ", "백금", "платин", "platino", "platina",
      "platin"), ("XPTUSD",), "metals"),
    (("钯金", "palladium", "xpdusd", "パラジウム", "팔라듐", "паллад", "paladio", "paládio"),
     ("XPDUSD",), "metals"),
    (("铜", "沪铜", "伦铜", "copper", "xcuusd", "銅", "구리", "медь", "ทองแดง", "tembaga",
      "तांबा", "نحاس", "bakır", "miedź", "koper", "kupfer", "cuivre", "cobre", "rame", "koppar",
      "kobber", "kupari", "shaba"), ("XCUUSD", "COPPER", "HG"), "metals"),
    (("沪铝", "铝", "aluminium", "aluminum", "xalusd", "アルミ", "алюмин", "aluminio", "alumínio"),
     ("XALUSD",), "metals"),
    (("沪镍", "镍", "nickel", "xniusd", "ニッケル", "никел", "níquel"), ("XNIUSD",), "metals"),
    (("沪锌", "锌", "zinc", "xznusd", "亜鉛", "цинк"), ("XZNUSD",), "metals"),
    (("沪铅", "铅", "lead futures", "xpbusd", "свинец", "plomo", "chumbo"), ("XPBUSD",), "metals"),
    # ---- energy
    (("原油", "布油", "美原油", "sc原油", "wti", "brent", "crude", "石油", "原油価格", "유가",
      "нефт",
      "dầu thô", "น้ำมันดิบ", "minyak mentah", "कच्चा तेल", "نفط", "خام برنت", "petrol", "ropa",
      "olie", "rohöl", "pétrole", "petróleo", "petrolio", "olja", "olje", "öljy", "mafuta",
      "brent crude", "ホルムズ", "opec", "أوبك"),
     ("XTIUSD", "XBRUSD", "USOIL", "UKOIL"), "energy"),
    (("天然气", "natural gas", "natgas", "xngusd", "天然ガス", "천연가스", "газ", "khí đốt",
      "gas alam", "erdgas", "gaz naturel", "gás natural", "gas natural", "henry hub", "ttf"),
     ("XNGUSD", "NATGAS"), "energy"),
    # ---- indices with a Fusion symbol
    (("恒指", "恒生", "港股", "hsi", "恆指", "恆生", "hang seng", "hangseng", "hk50", "ハンセン",
      "항셍"), ("HK50", "HSI"), "indices"),
    (("国企指数", "國企指數", "h股", "hscei", "chinah", "china h-shares"), ("CHINAH",), "indices"),
    (("纳指", "纳斯达克", "nasdaq", "nas100", "ustec", "那斯達克", "納斯達克", "ナスダック",
      "나스닥",
      "насдак", "ndx"), ("NAS100", "USTEC"), "indices"),
    (("标普", "s&p", "spx", "us500", "美股", "標普", "sp500", "s&p 500", "s&p500", "美国股市",
      "spy"), ("US500", "SPX500"), "indices"),
    (("道指", "dow", "us30", "道瓊", "ダウ", "다우", "dow jones", "djia"), ("US30", "DJ30"),
     "indices"),
    (("罗素", "russell 2000", "russell", "us2000", "rty"), ("US2000",), "indices"),
    (("德指", "dax", "ger40", "de40", "德國dax", "дакс"), ("GER40", "DE40"), "indices"),
    (("日经", "nikkei", "jp225", "日股", "日経", "日経225", "日経平均", "닛케이", "日經", "jpn225",
      "никкей", "nikkei 225"), ("JPN225", "JP225"), "indices"),
    (("富时", "ftse", "uk100", "富時", "footsie", "ftse 100"), ("UK100",), "indices"),
    (("cac", "cac 40", "cac40", "fra40", "法国股指"), ("FRA40",), "indices"),
    (("euro stoxx", "eurostoxx", "sx5e", "eustx50", "stoxx 50", "斯托克"), ("EUSTX50",),
     "indices"),
    (("aex", "neth25", "amsterdam index"), ("NETH25",), "indices"),
    (("ibex", "ibex 35", "ibex35", "e35"), ("E35",), "indices"),
    (("tsx", "s&p/tsx", "ca60", "toronto index"), ("CA60",), "indices"),
    (("asx 200", "asx200", "aus200", "xjo", "spi futures", "s&p/asx"), ("AUS200",), "indices"),
    (("美元指数", "dxy", "dollar index", "usdx", "ドルインデックス", "달러인덱스", "индекс доллара",
      "美元指數"), ("USDX", "DXY", "USDOLLAR"), "fx"),
    # ---- indices WITHOUT a Fusion symbol: the mechanism transfers to the index class
    (("沪深300", "if合约", "股指期货", "a股", "上证", "中证500", "ic合约", "ih合约", "im合约",
      "a50", "富时中国", "china a50", "csi 300", "上證", "滬深"), (), "indices (China A-share)"),
    (("코스피", "kospi", "코스닥", "kosdaq", "코스피200"), (), "indices (KRX)"),
    (("topix", "東証", "マザーズ", "グロース250"), (), "indices (TSE)"),
    (("台指", "加權指數", "台股", "taiex", "twse", "台指期", "小台"), (), "indices (TWSE)"),
    (("nifty", "bank nifty", "sensex", "निफ्टी", "बैंक निफ्टी", "सेंसेक्स", "finnifty"), (),
     "indices (NSE/BSE)"),
    (("straits times", "sti index", "海峽時報", "msci singapore"), (), "indices (SGX)"),
    (("set50", "set index", "ตลาดหุ้นไทย", "ดัชนี set"), (), "indices (SET)"),
    (("ihsg", "idx composite", "lq45", "jakarta composite"), (), "indices (IDX)"),
    (("klci", "fbm klci", "bursa malaysia", "fkli"), (), "indices (Bursa)"),
    (("psei", "pse index", "philippine stock"), (), "indices (PSE)"),
    (("vn-index", "vnindex", "vn30", "hnx"), (), "indices (HOSE)"),
    (("tadawul", "tasi", "تاسي", "adx index", "dfm index", "qe index"), (),
     "indices (Gulf exchanges)"),
    (("jse", "top40", "alsi", "jse all share"), (), "indices (JSE)"),
    (("ibovespa", "bovespa", "ibov", "índice bovespa", "b3 index"), (), "indices (B3)"),
    (("merval", "s&p merval", "ipc mexico", "bmv ipc", "ipsa", "colcap", "s&p/bvl"), (),
     "indices (LatAm exchanges)"),
    (("wig20", "wig 20", "mwig40", "swig80"), (), "indices (GPW)"),
    (("omxs30", "omxc25", "obx", "omxh25", "omx stockholm"), (), "indices (Nordic exchanges)"),
    (("bist 100", "bist100", "xu100", "borsa istanbul"), (), "indices (BIST)"),
    (("ta-35", "ta35", "ta-125", "tase"), (), "indices (TASE)"),
    (("moex index", "индекс мосбиржи", "ртс", "rts index", "imoex", "ммвб"), (), "indices (MOEX)"),
    (("psx", "kse-100", "kse 100", "dse index", "dsex", "cse all share", "aspi"), (),
     "indices (South Asian exchanges)"),
    (("ngx", "nse all share", "egx30", "egx 30", "nse 20", "masi"), (),
      "indices (African exchanges)"),
    # ---- FX majors
    (("欧元", "欧美", "eurusd", "eur/usd", "ユーロドル", "유로달러", "евродоллар", "euro-dollar",
      "歐元", "euro dollar", "eurodólar", "eurodollaro"), ("EURUSD",), "fx"),
    (("英镑", "镑美", "gbpusd", "gbp/usd", "ポンドドル", "파운드", "фунт", "英鎊", "cable",
      "sterling", "pound"), ("GBPUSD",), "fx"),
    (("日元", "美日", "usdjpy", "usd/jpy", "ドル円", "달러엔", "доллар иена", "日圓", "엔화",
      "円相場", "yen"), ("USDJPY",), "fx"),
    (("澳元", "澳美", "audusd", "aud/usd", "豪ドル", "호주달러", "澳幣", "aussie"), ("AUDUSD",),
     "fx"),
    (("加元", "美加", "usdcad", "usd/cad", "カナダドル", "loonie", "加拿大元"), ("USDCAD",), "fx"),
    (("瑞郎", "美瑞", "usdchf", "usd/chf", "スイスフラン", "swissie", "瑞士法郎"), ("USDCHF",),
      "fx"),
    (("纽元", "nzdusd", "nzd/usd", "kiwi", "紐元", "ニュージーランドドル"), ("NZDUSD",), "fx"),
    (("ユーロ円", "eurjpy", "eur/jpy"), ("EURJPY",), "fx"),
    (("ポンド円", "gbpjpy", "gbp/jpy"), ("GBPJPY",), "fx"),
    (("豪ドル円", "audjpy", "aud/jpy"), ("AUDJPY",), "fx"),
    (("eurgbp", "eur/gbp", "ユーロポンド"), ("EURGBP",), "fx"),
    # ---- FX exotics Fusion quotes: each region's own currency
    (("人民币", "离岸人民币", "usdcnh", "cnh", "人民幣", "usd/cnh", "usd/cny", "人民元"),
     ("USDCNH",), "fx"),
    (("港币", "港幣", "usdhkd", "usd/hkd", "港元", "hkd peg", "聯繫匯率", "联系汇率", "hkma"),
     ("USDHKD",), "fx"),
    (("원달러", "달러원", "usdkrw", "usd/krw", "원화", "won", "韓元", "韩元"), ("USDKRW",), "fx"),
    (("rupee", "usdinr", "usd/inr", "रुपया", "रुपये", "inr"), ("USDINR",), "fx"),
    (("บาท", "usdthb", "usd/thb", "baht", "thai baht"), ("USDTHB",), "fx"),
    (("rupiah", "usdidr", "usd/idr", "idr"), ("USDIDR",), "fx"),
    (("usdsgd", "usd/sgd", "sing dollar", "singapore dollar", "新元", "sgd"), ("USDSGD",), "fx"),
    (("usdbrl", "usd/brl", "dólar/real", "dolar/real", "real brasileiro", "brl"), ("USDBRL",),
     "fx"),
    (("usdmxn", "usd/mxn", "peso mexicano", "mxn", "superpeso"), ("USDMXN",), "fx"),
    (("usdtry", "usd/try", "dolar/tl", "dolar tl", "dolar kuru", "lira", "türk lirası", "try"),
     ("USDTRY",), "fx"),
    (("usdzar", "usd/zar", "rand", "zar"), ("USDZAR",), "fx"),
    (("usdils", "usd/ils", "shekel", "שקל", "דולר שקל", "ils"), ("USDILS",), "fx"),
    (("usdpln", "usd/pln", "złoty", "zloty", "pln", "eurpln", "eur/pln"), ("USDPLN",), "fx"),
    (("usdhuf", "usd/huf", "forint", "huf", "eurhuf", "eur/huf"), ("USDHUF",), "fx"),
    (("usdczk", "usd/czk", "koruna", "czk", "eurczk", "eur/czk"), ("USDCZK",), "fx"),
    (("usdsek", "usd/sek", "svenska kronan", "kronan", "sek", "eursek", "eur/sek"), ("USDSEK",),
     "fx"),
    (("usdnok", "usd/nok", "norske kronen", "nok", "eurnok", "eur/nok"), ("USDNOK",), "fx"),
    (("usddkk", "usd/dkk", "danske kronen", "dkk", "eurdkk", "eur/dkk"), ("USDDKK",), "fx"),
    (("usdrub", "usd/rub", "рубл", "курс доллара", "rub", "eurrub"), ("USDRUB",), "fx"),
    # currencies with no Fusion pair: the mechanism transfers to the FX class
    (("đồng việt nam", "tỷ giá usd/vnd", "usd/vnd", "vnd"), (), "fx (VND not quoted)"),
    (("ringgit", "usd/myr", "myr"), (), "fx (MYR not quoted)"),
    (("philippine peso", "usd/php", "php"), (), "fx (PHP not quoted)"),
    (("naira", "usd/ngn", "ngn"), (), "fx (NGN not quoted)"),
    (("egyptian pound", "usd/egp", "egp", "الجنيه"), (), "fx (EGP not quoted)"),
    (("kenyan shilling", "usd/kes", "shilingi", "kes"), (), "fx (KES not quoted)"),
    (("dirham", "usd/aed", "riyal", "usd/sar", "الريال", "الدرهم"), (), "fx (Gulf pegs)"),
    (("peso argentino", "usd/ars", "dólar blue", "dolar blue", "ars", "peso chileno", "usd/clp",
      "peso colombiano", "usd/cop", "sol peruano", "usd/pen"), (), "fx (LatAm not quoted)"),
    (("hryvnia", "гривн", "usd/uah", "uah"), (), "fx (UAH not quoted)"),
    (("pakistani rupee", "usd/pkr", "pkr", "taka", "usd/bdt", "usd/lkr"), (),
     "fx (South Asian not quoted)"),
    # ---- crypto CFDs Fusion quotes (the asset, never the exchange)
    (("比特币", "bitcoin", "btcusd", "ビットコイン", "비트코인", "биткоин"), ("BTCUSD",),
      "crypto_cfd"),
    (("以太坊", "ethereum", "ethusd", "イーサリアム", "이더리움", "эфир"), ("ETHUSD",),
      "crypto_cfd"),
    # ---- softs and grains
    (("大豆", "soybean", "soybeans", "soja", "soya", "đậu tương", "大豆先物"),
     ("SOYBEAN", "SOYBEANS", "ZS"), "softs"),
    (("玉米", "corn", "maize", "milho", "maíz", "トウモロコシ", "кукуруз"), ("CORN", "ZC"),
      "softs"),
    (("白糖", "sugar", "açúcar", "azúcar", "砂糖", "сахар", "gula"), ("SUGAR", "SUGARRAW", "SB"),
     "softs"),
    (("棉花", "cotton", "algodão", "algodón", "綿花", "хлопок"), ("COTTON", "CT"), "softs"),
    (("咖啡", "coffee", "arabica", "café", "kahve", "コーヒー", "кофе", "cà phê"),
     ("COFARA", "COFROB", "COFFEE", "KC"), "softs"),
    (("robusta", "robusta coffee"), ("COFROB", "COFARA"), "softs"),
    (("小麦", "wheat", "trigo", "blé", "小麦先物", "пшениц", "weizen"), ("WHEAT", "ZW"), "softs"),
    (("可可", "cocoa", "cacao", "kakao", "ココア", "какао", "cocoa board", "ghana cocoa",
      "ivory coast cocoa"), ("USCOCOA", "UKCOCOA", "COCOA"), "softs"),
    (("orange juice", "fcoj", "suco de laranja"), ("OJ",), "softs"),
    # ---- rates the desk can quote
    (("美国国债", "美债", "treasuries", "10-year treasury", "10y treasury", "ust10y", "10年債",
      "米国債", "10-year yield", "10y yield", "tnote", "t-note"), ("UST10Y", "UST05Y"),
     "rates"),
    (("gilt", "gilts", "ukgilt", "英国国债"), ("UKGILT",), "rates"),
    # ---- share CFDs Fusion quotes, where a region's own press names them
    (("台積電", "台积电", "tsmc", "taiwan semiconductor", "2330"), ("TSMC",), "equities"),
    (("トヨタ", "toyota", "7203"), ("Toyota",), "equities"),
    (("阿里巴巴", "alibaba", "baba", "9988"), ("AlibabaGroup",), "equities"),
    (("百度", "baidu"), ("Baidu",), "equities"),
    (("蔚来", "蔚來", "nio inc"), ("NIO",), "equities"),
    (("特斯拉", "テスラ", "테슬라", "tesla", "tsla"), ("Tesla",), "equities"),
    (("英伟达", "輝達", "エヌビディア", "엔비디아", "nvidia", "nvda"), ("NVIDIA",), "equities"),
    # ---- NO MT5 ANALOGUE: the mechanism transfers to the class, the instrument does not.
    (("螺纹钢", "螺纹", "热卷", "铁矿石", "铁矿", "焦炭", "焦煤", "动力煤", "iron ore", "鉄鉱石"),
     (), "metals/energy"),
    (("甲醇", "pta", "乙二醇", "纯碱", "玻璃", "尿素", "沥青", "橡胶", "pvc", "pp", "塑料"),
     (), "energy"),
    (("豆粕", "菜油", "菜粕", "棕榈油", "豆油", "鸡蛋", "生猪", "苹果", "红枣", "花生", "palm oil",
      "cpo", "minyak sawit"), (), "softs"),
    (("碳酸锂", "工业硅", "氧化铝", "沪锡", "lithium", "tin futures"), (), "metals"),
    (("国债期货", "十债", "五债", "二债", "bund futures", "jgb", "btp futures", "oat futures",
      "ofz", "офз", "selic futures", "di futures", "cetes", "kkm"), (), "rates->fx carry"),
    (("可转债", "转债", "打新", "涨停", "跌停", "龙虎榜", "北向资金"), (), "cn-equities-only"),
    (("baltic dry", "bdi", "freight index", "運賃指数", "drewry", "world container index",
      "scfi", "fbx"), (), "shipping/freight -> commodity currencies"),
)

#: INDIRECT CHANNELS: a foreign dataset, event or institution that moves an MT5 instrument
#: through an information shock rather than by naming it. The claim is recorded with
#: `channel="indirect"` and the instrument the shock lands on, so the funnel can measure whether
#: indirect channels convert (principal 2026-09-05: "indirect edges are the point").
INDIRECT_CHANNELS: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    # central banks -> the pair they set
    (("fomc", "federal reserve", "the fed", "美联储", "fed funds", "连准会", "聯準會", "фрс",
      "パウエル"), ("USDX", "US500"), "policy: Fed -> dollar and US equities"),
    (("ecb", "european central bank", "欧洲央行", "歐洲央行", "bce", "ezb", "ецб", "lagarde"),
     ("EURUSD",), "policy: ECB -> EUR"),
    (("bank of england", "boe", "英国央行", "英國央行", "mpc minutes"), ("GBPUSD",),
      "policy: BoE -> GBP"),
    (("bank of japan", "boj", "日銀", "日本央行", "日本銀行", "為替介入", "介入警戒", "神田財務官",
      "yen intervention", "円買い介入"), ("USDJPY",), "policy: BoJ / MoF intervention -> JPY"),
    (("rba", "reserve bank of australia", "澳洲联储", "澳洲央行"), ("AUDUSD",),
      "policy: RBA -> AUD"),
    (("rbnz", "reserve bank of new zealand"), ("NZDUSD",), "policy: RBNZ -> NZD"),
    (("bank of canada", "boc", "加拿大央行", "macklem"), ("USDCAD",), "policy: BoC -> CAD"),
    (("snb", "swiss national bank", "瑞士央行", "nationalbank"), ("USDCHF",), "policy: SNB -> CHF"),
    (("pboc", "people's bank of china", "人民银行", "中国人民银行", "中间价", "中間價",
      "逆周期因子",
      "cfets"), ("USDCNH",), "policy: PBoC fixing -> CNH"),
    (("hong kong monetary authority", "金管局", "弱方兌換保證", "强方兑换保证"), ("USDHKD",),
     "policy: HKMA peg defence -> HKD"),
    (("bank of korea", "bok", "한국은행", "한은", "외환당국", "구두개입", "smoothing operation"),
     ("USDKRW",), "policy: BoK / MoEF -> KRW"),
    (("reserve bank of india", "rbi", "आरबीआई", "रिज़र्व बैंक", "भारतीय रिज़र्व"), ("USDINR",),
     "policy: RBI -> INR"),
    (("bank of thailand", "bot ", "แบงก์ชาติ", "ธปท", "กนง"), ("USDTHB",), "policy: BoT -> THB"),
    (("bank indonesia", "bi rate", "bi-rate", "bi 7-day", "sri mulyani"), ("USDIDR",),
     "policy: BI -> IDR"),
    (("monetary authority of singapore", "mas ", "s$neer", "sgd neer"), ("USDSGD",),
     "policy: MAS band -> SGD"),
    (("banco central do brasil", "bacen", "copom", "selic", "galípolo", "swap cambial",
      "leilão de swap", "cupom cambial", "conab", "safra de soja", "exportações de soja",
      "soy exports", "brazil soy", "iron ore exports", "minério de ferro"), ("USDBRL",),
     "flow/policy: Brazil (BCB, soy, iron ore) -> BRL"),
    (("banxico", "banco de méxico", "banco de mexico", "remesas", "remittances", "nearshoring"),
     ("USDMXN",), "policy/flow: Banxico, remittances -> MXN"),
    (("cbrt", "tcmb", "merkez bankası", "merkez bankasi", "türkiye cumhuriyet merkez", "kkm",
      "karahan", "şimşek", "simsek"), ("USDTRY",), "policy: CBRT -> TRY"),
    (("sarb", "south african reserve bank", "reserve bank of south africa", "eskom",
      "load shedding", "platinum exports", "rand exports"), ("USDZAR",),
     "policy/flow: SARB, mining exports, power -> ZAR"),
    (("bank of israel", "boi ", "בנק ישראל"), ("USDILS",), "policy: BoI -> ILS"),
    (("nbp", "narodowy bank polski", "rpp", "rada polityki pieniężnej", "glapiński"), ("USDPLN",),
     "policy: NBP -> PLN"),
    (("mnb", "magyar nemzeti bank", "hungarian central bank"), ("USDHUF",), "policy: MNB -> HUF"),
    (("cnb", "czech national bank", "česká národní banka"), ("USDCZK",), "policy: CNB -> CZK"),
    (("riksbank", "riksbanken"), ("USDSEK",), "policy: Riksbank -> SEK"),
    (("norges bank", "oljefondet", "government pension fund global", "nbim"), ("USDNOK",),
     "policy/flow: Norges Bank and the oil fund -> NOK"),
    (("danmarks nationalbank", "nationalbanken"), ("USDDKK",), "policy: DN peg -> DKK"),
    (("bank of russia", "цб рф", "центробанк", "набиуллина", "ключевая ставка", "минфин",
      "бюджетное правило", "urals"), ("USDRUB",), "policy: CBR / MinFin -> RUB"),
    # commodity shocks -> commodity and the currency that exports it
    (("opec+", "opec", "أوبك", "saudi output", "saudi aramco", "eia inventories", "api inventories",
      "cushing", "strait of hormuz", "hormuz", "red sea", "houthi", "ホルムズ海峡"),
     ("XTIUSD", "XBRUSD", "USDCAD", "USDNOK"),
      "energy flow: OPEC / inventories / chokepoints -> oil, CAD, NOK"),
    (("shanghai gold premium", "sge premium", "上海金溢价", "上海黄金交易所", "上海金", "水贝",
      "india gold imports", "gold import duty", "central bank gold buying", "央行购金",
      "pboc gold"), ("XAUUSD",), "physical premia / official buying -> gold"),
    (("chilean copper", "codelco", "escondida", "ilo copper", "lme stocks", "lme inventories",
      "上期所库存"), ("XCUUSD", "AUDUSD"), "inventory: copper supply and stocks -> copper, AUD"),
    (("iron ore price", "pilbara", "port hedland", "铁矿石价格", "australian exports", "abares"),
     ("AUDUSD",), "flow: Australian bulk exports -> AUD"),
    (("dairy auction", "gdt auction", "fonterra", "global dairy trade"), ("NZDUSD",),
     "auction: dairy prices -> NZD"),
    (("wasde", "usda crop", "usda export sales", "crop progress", "la niña", "el niño", "el nino",
      "la nina", "monsoon"), ("SOYBEAN", "CORN", "WHEAT", "USDBRL"),
     "weather/agri report -> grains and BRL"),
    (("ghana cocoa board", "cocobod", "ivory coast harvest", "côte d'ivoire cocoa"),
     ("USCOCOA", "UKCOCOA"), "harvest: West African cocoa -> cocoa"),
    (("vietnam coffee exports", "vietnam robusta", "brazil coffee crop", "minas gerais frost"),
     ("COFROB", "COFARA"), "harvest: coffee origins -> coffee"),
    (("baltic dry", "freight rates", "container rates", "運賃", "运费", "shipping index",
      "drewry", "xeneta"), ("AUDUSD", "USDZAR", "USDBRL"),
      "shipping: freight indices -> commodity FX"),
    # positioning and flows
    (("cot report", "commitments of traders", "cftc positioning", "spec positioning", "tff report"),
     ("XAUUSD", "EURUSD", "USDJPY"), "positioning: CFTC -> FX and gold"),
    (("gold etf flows", "gld flows", "spdr gold holdings", "etf holdings", "金etf"),
     ("XAUUSD",), "fund flows: gold ETFs -> gold"),
    (("northbound flows", "southbound flows", "北向资金", "南下资金", "港股通", "陆股通", "北水"),
     ("HK50", "CHINAH", "USDCNH"), "flow: Stock Connect -> HK indices and CNH"),
    (("toshin", "投信", "nisa flows", "japanese investors", "lifers", "生保"), ("USDJPY",),
     "flow: Japanese outbound investment -> JPY"),
    (("fii flows", "fpi flows", "dii flows", "foreign portfolio"), ("USDINR",),
     "flow: India portfolio flows -> INR"),
    (("外資", "外资买卖超", "外資買賣超"), ("TSMC",), "flow: Taiwan foreign investors -> TSMC"),
    # sovereign auctions and fiscal
    (("treasury auction", "bond auction", "auction tail", "国债拍卖", "国債入札", "入札結果",
      "leilão do tesouro", "subasta del tesoro", "аукцион офз"), ("UST10Y", "USDX"),
     "auction: sovereign debt -> rates and dollar"),
    (("capital controls", "资本管制", "資本管制", "cepo cambiario", "capital flow measures",
      "外汇管制", "controle de capitais", "sermaye kontrolü"), ("USDCNH", "USDTRY", "USDINR"),
     "policy: capital controls -> the pair they fence"),
)


_LATIN = "a-z0-9À-ɏ"


def _alias_pattern(alias: str) -> str:
    """Substring for CJK/Thai/Arabic aliases; word-bounded for Latin ones, so `gold` does not
    match `golden` and `dow` does not match `download`."""
    starts = re.match(rf"[{_LATIN}]", alias) is not None
    ends = re.search(rf"[{_LATIN}]$", alias) is not None
    return ((rf"(?<![{_LATIN}])" if starts else "") + re.escape(alias)
            + (rf"(?![{_LATIN}])" if ends else ""))


_ALIAS_RE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _alias_rx(aliases: tuple[str, ...]) -> re.Pattern[str]:
    """ONE compiled alternation per alias tuple, longest alias first. Compiling per alias per
    call thrashed `re`'s 512-entry cache once the table passed a thousand aliases and made a
    page take seconds instead of milliseconds -- measured on the whole-grounds offline test."""
    rx = _ALIAS_RE.get(aliases)
    if rx is None:
        alts = "|".join(_alias_pattern(a) for a in sorted(set(aliases), key=len, reverse=True)
                        if a)
        rx = _ALIAS_RE[aliases] = re.compile(alts or r"(?!x)x")
    return rx


def _alias_hit(alias: str, low: str) -> bool:
    return _alias_rx((alias,)).search(low) is not None


def _first_alias(aliases: tuple[str, ...], low: str) -> str | None:
    m = _alias_rx(aliases).search(low)
    return m.group(0) if m else None


def resolve_instruments(text: str, universe: set[str] | None = None) -> dict[str, Any]:
    """MT5 analogues for every instrument the text names, the transfer-only classes, and the
    indirect channels (dataset/event -> instrument) it triggers."""
    low = (text or "").lower()
    analogues: list[str] = []
    mentioned: list[str] = []
    transfer: list[str] = []
    indirect: list[str] = []
    channels: list[str] = []
    uni = {u.upper() for u in (universe or set())}

    def pick(cands: tuple[str, ...]) -> str | None:
        if not uni:
            return cands[0]
        return next((c for c in cands if c.upper() in uni), None)

    for aliases, cands, cls in INSTRUMENT_ALIASES:
        hit = _first_alias(aliases, low)
        if hit is None:
            continue
        mentioned.append(hit)
        if not cands:
            transfer.append(f"{hit}->{cls}")
            continue
        chosen = pick(cands)
        if chosen and chosen not in analogues:
            analogues.append(chosen)
        elif chosen is None:
            transfer.append(f"{hit}->{cls} (not quoted here)")
    for aliases, cands, note in INDIRECT_CHANNELS:
        hit = _first_alias(aliases, low)
        if hit is None:
            continue
        channels.append(f"{hit}: {note}")
        for c in cands:
            chosen = c if not uni else (c if c.upper() in uni else None)
            if chosen and chosen not in analogues and chosen not in indirect:
                indirect.append(chosen)
    return {"analogues": analogues, "mentioned": mentioned, "transfer_only": transfer,
            "indirect": indirect, "channels": channels}


# ============================================================================== mechanism class
#: The orthogonality vocabulary (principal 2026-09-05): every claim is tagged with ONE class so a
#: later scorer can prefer classes the portfolio lacks, and a ground that yields only momentum
#: says so on the report. First class whose term appears wins; the order is deliberate --
#: specific structural classes before the two generic price-pattern classes.
MECHANISM_CLASSES: tuple[str, ...] = (
    "policy", "calendar", "positioning", "inventory", "flow", "carry", "cross_asset",
    "microstructure", "reversion", "momentum",
)
_CLASS_TERMS: dict[str, tuple[str, ...]] = {
    "policy": ("central bank", "rate decision", "rate hike", "rate cut", "intervention", "fomc",
               "ecb", "boj", "rbi", "cbrt", "banxico", "copom", "selic", "policy rate",
               "capital control",
               "央行", "加息", "降息", "升息", "干预", "干預", "介入", "政策金利", "日銀",
               "기준금리",
               "한은", "개입", "ставк", "интервенц", "цб", "lãi suất", "ngân hàng nhà nước",
               "ดอกเบี้ย",
               "แทรกแซง", "suku bunga", "intervensi", "ब्याज दर", "आरबीआई", "zins", "leitzins",
               "taux directeur", "tasso", "tipos de interés", "tasa de interés", "juros", "faiz",
               "merkez", "ריבית", "stóp procentow", "rente", "ränta", "korko", "riba", "فائدة",
               "البنك المركزي", "auction", "入札", "leilão", "subasta", "аукцион", "інтервенц",
               "нбу", "rpp", "korkopäätö", "räntebesked", "rentebeslut", "rentemøde", "benki kuu",
               "kuingili", "決定利率", "利率決議"),
    "calendar": ("seasonal", "seasonality", "turn of month", "day of week", "expiry", "witching",
                 "fix", "fixing", "roll", "rollover", "季节", "季節", "月末", "换月", "換月",
                 "结算",
                 "結算", "交割", "到期", "ゴトー日", "五十日", "仲値", "sq", "満期", "만기",
                 "롤오버",
                 "계절", "сезонн", "экспирац", "фиксинг", "đáo hạn", "mùa vụ", "หมดอายุ", "ฤดูกาล",
                 "kedaluwarsa", "musiman", "एक्सपायरी", "मौसमी", "verfall", "hexensabbat", "saison",
                 "échéance", "saisonnal", "scadenza", "stagional", "vencimiento", "estacional",
                 "sazonal", "vade", "mevsimsel", "wygaśnięci", "sezonow", "expiratie", "seizoen",
                 "förfall", "säsong", "udløb", "sæson", "forfall", "sesong", "erääntymi", "kausi",
                 "msimu", "موسمي", "quarter-end", "year-end", "options expiry", "opex", "фіксинг",
                 "експірац"),
    "positioning": ("cot", "commitments of traders", "positioning", "open interest", "net long",
                    "net short", "speculators", "crowded", "short squeeze", "持仓量", "持仓",
                    "多空比",
                    "主力", "净持仓", "建玉", "미결제약정", "포지션", "수급", "외국인",
                    "открыт интерес",
                    "позици", "шорт-сквиз", "khối ngoại", "tự doanh", "ต่างชาติ", "asing", "fii",
                    "dii",
                    "ओपन इंटरेस्ट", "pcr", "positionierung", "positionnement", "posizionamento",
                    "posicionamiento", "posicionamento", "estrangeiro", "外資", "法人", "籌碼",
                    "pozycjonowan", "positionering", "positiointi", "gamma", "dealer"),
    "inventory": ("inventory", "inventories", "stocks", "stockpile", "warehouse", "eia",
    "api report",
                  "lme stocks", "harvest", "crop", "wasde", "库存", "庫存", "产量", "產量", "在庫",
                  "재고",
                  "запас", "урожа", "tồn kho", "สต็อก", "stok", "persediaan", "भंडार", "मानसून",
                  "lagerbestand", "lagerbestände", "ernte", "récolte", "scorte", "raccolto",
                  "inventario", "existencias", "cosecha", "estoque", "safra", "hasat", "mavuno",
                  "hifadhi", "zapas", "zbior", "voorraad", "oogst", "lager", "skörd", "høst",
                  "avling", "varasto", "sato", "مخزون", "weather", "天气", "天候", "cuaca",
                  "monsoon",
                  "el niño", "la niña", "frost", "drought"),
    "flow": ("flow", "flows", "etf", "fund flows", "exports", "imports", "shipping", "freight",
             "remittances", "northbound", "southbound", "资金流", "資金流", "北向", "南下",
             "港股通",
             "出口", "进口", "运费", "運費", "実需", "輸出", "投信", "환율", "수출", "운임",
             "экспорт",
             "фрахт", "dòng tiền", "xuất khẩu", "cước", "ฟันด์โฟลว์", "ส่งออก", "ค่าระวาง",
             "aliran dana", "ekspor", "निर्यात", "आयात", "fracht", "export", "fret", "flux",
             "exportations", "noli", "flusso", "flujo", "flete", "exportaciones", "fluxo", "frete",
             "exportação", "ihracat", "navlun", "eksport", "vracht", "frakt", "vienti", "rahti",
             "usafirishaji", "صادرات", "شحن", "baltic", "container", "cargo", "auction"),
    "carry": ("carry", "swap", "interest differential", "rate differential", "yield differential",
              "funding", "套息", "利差", "掉期", "隔夜利息", "スワップ", "キャリー", "金利差",
              "캐리",
              "스왑", "금리차", "кэрри", "своп", "chênh lệch lãi suất", "ส่วนต่างดอกเบี้ย",
              "selisih bunga",
              "zinsdifferenz", "différentiel", "differenziale", "diferencial", "cupom cambial",
              "taşıma", "swap", "ränte", "korkoero", "carry trade"),
    "cross_asset": ("correlation", "cointegration", "lead-lag", "lead lag", "spread between",
    "ratio",
                    "pairs", "relative value", "basis", "term structure", "curve", "相关", "相關",
                    "协整",
                    "領先", "领先", "滞后", "金银比", "金油比", "沪伦比", "内外盘", "跨市",
                    "跨品种",
                    "基差", "期限结构", "相関", "乖離", "裁定", "상관관계", "괴리율", "차익거래",
                    "корреляц", "арбитраж", "базис", "tương quan", "chênh lệch", "ความสัมพันธ์",
                    "korelasi", "सहसंबंध", "korrelation", "arbitrage", "corrélation",
                    "correlazione",
                    "correlación", "correlação", "korelasyon", "מתאם", "korelac", "correlatie",
                    "korrelasjon", "korrelaatio", "uhusiano", "ارتباط", "contango",
                    "backwardation"),
    "microstructure": ("order flow", "orderflow", "liquidity", "spread", "slippage", "imbalance",
                       "book", "tick", "vwap", "auction", "stop hunt", "sweep", "market maker",
                       "盘口", "订单流", "滑点", "冲击成本", "做市", "流动性", "盤口", "滑價",
                       "造市",
                       "板", "歩み値", "スリッページ", "気配", "호가", "체결", "슬리피지", "стакан",
                       "проскальзыван", "ликвидн", "thanh khoản", "สภาพคล่อง", "likuiditas",
                       "लिक्विडिटी", "orderfluss", "liquidität", "liquidité", "liquidità",
                       "liquidez",
                       "likidite", "נזילות", "płynność", "liquiditeit", "likviditet",
                       "likviditeetti",
                       "ukwasi", "سيولة", "session", "夜盘", "夜盤", "早盘", "尾盘",
                       "开盘", "收盘", "寄り", "引け", "장초", "장마감", "открыти", "закрыти"),
    "reversion": ("mean reversion", "revert", "reversal", "fade", "bounce", "pullback",
    "overbought",
                  "oversold", "range", "均值回归", "均值回复", "反转", "反弹", "回调", "逆势",
                  "抄底",
                  "均值回歸", "反轉", "反彈", "回檔", "逆張り", "平均回帰", "反発", "反落",
                  "押し目",
                  "戻り", "역추세", "평균회귀", "반등", "되돌림", "눌림목", "разворот", "возврат",
                  "откат", "отскок", "đảo chiều", "hồi quy", "hồi phục", "điều chỉnh", "กลับตัว",
                  "รีบาวด์", "ปรับฐาน", "pembalikan", "rebound", "koreksi", "रिवर्सल", "पलटाव",
                  "उछाल", "umkehr", "rückkehr", "erhol", "retournement", "rebond", "inversione",
                  "rimbalz", "reversión", "rebote", "reversão", "repique", "dönüş", "toparlan",
                  "היפוך", "odwrócen", "odbici", "omkeer", "herstel", "vändning", "rekyl",
                  "vending",
                  "käänne", "انعكاس", "ارتداد", "contrarian", "відскок", "розворот", "kurudi"),
    "momentum": ("momentum", "trend", "breakout", "continuation", "follow", "动量", "趋势", "突破",
                 "顺势", "延续", "追涨", "動量", "趨勢", "順勢", "モメンタム", "順張り", "ブレイク",
                 "続伸", "続落", "모멘텀", "추세", "돌파", "моментум", "импульс", "пробой",
                 "xu hướng",
                 "động lượng", "phá vỡ", "โมเมนตัม", "แนวโน้ม", "ทะลุ", "tren", "penembusan",
                 "मोमेंटम", "ट्रेंड", "ब्रेकआउट", "ausbruch", "tendance", "cassure", "tendenza",
                 "rottura", "tendencia", "ruptura", "tendência", "rompimento", "kırılım", "מגמה",
                 "פריצה", "wybicie", "uitbraak", "utbrott", "udbrud", "utbrudd", "läpimurto",
                 "mwelekeo", "kuvunja", "kasi", "زخم", "اتجاه", "اختراق", "wybici", "läpimur",
                 "пробій", "імпульс"),
}
#: Direction buckets for the dedupe key. Not exhaustive: a word outside the buckets is "other",
#: and two tellings of one story still fold together on instrument, class and horizon.
_DIR_BUCKET_TERMS: dict[str, tuple[str, ...]] = {
    "long": ("rallies", "rises", "rose", "rallied", "gained", "gains", "strengthens",
    "strengthened", "appreciates", "climb", "climbs", "surge", "surges", "jumps",
            "long", "buy", "rally", "rise", "bullish", "higher", "strengthen", "appreciate",
    "做多",
             "买入", "看多", "上涨", "涨", "走强", "拉升", "買入", "上漲", "漲", "走強", "買い",
             "ロング",
             "上昇", "続伸", "上がる", "매수", "롱", "상승", "급등", "лонг", "покуп", "рост",
             "растет",
             "растёт", "mua", "tăng", "ซื้อ", "ขึ้น", "beli", "naik", "खरीद", "तेजी", "बढ़", "kauf",
             "steig", "achat", "hausse", "compra", "rialzo", "alza", "sube", "alta", "sobe", "alım",
             "yüksel", "קנייה", "עלייה", "kupn", "wzrost", "koop", "stijg", "köp", "stig", "køb",
             "kjøp", "osta", "nous", "nunua", "kupanda", "شراء", "صعود", "ارتفاع"),
    "short": ("short", "sell", "sell-off", "selloff", "fall", "falls", "fell", "drop", "drops",
              "dropped", "bearish", "lower", "weaken", "weakens", "weakened", "depreciate",
              "depreciates", "slide", "slides", "sinks", "tumbles", "dip", "dips",
              "depreciate", "做空", "卖出", "看空", "下跌", "跌", "走弱", "砸盘", "賣出", "殺盤",
              "売り",
              "ショート", "下落", "続落", "下がる", "매도", "숏", "하락", "급락", "шорт", "прода",
              "падени", "падает", "снижен", "bán", "giảm", "ขาย", "ลง", "jual", "turun", "बेच",
              "मंदी", "गिर", "verkauf", "fall", "fällt", "vente", "baisse", "vend", "ribasso",
              "venta", "baja", "cae", "queda", "satış", "düş", "מכירה", "ירידה", "sprzeda",
              "spadek", "verkoop", "daal", "sälj", "sjunk", "sælg", "fald", "selg", "myy", "lask",
              "uza", "kushuka", "بيع", "هبوط", "انخفاض"),
    "revert": ("fade", "fades", "revert", "reverts", "reverse", "reverses", "reversed", "bounce",
               "bounces", "bounced", "rebound", "rebounds", "pullback", "反向", "回归", "反弹",
               "回落",
               "回调", "抄底", "反轉", "反彈", "回檔", "反発", "反落", "戻る", "押し目買い",
               "戻り売り",
               "반등", "되돌림", "отскок", "разворот", "đảo chiều", "hồi phục", "điều chỉnh",
               "เด้ง",
               "กลับตัว", "ปรับฐาน", "rebound", "koreksi", "berbalik", "पलट", "उछाल", "erhol",
               "dreht", "rebond", "retourne", "rimbalz", "inverte", "rebote", "revierte", "repique",
               "reverte", "tepki", "dön", "korekt", "odwrac", "herstel", "draait", "rekyl",
               "vänder",
               "vender", "snur", "elpy", "kääntyy", "kurudi", "ارتداد", "تصحيح"),
    "continue": ("continues",
                "continue", "continues", "follow", "trend", "顺势", "延续", "順勢", "延續",
    "続伸", "続落",
                 "продолж", "tiếp diễn", "ต่อเนื่อง", "berlanjut", "जारी", "fortsetz", "continue",
                 "prosegue", "continúa", "continua", "devam", "המשך", "kontynu", "vervolg",
                 "fortsätter", "fortsætter", "fortsetter", "jatkuu", "kuendelea", "استمرار"),
    "widen": ("widens", "expands", "steepens",
             "widen", "widens", "expand", "expands", "steepen", "steepens", "扩大", "擴大",
    "拡大", "확대", "расшир", "mở rộng",
              "ขยาย", "melebar", "ausweit", "s'élargit", "si allarga", "se amplía", "amplia",
              "genişle"),
    "narrow": ("narrows", "contracts", "flattens",
              "narrow", "narrows", "contract", "contracts", "flatten", "flattens", "收窄", "收敛",
    "收斂", "縮小", "축소", "сужен",
               "thu hẹp", "แคบลง", "menyempit", "verengt", "se resserre", "si restringe",
               "se estrecha", "estreita", "daral"),
}
_HOR_BUCKET_TERMS: dict[str, tuple[str, ...]] = {
    "tick": ("tick", "秒级", "秒", "틱", "тик", "scalp", "スキャルピング", "스캘핑", "скальп"),
    "intraday": ("minute", "minutes", "hour", "hours", "hourly", "intraday", "session", "open",
                 "close", "m5", "m15", "h1", "h4", "分钟", "小时", "日内", "夜盘", "早盘", "尾盘",
                 "开盘后", "收盘前", "分鐘", "小時", "日內", "夜盤", "盤中", "分", "時間",
                 "デイトレ",
                 "寄り", "引け", "日中", "分足", "時間足", "ザラ場", "분", "시간", "장중", "분봉",
                 "시간봉", "단타", "минут", "час", "интрадей", "внутри дня", "phút", "giờ",
                 "trong phiên", "cuối phiên", "đầu phiên", "นาที", "ชั่วโมง", "ระหว่างวัน", "menit",
                 "jam", "sesi", "मिनट", "घंटा", "घंटे", "इंट्राडे", "minute", "stunde", "heure",
                 "séance", "minut", "ora", "seduta", "minuto", "hora", "sesión", "sesion", "pregão",
                 "dakika", "saat", "seans", "דקה", "דקות", "שעה", "שעות", "godzin", "sesj",
                 "minuut",
                 "uur", "timme", "timmar", "time", "timer", "tunti", "tuntia", "saa", "دقيقة",
                 "ساعة", "جلسة", "خلال اليوم"),
    "daily": ("daily", "day", "days", "overnight", "next day", "d1", "当日", "次日", "每日", "日线",
              "隔夜", "交易日", "當日", "日線", "隔日沖", "日", "翌日", "日足", "オーバーナイト",
              "일",
              "당일", "익일", "일봉", "오버나잇", "дне", "день", "дневн", "овернайт", "свеч",
              "ngày",
              "qua đêm", "hôm sau", "nến ngày", "วัน", "รายวัน", "ข้ามคืน", "hari", "harian",
              "semalam", "दिन", "दैनिक", "ओवरनाइट", "tag", "täglich", "übernacht", "jour",
              "journalier", "quotidien", "giorn", "día", "diario", "dia", "diário", "gün", "günlük",
              "יום", "יומי", "dzień", "dzienn", "dag", "dagelijks", "daglig", "päivä", "siku",
              "يوم", "يومي"),
    "weekly": ("week", "weekly", "一周", "周线", "周", "一週", "週線", "週", "週足", "주", "주봉",
               "недел", "tuần", "สัปดาห์", "minggu", "pekan", "हफ्ता", "सप्ताह", "woche", "semaine",
               "settiman", "semana", "hafta", "שבוע", "tydzień", "tygodni", "week", "vecka", "uge",
               "uke", "viikko", "wiki", "أسبوع"),
    "monthly": ("month", "monthly", "quarter", "quarterly", "一个月", "月线", "月", "季度",
    "一個月",
                "月線", "月足", "四半期", "월", "월봉", "분기", "месяц", "квартал", "tháng", "quý",
                "เดือน", "ไตรมาส", "bulan", "kuartal", "महीना", "महीने", "मासिक", "तिमाही", "monat",
                "quartal", "mois", "trimestre", "mese", "mensil", "mes", "mês", "ay", "aylık",
                "çeyrek", "חודש", "רבעון", "miesiąc", "kwartał", "maand", "kwartaal", "månad",
                "kvartal", "måned", "kuukausi", "mwezi", "robo", "شهر", "ربع"),
}


def mechanism_class(text: str) -> str:
    """The first orthogonality class whose vocabulary the sentence uses, else "other"."""
    low = (text or "").lower()
    for cls in MECHANISM_CLASSES:
        if _alias_rx(_CLASS_TERMS[cls]).search(low):
            return cls
    return "other"


def _bucket(terms: dict[str, tuple[str, ...]], words: list[str]) -> str:
    for w in words:
        wl = w.lower()
        for name, vocab in terms.items():
            if wl in vocab:
                return name
    return "other"


def mechanism_key(inst: dict[str, Any], cls: str, direction: list[str], horizon: list[str]) -> str:
    """The stable identity of a MECHANISM, independent of who told it and in which language:
    instrument (analogues, else indirect targets, else transfer classes), mechanism class,
    direction bucket and horizon bucket. Ten tellings fold to one key."""
    target = (sorted(inst.get("analogues") or []) or sorted(inst.get("indirect") or [])
              or sorted(t.split("->",
                                1)[-1].split(" (")[0] for t in (inst.get("transfer_only") or [])))
    key = "|".join([",".join(target), cls, _bucket(_DIR_BUCKET_TERMS, direction),
                    _bucket(_HOR_BUCKET_TERMS, horizon)])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ============================================================================== stated numbers
# Sentence enders: ASCII plus the full-width ideographic stop, bang, question and semicolon
# (U+3002, U+FF01, U+FF1F, U+FF1B), the Devanagari danda (U+0964) and the Arabic question mark
# (U+061F), written as escapes so the linter does not read them as typos.
_SPLIT = re.compile("(?<=[.!?\u3002\uff01\uff1f\uff1b;\u0964\u061f])\\s*|\\n+")
_PERF: tuple[tuple[str, str], ...] = (
    ("return_pct",
     r"(?:收益率?|報酬率?|年化(?:收益|報酬)?|盈利|利回り|リターン|수익률|доходност[ьи]?|"
                   r"дохідн[іи]сть|lợi nhuận|ผลตอบแทน|imbal hasil|रिटर्न|rendite|rendement|"
                   r"rendimiento|rentabilidad|retorno|rentabilidade|getiri|תשואה|stopa zwrotu|"
                   r"rendement|avkastning|afkast|tuotto|mapato|عائد|return(?:s)?|"
                   r"annual(?:ised|ized)?|cagr)\D{0,12}?(-?\d+(?:\.\d+)?)\s*%"),
    ("drawdown_pct", r"(?:最大回撤|回撤|最大ドローダウン|ドローダウン|최대낙폭|낙폭|просадк[аи]|"
                     r"drawdown|rebaixamento|sụt giảm tối đa|डीडी)\D{0,12}?(-?\d+(?:\.\d+)?)\s*%"),
    ("sharpe", r"(?:夏普(?:比率)?|シャープ(?:レシオ)?|샤프(?:지수|비율)?|шарп[а]?|sharpe)"
               r"\D{0,12}?(-?\d+(?:\.\d+)?)"),
    ("win_rate_pct", r"(?:胜率|勝率|승률|винрейт|процент прибыльных|win ?rate|trefferquote|"
                     r"taux de réussite|tasa de acierto|taxa de acerto|tỷ lệ thắng|"
                     r"อัตราชนะ|win ratio)\D{0,12}?(\d+(?:\.\d+)?)\s*%"),
    ("profit_factor", r"(?:盈亏比|プロフィットファクター|손익비|профит-?фактор|profit factor|"
                      r"fator de lucro|factor de beneficio|(?<![a-z])pf)\D{0,12}?(\d+(?:\.\d+)?)"),
)
_PERF_RE: tuple[tuple[str, re.Pattern[str]], ...] = tuple((n, re.compile(r)) for n, r in _PERF)
#: A date the sentence itself states -- the EVENT time of the claim, when there is one.
_DATE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})日?"
                   r"|(\d{1,2})[./](\d{1,2})[./](20\d{2})")


def performance(text: str) -> dict[str, float]:
    """Stated performance numbers. A STORY'S NUMBERS ARE EVIDENCE ABOUT THE STORY, NOT ABOUT THE
    MECHANISM -- they are kept so the reader can weigh the claim, never used as a prior."""
    out: dict[str, float] = {}
    low = (text or "").lower()
    for name, rx in _PERF_RE:
        m = rx.search(low)
        if m:
            try:
                out[name] = float(m.group(1))
            except ValueError:
                continue
    return out


def stated_date(text: str) -> str | None:
    """YYYY-MM-DD when the sentence names a date, else None. Never guessed."""
    m = _DATE.search(text or "")
    if not m:
        return None
    y, mo, d = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(6), m.group(5),
                                                                      m.group(4))
    try:
        if not (1 <= int(mo) <= 12 and 1 <= int(d) <= 31):
            return None
    except ValueError:
        return None
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


# ============================================================================== extraction
_STEM_RE: dict[tuple[str, ...], re.Pattern[str]] = {}


_EN_RE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _hits_en(words: tuple[str, ...], low: str) -> list[str]:
    """English words, whole-word only (`fix` is not `fixture`, `follow` is not `following`)."""
    rx = _EN_RE.get(words)
    if rx is None:
        alts = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
        rx = _EN_RE[words] = re.compile(r"(?<![a-z])(?:" + alts + r")(?![a-z])")
    out: list[str] = []
    for m in rx.finditer(low):
        if m.group(0) not in out:
            out.append(m.group(0))
    return out


def _hits_zh(words: tuple[str, ...], low: str) -> list[str]:
    return [w for w in words if w in low]


def _hits_stem(words: tuple[str, ...], low: str) -> list[str]:
    """Words that START at a word boundary and may continue -- one compiled alternation per
    vocabulary, longest first, so `steig` finds `steigt` and `steigen` in one pass."""
    key = words
    rx = _STEM_RE.get(key)
    if rx is None:
        alts = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
        rx = _STEM_RE[key] = re.compile(r"(?<!\w)(?:" + alts + ")")
        if len(_STEM_RE) > 256:
            _STEM_RE.clear()
            _STEM_RE[key] = rx
    out: list[str] = []
    for m in rx.finditer(low):
        w = m.group(0)
        if w not in out:
            out.append(w)
    return out


def _hits(lang: str, words: tuple[str, ...], low: str) -> list[str]:
    return _hits_zh(words, low) if lang in _SUBSTRING_LANGS else _hits_stem(words, low)


def _dedupe(words: list[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        if w not in out:
            out.append(w)
    return out


def extract_claims(text: str, *, max_claims: int = 40,
                   universe: set[str] | None = None) -> list[dict[str, Any]]:
    """Sentences naming a quantity, a direction and a horizon -- verbatim, never paraphrased.

    Returns the claims and nothing else; the drops are available through `extract` for a
    report that must show the fences working.
    """
    claims: list[dict[str, Any]] = extract(text, max_claims=max_claims,
                                           universe=universe)["claims"]
    return claims


def extract_claims_with_drops(text: str, *, max_claims: int = 40,
                              universe: set[str] | None = None
                              ) -> tuple[list[dict[str, Any]], int]:
    """(claims, crypto-venue drops) -- the older two-value shape, kept for its callers."""
    r = extract(text, max_claims=max_claims, universe=universe)
    return r["claims"], int(r["dropped_venue"])


def extract(text: str, *, max_claims: int = 40,
            universe: set[str] | None = None) -> dict[str, Any]:
    """Claims plus the counted fences: `dropped_venue` (crypto exchange named),
    `dropped_unmappable` (no MT5 analogue, no indirect target, no transfer note -- a summary
    nobody can test), and `duplicate_mechanisms` (a second sentence with the same key)."""
    out: list[dict[str, Any]] = []
    dropped_venue = dropped_unmappable = duplicates = 0
    seen: set[str] = set()
    keys: set[str] = set()
    # THE DOCUMENT NAMES THE INSTRUMENT ONCE. "I have traded Shanghai gold for seven years" is
    # sentence one; the mechanism is sentence three and says "it". A claim that names no
    # instrument inherits the document's, marked as context so the reader knows it was inherited.
    doc_inst = resolve_instruments((text or "").lower(), universe)
    for raw in _SPLIT.split(text or ""):
        s = re.sub(r"\s+", " ", raw).strip()
        if not s:
            continue
        lang = language_of(s)
        dense = lang in _SUBSTRING_LANGS
        lo, hi = (10, 400) if dense else (20, 400)
        if not (lo <= len(s) <= hi):
            continue
        low = s.lower()
        if forbidden_venue(low):
            dropped_venue += 1
            continue
        qv, dv, hv = _VOCAB.get(lang, (QUANTITY_EN, DIRECTION_EN, HORIZON_EN))
        # The ground's own vocabulary first, then English whole-word (RSI, breakout, COT ...
        # travel into every language); English itself is never stem-matched.
        q = _dedupe(_hits(lang, qv, low) + _hits_en(QUANTITY_EN, low)) if lang != "en" \
            else _hits_en(QUANTITY_EN, low)
        d = _dedupe(_hits(lang, dv, low) + _hits_en(DIRECTION_EN, low)) if lang != "en" \
            else _hits_en(DIRECTION_EN, low)
        h = _dedupe(_hits(lang, hv, low) + _hits_en(HORIZON_EN, low)) if lang != "en" \
            else _hits_en(HORIZON_EN, low)
        if not (q and d and h):
            continue
        digest = hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
        if digest in seen:
            continue
        seen.add(digest)
        inst = resolve_instruments(low, universe)
        inherited = False
        if not (inst["analogues"] or inst["transfer_only"] or inst["indirect"]) and (
                doc_inst["analogues"] or doc_inst["transfer_only"] or doc_inst["indirect"]):
            inst = {**doc_inst, "from_context": True}
            inherited = True
        if not (inst["analogues"] or inst["transfer_only"] or inst["indirect"]):
            dropped_unmappable += 1                     # a summary nobody can test
            continue
        channel = "direct" if inst["analogues"] else "indirect"
        cls = mechanism_class(low)
        key = mechanism_key(inst, cls, d[:2], h[:2])
        if key in keys:
            duplicates += 1
            continue
        keys.add(key)
        out.append({"claim": s, "lang": lang, "quantities": q[:4],
                    "direction": d[:2], "horizon": h[:2], "instruments": inst,
                    "instrument_from_context": inherited, "channel": channel,
                    "mechanism_class": cls, "mechanism_key": key,
                    "event_time": stated_date(s),
                    "claimed_performance": performance(s), "claim_hash": digest})
        if len(out) >= max_claims:
            break
    return {"claims": out, "dropped_venue": dropped_venue,
            "dropped_unmappable": dropped_unmappable, "duplicate_mechanisms": duplicates}


def claim_score(c: dict[str, Any]) -> float:
    """How much a claim is worth reading FIRST. Resolved instrument and a stated horizon beat a
    vague story; stated numbers add a little, because they at least make the story checkable;
    a structural class (policy, flow, inventory ...) edges out the four-hundredth momentum
    variant, which is the orthogonality target stated as a tie-break."""
    s = 1.0
    if c.get("instruments", {}).get("analogues"):
        s += 1.0
    if c.get("instruments", {}).get("transfer_only") or c.get("instruments", {}).get("indirect"):
        s += 0.25
    if len(c.get("quantities") or []) >= 2:
        s += 0.5
    if c.get("claimed_performance"):
        s += 0.25
    if c.get("mechanism_class") not in ("momentum", "other", None):
        s += 0.1
    return s
