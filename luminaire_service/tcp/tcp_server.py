import asyncio
import logging
import json

from utilities.ack_parser import parse_ACK

log = logging.getLogger(__name__)

class TCPServer:
    def __init__(self, host, port, service):
        self.host = host
        self.port = port
        self.service = service

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        log.info(f"connection request from:{peer}")
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
        self.server.close()
        await self.server.wait_closed()
        log.info("stopped TCP server")
