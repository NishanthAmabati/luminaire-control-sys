from models.state import SystemState, MetricsState


class TestSystemState:
    def test_from_dict_includes_metrics(self):
        data = {
            "system_on": True,
            "mode": "AUTO",
            "metrics": {"cpu": 45.2, "memory": 62.1, "temperature": 38.5, "uptime": 12345.0},
            "timer": {"enabled": True, "start": "06:00", "end": "18:00"},
            "auto": {"loaded_scene": "office", "running_scene": "office", "scene_progress": 50.0, "cct": 5000.0, "lux": 300.0},
            "manual": {"last_toggle": None, "cct": None, "lux": None, "cw": None, "ww": None},
            "last_updated": "2026-07-05 10:00:00+05:30",
        }
        state = SystemState.from_dict(data)

        assert state.system_on is True
        assert state.mode == "AUTO"
        assert isinstance(state.metrics, MetricsState)
        assert state.metrics.cpu == 45.2
        assert state.metrics.memory == 62.1
        assert state.metrics.temperature == 38.5
        assert state.metrics.uptime == 12345.0

    def test_from_dict_empty_metrics(self):
        data = {
            "system_on": False,
            "mode": "MANUAL",
            "timer": {},
            "auto": {},
            "manual": {},
        }
        state = SystemState.from_dict(data)

        assert isinstance(state.metrics, MetricsState)
        assert state.metrics.cpu is None
        assert state.metrics.memory is None

    def test_from_dict_no_metrics_key(self):
        data = {
            "system_on": True,
            "mode": "AUTO",
            "timer": {},
            "auto": {},
            "manual": {},
        }
        state = SystemState.from_dict(data)

        assert isinstance(state.metrics, MetricsState)

    def test_to_dict_roundtrip(self):
        original = SystemState(
            system_on=True,
            mode="AUTO",
            metrics=MetricsState(cpu=50.0, memory=70.0, temperature=36.0, uptime=999.0),
            last_updated="2026-07-05 10:00:00+05:30",
        )
        d = original.to_dict()
        restored = SystemState.from_dict(d)

        assert restored.system_on == original.system_on
        assert restored.mode == original.mode
        assert restored.metrics.cpu == 50.0
        assert restored.metrics.memory == 70.0
        assert restored.metrics.temperature == 36.0
        assert restored.metrics.uptime == 999.0
