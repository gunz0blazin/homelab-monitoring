# Generates grafana/dashboards/homelab-mobile.json. Run from the repo root: python3 tools/gen_mobile.py
# Edit this script (or dashlib.py), regenerate, and commit the script and the JSON together.
#
# Phone layout note: Grafana stacks every panel full width in a single column on a phone, whatever the
# x/w in the grid. Anything that should sit side by side (the three counts, the two uptimes, the host
# metrics) therefore lives inside ONE panel as several values, not as several small panels.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashlib import *  # noqa: E402,F401,F403

# No greens on this board: "up" is sapphire, the banner is mauve, and red/peach/yellow still mean trouble.
D = Dash(healthy=UP, maint=C["lavender"])   # UP, UPTIME_M, MONITOR_COLORS_M come from dashlib
quiet = lambda hit: steps((MUTED, None), (hit, 1))

# 1. banner: one phrase for the whole lab
D.hero("", '(count(monitor_status == 0) or vector(0)) * 10 + (count(monitor_status == 2 or monitor_status == 3) or vector(0))',
       pos(0, 0, 24, 4), up=C["mauve"])

# 2. the three counts, side by side
D.multi_stat("services", [
    ("Up", 'count(monitor_status == 1) or vector(0)', steps((UP, None)), "none", 0),
    ("Down", 'count(monitor_status == 0) or vector(0)', quiet(BAD), "none", 0),
    ("Pending", 'count(monitor_status == 2 or monitor_status == 3) or vector(0)', quiet(PENDING), "none", 0),
], pos(0, 4, 24, 5), size=44)

# 3. uptime, side by side
D.multi_stat("uptime", [
    ("24 hours", 'avg(monitor_uptime_ratio{window="1d"}) * 100', UPTIME_M, "percent", 2),
    ("30 days", 'avg(monitor_uptime_ratio{window="30d"}) * 100', UPTIME_M, "percent", 2),
], pos(0, 9, 24, 4), size=30)

# 4. one row per service, one cell per ~10 minutes of the last 6 hours
D.status_history("last 6 hours", "monitor_status", "{{monitor_name}}", pos(0, 13, 24, 11))

# 5. one row per host, CPU / memory / disk as gradient gauges
D.host_table("hosts", [
    ("CPU", 'max by (host) (100 * (1 - (sum by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m])) / sum by (host) (rate(node_cpu_seconds_total[5m])))))', C["blue"]),
    ("Mem", 'max by (host) (100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)))', C["mauve"]),
    ("Disk", 'max by (host) (100 * (1 - (node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"})))', C["lavender"]),
], pos(0, 24, 24, 11))

# 6. latest response time per service, each bar in its own Mocha colour
D.bars("latency now", "monitor_response_time", pos(0, 35, 24, 10), steps((INFO, None)), unit="ms", vmin=0, vmax=None,
       legend="{{monitor_name}}", display="gradient", overrides=color_overrides(MONITOR_COLORS_M), transparent=True)

# 7. response time over the last 6 hours
D.timeseries("response time", "monitor_response_time", "{{monitor_name}}", pos(0, 45, 24, 8), "ms", vmin=0,
             overrides=color_overrides(MONITOR_COLORS_M), table_legend=False)

D.finish("grafana/dashboards/homelab-mobile.json", "homelab-mobile", "Homelab Mobile",
         "Phone-sized view of Homelab Overview: one status banner, a 6-hour status grid, and host gauges. Source: the homelab-monitoring repo.",
         ["homelab", "mobile"], ("Full dashboard", "/d/homelab-overview"), hide_ds=True)
