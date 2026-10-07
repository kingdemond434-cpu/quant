"""TERMS ROWS FOR EVERY RAW-PACK HOST (asia_sources.json), so only a quoted clause mints.

#229 made the pack_cells raw-pack lane mint on `confirmed` terms only (2026-10-07): `ungoverned`
-- a URL on a host no terms row governs -- carries no quoted clause, so it mints nothing. On that
day 224 of the registry's 242 packs were ungoverned, behind 193 distinct hosts. This table gives
each of those hosts a row, keyed by the registrable host suffix the gate matches
(`alt_proxies._terms_id`: host == key or host ends with "." + key).

THIS IS NOT A SECOND TERMS TABLE. `alt_proxies` merges every row here into its own
GATE_TERMS / GATE_TERMS_EVIDENCE / TERMS_HOSTS (and ATTRIBUTION for a confirmed row that names a
credit) at import, under the id `pack_host:<key>`, and refuses a key that is already governed.
A row of the form {"adopt": <terms id>} maps the host to a decision the desk ALREADY holds (an
alt_proxies source on the same host, or a gate row for the same owner), so one host never has
two decisions.

VERDICTS (fail closed):
  confirmed    a VERBATIM clause that permits our use (reuse incl. commercial or own-account
               analysis: public domain, CC BY, OGL, PDL, "may be used for any purpose" ...).
  refused      a clause that prohibits commercial or automated use. Its packs mint nothing.
  to_confirm   ambiguous, or no clause could be read. `fetch_status: FETCH_BLOCKED` marks a page
               this container could not fetch (robots refusal, 403, timeout, certificate, a
               JavaScript shell, a WAF); its `box_action` names what to read on the box.

HOW THE QUOTES WERE READ. Every page was fetched on 2026-10-07 with the authoring fetcher, which
returns extracted text; quotes are verbatim fragments of the page as returned (long clauses are
cut with "..."), never paraphrase. A `judgement` is the reviewer's reading and is not a quote.
Hosts in /mnt/project-files/terms/global_data_clearances_2026-10-07.json (the Global data
thread's file) were checked first: none of its rows (prediction-market venues, calendars) is a
pack host, so no verdict here adopts or contradicts it.

Re-read a row's page before relying on its exact wording; a row changes only on a new reading.
"""
# ruff: noqa: RUF001, E501  (a data table: verbatim quotes and URLs are not split)
from __future__ import annotations

CHECKED_AT = "2026-10-07"

