import logging
from datetime import datetime as dt

log = logging.getLogger(__name__)

class Interpolator:
    def __init__(self, runtime_obj, scenes_dict, timezone):
        self.runtime = runtime_obj
        self.scenes = scenes_dict
        self.tz = timezone

    async def compute_current_values(self):
        """Calculates and updates CCT, LUX, and Progress on the runtime object."""
        if not self.runtime.running_scene:
            return

        scene = self.scenes.get(self.runtime.running_scene)
        if not scene or len(scene) < 2:
            return

        # Use high-precision time for smooth transitions
        now_dt = dt.now(self.tz)
        now_sec = (
            now_dt.hour * 3600 +
            now_dt.minute * 60 +
            now_dt.second +
            (now_dt.microsecond / 1_000_000)
        )

        for i in range(len(scene)):
            curr = scene[i]
            next_ = scene[(i + 1) % len(scene)]

            t1 = curr["time"].hour * 3600 + curr["time"].minute * 60 + curr["time"].second
            t2 = next_["time"].hour * 3600 + next_["time"].minute * 60 + next_["time"].second

            t1_adj, t2_adj, now_adj = t1, t2, now_sec

            # Handle midnight wrap for the specific segment
            if t2_adj <= t1_adj:
                t2_adj += 86400
                if now_adj < t1_adj:
                    now_adj += 86400

            # If current time falls within this segment
            if t1_adj <= now_adj < t2_adj:
                span = t2_adj - t1_adj
                factor = (now_adj - t1_adj) / span if span > 0 else 0

                # Linear Interpolation
                self.runtime.cct = round((curr["cct"] + (next_["cct"] - curr["cct"]) * factor), 2)
                self.runtime.lux = round((curr["lux"] + (next_["lux"] - curr["lux"]) * factor), 2)

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
        else:
            self.runtime.progress = 0.0