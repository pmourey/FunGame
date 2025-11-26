<#
scripts/windows_mkcert_setup.ps1
Automatisation mkcert (Windows)

- Vérifie si le script est lancé en Administrateur (nécessaire pour mkcert -install et modification hosts si demandé)
- Installe mkcert via Chocolatey si présent, sinon télécharge le binaire depuis GitHub Releases
- Exécute `mkcert -install`
- Génère les certificats pour philippe.mourey.com et philippe.mourey.com:60000
- Place/renomme les fichiers générés dans `deploy/certs/philippe.pem` et `deploy/certs/philippe-key.pem`

Usage (PowerShell administrateur):
  cd <repo-root>
  .\scripts\windows_mkcert_setup.ps1

Note: si vous préférez utiliser Chocolatey manuellement, installez choco puis relancez le script.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Is-Administrator {
    $current = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Is-Administrator)) {
    Write-Host "This script must be run as Administrator. Open PowerShell 'Run as Administrator' and re-run this script." -ForegroundColor Yellow
    exit 2
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$deployDir = Join-Path $repoRoot 'deploy'
$certsDir = Join-Path $deployDir 'certs'

if (-not (Test-Path $deployDir)) {
    New-Item -ItemType Directory -Path $deployDir | Out-Null
}
if (-not (Test-Path $certsDir)) {
    New-Item -ItemType Directory -Path $certsDir | Out-Null
}

# Helper to check command presence
function Command-Exists($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

# Locate or install mkcert
$mkcertPath = $null
if (Command-Exists 'mkcert') {
    $mkcertPath = (Get-Command mkcert).Source
    Write-Host "Found mkcert at: $mkcertPath"
} else {
    # Try Chocolatey
    if (Command-Exists 'choco') {
        Write-Host "Chocolatey detected. Installing mkcert via choco..."
        choco install mkcert -y
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')
        if (Command-Exists 'mkcert') {
            $mkcertPath = (Get-Command mkcert).Source
            Write-Host "mkcert installed at: $mkcertPath"
        }
    }
}

if (-not $mkcertPath) {
    Write-Host "mkcert not found on PATH and Chocolatey not available or install failed. Will download mkcert binary into deploy folder." -ForegroundColor Yellow
    # Query the latest release for Windows amd64
    $apiUrl = 'https://api.github.com/repos/FiloSottile/mkcert/releases/latest'
    try {
        $release = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing -Headers @{ 'User-Agent' = 'mkcert-windows-setup' }
        $asset = $release.assets | Where-Object { $_.name -match 'windows.*amd64' } | Select-Object -First 1
        if (-not $asset) { throw "No windows amd64 asset found in latest release" }
        $downloadUrl = $asset.browser_download_url
        $dest = Join-Path $deployDir 'mkcert.exe'
        Write-Host "Downloading mkcert from $downloadUrl to $dest"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $dest -UseBasicParsing
        # Ensure executable bit (Windows) -- just ensure file exists
        if (Test-Path $dest) {
            $mkcertPath = $dest
            Write-Host "Downloaded mkcert to $mkcertPath"
        }
    } catch {
        Write-Error "Failed to download mkcert: $_"
        exit 3
    }
}

# Run mkcert -install
Write-Host "Running mkcert -install (requires admin)"
& $mkcertPath -install

# Generate certificates
$domains = @('philippe.mourey.com', 'philippe.mourey.com:60000')
Write-Host "Generating certificates for: $($domains -join ', ')"
Push-Location $deployDir
try {
    & $mkcertPath @domains
} catch {
    Write-Error "mkcert failed to generate certs: $_"
    Pop-Location
    exit 4
}

# Find generated pem files and move/renames to certs dir
# mkcert typically writes files named like: philippe.mourey.com+2.pem and philippe.mourey.com+2-key.pem or philippe.mourey.com.pem
$patternPem = 'philippe.mourey.com*.pem'
$found = Get-ChildItem -Path $deployDir -Filter $patternPem -File | Where-Object { $_.Name -notlike '*-key.pem' }
$keyPattern = 'philippe.mourey.com*-key.pem'
$foundKey = Get-ChildItem -Path $deployDir -Filter $keyPattern -File | Select-Object -First 1

if (-not $found -or $found.Count -eq 0) {
    Write-Error "No generated certificate PEM found in $deployDir"
    Pop-Location
    exit 5
}

# Choose the most recent file if multiple
$certFile = $found | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $foundKey) {
    # look for a file with -key.pem naming; fallback find *-key.pem
    $foundKey = Get-ChildItem -Path $deployDir -Filter '*-key.pem' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
if (-not $foundKey) {
    Write-Error "No key PEM found in $deployDir"
    Pop-Location
    exit 6
}

$destCert = Join-Path $certsDir 'philippe.pem'
$destKey = Join-Path $certsDir 'philippe-key.pem'

Write-Host "Copying certificate $($certFile.Name) -> $destCert"
Copy-Item -Path $certFile.FullName -Destination $destCert -Force
Write-Host "Copying key $($foundKey.Name) -> $destKey"
Copy-Item -Path $foundKey.FullName -Destination $destKey -Force

# Optionally set restrictive permissions (best-effort)
try {
    Icacls $destCert /inheritance:r /grant:r "Administrators:F" | Out-Null
    Icacls $destKey /inheritance:r /grant:r "Administrators:F" | Out-Null
} catch {
    Write-Host "Warning: could not set strict ACLs on cert files (non-fatal)" -ForegroundColor Yellow
}

# Optionally add hosts entry on Windows to map philippe.mourey.com to localhost
# Ask interactively (script already requires Admin privileges)
try {
    $ans = Read-Host "Add hosts entry '127.0.0.1 philippe.mourey.com' to Windows hosts file? (Y/n)"
    if ([string]::IsNullOrWhiteSpace($ans) -or $ans.Trim().ToLower().StartsWith('y')) {
        $hostsPath = Join-Path $env:windir 'System32\drivers\etc\hosts'
        $hostsContent = Get-Content -Path $hostsPath -ErrorAction SilentlyContinue -Raw
        if ($hostsContent -match "^\s*127\.0\.0\.1\s+philippe\.mourey\.com\b") {
            Write-Host "Hosts entry already present: skipping"
        } else {
            Add-Content -Path $hostsPath -Value "`n127.0.0.1 philippe.mourey.com"
            Write-Host "Added hosts entry to $hostsPath"
        }
    } else {
        Write-Host "Skipped modifying hosts file as requested"
    }
} catch {
    Write-Host "Warning: failed to modify hosts file: $_" -ForegroundColor Yellow
}

Pop-Location

Write-Host "mkcert setup complete. Certificates are placed in: $certsDir" -ForegroundColor Green
Write-Host "Now run: docker compose up -d fungame && docker compose up -d nginx" -ForegroundColor Cyan
Write-Host "Or run: make deploy-https" -ForegroundColor Cyan

# Interactive option: offer to run the deploy commands now
try {
    $deployAns = Read-Host "Voulez-vous lancer immédiatement le déploiement (build + up) ? (Y/n)"
    if ([string]::IsNullOrWhiteSpace($deployAns) -or $deployAns.Trim().ToLower().StartsWith('y')) {
        Write-Host "Lancement du déploiement: build et démarrage des services (docker compose) ..."
        try {
            & docker compose build fungame
            & docker compose up -d fungame
            & docker compose up -d nginx
            Write-Host "Déploiement lancé : vérifiez les logs avec 'docker compose logs -f fungame' et 'docker compose logs -f nginx'" -ForegroundColor Green
        } catch {
            Write-Host "Erreur lors de l'exécution des commandes de déploiement : $_" -ForegroundColor Red
            Write-Host "Si 'docker compose' n'est pas disponible, exécutez manuellement : make deploy-https" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Déploiement non lancé (skipped)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Interaction de déploiement ignorée en raison d'une erreur : $_" -ForegroundColor Yellow
}

exit 0
