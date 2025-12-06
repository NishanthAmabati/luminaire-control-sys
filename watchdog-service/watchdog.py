#!/usr/bin/env python3
"""
Watchdog Service - Monitors and restarts critical services periodically
to prevent memory leaks and maintain system health.
"""

import subprocess
import time
import logging
import sys
from datetime import datetime
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"service": "watchdog-service", "time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load configuration
try:
    with open('/app/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    restart_interval_hours = config.get('watchdog', {}).get('restart_interval_hours', 6)
    monitored_services = config.get('watchdog', {}).get('monitored_services', [
        'scheduler-service',
        'luminaire-service',
        'timer-service',
        'monitoring-service',
        'websocket-service'
    ])
except Exception as e:
    logger.warning(f"Could not load config.yaml, using defaults: {e}")
    restart_interval_hours = 6
    monitored_services = [
        'scheduler-service',
        'luminaire-service',
        'timer-service',
        'monitoring-service',
        'websocket-service'
    ]

restart_interval_seconds = restart_interval_hours * 3600

def restart_container(container_name):
    """Restart a Docker container gracefully"""
    try:
        logger.info(f"Restarting container: {container_name}")
        result = subprocess.run(
            ['docker', 'restart', container_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully restarted {container_name}")
            return True
        else:
            logger.error(f"Failed to restart {container_name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout restarting {container_name}")
        return False
    except Exception as e:
        logger.error(f"Error restarting {container_name}: {e}")
        return False

def check_container_running(container_name):
    """Check if a container is running"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return container_name in result.stdout
    except Exception as e:
        logger.error(f"Error checking container {container_name}: {e}")
        return False

def main():
    """Main watchdog loop"""
    logger.info(f"Watchdog service started - monitoring {len(monitored_services)} services")
    logger.info(f"Restart interval: {restart_interval_hours} hours ({restart_interval_seconds} seconds)")
    logger.info(f"Monitored services: {', '.join(monitored_services)}")
    
    last_restart_times = {service: time.time() for service in monitored_services}
    
    while True:
        try:
            current_time = time.time()
            
            for service in monitored_services:
                time_since_last_restart = current_time - last_restart_times[service]
                
                # Check if it's time to restart this service
                if time_since_last_restart >= restart_interval_seconds:
                    # Verify container is running before restart
                    if check_container_running(service):
                        logger.info(f"Service {service} uptime: {time_since_last_restart/3600:.2f} hours - restarting")
                        
                        if restart_container(service):
                            last_restart_times[service] = current_time
                            # Wait a bit between restarts to avoid overwhelming the system
                            time.sleep(30)
                        else:
                            logger.warning(f"Failed to restart {service}, will retry next cycle")
                    else:
                        logger.warning(f"Service {service} not running, skipping restart")
                        last_restart_times[service] = current_time  # Reset timer
            
            # Sleep for 60 seconds before next check
            time.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("Watchdog service shutting down...")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error in watchdog loop: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == '__main__':
    main()
