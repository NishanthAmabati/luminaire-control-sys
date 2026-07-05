import structlog
from abc import ABC, abstractmethod
from datetime import datetime as dt

log = structlog.get_logger()


class InterpolationStrategy(ABC):
    @abstractmethod
    def compute(self, scene, now_sec, runtime):
        pass


class LinearInterpolation(InterpolationStrategy):
    def compute(self, scene, now_sec, runtime):
        for i in range(len(scene)):
            curr = scene[i]
            next_ = scene[(i + 1) % len(scene)]

            t1 = curr["time"].hour * 3600 + curr["time"].minute * 60 + curr["time"].second
            t2 = next_["time"].hour * 3600 + next_["time"].minute * 60 + next_["time"].second

            t1_adj, t2_adj, now_adj = t1, t2, now_sec

            if t2_adj <= t1_adj:
                t2_adj += 86400
                if now_adj < t1_adj:
                    now_adj += 86400

            if t1_adj <= now_adj < t2_adj:
                span = t2_adj - t1_adj
                factor = (now_adj - t1_adj) / span if span > 0 else 0

                runtime.cct = round((curr["cct"] + (next_["cct"] - curr["cct"]) * factor), 2)
                runtime.lux = round((curr["lux"] + (next_["lux"] - curr["lux"]) * factor), 2)

                log.debug(
                    "interpolation_computed",
                    scene=runtime.running_scene,
                    segment=f"{i}_to_{(i + 1) % len(scene)}",
                    factor=round(factor, 4),
                    calc_cct=runtime.cct,
                    calc_lux=runtime.lux
                )

                self._update_scene_progress(now_sec, scene, runtime)
                return

    def _update_scene_progress(self, now_sec, scene, runtime):
        s_start = scene[0]["time"].hour * 3600 + scene[0]["time"].minute * 60 + scene[0]["time"].second
        s_end = scene[-1]["time"].hour * 3600 + scene[-1]["time"].minute * 60 + scene[-1]["time"].second

        now_p = now_sec
        if s_end <= s_start:
            s_end += 86400
            if now_p < s_start:
                now_p += 86400

        total_duration = s_end - s_start
        if total_duration > 0:
            elapsed = now_p - s_start
            progress = (elapsed / total_duration) * 100
            runtime.progress = round(max(0.0, min(progress, 100.0)), 2)
        else:
            runtime.progress = 0.0


class StepInterpolation(InterpolationStrategy):
    def compute(self, scene, now_sec, runtime):
        for i in range(len(scene)):
            curr = scene[i]
            next_ = scene[(i + 1) % len(scene)]

            t1 = curr["time"].hour * 3600 + curr["time"].minute * 60 + curr["time"].second
            t2 = next_["time"].hour * 3600 + next_["time"].minute * 60 + next_["time"].second

            t1_adj, t2_adj, now_adj = t1, t2, now_sec

            if t2_adj <= t1_adj:
                t2_adj += 86400
                if now_adj < t1_adj:
                    now_adj += 86400

            if t1_adj <= now_adj < t2_adj:
                runtime.cct = curr["cct"]
                runtime.lux = curr["lux"]

                log.debug(
                    "interpolation_computed_step",
                    scene=runtime.running_scene,
                    segment=f"{i}_to_{(i + 1) % len(scene)}",
                    calc_cct=runtime.cct,
                    calc_lux=runtime.lux
                )

                self._update_scene_progress(now_sec, scene, runtime)
                return

    def _update_scene_progress(self, now_sec, scene, runtime):
        s_start = scene[0]["time"].hour * 3600 + scene[0]["time"].minute * 60 + scene[0]["time"].second
        s_end = scene[-1]["time"].hour * 3600 + scene[-1]["time"].minute * 60 + scene[-1]["time"].second

        now_p = now_sec
        if s_end <= s_start:
            s_end += 86400
            if now_p < s_start:
                now_p += 86400

        total_duration = s_end - s_start
        if total_duration > 0:
            elapsed = now_p - s_start
            progress = (elapsed / total_duration) * 100
            runtime.progress = round(max(0.0, min(progress, 100.0)), 2)
        else:
            runtime.progress = 0.0


STRATEGY_MAP = {
    "linear": LinearInterpolation,
    "step": StepInterpolation,
}


class Interpolator:
    def __init__(self, runtime_obj, scenes_dict, timezone, mode="linear"):
        self.runtime = runtime_obj
        self.scenes = scenes_dict
        self.tz = timezone

        strategy_cls = STRATEGY_MAP.get(mode)
        if not strategy_cls:
            log.warning("interpolation_mode_unknown_falling_back_to_linear", mode=mode)
            strategy_cls = LinearInterpolation
        self.strategy = strategy_cls()

    async def compute_current_values(self):
        if not self.runtime.running_scene:
            return

        scene = self.scenes.get(self.runtime.running_scene)
        if not scene or len(scene) < 2:
            log.warning(
                "interpolation_skipped_invalid_scene",
                scene_name=self.runtime.running_scene,
                points_count=len(scene) if scene else 0
            )
            return

        now_dt = dt.now(self.tz)
        now_sec = (
            now_dt.hour * 3600 +
            now_dt.minute * 60 +
            now_dt.second +
            (now_dt.microsecond / 1_000_000)
        )

        self.strategy.compute(scene, now_sec, self.runtime)
