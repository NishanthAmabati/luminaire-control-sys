import asyncio
import json
import structlog

log = structlog.get_logger()

class RedisListener:
    def __init__(self, redis, sub_chan, timer):
        self.redis = redis
        self.sub_chan = sub_chan
        self.timer = timer

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
                    log.error("redis_event_routing_failed", event=data.get("event"), error=str(e), exc_info=True)
                    
        except asyncio.CancelledError:
            log.info("redis_listener_task_cancelled")
            raise
        finally:
            await pubsub.unsubscribe(self.sub_chan)
            await pubsub.close()
            log.info("redis_listener_stopped")

    async def handle_event(self, event, payload):
        event_log = log.bind(redis_event=event)
        event_log.info("event_processing_started")

        try:
            if event == "timer:toggled":
                await self.timer.toggle_timer()

            elif event == "timer:configured":
                await self.timer.configure_timer()

            elif event == "timer:cleared":
                await self.timer.clear_timer()
            else:
                event_log.warning("unhandled_redis_event")
                return

            event_log.info("event_processing_complete")
        except Exception as e:
             event_log.error("event_handling_failed", error=str(e), exc_info=True)

    async def shutdown(self):
        log.info("redis_listener_shutdown_initiated")
        try:
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info("redis_connection_closed")
        except Exception as e:
            log.error("redis_close_failed", error=str(e), exc_info=True)