#!/usr/bin/env bash
# Empacota os arquivos de urna baixados do TSE para os Releases do GitHub (limite de 2 GB por arquivo).
# Um .tar.gz por turno e UF, mais os bweb do 1º turno como vieram do TSE, e um SHA256SUMS de tudo.
#
# Uso: scripts/empacotar_release.sh <pasta do projeto bu2026> <pasta de saída> [turnos, padrão "1t 2t"]
set -euo pipefail
ORIGEM=$(cd "$1" && pwd)
DIST=$(mkdir -p "$2" && cd "$2" && pwd)

for turno in ${3:-1t 2t}; do
  [ -d "$ORIGEM/$turno" ] || continue
  for uf in "$ORIGEM/$turno"/*/; do
    uf=$(basename "$uf")
    alvo="$DIST/urnas_${turno}_${uf}.tar.gz"
    [ -s "$alvo" ] && continue
    echo "empacotando $turno/$uf"
    tar -C "$ORIGEM/$turno" -czf "$alvo.tmp" "$uf" && mv "$alvo.tmp" "$alvo"
  done
done

for z in "$ORIGEM"/bweb_1t_*.zip; do
  cp -n "$z" "$z.sha512" "$DIST/" 2>/dev/null || true
done

cd "$DIST"
shasum -a 256 urnas_*.tar.gz bweb_1t_*.zip > SHA256SUMS
echo "pronto: $(ls urnas_*.tar.gz | wc -l) pacotes de urna; $(du -sh . | cut -f1) no total"
