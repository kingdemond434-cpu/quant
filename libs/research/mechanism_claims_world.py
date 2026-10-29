"""The claim reader's next thirteen languages, as data `mechanism_claims` merges at import.

THE WORLD STRATEGY HUNTER NAMED THEM (reports/WORLD_STRATEGY_HUNT.json, 2026-10-29): 33 map
languages had no vocabulary, so every forum, channel and blog written in them was an
EXTRACTOR_GAP -- reachable, and read as empty. These thirteen are the heaviest by the map's
country priors: Persian, Urdu, Bengali, Tamil, Telugu, Marathi, Gujarati, Malay, Tagalog,
Romanian, Czech, Hungarian and Greek. Same grammar as every other language (a QUANTITY, a
DIRECTION and a HORIZON in one sentence), the same seeds-never-boundaries rule, and the same
instrument fence: a claim still needs an MT5 analogue, so the gold, silver and oil words of each
language are added to the existing alias rows rather than as new instruments.

Kept in a module of its own so the core lexicon is not rewritten to add a row; `mechanism_claims`
merges these tables once, before anything is compiled. Malay shares Indonesian's function words,
so a Malay sentence is detected as `id` and read with Indonesian vocabulary widened by Malay's.
Persian's ک and ی are also typed by Arabic writers on Persian keyboards; such Arabic text reads as
`fa`, which costs nothing but its label: both vocabularies are searched against English as well.
"""
from __future__ import annotations

