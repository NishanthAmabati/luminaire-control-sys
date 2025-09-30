import csv
import os
import logging
import bisect
from typing import List, Tuple
import yaml
import pickle
import redis
import time

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Logging setup
timestamp = time.strftime(config["logging"]["filename_template"])
from logging.handlers import TimedRotatingFileHandler
handler = TimedRotatingFileHandler(
    timestamp,
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[handler, logging.StreamHandler()]
)

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

scene_data = {}

def downsample_data(scene_data_list: List[Tuple[int, float, float]], points_per_hour: int = 6) -> Tuple[List[float], List[float]]:
    """Directly compute downsampled data without building full interpolation list (memory optimization)."""
    logging.debug(f"Computing downsampled data for {points_per_hour} points per hour")
    step_seconds = max(1, 3600 // points_per_hour)
    total_points = 86400 // step_seconds
    downsampled_cct = []
    downsampled_intensity = []

    # Prepare segment starts for binary search
    segment_starts = [min_since_midnight * 60 for min_since_midnight, _, _ in scene_data_list]
    num_segments = len(scene_data_list)

    for point_idx in range(total_points):
        current_time_seconds = point_idx * step_seconds

        # Find the segment using binary search (DSA optimization for efficiency if many segments)
        seg_idx = bisect.bisect_left(segment_starts, current_time_seconds) % num_segments
        if seg_idx == 0 and current_time_seconds < segment_starts[0]:
            seg_idx = num_segments - 1  # Wrap around if before first

        start_idx = seg_idx - 1 if seg_idx == 0 else seg_idx - 1
        start_min, start_cct, start_intensity = scene_data_list[start_idx]
        end_min, end_cct, end_intensity = scene_data_list[seg_idx]

        start_sec = start_min * 60
        end_sec = end_min * 60 if end_min > start_min else end_min * 60 + 86400  # Handle wrap-around

        if current_time_seconds < start_sec:
            current_time_seconds += 86400  # Wrap for calculation

        t = (current_time_seconds - start_sec) / (end_sec - start_sec)
        interpolated_cct = start_cct + (end_cct - start_cct) * t
        interpolated_intensity = start_intensity + (end_intensity - start_intensity) * t

        downsampled_cct.append(interpolated_cct)
        downsampled_intensity.append(interpolated_intensity)

    logging.debug(f"Downsampled to {len(downsampled_cct)} points")
    return downsampled_cct, downsampled_intensity

def load_scenes() -> dict:
    """Load all scenes from CSV files and store in Redis and memory."""
    logging.debug("Loading scenes")
    scene_dir = config["luminaire_operations"]["scene_directory"]
    if not os.path.exists(scene_dir):
        os.makedirs(scene_dir)
    available_scenes = [f for f in os.listdir(scene_dir) if f.endswith('.csv')]
    global scene_data
    scene_data.clear()
    for scene in available_scenes:
        try:
            with open(os.path.join(scene_dir, scene), 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header
                scene_data_list = [(int(row[0].split(':')[0]) * 60 + int(row[0].split(':')[1]), float(row[1]), float(row[2])) for row in reader]
                
                # Use memory-optimized downsampling
                downsampled_cct, downsampled_intensity = downsample_data(scene_data_list, points_per_hour=6)
                scene_data[scene] = {
                    "cct": downsampled_cct,
                    "intensity": downsampled_intensity
                }
                # Store in Redis
                redis_client.set(f"scene_data:{scene}", pickle.dumps(scene_data[scene]))
            logging.info(f"Loaded scene {scene}.")
            logging.debug(f"Scene data for {scene}: {len(scene_data[scene]['cct'])} CCT points, {len(scene_data[scene]['intensity'])} intensity points")
        except Exception as e:
            logging.error(f"Error loading scene {scene}: {e}", exc_info=True)
    redis_client.set("available_scenes", pickle.dumps(available_scenes))
    return available_scenes