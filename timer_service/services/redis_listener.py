import asyncio
import json
import logging

from utilities.tracing import extract_trace_id, create_trace_logger, generate_trace_id
from utilities.trace_context import set_trace_id, clear_trace_id

log = logging.getLogger("services.timer_listener")


class RedisListener:
    def __init__(self, redis, sub_chan, timer):
        self.redis = redis
        self.sub_chan = sub_chan
        self.timer = timer

    async def listen(self):
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(self.sub_chan)
            log.info(f"timer listener subscribed to {self.sub_chan}")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    event = data.get("event")
                    payload = data.get("payload", {})

                    trace_id = extract_trace_id(data)
                    if not trace_id:
                        trace_id = generate_trace_id()
                        log.warning(
                            "received message without trace_id, generated: %s", trace_id
                        )

                    set_trace_id(trace_id)
                    trace_log = create_trace_logger(log, trace_id)

                    trace_log.debug("received event %s from redis", event)
                    await self.handle_event(event, payload, trace_id)

                except json.JSONDecodeError:
                    log.error("failed to decode json from redis message")
                except Exception:
                    log.exception("error processing redis message data")
                finally:
                    clear_trace_id()

        except Exception:
            log.exception("critical failure in timer listener loop")

    async def handle_event(self, event, payload, trace_id=None):
        trace_log = create_trace_logger(log, trace_id)
        try:
            if event == "timer:toggled":
                enabled = payload.get("enabled", False)
                trace_log.info("timer toggle event received: %s", enabled)
                await self.timer.toggle_timer(enabled, trace_id=trace_id)

            elif event == "timer:configured":
                start = payload.get("start")
                end = payload.get("end")
                trace_log.info(
                    "timer configuration event received: %s to %s", start, end
                )
                await self.timer.configure_timer(start, end, trace_id=trace_id)

            elif event == "timer:cleared":
                trace_log.info("timer clear event received")
                await self.timer.clear_timer(trace_id=trace_id)

            else:
                trace_log.debug("ignored non-timer event %s", event)
                return

            trace_log.debug("successfully handled event %s", event)

        except Exception:
            trace_log.exception("failed to handle event %s", event)

    async def shutdown(self):
        try:
            log.info("shutting down timer listener redis connection")
            await self.redis.close()
            log.info("timer listener stopped")
        except Exception:
            log.exception("failed to close redis during listener shutdown")
