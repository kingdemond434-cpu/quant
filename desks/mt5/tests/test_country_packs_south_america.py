"""THE SOUTH AMERICA COUNTRY PACKS: validated, counted, and checked against the broker.

    python -m pytest desks/mt5/tests/test_country_packs_south_america.py -q

WHAT THESE TESTS ARE FOR, AND WHAT THEY DELIBERATELY ARE NOT. They do not check that the packs
say true things about Brazil -- no test can do that. They check the properties that make a pack
USABLE and that silently break: that every executable instrument is in the broker's own registry
and is not a single-name equity, that every transmission seed lands on a symbol that exists, that
the actor and domain counts clear the floors, that the native terminology is actually in
Portuguese and Spanish rather than an English glossary with accents, that the holiday tables carry
the specific dates a calendar miner will ask for, and that every source carries all three
independent labels and one of the ten layers.

TWO REGRESSIONS ARE PINNED HERE BECAUSE THEY COST SOMETHING ONCE.

  1. A ONE-ELEMENT TUPLE WRITTEN WITHOUT ITS TRAILING COMMA IS A STRING, and a string iterates as
     CHARACTERS. `("only one item")` in an actor's `constraints` gives that actor fourteen
     single-letter constraints, every downstream count is wrong, and nothing raises. Twenty-nine
     of these existed across these packs at one point. `test_sequence_fields_are_sequences`
     fails on the next one.

  2. THE PACK IS VALIDATED IN ITS PLAIN-DATA FORM. `libs.research.country_lab.CountryPack` now
     COERCES a dict pack into typed rows and drops keys it does not know, so `check_pack` applied
     to the coerced object reads a vocabulary that is not the one the pack authored. The dict is
     the deliverable; the dataclass is a view of it. Both are asserted, each against the
     vocabulary that is actually its own.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import countries as C  # noqa: E402

CODES = ("br", "cl", "ar", "mx", "co")

#: The ten layers and the three label vocabularies, repeated here ON PURPOSE. A test that imports
#: its expectations from the module under test asserts only that the module agrees with itself.
LAYERS = ("official", "institutional", "academic", "practitioner", "retail_ecology",
          "app_ecosystem", "media", "archive", "physical_economy", "source_graph")
ACCESS = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE",
          "PUBLIC_SOCIAL", "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
          "STOLEN_UNAUTHORIZED")
CREDIBILITY = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
PREDICTIVE = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")

#: Fields that MUST be sequences of strings. A bare string here iterates as characters.
SEQUENCE_FIELDS = ("forced_to", "information", "constraints", "instruments", "counterparties",
                   "observables", "objects", "conditions", "controls", "targets", "roots",
                   "languages", "queries", "assets", "mechanism_families")


def _mod(code: str):
    return __import__(f"research.countries.{code}.pack", fromlist=["pack"])


@pytest.fixture(scope="module")
def packs() -> dict[str, dict]:
    return {code: _mod(code).as_dict() for code in CODES}


def test_every_pack_validates_in_its_own_vocabulary(packs: dict[str, dict]) -> None:
    """`check_pack` on the PLAIN DATA -- the form the packs author and the tests own."""
    for code, data in packs.items():
        problems = C.check_pack(data)
        assert problems == [], f"{code}: {problems[:6]}"


def test_counts_clear_the_floors(packs: dict[str, dict]) -> None:
    for code, data in packs.items():
        assert len(data["actors"]) >= 12, f"{code} actors"
        assert len(data["domains"]) >= 10, f"{code} domains"
        assert len(data["transmission_edges_seed"]) >= 8, f"{code} edges"
        assert len(data["datasets"]) >= 10, f"{code} datasets"
        assert len(data["policy_eras"]) >= 5, f"{code} eras"


def test_every_actor_has_eleven_fields_and_a_falsifier(packs: dict[str, dict]) -> None:
    """An actor with no falsifier is a story, and a story is not a research object."""
    for code, data in packs.items():
        for actor in data["actors"]:
            for field in C.ACTOR_FIELDS:
                assert actor.get(field), f"{code}/{actor.get('name')}: {field} empty"
            assert len(str(actor["falsifier"])) > 40, f"{code}/{actor['name']}: token falsifier"


def test_every_domain_names_a_negative_control(packs: dict[str, dict]) -> None:
    for code, data in packs.items():
        for dom in data["domains"]:
            assert len(dom["controls"]) >= 2, f"{code}/{dom['id']}: fewer than two controls"


def test_sequence_fields_are_sequences_not_strings(packs: dict[str, dict]) -> None:
    """THE TRAILING-COMMA REGRESSION. `("one item")` is a string and iterates as characters."""
    for code, data in packs.items():
        for bucket in ("actors", "domains", "transmission_edges_seed", "datasets",
                       "source_classes"):
            for row in data[bucket]:
                for field in SEQUENCE_FIELDS:
                    if field not in row:
                        continue
                    value = row[field]
                    assert not isinstance(value, str), (
                        f"{code}/{bucket}/{row.get('id') or row.get('name')}: {field} is a bare "
                        f"string -- a one-element tuple needs its trailing comma or it iterates "
                        f"as characters")


def test_executable_instruments_are_real_and_are_never_equities(packs: dict[str, dict]) -> None:
    """Absence is not permission and a single-name equity may never be hunted (2026-09-06)."""
    universe = C.universe()
    assert universe, "the broker registry is unreadable; nothing here was checked against anything"
    for code, data in packs.items():
        split = C.resolve(data["executable_instruments"])
        assert split["absent"] == [], f"{code}: {split['absent']} not in the broker universe"
        assert split["equities"] == [], f"{code}: {split['equities']} are single names"


def test_every_seed_names_executable_targets(packs: dict[str, dict]) -> None:
    for code, data in packs.items():
        execs = set(data["executable_instruments"])
        for edge in data["transmission_edges_seed"]:
            assert edge["targets"], f"{code}/{edge['id']}: no target"
            for sym in edge["targets"]:
                assert sym in execs, f"{code}/{edge['id']}: {sym} is not declared executable"
            assert edge["evidence"] in C.EDGE_EVIDENCE
            assert edge["asset"] == edge["targets"][0], f"{code}/{edge['id']}: derived asset"
            assert isinstance(edge["lag_days"], float), f"{code}/{edge['id']}: lag_days not a float"


def test_transmission_only_packs_declare_an_empty_own_price() -> None:
    """CL, AR and CO have no quotable local instrument, and the pack says so in its first field."""
    for code in ("cl", "ar", "co"):
        assert _mod(code).OWN_PRICE == (), f"{code} must declare OWN_PRICE empty"
    assert "USDBRL" in _mod("br").OWN_PRICE
    assert "USDMXN" in _mod("mx").OWN_PRICE


def test_terminology_is_native_portuguese_and_spanish(packs: dict[str, dict]) -> None:
    """A miner querying Brazilian boards in English finds the wire copy and nothing else."""
    required = {
        "br": ("PTAX", "Selic", "COPOM", "fluxo cambial", "exportadores", "safra",
               "kit de reversao", "boleta"),
        "cl": ("dolar observado", "cobre", "TPM", "AFP", "multifondos", "huelga"),
        "ar": ("brecha", "cepo", "dolar blue", "contado con liqui", "retenciones", "soja",
               "dolar MEP"),
        "mx": ("Banxico", "TIIE", "tipo de cambio FIX", "remesas familiares", "nearshoring"),
        "co": ("TRM", "precio interno de referencia", "cafe", "FNC", "Ecopetrol"),
    }
    for code, terms in required.items():
        vocab = {t for bucket in packs[code]["terminology"].values() for t in bucket}
        for term in terms:
            assert term in vocab, f"{code}: native term {term!r} missing from TERMINOLOGY"
        assert len(vocab) >= 60, f"{code}: only {len(vocab)} distinct native terms"


def test_native_languages_are_the_local_ones(packs: dict[str, dict]) -> None:
    expect = {"br": "pt-BR", "cl": "es-CL", "ar": "es-AR", "mx": "es-MX", "co": "es-CO"}
    for code, lang in expect.items():
        assert lang in packs[code]["native_languages"], f"{code}: {lang} not declared"


@pytest.mark.parametrize(("code", "iso", "fragment"), [
    ("br", "2026-02-16", "Carnaval"),
    ("br", "2026-02-17", "Carnaval"),
    ("br", "2026-04-03", "Sexta-feira Santa"),
    ("br", "2026-06-04", "Corpus Christi"),
    ("ar", "2026-05-25", "Revolucion de Mayo"),
    ("ar", "2026-02-16", "Carnaval"),
    ("cl", "2026-09-18", "Independencia"),
    ("cl", "2026-09-19", "Glorias del Ejercito"),
    ("mx", "2026-09-16", "Independencia"),
    ("mx", "2026-11-16", "Revolucion"),
    ("co", "2026-06-15", "Sagrado Corazon"),
    ("co", "2026-11-16", "Cartagena"),
])
def test_holiday_tables_carry_the_dates_a_calendar_miner_asks_for(
        code: str, iso: str, fragment: str, packs: dict[str, dict]) -> None:
    table = C.holiday_table(packs[code]["holidays_rule"], 2026)
    assert iso in table, f"{code}: {iso} absent from the 2026 table"
    assert fragment.lower() in table[iso].lower(), f"{code}/{iso}: {table[iso]!r}"


def test_holiday_rules_carry_three_years_and_a_derivation(packs: dict[str, dict]) -> None:
    """A table with no rule beside it cannot be extended past the years somebody typed."""
    for code, data in packs.items():
        rule = data["holidays_rule"]
        assert len(str(rule.get("rule") or "")) > 200, f"{code}: derivation text too thin"
        for year in (2024, 2025, 2026):
            table = C.holiday_table(rule, year)
            assert len(table) >= 9, f"{code}/{year}: {len(table)} holidays"
            for iso in table:
                assert date.fromisoformat(iso).year == year, f"{code}/{year}: {iso}"


def test_colombia_monday_law_is_measured_not_asserted() -> None:
    """Ley Emiliani moves twelve holidays to a Monday; the pack reports the share as a number."""
    co = _mod("co")
    share = co.monday_share(2026)
    assert 0.5 <= share <= 0.9, f"Emiliani Monday share {share:.2f} looks wrong"
    assert co.is_closed(date(2026, 9, 18)) is False       # a Colombian Friday, not a holiday
    assert co.is_closed(date(2026, 7, 20)) is True        # Independencia, immovable


def test_brazil_expiry_is_the_first_business_day_not_a_third_friday() -> None:
    """A wrong expiry constant silently inverts the sign of a whole domain."""
    br = _mod("br")
    assert br.dol_expiry(2026, 1) == date(2026, 1, 2)     # 1 Jan is a holiday, rolls forward
    assert br.dol_expiry(2026, 6) == date(2026, 6, 1)
    assert br.carnaval(2026) == (date(2026, 2, 16), date(2026, 2, 17))
    with pytest.raises(KeyError):
        br.easter(2099)                                   # never guessed


def test_every_source_carries_a_layer_and_three_independent_labels(
        packs: dict[str, dict]) -> None:
    """The principal's depth rule: ten layers, three labels, and a machine-use flag on every row."""
    for code, data in packs.items():
        for src in data["source_classes"]:
            sid = src.get("id")
            assert src.get("layer") in LAYERS, f"{code}/{sid}: layer {src.get('layer')!r}"
            assert src.get("access_label") in ACCESS, f"{code}/{sid}: access_label"
            assert src.get("credibility") in CREDIBILITY, f"{code}/{sid}: credibility"
            assert src.get("predictive_state") in PREDICTIVE, f"{code}/{sid}: predictive_state"
            assert isinstance(src.get("machine_use_allowed"), bool), f"{code}/{sid}: machine_use"
            assert src.get("roots"), f"{code}/{sid}: no crawlable root"
            assert len(src.get("queries") or ()) >= 3, f"{code}/{sid}: fewer than three queries"


