/* Demo-only: ?demo=1&autotest=1 clicks through all nine steps and writes the outcome into the title. */
(() => {
  const q = new URLSearchParams(location.search);
  if (!q.has("demo") || !q.has("autotest")) return;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s) => document.querySelector(s);
  const log = [];
  async function until(fn, what, ms = 20000) {
    const end = Date.now() + ms;
    while (Date.now() < end) { if (fn()) return; await sleep(50); }
    throw new Error("timeout: " + what);
  }
  const view = () => window.wasla._S.view;
  const fits = (what) => {           // no step may make the page scroll sideways
    const page = $("#page");
    if (page.scrollWidth > page.clientWidth + 1) throw new Error(`${view()} overflows sideways (${what})`);
  };
  const click = async (sel, what) => {
    await until(() => $(sel) && !$(sel).disabled, what);
    fits(what);
    $(sel).click(); log.push(what); await sleep(30);
  };
  async function run() {
    await until(() => $("h1"), "first render");
    await click('[data-act="mark"][data-step="welcome"]', "start");
    await until(() => view() === "connect", "connect view");
    await click('[data-act="mark"][data-step="connect"]', "connect continue");
    await until(() => view() === "key", "key view");
    const boxes = document.querySelectorAll("input[data-key]");
    boxes[0].value = "3f1a9c07b2e45d68a0c7e19b4f2d8a63c5e07b19d84f2a6c1e93b07d5a2c8f41";
    boxes[0].dispatchEvent(new Event("input"));
    if (boxes[15].value !== "8f41") throw new Error("paste did not fill the grid");
    await click('[data-act="check-key"]', "check key");
    await click('[data-go="copy"]', "key continue");
    await click('[data-act="start"][data-step="copy"]', "start copy");
    await click('[data-go="ready"]', "copy continue");
    for (const tick of ["register", "offline"]) {   // each tick re-renders the page, so look each box up again
      await until(() => $(`input[data-tick="${tick}"]`), tick);
      $(`input[data-tick="${tick}"]`).click();
      await sleep(30);
    }
    await click('[data-act="mark"][data-step="ready"]', "ready continue");
    await click('[data-act="start"][data-step="backup"]', "start backup");
    await until(() => document.querySelector(".banner.attention"), "passcode banner");
    await click('[data-go="prepare"]', "backup continue");
    await click('[data-act="start"][data-step="prepare"]', "start prepare");
    await click('[data-go="restore"]', "prepare continue");
    await click('[data-act="start"][data-step="restore"]', "start restore");
    await until(() => view() === "finish", "finish view", 30000);
    await click('[data-act="cleanup-dialog"]', "it worked");
    await click('#dialog button[value="ok"]', "delete copies");
    await until(() => document.body.textContent.includes(window.WASLA_STRINGS[window.wasla._S.lang]["finish.cleaned"]), "cleaned banner");
    if ($('[data-act="undo-dialog"]').disabled !== true) throw new Error("undo still enabled after cleanup");
    document.title = "AUTOTEST OK " + log.length;
  }
  run().catch((e) => { document.title = "AUTOTEST FAIL " + e.message + " after " + log.join(" > "); });
})();
