<p align="center"><img src="packaging/icon-1024.png" width="128" alt=""></p>

<h1 align="center">Wasla · وصلة</h1>

<p align="center">Move WhatsApp from an Android phone to the iPhone you already use, <b>without erasing the iPhone</b>.<br>
Free, open source, step by step, in English and Arabic.<br>
<a href="https://abdullahyahya1.github.io/wasla/">Website</a> · <a href="https://github.com/AbdullahYahya1/wasla/releases/latest">Download for Mac</a></p>

---

WhatsApp's own Android → iPhone transfer only works while setting up a new or erased iPhone. If your iPhone
is already full of photos and apps, the official answer is to reset it. Wasla adds your Android chats to
the iPhone as it is: it backs up the iPhone to your Mac, adds the Android chats and media to WhatsApp's part
of that backup, and restores only WhatsApp's data.

Wasla is a desktop front end for [wamove](https://github.com/alicin/wamove) by alicin, which does the
format work. Wasla adds the guided window, live progress and time left, plain-language help for the things
that go wrong (keys read backwards on Arabic phones, charge-only cables, a greyed-out Find My switch),
much faster thumbnails, and an Undo button.

> [!IMPORTANT]
> Wasla is not made by or affiliated with WhatsApp, Meta or Apple. It relies on undocumented formats.
> Keep your Android phone as it is until you are happy with the result. Undo puts WhatsApp on the iPhone
> back as it was, and a full iPhone backup stays on your Mac.

## Install

1. Download `Wasla-1.0.0.dmg` from [Releases](https://github.com/AbdullahYahya1/wasla/releases/latest).
2. Open it and drag Wasla to Applications.
3. The first time, right-click Wasla in Applications and choose **Open**, then **Open** again. macOS asks this
   for apps that are not notarized by Apple yet.

## What you need

- A Mac with Apple silicon and macOS 12 or later (for Intel Macs, run from source)
- The Android phone with WhatsApp (not WhatsApp Business) and USB debugging turned on
- The iPhone with WhatsApp installed and set up with the same number
- A cable for each phone that carries data, not only charge
- Free space on the Mac for a full iPhone backup plus about twice your WhatsApp media

## The nine steps

1. **Welcome**: what happens and what stays safe.
2. **Connect**: live checks for both phones and the Mac's free space. Downloads Google's `adb` on first use.
3. **Backup key**: make a fresh end-to-end encrypted backup with a 64-digit key and type it in. Wasla tries
   both reading orders, because phones in Arabic lay the key grid out right to left.
4. **Copy from Android**: chats, contact names and media over the cable, with % and time left; then the chats
   are unlocked on the Mac.
5. **Get the iPhone ready**: WhatsApp installed and registered, Find My off (with help for a greyed-out
   switch), then Airplane mode on so nothing arrives between the backup and the restore.
6. **Back up the iPhone**: a full backup, with a banner when the iPhone asks for its passcode.
7. **Prepare**: the Android chats and media are added to WhatsApp's data. Thumbnails are made in parallel:
   28,444 took 27 seconds instead of about 20 minutes.
8. **Restore**: only WhatsApp's data goes back to the iPhone.
9. **Finish**: a checklist, storage before and after, then delete the private copies or Undo.

Nothing is uploaded. The 64-digit key stays in memory and is never written to disk.

## Run from source

```sh
brew install uv
git clone https://github.com/AbdullahYahya1/wasla && cd wasla
uv run wasla
```

Optional: `brew install ffmpeg` for video thumbnails. To build the app and disk image: `packaging/build.sh`
(signs with a Developer ID certificate if one is in the keychain; set `WASLA_NOTARY_PROFILE` to notarize).

The website is `site/index.html`; `tools/publish_site.sh` publishes it to GitHub Pages.

Developing: `uv run pytest` runs the tests; open `src/wasla/ui/index.html?demo=1` in a browser to click
through every screen with a pretend engine; `python tools/screens.py` screenshots them all in both languages.

## عربي

**وصلة** تنقل واتساب من جوال أندرويد إلى الآيفون الذي تستخدمه الآن **بدون مسح الآيفون**. مجانية ومفتوحة
المصدر، وتشرح كل خطوة بالعربي مع نسبة الإنجاز والوقت المتبقي. تأخذ نسخة احتياطية من الآيفون على الماك،
وتضيف محادثات ووسائط الأندرويد إلى بيانات واتساب فيها، ثم تستعيد بيانات واتساب فقط. صورك وتطبيقاتك
وإعداداتك تبقى كما هي، وتقدر تتراجع في أي وقت.

وصلة ليست من إنتاج واتساب أو ميتا أو أبل ولا تتبع لها.

## Credits and license

Built on [wamove](https://github.com/alicin/wamove) (GPL-3.0). Font: Readex Pro (SIL Open Font License).
Wasla is free software under the GNU General Public License v3 or later; see [LICENSE](LICENSE).
Made by [AbdullahYahya1](https://github.com/AbdullahYahya1).
