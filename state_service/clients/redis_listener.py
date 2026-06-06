import asyncio
import json
import structlog

log = structlog.get_logger()

class RedisListener:
    def __init__(self, redis, scheduler_sub_chan, metrics_sub_chan, state_service):
        self.redis = redis
        self.scheduler_sub_chan = scheduler_sub_chan # scheduler:events
        self.metrics_sub_chan = metrics_sub_chan     # metrics:events
        self.state = state_service

    async def listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.scheduler_sub_chan, self.metrics_sub_chan)
        
        log.info("redis_listener_started", channels=[self.scheduler_sub_chan, self.metrics_sub_chan])

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
                    log.error("redis_message_parse_failed", error=str(e), raw_data=message["data"])
                except Exception as e:
                    log.error("redis_event_routing_failed", event=data.get("event"), error=str(e), exc_info=True)
                    
        except asyncio.CancelledError:
            log.info("redis_listener_task_cancelled")
            raise
        finally:
            await pubsub.unsubscribe(self.scheduler_sub_chan, self.metrics_sub_chan)
            await pubsub.close()
            log.info("redis_listener_stopped")

    async def handle_event(self, event, payload):
        try:
            if event == "scheduler:runtime":
                await self.state.update_auto_runtime(
                    payload.get("cct", 0.0),
                    payload.get("lux", 0.0),
                    payload.get("progress", 0.0)
                )

            elif event == "metrics:events":
                await self.state.update_metrics(
                    payload.get("cpu"),
                    payload.get("memory"),
                    payload.get("temperature")
                )
            else:
                log.debug("unhandled_redis_event", redis_event=event)
                
        except Exception as e:
            log.error("event_handling_failed", redis_event=event, error=str(e), exc_info=True)