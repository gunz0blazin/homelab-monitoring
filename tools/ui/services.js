// Service list: status dot, name, response time, 30-day uptime. Problems sort to the top.
const STATUS = { 0: ["Down", "crit"], 2: ["Pending", "warn"], 3: ["Maintenance", "info"] };
function renderServices(data) {
  const R = records(data);
  const st = only(R, "svc");
  if (!st.length) return skeleton("Services");
  const name = (r) => String(r.monitor_name).trim();
  const find = (q, n) => num(only(R, q).find((r) => name(r) === n));

  const items = st.map((r) => ({ n: name(r), s: num(r), ms: find("resp", name(r)), up: find("svcup", name(r)) }))
    .sort((a, b) => (a.s === 1) - (b.s === 1) || a.n.localeCompare(b.n));
  const upCount = items.filter((i) => i.s === 1).length;

  const rows = items.map((i) => {
    const bad = STATUS[i.s];
    return '<div class="row' + (bad ? " " + bad[1] : "") + '"><span class="sd ' + (bad ? bad[1] : "ok") + '"></span><span class="nm">' + esc(i.n) +
      '</span><span class="rt">' + (bad ? '<span class="tag ' + bad[1] + '">' + bad[0] + "</span>" : ms(i.ms)) +
      '</span><span class="up">' + (Number.isFinite(i.up) ? pct(i.up) : "") + "</span></div>";
  }).join("");

  return wrap("svcs", '<div class="hd"><span class="ti">Services</span><span class="su">' + upCount + " of " + items.length + " up</span></div>" + rows);
}
context.handlebars.registerHelper("services", (data) => renderServices(data));
