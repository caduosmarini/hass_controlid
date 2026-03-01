#!/usr/bin/env bash
set -euo pipefail

require_command() {
    if ! command -v "$1" &>/dev/null; then
        echo "Comando '$1' nao encontrado no PATH." >&2
        exit 1
    fi
}

require_command git
require_command gh

if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "Execute este script dentro de um repositorio git." >&2
    exit 1
fi

origin_url=$(git remote get-url origin 2>/dev/null) || {
    echo "Remote 'origin' nao encontrado." >&2
    exit 1
}

expected_repo="caduosmarini/hass_controlid"
if [[ "$origin_url" != *"$expected_repo"* ]]; then
    echo "Aviso: Origin atual nao parece ser '$expected_repo'. URL: $origin_url" >&2
fi

last_tag=$(git tag --sort=-creatordate 2>/dev/null | head -n1)
[[ -z "$last_tag" ]] && last_tag="<nenhuma>"

echo "Ultima tag: $last_tag"
read -r -p "Nome da nova tag/release: " tag_name

if [[ -z "${tag_name// }" ]]; then
    echo "Nome da tag nao pode ser vazio." >&2
    exit 1
fi

if [[ -n "$(git tag -l "$tag_name")" ]]; then
    echo "Tag '$tag_name' ja existe." >&2
    exit 1
fi

status=$(git status --porcelain)
if [[ -n "$status" ]]; then
    echo "Working tree com alteracoes nao commitadas. Faca commit ou stash antes de criar a release." >&2
    exit 1
fi

git push origin HEAD
git tag -a "$tag_name" -m "$tag_name"
git push origin "$tag_name"
gh release create "$tag_name" --title "$tag_name" --generate-notes

echo "Release criada: $tag_name"
