import asyncio
import json
import structlog
from redis.asyncio import Redis
from utilities.command_builder import CommandBuilder
from typing import Dict

log = structlog.get_logger()

class LuminaireService:
    def __init__(self, redisURL: str, channel: str):
        self.luminaires: Dict[str, dict] = {} # dict of luminaire ip -> dict of context
        self._tasks = set()
        self.redis = Redis.from_url(redisURL)
        self.channel = channel

    async def health(self):
        status = {
            "status": "healthy",
            "tcp": "up",
            "redis connectivity": "succeeded"
        }
        try:
            await self.redis.ping()
        except Exception as e:
            log.error("health_check_failed", error=str(e), exc_info=True)
            status["redis connectivity"] = "failed"
            status["status"] = "unhealthy"
        return status

    async def register(self, ip: str, writer: asyncio.StreamWriter):
        self.luminaires[ip] = {
            "writer": writer,
            "ip34": CommandBuilder.extract_ip34(ip),
            "log": log.bind(ip=ip)
        }
        l_log = self.luminaires[ip]["log"]
        l_log.info("luminaire_registered")
        
        try:
            payload = {
                "event": "connection",
                "ip": ip
            }
            await self.redis.publish(self.channel, json.dumps(payload))
            l_log.info("redis_publish_success", redis_event="connection")
        except Exception as e:
            l_log.error("redis_publish_failed", redis_event="connection", error=str(e), exc_info=True)

    async def unregister(self, ip: str):
        entry = self.luminaires.pop(ip, None)
        l_log = entry.get("log", log.bind(ip=ip)) if entry else log.bind(ip=ip)
        writer = entry.get("writer") if entry else None
        
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
                l_log.info("luminaire_disconnected")
            except Exception:
                l_log.error("writer_close_failed", exc_info=True)

        try:
            payload = {
                "event": "disconnection",
                "ip": ip
            }
            await self.redis.publish(self.channel, json.dumps(payload))
            # Changed 'event=' to 'redis_event='
            l_log.info("redis_publish_success", redis_event="disconnection")
        except Exception as e:
            # Changed 'event=' to 'redis_event='
            l_log.error("redis_publish_failed", redis_event="disconnection", error=str(e), exc_info=True)

    async def list_luminaires(self):
        return list(self.luminaires.keys())

    async def send_luminaire(self, ip: str, command: str):
        if not self.luminaires:
            log.warning("send_failed_no_luminaires_connected")
            return
            
        entry = self.luminaires.get(ip)
        if not entry:
            log.error("send_failed_luminaire_not_found", ip=ip)
            return

        l_log = entry["log"]
        writer = entry["writer"]
        
        try:
            writer.write(command.encode())
            await writer.drain()
            l_log.info("command_sent", command=command)
        except Exception:
            l_log.error("command_send_failed", exc_info=True)
            await self.unregister(ip)

    async def _drain_one(self, ip: str, writer: asyncio.StreamWriter):
        try:
            await writer.drain()
        except Exception:
            log.error("drain_failed", ip=ip, exc_info=True)
            await self.unregister(ip)
            raise

    async def send_luminaires(self, cw: float, ww: float):
        if not self.luminaires:
            log.warning("broadcast_skipped_no_luminaires_connected")
            return

        cw_ww = CommandBuilder.build_cw_ww(cw, ww)
        for ip, entry in self.luminaires.items():
            l_log = entry["log"]
            writer = entry["writer"]
            ip34 = entry["ip34"]
            try:
                command = CommandBuilder.build_command(ip34, cw_ww)
                writer.write(command.encode())
                task = asyncio.create_task(self._drain_one(ip, writer))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                l_log.debug("broadcast_queued", command=command)
            except Exception:
                l_log.error("broadcast_write_failed", exc_info=True)
                
        log.info("broadcast_completed", count=len(self.luminaires), payload=cw_ww)
    
    async def publish_ack(self, ip: str, cw: float, ww: float):
        l_log = self.luminaires.get(ip, {}).get("log", log.bind(ip=ip))
        try:
            payload = {
                "event": "ack",
                "ip": ip,
                "cw": cw,
                "ww": ww
            }
            await self.redis.publish(self.channel, json.dumps(payload))
            l_log.info("ack_published", cw=cw, ww=ww)
        except Exception as e:
            l_log.error("redis_publish_failed", redis_event="ack", error=str(e), exc_info=True)

    async def shutdown(self):
        log.info("service_shutdown_initiated")
        for task in list(self._tasks):
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        try:
            log.info("stopping_redis")
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info("redis_stopped")
        except Exception:
            log.error("redis_shutdown_failed", exc_info=True)
            
        items = list(self.luminaires.items())
        for ip, _ in items:
            await self.unregister(ip)
            
        self.luminaires.clear()
        log.info("service_shutdown_complete")