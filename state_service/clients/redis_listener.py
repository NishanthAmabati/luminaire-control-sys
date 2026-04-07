import asyncio
import json
import logging
import time

from utils.tracing import extract_trace_id, create_trace_logger, generate_trace_id
from utils.trace_context import set_trace_id, clear_trace_id

log = logging.getLogger("services.redis_listener")


class RedisListener:
    def __init__(self, redis, scheduler_sub_chan, metrics_sub_chan, state_service):
        self.redis = redis
        self.scheduler_sub_chan = scheduler_sub_chan
        self.metrics_sub_chan = metrics_sub_chan
        self.state = state_service

    async def listen(self):
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(self.scheduler_sub_chan, self.metrics_sub_chan)
            log.info(
                f"redis listener subscribed to {self.scheduler_sub_chan} and {self.metrics_sub_chan}"
            )

            async for message in pubsub.listen():
                if message["type"] != "message":
                    log.debug(f"received redis control message type {message['type']}")
                    continue

                try:
                    data = json.loads(message["data"])
                    event = data.get("event")
                    payload = data.get("payload", {})

                    trace_id = extract_trace_id(data)
                    if not trace_id:
                        trace_id = generate_trace_id()
                        log.warning(
                            "received message without trace_id, generated new: %s",
                            trace_id,
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
            log.exception("critical failure in redis listener loop")

    async def handle_event(self, event, payload, trace_id=None):
        trace_log = create_trace_logger(log, trace_id)

        try:
            if event == "scheduler:runtime":
                await self.state.update_auto_runtime(
                    payload.get("cct"),
                    payload.get("lux"),
                    payload.get("progress"),
                    trace_id=trace_id,
                )

            elif event == "metrics:events":
                await self.state.update_metrics(
                    payload.get("cpu"),
                    payload.get("memory"),
                    payload.get("temperature"),
                    trace_id=trace_id,
                )
            else:
                trace_log.debug("unhandled event type %s received", event)

        except Exception:
            trace_log.exception("failed to handle event %s", event)
