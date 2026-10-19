// Runs after the card's HTML is in the DOM. The plugin replaces the HTML whenever a value changes, which
// would make bars jump, so this keeps the previous value of every meter and number in window state and
// animates from it to the new one. First load grows from zero. Without this code the cards still show the
// right values (each bar has a static width class); this only adds motion.
const el = context.element;
const S = (window.__homelab = window.__homelab || {});
const calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const keyOf = (n) => { const m = /\bk_([\w-]+)/.exec(n.className); return m && m[1]; };
const frames = [];

el.querySelectorAll(".fil").forEach((n) => {
  const key = keyOf(n), m = /\bw(\d+)\b/.exec(n.className);
  if (!key || !m) return;
  const to = Number(m[1]), from = S["f_" + key] === undefined ? 0 : S["f_" + key];
  S["f_" + key] = to;
  if (calm) { n.style.width = to + "%"; return; }
  n.style.transition = "none";
  n.style.width = from + "%";
  void n.offsetWidth;
  n.style.transition = "width 900ms cubic-bezier(.22,.8,.24,1), background-color 400ms ease";
  n.style.width = to + "%";
});

el.querySelectorAll(".cnt").forEach((n) => {
  const key = keyOf(n), m = /^(-?\d+(?:\.\d+)?)(.*)$/.exec(n.textContent.trim());
  if (!key || !m || n.children.length) return;
  const to = parseFloat(m[1]), dec = (m[1].split(".")[1] || "").length, tail = m[2];
  const from = S["c_" + key];
  S["c_" + key] = to;
  if (calm || from === undefined || from === to) return;
  const t0 = performance.now();
  const step = (t) => {
    const p = Math.min(1, (t - t0) / 800), e = 1 - Math.pow(1 - p, 3);
    n.textContent = (from + (to - from) * e).toFixed(dec) + tail;
    if (p < 1) frames.push(requestAnimationFrame(step));
  };
  frames.push(requestAnimationFrame(step));
});

return () => frames.forEach((f) => cancelAnimationFrame(f));
