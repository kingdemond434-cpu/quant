"""The claim reader's last twelve gap languages, as data `mechanism_claims_world` merges.

THE WORLD STRATEGY HUNTER'S extractor_gaps after the thirteen (`mechanism_claims_world`) and the
eight one-script languages (`mechanism_claims_world_b`): four Cyrillic (Bulgarian, Serbian,
Kazakh, Mongolian) and eight Latin (Afrikaans, Azerbaijani, Uzbek, Estonian, Lithuanian,
Latvian, Croatian, Slovak). None is settled by script alone, so each is told from the languages
already read by its own letters (Kazakh ә ғ қ ң ұ һ, Mongolian ө ү, Serbian ђ ј љ њ ћ џ,
Azerbaijani ə, Lithuanian ė į ų, Latvian ģ ķ ļ ņ, Slovak ľ ĺ ŕ ô, Croatian đ, Afrikaans ŉ) and
by function words; Bulgarian, which has no letter of its own, by its particles and the absence
of Russian ы and э.

Same grammar, seeds-never-boundaries rule and instrument fence. Cyrillic words are stems, as in
Russian. Latin instrument words are word-bounded; bare "nafta" is left out (Spanish petrol at
the pump, Czech diesel), so only the inflected and "crude" forms name oil. Slovak "ropa" needs
nothing: Polish and Czech already carry it.
"""
# ruff: noqa: RUF001, RUF002, RUF003 -- a lexicon in two scripts and twelve languages is made of the
# letters that look like other letters
from __future__ import annotations

