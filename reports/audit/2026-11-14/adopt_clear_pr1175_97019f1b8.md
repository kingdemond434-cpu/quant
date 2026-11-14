# ADOPT CLEAR: PR #1175

Auditor, 2026-11-14T05:15Z. Commit 97019f1b833a0c4a59c0baea8c3416e35322a943. pre-merge row at CLEARed head; diff from merge-base d4c88564c2e1143a22b482145739992ad31e5e31 with LIVE 74e3b08a3620.
PR #1175 head 97019f1b833a0c4a59c0baea8c3416e35322a943 holds a CLEAR registry row; every blob below is identical to that CLEARed head.
Vouches only for these (path, blob) pairs. A merge where LIVE also changed one of these files yields a different blob and is not covered.

- desks/mt5/docs/CAPABILITY_AUDIT.md 9fd0d1a434704060a48981c303cb80ea71308765
- desks/mt5/research/ais_norway.py 56eee0310caa99ef5071ac904a8fc60e98ee7b2d
- desks/mt5/research/alt_proxies.py 4772a3283d2185d1f0560dfc1ecd40563f770f34
- desks/mt5/research/crowding_conditioner.py c220bfda42bf7eba92aa6dc82a6ebe7e20ad7a00
- desks/mt5/research/event_calendar_refresh.py 558e8321cc8c12c0cbdaef01b2da7cccbca46cb2
- desks/mt5/research/hourly_cycle.py d17dd4ca855476be918d2c98d79753fb51d5b572
- desks/mt5/tests/test_ais_norway.py d01145565d449fc8a2adaa99b7c2de2d390e8e09
- desks/mt5/tests/test_crowding_conditioner.py 40ca90eb7cc8587c62210455cbb5365366ce3253
- desks/mt5/tests/test_event_calendar_refresh.py 51e50f7ec63a393f201890a44847cd5a9fe09580
- desks/mt5/tests/test_free_stack_cftc.py 58b8f2d9376d2cfb54127195cd0e45750c8a2fec
- libs/data/datahub_feeds.py c73f1bfafa27b46e8614689f7f068807a62d2ffe
- libs/data/event_calendar.py d895f88ad615c44575f59e3d764f84c0bf533e29
- libs/data/ffaj_retail_fx.py b42d22522387d3f55a55a2cf6a82d5bfd2b05be5
- libs/data/free_stack.py d3852154ea5027959b5ae67275ca63d5a4f64e65
- libs/data/free_stack_cftc.py f556507c690dcc38d275a7cc57f59a6e62cf2340
- libs/ops/reference_freshness.py 337737eb840a71ea72069fd5d247e9fcd49705d3
- libs/research/layers.py 91887dfab37bf05ce640b45427a737618eca76e2
- tests/data/test_datahub_feeds.py 5e35eee614de82705ee558e5405a79fa7bfb749a
- tests/data/test_event_calendar.py de0bb0cdb5dae87cc4e77fc790433a830e130ae5
- tests/data/test_ffaj_retail_fx.py b4b9e16f42fa61d9b77dd318362c6864af023bdd
- tests/fixtures/event_calendar/bea_schedule.html.gz ccf369a929bb623c7c25bcb188c3e202451eaf36
- tests/fixtures/event_calendar/bls_cpi.html.gz 30a93a81fe2abe3ac5e46916c61bf30d7c9af932
- tests/fixtures/event_calendar/bls_empsit.html.gz 2a1776f5b08d1982833bd1bbf72094580d7a3f00
- tests/fixtures/event_calendar/boc_schedule.html.gz 04090a5c01aedc2a4a2644aa12c197e84c381fb6
- tests/fixtures/event_calendar/boe_mpc_dates.html.gz 6eeae276a0cf81d0471acc2d129dd7b98121cd14
- tests/fixtures/event_calendar/boj_mpm.html.gz 553bb0afd508867561209867056810041f7deba1
- tests/fixtures/event_calendar/ecb_mp_meetings.html.gz a238f51594a6e385b1110e4fd8fecf8e8d308993
- tests/fixtures/event_calendar/fed_fomc.html.gz 298a47a1082ba2fe7328059bd377bbba32c78f7b
- tests/fixtures/event_calendar/snb_events.html.gz 828b17556044d4f8b329ff8c8c240d0025b3740b
- tests/test_alt_proxies.py 620fc0e1b94f455dfc0505b60ba664adc63d0629
- tests/test_alt_proxies_substitutes.py 60964d1a26c16d3a5cb37d2a405192e01eadfbeb
- tests/test_dependency_caps.py e0c1a40b4bd61169377f4990b77c61cfc32d16fa

Verdict: CLEAR for adoption of the listed blobs.
