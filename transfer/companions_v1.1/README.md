# judge image companions v1.1: the audit's must-fixes and should-fixes (2026-10-27)

v1.1 answers the audit of v1 (`reports/audit/2026-10-14/JUDGE_IMAGE_COMPANIONS_2f28cf7de.md`), which put **2f28cf7de** on HOLD with MF1 and MF2.

- Four commits sit on top of 2f28cf7de, on the same branch `claude/judge-image-companions`.
- No sealed file is touched. Nothing is signed and nothing is pushed.
- v1's merges and remerge diffs are unchanged; they are in the parent directory.

**Head: `392b260bcacb6d0194ef976ac59ea35c2a6db82b`**

**Bundle: `judge_image_companions_v1.1_392b260bc.bundle`**
- Range: `180cebf26..claude/judge-image-companions`, 87 commits.
- It requires only `180cebf26`, which is **now on LIVE**.
- sha256 `683215761e505594ffbc4acd3dc43e97923288932934e5a36356a8cbd3f23801`.
- The four v1.1 commits are also in `v1.1_commits/`.

| sha | fix |
|---|---|
| `23459f93ddc64347113ecc87d7179ec7a8525af6` | **MF1**: gate_ledger_index future-row prune; SCHEMA 3; LAWS-7 row corrected |
| `605a92484cd1c6482836d1ec751abaca6f57b076` | **SF1**: deferral deadline inside the hard stop; plus the MF1 probe tests |
| `8c13b0419a3342b5f2a91c3815358ca566488128` | **SF2**: `test_check_trial_inflation` uses `==` instead of `<=` |
| `392b260bcacb6d0194ef976ac59ea35c2a6db82b` | **SF3**: the swallowed `emit` in cost_truth is unwrapped |

## MF1: one future-stamped row could prune every real bucket

**Problem.** In `gate_ledger_index.py`, `_fold_line` set `max_ts` to the newest stamp it saw, with no bound, and `_prune` cut at `max_ts - 35 d`. One row stamped 35+ days ahead therefore deleted every real bucket for good.

**Fix:**
- `max_ts` advances only to a stamp at or below **wall clock + `FUTURE_SKEW_S` (300 s)**. That is the desk's existing future-stamp tolerance. The wall clock is re-read for each folded chunk.
- `_prune` now cuts at **`min(max_ts, wall clock + 300 s) - KEEP_BUCKET_S`**. The prune line is bounded by the wall clock as well as by `max_ts`.
- A future row still keeps **its own bucket**. Every window reader therefore sees exactly the rows it saw before, and `judging_rate`'s `[now-24h, now]` window already excluded such a row. The row just never becomes `max_ts`, so it cannot move the prune line or `last_verdict_at`.
- **`SCHEMA` goes from 2 to 3.** A v2 pickle may already hold a poisoned `max_ts` and pruned buckets, so it now rebuilds from the ledger.

**LAWS-7 row** (`reference_freshness.py`, `gate_ledger_index.prune`):
- The reference now reads `min(max_ts, wall clock + FUTURE_SKEW_S)`.
- The note says why the v1 claim of "four weeks of margin" was false, and names the pinning test.
- `check_no_retirement_on_absence` still reads 6/6 on the image tree.

**Tests** (in `desks/mt5/tests/test_judge_rate.py`):
- **The auditor's probe**, `test_one_future_stamped_row_cannot_prune_the_real_buckets`:
  - 31 verdicts in the last 24 h, plus one row 36, 40 or 400 days ahead.
  - Run both in one fresh build and incrementally (the future row appended after a persisted index).
  - The index count must stay 31, `judging_rate.verdicts_24h` must be 31, and `max_ts` must stay at or before now + 300 s.
- **Negative control:** with v1's `gate_ledger_index.py` restored, all 6 parametrisations FAIL.
- `test_an_index_persisted_before_the_future_bound_rebuilds`: a poisoned v2 pickle is rebuilt and the count is 31.

## MF2: the red on `check_judge_coverage --require-state` (correction)

**v1's README was wrong.** It said this red was caused by a stale published report and would clear "when the box republishes". That is not true.

- Base 180cebf26 is now red as well, for staleness. On this run's trees the fence fails on both 2f28cf7de and 392b260bc for the same reasons: freshness (the report is 116 h old), `never_judged`, `tape_produces` and `judging_rate`.
- The auditor simulated a publish from the merged code with a ledger at the box's measured rate of about 5,300 verdicts a day. `--require-state` **stays red on `judging_rate`, at about 3.5% of the 150,000/day floor.**
- **The red is a standing capacity verdict**: the judge rules about 28 times too slowly for the desk's own floor. It is not stale state, and a republish will not clear it.
- The fence is correct and is **not weakened**: v1.1 changes no threshold, target or rule.

**This needs explicit acceptance from the coordinator or zuck before landing.** Landing the companions makes a fence go red and stay red until judging capacity reaches the floor. That is what the fence exists to say.

