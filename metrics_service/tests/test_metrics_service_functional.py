"""Functional tests for metrics_service — collection, publishing, runtime model."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from models.metrics_runtime import MetricsRuntime


# ═══════════════════════════════════════════════════════════════════════════════
# MetricsRuntime
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsRuntime:
    def test_defaults(self):
        m = MetricsRuntime()
        assert m.cpu is None
        assert m.memory is None
        assert m.temperature is None
        assert m.uptime is None

    def test_assignment(self):
        m = MetricsRuntime()
        m.cpu = 45.2
        m.memory = 62.1
        m.temperature = 38.5
        m.uptime = 12345.0
        assert m.cpu == 45.2
        assert m.memory == 62.1
        assert m.temperature == 38.5
        assert m.uptime == 12345.0

    def test_asdict(self):
        m = MetricsRuntime(cpu=50.0, memory=70.0, temperature=36.0, uptime=999.0)
        d = asdict(m)
        assert d["cpu"] == 50.0
        assert d["memory"] == 70.0

    def test_asdict_partial(self):
        m = MetricsRuntime(cpu=50.0)
        d = asdict(m)
        assert d["cpu"] == 50.0
        assert d["memory"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# MetricsService (mocked psutil + Redis)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestMetricsService:
    @pytest.fixture
    def service(self):
        import fakeredis.aioredis
        fake_redis = fakeredis.aioredis.FakeRedis()
        with patch("services.metrics_service.Redis.from_url", return_value=fake_redis):
            with patch("services.metrics_service.psutil") as mock_psutil:
                # prime cpu_percent
                mock_psutil.cpu_percent.return_value = 0.0
                from services.metrics_service import MetricsService
                svc = MetricsService(
                    redis_url="redis://localhost:6379",
                    channel="metrics:events",
                    interval_s=5.0,
                )
        yield svc, fake_redis

    async def test_collect_returns_dict(self, service):
        svc, _ = service
        with patch("services.metrics_service.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 45.2
            mock_psutil.virtual_memory.return_value.percent = 62.1
            mock_psutil.sensors_temperatures.return_value = {
                "coretemp": [MagicMock(current=38.5)]
            }
            payload = svc.collect()
        assert payload["cpu"] == 45.2
        assert payload["memory"] == 62.1
        assert payload["temperature"] == 38.5

    async def test_collect_no_temperature_sensor(self, service):
        svc, _ = service
        with patch("services.metrics_service.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 50.0
            mock_psutil.virtual_memory.return_value.percent = 60.0
            mock_psutil.sensors_temperatures.return_value = {}
            with patch.object(svc, "_read_temperature_sys", return_value=None):
                payload = svc.collect()
        assert payload["cpu"] == 50.0
        assert payload["memory"] == 60.0
        assert payload["temperature"] is None

    async def test_publish_sends_to_redis(self, service):
        svc, redis = service
        sub = redis.pubsub()
        await sub.subscribe("metrics:events")
        # consume the subscribe message
        await sub.get_message(timeout=2.0)

        await svc.publish({"cpu": 50.0, "memory": 60.0, "temperature": 36.0})

        msg = await sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg["type"] == "message"
        data = json.loads(msg["data"])
        assert data["event"] == "metrics:events"
        assert data["payload"]["cpu"] == 50.0

    async def test_collect_handles_psutil_exception(self, service):
        svc, _ = service
        with patch("services.metrics_service.psutil.cpu_percent", side_effect=Exception("boom")):
            with patch("services.metrics_service.psutil.virtual_memory") as mock_vm:
                mock_vm.return_value.percent = 45.8
                with patch.object(svc, "_read_temperature", return_value=None):
                    payload = svc.collect()
        assert payload["cpu"] is None
        assert payload["memory"] == 45.8
