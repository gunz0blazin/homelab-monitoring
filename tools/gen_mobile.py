# Generates the dashboard JSON in grafana/dashboards/. Run from the repo root: python3 tools/gen_mobile.py
# Edit this script, regenerate, and commit both the script and the JSON.
import json
import re

GREEN, RED, YELLOW, BLUE = "#a6e3a1", "#f38ba8", "#f9e2af", "#89b4fa"
DS = {"type": "prometheus", "uid": "${datasource}"}
_id = 0

# Catppuccin Mocha accents for graph lines. Matched by regex on the series name, so a trailing
# space in a monitor name (Kuma keeps what was typed) still matches. New monitors that are not
# listed fall back to Grafana's classic palette.
HOST_COLORS = {"proxmox": "#fab387", "pihole": "#f38ba8", "dockers": "#89b4fa",
               "tailscale": "#94e2d5", "plex": "#f9e2af", "qbittorrent": "#cba6f7"}
MONITOR_COLORS = {"420NAS": "#94e2d5", "Grafana": "#fab387", "Home Assistant": "#89dceb", "NPM": "#b4befe",
                  "PiHole Primary": "#f38ba8", "Plex": "#f9e2af", "Proxmox": "#eba0ac", "qBittorent": "#89b4fa",
                  "Uptime Kuma": "#a6e3a1"}

def color_overrides(mapping):
    return [{"matcher": {"id": "byRegexp", "options": "^" + name + r"\s*$"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": hexc}}]}
            for name, hexc in mapping.items()]

def nid():
    global _id
    _id += 1
    return _id

def steps(*pairs):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}

def target(expr, legend="", instant=False):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A"}
    if instant:
        t["instant"] = True
        t["range"] = False
    return t

def pos(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}

def stat(title, expr, g, unit="none", decimals=None, thresholds=None, text="value"):
    d = {"unit": unit, "color": {"mode": "thresholds"}, "thresholds": thresholds or steps((GREEN, None))}
    if decimals is not None:
        d["decimals"] = decimals
    return {"id": nid(), "type": "stat", "title": title, "datasource": DS, "gridPos": g,
            "targets": [target(expr, instant=True)],
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center",
                        "orientation": "auto", "textMode": text,
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}

def bars(title, expr, g, thresholds):
    return {"id": nid(), "type": "bargauge", "title": title, "datasource": DS, "gridPos": g,
            "targets": [target(expr, "{{host}}", instant=True)],
            "fieldConfig": {"defaults": {"unit": "percent", "decimals": 0, "min": 0, "max": 100,
                                         "color": {"mode": "thresholds"}, "thresholds": thresholds}, "overrides": []},
            "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                        "valueMode": "color", "namePlacement": "top", "minVizHeight": 16, "minVizWidth": 8,
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}

panels = [
    stat("Up", 'count(monitor_status == 1) or vector(0)', pos(0, 0, 8, 4), thresholds=steps((GREEN, None))),
    stat("Down", 'count(monitor_status == 0) or vector(0)', pos(8, 0, 8, 4), thresholds=steps((GREEN, None), (RED, 1))),
    stat("Pending", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', pos(16, 0, 8, 4), thresholds=steps((GREEN, None), (YELLOW, 1))),
    stat("Uptime 24h", 'avg(monitor_uptime_ratio{window="1d"}) * 100', pos(0, 4, 12, 3), unit="percent", decimals=2,
         thresholds=steps((RED, None), (YELLOW, 99), (GREEN, 99.9))),
    stat("Uptime 30d", 'avg(monitor_uptime_ratio{window="30d"}) * 100', pos(12, 4, 12, 3), unit="percent", decimals=2,
         thresholds=steps((RED, None), (YELLOW, 99), (GREEN, 99.9))),
]

# one big coloured tile per service
board = stat("Services", "monitor_status", pos(0, 7, 24, 12), text="value_and_name",
             thresholds=steps((RED, None), (GREEN, 1), (YELLOW, 2), (BLUE, 3)))
board["targets"] = [target("monitor_status", "{{monitor_name}}", instant=True)]
board["fieldConfig"]["defaults"]["mappings"] = [{"type": "value", "options": {
    "0": {"text": "DOWN", "color": RED, "index": 0},
    "1": {"text": "UP", "color": GREEN, "index": 1},
    "2": {"text": "PENDING", "color": YELLOW, "index": 2},
    "3": {"text": "MAINT", "color": BLUE, "index": 3}}}]
board["options"]["wideLayout"] = True
panels.append(board)

pct = steps((GREEN, None), (YELLOW, 75), (RED, 90))
panels += [
    bars("CPU", '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))', pos(0, 19, 24, 7), pct),
    bars("Memory", '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))', pos(0, 26, 24, 7), pct),
    bars("Disk (/)", '100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))', pos(0, 33, 24, 7), pct),
]

# one response-time graph, no legend table (the tooltip names the line)
panels.append({"id": nid(), "type": "timeseries", "title": "Response time", "datasource": DS, "gridPos": pos(0, 40, 24, 8),
               "targets": [target("monitor_response_time", "{{monitor_name}}")],
               "fieldConfig": {"defaults": {"unit": "ms", "min": 0, "color": {"mode": "palette-classic"},
                                            "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 8, "showPoints": "never",
                                                       "lineInterpolation": "smooth", "spanNulls": True}}, "overrides": color_overrides(MONITOR_COLORS)},
               "options": {"legend": {"showLegend": False, "displayMode": "list", "placement": "bottom", "calcs": []},
                           "tooltip": {"mode": "multi", "sort": "desc"}}})

dashboard = {
    "uid": "homelab-mobile", "title": "Homelab Mobile", "tags": ["homelab", "mobile"],
    "timezone": "browser", "schemaVersion": 39, "version": 1, "editable": True,
    "graphTooltip": 0, "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
    "description": "Phone-sized view of Homelab Overview: big status tiles and one bar per host. Source: the homelab-monitoring repo.",
    "templating": {"list": [{"name": "datasource", "label": "Data source", "type": "datasource", "query": "prometheus",
                             "current": {}, "hide": 2, "includeAll": False, "multi": False, "options": [], "refresh": 1}]},
    "annotations": {"list": []},
    "links": [{"title": "Full dashboard", "type": "link", "url": "/d/homelab-overview", "icon": "dashboard",
               "targetBlank": False, "asDropdown": False, "includeVars": False, "keepTime": False, "tags": [], "tooltip": ""}],
    "panels": panels}

with open("grafana/dashboards/homelab-mobile.json", "w") as f:
    json.dump(dashboard, f, indent=2); f.write("\n")

ids = [p["id"] for p in panels]
assert len(ids) == len(set(ids)), "duplicate panel ids"
boxes = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"], p["title"]) for p in panels]
for x, y, w, h, t in boxes:
    assert 0 <= x and x + w <= 24, f"{t} runs off the grid"
for i, a in enumerate(boxes):
    for b in boxes[i + 1:]:
        assert not (a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]), f"{a[4]} overlaps {b[4]}"
print(f"ok: {len(panels)} panels, stacked full width, no overlaps")
