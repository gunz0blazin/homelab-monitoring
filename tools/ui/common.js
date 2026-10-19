// Shared helpers for the Homelab cards (Business Text panels). Runs inside Grafana as the panel's
// "Before content rendering" code, with `context` in scope. Everything here is plain ES2018 so it can
// also be unit-tested in Node (tools/ui/test_ui.js).
//
// Data arrives in "All data" mode: an array of frames, each an array of records keyed by field name.
// Each query is tagged with a `q` label (label_replace in the PromQL) so we never depend on frame order.
const HOSTS = __HOSTS__;   // [["proxmox", "Proxmox"], ...] display names, filled in by gen_home.py

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function records(data) {
  const out = [];
  const walk = (d) => {
    if (Array.isArray(d)) d.forEach(walk);
    else if (d && typeof d === "object") out.push(d);
  };
  walk(data);
  return out;
}

function num(r) {
  if (!r) return NaN;
  if (typeof r.Value === "number") return r.Value;
  const k = Object.keys(r).find((x) => /^Value/.test(x));
  const v = k === undefined ? NaN : Number(r[k]);
  return Number.isFinite(v) ? v : NaN;
}

const only = (recs, q) => recs.filter((r) => r.q === q);
const first = (recs, q, fallback) => {
  const v = num(only(recs, q)[0]);
  return Number.isFinite(v) ? v : fallback;
};

const clamp = (v) => Math.max(0, Math.min(100, Math.round(v)));
const tone = (v) => (v >= 90 ? "crit" : v >= 75 ? "warn" : "");
const hostName = (raw) => {
  const hit = HOSTS.find((h) => h[0] === raw);
  return hit ? hit[1] : raw;
};

// "99.98%" but "100%" for a perfect score, and never more than two decimals
const pct = (v) => {
  if (!Number.isFinite(v)) return "n/a";
  const s = v.toFixed(2);
  return (s.endsWith(".00") ? s.slice(0, -3) : s.replace(/0$/, "")) + "%";
};

const ms = (v) => (!Number.isFinite(v) ? "n/a" : v >= 1000 ? (v / 1000).toFixed(1) + " s" : Math.round(v) + " ms");

const list = (items) =>
  items.length <= 1 ? items.join("") : items.slice(0, -1).join(", ") + " and " + items[items.length - 1];

// One line, no blank lines, no indentation: the plugin runs the output through a markdown pass, and a
// blank line or four leading spaces would turn part of it into a paragraph or a code block.
const wrap = (cls, inner) => '<div class="hlw"><div class="hl ' + cls + '">' + inner + "</div></div>";

const skeleton = (title) =>
  wrap("skel", '<div class="hd"><span class="ti">' + esc(title) + '</span><span class="su">Waiting for data</span></div>');
