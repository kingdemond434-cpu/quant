"""The claim reader's next thirteen languages: detected, read, mapped -- and nothing else moved."""
# ruff: noqa: RUF001
from __future__ import annotations

import pytest

from libs.research import mechanism_claims as mc
from libs.research import mechanism_claims_world as mcw

#: One London-session gold claim per language: a quantity, a direction and a horizon.
SENTENCES = {
    "fa": "قیمت طلا بعد از باز شدن سشن لندن معمولا صعود می‌کند و روند روزانه ادامه دارد.",
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