I did not re-run the auditor's 5,300/day simulation. The 3.5% figure is theirs.

## Should-fixes

1. **SF1** (`judge_coverage.py`):
   - **Problem:** with no `QUANT_LEG_BUDGET_S`, `stop_after_s` returned stop == budget. The deferral deadline then coincided with the hard stop, and a hand run timed out instead of publishing a deferred report.
   - **Fix:** the new `defer_deadline_s(budget, stop)` sets the deferral at `min(budget, max(stop - COMMIT_MARGIN_S, stop/2))`. That always falls before the stop with the 15 s commit margin in hand. The report records it as `defer_deadline_s`.
   - `stop_after_s` is unchanged and its tests still pass.
   - `test_main_enforces_budget_s` now expects the deferral 15 s before a hand-run stop.
   - New test: `test_the_deferral_always_fires_before_the_hard_stop_with_room_to_write`.
2. **SF2:** `tests/scripts/test_check_trial_inflation.py:153` now asserts `DSR_FIXED_TRIALS == BAR_N`. It runs, and passes, on the image tree; it skips before T8.
3. **SF3:** the `try/except Exception: pass` around the `COST_TRUTH_QUOTES_STALE` emit in `cost_truth.py` is removed. `emit` already reports its own OSError.
   - The file's `except Exception:` count is back to base: 4, against 5 in v1.
   - `check_bare_excepts --file-writes-only` drops from "… and 5 more" to "… and 4 more".
4. **SF4 (note only; the deadline is not moved):** `check_trial_inflation.SEALED_DEADLINE` (`:138`) is 2026-10-27, so the fence now **FAILs on head**. The message is "10 sealed site(s) still charge a moving N… owed by the T8 sealed re-sign (PAST 2026-10-27)".
   - **The sign clears it.** On the image tree (head + image chain + ride-along + a377) the same fence reads `trial inflation: PASS (bar N=5)`, with all four checks OK.
   - The fence stays red on any tree without the T8 re-sign, which is correct.

## Image chain on v1.1: hashes reproduce

I fetched LIVE fresh: `9eb83263181663dad3fd9356b0b349e4103fe3bf` (box state 2026-10-27_1522). 180cebf26 is an ancestor of it.

**`external_gauntlet.py` is the same blob (`d44204ad`, sha256 prefix `f56bc72f`) on LIVE and on head.** Applying the three patches in order at `patch -p1 -F0` on 392b260bc:

| patch | sha256 | result |
|---|---|---|
| `external_gauntlet_stack/CUMULATIVE_LIVE_f56bc72f_to_46392548.patch` | `acf3f1a1967d6407a5b54581833cf931662228f5773f8819d67f4f3b9ebf35ac` | `46392548…` |
| `judge_plan_phase/judge_plan_phase_on_46392548.patch` | `e54e26f7093c4a8d1cf42041a790e3b1e261b0fc6f58d8b0efe218ba424c5408` | `a02f095c…` |
| `judge_plan_phase_v2/judge_plan_phase_next_rotation_v2.2_on_a02f095c.patch` | `493de1d98fb8d3db76d01539b61e90f02979b6a6a9e768aa75ca123f0703cfe8` | **`242c04afbc0357a5d7a96d7b6a88864df33c0627835697e05880ae444d6d2366`**, 0 CR |

`SIGN_RIDEALONG_on_2f28cf7de.patch` is unchanged: same bytes, sha256 `25cfa2eebf4d3aed7bb64c2651406311d08a33f4bca20fe4d4f1df6d5828e8dc`.
- It applies cleanly on 392b260bc and on the LIVE+head merge tree.
- Its T8 results are gate_policy `845a7f23155d10b0`, universal_gate `0e03b4c73e609721`, multiplicity `fa7f963aa8dc58e3` and gate_spec `a11ca0cbf0501296`.
- The non-sealed files also match: qquant `31171c46`, fragility `fc33a6de`, run_hunt12 `8fb6faa9`, ug_remote `344f7902` and gate_calibration `0b5956bf`.

**merge-tree:**
- LIVE `9eb83263` merged with `392b260bc` is **clean**, tree `05a565f46`.
- That result merged with `a377f25c8` is **clean**, tree `6f7a3f5cd`.
- `IMMUTABLE_MANIFEST.json` and `quantbench.py` are unchanged between 180cebf26 and LIVE.

## Sign target

- **Sign target: `242c04afbc0357a5d7a96d7b6a88864df33c0627835697e05880ae444d6d2366`.**
- Fallbacks, in order: **a02f095c**, then **46392548**.
- **Never 1aa4b33f.**

## LAPTOP STEPS, in order

1. **Merge the companions.** 180cebf26 is already on LIVE.
   ```
   git fetch judge_image_companions_v1.1_392b260bc.bundle claude/judge-image-companions
   git merge --no-ff FETCH_HEAD      # brings in 392b260bcacb6d0194ef976ac59ea35c2a6db82b
   ```
