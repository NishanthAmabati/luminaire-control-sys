import asyncio
import logging
import json
import socket

from utilities.ack_parser import parse_ACK

# using a specific name for easier filtering in grafana/loki
log = logging.getLogger("services.tcp_server")

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
        tcp_user_timeout_ms=3000,
    ):
        self.host = host
        self.port = port
        self.service = service
        self.keepalive_enabled = keepalive_enabled
        self.keepalive_idle_s = keepalive_idle_s
        self.keepalive_interval_s = keepalive_interval_s
        self.keepalive_count = keepalive_count
        self.tcp_user_timeout_ms = tcp_user_timeout_ms

    def _configure_keepalive(self, writer):
        if not self.keepalive_enabled:
            log.debug("tcp keepalive disabled by configuration")
            return

        sock = writer.get_extra_info("socket")
        if sock is None:
            log.warning("unable to configure keepalive: socket unavailable")
            return

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # configuring os-specific socket options
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self.keepalive_idle_s)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self.keepalive_interval_s)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self.keepalive_count)
            if hasattr(socket, "TCP_USER_TIMEOUT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, self.tcp_user_timeout_ms)
            
            log.debug(
                f"tcp socket configured idle {self.keepalive_idle_s}s "
                f"interval {self.keepalive_interval_s}s "
                f"count {self.keepalive_count} "
                f"user_timeout {self.tcp_user_timeout_ms}ms"
            )
        except Exception as exc:
            log.warning(f"failed to configure tcp keepalive {str(exc).lower()}")

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        ip = peer[0] if peer else "unknown"
        
        log.info(f"new connection request from {ip}")
        
        self._configure_keepalive(writer)
        await self.service.register(ip, writer)
        
        buffer = ""
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    log.info(f"client {ip} closed the connection")
                    break
                
                buffer += data.decode(errors="ignore")
                
                # process messages delimited by '#'
                while "#" in buffer:
                    message, buffer = buffer.split("#", 1)
                    message += "#"
                    
                    log.debug(f"recv from {ip}: {message}")
                    
                    parsed_ack = parse_ACK(message)
                    if parsed_ack:
                        log.debug(f"parsed ack for {ip} cw {parsed_ack['cw']} ww {parsed_ack['ww']}")
                        await self.service.publish_ack(ip, parsed_ack["cw"], parsed_ack["ww"])
                    else:
                        log.warning(f"received malformed ack from {ip}: {message}")
                        
        except Exception:
            log.exception(f"critical failure handling connection from {ip}")
        finally:
            log.debug(f"cleaning up connection for {ip}")
            await self.service.unregister(ip)

    async def start(self):
        try:
            server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )
            self.server = server
            log.info(f"tcp server listening on {self.host}:{self.port}")
            async with server:
                await server.serve_forever()
        except Exception:
            log.exception(f"failed to start tcp server on {self.host}:{self.port}")

    async def stop(self):
        log.info("stopping tcp server")
        if not hasattr(self, "server") or self.server is None:
            log.debug("tcp server stop requested but server instance not found")
            return
        
        self.server.close()
        await self.server.wait_closed()
        log.info("tcp server stopped successfully")