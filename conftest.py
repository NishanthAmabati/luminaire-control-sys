import sys
import os

# Each service directory needs to be on sys.path for its own imports
service_dirs = [
    "scheduler_service",
    "state_service",
    "luminaire_service",
    "timer_service",
    "metrics_service",
]
root = os.path.dirname(__file__)
for d in service_dirs:
    p = os.path.join(root, d)
    if p not in sys.path:
        sys.path.insert(0, p)
