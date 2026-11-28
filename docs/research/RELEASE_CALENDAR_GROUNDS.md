# Release calendar grounds: the 25 zero-claim regions (2026-11-18)

Derived from `desks/mt5/data/release_calendar_grounds.json`, which is the data the organ reads.
Edit the JSON, not this page.

The cloud deep-forest pass of 2026-11-18 found no trader claims in 25 regions.
This page records, for each region, whether its official statistics office or central bank
release calendar and headline print are a lawful ground. Built routes are fetched hourly by
`desks/mt5/research/release_calendar_states.py` (leg `release_calendar_states`).

Verdicts: CONFIRMED (terms read and quoted, reuse allowed), BLOCKED_ON_TERMS (refused, or
unread: LAWS 5e act 6 counts unread terms as a refusal), HARD_STOP (a wall, challenge or
401/403/429/451, never bypassed), NO_CALENDAR (terms allow it, but no publication time can be stamped).

How the pages were read: terms and robots pages were read through a page reader from the build container (its proxy refuses these hosts to curl). The organ's live gate re-reads robots.txt on the box with the honest UA before any data request and fails closed.

| region | verdict | built | institution | calendar | terms | quoted clause | symbols | why |
|---|---|---|---|---|---|---|---|---|
| ae | BLOCKED_ON_TERMS | no | FCSC | https://fcsc.gov.ae/en-us | - | - | - | fcsc.gov.ae answered 'Page not found'; terms unread; no MT5 symbol |
| bd | BLOCKED_ON_TERMS | no | BBS | https://bbs.gov.bd/ | - | - | - | bbs.gov.bd unreachable (cloud pass 2026-11-18): terms unread; no MT5 symbol |
| ca | CONFIRMED | yes | Statistics Canada | https://www150.statcan.gc.ca/n1/dai-quo/cal2-eng.htm | https://www.statcan.gc.ca/en/terms-conditions/open-licence | Statistics Canada grants you a worldwide, royalty-free, non-exclusive licence to: use, reproduce, publish, freely distribute, or sell the Information | USDCAD | CPI all-items (v41690973, yoy computed) and LFS unemployment rate (v2062815) from the Web Data Service; every data point carries releaseTime (Ottawa local), the publisher's own publication stamp |
| co | BLOCKED_ON_TERMS | no | DANE / BanRep | https://www.dane.gov.co/ | - | - | - | no condiciones de uso or calendar link in the page text; no MT5 symbol (USDCOP absent) |
| cz | CONFIRMED | yes | CZSO (print republished by Eurostat) | https://ec.europa.eu/eurostat/news/release-calendar | https://ec.europa.eu/eurostat/about-us/policies/copyright | Eurostat has a policy of encouraging free re-use of its data, both for non-commercial and commercial purposes. ... can be reused without any payment or written licence provided that: the source is indicated as Eurostat; when re-use involves modifications to the data or text, this must be stated clearly to the end user of the information. | EURCZK, USDCZK | CONFIRMED on Eurostat's terms (geo=CZ). CZSO's own conditions page (czso.cz/csu/czso/conditions-for-the-use-of-czso-data) answered the page reader client_error twice: CZSO's direct route stays unbuilt until it is read. Eurostat's CZ row lands after CZSO's own release: a late bound |
| ea | CONFIRMED | yes | Eurostat (euro indicators) | https://ec.europa.eu/eurostat/news/release-calendar | https://ec.europa.eu/eurostat/about-us/policies/copyright | Eurostat has a policy of encouraging free re-use of its data, both for non-commercial and commercial purposes. ... can be reused without any payment or written licence provided that: the source is indicated as Eurostat; when re-use involves modifications to the data or text, this must be stated clearly to the end user of the information. | EURUSD | HICP annual rate and unemployment rate for the euro area from the dissemination API |
| eg | BLOCKED_ON_TERMS | no | CAPMAS | https://www.capmas.gov.eg/ | - | - | - | JavaScript shell only: terms unread; no MT5 symbol |
| gb | CONFIRMED | yes | Office for National Statistics | https://www.ons.gov.uk/releasecalendar | https://www.ons.gov.uk/help/termsandconditions | Most content on this website is available under the Open Government Licence (OGL). Reproduction of information is subject to the terms of the OGL ... We make most of the content on this website available through feeds for other websites and applications to use. | GBPUSD, EURGBP | CPI annual rate (D7G7/MM23) and ILO unemployment rate (MGSX/LMS) from the ONS time-series JSON; each month carries updateDate (the release day, stamped at London midnight, read 2026-11-18), published at 07:00 London under the release calendar's 7am rule |
| hu | CONFIRMED | yes | KSH / HCSO (print republished by Eurostat) | https://ec.europa.eu/eurostat/news/release-calendar | https://www.ksh.hu/copyright_eng | content on the site is licensed under CC BY 4.0 ... can be copied, reproduced and redistributed without limitations ... Any content can only be used if HCSO is indicated as a source (Source: HCSO / ksh.hu) | EURHUF, USDHUF | KSH terms CONFIRMED; the print is read from Eurostat (geo=HU) on Eurostat's CONFIRMED terms so one guarded route serves four regions; a late bound against KSH's own release |
| il | BLOCKED_ON_TERMS | no | CBS Israel | https://www.cbs.gov.il/en/Pages/Release-Calendar.aspx | - | - | USDILS, EURILS | the calendar's rules were read ('All media releases, except those for price indices, are published at 1 PM'; price indices on the 15th at 6:30 PM) but no terms or copyright page was found: terms UNREAD |
| it | CONFIRMED | yes | ISTAT (print republished by Eurostat) | https://ec.europa.eu/eurostat/news/release-calendar | https://www.istat.it/en/legal-notice/ | Unless otherwise stated, content on this website is licensed under a Creative Commons License - Attribution - 4.0 ... copy and redistribute the material in any medium or format for any purpose, even commercially. | EURUSD | ISTAT's own terms CONFIRMED (CC BY 4.0); the print is read from Eurostat (geo=IT), whose terms are CONFIRMED, because istat.it served the page reader client_error and its SDMX endpoint is rate-limited. No Italian FX or index CFD is in the registry, so the mapping is EURUSD (indirect: Italy is the third-largest euro-area print). Eurostat's IT row lands AFTER ISTAT's own release: available_time is Eurostat's, a late bound, never early |
| ke | BLOCKED_ON_TERMS | no | KNBS | https://www.knbs.or.ke/ | - | - | - | no terms or calendar link in the page text; no MT5 symbol |
| kr | BLOCKED_ON_TERMS | no | KOSTAT (now MODS) | https://mods.go.kr/menu.es?mid=a20301000000 | https://mods.go.kr/anse/ | (c) Ministry of Data and Statistics. All rights reserved. | USDKRW | kostat.go.kr redirects to mods.go.kr; no KOGL mark or reuse licence on the page, only 'All rights reserved'. BOK ECOS is KOGL 'no restriction' (alt_proxies kr_bok_card_spend) but keyed: not built |
| lk | BLOCKED_ON_TERMS | no | CBSL / DCS | https://www.cbsl.gov.lk/advance-release-calendar-2026 | https://www.cbsl.gov.lk/ | (c) Central Bank of Sri Lanka, 2018. All Rights Reserved | - | calendar exists; all rights reserved with no reuse licence; no MT5 symbol |
| mx | CONFIRMED | no | INEGI / Banco de Mexico | https://www.inegi.org.mx/app/calendario/ | https://www.inegi.org.mx/inegi/terminos.html | Puede explotar comercialmente la informacion, utilizandola como insumo para generar otros productos o servicios. / Debe otorgar los creditos correspondientes al INEGI como autor (alt_proxies TERMS_EVIDENCE mx_inegi_emec, read 2026-09-30) | USDMXN, EURMXN | terms CONFIRMED but the print's machine routes (INEGI BIE API, Banxico SIE API) need a per-user token: not built here (no logins); alt_proxies already holds the INEGI route |
| no | CONFIRMED | yes | Statistics Norway (print republished by Eurostat, EEA) | https://www.ssb.no/en/kalender | https://www.ssb.no/en/informasjon/copyright | subject to copyright under the Norwegian Licence for Open Government Data (NLOD) ... use the information commercially ... users shall attribute us as Statistics Norway | EURNOK, USDNOK | SSB terms CONFIRMED (NLOD). Read from Eurostat (geo=NO): SSB table 03013's metadata ends at 2025M12 (read 2026-11-18), i.e. the table was superseded and its successor is unread |
| nz | BLOCKED_ON_TERMS | no | Stats NZ | https://www.stats.govt.nz/release-calendar | https://www.stats.govt.nz/about-us/legal-matters/copyright/ | - | NZDUSD, AUDNZD | copyright page client_error and a JS shell on the alternate: terms UNREAD (LAWS 5e act 6) |
| pe | HARD_STOP | no | BCRP / INEI | https://www.bcrp.gob.pe/ | https://www.bcrp.gob.pe/ | - | - | bcrp.gob.pe answered an Incapsula bot challenge (_Incapsula_Resource): a wall; no MT5 symbol |
| ph | BLOCKED_ON_TERMS | no | PSA | https://psa.gov.ph/ | - | - | - | terms page not found in the page text; no MT5 symbol (USDPHP absent) |
| pk | BLOCKED_ON_TERMS | no | Pakistan Bureau of Statistics | - | https://www.pbs.gov.pk/ | Pakistan Bureau of Statistics (c) 2026. All Rights Reserved | - | all rights reserved, no reuse licence, no advance release calendar found; no MT5 symbol |
| sa | CONFIRMED | no | GASTAT | https://www.stats.gov.sa/statistical-calendar-releases | https://www.stats.gov.sa/en/use-policy | 1.2.2 including commercial use in accordance with the Open Data principle ... provided that GASTAT is acknowledged as the official source and any modifications are clearly indicated | - | no MT5 symbol: USDSAR is not in the universe registry (the riyal is pegged) |
| sg | NO_CALENDAR | no | SingStat | https://www.singstat.gov.sg/data-tools-services/advance-release-calendar | https://data.gov.sg/open-data-licence | You can use, access, download, copy, distribute, transmit, modify and adapt the datasets ... whether commercially or non-commercially (alt_proxies TERMS_EVIDENCE sg_port_throughput, read 2026-09-30) | USDSGD | terms CONFIRMED (Singapore Open Data Licence) but the advance release calendar lists bare dates (e.g. '30-11-2027') with no release name or time in its text and no ics/csv/json export (read 2026-11-18): no publication time can be stamped |
| ua | BLOCKED_ON_TERMS | no | Ukrstat / NBU | https://www.ukrstat.gov.ua/ | - | - | - | ukrstat.gov.ua robots refused the page reader; bank.gov.ua carries no terms link; no MT5 symbol |
| us | CONFIRMED | no | BLS / BEA / Census | https://www.bls.gov/schedule/news_release/ | https://www.law.cornell.edu/uscode/text/17/105 | 17 U.S.C. 105(a): 'Copyright protection under this title is not available for any work of the United States Government' | US500, USDX | covered elsewhere: libs/data/keyed_sources.py (BLS) and the EIA/USDA/TIC organs; not duplicated |
| za | HARD_STOP | no | Stats SA / SARB | https://www.statssa.gov.za/?page_id=1847 | https://www.statssa.gov.za/ | - | USDZAR | statssa.gov.za serves an Incapsula challenge (a wall: hard stop, never bypassed); its notice was read only on a third-party mirror (alt_proxies za_statssa_retail, to_confirm); 2026-11-18 the page reader got client_error |

