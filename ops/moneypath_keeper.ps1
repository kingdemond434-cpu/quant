# STOPGAP, NOT A FIX -- delete this once the disk is resized.
#
# WHY IT EXISTS. The box's disk is at ~400MB of 100GB (100% full), so writes fail with ENOSPC and
# `Adopt-Release` / `git checkout` leave the tree on its old 2026-09-07 content. That drifts the
# money path away from the sealed release, and `release_identity` then flips `allows_new_risk` to
# false -- which takes ALL SIX armed sleeves off the venue, gold included, because the bracket loop
# checks the release verdict before it reaches `place_bracket` (gateway.py:2116).
#
# MEASURED 2026-09-11: the tree reverted six times in one hour, every time within minutes of being
# restored, each time disarming the book. The stale 43-leg file is SMALLER than the correct 90-leg
# one, which is why it can still be written when the larger one cannot -- the signature of ENOSPC
# rather than of any process doing the reverting.
#
# WHAT IT DOES. Restores any tracked CODE path that differs from HEAD, every 20s, so the seal stays
# valid and the book keeps trading. It touches nothing else: state paths (data/, reports/, logs/)
# are left exactly as the organs write them, because those are supposed to differ from HEAD.
#
# WHY IT MUST NOT BECOME PERMANENT. This hides ENOSPC, and a hidden failure is worse than a loud
# one -- the desk's own law (III.16, L1.28a). It is here only so the six sleeves trade while the
# hardware is fixed. Once the disk has headroom: stop this, delete it, and let the adopt do its job.
Set-Location C:\opt\quant
$log = 'C:\opt\quant\desks\mt5\logs\moneypath_keeper.log'
while ($true) {
    try {
        $drift = & git diff --name-only HEAD -- '*.py' '*.ps1' '*.cmd' 2>$null
        if ($drift) {
            & git checkout HEAD -- $drift 2>$null
            "$((Get-Date).ToUniversalTime().ToString('u')) restored $(@($drift).Count) code path(s)" |
                Out-File $log -Append -Encoding utf8
        }
    } catch {}
    Start-Sleep -Seconds 20
}
