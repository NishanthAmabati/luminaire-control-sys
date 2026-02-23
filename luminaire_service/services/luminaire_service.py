import asyncio
import logging
import json

from redis.asyncio import Redis
from utilities.command_builder import CommandBuilder
from typing import Dict

log = logging.getLogger(__name__)

class LuminaireService:
    def __init__(self, redisURL, channel):
        self.luminaires: Dict[str, dict] = {} # dict of lumianire ip -> writer
        self._tasks = set()  # track background broadcast tasks
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
        except Exception:
            status["redis connectivity"] = "failed"
            status["status"] = "unhealthy"
        return status

    async def register(self, ip: str, writer: asyncio.StreamWriter):
        self.luminaires[ip] = {
            "writer": writer,
            "ip34": CommandBuilder.extract_ip34(ip)
        }
        log.info(f"accepted connection from {ip}")
        try:
            payload = {
                "event": "connection",
                "ip": ip
            }
            await self.redis.publish(
                self.channel,
                json.dumps(payload)
            )
            log.info(f"connection event for {ip}, published to redis")
        except Exception as e:
            log.exception(f"failed to publish event 'connection' for {ip} to redis. err: {e}")

    async def unregister(self, ip: str):
        entry = self.luminaires.pop(ip, None)
        writer = entry["writer"] if entry else None
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
                log.info(f"disconnected {ip}")
            except Exception as e:
                log.exception(f"failed to close writer for lumianire: {ip}")
        try:
            payload = {
                "event": "disconnection",
                "ip": ip
            }
            await self.redis.publish(
                self.channel,
                json.dumps(payload)
            )
            log.info(f"disconnection event for {ip}, published to redis")
        except Exception as e:
            log.exception(f"failed to publish event 'diconnection' for {ip} to redis. err: {e}")

    async def list_luminaires(self):
        return list(self.luminaires.keys())

    async def send_luminaire(self, ip: str, command: str):
        try:
            if not self.luminaires:
                log.warning("No luminaires connected")
                return
            entry = self.luminaires.get(ip)
            if not entry:
                raise RuntimeError(...)
            writer = entry["writer"]
            writer.write(command.encode())
            await writer.drain()
            log.info(f"sent to luminaiure {ip}: {command}")
        except Exception as e:
            log.exception(f"failed to write to luminaire {ip}: {e}")

    async def _drain_one(self, ip, writer):
        try:
            await writer.drain()
        except Exception:
            log.exception("Drain failed for luminaire %s", ip)
            await self.unregister(ip)
            raise

    async def send_luminaires(self, cw: float, ww: float):
        if not self.luminaires:
            log.warning("No luminaires connected, broadcast skipped")
            return
        cw_ww = CommandBuilder.build_cw_ww(cw, ww)
        for ip, entry in self.luminaires.items():
            writer = entry["writer"]
            ip34 = entry["ip34"]
            try:
                command = CommandBuilder.build_command(ip34, cw_ww)
                writer.write(command.encode())
                task = asyncio.create_task(self._drain_one(ip, writer))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                log.debug(f"broadcast to {ip}: {command}")
            except Exception:
                log.exception(f"failed to write to luminaire {ip}")
        log.info(f"broadcasted to {len(self.luminaires)} luminaires: {cw_ww}")
    
    async def publish_ack(self, ip: str, cw: float, ww: float):
        try:
            payload = {
                "event": "ack",
                "ip": ip,
                "cw": cw,
                "ww": ww
            }
            await self.redis.publish(
                self.channel,
                json.dumps(payload)
            )
            log.info(f"ACK published for {ip}, cw: {cw}, ww: {ww}")
        except Exception as e:
            log.exception(f"Failed to publish ACK for {ip} to redis: {e}")

    async def shutdown(self):
        log.info("stopping LuminaireService...")
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        try:
            log.info(f"stopping redis..")
            await self.redis.close()
            await self.redis.connection_pool.disconnect()
            log.info(f"stopped redis")
        except Exception:
            log.exception("Failed to close Redis")
        items = list(self.luminaires.items())
        for ip, writer in items:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                log.exception("Failed to close writer for %s", ip)
        self.luminaires.clear()
        log.info("stopped LuminaireSerivce")