# ADOPT CLEAR: PR #1165

Auditor, 2026-11-14T03:33Z. Commit 2cd60ce9b8fc7ea13181c9b76d895a4196a307e3. pre-merge row at CLEARed head; diff from merge-base d66204140c7f43a4acf4a04f25b2701d9352a121 with LIVE f34eaab96cbf.
PR #1165 head 2cd60ce9b8fc7ea13181c9b76d895a4196a307e3 holds a CLEAR registry row; every blob below is identical to that CLEARed head.
Vouches only for these (path, blob) pairs. A merge where LIVE also changed one of these files yields a different blob and is not covered.

- desks/mt5/recorders/vol_archive.py 94e9224ae113722e8eb5c3e12b3f20c7a6098d44
- desks/mt5/research/acquire_datasets.py c9cfa5a996fcce6b7baa7b9261fcea9825775edb
- desks/mt5/research/countries/us/pack.py cb8ad13f57bcd1a38fdd2a964fe36d3de61a0956
- desks/mt5/research/data_axis_miner.py bf3c97ecdac26f388cc93c53c7589b2b6dea8f46
- desks/mt5/research/fetch_alfred.py 70cc458c9947bd9c54a2e0fa3118833c62ec9771
- desks/mt5/research/fetch_fred.py 642572e62742c42ffc734b7f3ea5c9fc4c462507
- desks/mt5/research/fetch_futures_curves.py 66d113a33fca1fa38130ea71a11a18581ddcd550
- desks/mt5/research/fetch_sge_premium.py e80b210aa90b278ab267ee215056fe229d809515
- desks/mt5/research/free_data.py fa69462832d7f519c7d6390700f18864cd3a4c8c
- desks/mt5/research/futures_lead_lag.py af8910c650fa1f72bde5b6eb2d8ff852fd7c083a
- desks/mt5/research/futures_state_sources.json 17d348ac521d22884781adb1eb44c8bbf0d2bb0c
- desks/mt5/research/h1_source.py f1df16035e83010ad90b9f474faa156880707090
- desks/mt5/research/world_dataset_hunter.py c010f5535200629800bd9d5e8b39b272a318dc3e
- desks/mt5/side_channels/world_crawler.py 0593d2855f9a1b26ccd967ebf7436aee7a2d2d79
- libs/data/free_stack.py c308c7db88885afab3dd73a6dd1a4d0fb5390207
- libs/data/polite_fetch.py e6eaf1d16b5efa26da513496f4f843f9e451e9a8
- libs/data/terms_refused.py 189ef885fa6548afeb185a9cfb2df7134b581d91
- libs/data/us_primary_rates.py 2d9101fea46f814f0517bd093dbf83acf3650fc1
- scripts/check_source_routes.py 5bbc15cb2bff7cf0aee3a82bb76f33457f93dc42
- scripts/collect_fred_macro.py 83b60cb7e3dab8214248f33bc54711cb059b7ca0
- scripts/data_alternates.py 31a83a7789783e2a9dca13bb82180b73f889fdd3
- scripts/hurdle_rate.py c088a095663f553ad3e74813d3424e4552fa5ca6
- scripts/run_cot_screen.py b75d939640ef95b8451717fe96c9e05662bb57d5
- scripts/screen_fred_macro_axis.py 9c068085b7ce510eae33075567a31616595b6e82
- tests/data/test_terms_refused.py 68af008844ab2bee00c56ff9b4f629a81c7304ec
- tests/data/test_us_primary_rates.py 7647387e42c54369c544744e51ab43cd068defcd
- tests/research/test_vintage.py ddd291c0b65cd834d74036863c5040a252742ab6

Verdict: CLEAR for adoption of the listed blobs.
