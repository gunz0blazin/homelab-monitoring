// Status header: one sentence that answers "is everything up?", then three numbers.
function renderHeader(data) {
  const R = records(data);
  const up = first(R, "up", 0), down = first(R, "down", 0), pend = first(R, "pend", 0);
  const total = up + down + pend;
  const uptime = first(R, "up30", NaN);

  const bad = only(R, "svc").filter((r) => num(r) !== 1 && Number.isFinite(num(r)));
  const downNames = bad.filter((r) => num(r) === 0).map((r) => String(r.monitor_name).trim());
  const waitNames = bad.filter((r) => num(r) !== 0).map((r) => String(r.monitor_name).trim());
  const hosts = only(R, "hup");
  // a host that is offline because its own service is down or pending is the same story: say it once, as the service
  const norm = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");
  const flagged = downNames.concat(waitNames).map(norm);
  const covered = (name) => flagged.some((f) => f.startsWith(norm(name)) || norm(name).startsWith(f));
  const offline = hosts.filter((r) => num(r) === 0).map((r) => hostName(r.host)).filter((n) => !covered(n));
  const hostsOn = hosts.filter((r) => num(r) !== 0).length;

  let state = "ok", head = "All systems operational";
  if (downNames.length || down > 0) { state = "crit"; head = "Service outage"; }
  else if (waitNames.length || pend > 0 || offline.length) { state = "warn"; head = "Degraded performance"; }

  const notes = [];
  if (downNames.length) notes.push(list(downNames) + " down");
  if (waitNames.length) notes.push(list(waitNames) + " pending");
  if (offline.length) notes.push(list(offline) + " offline");
  const sub = notes.length ? notes.join(" · ") : total + " services and " + hosts.length + " hosts are healthy";

  const stat = (key, value, of, cap) =>
    '<div class="stat"><div class="num"><span class="cnt k_' + key + '">' + value + "</span>" +
    (of === "" ? "" : '<span class="of"> ' + of + "</span>") + '</div><div class="cap">' + cap + "</div></div>";

  return wrap("head " + state,
    '<div class="lead"><span class="dot"></span><div class="msg"><div class="h">' + esc(head) +
    '</div><div class="s">' + esc(sub) + "</div></div></div>" +
    '<div class="stats">' +
    stat("svc", up, "of " + total, "Services up") +
    stat("hst", hostsOn, "of " + hosts.length, "Hosts online") +
    stat("up30", pct(uptime), "", "Uptime, 30 days") +
    "</div>");
}
context.handlebars.registerHelper("header", (data) => renderHeader(data));