def test_every_layer_is_covered_or_named_absent_with_a_reason() -> None:
    """A country is never 'covered' by five obvious official feeds; blank is never an answer."""
    for code in CODES:
        cov = _mod(code).source_layer_coverage()
        assert cov["unexplained_missing"] == [], (
            f"{code}: layers {cov['unexplained_missing']} have neither a source nor a reason")
        assert cov["unknown_layer_tags"] == [], f"{code}: {cov['unknown_layer_tags']}"
        assert cov["n_layers_covered"] == len(LAYERS), f"{code}: {cov['n_layers_covered']}/10"


def test_queries_are_native_not_translated_english(packs: dict[str, dict]) -> None:
    """A query written in English finds the English wire copy, which is the one thing already
    priced. Every source's queries must carry the local vocabulary."""
    markers = {"br": ("dolar", "safra", "day trade", "robo", "fluxo", "cafe", "juros", "acucar",
                      "carga", "bolsa", "cambio", "serie", "taxa", "precio", "conjunto"),
               "cl": ("dolar", "cobre", "fondo", "huelga", "minera", "tipo de cambio", "serie",
                      "bloqueo", "reservas", "invertir", "catalogo", "feriados", "traspasos"),
               "ar": ("dolar", "blue", "brecha", "cepo", "soja", "rulo", "cueva", "reservas",
                      "liquidacion", "bonos", "plazo fijo", "comunicacion", "parking"),
               "mx": ("peso", "dolar", "remesas", "tasa", "crudo", "tipo de cambio", "cetes",
                      "cruces", "serie", "expectativas", "inhabiles", "produccion"),
               "co": ("dolar", "cafe", "carga", "trm", "petroleo", "oleoducto", "tasa", "festivos",
                      "embalses", "cosecha", "serie", "datos abiertos")}
    for code, data in packs.items():
        text = " ".join(q.lower() for s in data["source_classes"] for q in (s.get("queries") or ()))
        hits = [m for m in markers[code] if m in text]
        assert len(hits) >= 6, f"{code}: only {hits} native query markers found"


