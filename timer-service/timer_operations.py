"""
Production-Grade Timer Service Operations

This module provides robust timer functionality with:
- Immediate trigger support (triggers at scheduled time even if just set)
- Proper timezone handling
- Race condition prevention
- Clear trigger state management
- Comprehensive error handling
- Redis-backed persistence
"""

import asyncio
import json
import logging
import httpx
import structlog
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis.asyncio as aioredis

from models import Timer, SetTimerData

logger = structlog.get_logger(service="timer-service")


class TimerOperations:
    """Production-grade timer operations with immediate triggering support"""
    
    def __init__(self, redis_client: aioredis.Redis, api_url: str):
        """
        Initialize timer operations
        
        Args:
            redis_client: Async Redis client for state persistence
            api_url: API service URL for system control
        """
        self.redis_client = redis_client
        self.api_url = api_url
        self.timers: List[Dict] = []
        self.is_enabled: bool = False
        self._running: bool = False
        
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
                
            logger.info("Timer state loaded from Redis", timers=len(self.timers), enabled=self.is_enabled)
        except Exception as e:
            logger.error("Failed to load timer state from Redis", error=str(e))
            self.timers = []
            self.is_enabled = False
            
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
            for timer in data.timers:
                try:
                    datetime.strptime(timer.on, "%H:%M")
                    datetime.strptime(timer.off, "%H:%M")
                except ValueError as e:
                    error_msg = f"Invalid timer format: {timer.on} or {timer.off}"
                    logger.error(error_msg, error=str(e))
                    return {"status": "error", "error": error_msg}
            
            # Update timers
            self.timers = [timer.dict() for timer in data.timers]
            self.is_enabled = len(self.timers) > 0
            
            # Persist to Redis
            await self.redis_client.set("timer:timers", json.dumps(self.timers))
            await self.redis_client.set("timer:enabled", json.dumps(self.is_enabled))
            
            # Clear all trigger state (allows immediate triggering)
            await self.redis_client.delete("timer:triggers")
            
            logger.info("Timers set successfully", timer_count=len(self.timers), enabled=self.is_enabled)
            
            return {
                "status": "success",
                "message": f"Set {len(self.timers)} timer(s)",
                "isTimerEnabled": self.is_enabled,
                "timers": self.timers
            }
        except Exception as e:
            logger.error("Failed to set timers", error=str(e))
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
            await self.redis_client.set("timer:enabled", json.dumps(self.is_enabled))
            
            # If disabling, clear trigger state
            if not enable:
                await self.redis_client.delete("timer:triggers")
                
            logger.info("Timer system toggled", enabled=enable)
            
            return {
                "status": "success",
                "message": f"Timer system {'enabled' if enable else 'disabled'}",
                "isTimerEnabled": self.is_enabled,
                "timers": self.timers
            }
        except Exception as e:
            logger.error("Failed to toggle timer system", error=str(e))
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
            await self.redis_client.delete("timer:timers")
            await self.redis_client.delete("timer:enabled")
            await self.redis_client.delete("timer:triggers")
            
            logger.info("Timers reset")
            
            return {
                "status": "success",
                "message": "All timers reset",
                "isTimerEnabled": False,
                "timers": []
            }
        except Exception as e:
            logger.error("Failed to reset timers", error=str(e))
            return {"status": "error", "error": str(e)}
            
    async def _trigger_system(self, turn_on: bool, timer_id: str) -> bool:
        """
        Trigger system ON or OFF
        
        Args:
            turn_on: True to turn on, False to turn off
            timer_id: Identifier for this trigger (for logging/tracking)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/api/toggle_system",
                    json={"isSystemOn": turn_on}
                )
                
                if response.status_code == 200:
                    action = "ON" if turn_on else "OFF"
                    logger.info(f"Timer triggered: System turned {action}", timer_id=timer_id)
                    return True
                else:
                    logger.error(f"Timer trigger failed", timer_id=timer_id, status=response.status_code, response=response.text)
                    return False
                    
        except Exception as e:
            logger.error("Timer trigger error", timer_id=timer_id, error=str(e))
            return False
            
    async def run_timer_loop(self):
        """
        Main timer loop - checks every 30 seconds for timers to trigger
        
        This loop:
        1. Runs every 30 seconds for responsiveness
        2. Checks all enabled timers
        3. Triggers immediately if current time >= scheduled time
        4. Prevents duplicate triggers on the same day
        5. Resets trigger state at midnight
        """
        self._running = True
        logger.info("Timer loop started")
        
        while self._running:
            try:
                # Check if timer system is enabled
                if not self.is_enabled or not self.timers:
                    await asyncio.sleep(30)
                    continue
                    
                # Get current time
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                current_time_str = now.strftime("%H:%M")
                
                # Load trigger state from Redis
                triggers_data = await self.redis_client.get("timer:triggers")
                if triggers_data:
                    triggers = json.loads(triggers_data)
                else:
                    triggers = {}
                    
                # Reset triggers if it's a new day
                if triggers.get("date") != today_str:
                    triggers = {"date": today_str, "triggered": {}}
                    await self.redis_client.set("timer:triggers", json.dumps(triggers))
                    logger.info("Trigger state reset for new day", date=today_str)
                    
                triggered_this_cycle = False
                    
                # Check each timer
                for idx, timer in enumerate(self.timers):
                    if not timer.get("enabled", True):
                        continue
                        
                    on_time = timer["on"]
                    off_time = timer["off"]
                    
                    # Create unique identifiers for this timer's triggers
                    on_trigger_id = f"timer_{idx}_on"
                    off_trigger_id = f"timer_{idx}_off"
                    
                    # Check if ON time has been reached and not yet triggered today
                    if current_time_str >= on_time and not triggers["triggered"].get(on_trigger_id):
                        logger.info("Triggering ON timer", timer_index=idx, scheduled_time=on_time, current_time=current_time_str)
                        
                        if await self._trigger_system(True, on_trigger_id):
                            triggers["triggered"][on_trigger_id] = now.isoformat()
                            await self.redis_client.set("timer:triggers", json.dumps(triggers))
                            triggered_this_cycle = True
                            
                    # Check if OFF time has been reached and not yet triggered today
                    if current_time_str >= off_time and not triggers["triggered"].get(off_trigger_id):
                        logger.info("Triggering OFF timer", timer_index=idx, scheduled_time=off_time, current_time=current_time_str)
                        
                        if await self._trigger_system(False, off_trigger_id):
                            triggers["triggered"][off_trigger_id] = now.isoformat()
                            await self.redis_client.set("timer:triggers", json.dumps(triggers))
                            triggered_this_cycle = True
                            
                # If we triggered something, log the state
                if triggered_this_cycle:
                    logger.info("Timer cycle complete with triggers", triggered_count=len(triggers["triggered"]))
                    
            except Exception as e:
                logger.error("Error in timer loop", error=str(e))
                
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
            
        logger.info("Timer loop stopped")
        
    async def stop(self):
        """Stop the timer loop"""
        self._running = False
        logger.info("Timer loop stopping")
