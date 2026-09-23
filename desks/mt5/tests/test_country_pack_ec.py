"""THE ECUADOR PACK, VALIDATED -- no currency, a field shut by ballot, a grid on a schedule.

WHAT THESE TESTS REFUSE TO LET THROUGH, and every one of them is a failure this desk has had:

  * A CURRENCY CELL IN A COUNTRY WITH NO CURRENCY. Ecuador has used the US dollar since
    2000-01-09. The tests below assert that no Ecuadorian currency symbol is claimed anywhere,
    that `CENTRAL_BANK.decision_dates` is EMPTY on purpose, that the pack mints no
    central-bank-surprise cells at all, and that USDBRL and USDMXN are declared as REGIONAL RISK
    legs rather than as proxies for an exchange rate that does not exist.
  * A SPANISH-ONLY GLOSSARY OF A THREE-LANGUAGE COUNTRY. Kichwa and Shuar are official for
    intercultural use under article 2 of the 2008 constitution, and the community assemblies that
    shut the Amazonian wellheads sit in them. The vocabulary assertions check all three by name.
  * A SYMBOL THE BOX CANNOT TRADE. Every executable instrument, every domain instrument, every
    edge target and every interaction target is checked against the broker's OWN registry.
  * A SINGLE-NAME EQUITY ON A DOCKET. The two-lane order (2026-09-06) forbids hunting one, and
    this pack is full of tempting national names -- Petroecuador, OCP, CELEC, the mine parents --
    every one of which appears only as an ACTOR.
  * A PACK THAT REACHES THE FRAMEWORK BENT. `CountryPack` coerces every row; a coercion note is a
    field the framework could not read, and this pack must produce none.
  * A BLANK LAYER PRETENDING TO BE A MEASURED ONE. Nine layers are sourced and `retail_ecology`
    is DECLARED ABSENT with its reason and its lawful substitute, which is a measurement.
  * A HOLIDAY TABLE SOMEBODY TYPED. Carnaval and Viernes Santo are DERIVED from Easter with the
    anonymous Gregorian algorithm, and the 2016 TRASLADO rule is derived from the statute and
    asserted date by date -- including the November collision the merge handles honestly.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from countries import (  # type: ignore[import-not-found]  # noqa: E402
    check_pack,
    get,
    holiday_table,
    resolve,
    universe_symbols,
)
from countries.ec import pack as EC  # type: ignore[import-not-found]  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from libs.research import forests as F  # noqa: E402
from libs.research import regional_parity as RP  # noqa: E402

ACTOR_FIELDS = ("holds", "forced_to", "when", "information", "constraints", "instruments",
                "counterparties", "observables", "impact", "persistence", "falsifier")


@pytest.fixture(scope="module")
def built() -> Any:
    """The pack as the framework builds it, resolved through `resolve_pack` so the test measures
    the same object the country lab runs and not a private construction."""
    got = CL.resolve_pack("ec")
    assert got is not None, "no Ecuador pack resolves through the country lab"
    return got


# ------------------------------------------------------------------------------ the pack shape
def test_check_pack_finds_nothing() -> None:
    """`check_pack` is the validator the whole package shares, and an empty list is the pass."""
    assert check_pack(EC.as_dict()) == []


def test_pack_builds_through_the_framework(built: Any) -> None:
    assert str(get(built, "code")) == "ec"
    assert str(get(built, "region_command")) == "latam"
    assert str(get(built, "currency")) == "USD"


def test_the_framework_read_every_row_without_coercion(built: Any) -> None:
    """A coercion note is a field `CountryPack` could not read. There must be none."""
    notes = list(getattr(built, "coercion_notes", ()) or ())
    assert notes == [], f"the framework had to coerce {len(notes)} row(s): {notes[:4]}"
    fatal = CL.fatal_problems(CL.validate_pack(built))
    assert fatal == [], f"validate_pack is FATAL on this pack: {fatal[:4]}"


def test_jurisdictions_are_exactly_ecuador_and_on_the_desks_own_roster() -> None:
    """THE PARITY FENCE COUNTS THIS TUPLE. Ecuador is on the latam roster and no sibling pack
    answers for it: `pe` and `co` are each written around a domestic central bank and a domestic
    currency, and Ecuador has neither."""
    assert EC.JURISDICTIONS == ("ec",)
    assert all(c == c.lower() and len(c) == 2 for c in EC.JURISDICTIONS)
    assert EC.CODE == "ec"
    assert EC.REGION_COMMAND == "latam" and EC.FOREST == "latam"
    # REGISTRATION ON THE SHARED FOREST IS THE COORDINATOR'S EDIT, not this pack's: several
    # builders write `libs/research/forests.py` at once and a rewrite from here would clobber
    # them. Once `EC` is on the latam roster this assertion becomes live; until then the pending
    # state is REPORTED rather than asserted away (L1.28a).
    roster = {c.lower() for forest in F.FORESTS.values() for c in forest.countries}
    if not set(EC.JURISDICTIONS) <= roster:
        pytest.skip("ec is not yet on the forest roster in libs/research/forests.py; the "
                    "coordinator registers the pack on the latam forest")
    latam = F.FORESTS["latam"]
    assert "ec" in {p.lower() for p in latam.packs}, "the pack is not registered on the forest"


def test_pack_reaches_its_declared_parity_depth(built: Any) -> None:
    """The standing depth rule, MEASURED by the framework and not claimed by the pack."""
    row = RP.pack_depth(built, "ec").as_row()
    assert row["score"] >= EC.DECLARED_DEPTH, f"depth {row['score']}: {row['why']}"
    assert row["layers_unmapped"] == 0
    assert row["untagged_sources"] == 0
    for field, floor in RP.DEPTH_TARGETS.items():
        have = row["layers_declared"] if field == "layers" else row[field]
        assert have >= floor, f"{field}: {have} < {floor}"


def test_depth_counts_sit_above_the_floor_and_not_at_it() -> None:
    """Twelve actors is the floor; a country written to the floor is a country half-read."""
    assert len(EC.ACTORS) >= 14
    assert len(EC.DOMAINS) >= 12
    assert len(EC.TRANSMISSION_EDGES_SEED) >= 10
    assert len(EC.SOURCE_CLASSES) >= 20
    assert len(EC.DATASETS) >= 16
    assert len(EC.POLICY_ERAS) >= 6
    assert len(EC.INTERACTIONS) >= 4
    assert EC.term_count() >= 150


def test_every_actor_has_all_eleven_fields_and_a_falsifier() -> None:
    """An actor whose falsifier is blank is a story, and eleven fields is the chain's width."""
    for row in EC.ACTORS:
        for f in ACTOR_FIELDS:
            assert row.get(f), f"actor {row.get('name')!r} has an empty {f}"
        # a one-element tuple written without its trailing comma silently becomes a string, and
        # `tuple("abc")` is then three characters -- this catches that class of typo
        for f in ("forced_to", "information", "constraints", "instruments", "counterparties",
                  "observables"):
            value = row[f]
            assert isinstance(value, tuple), f"actor {row.get('name')!r}.{f} is not a tuple"
            assert all(len(str(v)) > 2 for v in value), (
                f"actor {row.get('name')!r}.{f} looks like a string split into characters -- a "
                f"single-element tuple needs its trailing comma")


