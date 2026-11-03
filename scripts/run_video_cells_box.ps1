# Hourly box job: pull sealed transcript bundles from the data branch, open them with the
# box-only private key, and turn them into discovery rows (free OpenRouter models only).
# Run as Administrator (the --user packages and the key live there), from C:\opt\quant.
param([string]$Repo = "C:\opt\quant", [string]$Branch = "claude/video-transcripts",
      [int]$MaxVideos = 40)
$ErrorActionPreference = "Stop"
Set-Location $Repo
$vault = Join-Path $Repo "data\video_vault"
$sealed = Join-Path $vault "sealed"; $open = Join-Path $vault "unsealed"
New-Item -ItemType Directory -Force -Path $sealed, $open | Out-Null
git fetch --quiet origin $Branch
$files = git ls-tree -r --name-only "origin/$Branch" -- sealed | Where-Object { $_ -like "*.vault" }
foreach ($f in $files) {
  $dest = Join-Path $sealed (Split-Path $f -Leaf)
  if (-not (Test-Path $dest)) {
    # cmd redirection keeps the blob's bytes intact (PowerShell's > would re-encode them)
    cmd /c "git cat-file blob origin/${Branch}:$f > `"$dest`""
  }
}
python scripts\video_transcript_vault.py open --src $sealed --dst $open
python scripts\extract_video_cells.py --mined $open --max-videos $MaxVideos
