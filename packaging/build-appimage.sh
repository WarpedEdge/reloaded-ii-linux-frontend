#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${APPIMAGETOOL:?Set APPIMAGETOOL to a verified appimagetool executable}"
RLM_LIBARCHIVE="$(python -c 'import ctypes.util; from PyInstaller.depend.bindepend import resolve_library_path; print(resolve_library_path(ctypes.util.find_library("archive")) or "")')"
if [ ! -f "$RLM_LIBARCHIVE" ]; then
    echo 'Build requires libarchive.so.13 on the build host' >&2
    exit 1
fi
python -m PyInstaller --noconfirm --clean --windowed --name reloaded-linux-manager \
    --collect-all libarchive --collect-all vdf --add-binary "$RLM_LIBARCHIVE:." \
    --runtime-hook packaging/runtime-hook.py --add-data "packaging/reloaded-linux-manager.png:." packaging/entry.py
rm -rf AppDir
mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons/hicolor/512x512/apps
cp -a dist/reloaded-linux-manager/. AppDir/usr/bin/
cp packaging/reloaded-linux-manager.desktop AppDir/
cp packaging/reloaded-linux-manager.desktop AppDir/usr/share/applications/
cp packaging/reloaded-linux-manager.png AppDir/
cp packaging/reloaded-linux-manager.png AppDir/usr/share/icons/hicolor/512x512/apps/
cat > AppDir/AppRun <<'RUN'
#!/bin/sh
APPDIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$APPDIR/usr/bin/reloaded-linux-manager" "$@"
RUN
chmod +x AppDir/AppRun
RLM_OUTPUT="$(mktemp dist/Reloaded-Linux-Manager-build-XXXXXX.AppImage)"
trap 'rm -f "$RLM_OUTPUT"' EXIT
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run AppDir "$RLM_OUTPUT"
mv -f "$RLM_OUTPUT" dist/Reloaded-Linux-Manager-x86_64.AppImage
sha256sum dist/Reloaded-Linux-Manager-x86_64.AppImage > dist/SHA256SUMS