#: lang -> (quantity, direction, horizon)
VOCAB: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "bg": (
        ("моментум", "тренд", "тенденци", "пробив", "подкреп", "съпротив", "волатилност",
         "обем", "ликвидност", "спред", "сесия", "отваряне", "затваряне", "гап", "лихв",
         "инфлаци", "долар", "евро", "злато", "сребро", "петрол", "форекс", "индикатор",
         "свещ", "пълзяща средна", "корелаци"),
        ("купува", "купи", "продава", "продай", "лонг", "шорт", "покачва", "поскъпва",
         "поевтинява", "спада", "пада", "расте", "нагоре", "надолу", "продължава", "обръща"),
        ("минут", "час", "ден", "дневн", "седмиц", "седмичн", "месец", "месечн", "краткосроч",
         "дългосроч", "таймфрейм", "скалпинг", "нощ", "сутрин")),
    "sr": (
        ("моментум", "тренд", "тенденциј", "пробој", "подршк", "отпор", "волатилност", "обим",
         "ликвидност", "спред", "сесиј", "отварањ", "затварањ", "гап", "камат", "инфлациј",
         "долар", "евро", "злато", "сребро", "нафт", "форекс", "индикатор", "свећ",
         "покретни просек", "корелациј"),
        ("купити", "купуј", "куповин", "продај", "продаја", "лонг", "шорт", "раст", "расте",
         "пад", "пада", "порасти", "опада", "горе", "доле", "настав"),
        ("минут", "сат", "дан", "дневн", "недељ", "недељн", "месец", "месечн", "краткороч",
         "дугороч", "тајмфрејм", "скалпинг", "ноћ", "јутр")),
    "kk": (
        ("моментум", "тренд", "үрдіс", "серпіліс", "қолдау", "қарсылық", "құбылмалылық", "көлем",
         "өтімділік", "спред", "сессия", "ашылу", "жабылу", "гэп", "пайыздық мөлшерлеме",
         "инфляция", "доллар", "еуро", "алтын", "күміс", "мұнай", "форекс", "индикатор", "шам",
         "жылжымалы орташа", "корреляция"),
        ("сатып ал", "сату", "сатамыз", "лонг", "шорт", "өсу", "өседі", "төмендеу",
         "төмендейді", "құлау", "көтеріл", "түсе", "жоғары", "төмен", "жалғас", "бұрыл"),
        ("минут", "сағат", "күн", "күнделікті", "апта", "апталық", "бір ай", "айлық", "тәулік",
         "қысқа мерзімді", "ұзақ мерзімді", "таймфрейм", "скальпинг", "түн")),
    "mn": (
        ("моментум", "тренд", "чиг хандлага", "эвдрэл", "дэмжлэг", "эсэргүүцэл", "хэлбэлзэл",
         "хэмжээ", "хөрвөх чадвар", "спред", "сесс", "нээлт", "хаалт", "зөрүү",
         "хүүгийн түвшин", "инфляц", "доллар", "евро", "алт", "мөнгө", "газрын тос", "форекс",
         "индикатор", "лаа", "хөдөлгөөнт дундаж", "корреляц"),
        ("худалдаж ав", "авах", "зарах", "зарна", "лонг", "шорт", "өсөх", "өснө", "буурах",
         "буурна", "унах", "өгсөх", "дээш", "доош", "үргэлжл", "эргэх"),
        ("минут", "цаг", "өдөр", "өдөр тутм", "долоо хоног", "сар", "сарын", "богино хугацаа",
         "урт хугацаа", "таймфрейм", "скальпинг", "шөнө", "өглөө", "орой")),
    "az": (
        ("momentum", "trend", "meyl", "qırılma", "dəstək", "müqavimət", "volatillik", "həcm",
         "likvidlik", "spred", "sessiya", "açılış", "bağlanış", "boşluq", "faiz dərəcəsi",
         "inflyasiya", "dollar", "avro", "qızıl", "gümüş", "neft", "forex", "indikator", "şam",
         "hərəkətli orta", "korrelyasiya"),
        ("alın", "alış", "almaq", "satış", "satmaq", "satmalı", "long", "short", "artır",
         "yüksəl", "enir", "düşür", "düşüş", "bahalaş", "ucuzlaş", "davam"),
        ("dəqiqə", "saat", "gün", "gündəlik", "həftə", "həftəlik", "bir ay", "aylıq", "seans",
         "qısamüddətli", "uzunmüddətli", "taymfreym", "skalpinq", "gecə")),
    "uz": (
        ("momentum", "trend", "tendensiya", "yorib o'tish", "qo'llab-quvvatlash", "qarshilik",
         "volatillik", "hajm", "likvidlik", "spred", "sessiya", "ochilish", "yopilish",
         "bo'shliq", "foiz stavkasi", "inflyatsiya", "dollar", "yevro", "oltin", "kumush",
         "neft", "forex", "indikator", "sham", "harakatlanuvchi o'rtacha", "korrelyatsiya"),
        ("sotib ol", "sotib olish", "sotish", "soting", "long", "short", "o'sadi", "o'sish",
         "ko'tariladi", "tushadi", "tushish", "pasayadi", "pasayish", "qimmatlashadi",
         "arzonlashadi", "davom"),
        ("daqiqa", "soat", "kun", "kunlik", "hafta", "haftalik", "bir oy", "oylik",
         "qisqa muddatli", "uzoq muddatli", "taymfreym", "skalping", "kecha", "ertalab")),
    "et": (
        ("momentum", "trend", "suundumus", "läbimurre", "tugi", "vastupanu", "volatiilsus",
         "maht", "likviidsus", "spread", "sessioon", "avamine", "sulgemine", "lõhe",
         "intressimäär", "inflatsioon", "dollar", "euro", "kuld", "hõbe", "toornafta", "forex",
         "indikaator", "küünal", "libisev keskmine", "korrelatsioon"),
        ("ost", "osta", "müü", "müük", "pikk positsioon", "lühike positsioon", "tõuse", "tõus",
         "lange", "langus", "kasva", "kahane", "üles", "alla", "jätka", "pöörd"),
        ("minut", "tund", "päev", "päevane", "igapäevane", "nädal", "nädala", "kuu", "kuine",
         "lühiajali", "pikaajali", "ajaraam", "skalpeeri", "öö")),
    "lt": (
        ("momentas", "tendencij", "trendas", "proveržis", "palaikym", "pasipriešinim",
         "kintamum", "apimtis", "likvidum", "skirtum", "sesij", "atidarym", "uždarym", "tarpas",
         "palūkanų norma", "infliacij", "doleris", "euras", "auksas", "sidabras", "žalia nafta",
         "foreksas", "indikatori", "žvakė", "slenkamasis vidurkis", "koreliacij"),
        ("pirk", "pirkti", "parduo", "parduoti", "ilga pozicija", "trumpa pozicija", "kyla",
         "kilimas", "krenta", "kritimas", "auga", "augimas", "mažėja", "didėja", "tęsiasi",
         "apsisuka"),
        ("minut", "valand", "dien", "dienos", "kasdien", "savait", "savaitės", "mėnes",
         "mėnesio", "trumpalaik", "ilgalaik", "laiko rėm", "skalping", "nakt")),
    "lv": (
        ("momentums", "tendence", "trends", "izlaušanās", "atbalsts", "pretestība",
         "svārstīgum", "apjoms", "likviditāte", "starpība", "sesija", "atvēršana", "slēgšana",
         "plaisa", "procentu likme", "inflācija", "dolārs", "eiro", "zelts", "sudrabs",
         "jēlnafta", "forekss", "indikators", "svece", "slīdošais vidējais", "korelācija"),
        ("pirk", "pirkt", "pārdo", "pārdot", "garā pozīcija", "īsā pozīcija", "kāpj", "kāpums",
         "krīt", "kritums", "aug", "pieaug", "samazinā", "palielinā", "turpinā", "apgriež"),
        ("minūt", "stund", "dien", "dienas", "ikdien", "nedēļ", "nedēļas", "mēnes", "mēneša",
         "īstermiņ", "ilgtermiņ", "laika rāmi", "skalping", "nakt")),
    "hr": (
        ("momentum", "trend", "tendencij", "proboj", "podršk", "otpor", "volatilnost",
         "volumen", "likvidnost", "spread", "sesij", "otvaranj", "zatvaranj", "gap", "kamatn",
         "inflacij", "dolar", "euro", "zlato", "srebro", "sirova nafta", "forex", "indikator",
         "svijeć", "pomični prosjek", "korelacij"),
        ("kupi", "kupnj", "kupovin", "prodaj", "prodaja", "long", "short", "rast", "raste",
         "pad", "pada", "poraste", "opada", "gore", "dolje", "nastav"),
        ("minut", "sat", "dan", "dnevn", "tjed", "tjedn", "mjesec", "mjesečn", "kratkoročn",
         "dugoročn", "vremenski okvir", "skalping", "noć", "jutr")),
    "sk": (
        ("momentum", "trend", "tendenci", "prieraz", "podpor", "odpor", "volatilit", "objem",
         "likvidit", "spread", "seans", "otvoren", "zatvoren", "medzer", "úrokov", "inflác",
         "dolár", "euro", "zlato", "striebro", "surová ropa", "forex", "indikátor", "sviečk",
         "kĺzavý priemer", "korelác"),
        ("kúp", "kúpiť", "predaj", "predať", "long", "short", "rast", "rastie", "pokles",
         "klesá", "stúpa", "stúpne", "nahor", "nadol", "pokrač", "obrat"),
        ("minút", "hodin", "deň", "denn", "týžd", "týždenn", "mesiac", "mesačn", "krátkodob",
         "dlhodob", "časový rámec", "skalping", "noc", "ráno")),
    "af": (
        ("momentum", "tendens", "neiging", "uitbreek", "steun", "weerstand",
         "wisselvalligheid", "volume", "likiditeit", "spread", "sessie", "opening", "sluiting",
         "gaping", "rentekoers", "inflasie", "dollar", "euro", "goud", "silwer", "ru-olie",
         "forex", "aanwyser", "kers", "bewegende gemiddelde", "korrelasie"),
        ("koop", "verkoop", "lang posisie", "kort posisie", "styg", "styging", "daal",
         "daling", "klim", "val", "hoër", "laer", "sterker", "swakker", "voortgaan", "omkeer"),
        ("minuut", "minute", "uur", "dag", "daagliks", "week", "weekliks", "maand",
         "maandeliks", "korttermyn", "langtermyn", "tydraamwerk", "skalpering", "nag")),
}

