# Wasla (وصلة): design

Date: 2026-10-22
Status: approved by the founder in chat ("go with A", "do it, make sure it is the best")

## What it is

A free, open-source Mac app that moves WhatsApp chats and media from an Android phone to an iPhone that is
already set up, without erasing the iPhone. It is a friendly step-by-step front end for the
[wamove](https://github.com/alicin/wamove) engine (GPL-3.0), which we used by hand on 2026-10-21 to move
12 years of chats (1,783 chats, 558,855 messages, 23.7 GB of media) from a Motorola to an iPhone 17 Pro.

"وصلة" in Saudi Arabic is "a lift" (give someone a ride): Wasla gives your chats a lift to the iPhone.

## Decisions (made in chat)

- Mac first; Windows maybe later (only the Mac flow is tested).
- Free and open source on top of wamove, GPL-3.0-or-later, crediting wamove's author.
- Approach A: a pywebview window (WKWebView) with an HTML/CSS/JS UI, the engine in Python in the same process.
- A product website follows the app, in the same look (`site/`).

## Decisions (made during the build, changeable)

- Name: Wasla / وصلة. "Naqla" was taken by a Saudi truck-booking app.
- Arabic and English UI, Arabic shown first when the Mac's language is Arabic. RTL is a first-class layout.
- `adb` is not shipped inside the app: Google's platform-tools license does not allow redistribution.
  Wasla downloads the official zip from `dl.google.com` on first use into its own support folder
  (or uses an `adb` already on the Mac).
- `ffmpeg` (for video thumbnails) is optional: used if present; otherwise videos simply have no thumbnail.
  Shipping a static ffmpeg can come later.
- The 64-digit key is never written to disk. It stays in memory until the chats are decrypted.
- No Developer ID certificate exists on this Mac yet (only Apple Development / Distribution), so release
  builds are ad-hoc signed; notarizing needs a Developer ID Application certificate and a `notarytool`
  profile, both one-time steps for the founder. The website tells users how to open an un-notarized app.
- Nothing is uploaded anywhere; there is no analytics.

## Lessons from the real transfer that the app must handle

1. The key grid on an Arabic-language Android phone is laid out right to left. Reading it left to right
   gives a wrong key. Wasla tries both reading orders against a small encrypted file and keeps the one
   that opens it, so the user never has to know.
2. Many iPhone cables are charge-only. If no iPhone (or Android) shows up, say so and suggest another cable.
3. Find My must be off for a restore. When its switch is greyed out, the cause is usually Stolen Device
   Protection's one-hour security delay away from familiar places, or Screen Time restrictions.
   Show both, in the iPhone's own menu names.
4. Between the iPhone backup and the restore the iPhone must stay offline (Airplane mode on, Wi-Fi off),
   or messages received in between are lost.
5. The iPhone asks for its passcode at the start of a backup ("Please enter the device passcode").
   Show a big banner when that happens.
6. Registering WhatsApp on the iPhone signs the Android phone out, so the Android backup must be made
   (and copied) first.
7. Thumbnails were the slowest part of the build (28,444 thumbnails took ~20 minutes at ~23 per second,
   one `sips` process at a time). Wasla makes them in parallel first.
8. The restore shows "Restore in progress" on the iPhone and locks it until done; progress sits at 0% for
   a minute or two first. Tell the user this is normal.
9. After the restore the iPhone shows setup screens. Users fear it was erased; say up front that it was not
   and show used storage before/after.

## Screens

One window, about 1000 × 680. Left: the step list with a state icon and % for each step. Right: the
current step's card. Top bar: logo, language switch, "Help". The app remembers progress (state file) and
reopens on the right step.

0. **Welcome**: what Wasla does, what you need (both phones, a data cable for each, free space, ~1–2 hours),
   the promises ("Only WhatsApp changes on your iPhone", "You can undo"), and a note that Wasla is not made
   by or affiliated with WhatsApp or Meta.
1. **Connect**: a live checklist refreshed every 2 seconds: Android connected and USB debugging allowed
   (with the steps to turn it on), iPhone connected and trusted, enough free space on the Mac.
   adb is downloaded here if needed (with %).
2. **Android key**: turn on the end-to-end encrypted backup with a 64-digit key and tap Back up; Wasla shows
   the date of the newest backup on the phone and warns if it is older than an hour. Then 16 boxes of 4
   characters (paste fills them all). On "Check key" Wasla copies a small encrypted file and tries both
   reading orders; a green tick says "Key works".
3. **Copy from Android**: copies the chat backup, contact names and media with % (bytes copied / bytes on
   the phone), speed and time left; then decrypts and shows a summary: chats, groups, messages, media,
   first and last message date.
4. **Get the iPhone ready**: install WhatsApp from the App Store and register the same number (warning:
   this signs the Android phone out, which is fine now). Wasla checks that WhatsApp is installed and that
   Find My is off, live. Greyed-out help. Then "Open WhatsApp once, then turn on Airplane mode and turn off
   Wi-Fi", confirmed with a checkbox.
5. **Back up the iPhone**: full backup with %, the passcode banner, then the WhatsApp-only copy.
   Shows the iPhone's used storage.
6. **Prepare**: thumbnails (parallel) → chats → media into the restore copy, one overall % with time left
   and the current phase; ends with what was added (chats created/merged, messages, media found/missing).
7. **Restore**: a confirm card ("Only WhatsApp's data on your iPhone changes; your photos and other apps stay"),
   then % and "The iPhone is restarting".
8. **Finish**: a checklist (finish the setup screens, turn off Airplane mode, open WhatsApp and re-download it
   if its icon is faded, open a group and scroll up, turn Find My back on), the used-storage comparison,
   and two buttons: "It worked" (delete the private copies on this Mac, keeping or deleting the iPhone
   backup by choice) and "Something's wrong" (Undo: restore the untouched WhatsApp copy).

Errors show as a red card on the step with a plain explanation and the one thing to do, plus "Try again".

## Architecture

```
src/wasla/
  __main__.py        entry point
  app.py             pywebview window, the JS bridge (Api), event pump
  bridge.py          Api: methods the UI calls; runs jobs on a worker thread
  events.py          Event types and a thread-safe emitter (throttled to ~8/s per step)
  state.py           state.json in the work folder: steps done, stats, timestamps
  progress.py        rate/ETA estimator (exponential moving average)
  errors.py          maps engine exceptions to friendly error codes (+ i18n keys)
  engine/
    checks.py        android/iphone/disk/find-my/whatsapp-installed checks, structured
    adbtool.py       find or download adb (platform-tools) with progress
    keygrid.py       normalize a key, candidate reading orders, test against a small crypt15 file
    android.py       pull with byte progress, decrypt, summary
    iphone.py        backup/restore/rollback with progress and passcode detection
    build.py         parallel thumbnails, import with progress, media copy with progress
  ui/
    index.html, app.css, app.js, i18n.js, strings/en.json, strings/ar.json, img/*.svg
tests/
packaging/            PyInstaller spec, build script, dmg script
site/                 the website
```

The UI is plain HTML/CSS/JS with no framework or build step, so the app and the site share CSS.
The UI calls `window.pywebview.api.*`; the engine pushes events to the UI through
`window.evaluate_js("wasla.onEvent(...)")`. The same UI runs in a normal browser with a fake API
(`?demo=1`), which is how screens are tested and screenshotted.

The engine uses wamove's modules (crypt15, msgstore, chatstorage, ios backup) directly, pinned to a commit,
and replaces wamove's command-line orchestration with its own functions that report progress. Where
wamove has no hook (thumbnails, per-chat import, adb pull), Wasla wraps it without editing wamove:
a `Writer` subclass, a thumbnail cache filled in parallel, and polling of bytes copied.

## Testing

- Unit tests: key reading orders and checking (with a real crypt15 made from a known key), ETA,
  state, error mapping, i18n completeness (every key in both languages), thumbnail cache, import progress
  (on a small synthetic ChatStorage built from wamove's own test fixtures if present, otherwise a minimal one).
- Engine checks run read-only against the connected iPhone.
- UI: every screen and state in demo mode, screenshotted in English and Arabic, light and dark.
- The full transfer is not re-run on the founder's phones (it changes the phone); the engine code paths
  mirror wamove's, which ran end to end on 2026-10-21.

## Out of scope for v1

Windows, WhatsApp Business, iPhone → Android, shipping ffmpeg, auto-update. (If the iPhone encrypts its
backups, the backup step asks for that password in a field and keeps it in memory only.)
