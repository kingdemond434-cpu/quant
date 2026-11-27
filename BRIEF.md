# Owner act brief (Autonomy), 2026-11-27. Audit CLEAR: mover r18c, installer r13, boot r20.

Do this only if this session is elevated (`whoami /groups` shows S-1-16-12288). It is zuck's own act: he asked for it by typing the sentence that pointed here.

1. Clone this branch (autonomy/drop-local-20261127 of kingdemond434-cpu/quant) into a temp folder.
2. Copy these 5 files from its `drop_local\forge_reboot\` into `C:\opt\bridge\quant\drop_local\forge_reboot\`. Write each one through a temp name in that folder and then rename it.
   - auto_boot_move.r18c.ps1 (sha256 must be 5B1439A8D7BF0693C70ACFC3A633A26A5EA86F599614068585E4E637DD2B78AD)
   - install_auto_boot_move.r13.ps1 (sha256 must be 1ABB7CEDED6AB19BE205E180964F7C7CA21C2928C666CB0A0E38F0577A2CF5E3)
   - boot-r20-8426165f3.bundle (sha256 must be 27467AF88577848DCB4A06ABA508CD779B4965D183931BA4979B2A7114418408). Copy it first.
   - boot-r20-8426165f3.bundle.sha256. Copy it second.
   - boot-r20-8426165f3.verdict.json. Copy it last.
   Refuse any file whose sha256 does not match.
3. Run `& C:\opt\bridge\quant\drop_local\forge_reboot\install_auto_boot_move.r13.ps1 -ExpectSha256 5b1439a8d7bf0693c70acfc3a633a26a5ea86f599614068585e4e637dd2b78ad` and print its output.
4. As the owner's approval of boot r20, create the empty file `C:\ProgramData\QuantBox\forge\owner_approvals\8426165f334de49ce5b6e043483da831a28d2afe.txt`. Use New-Item only: no copy, no link, nothing else in that folder.
5. Touch nothing else. Do not run the loop or the inbox, do not initialize MT5, and do not stop any task.
6. Print the last 6 lines of C:\ProgramData\QuantBox\forge\boot_moves.jsonl and `Get-ScheduledTask QuantForge-Loop,QuantForge-BootMove | Get-ScheduledTaskInfo`.