2. **Apply the image chain** to `desks/mt5/scripts/external_gauntlet.py`: the three patches above, at `patch -p1 -F0`, in order. Confirm the sha256 is `242c04af…6d2366` and there are 0 CR bytes.
3. **Apply the ride-along:** `git apply SIGN_RIDEALONG_on_2f28cf7de.patch`. Check the four T8 hashes.
4. **Pre-sign check.** `python scripts/check_immutable_evaluator.py` must show exactly **5 BREACH**: external_gauntlet, universal_gate, multiplicity, gate_policy, gate_spec. Verified here on the v1.1 image tree, rc 1, those five and nothing else.
   - `--sign-files` re-hashes every manifest file. **Stop if there is a sixth.**
5. **The single zuck sign step.** Choose one signer string, `$SIGNER`.
   - In `desks/mt5/research/quantbench.py`, `GAUNTLET_SEAL_ROTATION`:
     - set `"to"` (line 80) to `"242c04afbc0357a5d7a96d7b6a88864df33c0627835697e05880ae444d6d2366"`;
     - set `"signed_by"` to `$SIGNER`;
     - leave `"from"` (`d0919bfc…`) as it is.
   - Run `python scripts/check_immutable_evaluator.py --sign-files --by "$SIGNER"`. The `--by` string must be byte-identical to the one in quantbench.py.
   - This writes the `files` section only. It re-pins external_gauntlet to `242c04afbc0357a5` and the four T8 rows. No hand edit to `rotation_signers` is needed.
   - The auditor's simulated positive control gave immutable_evaluator OK, the QB-002 probe PASS, and constitution_core intact.
   - Commit the sign, the image and the ride-along together.
6. **Same push: `a377f25c8`.** Fetch `external_gauntlet_stack/stack_reference_freshness_a377f25c8.bundle` (sha256 `9c2b882c41f084395717c7205eb54a5fec0597e8a87e98c1c43db6fa2d81ff2f`) and merge it.
   - With it, LAWS 7 reads 6/6 OK on the image tree (`undeclared_count 6`, ceiling 6).
7. **Verify before the push.** Expected results:

   | check | expected |
   |---|---|
   | `check_immutable_evaluator` | 0 BREACH |
   | `check_constitution_core` | intact |
   | QB-002 probe | rotated, not REGRESSED |
   | `check_no_retirement_on_absence` | 6/6 |
   | `check_trial_inflation` | PASS; the sign is what clears SF4 |
   | `./ops/gates.sh` | green |
   | `python -m pytest --co -q` | rc 0 |
   | law gate | runs |
   | `check_judge_coverage --require-state` | stays red on judging_rate: the capacity verdict in MF2, accepted beforehand |

## Validation done here (4 cores)

- **`./ops/gates.sh` on 392b260bc:** all green, "fast pass on 392b260bcacb (tree_clean=True)". See `gates_head_392b260bc.txt`. `--full` was not run.
- **`pytest --co`:** rc 0 on both roots.
- **Head tests** (`v11_tests_head.txt`): the 89 files of v1's head list (v1's 88, with both `test_bar_clock.py` files) in 18 batches of 5. **All 18 batches rc 0**, 2,276 tests passed in total.
  - The new MF1/SF1 tests are in `test_judge_rate.py`.
  - `test_cost_truth`, `test_reference_freshness` and `test_judge_coverage_transaction` also pass.
- **Image tree tests** (`v11_tests_image.txt`). The image tree is v1.1 + the image chain + the ride-along + the a377 delta. 36 files: the stack union plus judge_rate, check_trial_inflation, cost_truth, reference_freshness, judge_coverage_transaction and replay_input_cache_identity. **All 8 batches rc 0**, 774 tests passed in total.
- **Fences: all 94, one at a time,** each in its own clean worktree, with checkout/clean between fences (`v11_fences_base_2f28cf7de.json`, `v11_fences_head_392b260bc.json`).
  - Base v1 2f28cf7de: 35 failing. Head v1.1: 35 failing. **The rc values are identical on all 94.**
  - Tail-only change: `check_bare_excepts` goes from "5 more" to "4 more" (SF3).
  - Compared with v1's run on a7a04414a, `check_judging_coverage` has turned red on both sides, because the published report aged past 6 h. That is the same on base and head.
  - `check_trial_inflation` is not among the 94. I ran it separately: FAIL at head (SF4) and PASS on the image tree.
- **Seal, negative control on the v1.1 image tree:** exactly 5 BREACH (rc 1). constitution_core intact.

## Not verified

- I did not run the positive seal control (re-pinned manifest and quantbench). That edit was refused here, even in a scratch tree. The auditor has run it on a simulated scratch tree.
- I did not reproduce MF2's 5,300/day simulation.
- No Windows or box behaviour, no real sweep, no speed measurement, and no `gates.sh --full`.
- Choices that need a ruling:
  - MF1: the future-row bound uses the existing 300 s skew, and the wall clock is read once per 8 MiB chunk.
  - SF1: the deferral floor is half the stop for tiny hand budgets.