#: lang -> (quantity, direction, horizon)
WORLD_VOCAB: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "fa": (
        ("مومنتوم", "روند", "برگشت", "بازگشت به میانگین", "شکست", "حمایت", "مقاومت", "نوسان",
         "نقدینگی", "اسپرد", "حجم", "سشن", "باز شدن", "بسته شدن", "گپ", "همبستگی", "نرخ بهره",
         "تورم", "سوآپ", "میانگین متحرک", "کندل", "پرایس اکشن", "واگرایی", "فیبوناچی", "دلار",
         "یورو", "طلا", "نقره", "نفت", "انس", "شاخص", "فارکس", "اندیکاتور", "پولبک"),
        ("خرید", "فروش", "لانگ", "شورت", "صعود", "نزول", "افزایش", "کاهش", "رشد", "سقوط",
         "برگشت", "ادامه", "صعودی", "نزولی", "ورود", "خروج", "بالا", "پایین", "تقویت", "تضعیف"),
        ("دقیقه", "ساعت", "روزانه", "روز", "هفته", "هفتگی", "ماه", "ماهانه", "اسکالپ",
         "سوئینگ", "کوتاه مدت", "بلند مدت", "تایم فریم", "شبانه", "سشن لندن", "سشن آسیا")),
    "ur": (
        ("مومینٹم", "رجحان", "ٹرینڈ", "بریک آؤٹ", "رینج", "سپورٹ", "ریزسٹنس", "اتار چڑھاؤ",
         "والیوم", "لیکویڈیٹی", "سپریڈ", "سیشن", "گیپ", "شرح سود", "افراط زر", "موونگ ایوریج",
         "کینڈل", "پرائس ایکشن", "ڈالر", "سونا", "چاندی", "تیل", "فاریکس", "انڈیکیٹر",
         "پل بیک", "اسٹاپ لاس"),
        ("خرید", "فروخت", "لانگ", "شارٹ", "اضافہ", "کمی", "بڑھ", "گر", "اوپر", "نیچے", "تیزی",
         "مندی", "انٹری", "ایگزٹ", "جاری", "پلٹ", "مضبوط", "کمزور"),
        ("منٹ", "گھنٹہ", "گھنٹے", "دن", "ہفتہ", "ہفتے", "مہینہ", "روزانہ", "اسکیلپنگ", "سوئنگ",
         "مختصر مدت", "طویل مدت", "ٹائم فریم", "سیشن")),
    "bn": (
        ("মোমেন্টাম", "ট্রেন্ড", "প্রবণতা", "ব্রেকআউট", "রেঞ্জ", "সাপোর্ট", "রেজিস্ট্যান্স",
         "অস্থিরতা", "ভলিউম", "স্প্রেড", "সেশন", "গ্যাপ", "সুদের হার", "মুদ্রাস্ফীতি",
         "মুভিং এভারেজ", "ক্যান্ডেল", "প্রাইস অ্যাকশন", "ডলার", "সোনা", "স্বর্ণ", "রূপা", "তেল",
         "ফরেক্স", "ইন্ডিকেটর", "পুলব্যাক", "স্টপ লস"),
        ("কেনা", "কিনুন", "বিক্রি", "লং", "শর্ট", "বৃদ্ধি", "বাড়", "কম", "পতন", "উত্থান",
         "ঊর্ধ্বমুখী", "নিম্নমুখী", "এন্ট্রি", "এক্সিট", "অব্যাহত", "শক্তিশালী", "দুর্বল"),
        ("মিনিট", "ঘণ্টা", "দিন", "দৈনিক", "সপ্তাহ", "সাপ্তাহিক", "মাস", "মাসিক", "স্ক্যাল্পিং",
         "সুইং", "স্বল্পমেয়াদী", "দীর্ঘমেয়াদী", "টাইমফ্রেম", "ইন্ট্রাডে")),
    "ta": (
        ("மொமென்டம்", "போக்கு", "டிரெண்ட்", "பிரேக்அவுட்", "ரேஞ்ச்", "சப்போர்ட்", "ரெசிஸ்டன்ஸ்",
         "ஏற்ற இறக்கம்", "வால்யூம்", "ஸ்ப்ரெட்", "வட்டி விகிதம்", "பணவீக்கம்", "மூவிங் ஆவரேஜ்",
         "கேண்டில்", "டாலர்", "தங்கம்", "வெள்ளி", "கச்சா எண்ணெய்", "ஃபாரெக்ஸ்", "இண்டிகேட்டர்",
         "ஸ்டாப் லாஸ்", "நிஃப்டி", "சந்தை", "விலை", "ஆதரவு"),
        ("வாங்க", "விற்க", "வாங்கு", "விற்", "லாங்", "ஷார்ட்", "உயர்வு", "சரிவு", "ஏற்றம்",
         "இறக்கம்", "அதிகரி", "குறை", "நுழைவு", "வெளியேறு", "தொடர்"),
        ("நிமிடம்", "நிமிட", "மணி நேர", "மணிநேர", "நாள்", "தினசரி", "வாரம்", "வாராந்திர",
         "மாதம்", "மாதாந்திர", "இன்ட்ராடே", "ஸ்கால்ப்பிங்", "ஸ்விங்", "குறுகிய கால",
         "நீண்ட கால")),
    "te": (
        ("మొమెంటం", "ట్రెండ్", "ధోరణి", "బ్రేక్అవుట్", "రేంజ్", "సపోర్ట్", "రెసిస్టెన్స్",
         "ఒడిదుడుకులు", "వాల్యూమ్", "స్ప్రెడ్", "వడ్డీ రేటు", "ద్రవ్యోల్బణం", "మూవింగ్ యావరేజ్",
         "క్యాండిల్", "డాలర్", "బంగారం", "వెండి", "ముడి చమురు", "ఫారెక్స్", "ఇండికేటర్",
         "స్టాప్ లాస్", "నిఫ్టీ", "మార్కెట్", "ధర", "సూచీ"),
        ("కొనుగోలు", "అమ్మకం", "కొను", "అమ్ము", "లాంగ్", "షార్ట్", "పెరుగు", "తగ్గు", "పతనం",
         "ర్యాలీ", "ఎంట్రీ", "ఎగ్జిట్", "కొనసాగు", "బలపడ", "బలహీన"),
        ("నిమిషం", "నిమిషాల", "గంట", "రోజు", "రోజువారీ", "వారం", "వారపు", "నెల", "నెలవారీ",
         "ఇంట్రాడే", "స్కాల్పింగ్", "స్వింగ్", "స్వల్పకాలిక", "దీర్ఘకాలిక")),
    "mr": (
        ("मोमेंटम", "ट्रेंड", "कल", "ब्रेकआउट", "रेंज", "सपोर्ट", "रेझिस्टन्स", "अस्थिरता",
         "व्हॉल्यूम", "स्प्रेड", "व्याजदर", "महागाई", "मूव्हिंग एव्हरेज", "कँडल", "डॉलर", "सोने",
         "सोनं", "चांदी", "कच्चे तेल", "फॉरेक्स", "इंडिकेटर", "स्टॉप लॉस", "निफ्टी", "बाजार",
         "किंमत"),
        ("खरेदी", "विक्री", "विक", "लॉंग", "शॉर्ट", "वाढ", "घसरण", "घसर", "तेजी", "मंदी",
         "एंट्री", "एक्झिट", "सुरू राह", "मजबूत", "कमकुवत"),
        ("मिनिट", "तास", "दिवस", "दैनिक", "आठवडा", "साप्ताहिक", "महिना", "मासिक", "इंट्राडे",
         "स्कॅल्पिंग", "स्विंग", "अल्पकालीन", "दीर्घकालीन", "सत्र")),
    "gu": (
        ("મોમેન્ટમ", "ટ્રેન્ડ", "વલણ", "બ્રેકઆઉટ", "રેન્જ", "સપોર્ટ", "રેઝિસ્ટન્સ", "અસ્થિરતા",
         "વોલ્યુમ", "સ્પ્રેડ", "વ્યાજ દર", "મોંઘવારી", "મૂવિંગ એવરેજ", "કેન્ડલ", "ડોલર", "સોનું",
         "સોના", "ચાંદી", "ક્રૂડ", "ફોરેક્સ", "ઇન્ડિકેટર", "સ્ટોપ લોસ", "નિફ્ટી", "બજાર", "ભાવ"),
        ("ખરીદ", "વેચ", "લોંગ", "શોર્ટ", "વધ", "ઘટ", "તેજી", "મંદી", "ઉછાળો", "કડાકો",
         "એન્ટ્રી", "એક્ઝિટ", "ચાલુ", "મજબૂત", "નબળ"),
        ("મિનિટ", "કલાક", "દિવસ", "દૈનિક", "અઠવાડિયું", "સાપ્તાહિક", "મહિનો", "માસિક",
         "ઇન્ટ્રાડે", "સ્કેલ્પિંગ", "સ્વિંગ", "ટૂંકા ગાળા", "લાંબા ગાળા", "સત્ર")),
    "ms": (
        ("momentum", "aliran", "pergerakan", "penembusan", "julat", "sokongan", "rintangan",
         "kemeruapan", "volum", "kecairan", "spread", "sesi", "pembukaan", "penutupan",
         "jurang", "korelasi", "kadar faedah", "inflasi", "purata bergerak", "lilin", "dolar",
         "emas", "perak", "minyak mentah", "forex", "penunjuk", "harga"),
        ("beli", "jual", "naik", "turun", "meningkat", "menurun", "melonjak", "jatuh", "lantun",
         "berterusan", "kukuh", "lemah", "masuk", "keluar", "bullish", "bearish"),
        ("minit", "jam", "hari", "harian", "minggu", "mingguan", "bulan", "bulanan", "intraday",
         "scalping", "swing", "jangka pendek", "jangka panjang", "sesi", "semalaman")),
    "tl": (
        ("momentum", "trend", "breakout", "suporta", "resistance", "galaw", "presyo",
         "volatility", "volume", "spread", "sesyon", "pagbubukas", "pagsasara", "interes",
         "implasyon", "moving average", "kandila", "dolyar", "ginto", "pilak", "langis",
         "forex", "indicator", "stop loss", "merkado"),
        ("bili", "bumili", "benta", "ibenta", "tumaas", "bumaba", "pagtaas", "pagbaba",
         "bumagsak", "lumakas", "humina", "pasok", "labas", "tuloy", "bumawi"),
        ("minuto", "oras", "araw", "araw-araw", "linggo", "lingguhan", "buwan", "buwanan",
         "intraday", "scalping", "swing", "panandalian", "pangmatagalan", "magdamag")),
    "ro": (
        ("impuls", "trend", "tendință", "tendinta", "spargere", "interval", "suport",
         "rezistență", "volatilitate", "volum", "lichiditate", "spread", "sesiune", "deschidere",
         "închidere", "gap", "corelație", "rata dobânzii", "dobândă", "inflație", "medie mobilă",
         "lumânare", "dolar", "euro", "aur", "argint", "petrol", "indicator", "pullback"),
        ("cumpăr", "vânz", "long", "short", "crește", "creștere", "scade", "scădere", "urcă",
         "coboară", "revine", "continuă", "se întărește", "slăbește", "intrare", "ieșire"),
        ("minut", "oră", "ore", "zi", "zilnic", "săptămân", "lună", "lunar", "intraday",
         "scalping", "swing", "termen scurt", "termen lung", "peste noapte")),
    "cs": (
        ("momentum", "trend", "průraz", "proražení", "rozsah", "podpora", "odpor", "volatilita",
         "objem", "likvidita", "spread", "seance", "otevření", "uzavření", "mezera", "korelace",
         "úroková sazba", "úrok", "inflace", "klouzavý průměr", "svíčk", "dolar", "euro",
         "zlato", "stříbro", "ropa", "indikátor", "cena"),
        ("nákup", "koupit", "kup", "prodej", "prodat", "prodá", "long", "short", "roste", "růst",
         "klesá", "pokles", "stoupá", "odraz", "pokračuje", "posiluje", "oslabuje"),
        ("minut", "hodin", "den", "denní", "dny", "týden", "týdenní", "měsíc", "měsíční",
         "intradenní", "intraday", "scalping", "swing", "krátkodob", "dlouhodob")),
    "hu": (
        ("momentum", "trend", "kitörés", "sáv", "támasz", "ellenállás", "volatilitás",
         "forgalom", "likviditás", "spread", "nyitás", "zárás", "rés", "korreláció", "kamat",
         "infláció", "mozgóátlag", "gyertya", "dollár", "euró", "arany", "ezüst", "olaj",
         "indikátor", "árfolyam"),
        ("vétel", "vesz", "vásárol", "eladás", "elad", "long", "short", "emelkedik",
         "emelkedés", "esik", "esés", "csökken", "nő", "növekedés", "visszapattan",
         "folytatódik", "erősödik", "gyengül"),
        ("perc", "óra", "nap", "napi", "hét", "heti", "hónap", "havi", "napon belüli",
         "intraday", "scalping", "swing", "rövid táv", "hosszú táv", "éjszaka")),
    "el": (
        ("ορμή", "τάση", "διάσπαση", "εύρος", "στήριξη", "αντίσταση", "μεταβλητότητα", "όγκος",
         "ρευστότητα", "spread", "συνεδρίαση", "άνοιγμα", "κλείσιμο", "χάσμα", "συσχέτιση",
         "επιτόκιο", "πληθωρισμός", "κινητός μέσος", "κερί", "δολάριο", "ευρώ", "χρυσ",
         "ασήμι", "πετρέλαιο", "δείκτη", "τιμή"),
        ("αγορά", "αγοράζ", "πώληση", "πουλ", "long", "short", "άνοδος", "ανεβαίν", "πτώση",
         "πέφτ", "αύξηση", "μείωση", "ανάκαμψη", "αντιστροφή", "συνεχίζ", "ενισχύ", "αποδυναμ"),
        ("λεπτ", "ώρα", "ώρες", "ημέρα", "ημερήσι", "εβδομάδα", "εβδομαδιαί", "μήνα", "μηνιαί",
         "ενδοσυνεδριακ", "intraday", "scalping", "swing", "βραχυπρόθεσμ", "μακροπρόθεσμ")),
}

