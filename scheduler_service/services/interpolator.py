import logging
import traceback
from datetime import datetime as dt

log = logging.getLogger(__name__)

class Interpolator:
    def __init__(self, runtime_obj, scenes_dict, timezone):
        self.runtime = runtime_obj
        self.scenes = scenes_dict
        self.tz = timezone
        log.info("interpolator initialized")

    async def compute_current_values(self):
        """calculates and updates cct, lux, and progress on the runtime object"""
        try:
            if not self.runtime.running_scene:
                log.debug("no running scene to interpolate")
                return

            scene = self.scenes.get(self.runtime.running_scene)
            if not scene:
                log.error(f"scene {self.runtime.running_scene} not found in scenes dict")
                return
            
            if len(scene) < 2:
                log.warning(f"scene {self.runtime.running_scene} has fewer than 2 points cannot interpolate")
                return

            # use high-precision time for smooth transitions
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

                # handle midnight wrap for the specific segment
                if t2_adj <= t1_adj:
                    t2_adj += 86400
                    if now_adj < t1_adj:
                        now_adj += 86400

                # if current time falls within this segment
                if t1_adj <= now_adj < t2_adj:
                    span = t2_adj - t1_adj
                    factor = (now_adj - t1_adj) / span if span > 0 else 0

                    # linear interpolation
                    self.runtime.cct = round((curr["cct"] + (next_["cct"] - curr["cct"]) * factor), 2)
                    self.runtime.lux = round((curr["lux"] + (next_["lux"] - curr["lux"]) * factor), 2)

                    log.debug(f"interpolating segment {i} to {i+1} with factor {factor:.4f} resulting in cct {self.runtime.cct} lux {self.runtime.lux}")

                    self._update_scene_progress(now_sec, scene)
                    return
            
            log.warning("could not find a valid time segment for current time")

        except Exception as e:
            log.error(f"failed to compute interpolated values error {str(e).lower()}")
            log.debug(traceback.format_exc().lower())

    def _update_scene_progress(self, now_sec, scene):
        try:
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
                log.debug("total scene duration is zero or negative progress set to zero")
                
            log.debug(f"scene progress updated to {self.runtime.progress}%")

        except Exception as e:
            log.error(f"error updating scene progress {str(e).lower()}")
            log.debug(traceback.format_exc().lower())