#!/bin/bash
# Lance le générateur (installe les dépendances la première fois).
#   ./lancer.sh                       -> reel vertical 9:16 du jour
#   ./lancer.sh --date 2026-12-25     -> une date précise
#   ./lancer.sh --format both         -> vertical + horizontal
cd "$(dirname "$0")" || exit 1
if [ ! -d .venv ]; then
  echo "Installation (première fois)…"
  python3 -m venv .venv && .venv/bin/pip -q install pillow imageio-ffmpeg || exit 1
fi
exec .venv/bin/python generer_video.py "$@"
