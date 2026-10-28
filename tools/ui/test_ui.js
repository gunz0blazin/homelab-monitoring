// Tests the card code exactly as shipped in grafana/dashboards/homelab-mobile.json, with mock Prometheus frames.
// No dependencies: a ~60 line DOM stub is enough for class selectors and text. Run from the repo root:
//   node tools/ui/test_ui.js
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const dash = JSON.parse(fs.readFileSync(path.join(__dirname, "../../grafana/dashboards/homelab-mobile.json"), "utf8"));
const panel = (helper) => dash.panels.find((p) => p.options && p.options.content && p.options.content.includes("{{{" + helper + " "));

// run a card's "before content rendering" code and return the helper it registers
function load(helper) {
  const helpers = {};
  const context = { handlebars: { registerHelper: (n, f) => (helpers[n] = f) } };
  new Function("context", panel(helper).options.helpers)(context);
  return helpers[helper];
}

const rec = (q, o, v) => ({ Time: 1, q, ...o, Value: v });
const svc = (name, v) => rec("svc", { monitor_name: name }, v);
const frames = (...recs) => [recs];   // one frame is plenty: the code reads records by their q label

const goodServices = ["420NAS ", "Grafana", "Home Assistant", "NPM", "PiHole Primary", "Plex", "Proxmox", "qBittorrent", "Uptime Kuma"];
const hostKeys = ["proxmox", "pihole", "dockers", "tailscale", "plex", "qbittorrent"];

function headerData(over = {}) {
  return frames(rec("up", {}, over.up ?? 9), rec("down", {}, over.down ?? 0), rec("pend", {}, over.pend ?? 0),
    rec("up30", {}, 99.9812), rec("kup", {}, over.kup ?? 1), ...goodServices.map((n, i) => svc(n, over.svc ? over.svc(n, i) : 1)),
    ...hostKeys.map((h) => rec("hup", { host: h }, over.hup ? over.hup(h) : 1)));
}

function hostData(cpu = {}) {
  return frames(...hostKeys.flatMap((h, i) => [
    rec("cpu", { host: h }, cpu[h] ?? 10 + i * 7), rec("mem", { host: h }, 40 + i * 5),
    rec("dsk", { host: h }, 55 + i), rec("hup", { host: h }, 1)]));
}

function serviceData() {
  return frames(...goodServices.flatMap((n, i) => [svc(n, n === "Plex" ? 0 : 1), rec("resp", { monitor_name: n }, 20 + i * 11),
    rec("svcup", { monitor_name: n }, 99.5 + i / 20)]));
}


