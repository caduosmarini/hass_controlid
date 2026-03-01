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
require_command jq

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

repo_root=$(git rev-parse --show-toplevel)
manifest_path="$repo_root/custom_components/controlid/manifest.json"
if [[ ! -f "$manifest_path" ]]; then
    echo "manifest.json nao encontrado em: $manifest_path" >&2
    exit 1
fi

tag_name=$(jq -r '.version' "$manifest_path")
if [[ -z "$tag_name" || "$tag_name" == "null" ]]; then
    echo "Campo 'version' vazio no manifest.json." >&2
    exit 1
fi

last_tag=$(git tag --sort=-creatordate 2>/dev/null | head -n1)
[[ -z "$last_tag" ]] && last_tag="<nenhuma>"

echo ""
echo "Ultima tag:              $last_tag"
echo "Versao no manifest.json: $tag_name"
echo ""

if [[ -n "$(git tag -l "$tag_name")" ]]; then
    echo "Aviso: Tag '$tag_name' ja existe." >&2
    read -r -p "Digite a nova versao (ou Enter para cancelar): " new_version
    if [[ -z "$new_version" ]]; then
        echo "Cancelado."
        exit 0
    fi
    if [[ -n "$(git tag -l "$new_version")" ]]; then
        echo "Tag '$new_version' tambem ja existe." >&2
        exit 1
    fi
    tag_name="$new_version"
    jq --arg v "$tag_name" '.version = $v' "$manifest_path" > "${manifest_path}.tmp" && mv "${manifest_path}.tmp" "$manifest_path"
    echo "manifest.json atualizado para versao $tag_name"
    git add "$manifest_path"
    git commit -m "Bump version to $tag_name"
    echo ""
fi

read -r -p "Criar release '$tag_name'? (s/n) " confirm
if [[ "$confirm" != "s" && "$confirm" != "S" && "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Cancelado."
    exit 0
fi

status=$(git status --porcelain)
if [[ -n "$status" ]]; then
    echo "Aviso: Working tree com alteracoes nao commitadas:" >&2
    git status --short
    read -r -p "Fazer commit de tudo antes de continuar? (s/n) " commit_confirm
    if [[ "$commit_confirm" != "s" && "$commit_confirm" != "S" && "$commit_confirm" != "y" && "$commit_confirm" != "Y" ]]; then
        echo "Cancelado."
        exit 0
    fi
    git add -A
    git commit -m "Release $tag_name"
fi

git push origin HEAD
git tag -a "$tag_name" -m "Release $tag_name"
git push origin "$tag_name"
gh release create "$tag_name" --title "$tag_name" --generate-notes

echo ""
echo "Release criada: $tag_name"
