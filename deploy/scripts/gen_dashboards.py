#!/usr/bin/env python3
"""Generate Grafana dashboard JSON for the Luminaire Control System.

Usage:
    python deploy/scripts/gen_dashboards.py

Requires prometheus datasource named "Prometheus" (see deploy/grafana/provisioning/datasources/prometheus.yaml).
"""

import json, os

DS = "Prometheus"

def p(**kw):
    pid = kw.get("id")
    exprs = kw.get("exprs", [])
    legend = kw.get("legend", "__auto")
    opts = kw.get("options", {})
    fc = kw.get("fieldConfig", {"defaults": {}, "overrides": []})
    return {
        "id": pid,
        "title": kw["title"],
        "type": kw["type"],
        "gridPos": {"h": kw["h"], "w": kw["w"], "x": kw["x"], "y": kw["y"]},
        "datasource": {"type": "prometheus", "uid": DS},
        "targets": [
            {"expr": e, "legendFormat": legend, "refId": chr(65 + i)}
            for i, e in enumerate(exprs)
        ],
        "options": opts,
        "fieldConfig": fc,
    }

OUT = "deploy/grafana/provisioning/dashboards"

def write(name, data):
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {path}  ({len(data['panels'])} panels)")

def dashboard(title, uid, panels):
    return {
        "title": title,
        "uid": uid,
        "schemaVersion": 39,
        "version": 1,
        "editable": True,
        "tags": ["luminaire"],
        "timezone": "browser",
        "refresh": "10s",
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "panels": panels,
    }

ENV = os.getenv("ENV", "production")

