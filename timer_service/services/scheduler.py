import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

class Scheduler:

    def __init__(self, timezone, state_client):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.state_client = state_client
        self._started = False

    def start(self):
        if not self._started:
            self.scheduler.start()
            self._started = True

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            log.info("APS Scheduler stopped")

    def clear_jobs(self):
        self.scheduler.remove_all_jobs()
        log.info("all timer jobs cleared")

    def configure(self, start_time: str, end_time: str):
        """
        start_time / end_time format: 'HH:MM'
        """

        self.clear_jobs()

        if not start_time or not end_time:
            log.warning("cannot configure timer: missing start/end")
            return

        start_hour, start_min = map(int, start_time.split(":"))
        end_hour, end_min = map(int, end_time.split(":"))

        self.scheduler.add_job(
            self._turn_on,
            CronTrigger(hour=start_hour, minute=start_min),
            id="timer_on",
            replace_existing=True
        )

        self.scheduler.add_job(
            self._turn_off,
            CronTrigger(hour=end_hour, minute=end_min),
            id="timer_off",
            replace_existing=True
        )
        log.info(f"timer scheduled, start: {start_time}, stop: {end_time}")

    async def _turn_on(self):
        log.info("timer triggered, SYSTEM ON")
        await self.state_client.send_toggle_system(True)

    async def _turn_off(self):
        log.info("timer triggered, SYSTEM OFF")
        await self.state_client.send_toggle_system(False)