Counts: BLOCKED_ON_TERMS 12, CONFIRMED 10, HARD_STOP 2, NO_CALENDAR 1.
Built: ca, cz, ea, gb, hu, it, no.

## What is not fixed

- **nz, il, kr, sg and za have MT5 symbols but no route.** nz's terms are unread (its copyright page
  only loads with JavaScript). il has no terms page that could be found. kr's KOSTAT/MODS page says
  "All rights reserved", and BOK ECOS needs a key. sg's calendar has no times. za has an Incapsula wall.
- **mx is CONFIRMED but keyed.** The INEGI BIE and Banxico SIE APIs need a per-user token.
- **cz, it, hu and no are read from Eurostat, which republishes after the national office.**
  available_time is Eurostat's, so it can only be late, never early. The national routes stay
  unbuilt: CZSO's conditions page was unreadable, and SSB table 03013 ends at 2025M12.
- **Cells wait for live history.** Backfill is never judged, so a monthly series needs 12
  scaled live releases before any `alt_release_drift` cell is minted. The event clock
  (`reports/RELEASE_CALENDAR_CLOCK.json`, read by `event_response_atlas`) gets each live print
  as soon as it lands.
- **Robots for ons.gov.uk and www150.statcan.gc.ca could not be read from the build container.**
  The live gate reads them on the box before the first data request, and refuses if it cannot.
- **The response shapes are only partly verified.** Eurostat JSON-stat and the ONS months[] rows were
  read live. The StatCan WDS shape comes from its documentation, because its robots refused the reader.
  A shape mismatch reads UNPARSEABLE or METADATA_MISMATCH by name. It is never guessed.
