#!/bin/bash
ps aux | grep -E 'run_cashcarry|run_leverage|run_live_combined|run_shadow_8h|collect_perpdex' | grep -v grep | awk '{print $2, $11, $12, $13, $14, $15}'