#: Function words for the Latin additions, scored like `mechanism_claims._STOPWORDS`. Words
#: another language read here also uses heavily ("die", "nie" alone, "je", "se") are left out.
STOPWORDS: dict[str, tuple[str, ...]] = {
    "af": ("gewoonlik", "baie", "wanneer", "hierdie", "daardie", "sal", "gaan", "dikwels",
           "prys", "nie", "ook", "wat", "die", "ná"),
    "az": ("və", "üçün", "adətən", "əgər", "qiyməti", "həm", "isə", "daha çox", "çünki"),
    "uz": ("va", "bilan", "uchun", "keyin", "odatda", "agar", "lekin", "juda", "narxi", "emas",
           "ham"),
    "et": ("ja", "see", "kui", "ei", "pärast", "tavaliselt", "sageli", "või", "mis", "aga",
           "hind"),
    "lt": ("ir", "yra", "kad", "kai", "bet", "arba", "dažnai", "paprastai", "kaina", "tai",
           "jei", "nėra"),
    "lv": ("un", "ir", "ka", "kad", "bet", "vai", "pēc", "bieži", "parasti", "cena", "tas",
           "nav"),
    "hr": ("da", "su", "kada", "ali", "ili", "nakon", "obično", "često", "cijena", "što", "nije",
           "kao"),
    "sk": ("sa", "že", "sú", "pre", "keď", "ale", "alebo", "ako", "tiež", "zvyčajne", "často",
           "pri", "ktorý", "nie", "cena"),
}
#: Letters only one of the additions writes; each counts as two function words.
LETTER_HINTS: tuple[tuple[str, str], ...] = (
    ("ə", "az"), ("oʻ", "uz"), ("gʻ", "uz"), ("o'", "uz"), ("õ", "et"), ("ė", "lt"),
    ("į", "lt"), ("ų", "lt"), ("ģ", "lv"), ("ķ", "lv"), ("ļ", "lv"), ("ņ", "lv"), ("ā", "lv"),
    ("ē", "lv"), ("ī", "lv"), ("đ", "hr"), ("ľ", "sk"), ("ĺ", "sk"), ("ŕ", "sk"), ("ô", "sk"),
    ("ŉ", "af"),
)
#: Letters no language read before these writes: one of them settles the language outright,
#: before function words are scored (Turkish shares Azerbaijani's ı ş ğ ç and scores above it on
#: hints, Polish shares Lithuanian's ą ę, German shares Afrikaans's "die").
DECISIVE_LETTERS: tuple[tuple[str, str], ...] = (
    ("ə", "az"), ("ėįų", "lt"), ("ģķļņ", "lv"), ("đ", "hr"), ("ľĺŕ", "sk"), ("ŉ", "af"),
)
#: Cyrillic additions against Russian and Ukrainian (checked in this order): Kazakh's letters,
#: Mongolian's, Serbian's, then Bulgarian by particles in a text with no ы or э.
KAZAKH_LETTERS = "әғқңұһӘҒҚҢҰҺ"
MONGOLIAN_LETTERS = "өүӨҮ"
SERBIAN_LETTERS = "ђјљњћџЂЈЉЊЋЏ"
BULGARIAN_MARKERS: tuple[str, ...] = (" са ", " че ", " от ", " като ", " това ", " ще ",
                                      " които ", " след ", " обикновено ", " при ")
