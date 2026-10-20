# Generates the two testing dashboards from the same cards: grafana/dashboards/homelab.json (phone layout,
# "Testing mobile") and grafana/dashboards/homelab-desktop.json (wide layout, "Testing desktop").
# Run from the repo root: python3 tools/gen_home.py
# The three cards (status header, hosts, services) are Business Text panels (plugin id
# marcusolsson-dynamictext-panel) whose HTML/JS/CSS live in tools/ui/. Edit those, regenerate, and commit
# the sources and the JSON together. The main dashboard's graphs (status grid, uptime and latency bars) and the trend charts are native Grafana panels.
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


CPU = '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))'
MEM = '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))'
DSK = ('100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / '
       'node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))')
RATE_CPU = CPU.replace("[5m]", "[$__rate_interval]")
HOSTS = color_overrides(HOST_COLORS_COOL, HOST_NAMES)

# Grid layouts (24 columns). Panel order is also the order they stack in on a narrow screen.
LAYOUTS = {
    # phone first: full-width header, hosts and services side by side on a wide screen, then the main
    # dashboard's graphs (status grid, uptime and latency bars), then the trend charts
    "mobile": {"header": pos(0, 0, 24, 8), "hosts": pos(0, 8, 14, 12), "services": pos(14, 8, 10, 12),
               "grid": pos(0, 20, 24, 11), "pts": 40, "uptime": pos(0, 31, 12, 15), "latency": pos(12, 31, 12, 15),
               "row": pos(0, 46, 24, 1),
               "charts": [pos(0, 47, 24, 9), pos(0, 56, 12, 8), pos(12, 56, 12, 8), pos(0, 64, 24, 8)]},
    # wide screens: hosts and services half and half, then everything from the main dashboard
    "desktop": {"header": pos(0, 0, 24, 7), "hosts": pos(0, 7, 12, 12), "services": pos(12, 7, 12, 12),
                "grid": pos(0, 19, 24, 9), "pts": 60, "uptime": pos(0, 28, 12, 11), "latency": pos(12, 28, 12, 11),
                "row": pos(0, 39, 24, 1),
                "charts": [pos(0, 40, 24, 10), pos(0, 50, 8, 9), pos(8, 50, 8, 9), pos(16, 50, 8, 9)]},
}


def build(kind, uid, title, path, description):
    g = LAYOUTS[kind]
    D = Dash(healthy=UP, maint=C["lavender"])

    # 1. status header: is everything up, and if not, what
    card(D, g["header"], "header.js", "header", [
        q("A", 'count(' + STATUS_Q + ' == 1) or vector(0)', "up"),
        q("B", 'count(' + STATUS_Q + ' == 0) or vector(0)', "down"),
        q("C", 'count(' + STATUS_Q + ' == 2 or ' + STATUS_Q + ' == 3) or vector(0)', "pend"),
        q("D", 'avg(' + UPTIME_Q("30d") + ') * 100', "up30"),
        q("E", STATUS_Q, "svc"),
        q("F", 'up{job="node"}', "hup"),
        q("G", 'up{job="uptime-kuma"}', "kup"),
        q("H", 'avg(' + UPTIME_Q("1d") + ') * 100', "up1d"),
        q("I", 'avg(monitor_response_time{monitor_type="dns",' + NOT_TESTER + '})', "dns"),
        # the Down Tester: shown in the card's second row, counted in nothing else
        q("J", 'max(monitor_status{' + ONLY_TESTER + '})', "tester"),
    ], "Status")

    # 2. hosts and 3. services
    card(D, g["hosts"], "hosts.js", "hosts", [
        q("A", f"max by (host) ({CPU})", "cpu"), q("B", f"max by (host) ({MEM})", "mem"),
        q("C", f"max by (host) ({DSK})", "dsk"), q("D", 'up{job="node"}', "hup"),
    ], "Hosts")
    card(D, g["services"], "services.js", "services", [
        q("A", STATUS_Q, "svc"), q("B", RESPONSE_Q, "resp"),
        q("C", UPTIME_Q("30d") + " * 100", "svcup"),
    ], "Services")

    # 4. the main dashboard's graphs, in the calm style: status grid, uptime bars, latency bars
    D.status_history("Service status, last 6 hours", STATUS_Q, "{{monitor_name}}", g["grid"], points=g["pts"],
                     desc="One row per service. Blue is up, red is down, yellow is retrying.")
    D.bars("Uptime by service, 30 days", UPTIME_Q("30d") + " * 100", g["uptime"], UPTIME_M,
           unit="percent", vmin=90, vmax=100, decimals=2, legend="{{monitor_name}}", display="basic", transparent=True,
           title_size=12, value_size=14)
    D.bars("Latency now", RESPONSE_Q, g["latency"], steps((INFO, None)), unit="ms", vmin=0, vmax=None,
           legend="{{monitor_name}}", display="gradient", overrides=color_overrides(MONITOR_COLORS_M), transparent=True,
           title_size=12, value_size=14, desc="Most recent check time for each service.")

    # 5. trends: open by default (an expanded row has an empty `panels` list and its charts follow it at the
    # top level; to collapse it, set "collapsed" to True and move the charts into the row's `panels`)
    D.add({"id": D.nid(), "type": "row", "title": "Trends", "collapsed": False, "gridPos": g["row"], "panels": []})
    c = g["charts"]
    for chart in (
        D.calm_timeseries("Response time", [(RESPONSE_Q, "{{monitor_name}}")], c[0], "ms", vmin=0,
                          overrides=color_overrides(MONITOR_COLORS_M), legend=True,
                          desc="Check time for each service over the selected time range."),
        D.calm_timeseries("CPU", [(RATE_CPU, "{{host}}")], c[1], "percent", 0, 100, HOSTS),
        D.calm_timeseries("Memory", [(MEM, "{{host}}")], c[2], "percent", 0, 100, HOSTS),
        D.calm_timeseries("Disk", [(DSK, "{{host}}")], c[3], "percent", 0, 100, HOSTS),
    ):
        D.add(chart)

    D.finish(path, uid, title, description, ["homelab", "testing"], nav_links(uid), hide_ds=True)


build("mobile", "homelab", "Homelab Testing Mobile", "grafana/dashboards/homelab.json",
      "Status, hosts and services for the home lab, laid out for a phone. Source: the homelab-monitoring repo.")
build("desktop", "homelab-desktop", "Homelab Testing Desktop", "grafana/dashboards/homelab-desktop.json",
      "Status, hosts and services for the home lab, laid out for a wide screen. Source: the homelab-monitoring repo.")
