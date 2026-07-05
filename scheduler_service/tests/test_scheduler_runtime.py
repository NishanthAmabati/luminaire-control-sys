from models.scheduler_runtime import SchedulerRuntime


class TestSchedulerRuntime:
    def test_has_available_scenes_field(self):
        r = SchedulerRuntime()
        assert hasattr(r, "available_scenes")

    def test_default_values(self):
        r = SchedulerRuntime()
        assert r.system_on is None
        assert r.mode is None
        assert r.available_scenes is None
        assert r.loaded_scene is None
        assert r.running_scene is None
        assert r.cct == 0.0
        assert r.lux == 0.0
        assert r.progress == 0.0
        assert r.cw == 0.0
        assert r.ww == 0.0

    def test_reset_scene(self):
        r = SchedulerRuntime()
        r.running_scene = "office"
        r.scene_start_ts = 1000.0
        r.progress = 50.0
        r.reset_scene()
        assert r.running_scene is None
        assert r.scene_start_ts is None
        assert r.progress == 0.0

    def test_available_scenes_assignment(self):
        r = SchedulerRuntime()
        scenes = ["office", "lab", "warehouse"]
        r.available_scenes = scenes
        assert r.available_scenes == scenes