health = dashboard(
    "LCS System Health",
    "lcs-system-health",
    [
        # ---- Row: Service Health ----
        p(title="Service Uptime", type="stat", h=4, w=3, x=0, y=0,
          exprs=['time() - process_start_time_seconds{job=~"scheduler|state|timer|metrics|luminaire"}'],
          legend="{{job}}",
          options={"graphMode": "none", "colorMode": "background"},
          fieldConfig={"defaults": {"unit": "s", "thresholds": {"mode": "absolute", "steps": [
              {"color": "red", "value": None},
              {"color": "orange", "value": 60},
              {"color": "green", "value": 300},
          ]}}, "overrides": []}),
        p(title="Service Up Count", type="stat", h=4, w=3, x=3, y=0,
          exprs=['count(up{job=~"scheduler|state|timer|metrics|luminaire|redis|gateway|web"} == 1)'],
          options={"graphMode": "none", "colorMode": "background"},
          fieldConfig={"defaults": {"max": 8, "thresholds": {"mode": "absolute", "steps": [
              {"color": "red", "value": None},
              {"color": "orange", "value": 6},
              {"color": "green", "value": 8},
          ]}}, "overrides": []}),
        p(title="Container Restarts", type="stat", h=4, w=3, x=6, y=0,
          exprs=['sum(increase(container_last_seen[1h])) by (name)'],
          legend="{{name}}",
          options={"graphMode": "none"},
          fieldConfig={"defaults": {"thresholds": {"mode": "absolute", "steps": [
              {"color": "green", "value": None},
              {"color": "red", "value": 1},
          ]}}, "overrides": []}),
        p(title="All Services Up", type="stat", h=4, w=3, x=9, y=0,
          exprs=['count(up{job=~"scheduler|state|timer|metrics|luminaire|redis|gateway|web"} == 1) / count(up{job=~"scheduler|state|timer|metrics|luminaire|redis|gateway|web"}) * 100'],
          options={"graphMode": "none", "colorMode": "background"},
          fieldConfig={"defaults": {"unit": "percent", "max": 100, "thresholds": {"mode": "absolute", "steps": [
              {"color": "red", "value": None},
              {"color": "orange", "value": 80},
              {"color": "green", "value": 100},
          ]}}, "overrides": []}),

        # ---- Row: CPU & Memory ----
        p(title="CPU Usage Rate (1m avg)", type="timeseries", h=6, w=6, x=0, y=4,
          exprs=['rate(process_cpu_seconds_total{job=~"scheduler|state|timer|metrics|luminaire"}[1m])'],
          legend="{{job}}"),
        p(title="Memory RSS", type="timeseries", h=6, w=6, x=6, y=4,
          exprs=['process_resident_memory_bytes{job=~"scheduler|state|timer|metrics|luminaire"}'],
          legend="{{job}}"),
        p(title="CPU Per Core", type="timeseries", h=6, w=6, x=12, y=4,
          exprs=['100 - (avg by (instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'],
          legend="CPU %"),
        p(title="Memory (node)", type="timeseries", h=6, w=6, x=18, y=4,
          exprs=['node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes', 'node_memory_MemAvailable_bytes'],
          legend="{{__name__}}"),

        # ---- Row: Disk & Network ----
        p(title="Disk Usage per Mount", type="timeseries", h=5, w=4, x=0, y=10,
          exprs=['100 - (node_filesystem_free_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"} * 100)'],
          legend="{{mountpoint}}"),
        p(title="Disk I/O", type="timeseries", h=5, w=4, x=4, y=10,
          exprs=['rate(node_disk_read_bytes_total[1m])', 'rate(node_disk_written_bytes_total[1m])'],
          legend="{{device}} {{__name__}}"),
        p(title="Network I/O", type="timeseries", h=5, w=4, x=8, y=10,
          exprs=['rate(node_network_receive_bytes_total[1m])', 'rate(node_network_transmit_bytes_total[1m])'],
          legend="{{device}} {{__name__}}"),
        p(title="Swap Usage", type="timeseries", h=5, w=4, x=12, y=10,
          exprs=['node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes'],
          legend="swap used"),
        p(title="Process Count", type="timeseries", h=5, w=4, x=16, y=10,
          exprs=['node_procs_running', 'node_procs_blocked'],
          legend="{{__name__}}"),
        p(title="Load Average", type="timeseries", h=5, w=4, x=20, y=10,
          exprs=['node_load1', 'node_load5', 'node_load15'],
          legend="{{__name__}}"),

        # ---- Row: Redis ----
        p(title="Redis Memory Usage", type="gauge", h=5, w=3, x=0, y=15,
          exprs=['redis_memory_used_bytes / redis_memory_max_bytes * 100'],
          fieldConfig={"defaults": {"min": 0, "max": 100, "unit": "percent", "thresholds": {"mode": "absolute", "steps": [
              {"color": "green", "value": None},
              {"color": "orange", "value": 70},
              {"color": "red", "value": 90},
          ]}}, "overrides": []}),
        p(title="Redis Connected Clients", type="stat", h=5, w=3, x=3, y=15,
          exprs=['redis_connected_clients'],
          options={"graphMode": "none"},
          fieldConfig={"defaults": {"thresholds": {"mode": "absolute", "steps": [
              {"color": "green", "value": None},
              {"color": "orange", "value": 50},
          ]}}, "overrides": []}),
        p(title="Redis Hit Ratio", type="timeseries", h=5, w=4, x=6, y=15,
          exprs=['rate(redis_keyspace_hits_total[1m]) / (rate(redis_keyspace_hits_total[1m]) + rate(redis_keyspace_misses_total[1m])) * 100'],
          legend="hit ratio %"),
        p(title="Redis Commands/sec", type="timeseries", h=5, w=4, x=10, y=15,
          exprs=['rate(redis_commands_processed_total[1m])'],
          legend="cmds/sec"),
        p(title="Redis Keyspace", type="timeseries", h=5, w=4, x=14, y=15,
          exprs=['redis_db_keys{db=~"db0"}'],
          legend="{{db}} keys"),
        p(title="Redis Expired Keys", type="timeseries", h=5, w=4, x=18, y=15,
          exprs=['rate(redis_expired_keys_total[1m])'],
          legend="expired/sec"),

        # ---- Row: Node ----
        p(title="Open File Descriptors", type="timeseries", h=5, w=4, x=0, y=20,
          exprs=['process_open_fds{job=~"scheduler|state|timer|metrics|luminaire"}'],
          legend="{{job}}"),
        p(title="FD Limit %", type="timeseries", h=5, w=4, x=4, y=20,
          exprs=['process_open_fds{job=~"scheduler|state|timer|metrics|luminaire"} / process_max_fds{job=~"scheduler|state|timer|metrics|luminaire"} * 100'],
          legend="{{job}}"),
        p(title="Container CPU Throttle", type="timeseries", h=5, w=4, x=8, y=20,
          exprs=['rate(container_cpu_cfs_throttled_seconds_total[1m])'],
          legend="{{name}}"),
        p(title="Container Memory Limit %", type="timeseries", h=5, w=4, x=12, y=20,
          exprs=['container_memory_working_set_bytes / container_spec_memory_limit_bytes * 100'],
          legend="{{name}}"),
        p(title="Container OOM", type="stat", h=5, w=3, x=16, y=20,
          exprs=['increase(container_oom_events_total[24h])'],
          options={"graphMode": "none"},
          fieldConfig={"defaults": {"thresholds": {"mode": "absolute", "steps": [
              {"color": "green", "value": None},
              {"color": "red", "value": 1},
          ]}}, "overrides": []}),
        p(title="Go Routines (gateway)", type="timeseries", h=5, w=4, x=19, y=20,
          exprs=['go_goroutines{job="gateway"}'],
          legend="goroutines"),
    ],
)

