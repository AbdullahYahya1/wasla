/* Wasla window: renders the nine steps from the engine's state and live events. */
(() => {
  "use strict";
  const STEPS = ["welcome", "connect", "key", "copy", "ready", "backup", "prepare", "restore", "finish"];
  const JOB_STEPS = ["key", "copy", "backup", "prepare", "restore", "undo", "adb"];
  const FOLDERS = {
    "WhatsApp Images": "images", "WhatsApp Video": "video", "WhatsApp Voice Notes": "voice",
    "WhatsApp Audio": "audio", "WhatsApp Documents": "documents", "WhatsApp Animated Gifs": "gifs",
    "WhatsApp Stickers": "stickers", "WhatsApp Video Notes": "videonotes",
  };
  const PREPARE_PHASES = ["read", "thumbnails", "chats", "media", "check"];
  const ISSUES = "https://github.com/kerneltics/wasla/issues";
  const STORE = "https://apps.apple.com/app/whatsapp-messenger/id310633997";
  const I = window.WASLA_ICONS;

  const S = {
    lang: "en",
    state: { steps: {}, current: "welcome", busy: null, has_key: false, version: "" },
    view: "welcome",
    live: {},          // step -> {pct, eta, phase, data, need}
    errors: {},        // step -> {code, ...}
    checks: {},        // latest check results
    ui: { open: {}, ticks: {}, keyResult: null, password: "" },
    pollTimer: null,
  };

  // ---------- helpers ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function t(key, vars = {}) {
    const table = window.WASLA_STRINGS[S.lang] || window.WASLA_STRINGS.en;
    let text = table[key] ?? window.WASLA_STRINGS.en[key] ?? key;
    for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, v);
    return text;
  }
  const num = (n) => Number(n || 0).toLocaleString(S.lang === "ar" ? "ar-SA-u-nu-latn" : "en-US");
  const gb = (bytes) => t("common.gb", { n: (bytes / 1e9).toFixed(bytes >= 1e10 ? 0 : 1) });
  const size = (bytes) => bytes >= 1e9 ? gb(bytes) : t("common.mb", { n: Math.max(1, Math.round(bytes / 1e6)) });
  function eta(seconds) {
    if (seconds == null) return t("common.calculating");
    if (seconds < 60) return t("common.under_min");
    if (seconds < 3600) return t("common.min_left", { n: Math.ceil(seconds / 60) });
    const h = Math.floor(seconds / 3600);
    return t("common.hours_left", { h, m: Math.round((seconds % 3600) / 60) });
  }
  function age(seconds) {
    if (seconds == null) return "";
    if (seconds < 90) return t("common.just_now");
    if (seconds < 5400) return t("common.age_min", { n: Math.round(seconds / 60) });
    if (seconds < 172800) return t("common.age_hours", { n: Math.round(seconds / 3600) });
    return t("common.age_days", { n: Math.round(seconds / 86400) });
  }
  const api = () => window.pywebview && window.pywebview.api;
  async function call(name, ...args) {
    try { return await api()[name](...args); } catch (e) { console.error(name, e); return null; }
  }
  const done = (step) => Boolean(S.state.steps[step]);
  const busy = () => S.state.busy;

  // ---------- events from the engine ----------
  function onEvent(e) {
    const step = e.step;
    if (e.kind === "progress") {
      S.live[step] = { ...(S.live[step] || {}), pct: e.pct, eta: e.eta_s, phase: e.phase, data: e.data || {}, running: true };
      updateLive();
      updateRoute();
    } else if (e.kind === "need") {
      S.live[step] = { ...(S.live[step] || {}), need: e.data.what, running: true };
      updateLive();
    } else if (e.kind === "clear") {
      if (S.live[step]) S.live[step].need = null;
      updateLive();
    } else if (e.kind === "done") {
      S.live[step] = { ...(S.live[step] || {}), pct: 100, running: false, need: null, result: e.data };
      if (step === "key") S.ui.keyResult = e.data;
      if (step === "adb") refreshChecks();
      refresh().then(() => {
        if (step === "restore") go("finish");
        else render();
      });
    } else if (e.kind === "error") {
      if (S.live[step]) { S.live[step].running = false; S.live[step].need = null; }
      S.errors[step === "adb" ? "connect" : step] = e.data;
      refresh().then(render);
    }
  }

  async function refresh() {
    const state = await call("get_state");
    if (state) S.state = state;
  }

  // ---------- frame ----------
  function applyLang() {
    document.documentElement.lang = S.lang;
    document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === S.lang)));
    $("#brand").innerHTML = `${I.logo}<span>${esc(t("app.name"))}</span><small>${esc(t("app.tagline"))}</small>`;
    $("#help-btn").textContent = t("bar.help");
    document.title = t("app.name");
  }

  function routeHtml() {
    return STEPS.map((step, i) => {
      const live = S.live[step];
      const classes = ["stop"];
      if (done(step)) classes.push("done");
      if (step === S.view) classes.push("here");
      if (S.errors[step]) classes.push("failed");
      const pct = live && live.running && live.pct != null ? `${Math.floor(live.pct)}%` : "";
      const reachable = done(step) || step === S.state.current;
      const label = `<span class="label">${esc(t(`steps.${step}`))}</span>`;
      return `<li class="${classes.join(" ")}">
        <span class="dot">${done(step) ? I.check : ""}</span>
        ${reachable && !busy() ? `<button type="button" data-go="${step}" aria-current="${step === S.view ? "step" : "false"}">${label}</button>` : label}
        <span class="pct">${pct}</span>
      </li>`;
    }).join("");
  }
  function updateRoute() { $("#route").innerHTML = routeHtml(); }

  // ---------- shared pieces ----------
  function checkRow(id, state, icon, title, sub, side = "", extra = "") {
    return `<div class="check ${state}" id="${id}">
      <div class="ic">${state === "busy" ? '<div class="spin"></div>' : icon}</div>
      <div><p class="title">${title}</p>${sub ? `<p class="sub">${sub}</p>` : ""}${extra}</div>
      <div class="side">${side}</div>
    </div>`;
  }
  function details(id, summary, body) {
    return `<details data-open="${id}" ${S.ui.open[id] ? "open" : ""}><summary>${esc(summary)}</summary>${body}</details>`;
  }
  function list(items) { return `<ol class="howto">${items.map((k) => `<li>${esc(t(k))}</li>`).join("")}</ol>`; }

  function encrypted() {
    return Boolean((S.state.steps.backup || {}).encrypted || ((S.checks.connect || {}).iphone || {}).encrypted);
  }
  function needsPassword(step) {
    const code = (S.errors[step] || {}).code || "";
    return (encrypted() && !S.state.has_password) || code.startsWith("password_");
  }
  function passwordField(step) {
    if (!needsPassword(step) || (S.live[step] || {}).running) return "";
    return `<h2>${esc(t("backup.password_title"))}</h2><p class="muted small">${esc(t("backup.password_sub"))}</p>
      <label class="field"><span>${esc(t("backup.password"))}</span><input type="password" id="pw" autocomplete="off"></label>`;
  }

  function errorCard(step) {
    const err = S.errors[step];
    if (!err) return "";
    const vars = {};
    if (err.code === "no_space" && err.needed) vars.gb = gb(Math.max(err.needed - (err.free || 0), 1e9));
    const detail = err.detail || err.trace;
    return `<div class="error" role="alert">
      <h2>${esc(t("error.title"))}</h2>
      <p>${esc(t(`error.${err.code}`, vars))}</p>
      ${detail ? details("err-" + step, t("common.details"), `<pre>${esc(detail)}</pre>
        <p><button type="button" class="btn quiet small" data-act="copy-detail">${esc(t("common.copy_details"))}</button>
        <button type="button" class="btn quiet small" data-url="${ISSUES}">${esc(t("error.report"))}</button></p>`) : ""}
    </div>`;
  }

  const END = {
    android: () => I.android.replace("<svg", '<svg class="end"'),
    mac: () => I.mac.replace("<svg", '<svg class="end"'),
    iphone: () => I.iphone.replace("<svg", '<svg class="end ios"'),
  };
  function trip(step, opts = {}) {
    const live = S.live[step] || {};
    const pct = live.pct;
    const indeterminate = pct == null;
    const from = opts.from || "android", to = opts.to || "iphone";
    return `<section class="trip" aria-live="polite">
      <div class="trip-top">
        ${indeterminate ? '<div class="spin big-spin"></div>' : `<div class="big">${Math.floor(pct)}<small>%</small></div>`}
        <div class="eta">${indeterminate ? "" : esc(eta(live.eta))}</div>
      </div>
      <p class="phase">${esc(opts.phase || "")}</p>
      ${opts.sub ? `<p class="phase-sub">${esc(opts.sub)}</p>` : ""}
      <div class="road-line">
        <span>${END[from]()}</span>
        <div class="lane ${indeterminate ? "indeterminate" : ""}" role="progressbar" aria-valuemin="0" aria-valuemax="100" ${indeterminate ? "" : `aria-valuenow="${Math.floor(pct)}"`}>
          <div class="fill" style="width:${indeterminate ? 30 : pct}%"></div>
          <div class="car" style="inset-inline-start:${indeterminate ? 0 : pct}%"></div>
        </div>
        <span>${END[to]()}</span>
      </div>
      ${opts.phases || ""}
    </section>`;
  }

  function stats(rows) {
    rows = rows.filter(Boolean);
    return `<div class="stats" style="grid-template-columns:repeat(${Math.min(rows.length, 5)},minmax(0,1fr))">${rows.map(([value, label]) =>
      `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join("")}</div>`;
  }

  // ---------- steps ----------
  const views = {};

  views.welcome = () => ({
    body: `
      <div class="journey-hero" aria-hidden="true">
        <div><div class="phone-ic">${I.phonebig(false)}</div><div class="phone-label">${esc(t("common.android"))}</div></div>
        <div class="road"></div>
        <div><div class="phone-ic ios">${I.phonebig(true)}</div><div class="phone-label">${esc(t("common.iphone"))}</div></div>
      </div>
      <div class="facts">
        <div><h2>${esc(t("welcome.need_title"))}</h2>
          <ul class="ticks need">${["need_phones", "need_cables", "need_space", "need_time"].map((k) =>
            `<li>${I.check}<span>${esc(t("welcome." + k))}</span></li>`).join("")}</ul></div>
        <div><h2>${esc(t("welcome.promise_title"))}</h2>
          <ul class="ticks">${["promise_iphone", "promise_android", "promise_undo", "promise_private"].map((k) =>
            `<li>${I.shield}<span>${esc(t("welcome." + k))}</span></li>`).join("")}</ul></div>
      </div>
      <p class="note">${esc(t("welcome.disclaimer"))}</p>`,
    actions: `<button type="button" class="btn" data-act="mark" data-step="welcome">${esc(t("welcome.start"))}</button>`,
  });

  views.connect = () => {
    const c = S.checks.connect || {};
    const a = c.android || {}, p = c.iphone || {}, d = c.disk || {};
    const live = S.live.adb;
    let androidRow;
    if (!c.android) androidRow = checkRow("ck-android", "busy", "", esc(t("connect.android")), esc(t("common.checking")));
    else if (a.state === "no_adb") {
      const getting = live && live.running;
      androidRow = checkRow("ck-android", "wait", I.android, esc(t("connect.android")), esc(t("connect.no_adb")),
        getting ? `<span class="small muted">${esc(t("connect.getting_adb", { pct: Math.floor(live.pct || 0) }))}</span>`
          : `<button type="button" class="btn small" data-act="adb">${esc(t("connect.get_adb"))}</button>`);
    } else if (a.state === "ready") {
      androidRow = checkRow("ck-android", "ok", I.android, esc(t("connect.android")), esc(t("connect.android_ready", { model: a.model })));
    } else {
      const sub = { unauthorized: "connect.android_unauthorized", offline: "connect.android_offline", several: "connect.android_several" }[a.state] || "connect.android_missing";
      androidRow = checkRow("ck-android", "wait", I.android, esc(t("connect.android")), esc(t(sub)), "",
        details("usb", t("connect.howto_usb"), list(["connect.usb_1", "connect.usb_2", "connect.usb_3", "connect.usb_4"]) + `<p class="small muted">${esc(t("connect.usb_note"))}</p>`));
    }
    let iphoneRow;
    if (!c.iphone) iphoneRow = checkRow("ck-iphone", "busy", "", esc(t("connect.iphone")), esc(t("common.checking")));
    else if (p.state === "ready") iphoneRow = checkRow("ck-iphone", "ok", I.iphone, esc(t("connect.iphone")), esc(t("connect.iphone_ready", { name: p.name, ios: p.ios })));
    else iphoneRow = checkRow("ck-iphone", "wait", I.iphone, esc(t("connect.iphone")),
      esc(t(p.state === "untrusted" ? "connect.iphone_untrusted" : "connect.iphone_missing")), "",
      `<p class="small muted" style="margin-top:8px">${esc(t("connect.cable_tip"))}</p>`);
    const low = d.free_bytes != null && p.used_bytes && d.free_bytes < p.used_bytes * 1.6;
    const diskRow = d.free_bytes == null
      ? checkRow("ck-disk", "busy", "", esc(t("connect.disk")), "")
      : checkRow("ck-disk", low ? "wait" : "ok", I.disk, esc(t("connect.disk")),
        esc(low ? t("connect.disk_low", { gb: gb(d.free_bytes) }) : t("connect.disk_free", { gb: gb(d.free_bytes) })));
    const ready = a.state === "ready" && p.state === "ready";
    return {
      body: `${errorCard("connect")}<div class="checks" id="live">${androidRow}${iphoneRow}${diskRow}</div>`,
      actions: `<button type="button" class="btn" data-act="mark" data-step="connect" ${ready ? "" : "disabled"}>${esc(t("common.continue"))}</button>`,
      poll: "connect",
    };
  };

  views.key = () => {
    const a = (S.checks.connect || {}).android || {};
    let backupLine = "";
    if (a.state === "ready") {
      if (a.backup === "ok" && a.backup_age_s != null) {
        const old = a.backup_age_s > 3600;
        backupLine = `<p class="status-line ${old ? "bad" : "ok"}">${old ? I.warn : I.check}<span>${esc(old ? t("key.backup_old", { age: age(a.backup_age_s) }) : t("key.backup_fresh", { age: age(a.backup_age_s) }))}</span></p>`;
      } else if (a.backup === "old_format") backupLine = `<p class="status-line bad">${I.warn}<span>${esc(t("key.backup_oldformat"))}</span></p>`;
      else if (a.backup === "none") backupLine = `<p class="status-line bad">${I.warn}<span>${esc(t("key.backup_none"))}</span></p>`;
    }
    const live = S.live.key || {};
    const result = S.ui.keyResult || (done("key") ? S.state.steps.key : null);
    const checking = live.running;
    let status = "";
    if (checking) status = `<p class="status-line"><span class="spin"></span><span>${esc(t("key.checking"))}</span></p>`;
    else if (result && S.state.has_key) status = `<p class="status-line ok">${I.check}<span>${esc(t(result.order === "rows_rtl" ? "key.ok_rtl" : "key.ok"))}</span></p>`;
    const keyOk = Boolean(result && S.state.has_key);
    const boxes = Array.from({ length: 16 }, (_, i) =>
      `<input inputmode="latin" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="200" aria-label="${i + 1}" data-key="${i}" value="${esc((S.ui.keyBoxes || [])[i] || "")}">`).join("");
    return {
      body: `${errorCard("key")}<div class="split">
        <div>
        <h2>${esc(t("key.how_title"))}</h2>
        ${list(["key.how_1", "key.how_2", "key.how_3"])}
        <p class="small muted">${esc(t("key.already"))}</p>
        <div id="live">${backupLine}</div>
        </div><div>
        <h2>${esc(t("key.enter_title"))}</h2>
        <p class="muted small">${esc(t("key.enter_sub"))}</p>
        <div class="keygrid ${keyOk ? "ok" : S.errors.key ? "bad" : ""}" id="keygrid" dir="${S.lang === "ar" ? "rtl" : "ltr"}">${boxes}</div>
        <div id="key-status">${status}</div>
        <p class="small muted">${I.lock.replace("<svg", '<svg style="width:15px;height:15px;vertical-align:-2px"')} ${esc(t("key.privacy"))}</p>
        </div></div>`,
      actions: keyOk
        ? `<button type="button" class="btn quiet" data-act="check-key">${esc(t("key.check"))}</button><button type="button" class="btn" data-go="copy">${esc(t("common.continue"))}</button>`
        : `<button type="button" class="btn" data-act="check-key" ${checking ? "disabled" : ""}>${esc(t("key.check"))}</button>`,
      poll: "connect",
    };
  };

  function copyPhase(live) {
    const p = live.phase;
    if (p === "chats") return [t("copy.phase_chats"), ""];
    if (p === "decrypt") return [t("copy.phase_decrypt"), ""];
    if (p === "read") return [t("copy.phase_read"), ""];
    const d = live.data || {};
    const folder = FOLDERS[p] ? t("copy.f_" + FOLDERS[p]) : "";
    const bytes = d.total_bytes ? t("common.of", { a: size(d.done_bytes || 0), b: size(d.total_bytes) }) : "";
    return [t("copy.phase_media"), [folder, bytes].filter(Boolean).join(S.lang === "ar" ? "، " : ", ")];
  }

  views.copy = () => {
    const live = S.live.copy || {};
    const result = done("copy") ? S.state.steps.copy : null;
    if (result && !live.running) {
      const year = result.first_ms ? new Date(result.first_ms).getFullYear() : "";
      return {
        body: `<h2>${esc(t("copy.summary_title"))}</h2>
          ${stats([[num(result.chats), t("copy.s_chats")], [num(result.groups), t("copy.s_groups")],
            [num(result.messages), t("copy.s_messages")], [num(result.media), t("copy.s_media")],
            year && [String(year), t("copy.s_since")]])}
          <div class="callout"><p>${esc(t("copy.note_next"))}</p></div>`,
        actions: `<button type="button" class="btn" data-go="ready">${esc(t("common.continue"))}</button>`,
      };
    }
    const needKey = !S.state.has_key;
    const [phase, sub] = copyPhase(live);
    return {
      body: `${errorCard("copy")}${needKey && !live.running ? `<div class="error"><p>${esc(t("error.key_missing"))}</p></div>` : ""}
        <div id="live">${live.running ? trip("copy", { phase, sub, from: "android", to: "mac" }) : ""}</div>`,
      actions: live.running
        ? `<button type="button" class="btn quiet" data-act="cancel">${esc(t("common.stop"))}</button>`
        : needKey ? `<button type="button" class="btn" data-act="back-to" data-step="key">${esc(t("steps.key"))}</button>`
          : `<button type="button" class="btn" data-act="start" data-step="copy">${esc(t("copy.start"))}</button>`,
    };
  };

  views.ready = () => {
    const c = S.checks.ready || {};
    const p = c.iphone || {};
    const ticks = S.ui.ticks;
    // When the iPhone can't tell us (older iOS, a hiccup), the person confirms it instead of getting stuck.
    const waUnknown = Boolean(c.iphone) && p.state === "ready" && p.whatsapp == null;
    const fmUnknown = Boolean(c.iphone) && p.state === "ready" && p.find_my == null;
    const waOk = p.whatsapp === true || (waUnknown && ticks.wa);
    const fmOk = p.find_my === false || (fmUnknown && ticks.fm);
    const confirm = (tick) => `<label class="manual below"><input type="checkbox" data-tick="${tick}" ${ticks[tick] ? "checked" : ""}>${esc(t("ready.register_done"))}</label>`;
    const waRow = !c.iphone ? checkRow("ck-wa", "busy", "", esc(t("ready.wa")), esc(t("common.checking")))
      : checkRow("ck-wa", waOk ? "ok" : "wait", I.chat, esc(t("ready.wa")),
        waOk && !waUnknown ? "" : esc(t(p.whatsapp_business ? "ready.wa_business" : "ready.wa_missing")),
        waOk ? "" : `<button type="button" class="btn small quiet" data-url="${STORE}">${esc(t("ready.open_store"))}</button>`,
        waUnknown ? confirm("wa") : "");
    const regRow = checkRow("ck-reg", ticks.register ? "ok" : "wait", I.key, esc(t("ready.register")), esc(t("ready.register_sub")), "",
      `<label class="manual below"><input type="checkbox" data-tick="register" ${ticks.register ? "checked" : ""}>${esc(t("ready.register_done"))}</label>`);
    const fmRow = !c.iphone ? checkRow("ck-fm", "busy", "", esc(t("ready.findmy")), "")
      : checkRow("ck-fm", fmOk ? "ok" : "wait", I.pin, esc(t("ready.findmy")), fmOk && !fmUnknown ? "" : esc(t("ready.findmy_on")), "",
        (fmOk ? "" : details("grey", t("ready.findmy_grey"), list(["ready.grey_1", "ready.grey_2", "ready.grey_3"]))) + (fmUnknown ? confirm("fm") : ""));
    const offRow = checkRow("ck-off", ticks.offline ? "ok" : "wait", I.plane, esc(t("ready.offline")), esc(t("ready.offline_sub")), "",
      `<label class="manual below"><input type="checkbox" data-tick="offline" ${ticks.offline ? "checked" : ""}>${esc(t("ready.offline_done"))}</label>`);
    const all = waOk && fmOk && ticks.register && ticks.offline;
    return {
      body: `<div class="checks" id="live">${waRow}${regRow}${fmRow}${offRow}</div>`,
      actions: `<button type="button" class="btn" data-act="mark" data-step="ready" ${all ? "" : "disabled"}>${esc(t("common.continue"))}</button>`,
      poll: "ready",
    };
  };

  views.backup = () => {
    const live = S.live.backup || {};
    const result = done("backup") ? S.state.steps.backup : null;
    const banner = live.need === "passcode" ? `<div class="banner attention" role="alert"><div class="ic">${I.lock}</div><div><strong>${esc(t("backup.passcode"))}</strong><span class="muted">${esc(t("backup.passcode_sub"))}</span></div></div>` : "";
    if (result && !live.running) {
      return {
        body: `<div class="banner"><div class="ic">${I.check}</div><div><strong>${esc(t("backup.done"))}</strong><span>${esc(t("backup.keep_offline"))}</span></div></div>`,
        actions: `<button type="button" class="btn" data-go="prepare">${esc(t("common.continue"))}</button>`,
      };
    }
    const phase = live.phase === "copy" ? t("backup.phase_copy") : t("backup.phase_phone");
    const pw = passwordField("backup");
    return {
      body: `${errorCard("backup")}<div id="live">${banner}${live.running ? trip("backup", { phase, from: "iphone", to: "mac" }) : ""}</div>${pw}`,
      actions: live.running ? "" : `<button type="button" class="btn" data-act="start" data-step="backup">${esc(t("backup.start"))}</button>`,
      poll: live.running ? null : "connect",
    };
  };

  function preparePhases(current) {
    const idx = PREPARE_PHASES.indexOf(current);
    return `<ul class="phases">${PREPARE_PHASES.map((p, i) =>
      `<li class="${i < idx ? "done" : i === idx ? "now" : ""}">${esc(t("prepare.p_" + p))}</li>`).join("")}</ul>`;
  }

  views.prepare = () => {
    const live = S.live.prepare || {};
    const r = done("prepare") ? S.state.steps.prepare : null;
    if (r && !live.running) {
      return {
        body: `<h2>${esc(t("prepare.done_title"))}</h2>
          ${stats([[num(r.messages_added), t("prepare.s_messages")], [num(r.chats_created), t("prepare.s_created")],
            [num(r.chats_merged), t("prepare.s_merged")], [num(r.media_found), t("prepare.s_media")]])}
          ${r.media_missing ? `<p class="small muted">${esc(t("prepare.missing", { n: num(r.media_missing) }))}</p>` : ""}`,
        actions: `<button type="button" class="btn" data-go="restore">${esc(t("common.continue"))}</button>`,
      };
    }
    const d = live.data || {};
    const sub = d.total ? t("common.of", { a: num(d.done), b: num(d.total) }) : "";
    return {
      body: `${errorCard("prepare")}${passwordField("prepare")}<div id="live">${live.running ? trip("prepare", { phase: t("prepare.p_" + (live.phase || "read")), sub, from: "android", to: "iphone", phases: preparePhases(live.phase || "read") }) : ""}</div>`,
      actions: live.running ? `<button type="button" class="btn quiet" data-act="cancel">${esc(t("common.stop"))}</button>`
        : `<button type="button" class="btn" data-act="start" data-step="prepare">${esc(t("prepare.start"))}</button>`,
    };
  };

  views.restore = () => {
    const live = S.live.restore || {};
    const p = S.checks.iphone || {};
    const fmOn = p.find_my === true;
    if (live.running) {
      const waiting = !live.pct;
      return {
        body: `<div id="live">${trip("restore", { phase: t("restore.phase"), sub: waiting ? t("restore.waiting") : "", from: "mac", to: "iphone" })}</div>
          <ul class="ticks need">${["restore.before_1", "restore.before_3"].map((k) => `<li>${I.warn}<span>${esc(t(k))}</span></li>`).join("")}</ul>`,
        actions: "",
      };
    }
    return {
      body: `${errorCard("restore")}${passwordField("restore")}
        <ul class="ticks need">${["restore.before_1", "restore.before_2", "restore.before_3"].map((k) => `<li>${I.warn}<span>${esc(t(k))}</span></li>`).join("")}</ul>
        <div id="live" style="margin-top:18px">${fmOn ? `<div class="checks">${checkRow("ck-fm2", "wait", I.pin, esc(t("ready.findmy")), esc(t("ready.findmy_on")), "",
          details("grey2", t("ready.findmy_grey"), list(["ready.grey_1", "ready.grey_2", "ready.grey_3"])))}</div>` : ""}</div>`,
      actions: `<button type="button" class="btn" data-act="start" data-step="restore" ${fmOn ? "disabled" : ""}>${esc(t("restore.start"))}</button>`,
      poll: "iphone",
    };
  };

  views.finish = () => {
    const live = S.live.undo || {};
    const before = (S.state.steps.backup || {}).used_bytes;
    const now = (S.checks.iphone || {}).used_bytes;
    const cleaned = (S.state.steps.finish || {}).cleaned;
    if (live.running) {
      return { body: `<div id="live">${trip("undo", { phase: t("finish.undoing"), from: "mac", to: "iphone" })}</div>`, actions: "" };
    }
    const undone = live.result && !S.errors.undo;
    const items = ["t1", "t2", "t3", "t4", "t5"].map((k) =>
      `<label class="todo-row"><input type="checkbox" data-tick="f_${k}" ${S.ui.ticks["f_" + k] ? "checked" : ""}><span>${esc(t("finish." + k))}</span></label>`).join("");
    return {
      body: `${errorCard("undo")}${cleaned ? "" : passwordField("undo")}
        ${undone ? `<div class="banner"><div class="ic">${I.undo}</div><div><strong>${esc(t("finish.undone"))}</strong></div></div>` : ""}
        ${cleaned ? `<div class="banner"><div class="ic">${I.check}</div><div><strong>${esc(t("finish.cleaned"))}</strong><span>${esc(t("finish.thanks"))}</span></div></div>` : ""}
        <div class="checks todo">${items}</div>
        <div id="live">${before ? stats([[gb(before), `${t("finish.storage")}, ${t("finish.before")}`],
          now ? [gb(now), `${t("finish.storage")}, ${t("finish.now")}`] : null]) : ""}</div>`,
      actions: `<button type="button" class="btn quiet left" data-act="show-folder">${esc(t("common.show_folder"))}</button>
        <button type="button" class="btn quiet" data-act="undo-dialog" ${cleaned ? "disabled" : ""}>${esc(t("finish.wrong"))}</button>
        <button type="button" class="btn" data-act="cleanup-dialog" ${cleaned ? "disabled" : ""}>${esc(t("finish.worked"))}</button>`,
      poll: "iphone",
    };
  };

  // ---------- rendering ----------
  let current = null;
  function render() {
    applyLang();
    updateRoute();
    const step = S.view;
    const v = views[step]();
    current = v;
    const idx = STEPS.indexOf(step) + 1;
    const lede = t(`${step}.lede`);
    $("#page").innerHTML = `
      <div class="page-inner">
        <p class="step-no">${esc(t("common.step_of", { n: idx }))}</p>
        <h1>${esc(t(`${step}.title`))}</h1>
        ${lede !== `${step}.lede` ? `<p class="lede">${esc(lede)}</p>` : ""}
        <div id="body">${v.body}</div>
      </div>
      <div class="actions">${v.actions || ""}</div>`;
    bindKeyGrid();
    schedulePoll(v.poll);
  }

  function updateLive() {
    const v = views[S.view]();
    const target = $("#live");
    const fresh = document.createElement("div");
    fresh.innerHTML = v.body;
    const replacement = fresh.querySelector("#live");
    if (target && replacement) {
      target.innerHTML = replacement.innerHTML;
      const actions = $(".actions");
      if (actions && actions.innerHTML !== (v.actions || "")) actions.innerHTML = v.actions || "";
    } else {
      render();
    }
  }

  function go(step) {
    if (!STEPS.includes(step)) return;
    S.view = step;
    render();
    $("#page").focus({ preventScroll: true });
    $("#page").scrollTop = 0;
  }

  // ---------- polling checks ----------
  let pollGen = 0;
  function schedulePoll(kind) {
    clearTimeout(S.pollTimer);
    const gen = ++pollGen;             // any older loop sees a newer generation and stops
    if (!kind || !api()) return;
    const tick = async () => {
      if (gen !== pollGen) return;
      if (!busy()) await pollOnce(kind, gen);
      if (gen === pollGen) S.pollTimer = setTimeout(tick, 2000);
    };
    S.pollTimer = setTimeout(tick, S.checks[kind] ? 1500 : 50);
  }
  async function pollOnce(kind, gen) {
    const result = await call({ connect: "check_connect", ready: "check_ready", iphone: "check_iphone" }[kind]);
    if (gen !== pollGen || !result) return;   // the page moved on, or the engine is busy
    S.checks[kind] = result;
    if (!document.activeElement || !document.activeElement.matches("input[data-key], #pw")) updateLive();
  }
  function refreshChecks() { delete S.checks.connect; schedulePoll("connect"); }

  // ---------- key grid ----------
  function keyText() {
    return Array.from(document.querySelectorAll("input[data-key]")).map((i) => i.value.trim()).join(" ");
  }
  function bindKeyGrid() {
    const inputs = Array.from(document.querySelectorAll("input[data-key]"));
    inputs.forEach((input, i) => {
      input.addEventListener("input", () => {
        const clean = input.value.toLowerCase().replace(/[^0-9a-f]/g, "");
        if (clean.length > 4) {             // a paste of several groups: spread it over the boxes
          const groups = clean.match(/.{1,4}/g);
          groups.forEach((g, k) => { if (inputs[i + k]) inputs[i + k].value = g; });
          (inputs[Math.min(i + groups.length, 15)]).focus();
        } else {
          input.value = clean;
          if (clean.length === 4 && inputs[i + 1]) inputs[i + 1].focus();
        }
        inputs.forEach((x) => x.classList.toggle("full", x.value.length === 4));
        S.ui.keyBoxes = inputs.map((x) => x.value);
        delete S.errors.key;
      });
      input.addEventListener("keydown", (e) => {
        if (e.key === "Backspace" && !input.value && inputs[i - 1]) inputs[i - 1].focus();
        if (e.key === "Enter") act("check-key");
      });
    });
    inputs.forEach((x) => x.classList.toggle("full", x.value.length === 4));
  }

  // ---------- actions ----------
  async function act(name, el) {
    const step = el && el.dataset.step;
    if (name === "mark") {
      S.state = await call("mark", step) || S.state;
      go(STEPS[STEPS.indexOf(step) + 1]);
    } else if (name === "start") {
      await startJob(step);
    } else if (name === "cancel") {
      await call("cancel");
    } else if (name === "check-key") {
      delete S.errors.key;
      S.ui.keyResult = null;
      S.live.key = { running: true };
      S.state.busy = "key";
      render();
      if (!(await call("check_key", keyText()))) delete S.live.key;
      await refresh();
      render();
    } else if (name === "adb") {
      S.live.adb = { running: true, pct: 0 };
      delete S.errors.connect;
      await call("install_adb");
      updateLive();
    } else if (name === "back-to") {
      S.state = await call("go_back", step) || S.state;
      go(step);
    } else if (name === "show-folder") {
      call("show_folder");
    } else if (name === "copy-detail") {
      const pre = el.closest(".error").querySelector("pre");
      try { await navigator.clipboard.writeText(pre.textContent); el.textContent = t("common.copied"); } catch (e) { /* clipboard blocked */ }
    } else if (name === "cleanup-dialog") {
      const before = (S.state.steps.backup || {}).used_bytes;
      dialog(`<h2>${esc(t("finish.cleanup_title"))}</h2><p class="muted">${esc(t("finish.cleanup_sub"))}</p>
        <label class="manual"><input type="checkbox" id="keep" checked>${esc(t("finish.keep_backup"))}${before ? ` (${esc(gb(before))})` : ""}</label>
        <div class="row"><button type="button" class="btn quiet" value="cancel">${esc(t("common.cancel"))}</button>
        <button type="button" class="btn danger" value="ok">${esc(t("finish.delete"))}</button></div>`, async (value, d) => {
        if (value !== "ok") return;
        await call("cleanup", d.querySelector("#keep").checked);
        await refresh();
        render();
      });
    } else if (name === "undo-dialog") {
      dialog(`<h2>${esc(t("finish.undo_title"))}</h2><p class="muted">${esc(t("finish.undo_sub"))}</p>
        <div class="row"><button type="button" class="btn quiet" value="cancel">${esc(t("common.cancel"))}</button>
        <button type="button" class="btn" value="ok">${esc(t("finish.undo"))}</button></div>`, async (value) => {
        if (value !== "ok") return;
        await startJob("undo");
      });
    }
  }

  async function startJob(step) {
    const pw = $("#pw");
    if (pw && pw.value) await call("set_password", pw.value);
    delete S.errors[step];
    S.live[step] = { running: true, pct: step === "copy" || step === "prepare" ? 0 : null };
    S.state.busy = step;               // stop polling before the engine starts using the phones
    render();
    if (!(await call("start", step))) delete S.live[step];
    await refresh();                   // the engine's own view of what is running
    render();
  }

  function dialog(html, onClose) {
    const d = $("#dialog");
    d.innerHTML = html;
    d.querySelectorAll("button[value]").forEach((b) => b.addEventListener("click", () => {
      d.close();
      onClose(b.value, d);
    }));
    d.showModal();
  }

  function helpHtml() {
    const qa = (q, a) => `<details><summary>${esc(t(q))}</summary>${a}</details>`;
    return `<h2>${esc(t("help.title"))}</h2>
      ${qa("help.q_erase", `<p>${esc(t("help.a_erase"))}</p>`)}
      ${qa("help.q_key", `<p>${esc(t("help.a_key"))}</p>`)}
      ${qa("help.q_findmy", list(["ready.grey_1", "ready.grey_2", "ready.grey_3"]))}
      ${qa("help.q_cable", `<p>${esc(t("help.a_cable"))}</p>`)}
      ${qa("help.q_new", `<p>${esc(t("help.a_new"))}</p>`)}
      ${qa("help.q_upload", `<p>${esc(t("help.a_upload"))}</p>`)}
      ${qa("help.q_wrong", `<p>${esc(t("help.a_wrong"))}</p>`)}
      <p class="small muted" style="margin-top:20px">${esc(t("help.about", { v: S.state.version || "" }))}</p>
      <p><button type="button" class="btn quiet small" data-url="https://github.com/kerneltics/wasla">${esc(t("help.source"))}</button>
      <button type="button" class="btn quiet small" data-url="${ISSUES}">${esc(t("error.report"))}</button></p>`;
  }
  function toggleHelp(open) {
    const drawer = $("#drawer");
    if (open) drawer.innerHTML = helpHtml();
    drawer.classList.toggle("open", open);
    $("#scrim").classList.toggle("open", open);
    drawer.setAttribute("aria-hidden", String(!open));
  }

  // ---------- wiring ----------
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-go],[data-act],[data-url],[data-lang]");
    if (!el) return;
    if (el.dataset.go) go(el.dataset.go);
    else if (el.dataset.act) act(el.dataset.act, el);
    else if (el.dataset.url) call("open_url", el.dataset.url);
    else if (el.dataset.lang) {
      S.lang = el.dataset.lang;
      call("set_lang", S.lang);
      render();
      if ($("#drawer").classList.contains("open")) toggleHelp(true);
    }
  });
  document.addEventListener("change", (e) => {
    const tick = e.target.dataset && e.target.dataset.tick;
    if (tick) { S.ui.ticks[tick] = e.target.checked; render(); }
  });
  document.addEventListener("toggle", (e) => {
    const id = e.target.dataset && e.target.dataset.open;
    if (id) S.ui.open[id] = e.target.open;
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") toggleHelp(false); });
  $("#help-btn").addEventListener("click", () => toggleHelp(true));
  $("#scrim").addEventListener("click", () => toggleHelp(false));

  async function start() {
    await refresh();
    S.lang = S.state.lang || ((navigator.language || "en").startsWith("ar") ? "ar" : "en");
    S.view = S.state.current;
    if (S.state.busy) S.live[S.state.busy] = { running: true };
    render();
  }

  window.wasla = { onEvent, _S: S, _go: go, _render: render };
  if (window.WASLA_DEMO) window.WASLA_DEMO.ready.then(start);
  else if (api()) start();
  else window.addEventListener("pywebviewready", start);
})();