def test_every_domain_has_objects_and_two_negative_controls() -> None:
    """Without a control an effect cannot be told from the desk's own sampling."""
    for row in EC.DOMAINS:
        assert row["objects"], f"domain {row['id']} has no research objects"
        assert len(row["controls"]) >= 2, f"domain {row['id']} has fewer than two controls"
        assert len(row["conditions"]) >= 3, f"domain {row['id']} names too few conditions"
        assert row["instruments"], f"domain {row['id']} names no instrument"
        assert row["id"] in EC.DOMAIN_CELL_SPEC, f"{row['id']} mints cells with no family"


# ------------------------------------------------------------------------------ the universe
def test_executable_instruments_are_in_the_brokers_registry() -> None:
    """The universe is the broker's (mandate 2026-08-18), and it is READ, never asserted."""
    registry = universe_symbols()
    assert registry, "the broker registry is unreadable -- UNMEASURED, so nothing here is checked"
    split = resolve(EC.EXECUTABLE_INSTRUMENTS)
    assert split["absent"] == [], f"not in the registry: {split['absent']}"
    assert split["equities"] == [], (
        f"{split['equities']} is a single-name equity and the two-lane order forbids hunting it")
    assert set(EC.EXECUTABLE_INSTRUMENTS) <= set(registry)


