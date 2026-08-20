#!/usr/bin/env bash
# ==============================================================================
# Netools Suite - AppImage Builder Script
# Builds a standalone, zero-dependency x86_64 AppImage for Linux.
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

echo "==> [1/4] Building standalone binary with PyInstaller..."
# Ensure .venv has system-site-packages for gi/AppIndicator3
uv venv --clear --system-site-packages .venv
uv pip install pyinstaller customtkinter pystray pillow packaging

.venv/bin/pyinstaller \
  --name netools \
  --onefile \
  --collect-all netools \
  --collect-all pystray \
  --collect-all PIL \
  --hidden-import "pystray._appindicator" \
  --hidden-import "pystray._gtk" \
  --hidden-import "pystray._xorg" \
  --hidden-import "gi.repository.AppIndicator3" \
  --hidden-import "gi.repository.AyatanaAppIndicator3" \
  --hidden-import "gi.repository.Gtk" \
  --hidden-import "gi.repository.GLib" \
  --hidden-import "gi.repository.GObject" \
  --add-data "dns_jumper_db.py:." \
  --add-data "dns_jumper_benchmark.py:." \
  --add-data "assets:assets" \
  --clean \
  netools.py

echo "==> [2/4] Assembling AppDir..."
mkdir -p build/AppDir/usr/bin
mkdir -p build/AppDir/usr/share/applications

cp dist/netools build/AppDir/usr/bin/netools

cat << 'INNER_EOF' > build/AppDir/netools.desktop
[Desktop Entry]
Name=Netools Suite
Comment=Unified DNS Searcher, GRC Benchmark & Sing-box Proxy Rotator
Exec=netools gui
Icon=netools
Type=Application
Categories=Network;Utility;
Terminal=false
StartupNotify=true
INNER_EOF

cp build/AppDir/netools.desktop build/AppDir/usr/share/applications/netools.desktop

cat << 'INNER_EOF' > build/AppDir/AppRun
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:/usr/lib64:/usr/lib:${LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="/usr/lib64/girepository-1.0:/usr/lib/girepository-1.0:${GI_TYPELIB_PATH}"
if [ $# -eq 0 ]; then
    exec "${HERE}/usr/bin/netools" gui
else
    exec "${HERE}/usr/bin/netools" "$@"
fi
INNER_EOF
chmod +x build/AppDir/AppRun

# Generate App icon
python3 -c "
import struct, zlib
def make_png(w, h):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            if (w//4 < x < 3*w//4) and (h//4 < y < 3*h//4):
                raw.extend([137, 180, 250, 255])
            else:
                raw.extend([30, 30, 46, 255])
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
with open('build/AppDir/netools.png', 'wb') as f:
    f.write(make_png(128, 128))
"
cp build/AppDir/netools.png build/AppDir/.DirIcon

echo "==> [3/4] Downloading AppImage type 2 runtime..."
if [ ! -f build/runtime-x86_64 ]; then
    curl -sL -o build/runtime-x86_64 "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"
    chmod +x build/runtime-x86_64
fi

echo "==> [4/4] Creating SquashFS & Generating Netools-x86_64.AppImage..."
rm -f build/app.squashfs
rm -f dist/Netools-x86_64.AppImage
mksquashfs build/AppDir build/app.squashfs -root-owned -noappend -comp zstd
cat build/runtime-x86_64 build/app.squashfs > dist/Netools-x86_64.AppImage
chmod +x dist/Netools-x86_64.AppImage

echo "==> [DONE] Standalone AppImage created:"
ls -lh dist/Netools-x86_64.AppImage
