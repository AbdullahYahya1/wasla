/* Demo mode (?demo=1): a pretend engine so every screen can be tried and screenshotted without phones.
   ?step=copy&scene=running&pct=42&lang=ar&theme=dark jumps straight to a state. Not used by the app. */
(() => {
  const q = new URLSearchParams(location.search);
  if (!q.has("demo")) return;
  if (q.get("theme")) document.documentElement.dataset.theme = q.get("theme");
  const STEPS = ["welcome", "connect", "key", "copy", "ready", "backup", "prepare", "restore", "finish"];
  const want = q.get("step") || "welcome";
  const scene = q.get("scene") || "idle";
  const pct = Number(q.get("pct") || 42);
  const results = {
    key: { order: "rows_rtl" },
    copy: { chats: 1783, groups: 190, messages: 558855, media: 136642, first_ms: Date.UTC(2014, 2, 14), contacts: 812 },
    backup: { udid: "demo", entries: 311, used_bytes: 14.4e9 },
    prepare: { chats_created: 1607, chats_merged: 176, messages_added: 558855, media_found: 129175, media_missing: 7404, thumbnails: 28444 },
    restore: { used_bytes_before: 14.4e9 },
  };
  const steps = {};
  for (const s of STEPS.slice(0, STEPS.indexOf(want))) steps[s] = { at: 1, ...(results[s] || {}) };
  if (scene === "done" && results[want]) steps[want] = { at: 1, ...results[want] };
  let polls = 0;
  const state = () => ({
    version: "1.0.0", steps, current: STEPS.find((s) => !steps[s]) || "finish", lang: q.get("lang") || "en",
    busy: scene === "running" ? want : null, has_key: scene !== "nokey", has_password: false, work: "~/Library/Application Support/Wasla/work",
  });
  const send = (e) => setTimeout(() => window.wasla.onEvent({ pct: null, eta_s: null, phase: null, data: {}, ...e }), 0);
  function simulate(step, phases, total = 4000) {
    let i = 0;
    const n = 40;
    const timer = setInterval(() => {
      i += 1;
      const p = (100 * i) / n;
      const phase = phases[Math.min(Math.floor((i / n) * phases.length), phases.length - 1)];
      send({ step, kind: "progress", pct: p, eta_s: ((n - i) * total) / n / 10, phase, data: { done: i * 700, total: n * 700, done_bytes: i * 5.8e8, total_bytes: n * 5.8e8 } });
      if (step === "backup" && i === 3) send({ step, kind: "need", data: { what: "passcode" } });
      if (step === "backup" && i === 9) send({ step, kind: "clear", data: { what: "passcode" } });
      if (i >= n) {
        clearInterval(timer);
        steps[step] = { at: 1, ...(results[step] || {}) };
        send({ step, kind: "done", pct: 100, data: results[step] || {} });
      }
    }, total / n);
  }
  const api = {
    get_state: async () => state(),
    set_lang: async () => null,
    mark: async (step) => { steps[step] = { at: 1 }; return state(); },
    go_back: async (step) => { for (const s of STEPS.slice(STEPS.indexOf(step))) delete steps[s]; return state(); },
    check_connect: async () => {
      polls += 1;
      const ready = scene !== "waiting" && polls > 1;
      return {
        android: scene === "noadb" ? { state: "no_adb" } : ready ? { state: "ready", model: "motorola edge 40 neo", backup: "ok", backup_age_s: 240 } : { state: "unauthorized" },
        iphone: ready ? { state: "ready", name: "iPhone Abdullah", ios: "27.0.1", used_bytes: 14.4e9, find_my: false, encrypted: false } : { state: "missing" },
        disk: { free_bytes: 68e9 },
      };
    },
    check_ready: async () => ({ iphone: { state: "ready", whatsapp: true, find_my: scene === "findmy" } }),
    check_iphone: async () => ({ state: "ready", used_bytes: 37.6e9, find_my: scene === "findmy" }),
    set_password: async () => null,
    open_url: async (u) => console.log("open", u),
    show_folder: async () => null,
    cancel: async () => null,
    install_adb: async () => simulate("adb", [null], 2500),
    check_key: async () => { setTimeout(() => { steps.key = { at: 1, order: "rows_rtl" }; send({ step: "key", kind: "done", data: { order: "rows_rtl" } }); }, 1200); return true; },
    start: async (step) => {
      const phases = {
        copy: ["chats", "WhatsApp Images", "WhatsApp Video", "WhatsApp Voice Notes", "WhatsApp Documents", "decrypt", "read"],
        backup: ["phone", "phone", "phone", "copy"],
        prepare: ["read", "thumbnails", "chats", "media", "check"],
        restore: ["phone"], undo: ["phone"],
      }[step];
      simulate(step, phases, step === "restore" ? 6000 : 5000);
      return true;
    },
    cleanup: async () => { steps.finish = { at: 1, cleaned: true }; return { ok: true }; },
  };
  window.pywebview = { api };
  window.WASLA_DEMO = {
    ready: new Promise((resolve) => document.addEventListener("DOMContentLoaded", resolve)),
  };
  window.WASLA_DEMO.ready.then(() => setTimeout(() => {
    const S = window.wasla._S;
    if (scene === "running") {
      const phase = { copy: "WhatsApp Images", backup: "phone", prepare: "thumbnails", restore: "phone" }[want];
      S.live[want] = { running: true, pct, eta_s: null, eta: 420, phase, data: { done: 12345, total: 28444, done_bytes: pct * 2.33e8, total_bytes: 2.33e10 }, need: q.get("need") };
    }
    if (scene === "error") S.errors[want] = { code: q.get("code") || "key_wrong", detail: q.get("code") === "unknown" ? "ConnectionTerminatedError: the device went away" : undefined };
    if (want === "key" && scene === "done") S.ui.keyResult = { order: "rows_rtl" };
    if (want === "ready" && scene === "done") S.ui.ticks = { register: true, offline: true };
    if (scene === "done" || scene === "running" || scene === "error") S.view = want;
    if (q.get("help")) document.getElementById("help-btn").click();
    if (q.get("open")) S.ui.open[q.get("open")] = true;
    window.wasla._render();
  }, 60));
})();
