import logging
import httpx
import structlog

logging.getLogger("httpx").setLevel(logging.WARNING)

log = structlog.get_logger()

class LuminaireClient:
    def __init__(
        self,
        luminaire_service_url: str,
        timeout: float = 0.9,
    ):
        self.url = luminaire_service_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        await self._client.aclose()
        log.info("luminaire_client_closed")

    async def send(self, cw: float, ww: float):
        payload = {
            "cw": cw,
            "ww": ww,
        }

        try:
            response = await self._client.post(self.url, json=payload)
            if response.status_code == 200:
                log.debug("luminaire_command_sent_success", cw=cw, ww=ww)
            else:
                log.warning("luminaire_service_http_error", status_code=response.status_code, cw=cw, ww=ww)
        except httpx.RequestError as e:
            log.error("luminaire_service_transport_error", error=str(e), cw=cw, ww=ww, exc_info=False)