def compute_tick_interval(system_on: bool | None, scheduler_interval: float) -> float:
    if system_on:
        return scheduler_interval
    return max(scheduler_interval * 5, 5.0)


class TestAdaptiveTickInterval:
    def test_returns_standard_interval_when_on(self):
        assert compute_tick_interval(True, 1.0) == 1.0
        assert compute_tick_interval(True, 0.5) == 0.5
        assert compute_tick_interval(True, 2.0) == 2.0

    def test_scales_to_5x_when_off(self):
        assert compute_tick_interval(False, 1.0) == 5.0
        assert compute_tick_interval(False, 2.0) == 10.0

    def test_enforces_5s_minimum_when_off(self):
        assert compute_tick_interval(False, 0.5) == 5.0
        assert compute_tick_interval(False, 0.1) == 5.0

    def test_none_treated_as_off(self):
        assert compute_tick_interval(None, 1.0) == 5.0
