import asyncio
import logging
import json
import socket

from utilities.ack_parser import parse_ACK

log = logging.getLogger(__name__)

class TCPServer:
    def __init__(
        self,
        host,
        port,
        service,
        keepalive_enabled=True,
        keepalive_idle_s=5,
        keepalive_interval_s=2,
        keepalive_count=3,
    ):
        self.host = host
        self.port = port
        self.service = service
        self.keepalive_enabled = keepalive_enabled
        self.keepalive_idle_s = keepalive_idle_s
        self.keepalive_interval_s = keepalive_interval_s
        self.keepalive_count = keepalive_count

    def _configure_keepalive(self, writer):
        if not self.keepalive_enabled:
            return

        sock = writer.get_extra_info("socket")
        if sock is None:
            log.warning("unable to configure keepalive: socket unavailable")
            return

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self.keepalive_idle_s)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self.keepalive_interval_s)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self.keepalive_count)
            log.info(
                "tcp keepalive configured idle=%ss interval=%ss count=%s",
                self.keepalive_idle_s,
                self.keepalive_interval_s,
                self.keepalive_count,
            )
        except Exception as exc:
            log.warning("failed to configure tcp keepalive: %s", exc)

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        log.info(f"connection request from:{peer}")
        self._configure_keepalive(writer)
        await self.service.register(peer[0], writer)
        buffer = ""
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    log.info(f"client {peer} closed the connection")
                    break
                buffer += data.decode(errors="ignore")
                while "#" in buffer:
                    message, buffer = buffer.split("#", 1)
                    message += "#"
                    log.info(f"Recv from {peer[0]}: {message}")
                    parsed_ack = parse_ACK(message)
                    if parsed_ack:
                        await self.service.publish_ack(peer[0], parsed_ack["cw"], parsed_ack["ww"])
        except Exception as e:
            log.exception(f"failed to handle connection from {peer}")
        finally:
                await self.service.unregister(peer[0])

    async def start(self):
        try:
            server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )
            self.server = server
            log.info(f"TCP server listening on {self.host}:{self.port}")
            async with server:
                await server.serve_forever()
        except Exception as e:
            log.exception(f"failed to start tcp server with error: {e}")

    async def stop(self):
        log.info("stopping TCP server...")
        if not hasattr(self, "server") or self.server is None:
            log.info("TCP server was not started")
            return
        self.server.close()
        await self.server.wait_closed()
        log.info("stopped TCP server")