def test_every_transmission_seed_and_interaction_names_tradable_targets() -> None:
    """A seed that terminates in a symbol the box cannot quote can never compile a cell."""
    for seed in EC.TRANSMISSION_EDGES_SEED:
        assert seed["targets"], f"edge {seed['id']} names no target"
        split = resolve(seed["targets"])
        assert split["absent"] == [], f"edge {seed['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"edge {seed['id']} -> equity {split['equities']}"
        assert seed["evidence"] in ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")
        assert seed["control"], f"edge {seed['id']} has no control"
        assert seed["falsifier"], f"edge {seed['id']} has no falsifier"
    for row in EC.INTERACTIONS:
        split = resolve(row["targets"])
        assert split["absent"] == [], f"interaction with {row['with']} -> {split['absent']}"
        assert split["equities"] == [], f"interaction with {row['with']} -> {split['equities']}"
        assert row["control"] and row["observable"] and row["mechanism"]
    # THE IDENTIFICATION STRATEGY IS NAMED, NOT IMPLIED: the floating neighbours come first
    assert {"pe", "co"} <= {r["with"] for r in EC.INTERACTIONS}
    assert EC.INTERACTIONS[0]["with"] == "pe"


def test_domain_instruments_are_tradable_and_never_single_names() -> None:
    for row in EC.DOMAINS:
        split = resolve(row["instruments"])
        assert split["absent"] == [], f"domain {row['id']} -> absent {split['absent']}"
        assert split["equities"] == [], f"domain {row['id']} -> equity {split['equities']}"


def test_there_is_no_ecuadorian_currency_and_the_pack_says_so() -> None:
    """THE PACK'S WHOLE THESIS. Ecuador uses the dollar, so the FX absorption channel every
    sibling routes through does not exist here -- and a pack that quietly proxied it with USDBRL
    would be inventing the one institution this country abolished in 2000."""
    registry = universe_symbols()
    assert not {"USDECS", "ECS", "USDPEN", "USDCOP"} & set(registry)
    assert EC.CURRENCY == "USD"
    assert EC.COT_CURRENCY == ""
    first = EC.TRANSMISSION_TARGETS[0]
    assert "There is none" in str(first["name"]) or "no currency" in str(first["route"]).lower()
    assert "dollaris" in str(first["regime"]).lower()
    for row in EC.TRANSMISSION_TARGETS:
        assert row["proxies"], f"{row['name']} is named absent with no carrier"
        assert row["route"], f"{row['name']} is named absent with no route"
        assert resolve(row["proxies"])["absent"] == []
    named = " ".join(str(t["name"]) for t in EC.TRANSMISSION_TARGETS)
    for must in ("Oriente", "Global bonds", "Shrimp FOB", "banana box price"):
        assert must in named, f"{must} is not named as an absent instrument"


def test_no_policy_surprise_object_is_manufactured() -> None:
    """A dollarised economy has no rate to be surprised by, and inventing one would be the
    single easiest way to fabricate an event study out of a publication date."""
    assert EC.CENTRAL_BANK["decision_dates"] == ()
    assert "NONE EXIST" in EC.CENTRAL_BANK["dates_status"]
    assert EC.CENTRAL_BANK["framework"] == "peg"
    assert EC.MINER_DOMAINS["central_bank_surprise"] == ()
    families = {row["mechanism_family"] for row in EC.cells()}
    assert "policy_surprise" not in families, "a policy-surprise cell in a country with no policy"
    assert "daylight saving" in EC.CENTRAL_BANK["dst_rule"].lower()


