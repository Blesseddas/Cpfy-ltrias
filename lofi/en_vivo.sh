#!/usr/bin/env bash
# Transmisión en vivo 24/7 a YouTube con los videos generados.
# Debe correr en un servidor que esté siempre encendido (un VPS); GitHub Actions
# corta los trabajos a las 6 horas, así que no sirve para esto.
#
# Uso:
#   YT_STREAM_KEY=xxxx-xxxx-xxxx-xxxx ./en_vivo.sh carpeta_con_videos
#
# Reproduce en orden todos los .mp4 de la carpeta y vuelve a empezar; en cada
# vuelta relee la carpeta, así que los videos nuevos entran solos. Usa
# «-c:v copy» (casi no gasta CPU), por eso todos los videos deben tener la misma
# resolución (no mezcles videos hechos con --rapido y sin él).
set -euo pipefail
: "${YT_STREAM_KEY:?Define YT_STREAM_KEY con la clave de transmisión de YouTube Studio}"
CARPETA="${1:-salida}"
DESTINO="rtmp://a.rtmp.youtube.com/live2/${YT_STREAM_KEY}"

while true; do
  LISTA="$(mktemp)"
  find "$CARPETA" -name '*.mp4' -print0 | sort -z |
    while IFS= read -r -d '' f; do printf "file '%s'\n" "$(realpath "$f")"; done > "$LISTA"
  if [ ! -s "$LISTA" ]; then
    echo "No hay videos .mp4 en $CARPETA" >&2
    rm -f "$LISTA"
    exit 1
  fi
  echo "$(date '+%F %T') transmitiendo $(wc -l < "$LISTA") videos"
  ffmpeg -hide_banner -loglevel warning -re -f concat -safe 0 -i "$LISTA" \
    -c:v copy -c:a aac -b:a 160k -ar 44100 -f flv "$DESTINO" || true
  rm -f "$LISTA"
  sleep 5
done
