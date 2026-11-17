# INSTALL TOR AS A LOCAL CLIENT-ONLY SERVICE, FOR THE ONION FOREST (2026-11-17).
#
# WHY. zuck 2026-11-17 20:31Z: "tor is legal", "remove our no proxy rule"; 20:32Z: continue the
# onion civilisation (governance/tor-proxy-ruling-2026-11-17.md). The onion forest
# (desks/mt5/research/onion_forest.py, libs/data/onion_fetch.py) reaches allowlisted .onion
# mirrors through a LOCAL Tor SOCKS5 port and reports TOR_ABSENT until one answers. This script
# provides that port, and nothing else.
#
# WHAT IT DOES, FAIL CLOSED AT EVERY STEP.
#  1. Refuses to run at all while $PinnedSha256 is not a 64-hex value (it ships as a failing
#     placeholder: the container that wrote it could not reach torproject.org to read the sums).
#  2. Downloads the official Tor Expert Bundle for Windows x86_64 at the PINNED version from the
#     Tor Project's own archive ONLY:
#       https://archive.torproject.org/tor-package-archive/torbrowser/<ver>/
#     The official download page that lists the current bundle and its checksums is
#       https://www.torproject.org/download/tor/
#     and the hash to pin is the bundle's line in that version's published sums file:
#       https://archive.torproject.org/tor-package-archive/torbrowser/<ver>/sha256sums-signed-build.txt
#  3. Verifies the archive's SHA-256 against the pinned value. A mismatch deletes the download and
#     stops: nothing is extracted, nothing is installed.
#  4. Extracts to C:\opt\tor and writes a torrc that is a CLIENT ONLY: SocksPort on 127.0.0.1:9050
#     and nowhere else, no ControlPort, no ORPort, no relay, no exit, ClientOnly 1.
#  5. Registers the Windows service with `tor.exe --service install -options -f <torrc>`.
#
# IDEMPOTENT. A service named 'tor' already running this pinned version is a no-op (and with
# -IfMissing, ANY existing 'tor' service is left alone). No account, no secret, no login: Tor's
# own service runs under its default service account.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_tor_service.ps1 -IfMissing

param(
    [switch]$IfMissing
)

$ErrorActionPreference = 'Stop'

# ---- PINS. Update the two together, from the sums file named above, never from anywhere else.
$TorVersion   = '14.0.4'
$PinnedSha256 = 'UNPINNED-READ-sha256sums-signed-build.txt-ON-THE-BOX-BEFORE-INSTALL'

$ArchiveBase = "https://archive.torproject.org/tor-package-archive/torbrowser/$TorVersion"
$BundleName  = "tor-expert-bundle-windows-x86_64-$TorVersion.tar.gz"
$BundleUrl   = "$ArchiveBase/$BundleName"
$TorDir      = 'C:\opt\tor'
$TorRc       = Join-Path $TorDir 'torrc'
$Marker      = Join-Path $TorDir 'INSTALLED_VERSION'
$ServiceName = 'tor'

function Write-Step([string]$m) { Write-Host "[install_tor_service] $m" }

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    $have = if (Test-Path $Marker) { (Get-Content $Marker -Raw).Trim() } else { '' }
    if ($IfMissing -or $have -eq $TorVersion) {
        Write-Step "service '$ServiceName' exists (version '$have', status $($existing.Status)); no-op"
        exit 0
    }
}

if ($PinnedSha256 -notmatch '^[0-9a-f]{64}$') {
    Write-Step "REFUSED: no pinned SHA-256 for $BundleName. Read its line from $ArchiveBase/sha256sums-signed-build.txt and pin it here first."
    exit 2
}
if ($BundleUrl -notmatch '^https://archive\.torproject\.org/tor-package-archive/torbrowser/') {
    throw "download URL is not the Tor Project archive: $BundleUrl"
}

New-Item -ItemType Directory -Force -Path $TorDir | Out-Null
$tmp = Join-Path $env:TEMP $BundleName
Write-Step "downloading $BundleUrl"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $BundleUrl -OutFile $tmp -UseBasicParsing

$got = (Get-FileHash -Algorithm SHA256 -Path $tmp).Hash.ToLowerInvariant()
if ($got -ne $PinnedSha256) {
    Remove-Item -Force $tmp
    Write-Step "REFUSED: SHA-256 mismatch (got $got, pinned $PinnedSha256); nothing installed"
    exit 3
}
Write-Step "SHA-256 verified"

if ($existing) {
    Write-Step "replacing version '$have' with $TorVersion"
    Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue
    & (Join-Path $TorDir 'tor\tor.exe') --service remove | Out-Null
}

& tar.exe -xzf $tmp -C $TorDir
if ($LASTEXITCODE -ne 0) { throw "tar.exe could not extract $tmp" }
Remove-Item -Force $tmp
$TorExe = Join-Path $TorDir 'tor\tor.exe'
if (-not (Test-Path $TorExe)) { throw "tor.exe not found at $TorExe after extraction" }

$DataDir = Join-Path $TorDir 'state'
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
# The bundle's GeoIP files: located, never assumed (their folder has moved between releases).
$geo  = Get-ChildItem -Path $TorDir -Recurse -File -Filter 'geoip'  | Select-Object -First 1
$geo6 = Get-ChildItem -Path $TorDir -Recurse -File -Filter 'geoip6' | Select-Object -First 1
$rc = @(
    '# Client-only Tor for the onion forest. SOCKS on loopback only; never a relay or exit.',
    'SocksPort 127.0.0.1:9050',
    'SocksPolicy accept 127.0.0.1',
    'SocksPolicy reject *',
    'ControlPort 0',
    'ORPort 0',
    'DirPort 0',
    'ClientOnly 1',
    'ExitRelay 0',
    'ExitPolicy reject *:*',
    "DataDirectory $DataDir",
    "Log notice file $(Join-Path $TorDir 'tor.log')"
)
if ($geo)  { $rc += "GeoIPFile $($geo.FullName)" }
if ($geo6) { $rc += "GeoIPv6File $($geo6.FullName)" }
Set-Content -Path $TorRc -Value $rc -Encoding ASCII

& $TorExe --service install -options -f $TorRc
if ($LASTEXITCODE -ne 0) { throw "tor.exe --service install exited $LASTEXITCODE" }
Set-Content -Path $Marker -Value $TorVersion -Encoding ASCII
Start-Service -Name $ServiceName -ErrorAction SilentlyContinue
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
Write-Step "installed Tor $TorVersion as service '$ServiceName' (status $($svc.Status)); SOCKS 127.0.0.1:9050"
exit 0
