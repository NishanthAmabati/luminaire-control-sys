import asyncio
import json
import time
import logging

log = logging.getLogger(__name__)

class RedisListener:
    def __init__(self, redis, scheduler_sub_chan, metrics_sub_chan, state_service):
        self.redis = redis
        self.scheduler_sub_chan = scheduler_sub_chan # scheduler:events
        self.metrics_sub_chan = metrics_sub_chan #metrics:events
        self.state = state_service

    async def listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.scheduler_sub_chan, self.metrics_sub_chan)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = json.loads(message["data"])
            event = data.get("event")
            payload = data.get("payload", {})

            await self.handle_event(event, payload)

    async def handle_event(self, event, payload):
        try:
            if event == "scheduler:runtime":
                await self.state.update_auto_runtime(
                    payload["cct"],
                    payload["lux"],
                    payload["progress"]
                )

            elif event == "metrics:events":
                await self.state.update_metrics(
                    payload.get("cpu"),
                    payload.get("memory"),
                    payload.get("temperature")
                )
        except Exception as e:
            log.exception(f"failed to handle event {event}, err: {e}")
