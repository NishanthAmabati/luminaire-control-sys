"""Functional tests for scheduler_service — scene lifecycle, tick cycle, channel mapping, interpolation."""

import pytest
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

from services.light_channeler import LightChanneler
from services.interpolator import (
    Interpolator, LinearInterpolation, StepInterpolation,
    STRATEGY_MAP,
)
from models.scheduler_runtime import SchedulerRuntime


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def channeler():
    return LightChanneler(cct_min=3500, cct_max=6500, lux_min=0, lux_max=500)


@pytest.fixture
def runtime():
    r = SchedulerRuntime()
    return r


SIMPLE_SCENE = [
    {"time": time(6, 0, 0), "cct": 4000, "lux": 200},
    {"time": time(12, 0, 0), "cct": 6000, "lux": 500},
    {"time": time(18, 0, 0), "cct": 5000, "lux": 300},
]

SCENE_WITH_INITIAL = [
    {"time": time(0, 0, 0), "cct": 3000, "lux": 50, "initial": True},
    {"time": time(6, 0, 0), "cct": 4000, "lux": 200},
    {"time": time(12, 0, 0), "cct": 6000, "lux": 500},
    {"time": time(18, 0, 0), "cct": 5000, "lux": 300},
    {"time": time(23, 59, 59), "cct": 4000, "lux": 200},
]


# ═══════════════════════════════════════════════════════════════════════════════
# LightChanneler
# ═══════════════════════════════════════════════════════════════════════════════

