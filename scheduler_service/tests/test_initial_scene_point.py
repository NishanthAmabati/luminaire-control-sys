from datetime import time
from unittest.mock import MagicMock

from services.interpolator import LinearInterpolation, StepInterpolation

def make_initial_scene():
    return [
        {"time": time(0, 0, 0), "cct": 3000, "lux": 50, "initial": True},
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


class TestInitialScenePoint:
    def test_linear_uses_initial_point_before_first_real(self):
        strat = LinearInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_initial_scene()
        # 3:00 AM — before 6:00 first real point
        strat.compute(scene, 3 * 3600, runtime)
        assert runtime.cct == 3000
        assert runtime.lux == 50
        assert runtime.progress == 0.0

    def test_linear_ignores_initial_after_first_real(self):
        strat = LinearInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_initial_scene()
        # 8:00 AM — after 6:00, normal interpolation
        strat.compute(scene, 8 * 3600, runtime)
        assert runtime.cct != 3000  # not initial value
        assert runtime.lux != 50

    def test_step_uses_initial_point_before_first_real(self):
        strat = StepInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_initial_scene()
        strat.compute(scene, 3 * 3600, runtime)
        assert runtime.cct == 3000
        assert runtime.lux == 50
        assert runtime.progress == 0.0

    def test_step_ignores_initial_after_first_real(self):
        strat = StepInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = make_initial_scene()
        strat.compute(scene, 8 * 3600, runtime)
        assert runtime.cct != 3000
        assert runtime.lux != 50

    def test_no_initial_point_still_works(self):
        strat = LinearInterpolation()
        runtime = make_runtime(running_scene="office")
        scene = [
            {"time": time(6, 0, 0), "cct": 4000, "lux": 200},
            {"time": time(12, 0, 0), "cct": 6000, "lux": 500},
        ]
        strat.compute(scene, 8 * 3600, runtime)
        assert runtime.cct is not None
        assert runtime.lux is not None