#: Function words for the Latin-script additions, scored like `mechanism_claims._STOPWORDS`.
#: Shared short words ("na", "po", "de") are left out: they separate nothing.
WORLD_STOPWORDS: dict[str, tuple[str, ...]] = {
    "ro": ("și", "este", "în", "care", "pentru", "nu", "sunt", "mai", "după", "când", "dar",
           "sau", "acest", "această", "foarte", "prețul", "de obicei"),
    "cs": ("je", "se", "že", "jsou", "pro", "když", "ale", "nebo", "jako", "také", "obvykle",
           "často", "při", "který", "není", "být", "cena"),
    "hu": ("és", "az", "hogy", "nem", "egy", "van", "ez", "meg", "ha", "után", "általában",
           "gyakran", "csak", "mint", "vagy", "amikor"),
    "tl": ("ang", "ng", "mga", "ay", "ito", "kung", "para", "hindi", "pero", "lang", "naman",
           "kapag", "yung", "presyo"),
}
#: Letters only one of the additions writes; each counts as two function words.
WORLD_LETTER_HINTS: tuple[tuple[str, str], ...] = (
    ("ș", "ro"), ("ț", "ro"), ("ş", "ro"), ("ţ", "ro"), ("ř", "cs"), ("ě", "cs"), ("ů", "cs"),
    ("ő", "hu"), ("ű", "hu"),
)
#: Romanian's comma-below letters: a sentence carrying one is Latin, never Vietnamese, however
#: many breve-a it also has (ă is in the Vietnamese class).
ROMANIAN_ONLY = "șțşţȘȚŞŢ"
#: Marathi against Hindi, both Devanagari: the words and the letter (ळ) that tell them apart.
MARATHI_MARKERS: tuple[str, ...] = ("आहे", "आणि", "च्या", "मध्ये", "नाही", "होते", "ळ")
HINDI_MARKERS: tuple[str, ...] = ("है", "और", " के ", "में", "नहीं", " की ", "था")
#: Urdu and Persian against Arabic, all Arabic script: letters each writes and Arabic does not.
URDU_LETTERS = "ٹڈڑںےۓ"
PERSIAN_LETTERS = "پچژگکی"

