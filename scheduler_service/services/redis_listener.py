import asyncio
import json
import structlog

log = structlog.get_logger()

class RedisListener:
    def __init__(self, redis, sub_chan, scheduler):
        self.redis = redis
        self.sub_chan = sub_chan
        self.scheduler = scheduler

    async def listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.sub_chan)
        
        log.info("redis_listener_started", channel=self.sub_chan)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    event = data.get("event")
                    payload = data.get("payload", {})
                    
                    await self.handle_event(event, payload)
                except json.JSONDecodeError as e:
                    log.error("redis_message_parse_failed", channel=self.sub_chan, error=str(e), raw_data=message["data"])
                except Exception as e:
                    log.error("redis_event_handling_crashed", event=data.get("event"), error=str(e), exc_info=True)
                    
        except asyncio.CancelledError:
            log.info("redis_listener_task_cancelled")
            raise
        finally:
            await pubsub.unsubscribe(self.sub_chan)
            await pubsub.close()
            log.info("redis_listener_stopped")

    async def handle_event(self, event, payload):
        event_log = log.bind(redis_event=event)
        event_log.info("event_processing_started", payload=payload)

        if event == "system:power":
            await self.scheduler.handle_power()

        elif event == "system:mode":
            await self.scheduler.handle_mode()

        elif event == "scheduler:scene_loaded":
            await self.scheduler.load_scene(payload.get("scene"))

        elif event == "scheduler:scene_activated":
            await self.scheduler.activate_scene(payload.get("scene"))

        elif event == "scheduler:scene_stopped":
            await self.scheduler.deactivate_scene()

        elif event == "manual:update":
            medium = payload.get("medium", "sliders")
            await self.scheduler.apply_manual(
                medium,
                cct=payload.get("cct"),
                lux=payload.get("lux"),
                cw=payload.get("cw"),
                ww=payload.get("ww"),
            )

        elif event == "scheduler:available_scenes":
            await self.scheduler.publish_available_scenes()
            
        else:
            event_log.warning("unhandled_redis_event")
            return

        event_log.info("event_processing_complete")