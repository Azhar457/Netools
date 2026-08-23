#!/usr/bin/env bash
# ==============================================================================
# Netools Suite - AppImage Builder Script
# Builds a standalone, zero-dependency x86_64 AppImage for Linux.
# Bundles GI/Gtk for a working system-tray (pystray AppIndicator backend).
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

echo "==> [1/4] Preparing build environment..."
if [ ! -d ".venv" ]; then
    uv venv .venv
fi
uv pip install pyinstaller customtkinter pystray pillow packaging

echo "==> [2/4] Compiling lean onedir bundle with PyInstaller..."
rm -rf dist/netools build/netools build/AppDir
.venv/bin/pyinstaller -y --clean netools.spec

# Prune heavy unused CJK multibyte codecs
rm -f dist/netools/_internal/python3.*/lib-dynload/_codecs_*.so 2>/dev/null || true

# Prune Tcl timezone & locale translation databases and unused encodings
rm -rf dist/netools/_internal/tcl*/tzdata \
       dist/netools/_internal/tcl*/msgs \
       dist/netools/_internal/tk*/msgs \
       dist/netools/_internal/tcl*/encoding/iso8859* \
       dist/netools/_internal/tcl*/encoding/ebcdic* \
       dist/netools/_internal/tcl*/encoding/jis* \
       dist/netools/_internal/tcl*/encoding/mac* \
       dist/netools/_internal/tcl*/encoding/koi* \
       dist/netools/_internal/tcl*/encoding/cp[0-7]* \
       dist/netools/_internal/tcl*/encoding/cp8[0-6]* \
       dist/netools/_internal/tcl*/encoding/cp87* \
       dist/netools/_internal/tcl*/encoding/cp9* 2>/dev/null || true

# Prune unneeded static assets (keep essential icon-256 and logo)
rm -f dist/netools/_internal/assets/icon-512.png dist/netools/_internal/assets/logo.png 2>/dev/null || true



echo "==> [3/4] Assembling AppDir..."
mkdir -p build/AppDir/usr/bin
mkdir -p build/AppDir/usr/share/applications

cp -r dist/netools build/AppDir/usr/bin/

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
export PATH="${HERE}/usr/bin/netools:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin/netools:${HERE}/usr/bin/netools/_internal:${HERE}/usr/bin/netools/_internal/lib:${LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="${HERE}/usr/bin/netools/_internal/gi_typelibs:/usr/lib64/girepository-1.0:/usr/lib/x86_64-linux-gnu/girepository-1.0:/usr/lib/girepository-1.0:${GI_TYPELIB_PATH}"
if [ $# -eq 0 ]; then
    exec "${HERE}/usr/bin/netools/netools" gui
else
    exec "${HERE}/usr/bin/netools/netools" "$@"
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

if [ ! -f build/runtime-x86_64 ]; then
    echo "==> Downloading AppImage type 2 runtime..."
    curl -sL -o build/runtime-x86_64 "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"
    chmod +x build/runtime-x86_64
fi

echo "==> [4/4] Creating SquashFS & Generating Netools-x86_64.AppImage..."
rm -f build/app.squashfs dist/Netools-x86_64.AppImage
mksquashfs build/AppDir build/app.squashfs -root-owned -noappend -b 1048576 -comp zstd -Xcompression-level 22
cat build/runtime-x86_64 build/app.squashfs > dist/Netools-x86_64.AppImage
chmod +x dist/Netools-x86_64.AppImage

# Clean intermediate directories to keep dist/ tidy
rm -rf dist/netools

echo "==> [DONE] Standalone AppImage created (system-tray enabled):"
ls -lh dist/Netools-x86_64.AppImage


