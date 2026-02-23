import asyncio
import json
import time
import logging

log = logging.getLogger(__name__)

class RedisListener:
    def __init__(self, redis, sub_chan, timer):
        self.redis = redis
        self.sub_chan = sub_chan
        self.timer = timer

    async def listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.sub_chan)

        async for message in pubsub.listen():
            if message ["type"] != "message":
                continue

            data = json.loads(message["data"])
            event = data.get("event")
            payload = data.get("payload", {})

            await self.handle_event(event, payload)

    async def handle_event(self, event, payload):
        if event == "timer:toggled":
            log.info(f"event triggered: {event}")
            await self.timer.toggle_timer()

        elif event == "timer:configured":
            log.info(f"event triggered: {event}")
            await self.timer.configure_timer()

        elif event == "timer:cleared":
            log.info(f"event triggered: {event}")
            await self.timer.clear_timer()
            
        log.info(f"handled event {event}")

    async def shutdown(self):
        try:
            log.info(f"stopping redis...")
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info("stopped redis")
        except Exception as e:
            log.exception(f"failed to close redis, err: {e}")