def test_the_national_champions_appear_only_as_actors() -> None:
    """Petroecuador, OCP, CELEC and the mine parents are the loudest mechanisms in this economy
    and the two-lane order forbids hunting any of them statistically."""
    actor_names = " ".join(str(a["name"]) for a in EC.ACTORS)
    for who in ("Petroecuador", "OCP Ecuador", "CELEC", "CONAIE", "Mirador"):
        assert who in actor_names, f"{who} is not carried as an actor"
    every_symbol: set[str] = set(EC.EXECUTABLE_INSTRUMENTS)
    for row in EC.DOMAINS:
        every_symbol |= set(row["instruments"])
    for seed in EC.TRANSMISSION_EDGES_SEED:
        every_symbol |= set(seed["targets"])
    assert resolve(sorted(every_symbol))["equities"] == []


# ------------------------------------------------------------------------------ the cells
def test_cells_are_real_and_every_declared_instrument_is_used() -> None:
    """THE POINT OF A PACK IS CELLS REACHING THE GAUNTLET. They must also be honest: each cell
    names a condition its own domain declared, on an instrument that domain owns."""
    rows = EC.cells()
    assert 60 <= len(rows) <= 260, f"{len(rows)} cells is outside the honest range"
    by_domain = {d["id"]: d for d in EC.DOMAINS}
    seen_ids: set[str] = set()
    for row in rows:
        for field in ("cell_id", "domain", "symbol", "condition", "mechanism_family",
                      "horizon", "control", "why"):
            assert row.get(field), f"cell {row.get('cell_id')} has an empty {field}"
        assert row["cell_id"] not in seen_ids, f"duplicate cell {row['cell_id']}"
        seen_ids.add(row["cell_id"])
        dom = by_domain[row["domain"]]
        assert row["symbol"] in dom["instruments"], (
            f"{row['cell_id']} names a symbol its own domain does not own")
        assert row["condition"] in dom["conditions"], (
            f"{row['cell_id']} names a condition its own domain never declared")
    unused = [s for s, n in EC.cells_by_symbol().items() if n == 0]
    assert unused == [], f"declared executable but no domain uses it: {unused}"


def test_mine_reports_the_cell_count_and_emits_nothing_without_a_ctx() -> None:
    """`mine(None)` is a MEASUREMENT of what the pack would emit and writes nowhere."""
    report = EC.mine(None)
    assert report["code"] == "ec"
    assert report["cells_emitted"] == len(EC.cells())
    assert report["emitted"] > 0
    assert report["rows"] and all(r.get("miner") for r in report["rows"])
    assert report["jurisdictions"] == ("ec",)
    assert "pe" in report["interactions"] and "co" in report["interactions"]
    # UNMEASURED is a real answer: the miners that need a series this box does not carry say so
    assert any("UNMEASURED" in u or "not loaded" in u or "no rate" in u
               for u in report["unmeasured"]), report["unmeasured"][:3]
    assert "recorded" not in report


def test_every_custom_miner_entry_resolves(built: Any) -> None:
    """`module:function` must actually import and be callable, or the miner is decorative."""
    got, problems = CL.load_custom_miners(built)
    assert problems == [], f"miner resolution: {problems}"
    assert set(got) == {f"custom:{name}" for name in EC.MINERS}
    assert all(callable(fn) for fn in got.values())
    ids = {d["id"] for d in EC.DOMAINS}
    for row in EC.CUSTOM_MINERS:
        module_path, _, func = str(row["entry"]).partition(":")
        assert module_path == "countries.ec.pack", row["entry"]
        assert func in EC.MINERS, f"{row['entry']} is not in the MINERS table"
        assert row["domain_ids"], f"{row['name']} names no domain"
        for did in row["domain_ids"]:
            assert did in ids, f"{row['name']} names unknown domain {did}"
    for domains in EC.MINER_DOMAINS.values():
        assert set(domains) <= ids


