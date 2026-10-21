"""Input reconstruction keeps literal rules and rejects missing identity before expensive IO."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DESK), str(DESK / 'scripts')]
from mt5desk import data, families, family_inputs
from mt5desk.legacy_family_inputs import RAW_COT_FAMILIES, input_preflight, legacy_inputs


def raw_cot():
    n = 160
    return pd.DataFrame({
        'report_date':pd.date_range('2022-01-04',periods=n,freq='7D',tz='UTC'),
        'noncomm_positions_long_all':1000+np.arange(n)**2,
        'noncomm_positions_short_all':np.full(n,500),
        'comm_positions_long_all':2000+np.arange(n)**2,
        'comm_positions_short_all':np.full(n,1000),
    })


def no_bars(*args):
    raise AssertionError('A malformed identity must not load bars')


@pytest.mark.parametrize('family,params',[
    ('usd_session_shock',{}),
    ('usd_session_shock',{'fx':'EURUSD','fx_symbol':'GBPUSD'}),
    ('clock_transition',{'stamp_hour':None}),
    ('clock_transition',{'stamp_hour':True}),
    ('clock_transition',{'stamp_hour':24}),
    ('relative_value',{}),
    ('correlation_regime',{'peer_symbol':None}),
    ('cross_asset_residual',{'factor_symbols':[]}),
    ('pca_residual',{'factor_symbols':['EURUSD',None]}),
])
def test_invalid_identity_never_loads_bars(family,params):
    extra,why=legacy_inputs('XAUUSD',family,params,no_bars)
    assert extra is None and why.startswith('BLOCKED_RULES:')


def test_valid_price_only_and_clock_identities_stay_unchanged():
    assert input_preflight('carry',None) is None
    assert input_preflight('clock_transition',{'stamp_hour':12}) is None


@pytest.mark.parametrize('params',[{'fx':'EURUSD'},{'fx_symbol':'EURUSD'},
                                 {'input_symbol':'EURUSD'}])
def test_fx_uses_exact_named_hourly_driver(params):
    calls=[]
    frame=pd.DataFrame({'close':np.ones(300)})
    def loader(symbol,chart):
        calls.append((symbol,chart))
        return frame
    extra,why=legacy_inputs('XAUUSD','usd_session_shock',params,loader)
    assert why=='ok' and extra['fx'] is frame
    assert calls==[('EURUSD','H1')]


@pytest.mark.parametrize('family',sorted(RAW_COT_FAMILIES))
def test_cot_reconstruction_preserves_dates_counts_and_literal_signals(monkeypatch,family):
    cot=raw_cot()
    monkeypatch.setattr(data,'load_cot',lambda sym:cot)
    extra,why=legacy_inputs('XAUUSD',family,None,no_bars)
    assert why=='ok' and extra['cot'] is cot
    index=pd.date_range('2022-01-01',periods=23000,freq='h',tz='UTC')
    price=2000+np.arange(len(index))*.003+np.sin(np.arange(len(index))/11)*20
    bars=pd.DataFrame({'open':price,'close':price,'high':price+2,'low':price-2},index=index)
    fn=getattr(families,'family_'+family)
    assert fn(bars,**extra)==fn(bars,cot)
    pd.testing.assert_frame_equal(extra['cot'],raw_cot())


def test_cot_entry_clock_preserves_epoch_and_subsecond_units():
    index=pd.date_range('2022-01-01',periods=5000,freq='h',tz='UTC')
    bars=pd.DataFrame({'open':2000.,'close':2000.,'high':2002.,'low':1998.},index=index)
    cot=raw_cot().iloc[:20]
    fn=families.family_cot_change_momentum
    reference=fn(bars,cot)
    assert reference
    finer=bars.copy()
    finer.index=finer.index.as_unit('us')
    assert fn(finer,cot)==reference
    other_zone=bars.copy()
    other_zone.index=other_zone.index.tz_convert('America/New_York')
    assert fn(other_zone,cot)==reference


def test_normalized_cot_and_source_substitution_are_refused(monkeypatch):
    monkeypatch.setattr(data,'load_cot',lambda sym:pd.DataFrame({'net':[1.0]}))
    extra,why=legacy_inputs('XAUUSD','cot_change_fade',{},no_bars)
    assert extra is None and 'normalized net' in why
    extra,why=legacy_inputs('XAUUSD','cot_change_fade',{'input_source':'cot_zcache'},no_bars)
    assert extra is None and 'cannot substitute source' in why


@pytest.mark.parametrize('bad',['duplicate_date','negative_count','nan_count'])
def test_invalid_raw_observations_are_refused(monkeypatch,bad):
    cot=raw_cot()
    if bad=='duplicate_date': cot.loc[1,'report_date']=cot.loc[0,'report_date']
    elif bad=='negative_count': cot.loc[0,'noncomm_positions_long_all']=-1
    else: cot.loc[0,'noncomm_positions_long_all']=np.nan
    monkeypatch.setattr(data,'load_cot',lambda sym:cot)
    extra,why=legacy_inputs('XAUUSD','cot_change_fade',{},no_bars)
    assert extra is None and why.startswith('BLOCKED_DATA:')


def test_missing_raw_cot_is_an_explicit_data_blocker(monkeypatch):
    def missing(sym): raise FileNotFoundError(sym)
    monkeypatch.setattr(data,'load_cot',missing)
    extra,why=legacy_inputs('EURUSD','cot_change_fade',{},no_bars)
    assert extra is None and 'BLOCKED_DATA:' in why


def test_forward_and_live_resolve_the_same_fx_frame(monkeypatch):
    frame=pd.DataFrame({'close':np.ones(300)})
    calls=[]
    def bars(inputs,sym,tf,h1):
        calls.append((sym,tf))
        return frame
    monkeypatch.setattr(family_inputs,'_runtime_bars',bars)
    extra,why=family_inputs.resolve('XAUUSD','usd_session_shock',{'fx_symbol':'EURUSD'},frame)
    assert why=='ok' and extra['fx'] is frame and calls==[('EURUSD','H1')]
    assert 'fx_symbol' not in family_inputs.runtime_call_params('usd_session_shock',{'fx_symbol':'EURUSD'})


@pytest.mark.parametrize('params', ['bad', ['bad'], 42])
def test_forward_and_live_refuse_non_object_params_without_io(monkeypatch, params):
    monkeypatch.setattr(family_inputs, '_runtime_bars', no_bars)
    extra, why = family_inputs.resolve('XAUUSD', 'usd_session_shock', params, None)
    assert extra is None and why == 'BLOCKED_RULES: candidate params are not an object'


def test_gauntlet_refuses_bad_clock_before_primary_bar_load(monkeypatch):
    import external_gauntlet as gauntlet
    monkeypatch.setattr(gauntlet,'_frame_for',no_bars)
    assert gauntlet.build_cell('XAUUSD','clock_transition',{'stamp_hour':None},{}) is None
    assert gauntlet.LAST_BUILD_FAILURE.startswith('BLOCKED_RULES:')


def test_warmer_refuses_bad_identity_before_loading_primary_bars(monkeypatch,tmp_path):
    import external_gauntlet as gauntlet
    import warm_gauntlet_cache as warmer
    monkeypatch.setattr(gauntlet,'CACHE_DIR',tmp_path)
    monkeypatch.setattr(gauntlet,'_bars_for',no_bars)
    key,outcome=warmer._warm_one({'ckey':'unbuildable-control','sym':'XAUUSD',
                                'family':'usd_session_shock','params':{},'tf':'M5'})
    assert key=='unbuildable-control' and outcome.startswith('failed|BLOCKED_RULES:')


def test_required_identity_refusals_are_build_failures_and_complete_specs_pass():
    # 2026-10-20 sweep 23324: 7,266 pre-warm build failures were these two deterministic refusals.
    # BLOCKED_ is what `main` files as NOT_RUN_BUILD_FAILED before the build budget is spent.
    for fam, params in (("lead_lag", {}), ("calendar_month", {"side_bias": 1})):
        why = input_preflight(fam, params)
        assert why is not None and why.startswith("BLOCKED_RULES")
    assert input_preflight("lead_lag", {"driver_symbol": "EURUSD"}) is None
    assert input_preflight("calendar_month", {"active_month": 12, "side_bias": -1}) is None
    # Present but out of range is the family's call, exactly as before.
    assert input_preflight("calendar_month", {"active_month": 13, "side_bias": 1}) is None
