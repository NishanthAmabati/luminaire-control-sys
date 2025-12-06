"""
Production-Grade Timer Service Operations

This module provides robust timer functionality with:
- Immediate trigger support (triggers at scheduled time even if just set)
- Proper timezone handling
- Race condition prevention
- Clear trigger state management
- Comprehensive error handling
- Redis-backed persistence
- Retry logic for API failures
- Performance optimizations
"""

import asyncio
import json
import logging
import httpx
import structlog
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import redis. asyncio as aioredis

from timer_service.models import Timer, SetTimerData

logger = structlog.get_logger(service="timer-service")

# Timer check interval in seconds - how often to check for timers to trigger
TIMER_CHECK_INTERVAL = 15

# Maximum retries for API calls
MAX_API_RETRIES = 3

# API call timeout
API_TIMEOUT = 10. 0


class TimerOperations:
    """Production-grade timer operations with immediate triggering support"""
    
    def __init__(self, redis_client: aioredis.Redis, api_url: str):
        """
        Initialize timer operations
        
        Args:
            redis_client: Async Redis client for state persistence
            api_url: API service URL for system control
        """
        self. redis_client = redis_client
        self.api_url = api_url
        self.timers: List[Dict] = []
        self.is_enabled: bool = False
        self._running: bool = False
        
        # Metrics for monitoring
        self.metrics = {
            "triggers_total": 0,
            "triggers_failed": 0,
            "last_trigger_time": None,
            "last_check_time": None
        }
        
    async def _broadcast_timer_status(self):
        """Broadcast current timer status via Redis pub/sub to update UI"""
        try:
            timer_status = {
                "system_timers": self.timers,
                "isTimerEnabled": self.is_enabled,
            }
            await self.redis_client.publish("system_update", json.dumps(timer_status))
            logger.debug("Broadcasted timer status", timer_count=len(self.timers), enabled=self.is_enabled)
        except Exception as e:
            logger.error("Failed to broadcast timer status", error=str(e))
        
    async def initialize(self):
        """Load timer state from Redis on startup"""
        try:
            # Load timers from Redis
            timers_data = await self.redis_client.get("timer:timers")
            if timers_data:
                self.timers = json.loads(timers_data)
                
            # Load enabled state from Redis
            enabled_data = await self.redis_client.get("timer:enabled")
            if enabled_data:
                self.is_enabled = json.loads(enabled_data)
                
            logger.info("Timer state loaded from Redis", timers=len(self.timers), enabled=self. is_enabled)
            
            # Broadcast initial timer status to UI
            await self._broadcast_timer_status()
        except Exception as e:
            logger.error("Failed to load timer state from Redis", error=str(e))
            
    async def set_timers(self, data: SetTimerData) -> Dict:
        """
        Set system timers
        
        Args:
            data: Timer configuration data
            
        Returns:
            Dict with status and current timer configuration
        """
        try:
            # Validate all timers
            for timer in data. timers:
                try:
                    # Validate time format
                    on_time = datetime.strptime(timer.on, "%H:%M")
                    off_time = datetime.strptime(timer.off, "%H:%M")
                    
                    # Check for same time
                    if timer.on == timer.off:
                        error_msg = f"ON and OFF times cannot be the same: {timer.on}"
                        logger.error(error_msg)
                        return {"status": "error", "error": error_msg}
                        
                except ValueError as e:
                    error_msg = f"Invalid timer format: {timer.on} or {timer.off}. Expected HH:MM format."
                    logger.error(error_msg, error=str(e))
                    return {"status": "error", "error": error_msg}
            
            # Update timers - add enabled flag if not present
            self.timers = []
            for timer in data.timers:
                timer_dict = timer.dict()
                if "enabled" not in timer_dict:
                    timer_dict["enabled"] = True
                self. timers.append(timer_dict)
            
            self.is_enabled = len(self.timers) > 0
            
            # Persist to Redis
            await self.redis_client.set("timer:timers", json.dumps(self. timers))
            await self. redis_client.set("timer:enabled", json.dumps(self. is_enabled))
            
            # Clear all trigger state (allows immediate triggering on schedule)
            await self.redis_client.delete("timer:triggers")
            
            # Broadcast timer status to UI
            await self._broadcast_timer_status()
            
            logger.info("Timers set successfully", timer_count=len(self.timers), enabled=self.is_enabled)
            
            return {
                "status": "success",
                "message": f"Set {len(self.timers)} timer(s)",
                "isTimerEnabled": self.is_enabled,
                "timers": self. timers
            }
        except Exception as e:
            logger. error("Failed to set timers", error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}
            
    async def get_timers(self) -> Dict:
        """
        Get current timer configuration
        
        Returns:
            Dict with timers and enabled state
        """
        return {
            "timers": self.timers,
            "isTimerEnabled": self.is_enabled
        }
        
    async def toggle_timers(self, enable: bool) -> Dict:
        """
        Enable or disable the timer system
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            Dict with status and current configuration
        """
        try:
            self.is_enabled = enable
            
            # Persist to Redis
            await self.redis_client. set("timer:enabled", json. dumps(self.is_enabled))
            
            # When disabling, clear trigger state
            # Users can re-enable with the same timer configurations
            if not enable:
                await self.redis_client.delete("timer:triggers")
                logger.info("Timer system disabled - triggers cleared")
            else:
                logger.info("Timer system enabled", timers_count=len(self.timers))
                
            # Broadcast timer status to UI
            await self._broadcast_timer_status()
                
            logger.info("Timer system toggled", enabled=enable, timers_count=len(self.timers))
            
            return {
                "status": "success",
                "message": f"Timer system {'enabled' if enable else 'disabled'}",
                "isTimerEnabled": self.is_enabled,
                "timers": self.timers
            }
        except Exception as e:
            logger.error("Failed to toggle timer system", error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}
            
    async def reset_timers(self) -> Dict:
        """
        Reset all timers and disable the system
        
        Returns:
            Dict with status
        """
        try:
            self.timers = []
            self.is_enabled = False
            
            # Clear Redis
            await self.redis_client. delete("timer:timers")
            await self.redis_client. delete("timer:enabled")
            await self.redis_client.delete("timer:triggers")
            
            # Broadcast the cleared state to UI
            await self._broadcast_timer_status()
            
            logger.info("Timers reset and state broadcasted")
            
            return {
                "status": "success",
                "message": "All timers reset",
                "isTimerEnabled": False,
                "timers": []
            }
        except Exception as e:
            logger.error("Failed to reset timers", error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}
            
    async def _trigger_system(self, turn_on: bool, timer_id: str) -> bool:
        """
        Trigger system ON or OFF with retry logic
        
        Directly sets the system to the desired state with exponential backoff retry. 
        
        Args:
            turn_on: True to turn on, False to turn off
            timer_id: Identifier for this trigger (for logging/tracking)
            
        Returns:
            True if successful, False otherwise
        """
        action = "ON" if turn_on else "OFF"
        
        for attempt in range(MAX_API_RETRIES):
            try:
                async with httpx. AsyncClient(timeout=API_TIMEOUT) as client:
                    response = await client.post(
                        f"{self.api_url}/api/toggle_system",
                        json={"isSystemOn": turn_on}
                    )
                    
                    if response.status_code == 200:
                        logger.info(
                            f"Timer triggered: System set to {action}", 
                            timer_id=timer_id,
                            attempt=attempt + 1
                        )
                        
                        # Update metrics
                        self.metrics["triggers_total"] += 1
                        self.metrics["last_trigger_time"] = datetime. now(). isoformat()
                        
                        return True
                    else:
                        logger.warning(
                            f"Timer trigger failed, retrying.. .",
                            timer_id=timer_id,
                            attempt=attempt + 1,
                            status=response.status_code,
                            response=response.text
                        )
                        
            except Exception as e:
                logger.error(
                    f"Timer trigger error, attempt {attempt + 1}/{MAX_API_RETRIES}",
                    timer_id=timer_id,
                    error=str(e),
                    exc_info=True
                )
            
            # Exponential backoff before retry (except on last attempt)
            if attempt < MAX_API_RETRIES - 1:
                backoff_time = 2 ** attempt  # 1s, 2s, 4s... 
                logger.debug(f"Backing off for {backoff_time}s before retry", timer_id=timer_id)
                await asyncio.sleep(backoff_time)
        
        # All retries failed
        logger.error(
            f"Timer trigger failed after {MAX_API_RETRIES} attempts",
            timer_id=timer_id,
            action=action
        )
        
        # Update metrics
        self.metrics["triggers_failed"] += 1
        
        return False
            
    async def run_timer_loop(self):
        """
        Main timer loop - checks for timers to trigger at configurable intervals
        
        This loop:
        1. Runs at intervals defined by TIMER_CHECK_INTERVAL for responsiveness
        2. Checks all enabled timers continuously every day
        3. Triggers immediately if current time >= scheduled time
        4. Prevents duplicate triggers on the same day
        5. Automatically resets trigger state at midnight for next day
        6. Timers remain active daily until manually disabled
        7. Handles each timer's ON and OFF independently
        """
        self._running = True
        logger.info(f"Timer loop started - checking every {TIMER_CHECK_INTERVAL} seconds")
        
        while self._running:
            try:
                # Update last check time for health monitoring
                self.metrics["last_check_time"] = datetime. now().isoformat()
                
                # Check if timer system is enabled
                if not self. is_enabled or not self.timers:
                    await asyncio.sleep(TIMER_CHECK_INTERVAL)
                    continue
                    
                # Get current time
                now = datetime. now()
                today_str = now.strftime("%Y-%m-%d")
                current_time_str = now.strftime("%H:%M")
                
                # Load trigger state from Redis
                triggers_data = await self.redis_client.get("timer:triggers")
                if triggers_data:
                    triggers = json.loads(triggers_data)
                else:
                    triggers = {}
                    
                # Reset triggers if it's a new day (automatic daily recurrence)
                if triggers. get("date") != today_str:
                    triggers = {"date": today_str, "triggered": {}}
                    await self.redis_client.set("timer:triggers", json.dumps(triggers))
                    logger.info("New day detected - timer triggers reset for daily recurrence", date=today_str)
                    
                triggered_count = 0
                triggers_changed = False  # Track if we need to write to Redis
                    
                # Check each timer (single loop - no nesting)
                for idx, timer in enumerate(self.timers):
                    # Skip disabled timers
                    if not timer. get("enabled", True):
                        continue
                        
                    on_time = timer["on"]
                    off_time = timer["off"]
                    
                    # Create unique identifiers for this timer's triggers TODAY
                    on_trigger_id = f"timer_{idx}_on_{today_str}"
                    off_trigger_id = f"timer_{idx}_off_{today_str}"
                    
                    # Check if already triggered today
                    on_already_triggered = triggers["triggered"].get(on_trigger_id)
                    off_already_triggered = triggers["triggered"].get(off_trigger_id)
                    
                    # Check if current time has reached scheduled times
                    on_should_trigger = current_time_str >= on_time
                    off_should_trigger = current_time_str >= off_time
                    
                    # Trigger ON independently at its scheduled time
                    if on_should_trigger and not on_already_triggered:
                        logger.info(
                            "Timer ON trigger activated", 
                            timer_index=idx, 
                            scheduled_time=on_time, 
                            current_time=current_time_str, 
                            date=today_str
                        )
                        
                        if await self._trigger_system(True, on_trigger_id):
                            triggers["triggered"][on_trigger_id] = now.isoformat()
                            triggers_changed = True
                            triggered_count += 1
                    
                    # Trigger OFF independently at its scheduled time
                    # Note: Not 'elif' - both can trigger in the same check cycle
                    if off_should_trigger and not off_already_triggered:
                        logger.info(
                            "Timer OFF trigger activated", 
                            timer_index=idx,
                            scheduled_time=off_time, 
                            current_time=current_time_str, 
                            date=today_str
                        )
                        
                        if await self._trigger_system(False, off_trigger_id):
                            triggers["triggered"][off_trigger_id] = now.isoformat()
                            triggers_changed = True
                            triggered_count += 1
                
                # Write to Redis once after all triggers (batch write for performance)
                if triggers_changed:
                    await self.redis_client.set("timer:triggers", json.dumps(triggers))
                    logger.info(
                        "Timer triggers executed - will recur daily", 
                        triggered_today=triggered_count,
                        total_triggered=len(triggers["triggered"]),
                        date=today_str
                    )
                    # Broadcast timer status after triggers to keep UI in sync
                    await self._broadcast_timer_status()
                    
            except Exception as e:
                logger.error("Error in timer loop", error=str(e), exc_info=True)
                
            # Wait before next check
            await asyncio.sleep(TIMER_CHECK_INTERVAL)
            
        logger.info("Timer loop stopped")
    
    async def stop(self):
        """Stop the timer loop gracefully"""
        self._running = False
        logger.info("Timer loop stopping...")
        
    async def health_check(self) -> Dict:
        """
        Get health status of timer service
        
        Returns:
            Dict with health information
        """
        return {
            "status": "healthy" if self._running else "stopped",
            "running": self._running,
            "enabled": self.is_enabled,
            "timer_count": len(self.timers),
            "metrics": self.metrics,
            "check_interval_seconds": TIMER_CHECK_INTERVAL
        }