def test_retail_and_app_layers_are_kept_even_though_unreliable(packs: dict[str, dict]) -> None:
    """Fringe or unreliable PUBLIC material is an evidence object with low weight, never dropped:
    the retail crowd's beliefs ARE the mechanism in several of these domains."""
    for code, data in packs.items():
        retail = [s for s in data["source_classes"]
                  if s["layer"] in ("retail_ecology", "app_ecosystem")]
        assert len(retail) >= 2, f"{code}: the retail and app layers are not both present"
        assert any(s["credibility"] in ("UNRELIABLE", "FRINGE") for s in retail), (
            f"{code}: no unreliable-but-kept source; a pack that only keeps authoritative "
            f"sources has discarded the layer where crowd behaviour lives")


def test_datasets_declare_point_in_time_feasibility(packs: dict[str, dict]) -> None:
    for code, data in packs.items():
        for ds in data["datasets"]:
            assert isinstance(ds["pit_feasible"], bool), f"{code}/{ds['name']}"
            assert float(ds["publication_lag_days"]) >= 0.0
            assert ds["how_to_fetch"], f"{code}/{ds['name']}: no fetch route"
        assert any(not ds["pit_feasible"] for ds in data["datasets"]), (
            f"{code}: every dataset claims to be point-in-time, which is not credible for a "
            f"pack that carries a practitioner-claims row")


def test_packs_build_as_country_lab_objects_when_the_framework_is_present() -> None:
    """The framework coerces plain data into typed rows; the pack must survive that and keep its
    derived keys (`asset`, `to_country`) rather than arriving blank."""
    lab = pytest.importorskip("libs.research.country_lab")
    for code in CODES:
        obj = _mod(code).pack()
        if not isinstance(obj, lab.CountryPack):
            continue
        assert obj.code == code
        assert obj.region_command in lab.REGION_COMMANDS
        seeds = obj.transmission_edges_seed
        assert seeds and all(getattr(s, "asset", "") for s in seeds), f"{code}: blank assets"
        assert all(isinstance(getattr(s, "lag_days", None), float) for s in seeds)
        assert obj.policy_eras and all(getattr(e, "name", "") for e in obj.policy_eras)
