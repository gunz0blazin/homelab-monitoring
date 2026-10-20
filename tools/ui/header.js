// Status header: one sentence that answers "is everything up?", then three numbers.
function renderHeader(data) {
  const R = records(data);
  const up = first(R, "up", 0), down = first(R, "down", 0), pend = first(R, "pend", 0);
  const total = up + down + pend;
  const uptime = first(R, "up30", NaN), uptime1d = first(R, "up1d", NaN), dns = first(R, "dns", NaN);
  // 1 while Prometheus can scrape Uptime Kuma, 0 when it can't, NaN when there is no such series at all
  const kuma = first(R, "kup", NaN);

  const bad = only(R, "svc").filter((r) => num(r) !== 1 && Number.isFinite(num(r)));
  const named = (status) => bad.filter((r) => num(r) === status).map((r) => String(r.monitor_name).trim());
  const downNames = named(0), waitNames = named(2), maintNames = named(3);
  const hosts = only(R, "hup");
  // a host that is offline because its own service is down or pending is the same story: say it once, as the service
  const norm = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");
  const flagged = downNames.concat(waitNames, maintNames).map(norm);
  const covered = (name) => flagged.some((f) => f.startsWith(norm(name)) || norm(name).startsWith(f));
  const offline = hosts.filter((r) => num(r) === 0).map((r) => hostName(r.host)).filter((n) => !covered(n));
  const hostsOn = hosts.filter((r) => num(r) !== 0).length;

  // A dashboard that goes quiet when its source dies is the worst failure, so "no data" is never "all clear".
  let state = "ok", head = "All systems operational", blind = "";
  if (kuma === 0) {
    state = "crit"; head = "Monitoring unavailable"; blind = "Uptime Kuma isn't reporting, so these numbers may be out of date";
  } else if (total === 0 && kuma !== 1) {
    state = "crit"; head = "No data from Uptime Kuma"; blind = "Check that Uptime Kuma and Prometheus are running";
  } else if (total === 0) {
    state = "warn"; head = "No services monitored yet"; blind = "Add monitors in Uptime Kuma";
  } else if (downNames.length || down > 0) { state = "crit"; head = "Service outage"; }
  else if (waitNames.length || maintNames.length || pend > 0 || offline.length) { state = "warn"; head = "Degraded performance"; }

  const notes = [];
  if (downNames.length) notes.push(list(downNames) + " down");
  if (waitNames.length) notes.push(list(waitNames) + " pending");
  if (maintNames.length) notes.push(list(maintNames) + " in maintenance");
  if (offline.length) notes.push(list(offline) + " offline");
  const sub = blind || (notes.length ? notes.join(" · ") : total + " services and " + hosts.length + " hosts are healthy");

  const stat = (key, value, of, cap) =>
    '<div class="stat"><div class="num"><span class="cnt k_' + key + '">' + value + "</span>" +
    (of === "" ? "" : '<span class="of"> ' + of + "</span>") + '</div><div class="cap">' + cap + "</div></div>";

  // second row: the smaller numbers. Zero down/pending stays grey; DNS and uptime take a tone when they slip.
  const mini = (key, value, cap, t) =>
    '<div class="mstat"><div class="mnum ' + (t || "") + '"><span class="cnt k_' + key + '">' + value + '</span></div><div class="cap">' + cap + "</div></div>";
  const upTone = (v) => (!Number.isFinite(v) ? "" : v < 95 ? "crit" : v < 99 ? "warn" : "");
  const dnsTone = !Number.isFinite(dns) ? "" : dns >= 500 ? "crit" : dns >= 100 ? "warn" : "";

  return wrap("head " + state,
    '<div class="lead"><span class="dot"></span><div class="msg"><div class="h">' + esc(head) +
    '</div><div class="s">' + esc(sub) + "</div></div></div>" +
    '<div class="stats">' +
    stat("svc", up, "of " + total, "Services up") +
    stat("hst", hostsOn, "of " + hosts.length, "Hosts online") +
    stat("up30", pct(uptime), "", "Uptime, 30 days") +
    '</div><div class="stats2">' +
    mini("down", down, "Down", down > 0 ? "crit" : "zero") +
    mini("pend", pend, "Pending", pend > 0 ? "warn" : "zero") +
    mini("up1d", pct(uptime1d), "Uptime, 24 hours", upTone(uptime1d)) +
    mini("dns", Number.isFinite(dns) ? Math.round(dns) + " ms" : "n/a", "DNS response", dnsTone) +
    "</div>");
}
context.handlebars.registerHelper("header", (data) => renderHeader(data));
