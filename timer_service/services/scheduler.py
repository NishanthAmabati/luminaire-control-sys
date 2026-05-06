import structlog
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logging.getLogger('apscheduler').setLevel(logging.DEBUG)
log = structlog.get_logger()

class Scheduler:

    def __init__(self, timezone, state_client):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.state_client = state_client
        self._started = False

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
        """
        start_time / end_time format: 'HH:MM'
        """
        self.clear_jobs()

        if not start_time or not end_time:
            log.warning("timer_configuration_skipped", reason="missing_times", start_time=start_time, end_time=end_time)
            return

        try:
            start_hour, start_min = map(int, start_time.split(":"))
            end_hour, end_min = map(int, end_time.split(":"))
        except ValueError as e:
            log.error("timer_configuration_failed", reason="invalid_format", error=str(e), exc_info=True)
            return

        try:
            self.scheduler.add_job(
                self._turn_on,
                CronTrigger(hour=start_hour, minute=start_min),
                id="timer_on",
                replace_existing=True,
                misfire_grace_time=60
            )

            self.scheduler.add_job(
                self._turn_off,
                CronTrigger(hour=end_hour, minute=end_min),
                id="timer_off",
                replace_existing=True,
                misfire_grace_time=60
            )
            log.info("timer_scheduled_successfully", start=start_time, end=end_time)
        except Exception as e:
            log.error("timer_job_addition_failed", error=str(e), exc_info=True)

    async def _turn_on(self):
        log.info("timer_trigger_executed", action="system_on")
        try:
            await self.state_client.send_toggle_system(True)
        except Exception as e:
            log.error("timer_trigger_failed", action="system_on", error=str(e), exc_info=True)

    async def _turn_off(self):
        log.info("timer_trigger_executed", action="system_off")
        try:
            await self.state_client.send_toggle_system(False)            
        except Exception as e:
            log.error("timer_trigger_failed", action="system_off", error=str(e), exc_info=True)