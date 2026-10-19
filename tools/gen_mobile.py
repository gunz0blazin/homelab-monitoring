# Generates grafana/dashboards/homelab-mobile.json. Run from the repo root: python3 tools/gen_mobile.py
# Edit this script (or dashlib.py), regenerate, and commit the script and the JSON together.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashlib import *  # noqa: E402,F401,F403

D = Dash()
quiet = lambda hit: steps((MUTED, None), (hit, 1))

D.stat("Up", 'count(monitor_status == 1) or vector(0)', pos(0, 0, 8, 4), thresholds=steps((HEALTHY, None)), instant=True)
D.stat("Down", 'count(monitor_status == 0) or vector(0)', pos(8, 0, 8, 4), thresholds=quiet(BAD), instant=True)
D.stat("Pending", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', pos(16, 0, 8, 4),
       thresholds=quiet(PENDING), instant=True)
D.stat("Uptime 24h", 'avg(monitor_uptime_ratio{window="1d"}) * 100', pos(0, 4, 12, 3), unit="percent", decimals=2,
       thresholds=UPTIME, instant=True, size=32)
D.stat("Uptime 30d", 'avg(monitor_uptime_ratio{window="30d"}) * 100', pos(12, 4, 12, 3), unit="percent", decimals=2,
       thresholds=UPTIME, instant=True, size=32)

# one line per service: its name, and UP or DOWN in colour
board = D.stat("Services", "monitor_status", pos(0, 7, 24, 12), thresholds=STATUS, instant=True,
               legend="{{monitor_name}}", text="value_and_name", size=28)
board["fieldConfig"]["defaults"]["mappings"] = D.status_mappings()

D.bars("CPU", '100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m]))))',
       pos(0, 19, 24, 10), PCT_USED)
D.bars("Memory", '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))', pos(0, 29, 24, 10), PCT_USED)
D.bars("Disk (/)",
       '100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}))',
       pos(0, 39, 24, 10), PCT_USED)
D.timeseries("Response time", "monitor_response_time", "{{monitor_name}}", pos(0, 49, 24, 8), "ms", vmin=0,
             overrides=color_overrides(MONITOR_COLORS), table_legend=False)

D.finish("grafana/dashboards/homelab-mobile.json", "homelab-mobile", "Homelab Mobile",
         "Phone-sized view of Homelab Overview: status at a glance and one bar per host. Source: the homelab-monitoring repo.",
         ["homelab", "mobile"], ("Full dashboard", "/d/homelab-overview"), hide_ds=True)
