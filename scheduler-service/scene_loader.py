import csv
import os
import logging
import bisect
from typing import List, Tuple
import yaml
import json
import redis
import time
import structlog
import uuid

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup to STDOUT only
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[logging.StreamHandler()]
)
logger = structlog.get_logger(service="scene-loader")

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

scene_data = {}

def downsample_data(scene_data_list: List[Tuple[int, float, float]], points_per_hour: int = 6) -> Tuple[List[float], List[float]]:
    correlation_id = str(uuid.uuid4())
    logger.debug("Computing downsampled data", correlation_id=correlation_id, points_per_hour=points_per_hour)
    step_seconds = max(1, 3600 // points_per_hour)
    total_points = 86400 // step_seconds
    downsampled_cct = []
    downsampled_intensity = []

    segment_starts = [min_since_midnight * 60 for min_since_midnight, _, _ in scene_data_list]
    num_segments = len(scene_data_list)

    for point_idx in range(total_points):
        current_time_seconds = point_idx * step_seconds
        seg_idx = bisect.bisect_left(segment_starts, current_time_seconds) % num_segments
        if seg_idx == 0 and current_time_seconds < segment_starts[0]:
            seg_idx = num_segments - 1
        start_idx = seg_idx - 1 if seg_idx == 0 else seg_idx - 1
        start_min, start_cct, start_intensity = scene_data_list[start_idx]
        end_min, end_cct, end_intensity = scene_data_list[seg_idx]
        start_sec = start_min * 60
        end_sec = end_min * 60 if end_min > start_min else end_min * 60 + 86400
        if current_time_seconds < start_sec:
            current_time_seconds += 86400
        t = (current_time_seconds - start_sec) / (end_sec - start_sec)
        interpolated_cct = start_cct + (end_cct - start_cct) * t
        interpolated_intensity = start_intensity + (end_intensity - start_intensity) * t
        downsampled_cct.append(interpolated_cct)
        downsampled_intensity.append(interpolated_intensity)

    logger.debug("Downsampled data computed", correlation_id=correlation_id, point_count=len(downsampled_cct))
    return downsampled_cct, downsampled_intensity

def load_scenes() -> dict:
    correlation_id = str(uuid.uuid4())
    logger.info("Loading scenes", correlation_id=correlation_id)
    scene_dir = config["luminaire_operations"]["scene_directory"]
    if not os.path.exists(scene_dir):
        os.makedirs(scene_dir)
        logger.info("Created scene directory", correlation_id=correlation_id, directory=scene_dir)
    available_scenes = [f for f in os.listdir(scene_dir) if f.endswith('.csv')]
    global scene_data
    scene_data.clear()
    for scene in available_scenes:
        try:
            with open(os.path.join(scene_dir, scene), 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)
                scene_data_list = [(int(row[0].split(':')[0]) * 60 + int(row[0].split(':')[1]), float(row[1]), float(row[2])) for row in reader]
                downsampled_cct, downsampled_intensity = downsample_data(scene_data_list, points_per_hour=6)
                scene_data[scene] = {
                    "cct": downsampled_cct,
                    "intensity": downsampled_intensity
                }
                # Store scene data as JSON
                redis_client.set(f"scene_data:{scene}", json.dumps(scene_data[scene]))
            logger.info("Loaded scene", correlation_id=correlation_id, scene=scene)
            logger.debug("Scene data", correlation_id=correlation_id, scene=scene, cct_count=len(scene_data[scene]["cct"]), intensity_count=len(scene_data[scene]["intensity"]))
        except Exception as e:
            logger.error("Error loading scene", correlation_id=correlation_id, scene=scene, error=str(e))
    # Store available scenes as JSON
    redis_client.set("available_scenes", json.dumps(available_scenes))
    logger.info("Scenes loaded", correlation_id=correlation_id, scene_count=len(available_scenes))
    return available_scenes