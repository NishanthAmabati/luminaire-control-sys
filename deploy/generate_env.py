import os
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
OUTPUT_PATH = os.path.join(ROOT, ".env")

def env_line(key, value):
    return f"{key}={value}"

def replace_host(url: str, host: str) -> str:
    if not isinstance(url, str):
        return url
    for prefix in ("http://", "https://", "redis://"):
        if url.startswith(prefix):
            rest = url[len(prefix):]
            if rest.startswith("localhost") or rest.startswith("127.0.0.1") or rest.startswith("0.0.0.0"):
                rest = rest.split(":", 1)[1] if ":" in rest else rest
                return f"{prefix}{host}{rest if rest.startswith(':') else ':' + rest if rest else ''}"
    return url

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

services = config.get("services", {})
scales = config.get("scales", {})
timezone = config.get("timezone", "")
event_gateway = config.get("event_gateway", {})
ui = config.get("ui", {})

lines = []

redis_url = services.get("redis", {}).get("redis_url", "")
redis_url = replace_host(redis_url, "redis")
lines.append(env_line("REDIS_URL", redis_url))

tcp = services.get("tcp", {})
tcp_fastapi = tcp.get("fastAPI", {})
tcp_tcpserver = tcp.get("tcpserver", {})
tcp_redis = tcp.get("redis", {})

lines.extend([
    env_line("LUMINAIRE_TCP_HOST", tcp_tcpserver.get("host", "")),
    env_line("LUMINAIRE_TCP_PORT", tcp_tcpserver.get("port", "")),
    env_line("LUMINAIRE_REDIS_PUB", tcp_redis.get("pub", "")),
    env_line("LUMINAIRE_API_HOST", tcp_fastapi.get("host", "")),
    env_line("LUMINAIRE_API_PORT", tcp_fastapi.get("port", "")),
    env_line("LUMINAIRE_API_LOOP", tcp_fastapi.get("loop", "")),
    env_line("LUMINAIRE_API_LOG_LEVEL", tcp_fastapi.get("log_level", "")),
    env_line("LUMINAIRE_API_ACCESS_LOG", tcp_fastapi.get("access_log", "")),
])

state = services.get("state", {})
state_fastapi = state.get("fastAPI", {})
state_redis = state.get("redis", {})

scheduler = services.get("scheduler", {})
scheduler_redis = scheduler.get("redis", {})

metrics = services.get("metrics", {})
metrics_redis = metrics.get("redis", {})

lines.extend([
    env_line("STATE_API_HOST", state_fastapi.get("host", "")),
    env_line("STATE_API_PORT", state_fastapi.get("port", "")),
    env_line("STATE_API_LOOP", state_fastapi.get("loop", "")),
    env_line("STATE_API_LOG_LEVEL", state_fastapi.get("log_level", "")),
    env_line("STATE_API_ACCESS_LOG", state_fastapi.get("access_log", "")),
    env_line("STATE_REDIS_PUB", state_redis.get("pub", "")),
    env_line("SCHEDULER_REDIS_PUB", scheduler_redis.get("pub", "")),
    env_line("METRICS_REDIS_PUB", metrics_redis.get("pub", "")),
])

scenes_dir = "/app/scheduler_service/scenes"
luminaire_url = scheduler.get("luminaire_service_url", "")
luminaire_url = replace_host(luminaire_url, "luminaire-service")

lines.extend([
    env_line("SCHEDULER_SCENES_DIR", scenes_dir),
    env_line("SCHEDULER_INTERVAL", scheduler.get("interval", "")),
    env_line("SCHEDULER_LUMINAIRE_URL", luminaire_url),
    env_line("SCALES_CCT_MIN", scales.get("cct", {}).get("min", "")),
    env_line("SCALES_CCT_MAX", scales.get("cct", {}).get("max", "")),
    env_line("SCALES_LUX_MIN", scales.get("lux", {}).get("min", "")),
    env_line("SCALES_LUX_MAX", scales.get("lux", {}).get("max", "")),
    env_line("TIMEZONE", timezone),
])

timer = services.get("timer", {})
timer_redis = timer.get("redis", {})

timer_state_url = timer.get("state_service_url", "")
timer_state_url = replace_host(timer_state_url, "state-service")

lines.extend([
    env_line("TIMER_REDIS_PUB", timer_redis.get("pub", "")),
    env_line("TIMER_STATE_SERVICE_URL", timer_state_url),
])

lines.extend([
    env_line("METRICS_INTERVAL", metrics.get("interval", "")),
])

gw_service = event_gateway.get("service", {})
gw_redis = event_gateway.get("redis", {})
gw_channels = event_gateway.get("channels", {})
gw_sse = event_gateway.get("sse", {})

gateway_state_url = gw_service.get("state_service_url", "")
gateway_state_url = replace_host(gateway_state_url, "state-service")
gateway_redis_url = gw_redis.get("url", "")
gateway_redis_url = replace_host(gateway_redis_url, "redis")

lines.extend([
    env_line("GATEWAY_PORT", gw_service.get("port", "")),
    env_line("GATEWAY_LOG_LEVEL", gw_service.get("log_level", "")),
    env_line("GATEWAY_STATE_SERVICE_URL", gateway_state_url),
    env_line("GATEWAY_REDIS_URL", gateway_redis_url),
    env_line("GATEWAY_REDIS_RECONNECT_MS", gw_redis.get("reconnect_strategy_ms", "")),
    env_line("GATEWAY_CHANNEL_SCHEDULER", gw_channels.get("scheduler", "")),
    env_line("GATEWAY_CHANNEL_LUMINAIRES", gw_channels.get("luminaires", "")),
    env_line("GATEWAY_CHANNEL_TIMER", gw_channels.get("timer", "")),
    env_line("GATEWAY_CHANNEL_METRICS", gw_channels.get("metrics", "")),
    env_line("GATEWAY_HEARTBEAT_MS", gw_sse.get("heartbeat_interval_ms", "")),
    env_line("GATEWAY_LATENCY_INTERVAL_MS", gw_sse.get("latency_interval_ms", "")),
])

state_port = state_fastapi.get("port", "")
gateway_port = gw_service.get("port", "")

lines.extend([
    env_line("VITE_API_URL", f"http://127.0.0.1:{state_port}"),
    env_line("VITE_EVENT_GATEWAY_URL", f"http://127.0.0.1:{gateway_port}"),
    env_line("VITE_UI_CONFIG_URL", "/config.yaml"),
])

with open(OUTPUT_PATH, "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"wrote {OUTPUT_PATH}")
