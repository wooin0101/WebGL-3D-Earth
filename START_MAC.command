#!/bin/bash
cd "$(dirname "$0")" || exit 1
printf '\nEarth Terrain + Sea Depth — WebGL 1.0\n'
printf 'Open: http://127.0.0.1:9715/index.html\n'
printf 'Stop with Control+C\n\n'
python3 -m http.server 9715
