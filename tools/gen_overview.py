# Generates the dashboard JSON in grafana/dashboards/. Run from the repo root: python3 tools/gen_overview.py
# Edit this script, regenerate, and commit both the script and the JSON.
import json
import re

GREEN, RED, YELLOW, BLUE, MAUVE, PEACH = "#a6e3a1", "#f38ba8", "#f9e2af", "#89b4fa", "#cba6f7", "#fab387"
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
    """pairs: (color, from_value) with the first being the base."""
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}

def target(expr, legend="", instant=False, ref="A"):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t["instant"] = True
        t["range"] = False
    return t

def stat(title, expr, x, w, unit="none", decimals=None, thresholds=None, desc=""):
    defaults = {"unit": unit, "color": {"mode": "thresholds"},
                "thresholds": thresholds or steps((GREEN, None))}
    if decimals is not None:
        defaults["decimals"] = decimals
    return {"id": nid(), "type": "stat", "title": title, "description": desc,
            "datasource": DS, "gridPos": {"x": x, "y": 0, "w": w, "h": 4},
            "targets": [target(expr)],
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center",
                        "orientation": "auto", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}

def timeseries(title, expr, legend, x, y, w, h, unit, vmin=None, vmax=None, thresholds=None, calcs=("mean", "max"), overrides=None):
    defaults = {"unit": unit, "color": {"mode": "palette-classic"},
                "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 8, "showPoints": "never",
                           "lineInterpolation": "smooth", "spanNulls": True}}
    if vmin is not None: defaults["min"] = vmin
    if vmax is not None: defaults["max"] = vmax
    if thresholds: defaults["thresholds"] = thresholds
    return {"id": nid(), "type": "timeseries", "title": title, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [target(expr, legend)],
            "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom", "showLegend": True, "calcs": list(calcs)},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}

panels = []
# --- top row of numbers
panels += [
    stat("Services up", 'count(monitor_status == 1) or vector(0)', 0, 4, thresholds=steps((GREEN, None))),
    stat("Services down", 'count(monitor_status == 0) or vector(0)', 4, 4,
         thresholds=steps((GREEN, None), (RED, 1)), desc="Monitors whose last check failed"),
    stat("Pending", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', 8, 4,
         thresholds=steps((GREEN, None), (YELLOW, 1)), desc="Checks that failed and are being retried, or are in maintenance"),
    stat("Uptime, 24 hours", 'avg(monitor_uptime_ratio{window="1d"}) * 100', 12, 4, unit="percent", decimals=2,
         thresholds=steps((RED, None), (YELLOW, 99), (GREEN, 99.9))),
    stat("Uptime, 30 days", 'avg(monitor_uptime_ratio{window="30d"}) * 100', 16, 4, unit="percent", decimals=2,
         thresholds=steps((RED, None), (YELLOW, 99), (GREEN, 99.9))),
    stat("DNS answer time", 'monitor_response_time{monitor_type="dns"}', 20, 4, unit="ms", decimals=0,
         thresholds=steps((GREEN, None), (YELLOW, 100), (RED, 500)), desc="How long the Pi-hole takes to answer"),
]

# --- status timeline
panels.append({
    "id": nid(), "type": "state-timeline", "title": "Service status", "datasource": DS,
    "gridPos": {"x": 0, "y": 4, "w": 24, "h": 9},
    "targets": [target("monitor_status", "{{monitor_name}}")],
    "fieldConfig": {"defaults": {
        "color": {"mode": "thresholds"},
        "custom": {"fillOpacity": 80, "lineWidth": 0},
        "mappings": [{"type": "value", "options": {
            "0": {"text": "DOWN", "color": RED, "index": 0},
            "1": {"text": "UP", "color": GREEN, "index": 1},
            "2": {"text": "PENDING", "color": YELLOW, "index": 2},
            "3": {"text": "MAINTENANCE", "color": BLUE, "index": 3}}}],
        "thresholds": steps((GREEN, None))}, "overrides": []},
    "options": {"mergeValues": True, "showValue": "never", "rowHeight": 0.85, "alignValue": "center",
                "legend": {"displayMode": "list", "placement": "bottom", "showLegend": False},
                "tooltip": {"mode": "single", "sort": "none"}}})

# --- response times + 30 day uptime bars
panels.append(timeseries("Response time", "monitor_response_time", "{{monitor_name}}", 0, 13, 14, 9, "ms", vmin=0,
                         overrides=color_overrides(MONITOR_COLORS)))
panels.append({
    "id": nid(), "type": "bargauge", "title": "Uptime by service, 30 days", "datasource": DS,
    "gridPos": {"x": 14, "y": 13, "w": 10, "h": 9},
    "targets": [target('monitor_uptime_ratio{window="30d"} * 100', "{{monitor_name}}", instant=True)],
    "fieldConfig": {"defaults": {"unit": "percent", "decimals": 2, "min": 90, "max": 100,
                                 "color": {"mode": "thresholds"},
                                 "thresholds": steps((RED, None), (YELLOW, 99), (GREEN, 99.9))}, "overrides": []},
    "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                "valueMode": "color", "namePlacement": "auto", "minVizHeight": 16, "minVizWidth": 8,
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})

# --- hosts
panels.append({"id": nid(), "type": "row", "title": "Hosts (node exporter)", "collapsed": False,
               "gridPos": {"x": 0, "y": 22, "w": 24, "h": 1}, "panels": []})
pct = steps((GREEN, None), (YELLOW, 75), (RED, 90))
panels.append(timeseries("CPU used", '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))',
                         "{{host}}", 0, 23, 8, 8, "percent", 0, 100, pct, overrides=color_overrides(HOST_COLORS)))
panels.append(timeseries("Memory used", '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))',
                         "{{host}}", 8, 23, 8, 8, "percent", 0, 100, pct, overrides=color_overrides(HOST_COLORS)))
panels.append(timeseries("Disk used (/)",
                         '100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))',
                         "{{host}}", 16, 23, 8, 8, "percent", 0, 100, pct, overrides=color_overrides(HOST_COLORS)))

dashboard = {
    "uid": "homelab-overview", "title": "Homelab Overview", "tags": ["homelab"],
    "timezone": "browser", "schemaVersion": 39, "version": 1, "editable": True,
    "graphTooltip": 1, "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
    "description": "Service status from Uptime Kuma, and host load from node exporters. Source: the homelab-monitoring repo.",
    "templating": {"list": [{
        "name": "datasource", "label": "Data source", "type": "datasource", "query": "prometheus",
        "current": {}, "hide": 0, "includeAll": False, "multi": False, "options": [], "refresh": 1}]},
    "annotations": {"list": []}, "panels": panels,
    "links": [{"title": "Mobile view", "type": "link", "url": "/d/homelab-mobile", "icon": "dashboard",
               "targetBlank": False, "asDropdown": False, "includeVars": False, "keepTime": False, "tags": [], "tooltip": ""}]}

with open("grafana/dashboards/homelab-overview.json", "w") as f:
    json.dump(dashboard, f, indent=2)
    f.write("\n")

# ---- structural checks
ids = [p["id"] for p in panels]
assert len(ids) == len(set(ids)), "duplicate panel ids"
boxes = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"], p["title"]) for p in panels]
for x, y, w, h, t in boxes:
    assert 0 <= x and x + w <= 24, f"{t} runs off the 24-column grid"
for i, a in enumerate(boxes):
    for b in boxes[i + 1:]:
        overlap = a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
        assert not overlap, f"{a[4]} overlaps {b[4]}"
print(f"ok: {len(panels)} panels, no overlaps, all within the grid")
