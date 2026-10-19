"""Shared pieces for the dashboard generators (gen_overview.py, gen_mobile.py).

Colour rule: healthy is a calm teal; red, peach and yellow appear only for real problems; blue,
mauve and lavender are the neutral accents. Palette: Catppuccin Mocha (https://catppuccin.com/palette).
"""
import json
import re

C = {"rosewater": "#f5e0dc", "flamingo": "#f2cdcd", "pink": "#f5c2e7", "mauve": "#cba6f7", "red": "#f38ba8",
     "maroon": "#eba0ac", "peach": "#fab387", "yellow": "#f9e2af", "green": "#a6e3a1", "teal": "#94e2d5",
     "sky": "#89dceb", "sapphire": "#74c7ec", "blue": "#89b4fa", "lavender": "#b4befe", "text": "#cdd6f4",
     "overlay0": "#6c7086", "surface1": "#45475a", "surface0": "#313244", "base": "#1e1e2e"}
HEALTHY, BAD, WARN, PENDING, INFO, MUTED = C["teal"], C["red"], C["peach"], C["yellow"], C["blue"], C["overlay0"]

DS = {"type": "prometheus", "uid": "${datasource}"}

# Graph line colours, matched by regex on the series name (Kuma keeps trailing spaces in monitor
# names, hence the \s*). Anything not listed falls back to Grafana's classic palette.
HOST_COLORS = {"proxmox": C["peach"], "pihole": C["red"], "dockers": C["blue"],
               "tailscale": C["teal"], "plex": C["yellow"], "qbittorrent": C["mauve"]}
MONITOR_COLORS = {"420NAS": C["teal"], "Grafana": C["peach"], "Home Assistant": C["sky"], "NPM": C["lavender"],
                  "PiHole Primary": C["red"], "Plex": C["yellow"], "Proxmox": C["maroon"], "qBittorent": C["blue"],
                  "Uptime Kuma": C["green"]}