PACK_HOST_TERMS: dict[str, dict[str, str]] = {'abs.gov.au': {'attribution': 'Source: Australian Bureau of Statistics, CC BY 4.0',
                'checked_at': '2026-10-07',
                'judgement': 'CONFIRMED: CC BY 4.0 permits commercial reuse with attribution',
                'terms_quote': 'All material presented on this website is provided under a '
                               'Creative Commons Attribution 4.0 International licence',
                'terms_url': 'https://www.abs.gov.au/website-privacy-copyright-and-disclaimer',
                'verdict': 'confirmed'},
 'adnoc.ae': {'also_quote': 'Except solely for your own personal and non-commercial use and '
                            'provided you keep intact all and any copyright and proprietary '
                            'notices',
              'checked_at': '2026-10-07',
              'judgement': 'REFUSED: only personal, non-commercial use is excepted from the '
                           'written-permission bar',
              'terms_quote': 'no part of the DIGITAL PLATFORM may be copied, adapted, modified, '
                             'distributed, transmitted, displayed, performed, reproduced or '
                             'published without the prior written permission of ADNOC',
              'terms_url': 'https://www.adnoc.ae/en/terms-and-conditions',
              'verdict': 'refused'},
 'aemo.com.au': {'attribution': 'Source: Australian Energy Market Operator (AEMO)',
                 'checked_at': '2026-10-07',
                 'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                              "the desk's own-account analysis",
                 'terms_quote': 'AEMO confirms its general permission for anyone to use AEMO '
                                'Material for any purpose, but only with accurate and appropriate '
                                'attribution',
                 'terms_url': 'https://www.aemo.com.au/privacy-and-legal-notices/copyright-permissions',
                 'verdict': 'confirmed'},
 'agriculture.gov.au': {'box_action': 'Read '
                                      'https://www.agriculture.gov.au/about/commitment/copyright '
                                      'on the box and quote the licence clause covering ABARES '
                                      'data',
                        'checked_at': '2026-10-07',
                        'fetch_status': 'FETCH_BLOCKED',
                        'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt unreadable to the '
                                     'authoring fetcher',
                        'terms_quote': '',
                        'terms_url': 'https://www.agriculture.gov.au/about/commitment/copyright',
                        'verdict': 'to_confirm'},
 'aramco.com': {'box_action': 'Read the terms of use / copyright page of https://www.aramco.com/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                             '(legal-notices URL 404 to the fetcher); the box action names where '
                             'to read it',
                'terms_quote': '',
                'terms_url': 'https://www.aramco.com/',
                'verdict': 'to_confirm'},
 'asx.com.au': {'box_action': 'Read the terms of use / copyright page of https://www.asx.com.au/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                             '(terms URL 404 to the fetcher); the box action names where to read '
                             'it',
                'terms_quote': '',
                'terms_url': 'https://www.asx.com.au/',
                'verdict': 'to_confirm'},
 'b3.com.br': {'box_action': "Read B3's website terms of use on the box and quote the market-data "
                             'clause',
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): read timeout to the fetcher; the '
                            'market-data page has no terms text',
               'terms_quote': '',
               'terms_url': 'https://www.b3.com.br/en_us/terms-of-use/',
               'verdict': 'to_confirm'},
 'baidu.com': {'adopt': 'cn_baidu_migration'},
 'bakerhughes.com': {'checked_at': '2026-10-07',
                     'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on '
                                  'the page read',
                     'terms_quote': '',
                     'terms_url': 'https://rigcount.bakerhughes.com/',
                     'verdict': 'to_confirm'},
 'balanca.economia.gov.br': {'box_action': 'Read the Comex Stat / balanca.economia.gov.br terms '
                                           '(gov.br sites usually state a CC licence in the '
                                           'footer) on the box and quote it',
                             'checked_at': '2026-10-07',
                             'fetch_status': 'FETCH_BLOCKED',
                             'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt fetch failed on '
                                          "the host's certificate chain",
                             'terms_quote': '',
                             'terms_url': 'https://balanca.economia.gov.br/',
                             'verdict': 'to_confirm'},
 'balticexchange.com': {'box_action': 'Read the terms of use / copyright page of '
                                      'https://www.balticexchange.com/ on the box and quote the '
                                      'clause governing reuse of its data',
                        'checked_at': '2026-10-07',
                        'judgement': 'TO_CONFIRM: no terms page could be located from this '
                                     'container (terms URL 404 to the fetcher (Baltic indices are '
                                     'licensed products)); the box action names where to read it',
                        'terms_quote': '',
                        'terms_url': 'https://www.balticexchange.com/',
                        'verdict': 'to_confirm'},
 'bankofcanada.ca': {'also_quote': 'If You provide content from this website through paid '
                                   'services or incorporate any content in documents for sale '
                                   '(regardless of the medium), You must inform any prospective '
                                   'purchaser, prior to its distribution or sale, that said '
                                   'content was obtained from this website and that such '
                                   'information is available on this website free of charge.',
                     'attribution': 'Source: Bank of Canada',
                     'checked_at': '2026-10-07',
                     'judgement': 'CONFIRMED: the quoted clause permits use of the data, '
                                  "including the desk's own-account analysis",
                     'terms_quote': 'the Bank permits you to freely use, copy, distribute and '
                                    'transmit its website content',
                     'terms_url': 'https://www.bankofcanada.ca/terms/',
                     'verdict': 'confirmed'},
 'bankofengland.co.uk': {'also_quote': 'selected exchange rate data and series are excluded from '
                                       'this licence as they are reproduced by the Bank under '
                                       'licence from third parties.',
                         'checked_at': '2026-10-07',
                         'judgement': 'TO_CONFIRM: the Database is OGL but selected exchange-rate '
                                      "series are excluded (third-party licence) and the site's "
                                      "general grant is 'personal use or internal use within an "
                                      "individual organisation for non-commercial purposes'; the "
                                      "pack's series must be checked against the exclusion list",
                         'terms_quote': 'Reproduction of data in the Database is subject to the '
                                        'terms of the UK Open Government Licence, allowing and '
                                        'encouraging free and flexible data reuse.',
                         'terms_url': 'https://www.bankofengland.co.uk/legal',
                         'verdict': 'to_confirm'},
 'banrep.gov.co': {'checked_at': '2026-10-07',
                   'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
                   'terms_quote': 'Any use, transformation, or exploitation of the contents '
                                  'included in the website for commercial or advertising purposes '
                                  'is prohibited unless prior authorization has been obtained '
                                  'from Banco de la República.',
                   'terms_url': 'https://www.banrep.gov.co/en/legal-notice',
                   'verdict': 'refused'},
 'banxico.org.mx': {'box_action': 'Read the SIE API terms of use '
                                  '(https://www.banxico.org.mx/SieAPIRest/service/v1/doc/terminos?) '
                                  'on the box and quote the reuse clause',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the SIE API root returned an empty '
                                 'JSON body',
                    'terms_quote': '',
                    'terms_url': 'https://www.banxico.org.mx/SieAPIRest/service/v1/',
                    'verdict': 'to_confirm'},
 'bcb.gov.br': {'adopt': 'br_bcb_payments'},
 'bcentral.cl': {'box_action': 'Read the Banco Central de Chile legal notice / BDE terms on the '
                               'box and quote the reuse clause',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): si3.bcentral.cl answered a 404 page; '
                              'the legal-notice URL 404',
                 'terms_quote': '',
                 'terms_url': 'https://si3.bcentral.cl/',
                 'verdict': 'to_confirm'},
 'bcrp.gob.pe': {'also_quote': 'La responsabilidad sobre las estadísticas cuya fuente es externa '
                               'al Banco recae en la entidad que provee el dato original.',
                 'attribution': 'Fuente: Banco Central de Reserva del Perú',
                 'checked_at': '2026-10-07',
                 'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                              "the desk's own-account analysis",
                 'terms_quote': 'Puede reproducirse total o parcialmente, sin autorización '
                                'expresa, siempre y cuando se cite la fuente.',
                 'terms_url': 'https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/condiciones-de-uso',
                 'verdict': 'confirmed'},
 'bi.go.id': {'box_action': 'Read the terms of use / copyright page of https://www.bi.go.id/ on '
                            'the box and quote the clause governing reuse of its data',
              'checked_at': '2026-10-07',
              'fetch_status': 'FETCH_BLOCKED',
              'judgement': "TO_CONFIRM (FETCH_BLOCKED): disclaimer URL 404; only '© 2020 Bank "
                           "Indonesia' read",
              'terms_quote': '',
              'terms_url': 'https://www.bi.go.id/',
              'verdict': 'to_confirm'},
 'bis.org': {'also_quote': 'if the statistics are reproduced, the BIS must be cited in your '
                           'publication or product as the source',
             'attribution': 'Source: Bank for International Settlements',
             'checked_at': '2026-10-07',
             'judgement': 'CONFIRMED: the quoted clause permits use of the data, including the '
                          "desk's own-account analysis",
             'terms_quote': 'The use of the statistics is unrestricted, provided that',
             'terms_url': 'https://data.bis.org/help/legal',
             'verdict': 'confirmed'},
 'bls.gov': {'attribution': 'Source: U.S. Bureau of Labor Statistics',
             'checked_at': '2026-10-07',
             'judgement': 'CONFIRMED: the quoted clause permits use of the data, including the '
                          "desk's own-account analysis",
             'terms_quote': 'You are free to use our public domain material without specific '
                            'permission, although we do ask that you cite the Bureau of Labor '
                            'Statistics as the source.',
             'terms_url': 'https://www.bls.gov/opub/copyright-information.htm',
             'verdict': 'confirmed'},
 'bnm.gov.my': {'box_action': 'Read the terms of use / copyright page of https://api.bnm.gov.my/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): API portal root 404 to the fetcher',
                'terms_quote': '',
                'terms_url': 'https://api.bnm.gov.my/',
                'verdict': 'to_confirm'},
 'bog.gov.gh': {'checked_at': '2026-10-07',
                'judgement': "TO_CONFIRM: footer reads '© 2026 Bank of Ghana. All rights "
                             "reserved.' and links /legal/ and /disclaimer/, whose text was not "
                             'read',
                'terms_quote': '',
                'terms_url': 'https://www.bog.gov.gh/legal/',
                'verdict': 'to_confirm'},
 'boi.org.il': {'checked_at': '2026-10-07',
                'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
                'terms_quote': 'The user may not copy, publish, disseminate, transmit or sell any '
                               'information made available this site, without the prior written '
                               'consent of the BOI.',
                'terms_url': 'https://www.boi.org.il/en/terms-of-use/',
                'verdict': 'refused'},
 'boj.or.jp': {'also_quote': 'When copying or reproducing, the source, the Bank of Japan, should '
                             'be explicitly credited.',
               'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: the page restricts copying or reproduction for '
                            'commercial purposes (permission from the Public Relations '
                            'Department, post.prd8@boj.or.jp); the clause governs reproduction '
                            'and grants nothing explicit for own-account analysis. '
                            'stat-search.boj.or.jp has its own notice page '
                            '(https://www.stat-search.boj.or.jp/info/notice.html), not read',
               'terms_quote': 'The information included in the site may be copied or reproduced',
               'terms_url': 'https://www.boj.or.jp/en/about/copyright.htm',
               'verdict': 'to_confirm'},
 'bok.or.kr': {'adopt': 'kr_bok_card_spend'},
 'borsaistanbul.com': {'adopt': 'tr_borsa_gold'},
 'bot.go.tz': {'box_action': 'Read the terms of use / copyright page of '
                             'https://www.bot.go.tz/Publications/ on the box and quote the clause '
                             'governing reuse of its data',
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 403 to the fetcher',
               'terms_quote': '',
               'terms_url': 'https://www.bot.go.tz/Publications/',
               'verdict': 'to_confirm'},
 'bot.or.th': {'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: the API portal page carries migration notices only; no '
                            'reuse, licence or copyright clause was found on the page read',
               'terms_quote': '',
               'terms_url': 'https://apiportal.bot.or.th/',
               'verdict': 'to_confirm'},
 'boz.zm': {'box_action': 'Read the terms of use / copyright page of '
                          'https://www.boz.zm/statistics.htm on the box and quote the clause '
                          'governing reuse of its data',
            'checked_at': '2026-10-07',
            'fetch_status': 'FETCH_BLOCKED',
            'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the page served only a loading shell to the '
                         'fetcher',
            'terms_quote': '',
            'terms_url': 'https://www.boz.zm/statistics.htm',
            'verdict': 'to_confirm'},
 'bsp.gov.ph': {'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                             'page read; no terms link in the page text',
                'terms_quote': '',
                'terms_url': 'https://www.bsp.gov.ph/',
                'verdict': 'to_confirm'},
 'cbe.org.eg': {'box_action': 'Read the terms of use / copyright page of https://www.cbe.org.eg/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the site served an error page (support '
                             'ID) to the fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.cbe.org.eg/',
                'verdict': 'to_confirm'},
 'cbk.gov.kw': {'box_action': 'Read the terms of use / copyright page of https://www.cbk.gov.kw/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): statistics page 404 to the fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.cbk.gov.kw/',
                'verdict': 'to_confirm'},
 'cbn.gov.ng': {'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                             'page read',
                'terms_quote': '',
                'terms_url': 'https://www.cbn.gov.ng/rates/',
                'verdict': 'to_confirm'},
 'cbr.ru': {'also_quote': 'The said information cannot be used for commercial purposes either.',
            'checked_at': '2026-10-07',
            'judgement': 'TO_CONFIRM: copying with a source link is allowed, but the page also '
                         "says 'The said information cannot be used for commercial purposes "
                         "either.' and which information that sentence binds was not resolvable "
                         'from the text read; the User Agreement '
                         '(https://www.cbr.ru/eng/user_agreement/) was not read',
            'terms_quote': 'Copying of information available at http://www.cbr.ru/ (as well as '
                           'citing in mass media of any data or information from the information '
                           "sections of the Bank of Russia's website) is allowed provided that "
                           'the link to the source of this information is indicated',
            'terms_url': 'https://www.cbr.ru/eng/about/',
            'verdict': 'to_confirm'},
 'ccgp.gov.cn': {'checked_at': '2026-10-07',
                 'judgement': "TO_CONFIRM: footer reads '© 1999-2025 中华人民共和国财政部 版权所有'; no "
                              'statement page and no reuse grant',
                 'terms_quote': '',
                 'terms_url': 'https://www.ccgp.gov.cn/',
                 'verdict': 'to_confirm'},
 'cecafe.com.br': {'checked_at': '2026-10-07',
                   'judgement': 'TO_CONFIRM: no terms text or link',
                   'terms_quote': '',
                   'terms_url': 'https://www.cecafe.com.br/en/',
                   'verdict': 'to_confirm'},
 'centralbank.ae': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://www.centralbank.ae/ on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                                 '(terms URL 404 to the fetcher); the box action names where to '
                                 'read it',
                    'terms_quote': '',
                    'terms_url': 'https://www.centralbank.ae/',
                    'verdict': 'to_confirm'},
 'centralbank.go.ke': {'checked_at': '2026-10-07',
                       'judgement': "TO_CONFIRM: only '© 2017 Central Bank of Kenya' read; no "
                                    'reuse, licence or copyright clause was found on the page '
                                    'read',
                       'terms_quote': '',
                       'terms_url': 'https://www.centralbank.go.ke/statistics/',
                       'verdict': 'to_confirm'},
 'cffex.com.cn': {'checked_at': '2026-10-07',
                  'judgement': "TO_CONFIRM: footer reads only '中国金融期货交易所2011 © 版权所有'; no reuse "
                               'grant and no statement page found',
                  'terms_quote': '',
                  'terms_url': 'http://www.cffex.com.cn/',
                  'verdict': 'to_confirm'},
 'cftc.gov': {'attribution': 'Source: U.S. Commodity Futures Trading Commission',
              'checked_at': '2026-10-07',
              'judgement': 'CONFIRMED: the quoted clause permits use of the data, including the '
                           "desk's own-account analysis",
              'terms_quote': 'Government information at the CFTC website is in the public domain. '
                             'Public domain information may be freely distributed and copied, but '
                             'it is requested that in any subsequent use the CFTC be given '
                             'appropriate acknowledgement.',
              'terms_url': 'https://www.cftc.gov/WebPolicy/index.htm',
              'verdict': 'confirmed'},
 'chinabond.com.cn': {'checked_at': '2026-10-07',
                      'judgement': 'TO_CONFIRM: product development or benchmark use needs a '
                                   'written application; no grant for own-account analysis was '
                                   'read',
                      'terms_quote': 'Any Institution or Individual who intends to use ChinaBond '
                                     'Pricing Data Products to develop products, or use index '
                                     'data as benchmark...shall apply to ChinaBond Pricing Center '
                                     'Co., Ltd. separately in writing.',
                      'terms_url': 'https://yield.chinabond.com.cn/',
                      'verdict': 'to_confirm'},
 'cmegroup.com': {'box_action': 'Read the CME Group Terms of Use (footer of '
                                'https://www.cmegroup.com/) on the box and quote the market-data '
                                'clause',
                  'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                               '(the terms URL returned 404 to the authoring fetcher); the box '
                               'action names where to read it',
                  'terms_quote': '',
                  'terms_url': 'https://www.cmegroup.com/terms-of-use.html',
                  'verdict': 'to_confirm'},
 'cochilco.cl': {'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: footer links privacy and transparency pages only; no '
                              'reuse clause',
                 'terms_quote': '',
                 'terms_url': 'https://www.cochilco.cl/',
                 'verdict': 'to_confirm'},
 'cocobod.gh': {'checked_at': '2026-10-07',
                'judgement': "TO_CONFIRM: footer reads '©2026 COCOBOD. All rights reserved' and "
                             'links terms-conditions, whose text was not read',
                'terms_quote': '',
                'terms_url': 'https://cocobod.gh/pages/terms-conditions',
                'verdict': 'to_confirm'},
 'collective2.com': {'box_action': 'Read the terms of use / copyright page of '
                                   'https://www.collective2.com/ on the box and quote the clause '
                                   'governing reuse of its data',
                     'checked_at': '2026-10-07',
                     'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                                  '(terms URL 404 to the fetcher); the box action names where to '
                                  'read it',
                     'terms_quote': '',
                     'terms_url': 'https://www.collective2.com/',
                     'verdict': 'to_confirm'},
 'conab.gov.br': {'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: CC BY-ND 3.0 permits commercial copying with '
                               'attribution but no derivatives; derived signals are adaptations '
                               '(kept internal, never redistributed) -- whether ND reaches '
                               "internal derivation is a principal's reading",
                  'terms_quote': 'Todo o conteúdo deste site está publicado sob a licença '
                                 'Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada',
                  'terms_url': 'https://www.gov.br/conab/pt-br',
                  'verdict': 'to_confirm'},
 'conseilcafecacao.ci': {'box_action': 'Read the terms of use / copyright page of '
                                       'https://www.conseilcafecacao.ci/ on the box and quote the '
                                       'clause governing reuse of its data',
                         'checked_at': '2026-10-07',
                         'fetch_status': 'FETCH_BLOCKED',
                         'judgement': 'TO_CONFIRM (FETCH_BLOCKED): certificate chain unverifiable '
                                      'to the fetcher',
                         'terms_quote': '',
                         'terms_url': 'https://www.conseilcafecacao.ci/',
                         'verdict': 'to_confirm'},
 'copernicus.eu': {'attribution': 'Contains modified Copernicus Sentinel data [year]',
                   'checked_at': '2026-10-07',
                   'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                                "the desk's own-account analysis",
                   'terms_quote': 'EU law grants free access to Copernicus Sentinel Data and '
                                  'Service Information for the purpose of the following use in so '
                                  'far as it is lawful: (a) reproduction; (b) distribution; (c) '
                                  'communication to the public; (d) adaptation, modification and '
                                  'combination with other data and information; (e) any '
                                  'combination of points (a) to (d).',
                   'terms_url': 'https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice',
                   'verdict': 'confirmed'},
 'customs.go.jp': {'also_quote': 'PDL1.0 '
                                 '(https://www.digital.go.jp/resources/open_data/public_data_license_v1.0): '
                                 '商用利用も可能です。 / 本コンテンツを利用する際は出典を記載してください。',
                   'attribution': 'Source: Japan Customs, Trade Statistics (PDL1.0)',
                   'checked_at': '2026-10-07',
                   'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                                "the desk's own-account analysis",
                   'terms_quote': 'Public Data License (Version 1.0:PDL1.0) applies unless any '
                                  'rights are indicated.',
                   'terms_url': 'https://www.customs.go.jp/copyright_e.htm',
                   'verdict': 'confirmed'},
 'customs.go.kr': {'box_action': 'Read the terms of use / copyright page of '
                                 'https://www.customs.go.kr/english/main.do on the box and quote '
                                 'the clause governing reuse of its data',
                   'checked_at': '2026-10-07',
                   'fetch_status': 'FETCH_BLOCKED',
                   'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt connect timeout (also '
                                'governs unipass.customs.go.kr)',
                   'terms_quote': '',
                   'terms_url': 'https://www.customs.go.kr/english/main.do',
                   'verdict': 'to_confirm'},
 'customs.gov.ru': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://customs.gov.ru/statistic on the box and quote the '
                                  'clause governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt connect timeout',
                    'terms_quote': '',
                    'terms_url': 'https://customs.gov.ru/statistic',
                    'verdict': 'to_confirm'},
 'customs.gov.vn': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://www.customs.gov.vn/ on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the page is a JavaScript shell to '
                                 'the fetcher',
                    'terms_quote': '',
                    'terms_url': 'https://www.customs.gov.vn/',
                    'verdict': 'to_confirm'},
 'czce.com.cn': {'box_action': 'Read the terms of use / copyright page of http://www.czce.com.cn/ '
                               'on the box and quote the clause governing reuse of its data',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the footer links 法律声明 but its page '
                              'answered 412 to the fetcher',
                 'terms_quote': '',
                 'terms_url': 'http://www.czce.com.cn/',
                 'verdict': 'to_confirm'},
 'darwinex.com': {'box_action': 'Read the terms of use / copyright page of '
                                'https://www.darwinex.com/legal/terms-and-conditions on the box '
                                'and quote the clause governing reuse of its data',
                  'checked_at': '2026-10-07',
                  'fetch_status': 'FETCH_BLOCKED',
                  'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt disallows the fetcher',
                  'terms_quote': '',
                  'terms_url': 'https://www.darwinex.com/legal/terms-and-conditions',
                  'verdict': 'to_confirm'},
 'dce.com.cn': {'box_action': 'Read the terms of use / copyright page of http://www.dce.com.cn/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt connect timeout',
                'terms_quote': '',
                'terms_url': 'http://www.dce.com.cn/',
                'verdict': 'to_confirm'},
 'destatis.de': {'box_action': 'Read https://www.govdata.de/dl-de/by-2-0 on the box and quote its '
                               'commercial-use grant; then this row may read confirmed',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the GENESIS content is under Data '
                              'licence Germany - attribution - 2.0, but the licence text '
                              '(govdata.de/dl-de/by-2-0) is robots-disallowed to the authoring '
                              'fetcher, so its grant was not read',
                 'terms_quote': '© Statistisches Bundesamt (Destatis), 2026 Data licence Germany '
                                '- attribution - version 2.0',
                 'terms_url': 'https://www.destatis.de/EN/Service/Legal-Notice/_node.html',
                 'verdict': 'to_confirm'},
 'dgciskol.gov.in': {'box_action': 'Read the terms of use / copyright page of '
                                   'https://ftddp.dgciskol.gov.in/ on the box and quote the '
                                   'clause governing reuse of its data',
                     'checked_at': '2026-10-07',
                     'fetch_status': 'FETCH_BLOCKED',
                     'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 404 to the fetcher',
                     'terms_quote': '',
                     'terms_url': 'https://ftddp.dgciskol.gov.in/',
                     'verdict': 'to_confirm'},
 'dgcx.ae': {'box_action': 'Read the terms of use / copyright page of '
                           'https://www.dgcx.ae/market-data on the box and quote the clause '
                           'governing reuse of its data',
             'checked_at': '2026-10-07',
             'fetch_status': 'FETCH_BLOCKED',
             'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 403 to the fetcher',
             'terms_quote': '',
             'terms_url': 'https://www.dgcx.ae/market-data',
             'verdict': 'to_confirm'},
 'e-stat.go.jp': {'also_quote': 'The user must cite the source when using the Content.',
                  'attribution': 'Source: e-Stat (Portal Site of Official Statistics of Japan)',
                  'checked_at': '2026-10-07',
                  'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                               "the desk's own-account analysis",
                  'terms_quote': 'Commercial use of Content is also permitted.',
                  'terms_url': 'https://www.e-stat.go.jp/en/terms-of-use',
                  'verdict': 'confirmed'},
 'eaindustry.nic.in': {'checked_at': '2026-10-07',
                       'judgement': 'TO_CONFIRM: a Disclaimer link exists but its text was not '
                                    'read; no reuse, licence or copyright clause was found on the '
                                    'page read',
                       'terms_quote': '',
                       'terms_url': 'https://eaindustry.nic.in/',
                       'verdict': 'to_confirm'},
 'eatta.co.ke': {'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                              'page read',
                 'terms_quote': '',
                 'terms_url': 'https://eatta.co.ke/',
                 'verdict': 'to_confirm'},
 'ec.europa.eu': {'also_quote': 'The following Eurostat data and documents may not be reused for '
                                'commercial purposes (but non-commercial reuse is possible '
                                'without restriction) ... Trade data originating from '
                                'Liechtenstein and Switzerland (as declaring countries), from '
                                '1995 onwards ... Trade data originating from Austria (as a '
                                'declaring country) for a level of detail of the Combined '
                                'Nomenclature of 8 digits',
                  'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: the pack is international trade in goods (Comext), '
                               'and Comext trade data from CH/LI and 8-digit AT are excluded from '
                               "commercial reuse; confirm once the pack's extract is limited to "
                               'non-excluded declarants',
                  'terms_quote': 'All statistical data, metadata, content of web pages or other '
                                 'dissemination tools, official publications and other documents '
                                 'published on its website, with the exceptions listed below, can '
                                 'be reused without any payment or written licence',
                  'terms_url': 'https://ec.europa.eu/eurostat/about-us/policies/copyright',
                  'verdict': 'to_confirm'},
 'ecb.europa.eu': {'also_quote': 'When such information is distributed or reproduced, it must '
                                 'appear accurately and the ECB must be cited as the source.',
                   'attribution': 'Source: European Central Bank',
                   'checked_at': '2026-10-07',
                   'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                                "the desk's own-account analysis",
                   'terms_quote': 'users of this website may make free use of the information '
                                  'obtained directly from it subject to the following conditions:',
                   'terms_url': 'https://www.ecb.europa.eu/services/disclaimer/html/index.en.html',
                   'verdict': 'confirmed'},
 'eia.gov': {'attribution': 'Source: U.S. Energy Information Administration (<publication date>)',
             'checked_at': '2026-10-07',
             'judgement': 'CONFIRMED: the quoted clause permits use of the data, including the '
                          "desk's own-account analysis",
             'terms_quote': 'You may use and/or distribute any of our data, files, databases, '
                            'reports, graphs, charts, and other information products that are on '
                            'our website or that you receive through our email distribution '
                            'service.',
             'terms_url': 'https://www.eia.gov/about/copyrights_reuse.php',
             'verdict': 'confirmed'},
 'entsog.eu': {'box_action': 'Read the ENTSOG Transparency Platform terms/legal notice in a '
                             'browser on the box and quote the reuse clause',
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the transparency platform is a '
                            'JavaScript app (no text to the fetcher); legal-notice URL 404',
               'terms_quote': '',
               'terms_url': 'https://transparency.entsog.eu/',
               'verdict': 'to_confirm'},
 'eosdis.nasa.gov': {'adopt': 'cn_firms_industrial'},
 'esdm.go.id': {'checked_at': '2026-10-07',
                'judgement': "TO_CONFIRM: only 'Copy Right © 2026 The Ministry of Energy and "
                             "Mineral Resources' read; no terms page",
                'terms_quote': '',
                'terms_url': 'https://www.esdm.go.id/en/',
                'verdict': 'to_confirm'},
 'eskom.co.za': {'checked_at': '2026-10-07',
                 'judgement': "TO_CONFIRM: footer reads '© 2026 Eskom Holdings SOC Ltd ... All "
                              "rights reserved'; the terms of use were not read",
                 'terms_quote': '',
                 'terms_url': 'https://www.eskom.co.za/dataportal/',
                 'verdict': 'to_confirm'},
 'ezv.admin.ch': {'box_action': 'Read the terms of use / copyright page of '
                                'https://www.gate.ezv.admin.ch/swissimpex/ on the box and quote '
                                'the clause governing reuse of its data',
                  'checked_at': '2026-10-07',
                  'fetch_status': 'FETCH_BLOCKED',
                  'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt disallows the fetcher',
                  'terms_quote': '',
                  'terms_url': 'https://www.gate.ezv.admin.ch/swissimpex/',
                  'verdict': 'to_confirm'},
 'federalreserve.gov': {'checked_at': '2026-10-07',
                        'judgement': 'CONFIRMED: the quoted clause permits use of the data, '
                                     "including the desk's own-account analysis",
                        'terms_quote': "Unless otherwise indicated, information on Board's "
                                       'website is in the public domain and may be copied and '
                                       'distributed without permission.',
                        'terms_url': 'https://www.federalreserve.gov/disclaimer.htm',
                        'verdict': 'confirmed'},
 'fonterra.com': {'box_action': 'Read the terms of use / copyright page of '
                                'https://www.fonterra.com/ on the box and quote the clause '
                                'governing reuse of its data',
                  'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                               '(terms URL 404 to the fetcher); the box action names where to '
                               'read it',
                  'terms_quote': '',
                  'terms_url': 'https://www.fonterra.com/',
                  'verdict': 'to_confirm'},
 'fss.or.kr': {'box_action': 'Read the terms of use / copyright page of '
                             'https://www.fss.or.kr/fss/eng/main/main.do on the box and quote the '
                             'clause governing reuse of its data',
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the page served an error page to the '
                            'fetcher',
               'terms_quote': '',
               'terms_url': 'https://www.fss.or.kr/fss/eng/main/main.do',
               'verdict': 'to_confirm'},
 'fusionmarkets.com': {'checked_at': '2026-10-07',
                       'judgement': "TO_CONFIRM: the broker's own disclosure documents "
                                    "(PDS/FSG/hedging policy); footer reads 'Fusion Markets 2026. "
                                    "All rights reserved.' and the linked Financial Product Terms "
                                    'PDF was not read',
                       'terms_quote': '',
                       'terms_url': 'https://fusionmarkets.com/static_images/Financial_Product_Terms_VFSC_e970634294.pdf',
                       'verdict': 'to_confirm'},
 'fusionmarkets.com.au': {'checked_at': '2026-10-07',
                          'judgement': "TO_CONFIRM: the broker's own ASIC hedging-counterparty "
                                       'policy PDF; no website terms read',
                          'terms_quote': '',
                          'terms_url': 'https://fusionmarkets.com.au/',
                          'verdict': 'to_confirm'},
 'fxblue.com': {'box_action': 'Read the terms of use / copyright page of '
                              'https://www.fxblue.com/terms on the box and quote the clause '
                              'governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt disallows the fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.fxblue.com/terms',
                'verdict': 'to_confirm'},
 'gapki.id': {'box_action': 'Read the terms of use / copyright page of https://gapki.id/en/ on '
                            'the box and quote the clause governing reuse of its data',
              'checked_at': '2026-10-07',
              'fetch_status': 'FETCH_BLOCKED',
              'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt connect timeout',
              'terms_quote': '',
              'terms_url': 'https://gapki.id/en/',
              'verdict': 'to_confirm'},
 'gazprom.com': {'checked_at': '2026-10-07',
                 'judgement': "TO_CONFIRM: only a photo-use permission ('You may use the photos "
                              "with a link to the source') was found; no data clause",
                 'terms_quote': '',
                 'terms_url': 'https://www.gazprom.com/press/',
                 'verdict': 'to_confirm'},
 'gecf.org': {'box_action': 'Read the terms of use / copyright page of https://www.gecf.org/ on '
                            'the box and quote the clause governing reuse of its data',
              'checked_at': '2026-10-07',
              'fetch_status': 'FETCH_BLOCKED',
              'judgement': 'TO_CONFIRM (FETCH_BLOCKED): report URL 404 to the fetcher',
              'terms_quote': '',
              'terms_url': 'https://www.gecf.org/',
              'verdict': 'to_confirm'},
 'gfex.com.cn': {'box_action': 'Read the terms of use / copyright page of http://www.gfex.com.cn/ '
                               'on the box and quote the clause governing reuse of its data',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): certificate hostname mismatch to the '
                              'fetcher',
                 'terms_quote': '',
                 'terms_url': 'http://www.gfex.com.cn/',
                 'verdict': 'to_confirm'},
 'gie.eu': {'box_action': 'Read https://agsi.gie.eu/data-usage on the box and quote the reuse and '
                          'source-referral rules',
            'checked_at': '2026-10-07',
            'fetch_status': 'FETCH_BLOCKED',
            'judgement': "TO_CONFIRM (FETCH_BLOCKED): the 'Data Usage - Rules & Source Referral' "
                         'page body did not render to the fetcher',
            'terms_quote': '',
            'terms_url': 'https://agsi.gie.eu/data-usage',
            'verdict': 'to_confirm'},
 'gjepc.org': {'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                            'page read',
               'terms_quote': '',
               'terms_url': 'https://gjepc.org/statistics.php',
               'verdict': 'to_confirm'},
 'globaldairytrade.info': {'box_action': 'Read the terms of use / copyright page of '
                                         'https://www.globaldairytrade.info/ on the box and quote '
                                         'the clause governing reuse of its data',
                           'checked_at': '2026-10-07',
                           'judgement': 'TO_CONFIRM: no terms page could be located from this '
                                        'container (terms URL 404 to the fetcher); the box action '
                                        'names where to read it',
                           'terms_quote': '',
                           'terms_url': 'https://www.globaldairytrade.info/',
                           'verdict': 'to_confirm'},
 'gob.pe': {'box_action': 'Read https://www.gob.pe/terminos-y-condiciones-de-uso on the box and '
                          'quote the reuse clause (MINEM pack)',
            'checked_at': '2026-10-07',
            'fetch_status': 'FETCH_BLOCKED',
            'judgement': 'TO_CONFIRM (FETCH_BLOCKED): gob.pe answered 418 to the fetcher',
            'terms_quote': '',
            'terms_url': 'https://www.gob.pe/terminos-y-condiciones-de-uso',
            'verdict': 'to_confirm'},
 'gold.org': {'checked_at': '2026-10-07',
              'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
              'terms_quote': 'you are not permitted to modify, copy, scrape, distribute, '
                             'transmit, display, reproduce, duplicate, publish, license, frame, '
                             'link, create derivative works from, transfer or otherwise use in '
                             'any manner, in whole or in part, this Website or the information '
                             'and materials on this Website without the prior written '
                             'authorisation of WGC',
              'terms_url': 'https://www.gold.org/terms-and-conditions',
              'verdict': 'refused'},
 'gpif.go.jp': {'checked_at': '2026-10-07',
                'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
                'terms_quote': 'You may not copy or reproduce all or a part of materials from '
                               'this website for the purpose of non-personal use, unless the law '
                               'permits otherwise.',
                'terms_url': 'https://www.gpif.go.jp/en/disclaimer/',
                'verdict': 'refused'},
 'hkex.com.hk': {'checked_at': '2026-10-07',
                 'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
                 'terms_quote': 'You are not permitted to conduct, facilitate, enable, authorise '
                                'or permit any text or data mining or web scraping in relation to '
                                'this Website',
                 'terms_url': 'https://www.hkex.com.hk/Global/Exchange/Terms-of-Use?sc_lang=en',
                 'verdict': 'refused'},
 'hkma.gov.hk': {'box_action': 'Read the HKMA Important Notices / API terms of use on the box and '
                               'quote the reuse clause',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the important-notices page returned an '
                              'empty body to the authoring fetcher',
                 'terms_quote': '',
                 'terms_url': 'https://www.hkma.gov.hk/eng/other-information/important-notices/',
                 'verdict': 'to_confirm'},
 'ibge.gov.br': {'checked_at': '2026-10-07',
                 'judgement': "TO_CONFIRM: no terms text or link found on SIDRA's first 100k "
                              "characters; IBGE's terms URL 404",
                 'terms_quote': '',
                 'terms_url': 'https://sidra.ibge.gov.br/',
                 'verdict': 'to_confirm'},
 'ibja.co': {'checked_at': '2026-10-07',
             'judgement': "TO_CONFIRM: the disclaimer is 'as is' liability text only; Terms and "
                          'Conditions open in a modal and were not read (the IBJA rates gate row '
                          'in_ibja_gold is to_confirm for the same association)',
             'terms_quote': '',
             'terms_url': 'https://www.ibja.co/',
             'verdict': 'to_confirm'},
 'icco.org': {'box_action': "Read ICCO's terms/copyright on the box and quote the reuse clause "
                            'for its statistics',
              'checked_at': '2026-10-07',
              'judgement': 'TO_CONFIRM: no terms page could be located from this container (the '
                           'terms URL returned 404 to the fetcher); the box action names where to '
                           'read it',
              'terms_quote': '',
              'terms_url': 'https://www.icco.org/',
              'verdict': 'to_confirm'},
 'iea.org': {'checked_at': '2026-10-07',
             'judgement': 'TO_CONFIRM: the pack is the Oil Market Report, which the terms page '
                          'lists as excluded from CC BY 4.0 (Non-CC Material); use beyond the '
                          'licence goes to Rights@iea.org',
             'terms_quote': 'all text content, reports, articles, commentaries, standalone '
                            'graphs, figures and infographics produced by and/or sourced to the '
                            'IEA...are licensed under a Creative Commons Attribution 4.0 '
                            'International (CC BY 4.0) licence',
             'terms_url': 'https://www.iea.org/terms',
             'verdict': 'to_confirm'},
 'iexindia.com': {'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on '
                               'the page read',
                  'terms_quote': '',
                  'terms_url': 'https://www.iexindia.com/',
                  'verdict': 'to_confirm'},
 'imf.org': {'also_quote': 'Users may download, extract, copy, create derivative works, publish, '
                           'distribute, and use Data obtained from IMF Sites',
             'checked_at': '2026-10-07',
             'judgement': 'TO_CONFIRM: use is granted but commercial reuse needs a request to '
                          "copyright@imf.org; whether own-account trading analysis is 'commercial "
                          "reuse' is ambiguous",
             'terms_quote': 'For any potential commercial reuse of IMF Data, email '
                            'copyright@imf.org to request permission.',
             'terms_url': 'https://www.imf.org/en/About/copyright-and-terms',
             'verdict': 'to_confirm'},
 'indec.gob.ar': {'attribution': 'Fuente: INDEC (CC BY-SA 4.0)',
                  'checked_at': '2026-10-07',
                  'judgement': 'CONFIRMED: the footer links the licence as CC BY-SA 4.0 '
                               '(https://creativecommons.org/licenses/by-sa/4.0/deed.es), which '
                               'permits commercial use with attribution (share-alike binds only '
                               'redistributed adaptations)',
                  'terms_quote': 'Todo el material publicado en el sitio web del INDEC posee la '
                                 'licencia Creative Commons (CC), salvo contenidos '
                                 'específicamente indicados.',
                  'terms_url': 'https://www.indec.gob.ar/',
                  'verdict': 'confirmed'},
 'industry.gov.au': {'box_action': 'Read the terms of use / copyright page of '
                                   'https://www.industry.gov.au/copyright on the box and quote '
                                   'the clause governing reuse of its data',
                     'checked_at': '2026-10-07',
                     'fetch_status': 'FETCH_BLOCKED',
                     'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt read timeout',
                     'terms_quote': '',
                     'terms_url': 'https://www.industry.gov.au/copyright',
                     'verdict': 'to_confirm'},
 'ine.cn': {'box_action': 'Read the terms of use / copyright page of '
                          'https://www.ine.cn/disclaimer/ on the box and quote the clause '
                          'governing reuse of its data',
            'checked_at': '2026-10-07',
            'fetch_status': 'FETCH_BLOCKED',
            'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the 版权声明 page is behind a WAF CAPTCHA for '
                         "the fetcher (INE is SHFE's subsidiary; SHFE's statement is refused)",
            'terms_quote': '',
            'terms_url': 'https://www.ine.cn/disclaimer/',
            'verdict': 'to_confirm'},
 'inegi.org.mx': {'also_quote': 'Debe otorgar los créditos correspondientes al INEGI como autor, '
                                'y cuando técnicamente sea posible, mencionar la fuente de '
                                'extracción de la información.',
                  'attribution': 'Fuente: INEGI, <nombre del producto>',
                  'checked_at': '2026-10-07',
                  'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                               "the desk's own-account analysis",
                  'terms_quote': 'Puede explotar comercialmente la información, utilizándola como '
                                 'insumo para generar otros productos o servicios.',
                  'terms_url': 'https://www.inegi.org.mx/inegi/terminos.html',
                  'verdict': 'confirmed'},
 'ins.ci': {'box_action': 'Read the terms of use / copyright page of https://www.ins.ci/ on the '
                          'box and quote the clause governing reuse of its data',
            'checked_at': '2026-10-07',
            'fetch_status': 'FETCH_BLOCKED',
            'judgement': 'TO_CONFIRM (FETCH_BLOCKED): certificate hostname mismatch to the '
                         'fetcher',
            'terms_quote': '',
            'terms_url': 'https://www.ins.ci/',
            'verdict': 'to_confirm'},
 'jodidata.org': {'box_action': "Read JODI's terms/disclaimer on the box and quote the reuse "
                                'clause',
                  'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                               '(the disclaimer URL returned 404 to the fetcher); the box action '
                               'names where to read it',
                  'terms_quote': '',
                  'terms_url': 'https://www.jodidata.org/',
                  'verdict': 'to_confirm'},
 'jpx-jquants.com': {'checked_at': '2026-10-07',
                     'judgement': 'TO_CONFIRM: the J-Quants page returned binary data to the '
                                  'authoring fetcher; its terms were not read (J-Quants is a '
                                  'keyed subscription API)',
                     'terms_quote': '',
                     'terms_url': 'https://jpx-jquants.com/',
                     'verdict': 'to_confirm'},
 'jpx.co.jp': {'checked_at': '2026-10-07',
               'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
               'terms_quote': 'The collection of data or secondary use of information from this '
                              'website for commercial purposes is strictly prohibited, unless JPX '
                              'has granted prior permission or authorized such use under a paid '
                              'contract.',
               'terms_url': 'https://www.jpx.co.jp/english/term-of-use/index.html',
               'verdict': 'refused'},
 'jsda.or.jp': {'box_action': 'Read the terms of use / copyright page of '
                              'https://www.jsda.or.jp/en/copyright/ on the box and quote the '
                              'clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the copyright page answered 429 (rate '
                             'limited) twice',
                'terms_quote': '',
                'terms_url': 'https://www.jsda.or.jp/en/copyright/',
                'verdict': 'to_confirm'},
 'jse.co.za': {'box_action': 'Read the terms of use / copyright page of https://www.jse.co.za/ on '
                             'the box and quote the clause governing reuse of its data',
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 403 to the fetcher',
               'terms_quote': '',
               'terms_url': 'https://www.jse.co.za/',
               'verdict': 'to_confirm'},
 'kase.kz': {'checked_at': '2026-10-07',
             'judgement': "TO_CONFIRM: copying needs KASE's written permission; no grant",
             'terms_quote': 'Kazakhstan Stock Exchange JSC © 1993-2026 Copying materials only '
                            'with written permission.',
             'terms_url': 'https://kase.kz/en/',
             'verdict': 'to_confirm'},
 'kdi.re.kr': {'also_quote': '공공누리 제3유형:출처표시+변경금지 조건에 따라 이용 할 수 있습니다.',
               'checked_at': '2026-10-07',
               'judgement': 'REFUSED: profit-seeking reproduction is treated as infringement, and '
                            'the KOGL type is 3 (attribution + no modification)',
               'terms_quote': '복제를 통해서 영리를 추구하는 행위를 할 경우에는 이 또한 저작권 침해로 판단할 수 있습니다.',
               'terms_url': 'https://www.kdi.re.kr/servicePolicy/copyright',
               'verdict': 'refused'},
 'kiep.go.kr': {'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                             'page read',
                'terms_quote': '',
                'terms_url': 'https://www.kiep.go.kr/eng/',
                'verdict': 'to_confirm'},
 'kita.net': {'box_action': 'Read the terms of use / copyright page of '
                            'https://kita.net/footerUtil/copyright.do on the box and quote the '
                            'clause governing reuse of its data',
              'checked_at': '2026-10-07',
              'fetch_status': 'FETCH_BLOCKED',
              'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the copyright policy page served a '
                           "queue/access-blocked notice; footer reads 'Copyright © KITA All right "
                           "reserved.'",
              'terms_quote': '',
              'terms_url': 'https://kita.net/footerUtil/copyright.do',
              'verdict': 'to_confirm'},
 'kores.net': {'box_action': 'Read the terms of use / copyright page of https://www.kores.net/ on '
                             'the box and quote the clause governing reuse of its data',
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt fetch failed (server '
                            'disconnected)',
               'terms_quote': '',
               'terms_url': 'https://www.kores.net/',
               'verdict': 'to_confirm'},
 'koshipa.or.kr': {'box_action': 'Read the terms of use / copyright page of '
                                 'https://www.koshipa.or.kr/eng/ on the box and quote the clause '
                                 'governing reuse of its data',
                   'checked_at': '2026-10-07',
                   'fetch_status': 'FETCH_BLOCKED',
                   'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt connect timeout',
                   'terms_quote': '',
                   'terms_url': 'https://www.koshipa.or.kr/eng/',
                   'verdict': 'to_confirm'},
 'kosis.kr': {'checked_at': '2026-10-07',
              'judgement': "TO_CONFIRM: the page names a 'Policy for the use of public data' menu "
                           'item but its text was not readable',
              'terms_quote': '',
              'terms_url': 'https://kosis.kr/eng/',
              'verdict': 'to_confirm'},
 'kpx.or.kr': {'checked_at': '2026-10-07',
               'judgement': "TO_CONFIRM: footer reads 'COPYRIGHT(C) 2022 KOREA POWER "
                            "EXCHANGE(KPX) ALL RIGHTS RESERVED'; no reuse grant",
               'terms_quote': '',
               'terms_url': 'https://www.kpx.or.kr/eng/',
               'verdict': 'to_confirm'},
 'krx.co.kr': {'adopt': 'kr_krx_gold'},
 'lbma.org.uk': {'box_action': 'Read the LBMA website terms (footer of https://www.lbma.org.uk/) '
                               'on the box and quote the clause covering vault-holdings data',
                 'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                              '(the terms URL returned 404 to the authoring fetcher); the box '
                              'action names where to read it',
                 'terms_quote': '',
                 'terms_url': 'https://www.lbma.org.uk/',
                 'verdict': 'to_confirm'},
 'lme.com': {'box_action': 'Read the LME website terms (footer of https://www.lme.com/) on the '
                           'box and quote the market-data clause',
             'checked_at': '2026-10-07',
             'judgement': 'TO_CONFIRM: no terms page could be located from this container (the '
                          'terms URL returned 404 to the authoring fetcher); the box action names '
                          'where to read it',
             'terms_quote': '',
             'terms_url': 'https://www.lme.com/',
             'verdict': 'to_confirm'},
 'mas.gov.sg': {'box_action': 'Read https://www.mas.gov.sg/terms-of-use on the box and quote the '
                              'reuse clause (also covers eservices.mas.gov.sg)',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 403 to the authoring fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.mas.gov.sg/terms-of-use',
                'verdict': 'to_confirm'},
 'matrade.gov.my': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://www.matrade.gov.my/ on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): statistics page 404 to the fetcher',
                    'terms_quote': '',
                    'terms_url': 'https://www.matrade.gov.my/',
                    'verdict': 'to_confirm'},
 'mcxindia.com': {'box_action': 'Read the terms of use / copyright page of '
                                'https://www.mcxindia.com/terms-of-use on the box and quote the '
                                'clause governing reuse of its data',
                  'checked_at': '2026-10-07',
                  'fetch_status': 'FETCH_BLOCKED',
                  'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt disallows the fetcher',
                  'terms_quote': '',
                  'terms_url': 'https://www.mcxindia.com/terms-of-use',
                  'verdict': 'to_confirm'},
 'meti.go.jp': {'adopt': 'jp_meti_retail'},
 'minagro.gov.ua': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://minagro.gov.ua/en on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 403 to the fetcher',
                    'terms_quote': '',
                    'terms_url': 'https://minagro.gov.ua/en',
                    'verdict': 'to_confirm'},
 'minenergo.gov.ru': {'box_action': 'Read the terms of use / copyright page of '
                                    'https://minenergo.gov.ru/ on the box and quote the clause '
                                    'governing reuse of its data',
                      'checked_at': '2026-10-07',
                      'fetch_status': 'FETCH_BLOCKED',
                      'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the page is a JavaScript shell to '
                                   'the fetcher',
                      'terms_quote': '',
                      'terms_url': 'https://minenergo.gov.ru/',
                      'verdict': 'to_confirm'},
 'mineralscouncil.org.za': {'box_action': 'Read the terms of use / copyright page of '
                                          'https://www.mineralscouncil.org.za/ on the box and '
                                          'quote the clause governing reuse of its data',
                            'checked_at': '2026-10-07',
                            'fetch_status': 'FETCH_BLOCKED',
                            'judgement': 'TO_CONFIRM (FETCH_BLOCKED): statistics URL 404 to the '
                                         'fetcher',
                            'terms_quote': '',
                            'terms_url': 'https://www.mineralscouncil.org.za/',
                            'verdict': 'to_confirm'},
 'minfin.gov.ru': {'box_action': 'Read the terms of use / copyright page of '
                                 'https://minfin.gov.ru/ on the box and quote the clause '
                                 'governing reuse of its data',
                   'checked_at': '2026-10-07',
                   'fetch_status': 'FETCH_BLOCKED',
                   'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt answered 503 to the '
                                'fetcher',
                   'terms_quote': '',
                   'terms_url': 'https://minfin.gov.ru/',
                   'verdict': 'to_confirm'},
 'moc.go.th': {'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                            'page read',
               'terms_quote': '',
               'terms_url': 'https://www.moc.go.th/en/',
               'verdict': 'to_confirm'},
 'moex.com': {'checked_at': '2026-10-07',
              'judgement': 'TO_CONFIRM: the footer links a User Agreement PDF that was not read; '
                           'the home page carries no data clause',
              'terms_quote': '',
              'terms_url': 'https://fs.moex.com/f/14214/agreement.pdf',
              'verdict': 'to_confirm'},
 'mof.go.jp': {'box_action': "Find the MOF 'Terms of Use' page (footer of "
                             'https://www.mof.go.jp/english/) on the box and quote its reuse '
                             'clause (MOF sites usually follow the government standard terms, CC '
                             'BY 4.0 compatible -- unverified here)',
               'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: no terms page could be located from this container (no '
                            'terms page found from the English home page; guessed terms URLs '
                            'returned 404); the box action names where to read it',
               'terms_quote': '',
               'terms_url': 'https://www.mof.go.jp/english/',
               'verdict': 'to_confirm'},
 'mospi.gov.in': {'box_action': 'Read the terms of use / copyright page of '
                                'https://www.mospi.gov.in/copyright-policy on the box and quote '
                                'the clause governing reuse of its data',
                  'checked_at': '2026-10-07',
                  'fetch_status': 'FETCH_BLOCKED',
                  'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the copyright page rendered no text '
                               'to the fetcher (JavaScript)',
                  'terms_quote': '',
                  'terms_url': 'https://www.mospi.gov.in/copyright-policy',
                  'verdict': 'to_confirm'},
 'mot.gov.cn': {'adopt': 'cn_mot_port_weekly'},
 'motie.go.kr': {'box_action': 'Read the terms of use / copyright page of '
                               'https://www.motie.go.kr/ on the box and quote the clause '
                               'governing reuse of its data',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt connect timeout',
                 'terms_quote': '',
                 'terms_url': 'https://www.motie.go.kr/',
                 'verdict': 'to_confirm'},
 'mpa.gov.sg': {'box_action': 'Read the MPA terms of use (footer of https://www.mpa.gov.sg/) on '
                              'the box and quote the reuse clause',
                'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no terms page could be located from this container (the '
                             'terms URL returned 404 to the authoring fetcher); the box action '
                             'names where to read it',
                'terms_quote': '',
                'terms_url': 'https://www.mpa.gov.sg/',
                'verdict': 'to_confirm'},
 'mpob.gov.my': {'checked_at': '2026-10-07',
                 'judgement': "TO_CONFIRM: footer reads '© Copyright 2017 - 2026 Malaysian Palm "
                              "Oil Board (MPOB). All Rights Reserved'; no terms page and no reuse "
                              'grant',
                 'terms_quote': '',
                 'terms_url': 'https://bepi.mpob.gov.my/',
                 'verdict': 'to_confirm'},
 'mql5.com': {'checked_at': '2026-10-07',
              'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
              'terms_quote': 'You specifically agree not to access the website www.mql5.com '
                             'through any automated means, including use of scripts, crawlers, or '
                             'similar technologies.',
              'terms_url': 'https://www.mql5.com/en/about/terms',
              'verdict': 'refused'},
 'myfxbook.com': {'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: the Terms & Conditions page as read contains no '
                               'clause on data use, API access, commercial use or automated '
                               'access; no grant',
                  'terms_quote': '',
                  'terms_url': 'https://www.myfxbook.com/terms',
                  'verdict': 'to_confirm'},
 'mysteel.net': {'checked_at': '2026-10-07',
                 'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
                 'terms_quote': 'You may not use, reproduce, modify, transfer, exploit, '
                                'distribute or dispose of any aspect of the Sites, Services '
                                'and/or Content for any commercial purpose',
                 'terms_url': 'https://www.mysteel.net/terms-conditions/',
                 'verdict': 'refused'},
 'nbg.gov.ge': {'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: the footer links a User Policy whose text was not read; '
                             'no reuse, licence or copyright clause was found on the page read',
                'terms_quote': '',
                'terms_url': 'https://nbg.gov.ge/en/user-policy',
                'verdict': 'to_confirm'},
 'newyorkfed.org': {'checked_at': '2026-10-07',
                    'judgement': 'TO_CONFIRM: the Terms of Use page body was not returned by the '
                                 'fetcher (only footer links); no clause read',
                    'terms_quote': '',
                    'terms_url': 'https://www.newyorkfed.org/termsofuse',
                    'verdict': 'to_confirm'},
 'nnpcgroup.com': {'checked_at': '2026-10-07',
                   'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on '
                                'the page read',
                   'terms_quote': '',
                   'terms_url': 'https://www.nnpcgroup.com/',
                   'verdict': 'to_confirm'},
 'norges-bank.no': {'also_quote': 'No changes may be made in the contents of the material or the '
                                  'website',
                    'checked_at': '2026-10-07',
                    'judgement': 'TO_CONFIRM: copying is permitted with attribution but the page '
                                 'says no changes may be made to the material and is silent on '
                                 'commercial use; derived signals are a change',
                    'terms_quote': 'copies – both electronic and paper-based – may be made of '
                                   'material on this website, provided that Norges Bank is quoted '
                                   'as the source',
                    'terms_url': 'https://www.norges-bank.no/en/disclaimer/',
                    'verdict': 'to_confirm'},
 'nsdl.co.in': {'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                             'page read',
                'terms_quote': '',
                'terms_url': 'https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx',
                'verdict': 'to_confirm'},
 'nseindia.com': {'box_action': 'Read the terms of use / copyright page of '
                                'https://www.nseindia.com/ on the box and quote the clause '
                                'governing reuse of its data',
                  'checked_at': '2026-10-07',
                  'fetch_status': 'FETCH_BLOCKED',
                  'judgement': 'TO_CONFIRM (FETCH_BLOCKED): terms-of-use URL 404 to the fetcher; '
                               'NSE blocks non-browser clients',
                  'terms_quote': '',
                  'terms_url': 'https://www.nseindia.com/',
                  'verdict': 'to_confirm'},
 'oecd.org': {'checked_at': '2026-10-07',
              'judgement': 'TO_CONFIRM: the terms page rendered only navigation to the authoring '
                           'fetcher; no licence clause read',
              'terms_quote': '',
              'terms_url': 'https://www.oecd.org/en/about/terms-conditions.html',
              'verdict': 'to_confirm'},
 'ons.gov.uk': {'attribution': 'Source: Office for National Statistics licensed under the Open '
                               'Government Licence v3.0',
                'checked_at': '2026-10-07',
                'judgement': 'CONFIRMED: OGL v3.0 permits commercial and non-commercial reuse '
                             'with attribution; third-party photographs/illustrations excluded '
                             '(not data)',
                'terms_quote': 'Most content on this website is subject to Crown copyright '
                               'protection and is published under the Open Government Licence '
                               '(OGL).',
                'terms_url': 'https://www.ons.gov.uk/help/termsandconditions',
                'verdict': 'confirmed'},
 'opec.org': {'box_action': "Read OPEC's copyright/terms page on the box and quote the reuse "
                            'clause for MOMR data',
              'checked_at': '2026-10-07',
              'fetch_status': 'FETCH_BLOCKED',
              'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the site answered 402 to the fetcher',
              'terms_quote': '',
              'terms_url': 'https://www.opec.org/',
              'verdict': 'to_confirm'},
 'paj.gr.jp': {'checked_at': '2026-10-07',
               'judgement': "TO_CONFIRM: no terms page linked; footer '© 2022 Petroleum "
                            "Association of Japan. All rights reserved.' grants nothing",
               'terms_quote': '',
               'terms_url': 'https://www.paj.gr.jp/english/',
               'verdict': 'to_confirm'},
 'pemex.com': {'box_action': "Read PEMEX's terms of use on the box and quote the reuse clause",
               'checked_at': '2026-10-07',
               'fetch_status': 'FETCH_BLOCKED',
               'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt disallows the fetcher',
               'terms_quote': '',
               'terms_url': 'https://www.pemex.com/',
               'verdict': 'to_confirm'},
 'pilbaraports.com.au': {'box_action': 'Read the terms of use / copyright page of '
                                       'https://www.pilbaraports.com.au/ on the box and quote the '
                                       'clause governing reuse of its data',
                         'checked_at': '2026-10-07',
                         'judgement': 'TO_CONFIRM: no terms page could be located from this '
                                      'container (terms URL 404 to the fetcher); the box action '
                                      'names where to read it',
                         'terms_quote': '',
                         'terms_url': 'https://www.pilbaraports.com.au/',
                         'verdict': 'to_confirm'},
 'ppac.gov.in': {'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                              'page read',
                 'terms_quote': '',
                 'terms_url': 'https://www.ppac.gov.in/copyright-policy',
                 'verdict': 'to_confirm'},
 'qcb.gov.qa': {'box_action': 'Read the terms of use / copyright page of https://www.qcb.gov.qa/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): certificate chain unverifiable to the '
                             'fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.qcb.gov.qa/',
                'verdict': 'to_confirm'},
 'rba.gov.au': {'also_quote': 'all RBA Material is provided under a Creative Commons Attribution '
                              '4.0 International License (CC BY 4.0 Licence)',
                'attribution': 'Source: Reserve Bank of Australia [year]',
                'checked_at': '2026-10-07',
                'judgement': 'CONFIRMED: the quoted clause permits use of the data, including the '
                             "desk's own-account analysis",
                'terms_quote': 'Financial Data and Financial Data Materials may be used, '
                               'reproduced, published, communicated to the public or otherwise '
                               'referenced for personal or commercial use',
                'terms_url': 'https://www.rba.gov.au/copyright/',
                'verdict': 'confirmed'},
 'rbi.org.in': {'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: the disclaimer covers liability and hyperlinking only; '
                             'no reuse grant for RBI data (also governs data.rbi.org.in)',
                'terms_quote': '',
                'terms_url': 'https://www.rbi.org.in/Scripts/Disclaimer.aspx',
                'verdict': 'to_confirm'},
 'rbnz.govt.nz': {'box_action': 'Find and quote the RBNZ copyright/terms page (footer of '
                                'https://www.rbnz.govt.nz/) on the box',
                  'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                               '(the copyright page URL returned 404 to the authoring fetcher); '
                               'the box action names where to read it',
                  'terms_quote': '',
                  'terms_url': 'https://www.rbnz.govt.nz/',
                  'verdict': 'to_confirm'},
 'resbank.co.za': {'box_action': 'Read the terms of use / copyright page of '
                                 'https://www.resbank.co.za/ on the box and quote the clause '
                                 'governing reuse of its data',
                   'checked_at': '2026-10-07',
                   'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                                '(terms URL 404 to the fetcher); the box action names where to '
                                'read it',
                   'terms_quote': '',
                   'terms_url': 'https://www.resbank.co.za/',
                   'verdict': 'to_confirm'},
 'riksbank.se': {'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no terms or licence text found on the statistics page; '
                              'guessed terms URL 404',
                 'terms_quote': '',
                 'terms_url': 'https://www.riksbank.se/en-gb/statistics/',
                 'verdict': 'to_confirm'},
 'rosstat.gov.ru': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://rosstat.gov.ru/ on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt unreadable to the '
                                 'fetcher',
                    'terms_quote': '',
                    'terms_url': 'https://rosstat.gov.ru/',
                    'verdict': 'to_confirm'},
 'sama.gov.sa': {'checked_at': '2026-10-07',
                 'judgement': 'REFUSED: the quoted clause prohibits commercial or automated use',
                 'terms_quote': 'Any use for obtaining personal or commercial gain is prohibited.',
                 'terms_url': 'https://www.sama.gov.sa/en-US/Pages/TermsofUse.aspx',
                 'verdict': 'refused'},
 'sars.gov.za': {'box_action': 'Read the terms of use / copyright page of '
                               'https://www.sars.gov.za/ on the box and quote the clause '
                               'governing reuse of its data',
                 'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                              '(legal-notice URL 404 to the fetcher); the box action names where '
                              'to read it',
                 'terms_quote': '',
                 'terms_url': 'https://www.sars.gov.za/',
                 'verdict': 'to_confirm'},
 'sbv.gov.vn': {'box_action': 'Read the terms of use / copyright page of https://www.sbv.gov.vn/ '
                              'on the box and quote the clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): 403 to the fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.sbv.gov.vn/',
                'verdict': 'to_confirm'},
 'sebi.gov.in': {'box_action': 'Read the terms of use / copyright page of '
                               'https://www.sebi.gov.in/ on the box and quote the clause '
                               'governing reuse of its data',
                 'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                              '(disclaimer URL 404 to the fetcher); the box action names where to '
                              'read it',
                 'terms_quote': '',
                 'terms_url': 'https://www.sebi.gov.in/',
                 'verdict': 'to_confirm'},
 'sgx.com': {'checked_at': '2026-10-07',
             'judgement': 'TO_CONFIRM: the terms page body was not returned to the authoring '
                          'fetcher (no clause read)',
             'terms_quote': '',
             'terms_url': 'https://www.sgx.com/terms-use',
             'verdict': 'to_confirm'},
 'shfe.com.cn': {'also_quote': '任何机构或者个人可基于非商业目的浏览、下载本网站的内容',
                 'checked_at': '2026-10-07',
                 'judgement': 'REFUSED: only non-commercial browsing and downloading is granted; '
                              "use for profit and electronic extraction (电子抓取系统) need SHFE's "
                              'written permission',
                 'terms_quote': '未经上海期货交易所书面许可，任何机构或者个人不得以向他人出售牟利为目的，使用本网站的任何内容',
                 'terms_url': 'https://www.shfe.com.cn/disclaimer/',
                 'verdict': 'refused'},
 'smart-lab.ru': {'checked_at': '2026-10-07',
                  'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on '
                               'the page read (forum site; practitioner content)',
                  'terms_quote': '',
                  'terms_url': 'https://smart-lab.ru/',
                  'verdict': 'to_confirm'},
 'snb.ch': {'checked_at': '2026-10-07',
            'judgement': 'TO_CONFIRM: the data portal page carries no terms text; legal-notice '
                         'URL 404',
            'terms_quote': '',
            'terms_url': 'https://data.snb.ch/en',
            'verdict': 'to_confirm'},
 'somooil.gov.iq': {'checked_at': '2026-10-07',
                    'judgement': "TO_CONFIRM: footer reads '© 2026 ... (SOMO) جميع الحقوق "
                                 "محفوظة'; no terms and no reuse grant",
                    'terms_quote': '',
                    'terms_url': 'https://somooil.gov.iq/',
                    'verdict': 'to_confirm'},
 'sse.net.cn': {'box_action': 'Read the terms of use / copyright page of '
                              'https://www.sse.net.cn/index/singleIndex on the box and quote the '
                              'clause governing reuse of its data',
                'checked_at': '2026-10-07',
                'fetch_status': 'FETCH_BLOCKED',
                'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the Shanghai Shipping Exchange page '
                             'answered 500 to the fetcher',
                'terms_quote': '',
                'terms_url': 'https://www.sse.net.cn/index/singleIndex',
                'verdict': 'to_confirm'},
 'stat.gov.az': {'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                              'page read',
                 'terms_quote': '',
                 'terms_url': 'https://www.stat.gov.az/?lang=en',
                 'verdict': 'to_confirm'},
 'stat.gov.kz': {'checked_at': '2026-10-07',
                 'judgement': 'TO_CONFIRM: no reuse, licence or copyright clause was found on the '
                              'page read',
                 'terms_quote': '',
                 'terms_url': 'https://stat.gov.kz/en/',
                 'verdict': 'to_confirm'},
 'statbank.dk': {'checked_at': '2026-10-07',
                 'judgement': "TO_CONFIRM: Statistics Denmark's about-the-website page as read "
                              'has no licence clause; StatBank API terms not found',
                 'terms_quote': '',
                 'terms_url': 'https://www.dst.dk/en/OmDS/omweb',
                 'verdict': 'to_confirm'},
 'statcan.gc.ca': {'attribution': 'Source: Statistics Canada, name of product, reference date. '
                                  "Reproduced and distributed on an 'as is' basis with the "
                                  'permission of Statistics Canada.',
                   'checked_at': '2026-10-07',
                   'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                                "the desk's own-account analysis",
                   'terms_quote': 'use, reproduce, publish, freely distribute, or sell the '
                                  'Information; use, reproduce, publish, freely distribute, or '
                                  'sell Value-added Products',
                   'terms_url': 'https://www.statcan.gc.ca/en/terms-conditions/open-licence',
                   'verdict': 'confirmed'},
 'stats.govt.nz': {'box_action': "Find and quote Stats NZ's copyright/licence page (linked from "
                                 'https://www.stats.govt.nz/ footer) on the box',
                   'checked_at': '2026-10-07',
                   'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                                '(the copyright page URL returned 404 to the authoring fetcher); '
                                'the box action names where to read it',
                   'terms_quote': '',
                   'terms_url': 'https://www.stats.govt.nz/about-us/legal-matters/copyright',
                   'verdict': 'to_confirm'},
 'statssa.gov.za': {'also_quote': 'They specify that the relevant application and analysis (where '
                                  'applicable) result from their own processing of the data.',
                    'attribution': 'Source: Statistics South Africa (basic data); processing and '
                                   "analysis are the desk's own",
                    'checked_at': '2026-10-07',
                    'judgement': 'CONFIRMED: the quoted clause permits use of the data, including '
                                 "the desk's own-account analysis",
                    'terms_quote': 'Users may apply the information as they wish, provided that '
                                   'they acknowledge Stats SA as the source of the basic data '
                                   'wherever they process, apply, utilise, publish or distribute '
                                   'the data.',
                    'terms_url': 'https://www.statssa.gov.za/?page_id=425',
                    'verdict': 'confirmed'},
 'stocktwits.com': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://stocktwits.com/ on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'judgement': 'TO_CONFIRM: no terms page could be located from this container '
                                 '(terms URL 404 to the fetcher); the box action names where to '
                                 'read it',
                    'terms_quote': '',
                    'terms_url': 'https://stocktwits.com/',
                    'verdict': 'to_confirm'},
 'swift.com': {'box_action': "Read swift.com's website terms of use on the box and quote the "
                             'clause covering RMB Tracker content',
               'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: no terms page could be located from this container (the '
                            'terms URL returned 404 to the fetcher); the box action names where '
                            'to read it',
               'terms_quote': '',
               'terms_url': 'https://www.swift.com/',
               'verdict': 'to_confirm'},
 'taifex.com.tw': {'checked_at': '2026-10-07',
                   'judgement': 'TO_CONFIRM: no terms or copyright page link found on the pack '
                                'page',
                   'terms_quote': '',
                   'terms_url': 'https://www.taifex.com.tw/',
                   'verdict': 'to_confirm'},
 'tcmb.gov.tr': {'box_action': 'Read the EVDS terms of use and tcmb.gov.tr copyright notice on '
                               'the box and quote the reuse clause',
                 'checked_at': '2026-10-07',
                 'fetch_status': 'FETCH_BLOCKED',
                 'judgement': 'TO_CONFIRM (FETCH_BLOCKED): EVDS is JavaScript-rendered (no text '
                              'to the fetcher)',
                 'terms_quote': '',
                 'terms_url': 'https://evds3.tcmb.gov.tr/',
                 'verdict': 'to_confirm'},
 'tfx.co.jp': {'checked_at': '2026-10-07',
               'judgement': 'TO_CONFIRM: the site policy covers linking only and the disclaimer '
                            "link returned 404; footer reads 'Copyright© Tokyo Financial Exchange "
                            "Inc. All Rights Reserved.' with no reuse grant",
               'terms_quote': '',
               'terms_url': 'https://www.tfx.co.jp/sitepolicy.html',
               'verdict': 'to_confirm'},
 'tianyancha.com': {'box_action': 'Read the terms of use / copyright page of '
                                  'https://open.tianyancha.com/ on the box and quote the clause '
                                  'governing reuse of its data',
                    'checked_at': '2026-10-07',
                    'fetch_status': 'FETCH_BLOCKED',
                    'judgement': 'TO_CONFIRM (FETCH_BLOCKED): the open-API site answered 419 to '
                                 'the fetcher (paid API)',
                    'terms_quote': '',
                    'terms_url': 'https://open.tianyancha.com/',
                    'verdict': 'to_confirm'},
 'tradestat.commerce.gov.in': {'checked_at': '2026-10-07',
                               'judgement': 'TO_CONFIRM: the footer links a Disclaimer whose text '
                                            'was not read; no reuse, licence or copyright clause '
                                            'was found on the page read',
                               'terms_quote': '',
                               'terms_url': 'https://tradestat.commerce.gov.in/',
                               'verdict': 'to_confirm'},
 'tradingview.com': {'checked_at': '2026-10-07',
                     'judgement': 'REFUSED: the quoted clause prohibits commercial or automated '
                                  'use',
                     'terms_quote': 'Except as otherwise expressly permitted by separate '
                                    'agreement, we do not permit commercial usage of any of our '
                                    'services or APIs.',
                     'terms_url': 'https://www.tradingview.com/policies/',
                     'verdict': 'refused'},
 'treasurydirect.gov': {'box_action': 'Read https://www.treasurydirect.gov/legal-information/ on '
                                      'the box and quote its copyright/public-domain clause',
                        'checked_at': '2026-10-07',
                        'fetch_status': 'FETCH_BLOCKED',
                        'judgement': 'TO_CONFIRM (FETCH_BLOCKED): robots.txt disallows the '
                                     'authoring fetcher; container proxy has no route',
                        'terms_quote': '',
                        'terms_url': 'https://www.treasurydirect.gov/legal-information/',
                        'verdict': 'to_confirm'},
 'trends.google.com': {'checked_at': '2026-10-07',
                       'judgement': 'TO_CONFIRM: Google Trends has no data licence; automated '
                                    'access is barred where robots.txt disallows it, and no '
                                    'clause grants reuse',
                       'terms_quote': 'using automated means to access content from any of our '
                                      'services in violation of the machine-readable instructions '
                                      'on our web pages (for example, robots.txt files that '
                                      'disallow crawling, training, or other activities)',
                       'terms_url': 'https://policies.google.com/terms',
                       'verdict': 'to_confirm'},
 'tuik.gov.tr': {'adopt': 'tr_tuik_retail'},
 'unctad.org': {'box_action': 'Read the UNCTADstat terms of use / disclaimer on the box and quote '
                              'the reuse clause',
                'checked_at': '2026-10-07',
                'judgement': 'TO_CONFIRM: no terms page could be located from this container (the '
                             'disclaimer URL returned 404 to the fetcher); the box action names '
                             'where to read it',
                'terms_quote': '',
                'terms_url': 'https://unctadstat.unctad.org/',
                'verdict': 'to_confirm'},
 'unicadata.com.br': {'checked_at': '2026-10-07',
                      'judgement': 'TO_CONFIRM: all rights reserved, no reuse grant',
                      'terms_quote': 'Copyright 2020 · Todos os direitos reservados - '
                                     'Observatório da Cana',
                      'terms_url': 'https://unicadata.com.br/',
                      'verdict': 'to_confirm'},
 'usda.gov': {'attribution': 'Source: U.S. Department of Agriculture',
              'checked_at': '2026-10-07',
              'judgement': 'CONFIRMED: the quoted clause permits use of the data, including the '
                           "desk's own-account analysis",
              'terms_quote': 'Most information presented on the USDA Web site is considered '
                             'public domain information. Public domain information may be freely '
                             'distributed or copied, but use of appropriate byline/photo/image '
                             'credits is requested.',
              'terms_url': 'https://www.usda.gov/about-usda/policies-and-links',
              'verdict': 'confirmed'},
 'worldbank.org': {'attribution': 'Source: World Bank Commodity Price Data (The Pink Sheet), CC '
                                  'BY 4.0',
                   'checked_at': '2026-10-07',
                   'judgement': "CONFIRMED: the commodity-markets page links 'Data Access and "
                                "Licensing' to datacatalog.worldbank.org/public-licenses#cc-by "
                                '(CC BY 4.0)',
                   'terms_quote': 'allows users to copy, modify and distribute data in any format '
                                  'for any purpose, including commercial use.',
                   'terms_url': 'https://datacatalog.worldbank.org/public-licenses',
                   'verdict': 'confirmed'}}
