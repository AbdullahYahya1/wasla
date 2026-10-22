#!/bin/sh
# Build dist/Wasla.app and dist/Wasla-<version>.dmg.
# Signs with a "Developer ID Application" certificate when one is in the keychain (and notarizes when
# WASLA_NOTARY_PROFILE names a notarytool profile); otherwise the app is ad-hoc signed.
set -eu
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
rm -rf build dist
uv run pyinstaller packaging/wasla.spec --noconfirm --distpath dist --workpath build/pyinstaller
APP=dist/Wasla.app
IDENTITY=$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' | head -1)
if [ -n "$IDENTITY" ]; then
  codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$APP"
else
  codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict "$APP"
STAGE=build/dmg
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="dist/Wasla-$VERSION.dmg"
hdiutil create -volname "Wasla" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
if [ -n "$IDENTITY" ]; then codesign --sign "$IDENTITY" --timestamp "$DMG"; fi
if [ -n "$IDENTITY" ] && [ -n "${WASLA_NOTARY_PROFILE:-}" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$WASLA_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi
du -sh "$APP" "$DMG"
