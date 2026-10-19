// Host list: one row per machine, CPU / memory / disk as thin meters. Colour only appears at 75% and 90%.
function renderHosts(data) {
  const R = records(data);
  const known = HOSTS.map((h) => h[0]);
  const seen = [...new Set(R.map((r) => r.host).filter(Boolean))];
  const order = known.filter((k) => seen.includes(k)).concat(seen.filter((k) => !known.includes(k)).sort());
  if (!order.length) return skeleton("Hosts");

  const val = (q, host) => num(only(R, q).find((r) => r.host === host));
  const meter = (host, key, label, v) => {
    const k = "k_" + slug(host) + "-" + key;
    if (!Number.isFinite(v)) {
      return '<div class="m off"><div class="mt"><span class="lab">' + label + '</span><span class="val">n/a</span></div><div class="trk"></div></div>';
    }
    const t = tone(v), w = clamp(v);
    return '<div class="m"><div class="mt"><span class="lab">' + label + '</span><span class="val ' + t + " cnt " + k + '">' +
      Math.round(v) + '%</span></div><div class="trk"><div class="fil ' + t + " w" + w + " " + k + '"></div></div></div>';
  };

  const online = order.filter((h) => val("hup", h) !== 0).length;
  const rows = order.map((h) => {
    const down = val("hup", h) === 0;
    return '<div class="row' + (down ? " gone" : "") + '"><div class="nm">' + esc(hostName(h)) +
      (down ? '<span class="tag crit">Offline</span>' : "") + "</div>" +
      meter(h, "cpu", "CPU", down ? NaN : val("cpu", h)) +
      meter(h, "mem", "Mem<b>ory</b>", down ? NaN : val("mem", h)) +
      meter(h, "dsk", "Disk", down ? NaN : val("dsk", h)) + "</div>";
  }).join("");

  return wrap("hosts", '<div class="hd"><span class="ti">Hosts</span><span class="su">' + online + " of " + order.length + " online</span></div>" + rows);
}
context.handlebars.registerHelper("hosts", (data) => renderHosts(data));
