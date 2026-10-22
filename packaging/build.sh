#!/bin/sh
# Build dist/Wasla.app and dist/Wasla-<version>.dmg.
# Signs with a "Developer ID Application" certificate when one is in the keychain (and notarizes when
# WASLA_NOTARY_PROFILE names a notarytool profile); otherwise the app is ad-hoc signed.
# One-time setup for notarizing: create the certificate (Xcode > Settings > Accounts > Manage Certificates >
# + > Developer ID Application), then: xcrun notarytool store-credentials wasla --apple-id <email>
#   --team-id <TEAM> --password <app-specific password from appleid.apple.com>
# and build with: WASLA_NOTARY_PROFILE=wasla packaging/build.sh
#
# WASLA_ARCH=intel builds the Intel version from .venv-intel, an x86_64 environment made once with:
#   uv python install cpython-3.13-macos-x86_64-none
#   UV_PROJECT_ENVIRONMENT=.venv-intel uv sync --python "$(uv python find cpython-3.13-macos-x86_64-none)"
#   uv pip install --python .venv-intel/bin/python "cryptography==48.0.1"   # newer ones ship no Intel Mac build
set -eu
cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
if [ "${WASLA_ARCH:-arm64}" = intel ]; then
  DIST=dist-intel; SUFFIX=-intel; WORK=build/intel
  rm -rf "$DIST" "$WORK"
  arch -x86_64 .venv-intel/bin/pyinstaller packaging/wasla.spec --noconfirm --distpath "$DIST" --workpath "$WORK"
else
  DIST=dist; SUFFIX=; WORK=build/pyinstaller
  rm -rf "$DIST" "$WORK"
  uv run pyinstaller packaging/wasla.spec --noconfirm --distpath "$DIST" --workpath "$WORK"
fi
APP=$DIST/Wasla.app
IDENTITY=$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' | head -1)
if [ -n "$IDENTITY" ]; then
  codesign --force --deep --options runtime --timestamp --entitlements packaging/entitlements.plist \
    --sign "$IDENTITY" "$APP"
else
  codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict "$APP"
STAGE=build/dmg$SUFFIX
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="$DIST/Wasla-$VERSION$SUFFIX.dmg"
hdiutil create -volname "Wasla" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
if [ -n "$IDENTITY" ]; then codesign --sign "$IDENTITY" --timestamp "$DMG"; fi
if [ -n "$IDENTITY" ] && [ -n "${WASLA_NOTARY_PROFILE:-}" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$WASLA_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
  spctl --assess --type open --context context:primary-signature -v "$DMG"
fi
du -sh "$APP" "$DMG"
