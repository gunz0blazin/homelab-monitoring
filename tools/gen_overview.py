# Generates grafana/dashboards/homelab-overview.json. Run from the repo root: python3 tools/gen_overview.py
# Edit this script (or dashlib.py), regenerate, and commit the script and the JSON together.
# Same look as gen_mobile.py: no greens ("up" is sapphire, the banner is mauve), red/peach/yellow only for trouble.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashlib import *  # noqa: E402,F401,F403

D = Dash(healthy=UP, maint=C["lavender"])
quiet = lambda hit: steps((MUTED, None), (hit, 1))    # zero is calm grey, one or more takes the warning colour

# --- top strip: banner, counts, uptime, DNS (side by side; this is the wide layout)
D.hero("", '(count(monitor_status == 0) or vector(0)) * 10 + (count(monitor_status == 2 or monitor_status == 3) or vector(0))',
       pos(0, 0, 8, 5), up=C["mauve"])
D.multi_stat("services", [
    ("Up", 'count(monitor_status == 1) or vector(0)', steps((UP, None)), "none", 0),
    ("Down", 'count(monitor_status == 0) or vector(0)', quiet(BAD), "none", 0),
    ("Pending", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', quiet(PENDING), "none", 0),
], pos(8, 0, 7, 5), size=40)
D.multi_stat("uptime", [
    ("24 hours", 'avg(monitor_uptime_ratio{window="1d"}) * 100', UPTIME_M, "percent", 2),
    ("30 days", 'avg(monitor_uptime_ratio{window="30d"}) * 100', UPTIME_M, "percent", 2),
], pos(15, 0, 5, 5), size=26)
D.stat("DNS time", 'monitor_response_time{monitor_type="dns"}', pos(20, 0, 4, 5), unit="ms", decimals=0,
       thresholds=steps((C["mauve"], None), (WARN, 100), (BAD, 500)), area=True, desc="How long the Pi-hole takes to answer")

# --- one row per service, one cell per ~6 minutes of the last 6 hours
D.status_history("last 6 hours", "monitor_status", "{{monitor_name}}", pos(0, 5, 24, 9), points=60)

# --- response times and 30 day uptime
D.timeseries("Response time", "monitor_response_time", "{{monitor_name}}", pos(0, 14, 14, 14), "ms", vmin=0,
             overrides=color_overrides(MONITOR_COLORS_M))
D.bars("Uptime by service, 30 days", 'monitor_uptime_ratio{window="30d"} * 100', pos(14, 14, 10, 14), UPTIME_M,
       unit="percent", vmin=90, vmax=100, decimals=2, legend="{{monitor_name}}", display="gradient", transparent=True,
       title_size=12, value_size=14)

# --- hosts: gauges first, trends underneath
D.add({"id": D.nid(), "type": "row", "title": "Host health", "collapsed": False,
       "gridPos": pos(0, 28, 24, 1), "panels": []})
D.host_table("hosts", [
    ("CPU", 'max by (host) (100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m])))))', C["blue"]),
    ("Mem", 'max by (host) (100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)))', C["mauve"]),
    ("Disk", 'max by (host) (100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"})))', C["lavender"]),
], pos(0, 29, 24, 9))
hosts = color_overrides(HOST_COLORS_M)
D.timeseries("CPU used", '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))',
             "{{host}}", pos(0, 38, 8, 8), "percent", 0, 100, hosts)
D.timeseries("Memory used", '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))',
             "{{host}}", pos(8, 38, 8, 8), "percent", 0, 100, hosts)
D.timeseries("Disk used (/)",
             '100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))',
             "{{host}}", pos(16, 38, 8, 8), "percent", 0, 100, hosts)

D.finish("grafana/dashboards/homelab-overview.json", "homelab-overview", "Homelab Overview",
         "Service status from Uptime Kuma, and host load from node exporters. Source: the homelab-monitoring repo.",
         ["homelab"], ("Mobile view", "/d/homelab-mobile"))
