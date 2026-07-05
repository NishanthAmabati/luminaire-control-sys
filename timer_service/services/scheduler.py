import structlog
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED, 
    EVENT_JOB_ERROR, 
    EVENT_JOB_MISSED, 
    JobExecutionEvent
)

logging.getLogger('apscheduler').setLevel(logging.WARNING)
log = structlog.get_logger()

class Scheduler:

    def __init__(self, timezone, state_client):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.state_client = state_client
        self._started = False
        
        # Attach the event listener to catch Executions, Errors, and Misses
        self.scheduler.add_listener(
            self._on_job_event, 
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
        )

    def _on_job_event(self, event: JobExecutionEvent):
        """Monitors all job lifecycle events for delays, errors, and misfires."""
        
        if event.code == EVENT_JOB_EXECUTED:
            if event.scheduled_run_time:
                now = datetime.now(event.scheduled_run_time.tzinfo)
                delay_seconds = (now - event.scheduled_run_time).total_seconds()
                
                # If delayed by more than 5 seconds, log a warning
                if delay_seconds > 5.0:
                    log.warning(
                        "timer_job_delayed", 
                        job_id=event.job_id, 
                        delay_seconds=delay_seconds, 
                        scheduled_for=str(event.scheduled_run_time),
                        executed_at=str(now)
                    )
                    
        elif event.code == EVENT_JOB_MISSED:
            log.error(
                "timer_job_missed", 
                job_id=event.job_id, 
                scheduled_for=str(event.scheduled_run_time)
            )
            
        elif event.code == EVENT_JOB_ERROR:
            log.error(
                "timer_job_crashed", 
                job_id=event.job_id, 
                error=str(event.exception)
            )

    def start(self):
        if not self._started:
            self.scheduler.start()
            self._started = True
            log.info("apscheduler_started")

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            log.info("apscheduler_stopped")

    def clear_jobs(self):
        self.scheduler.remove_all_jobs()
        log.info("timer_jobs_cleared")

    def configure(self, start_time: str, end_time: str):
        self.clear_jobs()

        if not start_time or not end_time:
            log.warning("timer_configuration_skipped", reason="missing_times")
            return

        try:
            self.start_t = datetime.strptime(start_time, "%H:%M").time()
            self.end_t = datetime.strptime(end_time, "%H:%M").time()
            start_hour, start_min = self.start_t.hour, self.start_t.minute
            end_hour, end_min = self.end_t.hour, self.end_t.minute
        except ValueError as e:
            log.error("timer_configuration_failed", reason="invalid_format", error=str(e), exc_info=True)
            return

        try:
            # Set misfire_grace_time to None to force execution no matter the delay
            self.scheduler.add_job(
                self._turn_on,
                CronTrigger(hour=start_hour, minute=start_min),
                id="timer_on",
                replace_existing=True,
                misfire_grace_time=None 
            )

            self.scheduler.add_job(
                self._turn_off,
                CronTrigger(hour=end_hour, minute=end_min),
                id="timer_off",
                replace_existing=True,
                misfire_grace_time=None
            )
            log.info("timer_scheduled_successfully", start=start_time, end=end_time)
        except Exception as e:
            log.error("timer_job_addition_failed", error=str(e), exc_info=True)

    def _is_active_window(self) -> bool:
            now = datetime.now(self.scheduler.timezone).time()
            if self.start_t <= self.end_t:
                return self.start_t <= now < self.end_t
            else:
                return now >= self.start_t or now < self.end_t

    async def _turn_on(self):
        now = datetime.now(self.scheduler.timezone).time()
        if not self._is_active_window():
            log.info(
                "timer_trigger_aborted", 
                action="system_on", 
                reason="outside_active_window",
                current_time=str(now),
                configured_window=f"{self.start_t} to {self.end_t}"
            )
            return
        log.info("timer_trigger_executing", action="system_on")
        try:
            await self.state_client.send_toggle_system(True)
        except Exception as e:
            log.error("timer_trigger_failed", action="system_on", error=str(e), exc_info=True)

    async def _turn_off(self):
        now = datetime.now(self.scheduler.timezone).time()
        if self._is_active_window():
            log.info(
                "timer_trigger_aborted", 
                action="system_off", 
                reason="inside_active_window",
                current_time=str(now),
                configured_window=f"{self.start_t} to {self.end_t}"
            )
            return
        log.info("timer_trigger_executing", action="system_off")
        try:
            await self.state_client.send_toggle_system(False)            
        except Exception as e:
            log.error("timer_trigger_failed", action="system_off", error=str(e), exc_info=True)