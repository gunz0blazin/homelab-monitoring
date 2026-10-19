# Generates grafana/dashboards/homelab.json: the single responsive "Homelab" dashboard (desktop and phone).
# Run from the repo root: python3 tools/gen_home.py
# The three cards (status header, hosts, services) are Business Text panels (plugin id
# marcusolsson-dynamictext-panel) whose HTML/JS/CSS live in tools/ui/. Edit those, regenerate, and commit
# the sources and the JSON together. Trend charts sit in a collapsed row and are native Grafana panels.
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dashlib import *  # noqa: E402,F401,F403

UI = os.path.join(HERE, "ui")
PLUGIN = "marcusolsson-dynamictext-panel"


def read(name):
    with open(os.path.join(UI, name)) as f:
        return f.read()


def ui_sources():
    """(common javascript with host names filled in, stylesheet with the .wN width classes appended)"""
    common = read("common.js").replace("__HOSTS__", json.dumps([[k, v] for k, v in HOST_NAMES.items()]))
    css = read("styles.css") + "\n/* static bar widths, used until after-render motion takes over */\n" + \
        "".join(f".w{i}{{width:{i}%}}" for i in range(101)) + "\n"
    return common, css


def q(ref, expr, tag):
    """Instant table query tagged with a `q` label so the card code finds each result without caring about order."""
    return {"datasource": DS, "refId": ref, "expr": f'label_replace(({expr}), "q", "{tag}", "", "")',
            "format": "table", "instant": True, "range": False, "legendFormat": ""}


def card(D, g, helper_file, helper_name, targets, loading):
    common, css = ui_sources()
    return D.add({
        "id": D.nid(), "type": PLUGIN, "title": "", "datasource": DS, "gridPos": g, "transparent": True,
        "targets": targets, "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {"renderMode": "data", "editors": ["default", "helpers", "styles", "afterRender"],
                    "content": "{{{" + helper_name + " data}}}",
                    "defaultContent": '<div class="hlw"><div class="hl skel"><div class="hd"><span class="ti">' + loading +
                                      '</span><span class="su">Waiting for data</span></div></div></div>',
                    "helpers": common + "\n" + read(helper_file), "styles": css,
                    "afterRender": read("after_render.js"), "externalStyles": [], "wrap": True,
                    "contentPartials": []}})


D = Dash(healthy=UP, maint=C["lavender"])

# --- 1. status header: is everything up, and if not, what
card(D, pos(0, 0, 24, 6), "header.js", "header", [
    q("A", 'count(monitor_status == 1) or vector(0)', "up"),
    q("B", 'count(monitor_status == 0) or vector(0)', "down"),
    q("C", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', "pend"),
    q("D", 'avg(monitor_uptime_ratio{window="30d"}) * 100', "up30"),
    q("E", 'monitor_status', "svc"),
    q("F", 'up{job="node"}', "hup"),
], "Status")

# --- 2. hosts and 3. services, side by side on desktop, stacked on a phone
CPU = '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))'
MEM = '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))'
DSK = ('100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / '
       'node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))')
card(D, pos(0, 6, 14, 11), "hosts.js", "hosts", [
    q("A", f"max by (host) ({CPU})", "cpu"), q("B", f"max by (host) ({MEM})", "mem"),
    q("C", f"max by (host) ({DSK})", "dsk"), q("D", 'up{job="node"}', "hup"),
], "Hosts")
card(D, pos(14, 6, 10, 11), "services.js", "services", [
    q("A", "monitor_status", "svc"), q("B", "monitor_response_time", "resp"),
    q("C", 'monitor_uptime_ratio{window="30d"} * 100', "svcup"),
], "Services")

# --- 4. trends: open by default, quiet native charts
rate_cpu = CPU.replace("[5m]", "[$__rate_interval]")
hosts = color_overrides(HOST_COLORS_COOL, HOST_NAMES)
ms_colors = [{"matcher": {"id": "byName", "options": "Average"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": C["blue"]}}]},
             {"matcher": {"id": "byName", "options": "Slowest"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": C["overlay0"]}}]}]
charts = [
    D.calm_timeseries("Response time", [("avg(monitor_response_time)", "Average"), ("max(monitor_response_time)", "Slowest")],
                      pos(0, 18, 12, 8), "ms", vmin=0, overrides=ms_colors, desc="Average and slowest check time across all services."),
    D.calm_timeseries("CPU", [(rate_cpu, "{{host}}")], pos(12, 18, 12, 8), "percent", 0, 100, hosts),
    D.calm_timeseries("Memory", [(MEM, "{{host}}")], pos(0, 26, 12, 8), "percent", 0, 100, hosts),
    D.calm_timeseries("Disk", [(DSK, "{{host}}")], pos(12, 26, 12, 8), "percent", 0, 100, hosts),
]
# Open by default: an expanded row has an empty `panels` list and its charts follow it at the top level.
# To collapse it again, set "collapsed" to True and move `charts` into the row's `panels`.
D.add({"id": D.nid(), "type": "row", "title": "Trends", "collapsed": False, "gridPos": pos(0, 17, 24, 1), "panels": []})
for chart in charts:
    D.add(chart)

D.finish("grafana/dashboards/homelab.json", "homelab", "Homelab",
         "Status, hosts and services for the home lab. Source: the homelab-monitoring repo.",
         ["homelab"], ("Classic view", "/d/homelab-overview"), refresh="5s", hide_ds=True)