#: First symbol of an INSTRUMENT_ALIASES row -> the words for it in the new languages. The
#: Arabic- and Indic-script ones are WHOLE WORDS of their script (SCRIPT_BOUNDED below), so each
#: inflected form is listed (Persian ezafe طلای, Urdu oblique سونے, Bengali genitive সোনার):
#: bare "طلا" is inside Arabic "انطلاق" (launch), "نفت" inside "انفتاح" (openness),
#: Urdu "تیل" inside "استیل" (steel).
#: Bengali oil is "তেলের"/crude, because bare "তেল" begins Telangana; Tamil silver is also Friday,
#: so only "silver price" counts; Marathi's oblique gold avoids Hindi "to sleep"; Romanian bare
#: "aur" is Hinglish and romanized Urdu "and", so only its inflected forms count.
WORLD_ALIASES: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("طلا", "طلای", "طلاها", "سونا", "سونے", "সোনা", "সোনার", "স্বর্ণ", "স্বর্ণের",
               "தங்கம்", "தங்கத்தின்", "தங்க", "బంగారం", "బంగారు", "सोन्याचा", "सोन्याचे",
               "सोन्याची", "सोनं", "સોનું", "સોના", "ginto", "aurul", "aurului", "aur fizic",
               "zlato", "zlata", "arany", "aranyat", "χρυσ"),
    "XAGUSD": ("نقره", "نقره\u200cای", "چاندی", "রূপা", "রূপার", "வெள்ளி விலை", "వెండి", "ચાંદી",  # noqa: RUF001
               "pilak", "argint", "stříbro", "ezüst", "ασήμι"),
    "XTIUSD": ("نفت", "نفتی", "تیل", "তেলের", "অপরিশোধিত তেল", "கச்சா எண்ணெய்", "ముడి చమురు",
               "कच्चे तेल", "ક્રૂડ", "langis", "țiței", "olaj", "πετρέλαιο"),
}
#: Arabic, Bengali, Tamil, Telugu, Gujarati and Devanagari, as regex character ranges.
_SCRIPTS = ("\u0600-\u06ff", "\u0980-\u09ff", "\u0b80-\u0bff", "\u0c00-\u0c7f", "\u0a80-\u0aff",
            "\u0900-\u097f")