def color_overrides(mapping):
    return [{"matcher": {"id": "byRegexp", "options": "^" + name + r"\s*$"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": hexc}}]}
            for name, hexc in mapping.items()]


def steps(*pairs):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}


# healthy-until-it-isn't thresholds
PCT_USED = steps((INFO, None), (WARN, 75), (BAD, 90))                  # CPU, memory, disk
UPTIME = steps((BAD, None), (PENDING, 95), (HEALTHY, 99))              # uptime %: teal from 99, yellow from 95, red below
STATUS = steps((BAD, None), (HEALTHY, 1), (PENDING, 2), (INFO, 3))     # monitor_status: 0 down 1 up 2 pending 3 maint


def pos(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


class Dash:
    def __init__(self):
        self._id = 0
        self.panels = []

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
             display="basic", overrides=None, transparent=False):
        defaults = {"unit": unit, "decimals": decimals, "min": vmin}
        if vmax is not None:
            defaults["max"] = vmax
        defaults["color"] = {"mode": "thresholds"}
        defaults["thresholds"] = thresholds
        panel = self.add({
            "id": self.nid(), "type": "bargauge", "title": title, "datasource": DS, "gridPos": g,
            "targets": [self.target(expr, legend, instant=True)],
            "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
            "options": {"orientation": "horizontal", "displayMode": display, "showUnfilled": True,
                        "valueMode": "color", "namePlacement": "top", "minVizHeight": 16, "minVizWidth": 8,
                        "text": {"titleSize": 13, "valueSize": 16},
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})
        if transparent:
            panel["transparent"] = True
        return panel

    def timeseries(self, title, expr, legend, g, unit, vmin=None, vmax=None, overrides=None, table_legend=True):
        d = {"unit": unit, "color": {"mode": "palette-classic"},
             "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 14, "gradientMode": "opacity",
                        "showPoints": "never", "lineInterpolation": "smooth", "spanNulls": True}}
        if vmin is not None:
            d["min"] = vmin
        if vmax is not None:
            d["max"] = vmax
        legend_opts = ({"displayMode": "table", "placement": "bottom", "showLegend": True, "calcs": ["mean", "max"]}
                       if table_legend else {"displayMode": "list", "placement": "bottom", "showLegend": False, "calcs": []})
        return self.add({
            "id": self.nid(), "type": "timeseries", "title": title, "datasource": DS, "gridPos": g,
            "targets": [self.target(expr, legend)],
            "fieldConfig": {"defaults": d, "overrides": overrides or []},
            "options": {"legend": legend_opts, "tooltip": {"mode": "multi", "sort": "desc"}}})

    def hero(self, title, expr, g):
        """Full-width status banner: one phrase on a soft gradient fill. The only filled block on the board.
        expr must be down * 10 + pending, so 0 = all up, 1-9 = something retrying, 10+ = something down."""
        def rng(lo, hi, text, color, i):
            return {"type": "range", "options": {"from": lo, "to": hi, "result": {"text": text, "color": color, "index": i}}}
        return self.add({
            "id": self.nid(), "type": "stat", "title": title, "datasource": DS, "gridPos": g, "transparent": True,
            "targets": [self.target(expr, "", instant=True)],
            "fieldConfig": {"defaults": {"unit": "none", "color": {"mode": "thresholds"},
                                         "thresholds": steps((HEALTHY, None)),
                                         "mappings": [rng(0, 0.5, "ALL SYSTEMS UP", HEALTHY, 0),
                                                      rng(0.5, 9.5, "DEGRADED", PENDING, 1),
                                                      rng(9.5, 1000000, "OUTAGE", BAD, 2)]}, "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "justifyMode": "center",
                        "orientation": "auto", "textMode": "value", "wideLayout": True,
                        "text": {"valueSize": 30},
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
            "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": steps((HEALTHY, None))},
                            "overrides": overrides},
            "options": {"colorMode": "value", "graphMode": "none", "justifyMode": "center",
                        "orientation": "horizontal", "textMode": "value_and_name", "wideLayout": True,
                        "text": {"valueSize": size, "titleSize": 12},
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})

    def status_history(self, title, expr, legend, g, points=40):
        """One row per monitor, one cell per time bucket, coloured by status. Replaces a plain list of UP/DOWN."""
        return self.add({
            "id": self.nid(), "type": "status-history", "title": title, "datasource": DS, "gridPos": g,
            "transparent": True, "maxDataPoints": points, "targets": [self.target(expr, legend)],
            "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "thresholds": STATUS,
                                         "mappings": self.status_mappings(),
                                         "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
            "options": {"showValue": "never", "rowHeight": 0.85, "colWidth": 0.92,
                        "legend": {"showLegend": False, "displayMode": "list", "placement": "bottom"},
                        "tooltip": {"mode": "single", "sort": "none"}}})

    def host_table(self, title, cols, g):
        """One row per host, one gradient gauge cell per metric. cols = [(name, expr_by_host, base_colour)]."""
        targets = []
        for i, (name, expr, _) in enumerate(cols):
            targets.append({"datasource": DS, "expr": expr, "format": "table", "instant": True, "range": False,
                            "refId": chr(65 + i)})
        keep = ["host"] + [f"Value #{chr(65 + i)}" for i in range(len(cols))]
        rename = {f"Value #{chr(65 + i)}": c[0] for i, c in enumerate(cols)}
        rename["host"] = "host"
        order = {n: i for i, n in enumerate(["host"] + [c[0] for c in cols])}
        overrides = []
        for name, _, base in cols:
            overrides.append({"matcher": {"id": "byName", "options": name}, "properties": [
                {"id": "unit", "value": "percent"}, {"id": "min", "value": 0}, {"id": "max", "value": 100},
                {"id": "decimals", "value": 0}, {"id": "color", "value": {"mode": "thresholds"}},
                {"id": "thresholds", "value": steps((base, None), (WARN, 75), (BAD, 90))},
                {"id": "custom.cellOptions", "value": {"type": "gauge", "mode": "gradient", "valueDisplayMode": "text"}}]})
        return self.add({
            "id": self.nid(), "type": "table", "title": title, "datasource": DS, "gridPos": g, "transparent": True,
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
            "0": {"text": "DOWN", "color": BAD, "index": 0},
            "1": {"text": "UP", "color": HEALTHY, "index": 1},
            "2": {"text": "PENDING", "color": PENDING, "index": 2},
            "3": {"text": "MAINT", "color": INFO, "index": 3}}}]

    def finish(self, path, uid, title, description, tags, link, refresh="10s", hide_ds=False):
        dashboard = {
            "uid": uid, "title": title, "tags": tags, "timezone": "browser", "schemaVersion": 39, "version": 1,
            "editable": True, "graphTooltip": 1, "refresh": refresh, "time": {"from": "now-6h", "to": "now"},
            "description": description,
            "templating": {"list": [{"name": "datasource", "label": "Data source", "type": "datasource",
                                     "query": "prometheus", "current": {}, "hide": 2 if hide_ds else 0,
                                     "includeAll": False, "multi": False, "options": [], "refresh": 1}]},
            "annotations": {"list": []},
            "links": [{"title": link[0], "type": "link", "url": link[1], "icon": "dashboard", "targetBlank": False,
                       "asDropdown": False, "includeVars": False, "keepTime": False, "tags": [], "tooltip": ""}],
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
