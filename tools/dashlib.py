"""Shared pieces for the dashboard generators (gen_overview.py, gen_mobile.py, gen_home.py).

Colour rule: there is no green or teal on any dashboard. "Up" is sapphire (UP), maintenance is lavender, red,
peach and yellow appear only for real problems, and blue, mauve and lavender are the neutral accents.
Palette: Catppuccin Mocha (https://catppuccin.com/palette).
"""
import json
import re

C = {"rosewater": "#f5e0dc", "flamingo": "#f2cdcd", "pink": "#f5c2e7", "mauve": "#cba6f7", "red": "#f38ba8",
     "maroon": "#eba0ac", "peach": "#fab387", "yellow": "#f9e2af", "green": "#a6e3a1", "teal": "#94e2d5",
     "sky": "#89dceb", "sapphire": "#74c7ec", "blue": "#89b4fa", "lavender": "#b4befe", "text": "#cdd6f4",
     "overlay0": "#6c7086", "surface1": "#45475a", "surface0": "#313244", "base": "#1e1e2e"}
UP = C["sapphire"]
HEALTHY, BAD, WARN, PENDING, INFO, MUTED = UP, C["red"], C["peach"], C["yellow"], C["blue"], C["overlay0"]

DS = {"type": "prometheus", "uid": "${datasource}"}

# Every dashboard refreshes this often (the owner wants all of them at 5 s, including new ones).
REFRESH = "5s"

# Graph line colours, matched by regex on the series name (Kuma keeps trailing spaces in monitor
# names, hence the \s*). Anything not listed falls back to Grafana's classic palette. Add new hosts and
# monitors here. "Up" is sapphire; line colours avoid teal and green.
HOST_COLORS_M = {"proxmox": C["peach"], "pihole": C["flamingo"], "dockers": C["blue"],
                 "tailscale": C["pink"], "plex": C["yellow"], "qbittorrent": C["mauve"]}
MONITOR_COLORS_M = {"420NAS": C["pink"], "Grafana": C["peach"], "Home Assistant": C["sky"], "NPM": C["lavender"],
                    "PiHole Primary": C["flamingo"], "Plex": C["yellow"], "Proxmox": C["mauve"],
                    "qBittorent": C["blue"], "Uptime Kuma": C["rosewater"]}


# How each host's `host` label (prometheus/targets/nodes.yml) is shown on the dashboards. The labels stay
# lowercase in Prometheus so history isn't split; only the display changes. A host that isn't listed here
# is shown as its raw label: add it (and a colour in HOST_COLORS_M).
HOST_NAMES = {"proxmox": "Proxmox", "pihole": "Pi-hole", "dockers": "Docker", "tailscale": "Tailscale",
              "plex": "Plex", "qbittorrent": "qBittorrent"}


def color_overrides(mapping, names=None):
    """Fixed line colour per series, matched by name. names optionally maps a series name to a display name."""
    out = []
    for name, hexc in mapping.items():
        props = [{"id": "color", "value": {"mode": "fixed", "fixedColor": hexc}}]
        if names and name in names:
            props.append({"id": "displayName", "value": names[name]})
        out.append({"matcher": {"id": "byRegexp", "options": "^" + name + r"\s*$"}, "properties": props})
    return out


# Cool-family line colours for the calm trend charts (one hue family, not a rainbow).
HOST_COLORS_COOL = {"proxmox": C["blue"], "pihole": C["lavender"], "dockers": C["sapphire"],
                    "tailscale": C["mauve"], "plex": C["sky"], "qbittorrent": "#9399b2"}


def host_overrides():
    """Colour and display name for every host series (legends, tooltips)."""
    return color_overrides(HOST_COLORS_M, HOST_NAMES)


def steps(*pairs):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}


# Uptime %: red below 95, yellow from 95, sapphire from 99
UPTIME_M = steps((BAD, None), (PENDING, 95), (UP, 99))


# Every dashboard shows a button for each of the others, so you can flip between them from anywhere.
# Add a new dashboard here and regenerate all of them.
NAV = [("homelab-overview", "Overview", "/d/homelab-overview"),
       ("homelab-mobile", "Mobile", "/d/homelab-mobile"),
       ("homelab", "Testing mobile", "/d/homelab"),
       ("homelab-desktop", "Testing desktop", "/d/homelab-desktop")]