# ------------------------------------------------------------------------------ the languages
def test_terminology_carries_spanish_kichwa_and_shuar() -> None:
    """Three languages, because the decision to shut an Amazonian wellhead is taken in two of
    them. Latin script is shared, so this is a VOCABULARY test rather than a codepoint one."""
    assert len(EC.accented_terms()) >= 40, (
        f"only {len(EC.accented_terms())} terms carry a Spanish diacritic -- this reads like an "
        f"English glossary of Ecuador")
    assert len(EC.spanish_terms()) == len(EC.SPANISH_MARKERS), (
        f"missing Spanish working vocabulary: "
        f"{sorted(set(EC.SPANISH_MARKERS) - set(EC.spanish_terms()))}")
    assert len(EC.kichwa_terms()) >= 12, "Kichwa vocabulary is too thin to crawl with"
    assert len(EC.shuar_terms()) >= 5, "no usable Shuar vocabulary at all"
    flat = {t for group in EC.TERMINOLOGY.values() for t in group}
    for must in ("dolarización", "erosión regresiva", "fuerza mayor", "racionamiento eléctrico",
                 "Yasuní", "bloque 43", "consulta popular", "muerte cruzada",
                 "precio mínimo de sustentación", "cacao fino de aroma",
                 "conflicto armado interno", "canje de deuda por naturaleza"):
        assert must in flat, f"the Ecuador pack does not carry {must!r}"
    # the constitution's own Kichwa phrase, and the two metals named in the language of the
    # communities the concessions sit on
    for term in ("sumak kawsay", "quri", "anta", "nunka"):
        assert any(term in t for t in flat), f"indigenous term {term!r} is missing"
    assert EC.has_spanish_diacritic("minería") and not EC.has_spanish_diacritic("mining")
    assert EC.has_kichwa("ayllu asamblea") and not EC.has_kichwa("community assembly")
    assert EC.has_shuar("entsa nunka") and not EC.has_shuar("river land")
    assert len(EC.TERMINOLOGY) >= 14


def test_every_layers_queries_are_written_in_the_languages_of_the_ground() -> None:
    """A query in English finds an English article about the release, not the release."""
    terms = EC.layer_terms()
    accented = [layer for layer, qs in terms.items()
                if any(EC.has_spanish_diacritic(q) for q in qs)]
    assert len(accented) >= 8, f"only {accented} carry an accented Spanish query"
    indigenous = [layer for layer, qs in terms.items()
                  if any(EC.has_kichwa(q) or EC.has_shuar(q) for q in qs)]
    assert len(indigenous) >= 2, f"only {indigenous} carry a Kichwa or Shuar query"
    native = sum(1 for row in EC.SOURCE_CLASSES if row["machine_use_allowed"]
                 for q in row["queries"] if EC.has_spanish_diacritic(q))
    assert native >= 40, f"only {native} accented queries across crawlable sources"


def test_query_territories_cover_every_sourced_layer_natively() -> None:
    """The deep-forest miner's own search space, per layer, in the language of the ground. A
    layer DECLARED ABSENT gets no territory, which is the honest answer rather than three
    invented phrases."""
    assert set(EC.QUERY_TERRITORIES) == set(EC.SOURCE_LAYERS)
    for layer, phrases in EC.QUERY_TERRITORIES.items():
        if layer in EC.LAYER_ABSENCES:
            assert phrases == (), f"{layer} is declared absent but carries query territories"
            continue
        assert len(phrases) >= 3, f"{layer} has only {len(phrases)} query territories"
        assert any(EC.has_spanish_diacritic(p) for p in phrases), (
            f"{layer}'s query territory carries no accented Spanish at all")
    media = EC.QUERY_TERRITORIES["media"]
    assert any(EC.has_kichwa(p) or EC.has_shuar(p) for p in media), (
        "the media territory must reach the indigenous wire in its own language")


