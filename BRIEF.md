# Drop delivery brief (Autonomy). Audit CLEAR packets, transport only.

Do this only if this session is elevated, meaning `whoami /groups` shows S-1-16-12288.

1. Clone this branch (autonomy/drop-local-20261126 of kingdemond434-cpu/quant) at commit fe5383fbfa27fc2f599fe78d57004d1e483d018a into a temp folder.
2. Copy these 15 files from its `drop_local\` into `C:\opt\bridge\quant\drop_local\`, keeping their relative paths:
   - ceilings-ftmo-gold-e8-probe-7c3fbc4a20.{bundle,json}
   - gold-session-probe-forge-a52e840922.{bundle,json}
   - ftmo-gold-decouple-forge-cc85654d0e.{bundle,json}
   - ftmo-gold-sleeves-forge-09f8cba568.{bundle,json}
   - release-train-4-gates-r6-d9d4e3f697.{bundle,json}
   - verdicts\<each of those five ids>.json

   Copy all .bundle files first, then the manifests, and the verdicts last. Write each one through a temp name in the destination folder, then rename it. Skip anything named ftmo-gold-decouple-forge-74bb2d4433.
3. Check each bundle's sha256 before you copy it, and refuse any mismatch:
   - ceilings E2DC0DFD1B9CFB5131DB59A8C4A5ED37D2F04CCB74BC1D8AB23BB59655FA2A78
   - gold-session-probe E181C99F854E07CBE3AA6FF90CE0B937EC29655A5CDB6D4705269585720FB172
   - decouple 2944A8E4ED8D5430DD53DC5C9F0B1EB5656FA990476467DA94EE43001AF5F6E3
   - sleeves B5D0A729148667954850AF14183B6908A2513E4A19642C1DB32A4E10C07BF48D
   - train r6 48AFF72D3B95F70A72ED0CD79CF89DABE9E51B8882EAA0514EB2160B7F013A77
4. Touch nothing else. Do not run the inbox or the loop, do not initialize MT5, and do not stop any task.
5. Print the last 6 lines of C:\ProgramData\QuantBox\forge\boot_moves.jsonl, plus `Get-ScheduledTask QuantForge-Loop,QuantForge-BootMove | Get-ScheduledTaskInfo`.
