from datetime import time
from unittest.mock import MagicMock

from services.interpolator import StepInterpolation, STRATEGY_MAP


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


class TestStepInterpolation:
    def test_step_returns_current_point_value(self):
        strat = StepInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_scene()

        # 6:00:00 exactly — matches first point
        strat.compute(scene, 6 * 3600, runtime)

        assert runtime.cct == 4000
        assert runtime.lux == 200

    def test_step_uses_previous_point_between(self):
        strat = StepInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_scene()

        # 8:00:00 — between 6h and 12h, should use 6h values
        strat.compute(scene, 8 * 3600, runtime)

        assert runtime.cct == 4000
        assert runtime.lux == 200

    def test_step_progress_computed(self):
        strat = StepInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_scene()

        strat.compute(scene, 36000, runtime)

        assert hasattr(runtime, "progress")
        assert 0.0 <= runtime.progress <= 100.0


class TestStrategyMapStep:
    def test_step_in_map(self):
        assert "step" in STRATEGY_MAP
        assert STRATEGY_MAP["step"] == StepInterpolation
