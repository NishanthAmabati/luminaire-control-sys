from datetime import time
from unittest.mock import MagicMock

from services.interpolator import LinearInterpolation, Interpolator, STRATEGY_MAP


def make_scene():
    return [
        {"time": time(6, 0, 0), "cct": 4000, "lux": 200},
        {"time": time(12, 0, 0), "cct": 6000, "lux": 500},
        {"time": time(18, 0, 0), "cct": 5000, "lux": 300},
        {"time": time(23, 59, 59), "cct": 4000, "lux": 200},
    ]


def make_runtime(**kwargs):
    r = MagicMock()
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


class TestLinearInterpolation:
    def test_compute_mid_segment(self):
        strat = LinearInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_scene()

        # noon-ish: 43200s — between 6h (21600) and 12h (43200)
        strat.compute(scene, 36000, runtime)

        assert runtime.cct is not None
        assert runtime.lux is not None

    def test_progress_computed(self):
        strat = LinearInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_scene()

        strat.compute(scene, 36000, runtime)

        assert hasattr(runtime, "progress")
        assert 0.0 <= runtime.progress <= 100.0


class TestStrategyMap:
    def test_linear_in_map(self):
        assert "linear" in STRATEGY_MAP
        assert STRATEGY_MAP["linear"] == LinearInterpolation


class TestInterpolator:
    def test_unknown_mode_falls_back_to_linear(self):
        runtime = make_runtime(running_scene="office")
        scenes = {"office": make_scene()}
        interp = Interpolator(runtime, scenes, "UTC", mode="nonexistent")
        assert isinstance(interp.strategy, LinearInterpolation)

    def test_linear_mode_selects_linear(self):
        runtime = make_runtime(running_scene="office")
        scenes = {"office": make_scene()}
        interp = Interpolator(runtime, scenes, "UTC", mode="linear")
        assert isinstance(interp.strategy, LinearInterpolation)

    async def test_compute_no_running_scene(self):
        runtime = make_runtime(running_scene=None)
        interp = Interpolator(runtime, {}, "UTC", mode="linear")
        # should not raise
        await interp.compute_current_values()
