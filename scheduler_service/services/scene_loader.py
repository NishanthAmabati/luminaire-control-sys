import csv
import os
import structlog

from datetime import time as dt

log = structlog.get_logger()

class SceneLoader:
    def __init__(self, scenes_dir, scales):
        self.scenes_dir = scenes_dir
        self.scales = scales

    def _validate_range(self, name, value, min_v, max_v, path, line_no):
        if value < min_v or value > max_v:
            raise ValueError(f"{path}:{line_no} {name} out of range {min_v}-{max_v}: {value}")

    def load_all(self):
        scenes = {}
        if not os.path.isdir(self.scenes_dir):
            log.error("scene_load_aborted_dir_not_found", path=self.scenes_dir)
            return scenes
            
        for file in os.listdir(self.scenes_dir):
            if not file.endswith(".csv"):
                continue
                
            scene_name = file.removesuffix(".csv")
            path = os.path.join(self.scenes_dir, file)
            
            try:
                scenes[scene_name] = self._load_scene(path)
                log.info("scene_loaded", scene_name=scene_name, points_count=len(scenes[scene_name]))
            except Exception as e:
                log.error("scene_load_failed", scene_name=scene_name, file_path=path, error=str(e), exc_info=True)
                
        log.info("all_scenes_loaded", total_scenes=len(scenes))
        return scenes
    
    def _load_scene(self, path):
        points = []
        cct_scale = self.scales.get("cct", {})
        lux_scale = self.scales.get("lux", {})

        with open(path, newline="") as f:
            reader = csv.DictReader(f)

            required_cols = {"time", "cct", "lux"}
            if not required_cols.issubset(reader.fieldnames or []):
                missing = required_cols - set(reader.fieldnames or [])
                raise ValueError(f"{path}: missing columns {missing}")
            
            for i, row in enumerate(reader, start=2):
                try:
                    h, m = map(int, row["time"].split(":"))
                    t = dt(hour=h, minute=m)
                except Exception as e:
                    raise ValueError(f"{path}:{i} invalid time format: {row['time']}") from e
                
                try:
                    cct = float(row["cct"])
                except Exception as e:
                    raise ValueError(f"{path}:{i} invalid cct value: {row['cct']}") from e
                    
                self._validate_range(
                    "cct",
                    cct,
                    cct_scale.get("min", float("-inf")),
                    cct_scale.get("max", float("inf")),
                    path,
                    i,
                )

                try:
                    lux = float(row["lux"])
                except Exception as e:
                    raise ValueError(f"{path}:{i} invalid lux value: {row['lux']}") from e
                    
                self._validate_range(
                    "lux",
                    lux,
                    lux_scale.get("min", float("-inf")),
                    lux_scale.get("max", float("inf")),
                    path,
                    i,
                )
                
                points.append({
                    "time": t,
                    "cct": cct,
                    "lux": lux,
                })
                
        return sorted(points, key=lambda x: x["time"])