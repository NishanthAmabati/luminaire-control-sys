"""Functional tests for state_service — state CRUD, serialization, timer/scene operations."""

import json
import pytest
import sys, os

_state_root = os.path.join(os.path.dirname(__file__), "..")
if _state_root in sys.path:
    sys.path.remove(_state_root)
sys.path.insert(0, _state_root)

from models.state import SystemState, MetricsState, TimerState, ManualState, AutoState
from models.requests import (
    SystemPowerRequest, ModeRequest, SceneRequest,
    ManualRequest, TimerToggleRequest, TimerConfigureRequest,
)
from dataclasses import asdict

# ═══════════════════════════════════════════════════════════════════════════════
# SystemState
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemState:
    def test_default_construction(self):
        s = SystemState()
        assert s.system_on is None  # dataclass default None
        assert s.mode == "MANUAL"
        assert isinstance(s.metrics, MetricsState)
        assert isinstance(s.timer, TimerState)
        assert isinstance(s.manual, ManualState)
        assert isinstance(s.auto, AutoState)

    def test_from_dict_full(self):
        data = {
            "system_on": True,
            "mode": "AUTO",
            "metrics": {"cpu": 45.0, "memory": 60.0, "temperature": 36.0, "uptime": 1000.0},
            "timer": {"enabled": True, "start": "07:00", "end": "19:00"},
            "auto": {"loaded_scene": "office", "running_scene": "office", "scene_progress": 50.0},
            "manual": {"last_toggle": "2025-01-01T12:00:00"},
        }
        s = SystemState.from_dict(data)
        assert s.system_on is True
        assert s.mode == "AUTO"
        assert s.metrics.cpu == 45.0
        assert s.timer.enabled is True
        assert s.auto.loaded_scene == "office"
        assert s.manual.last_toggle == "2025-01-01T12:00:00"

    def test_from_dict_minimal(self):
        s = SystemState.from_dict({"system_on": True})
        assert s.system_on is True
        assert s.mode == "MANUAL"
        assert s.metrics.cpu is None

    def test_from_dict_empty(self):
        s = SystemState.from_dict({})
        assert s.system_on is False  # from_dict defaults system_on to False
        assert s.mode == "MANUAL"

    def test_to_dict(self):
        s = SystemState(system_on=True, mode="AUTO")
        d = s.to_dict()
        assert d["system_on"] is True
        assert d["mode"] == "AUTO"
        assert "metrics" in d
        assert "timer" in d
        assert "manual" in d
        assert "auto" in d

    def test_to_dict_from_dict_roundtrip(self):
        data = {
            "system_on": True,
            "mode": "AUTO",
            "metrics": {"cpu": 50.0, "memory": 70.0, "temperature": None, "uptime": None},
            "timer": {"enabled": True, "start": None, "end": None},
            "auto": {"loaded_scene": None, "running_scene": None, "scene_progress": None, "cct": None, "lux": None},
            "manual": {"last_toggle": None, "cct": None, "lux": None, "cw": None, "ww": None},
            "last_updated": None,
        }
        s = SystemState.from_dict(data)
        d = s.to_dict()
        assert d["system_on"] is True
        assert d["mode"] == "AUTO"

    def test_json_serializable(self):
        s = SystemState(system_on=True)
        d = s.to_dict()
        js = json.dumps(d)
        assert isinstance(js, str)


# ═══════════════════════════════════════════════════════════════════════════════
# MetricsState
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsState:
    def test_default_all_none(self):
        m = MetricsState()
        assert m.cpu is None
        assert m.memory is None
        assert m.temperature is None
        assert m.uptime is None

    def test_construction(self):
        m = MetricsState(cpu=45.2, memory=62.1, temperature=38.5, uptime=12345.0)
        assert m.cpu == 45.2
        assert m.memory == 62.1
        assert m.temperature == 38.5
        assert m.uptime == 12345.0

    def test_asdict(self):
        m = MetricsState(cpu=50.0, memory=70.0)
        d = asdict(m)
        assert d["cpu"] == 50.0
        assert d["memory"] == 70.0
        assert d["temperature"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# TimerState
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimerState:
    def test_default(self):
        t = TimerState()
        assert t.enabled is None
        assert t.start is None
        assert t.end is None

    def test_construction(self):
        from datetime import time
        t = TimerState(enabled=True, start=time(7, 0), end=time(19, 0))
        assert t.enabled is True
        assert t.start == time(7, 0)
        assert t.end == time(19, 0)

    def test_asdict(self):
        from datetime import time
        t = TimerState(enabled=True, start=time(7, 0), end=time(19, 0))
        d = asdict(t)
        assert d["enabled"] is True
        assert d["start"] == time(7, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# AutoState & ManualState
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutoState:
    def test_default(self):
        a = AutoState()
        assert a.loaded_scene is None
        assert a.running_scene is None

    def test_construction(self):
        a = AutoState(loaded_scene="office", running_scene="office", scene_progress=50.0, cct=4000.0, lux=300.0)
        assert a.loaded_scene == "office"
        assert a.running_scene == "office"
        assert a.scene_progress == 50.0
        assert a.cct == 4000.0

    def test_asdict_omits_none(self):
        a = AutoState(loaded_scene="office")
        d = asdict(a)
        assert d["loaded_scene"] == "office"
        assert d["running_scene"] is None


class TestManualState:
    def test_default(self):
        m = ManualState()
        assert m.last_toggle is None
        assert m.cct is None
        assert m.lux is None
        assert m.cw is None
        assert m.ww is None

    def test_construction(self):
        m = ManualState(last_toggle="2025-01-01T12:00:00", cct=4000.0, lux=300.0, cw=128.0, ww=128.0)
        assert m.last_toggle == "2025-01-01T12:00:00"
        assert m.cct == 4000.0

    def test_asdict_partial(self):
        m = ManualState(cw=50.0, ww=50.0)
        d = asdict(m)
        assert d["cw"] == 50.0
        assert d["ww"] == 50.0
        assert d["cct"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Request Models (Pydantic)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequestModels:
    def test_system_power_request(self):
        r = SystemPowerRequest(on=True)
        assert r.on is True

    def test_mode_request(self):
        r = ModeRequest(mode="AUTO")
        assert r.mode == "AUTO"

    def test_scene_request(self):
        r = SceneRequest(scene="office")
        assert r.scene == "office"

    def test_manual_request(self):
        r = ManualRequest(medium="sliders", cct=5000, lux=300)
        assert r.medium == "sliders"
        assert r.cct == 5000.0
        assert r.lux == 300.0

    def test_manual_request_defaults(self):
        r = ManualRequest(medium="buttons")
        assert r.medium == "buttons"
        assert r.cct is None
        assert r.lux is None
        assert r.cw is None
        assert r.ww is None

    def test_timer_toggle_request(self):
        r = TimerToggleRequest(enabled=True)
        assert r.enabled is True

    def test_timer_configure_request(self):
        r = TimerConfigureRequest(start="07:00", end="19:00")
        assert r.start == "07:00"
        assert r.end == "19:00"
