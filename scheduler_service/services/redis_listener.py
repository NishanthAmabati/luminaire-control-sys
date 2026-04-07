import asyncio
import json
import time
import logging
import traceback

from utilities.tracing import extract_trace_id, create_trace_logger, generate_trace_id
from utilities.trace_context import set_trace_id, clear_trace_id

log = logging.getLogger(__name__)


class RedisListener:
    def __init__(self, redis, sub_chan, scheduler):
        self.redis = redis
        self.sub_chan = sub_chan
        self.scheduler = scheduler
        log.info(f"redis listener initialized on channel {sub_chan}")

    async def listen(self):
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(self.sub_chan)
            log.info(f"subscribed to channel {self.sub_chan}")

            async for message in pubsub.listen():
                try:
                    if message["type"] != "message":
                        log.debug(f"skipping non-message type {message['type']}")
                        continue

                    raw_data = message.get("data")
                    if not raw_data:
                        log.warning("received empty message data")
                        continue

                    data = json.loads(raw_data)
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
                    log.error("failed to decode message data as json")
                except Exception as e:
                    trace_id = None
                    try:
                        from utilities.trace_context import get_trace_id

                        trace_id = get_trace_id()
                    except:
                        pass
                    trace_log = create_trace_logger(log, trace_id)
                    trace_log.error("error processing message loop %s", str(e).lower())
                    trace_log.debug(traceback.format_exc().lower())
                finally:
                    clear_trace_id()

        except Exception as e:
            log.error(f"critical failure in redis listen task %s", str(e).lower())
            log.debug(traceback.format_exc().lower())

    async def handle_event(self, event, payload, trace_id=None):
        trace_log = create_trace_logger(log, trace_id)

        try:
            if not event:
                trace_log.warning("received event with no name")
                return

            if event == "system:power":
                trace_log.info("event triggered %s", event)
                await self.scheduler.handle_power(trace_id)

            elif event == "system:mode":
                trace_log.info("event triggered %s", event)
                await self.scheduler.handle_mode(trace_id)

            elif event == "scheduler:scene_loaded":
                trace_log.info("event triggered %s", event)
                scene_name = payload.get("scene")
                if scene_name:
                    await self.scheduler.load_scene(scene_name, trace_id)
                else:
                    trace_log.warning(
                        "scene_loaded event missing scene name in payload"
                    )

            elif event == "scheduler:scene_activated":
                trace_log.info("event triggered %s", event)
                scene_name = payload.get("scene")
                if scene_name:
                    await self.scheduler.activate_scene(scene_name, trace_id)
                else:
                    trace_log.warning(
                        "scene_activated event missing scene name in payload"
                    )

            elif event == "scheduler:scene_stopped":
                trace_log.info("event triggered %s", event)
                await self.scheduler.deactivate_scene(trace_id)

            elif event == "manual:update":
                trace_log.info("event triggered %s", event)
                medium = payload.get("medium", "sliders")
                await self.scheduler.apply_manual(
                    medium,
                    cct=payload.get("cct"),
                    lux=payload.get("lux"),
                    cw=payload.get("cw"),
                    ww=payload.get("ww"),
                    trace_id=trace_id,
                )

            elif event == "scheduler:available_scenes":
                trace_log.info("event triggered %s", event)
                await self.scheduler.publish_available_scenes(trace_id)

            else:
                trace_log.warning("received unknown event type %s", event)

            trace_log.info("successfully handled event %s", event)

        except Exception as e:
            trace_log.error(
                "failed to handle event %s because %s", event, str(e).lower()
            )
            trace_log.debug(traceback.format_exc().lower())