// ---- minimal DOM: parses the cards' HTML (div/span/b only) and supports class selectors ----
class Node_ {
  constructor(tag, cls) { this.tag = tag; this.children = []; this.parent = null; this.text = ""; this.classes = cls ? cls.split(/\s+/).filter(Boolean) : []; this.style = {}; }
  get className() { return this.classes.join(" "); }
  get classList() { return { contains: (c) => this.classes.includes(c) }; }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(""); }
  set textContent(v) { this.text = v; this.children = []; }
  get offsetWidth() { return 1; }
  all() { return this.children.flatMap((c) => [c, ...c.all()]); }
  matches(sel) { return sel.split(".").filter(Boolean).every((c) => this.classes.includes(c)); }
  querySelectorAll(sel) {
    const parts = sel.trim().split(/\s+/);
    return this.all().filter((n) => {
      if (!n.matches(parts[parts.length - 1])) return false;
      let p = n.parent, i = parts.length - 2;
      while (i >= 0 && p) { if (p.matches(parts[i])) i--; p = p.parent; }
      return i < 0;
    });
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
function html(src) {
  const root = new Node_("root", "");
  let cur = root;
  for (const m of src.matchAll(/<(\/?)(\w+)([^>]*)>|([^<]+)/g)) {
    if (m[4] !== undefined) { cur.text += m[4].replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&"); continue; }
    if (m[1]) { assert.strictEqual(cur.tag, m[2], "unbalanced </" + m[2] + ">"); cur = cur.parent; continue; }
    const n = new Node_(m[2], (/class="([^"]*)"/.exec(m[3]) || [])[1]);
    n.parent = cur; cur.children.push(n); cur = n;
  }
  assert.strictEqual(cur, root, "unclosed tag <" + cur.tag + ">");
  return root;
}
const oneLine = (s) => assert(!/\n/.test(s) && !/^\s/.test(s), "markdown pass would break multi-line or indented output");

let n = 0;
const test = (name, fn) => { fn(); n++; console.log("ok -", name); };

test("header: healthy", () => {
  const out = load("header")(headerData());
  oneLine(out);
  const d = html(out);
  assert(out.includes("All systems operational") && out.includes("9 services and 6 hosts are healthy"));
  assert.strictEqual(d.querySelectorAll(".stat").length, 3);
  assert(/99\.98%/.test(d.querySelector(".k_up30").textContent), "uptime keeps two decimals");
  assert(d.querySelector(".hl").classList.contains("ok"));
});

test("header: second row shows down, pending, 24 h uptime and DNS", () => {
  const data = headerData();
  data[0].push(rec("up1d", {}, 100), rec("dns", {}, 12.4));
  const d = html(load("header")(data));
  assert.strictEqual(d.querySelectorAll(".mstat").length, 5);   // down, pending, 24 h uptime, DNS, tester
  assert.strictEqual(d.querySelector(".k_down").textContent, "0");
  assert(d.querySelector(".k_down").parent.classList.contains("zero"), "zero down is calm grey");
  assert.strictEqual(d.querySelector(".k_up1d").textContent, "100%");
  assert.strictEqual(d.querySelector(".k_dns").textContent, "12 ms");
});

test("header: the Down Tester shows in the second row and never changes the headline", () => {
  const word = (data) => html(load("header")(data)).querySelector(".tester .mnum");
  // down is its normal state: pink word, and the card still reads all clear
  const downData = headerData();
  downData[0].push(rec("tester", {}, 0));
  const down = word(downData);
  assert.strictEqual(down.textContent, "Down");
  assert(down.classList.contains("pink") && !down.classList.contains("crit"), "pink, not a warning colour");
  const out = load("header")(downData);
  assert(out.includes("All systems operational") && html(out).querySelector(".hl").classList.contains("ok"));
  assert(!out.includes("Service outage") && !out.includes("Degraded"));
  // up, retrying, maintenance
  for (const [v, text] of [[1, "Up"], [2, "Retry"], [3, "Maint"]]) {
    const data = headerData();
    data[0].push(rec("tester", {}, v));
    assert.strictEqual(word(data).textContent, text);
  }
  // paused in Kuma, or not reporting: grey "Off", never an error
  const off = word(headerData());
  assert.strictEqual(off.textContent, "Off");
  assert(off.classList.contains("zero"));
});

test("header: slow DNS, a down service and low uptime take a tone", () => {
  const data = headerData({ down: 1, up: 8, pend: 2 });
  data[0].push(rec("up1d", {}, 93.2), rec("dns", {}, 620));
  const d = html(load("header")(data));
  assert(d.querySelector(".k_down").parent.classList.contains("crit"));
  assert(d.querySelector(".k_pend").parent.classList.contains("warn"));
  assert(d.querySelector(".k_up1d").parent.classList.contains("crit"));
  assert(d.querySelector(".k_dns").parent.classList.contains("crit"));
});

test("header: DNS and 24 h uptime show n/a when the series is missing", () => {
  const d = html(load("header")(headerData()));
  assert.strictEqual(d.querySelector(".k_dns").textContent, "n/a");
  assert.strictEqual(d.querySelector(".k_up1d").textContent, "n/a");
});

test("header: a service is down", () => {
  const out = load("header")(headerData({ down: 1, up: 8, svc: (n) => (n === "Plex" ? 0 : 1) }));
  assert(out.includes("Service outage") && out.includes("Plex down"));
  assert(html(out).querySelector(".hl").classList.contains("crit"));
});

test("header: pending service and offline host", () => {
  const out = load("header")(headerData({ pend: 1, up: 8, svc: (n) => (n === "NPM" ? 2 : 1), hup: (h) => (h === "pihole" ? 0 : 1) }));
  assert(out.includes("Degraded performance") && out.includes("NPM pending") && out.includes("Pi-hole offline"));
  assert(out.includes("5") && html(out).querySelector(".k_hst").textContent === "5");
});

test("header: a pending service does not also say its host is offline", () => {
  const out = load("header")(headerData({ pend: 1, up: 8, svc: (n) => (n === "qBittorrent" ? 2 : 1), hup: (h) => (h === "qbittorrent" ? 0 : 1) }));
  assert(out.includes("qBittorrent pending") && !out.includes("offline"), out);
  assert.strictEqual(html(out).querySelector(".k_hst").textContent, "5", "the host count still shows 5 of 6");
});

test("header: a service in maintenance is described as in maintenance, not pending", () => {
  const out = load("header")(headerData({ pend: 1, up: 8, svc: (n) => (n === "NPM" ? 3 : 1) }));
  assert(out.includes("NPM in maintenance"), out);
  assert(!out.includes("NPM pending"), out);
});

test("header: no data at all is never reported as all clear", () => {
  const out = load("header")([]);
  assert(!out.includes("All systems operational"), out);
  assert(out.includes("No data from Uptime Kuma"));
  assert(html(out).querySelector(".hl").classList.contains("crit"));
});

test("header: Uptime Kuma not being scraped says monitoring is unavailable, even if the last numbers look fine", () => {
  const out = load("header")(headerData({ kup: 0 }));
  assert(!out.includes("All systems operational"), out);
  assert(out.includes("Monitoring unavailable") && out.includes("may be out of date"));
  assert(html(out).querySelector(".hl").classList.contains("crit"));
});

test("header: no monitors yet is a warning, not an outage", () => {
  const hosts = hostKeys.map((h) => rec("hup", { host: h }, 1));
  const out = load("header")(frames(rec("up", {}, 0), rec("down", {}, 0), rec("pend", {}, 0), rec("kup", {}, 1), ...hosts));
  assert(out.includes("No services monitored yet"), out);
  assert(html(out).querySelector(".hl").classList.contains("warn"));
});

test("hosts: names, thresholds, static widths", () => {
  const out = load("hosts")(hostData({ proxmox: 95, pihole: 80 }));
  oneLine(out);
  const d = html(out);
  const names = [...d.querySelectorAll(".row .nm")].map((e) => e.textContent);
  assert.deepStrictEqual(names, ["Proxmox", "Pi-hole", "Docker", "Tailscale", "Plex", "qBittorrent"]);
  const px = d.querySelector(".k_proxmox-cpu.fil");
  assert(px.classList.contains("crit") && px.classList.contains("w95"));
  assert(d.querySelector(".k_pihole-cpu.fil").classList.contains("warn"));
  assert(!d.querySelector(".k_dockers-cpu.fil").classList.contains("warn"), "healthy bars stay neutral");
  assert(out.includes("6 of 6 online"));
});

test("hosts: offline host and empty data", () => {
  const data = hostData();
  data[0].forEach((r) => { if (r.q === "hup" && r.host === "plex") r.Value = 0; });
  const d = html(load("hosts")(data));
  assert(d.querySelector(".row.gone .tag").textContent === "Offline");
  assert(load("hosts")([]).includes("Waiting for data"));
});

test("services: problems first, formatting", () => {
  const out = load("services")(serviceData());
  oneLine(out);
  const d = html(out);
  const rows = [...d.querySelectorAll(".row")];
  assert.strictEqual(rows.length, 9);
  assert(rows[0].textContent.includes("Plex") && rows[0].querySelector(".tag.crit").textContent === "Down");
  assert(!out.includes("420NAS "), "trailing spaces from Kuma are trimmed");
  assert(/\d+ ms/.test(rows[1].querySelector(".rt").textContent));
  assert(out.includes("8 of 9 up"));
});

test("names are escaped", () => {
  const out = load("services")(frames(svc("<b>x</b> & co", 1)));
  assert(!out.includes("<b>x</b>") && out.includes("&lt;b&gt;"));
});

// ---- after-render motion ----
function runAfter(markup, win) {
  const el = html(markup);
  const cleanup = new Function("context", "window", "performance", "requestAnimationFrame", "cancelAnimationFrame", panel("hosts").options.afterRender)
    ({ element: el }, win, { now: () => 0 }, (f) => win.frames.push(f) , () => {});
  return { el, cleanup };
}

test("after render: bars animate from the previous value and counts tween", () => {
  const win = { frames: [], matchMedia: () => ({ matches: false }) };
  const cpu = (v) => load("hosts")(hostData({ proxmox: v }));
  const a = runAfter(cpu(20), win);
  assert.strictEqual(a.el.querySelector(".k_proxmox-cpu.fil").style.width, "20%");
  // the plugin swaps the HTML when a value changes: the new bar must start from the old width
  const b = runAfter(cpu(60), win);
  const bar = b.el.querySelector(".k_proxmox-cpu.fil");
  assert.strictEqual(bar.style.width, "60%");
  assert.match(bar.style.transition, /width 900ms/);
  assert.strictEqual(win.__homelab["f_proxmox-cpu"], 60);
  assert.strictEqual(win.__homelab["c_proxmox-cpu"], 60);
  assert.strictEqual(win.frames.length > 0, true, "a count-up was scheduled");
  const label = b.el.querySelector(".k_proxmox-cpu.cnt");
  win.frames.splice(0).forEach((f) => f(0));          // first frame: still at the old number
  assert.strictEqual(label.textContent, "20%");
  assert.strictEqual(typeof b.cleanup, "function");
});

test("after render: reduced motion sets the final width at once", () => {
  const win = { frames: [], matchMedia: () => ({ matches: true }) };
  const a = runAfter(load("hosts")(hostData({ proxmox: 42 })), win);
  assert.strictEqual(a.el.querySelector(".k_proxmox-cpu.fil").style.width, "42%");
  assert.strictEqual(win.frames.length, 0);
});

console.log(`\n${n} tests passed`);
process.exit(0);