#: alias -> its script block: no letter of that script may precede or follow it (so "طلاب",
#: students, and "نفتح", we open, never read as gold and oil).
SCRIPT_BOUNDED: dict[str, str] = {
    a: block for terms in WORLD_ALIASES.values() for a in terms
    for block in _SCRIPTS if block[0] <= a[0] <= block[-1]}

#: Direction buckets the mechanism key reads, so a Persian "buy" and an English "buy" key alike.
WORLD_DIR_BUCKETS: dict[str, tuple[str, ...]] = {
    "long": ("خرید", "صعود", "لانگ", "কেনা", "বৃদ্ধি", "வாங்க", "உயர்வு", "కొనుగోలు",
             "పెరుగు", "खरेदी", "वाढ", "ખરીદ", "વધ", "bumili", "tumaas", "cumpăr", "crește",
             "nákup", "roste", "vétel", "emelkedik", "αγοράζ", "άνοδος"),
    "short": ("فروش", "نزول", "شورت", "فروخت", "বিক্রি", "পতন", "விற்க", "சரிவு", "అమ్మకం",
              "తగ్గు", "विक्री", "घसरण", "વેચ", "ઘટ", "ibenta", "bumaba", "vânz", "scade",
              "prodej", "klesá", "eladás", "esik", "πώληση", "πτώση"),
}