scene_throughput = dashboard(
    "LCS Scene Throughput",
    "lcs-scene-throughput",
    [
        # ---- Current State Row ----
        p(title="Current System Power", type="stat", h=3, w=3, x=0, y=0,
          exprs=['scheduler_system_on'], legend="{{job}}",
          options={"graphMode": "none", "colorMode": "background"},
          fieldConfig={"defaults": {"thresholds": {"mode": "absolute", "steps": [
              {"color": "red", "value": None},
              {"color": "green", "value": 1},
          ]}}, "overrides": []}),
        p(title="Current Mode", type="stat", h=3, w=3, x=3, y=0,
          exprs=['scheduler_mode'], legend="{{instance}}",
          options={"graphMode": "none", "colorMode": "background"},
          fieldConfig={"defaults": {"thresholds": {"mode": "absolute", "steps": [
              {"color": "blue", "value": None},
          ]}}, "overrides": []}),
        p(title="Active Scene", type="stat", h=3, w=3, x=6, y=0,
          exprs=['scheduler_running_scene'], legend="{{instance}}",
          options={"graphMode": "none"}),
        p(title="Interpolation Mode", type="stat", h=3, w=3, x=9, y=0,
          exprs=['scheduler_interpolation_mode'], legend="{{instance}}",
          options={"graphMode": "none"}),
        p(title="Tick Interval", type="stat", h=3, w=3, x=12, y=0,
          exprs=['scheduler_tick_interval'], legend="{{instance}}",
          options={"graphMode": "none"},
          fieldConfig={"defaults": {"unit": "s"}}),
        p(title="Scene Count", type="stat", h=3, w=3, x=15, y=0,
          exprs=['count(scheduler_available_scenes)'], legend="{{instance}}",
          options={"graphMode": "none"}),
        p(title="Timer Enabled", type="stat", h=3, w=3, x=18, y=0,
          exprs=['timer_enabled'], legend="{{instance}}",
          options={"graphMode": "none", "colorMode": "background"},
          fieldConfig={"defaults": {"thresholds": {"mode": "absolute", "steps": [
              {"color": "dark-gray", "value": None},
              {"color": "green", "value": 1},
          ]}}, "overrides": []}),
        p(title="Luminaires Connected", type="stat", h=3, w=3, x=21, y=0,
          exprs=['luminaire_connected_count'], legend="{{instance}}",
          options={"graphMode": "none"}),

        # ---- Output Row ----
        p(title="CCT Output", type="timeseries", h=6, w=6, x=0, y=3,
          exprs=['scheduler_cct'], legend="{{job}}"),
        p(title="Lux Output", type="timeseries", h=6, w=6, x=6, y=3,
          exprs=['scheduler_lux'], legend="{{job}}"),
        p(title="CW Channel", type="timeseries", h=6, w=6, x=12, y=3,
          exprs=['scheduler_cw'], legend="{{job}}"),
        p(title="WW Channel", type="timeseries", h=6, w=6, x=18, y=3,
          exprs=['scheduler_ww'], legend="{{job}}"),

        # ---- Scene Progress & Transitions ----
        p(title="Scene Progress", type="timeseries", h=5, w=6, x=0, y=9,
          exprs=['scheduler_scene_progress'], legend="{{scene}}"),
        p(title="Scene Load Events", type="timeseries", h=5, w=6, x=6, y=9,
          exprs=['rate(scheduler_scene_load_total[1m])'], legend="{{scene}}"),
        p(title="Scene Activations", type="timeseries", h=5, w=6, x=12, y=9,
          exprs=['rate(scheduler_scene_activate_total[1m])'], legend="{{scene}}"),
        p(title="Scene Deactivations", type="timeseries", h=5, w=6, x=18, y=9,
          exprs=['rate(scheduler_scene_deactivate_total[1m])'], legend="{{scene}}"),

        # ---- Timer Row ----
        p(title="Timer Start", type="stat", h=4, w=3, x=0, y=14,
          exprs=['timer_start'], legend="{{instance}}",
          options={"graphMode": "none"}),
        p(title="Timer End", type="stat", h=4, w=3, x=3, y=14,
          exprs=['timer_end'], legend="{{instance}}",
          options={"graphMode": "none"}),
        p(title="Timer Toggle Events", type="timeseries", h=4, w=4, x=6, y=14,
          exprs=['rate(timer_toggle_total[1m])'], legend="toggles/min"),
        p(title="Timer Configure Events", type="timeseries", h=4, w=4, x=10, y=14,
          exprs=['rate(timer_configure_total[1m])'], legend="configures/min"),
        p(title="Timer Clear Events", type="timeseries", h=4, w=4, x=14, y=14,
          exprs=['rate(timer_clear_total[1m])'], legend="clears/min"),
        p(title="Timer State Publish", type="timeseries", h=4, w=4, x=18, y=14,
          exprs=['rate(timer_state_publish_total[1m])'], legend="publishes/min"),

        # ---- Event & Error Row ----
        p(title="Redis Scheduler Events/min", type="timeseries", h=4, w=4, x=0, y=18,
          exprs=['rate(redis_scheduler_events_total[1m])'], legend="{{type}}"),
        p(title="Redis Timer Events/min", type="timeseries", h=4, w=4, x=4, y=18,
          exprs=['rate(redis_timer_events_total[1m])'], legend="{{type}}"),
        p(title="Luminaire Commands Sent/min", type="timeseries", h=4, w=4, x=8, y=18,
          exprs=['rate(luminaire_commands_sent_total[1m])'], legend="{{type}}"),
        p(title="Luminaire ACK Errors/min", type="timeseries", h=4, w=4, x=12, y=18,
          exprs=['rate(luminaire_ack_errors_total[1m])'], legend="{{ip}}"),
        p(title="SSE Connection State", type="timeseries", h=4, w=4, x=16, y=18,
          exprs=['sse_connected'], legend="{{client}}"),
        p(title="Mode Toggle Events/min", type="timeseries", h=4, w=4, x=20, y=18,
          exprs=['rate(mode_toggle_total[1m])'], legend="toggles/min"),

        # ---- Manual vs Auto ----
        p(title="Time in AUTO mode", type="timeseries", h=4, w=6, x=0, y=22,
          exprs=['time() - scheduler_mode_change_timestamp{mode="AUTO"}'],
          legend="seconds in AUTO"),
        p(title="Manual CCT Override", type="timeseries", h=4, w=6, x=6, y=22,
          exprs=['manual_cct'], legend="{{instance}}",
          fieldConfig={"defaults": {"min": 3500, "max": 6500}}),
        p(title="Manual Lux Override", type="timeseries", h=4, w=6, x=12, y=22,
          exprs=['manual_lux'], legend="{{instance}}",
          fieldConfig={"defaults": {"min": 0, "max": 500}}),
        p(title="Last Scene Loaded", type="stat", h=4, w=6, x=18, y=22,
          exprs=['scheduler_loaded_scene'], legend="{{instance}}",
          options={"graphMode": "none"}),

        # ---- Scene Profile Viewer ----
        p(title="CCT Scene Profile", type="timeseries", h=6, w=12, x=0, y=26,
          exprs=['scene_profile_cct{scene=~".*"}'],
          legend="{{scene}}",
          fieldConfig={"defaults": {"min": 3500, "max": 6500}}),
        p(title="Lux Scene Profile", type="timeseries", h=6, w=12, x=12, y=26,
          exprs=['scene_profile_lux{scene=~".*"}'],
          legend="{{scene}}",
          fieldConfig={"defaults": {"min": 0, "max": 500}}),

        # ---- Error Rate ----
        p(title="Service Error Rate", type="timeseries", h=5, w=6, x=0, y=32,
          exprs=['rate(scheduler_errors_total[1m])', 'rate(state_errors_total[1m])', 'rate(timer_errors_total[1m])', 'rate(luminaire_errors_total[1m])'],
          legend="{{__name__}}"),
        p(title="Slow Ticks (>1s)", type="timeseries", h=5, w=6, x=6, y=32,
          exprs=['rate(scheduler_slow_ticks_total[1m])'],
          legend="slow ticks/min"),
        p(title="Redis Publish Failures", type="timeseries", h=5, w=6, x=12, y=32,
          exprs=['rate(redis_publish_errors_total[1m])'],
          legend="errors/min"),
        p(title="Log Errors/min", type="timeseries", h=5, w=6, x=18, y=32,
          exprs=['count_over_time({service=~".*"} |= "error" |~ "error|failed|crash" [1m])'],
          legend="{{service}}"),
    ],
)

write("LCS System Health Dashboard.json", health)
write("LCS Scene Throughput Dashboard.json", scene_throughput)
