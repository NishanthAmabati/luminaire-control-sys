import asyncio
import json
import logging
import httpx
import structlog
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Optional

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from timer_service.models import SetTimerData

logger = structlog.get_logger(service="timer-service")

# Constants
MAX_API_RETRIES = 3
API_TIMEOUT = 10.0
IST = ZoneInfo("Asia/Kolkata")
TRIGGERS_TTL_SECONDS = 86400 * 3  # 3 days - clean up old trigger data automatically


class TimerOperations:
    """Production-grade timer operations with APScheduler and single timer support"""
    
    def __init__(self, redis_client: aioredis.Redis, api_url: str):
        self.redis_client = redis_client
        self.api_url = api_url
        
        # Single timer state
        self.on_time: Optional[str] = None   # "HH:MM"
        self.off_time: Optional[str] = None  # "HH:MM"
        self.is_enabled: bool = False
        
        # APScheduler
        self.scheduler = AsyncIOScheduler(timezone=IST)
        
        # Job IDs
        self.on_job_id = "timer_on"
        self.off_job_id = "timer_off"
        
        # Metrics
        self.metrics = {
            "triggers_total": 0,
            "triggers_failed": 0,
            "last_trigger_time": None,
            "last_check_time": None  # Not needed anymore but kept for compatibility
        }
    
    async def _broadcast_timer_status(self):
        """Broadcast current timer status via Redis pub/sub to update UI"""
        try:
            # When disabled or no timer set, broadcast empty strings for on/off
            broadcast_on = self.on_time if self.is_enabled and self.on_time else ""
            broadcast_off = self.off_time if self.is_enabled and self.off_time else ""
            
            timer_status = {
                "system_timers": [{"on": broadcast_on, "off": broadcast_off}],
                "isTimerEnabled": self.is_enabled,
            }
            await self.redis_client.publish("system_update", json.dumps(timer_status))
            logger.debug("Broadcasted timer status", enabled=self.is_enabled, on=broadcast_on, off=broadcast_off)
        except Exception as e:
            logger.error("Failed to broadcast timer status", error=str(e))
    
    async def _safe_disable(self, reason: str):
        """Centralised disable logic on error or manual disable"""
        logger.warning(f"Disabling timer system: {reason}")
        self.is_enabled = False
        self.scheduler.remove_all_jobs()
        
        # Clear all Redis state
        await self.redis_client.delete("timer:timers", "timer:enabled", "timer:triggers")
        
        # Broadcast disabled state (empty times)
        await self._broadcast_timer_status()
    
    async def _trigger_system(self, turn_on: bool, trigger_id: str):
        """Trigger system ON/OFF with retries"""
        action = "ON" if turn_on else "OFF"
        endpoint = f"{self.api_url}/api/toggle_system"
        payload = {"isSystemOn": turn_on}
        
        for attempt in range(MAX_API_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                    response = await client.post(endpoint, json=payload)
                    if response.status_code == 200:
                        logger.info(
                            f"Timer {action} triggered successfully",
                            trigger_id=trigger_id,
                            attempt=attempt + 1
                        )
                        self.metrics["triggers_total"] += 1
                        self.metrics["last_trigger_time"] = datetime.now(IST).isoformat()
                        return True
                    else:
                        logger.warning(
                            "Timer trigger failed",
                            trigger_id=trigger_id,
                            attempt=attempt + 1,
                            status=response.status_code,
                            response=response.text
                        )
            except Exception as e:
                logger.error(
                    f"Timer trigger error, attempt {attempt + 1}/{MAX_API_RETRIES}",
                    trigger_id=trigger_id,
                    action=action,
                    error=str(e),
                    exc_info=True
                )
            
            # Backoff except last attempt
            if attempt < MAX_API_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
        
        # All retries failed -> critical error
        self.metrics["triggers_failed"] += 1
        await self._safe_disable(f"Failed to trigger {action} after {MAX_API_RETRIES} attempts")
        return False
    
    def _schedule_jobs(self):
        """(Re)schedule ON and OFF jobs based on current timer config"""
        # Remove existing jobs
        for job_id in [self.on_job_id, self.off_job_id]:
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass
        
        if not self.is_enabled or not self.on_time or not self.off_time:
            return
        
        try:
            hour_on, minute_on = map(int, self.on_time.split(":"))
            hour_off, minute_off = map(int, self.off_time.split(":"))
            
            # Schedule ON
            self.scheduler.add_job(
                self._trigger_system,
                CronTrigger(hour=hour_on, minute=minute_on, timezone=IST),
                id=self.on_job_id,
                args=(True, self.on_job_id),
                misfire_grace_time=60,  # Allow immediate trigger if missed
                coalesce=True
            )
            
            # Schedule OFF
            self.scheduler.add_job(
                self._trigger_system,
                CronTrigger(hour=hour_off, minute=minute_off, timezone=IST),
                id=self.off_job_id,
                args=(False, self.off_job_id),
                misfire_grace_time=60,
                coalesce=True
            )
            
            logger.info("Timer jobs scheduled", on=self.on_time, off=self.off_time)
        except ValueError as e:
            logger.error("Invalid time format when scheduling", error=str(e))
            asyncio.create_task(self._safe_disable("Invalid time format"))
    
    async def initialize(self):
        """Load timer state from Redis on startup"""
        try:
            timers_data = await self.redis_client.get("timer:timers")
            if timers_data:
                timers = json.loads(timers_data)
                # Expect single timer
                if timers:
                    timer = timers[0]
                    self.on_time = timer.get("on")
                    self.off_time = timer.get("off")
            
            enabled_data = await self.redis_client.get("timer:enabled")
            if enabled_data:
                self.is_enabled = json.loads(enabled_data)
            
            logger.info("Timer state loaded from Redis", on=self.on_time, off=self.off_time, enabled=self.is_enabled)
            
            # Start scheduler and schedule jobs
            self.scheduler.start()
            self._schedule_jobs()
            
            # Broadcast initial status
            await self._broadcast_timer_status()
        except Exception as e:
            logger.error("Failed to initialize timer service", error=str(e))
            await self._safe_disable("Initialization failure")
    
    async def set_timers(self, data: SetTimerData) -> Dict:
        """Set the single system timer"""
        try:
            if len(data.timers) != 1:
                return {"status": "error", "error": "Only one timer supported"}
            
            timer = data.timers[0]
            on_time = timer.on.strip()
            off_time = timer.off.strip()
            
            # Basic validation
            if not on_time or not off_time:
                return {"status": "error", "error": "ON and OFF times required"}
            
            try:
                datetime.strptime(on_time, "%H:%M")
                datetime.strptime(off_time, "%H:%M")
            except ValueError:
                return {"status": "error", "error": "Invalid time format. Use HH:MM"}
            
            if on_time == off_time:
                return {"status": "error", "error": "ON and OFF times cannot be the same"}
            
            # Update state
            self.on_time = on_time
            self.off_time = off_time
            self.is_enabled = True  # Setting timer enables the system
            
            # Persist
            await self.redis_client.set("timer:timers", json.dumps([{"on": on_time, "off": off_time}]))
            await self.redis_client.set("timer:enabled", json.dumps(True))
            
            # Clean old trigger tracking key with TTL
            await self.redis_client.delete("timer:triggers")
            await self.redis_client.set("timer:triggers", json.dumps({"date": "", "triggered": {}}), ex=TRIGGERS_TTL_SECONDS)
            
            # Reschedule jobs
            self._schedule_jobs()
            
            # Broadcast
            await self._broadcast_timer_status()
            
            logger.info("Timer set successfully", on=on_time, off=off_time)
            return {
                "status": "success",
                "message": "Timer set",
                "isTimerEnabled": True,
                "timers": [{"on": on_time, "off": off_time}]
            }
        except Exception as e:
            logger.error("Failed to set timer", error=str(e), exc_info=True)
            await self._safe_disable("Set timer failure")
            return {"status": "error", "error": str(e)}
    
    async def get_timers(self) -> Dict:
        """Get current timer configuration"""
        broadcast_on = self.on_time if self.is_enabled else ""
        broadcast_off = self.off_time if self.is_enabled else ""
        return {
            "timers": [{"on": broadcast_on, "off": broadcast_off}],
            "isTimerEnabled": self.is_enabled
        }
    
    async def toggle_timers(self, enable: bool) -> Dict:
        """Enable or disable the timer system"""
        try:
            if enable and (not self.on_time or not self.off_time):
                return {"status": "error", "error": "No timer configured to enable"}
            
            self.is_enabled = enable
            
            await self.redis_client.set("timer:enabled", json.dumps(enable))
            
            if enable:
                self._schedule_jobs()
                logger.info("Timer system enabled")
            else:
                self.scheduler.remove_all_jobs()
                await self.redis_client.delete("timer:triggers")
                logger.info("Timer system disabled")
            
            await self._broadcast_timer_status()
            
            return {
                "status": "success",
                "message": f"Timer system {'enabled' if enable else 'disabled'}",
                "isTimerEnabled": enable,
                "timers": [{"on": self.on_time or "", "off": self.off_time or ""}]
            }
        except Exception as e:
            logger.error("Failed to toggle timer", error=str(e))
            await self._safe_disable("Toggle failure")
            return {"status": "error", "error": str(e)}
    
    async def reset_timers(self) -> Dict:
        """Reset timer - clear config and disable"""
        try:
            self.on_time = None
            self.off_time = None
            self.is_enabled = False
            
            self.scheduler.remove_all_jobs()
            await self.redis_client.delete("timer:timers", "timer:enabled", "timer:triggers")
            
            await self._broadcast_timer_status()
            
            logger.info("Timers fully reset")
            return {"status": "success", "message": "Timers reset"}
        except Exception as e:
            logger.error("Failed to reset timers", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def stop(self):
        """Stop the scheduler gracefully"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("APScheduler stopped")
    
    async def health_check(self) -> Dict:
        """Health check including scheduler status"""
        return {
            "status": "healthy" if self.scheduler.running else "stopped",
            "running": self.scheduler.running,
            "enabled": self.is_enabled,
            "timer_configured": bool(self.on_time and self.off_time),
            "metrics": self.metrics
        }