RUSSIAN_ONLY = "ыэЫЭ"

#: First symbol of an INSTRUMENT_ALIASES row -> the words for it (see the module note on oil).
ALIASES: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("злато", "златото", "злата", "алтын", "алтынның", "алтны", "алтан", "qızıl",
               "oltin", "kuld", "kulla", "auksas", "aukso", "zelts", "zelta", "zlatom"),
    "XAGUSD": ("сребро", "среброто", "сребра", "күміс", "gümüş", "kumush", "hõbe", "hõbeda",
               "sidabras", "sidabro", "sudrabs", "sudraba", "srebro", "srebra", "striebro",
               "striebra", "silwer"),
    "XTIUSD": ("петрол", "нафта", "нафте", "мұнай", "газрын тос", "neft", "naftos", "naftas",
               "nafte", "naftu", "žalia nafta", "jēlnafta", "toornafta", "sirova nafta",
               "surová ropa", "ru-olie", "ruolie"),
}

#: Direction buckets the mechanism key reads (exact VOCAB terms).
DIR_BUCKETS: dict[str, tuple[str, ...]] = {
    "long": ("купува", "купи", "покачва", "поскъпва", "расте", "нагоре", "купити", "купуј",
             "раст", "порасти", "горе", "сатып ал", "өсу", "өседі", "көтеріл", "жоғары",
             "худалдаж ав", "авах", "өсөх", "өснө", "өгсөх", "дээш", "alın", "alış", "almaq",
             "artır", "yüksəl", "bahalaş", "sotib ol", "sotib olish", "o'sadi", "o'sish",
             "ko'tariladi", "qimmatlashadi", "ost", "osta", "tõuse", "tõus", "kasva", "üles",
             "pirk", "pirkti", "kyla", "kilimas", "auga", "augimas", "didėja", "pirkt",
             "kāpj", "kāpums", "aug", "pieaug", "palielinā", "kupi", "kupnj", "kupovin",
             "raste", "poraste", "kúp", "kúpiť", "rastie", "stúpa", "stúpne", "nahor", "koop",
             "styg", "styging", "klim", "hoër", "sterker"),
    "short": ("продава", "продай", "поевтинява", "спада", "пада", "надолу", "продаја",
              "пад", "опада", "доле", "сату", "сатамыз", "төмендеу", "төмендейді", "құлау",
              "түсе", "төмен", "зарах", "зарна", "буурах", "буурна", "унах", "доош", "satmalı",
              "satış", "satmaq", "enir", "düşür", "düşüş", "ucuzlaş", "sotish", "soting",
              "tushadi", "tushish", "pasayadi", "pasayish", "arzonlashadi", "müü", "müük",
              "lange", "langus", "kahane", "alla", "parduo", "parduoti", "krenta", "kritimas",
              "mažėja", "pārdo", "pārdot", "krīt", "kritums", "samazinā", "prodaj", "prodaja",
              "opada", "dolje", "predaj", "predať", "pokles", "klesá", "nadol",
              "verkoop", "daal", "daling", "val", "laer", "swakker"),
}
