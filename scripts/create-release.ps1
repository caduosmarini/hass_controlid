#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Require-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "Comando '$Name' nao encontrado no PATH."
        exit 1
    }
}

Require-Command git
Require-Command gh

try {
    $null = git rev-parse --is-inside-work-tree | Out-Null
} catch {
    Write-Error "Execute este script dentro de um repositorio git."
    exit 1
}

try {
    $originUrl = git remote get-url origin
} catch {
    Write-Error "Remote 'origin' nao encontrado."
    exit 1
}

$expectedRepo = "caduosmarini/hass_controlid"
if ($originUrl -notmatch [regex]::Escape($expectedRepo)) {
    Write-Warning "Origin atual nao parece ser '$expectedRepo'. URL: $originUrl"
}

$repoRoot = git rev-parse --show-toplevel
$manifestPath = Join-Path $repoRoot "custom_components" "controlid" "manifest.json"
if (-not (Test-Path $manifestPath)) {
    Write-Error "manifest.json nao encontrado em: $manifestPath"
    exit 1
}

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$tagName = $manifest.version

if ([string]::IsNullOrWhiteSpace($tagName)) {
    Write-Error "Campo 'version' vazio no manifest.json."
    exit 1
}

$lastTag = (git tag --sort=-creatordate) | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($lastTag)) {
    $lastTag = "<nenhuma>"
}

Write-Host ""
Write-Host "Ultima tag:              $lastTag"
Write-Host "Versao no manifest.json: $tagName"
Write-Host ""

$confirm = Read-Host "Criar release '$tagName'? (s/n)"
if ($confirm -notin @("s", "S", "y", "Y")) {
    Write-Host "Cancelado."
    exit 0
}

$existingTag = git tag --list $tagName
if (-not [string]::IsNullOrWhiteSpace($existingTag)) {
    Write-Error "Tag '$tagName' ja existe. Atualize a versao no manifest.json antes de criar uma nova release."
    exit 1
}

$status = git status --porcelain
if (-not [string]::IsNullOrWhiteSpace($status)) {
    Write-Error "Working tree com alteracoes nao commitadas. Faca commit ou stash antes de criar a release."
    exit 1
}

git push origin HEAD
git tag -a $tagName -m "Release $tagName"
git push origin $tagName
gh release create $tagName --title $tagName --generate-notes

Write-Host "Release criada: $tagName"