class TestLightChanneler:
    def test_resolve_channels_linear(self, channeler):
        # At midpoint (5000K, 250lux) — expect cw ~ ww
        result = channeler.resolve_channels(5000, 250)
        assert result is not None
        cw, ww = result["cw"], result["ww"]
        assert 0 <= cw <= 100
        assert 0 <= ww <= 100
        assert abs(cw - ww) < 10  # roughly balanced at midpoint
        assert abs(cw + ww - 50.0) < 1  # total = intensity_factor * 100

    def test_resolve_channels_full_cold(self, channeler):
        result = channeler.resolve_channels(6500, 500)
        assert result["cw"] > 90
        assert result["ww"] < 10

    def test_resolve_channels_full_warm(self, channeler):
        result = channeler.resolve_channels(3500, 500)
        assert result["ww"] > 90
        assert result["cw"] < 10

    def test_resolve_channels_dark(self, channeler):
        result = channeler.resolve_channels(5000, 0)
        assert result["cw"] == 0.0
        assert result["ww"] == 0.0

    def test_resolve_channels_clamps_inputs(self, channeler):
        result = channeler.resolve_channels(10000, 1000)
        assert result["cw"] <= 100
        assert result["ww"] <= 100

    def test_resolve_cct_midpoint(self, channeler):
        result = channeler.resolve_cct(50, 50)
        assert result["cct"] == 5000

    def test_resolve_cct_warm(self, channeler):
        result = channeler.resolve_cct(10, 90)
        assert result["cct"] < 5000

    def test_resolve_cct_cold(self, channeler):
        result = channeler.resolve_cct(90, 10)
        assert result["cct"] > 5000

    def test_resolve_cct_zero_division(self, channeler):
        result = channeler.resolve_cct(0, 0)
        assert result["cct"] == "NA"

    def test_resolve_cct_clamps(self, channeler):
        result = channeler.resolve_cct(200, 200)
        assert 3500 <= result["cct"] <= 6500

    def test_resolve_channels_none_values(self, channeler):
        assert channeler.resolve_channels(None, 250) is None
        assert channeler.resolve_channels(5000, None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Interpolation Strategies
# ═══════════════════════════════════════════════════════════════════════════════

class TestLinearInterpolation:
    def test_exact_point_match(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        strat.compute(SIMPLE_SCENE, 6 * 3600, runtime)
        assert runtime.cct == 4000
        assert runtime.lux == 200

    def test_mid_segment_interpolation(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        # 9:00 — halfway between 6h and 12h
        strat.compute(SIMPLE_SCENE, 9 * 3600, runtime)
        assert runtime.cct == pytest.approx(5000, abs=1)
        assert runtime.lux == pytest.approx(350, abs=1)

    def test_segment_quarter(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        # 7:30 — quarter between 6h and 12h
        strat.compute(SIMPLE_SCENE, 7.5 * 3600, runtime)
        assert runtime.cct == pytest.approx(4500, abs=1)
        assert runtime.lux == pytest.approx(275, abs=1)

    def test_progress_at_start(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        strat.compute(SIMPLE_SCENE, 6 * 3600, runtime)
        assert runtime.progress == pytest.approx(0, abs=1)

    def test_progress_at_midpoint(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        strat.compute(SIMPLE_SCENE, 12 * 3600, runtime)
        assert 40 < runtime.progress < 60


class TestStepInterpolation:
    def test_exact_point_match(self, runtime):
        strat = StepInterpolation()
        runtime.running_scene = "warehouse"
        strat.compute(SIMPLE_SCENE, 6 * 3600, runtime)
        assert runtime.cct == 4000

    def test_between_points_uses_prev(self, runtime):
        strat = StepInterpolation()
        runtime.running_scene = "warehouse"
        strat.compute(SIMPLE_SCENE, 8 * 3600, runtime)
        assert runtime.cct == 4000  # between 6-12, uses 6h value

    def test_after_last_point(self, runtime):
        strat = StepInterpolation()
        runtime.running_scene = "warehouse"
        strat.compute(SIMPLE_SCENE, 20 * 3600, runtime)
        assert runtime.cct == 5000  # in 18->6(wrap) segment, uses 18h value


class TestInitialPointHandling:
    def test_linear_uses_initial_before_first(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        strat.compute(SCENE_WITH_INITIAL, 3 * 3600, runtime)
        assert runtime.cct == 3000
        assert runtime.lux == 50
        assert runtime.progress == 0.0

    def test_linear_ignores_initial_after_first(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        strat.compute(SCENE_WITH_INITIAL, 8 * 3600, runtime)
        assert runtime.cct != 3000

    def test_step_uses_initial_before_first(self, runtime):
        strat = StepInterpolation()
        runtime.running_scene = "office"
        strat.compute(SCENE_WITH_INITIAL, 3 * 3600, runtime)
        assert runtime.cct == 3000

    def test_step_ignores_initial_after_first(self, runtime):
        strat = StepInterpolation()
        runtime.running_scene = "office"
        strat.compute(SCENE_WITH_INITIAL, 8 * 3600, runtime)
        assert runtime.cct != 3000

    def test_no_initial_still_works(self, runtime):
        strat = LinearInterpolation()
        runtime.running_scene = "office"
        strat.compute(SIMPLE_SCENE, 8 * 3600, runtime)
        assert runtime.cct is not None


class TestInterpolatorFacade:
    def test_linear_mode(self, runtime):
        import pytz
        scenes = {"office": SIMPLE_SCENE}
        runtime.running_scene = "office"
        interp = Interpolator(runtime, scenes, pytz.UTC, mode="linear")
        import asyncio
        asyncio.run(interp.compute_current_values())
        assert runtime.cct is not None

    def test_step_mode(self, runtime):
        import pytz
        scenes = {"office": SIMPLE_SCENE}
        runtime.running_scene = "office"
        interp = Interpolator(runtime, scenes, pytz.UTC, mode="step")
        import asyncio
        asyncio.run(interp.compute_current_values())
        assert runtime.cct is not None

    def test_unknown_mode_fallback(self, runtime):
        import pytz
        scenes = {"office": SIMPLE_SCENE}
        runtime.running_scene = "office"
        interp = Interpolator(runtime, scenes, pytz.UTC, mode="bogus")
        import asyncio
        asyncio.run(interp.compute_current_values())
        assert isinstance(interp.strategy, LinearInterpolation)

    def test_no_running_scene_noop(self, runtime):
        import pytz
        interp = Interpolator(runtime, {}, pytz.UTC, mode="linear")
        import asyncio
        asyncio.run(interp.compute_current_values())
        assert runtime.cct == 0.0

    def test_missing_scene_noop(self, runtime):
        import pytz
        runtime.running_scene = "nonexistent"
        interp = Interpolator(runtime, {}, pytz.UTC, mode="linear")
        import asyncio
        asyncio.run(interp.compute_current_values())
        assert runtime.cct == 0.0

    def test_strategy_map_contains_all(self):
        assert "linear" in STRATEGY_MAP
        assert "step" in STRATEGY_MAP
        assert STRATEGY_MAP["linear"] == LinearInterpolation
        assert STRATEGY_MAP["step"] == StepInterpolation


# ═══════════════════════════════════════════════════════════════════════════════
# SchedulerRuntime
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchedulerRuntime:
    def test_default_construction(self):
        r = SchedulerRuntime()
        assert r.system_on is None
        assert r.mode is None
        assert r.cct == 0.0
        assert r.lux == 0.0
        assert r.cw == 0.0
        assert r.ww == 0.0
        assert r.progress == 0.0
        assert r.running_scene is None
        assert r.available_scenes is None

    def test_field_assignments(self, runtime):
        runtime.system_on = True
        runtime.mode = "AUTO"
        runtime.cct = 5000.0
        runtime.lux = 300.0
        runtime.cw = 45.5
        runtime.ww = 54.5
        runtime.progress = 75.0
        runtime.running_scene = "office"
        runtime.available_scenes = ["office", "lab"]
        runtime.loaded_scene = "office"

        assert runtime.system_on is True
        assert runtime.mode == "AUTO"
        assert runtime.cct == 5000.0
        assert runtime.lux == 300.0
        assert runtime.cw == 45.5
        assert runtime.ww == 54.5
        assert runtime.progress == 75.0
        assert runtime.running_scene == "office"
        assert runtime.available_scenes == ["office", "lab"]
        assert runtime.loaded_scene == "office"

    def test_reset_scene(self, runtime):
        runtime.running_scene = "office"
        runtime.scene_start_ts = 1000.0
        runtime.progress = 50.0
        runtime.reset_scene()
        assert runtime.running_scene is None
        assert runtime.scene_start_ts is None
        assert runtime.progress == 0.0

    def test_reset_scene_when_already_none(self, runtime):
        runtime.reset_scene()
        assert runtime.running_scene is None


# ═══════════════════════════════════════════════════════════════════════════════
# Adaptive Tick
# ═══════════════════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler Service (mocked dependencies)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSchedulerService:
    """Functional simulation of the Scheduler service loop with mocked Redis/HTTP."""

    @pytest.fixture
    def sched(self):
        with patch("services.scheduler_service.Interpolator") as MockInterp, \
             patch("services.scheduler_service.LightChanneler") as MockChan, \
             patch("services.scheduler_service.LuminaireClient") as MockClient:

            from services.scheduler_service import Scheduler
            si = MagicMock()
            si.compute_current_values = AsyncMock()
            si.strategy = MagicMock()

            MockInterp.return_value = si
            MockChan.return_value.resolve_channels.return_value = {"cw": 50.0, "ww": 50.0}
            MockClient.return_value = MagicMock()

            scene_loader_mock = MagicMock()
            scene_loader_mock.load_all.return_value = {"office": SIMPLE_SCENE}

            s = Scheduler(
                redis=AsyncMock(),
                tz="Asia/Kolkata",
                scene_loader=scene_loader_mock,
                scheduler_interval=1.0,
                interpolation_mode="linear",
                pub_chan="scheduler:events",
                cct_min=3500, cct_max=6500,
                lux_min=0, lux_max=500,
                luminaire_service_url="http://luminaire:8000",
            )
            # Patch runtime after init to avoid constructor side effects
            s.runtime = SchedulerRuntime()
            s.publish_runtime = AsyncMock()
            s.publish_state = AsyncMock()
            s.redis.publish = AsyncMock()
            s.runtime.available_scenes = ["office"]
            yield s

    async def test_load_scene(self, sched):
        await sched.load_scene("office")
        assert sched.runtime.loaded_scene == "office"

    async def test_activate_scene(self, sched):
        sched.runtime.mode = "AUTO"
        await sched.activate_scene("office")
        assert sched.runtime.running_scene == "office"

    async def test_deactivate_scene(self, sched):
        sched.runtime.running_scene = "office"
        await sched.deactivate_scene()
        assert sched.runtime.running_scene is None
        assert sched.runtime.loaded_scene is None

    async def test_handle_power(self, sched):
        import json
        sched.redis.get = AsyncMock(return_value=json.dumps({"system_on": True}))
        await sched.handle_power()
        assert sched.runtime.system_on is True

    async def test_handle_mode_auto(self, sched):
        import json
        sched.redis.get = AsyncMock(return_value=json.dumps({"system_on": True, "mode": "AUTO", "auto": {}, "manual": {}}))
        await sched.handle_mode()
        assert sched.runtime.mode == "AUTO"

    async def test_handle_mode_manual(self, sched):
        import json
        sched.redis.get = AsyncMock(return_value=json.dumps({"system_on": True, "mode": "MANUAL", "manual": {"last_toggle": "sliders", "cct": 5000, "lux": 300}, "auto": {}}))
        await sched.handle_mode()
        assert sched.runtime.mode == "MANUAL"

    async def test_apply_manual_sliders(self, sched):
        await sched.apply_manual("sliders", cct=5000, lux=300)
        assert sched.runtime.cct == 5000
        assert sched.runtime.lux == 300

    async def test_tick_running_scene_interpolates(self, sched):
        sched.luminaire_client.send = AsyncMock()
        sched.runtime.system_on = True
        sched.runtime.mode = "AUTO"
        sched.runtime.running_scene = "office"
        await sched.tick()
        sched.interpolator.compute_current_values.assert_awaited()

    async def test_tick_no_scene_skips(self, sched):
        sched.luminaire_client.send = AsyncMock()
        sched.runtime.system_on = True
        sched.runtime.mode = "AUTO"
        sched.runtime.running_scene = None
        await sched.tick()
        sched.interpolator.compute_current_values.assert_not_awaited()

    async def test_tick_system_off_sends_zero(self, sched):
        sched.luminaire_client.send = AsyncMock()
        sched.runtime.system_on = False
        await sched.tick()
        sched.interpolator.compute_current_values.assert_not_awaited()
        assert sched.runtime.cct == 0.0

    async def test_manual_mode_does_not_interpolate(self, sched):
        sched.luminaire_client.send = AsyncMock()
        sched.runtime.system_on = True
        sched.runtime.mode = "MANUAL"
        sched.runtime.running_scene = None
        await sched.tick()
        sched.interpolator.compute_current_values.assert_not_awaited()

    async def test_sync_from_redis(self, sched):
        import json
        state = json.dumps({
            "system_on": True, "mode": "AUTO",
            "auto": {"loaded_scene": "office", "running_scene": "office", "cct": 5000, "lux": 300, "scene_progress": 50},
            "manual": {"cct": None, "lux": None, "cw": None, "ww": None},
        })
        sched.redis.get = AsyncMock(return_value=state)
        sched.interpolator.strategy = MagicMock()

        await sched.sync_from_redis()
        assert sched.runtime.system_on is True
        assert sched.runtime.mode == "AUTO"
        assert sched.runtime.running_scene == "office"

    async def test_sync_from_redis_none_state(self, sched):
        sched.redis.get = AsyncMock(return_value=None)
        await sched.sync_from_redis()  # should not raise
