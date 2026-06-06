import asyncio
import socket
import structlog
from utilities.ack_parser import parse_ACK

log = structlog.get_logger()

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
        self.server = None

    def _configure_keepalive(self, writer, logger):
        if not self.keepalive_enabled:
            return

        sock = writer.get_extra_info("socket")
        if sock is None:
            logger.warning("keepalive_config_skipped_socket_unavailable")
            return

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Linux-specific constants
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self.keepalive_idle_s)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self.keepalive_interval_s)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self.keepalive_count)
            if hasattr(socket, "TCP_USER_TIMEOUT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, self.tcp_user_timeout_ms)
            
            logger.debug("tcp_keepalive_configured", 
                         idle=self.keepalive_idle_s, 
                         interval=self.keepalive_interval_s, 
                         timeout=self.tcp_user_timeout_ms)
        except Exception as e:
            logger.error("keepalive_config_failed", error=str(e))

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        ip = peer[0]
        client_log = log.bind(ip=ip)
        
        client_log.info("connection_received")
        self._configure_keepalive(writer, client_log)
        await self.service.register(ip, writer)
        
        buffer = ""
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    client_log.info("connection_closed_by_client")
                    break
                
                buffer += data.decode(errors="ignore")
                while "#" in buffer:
                    message, buffer = buffer.split("#", 1)
                    message += "#"
                    
                    parsed_ack = parse_ACK(message)
                    if parsed_ack:
                        await self.service.publish_ack(ip, parsed_ack["cw"], parsed_ack["ww"])
        except Exception:
            client_log.error("handle_client_error", exc_info=True)
        finally:
            await self.service.unregister(ip)

    async def start(self):
        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )
            log.info("tcp_server_listening", host=self.host, port=self.port)
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            log.critical("tcp_server_start_failed", error=str(e), exc_info=True)

    async def stop(self):
        log.info("tcp_server_shutdown_initiated")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            log.info("tcp_server_stopped")