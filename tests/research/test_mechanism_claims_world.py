"""The claim reader's next thirteen languages: detected, read, mapped -- and nothing else moved."""
# ruff: noqa: RUF001
from __future__ import annotations

import pytest

from libs.research import mechanism_claims as mc
from libs.research import mechanism_claims_world as mcw

#: One London-session gold claim per language: a quantity, a direction and a horizon.
SENTENCES = {
    "fa": "قیمت طلا بعد از باز شدن سشن لندن معمولا صعود می\u200cکند و روند روزانه ادامه دارد.",
    "ur": "سونا لندن سیشن کھلنے کے بعد اکثر اوپر جاتا ہے اور روزانہ رجحان جاری رہتا ہے۔",
    "bn": "লন্ডন সেশনের পরে সোনা সাধারণত ঊর্ধ্বমুখী থাকে এবং দৈনিক ট্রেন্ড অব্যাহত থাকে।",
    "ta": "லண்டன் அமர்வுக்கு பிறகு தங்கம் உயர்வு காணும், தினசரி போக்கு தொடர் கிறது.",
    "te": "లండన్ సెషన్ తర్వాత బంగారం ధర పెరుగుతుంది, రోజువారీ ట్రెండ్ కొనసాగుతుంది.",
    "mr": "लंडन सत्रानंतर सोन्याचा भाव वाढतो आणि दैनिक ट्रेंड सुरू राहतो असे दिसते आहे.",
    "gu": "લંડન સત્ર પછી સોનું સામાન્ય રીતે વધે છે અને દૈનિક ટ્રેન્ડ ચાલુ રહે છે.",
    "tl": "Ang presyo ng ginto ay tumaas pagkatapos ng sesyon sa London at tuloy ang trend "
          "araw-araw.",
    "ro": "Aurul crește de obicei după deschiderea sesiunii Londra și trendul zilnic continuă.",
    "cs": "Zlato obvykle roste po otevření londýnské seance a denní trend pokračuje.",
    "hu": "Az arany általában emelkedik a londoni nyitás után, és a napi trend folytatódik.",
    "el": "Ο χρυσός συνήθως ανεβαίνει μετά το άνοιγμα της συνεδρίασης του Λονδίνου και η "
          "ημερήσια τάση συνεχίζεται.",
}


@pytest.mark.parametrize("lang", sorted(SENTENCES))
def test_each_new_language_is_detected_and_yields_a_gold_claim(lang: str) -> None:
    text = SENTENCES[lang]
    assert mc.language_of(text) == lang
    claims = mc.extract(text)["claims"]
    assert len(claims) == 1, lang
    assert claims[0]["lang"] == lang and claims[0]["instruments"]["analogues"] == ["XAUUSD"]


def test_malay_reads_through_indonesian_widened_by_malay_words() -> None:
    text = "Harga emas biasanya naik selepas pembukaan sesi London dan aliran harian berterusan."
    assert mc.language_of(text) == "id"
    assert mc.extract(text)["claims"][0]["instruments"]["analogues"] == ["XAUUSD"]
    assert "minit" in mc._VOCAB["id"][2] and mc._VOCAB["ms"] == mcw.WORLD_VOCAB["ms"]


def test_existing_detection_is_unchanged() -> None:
    assert mc.language_of("Giá vàng thường tăng sau khi phiên London mở cửa.") == "vi"
    assert mc.language_of("लंदन सेशन के बाद सोना अक्सर तेजी में रहता है और ट्रेंड जारी है।") == "hi"
    assert mc.language_of("يرتفع الذهب عادة بعد افتتاح جلسة لندن ويستمر الاتجاه.") == "ar"
    assert mc.language_of("plain english sentence about gold") == "en"


def test_persian_aliases_do_not_fire_inside_arabic_words() -> None:
    assert mc.resolve_instruments("انطلاق السوق اليوم")["analogues"] == []
    assert mc.resolve_instruments("سياسة الانفتاح الاقتصادي")["analogues"] == []
    assert "XAUUSD" in mc.resolve_instruments("قیمت طلا امروز")["analogues"]