def test_every_source_carries_three_independent_labels_and_a_query() -> None:
    """Access, credibility and predictive state are SEPARATE questions and stay separate."""
    for row in EC.SOURCE_CLASSES:
        assert row["access_label"] in EC.ACCESS_LABELS
        assert row["credibility"] in EC.CREDIBILITY_LABELS
        assert row["predictive_state"] in EC.PREDICTIVE_STATES
        assert row["access_label"] not in ("PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
        assert row["notes"], f"{row['id']} says nothing about why it is here"
        if str(row["id"]).startswith("absent_"):
            assert "DECLARED ABSENT" in row["notes"]
            continue
        assert row["queries"], f"{row['id']} has no native-language query"
        assert row["roots"], f"{row['id']} has no crawlable root"


def test_nine_layers_are_sourced_and_the_tenth_is_declared_absent_with_a_reason() -> None:
    """The principal's depth rule, and the honest half of it: a layer a country genuinely does
    not have is a MEASUREMENT when it is named and a hole when it is left blank."""
    counts = EC.layer_counts()
    assert set(counts) == set(EC.SOURCE_LAYERS)
    blank = [layer for layer, n in counts.items() if not n]
    assert blank == ["retail_ecology"], f"unexpected blank layers: {blank}"
    coverage = EC.source_layer_coverage()
    assert coverage["n_layers_covered"] == 9
    assert coverage["unexplained_missing"] == []
    assert set(EC.LAYER_ABSENCES) == {"retail_ecology"}
    why = EC.LAYER_ABSENCES["retail_ecology"]
    assert "no domestic currency" in why and "substitute" in why, (
        "an absence must name BOTH the reason and the lawful substitute")
    assert coverage["machine_use_forbidden"], (
        "nothing is registered as machine-use-forbidden, which is implausible for a country "
        "whose crude differential and shrimp FOB both live behind a price-reporting paywall")
    assert coverage["low_weight_kept"], "no fringe ground is kept at all, so it was dropped"


def test_no_crypto_exchange_ground_is_hunted() -> None:
    """Mandate 2026-08-18: no venue order book, no exchange feed, no exchange as a source."""
    blob = " ".join(str(r["label"]) + " ".join(r["roots"]) + " ".join(r["queries"])
                    for r in EC.SOURCE_CLASSES).lower()
    for venue in ("binance", "bybit", "okx", "hyperliquid", "coinbase", "kraken"):
        assert venue not in blob, f"{venue} is named as ground, which the mandate forbids"


# ------------------------------------------------------------------------------ the calendars
def test_the_holiday_table_resolves_for_all_three_years_inside_their_years() -> None:
    for year in (2024, 2025, 2026):
        table = holiday_table(EC.HOLIDAYS_RULE, year)
        assert table, f"no holiday table for {year}"
        for iso in table:
            assert date.fromisoformat(iso).year == year, f"{iso} is not in {year}"
        assert f"{year}-01-01" in table, "Ano Nuevo missing"
        assert f"{year}-12-25" in table, "Navidad missing"
    assert EC.HOLIDAYS_RULE["rule"].strip()
    assert "anonymous Gregorian" in EC.HOLIDAYS_RULE["rule"]
    assert "TRASLADO" in EC.HOLIDAYS_RULE["rule"]


def test_easter_is_computed_and_carnaval_follows_from_it() -> None:
    """MECHANISM FUNCTION ONE. Easter is derived with the anonymous Gregorian algorithm, so both
    Carnaval days and Viernes Santo extend to any year without anybody editing the file."""
    assert EC.easter(2024) == date(2024, 3, 31)
    assert EC.easter(2025) == date(2025, 4, 20)
    assert EC.easter(2026) == date(2026, 4, 5)
    assert EC.carnaval(2025) == (date(2025, 3, 3), date(2025, 3, 4))
    assert EC.carnaval(2026) == (date(2026, 2, 16), date(2026, 2, 17))
    assert EC.good_friday(2024) == date(2024, 3, 29)
    for year in (2024, 2025, 2026):
        lunes, martes = EC.carnaval(year)
        assert lunes.weekday() == 0 and martes.weekday() == 1, "Carnaval is Monday and Tuesday"
        table = EC.national_holidays(year)
        # NEVER TRASLADABLE: the statute exempts Carnaval, so both days stay where they fall
        assert lunes in table and martes in table
        assert EC.good_friday(year) in table
        # JUEVES SANTO IS NOT A FERIADO HERE, which is a real difference from Peru and Paraguay
        assert EC.easter(year) - __import__("datetime").timedelta(days=3) not in table


def test_the_traslado_rule_is_derived_from_the_statute_and_not_typed() -> None:
    """MECHANISM FUNCTION TWO, and the one a typed table could never explain. Tuesday moves back
    to Monday, Wednesday and Thursday forward to Friday, Saturday back to Friday and Sunday
    forward to Monday -- and 1 January, Carnaval and 25 December never move at all."""
    assert EC.traslado(date(2024, 10, 8)) == date(2024, 10, 7)     # Tuesday  -> Monday before
    assert EC.traslado(date(2024, 5, 1)) == date(2024, 5, 3)       # Wednesday -> Friday after
    assert EC.traslado(date(2025, 5, 1)) == date(2025, 5, 2)       # Thursday -> Friday after
    assert EC.traslado(date(2024, 8, 10)) == date(2024, 8, 9)      # Saturday -> Friday before
    assert EC.traslado(date(2025, 8, 10)) == date(2025, 8, 11)     # Sunday   -> Monday after
    assert EC.traslado(date(2026, 5, 1)) == date(2026, 5, 1)       # Friday   -> unmoved
    assert EC.traslado(date(2026, 8, 10)) == date(2026, 8, 10)     # Monday   -> unmoved
    # the exempt days: the statutory date is the observed date in every year
    for year in (2024, 2025, 2026):
        table = EC.national_holidays(year)
        assert date(year, 1, 1) in table and date(year, 12, 25) in table
    # and the moved set is DERIVED, not typed
    moved = {(s, o) for s, o, _n in EC.moved_holidays(2024)}
    assert (date(2024, 5, 1), date(2024, 5, 3)) in moved
    assert (date(2024, 11, 2), date(2024, 11, 1)) in moved
    assert EC.moved_holidays(2026) and all(s != o for s, o, _n in EC.moved_holidays(2026))


def test_the_november_collision_is_merged_rather_than_silently_overwritten() -> None:
    """2 and 3 November are adjacent feriados and the traslado rule lands them on the same day
    often. A dict that let one overwrite the other would lose a holiday without saying so."""
    table = EC.national_holidays(2026)
    collided = [name for day, name in table.items() if day.month == 11 and " y " in name]
    assert collided, "the 2026 November pair should collide onto one observed day and merge"
    assert "Difuntos" in collided[0] and "Cuenca" in collided[0]
    assert len(EC.statutory_holidays(2026)) >= len(table), (
        "the statutory table can never be smaller than the observed one once days merge")


def test_market_holidays_drop_weekend_feriados_and_the_regional_calendar_is_separate() -> None:
    for year in (2024, 2025, 2026):
        assert all(d.weekday() < 5 for d in EC.market_holidays(year))
        assert set(EC.market_holidays(year)) <= set(EC.national_holidays(year))
        regional = EC.regional_days(year)
        assert date(year, 12, 6) in regional, "Fundacion de Quito is a provincial day"
        assert date(year, 6, 21) in regional, "Inti Raymi is in the sierra calendar"
        assert date(year, 12, 6) not in EC.national_holidays(year), (
            "a provincial day must never enter the national market table")


# ------------------------------------------------------------------------------ the mechanisms
def test_the_pipeline_record_is_a_dated_supply_series() -> None:
    """MECHANISM FUNCTION THREE, and one half of the reason this pack exists. Both pipelines
    ruptured in April 2020 after the San Rafael waterfall collapsed and the Coca began eating
    its bed backwards toward the crossings."""
    assert len(EC.PIPELINE_EPISODES) >= 6
    assert EC.is_pipeline_outage(date(2020, 4, 15)) is True
    assert EC.is_pipeline_outage(date(2022, 6, 20)) is True
    assert EC.is_pipeline_outage(date(2021, 3, 15)) is False
    assert EC.is_pipeline_outage(date(2015, 6, 1)) is False
    days = EC.pipeline_outage_days(date(2020, 4, 1), date(2020, 6, 1))
    assert len(days) >= 25, f"only {len(days)} disrupted days in the 2020 rupture window"
    assert all(EC.is_pipeline_outage(d) for d in days)
    # every row is hypothesis-grade until a gazette or operator citation is attached
    assert all(st == "PRESS_REPORTED" for *_rest, st in EC.PIPELINE_EPISODES)
    assert len(EC.pipeline_episodes("GAZETTE_VERIFIED")) == 0, (
        "no episode may claim a gazette citation it does not have")
    blob = " ".join(str(c["constraint"]) + str(c["measured"]) + str(c["consequence"])
                    for c in EC.ACCESS_CONSTRAINTS)
    assert "PRESS_REPORTED" in blob


def test_the_rationing_episodes_are_a_quantified_output_shock() -> None:
    """MECHANISM FUNCTION FOUR. A published, scheduled, hour-counted loss of industrial load --
    and in April 2024 the state decreed two national non-working days to shed demand."""
    assert len(EC.RATIONING_EPISODES) >= 3
    assert EC.is_rationing_day(date(2024, 10, 15)) is True
    assert EC.is_rationing_day(date(2024, 4, 18)) is True
    assert EC.is_rationing_day(date(2024, 7, 15)) is False
    assert EC.is_rationing_day(date(2019, 10, 5)) is False
    state = EC.rationing_state(date(2024, 10, 15))
    assert state is not None and state[0] >= 12.0
    assert EC.rationing_days(2024) >= 90, "the 2024 rationing rounds ran for months"
    assert EC.rationing_days(2019) == 0
    # the decreed non-working days are in the holiday table as DECREE_REPORTED, not invented
    table = EC.national_holidays(2024)
    assert date(2024, 4, 18) in table and "DECREE_REPORTED" in table[date(2024, 4, 18)]


def test_the_itt_referendum_is_carried_as_a_supply_regime_and_not_as_colour() -> None:
    """A sovereign electorate voted a producing field shut on a published ballot. The regime
    function is what stops a crude-supply study from pooling across 2023-08-20."""
    assert EC.itt_regime(date(2014, 1, 1)) == "PRE_ITT_PRODUCTION"
    assert EC.itt_regime(date(2019, 6, 1)) == "ITT_PRODUCING"
    assert EC.itt_regime(date(2023, 9, 1)) == "POST_REFERENDUM_WIND_DOWN"
    assert EC.itt_regime(date(2025, 1, 1)) == "POST_DEADLINE"
    ballots = [d for d, _w, _s in EC.ITT_EVENTS]
    assert date(2023, 8, 20) in ballots and date(2024, 8, 31) in ballots
    assert all(st == "PRESS_REPORTED" for *_r, st in EC.ITT_EVENTS)
    ec_d = next(d for d in EC.DOMAINS if d["id"] == "EC-D")
    assert resolve(ec_d["instruments"])["tradable"] == list(ec_d["instruments"])


def test_cot_is_declared_undefined_rather_than_silently_missing() -> None:
    """There is no Ecuadorian currency, so there is no contract, and there never can be. That is
    not UNMEASURED -- it is UNDEFINED, and the difference is worth writing down."""
    rows = {r["name"]: r for r in EC.POSITIONING_SOURCES}
    cot = [r for r in rows.values() if not r["available"]]
    assert cot, "the COT question is not answered anywhere in the pack"
    assert any("DOES NOT EXIST AND CANNOT" in str(r["pit_warning"]) for r in cot)
    assert EC.COT_CURRENCY == ""


def test_every_dataset_carries_all_twelve_fields_and_a_fetchable_route() -> None:
    from countries import DATASET_FIELDS  # type: ignore[import-not-found]
    assert len(EC.DATASETS) >= 16
    for row in EC.DATASETS:
        for field in DATASET_FIELDS:
            if field == "pit_feasible":
                assert isinstance(row[field], bool)
                continue
            if field == "publication_lag_days":
                assert float(row[field]) >= 0.0
                continue
            assert row.get(field), f"dataset {row.get('name')!r} has an empty {field}"
        assert len(str(row["how_to_fetch"])) > 40, (
            f"dataset {row['name']!r} has a how_to_fetch a collector cannot act on")
    assert any(not row["pit_feasible"] for row in EC.DATASETS), (
        "every dataset claims to be point-in-time reconstructible, which is not true of any "
        "country whose ministries overwrite their statistics pages in place")
