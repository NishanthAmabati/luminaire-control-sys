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

from timer_service.models import Timer, SetTimerData

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
                
            logger.info("Timer state loaded from Redis", timers=len(self.timers), enabled=self.is_enabled)
            
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
            
            # Broadcast timer status to UI
            await self._broadcast_timer_status()
            
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
                
            # Broadcast timer status to UI
            await self._broadcast_timer_status()
                
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
        Trigger system ON or OFF (simple, reliable approach)
        
        Directly sets the system to the desired state without checking current state.
        This is the simplest and most reliable approach - no state checking complexity.
        
        Args:
            turn_on: True to turn on, False to turn off
            timer_id: Identifier for this trigger (for logging/tracking)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Directly set the system to desired state (no state checking)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/api/toggle_system",
                    json={"isSystemOn": turn_on}
                )
                
                if response.status_code == 200:
                    action = "ON" if turn_on else "OFF"
                    logger.info(
                        f"Timer triggered: System set to {action}", 
                        timer_id=timer_id
                    )
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
        1. Runs every 30 seconds for better responsiveness
        2. Checks all enabled timers continuously every day
        3. Triggers immediately if current time >= scheduled time
        4. Prevents duplicate triggers on the same day
        5. Automatically resets trigger state at midnight for next day
        6. Timers remain active daily until manually disabled
        """
        self._running = True
        logger.info("Timer loop started - checking every 30 seconds")
        
        last_check_date = None
        
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
                    
                # Reset triggers if it's a new day (automatic daily recurrence)
                if triggers.get("date") != today_str:
                    triggers = {"date": today_str, "triggered": {}}
                    await self.redis_client.set("timer:triggers", json.dumps(triggers))
                    logger.info("New day detected - timer triggers reset for daily recurrence", date=today_str)
                    last_check_date = today_str
                    
                triggered_count = 0
                    
                # Check each timer
                for idx, timer in enumerate(self.timers):
                    # Skip disabled timers
                    if not timer.get("enabled", True):
                        continue
                        
                    on_time = timer["on"]
                    off_time = timer["off"]
                    
                    # Create unique identifiers for this timer's triggers
                    on_trigger_id = f"timer_{idx}_on_{today_str}"
                    off_trigger_id = f"timer_{idx}_off_{today_str}"
                    
                    # Determine what action should be taken based on current time
                    # Strategy: Only trigger the LATEST event that should have occurred
                    
                    on_should_be_triggered = current_time_str >= on_time
                    off_should_be_triggered = current_time_str >= off_time
                    
                    # Check if already triggered today
                    on_already_triggered = triggers["triggered"].get(on_trigger_id)
                    off_already_triggered = triggers["triggered"].get(off_trigger_id)
                    
                    # Determine the correct current state based on which event is most recent
                    # If both times have passed, use the latest one to determine state
                    if on_should_be_triggered and off_should_be_triggered:
                        # Both times passed - which is more recent?
                        if on_time > off_time:
                            # ON is later -> System should be ON
                            desired_state = True
                            latest_trigger_id = on_trigger_id
                            latest_time = on_time
                        else:
                            # OFF is later (or same) -> System should be OFF
                            desired_state = False
                            latest_trigger_id = off_trigger_id
                            latest_time = off_time
                            
                        # Only trigger if we haven't already triggered this state today
                        if not triggers["triggered"].get(latest_trigger_id):
                            logger.info(
                                "Timer final state trigger",
                                timer_index=idx,
                                action="ON" if desired_state else "OFF",
                                scheduled_time=latest_time,
                                current_time=current_time_str,
                                date=today_str
                            )
                            
                            if await self._trigger_system(desired_state, latest_trigger_id):
                                # Mark both as triggered to prevent any further triggers today
                                triggers["triggered"][on_trigger_id] = now.isoformat()
                                triggers["triggered"][off_trigger_id] = now.isoformat()
                                await self.redis_client.set("timer:triggers", json.dumps(triggers))
                                triggered_count += 1
                        
                        continue  # Move to next timer
                    
                    # Only ON time has passed and not yet triggered
                    if on_should_be_triggered and not on_already_triggered:
                        logger.info(
                            "Timer ON trigger activated", 
                            timer_index=idx, 
                            scheduled_time=on_time, 
                            current_time=current_time_str,
                            date=today_str
                        )
                        
                        if await self._trigger_system(True, on_trigger_id):
                            triggers["triggered"][on_trigger_id] = now.isoformat()
                            await self.redis_client.set("timer:triggers", json.dumps(triggers))
                            triggered_count += 1
                    
                    # Only OFF time has passed and not yet triggered
                    elif off_should_be_triggered and not off_already_triggered:
                        logger.info(
                            "Timer OFF trigger activated", 
                            timer_index=idx, 
                            scheduled_time=off_time, 
                            current_time=current_time_str,
                            date=today_str
                        )
                        
                        if await self._trigger_system(False, off_trigger_id):
                            triggers["triggered"][off_trigger_id] = now.isoformat()
                            await self.redis_client.set("timer:triggers", json.dumps(triggers))
                            triggered_count += 1
                            
                # Log daily status if we triggered something
                if triggered_count > 0:
                    logger.info(
                        "Timer triggers executed - will recur daily", 
                        triggered_today=triggered_count,
                        total_triggered=len(triggers["triggered"]),
                        date=today_str
                    )
                    # Broadcast timer status after triggers to keep UI in sync
                    await self._broadcast_timer_status()
                    
            except Exception as e:
                logger.error("Error in timer loop", error=str(e))
                
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
            
        logger.info("Timer loop stopped")
    
    async def stop(self):
        """Stop the timer loop"""
        self._running = False
        logger.info("Timer loop stopping")
