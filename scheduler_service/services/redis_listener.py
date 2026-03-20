import asyncio
import json
import time
import logging

log = logging.getLogger(__name__)

class RedisListener:
    def __init__(self, redis, sub_chan, scheduler):
        self.redis = redis
        self.sub_chan = sub_chan
        self.scheduler = scheduler

    async def listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.sub_chan)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = json.loads(message["data"])
            event = data.get("event")
            payload = data.get("payload", {})

            await self.handle_event(event, payload)

    async def handle_event(self, event, payload):
        if event == "system:power":
            log.info(f"event triggered: {event}")
            await self.scheduler.handle_power()

        elif event == "system:mode":
            log.info(f"event triggered: {event}")
            await self.scheduler.handle_mode()

        elif event == "scheduler:scene_loaded":
            log.info(f"event triggered: {event}")
            await self.scheduler.load_scene(payload["scene"])

        elif event == "scheduler:scene_activated":
            log.info(f"event triggered: {event}")
            await self.scheduler.activate_scene(payload["scene"])

        elif event == "scheduler:scene_stopped":
            log.info(f"event triggered: {event}")
            await self.scheduler.deactivate_scene()

        elif event == "manual:update":
            log.info(f"event triggered: {event}")
            medium = payload.get("medium", "sliders")
            await self.scheduler.apply_manual(
                medium,
                cct=payload.get("cct"),
                lux=payload.get("lux"),
                cw=payload.get("cw"),
                ww=payload.get("ww"),
            )

        elif event == "scheduler:available_scenes":
            log.info(f"event triggered: {event}")
            await self.scheduler.publish_available_scenes()

        log.info(f"handled event {event}")
