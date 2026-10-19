# Generates grafana/dashboards/homelab-overview.json. Run from the repo root: python3 tools/gen_overview.py
# Edit this script (or dashlib.py), regenerate, and commit the script and the JSON together.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashlib import *  # noqa: E402,F401,F403

D = Dash()

# --- the numbers, floating on the canvas
quiet = lambda hit: steps((MUTED, None), (hit, 1))    # zero is calm grey, one or more takes the warning colour
D.stat("Up", 'count(monitor_status == 1) or vector(0)', pos(0, 0, 4, 4), thresholds=steps((HEALTHY, None)))
D.stat("Down", 'count(monitor_status == 0) or vector(0)', pos(4, 0, 4, 4), thresholds=quiet(BAD),
       desc="Monitors whose last check failed")
D.stat("Pending", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', pos(8, 0, 4, 4),
       thresholds=quiet(PENDING), desc="Checks that failed and are being retried, or are in maintenance")
D.stat("Uptime 24h", 'avg(monitor_uptime_ratio{window="1d"}) * 100', pos(12, 0, 4, 4), unit="percent",
       decimals=2, thresholds=UPTIME)
D.stat("Uptime 30d", 'avg(monitor_uptime_ratio{window="30d"}) * 100', pos(16, 0, 4, 4), unit="percent",
       decimals=2, thresholds=UPTIME)
D.stat("DNS time", 'monitor_response_time{monitor_type="dns"}', pos(20, 0, 4, 4), unit="ms", decimals=0,
       thresholds=steps((INFO, None), (WARN, 100), (BAD, 500)), area=True, desc="How long the Pi-hole takes to answer")

# --- status timeline
D.add({"id": D.nid(), "type": "state-timeline", "title": "Service status", "datasource": DS,
       "gridPos": pos(0, 4, 24, 9),
       "targets": [D.target("monitor_status", "{{monitor_name}}")],
       "fieldConfig": {"defaults": {"color": {"mode": "thresholds"},
                                    "custom": {"fillOpacity": 55, "lineWidth": 0},
                                    "mappings": D.status_mappings(), "thresholds": STATUS}, "overrides": []},
       "options": {"mergeValues": True, "showValue": "never", "rowHeight": 0.7, "alignValue": "center",
                   "legend": {"displayMode": "list", "placement": "bottom", "showLegend": False},
                   "tooltip": {"mode": "single", "sort": "none"}}})

# --- response times and 30 day uptime
D.timeseries("Response time", "monitor_response_time", "{{monitor_name}}", pos(0, 13, 14, 12), "ms", vmin=0,
             overrides=color_overrides(MONITOR_COLORS))
D.bars("Uptime by service, 30 days", 'monitor_uptime_ratio{window="30d"} * 100', pos(14, 13, 10, 12), UPTIME,
       unit="percent", vmin=90, vmax=100, decimals=2, legend="{{monitor_name}}")

# --- hosts
D.add({"id": D.nid(), "type": "row", "title": "Hosts (node exporter)", "collapsed": False,
       "gridPos": pos(0, 25, 24, 1), "panels": []})
hosts = color_overrides(HOST_COLORS)
D.timeseries("CPU used", '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))',
             "{{host}}", pos(0, 26, 8, 8), "percent", 0, 100, hosts)
D.timeseries("Memory used", '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))',
             "{{host}}", pos(8, 26, 8, 8), "percent", 0, 100, hosts)
D.timeseries("Disk used (/)",
             '100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))',
             "{{host}}", pos(16, 26, 8, 8), "percent", 0, 100, hosts)

D.finish("grafana/dashboards/homelab-overview.json", "homelab-overview", "Homelab Overview",
         "Service status from Uptime Kuma, and host load from node exporters. Source: the homelab-monitoring repo.",
         ["homelab"], ("Mobile view", "/d/homelab-mobile"))
