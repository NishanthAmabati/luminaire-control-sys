import asyncio
import logging
import json

from redis.asyncio import Redis
from utilities.command_builder import CommandBuilder
from typing import Dict

# using a named logger for better filtering in loki
log = logging.getLogger("services.luminaire_service")

class LuminaireService:
    def __init__(self, redisURL, channel):
        self.luminaires: Dict[str, dict] = {} 
        self._tasks = set()  
        self.redis = Redis.from_url(redisURL)
        self.channel = channel
        log.info(f"luminaire service initialized on channel {channel}")

    async def health(self):
        status = {
            "status": "healthy",
            "tcp": "up",
            "redis": "connected"
        }
        try:
            await self.redis.ping()
        except Exception as e:
            log.error(f"redis health check failed {str(e).lower()}")
            status["redis"] = "failed"
            status["status"] = "unhealthy"
        return status

    async def register(self, ip: str, writer: asyncio.StreamWriter):
        self.luminaires[ip] = {
            "writer": writer,
            "ip34": CommandBuilder.extract_ip34(ip)
        }
        log.info(f"accepted connection from {ip}")
        try:
            payload = {"event": "connection", "ip": ip}
            await self.redis.publish(self.channel, json.dumps(payload))
            log.debug(f"connection event for {ip} published to redis")
        except Exception:
            log.exception(f"failed to publish connection event for {ip}")

    async def unregister(self, ip: str):
        entry = self.luminaires.pop(ip, None)
        if not entry:
            log.debug(f"attempted to unregister unknown ip {ip}")
            return

        writer = entry.get("writer")
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
                log.info(f"disconnected and closed writer for {ip}")
            except Exception:
                log.exception(f"error closing writer for {ip}")

        try:
            payload = {"event": "disconnection", "ip": ip}
            await self.redis.publish(self.channel, json.dumps(payload))
            log.debug(f"disconnection event for {ip} published to redis")
        except Exception:
            log.exception(f"failed to publish disconnection event for {ip}")

    async def list_luminaires(self):
        ips = list(self.luminaires.keys())
        log.debug(f"active luminaires count {len(ips)}")
        return ips

    async def send_luminaire(self, ip: str, command: str):
        if not self.luminaires:
            log.warning("no luminaires connected to send command")
            return

        entry = self.luminaires.get(ip)
        if not entry:
            log.error(f"target luminaire {ip} not found in registry")
            return

        try:
            writer = entry["writer"]
            writer.write(command.encode())
            await writer.drain()
            log.info(f"command sent to {ip}")
            log.debug(f"raw command string {command}")
        except Exception:
            log.exception(f"failed to write to luminaire {ip}")

    async def _drain_one(self, ip, writer):
        try:
            await writer.drain()
            log.debug(f"drain successful for {ip}")
        except Exception:
            log.error(f"drain failed for {ip} - unregistering")
            await self.unregister(ip)

    async def send_luminaires(self, cw: float, ww: float):
        if not self.luminaires:
            log.debug("broadcast skipped - no luminaires connected")
            return

        cw_ww = CommandBuilder.build_cw_ww(cw, ww)
        log.info(f"broadcasting values cw {cw} ww {ww}")
        
        for ip, entry in self.luminaires.items():
            writer = entry["writer"]
            ip34 = entry["ip34"]
            try:
                command = CommandBuilder.build_command(ip34, cw_ww)
                writer.write(command.encode())
                
                # track background tasks safely
                task = asyncio.create_task(self._drain_one(ip, writer))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                
            except Exception:
                log.exception(f"failed to queue broadcast for {ip}")
        
        log.debug(f"broadcast command string {cw_ww} sent to {len(self.luminaires)} devices")
    
    async def publish_ack(self, ip: str, cw: float, ww: float):
        try:
            payload = {
                "event": "ack",
                "ip": ip,
                "cw": cw,
                "ww": ww
            }
            await self.redis.publish(self.channel, json.dumps(payload))
            log.debug(f"ack published for {ip} with cw {cw} ww {ww}")
        except Exception:
            log.exception(f"failed to publish ack for {ip}")

    async def shutdown(self):
        log.info("shutting down luminaire service")
        
        # cancel pending drain tasks
        if self._tasks:
            log.debug(f"cancelling {len(self._tasks)} pending drain tasks")
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        # close redis
        try:
            await self.redis.close()
            log.info("redis connection closed")
        except Exception:
            log.exception("error during redis shutdown")

        # close all active sockets
        for ip in list(self.luminaires.keys()):
            await self.unregister(ip)
            
        log.info("luminaire service stopped")