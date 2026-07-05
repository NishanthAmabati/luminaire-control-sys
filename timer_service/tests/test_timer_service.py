import json
import pytest
import fakeredis.aioredis
from unittest.mock import AsyncMock, MagicMock, patch
from services.timer_service import TimerService
from models.timer_runtime import TimerRuntime


class FakeScheduler:
    def __init__(self):
        self.running = False
        self.start_called = False
        self.stop_called = False
        self.configured_start = None
        self.configured_end = None
        self.jobs_cleared = False

    def start(self):
        self.running = True
        self.start_called = True

    def stop(self):
        self.running = False
        self.stop_called = True

    def shutdown(self):
        self.running = False

    def configure(self, start, end):
        self.configured_start = start
        self.configured_end = end

    def clear_jobs(self):
        self.jobs_cleared = True


@pytest.fixture
def service():
    redis = fakeredis.aioredis.FakeRedis()
    with patch("services.timer_service.StateClient") as MockClient:
        MockClient.return_value = MagicMock()
        svc = TimerService(
            redis_url=redis,
            pub_chan="timer:events",
            tz="Asia/Kolkata",
            state_service_url="http://state:8000",
        )
    fake_sched = FakeScheduler()
    svc.scheduler = fake_sched
    return svc, redis, fake_sched


class TestTimerService:
    async def test_toggle_timer_with_payload_enables(self, service):
        svc, _, scheduler = service
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        payload = {"enabled": True}
        await svc.toggle_timer(payload)

        assert svc.runtime.timer_enabled is True
        assert scheduler.start_called is True

    async def test_toggle_timer_with_payload_disables(self, service):
        svc, _, scheduler = service
        payload = {"enabled": False}
        await svc.toggle_timer(payload)

        assert svc.runtime.timer_enabled is False
        assert scheduler.jobs_cleared is True

    async def test_toggle_timer_falls_back_to_redis(self, service):
        svc, redis, scheduler = service
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        state = {"timer": {"enabled": True}}
        await redis.set("system:state", json.dumps(state))

        await svc.toggle_timer(None)

        assert svc.runtime.timer_enabled is True
        assert scheduler.start_called is True

    async def test_configure_timer_updates_start_end(self, service):
        svc, _, scheduler = service
        svc.runtime.timer_enabled = True
        payload = {"start": "07:00", "end": "19:00"}
        await svc.configure_timer(payload)

        assert svc.runtime.timer_start == "07:00"
        assert svc.runtime.timer_end == "19:00"
        assert scheduler.configured_start == "07:00"
        assert scheduler.configured_end == "19:00"

    async def test_configure_timer_skipped_when_disabled(self, service):
        svc, _, scheduler = service
        svc.runtime.timer_enabled = False
        payload = {"start": "07:00", "end": "19:00"}
        await svc.configure_timer(payload)

        assert scheduler.configured_start is None
        assert svc.runtime.timer_start is None  # not updated

    async def test_clear_timer_resets_runtime(self, service):
        svc, _, scheduler = service
        svc.runtime.timer_enabled = True
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"

        await svc.clear_timer()

        assert svc.runtime.timer_enabled is False
        assert svc.runtime.timer_start is None
        assert svc.runtime.timer_end is None
        assert scheduler.jobs_cleared is True
