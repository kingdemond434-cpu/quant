# ADOPT CLEAR: PR #1166

Auditor, 2026-11-14T09:53Z. Commit 4a5917fa9ce0165eacc2343c83b59f55145e5d26. pre-merge row at CLEARed head; diff from merge-base c532fa92d1aa7bbc992058a79e06d17125a62adf with LIVE 10b0ceef6313.
PR #1166 head 4a5917fa9ce0165eacc2343c83b59f55145e5d26 holds a CLEAR registry row; every blob below is identical to that CLEARed head.
Vouches only for these (path, blob) pairs. A merge where LIVE also changed one of these files yields a different blob and is not covered.

- desks/mt5/research/_retired/fetch_dukascopy.py 7b1f9b6be453693101d85ef5875d69bfc4b8c040
- desks/mt5/research/alpha_capture.py 00125da7e1984ef0c5cf6fc63939a20e71bd3dd9
- desks/mt5/research/data_axis_miner.py e2a41acc72a30ab23b66529f964c459bca661183
- desks/mt5/research/dukascopy_backfill.py 7e4d97515c6470dc3cb3c4cc8c53b76653c71779
- desks/mt5/research/fetch_dukascopy.py 7b1f9b6be453693101d85ef5875d69bfc4b8c040
- desks/mt5/side_channels/world_crawler.py 84db475673336f3d981f1d2f8e1f694ba97d363e
- desks/mt5/tests/test_crawler_targeting.py d0a22ca06697f8ff4c99b072c1ac735ec05f9f68
- desks/mt5/tests/test_dukascopy_backfill.py eb05025327c471f2da79e8394f8a6a1d8ae612d3
- libs/data/refused_hosts.py f1bf2befe5bbb1ce59dd8ccdb8fb59a4c792b3fd
- scripts/check_source_routes.py 05326875433dfd79d6930a070f2f7a284ea96605
- scripts/run_canaries.py c6c94e36810ccb566119773924a529f819757a94
- tests/data/test_refused_hosts.py 38460c74e63ae715c3bc167f934cb392777c9cf9
- tests/research/test_alpha_capture.py 9493cf5eb3283a910c3576d1835274c39ffdf1fe
- tests/test_source_routes_terms.py 285471cbc74f9814100ea7d4ad34045cb1c57f6b

Verdict: CLEAR for adoption of the listed blobs.
