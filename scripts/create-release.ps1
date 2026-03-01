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

$lastTag = (git tag --sort=-creatordate) | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($lastTag)) {
    $lastTag = "<nenhuma>"
}

Write-Host "Ultima tag: $lastTag"
$tagName = Read-Host "Nome da nova tag/release"

if ([string]::IsNullOrWhiteSpace($tagName)) {
    Write-Error "Nome da tag nao pode ser vazio."
    exit 1
}

$existingTag = git tag --list $tagName
if (-not [string]::IsNullOrWhiteSpace($existingTag)) {
    Write-Error "Tag '$tagName' ja existe."
    exit 1
}

$status = git status --porcelain
if (-not [string]::IsNullOrWhiteSpace($status)) {
    Write-Error "Working tree com alteracoes nao commitadas. Faca commit ou stash antes de criar a release."
    exit 1
}

git push origin HEAD
git tag -a $tagName -m $tagName
git push origin $tagName
gh release create $tagName --title $tagName --generate-notes

Write-Host "Release criada: $tagName"