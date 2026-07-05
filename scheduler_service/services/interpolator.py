import structlog
from datetime import datetime as dt

log = structlog.get_logger()

class Interpolator:
    def __init__(self, runtime_obj, scenes_dict, timezone):
        self.runtime = runtime_obj
        self.scenes = scenes_dict
        self.tz = timezone

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

        initial = scene[0] if scene[0].get("initial") else None
        if initial:
            first_real = scene[1] if len(scene) > 1 else None
            if first_real:
                t_first = first_real["time"].hour * 3600 + first_real["time"].minute * 60 + first_real["time"].second
                if now_sec < t_first:
                    self.runtime.cct = initial["cct"]
                    self.runtime.lux = initial["lux"]
                    self.runtime.progress = 0.0
                    log.debug("interpolation_initial_hold", cct=self.runtime.cct, lux=self.runtime.lux)
                    return
            scene = [p for p in scene if not p.get("initial")]

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
                    log.debug("interpolation_midnight_wrap_applied", scene=self.runtime.running_scene, segment_index=i)

            if t1_adj <= now_adj < t2_adj:
                span = t2_adj - t1_adj
                factor = (now_adj - t1_adj) / span if span > 0 else 0

                self.runtime.cct = round((curr["cct"] + (next_["cct"] - curr["cct"]) * factor), 2)
                self.runtime.lux = round((curr["lux"] + (next_["lux"] - curr["lux"]) * factor), 2)

                log.debug(
                    "interpolation_computed",
                    scene=self.runtime.running_scene,
                    segment=f"{i}_to_{(i + 1) % len(scene)}",
                    factor=round(factor, 4),
                    calc_cct=self.runtime.cct,
                    calc_lux=self.runtime.lux
                )

                self._update_scene_progress(now_sec, scene)
                return

    def _update_scene_progress(self, now_sec, scene):
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
            self.runtime.progress = round(max(0.0, min(progress, 100.0)), 2)
            
            log.debug("progress_computed", progress=self.runtime.progress, elapsed_sec=round(elapsed, 1))
        else:
            self.runtime.progress = 0.0
            log.debug("progress_computed_zero_duration", progress=0.0)