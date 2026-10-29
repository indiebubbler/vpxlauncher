#!/bin/bash
VPX_DIR="$HOME/Gry/VPinballX_BGFX-10.8.1-5436-af26b2d93-linux-x64-Release"
TABLES_DIR="$HOME/Gry/VPinballX_BGFX-10.8.1-5436-af26b2d93-linux-x64-Release/tables"   # <- zmień na folder, w którym trzymasz stoły .vpx

TABLE=$(kdialog --title "Visual Pinball X – wybierz stół" \
        --getopenfilename "$TABLES_DIR" "*.vpx|Stoły Visual Pinball (*.vpx)")

# Anulowano okno – nic nie uruchamiaj
[ -z "$TABLE" ] && exit 0

cd "$VPX_DIR" || exit 1

__NV_PRIME_RENDER_OFFLOAD=1 \
__GLX_VENDOR_LIBRARY_NAME=nvidia \
SDL_VIDEODRIVER=x11 \
./VPinballX_BGFX -play "$TABLE"