def nav_links(current_uid):
    return [(title, url) for uid, title, url in NAV if uid != current_uid]


# Banner value for hero(): down * 10 + pending, plus 1000 when Prometheus isn't scraping Uptime Kuma or no
# monitor series exist at all. Without the 1000s, "Kuma is gone" counted as zero problems and read all clear.
HERO_EXPR = ('(count(monitor_status == 0) or vector(0)) * 10'
             ' + (count(monitor_status == 2 or monitor_status == 3) or vector(0))'
             ' + (1 - clamp_max(count(monitor_status) or vector(0), 1)) * 1000'
             ' + (1 - (max(up{job="uptime-kuma"}) or vector(0))) * 1000')


def pos(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


class Dash:
    def __init__(self, healthy=None, maint=None):
        self._id = 0
        self.panels = []
        self.healthy = healthy or HEALTHY   # colour for "up" in status mappings and the status grid
        self.maint = maint or INFO          # colour for "maintenance"

    def nid(self):
        self._id += 1
        return self._id

    @staticmethod
    def target(expr, legend="", instant=False):
        t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A"}
        if instant:
            t["instant"] = True
            t["range"] = False
        return t

    def add(self, panel):
        self.panels.append(panel)
        return panel

    def stat(self, title, expr, g, unit="none", decimals=None, thresholds=None, desc="", instant=False,
             legend="", text="value", size=44, area=False, transparent=True):
        d = {"unit": unit, "color": {"mode": "thresholds"}, "thresholds": thresholds or steps((HEALTHY, None))}
        if decimals is not None:
            d["decimals"] = decimals
        return self.add({
            "id": self.nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": g, "transparent": transparent, "targets": [self.target(expr, legend, instant)],
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"colorMode": "value", "graphMode": "area" if area else "none", "justifyMode": "center",
                        "orientation": "auto", "textMode": text, "wideLayout": True,
                        "text": {"valueSize": size, "titleSize": 14},
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})

    def bars(self, title, expr, g, thresholds, unit="percent", vmin=0, vmax=100, decimals=0, legend="{{host}}",
             display="basic", overrides=None, transparent=False, title_size=13, value_size=16, desc=""):
        defaults = {"unit": unit, "decimals": decimals, "min": vmin}
        if vmax is not None:
            defaults["max"] = vmax
        defaults["color"] = {"mode": "thresholds"}
        defaults["thresholds"] = thresholds
        panel = self.add({
            "id": self.nid(), "type": "bargauge", "title": title, "description": desc, "datasource": DS, "gridPos": g,
            "targets": [self.target(expr, legend, instant=True)],
            "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
            "options": {"orientation": "horizontal", "displayMode": display, "showUnfilled": True,
                        "valueMode": "color", "namePlacement": "top", "minVizHeight": 16, "minVizWidth": 8,
                        "text": {"titleSize": title_size, "valueSize": value_size},
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})
        if transparent:
            panel["transparent"] = True
        return panel

    def timeseries(self, title, expr, legend, g, unit, vmin=None, vmax=None, overrides=None, table_legend=True, desc=""):
        d = {"unit": unit, "color": {"mode": "palette-classic"},
             "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 14, "gradientMode": "opacity",
                        "showPoints": "never", "lineInterpolation": "smooth", "spanNulls": True,
                        "axisBorderShow": False, "axisSoftMin": 0}}
        if vmin is not None:
            d["min"] = vmin
        if vmax is not None:
            d["max"] = vmax
        legend_opts = ({"displayMode": "table", "placement": "bottom", "showLegend": True, "calcs": ["mean", "max"]}
                       if table_legend else {"displayMode": "list", "placement": "bottom", "showLegend": False, "calcs": []})
        return self.add({
            "id": self.nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS, "gridPos": g,
            "targets": [self.target(expr, legend)],
            "fieldConfig": {"defaults": d, "overrides": overrides or []},
            "options": {"legend": legend_opts, "tooltip": {"mode": "multi", "sort": "desc"}}})

    def calm_timeseries(self, title, targets, g, unit, vmin=None, vmax=None, overrides=None, desc="", decimals=0):
        """Quiet trend chart for the detail rows: thin smooth line, soft fill, no legend, no points, no axis
        border or grid. Hover shows every series. targets = [(expr, legend)]."""
        d = {"unit": unit, "decimals": decimals, "color": {"mode": "palette-classic"},
             "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 12, "gradientMode": "opacity",
                        "showPoints": "never", "lineInterpolation": "smooth", "spanNulls": True,
                        "axisBorderShow": False, "axisGridShow": False, "axisLabel": "", "axisSoftMin": 0}}
        if vmin is not None:
            d["min"] = vmin
        if vmax is not None:
            d["max"] = vmax
        tg = []
        for i, (expr, legend) in enumerate(targets):
            t = self.target(expr, legend)
            t["refId"] = chr(65 + i)
            tg.append(t)
        return {"id": self.nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
                "gridPos": g, "transparent": True, "targets": tg,
                "fieldConfig": {"defaults": d, "overrides": overrides or []},
                "options": {"legend": {"showLegend": False, "displayMode": "list", "placement": "bottom", "calcs": []},
                            "tooltip": {"mode": "multi", "sort": "desc"}}}

    def hero(self, title, expr, g, up=None):
        """Full-width status banner: one phrase on a soft gradient fill. The only filled block on the board.
        expr is HERO_EXPR: 0 = all up, 1-9 = something retrying, 10-998 = something down, 999+ = Uptime Kuma
        isn't reporting (so nothing can be said about the services)."""
        up = up or self.healthy

        def rng(lo, hi, text, color, i):
            return {"type": "range", "options": {"from": lo, "to": hi, "result": {"text": text, "color": color, "index": i}}}
        return self.add({
            "id": self.nid(), "type": "stat", "title": title, "datasource": DS, "gridPos": g, "transparent": True,
            "targets": [self.target(expr, "", instant=True)],
            "fieldConfig": {"defaults": {"unit": "none", "color": {"mode": "thresholds"},
                                         "thresholds": steps((up, None)),
                                         "mappings": [rng(0, 0.5, "All systems operational", up, 0),
                                                      rng(0.5, 9.5, "Degraded performance", PENDING, 1),
                                                      rng(9.5, 999, "Service outage", BAD, 2),
                                                      rng(999, 1000000000, "Monitoring unavailable", BAD, 3)]}, "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center",
                        "orientation": "auto", "textMode": "value", "wideLayout": True,
                        "text": {"valueSize": 26},
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})

    def multi_stat(self, title, series, g, size=38):
        """Several numbers side by side inside ONE panel. Grafana stacks panels in a single column on a phone,
        so this is how a row of tiles survives on mobile. series = [(name, expr, thresholds, unit, decimals)]."""
        targets, overrides = [], []
        for i, (name, expr, th, unit, dec) in enumerate(series):
            t = self.target(expr, name, instant=True)
            t["refId"] = chr(65 + i)
            targets.append(t)
            props = [{"id": "thresholds", "value": th}, {"id": "color", "value": {"mode": "thresholds"}},
                     {"id": "unit", "value": unit}]
            if dec is not None:
                props.append({"id": "decimals", "value": dec})
            overrides.append({"matcher": {"id": "byName", "options": name}, "properties": props})
        return self.add({
            "id": self.nid(), "type": "stat", "title": title, "datasource": DS, "gridPos": g, "transparent": True,
            "targets": targets,
            "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": steps((INFO, None))},
                            "overrides": overrides},
            "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "center",
                        "orientation": "horizontal", "textMode": "value_and_name", "wideLayout": True,
                        "text": {"valueSize": size, "titleSize": 12},
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})

    def status_history(self, title, expr, legend, g, points=40, desc=""):
        """One row per monitor, one cell per time bucket, coloured by status. Replaces a plain list of UP/DOWN."""
        return self.add({
            "id": self.nid(), "type": "status-history", "title": title, "description": desc, "datasource": DS, "gridPos": g,
            "transparent": True, "maxDataPoints": points, "targets": [self.target(expr, legend)],
            "fieldConfig": {"defaults": {"color": {"mode": "thresholds"},
                                         "thresholds": steps((BAD, None), (self.healthy, 1), (PENDING, 2), (self.maint, 3)),
                                         "mappings": self.status_mappings(),
                                         "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
            "options": {"showValue": "never", "rowHeight": 0.85, "colWidth": 0.92,
                        "legend": {"showLegend": False, "displayMode": "list", "placement": "bottom"},
                        "tooltip": {"mode": "single", "sort": "none"}}})

    def host_table(self, title, cols, g, desc=""):
        """One row per host, one gradient gauge cell per metric. cols = [(name, expr_by_host, base_colour)].
        Host names are shown through HOST_NAMES (Proxmox, Pi-hole, ...); the underlying label is unchanged."""
        targets = []
        for i, (name, expr, _) in enumerate(cols):
            targets.append({"datasource": DS, "expr": expr, "format": "table", "instant": True, "range": False,
                            "refId": chr(65 + i)})
        keep = ["host"] + [f"Value #{chr(65 + i)}" for i in range(len(cols))]
        rename = {f"Value #{chr(65 + i)}": c[0] for i, c in enumerate(cols)}
        rename["host"] = "Host"
        # `indexByName` is keyed by the original names (host, Value #A, ...), so key it that way
        order = {"host": 0, **{f"Value #{chr(65 + i)}": i + 1 for i in range(len(cols))}}
        value_map = {raw: {"text": shown, "index": i} for i, (raw, shown) in enumerate(HOST_NAMES.items())}
        overrides = [{"matcher": {"id": "byName", "options": "Host"}, "properties": [
            {"id": "mappings", "value": [{"type": "value", "options": value_map}]},
            {"id": "custom.width", "value": 130}]}]
        for name, _, base in cols:
            overrides.append({"matcher": {"id": "byName", "options": name}, "properties": [
                {"id": "unit", "value": "percent"}, {"id": "min", "value": 0}, {"id": "max", "value": 100},
                {"id": "decimals", "value": 0}, {"id": "color", "value": {"mode": "thresholds"}},
                {"id": "thresholds", "value": steps((base, None), (WARN, 75), (BAD, 90))},
                {"id": "custom.cellOptions", "value": {"type": "gauge", "mode": "gradient", "valueDisplayMode": "text"}}]})
        return self.add({
            "id": self.nid(), "type": "table", "title": title, "description": desc, "datasource": DS, "gridPos": g,
            "transparent": True,
            "targets": targets,
            "transformations": [
                {"id": "joinByField", "options": {"byField": "host", "mode": "outer"}},
                {"id": "filterFieldsByName", "options": {"include": {"names": keep}}},
                {"id": "organize", "options": {"renameByName": rename, "indexByName": order}}],
            "fieldConfig": {"defaults": {"custom": {"align": "left", "cellOptions": {"type": "auto"}}},
                            "overrides": overrides},
            "options": {"showHeader": True, "cellHeight": "lg", "footer": {"show": False}}})

    def status_mappings(self):
        return [{"type": "value", "options": {
            "0": {"text": "Down", "color": BAD, "index": 0},
            "1": {"text": "Up", "color": self.healthy, "index": 1},
            "2": {"text": "Pending", "color": PENDING, "index": 2},
            "3": {"text": "Maintenance", "color": self.maint, "index": 3}}}]

    def finish(self, path, uid, title, description, tags, link, refresh=REFRESH, hide_ds=False):
        dashboard = {
            "uid": uid, "title": title, "tags": tags, "timezone": "browser", "schemaVersion": 39, "version": 1,
            "editable": True, "graphTooltip": 1, "refresh": refresh, "time": {"from": "now-6h", "to": "now"},
            "description": description,
            "templating": {"list": [{"name": "datasource", "label": "Data source", "type": "datasource",
                                     "query": "prometheus", "current": {}, "hide": 2 if hide_ds else 0,
                                     "includeAll": False, "multi": False, "options": [], "refresh": 1}]},
            "annotations": {"list": []},
            "links": [{"title": t, "type": "link", "url": u, "icon": "dashboard", "targetBlank": False,
                       "asDropdown": False, "includeVars": False, "keepTime": False, "tags": [], "tooltip": ""}
                      for t, u in (link if isinstance(link, list) else [link])],
            "panels": self.panels}
        with open(path, "w") as f:
            json.dump(dashboard, f, indent=2)
            f.write("\n")
        ids = [p["id"] for p in self.panels]
        assert len(ids) == len(set(ids)), "duplicate panel ids"
        boxes = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"], p["title"]) for p in self.panels]
        for x, y, w, h, t in boxes:
            assert 0 <= x and x + w <= 24, f"{t} runs off the 24-column grid"
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                assert not (a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]), \
                    f"{a[4]} overlaps {b[4]}"
        print(f"ok: {title}: {len(self.panels)} panels, no overlaps, all within the grid")
