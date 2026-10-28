#!/usr/bin/env bash
# Cria o repositório no GitHub, envia o código e o site, liga o GitHub Pages e sobe os pacotes de urna no Release.
# Precisa do GitHub CLI logado (brew install gh && gh auth login).
#
# Uso: scripts/publicar_github.sh <nome-do-repo> <pasta com os pacotes gerados por empacotar_release.sh>
set -euo pipefail
REPO=$1
DIST=$(cd "$2" && pwd)
cd "$(dirname "$0")/.."

[ -d .git ] || git init -b main
git add -A
git commit -m "Auditoria dos boletins de urna, 2º turno presidencial 2026" || true
gh repo view "$REPO" >/dev/null 2>&1 || gh repo create "$REPO" --public --source . --remote origin
git push -u origin main

# GitHub Pages servindo a pasta docs/ da branch main
DONO=$(gh api user -q .login)
gh api -X POST "repos/$DONO/${REPO##*/}/pages" -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1 || true

TAG=arquivos-tse-v1
gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" --title "Arquivos originais do TSE (boletins, RDV, logs, bweb)" \
  --notes "Arquivos baixados de resultados.tse.jus.br e dadosabertos.tse.jus.br, sem alteração. Hashes em SHA256SUMS e em manifesto/ no repositório."
# Sobe em lotes; --clobber substitui um arquivo se for reenviado
find "$DIST" -maxdepth 1 -type f \( -name 'urnas_*.tar.gz' -o -name 'bweb_1t_*' -o -name SHA256SUMS \) -print0 \
  | xargs -0 -n 10 gh release upload "$TAG" --clobber
echo "Site: https://$DONO.github.io/${REPO##*/}/"
