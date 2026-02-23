import csv
import os
import logging

from datetime import time as dt

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class SceneLoader:
    def __init__(self, scenes_dir, scales):
        self.scenes_dir = scenes_dir
        self.scales = scales

    def _validate_range(self, name, value, min_v, max_v, path, line_no):
        if value < min_v or value > max_v:
            raise ValueError(f"{path}:{line_no} {name} out of range {min_v}-{max_v}): {value}")

    def load_all(self):
        scenes = {}
        if not os.path.isdir(self.scenes_dir):
            log.error(f"scenes directory not found: {self.scenes_dir}")
            return scenes
        for file in os.listdir(self.scenes_dir):
            if not file.endswith(".csv"):
                continue
            scene_name = file.removesuffix(".csv")
            path = os.path.join(self.scenes_dir, file)
            try:
                scenes[scene_name] = self._load_scene(path)
                log.info(f"loaded scene: {scene_name}")
            except Exception:
                log.exception(f"failed to load scene: {scene_name}")
        log.info(f"loaded {len(scenes)} scenes")
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
                except Exception:
                    raise ValueError(f"{path}:{i} invalid time format: {row['time']}")
                
                try:
                    cct = float(row["cct"])
                except Exception:
                    raise ValueError(f"{path}:{i} invalid cct value: {row['cct']}")
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
                except Exception:
                    raise ValueError(f"{path}:{i} invalid lux value: {row['lux']}")
                self._validate_range(
                    "lux",
                    lux,
                    lux_scale.get("min", float("-inf")),
                    lux_scale.get("max", float("inf")),
                    path,
                    i,
                )
                
                points.append({
                    "time": dt(hour=h, minute=m),
                    "cct": float(row["cct"]),
                    "lux": float(row["lux"]),
                })
        return sorted(points, key=lambda x: x["time"])
