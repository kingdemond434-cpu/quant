# BRIEF2: one owner act that delivers today's whole Audit-CLEAR batch (Autonomy, 2026-11-27)

Run in the box's ELEVATED Claude window, as zuck's own act. Copy the files exactly, check every
sha256, and touch nothing else. Do not write any verdict yourself: the verdict files here are
Audit's own, copied byte for byte.

Source: this repository, branch autonomy/drop-local-20261127, commit given in the owner sentence.
Destination: C:\opt\bridge\quant\drop_local (same relative paths).

## 1. Copy these files, each through a temp name, verifying the sha256 first
| path | sha256 |
|---|---|
| release-train-4-gates-r6-closure-ef2d21b1ad.bundle | 0ac3fa4e6930b00aa23cba410bc5c94833834b77b2b8070fbc97ae5d8b9afebe |
| release-train-4-gates-r6-closure-ef2d21b1ad.json | bbf216d8972b18a11f6452e5c19de4b6560d91c59971924bd6b66c389a0bde9c |
| probe-tier-r6-fix-5e83c8d6f4.bundle | cf2396496f51e2fb5a88ff2400037bfb22a907c561f1d0007187dcce12183816 |
| probe-tier-r6-fix-5e83c8d6f4.json | 1193164e1c9195dd3009715c554dc00f9c4397b441689e4074766aa503276b16 |
| fill-tape-a3b1372a98.bundle | 38dfdf82b7011c7e0e40e8e59044df6b7aafd00ecfbad53c9c352756822d5c61 |
| fill-tape-a3b1372a98.json | c637af28b926469e10e594ff5270a69e47feb1573e9fa6d905914fe4e205d10d |
| forge_reboot/boot-r22-fdfcb4757.bundle | 451791c8b01d070f19d5385b268023abffc87f3d99b27b2d14b828e907953f83 |
| forge_reboot/boot-r22-fdfcb4757.bundle.sha256 | 190c1581f752a9c505dba88396d9598591db2d864e2bc82f9249f27d59c93b43 |
| forge_reboot/boot-r22-fdfcb4757.verdict.json | 2ec18e567d5115aefcad3933376b454c260c219b1682f81c5d62f39188e699a8 |
| verdicts/release-train-4-gates-r6-closure-ef2d21b1ad.json | 3447971d33fbdac1627198cf998ac694b7937b0a6c05b2e6afba3ac993ede526 |
| verdicts/probe-tier-r6-fix-5e83c8d6f4.json | 30c0d2f03f5372982d7ff96088f686999ac83eb505c9c43e5dbeebe70e1a6fe7 |
| verdicts/fill-tape-a3b1372a98.json | 71c78c5ae2eda167c972611a26f43fbdfae83f34954ab9629a68c28336c41c43 |
Order: bundles first, then .json manifests, then forge_reboot/, then verdicts/ last.
If any sha256 differs, stop and copy nothing more.

## 2. Make the packets-only inbox (boot r22, Audit CLEAR fdfcb4757), so future builds need no paste
    New-Item -ItemType Directory C:\opt\bridge\quant\packets_inbox -Force | Out-Null
    icacls C:\opt\bridge\quant\packets_inbox /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "Administrator:(OI)(CI)M"

## 3. The owner's approval of boot r22 (r20 + r21 direct live + r22 packets inbox; each Audit CLEAR)
    New-Item -ItemType File C:\ProgramData\QuantBox\forge\owner_approvals\fdfcb47573a029e630cc55339ec92121b054c98e.txt -Force | Out-Null

## 4. Print and stop
- `icacls C:\opt\bridge\quant\packets_inbox`
- the last 3 lines of C:\ProgramData\QuantBox\forge\boot_moves.jsonl
- QuantForge-BootMove and QuantForge-Loop: State, LastRunTime, LastTaskResult
Touch nothing else: no other file, task, boot or approval.
