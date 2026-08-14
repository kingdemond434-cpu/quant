#!/usr/bin/env python3
import json
d = json.load(open('/home/quant/quant-platform/web/cashcarry_shadow_8h.json'))
print('forward_ann_sharpe_8h:', d.get('forward_ann_sharpe_8h'))
print('forward_days_equiv:', d.get('forward_days_equiv'))
print('forward_nw_tstat_8h:', d.get('forward_nw_tstat_8h'))
print('autocorr_vif_8h:', d.get('autocorr_vif_8h'))
print('incumbent_daily:', d.get('incumbent_daily'))