"""Functional tests for timer_service — full timer lifecycle, scheduler, edge cases."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models.timer_runtime import TimerRuntime


# ═══════════════════════════════════════════════════════════════════════════════
# TimerRuntime
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimerRuntime:
    def test_defaults(self):
        r = TimerRuntime()
        assert r.timer_enabled is None
        assert r.timer_start is None
        assert r.timer_end is None

    def test_assignment(self):
        r = TimerRuntime()
        r.timer_enabled = True
        r.timer_start = "06:00"
        r.timer_end = "18:00"
        assert r.timer_enabled is True
        assert r.timer_start == "06:00"
        assert r.timer_end == "18:00"


# ═══════════════════════════════════════════════════════════════════════════════
# TimerService (mocked Redis + Scheduler)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTimerServiceFunctional:
    @pytest.fixture
    def service(self):
        with patch("services.timer_service.StateClient") as MockClient:
            MockClient.return_value = MagicMock()

            import fakeredis.aioredis
            from services.timer_service import TimerService

            redis = fakeredis.aioredis.FakeRedis()
            svc = TimerService(
                redis_url=redis,
                pub_chan="timer:events",
                tz="Asia/Kolkata",
                state_service_url="http://state:8000",
            )
            # Replace real scheduler with fake
            fake_sched = MagicMock()
            fake_sched.start = MagicMock()
            fake_sched.stop = MagicMock()
            fake_sched.shutdown = MagicMock()
            fake_sched.configure = MagicMock()
            fake_sched.clear_jobs = MagicMock()
            svc.scheduler = fake_sched
            yield svc, redis

    async def test_toggle_timer_with_payload_enable(self, service):
        svc, _ = service
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        await svc.toggle_timer({"enabled": True})
        assert svc.runtime.timer_enabled is True
        svc.scheduler.start.assert_called()

    async def test_toggle_timer_with_payload_disable(self, service):
        svc, _ = service
        svc.runtime.timer_enabled = True
        await svc.toggle_timer({"enabled": False})
        assert svc.runtime.timer_enabled is False
        svc.scheduler.clear_jobs.assert_called()

    async def test_toggle_timer_fallback_to_redis(self, service):
        svc, redis = service
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        await redis.set("system:state", json.dumps({"timer": {"enabled": True}}))
        await svc.toggle_timer(None)
        assert svc.runtime.timer_enabled is True

    async def test_configure_timer(self, service):
        svc, _ = service
        svc.runtime.timer_enabled = True
        await svc.configure_timer({"start": "07:00", "end": "19:00"})
        assert svc.runtime.timer_start == "07:00"
        assert svc.runtime.timer_end == "19:00"
        svc.scheduler.configure.assert_called_with("07:00", "19:00")

    async def test_configure_timer_skipped_when_disabled(self, service):
        svc, _ = service
        svc.runtime.timer_enabled = False
        await svc.configure_timer({"start": "07:00"})
        assert svc.runtime.timer_start is None  # not set

    async def test_clear_timer(self, service):
        svc, _ = service
        svc.runtime.timer_enabled = True
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        await svc.clear_timer()
        assert svc.runtime.timer_enabled is False
        assert svc.runtime.timer_start is None
        assert svc.runtime.timer_end is None
        svc.scheduler.clear_jobs.assert_called()

    async def test_sync_from_redis_populates_runtime(self, service):
        svc, redis = service
        state = json.dumps({
            "timer": {"enabled": True, "start": "06:00", "end": "18:00"},
        })
        await redis.set("system:state", state)
        await svc.sync_from_redis()
        assert svc.runtime.timer_enabled is True
        assert svc.runtime.timer_start == "06:00"
        assert svc.runtime.timer_end == "18:00"

    async def test_sync_from_redis_missing_state(self, service):
        svc, _ = service
        await svc.sync_from_redis()  # no key set — should not raise
        assert svc.runtime.timer_enabled is None

    async def test_publish_state_redis(self, service):
        svc, redis = service
        svc.runtime.timer_enabled = True
        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        await svc.publish_state()
        # verify redis channel got the message
        # Redis pub/sub doesn't store, can't assert on fake without subscriber
        # At least verify no exception

    async def test_shutdown_stops_scheduler(self, service):
        svc, _ = service
        svc.scheduler.running = True
        await svc.shutdown()
        svc.scheduler.shutdown.assert_called()

    async def test_toggle_timer_starts_when_start_end_set(self, service):
        """Regression: timer should start only when start AND end are set."""
        svc, _ = service
        # enabled but no start/end
        await svc.toggle_timer({"enabled": True})
        svc.scheduler.start.assert_not_called()

        svc.runtime.timer_start = "06:00"
        svc.runtime.timer_end = "18:00"
        await svc.toggle_timer({"enabled": True})
        svc.scheduler.start.assert_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler (APScheduler wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScheduler:
    def test_construction(self):
        from services.scheduler import Scheduler
        tz = "Asia/Kolkata"
        state_client = MagicMock()
        fake_apscheduler = MagicMock()
        with patch("services.scheduler.AsyncIOScheduler", return_value=fake_apscheduler):
            s = Scheduler(tz, state_client)
        assert s._started is False

    def test_start(self):
        from services.scheduler import Scheduler
        tz = "Asia/Kolkata"
        state_client = MagicMock()
        fake_apscheduler = MagicMock()
        with patch("services.scheduler.AsyncIOScheduler", return_value=fake_apscheduler):
            s = Scheduler(tz, state_client)
        s.start()
        assert s._started is True
        fake_apscheduler.start.assert_called_once()

    def test_shutdown(self):
        from services.scheduler import Scheduler
        tz = "Asia/Kolkata"
        state_client = MagicMock()
        fake_apscheduler = MagicMock()
        with patch("services.scheduler.AsyncIOScheduler", return_value=fake_apscheduler):
            s = Scheduler(tz, state_client)
        s.start()
        s.shutdown()
        assert s._started is False
        fake_apscheduler.shutdown.assert_called_once()

    def test_configure(self):
        from services.scheduler import Scheduler
        tz = "Asia/Kolkata"
        state_client = MagicMock()
        fake_apscheduler = MagicMock()
        with patch("services.scheduler.AsyncIOScheduler", return_value=fake_apscheduler):
            s = Scheduler(tz, state_client)
        s.configure("06:00", "18:00")
        assert fake_apscheduler.add_job.call_count == 2

    def test_clear_jobs(self):
        from services.scheduler import Scheduler
        tz = "Asia/Kolkata"
        state_client = MagicMock()
        fake_apscheduler = MagicMock()
        with patch("services.scheduler.AsyncIOScheduler", return_value=fake_apscheduler):
            s = Scheduler(tz, state_client)
        s.clear_jobs()
        fake_apscheduler.remove_all_jobs.assert_called_once()
