import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# using a specific name for easier filtering in grafana/loki
log = logging.getLogger("services.scheduler")

class Scheduler:
    def __init__(self, timezone, state_client):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.state_client = state_client
        self._started = False
        log.debug(f"scheduler initialized for timezone {timezone}")

    def start(self):
        if not self._started:
            try:
                self.scheduler.start()
                self._started = True
                log.info("aps scheduler started")
            except Exception:
                log.exception("failed to start aps scheduler")

    def shutdown(self):
        if self._started:
            try:
                self.scheduler.shutdown(wait=False)
                self._started = False
                log.info("aps scheduler stopped")
            except Exception:
                log.exception("error during scheduler shutdown")

    def clear_jobs(self):
        try:
            job_count = len(self.scheduler.get_jobs())
            self.scheduler.remove_all_jobs()
            log.info(f"all timer jobs cleared count {job_count}")
        except Exception:
            log.exception("failed to clear scheduler jobs")

    def configure(self, start_time: str, end_time: str):
        """
        start_time / end_time format: 'hh:mm'
        """
        try:
            self.clear_jobs()

            if not start_time or not end_time:
                log.warning("cannot configure timer due to missing start or end time")
                return

            # parsing assuming 'HH:MM' format
            start_hour, start_min = map(int, start_time.split(":"))
            end_hour, end_min = map(int, end_time.split(":"))

            self.scheduler.add_job(
                self._handle_timer_on,
                CronTrigger(hour=start_hour, minute=start_min),
                id="timer_on",
                replace_existing=True
            )

            self.scheduler.add_job(
                self._handle_timer_off,
                CronTrigger(hour=end_hour, minute=end_min),
                id="timer_off",
                replace_existing=True
            )
            
            log.info(f"timer scheduled with start {start_time} and stop {end_time}")
            
        except ValueError:
            log.error(f"invalid time format received start {start_time} end {end_time}")
        except Exception:
            log.exception("unexpected error configuring scheduler jobs")

    async def _handle_timer_on(self):
        log.info("timer event triggered - system power on")
        try:
            await self.state_client.send_toggle_system(True)
        except Exception:
            log.exception("failed to send power on command to state client")

    async def _handle_timer_off(self):
        log.info("timer event triggered - system power off")
        try:
            await self.state_client.send_toggle_system(False)
        except Exception:
            log.exception("failed to send power off command to state client")