def test_every_new_language_meets_the_vocabulary_floor_and_has_a_search_locale() -> None:
    import sys
    from pathlib import Path
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
    sys.path.insert(0, str(desk))
    import deep_forest_miner as dfm
    for lang, (q, d, h) in mcw.WORLD_VOCAB.items():
        assert lang in mc.LANGUAGES
        assert len(q) >= 25 and len(d) >= 15 and len(h) >= 14, lang
        assert lang == "ms" or lang in dfm._LOCALE, lang


#: Sentences in the languages that were already supported, with the language and claim count
#: the base reader gives them (measured on f7cd3826): the additions must move none of them.
BASE_CORPUS = [
    ("Este año el oro sube después de la apertura de Londres y la tendencia continúa.", "es", 1),
    ("O ouro costuma subir após a abertura de Londres e a tendência continua no dia.", "pt", 1),
    ("L'oro di solito sale dopo l'apertura di Londra e il trend continua nella seduta.", "it", 1),
    ("L'or monte souvent après l'ouverture de Londres et la tendance continue dans la séance.",
     "fr", 1),
    ("Altın genellikle Londra açılışından sonra yükselir ve günlük trend devam eder.", "tr", 1),
    ("Złoto zwykle rośnie po otwarciu Londynu i trend dzienny jest kontynuowany.", "pl", 1),
    ("Gold steigt meist nach der Londoner Eröffnung und der Trend setzt sich fort.", "de", 1),
    ("Goud stijgt vaak na de opening van Londen en de trend zet door.", "nl", 1),
    ("Guld brukar stiga efter öppningen i London och trenden fortsätter.", "sv", 1),
    ("Para la sesión de Londres, el oro sube cuando el dólar cae, este patrón dura un día.",
     "es", 1),
    # one Greek symbol never makes a sentence Greek (audit MF1)
    ("Gold momentum: buy when the 20-day return exceeds 2σ, hold one week.", "en", 1),
    ("When ΔDXY > 0 sell EURUSD into the London close.", "en", 1),
    ("Покупаем золото на пробое, когда доходность выше 2σ, держим неделю.", "ru", 1),
    ("黄金在伦敦开盘后上涨，当波动率超过2σ时做多，持有一周。", "zh", 1),
]


@pytest.mark.parametrize(("text", "lang", "n"), BASE_CORPUS)
def test_supported_languages_keep_their_base_reading(text: str, lang: str, n: int) -> None:
    assert mc.language_of(text) == lang
    assert len(mc.extract(text)["claims"]) == n


def test_false_instrument_words_stay_negative() -> None:
    # Hinglish / romanized Urdu "aur" is "and", never Romanian gold (audit MF2)
    assert mc.extract("Bhai market me breakout aaya aur price upar gaya, buy karo 1 day ke "
                      "liye")["claims"] == []
    assert mc.resolve_instruments("قیمت استیل امروز بالا رفت")["analogues"] == []  # steel
    assert mc.resolve_instruments("তেলেঙ্গানা বাজারে আজ দাম বেড়েছে")["analogues"] == []
    # a script-bounded alias still matches at the start of text and after punctuation
    assert mc.resolve_instruments("طلا امروز")["analogues"] == ["XAUUSD"]
    assert mc.resolve_instruments("«طلا» امروز")["analogues"] == ["XAUUSD"]


@pytest.mark.parametrize("text", [
    "ارتفع عدد طلاب الجامعة هذا العام",        # students
    "نفتح صفقة شراء على اليورو بعد الافتتاح",   # we open a buy trade on the euro
    "نفتقد السيولة في جلسة آسيا",              # we miss liquidity
    "نرخ طلاق در شهر بالا رفت",                # divorce (Persian)
])
def test_script_bounded_aliases_are_whole_words_never_prefixes(text: str) -> None:
    inst = mc.resolve_instruments(text)
    assert "XAUUSD" not in inst["analogues"] and "XTIUSD" not in inst["analogues"], text


def test_inflected_forms_are_listed_and_match() -> None:
    assert mc.resolve_instruments("قیمت طلای جهانی امروز بالا رفت")["analogues"] == ["XAUUSD"]
    assert mc.resolve_instruments("سونے کی قیمت آج بڑھ گئی")["analogues"] == ["XAUUSD"]
    assert mc.resolve_instruments("আজ সোনার দাম বেড়েছে")["analogues"] == ["XAUUSD"]
